#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hv_trainer_controller.py

Soft back-off HV training controller: RAMP_UP / HOLD / BACKOFF state machine
that replaces the CAEN crate's hard over-current trip with a back-off-and-
re-ramp loop, so a sparky detector gets conditioned instead of having its HV
killed by the 30 s TRIP.

Ported from P2_basket_analysis/cosmic_bench_analysis/hv_trainer.py (the
analysis repo copy remains the home of the offline backtester). Pure decision
logic, no hardware dependency, stdlib only.

Extension over the analysis-repo original (2026-07-08, first live session on
P2 det 1): optional sustained-elevated-current backoff. A continuously
sparking detector can draw a large average current (P2_1 at 455 V: 5-9 uA,
~7 discharges/min) while each spark self-quenches below the OVC threshold, so
the strict continuous-OVC condition never fires and the controller would sit
at a sparking voltage forever. If `i_elev` is set, an exponential moving
average of imon (time constant `i_avg_tau`) above `i_elev` triggers the same
BACKOFF path. Disabled by default (i_elev=None): behavior is then identical
to the original. See docs/hv_trainer_implementation_plan.md.
"""

from dataclasses import dataclass, field


@dataclass
class TrainerConfig:
    i_comp: float = 10.0        # crate current limit ISet [uA] -> OVC at this
    i_comp_frac: float = 0.95   # treat imon >= frac*i_comp as OVC
    i_safe: float = 2.0         # imon below this is "settled" [uA]
    v_target: float = 420.0     # conditioning target [V]
    v_floor: float = 0.0        # never command below this [V]
    v_step_up: float = 10.0     # ramp-up step [V]
    v_step_down: float = 25.0   # back-off drop per OVC event [V]
    dwell: float = 30.0         # safe-current hold before stepping up [s]
    recover_dwell: float = 30.0  # cooldown after a back-off before ramping [s]
    backoff_after: float = 6.0  # continuous OVC before backing off [s]
    caen_trip_time: float = 30.0  # crate's OVC->kill time, for comparison [s]
    i_elev: float = None        # EMA(imon) above this -> back off [uA]; None = off
    i_avg_tau: float = 120.0    # EMA time constant for the i_elev check [s]


@dataclass
class TrainingController:
    cfg: TrainerConfig
    vset: float = None                 # current commanded set voltage [V]
    _ovc_run: float = 0.0              # continuous OVC duration [s]
    _safe_run: float = 0.0             # continuous settled duration [s]
    _cooldown: float = 0.0             # remaining recovery cooldown [s]
    _i_avg: float = 0.0                # EMA of imon for the i_elev check [uA]
    events: list = field(default_factory=list)  # (t, kind, vset, imon)

    def __post_init__(self):
        if self.vset is None:
            self.vset = self.cfg.v_target

    def step(self, t, imon, dt):
        """Advance one readout. Returns (vset, state)."""
        c = self.cfg
        ovc = imon >= c.i_comp_frac * c.i_comp
        safe = imon < c.i_safe

        self._ovc_run = self._ovc_run + dt if ovc else 0.0
        self._safe_run = self._safe_run + dt if safe else 0.0
        self._cooldown = max(0.0, self._cooldown - dt)
        if c.i_elev is not None and c.i_avg_tau > 0:
            a = min(1.0, dt / c.i_avg_tau)
            self._i_avg += a * (imon - self._i_avg)
        elevated = (c.i_elev is not None and self._i_avg >= c.i_elev
                    and self._cooldown <= 0.0)

        state = 'HOLD'
        if self._ovc_run >= c.backoff_after or elevated:
            # Soft trip: back off before the crate would kill (OVC), or the
            # average current shows a continuous-sparking regime (elevated).
            new = max(self.vset - c.v_step_down, c.v_floor)
            self.events.append((t, 'BACKOFF', new, imon))
            self.vset = new
            self._ovc_run = 0.0
            self._safe_run = 0.0
            self._i_avg = 0.0
            self._cooldown = c.recover_dwell
            state = 'BACKOFF'
        elif (self.vset < c.v_target and self._safe_run >= c.dwell
              and self._cooldown <= 0.0):
            new = min(self.vset + c.v_step_up, c.v_target)
            if new != self.vset:
                self.events.append((t, 'STEP_UP', new, imon))
            self.vset = new
            self._safe_run = 0.0
            state = 'RAMP_UP'
        return self.vset, state
