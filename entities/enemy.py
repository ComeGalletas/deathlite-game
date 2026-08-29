"""Enemy entity, data-driven from data/enemies.json.

One class, many variants: `self.behavior` names a builder in `entities/ai`
(`build_behavior`) which composes a component pipeline; variant-specific numbers
(shield, explosion, summon, slam, ...) come from `self.cfg`. Per-frame behaviour
state lives on `self.bb` (a namespaced `Blackboard`).
"""
from __future__ import annotations

import pygame

from combat.damage import apply_armor
from combat.status import StatusState
from entities.ai import Blackboard, build_behavior
from game import config
from game.assets import get_assets
from systems.animation import Animator

_MACHINE = "__machine__"


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
        # Contact damage lands as a bite every `contact_interval` s (armor is a
        # flat per-hit subtraction). `contact_cd` counts down to the next bite.
        self.contact_interval = float(
            definition.get("contact_interval", config.INCOMING_TICK_INTERVAL))
        self.contact_cd = 0.0
        self.radius = float(definition["radius"])
        # CB-3 bump/knockback mass. Fallback ~= radius/2; elites carry the
        # folded "resist knockback" as extra weight (see data/enemies.json).
        self.weight = float(definition.get("weight", self.radius / 2.0))
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
        # Per-enemy transient behaviour state, in namespaced blackboard slots.
        self.bb = Blackboard()
        self._behavior = build_behavior(self.behavior, self.cfg)
        self.status = StatusState()

        # Sprite animation (only for variants that declare a rig; the rest draw
        # a primitive). `_hurt_t` drives the flinch anim; `_facing` is +1/-1.
        rig = definition.get("sprite")
        self.anim = Animator(get_assets(), rig) if rig else None
        # `_hurt_t` drives the hit tint; only switch to a real "hurt" strip if
        # the rig actually has one (the current packs do not -- the renderer
        # red-tints the live frame instead).
        self._has_hurt = self.anim is not None and get_assets().frame_count(rig, "hurt") > 0
        self._hurt_t = 0.0
        self._facing = -1

    # --- combat -----------------------------------------------------
    def apply_knockback(self, direction: pygame.Vector2, strength: float) -> None:
        # CB-3: resistance is expressed as `weight` now (the caller runs
        # `knock_split` against it), so there is no per-type damping here.
        if direction.length_squared() > 1e-6:
            self._knock += direction.normalize() * strength

    def take_damage(self, amount: float, armor: float = 0.0) -> float:
        dealt = apply_armor(amount, armor)
        self.hit_flash = 0.08
        if self.anim is not None:
            self._hurt_t = 0.26                     # hit-tint window
            if self._has_hurt:
                self.anim.play("hurt", restart=True)
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
    def update(self, ctx) -> None:
        self.contact_damage = self._base_contact
        self.contact_cd = max(0.0, self.contact_cd - ctx.dt)
        self._behavior.tick(self, ctx, ctx)          # ctx satisfies Perception + Combat

        dt = ctx.dt
        # Status DoT (burn) is dealt straight to HP and reported for stats.
        self.status.update(dt, lambda amt: self._status_damage(amt, ctx))
        # Chill scales movement; knockback is unaffected.
        step = (self.vel * self.status.speed_multiplier() + self._knock) * dt
        self.pos = ctx.resolve_movement(self.pos, self.pos + step, self.radius)
        self._knock *= pow(config.BUMP_DECAY, dt)
        if self._knock.length_squared() < 1.0:
            self._knock.update(0, 0)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

        self._hurt_t = max(0.0, self._hurt_t - dt)
        if self.anim is not None:
            fdx = ctx.player_pos.x - self.pos.x
            if fdx > 1.0:
                self._facing = 1
            elif fdx < -1.0:
                self._facing = -1
            self.anim.play(self._anim_name())
            self.anim.update(dt)

    def _anim_name(self) -> str:
        if not self.alive:
            return "death"
        if self._hurt_t > 0.0 and self._has_hurt:
            return "hurt"
        if self._attacking:
            return "attack"                 # FSM wind-up + strike / brute slam
        return "walk" if self.vel.length_squared() > 1.0 else "idle"

    @property
    def _attacking(self) -> bool:
        return self.bb.slot(_MACHINE).get("state") in ("telegraph", "attack")

    def _status_damage(self, amount: float, ctx) -> None:
        if not self.alive:
            return
        self.hp -= amount
        ctx.report_damage(amount)
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False

    @property
    def telegraphing(self) -> bool:
        return self.bb.slot(_MACHINE).get("state") == "telegraph"
