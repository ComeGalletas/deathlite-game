"""Target-relative steering: close on the player, back off, or hold a range.

Defaults are ported verbatim from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.components._util import unit_to
from entities.ai.machine import Component

_SLEW_DEFAULT = 9.0        # was _SLEW_RATE -- heading ease toward the field, per second


def _want(actor, per, via: str) -> pygame.Vector2:
    """The raw (unslewed) unit heading toward the player for `via`."""
    if via == "nav":
        d = per.nav_dir(actor.pos, actor.radius)
        if d.length_squared() > 1e-6:
            return pygame.Vector2(d)
    return unit_to(actor.pos, per.player_pos)


@dataclass
class SeekTarget(Component):
    """Steer toward the player.

    `via="nav"`  -- the shared flow field, straight-line fallback when it has no
                    route from here (covers the old `_approach`).
    `via="straight"` -- always a straight line (covers the old `_toward`).
    `slew` eases the heading (lerp toward the new want, snap on a near-180 flip)
    so a repath does not jerk the sprite; `0` disables it.
    """

    via: str = "nav"
    slew: float = _SLEW_DEFAULT
    weight: float = 1.0

    def tick(self, actor, per, cmb, acc):
        want = _want(actor, per, self.via)
        if want.length_squared() < 1e-12:
            return
        if self.slew <= 0.0:
            acc.add(want, self.weight)
            return
        s = actor.bb.slot(self.key)
        head = s.get("heading")
        if head is None or head.length_squared() < 1e-9:
            head = pygame.Vector2(want)
        else:
            head = head.lerp(want, min(1.0, self.slew * per.dt))
            if head.length_squared() < 0.04:            # near-180 flip -> take it
                head = pygame.Vector2(want)
            else:
                head.normalize_ip()
        s["heading"] = pygame.Vector2(head)
        acc.add(head, self.weight)


@dataclass
class Flee(Component):
    """Steer straight away from the player."""

    weight: float = 1.0

    def tick(self, actor, per, cmb, acc):
        acc.add(-unit_to(actor.pos, per.player_pos), self.weight)


@dataclass
class MaintainRange(Component):
    """Hold at ~`distance` from the player: flee (weight `weight`) inside
    `distance - band`, close (via `close_via`, weight `close_weight` or `weight`)
    outside `distance + band`, contribute nothing in the band (an actor whose
    only component is this then roots -- the old kiter feel)."""

    distance: float = 240.0
    band: float = 30.0
    close_via: str = "nav"
    weight: float = 1.0
    close_weight: float | None = None      # defaults to `weight`

    def tick(self, actor, per, cmb, acc):
        dist = (per.player_pos - actor.pos).length()
        if dist < self.distance - self.band:
            acc.add(-unit_to(actor.pos, per.player_pos), self.weight)
        elif dist > self.distance + self.band:
            w = self.weight if self.close_weight is None else self.close_weight
            acc.add(_want(actor, per, self.close_via), w)
