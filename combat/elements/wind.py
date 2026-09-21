"""Wind: a small hit, then a brief tornado around the enemy (design §4.4).

The area is the reusable `WindArea` component, so the three Wind reactions
are this with different numbers and a payload. Wind's own area has no
payload: damage and radial knockback are all of it.

The area is seated through the world, which refuses it once the run is at
`max_active_wind_areas`. A refused area is simply not there -- the hit and
its aura still happened -- because a cap that queued would let a crowd bank
tornadoes to fire later, which is worse than dropping one.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.area import WindArea
from combat.elements.base import Element
from combat.elements.ids import ElementId


class Wind(Element):
    ID = ElementId.WIND

    def apply_initial_effect(self, target, ctx) -> None:
        ctx.deal_spec(target, ctx.config.hit.damage, tracking.WIND_HIT)
        # The tornado is an outward effect, so it is seated whether or
        # not the enemy it formed on survived the hit. Anchored to a
        # corpse it simply stays where the body fell.
        self.spawn_area(target, ctx)

    @staticmethod
    def spawn_area(target, ctx, *, config=None, effect=tracking.WIND_AREA,
                   payload=None) -> WindArea | None:
        """Seat a Wind area on `target`. The Wind reactions call this with
        their own `config` block and a payload; it returns the area, or None
        when the run is at its cap."""
        cfg = config if config is not None else ctx.config.area
        area = WindArea(
            pos=target.pos, radius=cfg.radius,
            expires_at=ctx.now + cfg.duration,
            damage=cfg.damage.resolve(ctx.hit_damage),
            knockback=cfg.knockback, weapon_id=ctx.weapon_id, effect=effect,
            max_targets=cfg.max_targets, anchor=target, payload=payload,
            # Whether a body may be shoved is its own profile's call,
            # asked per contact rather than once for the carrier.
            allows=ctx.allows_on)
        return area if ctx.world.add_area(area) else None
