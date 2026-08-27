"""Milestone 6: blessing loading, stacking and tag synergy
(spec 4.2 / 4.3 / 8: "Blessing stacking")."""
import random
import unittest

from combat.status import StatusState
from entities.player import Player
from game.content import get_content
from progression.blessings import (BlessingLibrary, apply_blessing, rebuild,
                                   roll_blessing_choices)


def fresh():
    lib = BlessingLibrary(get_content().blessings)
    p = Player(0, 0)
    p._blessing_library = lib
    rebuild(p, lib)
    return p, lib


class LibraryTests(unittest.TestCase):
    def test_loads_all_sources(self):
        lib = BlessingLibrary(get_content().blessings)
        self.assertGreaterEqual(len(lib.by_id), 32)
        self.assertEqual(set(lib.sources), {"ember", "tide", "storm", "grave"})
        for src in lib.sources:
            count = sum(1 for b in lib.by_id.values() if b.source == src)
            self.assertGreaterEqual(count, 8)  # spec: 8-12 per source


class StackingTests(unittest.TestCase):
    def test_stat_blessing_applies_and_stacks(self):
        p, lib = fresh()
        base = p.stats["max_hp"]
        b = lib.get("tide_bulwark")  # +18% max HP, pct, stacks 4
        apply_blessing(p, b)
        self.assertAlmostEqual(p.stats["max_hp"], base * 1.18)
        apply_blessing(p, b)
        self.assertAlmostEqual(p.stats["max_hp"], base * 1.36)

    def test_tag_damage_scales_with_stacks(self):
        p, lib = fresh()
        b = lib.get("ember_kindling")  # +18% fire, x5
        apply_blessing(p, b)
        apply_blessing(p, b)
        self.assertAlmostEqual(p.blessing_fx.tag_bonus(("fire",), False), 0.36)
        # unrelated tag unaffected
        self.assertEqual(p.blessing_fx.tag_bonus(("frost",), False), 0.0)

    def test_elite_bonus_only_vs_elites(self):
        p, lib = fresh()
        apply_blessing(p, lib.get("grave_grim_toll"))  # +25% vs elites
        self.assertEqual(p.blessing_fx.tag_bonus(("projectile",), False), 0.0)
        self.assertAlmostEqual(p.blessing_fx.tag_bonus(("projectile",), True), 0.25)

    def test_status_vuln_respects_attack_tag_and_status(self):
        p, lib = fresh()
        apply_blessing(p, lib.get("ember_conflagration"))  # area vs burning +25%
        st = StatusState()
        st.apply("burn", 3.0, 2.0)
        # area attack on a burning enemy -> bonus
        self.assertAlmostEqual(p.blessing_fx.vuln_bonus(("area",), st), 0.25)
        # non-area attack -> no bonus
        self.assertEqual(p.blessing_fx.vuln_bonus(("projectile",), st), 0.0)
        # burning gone -> no bonus
        self.assertEqual(p.blessing_fx.vuln_bonus(("area",), StatusState()), 0.0)

    def test_on_hit_chance_scales_and_caps_at_one(self):
        p, lib = fresh()
        b = lib.get("ember_ignite")  # 30% burn on fire, x3
        for _ in range(5):
            apply_blessing(p, b)
        chances = [c for (_s, _t, c, _d, _p) in p.blessing_fx.on_hit]
        self.assertTrue(all(c <= 1.0 for c in chances))
        self.assertEqual(max(chances), 1.0)

    def test_status_tune_and_soul_heal_aggregate(self):
        p, lib = fresh()
        apply_blessing(p, lib.get("ember_pyre"))       # burn potency +50%
        apply_blessing(p, lib.get("grave_lingering"))  # all status duration +40%
        apply_blessing(p, lib.get("grave_soulharvest"))
        self.assertAlmostEqual(p.blessing_fx.tuned("burn", "potency"), 0.50)
        self.assertAlmostEqual(p.blessing_fx.tuned("burn", "duration"), 0.40)
        self.assertGreaterEqual(p.blessing_fx.soul_heal, 1)


class RollTests(unittest.TestCase):
    def test_offers_only_below_max_stacks(self):
        p, lib = fresh()
        b = lib.get("ember_wildfire")  # max_stacks 1
        apply_blessing(p, b)
        for _ in range(20):
            ids = {c.id for c in roll_blessing_choices(p, lib, random.Random(_), 3)}
            self.assertNotIn("bless:ember_wildfire", ids)

    def test_returns_at_most_n_upgrade_shaped(self):
        p, lib = fresh()
        choices = roll_blessing_choices(p, lib, random.Random(1), n=3)
        self.assertLessEqual(len(choices), 3)
        for c in choices:
            self.assertTrue(c.id.startswith("bless:"))
            self.assertTrue(callable(c.apply))


if __name__ == "__main__":
    unittest.main()
