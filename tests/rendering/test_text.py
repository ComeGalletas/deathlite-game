"""ui/text.py -- pixel-measured word wrap."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts
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
