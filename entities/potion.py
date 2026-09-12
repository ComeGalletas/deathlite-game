"""Health potion pickups (CB-8). Pooled short-lived world drops.

Behaviour mirrors `XPGem` deliberately -- sit still until the hero's pickup
radius reaches them, then home in with a vacuum feel, collected on contact --
so the two drop kinds read the same to the player and to the renderer. What
differs is the payload: a potion carries a rarity and a heal amount instead of
an XP value, and it does **not** expire, because walking away from a heal and
coming back for it when you need it is the point.
"""
from __future__ import annotations

import pygame

# Matches XPGem: the hero's body plus a little grace.
_COLLECT_GRACE = 6.0
_HOMING_SPEED = 320.0


class HealthPotion:
    __slots__ = ("active", "pos", "vel", "rarity", "heal", "homing", "age")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.rarity = "common"
        self.heal = 0.0
        self.homing = False
        self.age = 0.0

    def reset(self, pos: pygame.Vector2, rarity: str, heal: float) -> None:
        self.pos.update(pos)
        self.vel.update(0, 0)
        self.rarity = rarity
        self.heal = float(heal)
        self.homing = False
        self.age = 0.0

    def update(self, dt: float, player) -> bool:
        """Advance. Returns True if collected this frame.

        A potion is only picked up when the hero can actually use it: at full
        HP it lies still and waits, because a hero brushing a 50 HP rare potion
        with 2 HP missing would waste 48 of it. That gate covers homing as well
        as collection -- a potion that vacuumed to a full-HP hero and then sat
        on top of them uncollected would just look broken.
        """
        self.age += dt
        if player.hp >= player.max_hp:
            self.homing = False          # re-arms next time the hero is hurt
            self.vel.update(0, 0)
            return False

        collect_r = player.radius + _COLLECT_GRACE
        collect_sq = collect_r * collect_r
        to_player = player.pos - self.pos
        dist_sq = to_player.length_squared()

        if dist_sq <= collect_sq:
            self.active = False
            return True

        if not self.homing and dist_sq <= player.pickup_radius ** 2:
            self.homing = True

        if self.homing and dist_sq > 1e-6:
            direction = to_player / dist_sq ** 0.5
            travel_limit = max(0.0, dist_sq ** 0.5 - collect_r)
            speed = min(_HOMING_SPEED, travel_limit / dt) if dt > 0.0 else 0.0
            self.vel.update(direction * speed)
            self.pos += self.vel * dt

        if (player.pos - self.pos).length_squared() <= collect_sq:
            self.active = False
            return True
        return False
