"""Melee / dash / detonate attack components. Port `fsm_charger` (Charge),
`fsm_teleporter` (Blink), `brute`'s slam (Explosion) and `exploder` (Explode).
Defaults from `entities/enemy_ai.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.ai.machine import ATTACK_SLOT, Component, OneShot


@dataclass
class Charge(Component):
    """Per-frame dash at a fixed speed along the direction the telegraph
    transition locked into `bb.slot(ATTACK_SLOT)["dir"]`, bumping contact damage
    for the duration. Use as the `attack` state's only steering component."""

    speed: float = 620.0
    damage: float = 26.0

    def tick(self, actor, per, cmb, acc):
        d = actor.bb.slot(ATTACK_SLOT).get("dir")
        if d is None or d.length_squared() < 1e-9:
            d = pygame.Vector2(1, 0)
        acc.set_velocity(pygame.Vector2(d) * self.speed)
        actor.contact_damage = self.damage


@dataclass
class Blink(OneShot):
    """Teleport once to a random point `min_offset`..`max_offset` from the
    player, resolved against walls, and bump contact damage."""

    min_offset: float = 20.0
    max_offset: float = 70.0
    damage: float = 16.0

    def fire(self, actor, per, cmb):
        off = pygame.Vector2(per.rng.uniform(-1, 1), per.rng.uniform(-1, 1))
        if off.length_squared() > 0:
            off.scale_to_length(per.rng.uniform(self.min_offset, self.max_offset))
        actor.pos = per.resolve_movement(actor.pos, per.player_pos + off,
                                         actor.radius)
        actor.contact_damage = self.damage
        if hasattr(actor, "contact_cd"):
            actor.contact_cd = 0.0


@dataclass
class Explosion(OneShot):
    """Request one AoE blast at the actor. `require_range` (the brute's
    `slam_radius`) skips it if the player is further than that."""

    radius: float = 120.0
    damage: float = 28.0
    require_range: float | None = None

    def fire(self, actor, per, cmb):
        if (self.require_range is not None
                and (per.player_pos - actor.pos).length() > self.require_range):
            return
        cmb.explosion(pygame.Vector2(actor.pos), self.radius, self.damage)


@dataclass
class Explode(Component):
    """Self-destruct when the player is within `fuse_range`; the cull pass turns
    the corpse into the blast via `explode_radius` (the old `exploder`)."""

    fuse_range: float = 32.0

    def tick(self, actor, per, cmb, acc):
        if (per.player_pos - actor.pos).length() <= self.fuse_range:
            actor.hp = 0.0
            actor.alive = False
