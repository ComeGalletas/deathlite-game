"""Ice: a stacking slow that freezes (design §4.2).

Ice deals no direct hit damage. Each application adds a stack; the slow is
recomputed from the stack count (`percent_per_stack x stacks`, capped at
`max_percent`) rather than accumulated, so it is exact rather than drifting.
At `freeze.stacks_required` stacks the enemy freezes, the stacks reset, and
an immunity window keeps it from being re-frozen immediately.

Like Fire, Ice reuses an existing status -- `chill` -- instead of taking one
of its own. `chill` is refresh-only with a single stack, so **the stack
counter lives on the enemy's elemental state**: making `chill` a stacking
status so the count could live there would have let the Grave Totem's
Chilling Bolts freeze enemies, which is a blessing this system must not
change.

The counter still tracks the slow's lifetime exactly, because it is reset
whenever the `chill` is found to have lapsed. That covers the aura expiring
quietly (no hook fires on a lazy expiry) as well as a reaction consuming it.

Two of the design's open questions are answered by construction rather than
by a branch: a freeze survives its aura being consumed, because `freeze` is
never bound to the aura and only `chill` is (open item 8); and the Ice aura
stays after a freeze triggers, because triggering one touches the stacks and
the statuses, never the slot (open item 9).
"""
from __future__ import annotations

from combat.elements import tracking
from combat.elements.base import Element
from combat.elements.ids import ElementId  # noqa: F401  (contact helpers)

CHILL = "chill"
FREEZE = "freeze"


class Ice(Element):
    ID = ElementId.ICE

    def apply_initial_effect(self, target, ctx) -> None:
        """Ice has no direct hit damage: its whole effect is the slow and
        what the slow builds to."""

    def on_applied(self, target, ctx) -> None:
        add_stacks(target, ctx, count=1, duration=ctx.config.aura.duration,
                   bound=ctx.bound, config=ctx.config)

    def on_aura_ended(self, target, reason, ctx) -> None:
        """The slow went with the aura (the resolver ends bound statuses), so
        its stacks go too. A freeze already on the enemy is untouched: it is
        its own status with its own duration."""
        ctx.resolver.state_for(target).reset_ice_stacks()


# --- the stack model, shared with IceWind ------------------------------------

def add_stacks(target, ctx, *, count: int = 1, duration: float | None = None,
               bound: bool = False, config=None) -> int:
    """Put `count` Ice stacks on `target` and resize its slow to match.

    The one place the stack model lives, because IceWind pours stacks into
    the enemies its tornado touches and the design asks for exactly this
    behaviour there, freezing included (§5.5, open item 7).

    `config` is Ice's effective config; left out it is looked up for
    **`target`'s own profile**, which is what a secondary contact needs -- a
    boss with a higher freeze threshold keeps it when a tornado slows it.
    """
    status = getattr(target, "status", None)
    if status is None:
        return 0
    cfg = config if config is not None else ctx.registry.config(
        ElementId.ICE, ctx.resolver.profile_for(target))
    state = ctx.resolver.state_for(target)

    # The slow lapsed (its aura expired quietly, or a reaction took it):
    # the stacks were part of it and go with it.
    if CHILL not in status:
        state.reset_ice_stacks()

    stacks = state.add_ice_stack(count)
    required = cfg.freeze.stacks_required
    if stacks >= required:
        stacks = _freeze(target, ctx, state, status, cfg, required)

    if ctx.allows_on(target, "slow"):
        percent = min(cfg.slow.max_percent, cfg.slow.percent_per_stack * stacks)
        status.apply(CHILL,
                     duration=duration if duration is not None else cfg.aura.duration,
                     potency=percent, source=ctx.weapon_id, bound_to_aura=bound)
        # `apply` only ever raises a potency, which is right for a refresh
        # and wrong here: the slow is a function of the stack count, so it
        # must be able to come back down after a freeze reset it.
        status.set_potency(CHILL, percent)
    return stacks


def _freeze(target, ctx, state, status, cfg, required: int) -> int:
    """Freeze at the threshold and spend the stacks. Returns the stack count
    to size the slow from.

    An enemy that cannot be frozen -- still inside its immunity window, or a
    type whose profile disables freezing -- keeps its stacks *clamped* at the
    threshold instead of spending them, so its slow sits at the value the
    threshold earned rather than sawtoothing back down every few hits.
    """
    if not ctx.allows_on(target, "freeze") or state.freeze_immune(ctx.now):
        state.ice_stacks = required
        return required
    status.apply(FREEZE, duration=cfg.freeze.duration, potency=1.0,
                 source=ctx.weapon_id)
    state.reset_ice_stacks()
    state.freeze_immune_until = (ctx.now + cfg.freeze.duration
                                 + cfg.freeze.immunity_duration)
    return 0


# --- frozen contact damage (design §4.2 addendum, R25) -----------------------

# How fast a body must still be travelling under a shove to count as
# "sliding". The same threshold the Bomb's Demolitionist blessing uses to ask
# whether an enemy is being shoved, so the two agree about what motion means.
SLIDE_SPEED_SQ = 30.0 ** 2


def sliding(body) -> bool:
    knock = getattr(body, "_knock", None)
    return knock is not None and knock.length_squared() > SLIDE_SPEED_SQ


def is_frozen(body) -> bool:
    status = getattr(body, "status", None)
    return status is not None and FREEZE in status


def bite(body) -> float:
    """The body's own contact damage, on the game's existing bite model:
    `contact_damage x contact_interval` before mitigation. The design asks
    for the existing collision-damage calculation rather than a new formula,
    and this is it (`CombatResolver.enemy_contact`)."""
    return (float(getattr(body, "contact_damage", 0.0))
            * float(getattr(body, "contact_interval", 0.0)))


def exchange_contact(resolver, a, b, now: float) -> float:
    """A frozen body that is being shoved damages whatever it clips.

    Called from the bump pass, which is the one place two bodies are known
    to overlap. Either side may be the frozen one; both are checked. The
    damage is one-way: no aura, no reaction and no extra impulse, so a
    contact cannot chain into another (R30). Each body is clipped at most
    once per slide.
    """
    return (_one_way(resolver, a, b, now) + _one_way(resolver, b, a, now))


def _one_way(resolver, slider, victim, now: float) -> float:
    if not (sliding(slider) and is_frozen(slider)):
        return 0.0
    if not getattr(victim, "alive", False):
        return 0.0
    profile = resolver.profile_for(slider)
    if not profile.enabled("frozen_contact"):
        return 0.0
    cfg = resolver.registry.config(ElementId.ICE, profile).freeze.contact
    if not cfg.enabled:
        return 0.0
    amount = cfg.damage.resolve(bite(slider))
    if amount <= 0.0:
        return 0.0
    state = resolver.state_for(slider)
    if not state.note_contact(victim):
        return 0.0                      # already clipped during this slide
    weapon = state.knock_source or _freeze_source(slider)
    return resolver.world.deal(victim, amount, weapon, tracking.FROZEN_CONTACT)


def _freeze_source(body) -> str:
    """Whoever froze it, for a slide nothing else has claimed."""
    status = getattr(body, "status", None)
    return str((status.source_of(FREEZE) if status else None) or "")
