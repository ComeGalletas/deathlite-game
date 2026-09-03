"""Spawn geometry for the no-layout world (spec 3.4: spawn off-screen,
never on the player). The wave/budget director's tests moved to
`tests/spawn/test_budget.py` with the director (spawn master S2)."""
import random
import unittest

import pygame

from systems.camera import Camera
from world.spawning import ring_point_outside_view


class RingPointTests(unittest.TestCase):
    def setUp(self):
        self.cam = Camera(4000, 4000, 1280, 720)
        self.cam.snap_to(pygame.Vector2(2000, 2000))

    def test_point_is_outside_visible_rect(self):
        view = self.cam.visible_rect()
        rng = random.Random(0)
        for _ in range(300):
            p = ring_point_outside_view(self.cam, 4000, 4000, rng=rng)
            self.assertFalse(view.collidepoint(p.x, p.y))

    def test_point_stays_inside_world(self):
        rng = random.Random(1)
        for _ in range(300):
            p = ring_point_outside_view(self.cam, 4000, 4000, rng=rng)
            self.assertTrue(0 <= p.x <= 4000 and 0 <= p.y <= 4000)

    def test_deterministic_with_seed(self):
        a = ring_point_outside_view(self.cam, 4000, 4000, rng=random.Random(7))
        b = ring_point_outside_view(self.cam, 4000, 4000, rng=random.Random(7))
        self.assertEqual((a.x, a.y), (b.x, b.y))


if __name__ == "__main__":
    unittest.main()
