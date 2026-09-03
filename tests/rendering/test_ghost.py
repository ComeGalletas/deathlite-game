"""Ghost silhouettes: a character behind obstacle art is drawn again through
it, translucent and clipped to the covering art; one in front is not; a
kind the data does not list never ghosts; alpha 0 turns the pass off.
(`documentation/sprite_functionality.md`, the proposal at the end.)"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.content import get_content
from tests import worlds as W
from tests.rendering.test_depth_sort import fresh_playing

SEED = W.SEEDS[0]


def _tree(gm, kind="tree"):
    """An obstacle of `kind` with a baked skin, and its art rect."""
    for i, o in enumerate(gm.obstacles):
        if o.kind == kind and i in gm._art_rects:
            return i, o, gm._art_rects[i]
    raise AssertionError(f"no skinned {kind}")


def _character_frame(w=40, h=60):
    f = pygame.Surface((w, h), pygame.SRCALPHA)
    f.fill((200, 40, 40, 255))
    return f


class GhostPassTests(unittest.TestCase):
    def setUp(self):
        self.gm = W.baked(SEED)
        self.r = self.gm.renderer
        self.cam = SimpleNamespace(pos=pygame.Vector2(0, 0), zoom=1.0)
        self.gm._render_zoom = 1.0
        self.surface = pygame.Surface((512, 512))     # a tree's art is up to 192 x 256

    def _run(self, frame, dest, character_y):
        self.r.begin_frame()
        self.surface.fill((0, 0, 0))
        self.r.record_character(frame, dest, character_y)
        return self.r.ghost_pass(self.surface, self.cam)

    def _lone_tree(self):
        """A synthetic map with one skinned tree: art 80 x 120 world px,
        anchored so the trunk foot is at the obstacle (100, 100)."""
        from entities.obstacle import Obstacle
        from world.map import GameMap
        gm = GameMap.__new__(GameMap)
        gm.__dict__["_obstacles"] = [Obstacle("tree", 100, 100)]
        gm._render_zoom = 1.0
        gm._blit_cache = {}
        gm.__dict__["terrain"] = None
        gm.__dict__["layout"] = None
        r = gm.renderer
        # baked containers straight on the map (the `_baked` setters would
        # build a BakedTerrain; a bare dict is what the pass reads)
        gm.terrain = type("T", (), {})()
        gm.terrain.tree_shadows = {}
        gm.terrain.art_rects = {0: (60.0, -10.0, 80.0, 120.0)}
        gm.terrain.ghost = {"alpha": 110, "kinds": ["tree"]}
        return gm, r

    def test_a_body_behind_a_tree_is_ghosted_only_under_its_crown(self):
        gm, r = self._lone_tree()
        cam = SimpleNamespace(pos=pygame.Vector2(0, 0), zoom=1.0)
        surface = pygame.Surface((256, 256))
        frame = _character_frame(40, 60)
        # the body's top half under the art (art spans y -10..110), its
        # bottom half past the art's bottom edge; behind the trunk (Y 90 < 100)
        dest = (80, 80)
        r.begin_frame()
        r.record_character(frame, dest, 90.0)
        self.assertEqual(r.ghost_pass(surface, cam), 1)
        inside = surface.get_at((100, 90))                 # under the art
        outside = surface.get_at((100, 130))               # past its bottom edge
        self.assertGreater(inside.r, 0, "no ghost under the crown")
        self.assertLess(inside.r, 200, "the ghost is not translucent")
        self.assertEqual(outside, (0, 0, 0, 255), "ghost leaked outside the art")
        self.assertEqual(surface.get_at((10, 10)), (0, 0, 0, 255))

    def test_a_body_in_front_of_the_tree_is_not_ghosted(self):
        gm, r = self._lone_tree()
        cam = SimpleNamespace(pos=pygame.Vector2(0, 0), zoom=1.0)
        surface = pygame.Surface((256, 256))
        r.begin_frame()
        r.record_character(_character_frame(40, 60), (80, 80), 110.0)   # Y past the trunk
        self.assertEqual(r.ghost_pass(surface, cam), 0)
        self.assertEqual(surface.get_at((100, 90)), (0, 0, 0, 255))

    def test_on_a_real_world_every_covering_tree_ghosts_once(self):
        i, o, (ax, ay, aw, ah) = _tree(self.gm)
        self.cam.pos = pygame.Vector2(ax - 40, ay - 40)
        dest = (40 + aw // 2 - 20, 40 + ah - 30)
        blits = self._run(_character_frame(), dest, o.pos.y - 5.0)
        self.assertGreaterEqual(blits, 1)               # this tree, plus any grove mates
        inside = self.surface.get_at((dest[0] + 20, dest[1] + 10))
        self.assertGreater(inside.r, 0)
        self.assertLess(inside.r, 200)

    def test_a_kind_the_data_does_not_list_never_ghosts(self):
        kinds = get_content().terrain["obstacle_decor"]["ghost"]["kinds"]
        self.assertNotIn("sign", kinds)
        try:
            i, o, (ax, ay, aw, ah) = _tree(self.gm, "sign")
        except AssertionError:
            self.skipTest("no skinned sign on this seed")
        self.cam.pos = pygame.Vector2(ax - 40, ay - 40)
        dest = (40 + aw // 2 - 10, 40 + ah - 30)
        self.assertEqual(self._run(_character_frame(20, 40), dest, o.pos.y - 5.0), 0)

    def test_alpha_zero_turns_the_pass_off(self):
        i, o, (ax, ay, aw, ah) = _tree(self.gm)
        saved = self.gm._ghost
        try:
            self.gm._ghost = {"alpha": 0, "kinds": ["tree"]}
            self.cam.pos = pygame.Vector2(ax - 40, ay - 40)
            dest = (40 + aw // 2 - 20, 40 + ah - 30)
            self.assertEqual(self._run(_character_frame(), dest, o.pos.y - 5.0), 0)
            self.assertEqual(self.r._ghost_queue, [])           # nothing even recorded
        finally:
            self.gm._ghost = saved

    def test_the_ghost_is_the_drawn_frame_and_cached_by_identity(self):
        frame = _character_frame()
        a = self.r._ghost_of(frame, 110)
        b = self.r._ghost_of(frame, 110)
        self.assertIs(a, b)
        self.assertEqual(a.get_at((5, 5)).a, 110)
        self.assertEqual(frame.get_at((5, 5)).a, 255)             # the source untouched
        self.assertIsNot(self.r._ghost_of(frame, 60), a)

    def test_a_shaded_body_keeps_its_own_pixels_in_the_ghost(self):
        """Two bodies of one frame size, the first under the tree, the second
        drawn later through the same shade scratch: the first's ghost must
        be its own colour, not the second's."""
        gm, r = self._lone_tree()
        cam = SimpleNamespace(pos=pygame.Vector2(0, 0), zoom=1.0)
        surface = pygame.Surface((256, 256))
        red = _character_frame(40, 60)
        blue = pygame.Surface((40, 60), pygame.SRCALPHA); blue.fill((40, 40, 200, 255))
        r.begin_frame()
        # the way the run records a shaded body: a copy, not cacheable
        r.record_character(red.copy(), (80, 80), 90.0, cacheable=False)
        r.record_character(blue.copy(), (200, 200), 90.0, cacheable=False)
        self.assertEqual(r.ghost_pass(surface, cam), 1)
        px = surface.get_at((100, 90))
        self.assertGreater(px.r, px.b, "the ghost took another body's pixels")

    def test_the_art_index_holds_only_listed_kinds(self):
        index = self.r._art_index()
        kinds = set(get_content().terrain["obstacle_decor"]["ghost"]["kinds"])
        seen = {self.gm.obstacles[i].kind for cell in index.values() for i, _r in cell}
        self.assertTrue(seen)
        self.assertTrue(seen <= kinds, seen - kinds)


class RunIntegrationTests(unittest.TestCase):
    def test_an_enemy_behind_a_tree_ghosts_in_a_real_frame(self):
        _game, p = fresh_playing()
        gm = p.game_map
        i, o, (ax, ay, aw, ah) = _tree(gm)
        # stand the enemy just behind the trunk, the hero far away
        p.player.pos.update(o.pos.x - 400, o.pos.y)
        p.camera.snap_to(o.pos)
        e = p._spawn_enemy("chaser", at=pygame.Vector2(o.pos.x, o.pos.y - 12))
        r = gm.renderer
        p.draw(_game.screen)
        self.assertGreater(len(r._ghost_queue), 0)
        # the pass ran inside draw(); run it again on a scratch to count
        scratch = pygame.Surface(_game.screen.get_size())
        self.assertGreaterEqual(r.ghost_pass(scratch, p.camera), 1)


if __name__ == "__main__":
    unittest.main()
