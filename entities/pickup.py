"""XP gems (spec 3.5). Pooled short-lived pickups.

Behaviour: sit still until the player's pickup radius reaches them, then home in
with increasing speed ("vacuum" feel). Collected when they touch the player.
"""
from __future__ import annotations

import pygame

XP_TIER_COLORS = {
    0: (120, 210, 120),   # small
    1: (110, 180, 255),   # medium
    2: (210, 140, 255),   # large
}


def xp_tier(value: int) -> int:
    if value >= 15:
        return 2
    if value >= 6:
        return 1
    return 0


class XPGem:
    __slots__ = ("active", "pos", "vel", "value", "tier", "homing", "age", "is_soul")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.value = 1
        self.tier = 0
        self.homing = False
        self.age = 0.0
        self.is_soul = False

    def reset(self, pos: pygame.Vector2, value: int, is_soul: bool = False) -> None:
        self.pos.update(pos)
        self.vel.update(0, 0)
        self.value = value
        self.tier = xp_tier(value)
        # Souls (from the Grave blessing) ignore pickup radius and always home.
        self.is_soul = is_soul
        self.homing = is_soul
        self.age = 0.0

    def update(self, dt: float, player) -> bool:
        """Advance. Returns True if collected this frame."""
        self.age += dt
        to_player = player.pos - self.pos
        dist_sq = to_player.length_squared()
        collect_r = player.radius + 6

        if dist_sq <= collect_r * collect_r:
            self.active = False
            return True

        if not self.homing and dist_sq <= player.pickup_radius ** 2:
            self.homing = True

        if self.homing and dist_sq > 1e-6:
            direction = to_player / dist_sq ** 0.5
            travel_limit = max(0.0, dist_sq ** 0.5 - collect_r)
            speed = min(320.0, travel_limit / dt) if dt > 0.0 else 0.0
            self.vel.update(direction * speed)
            self.pos += self.vel * dt

        dist_sq = (player.pos - self.pos).length_squared()
        if dist_sq <= collect_r * collect_r:
            self.active = False
            return True
        return False
