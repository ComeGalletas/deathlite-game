"""Enemy variant behaviour, end-to-end through `Enemy.update` (spec 3.3 / 8).

The steering / attack components themselves are covered by `test_ai_components`,
`test_ai_behaviors_simple` and `test_ai_behaviors_fsm`; this file checks that a
data-driven `Enemy` wired to a behaviour actually moves / fires / detonates.
"""
import unittest

import pygame

from entities.enemy import Enemy
from game.content import get_content
from tests.aictx import ai_ctx


def ctx(dt=1 / 30, player=(0, 0), **cb):
    return ai_ctx(dt=dt, player=player, **cb), {}


def make(enemy_id, x=200, y=0):
    return Enemy(enemy_id, get_content().enemy(enemy_id), x, y)


class ShieldTests(unittest.TestCase):
    def test_shield_absorbs_before_hp(self):
        e = make("shielded")
        shield, hp = e.shield_hp, e.hp
        e.take_damage(shield - 5)
        self.assertAlmostEqual(e.shield_hp, 5)
        self.assertEqual(e.hp, hp)

    def test_overkill_spills_into_hp(self):
        e = make("shielded")
        e.take_damage(e.shield_hp + 10)
        self.assertEqual(e.shield_hp, 0)
        self.assertAlmostEqual(e.hp, e.max_hp - 10)


class BehaviorTests(unittest.TestCase):
    def test_chaser_moves_toward_player(self):
        e = make("chaser")
        c, _ = ctx(player=(0, 0))
        e.update(c)
        self.assertLess(e.pos.x, 200)                   # moved toward the origin

    def test_ranged_enemy_fires_projectile(self):
        e = make("ranged")
        e.pos = pygame.Vector2(150, 0)                  # inside firing range
        fired = []
        for _ in range(200):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       fire_projectile=lambda **kw: fired.append(kw))
            e.update(c)
        self.assertTrue(fired)
        self.assertIn("damage", fired[0])

    def test_exploder_dies_when_it_reaches_player(self):
        e = make("exploder")
        e.pos = pygame.Vector2(10, 0)
        c, _ = ctx(player=(0, 0))
        e.update(c)
        self.assertFalse(e.alive)

    def test_summoner_spawns_brood_on_interval(self):
        e = make("summoner")
        summoned = []
        for _ in range(300):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       summon=lambda eid, pos, n: summoned.append((eid, n)))
            e.update(c)
        self.assertTrue(summoned)
        self.assertEqual(summoned[0][0], "swarm")

    def test_brute_telegraphs_then_slams(self):
        e = make("brute")
        e.pos = pygame.Vector2(40, 0)                   # within slam_range
        exploded = []
        saw_telegraph = False
        for _ in range(400):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       explosion=lambda pos, r, d: exploded.append((r, d)))
            e.update(c)
            saw_telegraph = saw_telegraph or e.telegraphing
        self.assertTrue(saw_telegraph, "brute never entered telegraph")
        self.assertTrue(exploded, "brute never landed a slam")


if __name__ == "__main__":
    unittest.main()
