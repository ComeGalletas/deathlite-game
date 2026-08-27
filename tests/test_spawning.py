"""Milestone 2 & 4: spawn geometry + the wave/budget director
(spec 3.4 / 3.8 / 8: "Enemy spawn constraints")."""
import random
import unittest

import pygame

from game import config
from systems.camera import Camera
from world.spawning import SpawnDirector, ring_point_outside_view


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
        out = d.update(5.0, 9.0, config.MAX_ENEMIES)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
