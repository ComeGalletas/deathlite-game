"""Pacing: one bounded multiplier on the spawn cadence, read off the
condition of the run.

Spawn master S6. Five signals, each normalised to -1..1, are combined by
the weights in the tables, smoothed by an exponential moving average, held
at 1.0 inside a dead-band, and clamped to `bounds`:

    hp_fraction   +1 at full health, -1 at none
    damage_rate   0 when unhurt, -1 when losing `damage_rate_full` of max
                  HP per second (averaged over `window`)
    kill_rate     kills against spawns over `window`: +1 when the player
                  clears twice as fast as the master spawns, -1 when kills
                  stop
    crowd         0 when the live list is empty, -1 at the live cap
    lull          0 just after a hit, +1 after `lull_seconds` without one

The weighted mean maps to a target: above zero it leans toward the upper
bound, below zero toward the lower. The EMA (`tau`) is the smoothing, the
dead-band (`dead_band`) the hysteresis, the bounds the safety rail -- a
bad weight can make pacing dull, never empty or flood the map.

`value` is the condition multiplier; the master multiplies `base` (the
standing multiplier, 5 today) by it and by the named modifiers
(`SpawnMaster.set_modifier`), and scales the director's cadence with the
product. Pacing never touches the mix or the stat ramp, and it
does not move the live cap: that is the performance budget.

Knobs from the `pacing` section of `data/spawn_tables.json`.
"""
from __future__ import annotations

import math
from collections import deque

__all__ = ["Pacing"]

_KEYS = ("base", "bounds", "tau", "dead_band", "weights", "window", "lull_seconds",
         "damage_rate_full")
_SIGNALS = ("hp_fraction", "damage_rate", "kill_rate", "crowd", "lull")


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class Pacing:
    def __init__(self, knobs: dict) -> None:
        missing = [k for k in _KEYS if k not in knobs]
        if missing:
            raise KeyError(f"spawn_tables.json `pacing` lacks {missing}")
        # The standing multiplier on the cadence (S9): `value` and the named
        # modifiers scale the director *on top* of it. 1 was "normal" until
        # the owner set it to 5.
        self.base = float(knobs["base"])
        self.lo, self.hi = (float(v) for v in knobs["bounds"])
        self.tau = float(knobs["tau"])
        self.dead_band = float(knobs["dead_band"])
        self.weights = {k: float(knobs["weights"].get(k, 0.0)) for k in _SIGNALS}
        self.window = float(knobs["window"])
        self.lull_seconds = float(knobs["lull_seconds"])
        self.damage_rate_full = float(knobs["damage_rate_full"])
        self.value = 1.0
        self.target = 1.0
        self.signals: dict[str, float] = {k: 0.0 for k in _SIGNALS}
        self._kills: deque = deque()          # timestamps
        self._spawns: deque = deque()
        self._damage: deque = deque()         # (timestamp, fraction of max hp)
        self._last_hit: float | None = None

    # --- inputs -----------------------------------------------------------
    def on_kill(self, now: float) -> None:
        self._kills.append(now)

    def on_spawn(self, now: float) -> None:
        self._spawns.append(now)

    def on_damage(self, now: float, fraction: float) -> None:
        self._damage.append((now, max(0.0, float(fraction))))
        self._last_hit = now

    def _trim(self, now: float) -> None:
        edge = now - self.window
        for q in (self._kills, self._spawns):
            while q and q[0] < edge:
                q.popleft()
        while self._damage and self._damage[0][0] < edge:
            self._damage.popleft()

    # --- per frame --------------------------------------------------------
    def update(self, dt: float, now: float, hp_fraction: float,
               live: int, live_cap: int) -> float:
        self._trim(now)
        s = self.signals
        s["hp_fraction"] = _clamp(hp_fraction, 0.0, 1.0) * 2.0 - 1.0
        lost = sum(f for _t, f in self._damage) / self.window
        s["damage_rate"] = -_clamp(lost / self.damage_rate_full, 0.0, 1.0)
        kills, spawns = len(self._kills), len(self._spawns)
        if spawns == 0 and kills == 0:
            s["kill_rate"] = 0.0
        else:
            s["kill_rate"] = _clamp(kills / max(1, spawns) - 1.0, -1.0, 1.0)
        s["crowd"] = -_clamp(live / live_cap, 0.0, 1.0) if live_cap > 0 else 0.0
        since = (now - self._last_hit) if self._last_hit is not None else self.lull_seconds
        s["lull"] = _clamp(since / self.lull_seconds, 0.0, 1.0)

        total = sum(self.weights.values())
        mean = (sum(self.weights[k] * s[k] for k in _SIGNALS) / total) if total > 0 else 0.0
        if abs(mean) < self.dead_band:
            self.target = 1.0
        elif mean > 0.0:
            self.target = 1.0 + mean * (self.hi - 1.0)
        else:
            self.target = 1.0 + mean * (1.0 - self.lo)
        self.target = _clamp(self.target, self.lo, self.hi)
        if dt > 0.0 and self.tau > 0.0:
            self.value += (self.target - self.value) * (1.0 - math.exp(-dt / self.tau))
        else:
            self.value = self.target
        self.value = _clamp(self.value, self.lo, self.hi)
        return self.value

    def describe(self) -> str:
        return " ".join(f"{k[:4]}{v:+.2f}" for k, v in self.signals.items())
