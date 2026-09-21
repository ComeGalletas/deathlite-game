"""Spawn geometry for a world with no layout.

`ring_point_around` is the whole placement rule of the one-room
`GameMap(seed=None)` world the non-run tests use: a point in a distance band
around the hero, clamped to the world, regardless of the camera (spawn
master S11). A generated world has its spawn points decided at generation
(`world/gen/spawnpoints.py`).

The wave/budget director that lived here moved to `spawn/budget.py` in
spawn master S2, with its schedule in `data/enemies/spawn_tables.json`.
"""
from __future__ import annotations

import math
import random

import pygame

__all__ = ["ring_point_around"]


def ring_point_around(centre: pygame.Vector2, world_w: int, world_h: int,
                      min_distance: float, max_distance: float,
                      rng: random.Random | None = None) -> pygame.Vector2:
    """A world point between `min_distance` and `max_distance` from `centre`
    on a random side, clamped to the world (spec 3.4: never on the player).
    The camera is not an input: the band is the same whatever the view."""
    rng = rng or random
    dist = rng.uniform(float(min_distance), float(max_distance))
    angle = rng.uniform(0, math.tau)
    x = min(max(centre.x + math.cos(angle) * dist, 8), world_w - 8)
    y = min(max(centre.y + math.sin(angle) * dist, 8), world_h - 8)
    return pygame.Vector2(x, y)
