"""LD-9 phase D7: enemies notice the player, chase for a while, then give up.

Until now every enemy chased from anywhere on the map, for ever. That was
tolerable on the LD-8 worlds and is not on the height-map ones: movement between
terraces is by staircase only, so a flow field will happily route an enemy the
entire length of an island to reach a player standing one tile away across a
drop. The brief settled the rule --

* an enemy pursues only when the player comes **within its aggro range**, or
  when the player **attacks it**;
* once aggroed it takes the whole route however long -- there is deliberately
  **no path-length cap**, the timer is the only limiter;
* the timer **refreshes** while the player stays in range and **counts down
  from the moment they leave**;
* on giving up it **idles in place with a light wander**, not frozen;
* aggro range is straight-line and **elevation-blind** -- an enemy a terrace
  below reacts, and usually tires before it arrives, which is the point. A
  ranged enemy above the player can simply start shooting.

`aggro_range` and `pursuit_seconds` are per-enemy-type values and live in
`data/enemies.json` / `data/bosses.json`. An enemy that carries neither is
left exactly as it was -- unconditional pursuit -- rather than being given a
number chosen here, so nothing is silently retuned by this module's existence.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.machine import Behavior, Component, Transition

# Component taxonomy, not per-enemy tuning: the shape of an idle drift, which
# every enemy shares. Overridable per type from its JSON block like every other
# component parameter in `entities/ai/components`.
_WANDER_SPEED = 0.28          # fraction of the enemy's speed while idling
_WANDER_HOLD = (1.4, 3.2)     # seconds a heading is kept before re-rolling
_WANDER_PAUSE = 0.45          # chance a re-roll is a standstill instead

_SLOT = "aggro"


def _slot(actor) -> dict:
    return actor.bb.slot(_SLOT)


def provoke(actor) -> None:
    """Mark this actor as having been attacked. Consumed by `AggroSense` on its
    next tick, which is what turns a hit into pursuit regardless of range."""
    _slot(actor)["provoked"] = True


def is_aggroed(actor, per) -> bool:
    return _slot(actor).get("until", 0.0) > getattr(per, "now", 0.0)


@dataclass
class AggroSense(Component):
    """Keeps the pursuit timer. Runs in *every* state (`Behavior.always`), so
    the countdown continues through an attack cycle and a hit landed mid-swing
    still refreshes it."""

    range: float = 0.0
    seconds: float = 0.0

    def tick(self, actor, per, cmb, acc):
        s = _slot(actor)
        hit = s.pop("provoked", False)
        near = (per.player_pos - actor.pos).length_squared() <= self.range ** 2
        if near or hit:
            # Refresh, not extend: while the player stays in range the deadline
            # is always `seconds` away, so the countdown starts the moment they
            # leave rather than from when they first arrived.
            s["until"] = per.now + self.seconds


@dataclass
class Wander(Component):
    """A slow drift so a bored enemy is not a statue. Re-rolls its heading every
    few seconds and sometimes stands still instead."""

    speed: float = _WANDER_SPEED
    hold: tuple = _WANDER_HOLD
    pause: float = _WANDER_PAUSE

    def tick(self, actor, per, cmb, acc):
        s = _slot(actor)
        s["wander_t"] = s.get("wander_t", 0.0) - per.dt
        if s["wander_t"] <= 0.0:
            s["wander_t"] = per.rng.uniform(*self.hold)
            if per.rng.random() < self.pause:
                s["wander"] = pygame.Vector2()
            else:
                a = per.rng.uniform(0.0, 6.283185)
                s["wander"] = pygame.Vector2(pygame.math.Vector2(1, 0)
                                             .rotate_rad(a))
        d = s.get("wander")
        if d is not None and d.length_squared() > 1e-9:
            acc.add(d, self.speed)


def with_aggro(base: Behavior, cfg: dict) -> Behavior:
    """Gate a behaviour behind an aggro check, without touching its builder.

    Applied in `registry.build_behavior`, so every enemy and boss gets it from
    one place rather than twelve.

    The machine drops back to idle **only from the behaviour's initial state**
    -- its chase or move state. Letting the timer yank an enemy out of a
    telegraph or an active swing would cut the attack's own timing short and
    strand the melee hitbox it had already committed to; instead the attack
    finishes, the machine returns to chase as it always does, and gives up from
    there.

    It also **starts** in the behaviour's own state, not in idle, and falls to
    idle on the first tick if nothing is near. `Behavior.tick` evaluates
    transitions *after* the frame's components have run, so starting idle would
    cost every enemy a frame of doing nothing -- which, for one spawned on top
    of the player, shifted the contact-bite cadence enough to drop a bite
    (measured: `test_at_most_one_bite_per_interval_then_another` went from
    always passing to failing about half the time). The mirror case is
    harmless: a distant enemy runs one frame of its chase, worth a couple of
    pixels, before going quiet."""
    rng = cfg.get("aggro_range")
    secs = cfg.get("pursuit_seconds")
    if not rng or not secs:
        return base

    idle = "aggro_idle"
    while idle in base.states:
        idle += "_"
    states = dict(base.states)
    states[idle] = [Wander(speed=cfg.get("idle_speed", _WANDER_SPEED),
                           hold=tuple(cfg.get("idle_hold", _WANDER_HOLD)),
                           pause=cfg.get("idle_pause", _WANDER_PAUSE))]

    transitions = list(base.transitions) + [
        Transition(frm=idle, to=base.initial,
                   when=lambda a, p: is_aggroed(a, p)),
        Transition(frm=base.initial, to=idle,
                   when=lambda a, p: not is_aggroed(a, p)),
    ]
    always = list(base.always) + [AggroSense(range=float(rng),
                                             seconds=float(secs))]
    return Behavior(states, transitions, initial=base.initial, always=always)
