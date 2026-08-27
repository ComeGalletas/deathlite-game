"""Milestone 2: pure damage math."""
import random
import unittest

from combat.damage import apply_armor, outgoing_damage


class OutgoingDamageTests(unittest.TestCase):
    def test_base_times_multiplier(self):
        self.assertEqual(outgoing_damage(10, 1.5).amount, 15.0)

    def test_never_negative(self):
        self.assertEqual(outgoing_damage(-5, 2).amount, 0.0)
        self.assertEqual(outgoing_damage(10, -2).amount, 0.0)

    def test_crit_is_deterministic_with_seeded_rng(self):
        # Same seed -> same crit outcomes.
        a = [outgoing_damage(10, 1, crit_chance=0.5, rng=random.Random(1)).is_crit
             for _ in range(1)]
        b = [outgoing_damage(10, 1, crit_chance=0.5, rng=random.Random(1)).is_crit
             for _ in range(1)]
        self.assertEqual(a, b)

    def test_crit_applies_multiplier(self):
        # crit_chance 1.0 always crits.
        r = outgoing_damage(10, 1, crit_chance=1.0, crit_multiplier=3.0)
        self.assertTrue(r.is_crit)
        self.assertEqual(r.amount, 30.0)

    def test_crit_rate_roughly_matches_chance(self):
        rng = random.Random(42)
        crits = sum(outgoing_damage(1, 1, crit_chance=0.25, rng=rng).is_crit
                    for _ in range(4000))
        self.assertAlmostEqual(crits / 4000, 0.25, delta=0.03)


class ArmorTests(unittest.TestCase):
    def test_flat_subtraction(self):
        self.assertEqual(apply_armor(10, 3), 7)

    def test_floored_at_zero(self):
        self.assertEqual(apply_armor(2, 10), 0)

    def test_negative_armor_ignored(self):
        self.assertEqual(apply_armor(10, -5), 10)


if __name__ == "__main__":
    unittest.main()
