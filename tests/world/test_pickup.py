"""Milestone 3: XP gem homing + collection behaviour."""
import unittest

import pygame

from entities.player import Player
from entities.pickup import XPGem, xp_tier


class GemTests(unittest.TestCase):
    def test_tier_thresholds(self):
        self.assertEqual(xp_tier(3), 0)
        self.assertEqual(xp_tier(6), 1)
        self.assertEqual(xp_tier(15), 2)

    def test_idle_until_inside_pickup_radius(self):
        p = Player(0, 0)
        p.stats["pickup_radius"] = 80
        gem = XPGem()
        gem.reset(pygame.Vector2(400, 0), 5)
        gem.update(1 / 60, p)
        self.assertFalse(gem.homing)
        self.assertEqual(gem.pos.x, 400)

    def test_homes_in_once_in_range(self):
        p = Player(0, 0)
        p.stats["pickup_radius"] = 120
        gem = XPGem()
        gem.reset(pygame.Vector2(100, 0), 5)
        gem.update(1 / 60, p)
        self.assertTrue(gem.homing)
        # moves toward the player (x decreases from 100)
        gem.update(1 / 60, p)
        self.assertLess(gem.pos.x, 100)

    def test_collected_when_touching_player(self):
        p = Player(0, 0)
        gem = XPGem()
        gem.reset(pygame.Vector2(5, 0), 7)
        collected = gem.update(1 / 60, p)
        self.assertTrue(collected)
        self.assertFalse(gem.active)

    def test_reaches_player_within_a_second(self):
        p = Player(0, 0)
        p.stats["pickup_radius"] = 90
        gem = XPGem()
        gem.reset(pygame.Vector2(85, 0), 5)
        got = False
        for _ in range(120):
            if gem.update(1 / 60, p):
                got = True
                break
        self.assertTrue(got)


if __name__ == "__main__":
    unittest.main()
