"""Weapon runtime (the core of the `combat.weapons` package).

Weapons are data-driven (data/weapons/weapons.json) and fire automatically on a
cooldown (spec 3.2). Behavior differences come from data fields; four
`special_effect` values need extra logic:

  * "chain" -- projectile is redirected on hit by the collision resolver.
  * "cone"  -- fires one brief stationary arc; the resolver angle-filters hits.
  * "orbit" -- maintains N persistent projectiles circling the player.
  * "bomb"  -- a fused throw that detonates into a blast (`bomb.py`).

Everything else is a straight auto-aimed shot.

Six-weapon system (P1, `documentation/plans/weapon_system_plan.md`): every
weapon also names a `class` -- `melee` / `ranged` (the three weapon slots of
a run) or `summon` (its own single slot). Hero traits reach a weapon through
`FireContext.weapon_mods`, a callable the hero supplies that returns the
per-weapon `WeaponMods` (extra projectiles, cooldown and damage multipliers)
so a weapon granted mid-run gets them too.

CB-2: every weapon also has a `category` (`projectile` / `melee` / `summon` /
`orbit` / `spell`) and a **reach ring**. A weapon only fires while an enemy is
inside that ring; with the ring empty the hero drops to idle (the polling
`self._cd = 0.1` path keeps checking). Melee sizes the ring from its own cone
tip (`_area`); every other category reads an explicit `reach` field. The ring
scales with `area_multiplier` and `bonus["area"]`, so area blessings widen it.

CB-5: a manual aim (`FireContext.aim`, see `game/states/playing/core/aim.py`)
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
from combat.elements.ids import ElementId
from game import config

# --- weapon taxonomy (the only fixed weapon data that stays in code) ---------
# Every `data/weapons/weapons.json` entry names one `category` and one `special_effect`
# from these sets; the values decide how the reach ring is sized, what "no
# target" means, and which extra fire path runs. All per-weapon numbers live in
# the JSON -- nothing here has a value default.
CATEGORIES = ("projectile", "melee", "summon", "orbit", "spell")
SPECIAL_EFFECTS = (None, "chain", "cone", "orbit", "summon", "bomb", "slam")
# The slot a weapon occupies: melee / ranged share the run's three weapon
# slots (design §20); a summon has its own single slot (§3.7).
CLASSES = ("melee", "ranged", "summon")
# How a weapon decides which of its hits carry its element (owner's
# decision, 2026-09-21). `attack` counts attacks and stamps the whole
# attack; `time` grants one application per window, decided at hit time.
# Two modes are needed because "one firing = one attack" is false here:
# the Ember Ring's orbiters and the summons re-hit on their own timers
# and never fire an attack at all.
ATTACK_MODE, TIME_MODE = "attack", "time"
ELEMENT_MODES = (ATTACK_MODE, TIME_MODE)


@dataclass(frozen=True)
class WeaponMods:
    """Per-weapon modifiers a hero trait contributes at fire time."""
    extra_projectiles: int = 0
    cooldown_mult: float = 1.0
    damage_mult: float = 1.0


NO_MODS = WeaponMods()


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
    # P1: hero trait modifiers per weapon (`Player.weapon_mods`); None = none.
    weapon_mods: Callable[["Weapon"], WeaponMods] | None = None
    # P2: the melee / ranged stat blessings (design §21); summons get neither.
    melee_damage_mult: float = 1.0
    ranged_damage_mult: float = 1.0
    # P3: hero-owned ground hazards (Meteor Hammer). `None` = no hazards.
    spawn_hazard: Callable[..., object] | None = None
    # CR1: the Hammer's impact sheet (`slam.py`). `None` = no visual.
    spawn_impact: Callable[..., object] | None = None

    def mods_for(self, weapon: "Weapon") -> WeaponMods:
        if self.weapon_mods is None:
            return NO_MODS
        return self.weapon_mods(weapon) or NO_MODS

    def class_damage_mult(self, weapon_class: str) -> float:
        if weapon_class == "melee":
            return self.melee_damage_mult
        if weapon_class == "ranged":
            return self.ranged_damage_mult
        return 1.0

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
    # Numeric fire-time bonuses. Blessings add to (or multiply) these; the
    # fire path reads `definition + bonus`. Keys are the catalog's
    # `weapon_bonus` fields (P2).
    bonus: dict = field(default_factory=lambda: {
        "damage": 0.0, "cooldown_mult": 1.0, "projectile_count": 0, "area": 0.0,
        "pierce": 0, "crit_chance": 0.0, "weight": 0.0, "stun_chance": 0.0,
        "stun_duration": 0.0, "blast_radius": 0.0, "blast_radius_mult": 1.0,
        "aim_assist_deg": 0.0,
        "chain_count": 0, "chain_range": 0.0, "cone_half_angle": 0.0,
        "summon_lifetime": 0.0,
        # Six blessings per weapon (2026-09-19, `six_blessings_journal.md`):
        # crit damage, the reach ring, the ember ring's radius and rehit,
        # and the summons' bite interval / run speed / leash.
        "crit_damage": 0.0, "reach": 0.0, "orbit_radius": 0.0, "rehit_mult": 1.0,
        "orbit_speed_mult": 1.0,
        "attack_interval_mult": 1.0, "summon_speed": 0.0, "summon_reach": 0.0,
        # How often the weapon's element lands: fewer skipped attacks,
        # or a shorter window.
        "element_interval": 0.0, "element_window_mult": 1.0,
    })
    # Behaviour hooks the hit resolver / fire path read by key (P2): totals
    # set by `weapon_effect` blessings -- executioner_mult, split_count, ...
    effects: dict = field(default_factory=dict)
    # P3: the Forging this weapon took (`data/weapons/forges.json` id), or None.
    forge: str | None = None
    # The element infused into this weapon, or NONE. Run-scoped: a new
    # `Weapon` is built per run, so nothing has to clear it.
    element: ElementId = ElementId.NONE
    # Attack mode: does the attack now being fired carry the element?
    _element_this_attack: bool = field(default=False, init=False)
    # Time mode: the run-clock instant the next application is due.
    _next_element_at: float = field(default=0.0, init=False)
    _shots: int = field(default=0, init=False)          # attacks fired (Overcharge)
    _volley_mult: float = field(default=1.0, init=False)
    # CR1 slam: the pending swing -- seconds left, its full length, and the
    # locked direction (None = no swing pending).
    _swing_t: float = field(default=0.0, init=False)
    _swing_total: float = field(default=0.0, init=False)
    _swing_dir: object = field(default=None, init=False)
    _orbiters: list = field(default_factory=list, init=False)
    _orbit_count: int = field(default=0, init=False)
    _summons: list = field(default_factory=list, init=False)
    # Seconds left before another summon may be planted after one left the
    # field (`summon_replant_delay`, scaled by the weapon's cooldown bonus).
    _replant_t: float = field(default=0.0, init=False)
    # Flurry (Daggers): the stacks taken from the target's hit streak on the
    # last hit, and the seconds left before they go cold (the synergy window).
    _flurry_stacks: int = field(default=0, init=False)
    _flurry_t: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.definition.get("category") not in CATEGORIES:
            raise ValueError(
                f"{self.weapon_id}: category "
                f"{self.definition.get('category')!r} not in {CATEGORIES}")
        if self.definition.get("class") not in CLASSES:
            raise ValueError(
                f"{self.weapon_id}: class "
                f"{self.definition.get('class')!r} not in {CLASSES}")
        if self.definition.get("special_effect") not in SPECIAL_EFFECTS:
            raise ValueError(
                f"{self.weapon_id}: special_effect "
                f"{self.definition.get('special_effect')!r} not in {SPECIAL_EFFECTS}")
        self._check_element_application()

    def _check_element_application(self) -> None:
        """`element_application` is required on every weapon and names one
        of two modes with the number that mode needs. Validated here like
        the rest of the taxonomy, so bad data fails at load rather than on
        the first infusion."""
        spec = self.definition.get("element_application")
        if not isinstance(spec, dict):
            raise ValueError(
                f"{self.weapon_id}: element_application must be an object")
        mode = spec.get("mode")
        if mode not in ELEMENT_MODES:
            raise ValueError(
                f"{self.weapon_id}: element_application mode {mode!r} not in {ELEMENT_MODES}")
        if mode == ATTACK_MODE:
            if int(spec["interval"]) < 0:
                raise ValueError(
                    f"{self.weapon_id}: element interval must be >= 0")
        elif float(spec["window"]) <= 0.0:
            raise ValueError(
                f"{self.weapon_id}: element window must be > 0")

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

    @property
    def weapon_class(self) -> str:
        """One of `CLASSES` -- which slot the weapon takes (P1)."""
        return self.definition["class"]

    @property
    def is_summon(self) -> bool:
        return self.weapon_class == "summon"

    @property
    def visual_id(self) -> str:
        """The `weapon_visuals.json` key for this weapon's shots: its Forge
        when forged (P3), so a Forging can carry its own look."""
        return self.forge or self.weapon_id

    def _damage(self, ctx: FireContext | None = None) -> float:
        base = float(self.definition["damage"]) + self.bonus["damage"]
        if ctx is not None:
            base *= ctx.mods_for(self).damage_mult
            base *= ctx.class_damage_mult(self.weapon_class)
        return base

    def effect(self, key: str, default: float = 0.0) -> float:
        """A Forge / blessing effect value: the `effects` total plus any
        `bonus` a post-Forge blessing added under the same key (P3)."""
        return float(self.effects.get(key, default)) + float(self.bonus.get(key, 0.0))

    def _volley_damage(self, ctx: FireContext) -> float:
        """Damage for the attack being fired: `_damage` times the Overcharge
        multiplier when this is the Nth attack (P2)."""
        return self._damage(ctx) * self._volley_mult

    def _crit_chance(self, ctx: FireContext) -> float:
        return ctx.crit_chance + self.bonus["crit_chance"]

    def _crit_multiplier(self, ctx: FireContext) -> float:
        """The hero's crit multiplier plus the weapon's own `crit_damage`
        bonus (Critical Edge)."""
        return ctx.crit_multiplier + self.bonus["crit_damage"]

    # --- Flurry (Daggers) ---------------------------------------
    def _flurry_rate(self) -> float:
        """`1 + flurry_per_hit x stacks` while the streak is warm, else 1."""
        per_hit = float(self.effects.get("flurry_per_hit", 0.0))
        if per_hit <= 0.0 or self._flurry_t <= 0.0 or self._flurry_stacks <= 0:
            return 1.0
        return 1.0 + per_hit * self._flurry_stacks

    def note_flurry(self, streak: int, window: float) -> None:
        """A hit landed on a target whose consecutive-hit streak by this
        weapon is now `streak` (this hit included); the stacks stay warm for
        `window` seconds and are capped by `flurry_max`."""
        if "flurry_per_hit" not in self.effects:
            return
        cap = int(self.effects.get("flurry_max", 5))
        self._flurry_stacks = max(0, min(int(streak), cap))
        self._flurry_t = float(window)

    @property
    def flurry_stacks(self) -> int:
        return self._flurry_stacks if self._flurry_t > 0.0 else 0

    def _weight(self) -> float:
        return float(self.definition["weight"]) + self.bonus["weight"]

    # --- elemental infusion ---------------------------------------
    @property
    def element_mode(self) -> str:
        """`attack` or `time` -- how this weapon paces its element."""
        return self.definition["element_application"]["mode"]

    @property
    def element_interval(self) -> int:
        """Attack mode: attacks skipped between element-carrying ones.
        0 means every attack."""
        base = int(self.definition["element_application"]["interval"])
        return max(0, base + int(self.bonus["element_interval"]))

    @property
    def element_window(self) -> float:
        """Time mode: seconds between applications."""
        base = float(self.definition["element_application"]["window"])
        return max(0.01, base * self.bonus["element_window_mult"])

    @property
    def infused(self) -> bool:
        return self.element != ElementId.NONE

    @property
    def attack_element(self) -> ElementId:
        """The element to stamp on the projectiles of the attack being
        fired. `NONE` for a plain attack, and always `NONE` for a
        time-mode weapon, whose hits are gated at the hit site instead.
        """
        return self.element if self._element_this_attack else ElementId.NONE

    def take_element_window(self, now: float) -> bool:
        """Time mode: claim this window's one application, if it is due.

        Called once per hit by the hit resolver, so the first hit a
        time-mode weapon lands after the window elapses carries the
        element and the rest are plain -- which is what makes the
        re-hitting weapons (orbiters, summons) sane.
        """
        if not self.infused or self.element_mode != TIME_MODE:
            return False
        if now < self._next_element_at:
            return False
        self._next_element_at = now + self.element_window
        return True

    def _begin_attack(self) -> None:
        """Count the attack, set the volley multiplier (Overcharge: every
        `overcharge_every`-th attack is an overcharged one), and decide
        whether this attack carries the weapon's element."""
        self._shots += 1
        # One decision per attack, shared by every projectile it spawns
        # and every pierce they score -- never a per-hit check.
        self._element_this_attack = (
            self.infused and self.element_mode == ATTACK_MODE
            and (self._shots - 1) % (self.element_interval + 1) == 0)
        every = int(self.effects.get("overcharge_every", 0))
        if every > 0 and self._shots % every == 0:
            self._volley_mult = float(self.effects.get("overcharge_mult", 1.0))
        else:
            self._volley_mult = 1.0

    def _cooldown(self, attack_speed_multiplier: float,
                  ctx: FireContext | None = None) -> float:
        base = float(self.definition["cooldown"]) * self.bonus["cooldown_mult"]
        if ctx is not None:
            base *= ctx.mods_for(self).cooldown_mult
        base /= self._flurry_rate()
        if self.special == "slam":
            # CR1: attack speed shortens the *swing*; the rest between blows
            # answers only to the cooldown bonuses and trait mods.
            return max(0.05, base)
        return max(0.05, base / max(0.05, attack_speed_multiplier))

    # --- slam (CR1) ----------------------------------------------
    @property
    def swing_progress(self) -> float:
        """0 at the start of a pending swing, 1 as it lands; 0 with none."""
        if self._swing_dir is None or self._swing_total <= 0.0:
            return 0.0
        return min(1.0, max(0.0, 1.0 - self._swing_t / self._swing_total))

    def slam_centre(self, origin) -> pygame.Vector2:
        from combat.weapons import slam
        direction = self._swing_dir if self._swing_dir is not None else pygame.Vector2(1, 0)
        return slam.centre(self, origin, direction)

    def _projectile_count(self, ctx: FireContext | None = None) -> int:
        # Blessing data lands in `bonus` as floats (bug journal #2); the count
        # must stay an int because it feeds `range()`.
        n = int(self.definition["projectile_count"]) + int(self.bonus["projectile_count"])
        if ctx is not None:
            n += ctx.mods_for(self).extra_projectiles
        return max(1, n)

    def _pierce(self) -> int:
        return int(self.definition["pierce"]) + int(self.bonus["pierce"])

    def _area(self, area_multiplier: float) -> float:
        return (float(self.definition["area"]) + self.bonus["area"]) * area_multiplier

    def _blast_radius(self, area_multiplier: float) -> float:
        """Radius of the Bomb's detonation -- damage circle and, through
        `TransientFx.burst_visual`, the explosion art drawn over it.

        Bound to the area system the way `_reach` is (2026-09-12): the data's
        `blast_radius` plus the flat `bonus["blast_radius"]` and the same
        `bonus["area"]` every other size bonus feeds, all scaled by the hero's
        `area_multiplier` and then by `bonus["blast_radius_mult"]`. Before
        this the blast read its data field alone, so an `of Expanse` affix
        widened every weapon's area and every reach ring while leaving the one
        weapon that *is* an area untouched."""
        base = (float(self.definition["blast_radius"])
                + self.bonus["blast_radius"] + self.bonus["area"])
        return max(0.0, base * area_multiplier * self.bonus["blast_radius_mult"])

    def _reach(self, area_multiplier: float) -> float:
        """Radius of the reach ring (CB-2). Melee tracks the tip of its own cone
        (`_area`); every other category uses an explicit `reach` field. Both
        scale with `area_multiplier` and `bonus["area"]` (decision 2), so any
        area-growing blessing widens the ring too. A non-melee def with no
        `reach` is unbounded -- it fires exactly as it did before CB-2."""
        if self.special == "slam":
            from combat.weapons import slam
            return slam.reach(self, area_multiplier)   # CR1: offset + radius
        if self.category == "melee":
            return self._area(area_multiplier)
        if "reach" not in self.definition:
            return float("inf")
        return ((float(self.definition["reach"]) + self.bonus["area"]
                 + self.bonus["reach"]) * area_multiplier)

    @staticmethod
    def _within_reach(enemies, origin, reach: float) -> list:
        """Enemies whose *body* reaches within `reach` of `origin`: centre
        distance minus the enemy's radius (a stand-in with no radius counts
        its centre). The hit test overlaps circles, so a big enemy whose body
        already sits in the arc must also count as "in reach" -- with a short
        swing (the Sword's 32 px) the centre alone never gets close enough
        to a tank (CR2)."""
        out = []
        for e in enemies:
            d = (e.pos - origin).length() - float(getattr(e, "radius", 0.0) or 0.0)
            if d <= reach:
                out.append(e)
        return out

    # --- per-frame ---------------------------------------------
    def update(self, dt: float, ctx: FireContext) -> bool:
        """Advance the weapon; return True on the frame it produced an attack
        (a straight / chain / cone fire beat). Orbit + summon never report an
        attack -- they are not a hero "swing" -- so the attack animation, which
        only syncs to the main weapon, stays meaningful."""
        if self._flurry_t > 0.0:
            self._flurry_t -= dt
        if self.special == "orbit":
            self._maintain_orbit(ctx)
            return False
        if self.special == "summon":
            self._maintain_summons(dt, ctx)
            return False

        if self.special == "slam":
            return self._update_slam(dt, ctx)

        self._cd -= dt
        if self._cd > 0.0:
            return False
        if ctx.manual_fire:
            # CB-5: attack where the player points, ring empty or not.
            self._fire(ctx, forced=True)
            self._cd = self._cooldown(ctx.attack_speed_multiplier, ctx)
            return True
        if not ctx.auto_attack:
            self._cd = 0.0  # hold, ready: the next manual attack is instant
            return False
        if self._fire(ctx):
            self._cd = self._cooldown(ctx.attack_speed_multiplier, ctx)
            return True
        self._cd = 0.1  # nothing to shoot yet; retry soon
        return False

    def _update_slam(self, dt: float, ctx: FireContext) -> bool:
        """CR1: a swing in progress counts down and lands (the attack beat);
        otherwise the cooldown runs and, once ready, a swing begins where a
        plain weapon would have fired. Manual aim and the `Q` toggle gate the
        *start* of a swing exactly as they gate a shot."""
        from combat.weapons import slam
        if self._swing_dir is not None:
            self._swing_t -= dt
            if self._swing_t > 0.0:
                return False
            slam.land(self, ctx)
            self._cd = self._cooldown(ctx.attack_speed_multiplier, ctx)
            return True
        self._cd -= dt
        if self._cd > 0.0:
            return False
        if ctx.manual_fire:
            slam.begin_swing(self, ctx, forced=True)
            return False
        if not ctx.auto_attack:
            self._cd = 0.0
            return False
        if not slam.begin_swing(self, ctx, forced=False):
            self._cd = 0.1
        return False

    def _assist_half_angle(self) -> float:
        """Radians. The global `config.MANUAL_AIM_ASSIST_DEG` unless the
        weapon's data carries its own `aim_assist_deg`."""
        deg = self.definition.get("aim_assist_deg", config.MANUAL_AIM_ASSIST_DEG)
        return math.radians(float(deg) + self.bonus["aim_assist_deg"])

    # --- summon --------------------------------------------
    def _maintain_summons(self, dt: float, ctx: FireContext) -> None:
        d = self.definition
        live = [s for s in self._summons if getattr(s, "active", False)]
        if self._summons and not live:
            # The field just **emptied** -- the owner's rule is about the
            # field, not about one summon: "no totem on the field for 5 s
            # between the spawns" (2026-09-12). With more than one slot
            # (Twin Totems) the gap therefore starts when the last one
            # leaves, not when the first does. `summon_replant_delay` is
            # shortened by the same cooldown bonus Quick Plant applies to
            # the weapon's own cooldown.
            gap = float(d["summon_replant_delay"]) * self.bonus["cooldown_mult"]
            self._replant_t = max(self._replant_t, gap)
        self._summons = live
        self._cd -= dt
        self._replant_t = max(0.0, self._replant_t - dt)
        max_count = self._projectile_count(ctx)
        self._refresh_summons(ctx)
        if self._cd > 0.0 or self._replant_t > 0.0 or len(self._summons) >= max_count:
            return
        # A non-positive `summon_lifetime` means "never expires" -- the spirit
        # wolf stays on field indefinitely; the totem keeps its 8 s.
        raw_life = float(d["summon_lifetime"])
        lifetime = (float("inf") if raw_life <= 0.0
                    else raw_life + self.bonus["summon_lifetime"])
        s = ctx.spawn_summon(
            kind=d["summon_kind"],
            pos=ctx.anchor if ctx.anchor is not None else ctx.origin,
            damage=self._damage(ctx),
            lifetime=lifetime,
            weapon_id=self.weapon_id,
            tags=self.tags,
            speed=self._summon_speed(),
            attack_range=float(d["summon_attack_range"]),
            attack_interval=self._summon_attack_interval(),
            reach=self._summon_reach(ctx.area_multiplier))
        if s is not None:
            self._summons.append(s)
        self._cd = self._cooldown(ctx.attack_speed_multiplier, ctx)

    def _summon_speed(self) -> float:
        return float(self.definition["summon_speed"]) + self.bonus["summon_speed"]

    def _summon_attack_interval(self) -> float:
        return (float(self.definition["summon_attack_interval"])
                * self.bonus["attack_interval_mult"])

    def _summon_reach(self, area_multiplier: float) -> float:
        """CB-2: the leash ring centred on the hero -- the summon only targets
        enemies inside it and idles when it is empty. Long Stride widens it."""
        return ((float(self.definition["summon_reach"]) + self.bonus["summon_reach"])
                * area_multiplier)

    def _refresh_summons(self, ctx: FireContext) -> None:
        """Live summons pick up damage, run speed, bite interval and leash the
        frame a blessing changes them, the way the orbiters do."""
        if not self._summons:
            return
        dmg = self._damage(ctx)
        speed = self._summon_speed()
        interval = self._summon_attack_interval()
        reach = self._summon_reach(ctx.area_multiplier)
        for s in self._summons:
            s.damage = dmg
            s.speed = speed
            if s.attack_interval != interval:
                s.attack_interval = interval
                s.attack_cd = min(s.attack_cd, interval)
            s.reach = reach

    # --- straight / chain / cone ----------------------------
    def _pick_aim(self, ctx: FireContext, forced: bool):
        """Where the attack goes: `(aim, cone_dir, candidates)`, or None when
        an auto attack has nothing in reach."""
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
            candidates = in_cone
        else:
            # CB-2: gate on the reach ring. The trigger is a cheap "anything in
            # the ring" test (decision 4); we then aim at the nearest enemy
            # *within* it, and a projectile still flies on past the ring.
            in_reach = self._within_reach(ctx.enemies, ctx.origin, reach)
            if not in_reach:
                return None        # ring empty -> hero idles; caller polls (_cd = 0.1)
            aim = targeting.aim_direction(
                self.definition["targeting_mode"],
                ctx.origin, in_reach, ctx.fallback_dir)
            if aim is None:
                return None
            cone_dir = aim
            candidates = in_reach
        return aim, cone_dir, candidates

    def _fire(self, ctx: FireContext, forced: bool = False) -> bool:
        picked = self._pick_aim(ctx, forced)
        if picked is None:
            return False
        aim, cone_dir, candidates = picked

        area = self._area(ctx.area_multiplier)
        src_weight = self._weight()                      # CB-3 hit knockback
        self._begin_attack()

        if self.special == "cone":
            self._fire_cones(ctx, cone_dir, area, src_weight)
            return True

        if self.special == "bomb":
            from combat.weapons.bomb import throw_bombs
            throw_bombs(self, ctx, aim, candidates, area, src_weight)
            return True

        count = self._projectile_count(ctx)
        speed = float(self.definition["projectile_speed"]) * ctx.projectile_speed_multiplier
        lifetime = float(self.definition["projectile_lifetime"])
        # Chain: the data's own chain fields (a chain-special weapon) plus the
        # Chain blessing's bonus (P2) -- any weapon with charges chains.
        chain_left = (int(self.definition.get("chain_count", 0))
                      + int(self.bonus["chain_count"]))
        chain_range = (float(self.definition.get("chain_range", 0.0))
                       + self.bonus["chain_range"])
        if chain_left <= 0:
            chain_range = 0.0

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
            dmg = outgoing_damage(self._volley_damage(ctx), ctx.damage_multiplier,
                                  self._crit_chance(ctx), self._crit_multiplier(ctx), ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=direction * speed, damage=dmg.amount,
                radius=area, lifetime=lifetime, pierce=self._pierce(),
                src_weight=src_weight, weapon_id=self.weapon_id,
                visual=self.visual_id,
                source_tags=self.tags, is_crit=dmg.is_crit,
                chain_left=chain_left, chain_range=chain_range,
                element=self.attack_element)
        return True

    def _cone_directions(self, cone_dir: pygame.Vector2) -> list:
        """One cone, or two fanned by the Twin Daggers offset (P3)."""
        off = self.effect("twin_offset_deg")
        if off <= 0.0:
            return [cone_dir]
        return [cone_dir.rotate(-off), cone_dir.rotate(off)]

    def _fire_cones(self, ctx: FireContext, cone_dir: pygame.Vector2, area: float,
                    src_weight: float) -> None:
        """The melee swing: a stationary cone per direction, plus the Forge
        extras -- Earthshaker's shockwave blast past the impact and Meteor
        Hammer's crater hazard under it (P3)."""
        d = self.definition
        half = float(d["cone_half_angle"]) + self.bonus["cone_half_angle"]
        stun_chance = float(d.get("stun_chance", 0.0)) + self.bonus["stun_chance"]
        stun_duration = float(d.get("stun_duration", 0.0)) + self.bonus["stun_duration"]
        for direction in self._cone_directions(cone_dir):
            dmg = outgoing_damage(self._volley_damage(ctx), ctx.damage_multiplier,
                                  self._crit_chance(ctx), self._crit_multiplier(ctx), ctx.rng)
            ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(),
                damage=dmg.amount, radius=area,
                lifetime=float(d["projectile_lifetime"]),
                pierce=self._pierce(), src_weight=src_weight,
                weapon_id=self.weapon_id, visual=self.visual_id,
                source_tags=self.tags, is_crit=dmg.is_crit, cone_dir=direction,
                cone_half_angle=math.radians(half),
                stun_chance=stun_chance, stun_duration=stun_duration,
                swing=self._shots,                      # CR2: picks the slash
                element=self.attack_element)
        fx = self.effects
        impact = ctx.origin + cone_dir * (area * 0.55)
        if self.effect("shockwave_radius") > 0.0:
            base = self._volley_damage(ctx) * float(fx.get("shockwave_damage_mult", 0.5))
            dmg = outgoing_damage(base, ctx.damage_multiplier,
                                  self._crit_chance(ctx), self._crit_multiplier(ctx), ctx.rng)
            ctx.spawn_projectile(
                pos=impact, vel=pygame.Vector2(), damage=dmg.amount,
                radius=self.effect("shockwave_radius"), lifetime=0.15, pierce=999,
                src_weight=src_weight * 0.5, weapon_id=self.weapon_id,
                visual=self.visual_id, source_tags=self.tags + ("shockwave",),
                is_crit=dmg.is_crit, style="blast", no_block=True,
                element=self.attack_element)
        if self.effect("hazard_radius") > 0.0 and ctx.spawn_hazard is not None:
            ctx.spawn_hazard(
                pos=impact, radius=self.effect("hazard_radius"),
                dps=self._volley_damage(ctx) * float(fx.get("hazard_dps_mult", 0.3)),
                duration=self.effect("hazard_duration", 2.0),
                weapon_id=self.weapon_id, source_tags=self.tags + ("crater",))

    # --- orbit ------------------------------------------
    def _maintain_orbit(self, ctx: FireContext) -> None:
        desired = self._projectile_count(ctx)
        # CB-2 decision 6: the embers orbit only while a foe is inside `reach`.
        # With the ring empty the hero lowers it -- the orbiters are dropped and
        # re-form, evenly spaced, the moment a target returns. CB-5: a held
        # click raises them too, so the ring spins whenever the player is
        # actively attacking (a held aim key alone does not).
        if not ctx.click_held and not self._within_reach(
                ctx.enemies, ctx.origin, self._reach(ctx.area_multiplier)):
            desired = 0
        radius = float(self.definition["orbit_radius"]) + self.bonus["orbit_radius"]
        orbit_speed = float(self.definition["orbit_speed"]) * self.bonus["orbit_speed_mult"]
        rehit = float(self.definition["rehit_interval"]) * self.bonus["rehit_mult"]
        area = self._area(ctx.area_multiplier)
        dmg = outgoing_damage(self._damage(ctx), ctx.damage_multiplier).amount

        # `active` alone is not enough: projectiles are pooled, so an orbiter
        # retired by anything but this weapon (terrain, the dev menu) can be
        # handed to another weapon and come back `active` as, say, the
        # Hammer's blow -- which the refresh below would then shrink to a
        # mote. Keep only objects that are still *this weapon's* orbiters.
        self._orbiters = [o for o in self._orbiters
                          if getattr(o, "active", False)
                          and o.weapon_id == self.weapon_id
                          and o.orbit_speed != 0.0]

        while len(self._orbiters) < desired:
            o = ctx.spawn_projectile(
                pos=ctx.origin, vel=pygame.Vector2(), damage=dmg, radius=area,
                lifetime=float(self.definition["projectile_lifetime"]),
                pierce=self._pierce(),
                src_weight=self._weight(),
                weapon_id=self.weapon_id, visual=self.visual_id,
                source_tags=self.tags, anchor=ctx.anchor,
                orbit_angle=0.0, orbit_radius=radius, orbit_speed=orbit_speed,
                rehit_interval=rehit,
                # Orbiters never fire an attack, so they are time mode and
                # carry nothing: the hit site asks the weapon instead.
                element=self.attack_element)
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
            if o.rehit_interval != rehit:         # Fanned Flames
                o.rehit_interval = rehit
                o.rehit_timer = min(o.rehit_timer, rehit)
