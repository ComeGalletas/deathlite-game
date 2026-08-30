"""A small facing-side damage ring a melee enemy's `attack` state spawns once
(see `path_chase_attack` / spec: chaser R1). Unlike `Hazard` (area-denial, dps
ticks) this deals its `damage` exactly once -- the first frame it catches the
player -- then dies; a stale swing that never connects just expires.
"""
from __future__ import annotations

import pygame


class MeleeHitbox:
    __slots__ = ("pos", "radius", "damage", "life", "_spent")

    def __init__(self, x: float, y: float, radius: float, damage: float,
                 duration: float) -> None:
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.damage = damage
        self.life = duration
        self._spent = False

    @property
    def alive(self) -> bool:
        return not self._spent and self.life > 0.0

    def update(self, dt: float) -> None:
        self.life -= dt

    def contains(self, point: pygame.Vector2, pad: float = 0.0) -> bool:
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2

    def consume(self) -> float:
        """Mark this hit spent and return the damage to deal. Call once, on
        the frame the hitbox actually catches the player."""
        self._spent = True
        return self.damage
