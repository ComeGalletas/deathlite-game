"""Player summons (spec 5.8): a stationary Totem and a roaming Wolf.

Pooled (object pooling, spec 5.8 / 6.2). Each summon has spawn / lifetime /
targeting / movement / attack / death. Summons deal damage by emitting ordinary
friendly projectiles, so blessing tag-synergy and crit all apply for free and
the collision path is shared.
"""
from __future__ import annotations

import pygame


def _nearest(pos, enemies):
    best, best_d2 = None, float("inf")
    for e in enemies:
        if not getattr(e, "alive", True):
            continue
        d2 = (e.pos - pos).length_squared()
        if d2 < best_d2:
            best, best_d2 = e, d2
    return best


class Summon:
    __slots__ = ("active", "kind", "pos", "vel", "life", "attack_cd", "radius",
                 "color", "damage", "speed", "attack_range", "attack_interval",
                 "tags", "_t")

    def __init__(self) -> None:
        self.active = False
        self.kind = "totem"
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.life = 0.0
        self.attack_cd = 0.0
        self.radius = 12.0
        self.color = (150, 220, 190)
        self.damage = 6.0
        self.speed = 0.0
        self.attack_range = 320.0
        self.attack_interval = 0.7
        self.tags: tuple[str, ...] = ("summon",)
        self._t = 0.0

    def reset(self, *, kind, pos, damage, lifetime, color, tags,
              speed=0.0, attack_range=320.0, attack_interval=0.7,
              radius=12.0) -> None:
        self.kind = kind
        self.pos.update(pos)
        self.vel.update(0, 0)
        self.damage = damage
        self.life = lifetime
        self.color = color
        self.tags = tuple(tags) + ("summon",)
        self.speed = speed
        self.attack_range = attack_range
        self.attack_interval = attack_interval
        self.radius = radius
        self.attack_cd = 0.3
        self._t = 0.0

    def update(self, dt: float, ctx) -> None:
        self.life -= dt
        if self.life <= 0.0:
            self.active = False
            return
        self._t += dt
        target = _nearest(self.pos, ctx.enemies)

        if self.kind == "wolf" and target is not None:
            d = target.pos - self.pos
            if d.length() > self.attack_range * 0.6:
                self.vel = d.normalize() * self.speed
            else:
                self.vel = pygame.Vector2()
            self.pos += self.vel * dt

        self.attack_cd -= dt
        if target is None or self.attack_cd > 0.0:
            return
        if (target.pos - self.pos).length() > self.attack_range:
            return
        self.attack_cd = self.attack_interval
        direction = (target.pos - self.pos)
        if direction.length_squared() < 1e-6:
            return
        direction = direction.normalize()
        if self.kind == "wolf":
            ctx.spawn_projectile(pos=self.pos, vel=direction * 40, damage=self.damage,
                                 radius=22, lifetime=0.12, pierce=2, knockback=120,
                                 color=self.color, source_tags=self.tags)
        else:  # totem bolt
            ctx.spawn_projectile(pos=self.pos, vel=direction * 420, damage=self.damage,
                                 radius=6, lifetime=1.4, pierce=0, knockback=40,
                                 color=self.color, source_tags=self.tags)
