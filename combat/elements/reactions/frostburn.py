"""Frostburn: Fire + Ice (design §5.1, §5.5).

A status, not a blast. The enemy takes a burn stronger than Fire's own and
a slow at the same time, for the reaction's own duration, and its aura slot
stays locked for as long as that lasts -- which is what stops the pair being
re-triggered every second and is why Frostburn is the one reaction that
extends the global cooldown.

It **never freezes**, and that falls out of the design rather than needing a
guard: freezing counts Ice applications, and those live on the enemy's
elemental state, which Frostburn does not touch.

Following the owner's decision to reuse the game's existing statuses, this
is the `burn` and `chill` rows at Frostburn's own values, both standalone --
never bound to an aura, because the aura that earned them has just been
consumed.
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.ids import ReactionId
from combat.elements.reactions.base import Reaction, status_on

BURN = "burn"
CHILL = "chill"


class Frostburn(Reaction):
    ID = ReactionId.FROSTBURN

    def run(self, target, config, ctx) -> None:
        status = status_on(target, ctx)
        if status is None:
            return
        if ctx.allows("burn"):
            status.apply(BURN, duration=config.duration,
                         potency=config.tick.resolve(ctx.hit_damage),
                         source=ctx.weapon_id, bound_to_aura=False,
                         effect=tracking.FROSTBURN,
                         tick_interval=config.tick_interval,
                         add_stack=False)
        if ctx.allows("slow") and config.slow_percent > 0.0:
            status.apply(CHILL, duration=config.duration,
                         potency=config.slow_percent,
                         source=ctx.weapon_id, bound_to_aura=False)
            # Deeper than whatever was there, never shallower: Ice owns the
            # slow's depth through its stack count, and a Frostburn should
            # not undercut a heavier one it happens to land on.
            if status.potency(CHILL) < config.slow_percent:
                status.set_potency(CHILL, config.slow_percent)
