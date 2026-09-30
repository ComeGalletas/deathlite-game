"""Camera clamping and world<->screen transforms."""
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


class ZoomGranularityTests(unittest.TestCase):
    """A tile must land on a whole number of screen pixels at every zoom the
    game actually ships.

    Terrain is composited from several independently scaled surfaces (per room,
    per corridor, per cliff band), each blitted at a truncated screen position.
    When `TILE_PX * zoom` is fractional, two adjacent surfaces round to
    positions that do not quite meet and the sea painted underneath shows
    through the 1 px crack as blue seams along the tile frontiers. The web
    profile shipped at 1.2 (76.8 px per tile) and had them; 1.25 (80 px) does
    not.

    The zoom drawn at is `config.effective_zoom()`, `CAMERA_ZOOM` times the
    interface scale: the web profile draws its interface at 0.8 and
    compensates its `CAMERA_ZOOM` (1.5625) so the world still draws at 1.25
    (UI-016.D2).
    """

    def _shipped_zooms(self):
        """`(profile, CAMERA_ZOOM x RENDER_SCALE, TILE_PX)`, unsnapped:
        `effective_zoom()` rounds to whole tiles, so it cannot be the check."""
        from game import config
        from tests.web_profile import web_profile
        out = [("desktop", config.CAMERA_ZOOM * config.RENDER_SCALE, config.TILE_PX)]
        with web_profile():
            out.append(("web", config.CAMERA_ZOOM * config.RENDER_SCALE, config.TILE_PX))
        return out

    def test_a_tile_is_a_whole_number_of_pixels(self):
        for name, zoom, px in self._shipped_zooms():
            scaled = px * zoom
            self.assertEqual(scaled, int(scaled),
                             f"{name} build: tile is {scaled} px at zoom {zoom}")

    def test_the_web_world_draws_at_1_25_whatever_the_interface_scale(self):
        """The owner's call (UI-016.D2): the web interface scale moved to 0.8
        and the web world view did not move."""
        from game import config
        from tests.web_profile import web_profile
        with web_profile():
            self.assertEqual(config.RENDER_SCALE, 0.8)
            self.assertEqual(config.CAMERA_ZOOM, 1.5625)
            self.assertEqual(config.effective_zoom(), 1.25)
            self.assertEqual(config.effective_zoom(), config.WEB_VIEW_ZOOM)
            self.assertEqual(config.CAMERA_ZOOM * config.RENDER_SCALE, 1.25)

if __name__ == "__main__":
    unittest.main()
