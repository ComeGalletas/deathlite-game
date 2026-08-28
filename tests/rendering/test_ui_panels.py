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
