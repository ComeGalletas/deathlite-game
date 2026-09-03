"""`spawn/pacing.py` and the master's use of it (spawn master S6): the
signals, the smoothing, the dead-band, the bounds, the modifiers, and
that cadence actually follows the product."""
import math
import random
import unittest

import pygame

from game.content import get_content
from spawn import Pacing, SpawnMaster
from spawn.budget import SpawnDirector
from tests.spawn.fakehost import FakeHost


def _pacing() -> Pacing:
    return Pacing(get_content().spawn_tables.pacing)


def _settle(p: Pacing, seconds: float = 120.0, **state) -> float:
    """Hold a condition long enough for the EMA to converge."""
    kw = dict(hp_fraction=1.0, live=0, live_cap=100)
    kw.update(state)
    t = 0.0
    while t < seconds:
        t += 0.1
        p.update(0.1, t, **kw)
    return p.value


class SignalTests(unittest.TestCase):
    def test_at_rest_full_health_reads_one_inside_the_dead_band(self):
        p = _pacing()
        # Full health (+1) and a full lull (+1) against nothing else would
        # lean up; with all signals at their rest values the weighted mean
        # is what it is. Pin only what the design promises: the value is
        # inside the bounds and the target equals 1.0 whenever the mean is
        # inside the dead band.
        v = _settle(p)
        self.assertGreaterEqual(v, p.lo)
        self.assertLessEqual(v, p.hi)
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["crowd"] = 1.0
        p.update(0.1, 200.0, 1.0, live=5, live_cap=100)     # crowd -0.05: in the band
        self.assertEqual(p.target, 1.0)

    def test_low_health_pulls_pressure_down_and_full_health_up(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["hp_fraction"] = 1.0
        self.assertLess(_settle(p, hp_fraction=0.1), 1.0)
        self.assertGreater(_settle(p, hp_fraction=1.0), 1.0)
        self.assertEqual(p.signals["hp_fraction"], 1.0)

    def test_taking_damage_pulls_pressure_down(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["damage_rate"] = 1.0
        t = 0.0
        while t < 60.0:
            t += 0.5
            p.on_damage(t, 0.06)                 # 12 % of max HP per second
            p.update(0.5, t, 1.0, 0, 100)
        self.assertEqual(p.signals["damage_rate"], -1.0)
        self.assertAlmostEqual(p.value, p.lo, places=2)

    def test_clearing_faster_than_the_spawns_pushes_up_and_stalling_down(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["kill_rate"] = 1.0
        t = 0.0
        while t < 60.0:
            t += 0.5
            p.on_spawn(t)
            p.on_kill(t)
            p.on_kill(t)
            p.update(0.5, t, 1.0, 0, 100)
        self.assertEqual(p.signals["kill_rate"], 1.0)
        self.assertAlmostEqual(p.value, p.hi, places=2)
        while t < 120.0:
            t += 0.5
            p.on_spawn(t)                        # spawns, no kills
            p.update(0.5, t, 1.0, 0, 100)
        self.assertEqual(p.signals["kill_rate"], -1.0)
        self.assertAlmostEqual(p.value, p.lo, places=2)

    def test_a_full_crowd_holds_pressure_down(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["crowd"] = 1.0
        self.assertAlmostEqual(_settle(p, live=100, live_cap=100), p.lo, places=2)
        self.assertEqual(p.signals["crowd"], -1.0)

    def test_a_lull_raises_pressure_slowly(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["lull"] = 1.0
        p.on_damage(0.0, 0.01)
        p.update(0.1, 0.1, 1.0, 0, 100)
        self.assertAlmostEqual(p.signals["lull"], 0.0, delta=0.01)
        p.update(0.1, p.lull_seconds / 2, 1.0, 0, 100)
        self.assertAlmostEqual(p.signals["lull"], 0.5, places=2)
        p.update(0.1, p.lull_seconds * 2, 1.0, 0, 100)
        self.assertEqual(p.signals["lull"], 1.0)


class ShapeTests(unittest.TestCase):
    def test_the_bounds_hold_under_extreme_weights(self):
        p = _pacing()
        p.weights = {k: 1000.0 for k in p.weights}
        self.assertGreaterEqual(_settle(p, hp_fraction=0.0, live=100, live_cap=100), p.lo)
        p = _pacing()
        p.weights = {k: 1000.0 for k in p.weights}
        self.assertLessEqual(_settle(p, hp_fraction=1.0), p.hi)

    def test_the_ema_moves_a_third_of_the_way_per_tau(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        p.weights["hp_fraction"] = 1.0
        p.update(0.0, 0.0, 1.0, 0, 100)              # dt 0: value snaps to the target
        self.assertAlmostEqual(p.value, p.hi)
        target_lo = p.lo
        p.update(p.tau, p.tau, 0.0, 0, 100)          # one tau at empty health
        expected = p.hi + (target_lo - p.hi) * (1.0 - math.exp(-1.0))
        self.assertAlmostEqual(p.value, expected, places=6)

    def test_no_weights_means_no_opinion(self):
        p = _pacing()
        p.weights = {k: 0.0 for k in p.weights}
        self.assertEqual(_settle(p, hp_fraction=0.0), 1.0)

    def test_the_rate_window_forgets(self):
        p = _pacing()
        p.on_kill(0.0)
        p.on_spawn(0.0)
        p.update(0.1, p.window + 1.0, 1.0, 0, 100)
        self.assertEqual((len(p._kills), len(p._spawns)), (0, 0))
        self.assertEqual(p.signals["kill_rate"], 0.0)


class MasterTests(unittest.TestCase):
    def _master(self, host, seed=3):
        return SpawnMaster(host, SpawnDirector(run_duration=600.0, rng=random.Random(seed)))

    def test_pressure_is_pacing_times_modifiers(self):
        host = FakeHost()
        m = self._master(host)
        m.set_modifier("dev_menu", 2.0)
        self.assertAlmostEqual(m.pressure, m.pacing.value * 2.0)
        m.clear_modifier("dev_menu")
        self.assertAlmostEqual(m.pressure, m.pacing.value)

    def test_the_run_signals_reach_the_pacing_through_the_bus(self):
        host = FakeHost()
        m = self._master(host)
        host.elapsed = 5.0
        host.publish("player_damaged", amount=25.0)
        host.publish("enemy_killed", pos=pygame.Vector2(), color=(1, 1, 1), xp=1,
                     tags=(), elite=False)
        self.assertEqual(list(m.pacing._damage), [(5.0, 0.25)])
        self.assertEqual(list(m.pacing._kills), [5.0])
        m.spawn_at("chaser", pygame.Vector2(50, 50))
        self.assertEqual(list(m.pacing._spawns), [5.0])

    def test_cadence_follows_the_condition(self):
        """A hurt, swamped player sees fewer spawns than a healthy one
        clearing fast, everything else equal."""
        def run(hp, kills_per_spawn):
            host = FakeHost(seed=7)
            host.hp_fraction = hp
            m = self._master(host, seed=9)
            m.use_locality = False
            t = 0.0
            while t < 90.0:
                t += 1 / 30
                host.elapsed = t
                before = m.spawned
                m.update(1 / 30)
                for _ in range((m.spawned - before) * kills_per_spawn):
                    host.publish("enemy_killed", pos=pygame.Vector2(), color=(0, 0, 0),
                                 xp=1, tags=(), elite=False)
                host.live = host.live[-10:]            # keep the crowd small
            return m.spawned, m.pacing.value
        hurt_n, hurt_v = run(0.1, 0)
        strong_n, strong_v = run(1.0, 2)
        self.assertLess(hurt_v, strong_v)
        self.assertLess(hurt_n, strong_n)


if __name__ == "__main__":
    unittest.main()
