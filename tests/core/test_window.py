"""`Game._open_window`: the vsync flag asks for a display-synced window and
falls back to a plain one when the driver refuses -- which the headless
dummy driver the suite runs under does, so what is pinned here is the
fallback and the report, not the sync itself."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game


class WindowTests(unittest.TestCase):
    def test_vsync_off_opens_the_plain_window(self):
        with mock.patch.object(config, "VSYNC", False):
            surf, on = Game._open_window()
        self.assertFalse(on)
        self.assertEqual(surf.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    def test_vsync_on_never_fails_to_open(self):
        with mock.patch.object(config, "VSYNC", True):
            surf, on = Game._open_window()
        self.assertEqual(surf.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        self.assertIsInstance(on, bool)

    def test_a_refusing_driver_falls_back_and_says_so(self):
        real = pygame.display.set_mode
        calls = []

        def refusing(size, flags=0, *a, **kw):
            calls.append((flags, kw.get("vsync", 0)))
            if kw.get("vsync"):
                raise pygame.error("no vsync here")
            return real(size)

        with mock.patch.object(config, "VSYNC", True), \
                mock.patch.object(pygame.display, "set_mode", refusing):
            surf, on = Game._open_window()
        self.assertFalse(on)
        self.assertEqual(calls[0][1], 1)                    # asked for vsync first
        self.assertEqual(calls[-1], (0, 0))                 # then the plain window
        self.assertEqual(surf.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    def test_the_game_records_what_it_got(self):
        g = Game()
        self.assertIsInstance(g.vsync, bool)

    def test_the_web_profile_turns_vsync_off(self):
        saved = (config.VSYNC, config.SAVE_ENABLED, config.FPS, config.SCREEN_WIDTH,
                 config.SCREEN_HEIGHT, config.CAMERA_ZOOM)
        try:
            config.apply_web_profile()
            self.assertFalse(config.VSYNC)
        finally:
            (config.VSYNC, config.SAVE_ENABLED, config.FPS, config.SCREEN_WIDTH,
             config.SCREEN_HEIGHT, config.CAMERA_ZOOM) = saved


if __name__ == "__main__":
    unittest.main()
