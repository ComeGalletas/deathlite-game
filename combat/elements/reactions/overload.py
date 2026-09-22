"""Overload: Fire + Thunder (design §5.1, §5.5).

Heavy damage to the enemy whose aura was consumed, then a shockwave that
damages and shoves everything around it. No aura on anyone.

The **pinball** behaviour the design asks for is emergent, not written: the
shove goes through the game's ordinary weight-split knockback, so repeated
Overloads bounce bodies around by themselves. `max_knockback_speed` clamps
the accumulated impulse, which is what stops a stack of shockwaves flinging
an enemy across the island or through a cliff.

A dead carrier still sets it off. Its own share of the damage is dropped by
the world, and the shockwave -- the part that was owed to the enemies around
it -- lands in full.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ReactionId
from combat.elements.reactions.base import Reaction, blast


class Overload(Reaction):
    ID = ReactionId.OVERLOAD

    def run(self, target, config, ctx) -> None:
        ctx.deal_spec(target, config.damage, tracking.OVERLOAD)
        # Two caps on the same circle: the shockwave's own radius, and the
        # per-source reach every spreading effect carries (§4 area caps).
        radius = min(config.shockwave_radius, config.max_range)
        blast(target, ctx,
              effect=tracking.OVERLOAD_WAVE,
              damage=config.shockwave_damage.resolve(ctx.hit_damage),
              knockback=config.knockback,
              radius=radius,
              max_targets=config.max_targets,
              max_speed=config.max_knockback_speed)
