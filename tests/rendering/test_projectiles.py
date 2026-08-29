"""The per-family projectile draw package (`game/states/playing/projectiles/`):
the `@style` registry, `classify()`, the animated `orbit` flame, and the `cone`
reaping sector + `soul_slash` sprite.
"""
import math
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import Assets, reset_assets
from game.states.playing.projectiles import (
    DrawCtx, classify, draw_projectile, registered)
from game.states.playing.projectiles import cone as cone_mod
from game.states.playing.projectiles.orbit import orbit


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


class RegistryTests(unittest.TestCase):
    def test_every_family_is_registered(self):
        self.assertEqual(set(registered()), {"bolt", "arrow", "cone", "orbit", "melee"})

    def test_classify_routes_by_the_projectile_fields(self):
        cone = SimpleNamespace(cone_half_angle=0.5, orbit_speed=0.0, anchor=None)
        orb = SimpleNamespace(cone_half_angle=0.0, orbit_speed=3.2, anchor=object())
        plain = SimpleNamespace(cone_half_angle=0.0, orbit_speed=0.0, anchor=None)
        self.assertEqual(classify(cone, "bolt"), "cone")
        self.assertEqual(classify(orb, "bolt"), "orbit")
        self.assertEqual(classify(plain, "bolt"), "bolt")
        self.assertEqual(classify(plain, "arrow"), "arrow")   # hostile default


class OrbitFlameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        self.a = Assets()
        self.surf = pygame.Surface((160, 160), pygame.SRCALPHA)
        self.p = SimpleNamespace(orbit_angle=1.0, orbit_speed=3.2,
                                 color=(255, 150, 70), radius=8)
        self.ctx = DrawCtx(self.a, now=0.5, zoom=1.0)

    def test_orbit_asks_the_ember_rig_for_a_rotated_frame(self):
        seen = []
        real = self.a.frame_rotated
        self.a.frame_rotated = lambda *ar, **kw: (seen.append(ar), real(*ar, **kw))[1]
        orbit(self.surf, 80, 80, self.p, self.ctx)
        self.assertTrue(seen, "orbit style never called frame_rotated")
        self.assertEqual(seen[0][:2], ("ember", "loop"))

    def test_orbit_falls_back_to_a_disc_when_the_sprite_is_missing(self):
        self.a.frame_rotated = lambda *ar, **kw: None      # rig / sheet absent
        circles = []
        real = pygame.draw.circle
        pygame.draw.circle = lambda *ar, **kw: circles.append(ar[:3])
        try:
            orbit(self.surf, 80, 80, self.p, self.ctx)
        finally:
            pygame.draw.circle = real
        self.assertTrue(circles, "no disc fallback drawn")

    def test_frame_index_follows_the_run_clock(self):
        # 18 fps, 16 frames -> t=0 is frame 0, t=0.5 is frame 9
        fps = self.a.fps("ember", "loop")
        n = self.a.frame_count("ember", "loop")
        want = int(0.5 * fps) % n
        got = []
        self.a.frame_rotated = lambda rig, an, idx, deg, **kw: got.append(idx)
        orbit(self.surf, 80, 80, self.p, DrawCtx(self.a, now=0.5, zoom=1.0))
        self.assertEqual(got, [want])


class ConeSlashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        self.a = Assets()
        self.surf = pygame.Surface((240, 240), pygame.SRCALPHA)
        self.p = SimpleNamespace(cone_half_angle=math.radians(55),
                                 cone_dir=pygame.Vector2(1, 0),
                                 radius=74, color=(200, 120, 255))
        self.ctx = DrawCtx(self.a, now=0.0, zoom=1.0)

    def test_sector_alphas_are_dimmed_35_percent(self):
        self.assertEqual((cone_mod._FILL_A, cone_mod._EDGE_A),
                         (round(70 * 0.65), round(210 * 0.65)))

    def test_cone_draws_the_sector_and_asks_for_the_soul_slash_frame(self):
        cone_calls, fr_calls = [], []
        real_dc, real_fr = cone_mod.draw_cone, self.a.frame_rotated
        cone_mod.draw_cone = lambda *a, **k: cone_calls.append(a)
        self.a.frame_rotated = lambda *a, **k: (fr_calls.append(a), real_fr(*a, **k))[1]
        try:
            cone_mod.cone(self.surf, 120, 120, self.p, self.ctx)
        finally:
            cone_mod.draw_cone = real_dc
        self.assertTrue(cone_calls, "the damage sector is no longer drawn")
        self.assertTrue(fr_calls, "the slash sprite was not requested")
        self.assertEqual(fr_calls[0][:2], ("soul_slash", "loop"))
        # heading follows cone_dir (here +x -> 0 deg)
        self.assertAlmostEqual(fr_calls[0][3], 0.0, places=3)

    def test_cone_only_when_the_slash_rig_is_absent(self):
        self.a.scale_for = lambda rig: None            # rig / sheet missing
        fr_calls = []
        self.a.frame_rotated = lambda *a, **k: fr_calls.append(a)
        cone_calls = []
        real_dc = cone_mod.draw_cone
        cone_mod.draw_cone = lambda *a, **k: cone_calls.append(a)
        try:
            cone_mod.cone(self.surf, 120, 120, self.p, self.ctx)
        finally:
            cone_mod.draw_cone = real_dc
        self.assertTrue(cone_calls, "sector still draws without the sprite")
        self.assertEqual(fr_calls, [], "should not touch frame_rotated with no rig")

    def test_slash_frame_index_follows_the_run_clock(self):
        fps = self.a.fps("soul_slash", "loop")
        n = self.a.frame_count("soul_slash", "loop")
        want = int(0.5 * fps) % n
        got = []
        self.a.frame_rotated = lambda rig, an, idx, deg, **kw: got.append(idx)
        cone_mod.cone(self.surf, 120, 120, self.p, DrawCtx(self.a, now=0.5, zoom=1.0))
        self.assertEqual(got, [want])


if __name__ == "__main__":
    unittest.main()
