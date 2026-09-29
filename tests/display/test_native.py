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
import time
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.display import native


class NativeShimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((320, 180))

    def _with_lib(self, lib):
        """Run with `native._lib` swapped for `lib` (restored afterwards) and
        the kept wrapper cleared. The wrapper the test makes is left kept:
        dropping it is the dangling-pointer crash this module pins."""
        saved = native._lib
        self.addCleanup(setattr, native, "_lib", saved)
        native._lib, native._wrapper = lib, None

    def test_the_window_wrapper_is_made_once_and_kept(self):
        """The keeping is `_window`'s own Python, so it is checked against a
        stand-in SDL library that answers `SDL_GetWindowFromID` for pygame's
        real display window. That runs on every platform: a pip wheel's SDL
        is bundled under a mangled name that `ctypes.util.find_library`
        cannot find off Windows, and the check used to skip there
        (TST-004.3.10). The real library is covered below."""
        from types import SimpleNamespace

        def get_window_from_id(wid):
            return 0x1000 + int(wid)              # any non-null "pointer"

        self._with_lib(SimpleNamespace(SDL_GetWindowFromID=get_window_from_id))
        sdl, ptr = native._window()
        self.assertIsNotNone(ptr)
        first = native._wrapper
        self.assertIsNotNone(first)
        sdl2, ptr2 = native._window()
        self.assertIs(native._wrapper, first)          # not a new wrapper per call
        self.assertEqual(ptr2, ptr)

    def test_the_real_library_reaches_the_window_where_the_game_ships(self):
        """On Windows -- the platform the game is packaged for -- pygame's
        own `SDL2.dll` is always loadable, so the real round trip is
        asserted there, wrapper kept included. Elsewhere `_window` must
        answer a pointer or degrade to `(None, None)`, never raise."""
        self._with_lib(None)                      # load it afresh
        sdl, ptr = native._window()
        if sys.platform == "win32":
            self.assertIsNotNone(ptr, "SDL2.dll not reachable through ctypes")
            first = native._wrapper
            self.assertEqual(native._window()[1], ptr)
            self.assertIs(native._wrapper, first)
        else:
            self.assertTrue((sdl, ptr) == (None, None) or ptr)

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


def _sleep_median_ms(n: int = 15) -> float:
    """The median wall time of `pygame.time.wait(1)`: `SDL_Delay`, the very
    sleep `Clock.tick` makes. About 1.5 ms while the 1 ms timer request is
    honored, about 15.3 ms while Windows sets it aside."""
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        pygame.time.wait(1)
        samples.append((time.perf_counter() - t) * 1000.0)
    samples.sort()
    return samples[n // 2]


class TimerResolutionTests(unittest.TestCase):
    """`honor_timer_resolution` (SYS-011): Windows 11 may set aside the 1 ms
    timer SDL asks for while a process is hidden and silent, and the frame
    cap then holds every frame at ~31 ms. The fix turns the process's
    `IGNORE_TIMER_RESOLUTION` power-throttling policy off."""

    @classmethod
    def setUpClass(cls):
        pygame.display.init()           # SDL starts, and asks for its 1 ms timer
        pygame.time.wait(1)             # the timer subsystem, as `Clock.tick` starts it

    def setUp(self):
        # Every test leaves the process's policy as it found it.
        saved = native._throttling() or (0, 0)
        self.addCleanup(native._set_throttling, *saved)

    def test_the_policy_reads_back_as_always_honored(self):
        honored = native.honor_timer_resolution()
        if sys.platform != "win32":
            self.assertFalse(honored)
            self.assertIsNone(native._throttling())
            return
        self.assertTrue(honored)
        self.assertEqual(native._throttling(), (native._IGNORE_TIMER_RESOLUTION, 0))

    def test_the_fix_lifts_the_stretch_windows_applies(self):
        """The regression pin. Windows applying the rule on its own and the
        process switching `IGNORE_TIMER_RESOLUTION` on are one policy, so the
        stretch is forced here rather than waited for (SYS-011.D3): with it
        on, the tick's sleep rounds to the coarse timer; the fix brings it
        back to 1 ms in the same process. Off Windows there is no such
        policy, and forcing it is refused."""
        forced = native._set_throttling(native._IGNORE_TIMER_RESOLUTION,
                                        native._IGNORE_TIMER_RESOLUTION)
        if sys.platform != "win32":
            self.assertFalse(forced)
            self.assertFalse(native.honor_timer_resolution())
            return
        self.assertTrue(forced)
        self.assertGreater(_sleep_median_ms(), 10.0,
                           "the forced policy no longer stretches the sleep")
        self.assertTrue(native.honor_timer_resolution())
        self.assertLess(_sleep_median_ms(), 5.0,
                        "honoring the request did not bring the 1 ms sleep back")

    def test_off_windows_it_touches_no_win32_api(self):
        def no_kernel32():
            raise AssertionError("reached for kernel32 off Windows")

        with mock.patch.object(native.sys, "platform", "emscripten"), \
                mock.patch.object(native, "_kernel32", no_kernel32):
            self.assertFalse(native.honor_timer_resolution())
            self.assertFalse(native._set_throttling(0, 0))
            self.assertIsNone(native._throttling())

    def test_a_windows_without_the_api_answers_false_and_says_why(self):
        """Windows 7 has no `SetProcessInformation` (AttributeError); a
        failed load is OSError. Neither reaches the caller."""
        for exc in (AttributeError("SetProcessInformation"), OSError("kernel32")):
            def broken(exc=exc):
                raise exc

            with self.subTest(exc=type(exc).__name__), \
                    mock.patch.object(native.sys, "platform", "win32"), \
                    mock.patch.object(native, "_kernel32", broken), \
                    self.assertLogs(native.log, "INFO") as logged:
                self.assertFalse(native.honor_timer_resolution())
                self.assertIsNone(native._throttling())
            self.assertIn("unavailable", logged.output[0])

    def test_a_refused_policy_answers_false_and_says_why(self):
        """Before Windows 11 the timer-resolution bit is not a known policy
        and `SetProcessInformation` answers 0."""
        from types import SimpleNamespace
        refusing = SimpleNamespace(GetCurrentProcess=lambda: -1,
                                   SetProcessInformation=lambda *a: 0,
                                   GetProcessInformation=lambda *a: 0)
        with mock.patch.object(native.sys, "platform", "win32"), \
                mock.patch.object(native, "_kernel32", lambda: refusing), \
                self.assertLogs(native.log, "INFO") as logged:
            self.assertFalse(native.honor_timer_resolution())
            self.assertIsNone(native._throttling())
        self.assertIn("refused", logged.output[0])


if __name__ == "__main__":
    unittest.main()
