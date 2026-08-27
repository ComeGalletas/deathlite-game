"""Generic status-effect framework (spec 5.7).

A `StatusType` is pure data: an id, a `family` that says how it acts
(`dot` = damage over time, `slow` = movement multiplier, `amp` = extra damage
taken), stacking rules and a tick interval. `StatusState.update` has **one**
loop over active effects and dispatches by family -- there is no per-effect
hardcoded update (spec 5.7: "Avoid creating a separate hardcoded update system
for every effect"). Adding poison / bleed is just another table row.

`potency` meaning by family:
  * dot  -- damage per tick, multiplied by stack count
  * slow -- fraction of speed removed (0.3 => 70% speed)
  * amp  -- fraction of extra damage taken (0.15 => x1.15)
"""
from __future__ import annotations

from dataclasses import dataclass

REFRESH = "refresh"   # re-applying resets duration, keeps one stack
STACK = "stack"       # re-applying adds a stack (up to max) and resets duration


@dataclass(frozen=True)
class StatusType:
    id: str
    family: str            # "dot" | "slow" | "amp"
    stack_mode: str
    max_stacks: int
    tick_interval: float = 0.0


BURN = StatusType("burn", "dot", STACK, max_stacks=5, tick_interval=0.5)
POISON = StatusType("poison", "dot", STACK, max_stacks=8, tick_interval=0.75)
BLEED = StatusType("bleed", "dot", STACK, max_stacks=6, tick_interval=0.4)
CHILL = StatusType("chill", "slow", REFRESH, max_stacks=1)
SHOCK = StatusType("shock", "amp", REFRESH, max_stacks=1)

REGISTRY = {s.id: s for s in (BURN, POISON, BLEED, CHILL, SHOCK)}


@dataclass
class _Active:
    kind: StatusType
    stacks: int
    time_left: float
    potency: float
    _tick_accum: float = 0.0


class StatusState:
    def __init__(self) -> None:
        self._active: dict[str, _Active] = {}

    def __contains__(self, status_id: str) -> bool:
        return status_id in self._active

    def __bool__(self) -> bool:
        return bool(self._active)

    def active_ids(self):
        return tuple(self._active)

    def clear(self) -> None:
        self._active.clear()

    def apply(self, status_id: str, duration: float, potency: float,
              bonus_max_stacks: int = 0) -> None:
        kind = REGISTRY[status_id]
        cap = kind.max_stacks + max(0, int(bonus_max_stacks))
        cur = self._active.get(status_id)
        if cur is None:
            self._active[status_id] = _Active(kind, 1, duration, potency)
            return
        cur.time_left = max(cur.time_left, duration)
        cur.potency = max(cur.potency, potency)
        if kind.stack_mode == STACK:
            cur.stacks = min(cap, cur.stacks + 1)

    def stacks(self, status_id: str) -> int:
        a = self._active.get(status_id)
        return a.stacks if a else 0

    def update(self, dt: float, apply_damage) -> None:
        """One loop, family dispatch. `apply_damage(amount)` handles DoT ticks."""
        done = []
        for sid, a in self._active.items():
            a.time_left -= dt
            if a.kind.family == "dot" and a.kind.tick_interval > 0.0:
                a._tick_accum += dt
                while (a._tick_accum >= a.kind.tick_interval
                       and a.time_left > -a.kind.tick_interval):
                    a._tick_accum -= a.kind.tick_interval
                    apply_damage(a.potency * a.stacks)
            if a.time_left <= 0.0:
                done.append(sid)
        for sid in done:
            del self._active[sid]

    # --- family queries ------------------------------------------
    def speed_multiplier(self) -> float:
        m = 1.0
        for a in self._active.values():
            if a.kind.family == "slow":
                m *= (1.0 - a.potency)
        return max(0.1, m)

    def damage_taken_multiplier(self) -> float:
        m = 1.0
        for a in self._active.values():
            if a.kind.family == "amp":
                m *= (1.0 + a.potency)
        return m
