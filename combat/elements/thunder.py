"""Thunder: damage, then a branching chain of jumps (design §4.3).

The hit enemy takes the chain's damage and then the chain spreads to the
closest `targets_per_jump` enemies within `max_range`; each of those becomes
a node with one fewer jump left. It is resolved **breadth-first**, one jump
level at a time, an enemy is never taken twice by the same chain, and the
whole thing stops at `max_targets` -- which is not optional, because the
worst case grows as `Y + Y^2 + ... + Y^jumps`.

Every node goes back through the resolver, so a jump obeys the same rules a
direct hit does:

* **no aura, or a Thunder aura** -- jump damage, aura applied or refreshed,
  and the node spreads onward. Thunder laying auras across a crowd is the
  point of it.
* **a different aura** -- the resolver's step 5 takes over: no jump damage
  at all, the aura is consumed, the reaction fires, and **this node stops
  spreading**. Other branches carry on.
* **a locked slot** -- jump damage only, and it keeps spreading (open item
  1), because a locked node is an ordinary node that simply cannot hold an
  aura.

What stops the recursion is `ctx.chain`: a node carries one, and only a hit
with none may start a tree. Without that every jump would branch a fresh
chain of its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from combat.elements import tracking
from combat.elements.base import Element
from combat.elements.ids import ElementId
from combat.elements.spread import breadth_first


# How long a jump's placeholder arc stays on screen (design §8.6 replaces it
# with a pooled effect).
ARC_SECONDS = 0.18


@dataclass(frozen=True)
class ChainNode:
    """One node of a chain in flight. `level` is how many jumps from the
    original hit; `falloff` is the damage multiplier that has accumulated
    over those levels."""
    level: int
    falloff: float


class Thunder(Element):
    ID = ElementId.THUNDER

    def apply_initial_effect(self, target, ctx) -> None:
        cfg = ctx.config.chain
        node = ctx.chain
        multiplier = node.falloff if node is not None else 1.0
        ctx.deal(target, cfg.damage.resolve(ctx.hit_damage) * multiplier,
                 tracking.THUNDER_CHAIN)
        if node is None:
            self.spread(target, ctx, cfg)

    def spread(self, origin, ctx, cfg) -> int:
        """Run the whole jump tree from `origin`. Returns how many enemies
        the chain reached, not counting the one that was hit."""
        world = ctx.world
        return breadth_first(
            world, origin,
            jumps=cfg.jumps, per_jump=cfg.targets_per_jump,
            max_range=cfg.max_range, max_targets=cfg.max_targets,
            visit=lambda hit, level: self.strike(
                hit, ctx, level, cfg.falloff ** level),
            arc=lambda a, b: world.add_arc(a, b, ElementId.THUNDER,
                                           ctx.now + ARC_SECONDS))

    @staticmethod
    def strike(target, ctx, level: int, falloff: float) -> bool:
        """One jump. Returns whether the chain may continue from here: a node
        that set off a reaction does not spread further (design R17)."""
        from combat.elements.resolve import Outcome

        outcome = ctx.resolver.apply(
            target, ElementId.THUNDER, weapon_id=ctx.weapon_id,
            hit_damage=ctx.hit_damage, now=ctx.now,
            chain=ChainNode(level, falloff))
        return outcome not in (Outcome.REACTION, Outcome.DEFERRED)
