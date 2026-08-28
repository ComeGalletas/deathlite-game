"""Phase 4 D5: the Rankings screen -- per-difficulty best-run records reached
from the menu, back to the menu on ESC/ENTER, renders with and without data."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game
from game.states.menu_state import MenuState
from game.states.rankings_state import RankingsState


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


class RankingsStateTests(unittest.TestCase):
    def test_menu_rankings_entry_opens_the_screen(self):
        game = _game()
        game.state_machine.change(MenuState(game))
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_DOWN)                       # -> Rankings
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, RankingsState)

    def test_escape_and_enter_return_to_the_menu(self):
        for back_key in (pygame.K_ESCAPE, pygame.K_RETURN):
            game = _game()
            game.state_machine.change(RankingsState(game))
            _key(game, back_key)
            self.assertIsInstance(game.state_machine.current, MenuState)

    def test_draws_headless_with_no_records(self):
        game = _game()
        game.state_machine.change(RankingsState(game))
        game.state_machine.current.draw(game.screen)   # must not raise

    def test_draws_headless_and_shows_every_bucket_with_data(self):
        game = _game()
        game.save.record_best({"time": 300, "level": 8, "kills": 40,
                               "damage_dealt": 9000}, difficulty="normal")
        game.save.record_best({"time": 120, "level": 11, "kills": 77,
                               "damage_dealt": 15000}, difficulty="super_fast")
        rs = RankingsState(game)
        game.state_machine.change(rs)
        rs.draw(game.screen)
        # the screen pulls straight from the per-difficulty buckets
        self.assertEqual(rs.records["normal"]["time"], 300)
        self.assertEqual(rs.records["super_fast"]["kills"], 77)
        self.assertEqual(set(rs.records), set(config.DIFFICULTY_ORDER))


if __name__ == "__main__":
    unittest.main()
