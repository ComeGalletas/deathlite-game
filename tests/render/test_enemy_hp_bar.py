"""The overhead enemy health bar (journal: enemy_health_bar_journal.md).

Three rules, and every test here is one of them: nothing over an enemy at full
HP, a **fixed height** with a length set by the enemy's **maximum** HP, and no
second bar over the boss, which has the HUD's.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from tests import worlds as W

SEED = W.pinned(2)

from game import config
from game.assets import get_assets
from game.content import get_content
from game.states.playing.visual import health_bars
from game.states.playing.visual.rendering import WorldRenderer
from entities.enemy import Enemy
from systems.camera import Camera
from ui import bars

ZOOM = 1.5
SURFACE = (900, 600)
SHEET_RED = (217, 15, 30)


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


class TrackLengthTests(unittest.TestCase):
    """`native_track` -- the only place max HP becomes a length."""

    def test_a_tankier_enemy_gets_a_longer_bar(self):
        content = get_content()
        hps = sorted(float(content.enemy(e)["hp"]) for e in content.enemies)
        lengths = [health_bars.native_track(hp) for hp in hps]
        self.assertEqual(lengths, sorted(lengths))       # never shortens
        skull = health_bars.native_track(20)
        self.assertGreater(health_bars.native_track(290), skull)
        self.assertLess(health_bars.native_track(5), skull)

    def test_the_floor_and_the_ceiling_hold(self):
        self.assertEqual(health_bars.native_track(0.0),
                         config.ENEMY_HP_BAR_MIN_WIDTH)
        self.assertEqual(health_bars.native_track(1.0),
                         config.ENEMY_HP_BAR_MIN_WIDTH)
        # The director multiplies max HP by up to 2.4x over a run
        # (`spawn/budget.stat_multipliers`), so the ceiling has to hold for
        # the toughest enemy at the end of the longest run, not just for its
        # sheet value.
        self.assertEqual(health_bars.native_track(290 * 2.4),
                         config.ENEMY_HP_BAR_MAX_WIDTH)
        self.assertEqual(health_bars.native_track(10_000),
                         config.ENEMY_HP_BAR_MAX_WIDTH)

    def test_every_length_is_an_even_number_of_native_px(self):
        # Not cosmetic: `ui/bars/meters` keys its cache on the width, so an
        # odd px would double the number of bars a crowd puts in it.
        for hp in range(1, 400, 7):
            self.assertEqual(health_bars.native_track(hp) % 2, 0, hp)


class BarArtTests(unittest.TestCase):
    """The bar built out of the hex family."""

    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def setUp(self):
        bars.clear_cache()
        health_bars.clear_cache()

    def _bar(self, max_hp, fraction=0.5):
        return health_bars._art_bar(
            self.assets, health_bars.native_track(max_hp), fraction,
            config.ENEMY_HP_BAR_SCALE)

    def test_height_is_fixed_and_only_the_length_moves(self):
        small, large = self._bar(5), self._bar(290)
        self.assertIsNotNone(small)
        self.assertEqual(small.get_height(), large.get_height())
        self.assertGreater(large.get_width(), small.get_width())
        # The whole difference is track, not housing.
        self.assertEqual(
            large.get_width() - small.get_width(),
            (health_bars.native_track(290) - health_bars.native_track(5))
            * config.ENEMY_HP_BAR_SCALE)

    def test_an_almost_dead_enemy_still_shows_a_sliver(self):
        """The hero's bar drops its fill rather than overstate a sliver; on a
        22-px enemy track that same rule would blank the bar for the last
        fifth of the enemy's life, which is the fifth worth seeing."""
        bar = self._bar(5, fraction=0.02)
        found = any(tuple(bar.get_at((x, y)))[:3] == SHEET_RED
                    for x in range(bar.get_width())
                    for y in range(bar.get_height()))
        self.assertTrue(found, "a live enemy's bar drew no fill at all")

    def test_the_art_sits_centred_in_its_surface(self):
        """The frameless bar keeps the housing's inset, so `draw` can centre
        the surface and have the track land centred on the enemy."""
        bar = self._bar(87)
        ink = bar.get_bounding_rect()
        self.assertEqual(ink.left, bar.get_width() - ink.right)


class _Enemy:
    """Only the parts of an `Enemy` the bar reads."""

    def __init__(self, x, y, hp, max_hp, radius=12.0, anim=None):
        self.pos = pygame.Vector2(x, y)
        self.hp, self.max_hp, self.radius = hp, max_hp, radius
        self.anim = anim


class DrawTests(unittest.TestCase):
    """Where the bar lands, and when it is drawn at all."""

    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        bars.clear_cache()
        health_bars.clear_cache()
        camera = Camera(4000, 4000, zoom=ZOOM)
        camera.pos = pygame.Vector2(0, 0)
        self.ps = SimpleNamespace(
            run=SimpleNamespace(camera=camera),
            game=SimpleNamespace(assets=get_assets()))
        self.renderer = WorldRenderer(self.ps)

    def _draw(self, e):
        surface = pygame.Surface(SURFACE, pygame.SRCALPHA)
        health_bars.draw(surface, self.renderer, e)
        return surface

    def test_a_full_health_enemy_draws_nothing(self):
        surface = self._draw(_Enemy(300, 300, hp=40, max_hp=40))
        self.assertEqual(surface.get_bounding_rect().size, (0, 0))

    def test_a_hurt_enemy_draws_a_bar(self):
        surface = self._draw(_Enemy(300, 300, hp=39.5, max_hp=40))
        self.assertNotEqual(surface.get_bounding_rect().size, (0, 0))

    def test_the_bar_is_centred_over_the_enemy_and_clear_of_its_head(self):
        e = _Enemy(300, 300, hp=20, max_hp=40, radius=12.0)
        ink = self._draw(e).get_bounding_rect()
        sx, sy = self.ps.run.camera.world_to_screen(e.pos)
        # No rig: the collider is the body, and the bar hangs a gap above it.
        head = sy - e.radius * ZOOM
        gap = config.ENEMY_HP_BAR_GAP * config.ENEMY_HP_BAR_SCALE
        self.assertAlmostEqual(ink.centerx, round(sx), delta=1)
        self.assertAlmostEqual(ink.bottom, round(head - gap), delta=1)
        self.assertLess(ink.bottom, head)

    def test_a_sprited_enemy_hangs_its_bar_off_the_art_not_the_collider(self):
        skull = Enemy("skull", get_content().enemy("skull"), 300.0, 300.0)
        skull.hp = skull.max_hp * 0.5
        ink = self._draw(skull).get_bounding_rect()
        sx, sy = self.ps.run.camera.world_to_screen(skull.pos)
        lift = health_bars.rig_lift(get_assets(), "skull")
        head = sy - lift * ZOOM + self.renderer.sprite_drop(skull.radius)
        gap = config.ENEMY_HP_BAR_GAP * config.ENEMY_HP_BAR_SCALE
        self.assertAlmostEqual(ink.bottom, round(head - gap), delta=1)
        # ... and that really is higher up than the collider-only placement.
        self.assertLess(head, sy - skull.radius * ZOOM)

    def test_the_lift_is_measured_off_the_art_not_the_rig_box(self):
        """A rig's declared box is sized for its tallest pose -- a bear that
        rears up to swing carries 40 px of empty box over its head -- so the
        bar reads the idle art's ink instead and sits on the animal."""
        assets = get_assets()
        for rig in ("bear", "spear_goblin", "troll"):
            health_bars.clear_cache()
            self.assertLess(health_bars.rig_lift(assets, rig),
                            assets.anchor(rig)[1], rig)

    def test_an_unmeasurable_rig_falls_back_to_its_box(self):
        assets = get_assets()
        health_bars.clear_cache()
        self.assertEqual(health_bars.rig_lift(assets, "no_such_rig"),
                         assets.anchor("no_such_rig")[1])
        health_bars.clear_cache()

    def test_the_length_on_screen_follows_max_hp(self):
        weak = self._draw(_Enemy(300, 300, hp=2, max_hp=5)).get_bounding_rect()
        tank = self._draw(_Enemy(300, 300, hp=120, max_hp=290)).get_bounding_rect()
        self.assertEqual(weak.height, tank.height)
        self.assertGreater(tank.width, weak.width)

    def test_missing_art_falls_back_to_rectangles_of_the_same_height(self):
        art = self._draw(_Enemy(300, 300, hp=20, max_hp=40)).get_bounding_rect()
        with mock.patch.object(config, "ENEMY_HP_BAR_FRAME", "no_such_rig"):
            health_bars.clear_cache()
            flat = self._draw(_Enemy(300, 300, hp=20, max_hp=40)).get_bounding_rect()
        health_bars.clear_cache()
        self.assertNotEqual(flat.size, (0, 0))
        self.assertEqual(flat.height, art.height)


class BossExclusionTests(unittest.TestCase):
    """The boss has the HUD's bar and must not gain a second one. It is
    excluded structurally -- it is not a member of `run.enemies`, so the enemy
    painter never sees it -- and this is the test that says so."""

    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        from tests.boot import start_run
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        return g, start_run(g, SEED)

    def test_the_boss_draws_no_overhead_bar_but_a_hurt_enemy_does(self):
        _g, p = self._playing()
        p._spawn_enemy("skull", at=p.player.pos + pygame.Vector2(80, 0))
        e = p.enemies[-1]
        e.hp = e.max_hp * 0.5
        p._spawn_boss()
        boss = p.run.boss
        self.assertIsNotNone(boss)
        boss.hp = boss.max_hp * 0.5
        self.assertNotIn(boss, p.enemies)          # the structural reason
        p.fx.update_spawn_fx(1.0)                  # past both spawn bursts

        surface = pygame.Surface(SURFACE, pygame.SRCALPHA)
        calls = []
        with mock.patch.object(health_bars, "draw",
                               lambda s, r, body: calls.append(body)):
            p._draw_boss(surface)
            self.assertEqual(calls, [])
            p._draw_one_enemy(surface, e)
        self.assertEqual(calls, [e])
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
