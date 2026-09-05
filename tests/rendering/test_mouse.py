"""Mouse support in menus, group A: the `ui.mouse` helper and the cursor.

`HitMap` / `MouseNav` are pure and tested with synthetic events; the cursor
install is tested against the real asset and against a missing one.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import get_assets
from game.game import Game
from ui.mouse import HitMap, MouseNav, install_cursor


def motion(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def up(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


class HitMapTests(unittest.TestCase):
    def test_at_finds_the_registered_key_and_none_outside(self):
        h = HitMap()
        h.add(pygame.Rect(10, 10, 100, 20), "a")
        h.add(pygame.Rect(10, 40, 100, 20), "b")
        self.assertEqual(h.at((50, 15)), "a")
        self.assertEqual(h.at((50, 45)), "b")
        self.assertIsNone(h.at((50, 35)))
        self.assertIsNone(h.at((500, 15)))

    def test_last_added_wins_on_overlap(self):
        h = HitMap()
        h.add(pygame.Rect(0, 0, 100, 100), "under")
        h.add(pygame.Rect(25, 25, 50, 50), "over")
        self.assertEqual(h.at((50, 50)), "over")
        self.assertEqual(h.at((5, 5)), "under")

    def test_clear_and_rect_of(self):
        h = HitMap()
        r = h.add(pygame.Rect(1, 2, 3, 4), 7)
        self.assertEqual(h.rect_of(7), pygame.Rect(1, 2, 3, 4))
        self.assertEqual(len(h), 1)
        h.clear()
        self.assertEqual(len(h), 0)
        self.assertIsNone(h.at((2, 3)))
        self.assertIsNone(h.rect_of(7))
        self.assertEqual(r, pygame.Rect(1, 2, 3, 4))          # add returns the rect


class MouseNavTests(unittest.TestCase):
    def setUp(self):
        self.nav = MouseNav()
        self.nav.hits.add(pygame.Rect(0, 0, 100, 20), 0)
        self.nav.hits.add(pygame.Rect(0, 30, 100, 20), 1)

    def test_motion_over_a_row_hovers(self):
        self.assertEqual(self.nav.event(motion((10, 35))), ("hover", 1))
        self.assertIsNone(self.nav.event(motion((10, 25))))

    def test_press_and_release_on_one_row_clicks_on_the_release(self):
        self.assertIsNone(self.nav.event(down((10, 5))))
        self.assertEqual(self.nav.event(up((90, 15))), ("click", 0))

    def test_release_on_a_different_row_than_the_press_is_not_a_click(self):
        self.nav.event(down((10, 5)))
        self.assertIsNone(self.nav.event(up((10, 35))))
        self.assertIsNone(self.nav.event(up((10, 35))))       # press was consumed

    def test_release_without_a_press_is_not_a_click(self):
        self.assertIsNone(self.nav.event(up((10, 5))))

    def test_press_off_every_row_then_release_on_one_is_not_a_click(self):
        self.nav.event(down((10, 25)))
        self.assertIsNone(self.nav.event(up((10, 5))))

    def test_hover_property_follows_the_cursor_and_clears_off_every_rect(self):
        self.assertIsNone(self.nav.hover)
        self.nav.event(motion((10, 35)))
        self.assertEqual(self.nav.hover, 1)
        self.nav.event(motion((10, 25)))                      # between the rows
        self.assertIsNone(self.nav.hover)

    def test_other_buttons_are_ignored(self):
        self.assertIsNone(self.nav.event(down((10, 5), button=3)))
        self.assertIsNone(self.nav.event(up((10, 5), button=3)))
        self.assertIsNone(self.nav.event(up((10, 5))))        # no left press stored


class CursorTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_boot_survives_the_cursor_install_and_the_asset_exists(self):
        # The headless dummy driver refuses surface cursors ("Cursors are not
        # currently supported"), so `cursor_installed` is False here by the
        # driver, not by the asset: the boot must still complete and the
        # arrow must load. The surface path itself is pinned below with
        # `set_cursor` mocked.
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        self.assertIsInstance(game.cursor_installed, bool)
        self.assertTrue(config.UI_CURSOR_IMAGE.endswith("pointers/arrow.png"))
        self.assertIsNotNone(game.assets.picture(config.UI_CURSOR_IMAGE))

    def test_cursor_surface_is_the_ink_crop_at_the_configured_scale(self):
        pygame.init()
        pygame.display.set_mode((64, 64))
        captured = []
        with mock.patch.object(pygame.mouse, "set_cursor",
                               side_effect=lambda c: captured.append(c)):
            self.assertTrue(install_cursor(get_assets()))
        cur = captured[0]
        w, h = cur.data[1].get_size()
        ink = get_assets().picture(config.UI_CURSOR_IMAGE).get_bounding_rect()
        self.assertEqual((w, h), (round(ink.width * config.UI_CURSOR_SCALE),
                                  round(ink.height * config.UI_CURSOR_SCALE)))
        self.assertEqual(cur.data[0], (0, 0))                 # hotspot: the arrow tip

    def test_missing_pointer_keeps_the_system_cursor_and_boots(self):
        with mock.patch.object(config, "UI_CURSOR_IMAGE", "ui/pointers/nope.png"):
            game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        self.assertFalse(game.cursor_installed)

    def test_a_refusing_driver_is_survived(self):
        pygame.init()
        pygame.display.set_mode((64, 64))
        with mock.patch.object(pygame.mouse, "set_cursor",
                               side_effect=pygame.error("no cursors here")):
            self.assertFalse(install_cursor(get_assets()))


if __name__ == "__main__":
    unittest.main()
