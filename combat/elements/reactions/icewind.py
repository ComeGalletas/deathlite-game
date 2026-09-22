"""IceWind: Ice + Wind (design §5.1, §5.5).

The Wind area with an ice payload: everything the tornado touches takes its
damage, is shoved outward, gains `stacks_per_contact` Ice stacks, and is
**primed with the Ice aura** (owner's rework, 2026-09-22). The enemy the
reaction fired on takes the damage too, which it did not before.

The stacks go through **Ice's own model**, not a copy of it, so they can
freeze (design open item 7, proposal accepted). That also means each body's
own profile decides its freeze threshold and whether it may be frozen at
all, which matters here more than anywhere else: a tornado sweeps whatever
is standing nearby, elites and commons together.

The aura is spread first and these stacks land over it, so the slow ends
up standalone and sized from the full count. That count is
`stacks_per_contact` **plus one**: priming a body with Ice runs Ice's own
`on_applied`, which is a stack in its own right. The owner kept both halves
(2026-09-22), so both are paid.
"""
from __future__ import annotations

from combat.elements import ice as ice_rules
from combat.elements import tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.reactions.base import Reaction, wind_reaction


class IceWind(Reaction):
    ID = ReactionId.ICEWIND

    def run(self, target, config, ctx) -> None:
        wind_reaction(target, config, ctx, effect=tracking.ICEWIND,
                      element=ElementId.ICE, payload=self.chill)

    @staticmethod
    def chill(target, config, ctx) -> int:
        """Ice stacks on one body the tornado touched. The slow's duration is
        the reaction's own, and the stacks are standalone -- the aura that
        earned them belonged to somebody else."""
        return ice_rules.add_stacks(
            target, ctx, count=config.stacks_per_contact,
            duration=config.slow_duration, bound=False)
