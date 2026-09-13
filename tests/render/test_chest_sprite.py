"""The treasure chests' sprites (CB-9): four strips cut from the pack sheet,
one per rarity, and the rigs that name them.

Real assets, no world. The strips are checked against the cutting script so a
re-cut can never drift from what is committed, and the picks are pinned
against the sheet itself -- four *different* skins, each the one the journal
chose, with the frame order the open animation needs.
"""
import os
import subprocess
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import get_assets
from game.content import get_content
from progression import chests as chest_rules

FOLDER = os.path.join("assets", "items", "chests")
SHEET = os.path.join(FOLDER, "chests.png")
CELL, FRAMES = 32, 4
TIERS = ("common", "uncommon", "rare", "epic")


def _display():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()
        cls.table = get_content().chests

    def _rig(self, tier):
        return self.assets.meta[chest_rules.sprite_rig(tier, self.table)]

    def test_a_rig_exists_for_every_tier(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIsNotNone(self._rig(tier))

    def test_each_rig_names_one_strip_of_its_own(self):
        files = set()
        for tier in TIERS:
            with self.subTest(tier=tier):
                spec = self._rig(tier)["anims"]["open"]
                self.assertEqual(spec["frames"], FRAMES)
                self.assertFalse(spec["loop"], "the lid opens once and stays open")
                self.assertNotIn("row", spec,
                                 "a strip is its own file, not a row of the sheet")
                self.assertTrue(spec["file"].startswith("items/chests/chest_"))
                files.add(spec["file"])
        self.assertEqual(len(files), len(TIERS), "each tier wears its own art")

    def test_each_strip_exists_and_is_exactly_four_frames_wide(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                path = os.path.join("assets", self._rig(tier)["anims"]["open"]["file"])
                self.assertTrue(os.path.exists(path), path)
                self.assertEqual(pygame.image.load(path).get_size(),
                                 (CELL * FRAMES, CELL))

    def test_the_strips_are_what_the_cutting_script_produces(self):
        """`tools/asset_pipeline/cut_chest_sheets.py --check` compares every committed
        strip against a fresh cut of the source sheet, pixel for pixel."""
        done = subprocess.run(
            [sys.executable, os.path.join("tools", "asset_pipeline", "cut_chest_sheets.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_four_picks_are_four_different_skins(self):
        seen = set()
        for tier in TIERS:
            path = os.path.join("assets", self._rig(tier)["anims"]["open"]["file"])
            seen.add(pygame.image.tostring(pygame.image.load(path), "RGBA"))
        self.assertEqual(len(seen), len(TIERS))

    def test_the_frames_are_the_open_animation_in_order(self):
        """Frame 0 is the closed idle and frame 3 the settled open lid, so
        they must differ; the pack's baseline is at the bottom of the cell,
        which is what the bottom-centre anchor assumes."""
        for tier in TIERS:
            with self.subTest(tier=tier):
                path = os.path.join("assets", self._rig(tier)["anims"]["open"]["file"])
                strip = pygame.image.load(path).convert_alpha()
                cells = [strip.subsurface(pygame.Rect(i * CELL, 0, CELL, CELL))
                         for i in range(FRAMES)]
                shots = [pygame.image.tostring(c, "RGBA") for c in cells]
                self.assertEqual(len(set(shots)), FRAMES, "four distinct frames")
                for i, cell in enumerate(cells):
                    bottom = max((y for y in range(CELL) for x in range(CELL)
                                  if cell.get_at((x, y))[3] > 0), default=-1)
                    self.assertGreaterEqual(bottom, CELL - 3,
                                            f"frame {i} does not sit on the baseline")


class RigNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()
        cls.table = get_content().chests

    def _rig(self, tier):
        return self.assets.meta[chest_rules.sprite_rig(tier, self.table)]

    def test_every_rig_reads_the_32px_cell(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertEqual(self._rig(tier)["frame"], [CELL, CELL])

    def test_the_drawn_size_grows_with_the_tier(self):
        sizes = [self.assets.scale_for(chest_rules.sprite_rig(t, self.table))[0]
                 for t in TIERS]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(len(set(sizes)), len(TIERS))

    def test_the_anchor_is_bottom_centre_on_the_baseline(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                rig = chest_rules.sprite_rig(tier, self.table)
                w, h = self.assets.scale_for(rig)
                ax, ay = self.assets.anchor(rig)
                self.assertEqual(ax, w // 2)
                # 30 of the 32 px cell, scaled -- the pack's own baseline.
                self.assertAlmostEqual(ay, round(h * 30 / 32), delta=1)

    def test_a_frame_can_actually_be_built_for_every_tier(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                rig = chest_rules.sprite_rig(tier, self.table)
                for index in range(FRAMES):
                    self.assertIsNotNone(
                        self.assets.frame(rig, "open", index, size=(32, 32)))

    def test_the_colour_fallback_matches_the_rarity_ink(self):
        """Without art the chest draws a disc; it should still read as its
        tier, so no two tiers share a colour."""
        colours = {chest_rules.colour(t, self.table) for t in TIERS}
        self.assertEqual(len(colours), len(TIERS))


if __name__ == "__main__":
    unittest.main()
