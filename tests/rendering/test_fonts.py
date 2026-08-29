"""game/fonts.py -- the bundled cartoonish face (Fredoka) plus its degrade path.

These prove the helper returns a usable `pygame.font.Font` whether or not the
bundled `.ttf` is present, and that it never caches across a display teardown
(a cached Font from before `pygame.quit()` is a dangling handle -> segfault).
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


class FontHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def test_bundled_face_is_present(self):
        self.assertTrue(
            (fonts.FONTS_DIR / fonts._FILES["sans"]).is_file(),
            "assets/fonts/Fredoka-VariableFont_wdth,wght.ttf is missing")

    def test_helpers_return_usable_fonts(self):
        for make in (fonts.heading, fonts.body, fonts.mono):
            f = make(20)
            self.assertIsInstance(f, pygame.font.Font)
            surf = f.render("Death Lite 123", True, (255, 255, 255))
            self.assertGreater(surf.get_width(), 0)
            self.assertGreater(surf.get_height(), 0)

    def test_heading_is_taller_than_body_at_the_same_size_gap(self):
        self.assertGreater(fonts.heading(40).get_height(),
                           fonts.body(16).get_height())

    def test_missing_bundle_falls_back_without_raising(self):
        original = dict(fonts._FILES)
        fonts._FILES["sans"] = "does-not-exist-98765.ttf"
        fonts._warned.discard("sans")
        try:
            f = fonts.body(18)
            self.assertIsInstance(f, pygame.font.Font)     # SysFont / default
            self.assertGreater(f.render("x", True, (0, 0, 0)).get_width(), 0)
        finally:
            fonts._FILES.clear()
            fonts._FILES.update(original)
            fonts._warned.discard("sans")

    def test_no_cache_survives_a_quit_init_cycle(self):
        f1 = fonts.body(18)
        pygame.quit()
        _display()
        f2 = fonts.body(18)                                # must be a fresh object
        self.assertIsNot(f1, f2)
        self.assertGreater(f2.render("ok", True, (1, 2, 3)).get_width(), 0)


if __name__ == "__main__":
    unittest.main()
