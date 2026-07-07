# HV Trainer — implementation plan

**Goal**: a detector HV conditioning ("training") service on the cosmic-bench DAQ machine
(sedipcaa28) that ramps a detector toward the maximum voltage it can physically hold,
using the soft back-off controller from
`P2_basket_analysis/cosmic_bench_analysis/hv_trainer.py` instead of letting the CAEN
crate's 30 s over-current trip kill the channel. It must:

1. run **independently of the DAQ** (no daq_control / dream_daq involvement),
2. be **visible in the existing online HV monitoring** (Flask HV tab),
3. be **startable/stoppable from the Flask dashboard** like the other subsystems,
4. leave the detector in a well-defined state when it finishes or fails.

---

## 0. What already exists (reuse, don't rewrite)

| Piece | Where | Reuse |
|---|---|---|
| `TrainingController` + `TrainerConfig` — RAMP_UP / HOLD / BACKOFF state machine, pure logic, no hardware deps | analysis repo `hv_trainer.py` | copy the two classes verbatim into the DAQ repo (single file, stdlib-only) |
| `backtest_csv()` open-loop replay | analysis repo `hv_trainer.py` | stays in the analysis repo for offline parameter tuning |
| CAEN access pattern (`CAENHVController`, `set_ch_v0`, `get_ch_vmon/imon/power`, ramp-wait loop) | DAQ repo `hv_control.py` | copy the idioms; trainer opens its **own** crate session |
| `hv_monitor.csv` schema (`timestamp, <slot>:<ch> power/v0/vmon/imon, ...`) + drift-corrected write loop | `hv_control.py monitor_hvs()` | write the **identical schema** so every existing viewer works |
| Flask HV tab: `/hv_data` reads `run_out_dir/<subrun>/hv_monitor.csv` found via a JSON in `config/json_run_configs/` | `flask_app/app.py` | trainer masquerades as a "run" → **zero changes needed for plotting** |
| tmux session pattern + `start_tmux.sh` (does `unset TMUX`, needed because Flask runs inside tmux; tmux 1.8 quirk) | `bash_scripts/`, `/start_qa` endpoint | same pattern for an `hv_trainer` session |
| Detector → HV-channel mapping (`detectors[i]['hv_channels']`) | `run_config.py` | trainer config selects a detector **by name**, channels come from here |

## 1. Architecture

```
tmux "hv_trainer"                                   tmux "hv_control" (untouched)
  hv_trainer_service.py  ──caen_hv_py──► CAEN SY  ◄──caen_hv_py──  hv_control.py (DAQ runs)
        │
        ├─► /mnt/cosmic_data/<PROJ>/Run/hv_training_<det>_<M-D-YY>/train_<target>V/hv_monitor.csv
        ├─►   same dir /hv_trainer_events.csv      (BACKOFF / STEP_UP / KILL / DONE log)
        ├─► config/json_run_configs/hv_training_<det>_<M-D-YY>.json   (run-shaped → Flask HV tab)
        └─► config/hv_trainer_state.json           (live state for Flask status card + interlock)
```

- **Independent process**, own CAEN session, own tmux session. The DAQ can run
  simultaneously on *other* channels.
- The training session is written to disk exactly like a run
  (`Run/hv_training_.../<subrun>/hv_monitor.csv`), so the existing Flask HV plot, your
  `hv_live_monitor.py`, and the rsync mirror recipe all work unchanged. The trainer
  emits a minimal run-shaped JSON (`run_name`, `run_out_dir`, `sub_runs[{sub_run_name}]`)
  into `config/json_run_configs/` so the HV tab's run/subrun dropdowns list it.

## 2. New files (all in Cosmic_Bench_DAQ_Control)

### 2.1 `hv_trainer_controller.py`
Verbatim copy of `TrainerConfig` + `TrainingController` from the analysis repo
(keep the analysis copy as the backtesting home; note the provenance in the docstring).

### 2.2 `hv_trainer_config.py` → `config/hv_trainer_config.json`
Follows the repo's config-generator pattern (`processor_config.py`, `qa_config.py`).
Contents:

```python
detector = 'P2_2'            # name in run_config.py detectors list → hv_channels
train_channel = 'mesh'       # which hv_channels entry is being conditioned
linked_channels = {          # optional: channels that follow the trained one
    'drift': {'mode': 'offset', 'value': 160},   # drift = mesh + 160 V (constant gap)
    # or {'mode': 'fixed', 'value': 600}, or omit to leave untouched
}
controller = dict(           # TrainerConfig fields — start from backtested values
    i_comp=10.0, i_comp_frac=0.95, i_safe=2.0,
    v_target=470.0,          # ambition; plateau detection below finds the real max
    v_floor=250.0,           # never command below (keeps detector biased)
    v_step_up=5.0, v_step_down=25.0,
    dwell=60.0, recover_dwell=60.0, backoff_after=6.0,  # << crate TRIP=30 s
)
v_start = 300.0              # gentle entry point
poll = 2.0                   # s between crate readouts
session = dict(
    max_hours=12.0,
    success_hold_min=45.0,   # at v_target with imon<i_safe this long → TRAINED
    plateau_window_min=90.0, # if best-held V hasn't improved in this window → PLATEAU
    on_finish='hold',        # 'hold' | 'standby:<V>' | 'off'
    on_error='standby:250',  # crash/exception policy — never leave undefined
    crate_kill_reenable=2,   # auto re-enable after a real crate kill, at most N times
)
```

The generator resolves `detector` → `(slot, ch)` pairs via `run_config.Config().detectors`
(with `write_all_dectors_to_json=True` semantics so non-included detectors are found too)
and writes the JSON. **Max-voltage safety cap**: an explicit `v_ceiling` per detector
type in the generator (refuse to write a config with `v_target > v_ceiling`).

### 2.3 `hv_trainer_service.py` (the actual service)
Main loop, structured like `monitor_hvs()`:

1. Read config JSON; create out dirs; write the run-shaped JSON for the Flask HV tab.
2. Open one `CAENHVController` session for the whole run (like the monitor thread does).
3. Power on the trained + linked channels if off; command `v_start`; wait for ramp
   (reuse the `set_hvs` ramp-wait idiom, 10 s poll).
4. Every `poll` seconds:
   - read `power, v0, vmon, imon` for trained + linked channels,
   - append the `hv_monitor.csv` row (same schema/flush pattern as `monitor_hvs`),
   - `vset, state = controller.step(now, imon, dt)`; push `set_ch_v0` when it changed
     by > 0.5 V; move linked channels per their rule,
   - detect **crate kill** (power dropped to 0 while we think it's on): log `KILL`,
     re-enable per `crate_kill_reenable` budget or stop via `on_error`,
   - append any controller event to `hv_trainer_events.csv`,
   - rewrite `config/hv_trainer_state.json`: `{pid, detector, channels, state, vset,
     vmon, imon, n_backoffs, best_held_v, started, updated}` (atomic tmp+rename).
5. End conditions → `TRAINED` (target held `success_hold_min` with quiet current),
   `PLATEAU` (best held V stagnant for `plateau_window_min` → report that V as the
   detector's current physical max), `TIMEOUT`, `STOPPED` (SIGINT/SIGTERM), `ERROR`.
   All paths execute `on_finish`/`on_error`, write a final `DONE` event with the
   summary, and clear the "active" flag in the state JSON.
6. `--dry-run` flag: full loop against the crate **read-only** (no `set_ch_v0`/`set_ch_pw`),
   prints what it would command — first live-hardware test mode.

### 2.4 `bash_scripts/start_hv_trainer.sh` / `stop_hv_trainer.sh`
`start_tmux.sh hv_trainer "python hv_trainer_service.py config/hv_trainer_config.json"`;
stop sends SIGINT (tmux `C-c`) so the service runs its shutdown policy — **not**
`kill-session` (that would skip `on_finish`). `kill-session` only as a follow-up.

## 3. Flask integration (`flask_app/`)

1. `TMUX_SESSIONS += ["hv_trainer"]` — the pane/status card appears automatically.
2. `daq_status.py: get_hv_trainer_status()` — read `config/hv_trainer_state.json`:
   - no file / stale `updated` (> 3×poll) → `OFF`/`STALLED (red)`,
   - else show state (`RAMP_UP/HOLD/BACKOFF`), `vset→`, `vmon`, `imon`,
     `#backoffs`, `best_held_v`, detector name.
3. Endpoints, mirroring `/start_qa`//`/stop_qa`: `/start_hv_trainer` (regenerate config
   via `python hv_trainer_config.py`, then `start_hv_trainer.sh`), `/stop_hv_trainer`.
4. `index.html`: Start/Stop buttons next to the QA watcher's; the HV tab needs nothing —
   training sessions appear in its run dropdown via the run-shaped JSON.

## 4. Interlocks (both directions)

- **Trainer refuses to start** if the channels it wants overlap the `hvs` of the
  currently loaded run config while a run is active (reuse
  `is_dream_daq_running()` + parse `config/json_run_configs/run_config.json`).
- **`/start_run` warns/refuses** if requested `hvs` overlap `hv_trainer_state.json`
  active channels (Flask-side check; daq_control itself stays untouched in phase 1).
- Document the residual risk: nothing stops a *manual* GECO/web session from fighting
  the trainer — same as today for hv_control.

## 5. Safety review checklist (before first unattended night)

- [ ] `backoff_after` ≪ crate TRIP time on every channel involved (config assert).
- [ ] `v_ceiling` per detector enforced at config-generation *and* in the service.
- [ ] Crate concurrency verified: trainer session + hv_control monitor session
      logged in simultaneously, both reading, only one writing per channel
      (test with a DAQ run on M3 channels while trainer dry-runs on P2_2). CAEN
      SY4527 allows multiple API logins, but **verify on ours before relying on it**.
- [ ] SIGINT path proven: `stop_hv_trainer.sh` → detector at `on_finish` state.
- [ ] Network-loss behavior: caen_hv_py exception → `on_error` path (test by
      unplugging nothing — simulate with a wrong IP after start... i.e. unit-test the
      exception branch with a mock; don't improvise on the crate).
- [ ] State JSON heartbeat visible in Flask (kill -9 the service → card goes STALLED).

## 6. Rollout phases

| Phase | Content | Effort | Risk |
|---|---|---|---|
| 0 | Backtest controller params for the **new detector** against existing sparky traces (BADGAS run, old P2_1 conditioning CSVs) with `hv_trainer.py --csv`; pick `v_step_*`, `dwell`, `backoff_after` | ~1 h offline | none |
| 1 | `hv_trainer_controller.py` + `hv_trainer_config.py` + `hv_trainer_service.py` with `--dry-run`; unit-test end conditions + kill/exception branches with a mocked crate | ½ day | none (no writes) |
| 2 | Dry-run on the real crate (reads only) while HV is on for something else; verify CSV/state/events output + concurrent-session behavior | 1 h | low |
| 3 | Flask: status card, start/stop endpoints, interlocks | 2–3 h | low |
| 4 | First **supervised daytime** live training of P2_2 at a modest `v_target` (e.g. current working point +10–20 V); watch Flask HV tab; tune | ½ day at bench | medium — someone present |
| 5 | First unattended overnight session; review `hv_trainer_events.csv` + plateau report next morning | overnight | after 0–4 pass |

## 7. Open decisions (Alexandra)

1. **`on_finish` default** — hold at reached voltage, drop to a standby V, or power off?
2. **Drift channel during mesh training** — fixed at operating value, constant-gap
   offset link, or untouched?
3. **Plateau definition** — is "best voltage *held quietly* for ≥ dwell, not improved in
   90 min" the right operational meaning of "maximum the detector can physically reach"?
4. **Crate-kill auto-re-enable** — allowed at all unattended? (Suggest: yes, ≤ 2×,
   then stop at `on_error` policy and flag STALLED in Flask.)
5. Does training belong in the run database / logbook (the run-shaped JSON makes it
   look like a run — name convention `hv_training_*` keeps it filterable)?
