"""Milestone 4: boss FSM -- pattern cycling, telegraph-before-damage,
distinct pattern effects, health fraction, death (spec 3.7)."""
import random
import unittest

import pygame

from entities.boss import Boss
from entities.enemy_ai import EnemyContext
from game.content import get_content


def boss():
    bid = next(iter(get_content().bosses))
    return Boss(bid, get_content().boss(bid), 0, 0)


def ctx(dt, sink):
    return EnemyContext(
        dt=dt, player_pos=pygame.Vector2(300, 0), player=object(),
        rng=random.Random(0),
        fire_projectile=lambda **kw: sink["fired"].append(kw),
        summon=lambda eid, pos, n: sink["summoned"].append((eid, n)),
        explosion=lambda *a: None)


class BossTests(unittest.TestCase):
    def test_hp_fraction_and_death(self):
        b = boss()
        self.assertEqual(b.hp_fraction, 1.0)
        b.take_damage(b.max_hp / 2)
        self.assertAlmostEqual(b.hp_fraction, 0.5, places=3)
        b.take_damage(b.max_hp)
        self.assertFalse(b.alive)
        self.assertEqual(b.hp_fraction, 0.0)

    def test_cycles_through_all_three_patterns(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        seen = set()
        for _ in range(4000):
            b.update(ctx(1 / 30, sink))
            if b.pattern:
                seen.add(b.pattern["id"])
        self.assertEqual(seen, {"radial_barrage", "charge", "summon_brood"})

    def test_no_damage_output_during_telegraph(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        # step until the first telegraph of the radial pattern
        while not (b.phase == "telegraph" and b.pattern.get("id") == "radial_barrage"):
            b.update(ctx(1 / 60, sink))
        self.assertEqual(sink["fired"], [], "bullets fired before telegraph ended")
        # run the telegraph out
        guard = 0
        while b.phase == "telegraph" and guard < 1000:
            b.update(ctx(1 / 60, sink))
            guard += 1
        self.assertTrue(sink["fired"], "radial barrage never fired after telegraph")

    def test_radial_barrage_fires_ring_of_bullets(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        pat = next(p for p in b.cfg["patterns"] if p["id"] == "radial_barrage")
        for _ in range(6000):
            b.update(ctx(1 / 30, sink))
            if len(sink["fired"]) >= pat["bullets"]:
                break
        self.assertGreaterEqual(len(sink["fired"]), pat["bullets"])

    def test_summon_pattern_calls_summon(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        for _ in range(9000):
            b.update(ctx(1 / 30, sink))
            if sink["summoned"]:
                break
        self.assertTrue(sink["summoned"])
        self.assertEqual(sink["summoned"][0][0], "swarm")


if __name__ == "__main__":
    unittest.main()
