#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hv_trainer_config.py

Config generator for the HV trainer service, following the repo's
config-generator pattern (processor_config.py, qa_config.py): edit the
session definition below, run this script, and it writes
config/hv_trainer_config.json for hv_trainer_service.py.

Safety: refuses to write a config whose v_target exceeds the per-detector-type
v_ceiling, or whose backoff_after is not well below the crate TRIP time.

See docs/hv_trainer_implementation_plan.md.
"""

import json
import os

# Max mesh voltage we ever allow the trainer to be configured for, per
# detector type. A config asking beyond this is refused outright.
V_CEILINGS = {
    'P2': 520.0,
}

CAEN_TRIP_TIME = 30.0  # crate OVC->kill time [s]; backoff_after must be << this


def build_config():
    # ------------------------------------------------------------------ #
    # Session: train P2 det 1 + det 2 mesh channels together (2026-07-08).
    # Channels from run_config.py P2_1 hv_channels + bench cabling for det 2
    # (P2_2 not yet in run_config detectors): det 1 mesh 1:0 / drift 1:1,
    # det 2 mesh 1:2 / drift 1:3. Drifts held fixed at 550 V, mesh trained
    # to 500 V from a gentle 300 V entry point.
    # ------------------------------------------------------------------ #
    controller = dict(
        i_comp=10.0, i_comp_frac=0.95, i_safe=2.0,
        v_target=500.0,
        v_floor=250.0,          # never command below (keeps detector biased)
        v_step_up=5.0, v_step_down=25.0,
        dwell=60.0, recover_dwell=60.0,
        backoff_after=6.0,      # << crate TRIP = 30 s
        caen_trip_time=CAEN_TRIP_TIME,
    )
    config = {
        'detectors': [
            {
                'name': 'P2_1',
                'det_type': 'P2',
                'train': {'label': 'mesh', 'slot': 1, 'ch': 0},
                'fixed': [{'label': 'drift', 'slot': 1, 'ch': 1, 'v': 550.0}],
                'controller': dict(controller),
                'v_start': 300.0,
            },
            {
                'name': 'P2_2',
                'det_type': 'P2',
                'train': {'label': 'mesh', 'slot': 1, 'ch': 2},
                'fixed': [{'label': 'drift', 'slot': 1, 'ch': 3, 'v': 550.0}],
                'controller': dict(controller),
                'v_start': 300.0,
            },
        ],
        'hv': {
            'ip': '192.168.10.81',
            'username': 'admin',
            'password': 'admin',
        },
        'out': {
            'base_dir': '/mnt/cosmic_data/P2/Run',
            'run_name': 'hv_training_p2_det1_det2_7-8-26',
            'sub_run_name': 'train_mesh500V_drift550V',
        },
        'json_run_config_dir': 'config/json_run_configs',
        'state_json': 'config/hv_trainer_state.json',
        'poll': 2.0,
        'session': {
            'max_hours': 8.0,
            'success_hold_min': 45.0,  # at v_target, imon quiet this long -> TRAINED
            'plateau_window_min': 90.0,  # best-held V stagnant this long -> PLATEAU
            'on_finish': 'hold',       # hold | standby:<V> | off
            'on_error': 'standby:250',
            'crate_kill_reenable': 2,  # auto re-enables per channel, then STALLED
        },
    }
    return config


def validate(config):
    for det in config['detectors']:
        ctrl = det['controller']
        ceiling = V_CEILINGS.get(det['det_type'])
        if ceiling is None:
            raise ValueError(f"{det['name']}: no v_ceiling defined for det_type "
                             f"'{det['det_type']}' — add it to V_CEILINGS")
        if ctrl['v_target'] > ceiling:
            raise ValueError(f"{det['name']}: v_target {ctrl['v_target']} V exceeds "
                             f"{det['det_type']} ceiling {ceiling} V — refusing")
        if ctrl['backoff_after'] > CAEN_TRIP_TIME / 3:
            raise ValueError(f"{det['name']}: backoff_after {ctrl['backoff_after']} s "
                             f"not well below crate TRIP {CAEN_TRIP_TIME} s — refusing")
        if ctrl['v_floor'] > det['v_start']:
            raise ValueError(f"{det['name']}: v_floor {ctrl['v_floor']} above "
                             f"v_start {det['v_start']}")


def main():
    config = build_config()
    validate(config)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'config', 'hv_trainer_config.json')
    with open(out_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f'HV trainer config written to {out_path}')


if __name__ == '__main__':
    main()
