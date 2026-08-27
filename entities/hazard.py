"""Ground hazards (spec 5.6 area-denial): a lingering circle that damages the
player while they stand in it. Spawned by the Warlock enemy after a telegraph.
Plain list-managed (few exist at once); short-lived.
"""
from __future__ import annotations

import pygame


class Hazard:
    __slots__ = ("pos", "radius", "dps", "life", "max_life", "color")

    def __init__(self, x: float, y: float, radius: float, dps: float,
                 duration: float, color=(200, 90, 220)) -> None:
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.dps = dps
        self.life = self.max_life = duration
        self.color = color

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life -= dt

    def contains(self, point: pygame.Vector2, pad: float = 0.0) -> bool:
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2
