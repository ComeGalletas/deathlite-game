"""Enemy entity, data-driven from data/enemies.json.

One class, many variants: behavior comes from `entities.enemy_ai.BEHAVIORS`
keyed by the `behavior` field; variant-specific numbers (shield, explosion,
summon, slam, ...) are kept in `self.cfg` and read by the behavior functions.
Ordinary enemies use cheap steering, never pathfinding (spec 3.3).
"""
from __future__ import annotations

import pygame

from combat.damage import apply_armor
from combat.status import StatusState
from entities.enemy_ai import BEHAVIORS, EnemyContext, chase


class Enemy:
    def __init__(self, enemy_id: str, definition: dict, x: float, y: float) -> None:
        self.enemy_id = enemy_id
        self.cfg = definition
        self.name = definition.get("name", enemy_id)
        self.max_hp = float(definition["hp"])
        self.hp = self.max_hp
        self.speed = float(definition["speed"])
        self.contact_damage = float(definition["contact_damage"])
        self._base_contact = self.contact_damage  # FSM attacks bump this transiently
        self.radius = float(definition["radius"])
        self.xp_reward = int(definition.get("experience_reward", 1))
        self.behavior = definition.get("behavior", "chase")
        self.color = tuple(definition.get("color", (200, 90, 90)))
        self.tags = tuple(definition.get("tags", ()))
        self.is_elite = bool(definition.get("is_elite", False))

        self.shield_hp = float(definition.get("shield_hp", 0.0))
        self.explode_radius = float(definition.get("explode_radius", 0.0))
        self.explode_damage = float(definition.get("explode_damage", 0.0))

        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2()
        self.alive = True
        self.hit_flash = 0.0
        self._knock = pygame.Vector2()
        # Per-enemy transient behavior state (timers, sub-state).
        self.ai: dict = {}
        self.status = StatusState()

    # --- combat -----------------------------------------------------
    def apply_knockback(self, direction: pygame.Vector2, strength: float) -> None:
        # Elites and bosses resist being shoved around.
        if self.is_elite:
            strength *= 0.35
        if direction.length_squared() > 1e-6:
            self._knock += direction.normalize() * strength

    def take_damage(self, amount: float, armor: float = 0.0) -> float:
        dealt = apply_armor(amount, armor)
        self.hit_flash = 0.08
        if self.shield_hp > 0.0:
            absorbed = min(self.shield_hp, dealt)
            self.shield_hp -= absorbed
            dealt -= absorbed
        self.hp -= dealt
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False
        return dealt

    # --- per-frame ------------------------------------------------
    def update(self, ctx: EnemyContext) -> None:
        self.contact_damage = self._base_contact
        BEHAVIORS.get(self.behavior, chase)(self, ctx)

        dt = ctx.dt
        # Status DoT (burn) is dealt straight to HP and reported for stats.
        self.status.update(dt, lambda amt: self._status_damage(amt, ctx))
        # Chill scales movement; knockback is unaffected.
        step = (self.vel * self.status.speed_multiplier() + self._knock) * dt
        self.pos = ctx.resolve_movement(self.pos, self.pos + step, self.radius)
        self._knock *= pow(0.001, dt)
        if self._knock.length_squared() < 1.0:
            self._knock.update(0, 0)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

    def _status_damage(self, amount: float, ctx: EnemyContext) -> None:
        if not self.alive:
            return
        self.hp -= amount
        ctx.report_damage(amount)
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False

    @property
    def telegraphing(self) -> bool:
        return (self.ai.get("slam_state") == "telegraph"
                or self.ai.get("fs") == "telegraph")
