"""Milestone 7: meta-progression purchase rules and run-start application
(spec 4.6)."""
import unittest

from game.content import get_content
from game.save import SaveData
from progression.meta import MetaCatalog, buy
from progression.stats import StatSet


def catalog():
    return MetaCatalog(get_content().meta_upgrades)


class MetaTests(unittest.TestCase):
    def test_cost_rises_with_level(self):
        c = catalog()
        uid = next(iter(c.defs))
        self.assertLess(c.cost(uid, 0), c.cost(uid, 1))

    def test_cannot_buy_without_currency(self):
        c = catalog()
        save = SaveData(currency=0)
        uid = next(iter(c.defs))
        self.assertFalse(buy(c, save, uid))
        self.assertEqual(save.meta.get(uid, 0), 0)

    def test_buy_spends_and_levels(self):
        c = catalog()
        uid = "constitution"
        save = SaveData(currency=10_000)
        cost0 = c.cost(uid, 0)
        self.assertTrue(buy(c, save, uid))
        self.assertEqual(save.meta[uid], 1)
        self.assertEqual(save.currency, 10_000 - cost0)

    def test_cannot_exceed_max_level(self):
        c = catalog()
        uid = "fortune"
        save = SaveData(currency=10_000_000)
        for _ in range(c.max_level(uid)):
            self.assertTrue(buy(c, save, uid))
        self.assertFalse(buy(c, save, uid))
        self.assertEqual(save.meta[uid], c.max_level(uid))

    def test_modifiers_scale_with_level_and_skip_meta_only(self):
        c = catalog()
        levels = {"constitution": 3, "salvager": 4}
        mods = c.player_modifiers(levels)
        stats = {m.stat for m in mods}
        self.assertIn("max_hp", stats)
        self.assertNotIn("__salvage_gain", stats)  # meta-only knob excluded

        s = StatSet({"max_hp": 100.0})
        s.add(*[m for m in mods if m.stat == "max_hp"])
        self.assertAlmostEqual(s.get("max_hp"), 100.0 * (1 + 0.02 * 3))

    def test_salvage_multiplier(self):
        c = catalog()
        self.assertEqual(c.salvage_multiplier({}), 1.0)
        self.assertGreater(c.salvage_multiplier({"salvager": 5}), 1.0)


if __name__ == "__main__":
    unittest.main()
