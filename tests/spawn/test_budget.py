"""The spawn director (spec 3.4 / 3.8 / 8: "Enemy spawn constraints"),
`spawn/budget.py` reading `data/enemies/spawn_tables.json`.

**G3 rewrote what this module tests.** The director used to walk a phase
schedule, roll a pack size and draw each body's type; it now names a *group*
when its cooldown ladder is ready and lets the master compose the company.
So the phase tests are gone, and with them the S2 sequence fixture
(`director_sequence.json`): it replayed the pre-move `world.spawning` module
draw for draw, and there is no draw sequence left to replay. It had been
wound back three times to survive tuning, and this is where that proof ends
rather than being re-recorded against a unit that no longer exists.

What survives untouched is everything the company model does not change:
`stat_multipliers`, `enemy_count_cap`, the boss clock, and the difficulty
factors that feed them.
"""
import random
import unittest
from unittest import mock

from game import config
from game.content import get_content
from spawn.budget import SpawnDirector
from spawn.roster import resolve_groups
from spawn.tables import SpawnTables


def _director(seed: int = 7, duration: float = 600.0,
              difficulty: str = "normal", roster=True) -> SpawnDirector:
    d = SpawnDirector(run_duration=duration, rng=random.Random(seed),
                      difficulty=difficulty)
    if roster:
        d.roster = resolve_groups(get_content().spawn_tables.groups,
                                  get_content().enemies)
    return d


def _run(director, seconds: float, dt: float = 1 / 30) -> list[tuple[float, str]]:
    """Every company the director names over `seconds`, with its time."""
    out, t = [], 0.0
    while t < seconds:
        name = director.update(dt, t)
        if name is not None:
            out.append((t, name))
        t += dt
    return out


class LadderTests(unittest.TestCase):
    """The two cooldowns, and the step they share."""

    def test_each_ladder_walks_its_own_table_from_start_to_floor(self):
        """The shape, read off `cooldowns` rather than restated here.

        The numbers are tuning and have already moved once (the common base
        went 5 -> 2 on 2026-09-18), so pinning them would mean editing this
        test every time the game is balanced. What must hold is that each
        ladder starts at its declared value, drops by its decay once per
        step, and stops at its floor.
        """
        d = _director()
        cd = get_content().spawn_tables.cooldowns
        for name, fn in (("common", d.common_cooldown), ("elite", d.elite_cooldown)):
            start, decay = cd[name], cd[f"{name}_decay"]
            floor = cd[f"{name}_floor"]
            for steps in range(0, 8):
                t = steps * cd["step_seconds"]
                with self.subTest(ladder=name, steps=steps):
                    self.assertAlmostEqual(fn(t), max(floor, start - decay * steps),
                                           places=6)
            self.assertAlmostEqual(fn(1e6), floor, places=6)

    def test_the_elite_gate_stays_the_slower_of_the_two(self):
        """The shape the design depends on: elite companies are never more
        frequent than common ones at any point in the run, however the two
        are tuned. Not strictly rarer: with the common ladder at 5 / 0.5 / 1
        (owner, 2026-09-20) the two meet at 3 s for the minute-8 step, and
        the owner chose that tuning knowing it."""
        d = _director()
        for minute in range(0, 16, 2):
            t = minute * 60.0
            with self.subTest(minute=minute):
                self.assertGreaterEqual(d.elite_cooldown(t), d.common_cooldown(t))

    def test_the_step_and_the_values_both_compress_with_pace(self):
        """The whole ladder scales together rather than just its numbers --
        the step, the starts, the floors and the hard unlock all divide by
        `timeline_pace`. Derived from Normal rather than listed, so the
        relationship is what is pinned and not the tuning."""
        base = _director()
        for level, pace in (("normal", 1.0), ("fast", 1.25), ("super_fast", 1.5)):
            d = _director(difficulty=level)
            with self.subTest(level=level):
                self.assertAlmostEqual(d.step_seconds, base.step_seconds / pace, places=6)
                self.assertAlmostEqual(d.elite_unlock, base.elite_unlock / pace, places=6)
                for fn in ("common_cooldown", "elite_cooldown"):
                    self.assertAlmostEqual(getattr(d, fn)(0.0),
                                           getattr(base, fn)(0.0) / pace, places=6)
                    self.assertAlmostEqual(getattr(d, fn)(1e5),
                                           getattr(base, fn)(1e5) / pace, places=6)

    def test_every_difficulty_reaches_the_same_elite_count_at_its_boss(self):
        """The step and the boss time scale by the same factor and cancel,
        so harder means the same elites sooner, not more of them."""
        counts = set()
        for level in ("normal", "fast", "super_fast"):
            d = _director(difficulty=level)
            steps = d.steps(d.boss_time())
            counts.add((steps, d.roster.get("goblin").elite_count(steps)))
        self.assertEqual(len(counts), 1, counts)

    def test_the_ladder_never_climbs_backwards(self):
        d = _director()
        for cd in (d.common_cooldown, d.elite_cooldown):
            seen = [cd(t) for t in range(0, 1200, 30)]
            self.assertEqual(seen, sorted(seen, reverse=True))


class ChoiceTests(unittest.TestCase):
    def test_the_first_company_arrives_immediately(self):
        """owner: "the first company gets selected as any other and placed
        immediately" -- no opening pause."""
        d = _director()
        self.assertIsNotNone(d.update(1 / 30, 0.0))

    def test_no_elite_group_before_the_hard_unlock(self):
        d = _director()
        elite = set(d.roster.names(elite=True))
        early = [n for t, n in _run(d, d.elite_unlock - 1.0)]
        self.assertTrue(early, "the director emitted nothing")
        self.assertEqual(set(early) & elite, set())

    def test_an_elite_group_arrives_once_the_gate_opens(self):
        d = _director()
        elite = set(d.roster.names(elite=True))
        names = [n for t, n in _run(d, 240.0) if n in elite]
        self.assertTrue(names, "no elite company in four minutes")

    def test_the_pools_are_separate(self):
        """While the gate is shut the draw is from the common groups only;
        when it is open it is from the elite ones."""
        d = _director()
        d._elite_timer = 0.0
        self.assertEqual(set(d.pool(0.0)), set(d.roster.names(elite=False)),
                         "the hard unlock still applies")
        self.assertEqual(set(d.pool(d.elite_unlock)),
                         set(d.roster.names(elite=True)))

    def test_an_elite_company_resets_the_common_cadence_too(self):
        """So an elite and a common company never land back to back."""
        d = _director()
        d.update(1 / 30, 0.0)                       # consume the opening one
        t = d.elite_unlock + 30.0
        while True:
            name = d.update(1 / 30, t)
            t += 1 / 30
            if name in d.roster.names(elite=True):
                break
            self.assertLess(t, d.elite_unlock + 300.0, "no elite company came")
        self.assertGreater(d._common_timer, 0.0)

    def test_the_elite_gate_reopens_faster_as_the_run_goes_on(self):
        early = [n for t, n in _run(_director(), 300.0)]
        late = _director()
        late._elite_timer = 0.0
        out, t = [], 600.0
        while t < 900.0:
            name = late.update(1 / 30, t)
            if name is not None:
                out.append(name)
            t += 1 / 30
        elite = set(late.roster.names(elite=True))
        early_share = sum(1 for n in early if n in elite) / max(1, len(early))
        late_share = sum(1 for n in out if n in elite) / max(1, len(out))
        self.assertGreater(late_share, early_share)

    def test_a_blocked_master_stops_the_draw_without_losing_the_turn(self):
        """The cadence is left expired rather than consumed, so the moment
        the cap gate opens the next company goes immediately."""
        d = _director()
        for _ in range(200):
            self.assertIsNone(d.update(1 / 30, 5.0, blocked=True))
        self.assertIsNotNone(d.update(0.0, 5.0))

    def test_the_boss_stops_the_tide(self):
        d = _director()
        d.mark_boss_spawned()
        self.assertEqual(_run(d, 120.0), [])

    def test_no_roster_means_no_company_rather_than_a_crash(self):
        d = _director(roster=False)
        self.assertEqual(d.pool(0.0), [])
        self.assertIsNone(d.update(1 / 30, 0.0))

    def test_an_empty_pool_falls_back_to_the_other_one(self):
        """A group whose data did not hold up is simply absent, so a pool
        can empty; the run should not go quiet because of it."""
        d = _director()
        d.roster = resolve_groups(
            {"only_elite": {"commons": {"skull": 1.0}, "common_range": [2, 3],
                            "elites": {"bear": 1.0}, "elite_range": [1, 2],
                            "elite_step": 1}},
            get_content().enemies)
        self.assertEqual(d.pool(0.0), ["only_elite"])       # gate shut, but it is all there is
        self.assertEqual(d.pool(1e5), ["only_elite"])

    def test_the_draw_is_reproducible_from_the_seed(self):
        self.assertEqual(_run(_director(seed=4), 300.0),
                         _run(_director(seed=4), 300.0))


class SurvivingTests(unittest.TestCase):
    """What the company model did not change."""

    def test_difficulty_multipliers_increase_monotonically(self):
        d = _director()
        hp, spd = zip(*(d.stat_multipliers(t) for t in range(0, 600, 30)))
        self.assertEqual(list(hp), sorted(hp))
        self.assertEqual(list(spd), sorted(spd))
        self.assertAlmostEqual(hp[0], 1.0)

    def test_stat_ramp_accelerates_but_still_tops_out_at_run_end(self):
        normal, fast = _director(), _director(difficulty="fast")
        self.assertGreater(fast.stat_multipliers(100.0)[0],
                           normal.stat_multipliers(100.0)[0])
        self.assertAlmostEqual(normal.stat_multipliers(600.0)[0],
                               fast.stat_multipliers(600.0 / 1.25)[0], places=6)

    def test_boss_timing_and_one_shot(self):
        d = _director()
        self.assertFalse(d.should_spawn_boss(d.boss_time() - 1.0))
        self.assertTrue(d.should_spawn_boss(d.boss_time()))
        d.mark_boss_spawned()
        self.assertFalse(d.should_spawn_boss(d.boss_time() + 100.0))

    def test_the_boss_arrives_sooner_on_a_faster_run(self):
        self.assertGreater(_director().boss_time(),
                           _director(difficulty="fast").boss_time())

    def test_enemy_count_cap_grows_on_the_in_game_clock(self):
        d = _director()
        base = d.enemy_count_cap(0.0)
        self.assertEqual(base, config.ENEMY_COUNT_BASE)
        later = d.enemy_count_cap(config.ENEMY_COUNT_STEP_PERIOD * 3)
        self.assertEqual(later, base + config.ENEMY_COUNT_STEP * 3)
        self.assertLessEqual(d.enemy_count_cap(1e6), config.ENEMY_COUNT_HARD_CAP)

    def test_step_scales_with_difficulty_and_clamps_to_the_hard_cap(self):
        normal, fast = _director(), _director(difficulty="fast")
        t = config.ENEMY_COUNT_STEP_PERIOD * 4
        self.assertGreater(fast.enemy_count_cap(t), normal.enemy_count_cap(t))
        self.assertLessEqual(fast.enemy_count_cap(1e6), config.ENEMY_COUNT_HARD_CAP)

    def test_the_live_cap_clamps_the_schedule(self):
        d = _director()
        d.live_cap = 12
        self.assertEqual(d.enemy_count_cap(1e6), 12)

    def test_set_difficulty_rebinds_live(self):
        d = _director()
        before = (d.step_seconds, d.run_duration, d.elite_unlock)
        d.set_difficulty("super_fast")
        self.assertNotEqual((d.step_seconds, d.run_duration, d.elite_unlock), before)
        d.set_difficulty("nonsense")
        self.assertEqual(d.difficulty, config.DIFFICULTY_DEFAULT)

    def test_tables_can_be_handed_in(self):
        data = {"groups": {"only": {"commons": {"turtle": 1.0},
                                    "common_range": [1, 1]}},
                "cooldowns": {"common": 5.0, "common_decay": 1.0,
                              "common_floor": 1.0, "elite": 15.0,
                              "elite_decay": 3.0, "elite_floor": 3.0,
                              "step_seconds": 120.0, "elite_unlock": 60.0,
                              "cap_retry": 2.0}}
        d = SpawnDirector(run_duration=100, rng=random.Random(2),
                          tables=SpawnTables(data))
        d.roster = resolve_groups(data["groups"], get_content().enemies)
        self.assertEqual({n for _t, n in _run(d, 60.0)}, {"only"})


if __name__ == "__main__":
    unittest.main()
