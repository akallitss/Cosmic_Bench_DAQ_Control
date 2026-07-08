#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hv_trainer_service.py

Detector HV conditioning ("training") service. Ramps each configured
detector's train channel (mesh) toward its target voltage using the soft
back-off TrainingController from hv_trainer_controller.py, while holding the
detector's fixed channels (drift) at user-set voltages. Runs independently of
the DAQ in its own tmux session, with its own CAEN crate session.

Outputs (masquerading as a run so all existing HV viewers work unchanged):
  <base_dir>/<run_name>/<sub_run_name>/hv_monitor.csv       same schema as hv_control
  <base_dir>/<run_name>/<sub_run_name>/hv_trainer_events.csv BACKOFF/STEP_UP/KILL/DONE log
  config/json_run_configs/<run_name>.json                    run-shaped -> Flask HV tab
  config/hv_trainer_state.json                               live heartbeat/state

Usage:
  python hv_trainer_service.py config/hv_trainer_config.json [--dry-run] [--force]

  --dry-run  full loop against the crate READ-ONLY: no power/voltage commands,
             prints what it would do. First live-hardware test mode.
  --force    proceed even if involved channels are already powered (e.g. when
             restarting the trainer over a session that is still biased).

Stop with SIGINT/SIGTERM (stop_hv_trainer.sh sends C-c) — the service then
applies its on_finish policy and exits cleanly. Do NOT tmux kill-session first.

See docs/hv_trainer_implementation_plan.md.
"""

import argparse
import csv
import json
import os
import signal
import sys
import time
from datetime import datetime

from hv_trainer_controller import TrainerConfig, TrainingController


RAMP_TOL = 1.5        # V — consider ramped when |vmon - v0| below this (as set_hvs)
RAMP_TIMEOUT = 900.0  # s — give up waiting for initial ramp, proceed with warning
PUSH_TOL = 0.5        # V — push set_ch_v0 when commanded vset moved more than this
MAX_CONSEC_ERRORS = 5  # consecutive crate comm failures before on_error exit
POWERED_V = 30.0      # V — a channel above this at startup counts as "in use"


def now_stamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


class DetectorSession:
    """Per-detector training state wrapped around one TrainingController."""

    def __init__(self, det_cfg, session_cfg):
        self.name = det_cfg['name']
        self.train = det_cfg['train']          # {'label','slot','ch'}
        self.fixed = det_cfg['fixed']          # [{'label','slot','ch','v'}, ...]
        self.v_start = float(det_cfg['v_start'])
        self.ctrl_cfg = TrainerConfig(**det_cfg['controller'])
        self.ctrl = TrainingController(self.ctrl_cfg, vset=self.v_start)
        self.session_cfg = session_cfg
        self.status = 'TRAINING'   # TRAINING | TRAINED | PLATEAU | STALLED | STOPPED | TIMEOUT | ERROR
        self.state = 'HOLD'        # last controller state (or KILL)
        self.last_pushed = None    # last vset actually sent to the crate
        self.best_held_v = self.v_start
        self.last_improve_mono = None
        self.quiet_at_target_run = 0.0
        self.kills = {}            # (slot, ch) -> re-enable count
        self.n_backoffs = 0
        self.started_mono = None
        self.vmon = None
        self.imon = None

    def channels(self):
        chans = [(self.train['slot'], self.train['ch'])]
        chans += [(f['slot'], f['ch']) for f in self.fixed]
        return chans

    def finished(self):
        return self.status != 'TRAINING'


class TrainerService:
    def __init__(self, config, dry_run=False, force=False):
        self.config = config
        self.dry_run = dry_run
        self.force = force
        self.session_cfg = config['session']
        self.poll = float(config.get('poll', 2.0))
        self.dets = [DetectorSession(d, self.session_cfg)
                     for d in config['detectors']]
        self.stop_requested = False
        self.consec_errors = 0
        self.caen = None
        self.started = None
        self.started_mono = None

        out = config['out']
        self.run_name = out['run_name']
        self.sub_run_name = out['sub_run_name']
        self.run_out_dir = os.path.join(out['base_dir'], self.run_name)
        self.sub_run_dir = os.path.join(self.run_out_dir, self.sub_run_name)
        base = os.path.dirname(os.path.abspath(__file__))
        self.run_json_path = os.path.join(
            base, config['json_run_config_dir'], self.run_name + '.json')
        self.state_json_path = os.path.join(base, config['state_json'])
        self.monitor_csv_path = os.path.join(self.sub_run_dir, 'hv_monitor.csv')
        self.events_csv_path = os.path.join(self.sub_run_dir, 'hv_trainer_events.csv')
        self._monitor_csv = None
        self._monitor_writer = None
        self._events_csv = None
        self._events_writer = None

    # ------------------------------------------------------------------ #
    # I/O plumbing
    # ------------------------------------------------------------------ #
    def all_channels(self):
        chans = []
        for det in self.dets:
            for sc in det.channels():
                if sc not in chans:
                    chans.append(sc)
        return chans

    def open_outputs(self):
        os.makedirs(self.sub_run_dir, exist_ok=True)
        headers = ['timestamp']
        for slot, ch in self.all_channels():
            prefix = '{}:{}'.format(slot, ch)
            headers.extend([prefix + ' power', prefix + ' v0',
                            prefix + ' vmon', prefix + ' imon'])
        self._monitor_csv = open(self.monitor_csv_path, 'w', newline='')
        self._monitor_writer = csv.writer(self._monitor_csv)
        self._monitor_writer.writerow(headers)
        self._monitor_csv.flush()

        self._events_csv = open(self.events_csv_path, 'w', newline='')
        self._events_writer = csv.writer(self._events_csv)
        self._events_writer.writerow(
            ['timestamp', 'detector', 'channel', 'kind', 'vset', 'imon', 'note'])
        self._events_csv.flush()

        self.write_run_json()

    def write_run_json(self, training_result=None):
        # Keep sub_runs from previous sessions of the same run (e.g. a
        # restart under a new sub_run_name) visible in the Flask HV tab.
        sub_runs = [{'sub_run_name': self.sub_run_name}]
        try:
            with open(self.run_json_path) as f:
                for sr in json.load(f).get('sub_runs', []):
                    if sr.get('sub_run_name') != self.sub_run_name:
                        sub_runs.append(sr)
        except (IOError, OSError, ValueError):
            pass
        run_json = {
            'run_name': self.run_name,
            'run_out_dir': self.run_out_dir,
            'sub_runs': sub_runs,
            'hv_trainer': True,
        }
        if training_result is not None:
            run_json['training_result'] = training_result
        with open(self.run_json_path, 'w') as f:
            json.dump(run_json, f, indent=2)

    def log_event(self, det_name, channel, kind, vset, imon, note=''):
        stamp = now_stamp()
        self._events_writer.writerow(
            [stamp, det_name, channel, kind,
             '' if vset is None else '{:.1f}'.format(vset),
             '' if imon is None else '{:.3f}'.format(imon), note])
        self._events_csv.flush()
        print('{} [{}] {} {} vset={} imon={} {}'.format(
            stamp, det_name, channel, kind, vset, imon, note))

    def write_state(self, active=True):
        state = {
            'pid': os.getpid(),
            'active': active,
            'dry_run': self.dry_run,
            'run_name': self.run_name,
            'started': self.started,
            'updated': now_stamp(),
            'poll': self.poll,
            'detectors': {},
        }
        for det in self.dets:
            state['detectors'][det.name] = {
                'status': det.status,
                'state': det.state,
                'train_channel': '{}:{}'.format(det.train['slot'], det.train['ch']),
                'vset': det.ctrl.vset,
                'vmon': det.vmon,
                'imon': det.imon,
                'n_backoffs': det.n_backoffs,
                'best_held_v': det.best_held_v,
                'kills': sum(det.kills.values()),
            }
        tmp = self.state_json_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_json_path)

    # ------------------------------------------------------------------ #
    # Crate helpers (every write goes through these; dry-run = no-ops)
    # ------------------------------------------------------------------ #
    def set_v0(self, slot, ch, v):
        if self.dry_run:
            print('  [dry-run] would set_ch_v0({}, {}, {:.1f})'.format(slot, ch, v))
            return
        self.caen.set_ch_v0(int(slot), int(ch), float(v))

    def set_power(self, slot, ch, on):
        if self.dry_run:
            print('  [dry-run] would set_ch_pw({}, {}, {})'.format(slot, ch, int(on)))
            return
        self.caen.set_ch_pw(int(slot), int(ch), int(on))

    def read_channel(self, slot, ch):
        power = self.caen.get_ch_power(int(slot), int(ch))
        vmon = self.caen.get_ch_vmon(int(slot), int(ch))
        imon = self.caen.get_ch_imon(int(slot), int(ch))
        return power, vmon, imon

    # ------------------------------------------------------------------ #
    # Startup
    # ------------------------------------------------------------------ #
    def startup_check(self):
        busy = []
        for slot, ch in self.all_channels():
            power, vmon, _ = self.read_channel(slot, ch)
            if power and vmon > POWERED_V:
                busy.append('{}:{} (vmon {:.0f} V)'.format(slot, ch, vmon))
        if busy and not self.force:
            raise RuntimeError(
                'Channels already powered: {} — is something else using them? '
                'Re-run with --force to take them over.'.format(', '.join(busy)))
        if busy:
            self.log_event('-', '-', 'FORCED_START', None, None,
                           'taking over powered channels: ' + ', '.join(busy))

    def power_up(self):
        """Command fixed voltages + v_start on train channels, wait for ramp.
        A channel that trips (power drops) during the ramp stalls its detector
        immediately instead of blocking the wait until RAMP_TIMEOUT."""
        targets = {}   # (slot, ch) -> (det, target_v)
        for det in self.dets:
            tr = det.train
            self.set_v0(tr['slot'], tr['ch'], det.v_start)
            det.last_pushed = det.v_start
            targets[(tr['slot'], tr['ch'])] = (det, det.v_start)
            for fx in det.fixed:
                self.set_v0(fx['slot'], fx['ch'], fx['v'])
                targets[(fx['slot'], fx['ch'])] = (det, fx['v'])
        for slot, ch in targets:
            power, _, _ = self.read_channel(slot, ch)
            if not power:
                self.set_power(slot, ch, 1)
        self.log_event('-', '-', 'RAMP_START', None, None,
                       '; '.join('{}:{}->{:.0f}V'.format(s, c, v)
                                 for (s, c), (_, v) in sorted(targets.items())))
        if self.dry_run:
            return
        t0 = time.monotonic()
        while not self.stop_requested:
            readings = self.log_monitor_row()
            pending = []
            for (slot, ch), (det, v) in targets.items():
                if det.finished():
                    continue
                power, vmon, imon = readings[(slot, ch)]
                if not power:
                    self.log_event(det.name, '{}:{}'.format(slot, ch),
                                   'RAMP_TRIP', v, imon,
                                   'channel tripped during initial ramp')
                    self.finish_detector(det, 'STALLED', on_error=True)
                elif abs(vmon - v) > RAMP_TOL:
                    pending.append('{}:{} {:.1f}->{:.0f}'.format(slot, ch, vmon, v))
            self.write_state()
            if all(det.finished() for det in self.dets):
                return
            if not pending:
                self.log_event('-', '-', 'RAMP_DONE', None, None, '')
                return
            if time.monotonic() - t0 > RAMP_TIMEOUT:
                self.log_event('-', '-', 'RAMP_TIMEOUT', None, None,
                               'still pending: ' + ', '.join(pending))
                return
            print('Waiting for ramp: ' + ', '.join(pending))
            time.sleep(self.poll)

    # ------------------------------------------------------------------ #
    # Main loop pieces
    # ------------------------------------------------------------------ #
    def log_monitor_row(self):
        row = [now_stamp()]
        readings = {}
        commanded = {}
        for det in self.dets:
            tr = det.train
            commanded[(tr['slot'], tr['ch'])] = det.ctrl.vset
            for fx in det.fixed:
                commanded[(fx['slot'], fx['ch'])] = fx['v']
        for slot, ch in self.all_channels():
            power, vmon, imon = self.read_channel(slot, ch)
            readings[(slot, ch)] = (power, vmon, imon)
            row.extend([int(power), commanded.get((slot, ch), ''), vmon, imon])
        self._monitor_writer.writerow(row)
        self._monitor_csv.flush()
        return readings

    def handle_kill(self, det, slot, ch, label, imon):
        """A channel we believe should be on reads power=0: crate kill (or a
        manual off). Re-enable within budget, else stall the detector."""
        key = (slot, ch)
        det.kills[key] = det.kills.get(key, 0) + 1
        budget = int(self.session_cfg.get('crate_kill_reenable', 2))
        chan_str = '{}:{}'.format(slot, ch)
        if det.kills[key] <= budget:
            if label == 'train':
                # Back off before re-biasing: the kill happened at high current.
                det.ctrl.vset = max(det.ctrl.vset - det.ctrl_cfg.v_step_down,
                                    det.ctrl_cfg.v_floor)
            self.log_event(det.name, chan_str, 'KILL_REENABLE', det.ctrl.vset, imon,
                           '{}/{} re-enables used'.format(det.kills[key], budget))
            if label == 'train':
                self.set_v0(slot, ch, det.ctrl.vset)
                det.last_pushed = det.ctrl.vset
            self.set_power(slot, ch, 1)
            det.state = 'KILL'
        else:
            self.log_event(det.name, chan_str, 'KILL_STALLED', det.ctrl.vset, imon,
                           're-enable budget exhausted')
            self.finish_detector(det, 'STALLED', on_error=True)

    def finish_detector(self, det, status, on_error=False):
        det.status = status
        policy = (self.session_cfg.get('on_error', 'standby:250') if on_error
                  else self.session_cfg.get('on_finish', 'hold'))
        tr = det.train
        chan_str = '{}:{}'.format(tr['slot'], tr['ch'])
        try:
            if policy == 'hold':
                # PLATEAU means the detector never held above best_held_v —
                # the current vset may be a probing step into the sparking
                # region, so park at the proven voltage instead.
                if status == 'PLATEAU' and det.ctrl.vset > det.best_held_v:
                    det.ctrl.vset = det.best_held_v
                    self.set_v0(tr['slot'], tr['ch'], det.best_held_v)
                    det.last_pushed = det.best_held_v
            elif policy.startswith('standby:'):
                v = float(policy.split(':', 1)[1])
                det.ctrl.vset = v
                self.set_v0(tr['slot'], tr['ch'], v)
                det.last_pushed = v
            elif policy == 'off':
                self.set_power(tr['slot'], tr['ch'], 0)
        except Exception as e:
            print('WARNING: {} policy {} failed: {}'.format(det.name, policy, e))
        dur_min = ((time.monotonic() - det.started_mono) / 60.0
                   if det.started_mono else 0.0)
        self.log_event(
            det.name, chan_str, 'DONE', det.ctrl.vset, det.imon,
            '{}; best_held={:.0f}V; backoffs={}; kills={}; {:.0f} min; policy={}'.format(
                status, det.best_held_v, det.n_backoffs,
                sum(det.kills.values()), dur_min, policy))

    def step_detector(self, det, readings, dt, mono_now):
        tr = det.train
        power, vmon, imon = readings[(tr['slot'], tr['ch'])]
        det.vmon, det.imon = vmon, imon

        if not power:
            if self.dry_run:  # can't power on in dry-run; don't spam KILL
                det.state = 'OFF'
                return
            self.handle_kill(det, tr['slot'], tr['ch'], 'train', imon)
            return
        for fx in det.fixed:
            fpower, _, fimon = readings[(fx['slot'], fx['ch'])]
            if not fpower and not self.dry_run:
                self.handle_kill(det, fx['slot'], fx['ch'], fx['label'], fimon)
                if det.finished():
                    return

        vset_before = det.ctrl.vset
        n_events_before = len(det.ctrl.events)
        vset, state = det.ctrl.step(now_stamp(), imon, dt)
        det.state = state

        for ev in det.ctrl.events[n_events_before:]:
            t_ev, kind, v_ev, i_ev = ev
            if kind == 'BACKOFF':
                det.n_backoffs += 1
            self.log_event(det.name, '{}:{}'.format(tr['slot'], tr['ch']),
                           kind, v_ev, i_ev)

        if state == 'RAMP_UP' and vset_before > det.best_held_v:
            det.best_held_v = vset_before
            det.last_improve_mono = mono_now

        if det.last_pushed is None or abs(vset - det.last_pushed) > PUSH_TOL:
            self.set_v0(tr['slot'], tr['ch'], vset)
            det.last_pushed = vset

        cfg = det.ctrl_cfg
        at_target = vset >= cfg.v_target - PUSH_TOL
        if at_target and imon < cfg.i_safe:
            det.quiet_at_target_run += dt
        else:
            det.quiet_at_target_run = 0.0
        if det.quiet_at_target_run >= self.session_cfg['success_hold_min'] * 60.0:
            det.best_held_v = cfg.v_target
            self.finish_detector(det, 'TRAINED')
            return

        plateau_s = self.session_cfg['plateau_window_min'] * 60.0
        if (not at_target and det.last_improve_mono is not None
                and mono_now - det.last_improve_mono > plateau_s):
            self.finish_detector(det, 'PLATEAU')

    # ------------------------------------------------------------------ #
    def training_result(self):
        return {
            det.name: {
                'status': det.status,
                'best_held_v': det.best_held_v,
                'final_vset': det.ctrl.vset,
                'v_target': det.ctrl_cfg.v_target,
                'n_backoffs': det.n_backoffs,
                'kills': sum(det.kills.values()),
            }
            for det in self.dets
        }

    def run(self):
        from caen_hv_py.CAENHVController import CAENHVController

        def on_signal(signum, frame):
            print('Signal {} received — shutting down after this cycle.'.format(signum))
            self.stop_requested = True
        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

        self.started = now_stamp()
        self.started_mono = time.monotonic()
        self.open_outputs()
        hv = self.config['hv']
        max_s = self.session_cfg['max_hours'] * 3600.0

        print('HV trainer starting (dry_run={}): run {}'.format(
            self.dry_run, self.run_name))
        for det in self.dets:
            print('  {}: train {}:{} {}V -> {}V; fixed {}'.format(
                det.name, det.train['slot'], det.train['ch'], det.v_start,
                det.ctrl_cfg.v_target,
                ', '.join('{}:{}@{:.0f}V'.format(f['slot'], f['ch'], f['v'])
                          for f in det.fixed)))

        with CAENHVController(hv['ip'], hv['username'], hv['password']) as caen:
            self.caen = caen
            self.write_state()  # heartbeat exists from the very start (ramp incl.)
            self.startup_check()
            self.power_up()
            for det in self.dets:
                det.started_mono = time.monotonic()
                det.last_improve_mono = time.monotonic()
            self.write_state()

            last_mono = time.monotonic()
            next_tick = time.monotonic()
            while not self.stop_requested:
                next_tick += self.poll
                mono_now = time.monotonic()
                dt = mono_now - last_mono
                last_mono = mono_now
                try:
                    readings = self.log_monitor_row()
                    for det in self.dets:
                        if not det.finished():
                            self.step_detector(det, readings, dt, mono_now)
                    self.consec_errors = 0
                except Exception as e:
                    self.consec_errors += 1
                    print('ERROR ({}/{}): {}'.format(
                        self.consec_errors, MAX_CONSEC_ERRORS, e))
                    if self.consec_errors >= MAX_CONSEC_ERRORS:
                        self.log_event('-', '-', 'ERROR', None, None, str(e))
                        for det in self.dets:
                            if not det.finished():
                                self.finish_detector(det, 'ERROR', on_error=True)
                        break
                self.write_state()

                if all(det.finished() for det in self.dets):
                    print('All detectors finished.')
                    break
                if mono_now - self.started_mono > max_s:
                    self.log_event('-', '-', 'TIMEOUT', None, None,
                                   'max_hours={} reached'.format(
                                       self.session_cfg['max_hours']))
                    for det in self.dets:
                        if not det.finished():
                            self.finish_detector(det, 'TIMEOUT')
                    break

                sleep_s = next_tick - time.monotonic()
                if sleep_s > 0:
                    time.sleep(sleep_s)
                else:
                    next_tick = time.monotonic()

            if self.stop_requested:
                for det in self.dets:
                    if not det.finished():
                        self.finish_detector(det, 'STOPPED')

            result = self.training_result()
            self.write_run_json(training_result=result)
            self.write_state(active=False)
            print('\n=== Training session summary ===')
            for name, r in result.items():
                print('  {}: {} — best held {:.0f} V (target {:.0f} V), '
                      '{} backoffs, {} kills'.format(
                          name, r['status'], r['best_held_v'], r['v_target'],
                          r['n_backoffs'], r['kills']))
        print('donzo')


def main():
    ap = argparse.ArgumentParser(description='HV conditioning (training) service.')
    ap.add_argument('config', help='path to hv_trainer_config.json')
    ap.add_argument('--dry-run', action='store_true',
                    help='read-only against the crate; no power/voltage commands')
    ap.add_argument('--force', action='store_true',
                    help='start even if involved channels are already powered')
    args = ap.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    for det in config['detectors']:
        ctrl = det['controller']
        trip = ctrl.get('caen_trip_time', 30.0)
        if ctrl['backoff_after'] > trip / 3:
            sys.exit('{}: backoff_after {} s not well below crate TRIP {} s'.format(
                det['name'], ctrl['backoff_after'], trip))

    TrainerService(config, dry_run=args.dry_run, force=args.force).run()


if __name__ == '__main__':
    main()
