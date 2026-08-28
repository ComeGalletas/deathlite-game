"""Ranged / summon / hazard actions. Ports the timer bodies of `kite_shoot`,
`summoner` and `fsm_warlock`'s cast. Defaults from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.machine import ATTACK_SLOT, Component, OneShot


@dataclass
class FireProjectile(Component):
    """Fire a hostile shot at the player every `interval` s, only while the
    player is within `max_range` (the old kiter used `prefer_distance * 1.8`)."""

    interval: float = 2.0
    damage: float = 6.0
    speed: float = 220.0
    radius: float = 6.0
    max_range: float = 1.0e9

    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        s["t"] = s.get("t", self.interval) - per.dt
        if s["t"] > 0.0:
            return
        to = per.player_pos - actor.pos
        if to.length() > self.max_range:
            return                              # timer stays <= 0: fire on re-entry
        s["t"] = self.interval
        if to.length_squared() > 1e-6:
            cmb.fire_projectile(pos=actor.pos, vel=to.normalize() * self.speed,
                                damage=self.damage, radius=self.radius)


@dataclass
class SummonBrood(Component):
    """Spawn `count` of `enemy_id` at the actor every `interval` s."""

    interval: float = 4.0
    enemy_id: str = "swarm"
    count: int = 3

    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        s["t"] = s.get("t", self.interval) - per.dt
        if s["t"] <= 0.0:
            s["t"] = self.interval
            cmb.summon(self.enemy_id, actor.pos, int(self.count))


@dataclass
class CastHazard(OneShot):
    """Drop an area-denial hazard once, at the target snapshotted into
    `bb.slot(ATTACK_SLOT)["cast_at"]` by the telegraph transition (falls back to
    the live player position)."""

    radius: float = 90.0
    dps: float = 20.0
    duration: float = 3.5
    tick_interval: float | None = None

    def fire(self, actor, per, cmb):
        at = actor.bb.slot(ATTACK_SLOT).get("cast_at", per.player_pos)
        cmb.spawn_hazard(pygame.Vector2(at), self.radius, self.dps,
                         self.duration, self.tick_interval)
