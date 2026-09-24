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
from game.states.playing.core.state import PlayingState
from tests import worlds as W
from tools.verification import world_digest as digest

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
        self.assertIn("warming the animations", labels)
        gm = p.game_map
        before = len(gm._blit_cache)
        self.assertGreater(before, 20, "the loading screen warmed nothing")
        # Foam and decor pick their frame from `TerrainRenderer.seconds()`, so a
        # run's first frame lands on an arbitrary phase. It used to be pinned
        # here to a phase the ring covered, because any other one still scaled
        # a few frames; since RND-005 every animation frame is warm, so the
        # first draw at *any* phase -- these include ones no ring pass drew --
        # adds nothing at all.
        for phase in (0.0, 0.13, 0.5, 2.9, 7.77):
            gm.renderer.clock = lambda t=phase: t
            p.draw(game.screen)
            self.assertEqual(len(gm._blit_cache), before,
                             f"a first frame at phase {phase} still filled the cache")
        pygame.quit()

    def test_every_frame_but_the_bands_is_warm_before_the_run_starts(self):
        """RND-005: the loading screen scales every surface the renderer can
        show except the terrace bands -- all foam, bridge, decor, obstacle and
        shadow frames, not only the ones the warm ring drew. The bands are
        left to first sight by the owner's call (RND-005.D1)."""
        from world.terrain.warm import scaled_sources

        game = _game()
        game.state_machine.change(LoadingState(game), seed=SEED)
        _drive(game)
        gm = game.state_machine.current.game_map
        sources = scaled_sources(gm)
        self.assertGreater(len(sources), 100, "the world holds almost nothing to warm")
        cold = [s for s in sources if id(s) not in gm._blit_cache]
        self.assertEqual(cold, [], f"{len(cold)} of {len(sources)} surfaces left cold")
        bands = {id(s) for _b, s, _l in gm._grid_surfs}
        self.assertFalse(bands & {id(s) for s in sources},
                         "the bands are not part of the warm set (D1)")
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
