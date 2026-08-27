"""Milestone 1: camera clamping and world<->screen transforms."""
import unittest

import pygame

from systems.camera import Camera


class CameraTests(unittest.TestCase):
    def test_snap_centres_on_target_when_room(self):
        cam = Camera(5000, 5000, 800, 600)
        cam.snap_to(pygame.Vector2(2500, 2500))
        self.assertAlmostEqual(cam.pos.x, 2500 - 400)
        self.assertAlmostEqual(cam.pos.y, 2500 - 300)

    def test_never_scrolls_past_world_edges(self):
        cam = Camera(1000, 1000, 800, 600)
        cam.snap_to(pygame.Vector2(0, 0))
        self.assertEqual((cam.pos.x, cam.pos.y), (0, 0))
        cam.snap_to(pygame.Vector2(99999, 99999))
        self.assertEqual((cam.pos.x, cam.pos.y), (1000 - 800, 1000 - 600))

    def test_world_to_screen_is_inverse_of_screen_to_world(self):
        cam = Camera(5000, 5000, 800, 600)
        cam.snap_to(pygame.Vector2(1234, 987))
        world = pygame.Vector2(1500, 1100)
        sx, sy = cam.world_to_screen(world)
        back = cam.screen_to_world((sx, sy))
        self.assertAlmostEqual(back.x, world.x)
        self.assertAlmostEqual(back.y, world.y)

    def test_smoothed_follow_converges(self):
        cam = Camera(5000, 5000, 800, 600)
        cam.snap_to(pygame.Vector2(0, 0))
        target = pygame.Vector2(2000, 2000)
        for _ in range(600):
            cam.update(1 / 60, target)
        self.assertAlmostEqual(cam.pos.x, 2000 - 400, places=1)


if __name__ == "__main__":
    unittest.main()
