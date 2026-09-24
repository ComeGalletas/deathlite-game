"""The last reactions a run fired, for the dev overlay (CMB-009.4, §10.3).

The resolver appends one entry each time a reaction actually runs -- at
once, or a frame later when the per-frame budget held it over -- and the
developer overlay reads them newest first. A fixed-length ring, so it costs
one append per reaction and never grows.

`depth` is how deep in a cascade the reaction was set off: 0 for one a
weapon's hit triggered, 1 for one set off inside another reaction's run
(a tornado or a Superconduct jump laying an aura on a body that already
held one), and so on. `damage` is what the reaction itself dealt through
its context -- to its carrier and to the bodies it reached -- not what the
reactions it set off went on to deal, which log their own lines.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class LoggedReaction:
    serial: int          # the run's reaction count when it ran (1-based)
    time: float          # run seconds when it ran
    reaction: str        # reaction key, e.g. "overload"
    aura: str            # element key the carrier held
    trigger: str         # element key of the hit that met it
    damage: float
    depth: int
    deferred: bool       # held over a frame by the budget


class ReactionLog:
    __slots__ = ("_entries",)

    def __init__(self, capacity: int) -> None:
        self._entries: deque[LoggedReaction] = deque(maxlen=max(1, int(capacity)))

    @property
    def capacity(self) -> int:
        return self._entries.maxlen

    def record(self, entry: LoggedReaction) -> None:
        self._entries.append(entry)

    def newest(self, n: int | None = None) -> list[LoggedReaction]:
        """The most recent `n` entries (all of them by default), newest first."""
        out = list(reversed(self._entries))
        return out if n is None else out[:n]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
