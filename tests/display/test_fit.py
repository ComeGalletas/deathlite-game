"""`game/display/fit.py`: the window-size arithmetic (journal "Dynamic
window scaling", 2026-09-15). Pure functions; no display."""
import unittest

from game.display import fit

LOGICAL = (1600, 900)
MIN = (800, 450)


class FitWindowTests(unittest.TestCase):
    def test_a_1080p_desktop_keeps_the_logical_size(self):
        self.assertEqual(fit.fit_window(LOGICAL, (1920, 1080), minimum=MIN), (1600, 900))

    def test_a_small_laptop_shrinks_the_window_keeping_the_aspect(self):
        w, h = fit.fit_window(LOGICAL, (1366, 768), minimum=MIN, fraction=0.9)
        self.assertLessEqual(w, 1366 * 0.9 + 1)
        self.assertLessEqual(h, 768 * 0.9 + 1)
        self.assertAlmostEqual(w / h, 16 / 9, places=2)
        self.assertLess(w, 1600)

    def test_the_usable_area_not_the_desktop_bounds_the_window(self):
        with_bar = fit.fit_window(LOGICAL, (1600, 900), usable=(1600, 860),
                                  minimum=MIN, fraction=1.0)
        self.assertEqual(with_bar[1], 860)
        self.assertAlmostEqual(with_bar[0] / with_bar[1], 16 / 9, places=2)

    def test_the_dpi_factor_grows_the_window(self):
        # 3440x1440 at 125 %: the window looks the size it always did.
        self.assertEqual(fit.fit_window(LOGICAL, (3440, 1440), dpi_scale=1.25, minimum=MIN),
                         (2000, 1125))
        self.assertEqual(fit.fit_window(LOGICAL, (3840, 2160), dpi_scale=1.5, minimum=MIN),
                         (2400, 1350))

    def test_never_below_the_minimum(self):
        self.assertEqual(fit.fit_window(LOGICAL, (800, 600), minimum=MIN), MIN)


class ClampTests(unittest.TestCase):
    def test_a_saved_size_is_held_between_the_floor_and_the_desktop(self):
        self.assertEqual(fit.clamp_window((3000, 2000), MIN, (1920, 1080)), (1920, 1080))
        self.assertEqual(fit.clamp_window((300, 200), MIN, (1920, 1080)), MIN)
        self.assertEqual(fit.clamp_window((1280, 720), MIN, (1920, 1080)), (1280, 720))

    def test_a_desktop_smaller_than_the_floor_still_yields_the_floor(self):
        self.assertEqual(fit.clamp_window((640, 360), MIN, (640, 480)), MIN)


class LetterboxTests(unittest.TestCase):
    def test_a_wider_window_pillarboxes(self):
        scale, (ox, oy) = fit.letterbox((3440, 1440), LOGICAL)
        self.assertAlmostEqual(scale, 1.6)
        self.assertAlmostEqual(ox, 440.0)
        self.assertAlmostEqual(oy, 0.0)

    def test_a_taller_window_letterboxes(self):
        scale, (ox, oy) = fit.letterbox((1400, 1000), LOGICAL)
        self.assertAlmostEqual(scale, 0.875)
        self.assertAlmostEqual(ox, 0.0)
        self.assertAlmostEqual(oy, (1000 - 900 * 0.875) / 2)

    def test_an_exact_fit_is_the_identity(self):
        self.assertEqual(fit.letterbox(LOGICAL, LOGICAL), (1.0, (0.0, 0.0)))


class ResolutionListTests(unittest.TestCase):
    CANDS = ((1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160))

    def test_only_sizes_that_fit_the_desktop_are_listed(self):
        self.assertEqual(fit.resolution_entries(self.CANDS, (1920, 1080), MIN),
                         [(1280, 720), (1600, 900), (1920, 1080)])

    def test_sizes_under_the_floor_are_dropped(self):
        self.assertEqual(fit.resolution_entries(((640, 360), (1280, 720)), (1920, 1080), MIN),
                         [(1280, 720)])

    def test_nearest_entry_by_width(self):
        entries = [(1280, 720), (1600, 900), (1920, 1080)]
        self.assertEqual(fit.nearest_entry(entries, (1734, 975)), 1)
        self.assertEqual(fit.nearest_entry(entries, (1800, 1000)), 2)
        self.assertEqual(fit.nearest_entry([], (1, 1)), -1)


if __name__ == "__main__":
    unittest.main()
