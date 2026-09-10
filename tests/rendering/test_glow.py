"""game/states/playing/glow.py -- the XP-orb glow cache and its breathing
curve (group A of the glow plan)."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.states.playing.glow import GlowCache, pulse_alpha, quantise

CFG = {"scale": 2.25, "alpha_min": 40, "alpha_max": 110, "period": 1.1,
       "steps": 8, "colour": (255, 255, 255)}


class PulseTests(unittest.TestCase):
    def test_stays_inside_the_range_and_starts_mid_way(self):
        lo, hi = CFG["alpha_min"], CFG["alpha_max"]
        for age in [i * 0.037 for i in range(200)]:
            a = pulse_alpha(age, CFG)
            self.assertGreaterEqual(a, lo)
            self.assertLessEqual(a, hi)
        self.assertEqual(pulse_alpha(0.0, CFG), round((lo + hi) / 2))

    def test_peaks_at_a_quarter_period_and_bottoms_at_three_quarters(self):
        p = CFG["period"]
        self.assertEqual(pulse_alpha(p / 4, CFG), CFG["alpha_max"])
        self.assertEqual(pulse_alpha(3 * p / 4, CFG), CFG["alpha_min"])
        self.assertEqual(pulse_alpha(p / 4 + p, CFG), CFG["alpha_max"])   # once per period

    def test_two_ages_half_a_period_apart_are_opposite_extremes(self):
        p = CFG["period"]
        self.assertEqual(pulse_alpha(p / 4, CFG) - pulse_alpha(p / 4 + p / 2, CFG),
                         CFG["alpha_max"] - CFG["alpha_min"])

    def test_non_positive_period_holds_the_maximum(self):
        cfg = dict(CFG, period=0.0)
        self.assertEqual(pulse_alpha(3.3, cfg), CFG["alpha_max"])


class QuantiseTests(unittest.TestCase):
    def test_snaps_to_steps_levels_inclusive_of_both_ends(self):
        levels = {quantise(a, CFG) for a in range(0, 256)}
        self.assertEqual(len(levels), CFG["steps"])
        self.assertIn(CFG["alpha_min"], levels)
        self.assertIn(CFG["alpha_max"], levels)
        self.assertTrue(all(CFG["alpha_min"] <= v <= CFG["alpha_max"] for v in levels))

    def test_out_of_range_clamps(self):
        self.assertEqual(quantise(-50, CFG), CFG["alpha_min"])
        self.assertEqual(quantise(999, CFG), CFG["alpha_max"])


class GlowCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((8, 8))

    def setUp(self):
        self.cache = GlowCache(CFG)

    def test_diameter_scales_the_orb_and_zoom(self):
        self.assertEqual(self.cache.diameter(8, 1.0), 18)
        self.assertEqual(self.cache.diameter(12, 1.5), round(12 * 2.25 * 1.5))
        self.assertEqual(GlowCache(dict(CFG, scale=0)).diameter(8, 1.0), 0)

    def test_one_surface_per_key_reused(self):
        a = self.cache.surface(18, 110)
        b = self.cache.surface(18, 110)
        c = self.cache.surface(18, 40)
        self.assertIs(a, b)
        self.assertIsNot(a, c)
        self.assertEqual(len(self.cache), 2)
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)

    def test_disc_has_full_alpha_at_the_centre_and_none_at_the_corner(self):
        s = self.cache.surface(30, 110)
        self.assertEqual(s.get_size(), (30, 30))
        self.assertEqual(s.get_at((15, 15)).a, 110)
        self.assertEqual(s.get_at((0, 0)).a, 0)
        rim = s.get_at((15, 2)).a
        self.assertGreater(rim, 0)
        self.assertLess(rim, 110)                              # soft edge
        self.assertEqual(tuple(s.get_at((15, 15)))[:3], (255, 255, 255))

    def test_pulsed_uses_only_cached_steps(self):
        for age in [i * 0.05 for i in range(60)]:
            self.assertIsNotNone(self.cache.pulsed(8, 1.0, age))
        self.assertLessEqual(len(self.cache), CFG["steps"])   # one size, at most `steps` alphas

    def test_off_and_zero_alpha_give_none(self):
        self.assertIsNone(GlowCache(dict(CFG, scale=0)).pulsed(8, 1.0, 0.3))
        self.assertIsNone(self.cache.surface(18, 0))

    def test_default_config_is_the_game_one(self):
        self.assertIs(GlowCache().cfg, config.XP_GLOW)
        for key in ("scale", "alpha_min", "alpha_max", "period", "steps", "colour"):
            self.assertIn(key, config.XP_GLOW)


if __name__ == "__main__":
    unittest.main()
