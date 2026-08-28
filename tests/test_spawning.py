"""Milestone 2 & 4: spawn geometry + the wave/budget director
(spec 3.4 / 3.8 / 8: "Enemy spawn constraints")."""
import random
import unittest

import pygame

from game import config
from systems.camera import Camera
from world.spawning import _PHASES, SpawnDirector, ring_point_outside_view


class RingPointTests(unittest.TestCase):
    def setUp(self):
        self.cam = Camera(4000, 4000, 1280, 720)
        self.cam.snap_to(pygame.Vector2(2000, 2000))

    def test_point_is_outside_visible_rect(self):
        view = self.cam.visible_rect()
        rng = random.Random(0)
        for _ in range(300):
            p = ring_point_outside_view(self.cam, 4000, 4000, rng=rng)
            self.assertFalse(view.collidepoint(p.x, p.y))

    def test_point_stays_inside_world(self):
        rng = random.Random(1)
        for _ in range(300):
            p = ring_point_outside_view(self.cam, 4000, 4000, rng=rng)
            self.assertTrue(0 <= p.x <= 4000 and 0 <= p.y <= 4000)

    def test_deterministic_with_seed(self):
        a = ring_point_outside_view(self.cam, 4000, 4000, rng=random.Random(7))
        b = ring_point_outside_view(self.cam, 4000, 4000, rng=random.Random(7))
        self.assertEqual((a.x, a.y), (b.x, b.y))


class SpawnDirectorTests(unittest.TestCase):
    def _run(self, director, duration, dt=1 / 30, cap_probe=None):
        spawned, elapsed, active = [], 0.0, 0
        while elapsed < duration:
            ids = director.update(dt, elapsed, active if cap_probe is None else cap_probe)
            spawned.extend(ids)
            active += len(ids)
            elapsed += dt
        return spawned

    def test_only_chasers_in_the_opening_phase(self):
        d = SpawnDirector(run_duration=1000, rng=random.Random(3))
        opening = self._run(d, duration=180)  # first 18% of the run
        self.assertTrue(opening)
        self.assertTrue(all(e == "chaser" for e in opening))

    def test_variety_and_elites_appear_later(self):
        d = SpawnDirector(run_duration=1000, rng=random.Random(4))
        late = self._run(d, duration=800)
        self.assertGreater(len({e for e in late}), 4, "late game should be varied")
        self.assertIn("elite", late)

    def test_respects_phase_soft_cap(self):
        d = SpawnDirector(run_duration=1000, rng=random.Random(5))
        # Pin active count above the opening phase cap (45): nothing should spawn.
        out = self._run(d, duration=120, cap_probe=999)
        self.assertEqual(out, [])

    def test_difficulty_multipliers_increase_monotonically(self):
        d = SpawnDirector(run_duration=1000)
        samples = [d.stat_multipliers(t) for t in range(0, 1001, 100)]
        hp = [s[0] for s in samples]
        spd = [s[1] for s in samples]
        self.assertEqual(hp, sorted(hp))
        self.assertEqual(spd, sorted(spd))
        self.assertGreater(hp[-1], hp[0])

    def test_boss_timing_and_one_shot(self):
        d = SpawnDirector(run_duration=1000)
        self.assertFalse(d.should_spawn_boss(500))
        self.assertTrue(d.should_spawn_boss(d.boss_time() + 1))
        d.mark_boss_spawned()
        self.assertFalse(d.should_spawn_boss(2000))
        # tide stops once the boss is up
        self.assertEqual(d.update(1.0, 2000, 0), [])

    def test_never_exceeds_global_hard_cap(self):
        d = SpawnDirector(run_duration=10, rng=random.Random(1))
        out = d.update(5.0, 9.0, config.ENEMY_COUNT_HARD_CAP)
        self.assertEqual(out, [])


class DifficultyTests(unittest.TestCase):
    """Phase 4 D1 / D2: Normal / Fast / Super Fast resolve to four independent
    factors on the director."""

    def test_normal_is_unchanged_from_the_shipped_numbers(self):
        d = SpawnDirector(run_duration=1000, difficulty="normal")
        self.assertEqual(d.run_duration, 1000)
        self.assertEqual(d.boss_time(), config.BOSS_FRACTION * 1000)
        self.assertAlmostEqual(d._interval(0.0), _PHASES[0]["interval"][0])
        self.assertEqual(d.stat_multipliers(1000), (1.0 + 1.4, 1.0 + 0.30))

    def test_unknown_difficulty_falls_back_to_normal(self):
        d = SpawnDirector(run_duration=600, difficulty="nightmare")
        self.assertEqual(d.difficulty, "normal")
        self.assertEqual(d.run_duration, 600)

    def test_spawn_rate_shortens_the_interval(self):
        base = SpawnDirector(run_duration=1000, difficulty="normal")._interval(0.0)
        fast = SpawnDirector(run_duration=1000, difficulty="fast")._interval(0.0)
        sfast = SpawnDirector(run_duration=1000, difficulty="super_fast")._interval(0.0)
        self.assertAlmostEqual(fast, base / 1.25)
        self.assertAlmostEqual(sfast, base / 1.5)

    def test_timeline_pace_pulls_the_boss_and_phases_in(self):
        base = SpawnDirector(run_duration=1000, difficulty="normal")
        fast = SpawnDirector(run_duration=1000, difficulty="fast")
        sfast = SpawnDirector(run_duration=1000, difficulty="super_fast")
        self.assertAlmostEqual(fast.boss_time(), base.boss_time() / 1.25)
        self.assertAlmostEqual(sfast.boss_time(), base.boss_time() / 1.5)
        # a mid-run instant that is still the chaser-only opening on Normal has
        # already moved on to a varied composition on Super Fast
        self.assertEqual(base._phase(150)["types"], {"chaser": 1.0})
        self.assertGreater(len(sfast._phase(150)["types"]),
                           len(base._phase(150)["types"]))

    def test_stat_ramp_accelerates_but_still_tops_out_at_run_end(self):
        base = SpawnDirector(run_duration=600, difficulty="normal")
        fast = SpawnDirector(run_duration=600, difficulty="fast")
        sfast = SpawnDirector(run_duration=600, difficulty="super_fast")
        # same real elapsed -> harder difficulty ramps enemies higher
        at = 200.0
        self.assertLess(base.stat_multipliers(at)[0], fast.stat_multipliers(at)[0])
        self.assertLess(fast.stat_multipliers(at)[0], sfast.stat_multipliers(at)[0])
        # each difficulty still reaches the full ramp by its own (earlier) end
        for d in (base, fast, sfast):
            hp, spd = d.stat_multipliers(d.run_duration)
            self.assertAlmostEqual(hp, 1.0 + 1.4)
            self.assertAlmostEqual(spd, 1.0 + 0.30)

    def test_enemy_count_cap_grows_on_the_in_game_clock(self):
        d = SpawnDirector(run_duration=600, difficulty="normal")
        self.assertEqual(d.enemy_count_cap(0.0), config.ENEMY_COUNT_BASE)
        self.assertEqual(d.enemy_count_cap(19.9), config.ENEMY_COUNT_BASE)
        self.assertEqual(d.enemy_count_cap(20.0), config.ENEMY_COUNT_BASE + 5)
        self.assertEqual(d.enemy_count_cap(60.0), config.ENEMY_COUNT_BASE + 15)
        # the cap is a pure function of the in-game elapsed it is handed --
        # frame count / real time never enter into it
        for _ in range(50):
            d.update(1 / 30, 5.0, 0)
        self.assertEqual(d.enemy_count_cap(5.0), config.ENEMY_COUNT_BASE)

    def test_step_scales_with_difficulty_and_clamps_to_the_hard_cap(self):
        normal = SpawnDirector(run_duration=600, difficulty="normal")
        fast = SpawnDirector(run_duration=600, difficulty="fast")
        sfast = SpawnDirector(run_duration=600, difficulty="super_fast")
        # ceil(5 * 1.0 / 1.5 / 2.0) -> +5 / +8 / +10 per 20 s
        self.assertEqual(normal.enemy_count_cap(20.0), config.ENEMY_COUNT_BASE + 5)
        self.assertEqual(fast.enemy_count_cap(20.0), config.ENEMY_COUNT_BASE + 8)
        self.assertEqual(sfast.enemy_count_cap(20.0), config.ENEMY_COUNT_BASE + 10)
        self.assertEqual(sfast.enemy_count_cap(10_000.0), config.ENEMY_COUNT_HARD_CAP)

    def test_set_difficulty_rebinds_live(self):
        d = SpawnDirector(run_duration=1000, difficulty="normal")
        base_boss = d.boss_time()
        d.set_difficulty("super_fast")
        self.assertEqual(d.difficulty, "super_fast")
        self.assertAlmostEqual(d.boss_time(), base_boss / 1.5)
        self.assertEqual(d.enemy_count_cap(20.0), config.ENEMY_COUNT_BASE + 10)


if __name__ == "__main__":
    unittest.main()
