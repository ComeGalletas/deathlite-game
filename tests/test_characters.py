"""Milestone 6: 3 characters with distinct identities (spec 4.1)."""
import unittest

from entities.player import Player
from game.content import get_content


class CharacterDataTests(unittest.TestCase):
    def test_three_characters_each_distinct(self):
        chars = get_content().characters
        self.assertEqual(len(chars), 3)
        weapons = set()
        traits = set()
        for c in chars.values():
            self.assertIn("base_stats", c)
            self.assertTrue(c.get("trait"))
            self.assertTrue(c.get("starting_weapon"))
            weapons.add(c["starting_weapon"])
            traits.add(c["trait"])
        self.assertEqual(len(weapons), 3, "each hero starts with a different weapon")
        self.assertEqual(len(traits), 3, "each hero has a different trait")


class CharacterBuildTests(unittest.TestCase):
    def _player(self, cid):
        c = get_content().character(cid)
        return Player(0, 0, base_stats=c["base_stats"], trait=c["trait"],
                     character_id=cid)

    def test_base_stats_override_defaults(self):
        aegis = self._player("aegis")
        kestrel = self._player("kestrel")
        self.assertEqual(aegis.stats["max_hp"], 160)
        self.assertGreater(kestrel.move_speed, aegis.move_speed)
        self.assertLess(kestrel.stats["max_hp"], aegis.stats["max_hp"])

    def test_bulwark_reduces_damage_only_after_standing_still(self):
        p = self._player("aegis")
        p.still_time = 0.0
        self.assertEqual(p.incoming_damage_multiplier(), 1.0)
        p.still_time = 0.5
        self.assertAlmostEqual(p.incoming_damage_multiplier(), 0.7)

    def test_windborne_momentum_builds_moving_and_bleeds_still(self):
        world = _FreeWorld()
        p = self._player("kestrel")
        p._move_dir.update(1, 0)
        for _ in range(120):
            p.update(1 / 60, world)
        self.assertGreater(p.momentum, 4.0)
        self.assertGreater(p.outgoing_damage_multiplier(), 1.2)
        # now stand still
        p._move_dir.update(0, 0)
        for _ in range(120):
            p.update(1 / 60, world)
        self.assertEqual(p.momentum, 0.0)
        self.assertEqual(p.outgoing_damage_multiplier(), 1.0)

    def test_other_traits_have_no_passive_multiplier(self):
        nihil = self._player("nihil")
        self.assertEqual(nihil.incoming_damage_multiplier(), 1.0)
        self.assertEqual(nihil.outgoing_damage_multiplier(), 1.0)


import pygame


class _FreeWorld:
    """No walls -- movement is unconstrained (for trait tests)."""
    def resolve_movement(self, prev, new, radius):
        return new


if __name__ == "__main__":
    unittest.main()
