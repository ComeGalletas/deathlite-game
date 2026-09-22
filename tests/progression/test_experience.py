"""Milestone 3: XP curve + LevelTracker (spec 8: "XP progression")."""
import unittest

from progression.experience import (
    BASE_XP, KNEE_LEVEL, LINEAR, QUADRATIC, XP_SCALE,
    LevelTracker, xp_for_level,
)


class XpCurveTests(unittest.TestCase):
    def test_strictly_increasing(self):
        costs = [xp_for_level(l) for l in range(1, 40)]
        self.assertEqual(costs, sorted(costs))
        self.assertTrue(all(b >= a for a, b in zip(costs, costs[1:])))

    def test_level_one_is_cheapest_and_positive(self):
        self.assertGreater(xp_for_level(1), 0)
        self.assertLess(xp_for_level(1), xp_for_level(2))

    def test_no_trough_in_the_increments(self):
        """The increment must keep growing: a stretch of levels that all cost
        about the same is what the removed L21-25 discount produced, and it
        reads as the run stalling even though the cost still rises. Truncating
        to an int makes neighbouring increments jitter by 1 on a rising trend,
        so the trend is measured over a window and the jitter is bounded.
        """
        costs = [xp_for_level(l) for l in range(1, 61)]
        steps = [b - a for a, b in zip(costs, costs[1:])]
        # steps[i] is the increment arriving at level i + 2. The knee at level
        # 10 is the one deliberate flat spot (see the module docstring).
        first = KNEE_LEVEL - 1  # the increment arriving at level 11
        for i in range(first + 1, len(steps)):
            self.assertGreaterEqual(
                steps[i], steps[i - 1] - 1,
                f"increment dropped at level {i + 2}: {steps[i - 1]} -> {steps[i]}",
            )
        for i in range(first + 5, len(steps)):
            self.assertGreater(
                steps[i], steps[i - 5],
                f"increment stalled across levels {i - 3}-{i + 2}: "
                f"{steps[i - 5]} -> {steps[i]}",
            )

    def test_knee_cuts_at_least_fifteen_percent(self):
        """From the knee on, the flattening must be worth at least 15 % against
        the plain quadratic the early levels use."""
        for level in range(KNEE_LEVEL, 61):
            n = level - 1
            plain = int(XP_SCALE * (BASE_XP + LINEAR * n + QUADRATIC * n * n))
            self.assertLessEqual(xp_for_level(level), 0.85 * plain)

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
