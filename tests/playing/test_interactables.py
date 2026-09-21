"""Milestone 10: special-location interactables (spec 5.5).

Driven through a real headless PlayingState so the effects hit the same code the
game runs (drops, heals, blessing grants).

**Four of these are parked code** (owner, 2026-09-20 --
`journals/special_facilities_journal.md`): the shrine, treasure, altar and
merchant islands are no longer generated, so `SPECIAL_KINDS` is empty and no
world builds one of those interactables. Their handlers are kept for the
re-implementation, so the tests below *hand-build* the interactable instead of
hunting a layout for one -- `_parked` says so at each call. The alternative
was four `skipTest`s, which would look like coverage and be none.

What a real world still places -- the village forge and sanctuary heal, and
the buff buildings -- is still found through the layout.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.interactable import Interactable
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing.core.locations import MERCHANT_COST
from tests import worlds as W
from world.gen.tuning import SPECIAL_KINDS


SEED = W.pinned(0)


def fresh_playing(seed=SEED):
    """A booted run on the pinned world. Pinned because how many villages and
    buff buildings a layout has decides what `PlacementTests` counts, and
    because the forge tests need the village that carries the forge."""
    from tests.boot import start_run
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    return game, start_run(game, seed)


def _parked(p, kind, cost=0):
    """One of the four parked facilities, built by hand at the hero's feet.

    Generation never produces these any more; the handler under test does not
    care where the interactable came from.
    """
    return Interactable(kind, p.player.pos.x, p.player.pos.y, cost=cost)


class PlacementTests(unittest.TestCase):
    def test_a_world_builds_only_village_and_buff_interactables(self):
        """HI-2: a forge and a sanctuary heal per village, and one per buff
        building (journal: buff_buildings_journal.md) -- and nothing else.

        The `specials` term used to be the point of this test. It is now
        asserted to be empty: the four special islands were parked on
        2026-09-20 (`journals/special_facilities_journal.md`), and this is
        where "the generator really stopped building them" is pinned on the
        run side.
        """
        _, p = fresh_playing()
        lay = p.game_map.layout
        self.assertEqual(SPECIAL_KINDS, ())
        self.assertEqual([r.kind for r in lay.rooms if r.kind in SPECIAL_KINDS], [])
        buildings = lay.buff_buildings(p.buffs.kinds)
        self.assertEqual(len(p.interactables),
                         2 * len(lay.villages) + len(buildings))
        forges = {(it.pos.x, it.pos.y) for it in p.interactables if it.kind == "forge"}
        heals = {(it.pos.x, it.pos.y) for it in p.interactables if it.kind == "fountain"}
        self.assertEqual(forges, {(v.forge.x, v.forge.y) for v in lay.villages})
        self.assertEqual(heals, {(v.heal.x, v.heal.y) for v in lay.villages})
        pygame.quit()


class EffectTests(unittest.TestCase):
    def _get(self, p, kind):
        return next((it for it in p.interactables if it.kind == kind), None)

    def test_shrine_grants_a_blessing_and_is_consumed(self):
        """Parked handler, hand-built interactable -- see the module docstring."""
        _, p = fresh_playing()
        it = _parked(p, "shrine")
        before = sum(p.player.blessings.values())
        p._use_shrine(it)
        self.assertTrue(it.used)
        self.assertGreater(sum(p.player.blessings.values()), before)
        pygame.quit()

    def test_fountain_heals_to_full(self):
        _, p = fresh_playing()
        it = self._get(p, "fountain")
        if it is None:
            self.skipTest("no fountain in this layout")
        p.player.hp = 1
        p._use_fountain(it)
        self.assertEqual(p.player.hp, p.player.max_hp)
        pygame.quit()

    def test_forge_with_nothing_eligible_explains_and_is_never_consumed(self):
        game, p = fresh_playing()
        it = self._get(p, "forge")
        self.assertIsNotNone(it, "every world has a village, so a forge")
        p._use_forge(it)
        self.assertFalse(it.used)
        self.assertGreater(p._notice_t, 0.0)
        self.assertIn("needs", p._notice_text)
        self.assertIn("2 more", p._notice_text)             # sword at 0 of 2
        game._render()                                      # the notice draws (owner bug: `_hud`)
        pygame.quit()

    def test_forge_offers_the_two_forgings_of_an_eligible_weapon(self):
        from game.states.level_up_state import LevelUpState
        game, p = fresh_playing()
        it = self._get(p, "forge")
        p.player.weapons[0].level = 3                     # two blessing levels
        p._use_forge(it)
        top = game.state_machine.current
        self.assertIsInstance(top, LevelUpState)
        self.assertEqual({u.id for u in top.choices}, {"forge:whirlwind", "forge:greatsword"})
        self.assertIn("Forge", top.title)
        self.assertTrue(top.cancelable)
        top.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIs(game.state_machine.current, p)      # walked away, nothing forged
        self.assertIsNone(p.player.weapons[0].forge)
        p._use_forge(it)
        game.state_machine.current.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
        self.assertEqual(p.player.weapons[0].forge, "whirlwind")
        self.assertIs(game.state_machine.current, p)
        self.assertIn("reforged", p._notice_text)
        self.assertFalse(it.used)
        p._use_forge(it)                                  # nothing eligible now
        self.assertIn("already forged", p._notice_text)
        pygame.quit()

    def test_treasure_adds_an_item_to_the_run_drops(self):
        """Parked handler, hand-built interactable -- see the module docstring."""
        _, p = fresh_playing()
        it = _parked(p, "treasure")
        n = len(p.stats["dropped_items"])
        p._use_treasure(it)
        self.assertEqual(len(p.stats["dropped_items"]), n + 1)
        pygame.quit()

    def test_altar_costs_hp_and_refuses_when_too_low(self):
        """Parked handler, hand-built interactable -- see the module docstring."""
        _, p = fresh_playing()
        it = _parked(p, "altar")
        p.player.hp = p.player.max_hp
        p._use_altar(it)
        self.assertTrue(it.used)
        self.assertLess(p.player.hp, p.player.max_hp)   # paid HP

        it2 = type(it)("altar", 0, 0)
        p.player.hp = 1
        p._use_altar(it2)
        self.assertFalse(it2.used)                      # refused, not lethal
        pygame.quit()

    def test_merchant_requires_gold(self):
        """Parked handler, hand-built interactable -- see the module docstring.

        `MERCHANT_COST` is passed explicitly because `locations.build()` used
        to supply it and no longer builds one of these at all.
        """
        _, p = fresh_playing()
        it = _parked(p, "merchant", cost=MERCHANT_COST)
        p.stats["gold"] = 0
        p._use_merchant(it)
        self.assertFalse(it.used)
        p.stats["gold"] = it.cost + 5
        drops = len(p.stats["dropped_items"])
        p._use_merchant(it)
        self.assertTrue(it.used)
        self.assertEqual(p.stats["gold"], 5)
        self.assertEqual(len(p.stats["dropped_items"]), drops + 1)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
