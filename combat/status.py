"""Generic status-effect framework (spec 5.7).

A `StatusType` is pure data: an id, a `family` that says how it acts
(`dot` = damage over time, `slow` = movement multiplier, `amp` = extra damage
taken, `stun` = frozen: no movement, no behaviour, no contact damage),
stacking rules and a tick interval. `StatusState.update` has **one**
loop over active effects and dispatches by family -- there is no per-effect
hardcoded update (spec 5.7: "Avoid creating a separate hardcoded update system
for every effect"). Adding poison / bleed is just another table row.

`potency` meaning by family:
  * dot  -- damage per tick, multiplied by stack count
  * slow -- fraction of speed removed (0.3 => 70% speed)
  * amp  -- fraction of extra damage taken (0.15 => x1.15)
  * stun -- unused (a stun is all-or-nothing); the Hammer applies it (P1)
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
STUN = StatusType("stun", "stun", REFRESH, max_stacks=1)
# Ice's freeze (elemental system M2). A row of its own so the dev inspector
# and the tracking can tell it from the Hammer's stun, but in the **stun
# family**, so "no movement, no behaviour, no contact bite" and
# `is_stunned()` work with no new code (owner's decision, 2026-09-21). The
# side effect the owner accepted: Demolitionist pays against frozen enemies
# as it does against stunned ones.
FREEZE = StatusType("freeze", "stun", REFRESH, max_stacks=1)
# P4: the Rod's mark -- a flag the synergies read (design decision 2); no
# family behaviour of its own.
MARK = StatusType("mark", "mark", REFRESH, max_stacks=1)

REGISTRY = {s.id: s for s in (BURN, POISON, BLEED, CHILL, SHOCK, STUN, FREEZE,
                              MARK)}


@dataclass
class _Active:
    kind: StatusType
    stacks: int
    time_left: float
    potency: float
    _tick_accum: float = 0.0
    # What applied it -- a weapon id, normally. Carried so a damage-over-time
    # tick can say which weapon it belongs to; without it a burn's damage is
    # unattributable and a build's breakdown has a hole in it.
    source: object = None
    # Elemental system: this status shares an aura's lifetime (Fire -> burn,
    # Ice -> chill), so consuming the aura ends it too. The flag follows the
    # **most recent application**: a blessing re-applying the same status
    # takes it over and it then outlives the aura, and an element applying
    # over a blessing's status binds it. Last applier owns it.
    bound_to_aura: bool = False
    # Elemental system: which *effect* a tick of this status is credited
    # to ("burn", "frostburn"). `source` stays the weapon, so both
    # dimensions of the tracking come off one entry. `None` for the
    # blessing-applied statuses, whose ticks are the weapon's own.
    effect: str | None = None
    # Elemental system: a tick interval for this entry, overriding the
    # type's. Fire's burn ticks on `fire.burn.tick_interval` from the
    # data while the Ember Ring's Scorch keeps the type's 0.5 s, and
    # the tuning stays in the JSON where this project keeps it.
    tick_override: float = 0.0

    @property
    def interval(self) -> float:
        return self.tick_override or self.kind.tick_interval


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
              bonus_max_stacks: int = 0, source=None,
              bound_to_aura: bool = False, effect: str | None = None,
              tick_interval: float = 0.0, add_stack: bool = True) -> int:
        """Apply or refresh a status; return its stack count afterwards.

        `add_stack=False` refreshes without adding one -- Fire's burn
        refreshes its duration and never stacks (design 4.1), while the
        same `burn` row applied by a blessing still stacks to five.
        """
        kind = REGISTRY[status_id]
        cap = kind.max_stacks + max(0, int(bonus_max_stacks))
        cur = self._active.get(status_id)
        if cur is None:
            self._active[status_id] = _Active(kind, 1, duration, potency,
                                              source=source,
                                              bound_to_aura=bound_to_aura,
                                              effect=effect,
                                              tick_override=tick_interval)
            return 1
        cur.time_left = max(cur.time_left, duration)
        cur.potency = max(cur.potency, potency)
        # A refresh re-attributes: the weapon keeping the burn alive is the one
        # its ticks belong to.
        if source is not None:
            cur.source = source
        # ...and re-binds: whoever applied it last decides whether it shares
        # an aura's lifetime.
        cur.bound_to_aura = bound_to_aura
        cur.effect = effect
        cur.tick_override = tick_interval
        if add_stack and kind.stack_mode == STACK:
            cur.stacks = min(cap, cur.stacks + 1)
        return cur.stacks

    def stacks(self, status_id: str) -> int:
        a = self._active.get(status_id)
        return a.stacks if a else 0

    def potency(self, status_id: str) -> float:
        a = self._active.get(status_id)
        return a.potency if a else 0.0

    def remaining(self, status_id: str) -> float:
        """Seconds left, or 0.0 when the status is not active (dev
        inspector)."""
        a = self._active.get(status_id)
        return max(0.0, a.time_left) if a else 0.0

    def set_potency(self, status_id: str, value: float) -> None:
        """Overwrite a potency outright. `apply` only ever raises it
        (`max`), which is right for a refresh but wrong for Ice, whose slow
        is recomputed from its stack count on every application."""
        a = self._active.get(status_id)
        if a is not None:
            a.potency = float(value)

    def end(self, status_id: str) -> bool:
        """Remove a status now. Returns whether it was active."""
        return self._active.pop(status_id, None) is not None

    def end_bound(self) -> tuple[str, ...]:
        """End every status bound to the aura -- what a consumed or expired
        aura takes with it. Returns the ids that ended."""
        gone = tuple(sid for sid, a in self._active.items() if a.bound_to_aura)
        for sid in gone:
            del self._active[sid]
        return gone

    def source_of(self, status_id: str):
        """What applied a status -- normally a weapon id, or None."""
        a = self._active.get(status_id)
        return a.source if a else None

    def is_bound(self, status_id: str) -> bool:
        a = self._active.get(status_id)
        return bool(a and a.bound_to_aura)

    def update(self, dt: float, apply_damage) -> None:
        """One loop, family dispatch. `apply_damage(amount, source)` handles
        DoT ticks; `source` is what applied the status."""
        done = []
        for sid, a in self._active.items():
            a.time_left -= dt
            interval = a.interval
            if a.kind.family == "dot" and interval > 0.0:
                a._tick_accum += dt
                while (a._tick_accum >= interval
                       and a.time_left > -interval):
                    a._tick_accum -= interval
                    # Two arguments unless the entry names an effect, so
                    # every existing `(amount, source)` tick callback
                    # keeps working and only the elemental statuses pay
                    # for the third dimension.
                    if a.effect is None:
                        apply_damage(a.potency * a.stacks, a.source)
                    else:
                        apply_damage(a.potency * a.stacks, a.source, a.effect)
            if a.time_left <= 0.0:
                done.append(sid)
        for sid in done:
            del self._active[sid]

    # --- family queries ------------------------------------------
    def speed_multiplier(self) -> float:
        m = 1.0
        for a in self._active.values():
            if a.kind.family == "stun":
                return 0.0
            if a.kind.family == "slow":
                m *= (1.0 - a.potency)
        return max(0.1, m)

    def is_stunned(self) -> bool:
        return any(a.kind.family == "stun" for a in self._active.values())

    def damage_taken_multiplier(self) -> float:
        m = 1.0
        for a in self._active.values():
            if a.kind.family == "amp":
                m *= (1.0 + a.potency)
        return m
