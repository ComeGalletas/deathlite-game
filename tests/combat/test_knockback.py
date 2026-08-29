"""CB-3: `combat.knockback.knock_split` -- the shared weight-driven impulse
split used by both unit bumps and weapon hits.
"""
import math
import unittest

from game import config
from combat.knockback import knock_split


class KnockSplitTests(unittest.TestCase):
    def test_equal_weights_split_symmetrically(self):
        ps, pt = knock_split(10.0, 10.0, 100.0, diff_gain=2.0)
        self.assertEqual(ps, pt)                       # no gap -> no amplification
        self.assertAlmostEqual(ps + pt, 100.0)

    def test_push_shares_sum_to_the_amplified_total(self):
        w_src, w_tgt, base, k = 8.0, 20.0, 55.0, 2.0
        total = base * (1.0 + k * abs(w_src - w_tgt) / (w_src + w_tgt))
        ps, pt = knock_split(w_src, w_tgt, base, diff_gain=k)
        self.assertAlmostEqual(ps + pt, total)

    def test_a_bigger_weight_gap_means_a_bigger_total(self):
        even = sum(knock_split(10.0, 10.0, 100.0, diff_gain=2.0))
        lop = sum(knock_split(10.0, 60.0, 100.0, diff_gain=2.0))
        self.assertGreater(lop, even)

    def test_featherweight_recoils_more_than_it_shoves(self):
        ps, pt = knock_split(5.0, 50.0, 100.0, diff_gain=2.0)   # tiny hits huge
        self.assertGreater(ps, pt)

    def test_heavy_source_shoves_more_than_it_recoils(self):
        ps, pt = knock_split(50.0, 5.0, 100.0, diff_gain=2.0)   # huge hits tiny
        self.assertGreater(pt, ps)

    def test_zero_source_weight_is_no_knockback(self):
        self.assertEqual(knock_split(0.0, 20.0, 100.0), (0.0, 0.0))

    def test_negative_weight_is_treated_as_no_knockback(self):
        self.assertEqual(knock_split(-5.0, 20.0, 100.0), (0.0, 0.0))

    def test_zero_or_negative_base_is_no_knockback(self):
        self.assertEqual(knock_split(20.0, 20.0, 0.0), (0.0, 0.0))
        self.assertEqual(knock_split(20.0, 20.0, -3.0), (0.0, 0.0))

    def test_infinite_target_takes_nothing_source_takes_the_lot(self):
        ps, pt = knock_split(10.0, math.inf, 100.0, diff_gain=2.0)
        self.assertEqual(pt, 0.0)
        self.assertAlmostEqual(ps, 100.0 * (1.0 + 2.0))         # infinite gap -> ratio 1

    def test_infinite_source_shoves_the_target_with_everything(self):
        ps, pt = knock_split(math.inf, 10.0, 100.0, diff_gain=2.0)
        self.assertEqual(ps, 0.0)
        self.assertAlmostEqual(pt, 100.0 * (1.0 + 2.0))

    def test_two_immovable_bodies_do_nothing(self):
        self.assertEqual(knock_split(math.inf, math.inf, 100.0), (0.0, 0.0))

    def test_diff_gain_defaults_to_the_config_knob(self):
        ps, _ = knock_split(10.0, math.inf, 10.0)               # no diff_gain arg
        self.assertAlmostEqual(ps, 10.0 * (1.0 + config.BUMP_DIFF_GAIN))

    def test_no_nan_or_inf_leaks_from_the_edge_cases(self):
        for args in ((10.0, math.inf, 50.0), (math.inf, 10.0, 50.0),
                     (math.inf, math.inf, 50.0), (0.0, 10.0, 50.0)):
            for v in knock_split(*args):
                self.assertTrue(math.isfinite(v), args)


if __name__ == "__main__":
    unittest.main()
