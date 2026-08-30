"""Player summons (spec 5.8): a stationary Totem and a roaming Wolf.

Pooled (object pooling, spec 5.8 / 6.2). Each summon has spawn / lifetime /
targeting / movement / attack / death. Summons deal damage by emitting ordinary
friendly projectiles, so blessing tag-synergy and crit all apply for free and
the collision path is shared.
"""
from __future__ import annotations

import pygame

from game.assets import get_assets
from systems.animation import Animator

# The wolf's `bite_*` strip is 5 frames at 16 fps; hold the bite anim this long
# after a bite before falling back to `run_*` (< `attack_interval` so there is a
# run gap between snaps).
_BITE_ANIM_S = 0.32


def _nearest(pos, enemies):
    best, best_d2 = None, float("inf")
    for e in enemies:
        if not getattr(e, "alive", True):
            continue
        d2 = (e.pos - pos).length_squared()
        if d2 < best_d2:
            best, best_d2 = e, d2
    return best


class Summon:
    __slots__ = ("active", "kind", "pos", "vel", "life", "attack_cd", "radius",
                 "color", "damage", "speed", "attack_range", "attack_interval",
                 "tags", "_t", "anim", "_bite_t", "_side", "reach", "fx")

    def __init__(self) -> None:
        self.active = False
        self.kind = "totem"
        self.pos = pygame.Vector2()
        self.vel = pygame.Vector2()
        self.life = 0.0
        self.attack_cd = 0.0
        self.radius = 12.0
        self.color = (150, 220, 190)
        self.damage = 6.0
        self.speed = 0.0
        self.attack_range = 320.0
        self.attack_interval = 0.7
        self.reach = float("inf")            # CB-2 leash ring; wired up in step C
        self.tags: tuple[str, ...] = ("summon",)
        self._t = 0.0
        self.anim: Animator | None = None   # wolf only
        self._bite_t = 0.0                   # seconds left showing `bite_*`
        self._side = "right"                 # last-known facing: "left" | "right"
        self.fx: dict = {}                   # render-only: per-weapon effect tuning

    def reset(self, *, kind, pos, damage, lifetime, color, tags,
              speed=0.0, attack_range=320.0, attack_interval=0.7,
              radius=12.0, reach=float("inf"), fx: dict | None = None) -> None:
        self.kind = kind
        self.pos.update(pos)
        self.vel.update(0, 0)
        self.damage = damage
        self.life = lifetime
        self.color = color
        self.tags = tuple(tags) + ("summon",)
        self.speed = speed
        self.attack_range = attack_range
        self.attack_interval = attack_interval
        self.radius = radius
        self.reach = reach                   # CB-2 leash ring; wired up in step C
        self.fx = fx if fx is not None else {}
        self.attack_cd = 0.3
        self._t = 0.0
        self._bite_t = 0.0
        self._side = "right"
        self.anim = Animator(get_assets(), "spirit_wolf",
                             start="run_right") if kind == "wolf" else None

    def update(self, dt: float, ctx) -> None:
        self.life -= dt
        if self.life <= 0.0:
            self.active = False
            return
        self._t += dt
        self._bite_t = max(0.0, self._bite_t - dt)
        self.attack_cd -= dt
        target = self._acquire_target(ctx)

        if self.kind == "wolf":
            self._chase(dt, target, ctx)
        self._maybe_attack(ctx, target)

        if self.anim is not None:
            self.anim.play(self._anim_name(target))
            self.anim.update(dt)

    def _acquire_target(self, ctx):
        """Nearest enemy that also sits inside the leash ring (CB-2). The wolf's
        ring is centred on the live hero (`ctx.player_pos`); the planted totem
        defends its own spot. `reach == inf` (a summon spawned without one) means
        no ring -- every enemy is a candidate, exactly as before CB-2."""
        center = ctx.player_pos if self.kind == "wolf" else self.pos
        r2 = self.reach * self.reach
        in_ring = [e for e in ctx.enemies
                   if (e.pos - center).length_squared() <= r2]
        return _nearest(self.pos, in_ring)

    # --- wolf movement / attack ---------------------------------
    def _chase(self, dt: float, target, ctx) -> None:
        home = ctx.player_pos
        # Leashed: too far from the hero -> abandon the chase and run home, so a
        # fleeing enemy cannot drag the wolf across the map (CB-2).
        if (self.pos - home).length() > self.reach:
            self._steer(home - self.pos)
            self.pos += self.vel * dt
            return
        if target is None:
            self.vel = pygame.Vector2()   # nothing in the ring -> hold, then sleep
            return
        d = target.pos - self.pos
        if d.length() > self.attack_range * 0.6:
            self._steer(d)
        else:
            self.vel = pygame.Vector2()
        self.pos += self.vel * dt

    def _steer(self, d: pygame.Vector2) -> None:
        self.vel = (d.normalize() * self.speed
                    if d.length_squared() > 1e-6 else pygame.Vector2())
        if abs(self.vel.x) > 1.0:
            self._side = "left" if self.vel.x < 0 else "right"

    def _maybe_attack(self, ctx, target) -> None:
        if target is None or self.attack_cd > 0.0:
            return
        if (target.pos - self.pos).length() > self.attack_range:
            return
        self.attack_cd = self.attack_interval
        direction = (target.pos - self.pos)
        if direction.length_squared() < 1e-6:
            return
        direction = direction.normalize()
        if self.kind == "wolf":
            self._bite_t = _BITE_ANIM_S
            self._side = "left" if direction.x < 0 else "right"
            # CB-3: a spirit weighs nothing -> its bite deals no knockback.
            ctx.spawn_projectile(pos=self.pos, vel=direction * 40, damage=self.damage,
                                 radius=22, lifetime=0.12, pierce=2, src_weight=0,
                                 color=self.color, source_tags=self.tags, style="melee")
        else:  # totem bolt -- a barely-there nudge
            ctx.spawn_projectile(pos=self.pos, vel=direction * 420, damage=self.damage,
                                 radius=6, lifetime=1.4, pierce=0, src_weight=1,
                                 color=self.color, source_tags=self.tags)

    def _anim_name(self, target) -> str:
        if self._bite_t > 0.0:
            return f"bite_{self._side}"
        # `idle` is the sleeping strip -- only when the wolf is genuinely idle
        # (nothing in the leash ring and standing still), never between bites.
        if target is None and self.vel.length_squared() < 1.0:
            return "idle"
        return f"run_{self._side}"
