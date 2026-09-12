"""Damage per second against the training dummy.

What a build actually does is not a number you can read off the data: weapons
have cooldowns, blessings multiply conditionally, items add affixes, and the
synergies only fire in sequence. The honest way to know is to hit something and
count.

So the meter arms itself on **one** enemy -- the dummy the dev menu spawns --
and records what lands on it. Not `stats["damage_dealt"]`, which is every
enemy in the world: a stray shot at something else would inflate the reading,
and the point of the number is that it is comparable between builds.

Two figures, because one alone misleads:

* **window** -- the last `WINDOW_S` seconds. What the build is doing *now*,
  and the one to read while tuning.
* **total** -- everything since the meter was armed, divided by elapsed. It
  settles where the window oscillates, which matters for a cooldown-gated
  weapon like the Hammer whose window figure swings between blows.

The per-source split is keyed by whatever the damage path named itself with --
a weapon id for a hit or a damage-over-time tick, a blessing id for a proc.
`VILLAGER` is dropped: a village lancer stabbing the dummy is not the hero.
"""
from __future__ import annotations

from collections import deque

# The source string village NPCs damage with. Lives here rather than in
# `npcs.py` because only the meter and the run ledger care.
VILLAGER = "villager"

WINDOW_S = 10.0
# Anything a damage path did not name. Kept visible rather than folded into a
# weapon, so a hole in the attribution shows up as a hole.
UNATTRIBUTED = "other"


class DpsMeter:
    """Armed on one enemy; records what lands on it until disarmed."""

    def __init__(self, window_s: float = WINDOW_S) -> None:
        self.window_s = float(window_s)
        self.target = None
        self.elapsed = 0.0
        self.total = 0.0
        self.by_source: dict[str, float] = {}
        # (timestamp, amount) inside the window, oldest first.
        self._recent: deque = deque()
        self._window_total = 0.0

    # --- arming ---------------------------------------------------
    @property
    def armed(self) -> bool:
        return self.target is not None

    def arm(self, enemy) -> None:
        """Meter `enemy`. Hooks its `damage_sink`, which `Enemy._absorb` calls
        for every point that lands, whatever path delivered it."""
        self.disarm()
        self.reset()
        self.target = enemy
        enemy.damage_sink = self.record

    def disarm(self) -> None:
        if self.target is not None:
            self.target.damage_sink = None
            self.target = None

    def reset(self) -> None:
        self.elapsed = 0.0
        self.total = 0.0
        self.by_source.clear()
        self._recent.clear()
        self._window_total = 0.0

    # --- recording ------------------------------------------------
    def record(self, amount: float, source=None) -> None:
        """One hit. Called through the target's `damage_sink`."""
        if amount <= 0.0:
            return
        key = UNATTRIBUTED if source is None else str(source)
        if key == VILLAGER:
            return
        self.total += amount
        self.by_source[key] = self.by_source.get(key, 0.0) + amount
        self._recent.append((self.elapsed, amount))
        self._window_total += amount

    def update(self, dt: float) -> None:
        """Advance the clock and drop samples that fell out of the window."""
        if self.target is None:
            return
        self.elapsed += dt
        cutoff = self.elapsed - self.window_s
        recent = self._recent
        while recent and recent[0][0] < cutoff:
            self._window_total -= recent.popleft()[1]
        # Float drift over a long session; an empty deque means exactly zero.
        if not recent:
            self._window_total = 0.0

    # --- readout --------------------------------------------------
    @property
    def window_dps(self) -> float:
        """Damage over the last `window_s` seconds. Divided by the window's
        real span, so the figure is not a quarter of the truth while the first
        ten seconds are still filling."""
        span = min(self.elapsed, self.window_s)
        return self._window_total / span if span > 0.0 else 0.0

    @property
    def total_dps(self) -> float:
        return self.total / self.elapsed if self.elapsed > 0.0 else 0.0

    def breakdown(self):
        """`[(source, damage, share)]`, biggest first."""
        if not self.total:
            return []
        return [(k, v, v / self.total)
                for k, v in sorted(self.by_source.items(),
                                   key=lambda kv: -kv[1])]

    def summary(self) -> str:
        """One line for the F1 overlay."""
        if not self.armed:
            return "off"
        return (f"{self.window_dps:7.1f} dps ({self.window_s:.0f}s)   "
                f"avg {self.total_dps:7.1f}   {self.total:8.0f} in "
                f"{self.elapsed:5.1f}s")

    def breakdown_line(self) -> str:
        """The per-source split for the overlay, biggest first."""
        rows = self.breakdown()
        if not rows:
            return "-"
        return "   ".join(f"{k} {share * 100:.0f}%" for k, _dmg, share in rows)
