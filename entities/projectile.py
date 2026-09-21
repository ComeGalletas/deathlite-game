"""Projectile: pooled, short-lived. Used for player shots and, with
`hostile=True`, enemy/boss shots.

Movement modes:
  * straight  -- default; travels along `vel`.
  * orbit     -- Ember Ring; circles `anchor` (a live reference to the player
                 position) at `orbit_radius`, re-clearing `hit_ids` every
                 `rehit_interval` so it keeps scoring hits.
Extra hit filters:
  * cone_half_angle > 0  -- Soul Scythe; the collision resolver also requires
                 the target to lie within this angle of `cone_dir`.
  * chain_left > 0        -- chain upgrades; resolver redirects instead of despawning.
  * inert                 -- Bomb (P1); never scores a direct hit. `stop_after`
                 seconds after the throw it halts; when it expires (or is
                 blocked) `TransientFx.detonate` spawns a blast of
                 `blast_radius` that lasts `blast_lifetime`.
  * stun_chance > 0       -- Hammer (P1); the resolver rolls a stun on hit.
  * bounces_left > 0      -- a pinball (buff buildings); the obstacle and
                 terrain blocks reflect it instead of killing it.
`weapon_id` names the weapon that fired it (synergies read it later).

`fire_level` carries the terrain elevation the shot was fired from, for the
LD-9 D10 rule; see `TransientFx.block_on_terrain`.
"""
from __future__ import annotations

import math

import pygame

from combat.elements.ids import ElementId as _ElementId
from world.elevation import NONE as _NO_LEVEL

_NO_ELEMENT = _ElementId.NONE


class Projectile:
    __slots__ = (
        "active", "pos", "vel", "damage", "radius", "lifetime", "pierce_left",
        "src_weight", "color", "hit_ids", "source_tags", "is_crit", "hostile",
        "chain_left", "chain_range",
        "anchor", "orbit_angle", "orbit_radius", "orbit_speed",
        "rehit_interval", "rehit_timer",
        "cone_dir", "cone_half_angle", "style", "fx", "trail_shed",
        "fire_level",
        "weapon_id", "age", "stop_after", "inert", "blast_radius",
        "blast_lifetime", "detonated", "stun_chance", "stun_duration",
        "no_block", "mine", "arm_delay", "swing", "sticky", "stuck_to",
        "bounces_left", "element",
    )

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.damage = 0.0
        self.radius = 4.0
        self.lifetime = 0.0
        self.pierce_left = 0
        self.src_weight = 0.0          # CB-3: wielder-independent weapon weight for hit knockback
        self.color = (255, 255, 255)
        self.hit_ids: set[int] = set()
        self.source_tags: tuple[str, ...] = ()
        self.is_crit = False
        self.hostile = False
        self.chain_left = 0
        self.chain_range = 0.0
        self.anchor: pygame.Vector2 | None = None
        self.orbit_angle = 0.0
        self.orbit_radius = 0.0
        self.orbit_speed = 0.0
        self.rehit_interval = 0.0
        self.rehit_timer = 0.0
        self.cone_dir = pygame.Vector2(1, 0)
        self.cone_half_angle = 0.0
        self.style = ""          # render-only: forces a `projectiles/` draw family
        self.fx: dict = {}       # render-only: per-weapon effect tuning
        self.trail_shed = 0.0    # render-only: world px travelled since the last trail puff
        # LD-9 D10: the terrain elevation this shot was fired from. Stamped by
        # the spawner right after `reset`, because only the spawner knows the
        # true muzzle position -- by the projectile's first update it has
        # already moved several pixels, which at a rim is enough to sample the
        # wrong tile. `NONE` disables the rule, which is what a flat world and
        # every unit test that builds a projectile directly get.
        self.fire_level = _NO_LEVEL
        self.weapon_id = ""
        self.age = 0.0
        self.stop_after = 0.0        # > 0: halt after this many seconds
        self.inert = False           # no direct hits (a fused bomb)
        self.blast_radius = 0.0      # > 0: detonate on expiry / block
        self.blast_lifetime = 0.0
        self.detonated = False
        self.stun_chance = 0.0
        self.stun_duration = 0.0
        self.no_block = False        # a stationary blast: walls cannot stop it
        self.mine = False            # P3 Minefield: detonates when an enemy steps on it
        self.arm_delay = 0.0         # ...once this old
        self.swing = 0               # CR2: the attack's ordinal (1 = first); picks the slash
        self.sticky = False          # Sticky Bomb: attaches to the first enemy it touches...
        self.stuck_to = None         # ...and this is the enemy it rides on
        # Buff buildings: a pinball reflects off obstacles, cliffs and the
        # shoreline this many more times before it is spent; 0 for every
        # ordinary shot, which the blocks kill on contact as before.
        self.bounces_left = 0
        # Elemental system: the element this attack carries, stamped by
        # the spawner (M6). `NONE` for a plain attack, which is every
        # attack until a weapon is infused.
        self.element = _NO_ELEMENT

    def reset(self, *, pos, vel, damage: float, radius: float, lifetime: float,
              pierce: int = 0, src_weight: float = 0.0, color=(255, 255, 255),
              source_tags: tuple[str, ...] = (), is_crit: bool = False,
              hostile: bool = False, chain_left: int = 0, chain_range: float = 0.0,
              anchor=None, orbit_angle: float = 0.0, orbit_radius: float = 0.0,
              orbit_speed: float = 0.0, rehit_interval: float = 0.0,
              cone_dir=None, cone_half_angle: float = 0.0, style: str = "",
              fx: dict | None = None, weapon_id: str = "",
              stop_after: float = 0.0, inert: bool = False,
              blast_radius: float = 0.0, blast_lifetime: float = 0.0,
              stun_chance: float = 0.0, stun_duration: float = 0.0,
              no_block: bool = False, mine: bool = False,
              arm_delay: float = 0.0, swing: int = 0, sticky: bool = False,
              bounces: int = 0, element=_NO_ELEMENT) -> None:
        self.pos.update(pos)
        self.vel.update(vel)
        self.damage = damage
        self.radius = radius
        self.lifetime = lifetime
        self.pierce_left = pierce
        self.src_weight = src_weight
        self.color = color
        self.hit_ids.clear()
        self.source_tags = source_tags
        self.is_crit = is_crit
        self.hostile = hostile
        self.chain_left = chain_left
        self.chain_range = chain_range
        self.anchor = anchor
        self.orbit_angle = orbit_angle
        self.orbit_radius = orbit_radius
        self.orbit_speed = orbit_speed
        self.rehit_interval = rehit_interval
        self.rehit_timer = rehit_interval
        self.cone_dir.update(cone_dir if cone_dir is not None else (1, 0))
        self.cone_half_angle = cone_half_angle
        self.style = style
        self.fx = fx if fx is not None else {}
        self.trail_shed = 0.0
        # Pooled: a recycled projectile must not inherit the last shot's level.
        self.fire_level = _NO_LEVEL
        self.weapon_id = weapon_id
        self.age = 0.0
        self.stop_after = stop_after
        self.inert = inert
        self.blast_radius = blast_radius
        self.blast_lifetime = blast_lifetime
        self.detonated = False
        self.stun_chance = stun_chance
        self.stun_duration = stun_duration
        self.no_block = no_block
        self.mine = mine
        self.arm_delay = arm_delay
        self.swing = swing
        self.sticky = sticky
        self.stuck_to = None
        self.bounces_left = int(bounces)
        self.element = element

    def update(self, dt: float) -> None:
        if self.orbit_speed != 0.0 and self.anchor is not None:
            self.orbit_angle += self.orbit_speed * dt
            self.pos.update(
                self.anchor.x + math.cos(self.orbit_angle) * self.orbit_radius,
                self.anchor.y + math.sin(self.orbit_angle) * self.orbit_radius)
            if self.rehit_interval > 0.0:
                self.rehit_timer -= dt
                if self.rehit_timer <= 0.0:
                    self.rehit_timer = self.rehit_interval
                    self.hit_ids.clear()
            return  # orbiters are persistent: no lifetime countdown

        self.age += dt
        if self.rehit_interval > 0.0:
            # A travelling shot with a re-hit interval (the pinball) keeps
            # scoring on the enemies it rolls through, the way an orbiter does.
            self.rehit_timer -= dt
            if self.rehit_timer <= 0.0:
                self.rehit_timer = self.rehit_interval
                self.hit_ids.clear()
        if self.stop_after > 0.0 and self.age >= self.stop_after:
            self.vel.update(0, 0)        # a thrown bomb has landed
        self.pos += self.vel * dt
        self.lifetime -= dt
        if self.lifetime <= 0.0:
            self.active = False

    def on_hit(self) -> None:
        if self.is_orbiter:
            # Persistent by design: it scores again every `rehit_interval`
            # rather than being spent. A base weapon's `pierce` (the Rod's 0
            # under the Arcane Storm forge) must not turn each mote into a
            # one-hit shot that the weapon replaces at the hero's feet every
            # frame -- that read as 1500 dps on the training dummy.
            return
        if self.pierce_left > 0:
            self.pierce_left -= 1
        else:
            self.active = False

    @property
    def is_orbiter(self) -> bool:
        return self.orbit_speed != 0.0 and self.anchor is not None
