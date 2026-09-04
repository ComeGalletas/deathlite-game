"""The spawn budget: how often, how many, and which (spec 3.4 / 3.8).

`SpawnDirector` drives difficulty over the length of a run through the phase
schedule in `data/spawn_tables.json` (`spawn/tables.py`). Each phase defines
its enemy composition, spawn interval, pack size and elite chance.
Concurrency is limited by `enemy_count_cap`, which grows with in-game time.
Separately, `stat_multipliers` ramps enemy HP and speed with elapsed time.
Difficulty therefore rises through several independent knobs, not one
master number (spec 3.4: "Do not increase every variable simultaneously
without reason").

The run's chosen difficulty (`config.DIFFICULTIES`) feeds four independent
multipliers -- `spawn_rate` (spawn cadence), `timeline_pace` (how fast the
phase schedule and the boss arrive), `stat_ramp_pace` (the HP/speed ramp)
and `enemy_count_step_scale` (crowd growth). Normal leaves every one at 1.0.

Spawn master S2: moved here from `world/spawning.py` unchanged in behaviour
-- `tests/spawn/test_budget.py` replays a scripted run against the sequence
the old module produced. The tables are handed in, or read from the loaded
content when they are not; the director draws every random number from the
`rng` it is given, in the same order as before.
"""
from __future__ import annotations

import math
import random

from game import config
from spawn.tables import SpawnTables

__all__ = ["SpawnDirector"]


def _default_tables() -> SpawnTables:
    from game.content import get_content
    return get_content().spawn_tables


class SpawnDirector:
    def __init__(self, run_duration: float = config.RUN_DURATION_SECONDS,
                 rng: random.Random | None = None,
                 difficulty: str = config.DIFFICULTY_DEFAULT,
                 tables: SpawnTables | None = None) -> None:
        self._base_run_duration = max(1.0, run_duration)
        self.rng = rng or random.Random()
        self.tables = tables if tables is not None else _default_tables()
        self._timer = 0.8
        self.boss_spawned = False
        # S4: the simulated-enemy budget. `None` leaves the schedule alone
        # (the isolated director the tests pin); the master sets it from
        # `config.ENEMY_LIVE_CAP`.
        self.live_cap: int | None = None
        self.set_difficulty(difficulty)

    def set_difficulty(self, difficulty: str) -> None:
        """(Re)bind the four difficulty factors. Safe to call mid-run (the
        dev-menu live switch does): the phase schedule and the boss re-key off
        the new `run_duration` immediately -- raising the pace late can arm the
        boss on the next frame, which is intentional (dev testing)."""
        if difficulty not in config.DIFFICULTIES:
            difficulty = config.DIFFICULTY_DEFAULT
        f = config.DIFFICULTIES[difficulty]
        self.difficulty = difficulty
        self._spawn_rate = f["spawn_rate"]
        self._timeline_pace = f["timeline_pace"]
        self._stat_ramp_pace = f["stat_ramp_pace"]
        self._enemy_count_step_scale = f["enemy_count_step_scale"]
        # Harder enemy types + the boss arrive sooner: the whole phase schedule
        # is compressed by dividing the run length it is measured against.
        self.run_duration = max(1.0, self._base_run_duration / self._timeline_pace)

    # --- schedule lookup ------------------------------------
    def _phase(self, elapsed: float) -> dict:
        f = min(1.0, elapsed / self.run_duration)
        return self.tables.phase_at(f, self.difficulty)

    def _interval(self, elapsed: float) -> float:
        p = self._phase(elapsed)
        # Lerp the interval across the whole run so it tightens smoothly, then
        # divide by the spawn-rate factor so a harder run spawns more often.
        f = min(1.0, elapsed / self.run_duration)
        lo, hi = p["interval"]
        return (lo + (hi - lo) * f) / self._spawn_rate

    def stat_multipliers(self, elapsed: float) -> tuple[float, float]:
        """(hp_mult, speed_mult) for enemies spawned at `elapsed`.

        Tuned in Milestone 10: the HP ramp was too steep for a mediocre build --
        a reasonable build should be pressed, not overrun, on the way to the boss.
        `stat_ramp_pace` accelerates the ramp on the faster difficulties (the
        inverse of the timeline compression), so a shorter run still reaches the
        full ramp by its end.
        """
        f = min(1.0, elapsed * self._stat_ramp_pace / self._base_run_duration)
        return (1.0 + 1.4 * f, 1.0 + 0.30 * f)

    def enemy_count_cap(self, elapsed: float) -> int:
        """The live ceiling on concurrent enemies. Starts at ENEMY_COUNT_BASE
        and grows by ceil(STEP * step_scale) every STEP_PERIOD seconds of
        in-game time (`elapsed` is PlayingState.stats["time"] -- the HUD clock,
        pause-safe, no wall clock), clamped to the hard cap."""
        steps = int(max(0.0, elapsed) // config.ENEMY_COUNT_STEP_PERIOD)
        step = math.ceil(config.ENEMY_COUNT_STEP * self._enemy_count_step_scale)
        cap = min(config.ENEMY_COUNT_HARD_CAP,
                  config.ENEMY_COUNT_BASE + step * steps)
        if self.live_cap is not None:
            cap = min(cap, int(self.live_cap))
        return cap

    def boss_time(self) -> float:
        return config.BOSS_FRACTION * self.run_duration

    def should_spawn_boss(self, elapsed: float) -> bool:
        return (not self.boss_spawned) and elapsed >= self.boss_time()

    def mark_boss_spawned(self) -> None:
        self.boss_spawned = True

    def roll_elite(self) -> str:
        """An elite slot: the rare one on a single draw under `rare_chance`,
        else the default. One `random()` either way, as it always was."""
        el = self.tables.elites
        return el["rare"] if self.rng.random() < el["rare_chance"] else el["default"]

    # --- per-frame -------------------------------------------
    def update(self, dt: float, elapsed: float, active_count: int) -> list[str]:
        """Return a list of enemy ids to spawn this frame (possibly empty).
        Respects the time-growing concurrency cap (spec 6.3)."""
        if self.boss_spawned:
            return []  # stop the tide while the boss fight is on
        phase = self._phase(elapsed)
        cap = self.enemy_count_cap(elapsed)
        if active_count >= cap:
            return []

        self._timer -= dt
        if self._timer > 0.0:
            return []
        self._timer += self._interval(elapsed)

        lo, hi = phase["pack"]
        pack = self.rng.randint(lo, hi)
        return self._roll_slots(phase, min(pack, cap - active_count))

    def _roll_slots(self, phase: dict, n: int) -> list[str]:
        """`n` enemy ids for this phase, one draw per slot (an elite check,
        then the weighted type)."""
        out: list[str] = []
        ids = list(phase["types"].keys())
        weights = list(phase["types"].values())
        for _ in range(n):
            if self.rng.random() < phase["elite"]:
                out.append(self.roll_elite())
            else:
                out.append(self.rng.choices(ids, weights=weights, k=1)[0])
        return out

    def roll_pack(self, elapsed: float) -> list[str]:
        """One pack for this moment of the run, drawn off-schedule: the
        timer and the cap are not consulted. S4's residents use it, so an
        island's first population is the mix the run would spawn anyway."""
        phase = self._phase(elapsed)
        lo, hi = phase["pack"]
        return self._roll_slots(phase, self.rng.randint(lo, hi))
