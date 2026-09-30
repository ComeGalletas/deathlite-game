"""The elemental particle allowance (design §9, particle budget).

A hundred enemies with auras would happily ask for more particles than the
pool holds, and the pool answers by silently dropping whatever asks last --
which in practice means the hit bursts and the death poofs, because the
auras get there first every frame.

So elements draw from their own allowance instead: a cap per step and a
smaller one per element, both refilled at the top of each update step. When
it runs out the auras keep their rings and markers and simply stop shedding
particles, which is the level-of-detail the design asks for rather than a
visible failure.

The two numbers are per 1/60 s of play, not per step (RND-011.D3). The shed
runs once per update step, and a step is 1/62 s on the desktop's capped
tick but about 1/175 s in the browser, which is paced by the display: a
fixed allowance per step would let the browser shed three times as much a
second before the cap bit. So each step is granted its share of the
second, and the fraction a step cannot hand out as a whole particle is
carried to the next, which keeps the grant exact over time.
"""
from __future__ import annotations

from combat.elements.ids import ELEMENTS


class ParticleBudget:
    __slots__ = ("per_frame", "per_element", "_left", "_by_element",
                 "_frame_carry", "_element_carry", "granted", "spent",
                 "refused")

    # What `per_frame` and `per_element` are counted against: one frame of
    # the 60 fps the numbers were tuned at (RND-011.D3).
    RATE_HZ = 60.0

    def __init__(self, per_frame: int, per_element: int) -> None:
        self.per_frame = int(per_frame)
        self.per_element = int(per_element)
        self._left = 0
        self._by_element = {e: 0 for e in ELEMENTS}
        # The fraction of a particle each allowance was owed but could not
        # be granted whole, handed on to the next step.
        self._frame_carry = 0.0
        self._element_carry = {e: 0.0 for e in ELEMENTS}
        # What the last step was granted and actually used, for the debug
        # overlay.
        self.granted = 0
        self.spent = 0
        self.refused = 0

    def begin_step(self, dt: float) -> None:
        """Refill for an update step `dt` seconds long.

        Unspent allowance is not carried: a step that sheds nothing has not
        earned the next one a burst. Only the fraction is, so over any run
        of steps the grant is `per_frame * 60` a second, whatever their
        length.
        """
        share = max(0.0, dt) * self.RATE_HZ
        self._left, self._frame_carry = _whole(
            self.per_frame * share + self._frame_carry)
        self.granted = self._left
        for element in self._by_element:
            self._by_element[element], self._element_carry[element] = _whole(
                self.per_element * share + self._element_carry[element])
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
        """One line for the F1 overlay: the last step's use against what
        that step was granted, which is `per_frame` only at 60 steps a
        second (about 31 at the browser's 175 Hz)."""
        return f"{self.spent}/{self.granted} used, {self.refused} refused"


def _whole(owed: float) -> tuple[int, float]:
    """`owed` split into the particles grantable now and the fraction kept.

    The nudge keeps a carry summed back to a whole number (0.999...) from
    being floored one short."""
    whole = int(owed + 1e-9)
    return whole, max(0.0, owed - whole)
