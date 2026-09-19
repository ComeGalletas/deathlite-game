"""The spawn budget: when a company arrives and which group it is
(spec 3.4 / 3.8).

`SpawnDirector.update(dt, elapsed, blocked)` returns **a group name or
None**. It does not say which enemies -- a company is one social group and
the master composes it from the resolved roster (`spawn/roster.py`) -- and
it does not look at the live count, because the cap is a gate the master
holds.

**Two ladders**, both read from `cooldowns` in
`data/enemies/spawn_tables.json`:

* the **common cadence**, how long before the next company of any kind;
* the **elite gate**, which decides when an elite-bearing group is
  *eligible*. Picking one resets the common cadence too, so an elite and a
  common company never land back to back.

Both step down every `step_seconds` and stop at their floors. The gate
falls faster and floors higher, so elite companies go from roughly one in
three at the start to one in one-and-a-bit late. A hard `elite_unlock`
keeps elites out of the opening whatever the ladder says. The two pools are
drawn from separately: while the gate is shut only the common groups are
eligible.

Concurrency is `enemy_count_cap`, which grows with in-game time; the master
gates whole companies against it. `stat_multipliers` ramps enemy HP and
speed with elapsed time. Difficulty therefore rises through several
independent knobs, not one master number (spec 3.4: "Do not increase every
variable simultaneously without reason").

**Difficulty.** `config.DIFFICULTIES` carries four factors, of which this
module reads three: `timeline_pace` (the run clock and the whole ladder),
`stat_ramp_pace` (the HP/speed ramp) and `enemy_count_step_scale` (crowd
growth). `spawn_rate` is **no longer read** -- it stays in config as part of
a difficulty's description, but nothing multiplies by it since the cadence
became the cooldown ladder (G3).

Everything time-shaped divides by `timeline_pace`, the ladder's *step*
included. That is what makes every difficulty reach the same elite count at
its boss: the step and the boss time scale by the same factor and cancel,
so harder means the same elites sooner rather than more of them.

**History.** This was a phase schedule until G3 (2026-09-18) -- ramp-fraction
bands of enemy weights, pack sizes and lerped intervals, with `ramp_seconds`
as its own clock and `min(pack, cap - active)` clipping a pack that did not
fit. All of it went with the company model, along with the S2 sequence
fixture that had replayed the pre-move `world/spawning.py` draw for draw.
The tables are still handed in, or read from the loaded content when they
are not, and the director still draws every random number from the `rng` it
is given.
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
        self._cd = dict(self.tables.cooldowns)
        # G3: the two ladders. The common cadence starts expired, so the
        # first company is chosen and placed like any other rather than
        # after an opening pause (owner, 2026-09-17). The elite gate starts
        # at its full length, and the hard unlock is later still.
        self._common_timer = 0.0
        self._elite_timer = float(self._cd.get("elite", 0.0))
        # Set by the master, which owns the resolved roster: the director
        # picks *which group*, the master composes it.
        self.roster = None
        self.boss_spawned = False
        # S4: the simulated-enemy budget. `None` leaves the schedule alone
        # (the isolated director the tests pin); the master sets it from
        # `config.ENEMY_LIVE_CAP`.
        self.live_cap: int | None = None
        self.set_difficulty(difficulty)

    def set_difficulty(self, difficulty: str) -> None:
        """(Re)bind the difficulty factors. Safe to call mid-run (the
        dev-menu live switch does): the ladder, the elite unlock and the boss
        all re-key off the new `timeline_pace` immediately -- raising the pace
        late can arm the boss on the next frame, which is intentional (dev
        testing). The ladder timers already running are left alone; only the
        lengths they are reset to change."""
        if difficulty not in config.DIFFICULTIES:
            difficulty = config.DIFFICULTY_DEFAULT
        f = config.DIFFICULTIES[difficulty]
        self.difficulty = difficulty
        self._timeline_pace = f["timeline_pace"]
        self._stat_ramp_pace = f["stat_ramp_pace"]
        self._enemy_count_step_scale = f["enemy_count_step_scale"]
        # G3: `spawn_rate` is no longer read. The cadence is the cooldown
        # ladder, and `timeline_pace` is the only difficulty factor it
        # consults -- the factor stays in `config.DIFFICULTIES` because it
        # is a difficulty's description, but nothing multiplies by it now.
        self.run_duration = max(1.0, self._base_run_duration / self._timeline_pace)
        # The ladder's own clock. Compressing the step as well as the values
        # is what makes every difficulty reach the same elite count at its
        # boss: the step and the boss time scale by the same factor and
        # cancel, so harder means the same elites sooner, not more of them.
        self.step_seconds = max(0.001, float(self._cd.get("step_seconds", 120.0))
                                / self._timeline_pace)
        self.elite_unlock = float(self._cd.get("elite_unlock", 0.0)) / self._timeline_pace
        self.cap_retry = float(self._cd.get("cap_retry", 2.0)) / self._timeline_pace

    # --- the two ladders (G3) -------------------------------
    def steps(self, elapsed: float) -> int:
        """How many rungs of the ladder the run has climbed. One every
        `step_seconds`, compressed by `timeline_pace` like everything else
        time-shaped, so the whole ladder scales together rather than just
        its values."""
        return int(max(0.0, elapsed) // self.step_seconds)

    def common_cooldown(self, elapsed: float) -> float:
        """How long before the next company of any kind."""
        cd = self._cd
        return max(cd["common_floor"],
                   cd["common"] - cd["common_decay"] * self.steps(elapsed)) / self._timeline_pace

    def elite_cooldown(self, elapsed: float) -> float:
        """How long an elite-bearing group stays ineligible after one is
        picked. Falls three times as fast as the common cadence and floors
        three times higher, so elite companies go from about one in three at
        the start to roughly one in one-and-a-bit by minute eight."""
        cd = self._cd
        return max(cd["elite_floor"],
                   cd["elite"] - cd["elite_decay"] * self.steps(elapsed)) / self._timeline_pace

    def elite_unlocked(self, elapsed: float) -> bool:
        """The hard gate: no elite group at all before `elite_unlock`,
        whatever the ladder says."""
        return elapsed >= self.elite_unlock and self._elite_timer <= 0.0

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

    # --- choosing a company (G3) -----------------------------
    def pool(self, elapsed: float) -> list[str]:
        """The groups eligible right now.

        The two pools are **separate** (owner, 2026-09-17): while the elite
        gate is open the draw is from the elite-bearing groups, and
        otherwise from the common ones. If the pool that should be used is
        empty -- which the roster allows, since a group whose data did not
        hold up is simply absent -- the other one is used rather than
        spawning nothing.
        """
        if self.roster is None:
            return []
        if self.elite_unlocked(elapsed):
            return self.roster.names(elite=True) or self.roster.names(elite=False)
        return self.roster.names(elite=False) or self.roster.names(elite=True)

    def update(self, dt: float, elapsed: float, blocked: bool = False) -> str | None:
        """The group to spawn a company of this frame, or `None`.

        The director no longer says *which enemies*: a company is one group,
        and the master composes it from the roster. It no longer looks at
        the live count either -- the cap is a gate the master holds, and a
        company that does not fit waits whole rather than arriving short.

        `blocked` is the master saying it is still holding a company the cap
        refused. The timers keep running, and the cadence is left expired
        rather than consumed, so the moment the gate opens the next company
        goes immediately instead of paying the wait twice.
        """
        if self.boss_spawned:
            return None                     # stop the tide during the fight
        self._common_timer -= dt
        self._elite_timer -= dt
        if blocked or self._common_timer > 0.0:
            return None
        pool = self.pool(elapsed)
        if not pool:
            return None
        name = self.rng.choice(pool)
        self._common_timer = self.common_cooldown(elapsed)
        if self.roster is not None and self.roster.get(name) is not None \
                and self.roster.get(name).has_elites:
            # Spawning an elite company resets the common cadence too, so an
            # elite and a common company never land back to back.
            self._elite_timer = self.elite_cooldown(elapsed)
        return name
