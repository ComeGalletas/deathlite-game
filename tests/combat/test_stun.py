"""Six-weapon system P1: the stun status (design §3.2, the Hammer). A stunned
enemy neither moves, nor advances its behaviour, nor bites; the boss is
immune; the Hammer rolls it on every cone hit."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.status import REGISTRY, StatusState
from combat.weapons import FireContext, Weapon
from entities.enemy import Enemy
from game.content import get_content
from game.states.playing.combat import CombatResolver
from tests.aictx import ai_ctx
from tests.combat.fakes import FakeEnemy, fake_ps


class _Rng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class StatusFamilyTests(unittest.TestCase):
    def test_stun_is_a_registered_family(self):
        self.assertEqual(REGISTRY["stun"].family, "stun")

    def test_stun_zeroes_speed_and_reports_itself(self):
        s = StatusState()
        self.assertFalse(s.is_stunned())
        self.assertEqual(s.speed_multiplier(), 1.0)
        s.apply("stun", 0.8, 1.0)
        self.assertTrue(s.is_stunned())
        self.assertEqual(s.speed_multiplier(), 0.0)

    def test_stun_beats_chill_and_expires(self):
        s = StatusState()
        s.apply("chill", 5.0, 0.3)
        s.apply("stun", 0.5, 1.0)
        self.assertEqual(s.speed_multiplier(), 0.0)
        s.update(0.6, lambda amt: None)
        self.assertFalse(s.is_stunned())
        self.assertAlmostEqual(s.speed_multiplier(), 0.7)

    def test_reapplying_refreshes_the_longer_duration(self):
        s = StatusState()
        s.apply("stun", 0.3, 1.0)
        s.apply("stun", 0.8, 1.0)
        s.update(0.5, lambda amt: None)
        self.assertTrue(s.is_stunned())


class FrozenEnemyTests(unittest.TestCase):
    def _chaser(self):
        return Enemy("chaser", get_content().enemies["chaser"], 100, 0)

    def test_a_stunned_chaser_does_not_move_or_bite(self):
        e = self._chaser()
        ctx = ai_ctx(player=(0, 0), nav_dir=lambda pos, r: pygame.Vector2(-1, 0))
        e.update(ctx)                                  # one free frame: it walks
        moved = e.pos.x
        self.assertLess(moved, 100)
        e.status.apply("stun", 1.0, 1.0)
        for _ in range(10):
            e.update(ctx)
        self.assertAlmostEqual(e.pos.x, moved)
        self.assertEqual(e.vel, pygame.Vector2())
        self.assertEqual(e.contact_damage, 0.0)

    def test_it_walks_and_bites_again_when_the_stun_ends(self):
        e = self._chaser()
        ctx = ai_ctx(player=(0, 0), nav_dir=lambda pos, r: pygame.Vector2(-1, 0))
        e.status.apply("stun", 0.1, 1.0)
        for _ in range(12):                            # 0.2 s
            e.update(ctx)
        self.assertLess(e.pos.x, 100)
        self.assertGreater(e.contact_damage, 0.0)

    def test_knockback_still_moves_a_stunned_enemy(self):
        e = self._chaser()
        e.status.apply("stun", 1.0, 1.0)
        e.apply_knockback(pygame.Vector2(1, 0), 400)
        e.update(ai_ctx(player=(0, 0)))
        self.assertGreater(e.pos.x, 100)


class ResolverRollTests(unittest.TestCase):
    def _hit(self, ps, enemy, chance, duration=0.8):
        p = ps._spawn_projectile(pos=enemy.pos, vel=(0, 0), damage=5, radius=20,
                                 lifetime=0.2, pierce=999, stun_chance=chance,
                                 stun_duration=duration)
        CombatResolver(ps).projectile_hits()
        return p

    def test_a_winning_roll_stuns_for_the_projectile_duration(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e], rng=_Rng(0.1))
        self._hit(ps, e, chance=0.35, duration=0.8)
        self.assertTrue(e.status.is_stunned())
        e.status.update(0.79, lambda a: None)
        self.assertTrue(e.status.is_stunned())
        e.status.update(0.02, lambda a: None)
        self.assertFalse(e.status.is_stunned())

    def test_a_losing_roll_does_not(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e], rng=_Rng(0.9))
        self._hit(ps, e, chance=0.35)
        self.assertFalse(e.status.is_stunned())

    def test_a_projectile_without_a_stun_chance_never_rolls(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e], rng=_Rng(0.0))
        self._hit(ps, e, chance=0.0)
        self.assertFalse(e.status.is_stunned())

    def test_the_boss_is_immune(self):
        e = FakeEnemy(0, 0)
        e.stun_immune = True
        ps = fake_ps([e], rng=_Rng(0.0))
        self._hit(ps, e, chance=1.0)
        self.assertFalse(e.status.is_stunned())
        self.assertLess(e.hp, 100.0, "the hit itself still lands")

    def test_the_real_boss_declares_immunity(self):
        from entities.boss import Boss
        self.assertTrue(Boss.stun_immune)

    def test_dev_no_damage_skips_the_roll(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e], rng=_Rng(0.0))
        ps.dev_mode = True
        ps._dev_no_damage = True
        self._hit(ps, e, chance=1.0)
        self.assertFalse(e.status.is_stunned())


class HammerTests(unittest.TestCase):
    def test_the_hammer_blow_carries_its_stun_and_the_sword_does_not(self):
        sink = []

        def fire(wid):
            w = Weapon(wid, get_content().weapon(wid))
            sink.clear()
            # CR1: the Hammer swings for 1.2 s before its blow lands.
            for _ in range(80):
                w.update(1 / 60, FireContext(
                    origin=pygame.Vector2(), enemies=[FakeEnemy(25, 0)],   # inside the sword's reach
                    damage_multiplier=1.0, attack_speed_multiplier=1.0,
                    projectile_speed_multiplier=1.0, area_multiplier=1.0,
                    fallback_dir=pygame.Vector2(1, 0),
                    spawn_projectile=lambda **kw: sink.append(kw)))
                if sink:
                    break
            return sink[0]

        d = get_content().weapon("hammer")
        h = fire("hammer")
        self.assertAlmostEqual(h["stun_chance"], d["stun_chance"])
        self.assertAlmostEqual(h["stun_duration"], d["stun_duration"])
        s = fire("sword")
        self.assertEqual(s["stun_chance"], 0.0)

    def test_over_many_hits_the_hammer_stuns_about_its_chance(self):
        d = get_content().weapon("hammer")
        rng = random.Random(3)
        stunned = 0
        n = 400
        for _ in range(n):
            e = FakeEnemy(0, 0)
            ps = fake_ps([e], rng=rng)
            ps._spawn_projectile(pos=(0, 0), vel=(0, 0), damage=1, radius=20,
                                 lifetime=0.2, pierce=999,
                                 stun_chance=d["stun_chance"],
                                 stun_duration=d["stun_duration"])
            CombatResolver(ps).projectile_hits()
            stunned += e.status.is_stunned()
        self.assertAlmostEqual(stunned / n, d["stun_chance"], delta=0.08)


if __name__ == "__main__":
    unittest.main()
