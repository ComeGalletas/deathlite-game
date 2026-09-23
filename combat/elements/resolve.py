"""Single-element hit resolution (design §3.2): the rules that decide what
one element-carrying hit does to one enemy.

    1. the weapon's own damage has already landed (the existing pipeline)
    2. aura slot locked  -> initial effect and statuses, no aura, no reaction
    3. slot empty        -> initial effect, set the aura, bind its status
    4. same element      -> initial effect, refresh the aura and its status
    5. different element -> consume the aura, run the reaction, lock the slot
                            (the incoming element's initial effect does
                            **not** apply and it leaves no aura)

The resolver owns the parts of that which must hold whatever the elements
do: the aura slot, the lock, the binding contract (a consumed aura takes
its bound statuses with it), the per-frame reaction budget, and the
bookkeeping. What an element or a reaction actually *does* lives behind two
seams: the `Element` hooks (`combat/elements/`) and the reaction runner
(`combat/elements/reactions/`).

Nothing here scans the enemy list. Auras expire lazily by timestamp
comparison and bound statuses expire on their own clock at the same moment,
so a field of several hundred auras costs nothing per frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from combat.elements.aura import ElementalState
from combat.elements.base import AuraEnd
from combat.elements.ids import ElementId
from combat.elements.profiles import DEFAULT as DEFAULT_PROFILE
from combat.elements.world import NullWorld


class Outcome(IntEnum):
    """What one call to `ElementalResolver.apply` did."""
    NONE = 0          # nothing to apply (no element, or a dead target)
    APPLIED = 1       # the slot was empty: aura set
    REFRESHED = 2     # the same element again: aura pushed out
    LOCKED = 3        # the slot was locked: effects only, no aura
    REACTION = 4      # a different element: aura consumed, reaction ran
    DEFERRED = 5      # ...and the reaction was held over to the next frame
    OUTWARD = 6       # the carrier is dead: spread only, nothing written to it


@dataclass
class HitContext:
    """What an element hook or a reaction is handed. One per resolved hit;
    elements are stateless, so everything they need arrives here."""
    target: object
    element: ElementId
    now: float
    weapon_id: str
    hit_damage: float          # the weapon damage that carried the element
    config: object             # that element's effective config for this target
    profile: object
    registry: object
    resolver: "ElementalResolver"
    # The hit that placed the aura this one is meeting, taken off the slot
    # before it is consumed. Zero on a hit that starts no reaction, and on
    # a reaction whose aura was laid by a path that carried no damage. A
    # reaction reads the two together through `sources` (owner's rework,
    # 2026-09-22).
    aura_damage: float = 0.0
    tracking: object = None
    # May a status applied now share the aura's lifetime? False on a locked
    # slot, where Fire's burn and Ice's chill are applied standalone (§3.2).
    bound: bool = True
    # Is this a repeat application of the element already on the slot?
    refreshed: bool = False
    # The hit that carried this element had already killed its target.
    # Everything that reaches *other* enemies still runs -- the chain,
    # the Wind area, the reaction -- but nothing may be written to the
    # body: no aura, no status, and its share of the damage is dropped
    # (the world refuses damage to a dead target, so that part is
    # automatic). A reaction that writes to its target must check this.
    carrier_dead: bool = False
    # Set when this hit is one node of a Thunder chain already in flight
    # (`thunder.ChainNode`). `None` means a root hit, which is the only kind
    # that may start a new chain -- without it every jump would branch a
    # fresh tree of its own.
    chain: object = None

    @property
    def world(self):
        return self.resolver.world

    def record_damage(self, amount: float, effect: str) -> None:
        if self.tracking is not None:
            self.tracking.record_damage(amount, self.weapon_id, effect)

    # --- what an element does to the world -------------------------------
    def deal(self, target, amount: float, effect: str) -> float:
        """Damage `target`, credited to this hit's weapon and to `effect`."""
        if amount <= 0.0:
            return 0.0
        # The world records it: one place, so a Wind area that outlives
        # this context still lands in the same books.
        return self.resolver.world.deal(target, amount, self.weapon_id, effect)

    def deal_spec(self, target, spec, effect: str) -> float:
        """The same, for a `DamageSpec` resolved against the hit that carried
        the element (the owner's rule: element damage is a fraction of the
        hit unless the value is flat)."""
        return self.deal(target, spec.resolve(self.reference), effect)

    # --- the two damage sources a reaction is paid from ---------------------
    @property
    def sources(self) -> tuple[float, float]:
        """The two hits that met on this body: the one that placed the aura
        and the one that triggered the reaction.

        An aura that carries no damage of its own falls back to the
        triggering hit, so a reaction is never paid as if one of its two
        halves were free. That covers a slot filled by something with no
        weapon damage behind it as well as the first reaction after a save
        is loaded."""
        placed = self.aura_damage if self.aura_damage > 0.0 else self.hit_damage
        return (placed, self.hit_damage)

    @property
    def reference(self) -> float:
        """The single number the *non-pair* values of a reaction resolve
        against -- FireWind's burn, ThunderWind's strike -- and the damage
        an ordinary element hit uses.

        For an element hit that is simply the hit itself. For a reaction it
        is the larger of the two sources, so the payloads the owner kept
        (2026-09-22) benefit from the rework's central point without their
        tuning numbers being restated."""
        return max(self.sources)

    def pair_damage(self, spec) -> float:
        """A `PairSpec` resolved against both sources: `high x max + low x min`."""
        first, second = self.sources
        return spec.resolve(first, second)

    def floored(self, amount: float) -> float:
        """`amount` raised to the global floor -- the owner's rule that a
        reaction never lands for less than a few points on the enemy it
        fired on (2026-09-22). Applied to the carrier only; the bodies a
        reaction spreads to take the raw figure."""
        return max(float(amount), self.registry.global_cfg.reaction_min_damage)

    def knock(self, target, direction, strength: float, max_speed: float = 0.0) -> None:
        self.resolver.world.knock(target, direction, strength,
                                  weapon_id=self.weapon_id, max_speed=max_speed)

    def allows(self, effect: str) -> bool:
        """Does the *carrier's* profile permit this effect?"""
        return self.profile.enabled(effect)

    def allows_on(self, other, effect: str) -> bool:
        """The same question for someone else -- a bystander in a
        blast, an enemy a spread reached, a body inside a Wind area.
        Their own profile decides what may be done to them, not the
        profile of whoever happened to set the effect off."""
        return self.resolver.profile_for(other).enabled(effect)


@dataclass
class PendingReaction:
    """A reaction the frame's budget pushed to the next frame. Its aura is
    already consumed and its lock already applied, so holding it over can
    never let the same aura fire twice."""
    target: object
    variant: object
    config: object
    ctx: HitContext
    queued_at: float


@dataclass
class ResolverStats:
    """Counters the debug overlay reads (§9.8)."""
    reactions_this_frame: int = 0
    reactions_total: int = 0
    # Enemies a Thunder chain jumped to, the struck one not counted
    # (CMB-009.2, design §9.8).
    jump_nodes_this_frame: int = 0
    jump_nodes_total: int = 0
    deferred_now: int = 0
    deferred_total: int = 0
    applications: int = 0
    locked_hits: int = 0
    # Resolved on a carrier the *weapon* had already killed. An element
    # that kills its own carrier reports `OUTWARD` but is not counted
    # here, so this stays a measure of what the death rule recovered.
    corpse_hits: int = 0
    by_outcome: dict = field(default_factory=dict)

    def note(self, outcome: Outcome) -> None:
        self.by_outcome[outcome] = self.by_outcome.get(outcome, 0) + 1


def alive(target) -> bool:
    return bool(getattr(target, "alive", False))


def state_of(target) -> ElementalState:
    """The target's elemental state, created on first use so a hand-built
    test double needs no setup."""
    state = getattr(target, "elemental", None)
    if state is None:
        state = ElementalState()
        try:
            target.elemental = state
        except AttributeError:      # a slotted stand-in: keep it off to the side
            pass
    return state


class ElementalResolver:
    def __init__(self, registry, *, profiles=None, tracking=None,
                 reaction_runner=None, world=None) -> None:
        self.registry = registry
        # Everything outward-facing (damage, queries, impulses, areas)
        # goes through this; `NullWorld` is the tests' recorder.
        self.world = world if world is not None else NullWorld()
        # {enemy id / boss id: ElementProfile}; anything missing is default.
        self.profiles = profiles or {}
        self.tracking = tracking
        # `runner(target, variant, config, ctx)` -- `reactions.run`.
        self.reaction_runner = reaction_runner
        self.stats = ResolverStats()
        self._pending: list[PendingReaction] = []

    # --- frame -----------------------------------------------------------
    def begin_frame(self, now: float) -> int:
        """Reset the reaction budget and run whatever last frame held over.
        Returns how many deferred reactions ran."""
        self.stats.reactions_this_frame = 0
        self.stats.jump_nodes_this_frame = 0
        self.stats.deferred_now = 0
        if not self._pending:
            return 0
        held, self._pending = self._pending, []
        ran = 0
        for entry in held:
            # A target that died while the reaction waited still gets it:
            # the blast was owed to the enemies around it, and the
            # reaction reads only its position.
            if self._budget_left():
                self._run_reaction(entry.target, entry.variant, entry.config, entry.ctx)
                ran += 1
            else:
                self._pending.append(entry)
                self.stats.deferred_now += 1
        return ran

    @property
    def pending(self) -> int:
        return len(self._pending)

    def _budget_left(self) -> bool:
        cap = self.registry.global_cfg.max_reactions_per_frame
        return self.stats.reactions_this_frame < cap

    # --- lookups ----------------------------------------------------------
    @staticmethod
    def state_for(target):
        return state_of(target)

    def profile_for(self, target):
        key = getattr(target, "enemy_id", None) or getattr(target, "boss_id", None)
        return self.profiles.get(key, DEFAULT_PROFILE)

    def config_for(self, target, element: ElementId):
        return self.registry.config(element, self.profile_for(target))

    # --- the resolution ------------------------------------------------------
    def apply(self, target, element: ElementId, *, weapon_id: str = "",
              hit_damage: float = 0.0, now: float = 0.0,
              chain=None) -> Outcome:
        """Resolve one element-carrying hit on one enemy.

        `chain` marks the hit as one node of a Thunder chain already in
        flight, so the element deals the node's damage without starting
        a tree of its own.
        """
        if element == ElementId.NONE:
            return Outcome.NONE

        state = state_of(target)
        profile = self.profile_for(target)
        # Read before anything can consume the slot: this is the reaction's
        # first damage source (owner's rework, 2026-09-22).
        aura_damage = state.source_damage if state.has_aura(now) else 0.0
        # A carrier the hit has already killed still resolves, but only for
        # what reaches *other* enemies (the owner's rule, 2026-09-21). See
        # `HitContext.carrier_dead`.
        dead = not getattr(target, "alive", False)
        ctx = HitContext(
            target=target, element=element, now=now, weapon_id=weapon_id,
            hit_damage=hit_damage, config=self.registry.config(element, profile),
            profile=profile, registry=self.registry, resolver=self,
            aura_damage=aura_damage, tracking=self.tracking, chain=chain,
            carrier_dead=dead)

        if self.tracking is not None:
            self.tracking.record_application(weapon_id, element)
        self.stats.applications += 1
        if dead:
            self.stats.corpse_hits += 1

        # Step 2. A locked slot -- or a type whose profile disables auras,
        # which is the same thing forever (§3.5): the element lands, but
        # nothing reacts and no aura is left.
        if not profile.aura_enabled or state.is_locked(now):
            ctx.bound = False
            self.stats.locked_hits += 1
            self._land(target, element, ctx)
            return self._done(Outcome.LOCKED if alive(target)
                              else Outcome.OUTWARD)

        held = state.element(now)

        # Step 3. Empty slot.
        if held == ElementId.NONE:
            self._land(target, element, ctx)
            if not alive(target):
                return self._done(Outcome.OUTWARD)
            state.set_aura(element, now, ctx.config.aura.duration, weapon_id,
                           damage=hit_damage)
            self.registry.element(element).on_applied(target, ctx)
            return self._done(Outcome.APPLIED)

        # Step 4. The same element again.
        if held == element:
            ctx.refreshed = True
            self._land(target, element, ctx)
            if not alive(target):
                return self._done(Outcome.OUTWARD)
            state.refresh_aura(now, ctx.config.aura.duration, weapon_id,
                               damage=hit_damage)
            self.registry.element(element).on_applied(target, ctx)
            return self._done(Outcome.REFRESHED)

        # Step 5. A different element: the reaction replaces everything the
        # incoming element would have done. A dead carrier still reacts --
        # the aura it was holding is what earned the reaction, and the blast
        # is owed to the enemies around it, not to the body.
        return self._done(self._react(target, state, held, element, ctx))

    def spread_aura(self, target, element: ElementId, *, weapon_id: str = "",
                    hit_damage: float = 0.0, now: float = 0.0) -> Outcome:
        """An aura laid on a **bystander** by a reaction (owner's decision,
        2026-09-22): a tornado's contacts and Superconduct's jump tree.

        This is deliberately the ordinary `apply`, which means a spread aura
        landing on an enemy already holding a different one **triggers
        another reaction**. The design's old rule -- secondary hits never
        apply auras, so reaction depth is exactly 1 (§5.3, §5.4) -- is
        retired by that decision; the owner chose the cascade with the
        blow-up risk stated, and chose not to cap its depth.

        What bounds it is what already existed: the per-enemy aura lock, so
        a body that has just reacted takes no new aura for
        `reaction_aura_cooldown`; and `max_reactions_per_frame`, which caps
        the recursion depth of a cascade at the frame's remaining budget and
        defers the rest rather than dropping it. The value carried also
        decays -- a spread aura is worth the damage that enemy just took --
        so successive generations are paid less.

        A method of its own rather than a bare `apply` call because it is
        the one seam a depth cap would go behind if play asks for one.
        """
        return self.apply(target, element, weapon_id=weapon_id,
                          hit_damage=hit_damage, now=now)

    def _land(self, target, element: ElementId, ctx: HitContext) -> None:
        """The element's own effect, then its statuses. On a locked slot
        `ctx.bound` is False and the statuses are standalone; on a dead
        carrier no status is written at all, and the element's own damage
        is dropped by the world because the target is not alive.

        The aliveness test is taken *after* the initial effect, not
        before it, so an element whose own damage finished the enemy
        writes nothing either."""
        el = self.registry.element(element)
        el.apply_initial_effect(target, ctx)
        if ctx.bound is False and alive(target):
            el.on_applied(target, ctx)

    def _react(self, target, state, held: ElementId, incoming: ElementId,
               ctx: HitContext) -> Outcome:
        variant = self.registry.reaction(held, incoming)
        if variant is None:
            # No pair for these two. Cannot happen with the shipped table;
            # treated as a plain application so a future fifth element
            # without a full row of reactions degrades instead of crashing.
            self._land(target, incoming, ctx)
            state.set_aura(incoming, ctx.now, ctx.config.aura.duration,
                           ctx.weapon_id, damage=ctx.hit_damage)
            self.registry.element(incoming).on_applied(target, ctx)
            return Outcome.APPLIED

        config = self.registry.reaction_config(variant.reaction, incoming, ctx.profile)

        # Consume first: the aura is gone whether or not the budget lets the
        # reaction run this frame.
        state.consume_aura()
        self.registry.element(held).on_aura_ended(target, AuraEnd.CONSUMED, ctx)
        # The binding contract is the resolver's, not the element's: whatever
        # shared that aura's life ends with it.
        status = getattr(target, "status", None)
        if status is not None:
            status.end_bound()

        state.lock(ctx.now, self._lock_seconds(config))

        if self.tracking is not None:
            self.tracking.record_reaction(ctx.weapon_id, variant.reaction)

        if not self._budget_left():
            self._pending.append(PendingReaction(target, variant, config, ctx, ctx.now))
            self.stats.deferred_now += 1
            self.stats.deferred_total += 1
            return Outcome.DEFERRED

        self._run_reaction(target, variant, config, ctx)
        return Outcome.REACTION

    def _lock_seconds(self, config) -> float:
        """Every reaction starts the global cooldown; one that locks the slot
        itself wins if it is longer (§3)."""
        base = self.registry.global_cfg.reaction_aura_cooldown
        own = config.lock_duration if config.lock_aura_slot else 0.0
        return max(base, own)

    def _run_reaction(self, target, variant, config, ctx) -> None:
        self.stats.reactions_this_frame += 1
        self.stats.reactions_total += 1
        if self.reaction_runner is not None:
            self.reaction_runner(target, variant, config, ctx)

    def _done(self, outcome: Outcome) -> Outcome:
        self.stats.note(outcome)
        return outcome

    # --- dev readout --------------------------------------------------------
    def active_auras(self, enemies, now: float) -> int:
        """How many of `enemies` hold a live aura. A dev-overlay scan, never
        called by gameplay."""
        total = 0
        for enemy in enemies:
            state = getattr(enemy, "elemental", None)
            if state is not None and state.has_aura(now):
                total += 1
        return total

    def clear(self) -> None:
        self._pending.clear()
        self.stats = ResolverStats()
