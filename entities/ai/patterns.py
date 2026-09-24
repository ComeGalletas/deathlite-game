"""Boss attack patterns: name -> what the pattern does (ENT-015).

A boss's `patterns` list in `data/enemies/bosses.json` is a cycle of these,
each with its own `telegraph` / `duration` / `recover` seconds plus the keys
the pattern itself reads. `behaviors/boss.py` runs the cycle; this module is
what each step *does*:

* `fire(actor, per, cmb, p)` -- once, on `telegraph -> active`, where the
  one-shot belongs (a bullet ring, a locked dash direction, a summon, a melee
  ring). `p` is the pattern's own data block.
* `active(actor, per, cmb, acc, p)` -- optional, every frame of the dangerous
  window. Without one the boss holds still for it (the old `_phase_active`).

A new kind of boss attack is one `@boss_pattern` function; a new boss is a
pattern list in the data. `requires` names the keys a pattern reads beyond the
three timings, so a data block missing one is caught when the boss is built
(`valid_patterns`) rather than mid-fight.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable

import pygame

from entities.ai.components.attacks import Charge
from entities.ai.machine import ATTACK_SLOT

log = logging.getLogger(__name__)

TIMINGS = ("telegraph", "duration", "recover")


@dataclass(frozen=True)
class Pattern:
    fire: Callable
    active: Callable | None = None
    requires: tuple[str, ...] = ()


_PATTERNS: dict[str, Pattern] = {}


def boss_pattern(name: str, *, requires: tuple[str, ...] = (), active=None):
    def deco(fire):
        if name in _PATTERNS:
            raise ValueError(f"boss pattern {name!r} already registered")
        _PATTERNS[name] = Pattern(fire, active, tuple(requires))
        return fire
    return deco


def get(name: str) -> Pattern | None:
    return _PATTERNS.get(name)


def registered() -> list[str]:
    return sorted(_PATTERNS)


def problems(p: dict) -> list[str]:
    """What is wrong with one pattern block (empty when it is usable)."""
    pid = p.get("id")
    pat = _PATTERNS.get(pid)
    if pat is None:
        return [f"unknown pattern id {pid!r} (registered: {registered()})"]
    return [f"pattern {pid!r} lacks {k!r}" for k in (*TIMINGS, *pat.requires)
            if k not in p]


def valid_patterns(boss_id: str, patterns) -> list[dict]:
    """The usable patterns of a boss, in order. An unusable one is dropped
    from the cycle with a log line -- the boss still spawns and fights with
    the rest (the standing rule: invalid data fails soft, never refuses)."""
    out = []
    for p in patterns:
        bad = problems(p)
        if bad:
            log.warning("boss %s: pattern dropped: %s", boss_id, "; ".join(bad))
            continue
        out.append(p)
    return out


# --- the patterns ------------------------------------------------------------

@boss_pattern("radial_barrage", requires=("bullets", "bullet_speed", "bullet_damage"))
def _radial_barrage(actor, per, cmb, p) -> None:
    """A ring of `bullets` shots, evenly spaced, out from the boss."""
    n, spd, dmg = int(p["bullets"]), float(p["bullet_speed"]), float(p["bullet_damage"])
    for i in range(n):
        ang = (math.tau / n) * i
        cmb.fire_projectile(pos=actor.pos,
                            vel=pygame.Vector2(math.cos(ang), math.sin(ang)) * spd,
                            damage=dmg, radius=7)


def _charge_dash(actor, per, cmb, acc, p) -> None:
    # The shared dash component, at this pattern's own speed and damage.
    Charge(speed=float(p["charge_speed"]), damage=float(p["charge_damage"])).tick(
        actor, per, cmb, acc)


@boss_pattern("charge", requires=("charge_speed", "charge_damage"), active=_charge_dash)
def _charge(actor, per, cmb, p) -> None:
    """Lock the dash at the player as the telegraph ends; `active` runs it."""
    d = per.player_pos - actor.pos
    actor.bb.slot(ATTACK_SLOT)["dir"] = (d.normalize() if d.length_squared() > 1
                                         else pygame.Vector2(1, 0))


@boss_pattern("summon_brood", requires=("summon_id", "summon_count"))
def _summon_brood(actor, per, cmb, p) -> None:
    cmb.summon(p["summon_id"], actor.pos, int(p["summon_count"]))


@boss_pattern("sweep", requires=("sweep_radius", "sweep_damage"))
def _sweep(actor, per, cmb, p) -> None:
    """A ring of melee centred on the boss, for a weapon that swings all the
    way round the wielder. The hitbox is static, which is correct: the boss
    holds still for every pattern without an `active`, so it and its sweep
    stay on the same spot for the swing."""
    cmb.melee_hit(actor.pos, float(p["sweep_radius"]), float(p["sweep_damage"]),
                  float(p["duration"]))
