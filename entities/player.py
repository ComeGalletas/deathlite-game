"""The player hero.

Stats are resolved through a `StatSet` (base values + layered modifiers from the
chosen character, level-up upgrades, blessings, items and meta-progression).
`self.stats` is a cached plain dict rebuilt by `recompute()` whenever modifiers
change, so the hot combat loop reads a dict, not a solver.

Character identity lives in `self.trait` + `self.trait_params` (both from
`data/characters.json`) and three small hooks: `incoming_damage_multiplier`
(Bulwark), `weapon_mods` (Double Shot, Quick Cast -- handed to weapons through
`FireContext.weapon_mods`) and the evasion / block rolls in `take_damage`
(six-weapon system P1, design §20).
"""
from __future__ import annotations

import random

import pygame

from combat.weapons import NO_MODS, WeaponMods
from game import config
from progression.stats import Modifier, StatSet

def _any(pressed, keys) -> bool:
    return any(pressed[k] for k in keys)


def input_vector(pressed, keyset: dict) -> pygame.Vector2:
    """Unit direction from a key-state sequence. Pure; diagonals normalised.

    `keyset` is one direction table from `config.KEY_LAYOUTS` -- the layout's
    `"move"` table for walking, its `"aim"` table for manual aim (CB-5) --
    mapping `left / right / up / down` to tuples of raw SDL keycodes."""
    x = float(_any(pressed, keyset["right"])) - float(_any(pressed, keyset["left"]))
    y = float(_any(pressed, keyset["down"])) - float(_any(pressed, keyset["up"]))
    vec = pygame.Vector2(x, y)
    if vec.length_squared() > 0:
        vec.normalize_ip()
    return vec


class Player:
    def __init__(self, x: float, y: float, *, base_stats: dict | None = None,
                 trait: str = "", character_id: str = "",
                 trait_params: dict | None = None, rng=None) -> None:
        self.pos = pygame.Vector2(x, y)
        self.radius = config.PLAYER_RADIUS
        self.character_id = character_id
        self.trait = trait
        self.trait_params: dict = dict(trait_params or {})
        # Evasion / block rolls. `PlayingState` hands in the run's seeded RNG;
        # a bare `Player` (tests, menus) gets its own.
        self.rng = rng if rng is not None else random.Random()

        # CB-3 physics: the hero has mass and can be shoved. `_knock` is an
        # extra velocity (px/s) that decays each frame, mirroring `Enemy`.
        self.weight = float(config.PLAYER_WEIGHT)
        self._knock = pygame.Vector2()

        merged = dict(config.PLAYER_DEFAULTS)
        merged.update(base_stats or {})
        self.statset = StatSet(merged)
        self.stats: dict[str, float] = {}
        self.recompute()

        self.hp: float = self.max_hp
        self.alive = True
        self._move_dir = pygame.Vector2()
        self.invulnerable = False
        self.weapons: list = []
        self.upgrade_stacks: dict[str, int] = {}

        # Blessings (Milestone 6): id -> stacks, plus rebuilt aggregate effects.
        self.blessings: dict[str, int] = {}
        self.blessing_fx = None  # set by progression.blessings.rebuild

        # Trait runtime state.
        self.still_time: float = 0.0     # Aegis / Bulwark
        # What the last `take_damage` did, for feedback: "evaded" / "blocked" / "".
        self.last_defense: str = ""

        # Sprite-animation state (read by PlayingState's animator; harmless when
        # the hero has no sprite rig). `_facing` is +1 right / -1 left, kept
        # from the last non-zero horizontal input.
        self._hurt_t: float = 0.0
        self._attack_t: float = 0.0
        self._attack_cycle: int = 0      # P5: odd -> the second attack sheet
        self._facing: int = 1
        # CB-5: a manual aim faces the hero for this frame; `update` then
        # skips the movement-facing rule once and clears the flag.
        self._face_override: bool = False

    # --- stats -----------------------------------------------------
    def recompute(self) -> None:
        self.stats = self.statset.as_dict()
        if hasattr(self, "hp"):
            self.hp = min(self.hp, self.max_hp)

    def add_modifiers(self, *mods: Modifier) -> None:
        self.statset.add(*mods)
        self.recompute()

    def remove_modifier_source(self, source: str) -> None:
        self.statset.remove_source(source)
        self.recompute()

    @property
    def max_hp(self) -> float:
        return self.stats["max_hp"]

    @property
    def move_speed(self) -> float:
        return self.stats["move_speed"]

    @property
    def pickup_radius(self) -> float:
        return self.stats["pickup_radius"]

    # --- trait hooks --------------------------------------------
    @property
    def bulwark_active(self) -> bool:
        """Aegis: the guard is up after `still_after` seconds without moving.
        Read by the sprite animator too (the guard sheet, P5)."""
        return (self.trait == "bulwark"
                and self.still_time >= float(self.trait_params["still_after"]))

    def incoming_damage_multiplier(self) -> float:
        if self.bulwark_active:
            return float(self.trait_params["damage_taken_mult"])
        return 1.0

    def outgoing_damage_multiplier(self) -> float:
        return 1.0

    def weapon_by_id(self, weapon_id: str):
        """The owned `Weapon` with this id, or None (P2: the hit resolver and
        the on-kill hook look the firing weapon up by the projectile's id)."""
        if not weapon_id:
            return None
        for w in self.weapons:
            if w.weapon_id == weapon_id:
                return w
        return None

    def weapon_mods(self, weapon) -> WeaponMods:
        """Per-weapon trait modifiers (P1). Double Shot: extra Bow arrows at a
        damage split. Quick Cast: a Rod cooldown multiplier. Every number is
        the hero's `trait_params`; a trait that names no weapon does nothing."""
        tp = self.trait_params
        if not tp or tp.get("weapon") != weapon.weapon_id:
            return NO_MODS
        return WeaponMods(
            extra_projectiles=int(tp.get("extra_projectiles", 0)),
            cooldown_mult=float(tp.get("cooldown_mult", 1.0)),
            damage_mult=float(tp.get("damage_mult", 1.0)))

    # --- per-frame ---------------------------------------------
    def handle_input(self, pressed, move_keys: dict) -> None:
        self._move_dir = input_vector(pressed, move_keys)

    def face(self, direction: pygame.Vector2) -> None:
        """CB-5: face along a manual aim for this frame, overriding the
        movement rule. A vertical aim keeps the current facing."""
        if direction.x > 0.01:
            self._facing = 1
        elif direction.x < -0.01:
            self._facing = -1
        self._face_override = True

    def trigger_attack_anim(self, duration: float = 0.38) -> None:
        """Called by PlayingState when a weapon fires -- drives the attack
        animation. No gameplay effect. A fresh attack (the previous one had
        played out) advances `_attack_cycle`, which picks the sheet (P5)."""
        if self._attack_t <= 0.0:
            self._attack_cycle += 1
        self._attack_t = max(self._attack_t, duration)

    def apply_knockback(self, direction: pygame.Vector2, strength: float) -> None:
        """CB-3: add an outward impulse (px/s) that decays over ~0.7 s -- the
        bump resolver calls this when an enemy overlaps the hero."""
        if direction.length_squared() > 1e-6:
            self._knock += direction.normalize() * strength

    def update(self, dt: float, world) -> None:
        # Input velocity plus any bump impulse (`_knock`), integrated together
        # so a shove slides along walls via `resolve_movement`.
        target = self.pos + (self._move_dir * self.move_speed + self._knock) * dt
        #self.pos = world.resolve_movement(self.pos, target, self.radius)
        self.pos.update(world.resolve_movement(self.pos, target, self.radius)) # to fix the issue with static orbitals
        self._knock *= pow(config.BUMP_DECAY, dt)
        if self._knock.length_squared() < 1.0:
            self._knock.update(0, 0)

        moving = self._move_dir.length_squared() > 0
        self.still_time = 0.0 if moving else self.still_time + dt

        if self._face_override:
            self._face_override = False       # `face()` already set it this frame
        elif self._move_dir.x > 0.01:
            self._facing = 1
        elif self._move_dir.x < -0.01:
            self._facing = -1
        self._hurt_t = max(0.0, self._hurt_t - dt)
        self._attack_t = max(0.0, self._attack_t - dt)

    def take_damage(self, amount: float) -> float:
        """Incoming hit (design §20): evasion negates it, a block removes
        `block_strength` of it, then the trait multiplier, then flat armour."""
        if self.invulnerable or not self.alive:
            return 0.0
        self.last_defense = ""
        if self.rng.random() < self.stats["evasion_chance"]:
            self.last_defense = "evaded"
            return 0.0
        if self.rng.random() < self.stats["block_chance"]:
            self.last_defense = "blocked"
            amount *= max(0.0, 1.0 - self.stats["block_strength"])
        amount *= self.incoming_damage_multiplier()
        dealt = max(0.0, amount - self.stats["armor"])
        self.hp -= dealt
        if dealt > 0:
            self._hurt_t = 0.30          # ~4 frames @ 14 fps (hurt animation)
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False
        return dealt

    def heal(self, amount: float) -> None:
        self.hp = min(self.max_hp, self.hp + amount)
