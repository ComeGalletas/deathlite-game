"""IceWind: Ice + Wind (design §5.1, §5.5).

The Wind area with an ice payload: everything the tornado touches takes its
damage, is shoved outward, and gains `stacks_per_contact` Ice stacks.

Those stacks go through **Ice's own model**, not a copy of it, so they can
freeze (design open item 7, proposal accepted). That also means each body's
own profile decides its freeze threshold and whether it may be frozen at
all, which matters here more than anywhere else: a tornado sweeps whatever
is standing nearby, elites and commons together.
"""
from __future__ import annotations

from combat.elements import ice as ice_rules
from combat.elements import tracking
from combat.elements.ids import ReactionId
from combat.elements.reactions.base import Reaction
from combat.elements.wind import Wind


class IceWind(Reaction):
    ID = ReactionId.ICEWIND

    def run(self, target, config, ctx) -> None:
        Wind.spawn_area(
            target, ctx, config=config, effect=tracking.ICEWIND,
            payload=lambda other, _area, _world: self.chill(other, config, ctx))

    @staticmethod
    def chill(target, config, ctx) -> int:
        """Ice stacks on one body the tornado touched. The slow's duration is
        the reaction's own, and the stacks are standalone -- the aura that
        earned them belonged to somebody else."""
        return ice_rules.add_stacks(
            target, ctx, count=config.stacks_per_contact,
            duration=config.slow_duration, bound=False)
