"""Superconduct: Ice + Thunder (design §5.1, §5.5).

Medium damage to the enemy whose aura was consumed, then a jump tree that
carries **the slow alone** -- no damage, no aura -- further than base
Thunder reaches.

"Further than Thunder" is defined rather than authored: the tree runs for
`thunder.chain.jumps + bonus_jumps` levels, read off Thunder's live config,
so a blessing that lengthens Thunder's chain lengthens this too and no edit
to `reactions.json` can quietly make Superconduct the shorter of the pair.
The schema requires `bonus_jumps >= 1`, so it is always at least one level
longer.

The spread does **not** add freeze stacks (design §5.5). Those live on the
enemy's elemental state and only Ice applications touch them, so a
Superconduct can slow a crowd without freezing any of it.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.reactions.base import Reaction, status_on
from combat.elements.spread import breadth_first
from combat.elements.thunder import ARC_SECONDS

CHILL = "chill"


class Superconduct(Reaction):
    ID = ReactionId.SUPERCONDUCT

    def run(self, target, config, ctx) -> None:
        ctx.deal_spec(target, config.damage, tracking.SUPERCONDUCT)
        world = ctx.world
        breadth_first(
            world, target,
            jumps=self.jumps(config, ctx), per_jump=config.targets_per_jump,
            max_range=config.max_range, max_targets=config.max_targets,
            visit=lambda hit, _level: self.chill(hit, config, ctx),
            arc=lambda a, b: world.add_arc(a, b, ElementId.ICE,
                                           ctx.now + ARC_SECONDS))

    @staticmethod
    def jumps(config, ctx) -> int:
        """Always more levels than base Thunder, read off Thunder's own
        effective config so buffs to it carry over."""
        thunder = ctx.registry.config(ElementId.THUNDER, ctx.profile)
        return thunder.chain.jumps + config.bonus_jumps

    @staticmethod
    def chill(target, config, ctx) -> bool:
        """Slow one enemy the spread reached. Returns True so the tree keeps
        going: unlike a Thunder jump there is no reaction to stop it."""
        status = getattr(target, "status", None)
        if status is None or not ctx.allows_on(target, "slow"):
            return True
        # Plain `apply`, which only ever raises a potency: Ice owns the
        # slow's depth through its stack count, so a shallower spread must
        # not undercut a deep stack, and a later Ice hit recomputing from
        # its own stacks may take the value back over.
        status.apply(CHILL, duration=config.slow_duration,
                     potency=config.slow_percent,
                     source=ctx.weapon_id, bound_to_aura=False)
        return True
