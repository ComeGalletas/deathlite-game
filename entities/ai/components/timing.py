"""Timers and transition predicates -- the machine's plumbing.

`Cooldown` is meant for a `Behavior`'s `always=[...]` list so it ticks in every
state (matches the old `enemy.ai["cd"]` which decremented each frame regardless
of the FSM phase). The `after` / `in_range` / ... helpers build the
`when(actor, perception)` callables a `Transition` takes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from entities.ai.machine import Component, time_in_state


@dataclass
class Cooldown(Component):
    """A down-counter. `ready()` once it hits 0; `trigger()` reloads it. Put it
    in `always=[...]` and read it from a transition predicate."""

    seconds: float = 1.0
    start_ready: bool = True

    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        if "t" not in s:
            s["t"] = 0.0 if self.start_ready else self.seconds
        if s["t"] > 0.0:
            s["t"] = max(0.0, s["t"] - per.dt)

    def ready(self, actor) -> bool:
        s = actor.bb.slot(self.key)
        return self.start_ready if "t" not in s else s["t"] <= 0.0

    def trigger(self, actor) -> None:
        actor.bb.slot(self.key)["t"] = self.seconds


@dataclass
class OnEnter(Component):
    """Run `action(actor, per, cmb, acc)` once on each entry into this state."""

    action: Callable

    def tick(self, actor, per, cmb, acc):
        from entities.ai.machine import _MACHINE
        s = actor.bb.slot(self.key)
        visit = actor.bb.slot(_MACHINE).get("visit", 0)
        if s.get("visit") != visit:
            s["visit"] = visit
            self.action(actor, per, cmb, acc)


# --- transition predicates ---------------------------------------

def after(seconds: float) -> Callable:
    return lambda actor, per: time_in_state(actor) >= seconds


def in_range(dist: float) -> Callable:
    d2 = dist * dist
    return lambda actor, per: \
        (per.player_pos - actor.pos).length_squared() <= d2


def out_of_range(dist: float) -> Callable:
    d2 = dist * dist
    return lambda actor, per: \
        (per.player_pos - actor.pos).length_squared() > d2


def ready(cooldown: Cooldown) -> Callable:
    return lambda actor, per: cooldown.ready(actor)


def all_of(*preds: Callable) -> Callable:
    return lambda actor, per: all(p(actor, per) for p in preds)


def any_of(*preds: Callable) -> Callable:
    return lambda actor, per: any(p(actor, per) for p in preds)
