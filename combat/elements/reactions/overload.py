"""Overload: Fire + Thunder (design §5.1, §5.5).

Heavy damage to the enemy whose aura was consumed, then a shockwave that
damages and shoves everything around it. No aura on anyone -- Overload and
Frostburn are the two reactions the owner's 2026-09-22 rework left without
an aura to spread, so neither can start a cascade.

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
        # One figure from the two hits that met here: 50 % of the larger and
        # 30 % of the smaller (owner, 2026-09-22). The shockwave carries the
        # same number, so a body caught beside the reaction takes what the
        # reacting body takes -- floored only on the carrier.
        amount = ctx.pair_damage(config.damage)
        ctx.deal(target, ctx.floored(amount), tracking.OVERLOAD)
        # Two caps on the same circle: the shockwave's own radius, and the
        # per-source reach every spreading effect carries (§4 area caps).
        radius = min(config.shockwave_radius, config.max_range)
        blast(target, ctx,
              effect=tracking.OVERLOAD_WAVE,
              damage=amount,
              knockback=config.knockback,
              radius=radius,
              max_targets=config.max_targets,
              max_speed=config.max_knockback_speed)
