#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hv_trainer_controller.py

Soft back-off HV training controller: RAMP_UP / HOLD / BACKOFF state machine
that replaces the CAEN crate's hard over-current trip with a back-off-and-
re-ramp loop, so a sparky detector gets conditioned instead of having its HV
killed by the 30 s TRIP.

Verbatim copy of TrainerConfig + TrainingController from
P2_basket_analysis/cosmic_bench_analysis/hv_trainer.py (the analysis repo
copy remains the home of the offline backtester). Pure decision logic, no
hardware dependency, stdlib only. See docs/hv_trainer_implementation_plan.md.
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


@dataclass
class TrainingController:
    cfg: TrainerConfig
    vset: float = None                 # current commanded set voltage [V]
    _ovc_run: float = 0.0              # continuous OVC duration [s]
    _safe_run: float = 0.0             # continuous settled duration [s]
    _cooldown: float = 0.0             # remaining recovery cooldown [s]
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

        state = 'HOLD'
        if self._ovc_run >= c.backoff_after:
            # Soft trip: back off before the crate would kill.
            new = max(self.vset - c.v_step_down, c.v_floor)
            self.events.append((t, 'BACKOFF', new, imon))
            self.vset = new
            self._ovc_run = 0.0
            self._safe_run = 0.0
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
