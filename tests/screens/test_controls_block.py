"""ui/controls_block.py: the pause menu's Controls block (journal:
key_icons_journal.md, pass 4) -- rows follow the key layout, words take the
wide grey cap, and the block sits clear of the pause buttons."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import Assets, reset_assets
from ui import controls_block, keycap


class _Game:
    def __init__(self, layout="wasd_move"):
        self.key_layout = layout


class RowTests(unittest.TestCase):
    def test_wasd_layout(self):
        r = controls_block.rows(_Game("wasd_move"))
        self.assertEqual(r[0], (["W", "A", "S", "D"], "Move"))
        self.assertEqual(r[1][0], ["↑", "←", "↓", "→"])
        self.assertEqual(r[1][1], "Aim (hold)")

    def test_arrows_layout_swaps_the_two_rows(self):
        r = controls_block.rows(_Game("arrows_move"))
        self.assertEqual(r[0][0], ["↑", "←", "↓", "→"])
        self.assertEqual(r[1][0], ["W", "A", "S", "D"])

    def test_the_fixed_rows_come_from_the_bindings(self):
        r = dict((what, labels) for labels, what in controls_block.rows(_Game()))
        self.assertEqual(r["Interact"], [keycap.label_for(config.KEY_INTERACT)])
        self.assertEqual(r["Auto attack"], [keycap.label_for(config.KEY_TOGGLE_AUTO_ATTACK)])
        self.assertEqual(r["Build"], ["TAB"])
        self.assertEqual(r["Pause"], ["ESC"])
        self.assertEqual(r["Attack"], [controls_block.CLICK])

    def test_words_are_wide_letters_and_arrows_are_not(self):
        self.assertTrue(keycap.is_wide("TAB"))
        self.assertTrue(keycap.is_wide(controls_block.CLICK))
        self.assertFalse(keycap.is_wide("E"))
        self.assertFalse(keycap.is_wide("↑"))
        self.assertEqual(controls_block.cluster_width(["W", "A", "S", "D"]),
                         4 * controls_block.CAP + 3 * controls_block.CAP_GAP)
        self.assertEqual(controls_block.cluster_width(["TAB"]),
                         controls_block.CAP * keycap.WIDE_RATIO)


class GreyCapTests(unittest.TestCase):
    """The grey sheets only exist in the down position."""

    def test_grey_uses_the_same_frame_in_both_states(self):
        self.assertEqual(keycap.keycap_sheet("grey", "raised"), "keycap_grey")
        self.assertEqual(keycap.keycap_sheet("grey", "pressed"), "keycap_grey")
        self.assertEqual(keycap.keycap_sheet("grey", "raised", wide=True), "keycap_grey_wide")
        self.assertEqual(keycap.face_y("grey", "raised"), keycap.FACE_Y["pressed"])

    def test_grey_label_does_not_move_between_states(self):
        a = keycap.label_center((100, 200), "raised", colour="grey")
        b = keycap.label_center((100, 200), "pressed", colour="grey")
        self.assertEqual(a, b)

    def test_a_wide_cap_is_three_squares_across(self):
        r = keycap.cap_rect((100, 200), 32, colour="grey", wide=True)
        self.assertEqual(r.size, (96, 32))
        self.assertEqual(r.centerx, 100)

    def test_unknown_colour_is_refused(self):
        with self.assertRaises(ValueError):
            keycap.keycap_sheet("red", "raised")


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def setUp(self):
        reset_assets()
        self.assets = Assets()
        self.surface = pygame.Surface((800, 500), pygame.SRCALPHA)

    def test_every_row_draws_its_caps_in_grey(self):
        game = _Game()
        want = sum(len(labels) for labels, _ in controls_block.rows(game))
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            rect = controls_block.draw(self.surface, self.assets, (20, 20), game)
        self.assertEqual(m.call_count, want)
        self.assertTrue(all(c.kwargs["colour"] == "grey" for c in m.call_args_list))
        self.assertTrue(all(c.kwargs["state"] == "raised" for c in m.call_args_list))
        self.assertEqual(rect.topleft, (20, 20))
        self.assertGreater(rect.width, controls_block.cluster_width(["W", "A", "S", "D"]))
        self.assertGreater(rect.height, 7 * controls_block.ROW_STEP)

    def test_the_grey_and_wide_sheets_load(self):
        for rig in ("keycap_grey", "keycap_grey_wide", "keycap_blue_wide",
                    "keycap_blue_wide_pressed"):
            self.assertIsNotNone(self.assets.image(rig), rig)
        self.assertEqual(self.assets.image("keycap_grey_wide", size=(96, 32)).get_size(), (96, 32))

    def test_an_arrow_is_drawn_not_typed(self):
        calls = []

        class _Font:
            def render(self, *a):
                calls.append(a)
                return pygame.Surface((4, 4))
        with mock.patch.object(keycap, "draw_arrow", wraps=keycap.draw_arrow) as m:
            keycap.draw_keycap(self.surface, self.assets, (60, 60), "↑",
                               colour="grey", font=_Font())
        self.assertEqual(m.call_count, 1)
        self.assertEqual(calls, [])
        self.assertEqual(m.call_args.args[2], (0, -1))
        # ink of the label colour landed on the cap's face
        black = tuple(config.COLOR_ON_BUTTON) + (255,)
        r = keycap.cap_rect((60, 60), colour="grey")
        self.assertTrue(any(tuple(self.surface.get_at((x, y))) == black
                            for x in range(r.left, r.right) for y in range(r.top, r.bottom)))

    def test_the_words_land_on_wide_caps(self):
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            controls_block.draw(self.surface, self.assets, (20, 20), _Game())
        wide = [c.args[3] for c in m.call_args_list if c.kwargs["wide"]]
        self.assertEqual(wide, [controls_block.CLICK, "TAB", "ESC"])


if __name__ == "__main__":
    unittest.main()
