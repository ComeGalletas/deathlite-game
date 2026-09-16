"""`game/display/native.py`: the SDL shims never raise, and the one
`Window` wrapper of the display window is made once and kept.

The keeping is the regression pin for the 2026-09-15 crash: pygame stores
a pointer to the wrapper in the SDL window's data and resolves window
events through it, so a wrapper made per call and dropped left a dangling
pointer and the next resize event read freed memory (an access violation
in the event pump, on a fresh save and not on a saved one -- heap layout).
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.display import native


class NativeShimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((320, 180))

    def test_the_window_wrapper_is_made_once_and_kept(self):
        native._wrapper = None
        sdl, ptr = native._window()
        if ptr is None:
            self.skipTest("SDL not reachable through ctypes on this driver")
        first = native._wrapper
        self.assertIsNotNone(first)
        sdl2, ptr2 = native._window()
        self.assertIs(native._wrapper, first)          # not a new wrapper per call
        self.assertEqual(ptr2, ptr)

    def test_every_shim_degrades_instead_of_raising(self):
        # Whatever the driver says, the answers are a bool or None.
        self.assertIsInstance(native.set_minimum_size(100, 100), bool)
        self.assertIsInstance(native.set_integer_scale(False), bool)
        self.assertIsInstance(native.set_window_size(320, 180), bool)
        ub = native.usable_bounds(0)
        self.assertTrue(ub is None or (isinstance(ub, tuple) and len(ub) == 2))
        dpi = native.dpi_scale(0)
        self.assertTrue(dpi is None or isinstance(dpi, float))

    def test_a_missing_sdl_means_every_shim_says_no(self):
        saved = native._lib
        try:
            native._lib = False
            self.assertFalse(native.set_minimum_size(1, 1))
            self.assertFalse(native.set_integer_scale(False))
            self.assertFalse(native.set_window_size(1, 1))
            self.assertIsNone(native.usable_bounds(0))
            self.assertIsNone(native.dpi_scale(0))
        finally:
            native._lib = saved


class SystemCursorTests(unittest.TestCase):
    """`system_cursor_ink_height`: the size the desktop draws its own arrow,
    which the in-game arrow is matched against (journal "Cursor size")."""

    def test_it_is_a_plausible_pixel_height_on_windows_and_none_elsewhere(self):
        height = native.system_cursor_ink_height()
        if height is None:
            self.assertNotEqual(sys.platform, "win32")
            return
        self.assertIsInstance(height, float)
        # A cursor smaller than the smallest slider stop's ink, or larger
        # than its largest, means the reading went wrong rather than the
        # player choosing an unusual size.
        self.assertGreater(height, 8.0)
        self.assertLess(height, 512.0)

    def test_the_arrow_ink_fraction_is_a_fraction_and_is_read_once(self):
        saved = native._arrow_fraction
        try:
            native._arrow_fraction = None
            first = native._arrow_ink_fraction()
            self.assertGreater(first, 0.0)
            self.assertLessEqual(first, 1.0)
            self.assertEqual(native._arrow_ink_fraction(), first)   # cached
        finally:
            native._arrow_fraction = saved

    def test_an_unreadable_bitmap_falls_back_to_the_stock_arrow(self):
        self.assertIsNone(native._ink_fraction_of(None, 0))


if __name__ == "__main__":
    unittest.main()
