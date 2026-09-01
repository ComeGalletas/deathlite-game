"""Static obstacles (spec 5.3): trees, rocks, pillars, buildings.

All block movement and projectiles (a solid trunk / mass / wall). Circular
colliders -- convex, so entities using axis-slide movement resolution slide
around them rather than getting wedged. Low foliage (bushes) is no longer an
obstacle -- it is scattered as non-colliding decoration (see
world/map.py `_build_decor_scatter` and data/terrain.json `decorations`).
"""
from __future__ import annotations

import pygame

class _Kinds:
    """`kind -> (radius, blocks_projectiles, color)`, read from
    `data/terrain.json` `obstacles`.

    These used to be literals here, which put an obstacle's *collision* size in
    code while its *drawn* size lived in `terrain.json` `obstacle_decor` -- two
    files to change to resize one prop, and against the standing rule that
    entity tuning belongs in the data. Loaded on first use rather than at import
    so this module stays importable without the asset layer, and exposed as a
    mapping so `from entities.obstacle import KINDS` keeps working."""

    __slots__ = ("_d",)

    def __init__(self) -> None:
        self._d: dict | None = None

    def _load(self) -> dict:
        if self._d is None:
            from game.assets import get_assets
            block = get_assets().terrain.get("obstacles", {})
            self._d = {k: (float(v["radius"]),
                           bool(v.get("blocks_projectiles", True)),
                           tuple(v.get("color", (92, 92, 100))))
                       for k, v in block.items()}
            if not self._d:
                raise KeyError("data/terrain.json is missing its `obstacles` block")
        return self._d

    def __getitem__(self, k):
        return self._load()[k]

    def get(self, k, default=None):
        return self._load().get(k, default)

    def __contains__(self, k):
        return k in self._load()

    def __iter__(self):
        return iter(self._load())

    def __len__(self):
        return len(self._load())

    def keys(self):
        return self._load().keys()

    def items(self):
        return self._load().items()


KINDS = _Kinds()


class Obstacle:
    __slots__ = ("pos", "radius", "kind", "blocks_projectiles", "color", "variant")

    def __init__(self, kind: str, x: float, y: float, variant: int = 1) -> None:
        radius, blocks_proj, color = KINDS.get(kind, KINDS["rock"])
        self.kind = kind
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.blocks_projectiles = blocks_proj
        self.color = color
        # Cosmetic only: which decoration variant skins this obstacle (1..4).
        # Chosen from the run seed; never affects collision.
        self.variant = int(variant)
