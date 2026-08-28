"""`Component` base + the state machine every behaviour is (a plain chaser is a
one-state machine).

A `Behavior` is stateless and shared by every enemy of its type -- all mutable
state lives on the actor: component state in `actor.bb.slot(component.key)`, the
active machine state in `actor.bb.slot("__machine__")`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from entities.ai.steering import Steering

_MACHINE = "__machine__"


class Component:
    """A building block. Subclasses are usually `@dataclass` for their params and
    override `tick`. Never store per-actor state on the instance -- use
    `actor.bb.slot(self.key)`."""

    key: str = ""            # assigned by Behavior at build time; stable & unique

    def tick(self, actor, per, cmb, acc: Steering) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class Transition:
    """Checked after the active state's components tick each frame; the first
    whose `when(actor, perception)` is true switches the machine to `to`."""

    frm: str
    to: str
    when: Callable[[object, object], bool]


class Behavior:
    def __init__(self, states: dict[str, list],
                 transitions=(), initial: str | None = None) -> None:
        if not states:
            raise ValueError("a Behavior needs at least one state")
        self.states = states
        self.transitions = list(transitions)
        self.initial = initial or next(iter(states))
        if self.initial not in states:
            raise ValueError(f"initial state {self.initial!r} not in {list(states)}")
        for sname, comps in states.items():
            for i, c in enumerate(comps):
                c.key = f"{sname}#{i}:{type(c).__name__}"

    # --- per-actor machine state ---------------------------------
    def state_of(self, actor) -> str:
        return actor.bb.slot(_MACHINE).setdefault("state", self.initial)

    def time_in_state(self, actor) -> float:
        return actor.bb.slot(_MACHINE).get("entered", 0.0)

    def set_state(self, actor, name: str) -> None:
        if name not in self.states:
            raise KeyError(f"no state {name!r} in {list(self.states)}")
        m = actor.bb.slot(_MACHINE)
        m["state"] = name
        m["entered"] = 0.0

    # --- per-frame ---------------------------------------------
    def tick(self, actor, per, cmb) -> None:
        m = actor.bb.slot(_MACHINE)
        state = m.setdefault("state", self.initial)
        m["entered"] = m.get("entered", 0.0) + getattr(per, "dt", 0.0)

        acc = Steering()
        for c in self.states[state]:
            c.tick(actor, per, cmb, acc)
        actor.vel = acc.resolve(actor.speed)

        for t in self.transitions:
            if t.frm == state and t.when(actor, per):
                self.set_state(actor, t.to)
                break
