"""The render fixes from the fluidity plan: the actor pass draws only what
the view can reach, the tree-shade pass consults an index instead of the
world, the shade scratch surfaces are reused, and the hit tint is cached."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.states.playing import rendering
from tests import worlds as W
from tests.rendering.test_depth_sort import fresh_playing
from world.map import GameMap


class ActorCullTests(unittest.TestCase):
    def test_far_enemies_are_not_in_the_actor_pass(self):
        _game, p = fresh_playing()
        near = p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(120, 0))
        far = p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(
            config.SCREEN_WIDTH / config.CAMERA_ZOOM + 2 * config.RENDER_ACTOR_CULL_PAD + 300, 0))
        edge = p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(
            config.SCREEN_WIDTH / config.CAMERA_ZOOM / 2 + config.RENDER_ACTOR_CULL_PAD - 40, 0))
        ys = [d for _lvl, d, _f in p._actor_items()]
        self.assertIn(near.pos.y, ys)
        self.assertIn(edge.pos.y, ys)
        # the far one shares a y with the others; count instead
        self.assertEqual(len(p._actor_items()), 3)        # near, edge, the player
        self.assertEqual(len(p.enemies), 3)
        self.assertTrue(all(fn is not None for _l, _d, fn in p._actor_items()))
        p.draw(p.game.screen)                              # the pass still runs clean

    def test_the_player_is_always_in_the_pass(self):
        _game, p = fresh_playing()
        self.assertEqual(len(p._actor_items()), 1)


class ShadeIndexTests(unittest.TestCase):
    def _gm(self, shadows):
        gm = GameMap.__new__(GameMap)
        gm._tree_shadows = shadows
        gm._render_zoom = 1.0
        gm._blit_cache = {}
        return gm

    def _shade(self, r=2):
        s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        s.fill((12, 18, 22, 128))
        return s

    def test_the_index_holds_each_shadow_in_every_cell_it_touches(self):
        cell = 256
        gm = self._gm({0: (10.0, 10.0, 4, self._shade(4)),          # one cell
                       1: (cell - 2.0, 300.0, 6, self._shade(6))})  # straddles x
        idx = gm.renderer._shadow_index()
        self.assertEqual({k for k, v in idx.items() if gm._tree_shadows[0] in v}, {(0, 0)})
        self.assertEqual({k for k, v in idx.items() if gm._tree_shadows[1] in v}, {(0, 1), (1, 1)})

    def test_a_character_far_from_every_tree_is_returned_untouched(self):
        gm = self._gm({0: (2000.0, 2000.0, 8, self._shade(8))})
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        frame.set_at((1, 1), (240, 240, 240, 255))
        cam = SimpleNamespace(pos=pygame.Vector2())
        self.assertIs(gm.renderer.shade_character_frame(frame, (0, 0), cam, 5.0), frame)

    def test_shading_matches_the_old_whole_world_walk(self):
        """Random characters on a real baked world: the indexed pass darkens
        exactly the characters the exhaustive walk darkens."""
        gm = W.baked(W.SEEDS[0])
        r = gm.renderer
        cam = SimpleNamespace(pos=pygame.Vector2(0, 0))
        frame = pygame.Surface((40, 60), pygame.SRCALPHA)
        frame.fill((200, 200, 200, 255))
        import random
        rng = random.Random(3)
        shadows = list(gm._tree_shadows.values())
        checked = darkened = 0
        for _ in range(300):
            wx, wy, _r, _s = rng.choice(shadows)
            dest = (wx + rng.uniform(-120, 120), wy + rng.uniform(-120, 120))
            cy = dest[1] + 60
            got = r.shade_character_frame(frame, dest, cam, cy)
            # exhaustive: does any shadow with wy <= cy intersect the frame?
            fr = frame.get_rect(topleft=(int(dest[0]), int(dest[1])))
            hit = any(cy >= sy - 0.01 and fr.colliderect(
                pygame.Rect(round(sx - sr), round(sy - sr), 2 * sr, 2 * sr))
                for sx, sy, sr, _ in shadows)
            self.assertEqual(got is not frame, hit)
            checked += 1
            darkened += got is not frame
        self.assertGreater(darkened, 30)
        self.assertLess(darkened, checked)

    def test_scratch_surfaces_are_reused_and_cleared(self):
        gm = self._gm({0: (2.0, 2.0, 2, self._shade(2))})
        cam = SimpleNamespace(pos=pygame.Vector2())
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        frame.set_at((1, 1), (240, 240, 240, 255))
        a = gm.renderer.shade_character_frame(frame, (0, 0), cam, 2.0)
        b = gm.renderer.shade_character_frame(frame, (0, 0), cam, 2.0)
        self.assertIs(a, b)                                   # the same scratch
        self.assertEqual(a.get_at((0, 0)).a, 0)               # cleared between uses
        self.assertLess(a.get_at((1, 1)).r, 240)


class HitTintCacheTests(unittest.TestCase):
    def test_the_tint_is_computed_once_per_frame_object(self):
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        frame.set_at((1, 1), (10, 10, 10, 255))
        a = rendering.hit_tinted(frame)
        b = rendering.hit_tinted(frame)
        self.assertIs(a, b)
        self.assertGreater(a.get_at((1, 1)).r, 10)
        self.assertEqual(a.get_at((0, 0)).a, 0)
        other = pygame.Surface((4, 4), pygame.SRCALPHA)
        self.assertIsNot(rendering.hit_tinted(other), a)


if __name__ == "__main__":
    unittest.main()
