"""Milestone 6: layered stat modifiers (spec 8: "Stat modifiers")."""
import unittest

from progression.stats import FLAT, MULT, PCT, Modifier, StatSet


class ModifierTests(unittest.TestCase):
    def test_rejects_unknown_op(self):
        with self.assertRaises(ValueError):
            Modifier("x", "bogus", 1.0)


class StatSetTests(unittest.TestCase):
    def test_flat_and_pct_pool_then_mult_compounds(self):
        s = StatSet({"dmg": 100.0})
        s.add(Modifier("dmg", FLAT, 10), Modifier("dmg", FLAT, 5))
        s.add(Modifier("dmg", PCT, 0.20), Modifier("dmg", PCT, 0.10))
        s.add(Modifier("dmg", MULT, 0.5), Modifier("dmg", MULT, 0.5))
        # (100 + 15) * (1 + 0.30) * 1.5 * 1.5
        self.assertAlmostEqual(s.get("dmg"), 115 * 1.30 * 1.5 * 1.5)

    def test_mult_stacks_geometrically(self):
        s = StatSet({"move_speed": 100.0})
        for _ in range(3):
            s.add(Modifier("move_speed", MULT, 0.10, f"u#{_}"))
        self.assertAlmostEqual(s.get("move_speed"), 100 * 1.1 ** 3)

    def test_remove_source_reverts(self):
        s = StatSet({"hp": 100.0})
        s.add(Modifier("hp", FLAT, 50, "item:ring"))
        self.assertEqual(s.get("hp"), 150)
        s.remove_source("item:ring")
        self.assertEqual(s.get("hp"), 100)

    def test_non_negative_stats_floored(self):
        s = StatSet({"armor": 5.0})
        s.add(Modifier("armor", FLAT, -999))
        self.assertEqual(s.get("armor"), 0.0)

    def test_unknown_stat_defaults_zero(self):
        self.assertEqual(StatSet({}).get("nope"), 0.0)

    def test_as_dict_reflects_changes_and_caches(self):
        s = StatSet({"a": 1.0})
        d1 = s.as_dict()
        s.add(Modifier("a", FLAT, 9))
        self.assertEqual(d1["a"], 1.0)          # old snapshot unchanged
        self.assertEqual(s.as_dict()["a"], 10.0)


if __name__ == "__main__":
    unittest.main()
