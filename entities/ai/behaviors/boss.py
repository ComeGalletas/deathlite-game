"""`boss_patterns` -- the boss's attack cycle as a machine (ENT-015).

    intro -> telegraph -> active -> recover -> telegraph (next pattern) -> ...

Each pattern in the boss's `patterns` list (`data/enemies/bosses.json`) sets
its own `telegraph` / `duration` / `recover` seconds; what a pattern *does* is
`entities/ai/patterns.py`. While it winds up and recovers the boss drifts at
the player -- 0.3 / 0.25 / 0.5 of its speed through the intro, the telegraph
and the recovery, straight at it for a flyer -- and it holds still for the
dangerous window unless the pattern moves it (the charge's dash).

The phase clock counts *down* (`bb.slot(ATTACK_SLOT)["left"]`), as the boss's
own loop did, rather than up like the machine's `entered`: the subtraction is
what the bosses were tuned and tested against, and a sum lands a boundary like
0.45 s a frame differently. `PhaseClock` ticks first, in `always`.

Out of sight the boss does not tick this machine at all (`Boss.update`), so the
clock -- and a telegraph half done -- holds where it was.
"""
from __future__ import annotations

from dataclasses import dataclass

from entities.ai import patterns
from entities.ai.components import SeekTarget
from entities.ai.machine import ATTACK_SLOT, Behavior, Component, Transition
from entities.ai.registry import behavior

_MIN_PHASE = 0.0001


def _slot(actor) -> dict:
    return actor.bb.slot(ATTACK_SLOT)


def enter(actor, length: float) -> None:
    """Start the phase clock on a phase `length` seconds long."""
    s = _slot(actor)
    s["left"] = s["len"] = max(_MIN_PHASE, float(length))


@dataclass
class PhaseClock(Component):
    """Counts the current phase down; starts on the intro's length."""

    intro: float = 0.0

    def tick(self, actor, per, cmb, acc):
        s = _slot(actor)
        if "left" not in s:
            enter(actor, self.intro)
        s["left"] -= per.dt


@dataclass
class PatternActive(Component):
    """The dangerous window: the current pattern's `active`, if it has one.
    Nothing else steers in this state, so without one the boss holds still."""

    def tick(self, actor, per, cmb, acc):
        p = _slot(actor).get("pattern") or {}
        pat = patterns.get(p.get("id"))
        if pat is not None and pat.active is not None:
            pat.active(actor, per, cmb, acc, p)


def _phase_over(actor, per) -> bool:
    return _slot(actor).get("left", 1.0) <= 0.0


@behavior("boss_patterns")
def boss_patterns(cfg: dict) -> Behavior:
    cycle = patterns.valid_patterns(cfg.get("name", "?"), cfg.get("patterns", ()))
    via = "straight" if "flying" in cfg.get("tags", ()) else "nav"

    def drift(weight: float) -> SeekTarget:
        return SeekTarget(via=via, slew=0.0, weight=weight)

    if not cycle:
        # Nothing to cycle: it just comes for the player.
        return Behavior(states={"chase": [drift(1.0)]})

    def next_pattern(actor, per, cmb):
        s = _slot(actor)
        s["index"] = (s.get("index", -1) + 1) % len(cycle)
        s["pattern"] = cycle[s["index"]]
        enter(actor, s["pattern"]["telegraph"])

    def fire(actor, per, cmb):
        p = _slot(actor)["pattern"]
        patterns.get(p["id"]).fire(actor, per, cmb, p)
        enter(actor, p["duration"])

    def recover(actor, per, cmb):
        enter(actor, _slot(actor)["pattern"]["recover"])

    return Behavior(
        always=[PhaseClock(intro=float(cfg["intro"]))],
        states={
            "intro": [drift(0.3)],
            "telegraph": [drift(0.25)],
            "active": [PatternActive()],
            "recover": [drift(0.5)],
        },
        transitions=[
            Transition("intro", "telegraph", _phase_over, next_pattern),
            Transition("telegraph", "active", _phase_over, fire),
            Transition("active", "recover", _phase_over, recover),
            Transition("recover", "telegraph", _phase_over, next_pattern),
        ],
        initial="intro",
    )
