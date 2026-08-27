"""Asset-integration Phase A: sprite metadata + the Assets loader/cache.

No gameplay is affected by this phase; these tests just prove the loader slices
sheets correctly and degrades gracefully."""
import logging
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import ASSETS_DIR, Assets, reset_assets
from game.content import get_content


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))   # convert_alpha() needs a display


class SpriteMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.meta = get_content().sprites

    def test_expected_rigs_present(self):
        for rig in ("soldier", "orc", "arrow"):
            self.assertIn(rig, self.meta)

    def test_files_exist(self):
        for rig, r in self.meta.items():
            files = ([r["file"]] if "file" in r
                     else [a["file"] for a in r.get("anims", {}).values()])
            for f in files:
                self.assertTrue((ASSETS_DIR / f).is_file(), f"missing {f}")

    def test_strip_width_matches_declared_frame_count(self):
        for rig in ("soldier", "orc"):
            fw, fh = self.meta[rig]["frame"]
            for anim, spec in self.meta[rig]["anims"].items():
                surf = pygame.image.load(str(ASSETS_DIR / spec["file"]))
                self.assertEqual(
                    surf.get_width(), fw * spec["frames"],
                    f"{rig}/{anim}: width {surf.get_width()} != {fw}*{spec['frames']}")
                self.assertEqual(surf.get_height(), fh, f"{rig}/{anim}: height")


class AssetsLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        self.a = Assets()

    def test_slices_every_declared_frame(self):
        self.assertEqual(len(self.a.frames("soldier", "walk")), 8)
        self.assertEqual(len(self.a.frames("orc", "death")), 4)

    def test_unscaled_frame_is_the_content_crop_size(self):
        rig = get_content().sprites["orc"]
        f = self.a.frame("orc", "idle", 0)
        expect = tuple(rig["content"][2:]) if "content" in rig else tuple(rig["frame"])
        self.assertEqual(f.get_size(), expect)

    def test_scaled_frame_matches_requested_size(self):
        f = self.a.frame("soldier", "walk", 2, size=(48, 48))
        self.assertIsInstance(f, pygame.Surface)
        self.assertEqual(f.get_size(), (48, 48))

    def test_loop_wraps_index(self):
        self.assertIs(self.a.frame("soldier", "walk", 0),
                      self.a.frame("soldier", "walk", 8))

    def test_oneshot_clamps_past_the_end(self):
        self.assertIs(self.a.frame("soldier", "death", 99),
                      self.a.frame("soldier", "death", 3))

    def test_frames_list_is_cached(self):
        self.assertIs(self.a.frames("orc", "walk", flip=True),
                      self.a.frames("orc", "walk", flip=True))

    def test_flip_produces_a_distinct_surface(self):
        normal = self.a.frame("orc", "walk", 0)
        flipped = self.a.frame("orc", "walk", 0, flip=True)
        self.assertIsNot(normal, flipped)
        self.assertEqual(normal.get_size(), flipped.get_size())

    def test_missing_rig_or_anim_returns_none(self):
        self.assertIsNone(self.a.frame("ghost", "walk", 0))
        self.assertIsNone(self.a.frames("soldier", "nope"))

    def test_missing_file_returns_none_and_warns_once(self):
        self.a._meta = {"ghost": {"frame": [10, 10],
                                  "anims": {"x": {"file": "none/none.png",
                                                  "frames": 1, "loop": False}}}}
        logging.disable(logging.CRITICAL)          # the warning here is expected
        try:
            self.assertIsNone(self.a.frame("ghost", "x", 0))
            self.assertIsNone(self.a.frame("ghost", "x", 0))
        finally:
            logging.disable(logging.NOTSET)
        self.assertEqual(len(self.a._warned), 1)   # logged once, not per call

    def test_arrow_image_uses_content_crop_when_unsized(self):
        crop = get_content().sprites["arrow"].get("content")
        img = self.a.image("arrow")
        self.assertEqual(img.get_size(), tuple(crop[2:]))

    def test_arrow_image_and_bucketed_rotation(self):
        img = self.a.image("arrow", size=(20, 20))
        self.assertEqual(img.get_size(), (20, 20))
        r = self.a.rotated("arrow", 90, size=(20, 20))
        self.assertIsInstance(r, pygame.Surface)
        # 88 deg falls in the same 8-deg bucket as 90 -> same cached surface
        self.assertIs(r, self.a.rotated("arrow", 88, size=(20, 20)))

    def test_tinted_arrow_is_distinct_and_cached(self):
        plain = self.a.rotated("arrow", 0, size=(20, 20))
        red = self.a.rotated("arrow", 0, size=(20, 20), tint=(150, 20, 10))
        self.assertIsNot(plain, red)
        self.assertIs(red, self.a.rotated("arrow", 0, size=(20, 20), tint=(150, 20, 10)))

    def test_picture_loads_scales_and_caches(self):
        base = self.a.picture("projectiles/arrow.png")
        self.assertIsInstance(base, pygame.Surface)
        scaled = self.a.picture("projectiles/arrow.png", size=(40, 40))
        self.assertEqual(scaled.get_size(), (40, 40))
        self.assertIs(scaled, self.a.picture("projectiles/arrow.png", size=(40, 40)))

    def test_picture_missing_returns_none(self):
        logging.disable(logging.CRITICAL)
        try:
            self.assertIsNone(self.a.picture("no/such/picture.png"))
        finally:
            logging.disable(logging.NOTSET)

    def test_metadata_helpers(self):
        meta = get_content().sprites
        self.assertEqual(self.a.frame_count("soldier", "idle"), 6)
        self.assertTrue(self.a.loops("soldier", "walk"))
        self.assertFalse(self.a.loops("soldier", "death"))
        self.assertEqual(self.a.anchor("orc"), tuple(meta["orc"]["anchor"]))
        self.assertEqual(self.a.scale_for("soldier"), tuple(meta["soldier"]["scale"]))
        self.assertEqual(self.a.face("soldier"), "right")


if __name__ == "__main__":
    unittest.main()
