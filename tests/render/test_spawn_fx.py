"""The enemy spawn burst (assets journal, "Enemy spawn burst", 2026-09-12):
the dark purple bottom row of the spawn pack as its own strip, the
`enemy_spawn` rig, the burst every spawn pushes (and a wake does not), its
size following the enemy's own sprite, and the veil that holds the body
back until the ball breaks.

Real assets; the run tests boot a real world through the loading screen.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from tests import worlds as W

SEED = W.pinned(0)

from game.assets import get_assets

FOLDER = os.path.join("assets", "effects", "spawn")
PURPLE = (82, 63, 144)          # the bottom row's mean opaque colour, measured


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


def _mean_opaque(img):
    tot = [0, 0, 0]
    n = 0
    for x in range(0, img.get_width(), 2):
        for y in range(0, img.get_height(), 2):
            r, g, b, a = img.get_at((x, y))
            if a > 128:
                tot[0] += r
                tot[1] += g
                tot[2] += b
                n += 1
    return tuple(t / max(n, 1) for t in tot), n


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def test_the_strip_is_twelve_frames_wide(self):
        w, h = pygame.image.load(os.path.join(FOLDER, "enemy_spawn.png")).get_size()
        self.assertEqual((w, h), (64 * 12, 64))
        spec = self.assets.meta["enemy_spawn"]["anims"]["burst"]
        self.assertEqual(spec["frames"], 12)
        self.assertFalse(spec["loop"])
        self.assertNotIn("row", spec)

    def test_the_strip_matches_the_script(self):
        """Exit 2 means the source has been archived away from the folder
        and `unused/` both; the strip itself is still pinned above."""
        from tools.asset_pipeline import cut_spawn_sheet
        code = cut_spawn_sheet.main(["--check"])
        if code == 2:
            self.skipTest("the source has been archived away entirely")
        self.assertEqual(code, 0)

    def test_the_strip_is_the_dark_purple_row(self):
        """Bluer than red, redder than green, and near the measured mean --
        not the bright magenta row above it (191, 86, 231)."""
        img = pygame.image.load(os.path.join(FOLDER, "enemy_spawn.png"))
        (r, g, b), n = _mean_opaque(img)
        self.assertGreater(n, 200)
        self.assertGreater(b, r)
        self.assertGreater(r, g)
        for got, want in zip((r, g, b), PURPLE):
            self.assertLess(abs(got - want), 12, (r, g, b))

    def test_every_frame_loads(self):
        for i in range(12):
            self.assertIsNotNone(self.assets.frame("enemy_spawn", "burst", i), i)

    def test_the_rig_carries_its_tuning(self):
        rig = self.assets.rig("enemy_spawn")
        self.assertEqual(rig["ring"], 50)
        self.assertEqual(rig["over_sprite"], 1.25)
        self.assertEqual(rig["reveal_frame"], 6)
        self.assertEqual(rig["anchor"], [32, 32])


class RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _playing(self, seed=SEED):
        from game.game import Game
        from game.states.menu_state import MenuState
        from tests.boot import start_run
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        return g, start_run(g, seed)

    def _spawn(self, p, eid="skull", dx=80):
        p._spawn_fx.clear()
        e = p._spawn_enemy(eid, at=p.player.pos + pygame.Vector2(dx, 0))
        self.assertIsNotNone(e)
        return e

    def test_every_spawn_pushes_one_burst_on_its_body(self):
        g, p = self._playing()
        e = self._spawn(p)
        self.assertEqual(len(p._spawn_fx), 1)
        anim, body = p._spawn_fx[0]
        self.assertIs(body, e)
        self.assertEqual((anim.rig, anim.anim), ("enemy_spawn", "burst"))
        self.assertIs(e._spawn_fx, anim)
        pygame.quit()

    def test_a_wake_is_not_a_spawn(self):
        g, p = self._playing()
        e = self._spawn(p)
        host = p.spawn.host
        rec = host.sleep(e)
        p._spawn_fx.clear()
        woken = host.wake(rec, e.pos.x, e.pos.y)
        self.assertIn(woken, p.enemies)
        self.assertEqual(p._spawn_fx, [])
        pygame.quit()

    def test_the_boss_spawns_out_of_one_too(self):
        g, p = self._playing()
        p._spawn_fx.clear()
        p.spawn.spawn_boss()
        self.assertIsNotNone(p.boss)
        self.assertEqual(len(p._spawn_fx), 1)
        self.assertIs(p._spawn_fx[0][1], p.boss)
        pygame.quit()

    def test_the_ring_follows_the_sprite_and_falls_back_to_the_collider(self):
        g, p = self._playing()
        r = p.renderer
        z = p.camera.zoom
        e = self._spawn(p)
        bw, bh = g.assets.scale_for(e.anim.rig)
        cx, cy, d = r.spawn_fx_geometry(e)
        self.assertAlmostEqual(d, 1.25 * max(bw, bh) * z, places=4)
        # centred on the drawn frame, which hangs from the feet anchor
        sx, sy = p.camera.world_to_screen(e.pos)
        flip = e._facing < 0
        ax, ay = r.anchor_for(e.anim.rig, flip)
        self.assertAlmostEqual(cx, sx - ax * z + bw * z / 2, places=4)
        self.assertAlmostEqual(cy, sy - ay * z + r.sprite_drop(e.radius) + bh * z / 2,
                               places=4)
        # a bigger rig -> a bigger ring
        big = self._spawn(p, "troll", dx=-120)
        self.assertGreater(r.spawn_fx_geometry(big)[2], d)
        # no rig -> the collider
        e.anim = None
        cx, cy, d = r.spawn_fx_geometry(e)
        self.assertAlmostEqual(d, 1.25 * 2 * e.radius * z, places=4)
        self.assertAlmostEqual(cx, sx, places=4)
        self.assertAlmostEqual(cy, sy, places=4)
        pygame.quit()

    def test_the_body_is_veiled_until_the_ball_breaks(self):
        g, p = self._playing()
        r = p.renderer
        e = self._spawn(p)
        drawn = []
        r.enemy_sprite = lambda surface, body: drawn.append(body)
        surface = pygame.Surface((320, 240))
        self.assertTrue(r.spawn_veiled(e))
        r.one_enemy(surface, e)
        self.assertEqual(drawn, [])                # hidden inside the burst
        p.fx.update_spawn_fx(5 / 20 + 1e-3)        # frame 5: still the ball
        self.assertTrue(r.spawn_veiled(e))
        p.fx.update_spawn_fx(1 / 20)               # frame 6: the ball breaks
        self.assertFalse(r.spawn_veiled(e))
        r.one_enemy(surface, e)
        self.assertEqual(drawn, [e])
        self.assertTrue(e.alive)                   # live the whole time
        pygame.quit()

    def test_the_burst_is_culled_when_it_finishes(self):
        g, p = self._playing()
        e = self._spawn(p)
        p.fx.update_spawn_fx(12 / 20 + 1e-3)
        self.assertEqual(p._spawn_fx, [])
        self.assertIsNone(e._spawn_fx)
        self.assertFalse(p.renderer.spawn_veiled(e))
        pygame.quit()

    def test_the_burst_sits_just_over_its_body_in_the_depth_pass(self):
        g, p = self._playing()
        e = self._spawn(p)
        keys = {round(y, 3) for y, _ in p._depth_items()}
        self.assertIn(round(e.pos.y + 0.5, 3), keys)
        pygame.quit()

    def test_the_burst_paints_purple_round_the_body(self):
        g, p = self._playing()
        e = self._spawn(p, dx=0)
        p.camera.snap_to(p.player.pos)
        p.fx.update_spawn_fx(9 / 20 + 1e-3)        # the widest ring
        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))
        p._draw_spawn_fx(surface, p._spawn_fx[0])
        cx, cy, d = p.renderer.spawn_fx_geometry(e)
        box = pygame.Rect(0, 0, int(d), int(d))
        box.center = (int(cx), int(cy))
        box = box.clip(surface.get_rect())
        (r, g_, b), n = _mean_opaque(surface.subsurface(box))
        self.assertGreater(n, 20)
        self.assertGreater(b, r)
        self.assertGreater(r, g_)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
