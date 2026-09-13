"""The Grave Totem bolt's look (assets journal, "Grave Totem bolt --
rework", 2026-09-12): the blue row of `proyectile.png` as its own sheets,
`fire.png` recoloured blue, the `totem_bolt` style that draws the orb with
the flame trailing it, and the burst a consuming hit plays through the
impact machinery.

Real assets, no world. The sheets are checked against the scripts that make
them so a re-cut or a re-tuned ramp can never drift from what is committed.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.projectile import Projectile
from game.assets import get_assets
from game.content import get_content
from game.states.playing.core.combat import CombatResolver
from game.states.playing.visual.drawctx import DrawCtx
from game.states.playing.visual.projectiles import draw_projectile
from game.states.playing.visual.projectiles.totem_bolt import tail_angle

FOLDER = os.path.join("assets", "effects", "weapons", "grave_totem")


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def test_the_blue_row_is_its_own_sheet(self):
        w, h = pygame.image.load(os.path.join(FOLDER, "totem_bolt_blue.png")).get_size()
        self.assertEqual((w, h), (64 * 12, 64))

    def test_the_orb_and_burst_strips_are_their_frames_wide(self):
        for anim, frames in (("orb", 6), ("burst", 6)):
            spec = self.assets.meta["totem_bolt"]["anims"][anim]
            self.assertEqual(spec["frames"], frames)
            self.assertNotIn("row", spec)
            w, h = pygame.image.load(os.path.join("assets", spec["file"])).get_size()
            self.assertEqual((w, h), (64 * frames, 64))

    def test_the_fire_sheet_is_seven_frames(self):
        spec = self.assets.meta["totem_bolt_fire"]["anims"]["loop"]
        w, h = pygame.image.load(os.path.join("assets", spec["file"])).get_size()
        self.assertEqual((w, h), (128 * spec["frames"], 128))
        self.assertEqual(spec["frames"], 7)

    def test_the_sheets_match_the_scripts(self):
        """Exit 2 from either script means its source has been archived away
        from the folder and `unused/` both; the sheets themselves are still
        pinned by the tests above."""
        from utilities import cut_totem_bolt_sheets, recolour_totem_fire
        for script in (cut_totem_bolt_sheets, recolour_totem_fire):
            with self.subTest(script=script.__name__):
                code = script.main(["--check"])
                if code == 2:
                    self.skipTest("the source has been archived away entirely")
                self.assertEqual(code, 0)

    def test_the_recoloured_flame_is_blue_everywhere(self):
        """No opaque pixel of the tail is redder than it is blue -- the ramp
        keeps the white core, but nothing orange or yellow survives."""
        img = pygame.image.load(os.path.join(FOLDER, "totem_bolt_fire.png"))
        for x in range(0, img.get_width(), 2):
            for y in range(0, img.get_height(), 2):
                r, g, b, a = img.get_at((x, y))
                if a > 8:
                    self.assertLessEqual(r, b, (x, y, (r, g, b)))

    def test_every_frame_loads(self):
        for rig, anim, n in (("totem_bolt", "orb", 6), ("totem_bolt", "burst", 6),
                             ("totem_bolt_fire", "loop", 7)):
            for i in range(n):
                self.assertIsNotNone(self.assets.frame(rig, anim, i), (rig, anim, i))

    def test_the_weapon_visual_names_the_style_and_the_burst(self):
        vis = get_content().weapon_visual("grave_totem")
        self.assertEqual(vis.style, "totem_bolt")
        self.assertEqual(vis.fx["impact"], "totem_bolt")
        self.assertEqual(vis.fx["impact_anim"], "burst")
        self.assertEqual(vis.fx["orb_px"], 24)
        self.assertEqual(vis.fx["tail_px"], 28)


def _bolt(vel=(420, 0), fx=None):
    p = Projectile()
    vis = get_content().weapon_visual("grave_totem")
    p.reset(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(*vel), damage=7, radius=6,
            lifetime=1.4, pierce=0, color=vis.color, style="totem_bolt",
            fx=dict(vis.fx) if fx is None else fx, weapon_id="grave_totem")
    p.active = True
    return p


def _ink_cols(surface):
    """Which screen columns carry any ink."""
    w, h = surface.get_size()
    return [x for x in range(w) if any(surface.get_at((x, y))[3] > 0 for y in range(0, h, 2))]


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def _draw(self, p, assets, now=0.0):
        surface = pygame.Surface((200, 120), pygame.SRCALPHA)
        draw_projectile(surface, 100, 60, p, DrawCtx(assets, now, 1.0), default="bolt")
        return surface

    def test_the_tail_trails_the_bolt_along_its_travel_line(self):
        """Flying +x: ink reaches further behind (left of) the bolt than
        ahead of it, by about the tail's length."""
        surface = self._draw(_bolt(vel=(420, 0)), get_assets())
        cols = _ink_cols(surface)
        self.assertTrue(cols)
        behind, ahead = 100 - cols[0], cols[-1] - 100
        self.assertGreater(behind, ahead + 10, (behind, ahead))
        self.assertLessEqual(ahead, 14)                        # the orb's half

    def test_flying_left_the_tail_trails_to_the_right(self):
        surface = self._draw(_bolt(vel=(-420, 0)), get_assets())
        cols = _ink_cols(surface)
        self.assertGreater(cols[-1] - 100, 100 - cols[0] + 10)

    def test_the_orb_pulses_with_the_run_clock(self):
        p = _bolt()
        a = pygame.image.tostring(self._draw(p, get_assets(), now=0.0), "RGBA")
        b = pygame.image.tostring(self._draw(p, get_assets(), now=0.25), "RGBA")
        self.assertNotEqual(a, b)

    def test_missing_rigs_fall_back_to_the_disc(self):
        p = _bolt(fx={"orb_rig": "no_such", "fire_rig": "no_such_either"})
        surface = self._draw(p, get_assets())
        cols = _ink_cols(surface)
        self.assertTrue(cols)
        self.assertLessEqual(cols[-1] - cols[0], 14)          # a 6 px disc, nothing more

    def test_tail_angle_points_away_from_travel(self):
        # Flying +x: the tail heads 180; the art points up (270) -> pass -90.
        self.assertAlmostEqual(tail_angle(pygame.Vector2(1, 0), 270.0), -90.0)
        # Flying down (+y on screen, heading 90): tail heads 270 -> pass 0.
        self.assertAlmostEqual(tail_angle(pygame.Vector2(0, 1), 270.0), 0.0)


class ImpactTests(unittest.TestCase):
    """The resolver plays `fx.impact` once when a hit consumes the bolt."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _resolver(self):
        calls = []
        ps = SimpleNamespace(_spawn_impact=lambda **kw: calls.append(kw))
        return CombatResolver(ps), calls

    def test_a_consuming_hit_bursts_where_the_bolt_stopped(self):
        res, calls = self._resolver()
        p = _bolt()
        p.pos.update(40, 50)
        p.on_hit()                                   # pierce 0 -> spent
        self.assertFalse(p.active)
        res.impact_if_spent(p)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["rig"], "totem_bolt")
        self.assertEqual(calls[0]["anim"], "burst")
        self.assertEqual(calls[0]["pos"], pygame.Vector2(40, 50))
        self.assertEqual(calls[0]["radius"], 6)
        self.assertEqual(calls[0]["weapon_id"], "grave_totem")

    def test_a_pierced_hit_draws_nothing(self):
        res, calls = self._resolver()
        p = _bolt()
        p.pierce_left = 2
        p.on_hit()
        self.assertTrue(p.active)
        res.impact_if_spent(p)
        self.assertEqual(calls, [])

    def test_a_projectile_with_no_impact_rig_draws_nothing(self):
        res, calls = self._resolver()
        p = _bolt(fx={})
        p.on_hit()
        res.impact_if_spent(p)
        self.assertEqual(calls, [])

    def test_the_burst_plays_once_through_the_impact_machinery(self):
        """`slam_fx.spawn_impact` with `anim="burst"`: queued, advances, and
        is culled when the strip has shown its last frame (6 @ 16 fps)."""
        from game.states.playing.visual import slam_fx
        ps = SimpleNamespace(game=SimpleNamespace(assets=get_assets()), _impacts=[])
        slam_fx.spawn_impact(ps, pos=(1, 2), radius=6, rig="totem_bolt", anim="burst")
        self.assertEqual(len(ps._impacts), 1)
        self.assertEqual(ps._impacts[0]["anim"].anim, "burst")
        slam_fx.update_impacts(ps, 0.2)
        self.assertEqual(len(ps._impacts), 1)
        slam_fx.update_impacts(ps, 0.3)
        self.assertEqual(ps._impacts, [])


if __name__ == "__main__":
    unittest.main()
