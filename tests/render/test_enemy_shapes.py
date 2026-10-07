"""RND-013: the dev menu's "Enemy shapes" switch.

With it on, a dev run draws every enemy and the boss down the primitive
branch a rig-less body always took -- the collider-sized circle in the data
colour, with its state rings -- and fetches no sprite frame for them. The HP
bar and the spawn burst follow the circle. A regular run ignores the flag,
and the switch is draw-only: a run plays out the same with it on or off.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from tests import worlds as W

SEED = W.pinned(1)

from entities.enemy import Enemy
from game.content import get_content
from game.states.playing.visual import health_bars

ALL_ENEMIES = tuple(sorted(get_content().enemies))


def _boot(dev=True):
    from game.game import Game
    from game.states.menu_state import MenuState
    from tests.boot import start_run
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    g.state_machine.change(MenuState(g))
    return g, start_run(g, SEED, dev=dev)


class _Draws:
    """Records `pygame.draw.circle` calls and asset frame fetches while
    one body is drawn."""

    def __init__(self, p):
        self.p = p

    def __enter__(self):
        assets = self.p.game.assets
        self._circle = mock.patch.object(pygame.draw, "circle", wraps=pygame.draw.circle)
        self._frame = mock.patch.object(assets, "frame", wraps=assets.frame)
        self.circle = self._circle.start()
        self.frame = self._frame.start()
        return self

    def __exit__(self, *exc):
        self._circle.stop()
        self._frame.stop()

    def circles(self):
        """`(centre, radius)` of every circle drawn."""
        return [(tuple(c.args[2]), c.args[3]) for c in self.circle.call_args_list]


def _beside(p, eid, dx=80.0):
    """A body of `eid` beside the hero, built directly: it carries no spawn
    burst, so nothing veils it, and it never enters the run."""
    pos = p.player.pos + pygame.Vector2(dx, 0)
    return Enemy(eid, get_content().enemy(eid), pos.x, pos.y)


class DevRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g, cls.p = _boot(dev=True)
        cls.surface = pygame.Surface(cls.g.screen.get_size())

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.p._dev_enemy_shapes = False
        self.p.camera.snap_to(self.p.player.pos)

    tearDown = setUp

    def _collider(self, body):
        sx, sy = self.p.camera.world_to_screen(body.pos)
        return (int(sx), int(sy)), round(body.radius * self.p.camera.zoom)

    def test_off_by_default_and_the_sprite_is_drawn(self):
        self.assertFalse(self.p.dev.enemy_shapes)
        self.assertFalse(self.p.renderer.enemy_shapes())
        e = _beside(self.p, "skull")
        with _Draws(self.p) as d:
            self.p.renderer.one_enemy(self.surface, e)
        self.assertGreater(d.frame.call_count, 0)
        self.assertNotIn(self._collider(e), d.circles())

    def test_every_enemy_draws_its_collider_circle_and_fetches_no_frame(self):
        self.p._dev_enemy_shapes = True
        self.assertTrue(self.p.renderer.enemy_shapes())
        for eid in ALL_ENEMIES:
            e = _beside(self.p, eid)
            self.assertIsNotNone(e.anim, eid)            # it has art to skip
            with _Draws(self.p) as d:
                self.p.renderer.one_enemy(self.surface, e)
            self.assertEqual(d.frame.call_count, 0, eid)
            self.assertIn(self._collider(e), d.circles(), eid)

    def test_the_shape_paints_the_data_colour_at_the_collider(self):
        self.p._dev_enemy_shapes = True
        surface = pygame.Surface(self.surface.get_size())
        surface.fill((0, 0, 0))
        e = _beside(self.p, "skull")
        self.p.renderer.one_enemy(surface, e)
        (cx, cy), _r = self._collider(e)
        self.assertEqual(tuple(surface.get_at((cx, cy)))[:3], e.color)

    def test_the_shape_keeps_the_hit_flash_and_the_state_rings(self):
        self.p._dev_enemy_shapes = True
        e = _beside(self.p, "skull")
        e.is_elite = True
        e.hit_flash = 0.1
        with _Draws(self.p) as d:
            self.p.renderer.one_enemy(self.surface, e)
        centre, r = self._collider(e)
        colours = {c.args[1] for c in d.circle.call_args_list
                   if tuple(c.args[2]) == centre and c.args[3] == r}
        self.assertIn((255, 255, 255), colours)          # the flash
        self.assertIn((centre, r + 3), d.circles())      # the elite ring

    def test_the_hp_bar_hangs_off_the_circle(self):
        p = self.p
        e = _beside(p, "troll")                          # tall art over a small collider
        z = p.camera.zoom
        _sx, sy = p.camera.world_to_screen(e.pos)
        over_art = health_bars.sprite_top(p.renderer, e, sy, z)
        p._dev_enemy_shapes = True
        self.assertAlmostEqual(health_bars.sprite_top(p.renderer, e, sy, z),
                               sy - e.radius * z)
        self.assertLess(over_art, sy - e.radius * z)     # it really moved

    def test_the_spawn_burst_wraps_the_collider(self):
        p = self.p
        e = _beside(p, "troll")
        over = float(p.game.assets.rig("enemy_spawn")["over_sprite"])
        sprited = p.renderer.spawn_fx_geometry(e)
        p._dev_enemy_shapes = True
        sx, sy = p.camera.world_to_screen(e.pos)
        cx, cy, d = p.renderer.spawn_fx_geometry(e)
        self.assertAlmostEqual(cx, sx)
        self.assertAlmostEqual(cy, sy)
        self.assertAlmostEqual(d, over * 2.0 * e.radius * p.camera.zoom)
        self.assertNotAlmostEqual(sprited[2], d)

    def test_turning_it_off_brings_the_sprite_back(self):
        p = self.p
        e = _beside(p, "skull")
        p._dev_enemy_shapes = True
        p.renderer.one_enemy(self.surface, e)            # drawn as a shape first
        p._dev_enemy_shapes = False
        with _Draws(p) as d:
            p.renderer.one_enemy(self.surface, e)
        self.assertGreater(d.frame.call_count, 0)
        self.assertNotIn(self._collider(e), d.circles())

    def test_the_whole_frame_draws_headless_with_it_on(self):
        p = self.p
        for dx in (60, -60, 0):
            p._spawn_enemy("skull", at=p.player.pos + pygame.Vector2(dx, 70),
                           owner="dev")
        p._dev_enemy_shapes = True
        p.fx.update_spawn_fx(5.0)
        p.draw(self.g.screen)                            # must not raise


class BossTests(unittest.TestCase):
    """On a run of its own: spawning the boss arms timers and phases that
    the other tests' shared run must not inherit."""

    def test_the_boss_draws_its_circle_and_ring_and_fetches_no_frame(self):
        g, p = _boot(dev=True)
        try:
            p.camera.snap_to(p.player.pos)
            p.spawn.spawn_boss()
            b = p.boss
            self.assertIsNotNone(b.anim)
            p.fx.update_spawn_fx(5.0)                    # past the burst's veil
            surface = pygame.Surface(g.screen.get_size())
            sx, sy = p.camera.world_to_screen(b.pos)
            collider = ((int(sx), int(sy)), round(b.radius * p.camera.zoom))
            p._dev_enemy_shapes = True
            with _Draws(p) as d:
                p.renderer.boss(surface)
            self.assertEqual(d.frame.call_count, 0)
            self.assertGreaterEqual(d.circles().count(collider), 2)   # body + ring
            p._dev_enemy_shapes = False
            with _Draws(p) as d:
                p.renderer.boss(surface)
            self.assertGreater(d.frame.call_count, 0)    # the sprite is back
        finally:
            pygame.quit()


class RegularRunTests(unittest.TestCase):
    def test_a_regular_run_ignores_the_flag(self):
        g, p = _boot(dev=False)
        try:
            p._dev_enemy_shapes = True                   # set behind the menu's back
            self.assertFalse(p.renderer.enemy_shapes())
            e = _beside(p, "skull")
            with _Draws(p) as d:
                p.renderer.one_enemy(pygame.Surface(g.screen.get_size()), e)
            self.assertGreater(d.frame.call_count, 0)
        finally:
            pygame.quit()


class DrawOnlyTests(unittest.TestCase):
    """The switch changes pixels and nothing else: the same dev run, ticked
    and drawn frame by frame with it off and with it on, ends in the same
    state -- bodies, health, the hero, the run clock."""

    def _play(self, shapes: bool):
        g, p = _boot(dev=True)
        try:
            p._dev_enemy_shapes = shapes
            for i, eid in enumerate(("skull", "troll", "minotaur")):
                p._spawn_enemy(eid, at=p.player.pos + pygame.Vector2(90, 0).rotate(120 * i),
                               owner="dev")
            for _ in range(180):
                g.state_machine.update(1 / 60)
                g._render()
            return ([(e.enemy_id, round(e.pos.x, 6), round(e.pos.y, 6), round(e.hp, 6),
                      e.anim.anim, e.anim.index) for e in p.enemies],
                    (round(p.player.pos.x, 6), round(p.player.pos.y, 6), round(p.player.hp, 6)),
                    round(p.stats["time"], 6), p.stats["kills"])
        finally:
            pygame.quit()

    def test_a_run_plays_out_the_same_with_it_on(self):
        off = self._play(False)
        on = self._play(True)
        self.assertTrue(off[0])                          # there were enemies to compare
        self.assertEqual(off, on)


if __name__ == "__main__":
    unittest.main()
