"""Static obstacles (spec 5.3): trees, rocks, pillars, low walls.

All block movement. Rocks and pillars also block projectiles; trees and shrubs
do not (you can shoot through foliage). Circular colliders -- convex, so
entities using axis-slide movement resolution slide around them rather than
getting wedged.
"""
from __future__ import annotations

import pygame

# kind -> (radius, blocks_projectiles, color)
KINDS = {
    "tree":   (26, False, (54, 82, 54)),
    "rock":   (30, True,  (92, 92, 100)),
    "pillar": (22, True,  (120, 118, 130)),
    "shrub":  (18, False, (64, 96, 60)),
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
