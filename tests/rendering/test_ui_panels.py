"""ui/panels.py: composed 3-slice horizontal banner panels."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import Assets, reset_assets
from ui import panels


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class ThreeSliceHTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        panels.clear_cache()
        self.assets = Assets()

    def test_returns_a_surface_of_the_requested_size(self):
        panel = panels.three_slice_h(
            self.assets, left="ui_banner_cap_left", mid="ui_banner_mid",
            right="ui_banner_cap_right", width=400, height=80)
        self.assertIsNotNone(panel)
        self.assertEqual(panel.get_size(), (400, 80))

    def test_missing_rig_returns_none(self):
        panel = panels.three_slice_h(
            self.assets, left="not_a_real_rig", mid="ui_banner_mid",
            right="ui_banner_cap_right", width=400, height=80)
        self.assertIsNone(panel)

    def test_same_inputs_return_the_cached_surface(self):
        a = panels.three_slice_h(
            self.assets, left="ui_banner_cap_left", mid="ui_banner_mid",
            right="ui_banner_cap_right", width=300, height=60)
        b = panels.three_slice_h(
            self.assets, left="ui_banner_cap_left", mid="ui_banner_mid",
            right="ui_banner_cap_right", width=300, height=60)
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()


class SliceTests(unittest.TestCase):
    """`panels.slice`: one sheet cut on its 64-px grid and rebuilt at a size."""

    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        panels.clear_cache()
        self.assets = Assets()

    def _sheet(self, rig):
        return self.assets.image(rig)

    def test_three_slice_strip_keeps_its_caps_and_size(self):
        out = panels.slice(self.assets, "btn_blue_wide", (500, 64))
        self.assertEqual(out.get_size(), (500, 64))
        sheet = self._sheet("btn_blue_wide")
        # Caps are copied 1:1: sample a pixel inside each cap.
        for x_out, x_src in ((20, 20), (500 - 20, 192 - 20)):
            self.assertEqual(out.get_at((x_out, 30)), sheet.get_at((x_src, 30)))

    def test_nine_slice_panel_keeps_its_corners(self):
        out = panels.slice(self.assets, "btn_blue_panel", (340, 340))
        self.assertEqual(out.get_size(), (340, 340))
        sheet = self._sheet("btn_blue_panel")
        for (ox, oy), (sx, sy) in (((12, 12), (12, 12)), ((340 - 12, 12), (192 - 12, 12)),
                                   ((12, 340 - 12), (12, 192 - 12)),
                                   ((340 - 12, 340 - 12), (192 - 12, 192 - 12))):
            self.assertEqual(out.get_at((ox, oy)), sheet.get_at((sx, sy)))

    def test_short_target_prescales_the_caps_proportionally(self):
        # 40 px tall from a 64-px strip: the whole sheet scales by 0.625 first,
        # so a cap is 40 px wide, not 64.
        out = panels.slice(self.assets, "btn_blue_wide", (200, 40))
        self.assertEqual(out.get_size(), (200, 40))
        ref = pygame.transform.scale(self._sheet("btn_blue_wide"), (120, 40))
        self.assertEqual(out.get_at((10, 20)), ref.get_at((10, 20)))       # left cap
        self.assertEqual(out.get_at((190, 20)), ref.get_at((110, 20)))     # right cap

    def test_single_tile_is_plainly_scaled(self):
        d = dict(self.assets.rig("btn_blue_wide"))
        d["file"] = "ui/buttons/blue.png"
        self.assets.meta["_single"] = d
        out = panels.slice(self.assets, "_single", (32, 32))
        self.assertEqual(out.get_size(), (32, 32))

    def test_missing_rig_or_bad_size_is_none(self):
        self.assertIsNone(panels.slice(self.assets, "no_such_rig", (100, 64)))
        self.assertIsNone(panels.slice(self.assets, "btn_blue_wide", (0, 64)))

    def test_cached_per_rig_and_size(self):
        a = panels.slice(self.assets, "ribbon_blue", (300, 64))
        b = panels.slice(self.assets, "ribbon_blue", (300, 64))
        c = panels.slice(self.assets, "ribbon_blue", (301, 64))
        self.assertIs(a, b)
        self.assertIsNot(a, c)

    def test_every_declared_ui_rig_slices(self):
        for rig in ("btn_blue_wide", "btn_blue_wide_pressed", "btn_gold_wide",
                    "btn_red_wide", "btn_red_wide_pressed", "btn_blue_panel",
                    "btn_blue_panel_pressed", "btn_gold_panel",
                    "ribbon_blue", "ribbon_yellow", "ribbon_red"):
            with self.subTest(rig=rig):
                self.assertIsNotNone(panels.slice(self.assets, rig, (256, 64)))
