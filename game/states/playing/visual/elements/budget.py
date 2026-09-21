"""The elemental particle allowance (design §9, particle budget).

A hundred enemies with auras would happily ask for more particles than the
pool holds, and the pool answers by silently dropping whatever asks last --
which in practice means the hit bursts and the death poofs, because the
auras get there first every frame.

So elements draw from their own allowance instead: a cap per frame and a
smaller one per element, both refilled at the top of the frame. When it runs
out the auras keep their rings and markers and simply stop shedding
particles, which is the level-of-detail the design asks for rather than a
visible failure.
"""
from __future__ import annotations

from combat.elements.ids import ELEMENTS


class ParticleBudget:
    __slots__ = ("per_frame", "per_element", "_left", "_by_element",
                 "spent", "refused")

    def __init__(self, per_frame: int, per_element: int) -> None:
        self.per_frame = int(per_frame)
        self.per_element = int(per_element)
        self._left = self.per_frame
        self._by_element = {e: self.per_element for e in ELEMENTS}
        # What the last frame actually used, for the debug overlay.
        self.spent = 0
        self.refused = 0

    def begin_frame(self) -> None:
        self._left = self.per_frame
        for element in self._by_element:
            self._by_element[element] = self.per_element
        self.spent = 0
        self.refused = 0

    def take(self, element, count: int = 1) -> int:
        """Claim up to `count` particles for `element`; returns how many were
        granted, which may be none."""
        if count <= 0:
            return 0
        room = min(count, self._left, self._by_element.get(element, 0))
        if room <= 0:
            self.refused += count
            return 0
        self._left -= room
        self._by_element[element] -= room
        self.spent += room
        if room < count:
            self.refused += count - room
        return room

    @property
    def left(self) -> int:
        return self._left

    def report(self) -> str:
        """One line for the F1 overlay."""
        return f"{self.spent}/{self.per_frame} used, {self.refused} refused"
