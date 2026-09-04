"""Spawn geometry for a world with no layout.

`ring_point_outside_view` is the whole placement rule of the one-room
`GameMap(seed=None)` world the non-run tests use: a point just outside the
view, clamped to the world. A generated world has its spawn points decided
at generation (`world/gen/spawnpoints.py`).

The wave/budget director that lived here moved to `spawn/budget.py` in
spawn master S2, with its schedule in `data/spawn_tables.json`. The name is
re-exported so `from world.spawning import SpawnDirector` keeps working.
"""
from __future__ import annotations

import math
import random

import pygame

from spawn.budget import SpawnDirector  # noqa: F401  -- re-export, see above

__all__ = ["ring_point_outside_view", "SpawnDirector"]


def ring_point_outside_view(camera, world_w: int, world_h: int,
                            margin: float = 80.0,
                            rng: random.Random | None = None) -> pygame.Vector2:
    """A world point just outside the visible rectangle, clamped to the world
    (spec 3.4: spawn off-screen, never on the player)."""
    rng = rng or random
    view = camera.visible_rect()
    cx, cy = view.centerx, view.centery
    dist = math.hypot(view.width, view.height) / 2 + margin
    angle = rng.uniform(0, math.tau)
    x = min(max(cx + math.cos(angle) * dist, 8), world_w - 8)
    y = min(max(cy + math.sin(angle) * dist, 8), world_h - 8)
    return pygame.Vector2(x, y)
