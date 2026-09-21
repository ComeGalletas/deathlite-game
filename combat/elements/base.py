"""The interface every element implements (design §2.2).

An element is stateless: one instance serves every enemy, and all per-enemy
state (the aura, the statuses) lives on the enemy (§3). The hooks receive
the target, the source (the hit that carried the element) and a context
the resolver supplies; what those are is fixed in M2/M3 when the resolver
and the four elements land. `Element` itself is the M1 placeholder the
registry holds until then, so the registry is complete from day one.
"""
from __future__ import annotations

from enum import IntEnum

from combat.elements.ids import ElementId


class AuraEnd(IntEnum):
    """Why an aura left an enemy (`on_aura_ended`'s `reason`)."""
    EXPIRED = 1
    CONSUMED = 2      # a reaction took it
    DEATH = 3


class Element:
    """Base class and interface. Subclasses set `ID` and override the
    hooks they need; the defaults do nothing, which is right for the two
    marker-only elements (Thunder, Wind have no bound status)."""
    ID: ElementId = ElementId.NONE

    def __init__(self, element_id: ElementId | None = None) -> None:
        self.id = self.ID if element_id is None else element_id

    @property
    def key(self) -> str:
        return self.id.key

    # -- hooks ------------------------------------------------------------
    # Each takes the target and the `HitContext` the resolver built. The
    # context carries the moment's two flags -- `bound` (may a status share
    # the aura's life?) and `refreshed` (is this a repeat?) -- so one hook
    # covers applying, refreshing and the locked-slot case rather than three
    # near-identical ones.
    def apply_initial_effect(self, target, ctx) -> None:
        """Damage, chain, wind area... (§4). M3."""

    def on_applied(self, target, ctx) -> None:
        """Create or refresh this element's status. `ctx.bound` is False on
        a locked slot, where Fire's burn and Ice's chill are standalone
        (§3.2); `ctx.refreshed` marks a repeat of the element already on the
        aura."""

    def on_aura_ended(self, target, reason: AuraEnd, ctx) -> None:
        """The aura left the slot. Bound statuses are ended by the resolver,
        which owns that contract; this is for anything else the element
        keeps (Ice's stack counter)."""

    def __repr__(self) -> str:
        return f"<Element {self.key}>"
