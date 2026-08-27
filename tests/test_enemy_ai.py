"""Milestone 4: enemy variant behaviors (spec 3.3 / 8)."""
import random
import unittest

import pygame

from entities.enemy import Enemy
from entities.enemy_ai import EnemyContext
from game.content import get_content


def ctx(dt=1 / 30, player=(0, 0), **cb):
    calls = {"fired": [], "summoned": [], "exploded": []}
    base = dict(
        dt=dt, player_pos=pygame.Vector2(*player), player=object(),
        rng=random.Random(0),
        fire_projectile=lambda **kw: calls["fired"].append(kw),
        summon=lambda eid, pos, n: calls["summoned"].append((eid, n)),
        explosion=lambda pos, r, d: calls["exploded"].append((r, d)),
    )
    base.update(cb)
    return EnemyContext(**base), calls


def make(enemy_id):
    return Enemy(enemy_id, get_content().enemy(enemy_id), 200, 0)


class ShieldTests(unittest.TestCase):
    def test_shield_absorbs_before_hp(self):
        e = make("shielded")
        shield = e.shield_hp
        hp = e.hp
        e.take_damage(shield - 5)
        self.assertAlmostEqual(e.shield_hp, 5)
        self.assertEqual(e.hp, hp)  # nothing bled through

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
        self.assertLess(e.pos.x, 200)  # moved left toward origin

    def test_ranged_enemy_fires_projectile(self):
        e = make("ranged")
        e.pos = pygame.Vector2(150, 0)  # inside firing range
        fired = []
        for _ in range(200):
            c, calls = ctx(dt=1 / 30, player=(0, 0),
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
        e.pos = pygame.Vector2(40, 0)  # within slam_range
        exploded = []
        saw_telegraph = False
        for _ in range(400):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       explosion=lambda pos, r, d: exploded.append((r, d)))
            e.update(c)
            if e.telegraphing:
                saw_telegraph = True
        self.assertTrue(saw_telegraph, "brute never entered telegraph")
        self.assertTrue(exploded, "brute never landed a slam")


if __name__ == "__main__":
    unittest.main()
