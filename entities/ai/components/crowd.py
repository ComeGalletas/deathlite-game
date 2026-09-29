"""Local crowding / obstacle avoidance -- weak capped pushes on top of the
primary heading. Defaults ported from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.machine import Component

_SEP_RADIUS_MULT = 1.6
_SEP_CAP = 0.6            # was _SEP_MAX
# `Separation`'s early drop keeps a billionth inside the vector test's own
# limits (`r * r` and `1e-6`), so the two never disagree about a neighbour
# that pushes (ENT-018.2).
_MARGIN_OUT = 1.0 + 1e-9
_NEAR = 1e-6 * (1.0 - 1e-9)
_OBSTACLE_MARGIN = 14.0
_OBSTACLE_CAP = 0.7      # was _OBSTACLE_MAX


@dataclass
class Separation(Component):
    """Push away from crowding neighbours (`per.neighbors`), stronger the closer
    they are, summed then capped."""

    radius_mult: float = _SEP_RADIUS_MULT
    cap: float = _SEP_CAP
    weight: float = 1.0

    def tick(self, actor, per, cmb, acc):
        r = actor.radius * self.radius_mult
        push = pygame.Vector2()
        # ENT-018.2: the grid hands back whole cells, so most candidates are
        # beyond `r`. They are dropped on float products before any vector;
        # a candidate within a billionth of either limit is left to the
        # vector test below, which decides exactly as it always has. The
        # ones that push go through unchanged and in the same order, so the
        # summed push is the same float.
        apos = actor.pos
        ax, ay = apos.x, apos.y
        far = r * r * _MARGIN_OUT
        for other in per.neighbors(apos, r):
            if other is actor or not getattr(other, "alive", True):
                continue
            opos = other.pos
            dx, dy = ax - opos.x, ay - opos.y
            d2 = dx * dx + dy * dy
            if d2 >= far or d2 < _NEAR:
                continue
            away = apos - opos
            dsq = away.length_squared()
            if dsq < 1e-6 or dsq >= r * r:
                continue
            away.scale_to_length((r - dsq ** 0.5) / r)
            push += away
        if push.length_squared() > self.cap * self.cap:
            push.scale_to_length(self.cap)
        acc.add(push, self.weight)


@dataclass
class AvoidObstacles(Component):
    """Push away from any static obstacle whose edge is within `margin` of the
    actor's edge (`per.obstacles_near`), summed then capped."""

    margin: float = _OBSTACLE_MARGIN
    cap: float = _OBSTACLE_CAP
    weight: float = 1.0

    def tick(self, actor, per, cmb, acc):
        push = pygame.Vector2()
        reach = actor.radius + self.margin + 40.0        # +slack for big props
        for o in per.obstacles_near(actor.pos, reach):
            away = actor.pos - o.pos
            gap = away.length() - o.radius - actor.radius
            if gap >= self.margin or away.length_squared() < 1e-6:
                continue
            away.scale_to_length(min(1.0, (self.margin - gap) / self.margin))
            push += away
        if push.length_squared() > self.cap * self.cap:
            push.scale_to_length(self.cap)
        acc.add(push, self.weight)
