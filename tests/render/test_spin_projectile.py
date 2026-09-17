"""The `spin` projectile style: a tumbling strip played on the shot's clock.

R2 of `documentation/journals/enemy_roster_expansion_journal.md`. The Gnoll's
bone and the slingshot gnome's acorn are the first projectiles in the game
whose *art* animates -- every other shot is a still (`thrown`, `arrow`) or a
drawn shape (`bolt`). The frames already carry the rotation, so the style must
not also rotate by heading, and each shot must read its own `age` so two bones
in flight are not in lockstep.

Real assets, no world.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.projectile import Projectile
from game.assets import get_assets
from game.states.playing.visual.drawctx import DrawCtx
from game.states.playing.visual.projectiles import classify, draw_projectile
from game.states.playing.visual.projectiles.spin import ANIM, frame_index


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


def _shot(rig="gnoll_bone", style="spin", age=0.0):
    p = Projectile()
    p.reset(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(120, 0), damage=5,
            radius=8, lifetime=4.0, hostile=True, style=style,
            fx={"rig": rig} if rig else None)
    p.age = age
    return p


def _lit(surface):
    surface.lock()
    n = sum(1 for y in range(surface.get_height())
            for x in range(surface.get_width()) if surface.get_at((x, y))[3] > 0)
    surface.unlock()
    return n


class FrameIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def test_the_strip_advances_with_age_and_wraps(self):
        n = self.assets.frame_count("gnoll_bone", ANIM)
        self.assertEqual(n, 4)
        fps = self.assets.fps("gnoll_bone", ANIM)
        seen = [frame_index(self.assets, "gnoll_bone", i / fps, None) for i in range(n * 2)]
        self.assertEqual(seen, list(range(n)) * 2)      # wraps, never runs off

    def test_two_shots_of_different_age_show_different_frames(self):
        """The frame comes off the projectile's own `age`, which the pool
        resets on reuse -- otherwise a volley would tumble in lockstep."""
        fps = self.assets.fps("gnoll_bone", ANIM)
        a = frame_index(self.assets, "gnoll_bone", 0.0, None)
        b = frame_index(self.assets, "gnoll_bone", 1.0 / fps, None)
        self.assertNotEqual(a, b)

    def test_an_fx_fps_overrides_the_rigs_own_rate(self):
        slow = frame_index(self.assets, "gnoll_bone", 0.5, 1.0)
        fast = frame_index(self.assets, "gnoll_bone", 0.5, 100.0)
        self.assertEqual(slow, 0)
        self.assertNotEqual(fast, 0)

    def test_a_rig_with_no_spin_strip_reports_none(self):
        self.assertIsNone(frame_index(self.assets, "skull", 0.0, None))
        self.assertIsNone(frame_index(self.assets, "no_such_rig", 0.0, None))

    def test_a_negative_age_does_not_index_backwards(self):
        self.assertEqual(frame_index(self.assets, "gnoll_bone", -5.0, None), 0)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def _draw(self, proj):
        surface = pygame.Surface((120, 120), pygame.SRCALPHA)
        ctx = DrawCtx(assets=self.assets, now=0.0, zoom=1.0)
        draw_projectile(surface, 60, 60, proj, ctx, default="arrow")
        return surface

    def test_an_explicit_style_wins_over_the_default(self):
        self.assertEqual(classify(_shot(), "arrow"), "spin")

    def test_the_bone_draws_something(self):
        self.assertGreater(_lit(self._draw(_shot())), 0)

    def test_the_acorn_draws_something(self):
        self.assertGreater(_lit(self._draw(_shot(rig="acorn"))), 0)

    def test_the_art_is_not_turned_by_the_shots_heading(self):
        """The strip already tumbles; rotating it too would spin it twice.
        Two shots travelling opposite ways must render identically."""
        right, left = _shot(), _shot()
        left.vel.update(-120, 0)
        a, b = self._draw(right), self._draw(left)
        self.assertEqual(_lit(a), _lit(b))
        self.assertEqual(pygame.image.tostring(a, "RGBA"),
                         pygame.image.tostring(b, "RGBA"))

    def test_a_missing_rig_falls_back_to_the_disc_rather_than_crashing(self):
        for rig in (None, "no_such_rig", "skull"):
            with self.subTest(rig=rig):
                self.assertGreater(_lit(self._draw(_shot(rig=rig))), 0)
