"""Per-enemy elemental state: the aura slot, its lock, and Ice's stacks
(design §3.1).

One small slotted object per enemy, created with the enemy and cleared on
death. Every timestamp is **absolute run-clock time**, so expiry is a
comparison and nothing has to be decremented per frame: with a few hundred
enemies on the field that difference is the whole point.

Auras therefore expire **lazily** -- no scan notices the moment one lapses.
That is safe because a bound status (Fire's burn, Ice's chill) is applied
with the same duration as the aura, so it expires on its own clock at the
same instant. Only *consumption* by a reaction has to end a bound status
explicitly, and that path is taken while the resolver holds the enemy.

Ice's stack count lives here rather than on the `chill` status (owner's
decision, 2026-09-21): `chill` is the Grave Totem's refresh-only slow, and
making it a stacking status so the elemental system could count it would
have let Chilling Bolts freeze enemies. Keeping the counter beside the aura
leaves that blessing exactly as it was, and reactions that apply slow
without an aura (IceWind) can still bump it.
"""
from __future__ import annotations

from combat.elements.ids import ElementId


class ElementalState:
    __slots__ = ("aura", "aura_expires_at", "locked_until", "source_weapon",
                 "source_damage", "ice_stacks", "freeze_immune_until",
                 "knock_source", "contact_hits")

    def __init__(self) -> None:
        self.aura: ElementId = ElementId.NONE
        self.aura_expires_at: float = 0.0
        # The aura slot takes no new aura while `now < locked_until`; every
        # reaction starts one (§3), and some reactions extend it.
        self.locked_until: float = 0.0
        # Which weapon applied the live aura -- tracking only (§3.6).
        self.source_weapon: str = ""
        # **How big the hit was** that applied it. Not tracking: this is one
        # of the two numbers a reaction is paid from (owner's rework,
        # 2026-09-22), so an aura that forgot it would leave the reaction
        # reading a single hit again, which is what the rework replaced.
        self.source_damage: float = 0.0
        # Ice applications since the last freeze; `freeze.stacks_required`
        # of them freeze the enemy and reset this to zero.
        self.ice_stacks: int = 0
        # No second freeze before this time (`freeze.immunity_duration`).
        self.freeze_immune_until: float = 0.0
        # Who last shoved this body. A frozen enemy that slides into another
        # deals its contact damage on that weapon's account (design §3.6:
        # "the weapon whose knockback pushed the frozen enemy").
        self.knock_source: str = ""
        # Bodies already clipped during the current slide. `None` until this
        # one is knocked back at all, so a still enemy carries no set.
        self.contact_hits = None

    # --- queries -------------------------------------------------------
    def element(self, now: float) -> ElementId:
        """The live aura, or `NONE` when the slot is empty or has lapsed."""
        if self.aura != ElementId.NONE and now >= self.aura_expires_at:
            return ElementId.NONE
        return self.aura

    def has_aura(self, now: float) -> bool:
        return self.element(now) != ElementId.NONE

    def remaining(self, now: float) -> float:
        """Seconds left on the live aura, else 0.0 (dev inspector)."""
        return max(0.0, self.aura_expires_at - now) if self.has_aura(now) else 0.0

    def is_locked(self, now: float) -> bool:
        return now < self.locked_until

    def lock_remaining(self, now: float) -> float:
        return max(0.0, self.locked_until - now)

    def freeze_immune(self, now: float) -> bool:
        return now < self.freeze_immune_until

    # --- mutation --------------------------------------------------------
    def set_aura(self, element: ElementId, now: float, duration: float,
                 weapon_id: str = "", damage: float = 0.0) -> None:
        self.aura = element
        self.aura_expires_at = now + duration
        self.source_weapon = weapon_id
        self.source_damage = max(0.0, float(damage))

    def refresh_aura(self, now: float, duration: float, weapon_id: str = "",
                     damage: float = 0.0) -> None:
        """Same element again: push the expiry out and re-attribute.

        The damage takes the **larger** of the two rather than the latest.
        A refresh is the same aura being kept alive, and letting a weak
        re-application overwrite a heavy one would mean a fast cheap weapon
        could quietly defuse a reaction the player had set up with a slow
        expensive one -- which is the failure the rework was for."""
        self.aura_expires_at = max(self.aura_expires_at, now + duration)
        if weapon_id:
            self.source_weapon = weapon_id
        self.source_damage = max(self.source_damage, float(damage))

    def consume_aura(self) -> ElementId:
        """Take the aura off the slot (a reaction). Returns what it was."""
        was, self.aura = self.aura, ElementId.NONE
        self.aura_expires_at = 0.0
        self.source_weapon = ""
        self.source_damage = 0.0
        return was

    def lock(self, now: float, seconds: float) -> None:
        """Lock the slot for `seconds`, never shortening an existing lock
        (§3: the effective lock is the longer of the two)."""
        self.locked_until = max(self.locked_until, now + seconds)

    def add_ice_stack(self, amount: int = 1) -> int:
        self.ice_stacks = max(0, self.ice_stacks + int(amount))
        return self.ice_stacks

    def reset_ice_stacks(self) -> None:
        self.ice_stacks = 0

    def note_contact(self, other) -> bool:
        """Claim `other` for the current slide. False when it was already
        clipped, so each body takes at most one contact per knockback
        instance (design §4.2)."""
        if self.contact_hits is None:
            self.contact_hits = set()
        key = id(other)
        if key in self.contact_hits:
            return False
        self.contact_hits.add(key)
        return True

    def end_slide(self) -> None:
        """The body came to rest: the next shove starts with a clean sheet,
        and a still enemy carries no set at all."""
        self.contact_hits = None

    def clear(self) -> None:
        """Death, or an enemy recycled back into the pool."""
        self.aura = ElementId.NONE
        self.aura_expires_at = 0.0
        self.locked_until = 0.0
        self.source_weapon = ""
        self.ice_stacks = 0
        self.freeze_immune_until = 0.0
        self.knock_source = ""
        self.contact_hits = None

    def __repr__(self) -> str:
        return (f"<ElementalState {self.aura.key} until {self.aura_expires_at:.2f} "
                f"lock {self.locked_until:.2f} ice {self.ice_stacks}>")
