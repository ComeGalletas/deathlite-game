"""Milestone 3: XP curve + LevelTracker (spec 8: "XP progression")."""
import unittest

from progression.experience import LevelTracker, xp_for_level


class XpCurveTests(unittest.TestCase):
    def test_strictly_increasing(self):
        costs = [xp_for_level(l) for l in range(1, 40)]
        self.assertEqual(costs, sorted(costs))
        self.assertTrue(all(b >= a for a, b in zip(costs, costs[1:])))

    def test_level_one_is_cheapest_and_positive(self):
        self.assertGreater(xp_for_level(1), 0)
        self.assertLess(xp_for_level(1), xp_for_level(2))

    def test_rejects_zero_level(self):
        with self.assertRaises(ValueError):
            xp_for_level(0)


class LevelTrackerTests(unittest.TestCase):
    def test_single_level_up(self):
        t = LevelTracker()
        gained = t.add_xp(xp_for_level(1))
        self.assertEqual(gained, 1)
        self.assertEqual(t.level, 2)
        self.assertEqual(t.pending_level_ups, 1)

    def test_large_xp_dump_rolls_multiple_levels(self):
        t = LevelTracker()
        big = sum(xp_for_level(l) for l in range(1, 6))  # exactly 5 levels
        gained = t.add_xp(big)
        self.assertEqual(gained, 5)
        self.assertEqual(t.level, 6)
        self.assertEqual(t.xp_into_level, 0)

    def test_partial_progress_tracked(self):
        t = LevelTracker()
        need = xp_for_level(1)
        t.add_xp(need - 1)
        self.assertEqual(t.level, 1)
        self.assertAlmostEqual(t.progress_fraction, (need - 1) / need)

    def test_consume_pending(self):
        t = LevelTracker()
        t.add_xp(sum(xp_for_level(l) for l in range(1, 4)))
        self.assertEqual(t.pending_level_ups, 3)
        self.assertTrue(t.consume_pending())
        self.assertEqual(t.pending_level_ups, 2)
        t.consume_pending(); t.consume_pending()
        self.assertFalse(t.consume_pending())

    def test_negative_xp_rejected(self):
        with self.assertRaises(ValueError):
            LevelTracker().add_xp(-1)


if __name__ == "__main__":
    unittest.main()
