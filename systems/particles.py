"""Lightweight pooled particle system (spec 3.6 feedback, 6.2 pooling).

Particles are simple coloured dots with velocity, gravity-free, fading via
shrinking radius / alpha over their lifetime. Used for enemy death bursts, hit
sparks and XP pickup pops.
"""
from __future__ import annotations

import random

import pygame

from game import config
from systems.object_pool import Pool


class Particle:
    __slots__ = ("active", "pos", "vel", "life", "max_life", "radius", "color")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.life = 0.0
        self.max_life = 1.0
        self.radius = 3.0
        self.color = (255, 255, 255)

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.vel *= pow(0.15, dt)  # air drag, frame-rate independent
        self.life -= dt
        if self.life <= 0.0:
            self.active = False


class ParticleSystem:
    def __init__(self, max_particles: int = config.MAX_PARTICLES) -> None:
        self._pool: Pool[Particle] = Pool(Particle, max_particles, prefill=64)

    def __len__(self) -> int:
        return len(self._pool)

    def burst(self, pos: pygame.Vector2, color, count: int = 10,
              speed: float = 140.0, life: float = 0.45,
              radius: float = 3.0) -> None:
        for _ in range(count):
            p = self._pool.acquire()
            if p is None:
                return  # at cap: stop, don't crash
            angle = random.uniform(0, 6.2831853)
            spd = speed * random.uniform(0.3, 1.0)
            p.pos.update(pos)
            p.vel.update(pygame.math.Vector2(spd, 0).rotate_rad(angle))
            p.life = p.max_life = life * random.uniform(0.7, 1.2)
            p.radius = radius
            p.color = color

    def update(self, dt: float) -> None:
        for p in self._pool:
            p.update(dt)
        self._pool.sweep()

    def draw(self, surface: pygame.Surface, camera) -> None:
        for p in self._pool:
            frac = max(0.0, p.life / p.max_life)
            r = max(1.0, p.radius * frac)
            sx, sy = camera.world_to_screen(p.pos)
            pygame.draw.circle(surface, p.color, (int(sx), int(sy)), int(r))

    def clear(self) -> None:
        self._pool.clear()
