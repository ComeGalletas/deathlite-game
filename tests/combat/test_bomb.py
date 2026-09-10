"""Six-weapon system P1: the Bomb (design §3.6). A fused, inert throw that
lands on its target, sits, and detonates into a blast that scores through
the normal hit resolver."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from combat.weapons.bomb import landing_time
from entities.projectile import Projectile
from game.content import get_content
from game.states.playing.combat import CombatResolver
from game.states.playing.effects import TransientFx
from tests.combat.fakes import FakeEnemy, fake_ps


class _Target:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


class _Shot:
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def bomb():
    w = Weapon("bomb", get_content().weapon("bomb"))
    w._cd = 0.0
    return w


def ctx(enemies, sink, **over):
    base = dict(origin=pygame.Vector2(0, 0), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: (sink.append(_Shot(**kw)), sink[-1])[1])
    base.update(over)
    return FireContext(**base)


DATA = get_content().weapon("bomb")


class ThrowTests(unittest.TestCase):
    def test_a_throw_is_one_inert_fused_projectile(self):
        sink = []
        self.assertTrue(bomb().update(1 / 60, ctx([_Target(150, 0)], sink)))
        self.assertEqual(len(sink), 1)
        s = sink[0]
        self.assertTrue(s.inert)
        self.assertAlmostEqual(s.lifetime, DATA["fuse"])
        self.assertAlmostEqual(s.blast_radius, DATA["blast_radius"])
        self.assertAlmostEqual(s.blast_lifetime, DATA["blast_lifetime"])
        self.assertEqual(s.weapon_id, "bomb")
        self.assertAlmostEqual(s.vel.length(), DATA["projectile_speed"])

    def test_it_stops_on_a_near_target_rather_than_flying_past(self):
        sink = []
        bomb().update(1 / 60, ctx([_Target(150, 0)], sink))
        self.assertAlmostEqual(sink[0].stop_after, 150 / DATA["projectile_speed"])

    def test_a_far_target_gets_the_full_throw(self):
        sink = []
        bomb().update(1 / 60, ctx([_Target(300, 0)], sink))        # inside reach 320
        self.assertAlmostEqual(sink[0].stop_after, DATA["throw_time"])

    def test_landing_time_helper(self):
        o = pygame.Vector2()
        self.assertAlmostEqual(landing_time(o, [], 300, 0.55), 0.55)
        self.assertAlmostEqual(landing_time(o, [_Target(60, 0)], 300, 0.55), 0.2)
        self.assertEqual(landing_time(o, [_Target(60, 0)], 0, 0.55), 0.0)

    def test_extra_bombs_fan_out(self):
        sink = []
        w = bomb()
        w.bonus["projectile_count"] += 2
        w.update(1 / 60, ctx([_Target(200, 0)], sink))
        self.assertEqual(len(sink), 3)
        self.assertEqual(len({round(s.vel.y) for s in sink}), 3)

    def test_manual_throw_whiffs_into_empty_space_with_the_full_throw(self):
        from game.states.playing.aim import AimInput
        sink = []
        held = AimInput(pygame.Vector2(0, -1), "keys", held=True)
        self.assertTrue(bomb().update(1 / 60, ctx([], sink, aim=held)))
        self.assertAlmostEqual(sink[0].vel.normalize().y, -1.0)
        self.assertAlmostEqual(sink[0].stop_after, DATA["throw_time"])


class ProjectileFlightTests(unittest.TestCase):
    def _thrown(self):
        p = Projectile()
        p.active = True
        p.reset(pos=(0, 0), vel=(300, 0), damage=10, radius=8, lifetime=1.1,
                inert=True, stop_after=0.5, blast_radius=72, blast_lifetime=0.12)
        return p

    def test_it_halts_after_stop_after_and_keeps_its_fuse_running(self):
        p = self._thrown()
        for _ in range(31):                     # just past 0.5 s
            p.update(1 / 60)
        self.assertAlmostEqual(p.pos.x, 150, delta=6)
        self.assertEqual(p.vel, pygame.Vector2())
        self.assertTrue(p.active)
        for _ in range(36):                     # to ~1.12 s
            p.update(1 / 60)
        self.assertFalse(p.active)
        self.assertAlmostEqual(p.pos.x, 150, delta=6)

    def test_reset_clears_the_bomb_fields_for_the_next_shot(self):
        p = self._thrown()
        p.detonated = True
        p.reset(pos=(0, 0), vel=(1, 0), damage=1, radius=1, lifetime=1)
        self.assertFalse(p.inert)
        self.assertEqual(p.blast_radius, 0.0)
        self.assertEqual(p.stop_after, 0.0)
        self.assertFalse(p.detonated)
        self.assertEqual(p.age, 0.0)


class DetonationTests(unittest.TestCase):
    """Through `TransientFx.update_projectiles` and `CombatResolver`."""

    def _throw(self, ps):
        fx = TransientFx(ps)
        p = ps._spawn_projectile(pos=(0, 0), vel=(300, 0), damage=30, radius=8,
                                 lifetime=1.1, inert=True, stop_after=0.5,
                                 blast_radius=72, blast_lifetime=0.12,
                                 src_weight=22, weapon_id="bomb",
                                 source_tags=("ranged", "area"))
        return fx, p

    def test_a_flying_bomb_scores_no_direct_hit(self):
        e = FakeEnemy(20, 0)
        ps = fake_ps([e])
        self._throw(ps)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(e.hp, 100.0)

    def test_the_fuse_spawns_a_blast_that_damages_everything_in_radius(self):
        near, far = FakeEnemy(150, 40), FakeEnemy(150, 300)
        ps = fake_ps([near, far])
        fx, bomb_p = self._throw(ps)
        for _ in range(67):                         # 1.12 s: the fuse runs out
            fx.update_projectiles(1 / 60)
        self.assertTrue(bomb_p.detonated)
        live = [p for p in ps.projectiles if p.active]
        self.assertEqual(len(live), 1)
        blast = live[0]
        self.assertEqual(blast.style, "blast")
        self.assertAlmostEqual(blast.radius, 72)
        self.assertEqual(blast.pierce_left, 999)
        self.assertAlmostEqual(blast.pos.x, 150, delta=6)
        self.assertEqual(len(ps._explosions), 1)     # the ring visual
        CombatResolver(ps).projectile_hits()
        self.assertEqual(near.hp, 70.0)
        self.assertEqual(far.hp, 100.0)
        self.assertTrue(near.knocks, "a blast shoves like any weighted hit")

    def test_the_blast_expires_after_its_lifetime(self):
        ps = fake_ps([])
        fx, _ = self._throw(ps)
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        for _ in range(9):                          # 0.15 s > blast_lifetime
            fx.update_projectiles(1 / 60)
        self.assertEqual([p for p in ps.projectiles if p.active], [])

    def test_a_bomb_detonates_once(self):
        ps = fake_ps([])
        fx, bomb_p = self._throw(ps)
        for _ in range(80):
            fx.update_projectiles(1 / 60)
        self.assertEqual(len(ps._explosions), 1)

    def test_a_blocked_bomb_detonates_where_it_stopped(self):
        e = FakeEnemy(10, 0)
        ps = fake_ps([e], blocked=True)              # every step hits an obstacle
        fx, bomb_p = self._throw(ps)
        fx.update_projectiles(1 / 60)
        self.assertTrue(bomb_p.detonated)
        blast = [p for p in ps.projectiles if p.active and p.style == "blast"]
        self.assertEqual(len(blast), 1)
        self.assertLess(blast[0].pos.x, 10)



class BurstVisualTests(unittest.TestCase):
    """The detonation plays `effects/explosion_2.png` (the `explosion` rig's
    one-shot `burst`) for exactly the strip's length, scaled to the blast."""

    def _detonated(self):
        ps = fake_ps([])
        fx = TransientFx(ps)
        p = ps._spawn_projectile(pos=(0, 0), vel=(300, 0), damage=30, radius=8,
                                 lifetime=1.1, inert=True, stop_after=0.5,
                                 blast_radius=72, blast_lifetime=0.12,
                                 src_weight=22, weapon_id="bomb",
                                 source_tags=("ranged", "area"))
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        self.assertTrue(p.detonated)
        return ps, fx, ps._explosions[0]

    def test_the_bomb_burst_carries_the_explosion_animation(self):
        from game.assets import get_assets
        ps, fx, ex = self._detonated()
        self.assertEqual(ex["anim"].rig, "explosion")
        self.assertEqual(ex["anim"].anim, "burst")
        self.assertAlmostEqual(ex["radius"], 72)
        a = get_assets()
        self.assertEqual(a.frame_count("explosion", "burst"), 10)
        self.assertFalse(a.loops("explosion", "burst"))
        self.assertAlmostEqual(ex["dur"], 10 / a.fps("explosion", "burst"))

    def test_the_burst_advances_and_is_culled_when_the_strip_ends(self):
        ps, fx, ex = self._detonated()
        fx.update_explosions(ex["dur"] / 2)
        self.assertEqual(ex["anim"].t, ex["dur"] / 2)
        self.assertFalse(ex["anim"].finished)
        self.assertIn(ex, ps._explosions)
        fx.update_explosions(ex["dur"] / 2 + 0.001)
        self.assertTrue(ex["anim"].finished)
        self.assertNotIn(ex, ps._explosions)

    def test_the_renderer_scales_the_burst_to_the_blast_diameter(self):
        from types import SimpleNamespace
        from game.assets import get_assets
        from game.states.playing.rendering import WorldRenderer
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        ps, fx, ex = self._detonated()
        fx.update_explosions(0.2)                     # mid-burst: the widest frames
        a = get_assets()
        camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda p: (p.x + 200, p.y + 200))
        r_ps = SimpleNamespace(game=SimpleNamespace(assets=a), camera=camera,
                               _explosions=[ex])
        surf = pygame.Surface((800, 800), pygame.SRCALPHA)
        WorldRenderer(r_ps).explosions(surf)
        bb = surf.get_bounding_rect(min_alpha=1)
        cx, cy = ex["pos"].x + 200, ex["pos"].y + 200
        self.assertTrue(bb.collidepoint(cx, cy))
        self.assertAlmostEqual(bb.centerx, cx, delta=8)   # centred on the blast
        self.assertAlmostEqual(bb.width, 2 * 72, delta=10)   # fireball spans the diameter
        # sheet gone -> the ring is drawn instead, never a crash
        a.frame = lambda *args, **kw: None
        try:
            surf.fill((0, 0, 0, 0))
            WorldRenderer(r_ps).explosions(surf)
            self.assertGreater(surf.get_bounding_rect(min_alpha=1).width, 0)
        finally:
            del a.frame


if __name__ == "__main__":
    unittest.main()
