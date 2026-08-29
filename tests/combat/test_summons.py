"""Milestone 9: summon weapons (spec 5.8) -- maintained count, lifetime,
damage via ordinary friendly projectiles."""
import unittest

import pygame

from combat.weapons import Weapon, FireContext
from entities.summon import Summon
from game.content import get_content


class FakeEnemy:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.alive = True


class SummonPool:
    def __init__(self):
        self.made = []

    def spawn(self, **kw):
        s = Summon()
        s.active = True
        s.reset(**kw)
        self.made.append(s)
        return s


def fire_ctx(pool, shots, anchor=(0, 0)):
    return FireContext(
        origin=pygame.Vector2(*anchor), enemies=[FakeEnemy(120, 0)],
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=1.0,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: shots.append(kw),
        anchor=pygame.Vector2(*anchor),
        spawn_summon=pool.spawn)


class TotemWeaponTests(unittest.TestCase):
    def test_maintains_projectile_count_summons_not_more(self):
        w = Weapon("grave_totem", get_content().weapon("grave_totem"))
        pool, shots = SummonPool(), []
        for _ in range(600):
            w.update(1 / 30, fire_ctx(pool, shots))
        want = w._projectile_count()
        alive = [s for s in pool.made if s.active]
        self.assertEqual(len(alive), want)

    def test_dead_summon_is_replaced(self):
        w = Weapon("grave_totem", get_content().weapon("grave_totem"))
        pool, shots = SummonPool(), []
        w.update(10.0, fire_ctx(pool, shots))          # spawn one
        self.assertTrue(pool.made)
        pool.made[0].active = False                    # it "expires"
        w.update(10.0, fire_ctx(pool, shots))          # should top up again
        self.assertGreaterEqual(len([s for s in pool.made if s.active]), 1)

    def test_totem_summon_keeps_its_finite_lifetime(self):
        w = Weapon("grave_totem", get_content().weapon("grave_totem"))
        pool, shots = SummonPool(), []
        w.update(1 / 30, fire_ctx(pool, shots))
        self.assertTrue(pool.made)
        self.assertNotEqual(pool.made[0].life, float("inf"))
        self.assertGreater(pool.made[0].life, 0.0)

    def test_wolf_summon_never_expires_and_is_not_recycled(self):
        from types import SimpleNamespace
        w = Weapon("spirit_wolf", get_content().weapon("spirit_wolf"))
        pool, shots = SummonPool(), []
        w.update(1 / 30, fire_ctx(pool, shots))
        self.assertEqual(len(pool.made), 1)
        wolf = pool.made[0]
        self.assertEqual(wolf.life, float("inf"))
        sctx = SimpleNamespace(enemies=[], spawn_projectile=lambda **k: None,
                               player_pos=pygame.Vector2(0, 0))
        for _ in range(600):                           # age it ~600 s
            wolf.update(1.0, sctx)
            w.update(1.0, fire_ctx(pool, shots))
        self.assertTrue(wolf.active)                   # still on field
        self.assertEqual(len(pool.made), 1)           # weapon never summoned a second


class SummonBehaviourTests(unittest.TestCase):
    def _ctx(self, shots, enemies, player=(0, 0)):
        from types import SimpleNamespace
        return SimpleNamespace(enemies=enemies,
                               spawn_projectile=lambda **kw: shots.append(kw),
                               player_pos=pygame.Vector2(*player))

    def _wolf(self, reach=280.0):
        s = Summon()
        s.reset(kind="wolf", pos=pygame.Vector2(0, 0), damage=12, lifetime=99,
                color=(1, 2, 3), tags=("summon",), speed=240, attack_range=70,
                reach=reach)
        return s

    def test_totem_fires_a_projectile_at_a_nearby_enemy(self):
        s = Summon()
        s.reset(kind="totem", pos=pygame.Vector2(0, 0), damage=7, lifetime=8,
                color=(1, 2, 3), tags=("summon",), attack_range=400,
                attack_interval=0.5)
        shots = []
        for _ in range(30):
            s.update(1 / 30, self._ctx(shots, [FakeEnemy(100, 0)]))
        self.assertTrue(shots)
        self.assertGreater(shots[0]["vel"].length(), 0)

    def test_wolf_moves_toward_the_enemy(self):
        s = Summon()
        s.reset(kind="wolf", pos=pygame.Vector2(0, 0), damage=12, lifetime=10,
                color=(1, 2, 3), tags=("summon",), speed=240, attack_range=70)
        shots = []
        for _ in range(15):
            s.update(1 / 30, self._ctx(shots, [FakeEnemy(600, 0)]))
        self.assertGreater(s.pos.x, 5)

    def test_summon_expires_after_its_lifetime(self):
        s = Summon()
        s.active = True
        s.reset(kind="totem", pos=pygame.Vector2(0, 0), damage=5, lifetime=1.0,
                color=(1, 2, 3), tags=("summon",))
        for _ in range(40):
            s.update(0.1, self._ctx([], []))
        self.assertFalse(s.active)

    # --- CB-2 leash ring -------------------------------------------
    def test_wolf_sleeps_when_the_only_enemy_is_outside_the_leash_ring(self):
        s = self._wolf(reach=280.0)
        shots = []
        for _ in range(60):                       # hero at origin, foe at 600 > 280
            s.update(1 / 60, self._ctx(shots, [FakeEnemy(600, 0)]))
        self.assertEqual(s.pos, pygame.Vector2(0, 0))       # never moved
        self.assertEqual(s.vel, pygame.Vector2(0, 0))
        self.assertEqual(shots, [])                          # no bite
        self.assertIsNone(s._acquire_target(self._ctx([], [FakeEnemy(600, 0)])))
        self.assertEqual(s._anim_name(None), "idle")         # the SLEEP strip

    def test_wolf_wakes_and_bites_when_the_enemy_is_inside_the_leash_ring(self):
        s = self._wolf(reach=280.0)
        shots = []
        for _ in range(180):
            s.update(1 / 60, self._ctx(shots, [FakeEnemy(150, 0)]))
        self.assertGreater(s.pos.x, 5)                       # closed on the foe
        self.assertTrue(shots)                               # and bit it

    def test_wolf_pulled_past_its_leash_runs_home(self):
        s = self._wolf(reach=280.0)
        s.pos.update(400, 0)                                 # dragged out: 400 > 280
        before = s.pos.x
        s.update(1 / 60, self._ctx([], [FakeEnemy(900, 0)]))  # a further foe must not hold it
        self.assertLess(s.pos.x, before)                     # moved back toward the hero
        self.assertLess(s.vel.x, 0)
        self.assertEqual(s._anim_name(None), "run_left")     # running, not sleeping

    def test_totem_defends_its_planted_spot_not_the_roaming_hero(self):
        s = Summon()
        s.reset(kind="totem", pos=pygame.Vector2(0, 0), damage=7, lifetime=99,
                color=(1, 2, 3), tags=("summon",), attack_range=360,
                attack_interval=0.4, reach=360)
        shots = []
        for _ in range(60):                       # hero has wandered 5000 px away
            s.update(1 / 30, self._ctx(shots, [FakeEnemy(200, 0)], player=(5000, 0)))
        self.assertTrue(shots)                    # still zaps a foe by its base


if __name__ == "__main__":
    unittest.main()
