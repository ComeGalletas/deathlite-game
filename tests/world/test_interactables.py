"""Milestone 10: special-location interactables (spec 5.5).

Driven through a real headless PlayingState so the effects hit the same code the
game runs (drops, heals, blessing grants, elite arena)."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState
from world.procedural import SPECIAL_KINDS


def fresh_playing():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    from tests.boot import settle
    p = settle(game)                       # through the loading screen
    assert isinstance(p, PlayingState)
    return game, p


class PlacementTests(unittest.TestCase):
    def test_one_interactable_per_special_room_at_its_centre(self):
        _, p = fresh_playing()
        specials = [r for r in p.game_map.layout.rooms if r.kind in SPECIAL_KINDS]
        self.assertEqual(len(p.interactables), len(specials))
        by_kind = {it.kind: it for it in p.interactables}
        for room in specials:
            it = by_kind[room.kind]
            self.assertAlmostEqual(it.pos.x, room.center.x)
            self.assertAlmostEqual(it.pos.y, room.center.y)
        pygame.quit()


class EffectTests(unittest.TestCase):
    def _get(self, p, kind):
        return next((it for it in p.interactables if it.kind == kind), None)

    def test_shrine_grants_a_blessing_and_is_consumed(self):
        _, p = fresh_playing()
        it = self._get(p, "shrine")
        if it is None:
            self.skipTest("no shrine in this layout")
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

    def test_treasure_adds_an_item_to_the_run_drops(self):
        _, p = fresh_playing()
        it = self._get(p, "treasure")
        if it is None:
            self.skipTest("no treasure in this layout")
        n = len(p.stats["dropped_items"])
        p._use_treasure(it)
        self.assertEqual(len(p.stats["dropped_items"]), n + 1)
        pygame.quit()

    def test_altar_costs_hp_and_refuses_when_too_low(self):
        _, p = fresh_playing()
        it = self._get(p, "altar")
        if it is None:
            self.skipTest("no altar in this layout")
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
        _, p = fresh_playing()
        it = self._get(p, "merchant")
        if it is None:
            self.skipTest("no merchant in this layout")
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

    def test_elite_arena_triggers_on_approach_and_rewards_on_clear(self):
        _, p = fresh_playing()
        it = self._get(p, "elite_arena")
        if it is None:
            self.skipTest("no elite arena in this layout")
        p.player.pos.update(it.pos)
        p._update_elite_arenas()
        self.assertEqual(it.state, "active")
        self.assertEqual(len(it.arena_ids), 3)
        drops = len(p.stats["dropped_items"])
        for e in p.enemies:
            e.alive = False
        p._update_elite_arenas()
        self.assertEqual(it.state, "done")
        self.assertEqual(len(p.stats["dropped_items"]), drops + 1)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
