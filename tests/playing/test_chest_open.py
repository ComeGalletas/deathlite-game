"""The chest props, the interact key, and what opening one
actually pays out.

Covers `entities.chest.Chest` against a stub hero and its animation clock,
then the real `PlayingState` paths -- the props built from the layout, the
nearest-first prompt, the gold / potion / blessing payout, the one-shot rule,
and the pool-capped and maxed-out degradations.
"""
import os
import random
import tempfile
import unittest

import pygame

from entities.chest import Chest
from game import config
from game.content import get_content
from game.game import Game
from game.states.playing.core.state import PlayingState
from progression import chests as chest_rules

C = get_content()
T = C.chests


def _run(seed=1234):
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    p = PlayingState(g)
    p.enter(seed=seed)
    return g, p


def _put(ps, rarity, at=None):
    """Seat one chest of `rarity` under the hero and return it."""
    at = ps.player.pos if at is None else at
    chest = Chest(at.x, at.y, rarity, radius=chest_rules.radius(T))
    ps.chests.append(chest)
    return chest


class PropTests(unittest.TestCase):
    def test_it_starts_closed_on_frame_zero(self):
        chest = Chest(0, 0, "common")
        self.assertFalse(chest.opened)
        self.assertEqual(chest.frame_index(4, 0.45), 0)

    def test_a_closed_chest_does_not_age(self):
        chest = Chest(0, 0, "common")
        for _ in range(30):
            chest.update(1 / 60, 0.45)
        self.assertEqual(chest.age, 0.0)

    def test_an_open_chest_walks_the_strip_and_holds_the_last_frame(self):
        chest = Chest(0, 0, "rare")
        chest.opened = True
        seen = []
        for _ in range(120):
            chest.update(1 / 60, 0.45)
            seen.append(chest.frame_index(4, 0.45))
        self.assertEqual(seen[-1], 3)
        self.assertEqual(seen, sorted(seen), "the lid never runs backwards")
        self.assertEqual(set(seen) | {0}, {0, 1, 2, 3})

    def test_the_clock_stops_once_the_strip_has_played(self):
        chest = Chest(0, 0, "epic")
        chest.opened = True
        for _ in range(600):
            chest.update(1 / 60, 0.45)
        self.assertEqual(chest.age, 0.45)

    def test_in_range_matches_the_interactable_pad(self):
        chest = Chest(0, 0, "common", radius=24.0)
        self.assertTrue(chest.in_range(pygame.Vector2(60, 0)))
        self.assertFalse(chest.in_range(pygame.Vector2(200, 0)))


class BuildTests(unittest.TestCase):
    def test_the_run_builds_one_prop_per_seated_chest(self):
        _g, p = _run()
        self.assertEqual(len(p.chests), len(p.game_map.layout.chests))
        self.assertTrue(p.chests, "seed 1234 seats no chests at all")

    def test_each_prop_carries_its_tier_and_place(self):
        _g, p = _run()
        for prop, record in zip(p.chests, p.game_map.layout.chests):
            self.assertEqual(prop.rarity, record.rarity)
            self.assertEqual((prop.pos.x, prop.pos.y), (record.x, record.y))
            self.assertEqual(prop.floor, record.floor)

    def test_every_prop_starts_closed(self):
        _g, p = _run()
        self.assertFalse(any(c.opened for c in p.chests))

    def test_the_run_starts_with_no_chests_opened(self):
        _g, p = _run()
        self.assertEqual(p.stats["chests"], 0)


class ProximityTests(unittest.TestCase):
    def test_nothing_is_nearby_out_in_the_open(self):
        _g, p = _run()
        p.chests = []
        self.assertIsNone(p.chest_manager.nearby())

    def test_a_chest_underfoot_is_nearby(self):
        _g, p = _run()
        p.chests = []
        chest = _put(p, "common")
        self.assertIs(p.chest_manager.nearby(), chest)

    def test_the_nearest_one_wins(self):
        _g, p = _run()
        p.chests = []
        far = _put(p, "epic", p.player.pos + pygame.Vector2(50, 0))
        near = _put(p, "common", p.player.pos + pygame.Vector2(5, 0))
        self.assertIs(p.chest_manager.nearby(), near)
        self.assertIsNot(p.chest_manager.nearby(), far)

    def test_an_opened_chest_is_no_longer_nearby(self):
        _g, p = _run()
        p.chests = []
        _put(p, "common")
        p.chest_manager.activate_nearby()
        self.assertIsNone(p.chest_manager.nearby())


class PayoutTests(unittest.TestCase):
    def test_opening_pays_gold_inside_the_tiers_range(self):
        _g, p = _run()
        p.chests = []
        lo, hi = T["chests"]["uncommon"]["gold"]
        before = p.stats["gold"]
        p.chest_manager.open(_put(p, "uncommon"))
        self.assertTrue(lo <= p.stats["gold"] - before <= hi)

    def test_opening_spills_exactly_one_potion(self):
        _g, p = _run()
        p.chests, before = [], len(p.potions)
        p.chest_manager.open(_put(p, "rare"))
        self.assertEqual(len(p.potions) - before, 1)

    def test_the_potion_is_the_tiers_rarity(self):
        for tier in ("common", "uncommon", "rare", "epic"):
            with self.subTest(tier=tier):
                _g, p = _run()
                p.chests = []
                p.chest_manager.open(_put(p, tier))
                dropped = list(p.potions)[-1]
                self.assertEqual(dropped.rarity,
                                 chest_rules.potion_rarity(tier, T))

    def test_the_potion_lands_on_top_of_the_chest(self):
        """The owner's rule: loot reads as coming out of the chest it was
        found in, so the potion sits on the box, not on a ring beside it."""
        _g, p = _run()
        p.chests = []
        chest = _put(p, "common")
        p.chest_manager.open(chest)
        dropped = list(p.potions)[-1]
        self.assertEqual(dropped.pos.x, chest.pos.x, "same column as the chest")
        self.assertLess(dropped.pos.y, chest.pos.y, "above the chest, not below")
        self.assertAlmostEqual(chest.pos.y - dropped.pos.y,
                               chest_rules.potion_lift(T), delta=0.01)

    def test_the_lift_keeps_the_potion_inside_the_chests_art(self):
        """It should sit in the open box's mouth, not float over the lid: the
        chest art stands ~30 px off its baseline."""
        lift = chest_rules.potion_lift(T)
        self.assertGreater(lift, 0.0)
        self.assertLess(lift, 30.0)

    def test_each_chest_keeps_its_own_potion(self):
        _g, p = _run()
        p.chests = []
        here = p.player.pos
        a_chest = _put(p, "common", here)
        b_chest = _put(p, "common", here + pygame.Vector2(120, 0))
        p.chest_manager.open(a_chest)
        p.chest_manager.open(b_chest)
        a, b = list(p.potions)[-2:]
        self.assertEqual(a.pos.x, a_chest.pos.x)
        self.assertEqual(b.pos.x, b_chest.pos.x)
        self.assertNotEqual((a.pos.x, a.pos.y), (b.pos.x, b.pos.y))

    def test_a_common_chest_grants_no_blessing(self):
        _g, p = _run()
        p.chests = []
        p.rng = random.Random(3)
        before = dict(p.player.blessings)
        for _ in range(20):
            p.chest_manager.open(_put(p, "common"))
        self.assertEqual(dict(p.player.blessings), before)

    def test_a_rare_chest_always_grants_one(self):
        _g, p = _run()
        p.chests = []
        p.rng = random.Random(4)
        before = sum(p.player.blessings.values())
        p.chest_manager.open(_put(p, "rare"))
        self.assertEqual(sum(p.player.blessings.values()), before + 1)

    def test_an_epic_chest_always_grants_one(self):
        _g, p = _run()
        p.chests = []
        p.rng = random.Random(5)
        before = sum(p.player.blessings.values())
        p.chest_manager.open(_put(p, "epic"))
        self.assertEqual(sum(p.player.blessings.values()), before + 1)

    def test_opening_counts_toward_the_run_stats(self):
        _g, p = _run()
        p.chests = []
        for _ in range(3):
            p.chest_manager.open(_put(p, "common"))
        self.assertEqual(p.stats["chests"], 3)

    def test_a_chest_pays_out_once(self):
        _g, p = _run()
        p.chests = []
        chest = _put(p, "uncommon")
        p.chest_manager.activate_nearby()
        gold, potions = p.stats["gold"], len(p.potions)
        self.assertTrue(chest.opened)
        for _ in range(5):
            p.chest_manager.activate_nearby()
        self.assertEqual((p.stats["gold"], len(p.potions)), (gold, potions))

    def test_the_notice_names_what_was_found(self):
        _g, p = _run()
        p.chests = []
        p.rng = random.Random(6)
        p.chest_manager.open(_put(p, "rare"))
        self.assertIn("gold", p._notice_text)
        self.assertIn("potion", p._notice_text)
        self.assertTrue(p._notice_text.startswith("Rare chest:"))

    def test_a_capped_potion_pool_still_pays_the_gold(self):
        """The pool degrades gracefully: no potion, but never a crash and
        never a chest that silently paid nothing."""
        _g, p = _run()
        p.chests = []
        while p.potions.acquire() is not None:
            pass
        before = p.stats["gold"]
        p.chest_manager.open(_put(p, "common"))
        self.assertGreater(p.stats["gold"], before)
        self.assertNotIn("potion", p._notice_text)


class KeyTests(unittest.TestCase):
    def test_e_opens_the_chest_underfoot(self):
        _g, p = _run()
        p.chests = []
        chest = _put(p, "common")
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT))
        self.assertTrue(chest.opened)

    def test_e_away_from_anything_does_nothing(self):
        _g, p = _run()
        p.chests = []
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT))
        self.assertEqual(p.stats["chests"], 0)

    def test_a_special_location_wins_a_tie(self):
        """The key goes to the closest element; at an equal distance the
        location wins, as it always did.

        The shrine is hand-seated rather than found in the layout: the four
        special islands were parked on 2026-09-20
        (`journals/special_facilities_journal.md`), so no world generates one.
        That does not retire the rule -- a village forge or a buff building
        can tie with a chest the same way -- and a hand-built interactable is
        the smallest thing that exercises `interactions.nearest`."""
        from entities.interactable import Interactable
        _g, p = _run()
        p.chests = []
        it = Interactable("shrine", p.player.pos.x, p.player.pos.y)
        p.interactables.append(it)
        p.player.pos.update(it.pos)
        chest = _put(p, "epic", it.pos)
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT))
        self.assertTrue(it.used)
        self.assertFalse(chest.opened)


class DrawOrderTests(unittest.TestCase):
    """The other half of "on top of the chest": the potion's *sprite* has to
    land above the chest's, or a potion sitting in the box would be painted
    over by it."""

    def _order(self, ps):
        seen = []
        for name in ("interactables", "chests", "gems", "potions", "hazards"):
            def spy(_s, _lvl=None, _n=name):
                seen.append(_n)
            setattr(ps.renderer, name, spy)
        ps._draw_flat_effects(pygame.Surface((32, 32)), 0)
        return seen

    def test_potions_are_drawn_after_chests(self):
        _g, p = _run()
        order = self._order(p)
        self.assertIn("chests", order)
        self.assertIn("potions", order)
        self.assertLess(order.index("chests"), order.index("potions"))


class UpdateTests(unittest.TestCase):
    def test_the_manager_advances_only_open_lids(self):
        _g, p = _run()
        p.chests = []
        shut, open_ = _put(p, "common"), _put(p, "rare")
        open_.opened = True
        for _ in range(10):
            p.chest_manager.update(1 / 60)
        self.assertEqual(shut.age, 0.0)
        self.assertGreater(open_.age, 0.0)


if __name__ == "__main__":
    unittest.main()
