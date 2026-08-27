"""Milestone 9: FSM advanced enemies -- charger / teleporter / warlock
(spec 5.6). The cycle chase -> telegraph -> attack -> recover must be visible
and the dangerous frame must follow a telegraph."""
import random
import unittest

import pygame

from entities.enemy import Enemy
from entities.enemy_ai import EnemyContext
from game.content import get_content


def make(eid, x=200, y=0):
    return Enemy(eid, get_content().enemy(eid), x, y)


def ctx(dt=1 / 30, player=(0, 0), **cb):
    calls = {"hazards": []}
    base = dict(
        dt=dt, player_pos=pygame.Vector2(*player), player=object(),
        rng=random.Random(0),
        fire_projectile=lambda **kw: None,
        summon=lambda *a: None, explosion=lambda *a: None,
        resolve_movement=lambda prev, new, r: new,
        spawn_hazard=lambda pos, radius, dps, duration:
            calls["hazards"].append((tuple(pos), radius, dps, duration)),
    )
    base.update(cb)
    return EnemyContext(**base), calls


class ChargerTests(unittest.TestCase):
    def test_cycles_states_and_bumps_damage_on_the_dash(self):
        e = make("charger", x=180)
        states = set()
        dashed_damage = 0.0
        for _ in range(600):
            c, _ = ctx(player=(0, 0))
            e.update(c)
            states.add(e.ai.get("fs"))
            if e.ai.get("fs") == "attack":
                dashed_damage = max(dashed_damage, e.contact_damage)
        self.assertEqual({"chase", "telegraph", "attack", "recover"} & states,
                         {"chase", "telegraph", "attack", "recover"})
        self.assertGreater(dashed_damage, e._base_contact)

    def test_telegraphs_before_attacking(self):
        e = make("charger", x=150)
        seq = []
        for _ in range(400):
            c, _ = ctx(player=(0, 0))
            e.update(c)
            if not seq or seq[-1] != e.ai.get("fs"):
                seq.append(e.ai.get("fs"))
        # find first attack, ensure a telegraph immediately precedes it
        i = seq.index("attack")
        self.assertEqual(seq[i - 1], "telegraph")


class TeleporterTests(unittest.TestCase):
    def test_blinks_close_to_the_player(self):
        e = make("teleporter", x=800)
        for _ in range(500):
            c, _ = ctx(player=(0, 0))
            e.update(c)
            if e.ai.get("fs") in ("attack", "recover"):
                break
        self.assertLess((e.pos - pygame.Vector2(0, 0)).length(), 200)


class WarlockTests(unittest.TestCase):
    def test_spawns_a_hazard_after_a_telegraph(self):
        e = make("warlock", x=260)
        saw_telegraph = False
        hazards = []
        for _ in range(500):
            c, calls = ctx(player=(0, 0))
            e.update(c)
            saw_telegraph = saw_telegraph or e.telegraphing
            hazards += calls["hazards"]
        self.assertTrue(saw_telegraph)
        self.assertTrue(hazards, "warlock never cast a hazard")
        # hazard was placed roughly where the player was
        (hx, hy), radius, dps, dur = hazards[0]
        self.assertLess(abs(hx), 60)
        self.assertGreater(dps, 0)


if __name__ == "__main__":
    unittest.main()
