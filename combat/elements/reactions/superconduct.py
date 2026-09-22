"""Superconduct: Ice + Thunder (design §5.1, §5.5).

Damage to the enemy whose aura was consumed, then a jump tree that carries
**the same damage, Ice stacks and the Ice aura** further than base Thunder
reaches (owner's rework, 2026-09-22). It used to carry a slow and nothing
else, which meant its arcs flew out to bodies that took nothing at all.

"Further than Thunder" is defined rather than authored: the tree runs for
`thunder.chain.jumps + bonus_jumps` levels, read off Thunder's live config,
so a blessing that lengthens Thunder's chain lengthens this too and no edit
to `reactions.json` can quietly make Superconduct the shorter of the pair.
The schema requires `bonus_jumps >= 1`, so it is always at least one level
longer.

The spread now **does** add freeze stacks, reversing design §5.5: the owner
asked for three of them per body, through Ice's own model, so each enemy's
own profile still decides its freeze threshold. And because it lays a real
Ice aura, a body already holding Fire or Thunder reacts again -- the
cascade the owner chose, with no depth cap. What bounds it is the per-enemy
aura lock and the per-frame reaction budget; see
`ElementalResolver.spread_aura`.
"""
from __future__ import annotations

from combat.elements import ice as ice_rules
from combat.elements import tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.reactions.base import Reaction
from combat.elements.resolve import Outcome
from combat.elements.spread import breadth_first
from combat.elements.thunder import ARC_SECONDS

CHILL = "chill"


class Superconduct(Reaction):
    ID = ReactionId.SUPERCONDUCT

    def run(self, target, config, ctx) -> None:
        amount = ctx.pair_damage(config.damage)
        ctx.deal(target, ctx.floored(amount), tracking.SUPERCONDUCT)
        world = ctx.world
        breadth_first(
            world, target,
            jumps=self.jumps(config, ctx), per_jump=config.targets_per_jump,
            max_range=config.max_range, max_targets=config.max_targets,
            visit=lambda hit, _level: self.reach(hit, config, ctx, amount),
            arc=lambda a, b: world.add_arc(a, b, ElementId.ICE,
                                           ctx.now + ARC_SECONDS))

    @staticmethod
    def jumps(config, ctx) -> int:
        """Always more levels than base Thunder, read off Thunder's own
        effective config so buffs to it carry over."""
        thunder = ctx.registry.config(ElementId.THUNDER, ctx.profile)
        return thunder.chain.jumps + config.bonus_jumps

    @staticmethod
    def reach(target, config, ctx, amount: float) -> bool:
        """One enemy the tree found: the reaction's damage (unfloored -- the
        floor is the carrier's alone), then the Ice aura, then enough stacks
        to bring it to `ice_stacks`.

        Returns True so the tree keeps going, even when the aura it just
        laid set off a reaction of its own. A Thunder jump stops at a
        reaction because that node's *own* element was consumed by it; here
        the tree is Superconduct's and the reaction is a bystander event, so
        stopping would make the spread's reach depend on what the crowd
        happened to be carrying.
        """
        ctx.deal(target, amount, tracking.SUPERCONDUCT)
        if not getattr(target, "alive", False):
            return True
        outcome = ctx.resolver.spread_aura(
            target, ElementId.ICE, weapon_id=ctx.weapon_id,
            hit_damage=amount, now=ctx.now)
        # A body whose own aura this just consumed has had its Ice stacks
        # reset with it; topping it back up would undo the reaction it just
        # paid for.
        if outcome in (Outcome.REACTION, Outcome.DEFERRED):
            return True
        Superconduct.top_up(target, config, ctx)
        return True

    @staticmethod
    def top_up(target, config, ctx) -> int:
        """Bring this body to `ice_stacks` Ice stacks, counting whatever the
        aura's own application already put there.

        Counted rather than added blind: laying the aura runs Ice's
        `on_applied`, which is worth one stack on its own, so adding three
        more would land four and the data's figure would not mean what it
        says.
        """
        state = ctx.resolver.state_for(target)
        missing = config.ice_stacks - state.ice_stacks
        if missing <= 0:
            return state.ice_stacks
        return ice_rules.add_stacks(
            target, ctx, count=missing, duration=config.slow_duration,
            bound=False)
