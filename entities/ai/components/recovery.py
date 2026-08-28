"""Stuck recovery -- a brief perpendicular nudge when the actor stops making
headway. Defaults ported from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.components._util import unit_to
from entities.ai.machine import Component

_STUCK_SECONDS = 0.4
_STUCK_PROGRESS_FRAC = 0.3      # "made progress" = moved >= this fraction of speed*window
_NUDGE_SECONDS = 0.35
_NUDGE_STRENGTH = 1.5          # dominates the heading during the nudge, to break free


@dataclass
class Unstick(Component):
    """If the actor covers less than `progress_frac` of the distance it should
    have over `seconds`, add a `nudge_seconds` sideways push (side seeded from
    `per.rng`). Order this LAST in a state -- it nudges perpendicular to the
    steering accumulated so far."""

    seconds: float = _STUCK_SECONDS
    progress_frac: float = _STUCK_PROGRESS_FRAC
    nudge_strength: float = _NUDGE_STRENGTH
    nudge_seconds: float = _NUDGE_SECONDS

    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        s["nudge_t"] = s.get("nudge_t", 0.0) - per.dt
        if s["nudge_t"] > 0.0:
            acc.add(s.get("nudge_v", pygame.Vector2()))
            return
        reset_sq = (actor.speed * self.seconds * self.progress_frac) ** 2
        anchor = s.get("anchor")
        if anchor is None or actor.pos.distance_squared_to(anchor) > reset_sq:
            s["anchor"] = pygame.Vector2(actor.pos)
            s["t"] = 0.0
            return
        s["t"] = s.get("t", 0.0) + per.dt
        if s["t"] < self.seconds:
            return
        base = acc.direction()
        if base.length_squared() < 1e-9:
            base = unit_to(actor.pos, per.player_pos)
        perp = pygame.Vector2(-base.y, base.x)
        if per.rng.random() < 0.5:
            perp = -perp
        s["nudge_v"] = perp * self.nudge_strength
        s["nudge_t"] = self.nudge_seconds
        s["t"] = 0.0
        s["anchor"] = pygame.Vector2(actor.pos)
        acc.add(s["nudge_v"])
