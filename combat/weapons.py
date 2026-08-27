"""Weapon runtime.

Weapons are data-driven (data/weapons.json) and fire automatically on a
cooldown (spec 3.2). Behavior differences come from data fields; three
`special_effect` values need extra logic:

  * "chain" -- projectile is redirected on hit by the collision resolver.
  * "cone"  -- fires one brief stationary arc; the resolver angle-filters hits.
  * "orbit" -- maintains N persistent projectiles circling the player.

Everything else is a straight auto-aimed shot.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import pygame

from combat import targeting
from combat.damage import outgoing_damage


@dataclass
class FireContext:
    origin: pygame.Vector2
    enemies: list
    damage_multiplier: float
    attack_speed_multiplier: float
    projectile_speed_multiplier: float
    area_multiplier: float
    fallback_dir: pygame.Vector2
    spawn_projectile: Callable[..., object]
    anchor: pygame.Vector2 | None = None   # live player-position ref for orbit
    crit_chance: float = 0.0
    crit_multiplier: float = 2.0
    rng: object | None = None
    spawn_summon: Callable[..., object] = lambda **kw: None


@dataclass
class Weapon:
    weapon_id: str
    definition: dict
    level: int = 1
    _cd: float = field(default=0.0, init=False)
    bonus: dict = field(default_factory=lambda: {
        "damage": 0.0, "cooldown_mult": 1.0, "projectile_count": 0, "area": 0.0,
        "pierce": 0,
    })
    _orbiters: list = field(default_factory=list, init=False)
    _orbit_count: int = field(default=0, init=False)
    _summons: list = field(default_factory=list, init=False)

    # --- derived stats -------------------------------------------
    @property
    def name(self) -> str:
        return self.definition.get("name", self.weapon_id)

    @property
    def tags(self) -> tuple[str, ...]:
        return tuple(self.definition.get("tags", ()))

    @property
    def special(self) -> str | None:
        return self.definition.get("special_effect")

    def _damage(self) -> float:
        return float(self.definition["damage"]) + self.bonus["damage"]

    def _cooldown(self, attack_speed_multiplier: float) -> float:
        base = float(self.definition["cooldown"]) * self.bonus["cooldown_mult"]
        return max(0.05, base / max(0.05, attack_speed_multiplier))

    def _projectile_count(self) -> int:
        return max(1, int(self.definition.get("projectile_count", 1))
                   + self.bonus["projectile_count"])

    def _pierce(self) -> int:
        return int(self.definition.get("pierce", 0)) + self.bonus["pierce"]

    def _area(self, area_multiplier: float) -> float:
        return (float(self.definition.get("area", 5)) + self.bonus["area"]) * area_multiplier

    # --- per-frame ---------------------------------------------
    def update(self, dt: float, ctx: FireContext) -> None:
        if self.special == "orbit":
            self._maintain_orbit(ctx)
            return
        if self.special == "summon":
            self._maintain_summons(dt, ctx)
            return

        self._cd -= dt
        if self._cd > 0.0:
            return
        if self._fire(ctx):
            self._cd = self._cooldown(ctx.attack_speed_multiplier)
        else:
            self._cd = 0.1  # nothing to shoot yet; retry soon

    # --- summon --------------------------------------------
    def _maintain_summons(self, dt: float, ctx: FireContext) -> None:
        self._summons = [s for s in self._summons if getattr(s, "active", False)]
        self._cd -= dt
        max_count = self._projectile_count()
        if self._cd > 0.0 or len(self._summons) >= max_count:
            return
        d = self.definition
        s = ctx.spawn_summon(
            kind=d.get("summon_kind", "totem"),
            pos=ctx.anchor if ctx.anchor is not None else ctx.origin,
            damage=self._damage(),
            lifetime=float(d.get("summon_lifetime", 8.0)),
            color=tuple(d.get("color", (150, 220, 190))),
            tags=self.tags,
            speed=float(d.get("summon_speed", 0.0)),
            attack_range=float(d.get("summon_attack_range", 320.0)),
            attack_interval=float(d.get("summon_attack_interval", 0.7)))
        if s is not None:
            self._summons.append(s)
        self._cd = self._cooldown(ctx.attack_speed_multiplier)

    # --- straight / chain / cone ----------------------------
    def _fire(self, ctx: FireContext) -> bool:
        aim = targeting.aim_direction(
            self.definition.get("targeting_mode", "nearest"),
            ctx.origin, ctx.enemies, ctx.fallback_dir)
        if aim is None:
            return False

        area = self._area(ctx.area_multiplier)
        color = tuple(self.definition.get("color", (255, 255, 255)))
        knockback = float(self.definition.get("knockback", 0.0))

        if self.special == "cone":
            dmg = outgoing_damage(self._damage(), ctx.damage_multiplier,
                                  ctx.crit_chance, ctx.crit_multiplier, ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(),
                damage=dmg.amount, radius=area,
                lifetime=float(self.definition.get("projectile_lifetime", 0.14)),
                pierce=self._pierce(), knockback=knockback, color=color,
                source_tags=self.tags, is_crit=dmg.is_crit,
                cone_dir=aim,
                cone_half_angle=math.radians(self.definition.get("cone_half_angle", 45)))
            return True

        count = self._projectile_count()
        speed = float(self.definition["projectile_speed"]) * ctx.projectile_speed_multiplier
        lifetime = float(self.definition.get("projectile_lifetime", 1.5))
        is_chain = self.special == "chain"
        chain_left = int(self.definition.get("chain_count", 0)) if is_chain else 0
        chain_range = float(self.definition.get("chain_range", 0.0)) if is_chain else 0.0

        spread = math.radians(12) * (count - 1)
        base_angle = math.atan2(aim.y, aim.x) - spread / 2
        for i in range(count):
            angle = base_angle + (spread / (count - 1)) * i if count > 1 else base_angle
            direction = pygame.Vector2(math.cos(angle), math.sin(angle))
            dmg = outgoing_damage(self._damage(), ctx.damage_multiplier,
                                  ctx.crit_chance, ctx.crit_multiplier, ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=direction * speed, damage=dmg.amount,
                radius=area, lifetime=lifetime, pierce=self._pierce(),
                knockback=knockback, color=color, source_tags=self.tags,
                is_crit=dmg.is_crit, chain_left=chain_left, chain_range=chain_range)
        return True

    # --- orbit ------------------------------------------
    def _maintain_orbit(self, ctx: FireContext) -> None:
        desired = self._projectile_count()
        radius = float(self.definition.get("orbit_radius", 90))
        orbit_speed = float(self.definition.get("orbit_speed", 3.0))
        rehit = float(self.definition.get("rehit_interval", 0.4))
        area = self._area(ctx.area_multiplier)
        color = tuple(self.definition.get("color", (255, 180, 90)))
        dmg = outgoing_damage(self._damage(), ctx.damage_multiplier).amount

        self._orbiters = [o for o in self._orbiters if getattr(o, "active", False)]

        while len(self._orbiters) < desired:
            o = ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(), damage=dmg, radius=area,
                lifetime=1e9, pierce=999,
                knockback=float(self.definition.get("knockback", 0.0)),
                color=color, source_tags=self.tags, anchor=ctx.anchor,
                orbit_angle=0.0, orbit_radius=radius, orbit_speed=orbit_speed,
                rehit_interval=rehit)
            if o is None:
                break
            self._orbiters.append(o)

        # Trim if a projectile-count downgrade ever happens.
        while len(self._orbiters) > desired:
            self._orbiters.pop().active = False

        # Re-space evenly when the count changed; always refresh live stats so
        # upgrades to damage/area take effect immediately.
        respace = len(self._orbiters) != self._orbit_count
        self._orbit_count = len(self._orbiters)
        n = max(1, len(self._orbiters))
        for i, o in enumerate(self._orbiters):
            if respace:
                o.orbit_angle = (math.tau / n) * i
            o.damage = dmg
            o.radius = area
            o.orbit_radius = radius
            o.orbit_speed = orbit_speed
