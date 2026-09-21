"""The two menus that took no mouse before the shared navigation module
(structure review, B): the Sanctuary and the Rankings.

Hovering a Sanctuary row selects it and its panel, a click does what ENTER
does; the Rankings' hint line is its one target and a click on it leaves.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.rankings_state import RankingsState
from progression.items import generate_item


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _mouse(game, event_type, pos, button=1):
    kw = {"pos": pos}
    if event_type == pygame.MOUSEMOTION:
        kw.update(rel=(0, 0), buttons=(0, 0, 0))
    else:
        kw["button"] = button
    game.state_machine.handle_event(pygame.event.Event(event_type, **kw))


def _click(game, pos):
    _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
    _mouse(game, pygame.MOUSEBUTTONUP, pos)


class SanctuaryMouseTests(unittest.TestCase):
    def setUp(self):
        self.game = _game()
        for i in range(3):
            self.game.save.add_item(
                generate_item(self.game.content, seed=i, item_level=1).to_dict())
        self.meta = MetaState(self.game)
        self.game.state_machine.change(self.meta)
        self.meta.draw(self.game.screen)

    def _row(self, panel, i):
        rect = self.meta._mouse.hits.rect_of((panel, i))
        self.assertIsNotNone(rect, f"row {(panel, i)} not registered")
        return rect.center

    def test_draw_registers_every_upgrade_and_stash_row(self):
        for i in range(len(self.meta._upgrade_ids())):
            self._row(0, i)
        for i in range(len(self.game.save.stash)):
            self._row(1, i)

    def test_hover_selects_the_row_and_its_panel(self):
        _mouse(self.game, pygame.MOUSEMOTION, self._row(1, 2))
        self.assertEqual((self.meta.panel, self.meta.sel[1]), (1, 2))
        _mouse(self.game, pygame.MOUSEMOTION, self._row(0, 1))
        self.assertEqual((self.meta.panel, self.meta.sel[0]), (0, 1))
        self.assertEqual(self.meta.sel[1], 2)          # the other panel keeps its cursor

    def test_click_on_a_stash_row_equips_it(self):
        _click(self.game, self._row(1, 1))
        item = self.game.save.stash[1]
        self.assertEqual(self.game.save.equipped[item["slot"]], item["item_id"])

    def test_click_on_an_upgrade_row_buys_it_when_affordable(self):
        uid = self.meta._upgrade_ids()[0]
        self.game.save.currency = 10_000
        _click(self.game, self._row(0, 0))
        self.assertEqual(self.game.save.meta.get(uid, 0), 1)

    def test_keyboard_still_clamps_and_tab_still_switches(self):
        for _ in range(20):
            self.game.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        self.assertEqual(self.meta.sel[0], len(self.meta._upgrade_ids()) - 1)
        self.game.state_machine.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
        self.assertEqual(self.meta.panel, 1)


class RankingsMouseTests(unittest.TestCase):
    def test_click_on_the_hint_line_returns_to_the_menu(self):
        game = _game()
        rs = RankingsState(game)
        game.state_machine.change(rs)
        rs.draw(game.screen)
        target = rs._mouse.hits.rect_of(0)
        self.assertIsNotNone(target)
        _click(game, target.center)
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_a_click_elsewhere_stays(self):
        game = _game()
        rs = RankingsState(game)
        game.state_machine.change(rs)
        rs.draw(game.screen)
        _click(game, (10, 10))
        self.assertIs(game.state_machine.current, rs)


if __name__ == "__main__":
    unittest.main()
