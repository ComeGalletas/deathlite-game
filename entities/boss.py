"""The boss (spec 3.7).

A small finite-state machine cycles authored attack patterns, each with a
visible telegraph before the dangerous frames. Not "a big enemy with more HP":
it has three distinct patterns (radial bullet ring, telegraphed charge, brood
summon), a health bar (drawn by the HUD) and a currency reward on death.

Duck-types the bits of `Enemy` the combat loop needs: `pos`, `radius`, `alive`,
`hit_flash`, `is_elite`, `tags`, `take_damage`, `apply_knockback`,
`contact_damage`.
"""
from __future__ import annotations

import math

import pygame

from combat.damage import apply_armor
from combat.status import StatusState
from entities.enemy_ai import EnemyContext
from game import config
from game.assets import get_assets
from systems.animation import Animator


class Boss:
    def __init__(self, boss_id: str, definition: dict, x: float, y: float) -> None:
        self.boss_id = boss_id
        self.cfg = definition
        self.name = definition.get("name", boss_id)
        self.max_hp = float(definition["hp"])
        self.hp = self.max_hp
        self.speed = float(definition["speed"])
        self._base_contact = float(definition["contact_damage"])
        self.contact_damage = self._base_contact
        # Contact lands as a timed bite, like ordinary enemies (see Enemy).
        self.contact_interval = float(
            definition.get("contact_interval", config.INCOMING_TICK_INTERVAL))
        self.contact_cd = 0.0
        self.radius = float(definition["radius"])
        self.xp_reward = int(definition.get("experience_reward", 200))
        self.reward_currency = int(definition.get("reward_currency", 50))
        self.color = tuple(definition.get("color", (180, 40, 70)))
        self.tags = tuple(definition.get("tags", ("boss",)))
        self.is_elite = True

        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2()
        self.alive = True
        self.hit_flash = 0.0
        self.status = StatusState()
        # Duck-typed to satisfy the shared combat loop / draw code.
        self.shield_hp = 0.0
        self.explode_radius = 0.0

        self._patterns = list(definition.get("patterns", []))
        self._pattern_index = -1
        self.pattern: dict = {}
        self.phase = "intro"          # intro -> telegraph -> active -> recover
        self.phase_t = 1.4
        self.phase_len = 1.4
        self._charge_dir = pygame.Vector2()

        # Sprite animation (same contract as Enemy: idle / walk / attack, no
        # hurt/death strip -> the renderer red-tints on hit + plays the shared
        # `dead` poof).
        rig = definition.get("sprite")
        self.anim = Animator(get_assets(), rig) if rig else None
        self._has_hurt = self.anim is not None and get_assets().frame_count(rig, "hurt") > 0
        self._hurt_t = 0.0
        self._facing = -1

    # --- combat --------------------------------------------------
    def take_damage(self, amount: float, armor: float = 0.0) -> float:
        dealt = apply_armor(amount, armor)
        self.hp -= dealt
        self.hit_flash = 0.06
        if self.anim is not None:
            self._hurt_t = 0.22
            if self._has_hurt:
                self.anim.play("hurt", restart=True)
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False
        return dealt

    def apply_knockback(self, *_args) -> None:
        pass  # immovable

    @property
    def hp_fraction(self) -> float:
        return 0.0 if self.max_hp <= 0 else max(0.0, self.hp / self.max_hp)

    @property
    def telegraph_fraction(self) -> float:
        if self.phase != "telegraph" or self.phase_len <= 0:
            return 0.0
        return 1.0 - max(0.0, self.phase_t / self.phase_len)

    # --- FSM ----------------------------------------------------
    def _enter(self, phase: str, length: float) -> None:
        self.phase = phase
        self.phase_t = self.phase_len = max(0.0001, length)

    def _next_pattern(self) -> None:
        self._pattern_index = (self._pattern_index + 1) % len(self._patterns)
        self.pattern = self._patterns[self._pattern_index]
        self._enter("telegraph", float(self.pattern.get("telegraph", 0.8)))

    def _anim_name(self) -> str:
        if not self.alive:
            return "death"
        if self._hurt_t > 0.0 and self._has_hurt:
            return "hurt"
        if self.phase in ("telegraph", "active"):
            return "attack"                    # wind-up + the dangerous frames
        return "walk" if self.vel.length_squared() > 1.0 else "idle"

    def update(self, ctx: EnemyContext) -> None:
        dt = ctx.dt
        self.contact_cd = max(0.0, self.contact_cd - dt)
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
        self.status.update(dt, lambda amt: self._status_damage(amt, ctx))
        self.contact_damage = self._base_contact
        chill = self.status.speed_multiplier()

        if not self._patterns:
            self.vel = (ctx.player_pos - self.pos)
            if self.vel.length_squared() > 1:
                self.vel.scale_to_length(self.speed)
            self.pos = ctx.resolve_movement(self.pos, self.pos + self.vel * dt * chill,
                                            self.radius)
            return

        self.phase_t -= dt
        handler = getattr(self, f"_phase_{self.phase}", None)
        if handler:
            handler(ctx)

        # Chill does not slow the committed charge dash.
        scale = (1.0 if self.pattern.get("id") == "charge" and self.phase == "active"
                 else chill)
        self.pos = ctx.resolve_movement(self.pos, self.pos + self.vel * dt * scale,
                                        self.radius)

    def _status_damage(self, amount: float, ctx: EnemyContext) -> None:
        if not self.alive:
            return
        self.hp -= amount
        ctx.report_damage(amount)
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False

    # drift slowly toward the player unless a pattern overrides velocity
    def _approach(self, ctx: EnemyContext, factor: float = 0.5) -> None:
        d = ctx.player_pos - self.pos
        self.vel = d.normalize() * self.speed * factor if d.length_squared() > 1 else pygame.Vector2()

    def _phase_intro(self, ctx: EnemyContext) -> None:
        self._approach(ctx, 0.3)
        if self.phase_t <= 0.0:
            self._next_pattern()

    def _phase_telegraph(self, ctx: EnemyContext) -> None:
        self._approach(ctx, 0.25)
        if self.phase_t <= 0.0:
            self._fire_pattern(ctx)
            self._enter("active", float(self.pattern.get("duration", 0.3)))

    def _phase_active(self, ctx: EnemyContext) -> None:
        if self.pattern.get("id") == "charge":
            self.vel = self._charge_dir * float(self.pattern.get("charge_speed", 700))
            self.contact_damage = float(self.pattern.get("charge_damage", self._base_contact))
        else:
            self.vel = pygame.Vector2()
        if self.phase_t <= 0.0:
            self._enter("recover", float(self.pattern.get("recover", 1.5)))

    def _phase_recover(self, ctx: EnemyContext) -> None:
        self._approach(ctx, 0.5)
        if self.phase_t <= 0.0:
            self._next_pattern()

    # --- pattern effects ------------------------------------
    def _fire_pattern(self, ctx: EnemyContext) -> None:
        pid = self.pattern.get("id")
        if pid == "radial_barrage":
            n = int(self.pattern.get("bullets", 18))
            spd = float(self.pattern.get("bullet_speed", 180))
            dmg = float(self.pattern.get("bullet_damage", 10))
            for i in range(n):
                ang = (math.tau / n) * i
                ctx.fire_projectile(
                    pos=self.pos,
                    vel=pygame.Vector2(math.cos(ang), math.sin(ang)) * spd,
                    damage=dmg, radius=7)
        elif pid == "charge":
            d = ctx.player_pos - self.pos
            self._charge_dir = d.normalize() if d.length_squared() > 1 else pygame.Vector2(1, 0)
        elif pid == "summon_brood":
            ctx.summon(self.pattern.get("summon_id", "swarm"), self.pos,
                       int(self.pattern.get("summon_count", 6)))
