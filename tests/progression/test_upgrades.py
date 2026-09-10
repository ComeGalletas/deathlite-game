"""The level-up card facade (`progression.upgrades`) over the P2 offering.

Invariants:
  * exactly N distinct choices when the pool is large enough
  * never a weapon blessing for an unowned weapon
  * never a grant for a weapon already owned, nor once the slots are full
  * maxed-out blessings stop appearing
  * deterministic for a given seed
"""
import random
import unittest

from combat.weapons import Weapon
from entities.player import Player
from game.content import get_content
from progression.upgrades import (MAX_SUMMONS, MAX_WEAPONS, apply_choice,
                                  roll_choices, valid_choices)


def fresh_player(*wids):
    p = Player(0, 0)
    p.weapons = [Weapon(w, get_content().weapon(w)) for w in (wids or ("sword",))]
    return p


class RollTests(unittest.TestCase):
    def setUp(self):
        self.content = get_content()

    def test_returns_three_distinct(self):
        choices = roll_choices(fresh_player(), self.content, random.Random(1), n=3)
        self.assertEqual(len(choices), 3)
        self.assertEqual(len({c.id for c in choices}), 3)

    def test_no_blessing_for_unowned_weapon(self):
        ids = {u.id for u in valid_choices(fresh_player(), self.content)}
        self.assertFalse(any(i.startswith("bow_") for i in ids))
        self.assertFalse(any(i.startswith("magic_rod_") for i in ids))
        self.assertTrue(any(i.startswith("sword_") for i in ids))

    def test_owned_weapon_not_offered_as_a_grant(self):
        ids = {u.id for u in valid_choices(fresh_player(), self.content)}
        self.assertNotIn("grant:sword", ids)
        self.assertIn("grant:bow", ids)

    def test_a_grant_adds_the_weapon_and_opens_its_blessings(self):
        p = fresh_player()
        new = next(u for u in valid_choices(p, self.content) if u.id == "grant:magic_rod")
        apply_choice(p, new)
        self.assertIn("magic_rod", {w.weapon_id for w in p.weapons})
        ids = {u.id for u in valid_choices(p, self.content)}
        self.assertIn("magic_rod_arcane_missiles", ids)
        self.assertNotIn("grant:magic_rod", ids)

    def test_max_level_enforced(self):
        p = fresh_player()
        for _ in range(5):
            move = next(u for u in valid_choices(p, self.content) if u.id == "fleet_foot")
            apply_choice(p, move)
        self.assertNotIn("fleet_foot", {u.id for u in valid_choices(p, self.content)})
        self.assertEqual(p.upgrade_stacks["fleet_foot"], 5)

    def test_apply_changes_stat(self):
        p = fresh_player()
        before = p.stats["move_speed"]
        move = next(u for u in valid_choices(p, self.content) if u.id == "fleet_foot")
        apply_choice(p, move)
        self.assertGreater(p.stats["move_speed"], before)

    def test_deterministic_for_seed(self):
        a = [u.id for u in roll_choices(fresh_player(), self.content, random.Random(9))]
        b = [u.id for u in roll_choices(fresh_player(), self.content, random.Random(9))]
        self.assertEqual(a, b)


class SlotTests(unittest.TestCase):
    """Design §20 / §3.7: three weapons (melee + ranged) and one summon."""

    def _grants(self, p):
        return {u.id for u in valid_choices(p, get_content()) if u.id.startswith("grant:")}

    def test_limits(self):
        self.assertEqual((MAX_WEAPONS, MAX_SUMMONS), (3, 1))

    def test_three_weapons_stop_weapon_grants_but_not_the_summon(self):
        offers = self._grants(fresh_player("sword", "bow", "bomb"))
        self.assertFalse({"grant:hammer", "grant:daggers", "grant:magic_rod"} & offers)
        self.assertEqual({"grant:ember_ring", "grant:grave_totem", "grant:spirit_wolf"}, offers)

    def test_a_summon_does_not_use_a_weapon_slot(self):
        offers = self._grants(fresh_player("sword", "bow", "spirit_wolf"))
        self.assertIn("grant:hammer", offers)
        self.assertNotIn("grant:grave_totem", offers)
        self.assertNotIn("grant:ember_ring", offers)

    def test_full_run_offers_no_grants(self):
        self.assertEqual(self._grants(fresh_player("sword", "bow", "bomb", "ember_ring")), set())


if __name__ == "__main__":
    unittest.main()
