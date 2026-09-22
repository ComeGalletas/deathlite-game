"""ThunderWind: Thunder + Wind (design §5.1, §5.5).

The Wind area, priming everything it touches with the Thunder aura (owner's
rework, 2026-09-22), plus a Thunder strike delivered **through the reacting
enemy** to the N closest enemies around it. The enemy the reaction fired on
now takes the area's damage as well; it used to be excluded from its own
tornado and the strike, and so took nothing at all.

The strike is a single nearest-N query, not a jump tree -- that is what
distinguishes it from base Thunder and from Superconduct, and it is why N is
meant to be high: this is a wide, flat burst rather than an arc that walks
from body to body. The owner kept it when the rework gave the tornado an
aura to spread, so ThunderWind is the area *and* the burst.

N is floored at what a base Thunder spread would have reached
(`targets_per_jump x (jumps + 1)`), read off Thunder's live config, so
ThunderWind can never be the weaker of the two and a buff to Thunder's reach
widens this as well.

The strike itself leaves no aura: only the tornado primes, so a body outside
the tornado's radius but inside the strike's range takes damage and nothing
more.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.reactions.base import Reaction, wind_reaction
from combat.elements.thunder import ARC_SECONDS


class ThunderWind(Reaction):
    ID = ReactionId.THUNDERWIND

    def run(self, target, config, ctx) -> None:
        wind_reaction(target, config, ctx, effect=tracking.THUNDERWIND,
                      element=ElementId.THUNDER)
        self.strike(target, config, ctx)

    @staticmethod
    def targets(config, ctx) -> int:
        """N: the data's own figure, or what base Thunder would have
        reached, whichever is larger."""
        chain = ctx.registry.config(ElementId.THUNDER, ctx.profile).chain
        reach = chain.targets_per_jump * (chain.jumps + 1)
        return max(config.strike_targets, reach)

    @staticmethod
    def strike(target, config, ctx) -> int:
        """One flat burst on the closest bodies. Returns how many it hit."""
        world = ctx.world
        damage = config.strike_damage.resolve(ctx.reference)
        hit = 0
        for other in world.nearest(target.pos, ThunderWind.targets(config, ctx),
                                   config.strike_range, exclude={id(target)}):
            hit += 1
            ctx.deal(other, damage, tracking.THUNDER_STRIKE)
            world.add_arc(target.pos, other.pos, ElementId.THUNDER,
                          ctx.now + ARC_SECONDS)
        return hit
