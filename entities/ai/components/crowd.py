"""Local crowding / obstacle avoidance -- weak capped pushes on top of the
primary heading. Defaults ported from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.machine import Component

_SEP_RADIUS_MULT = 1.6
_SEP_CAP = 0.6            # was _SEP_MAX
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
        for other in per.neighbors(actor.pos, r):
            if other is actor or not getattr(other, "alive", True):
                continue
            away = actor.pos - other.pos
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
