"""FireWind: Fire + Wind (design §5.1, §5.5).

The Wind area of §4.4 with a fire payload: everything the tornado touches
takes its damage, is shoved outward, is left burning, and is **primed with
the Fire aura** (owner's rework, 2026-09-22).

Two things changed with that rework. The enemy the reaction fired on now
takes the damage too -- it used to be excluded from its own tornado and so
took literally nothing, which with the incoming Wind hit suppressed made
triggering this on a lone enemy a net loss. And the aura the tornado leaves
behind can meet a different one and react again; the owner kept the burn
payload as well rather than letting the spread aura's own burn replace it.

The burn is **standalone** -- not bound to any aura, because the bodies it
lands on are bystanders with auras of their own that this must not disturb
-- and it is credited to FireWind rather than to Burn, so the run summary
can tell the reaction's damage-over-time from Fire's.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.reactions.base import Reaction, wind_reaction
from combat.elements.wind import Wind

BURN = "burn"


class FireWind(Reaction):
    ID = ReactionId.FIREWIND

    def run(self, target, config, ctx) -> None:
        wind_reaction(target, config, ctx, effect=tracking.FIREWIND,
                      element=ElementId.FIRE, payload=self.burn)

    @staticmethod
    def burn(target, config, ctx) -> None:
        status = getattr(target, "status", None)
        if status is None or not ctx.allows_on(target, "burn"):
            return
        status.apply(BURN, duration=config.burn_duration,
                     potency=config.burn_tick.resolve(ctx.reference),
                     source=ctx.weapon_id, bound_to_aura=False,
                     effect=tracking.FIREWIND,
                     tick_interval=config.burn_tick_interval,
                     add_stack=False)
