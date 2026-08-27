"""Projectile: pooled, short-lived. Used for player shots and, with
`hostile=True`, enemy/boss shots.

Movement modes:
  * straight  -- default; travels along `vel`.
  * orbit     -- Ember Ring; circles `anchor` (a live reference to the player
                 position) at `orbit_radius`, re-clearing `hit_ids` every
                 `rehit_interval` so it keeps scoring hits.
Extra hit filters:
  * cone_half_angle > 0  -- Soul Scythe; the collision resolver also requires
                 the target to lie within this angle of `cone_dir`.
  * chain_left > 0        -- Thunder Orb; resolver redirects instead of despawning.
"""
from __future__ import annotations

import math

import pygame


class Projectile:
    __slots__ = (
        "active", "pos", "vel", "damage", "radius", "lifetime", "pierce_left",
        "knockback", "color", "hit_ids", "source_tags", "is_crit", "hostile",
        "chain_left", "chain_range",
        "anchor", "orbit_angle", "orbit_radius", "orbit_speed",
        "rehit_interval", "rehit_timer",
        "cone_dir", "cone_half_angle",
    )

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.damage = 0.0
        self.radius = 4.0
        self.lifetime = 0.0
        self.pierce_left = 0
        self.knockback = 0.0
        self.color = (255, 255, 255)
        self.hit_ids: set[int] = set()
        self.source_tags: tuple[str, ...] = ()
        self.is_crit = False
        self.hostile = False
        self.chain_left = 0
        self.chain_range = 0.0
        self.anchor: pygame.Vector2 | None = None
        self.orbit_angle = 0.0
        self.orbit_radius = 0.0
        self.orbit_speed = 0.0
        self.rehit_interval = 0.0
        self.rehit_timer = 0.0
        self.cone_dir = pygame.Vector2(1, 0)
        self.cone_half_angle = 0.0

    def reset(self, *, pos, vel, damage: float, radius: float, lifetime: float,
              pierce: int = 0, knockback: float = 0.0, color=(255, 255, 255),
              source_tags: tuple[str, ...] = (), is_crit: bool = False,
              hostile: bool = False, chain_left: int = 0, chain_range: float = 0.0,
              anchor=None, orbit_angle: float = 0.0, orbit_radius: float = 0.0,
              orbit_speed: float = 0.0, rehit_interval: float = 0.0,
              cone_dir=None, cone_half_angle: float = 0.0) -> None:
        self.pos.update(pos)
        self.vel.update(vel)
        self.damage = damage
        self.radius = radius
        self.lifetime = lifetime
        self.pierce_left = pierce
        self.knockback = knockback
        self.color = color
        self.hit_ids.clear()
        self.source_tags = source_tags
        self.is_crit = is_crit
        self.hostile = hostile
        self.chain_left = chain_left
        self.chain_range = chain_range
        self.anchor = anchor
        self.orbit_angle = orbit_angle
        self.orbit_radius = orbit_radius
        self.orbit_speed = orbit_speed
        self.rehit_interval = rehit_interval
        self.rehit_timer = rehit_interval
        self.cone_dir.update(cone_dir if cone_dir is not None else (1, 0))
        self.cone_half_angle = cone_half_angle

    def update(self, dt: float) -> None:
        if self.orbit_speed != 0.0 and self.anchor is not None:
            self.orbit_angle += self.orbit_speed * dt
            self.pos.update(
                self.anchor.x + math.cos(self.orbit_angle) * self.orbit_radius,
                self.anchor.y + math.sin(self.orbit_angle) * self.orbit_radius)
            if self.rehit_interval > 0.0:
                self.rehit_timer -= dt
                if self.rehit_timer <= 0.0:
                    self.rehit_timer = self.rehit_interval
                    self.hit_ids.clear()
            return  # orbiters are persistent: no lifetime countdown

        self.pos += self.vel * dt
        self.lifetime -= dt
        if self.lifetime <= 0.0:
            self.active = False

    def on_hit(self) -> None:
        if self.pierce_left > 0:
            self.pierce_left -= 1
        else:
            self.active = False
