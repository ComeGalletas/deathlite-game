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
        for rig in ("hero_aegis", "hero_kestrel", "hero_nihil",
                    "skull", "arrow"):
            self.assertIn(rig, self.meta)

    def test_rigs_are_merged_from_the_split_files_with_shared_dead(self):
        import json
        from game.content import DATA_DIR
        files = {f: json.loads((DATA_DIR / f).read_text("utf-8")) for f in (
            "character_sprites.json", "enemy_sprites.json",
            "weapon_sprites.json", "prop_sprites.json")}
        # every split-file rig ended up in the merged namespace
        for name, rigs in files.items():
            for rig in rigs:
                self.assertIn(rig, self.meta, f"{rig} from {name} not merged")
        # `dead` is copied into both character + enemy files, identical content
        self.assertIn("dead", files["character_sprites.json"])
        self.assertIn("dead", files["enemy_sprites.json"])
        self.assertEqual(files["character_sprites.json"]["dead"],
                         files["enemy_sprites.json"]["dead"])

    def test_files_exist(self):
        for rig, r in self.meta.items():
            files = ([r["file"]] if "file" in r
                     else [a["file"] for a in r.get("anims", {}).values()])
            for f in files:
                self.assertTrue((ASSETS_DIR / f).is_file(), f"missing {f}")

    def test_strip_width_matches_declared_frame_count(self):
        for rig, m in ((r, mm) for r, mm in self.meta.items() if "anims" in mm):
            fw, fh = m["frame"]
            gcols, grows = m.get("grid", (None, None))
            for anim, spec in m["anims"].items():
                surf = pygame.image.load(str(ASSETS_DIR / spec["file"]))
                if gcols:                       # grid sheet: cols*fw x rows*fh
                    self.assertEqual((surf.get_width(), surf.get_height()),
                                     (fw * gcols, fh * grows), f"{rig}/{anim}: grid")
                    self.assertLessEqual(spec["frames"], gcols,
                                         f"{rig}/{anim}: frames > grid cols")
                    self.assertLess(spec.get("row", 0), grows,
                                    f"{rig}/{anim}: row out of range")
                else:                           # plain horizontal strip
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
        self.assertEqual(len(self.a.frames("hero_aegis", "idle")), 8)
        self.assertEqual(len(self.a.frames("skull", "attack")), 7)

    def test_unscaled_frame_is_the_content_crop_size(self):
        rig = get_content().sprites["skull"]
        f = self.a.frame("skull", "idle", 0)
        expect = tuple(rig["content"][2:]) if "content" in rig else tuple(rig["frame"])
        self.assertEqual(f.get_size(), expect)

    def test_scaled_frame_matches_requested_size(self):
        f = self.a.frame("hero_aegis", "idle", 2, size=(48, 48))
        self.assertIsInstance(f, pygame.Surface)
        self.assertEqual(f.get_size(), (48, 48))

    def test_loop_wraps_index(self):
        self.assertIs(self.a.frame("hero_aegis", "idle", 0),
                      self.a.frame("hero_aegis", "idle", 8))

    def test_oneshot_clamps_past_the_end(self):
        self.assertIs(self.a.frame("hero_aegis", "attack", 99),
                      self.a.frame("hero_aegis", "attack", 3))

    def test_frames_list_is_cached(self):
        self.assertIs(self.a.frames("skull", "walk", flip=True),
                      self.a.frames("skull", "walk", flip=True))

    def test_flip_produces_a_distinct_surface(self):
        normal = self.a.frame("skull", "walk", 0)
        flipped = self.a.frame("skull", "walk", 0, flip=True)
        self.assertIsNot(normal, flipped)
        self.assertEqual(normal.get_size(), flipped.get_size())

    def test_row_offset_slices_the_named_grid_strip(self):
        # 3-col x 2-row sheet of 4px cells: row 0 red, row 1 green.
        sheet = pygame.Surface((12, 8), pygame.SRCALPHA)
        sheet.fill((200, 0, 0), pygame.Rect(0, 0, 12, 4))
        sheet.fill((0, 200, 0), pygame.Rect(0, 4, 12, 4))
        self.a._sheets["grid_test.png"] = sheet            # bypass disk
        self.a._meta = {"grid": {
            "frame": [4, 4], "grid": [3, 2],
            "anims": {
                "top":    {"file": "grid_test.png", "frames": 3, "loop": True},
                "bottom": {"file": "grid_test.png", "frames": 3, "loop": True, "row": 1},
            }}}
        self.assertEqual(len(self.a.frames("grid", "bottom")), 3)
        self.assertEqual(self.a.frame("grid", "top", 0).get_at((1, 1))[:3], (200, 0, 0))
        self.assertEqual(self.a.frame("grid", "bottom", 0).get_at((1, 1))[:3], (0, 200, 0))
        # row default (0) is unchanged behaviour
        self.assertEqual(self.a.frame("grid", "top", 2).get_at((1, 1))[:3], (200, 0, 0))

    def test_tint_multiplies_frames_and_caches_per_colour(self):
        sheet = pygame.Surface((8, 4), pygame.SRCALPHA)
        sheet.fill((255, 255, 255))
        self.a._sheets["white.png"] = sheet
        self.a._meta = {"w": {"frame": [4, 4], "anims": {
            "loop": {"file": "white.png", "frames": 2, "loop": True}}}}
        plain = self.a.frame("w", "loop", 0)
        blue = self.a.frame("w", "loop", 0, tint=(0, 0, 255))
        self.assertEqual(plain.get_at((1, 1))[:3], (255, 255, 255))
        self.assertEqual(blue.get_at((1, 1))[:3], (0, 0, 255))
        # cached per colour; a list tint hits the same cache entry as its tuple
        self.assertIs(blue, self.a.frame("w", "loop", 0, tint=[0, 0, 255]))
        self.assertIsNot(blue, plain)

    def test_missing_rig_or_anim_returns_none(self):
        self.assertIsNone(self.a.frame("ghost", "walk", 0))
        self.assertIsNone(self.a.frames("hero_aegis", "nope"))

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
        self.assertIsNotNone(crop)
        assert crop is not None
        img = self.a.image("arrow")
        self.assertIsNotNone(img)
        assert img is not None
        self.assertEqual(img.get_size(), tuple(crop[2:]))

    def test_arrow_image_and_bucketed_rotation(self):
        img = self.a.image("arrow", size=(20, 20))
        self.assertIsNotNone(img)
        assert img is not None
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

    def test_frame_rotated_returns_a_surface_and_buckets(self):
        r = self.a.frame_rotated("skull", "idle", 0, 90)
        self.assertIsInstance(r, pygame.Surface)
        # 1 deg and 3 deg both snap to the 0 bucket -> the same cached surface
        self.assertIs(self.a.frame_rotated("skull", "idle", 0, 1),
                      self.a.frame_rotated("skull", "idle", 0, 3))
        # a different frame index is a different surface
        self.assertIsNot(self.a.frame_rotated("skull", "idle", 0, 0),
                         self.a.frame_rotated("skull", "idle", 1, 0))

    def test_frame_rotated_zero_keeps_the_frame_size_a_turn_grows_it(self):
        size = (40, 12)
        flat = self.a.frame_rotated("skull", "idle", 0, 0, size=size)
        self.assertIsNotNone(flat)
        assert flat is not None
        self.assertEqual(flat.get_size(), size)                 # 0-bucket: no growth
        turned = self.a.frame_rotated("skull", "idle", 0, 40, size=size)
        self.assertIsNotNone(turned)
        assert turned is not None
        self.assertGreater(turned.get_width() * turned.get_height(),
                           flat.get_width() * flat.get_height())  # oblique -> bigger bbox

    def test_frame_rotated_tint_is_distinct_and_cached(self):
        plain = self.a.frame_rotated("skull", "idle", 0, 0)
        red = self.a.frame_rotated("skull", "idle", 0, 0, tint=(150, 20, 10))
        self.assertIsNot(plain, red)
        self.assertIs(red, self.a.frame_rotated("skull", "idle", 0, 0, tint=(150, 20, 10)))

    def test_frame_rotated_missing_rig_returns_none(self):
        self.assertIsNone(self.a.frame_rotated("nope", "idle", 0, 45))
        self.assertIsNone(self.a.frame_rotated("skull", "nope", 0, 45))

    def test_picture_loads_scales_and_caches(self):
        base = self.a.picture("projectiles/arrow.png")
        self.assertIsInstance(base, pygame.Surface)
        scaled = self.a.picture("projectiles/arrow.png", size=(40, 40))
        self.assertIsNotNone(scaled)
        assert scaled is not None
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
        self.assertEqual(self.a.frame_count("hero_aegis", "idle"), 8)
        self.assertTrue(self.a.loops("hero_aegis", "walk"))
        self.assertFalse(self.a.loops("hero_aegis", "attack"))
        self.assertEqual(self.a.anchor("skull"), tuple(meta["skull"]["anchor"]))
        self.assertEqual(self.a.scale_for("hero_aegis"), tuple(meta["hero_aegis"]["scale"]))
        self.assertEqual(self.a.face("hero_aegis"), "right")


if __name__ == "__main__":
    unittest.main()
