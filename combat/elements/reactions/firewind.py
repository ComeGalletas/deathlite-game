"""FireWind: Fire + Wind (design §5.1, §5.5).

The Wind area of §4.4 with a fire payload: everything the tornado touches
takes its damage, is shoved outward, and is left burning.

The burn is **standalone** -- not bound to any aura, because the bodies it
lands on are bystanders with auras of their own that this must not disturb
-- and it is credited to FireWind rather than to Burn, so the run summary
can tell the reaction's damage-over-time from Fire's.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ReactionId
from combat.elements.reactions.base import Reaction
from combat.elements.wind import Wind

BURN = "burn"


class FireWind(Reaction):
    ID = ReactionId.FIREWIND

    def run(self, target, config, ctx) -> None:
        Wind.spawn_area(
            target, ctx, config=config, effect=tracking.FIREWIND,
            payload=lambda other, _area, _world: self.burn(other, config, ctx))

    @staticmethod
    def burn(target, config, ctx) -> None:
        status = getattr(target, "status", None)
        if status is None or not ctx.allows_on(target, "burn"):
            return
        status.apply(BURN, duration=config.burn_duration,
                     potency=config.burn_tick.resolve(ctx.hit_damage),
                     source=ctx.weapon_id, bound_to_aura=False,
                     effect=tracking.FIREWIND,
                     tick_interval=config.burn_tick_interval,
                     add_stack=False)
