"""Depth-sorted render layer: obstacles + interior decorations + characters are
painted back-to-front by ground-contact Y, so a character with a smaller Y than
an obstacle is drawn behind it (hidden by e.g. a tree canopy)."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState
from world.map import GameMap
from game import config



# LD-9: this module covers the **LD-8 world model** -- grown room shapes,
# corridors, cliff bands, one `floor` per room. `config.HEIGHTMAP_ROOMS`
# defaults on now and selects a different generator entirely, whose rooms are
# height maps with overlapping bounding rects and no cliff band. Pin the flag
# off here so this coverage keeps testing the path it was written for; the
# height-map path has its own in `tests/world/test_elevation.py`.
_SAVED_HEIGHTMAP = None


def _pin_heightmap_off():
    global _SAVED_HEIGHTMAP
    _SAVED_HEIGHTMAP = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = False


def _restore_heightmap():
    config.HEIGHTMAP_ROOMS = _SAVED_HEIGHTMAP


def fresh_playing():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    p = game.state_machine.current
    assert isinstance(p, PlayingState)
    return game, p


class SceneryDrawablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_one_entry_per_visible_obstacle_keyed_by_its_y(self):
        from systems.camera import Camera
        gm = GameMap(seed=1234)
        gm._build_tiles()
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.center)
        view = cam.visible_rect().inflate(320, 320)
        want = {round(o.pos.y) for o in gm.obstacles
                if view.collidepoint(o.pos.x, o.pos.y)}
        got = {round(y) for y, fn in gm.renderer.scenery_drawables(cam)}
        self.assertTrue(want)
        self.assertTrue(want.issubset(got), "an in-view obstacle is missing a drawable")

    def test_drawables_are_callable_with_a_surface(self):
        from systems.camera import Camera
        gm = GameMap(seed=7)
        gm._build_tiles()
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.center)
        surf = pygame.Surface((320, 240))
        for _y, fn in gm.renderer.scenery_drawables(cam):
            fn(surf)                                # must not raise

    def test_tree_shade_is_sorted_by_tree_depth_before_its_owner(self):
        from systems.camera import Camera
        gm = GameMap(seed=7)
        gm._build_tiles()
        tree_idx = next(iter(gm._tree_shadows))
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.obstacles[tree_idx].pos)

        shadow_owner = {id(shadow): i for i, shadow in gm._tree_shadows.items()}
        calls = []
        # Patched on the renderer, which is where the drawing lives.
        # `GameMap` used to carry a forwarder for each of these and
        # `TerrainRenderer` called back through it to reach its own methods, so
        # patching the map worked by accident; the round trip is gone.
        gm.renderer._draw_one_tree_shadow = (
            lambda _surface, _camera, shadow:
            calls.append(("shadow", shadow_owner[id(shadow)])))
        gm.renderer._draw_one_obstacle = (
            lambda _surface, _camera, i, _obstacle: calls.append(("obstacle", i)))

        drawables = sorted(gm.renderer.scenery_drawables(cam), key=lambda item: item[0])
        for _depth, draw in drawables:
            draw(None)

        shadow_pos = calls.index(("shadow", tree_idx))
        owner_pos = calls.index(("obstacle", tree_idx))
        self.assertLess(shadow_pos, owner_pos)
        tree_y = gm.obstacles[tree_idx].pos.y
        for position, (kind, i) in enumerate(calls):
            if kind != "obstacle" or i == tree_idx:
                continue
            if gm.obstacles[i].pos.y < tree_y - 0.01:
                self.assertLess(position, shadow_pos)
            elif gm.obstacles[i].pos.y > tree_y:
                self.assertGreater(position, shadow_pos)

    def test_no_layout_returns_empty(self):
        from systems.camera import Camera
        gm = GameMap()                              # one big room, no procedural obstacles
        cam = Camera(gm.width, gm.height)
        self.assertEqual(gm.renderer.scenery_drawables(cam), [])


class DepthOrderTests(unittest.TestCase):
    def test_items_sorted_by_ground_contact_y(self):
        game, p = fresh_playing()
        try:
            # a couple of enemies so the layer has >1 entry regardless of which
            # room the random seed drops the player in
            p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(120, 30))
            p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(-90, -40))
            ys = [y for y, _ in p._depth_items()]
            self.assertEqual(ys, sorted(ys))
            self.assertGreater(len(ys), 1)
        finally:
            pygame.quit()

    def test_player_rank_follows_the_player_y(self):
        game, p = fresh_playing()
        try:
            obst = p.game_map.obstacles
            self.assertTrue(obst)
            oys = sorted(o.pos.y for o in obst)
            below_all = oys[-1] + 500          # player lower on the map than every obstacle
            above_all = oys[0] - 500           # player higher than every obstacle

            p.player.pos.y = below_all
            items = p._depth_items()
            player_idx = next(i for i, (_, fn) in enumerate(items)
                              if getattr(fn, "__func__", None) is PlayingState._draw_player)
            self.assertEqual(player_idx, len(items) - 1, "player should paint last (in front)")

            p.player.pos.y = above_all
            items = p._depth_items()
            player_idx = next(i for i, (_, fn) in enumerate(items)
                              if getattr(fn, "__func__", None) is PlayingState._draw_player)
            self.assertEqual(player_idx, 0, "player should paint first (behind)")
        finally:
            pygame.quit()

    def test_draw_runs_clean_after_the_split(self):
        game, p = fresh_playing()
        try:
            for _ in range(8):
                game.state_machine.update(1 / 120)
            p.draw(game.screen)                     # must not raise
        finally:
            pygame.quit()

    def test_render_pipeline_order(self):
        game, p = fresh_playing()
        try:
            order = []
            p._draw_player_projectiles = lambda s: order.append("weapon_fx")
            p._draw_depth_layer = lambda s: order.append("depth")
            p._draw_hostile_projectiles = lambda s: order.append("hostile")
            p.draw(game.screen)
            # Tree shades are now inside depth; enemy shots remain on top.
            self.assertLess(order.index("weapon_fx"), order.index("depth"))
            self.assertLess(order.index("depth"), order.index("hostile"))
        finally:
            pygame.quit()


class ConeWeaponVisualTests(unittest.TestCase):
    """The reaping-arc weapons (Soul Scythe) hit a circular *sector*; the drawn
    range must be that sector, not a full circle -- matching `_in_cone`."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _proj(self, cx, cy, r=60, half_deg=55, dir=(1, 0)):
        import math
        from game.states.playing_state import PlayingState

        class P:
            radius = r
            color = (200, 120, 255)
            cone_half_angle = math.radians(half_deg)
            cone_dir = pygame.Vector2(*dir)
        surf = pygame.Surface((2 * cx, 2 * cy))
        surf.fill((0, 0, 0))
        PlayingState._draw_cone(surf, cx, cy, P())
        return surf

    def test_pixels_inside_the_arc_are_painted_outside_are_not(self):
        import math
        cx = cy = 120
        surf = self._proj(cx, cy, r=80, half_deg=50, dir=(1, 0))
        painted = lambda a, dist: surf.get_at(
            (int(cx + math.cos(a) * dist), int(cy + math.sin(a) * dist)))[:3] != (0, 0, 0)
        # along the aim, well inside the radius -> painted
        self.assertTrue(painted(0.0, 40))
        # 30 deg off-aim (< 50 half-angle) -> painted
        self.assertTrue(painted(math.radians(30), 40))
        # 80 deg off-aim (> 50) -> NOT painted  (a circle would paint here)
        self.assertFalse(painted(math.radians(80), 40))
        # directly behind the apex -> NOT painted
        self.assertFalse(painted(math.pi, 40))
        # beyond the radius along the aim -> NOT painted
        self.assertFalse(painted(0.0, 95))

    def test_cone_apex_is_the_projectile_position(self):
        cx = cy = 100
        surf = self._proj(cx, cy, r=50, half_deg=40, dir=(0, 1))
        # the wedge points down (+y); a point just below the apex is painted,
        # a point just above (opposite the cone) is not
        self.assertNotEqual(surf.get_at((cx, cy + 20))[:3], (0, 0, 0))
        self.assertEqual(surf.get_at((cx, cy - 20))[:3], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()


def setUpModule():
    _pin_heightmap_off()


def tearDownModule():
    _restore_heightmap()
