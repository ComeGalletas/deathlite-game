"""Spawn geometry for the no-layout world (spec 3.4: never on the player).
Since spawn master S11 the rule is a distance band around the hero and the
camera is not an input. The wave/budget director's tests moved to
`tests/spawn/test_budget.py` with the director (spawn master S2)."""
import random
import unittest

import pygame

from world.spawning import ring_point_around

CENTRE = pygame.Vector2(2000, 2000)


class RingPointTests(unittest.TestCase):
    def test_point_is_inside_the_band(self):
        rng = random.Random(0)
        for _ in range(300):
            p = ring_point_around(CENTRE, 4000, 4000, 700.0, 1100.0, rng=rng)
            d = (p - CENTRE).length()
            self.assertGreaterEqual(d, 700.0 - 1e-6)
            self.assertLessEqual(d, 1100.0 + 1e-6)

    def test_point_stays_inside_world(self):
        rng = random.Random(1)
        edge = pygame.Vector2(50, 50)                     # the band would leave the world
        for _ in range(300):
            p = ring_point_around(edge, 4000, 4000, 700.0, 1100.0, rng=rng)
            self.assertTrue(0 <= p.x <= 4000 and 0 <= p.y <= 4000)

    def test_deterministic_with_seed(self):
        a = ring_point_around(CENTRE, 4000, 4000, 700.0, 1100.0, rng=random.Random(7))
        b = ring_point_around(CENTRE, 4000, 4000, 700.0, 1100.0, rng=random.Random(7))
        self.assertEqual((a.x, a.y), (b.x, b.y))


if __name__ == "__main__":
    unittest.main()
