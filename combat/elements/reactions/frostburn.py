"""Frostburn: Fire + Ice (design §5.1, §5.5).

Since the owner's rework (2026-09-22) it lands in two parts:

* an **immediate** hit of `0.70 x` the smaller of the two source hits plus
  `0.20 x` the larger -- the one reaction weighted toward the *weaker* of
  the pair, so it pays a fast cheap weapon finishing a heavy weapon's aura;
* a **burn** worth `0.50 x` the larger, divided into `ticks` ticks one
  `tick_interval` apart, which is the owner's "50 % of the highest, split
  into 3, one a second".

The slow rides alongside for the reaction's own `duration`, and the aura
slot stays locked for as long as that lasts -- which is what stops the pair
being re-triggered every second and is why Frostburn is the one reaction
that extends the global cooldown.

It **never freezes**, and that falls out of the design rather than needing a
guard: freezing counts Ice applications, and those live on the enemy's
elemental state, which Frostburn does not touch. It also spreads nothing,
so like Overload it can never start a cascade.

Following the owner's decision to reuse the game's existing statuses, the
burn and slow are the `burn` and `chill` rows, both standalone -- never
bound to an aura, because the aura that earned them has just been consumed.
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
        # The immediate half lands first and through the ordinary damage
        # path, so a dead carrier drops it exactly as every other reaction's
        # direct damage is dropped.
        ctx.deal(target, ctx.floored(ctx.pair_damage(config.damage)),
                 tracking.FROSTBURN)
        status = status_on(target, ctx)
        if status is None:
            return
        if ctx.allows("burn"):
            status.apply(BURN, duration=self.burn_seconds(config),
                         potency=self.tick_potency(config, ctx),
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

    @staticmethod
    def tick_potency(config, ctx) -> float:
        """One tick of the burn: the whole `tick` figure divided by how many
        ticks it is paid over. The data says what the burn is *worth*, not
        what one tick of it is, so changing `ticks` redistributes the same
        damage instead of multiplying it."""
        return ctx.pair_damage(config.tick) / max(1, config.ticks)

    @staticmethod
    def burn_seconds(config) -> float:
        """Exactly long enough for `ticks` ticks.

        Derived rather than a `duration` of its own: `StatusState.update`
        fires a tick each time the accumulator passes the interval while the
        status is still live, so `ticks x tick_interval` is the duration that
        pays out the figure the data names, and no second value can drift
        away from it."""
        return config.ticks * config.tick_interval
