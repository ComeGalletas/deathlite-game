"""Fire: direct damage, then a burn that shares the aura's life (design §4.1).

Fire reuses the game's existing `burn` status rather than taking one of its
own (owner's decision, 2026-09-21). Two consequences are deliberate:

* it applies with `add_stack=False`, so Fire refreshes its burn and never
  stacks it, while the Ember Ring's Scorch keeps stacking the same row to
  five;
* it carries its own `tick_interval` from the data, so Fire's burn ticks on
  `fire.burn.tick_interval` while Scorch keeps the status type's 0.5 s.

Where the two meet on one enemy the stronger potency wins for every stack
(`StatusState.apply` raises a potency, never lowers it), and whichever
applied last decides whether the burn is bound to the aura.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.base import Element
from combat.elements.ids import ElementId

BURN = "burn"


class Fire(Element):
    ID = ElementId.FIRE

    def apply_initial_effect(self, target, ctx) -> None:
        ctx.deal_spec(target, ctx.config.hit.damage, tracking.FIRE_HIT)

    def on_applied(self, target, ctx) -> None:
        """Start or refresh the burn. On a locked slot `ctx.bound` is False
        and the burn is standalone, but it still uses the duration the aura
        would have had (§3.2)."""
        status = getattr(target, "status", None)
        if status is None or not ctx.allows("burn"):
            return
        cfg = ctx.config
        status.apply(BURN,
                     duration=cfg.aura.duration,
                     potency=cfg.burn.tick.resolve(ctx.hit_damage),
                     source=ctx.weapon_id,
                     bound_to_aura=ctx.bound,
                     effect=tracking.BURN,
                     tick_interval=cfg.burn.tick_interval,
                     add_stack=False)
