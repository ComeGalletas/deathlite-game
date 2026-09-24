"""CMB-009.5: the dev menu seats an elemental buff building beside the hero.

Integration tier: a real developer run on a pinned seed, because what is
pinned is that the building goes through the world's own compound, skin and
interactable code -- and that using it runs the ordinary buff and infusion
flow.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS
from entities.obstacle import satellites_of
from game.game import Game
from game.states.dev_menu_state import _HEADINGS, _ROOT_ROWS
from game.states.menu_state import MenuState
from game.states.playing.core.state import PlayingState
from game.states.playing.devtools import element_building
from game.states.playing.devtools.element_building import spawn_elemental_building
from tests import worlds as W
from tests.boot import start_run

SEED = W.pinned(0)


def _run():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    return game, start_run(game, seed=SEED, dev=True)


class ElementBuildingTests(unittest.TestCase):
    def setUp(self):
        self.game, self.ps = _run()
        self.run = self.ps.run

    def _spawn(self, element=ELEMENTS[0], kind=None):
        before = len(self.run.game_map.obstacles)
        ok, message = spawn_elemental_building(self.ps, element, kind=kind)
        return ok, message, before

    def test_it_is_seated_as_the_world_seats_a_building(self):
        ok, _msg, before = self._spawn(kind="magnet")
        self.assertTrue(ok)
        gm = self.run.game_map
        added = gm.obstacles[before:]
        self.assertEqual(len(added), 1 + len(satellites_of("magnet")),
                         "the primary and its collide-only satellites")
        primary = added[0]
        self.assertTrue(primary.skin)
        self.assertTrue(all(not o.skin for o in added[1:]))
        self.assertIn(before, gm._decos, "the primary wears the kind's art")
        near = gm._obstacle_index.near(primary.pos.x, primary.pos.y, 1.0)
        self.assertIn(primary, near, "the obstacle index was rebuilt")

    def test_it_stands_near_the_hero_on_clear_ground(self):
        """Where the spot search said -- every circle of the compound was on
        walkable ground clear of every obstacle before it was seated (after,
        its own collider fills the spot, so that cannot be asked then)."""
        gm = self.run.game_map
        spot = element_building._free_spot(gm, self.run.player.pos, "magnet")
        self.assertIsNotNone(spot)
        self._spawn(kind="magnet")
        it = self.run.interactables[-1]
        self.assertEqual((it.pos.x, it.pos.y), (spot.x, spot.y))
        self.assertLess((it.pos - self.run.player.pos).length(), 9 * 64)
        self.assertFalse(gm.is_walkable(pygame.Vector2(it.pos), 1.0),
                         "and now it is solid")

    def test_it_carries_the_chosen_element(self):
        for element in ELEMENTS:
            self._spawn(element)
            self.assertEqual(self.run.interactables[-1].element, element)

    def test_the_kind_takes_the_buff_kinds_in_turn(self):
        kinds = list(self.ps.buffs.kinds)
        got = []
        for _ in range(len(kinds)):
            self._spawn()
            got.append(self.run.interactables[-1].kind)
        self.assertEqual(sorted(got), sorted(kinds))

    def test_using_it_runs_the_buff_and_offers_the_element(self):
        self._spawn(ELEMENTS[0], kind="magnet")
        it = self.run.interactables[-1]
        self.run.player.pos.update(it.pos.x, it.pos.y + it.radius * 0.5)
        self.assertIs(self.ps.locations.nearby(), it)
        self.ps.locations.use(it)
        self.assertTrue(it.used)
        self.assertIn("magnet", self.ps.buffs.active)
        self.assertNotIsInstance(self.game.state_machine.current, PlayingState,
                                 "the weapon picker for the element opened")

    def test_no_room_says_so_and_changes_nothing(self):
        before = len(self.run.game_map.obstacles)
        with mock.patch.object(element_building, "_free_spot", return_value=None):
            ok, message = spawn_elemental_building(self.ps, ELEMENTS[0], kind="magnet")
        self.assertFalse(ok)
        self.assertIn("No room", message)
        self.assertEqual(len(self.run.game_map.obstacles), before)

    def test_it_is_a_dev_menu_page(self):
        self.assertIn("element_building", _ROOT_ROWS)
        self.assertIn("buildings", _HEADINGS)


if __name__ == "__main__":
    unittest.main()
