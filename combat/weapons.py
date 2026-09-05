"""Weapon runtime.

Weapons are data-driven (data/weapons.json) and fire automatically on a
cooldown (spec 3.2). Behavior differences come from data fields; three
`special_effect` values need extra logic:

  * "chain" -- projectile is redirected on hit by the collision resolver.
  * "cone"  -- fires one brief stationary arc; the resolver angle-filters hits.
  * "orbit" -- maintains N persistent projectiles circling the player.

Everything else is a straight auto-aimed shot.

CB-2: every weapon also has a `category` (`projectile` / `melee` / `summon` /
`orbit` / `spell`) and a **reach ring**. A weapon only fires while an enemy is
inside that ring; with the ring empty the hero drops to idle (the polling
`self._cd = 0.1` path keeps checking). Melee sizes the ring from its own cone
tip (`_area`); every other category reads an explicit `reach` field. The ring
scales with `area_multiplier` and `bonus["area"]`, so area blessings widen it.

CB-5: a manual aim (`FireContext.aim`, see `game/states/playing/aim.py`)
overrides all of that for the straight / chain / cone weapons: the attack goes
off in the aimed direction as soon as the cooldown allows, ring empty or not
(it may whiff), targeting the closest enemy inside an assist cone around the
aim if there is one. `FireContext.auto_attack` off + no manual aim = those
weapons hold. Orbit and summon take no direction; the orbiters do form while a
click is held so the ring is up whenever the player is actively attacking.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import pygame

from combat import targeting
from combat.damage import outgoing_damage
from game import config

# --- weapon taxonomy (the only fixed weapon data that stays in code) ---------
# Every `data/weapons.json` entry names one `category` and one `special_effect`
# from these sets; the values decide how the reach ring is sized, what "no
# target" means, and which extra fire path runs. All per-weapon numbers live in
# the JSON -- nothing here has a value default.
CATEGORIES = ("projectile", "melee", "summon", "orbit", "spell")
SPECIAL_EFFECTS = (None, "chain", "cone", "orbit", "summon")


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
    # CB-5: this frame's manual aim (`AimInput`, or None) and the `Q` toggle.
    aim: object | None = None
    auto_attack: bool = True

    @property
    def manual_fire(self) -> bool:
        """A manual attack is wanted this frame (held click / key, or a tap)."""
        return self.aim is not None and self.aim.wants_fire

    @property
    def click_held(self) -> bool:
        return (self.aim is not None and self.aim.source == "mouse"
                and self.aim.held)


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

    def __post_init__(self) -> None:
        if self.definition.get("category") not in CATEGORIES:
            raise ValueError(
                f"{self.weapon_id}: category "
                f"{self.definition.get('category')!r} not in {CATEGORIES}")

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

    @property
    def category(self) -> str:
        """One of `CATEGORIES` -- decides the reach ring and what "no target"
        means. Always present in the data (validated in `__post_init__`)."""
        return self.definition["category"]

    def _damage(self) -> float:
        return float(self.definition["damage"]) + self.bonus["damage"]

    def _cooldown(self, attack_speed_multiplier: float) -> float:
        base = float(self.definition["cooldown"]) * self.bonus["cooldown_mult"]
        return max(0.05, base / max(0.05, attack_speed_multiplier))

    def _projectile_count(self) -> int:
        return max(1, int(self.definition["projectile_count"])
                   + self.bonus["projectile_count"])

    def _pierce(self) -> int:
        return int(self.definition["pierce"]) + self.bonus["pierce"]

    def _area(self, area_multiplier: float) -> float:
        return (float(self.definition["area"]) + self.bonus["area"]) * area_multiplier

    def _reach(self, area_multiplier: float) -> float:
        """Radius of the reach ring (CB-2). Melee tracks the tip of its own cone
        (`_area`); every other category uses an explicit `reach` field. Both
        scale with `area_multiplier` and `bonus["area"]` (decision 2), so any
        area-growing blessing widens the ring too. A non-melee def with no
        `reach` is unbounded -- it fires exactly as it did before CB-2."""
        if self.category == "melee":
            return self._area(area_multiplier)
        if "reach" not in self.definition:
            return float("inf")
        return (float(self.definition["reach"]) + self.bonus["area"]) * area_multiplier

    @staticmethod
    def _within_reach(enemies, origin, reach: float) -> list:
        """Enemies whose centre lies within `reach` of `origin` (squared scan)."""
        r2 = reach * reach
        return [e for e in enemies if (e.pos - origin).length_squared() <= r2]

    # --- per-frame ---------------------------------------------
    def update(self, dt: float, ctx: FireContext) -> bool:
        """Advance the weapon; return True on the frame it produced an attack
        (a straight / chain / cone fire beat). Orbit + summon never report an
        attack -- they are not a hero "swing" -- so the attack animation, which
        only syncs to the main weapon, stays meaningful."""
        if self.special == "orbit":
            self._maintain_orbit(ctx)
            return False
        if self.special == "summon":
            self._maintain_summons(dt, ctx)
            return False

        self._cd -= dt
        if self._cd > 0.0:
            return False
        if ctx.manual_fire:
            # CB-5: attack where the player points, ring empty or not.
            self._fire(ctx, forced=True)
            self._cd = self._cooldown(ctx.attack_speed_multiplier)
            return True
        if not ctx.auto_attack:
            self._cd = 0.0  # hold, ready: the next manual attack is instant
            return False
        if self._fire(ctx):
            self._cd = self._cooldown(ctx.attack_speed_multiplier)
            return True
        self._cd = 0.1  # nothing to shoot yet; retry soon
        return False

    def _assist_half_angle(self) -> float:
        """Radians. The global `config.MANUAL_AIM_ASSIST_DEG` unless the
        weapon's data carries its own `aim_assist_deg`."""
        deg = self.definition.get("aim_assist_deg", config.MANUAL_AIM_ASSIST_DEG)
        return math.radians(float(deg))

    # --- summon --------------------------------------------
    def _maintain_summons(self, dt: float, ctx: FireContext) -> None:
        self._summons = [s for s in self._summons if getattr(s, "active", False)]
        self._cd -= dt
        max_count = self._projectile_count()
        if self._cd > 0.0 or len(self._summons) >= max_count:
            return
        d = self.definition
        # CB-2: the summon gets a leash ring centred on the hero -- it only
        # targets enemies inside it and idles when it is empty.
        reach = float(d["summon_reach"])
        # A non-positive `summon_lifetime` means "never expires" -- the spirit
        # wolf stays on field indefinitely; the totem keeps its 8 s.
        raw_life = float(d["summon_lifetime"])
        lifetime = float("inf") if raw_life <= 0.0 else raw_life
        s = ctx.spawn_summon(
            kind=d["summon_kind"],
            pos=ctx.anchor if ctx.anchor is not None else ctx.origin,
            damage=self._damage(),
            lifetime=lifetime,
            weapon_id=self.weapon_id,
            tags=self.tags,
            speed=float(d["summon_speed"]),
            attack_range=float(d["summon_attack_range"]),
            attack_interval=float(d["summon_attack_interval"]),
            reach=reach * ctx.area_multiplier)
        if s is not None:
            self._summons.append(s)
        self._cd = self._cooldown(ctx.attack_speed_multiplier)

    # --- straight / chain / cone ----------------------------
    def _fire(self, ctx: FireContext, forced: bool = False) -> bool:
        reach = self._reach(ctx.area_multiplier)
        if forced:
            # CB-5 manual attack: always goes off. The shot homes on the
            # closest enemy inside the assist cone around the aim, else flies
            # straight along it. Melee points the cone at the raw aim.
            manual = ctx.aim.direction
            in_cone = targeting.enemies_in_cone(
                ctx.origin, manual, ctx.enemies, self._assist_half_angle(), reach)
            aim = targeting.aim_direction(
                self.definition["targeting_mode"], ctx.origin, in_cone, manual)
            cone_dir = manual
        else:
            # CB-2: gate on the reach ring. The trigger is a cheap "anything in
            # the ring" test (decision 4); we then aim at the nearest enemy
            # *within* it, and a projectile still flies on past the ring.
            in_reach = self._within_reach(ctx.enemies, ctx.origin, reach)
            if not in_reach:
                return False       # ring empty -> hero idles; caller polls (_cd = 0.1)
            aim = targeting.aim_direction(
                self.definition["targeting_mode"],
                ctx.origin, in_reach, ctx.fallback_dir)
            if aim is None:
                return False
            cone_dir = aim

        area = self._area(ctx.area_multiplier)
        src_weight = float(self.definition["weight"])   # CB-3 hit knockback

        if self.special == "cone":
            dmg = outgoing_damage(self._damage(), ctx.damage_multiplier,
                                  ctx.crit_chance, ctx.crit_multiplier, ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(),
                damage=dmg.amount, radius=area,
                lifetime=float(self.definition["projectile_lifetime"]),
                pierce=self._pierce(), src_weight=src_weight,
                weapon_id=self.weapon_id, source_tags=self.tags,
                is_crit=dmg.is_crit, cone_dir=cone_dir,
                cone_half_angle=math.radians(self.definition["cone_half_angle"]))
            return True

        count = self._projectile_count()
        speed = float(self.definition["projectile_speed"]) * ctx.projectile_speed_multiplier
        lifetime = float(self.definition["projectile_lifetime"])
        is_chain = self.special == "chain"
        chain_left = int(self.definition["chain_count"]) if is_chain else 0
        chain_range = float(self.definition["chain_range"]) if is_chain else 0.0

        if count > 1:
            spread = math.radians(float(self.definition["spread_deg"])) * (count - 1)
            base_angle = math.atan2(aim.y, aim.x) - spread / 2
            step = spread / (count - 1)
        else:
            base_angle = math.atan2(aim.y, aim.x)
            step = 0.0
        for i in range(count):
            direction = pygame.Vector2(math.cos(base_angle + step * i),
                                       math.sin(base_angle + step * i))
            dmg = outgoing_damage(self._damage(), ctx.damage_multiplier,
                                  ctx.crit_chance, ctx.crit_multiplier, ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=direction * speed, damage=dmg.amount,
                radius=area, lifetime=lifetime, pierce=self._pierce(),
                src_weight=src_weight, weapon_id=self.weapon_id,
                source_tags=self.tags, is_crit=dmg.is_crit,
                chain_left=chain_left, chain_range=chain_range)
        return True

    # --- orbit ------------------------------------------
    def _maintain_orbit(self, ctx: FireContext) -> None:
        desired = self._projectile_count()
        # CB-2 decision 6: the embers orbit only while a foe is inside `reach`.
        # With the ring empty the hero lowers it -- the orbiters are dropped and
        # re-form, evenly spaced, the moment a target returns. CB-5: a held
        # click raises them too, so the ring spins whenever the player is
        # actively attacking (a held aim key alone does not).
        if not ctx.click_held and not self._within_reach(
                ctx.enemies, ctx.origin, self._reach(ctx.area_multiplier)):
            desired = 0
        radius = float(self.definition["orbit_radius"])
        orbit_speed = float(self.definition["orbit_speed"])
        rehit = float(self.definition["rehit_interval"])
        area = self._area(ctx.area_multiplier)
        dmg = outgoing_damage(self._damage(), ctx.damage_multiplier).amount

        self._orbiters = [o for o in self._orbiters if getattr(o, "active", False)]

        while len(self._orbiters) < desired:
            o = ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(), damage=dmg, radius=area,
                lifetime=float(self.definition["projectile_lifetime"]),
                pierce=self._pierce(),
                src_weight=float(self.definition["weight"]),
                weapon_id=self.weapon_id, source_tags=self.tags, anchor=ctx.anchor,
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
