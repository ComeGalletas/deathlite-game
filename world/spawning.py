"""Enemy spawning: geometry helper + the wave/budget director (spec 3.4 / 3.8).

`SpawnDirector` drives difficulty over the length of a run through a phase
schedule. Each phase defines its enemy composition, spawn interval, pack size,
elite chance and a soft concurrency cap. Separately, `stat_multipliers` ramps
enemy HP and speed with elapsed time. Difficulty therefore rises through several
independent knobs, not one master number (spec 3.4: "Do not increase every
variable simultaneously without reason").
"""
from __future__ import annotations

import math
import random

import pygame

from game import config


def ring_point_outside_view(camera, world_w: int, world_h: int,
                            margin: float = 80.0,
                            rng: random.Random | None = None) -> pygame.Vector2:
    """A world point just outside the visible rectangle, clamped to the world
    (spec 3.4: spawn off-screen, never on the player)."""
    rng = rng or random
    view = camera.visible_rect()
    cx, cy = view.centerx, view.centery
    dist = math.hypot(view.width, view.height) / 2 + margin
    angle = rng.uniform(0, math.tau)
    x = min(max(cx + math.cos(angle) * dist, 8), world_w - 8)
    y = min(max(cy + math.sin(angle) * dist, 8), world_h - 8)
    return pygame.Vector2(x, y)


# fraction-of-run -> composition. `until` is the upper bound (exclusive).
_PHASES = [
    {"until": 0.20, "interval": (1.20, 1.00), "pack": (1, 1), "elite": 0.0,
     "cap": 40, "types": {"chaser": 1.0}},
    {"until": 0.45, "interval": (1.00, 0.82), "pack": (1, 2), "elite": 0.02,
     "cap": 70, "types": {"chaser": 0.6, "fast": 0.25, "swarm": 0.15}},
    {"until": 0.70, "interval": (0.82, 0.66), "pack": (2, 3), "elite": 0.05,
     "cap": 100, "types": {"chaser": 0.28, "fast": 0.16, "swarm": 0.1,
                            "tank": 0.1, "ranged": 0.12, "exploder": 0.07,
                            "shielded": 0.04, "charger": 0.08, "teleporter": 0.05}},
    {"until": 0.95, "interval": (0.66, 0.52), "pack": (2, 4), "elite": 0.10,
     "cap": 130, "types": {"chaser": 0.18, "fast": 0.12, "swarm": 0.09,
                            "tank": 0.12, "ranged": 0.1, "exploder": 0.09,
                            "shielded": 0.07, "summoner": 0.08,
                            "charger": 0.09, "teleporter": 0.06, "warlock": 0.06}},
    {"until": 1.01, "interval": (0.54, 0.44), "pack": (3, 4), "elite": 0.14,
     "cap": 150, "types": {"chaser": 0.14, "fast": 0.12, "tank": 0.13,
                            "ranged": 0.1, "exploder": 0.1, "shielded": 0.09,
                            "summoner": 0.1, "swarm": 0.05,
                            "charger": 0.1, "teleporter": 0.08, "warlock": 0.08}},
]


class SpawnDirector:
    def __init__(self, run_duration: float = config.RUN_DURATION_SECONDS,
                 rng: random.Random | None = None) -> None:
        self.run_duration = max(1.0, run_duration)
        self.rng = rng or random.Random()
        self._timer = 0.8
        self.boss_spawned = False

    # --- schedule lookup ------------------------------------
    def _phase(self, elapsed: float) -> dict:
        f = min(1.0, elapsed / self.run_duration)
        for phase in _PHASES:
            if f < phase["until"]:
                return phase
        return _PHASES[-1]

    def _interval(self, elapsed: float) -> float:
        p = self._phase(elapsed)
        # Lerp the interval across the whole run so it tightens smoothly.
        f = min(1.0, elapsed / self.run_duration)
        lo, hi = p["interval"]
        return lo + (hi - lo) * f

    def stat_multipliers(self, elapsed: float) -> tuple[float, float]:
        """(hp_mult, speed_mult) for enemies spawned at `elapsed`.

        Tuned in Milestone 10: the HP ramp was too steep for a mediocre build --
        a reasonable build should be pressed, not overrun, on the way to the boss.
        """
        f = min(1.0, elapsed / self.run_duration)
        return (1.0 + 1.4 * f, 1.0 + 0.30 * f)

    def boss_time(self) -> float:
        return config.BOSS_FRACTION * self.run_duration

    def should_spawn_boss(self, elapsed: float) -> bool:
        return (not self.boss_spawned) and elapsed >= self.boss_time()

    def mark_boss_spawned(self) -> None:
        self.boss_spawned = True

    # --- per-frame -------------------------------------------
    def update(self, dt: float, elapsed: float, active_count: int) -> list[str]:
        """Return a list of enemy ids to spawn this frame (possibly empty).
        Respects the phase soft cap and the global hard cap (spec 6.3)."""
        if self.boss_spawned:
            return []  # stop the tide while the boss fight is on
        phase = self._phase(elapsed)
        cap = min(phase["cap"], config.MAX_ENEMIES)
        if active_count >= cap:
            return []

        self._timer -= dt
        if self._timer > 0.0:
            return []
        self._timer += self._interval(elapsed)

        lo, hi = phase["pack"]
        pack = self.rng.randint(lo, hi)
        room = cap - active_count
        out: list[str] = []
        ids = list(phase["types"].keys())
        weights = list(phase["types"].values())
        for _ in range(min(pack, room)):
            if self.rng.random() < phase["elite"]:
                out.append("brute" if self.rng.random() < 0.15 else "elite")
            else:
                out.append(self.rng.choices(ids, weights=weights, k=1)[0])
        return out
