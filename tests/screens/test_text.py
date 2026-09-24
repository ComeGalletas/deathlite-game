"""ui/text.py -- pixel-measured word wrap."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts
from ui import text as text_mod
from ui.text import wrap


class WrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.font = fonts.body(20)

    def test_every_line_fits_and_is_greedy(self):
        text = "Moving builds Momentum (max 5); each stack is +7% damage. Standing still bleeds it away."
        lines = wrap(self.font, text, 300)
        self.assertGreater(len(lines), 1)
        for i, line in enumerate(lines):
            self.assertLessEqual(self.font.size(line)[0], 300, line)
            if i + 1 < len(lines):                     # the next word would not have fit
                first_next = lines[i + 1].split()[0]
                self.assertGreater(self.font.size(f"{line} {first_next}")[0], 300)
        self.assertEqual(" ".join(lines), text)        # nothing lost, nothing split

    def test_wide_glyphs_wrap_sooner_than_narrow_ones(self):
        wide = "WWWWWWWWWW " * 6
        narrow = "iiiiiiiiii " * 6
        self.assertGreater(len(wrap(self.font, wide, 300)), len(wrap(self.font, narrow, 300)))

    def test_an_overlong_word_gets_its_own_line(self):
        lines = wrap(self.font, "a Supercalifragilisticexpialidocious b", 60)
        self.assertEqual(lines, ["a", "Supercalifragilisticexpialidocious", "b"])

    def test_empty_and_single_word(self):
        self.assertEqual(wrap(self.font, "", 300), [])
        self.assertEqual(wrap(self.font, "   ", 300), [])
        self.assertEqual(wrap(self.font, "Aegis", 300), ["Aegis"])


if __name__ == "__main__":
    unittest.main()


class EllipsizeTests(unittest.TestCase):
    """`ellipsize`: `wrap`'s sibling for rows that get no second line.

    Nothing clips at the blit, so an untrimmed item name draws straight over
    the column beside it -- 38 % of generated names were wider than the
    victory screen's Run column before this existed.
    """

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((64, 64))
        cls.font = fonts.body(22)

    def w(self, text):
        return self.font.size(text)[0]

    def test_text_that_already_fits_is_untouched(self):
        for text in ("", "Ring", "[R] Ashen Signet"):
            self.assertEqual(text_mod.ellipsize(self.font, text, 400), text)

    def test_a_long_line_is_trimmed_to_the_width(self):
        long = "[E] Ascendant Warded Weave of Scholarship"
        self.assertGreater(self.w(long), 251)
        out = text_mod.ellipsize(self.font, long, 251)
        self.assertLessEqual(self.w(out), 251)
        self.assertTrue(out.endswith("..."))
        self.assertTrue(long.startswith(out[:-3].rstrip()))

    def test_the_result_never_exceeds_the_width_at_any_size(self):
        long = "[E] Ascendant Warded Weave of Scholarship"
        for width in range(20, 460, 7):
            self.assertLessEqual(self.w(text_mod.ellipsize(self.font, long, width)),
                                 width, f"overflowed at {width} px")

    def test_a_width_too_small_for_even_the_ellipsis_yields_the_ellipsis(self):
        self.assertEqual(text_mod.ellipsize(self.font, "anything", 4), "...")

    def test_a_width_of_zero_or_less_yields_nothing(self):
        for width in (0, -10):
            self.assertEqual(text_mod.ellipsize(self.font, "anything", width), "")

    def test_it_does_not_leave_a_space_before_the_dots(self):
        out = text_mod.ellipsize(self.font, "Ascendant Warded Weave", 130)
        self.assertNotIn(" ...", out)

    def test_every_generated_item_name_fits_the_narrowest_column(self):
        """The real worst case, not a sample: every name the item roller can
        produce, against the victory screen's Run column."""
        from game.content import get_content
        from progression.items import generate_item
        from ui import run_summary

        mins = run_summary.column_minimums(
            run_summary.VICTORY_COLUMNS, run_summary.RunSummaryPanel({})._row)
        space = 1600 - 2 * 60 - (len(mins) - 1) * 20
        content = run_summary.column_widths(space, mins)[0] - 56
        c = get_content()
        for seed in range(300):
            item = generate_item(c, seed=seed, item_level=(seed % 10) + 1, luck=0.5)
            name = f"[{item.rarity[:1].upper()}] {item.name}"
            self.assertLessEqual(
                self.w(text_mod.ellipsize(self.font, name, content)), content,
                f"seed {seed}: {name!r} overflows the Run column")
