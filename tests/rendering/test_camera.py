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


class CameraZoomTests(unittest.TestCase):
    """C1: `zoom` is a draw-time magnification about `pos`; `zoom = 1.0` is
    byte-identical to the pre-zoom translation."""

    def test_zoom_one_is_a_plain_translation(self):
        cam = Camera(5000, 5000, 800, 600)          # default zoom == 1.0
        self.assertEqual(cam.zoom, 1.0)
        cam.snap_to(pygame.Vector2(1234, 987))
        self.assertEqual(cam.world_span(), (800, 600))
        sx, sy = cam.world_to_screen(pygame.Vector2(1500, 1100))
        self.assertEqual((sx, sy), (1500 - cam.pos.x, 1100 - cam.pos.y))
        self.assertEqual(cam.visible_rect().size, (800, 600))

    def test_zoom_scales_the_screen_delta_about_pos(self):
        cam = Camera(5000, 5000, 800, 600, zoom=2.0)
        cam.snap_to(pygame.Vector2(2500, 2500))     # span is 400x300 now
        self.assertEqual(cam.world_span(), (400, 300))
        # a point one span-half to the right of pos maps to the screen edge
        px = pygame.Vector2(cam.pos.x + 200, cam.pos.y + 150)
        self.assertEqual(cam.world_to_screen(px), (400, 300))

    def test_zoom_shrinks_the_visible_region(self):
        cam = Camera(5000, 5000, 800, 600, zoom=2.0)
        cam.snap_to(pygame.Vector2(2500, 2500))
        self.assertEqual(cam.visible_rect().size, (400, 300))

    def test_clamp_keeps_the_zoomed_view_inside_the_world(self):
        cam = Camera(1000, 1000, 800, 600, zoom=2.0)   # span 400x300
        cam.snap_to(pygame.Vector2(0, 0))
        self.assertEqual((cam.pos.x, cam.pos.y), (0, 0))
        cam.snap_to(pygame.Vector2(99999, 99999))
        self.assertEqual((cam.pos.x, cam.pos.y), (1000 - 400, 1000 - 300))

    def test_small_world_is_centred(self):
        cam = Camera(400, 300, 800, 600)               # world smaller than span
        cam.snap_to(pygame.Vector2(200, 150))
        self.assertEqual((cam.pos.x, cam.pos.y), ((400 - 800) / 2, (300 - 600) / 2))

    def test_screen_to_world_inverts_world_to_screen_under_zoom(self):
        cam = Camera(5000, 5000, 800, 600, zoom=1.5)
        cam.snap_to(pygame.Vector2(1234, 987))
        world = pygame.Vector2(1500, 1100)
        back = cam.screen_to_world(cam.world_to_screen(world))
        self.assertAlmostEqual(back.x, world.x)
        self.assertAlmostEqual(back.y, world.y)


if __name__ == "__main__":
    unittest.main()
