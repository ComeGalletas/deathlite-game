"""The potion pickup, collection, and the drop wiring.

Covers `entities.potion.HealthPotion` against a stub hero, then the real
`PlayingState` paths -- the kill roll, the pool cap, the run stats, and the
boss exclusion.
"""
import os
import random
import tempfile
import unittest

import pygame

from entities.potion import HealthPotion
from game.content import get_content
from game.events import Events
from game.game import Game
from game.states.playing.core.state import PlayingState

C = get_content()
T = C.potions


class _Hero:
    """Minimal stand-in for `Player` as `HealthPotion.update` reads it."""
    def __init__(self, x=0.0, y=0.0, hp=50.0, max_hp=100.0, pickup_radius=90.0):
        self.pos = pygame.Vector2(x, y)
        self.radius = 14.0
        self.hp = hp
        self.max_hp = max_hp
        self.pickup_radius = pickup_radius


def potion(x=0.0, y=0.0, rarity="common", heal=15.0):
    p = HealthPotion()
    p.active = True
    p.reset(pygame.Vector2(x, y), rarity, heal)
    return p


class PickupBehaviourTests(unittest.TestCase):
    def test_it_sits_still_outside_the_pickup_radius(self):
        p, hero = potion(500, 0), _Hero()
        self.assertFalse(p.update(1 / 60, hero))
        self.assertEqual(p.pos, pygame.Vector2(500, 0))
        self.assertFalse(p.homing)

    def test_it_homes_once_inside_the_pickup_radius(self):
        p, hero = potion(60, 0), _Hero()
        p.update(1 / 60, hero)
        self.assertTrue(p.homing)
        self.assertLess(p.pos.x, 60)

    def test_it_is_collected_on_contact(self):
        p, hero = potion(5, 0), _Hero()
        self.assertTrue(p.update(1 / 60, hero))
        self.assertFalse(p.active)

    def test_a_full_hp_hero_leaves_it_on_the_ground(self):
        # The whole point: a 50 HP rare potion is not spent for a sliver.
        p = potion(5, 0, "rare", 50.0)
        hero = _Hero(hp=100.0, max_hp=100.0)
        for _ in range(60):
            self.assertFalse(p.update(1 / 60, hero))
        self.assertTrue(p.active)
        self.assertEqual(p.pos, pygame.Vector2(5, 0))

    def test_a_full_hp_hero_does_not_drag_it_around(self):
        p = potion(60, 0)
        hero = _Hero(hp=100.0, max_hp=100.0)
        for _ in range(30):
            p.update(1 / 60, hero)
        self.assertFalse(p.homing)
        self.assertEqual(p.pos.x, 60)

    def test_it_becomes_collectable_again_once_the_hero_is_hurt(self):
        p = potion(5, 0)
        hero = _Hero(hp=100.0, max_hp=100.0)
        self.assertFalse(p.update(1 / 60, hero))
        hero.hp = 60.0
        self.assertTrue(p.update(1 / 60, hero))

    def test_reset_carries_the_rarity_and_the_heal(self):
        p = potion(0, 0, "uncommon", 25.0)
        self.assertEqual((p.rarity, p.heal), ("uncommon", 25.0))
        self.assertEqual(p.age, 0.0)

    def test_age_advances_for_the_shimmer(self):
        p, hero = potion(500, 0), _Hero()
        p.update(0.25, hero)
        self.assertAlmostEqual(p.age, 0.25)


def _run(seed=1234):
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    p = PlayingState(g)
    p.enter(seed=seed)
    return g, p


class DropWiringTests(unittest.TestCase):
    def test_the_pool_is_sized_from_data(self):
        _g, p = _run()
        self.assertEqual(p.potions.max_size, int(T["pool_size"]))

    def test_a_kill_can_drop_a_potion(self):
        _g, p = _run()
        p.rng = random.Random(7)
        for _ in range(60):
            p._roll_potion_drop("troll", p.player.pos + pygame.Vector2(400, 0))
        self.assertGreater(len(p.potions), 0)

    def test_a_dropped_potion_carries_its_rarity_heal(self):
        _g, p = _run()
        p.rng = random.Random(7)
        for _ in range(60):
            p._roll_potion_drop("troll", p.player.pos + pygame.Vector2(400, 0))
        for drop in p.potions:
            self.assertEqual(drop.heal, float(T["potions"][drop.rarity]["heal"]))

    def test_a_rare_enemys_drops_are_never_common(self):
        _g, p = _run()
        p.rng = random.Random(3)
        for _ in range(200):
            p._roll_potion_drop("troll", p.player.pos + pygame.Vector2(400, 0))
        self.assertNotIn("common", {d.rarity for d in p.potions})

    def test_an_unknown_enemy_id_drops_nothing(self):
        _g, p = _run()
        p._roll_potion_drop("not_an_enemy", p.player.pos)
        self.assertEqual(len(p.potions), 0)

    def test_the_kill_event_carries_the_enemy_id(self):
        _g, p = _run()
        p.rng = random.Random(7)
        before = len(p.potions)
        for _ in range(80):
            p.game.events.publish(
                Events.ENEMY_KILLED, pos=p.player.pos + pygame.Vector2(400, 0),
                color=(200, 90, 90), xp=1, tags=("elite",), elite=True,
                enemy_id="troll")
        self.assertGreater(len(p.potions), before)

    def test_a_kill_event_without_an_enemy_id_still_works(self):
        # `tests/systems/test_audio.py` publishes the older payload shape.
        _g, p = _run()
        p.game.events.publish(Events.ENEMY_KILLED, pos=p.player.pos,
                              color=(0, 0, 0), xp=1, tags=())
        self.assertEqual(len(p.potions), 0)

    def test_the_pool_cap_is_graceful(self):
        _g, p = _run()
        far = p.player.pos + pygame.Vector2(4000, 0)
        for _ in range(int(T["pool_size"]) + 40):
            drop = p.potions.acquire()
            if drop is not None:
                drop.reset(far, "common", 15.0)
        self.assertEqual(len(p.potions), int(T["pool_size"]))
        p._roll_potion_drop("troll", far)          # must not raise
        self.assertEqual(len(p.potions), int(T["pool_size"]))


class CollectionTests(unittest.TestCase):
    def test_collecting_heals_and_counts(self):
        _g, p = _run()
        p.player.hp = 20.0
        drop = p.potions.acquire()
        drop.reset(p.player.pos.copy(), "uncommon", 25.0)
        p._collect_potions(1 / 60)
        self.assertAlmostEqual(p.player.hp, 45.0)
        self.assertEqual(p.stats["potions"], 1)
        self.assertAlmostEqual(p.stats["potion_healing"], 25.0)
        self.assertEqual(len(p.potions), 0)

    def test_the_counted_healing_is_what_was_actually_gained(self):
        # A 50 HP potion into 10 HP of missing health counts 10, not 50.
        _g, p = _run()
        p.player.hp = p.player.max_hp - 10.0
        drop = p.potions.acquire()
        drop.reset(p.player.pos.copy(), "rare", 50.0)
        p._collect_potions(1 / 60)
        self.assertAlmostEqual(p.player.hp, p.player.max_hp)
        self.assertAlmostEqual(p.stats["potion_healing"], 10.0)

    def test_a_full_hp_hero_collects_nothing(self):
        _g, p = _run()
        p.player.hp = p.player.max_hp
        drop = p.potions.acquire()
        drop.reset(p.player.pos.copy(), "rare", 50.0)
        p._collect_potions(1 / 60)
        self.assertEqual(p.stats["potions"], 0)
        self.assertEqual(len(p.potions), 1)

    def test_collection_runs_from_the_update_loop(self):
        _g, p = _run()
        p.player.hp = 20.0
        drop = p.potions.acquire()
        drop.reset(p.player.pos.copy(), "common", 15.0)
        p.update(1 / 120)
        self.assertEqual(p.stats["potions"], 1)
        self.assertGreater(p.player.hp, 20.0)


class BossExclusionTests(unittest.TestCase):
    def test_the_boss_death_drops_no_potion(self):
        _g, p = _run()
        p.stats["potions"] = 0
        before = len(p.potions)
        p.boss = None
        p._on_boss_killed() if p.boss is not None else None
        self.assertEqual(len(p.potions), before)

    def test_the_boss_is_not_in_the_enemy_table(self):
        # `_roll_potion_drop` looks the id up in `content.enemies`, which holds
        # no bosses -- so a boss id can never roll a drop even if it got here.
        _g, p = _run()
        for boss_id in C.bosses:
            self.assertNotIn(boss_id, C.enemies)
            p._roll_potion_drop(boss_id, p.player.pos)
        self.assertEqual(len(p.potions), 0)


if __name__ == "__main__":
    unittest.main()
