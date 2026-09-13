"""The HUD bar and gem pieces: ten files cut out of the big UI pack sheets.

The rigs used to reach into `assets/ui/04.png` and `01.png` with offsets. Now
each names its own file in `assets/ui/hud/`, and the big sheets sit unread in
`assets/ui/base/` (owner, 2026-09-12). What is pinned here is that the split
did not change a pixel and cannot drift: the committed files are checked
against the cutting script, and the rig names, filenames and geometry are
checked against each other.

Real assets, no world.
"""
import os
import subprocess
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import get_assets
from game.content import get_content

HUD_DIR = os.path.join("assets", "ui", "hud")
BASE_DIR = os.path.join("assets", "ui", "base")
CUTTER = os.path.join("tools", "asset_pipeline", "cut_ui_bars.py")
BAR_RIGS = ("bar_hex_frame_silver", "bar_hex_frame_grey", "bar_hex_frame_copper",
            "bar_hex_fill_red", "bar_hex_fill_yellow", "bar_hex_fill_blue",
            "bar_hex_fill_green", "bar_hex_empty")
GEM_RIGS = ("gem_socket_blue", "gem_core_blue")


def _display():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


class CutTests(unittest.TestCase):
    def test_the_committed_pieces_are_what_the_script_cuts(self):
        """A re-cut can never silently drift from what is committed."""
        done = subprocess.run([sys.executable, CUTTER, "--check"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0,
                         f"cut_ui_bars.py --check failed:\n{done.stdout}{done.stderr}")

    def test_the_big_sheets_moved_to_base_and_nothing_reads_them(self):
        for name in ("00", "01", "02", "03", "04", "05", "06", "07", "All"):
            self.assertTrue(os.path.exists(os.path.join(BASE_DIR, f"{name}.png")),
                            f"{name}.png is not in assets/ui/base")
            self.assertFalse(os.path.exists(os.path.join("assets", "ui", f"{name}.png")),
                             f"{name}.png is still loose in assets/ui")
        rigs = get_content().ui_sprites
        for name, rig in rigs.items():
            self.assertNotIn("/base/", rig.get("file", ""),
                             f"{name} still reads a pack sheet")

    def test_the_window_icon_stayed_put(self):
        # It lives in assets/ui/ beside the sheets but is not one of them;
        # sweeping it into base/ would drop the window icon.
        self.assertTrue(os.path.exists(os.path.join("assets", config.WINDOW_ICON)))


class RigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def test_every_piece_has_a_rig_and_every_rig_a_file(self):
        meta = self.assets.meta
        for name in BAR_RIGS + GEM_RIGS:
            self.assertIn(name, meta, f"no rig {name}")
            self.assertIsNotNone(self.assets.image(name), f"{name} has no art")

    def test_each_file_is_named_after_the_rig_that_draws_it(self):
        """The point of the split: no indirection between rig and pixels."""
        for name in BAR_RIGS + GEM_RIGS:
            self.assertEqual(self.assets.meta[name]["file"],
                             f"ui/hud/{name}.png")

    def test_no_rig_needs_a_content_crop_any_more(self):
        # The file *is* the crop now; a leftover `content` would crop twice.
        for name in BAR_RIGS + GEM_RIGS:
            self.assertNotIn("content", self.assets.meta[name])

    def test_the_housings_and_the_fills_are_the_sizes_the_layout_assumes(self):
        for name in BAR_RIGS[:3]:
            self.assertEqual(self.assets.image(name).get_size(), (42, 11), name)
        for name in BAR_RIGS[3:]:
            self.assertEqual(self.assets.image(name).get_size(), (34, 5), name)

    def test_a_housings_well_matches_the_fill_it_holds(self):
        """`well` survived the cut: it is relative to the housing's art box,
        which is exactly what the cut file now is."""
        fill = self.assets.image("bar_hex_fill_red")
        for name in BAR_RIGS[:3]:
            wx, _wy, ww, wh = self.assets.meta[name]["well"]
            self.assertEqual((ww, wh), fill.get_size(), name)
            housing = self.assets.image(name)
            self.assertEqual(wx, housing.get_width() - ww - wx,
                             f"{name}: the fill is not centred in its housing")

    def test_the_gem_pieces_keep_their_whole_cell(self):
        """Cropping each to its own ink would throw away the offset that
        seats the gem inside the ring."""
        ring = self.assets.image("gem_socket_blue")
        core = self.assets.image("gem_core_blue")
        self.assertEqual(ring.get_size(), (48, 48))
        self.assertEqual(core.get_size(), (48, 48))
        cx, cy = 24, 24
        self.assertEqual(ring.get_at((cx, cy))[3], 0, "the ring should be hollow")
        self.assertGreater(core.get_at((cx, cy))[3], 0, "the gem should fill it")

    def test_the_rigs_the_hud_and_the_end_screens_name_all_exist(self):
        for attr in ("HUD_BAR_FRAME", "HUD_BAR_HP_FILL", "HUD_BAR_XP_FILL",
                     "HUD_BAR_EMPTY", "HUD_BOSS_FRAME", "HUD_BOSS_FILL",
                     "HUD_GEM_SOCKET", "HUD_GEM_CORE"):
            rig = getattr(config, attr)
            self.assertIsNotNone(self.assets.image(rig),
                                 f"config.{attr} names {rig!r}, which has no art")


if __name__ == "__main__":
    unittest.main()
