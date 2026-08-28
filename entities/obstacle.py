"""Static obstacles (spec 5.3): trees, rocks, pillars, buildings.

All block movement and projectiles (a solid trunk / mass / wall). Circular
colliders -- convex, so entities using axis-slide movement resolution slide
around them rather than getting wedged. Low foliage (bushes) is no longer an
obstacle -- it is scattered as non-colliding decoration (see
world/map.py `_build_decor_scatter` and data/terrain.json `decorations`).
"""
from __future__ import annotations

import pygame

# kind -> (radius, blocks_projectiles, color)
KINDS = {
    "tree":   (11, True,  (54, 82, 54)),   # small trunk ring; canopy drawn larger
    "rock":   (25, True,  (92, 92, 100)),
    "pillar": (15, True,  (120, 118, 130)),
    "house":  (31, True,  (150, 120, 90)),   # building; skinned per colour
}


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
