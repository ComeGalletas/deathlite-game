"""The loading screen builds the run's world a slice at a time and hands it
over intact."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.loading_state import LoadingState
from game.states.playing_state import PlayingState
from tests import worlds as W
from world import digest

SEED = W.SEEDS[0]


def _game() -> Game:
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _drive(game, limit=5000) -> int:
    """Frames until the loading screen has handed over, or `limit`."""
    n = 0
    while isinstance(game.state_machine.current, LoadingState) and n < limit:
        game.state_machine.update(1 / 60)
        game._render()
        n += 1
    return n


class LoadingStateTests(unittest.TestCase):
    def test_it_hands_a_baked_world_to_the_run(self):
        game = _game()
        game.state_machine.change(LoadingState(game), seed=SEED)
        frames = _drive(game)
        p = game.state_machine.current
        self.assertIsInstance(p, PlayingState)
        # More than one frame: the world was built in slices, not in `enter`.
        self.assertGreater(frames, 5)
        self.assertEqual(p.run_seed, SEED)
        self.assertTrue(p.game_map._tiles_ok, "the run started with an unbaked map")
        self.assertIsNotNone(p._nav)
        # The same world the run would have built for itself.
        self.assertEqual(digest.layout_digest(p.game_map.layout),
                         digest.layout_digest(W.layout(SEED)))
        pygame.quit()

    def test_the_view_is_warmed_before_the_run_starts(self):
        """The blit cache the first frames would have filled is filled on
        the loading screen: the run's first draw adds almost nothing."""
        game = _game()
        state = LoadingState(game)
        game.state_machine.change(state, seed=SEED)
        labels = []
        steps = state._steps
        state._steps = iter(lambda: (labels.append(next(steps)) or labels[-1]), None)
        _drive(game)
        p = game.state_machine.current
        self.assertIsInstance(p, PlayingState)
        warm = [l for l in labels if str(l).startswith("warming the view")]
        self.assertEqual(len(warm), len(LoadingState._WARM_RING))
        gm = p.game_map
        before = len(gm._blit_cache)
        self.assertGreater(before, 20, "the loading screen warmed nothing")
        p.draw(game.screen)
        self.assertLessEqual(len(gm._blit_cache) - before, 3,
                             "the run's first frame still filled the cache")
        pygame.quit()

    def test_the_hero_animates_while_it_waits(self):
        game = _game()
        state = LoadingState(game)
        game.state_machine.change(state, seed=SEED)
        self.assertIsNotNone(state._anim, "the first hero has a rig")
        self.assertEqual(state._anim.anim, "walk")
        before = state._anim.index
        for _ in range(12):
            game.state_machine.update(1 / 12)      # a full cycle of any 12-frame walk
            game._render()
            if state._anim.index != before:
                break
        self.assertNotEqual(state._anim.index, before, "the sprite did not advance")
        pygame.quit()

    def test_the_screen_is_dark_with_text_and_the_hero(self):
        game = _game()
        state = LoadingState(game)
        game.state_machine.change(state, seed=SEED)
        surf = pygame.Surface(game.screen.get_size())
        state.draw(surf)
        w, h = surf.get_size()
        self.assertEqual(surf.get_at((4, 4))[:3], (10, 10, 14), "not a dark fill")
        lit = sum(1 for x in range(0, w, 8) for y in range(0, h, 8)
                  if surf.get_at((x, y))[:3] != (10, 10, 14))
        self.assertGreater(lit, 10, "neither text nor hero was drawn")
        pygame.quit()

    def test_the_dev_restart_goes_through_the_loading_screen(self):
        game = _game()
        game.state_machine.change(LoadingState(game), seed=SEED, dev=True)
        _drive(game)
        p = game.state_machine.current
        self.assertIsInstance(p, PlayingState)
        p._restart_dev_run()
        self.assertIsInstance(game.state_machine.current, LoadingState)
        _drive(game)
        q = game.state_machine.current
        self.assertIsInstance(q, PlayingState)
        self.assertEqual(q.run_seed, SEED)
        self.assertTrue(q.dev_mode)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
