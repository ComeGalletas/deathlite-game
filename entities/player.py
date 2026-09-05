"""The player hero.

Stats are resolved through a `StatSet` (base values + layered modifiers from the
chosen character, level-up upgrades, blessings, items and meta-progression).
`self.stats` is a cached plain dict rebuilt by `recompute()` whenever modifiers
change, so the hot combat loop reads a dict, not a solver.

Character identity lives in `self.trait` plus a few small hooks
(`incoming_damage_multiplier`, momentum) driven by `PlayingState`.
"""
from __future__ import annotations

import pygame

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
                 trait: str = "", character_id: str = "") -> None:
        self.pos = pygame.Vector2(x, y)
        self.radius = config.PLAYER_RADIUS
        self.character_id = character_id
        self.trait = trait

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
        self.momentum: float = 0.0      # Kestrel / Windborne
        self.still_time: float = 0.0     # Aegis / Bulwark
        self._hexed: set[int] = set()    # Nihil / Cursebrand -- enemies already cursed

        # Sprite-animation state (read by PlayingState's animator; harmless when
        # the hero has no sprite rig). `_facing` is +1 right / -1 left, kept
        # from the last non-zero horizontal input.
        self._hurt_t: float = 0.0
        self._attack_t: float = 0.0
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
    def incoming_damage_multiplier(self) -> float:
        if self.trait == "bulwark" and self.still_time >= 0.4:
            return 0.7
        return 1.0

    def outgoing_damage_multiplier(self) -> float:
        if self.trait == "windborne":
            return 1.0 + 0.07 * self.momentum
        return 1.0

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
        animation. No gameplay effect."""
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
        if self.trait == "windborne":
            self.momentum = (min(5.0, self.momentum + dt * 2.5) if moving
                             else max(0.0, self.momentum - dt * 3.5))

        if self._face_override:
            self._face_override = False       # `face()` already set it this frame
        elif self._move_dir.x > 0.01:
            self._facing = 1
        elif self._move_dir.x < -0.01:
            self._facing = -1
        self._hurt_t = max(0.0, self._hurt_t - dt)
        self._attack_t = max(0.0, self._attack_t - dt)

    def take_damage(self, amount: float) -> float:
        if self.invulnerable or not self.alive:
            return 0.0
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
