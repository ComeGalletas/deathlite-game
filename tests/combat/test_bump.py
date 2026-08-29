"""CB-3: `BumpResolver` (unit bumping) + the hero-shove and weapon-hit
knockback that share `combat.knockback.knock_split`.

`BumpResolver` only needs `ps.enemies`, `ps.boss`, `ps.player`, each a body
with `.pos` / `.radius` / `.weight` / `.alive` / `.apply_knockback`, so the
tests use a tiny stub rather than real `Enemy` / `Player` objects.
"""
import math
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from combat.knockback import knock_split
from game.states.playing.physics import BumpResolver, _PEN_CAP_FRAC


class Body:
    """Mirrors the `apply_knockback` / `_knock` contract of Enemy / Player."""
    def __init__(self, x, y, radius, weight, alive=True):
        self.pos = pygame.Vector2(x, y)
        self.radius = float(radius)
        self.weight = float(weight)
        self.alive = alive
        self._knock = pygame.Vector2()

    def apply_knockback(self, direction, strength):
        if direction.length_squared() > 1e-6:
            self._knock += direction.normalize() * strength


def _ps(enemies=(), boss=None, player=None):
    return SimpleNamespace(enemies=list(enemies), boss=boss,
                           player=player or Body(10_000, 10_000, 10, 40))


def _resolve(ps):
    BumpResolver(ps).resolve()


class BumpResolverTests(unittest.TestCase):
    def test_two_equal_bodies_get_symmetric_opposite_impulses(self):
        a = Body(0, 0, 14, 7)
        b = Body(20, 0, 14, 7)                     # overlap by 8 px along +x
        _resolve(_ps([a, b]))
        self.assertAlmostEqual(a._knock.x, -b._knock.x, places=4)
        self.assertAlmostEqual(a._knock.length(), b._knock.length(), places=4)
        self.assertLess(a._knock.x, 0)             # a shoved -x, away from b
        self.assertGreater(b._knock.x, 0)

    def test_light_body_flies_and_the_heavy_one_barely_moves(self):
        bug = Body(0, 0, 7, 3)
        tank = Body(24, 0, 24, 14)                 # deep overlap
        _resolve(_ps([bug, tank]))
        self.assertGreater(bug._knock.length(), tank._knock.length())
        # roughly the inverse weight ratio (14/3 ~= 4.7)
        self.assertGreater(bug._knock.length(), 3.0 * tank._knock.length())

    def test_no_impulse_when_the_circles_do_not_touch(self):
        a = Body(0, 0, 14, 7)
        b = Body(40, 0, 14, 7)                     # 12 px gap
        _resolve(_ps([a, b]))
        self.assertEqual(a._knock, pygame.Vector2())
        self.assertEqual(b._knock, pygame.Vector2())

    def test_coincident_bodies_are_skipped_no_nan(self):
        a = Body(100, 100, 14, 7)
        b = Body(100, 100, 14, 7)
        _resolve(_ps([a, b]))
        for v in (a._knock.x, a._knock.y, b._knock.x, b._knock.y):
            self.assertTrue(math.isfinite(v))
        self.assertEqual(a._knock, pygame.Vector2())

    def test_a_dead_enemy_neither_shoves_nor_is_shoved(self):
        live = Body(0, 0, 14, 7)
        dead = Body(10, 0, 14, 7, alive=False)
        _resolve(_ps([live, dead]))
        self.assertEqual(live._knock, pygame.Vector2())
        self.assertEqual(dead._knock, pygame.Vector2())

    def test_the_boss_shoves_an_enemy_and_takes_nothing(self):
        boss = Body(0, 0, 60, float("inf"))
        e = Body(70, 0, 14, 7)                     # overlapping the boss
        _resolve(_ps([e], boss=boss))
        self.assertGreater(e._knock.length(), 0.0)
        self.assertEqual(boss._knock, pygame.Vector2())

    def test_penetration_is_clamped_so_a_tunnelling_body_cannot_spike(self):
        rr = 14 + 14
        deep = _ps([Body(0, 0, 14, 7), Body(rr * 0.05, 0, 14, 7)])   # ~95% overlap
        capped = _ps([Body(0, 0, 14, 7), Body(rr * (1.0 - _PEN_CAP_FRAC), 0, 14, 7)])
        _resolve(deep)
        _resolve(capped)
        self.assertAlmostEqual(deep.enemies[0]._knock.length(),
                               capped.enemies[0]._knock.length(), places=3)


class HeroShoveTests(unittest.TestCase):
    def _hero_bump(self, enemy_weight, enemy_radius):
        hero = Body(0, 0, config.PLAYER_RADIUS, config.PLAYER_WEIGHT)
        e = Body(config.PLAYER_RADIUS + enemy_radius - 6, 0, enemy_radius,
                 enemy_weight)                     # overlap the hero by 6 px
        _resolve(_ps([e], player=hero))
        return hero._knock.length(), e._knock.length()

    def test_a_swarm_bug_barely_nudges_the_hero_but_a_brute_shoves_it(self):
        swarm_hero, _ = self._hero_bump(3, 7)
        brute_hero, _ = self._hero_bump(80, 30)
        self.assertGreater(brute_hero, 3.0 * swarm_hero)   # mass gap shows on the hero
        self.assertGreater(swarm_hero, 0.0)               # but a bug still registers

    def test_the_enemy_is_shoved_harder_than_the_hero_in_a_bump(self):
        hero_k, enemy_k = self._hero_bump(7, 14)          # chaser
        self.assertGreater(enemy_k, hero_k)

    def test_the_hero_is_shoved_by_the_boss_and_never_shoves_it_back(self):
        hero = Body(0, 0, config.PLAYER_RADIUS, config.PLAYER_WEIGHT)
        boss = Body(config.PLAYER_RADIUS + 50, 0, 60, float("inf"))
        _resolve(_ps([], boss=boss, player=hero))
        self.assertGreater(hero._knock.length(), 0.0)
        self.assertEqual(boss._knock, pygame.Vector2())


class HitKnockbackTests(unittest.TestCase):
    """Mirrors `CombatResolver.projectile_hits`:
    `_, push = knock_split(src_weight, enemy.weight, HIT_KNOCK_GAIN*src_weight)`.
    """
    def _hit_push(self, weapon_weight, enemy_weight):
        _, push = knock_split(weapon_weight, enemy_weight,
                              config.HIT_KNOCK_GAIN * weapon_weight)
        return push

    def test_a_heavy_weapon_shoves_a_light_enemy_more_than_a_heavy_one(self):
        scythe_w = 30
        self.assertGreater(self._hit_push(scythe_w, 3),      # vs a swarm
                           self._hit_push(scythe_w, 80))     # vs a brute

    def test_a_light_projectile_barely_knocks_anything(self):
        bolt_push = self._hit_push(7, 7)                     # arcane_bolt vs chaser
        scythe_push = self._hit_push(30, 7)
        self.assertLess(bolt_push, scythe_push / 5.0)

    def test_a_weightless_spirit_bite_deals_no_knockback(self):
        self.assertEqual(self._hit_push(0, 7), 0.0)

    def test_the_boss_takes_no_hit_knockback(self):
        self.assertEqual(self._hit_push(30, float("inf")), 0.0)


if __name__ == "__main__":
    unittest.main()
