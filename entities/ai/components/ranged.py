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
    player is within `max_range` (the old kiter used `prefer_distance * 1.8`).

    `style` / `rig` / `pierce` are R1 of
    `journals/enemy_roster_expansion_journal.md`: what the shot is *drawn* as,
    and whether it passes through a body. Left unset the shot is the red
    `arrow` every enemy fired before, so no existing enemy moves.
    """

    interval: float = 2.0
    damage: float = 6.0
    speed: float = 220.0
    radius: float = 6.0
    max_range: float = 1.0e9
    style: str = ""
    rig: str = ""
    pierce: int = 0
    tint: tuple | None = None
    lifetime: float = 6.0
    stop_after: float = 0.0
    blast_radius: float = 0.0

    def fire(self, actor, per, cmb) -> bool:
        """Loose one shot at the player, ignoring the timer and the range.

        Split out of `tick` so a telegraphed kiter can fire from the
        wind-up's end transition instead (`kite_shoot`), which is what makes
        the shot and the animation one event. One definition of what a shot
        *is*, whichever path releases it.
        """
        to = per.player_pos - actor.pos
        if to.length_squared() <= 1e-6:
            return False
        fx = {}
        if self.rig:
            fx["rig"] = self.rig
        if self.tint:
            fx["tint"] = tuple(self.tint)
        cmb.fire_projectile(pos=actor.pos, vel=to.normalize() * self.speed,
                            damage=self.damage, radius=self.radius,
                            style=self.style, fx=fx or None,
                            pierce=int(self.pierce),
                            lifetime=self.lifetime,
                            stop_after=self.stop_after,
                            blast_radius=self.blast_radius,
                            inert=self.blast_radius > 0.0)
        return True

    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        s["t"] = s.get("t", self.interval) - per.dt
        if s["t"] > 0.0:
            return
        to = per.player_pos - actor.pos
        if to.length() > self.max_range:
            return                              # timer stays <= 0: fire on re-entry
        s["t"] = self.interval
        self.fire(actor, per, cmb)


@dataclass
class SummonBrood(Component):
    """Spawn `count` of `enemy_id` at the actor every `interval` s."""

    interval: float = 4.0
    enemy_id: str = "bumblebee"
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
