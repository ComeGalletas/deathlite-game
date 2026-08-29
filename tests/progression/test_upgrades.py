"""Milestone 3: level-up selection pool (spec 3.5 / 8).

Invariants:
  * exactly N distinct choices when the pool is large enough
  * never a weapon-specific option for an unowned weapon
  * never "new weapon X" for a weapon already owned
  * maxed-out upgrades stop appearing
  * deterministic for a given seed
"""
import random
import unittest

from entities.player import Player
from combat.weapons import Weapon
from game.content import get_content
from progression.upgrades import roll_choices, valid_choices, apply_choice


def fresh_player():
    p = Player(0, 0)
    p.weapons = [Weapon("arcane_bolt", get_content().weapon("arcane_bolt"))]
    return p


class RollTests(unittest.TestCase):
    def setUp(self):
        self.content = get_content()

    def test_returns_three_distinct(self):
        p = fresh_player()
        choices = roll_choices(p, self.content, random.Random(1), n=3)
        self.assertEqual(len(choices), 3)
        self.assertEqual(len({c.id for c in choices}), 3)

    def test_no_upgrade_for_unowned_weapon(self):
        p = fresh_player()  # owns only arcane_bolt
        ids = {u.id for u in valid_choices(p, self.content)}
        self.assertFalse(any(i.startswith("frost_shards:") for i in ids))
        self.assertFalse(any(i.startswith("thunder_orb:") for i in ids))

    def test_owned_weapon_not_offered_as_new(self):
        p = fresh_player()
        ids = {u.id for u in valid_choices(p, self.content)}
        self.assertNotIn("new:arcane_bolt", ids)
        self.assertIn("new:frost_shards", ids)

    def test_new_weapon_upgrade_actually_adds_weapon(self):
        p = fresh_player()
        new = next(u for u in valid_choices(p, self.content)
                   if u.id == "new:thunder_orb")
        apply_choice(p, new)
        self.assertIn("thunder_orb", {w.weapon_id for w in p.weapons})
        # ...and now bolt-style upgrades for it become available
        ids = {u.id for u in valid_choices(p, self.content)}
        self.assertIn("thunder_orb:damage", ids)
        self.assertNotIn("new:thunder_orb", ids)

    def test_max_stacks_enforced(self):
        p = fresh_player()
        move = next(u for u in valid_choices(p, self.content) if u.id == "move_speed")
        for _ in range(move.max_stacks):
            apply_choice(p, move)
        ids = {u.id for u in valid_choices(p, self.content)}
        self.assertNotIn("move_speed", ids)

    def test_apply_changes_stat(self):
        p = fresh_player()
        before = p.stats["move_speed"]
        move = next(u for u in valid_choices(p, self.content) if u.id == "move_speed")
        apply_choice(p, move)
        self.assertAlmostEqual(p.stats["move_speed"], before * 1.10)

    def test_deterministic_with_seed(self):
        a = roll_choices(fresh_player(), self.content, random.Random(99), n=3)
        b = roll_choices(fresh_player(), self.content, random.Random(99), n=3)
        self.assertEqual([u.id for u in a], [u.id for u in b])

    def test_degrades_when_pool_smaller_than_n(self):
        p = fresh_player()
        # Exhaust everything, then ask for 3.
        while valid_choices(p, self.content):
            apply_choice(p, valid_choices(p, self.content)[0])
        self.assertEqual(roll_choices(p, self.content, random.Random(0), n=3), [])


if __name__ == "__main__":
    unittest.main()
