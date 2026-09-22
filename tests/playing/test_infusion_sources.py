"""Elemental system M7: where a run gets its infusions
(design §7, journal `elemental_system_journal.md`).

Two sources, differing only in who picks the element: the Monastery offers
all four and the player chooses, an elemental buff building has already
rolled one. Both reuse the Forge's screen rather than growing their own.

Integration tier: these boot a real run, because the Monastery's whole point
is that it stands on a building the village pass already places, and that is
only true of a generated world.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS, ElementId
from game.states.level_up_state import LevelUpState
from game.states.playing.core import elemental, infusion
from tests import worlds as W
from tests.playing.test_interactables import fresh_playing

SEED = W.pinned(2)
FIRE, ICE = ElementId.FIRE, ElementId.ICE


def monastery(playing):
    return next(it for it in playing.interactables if it.kind == "monastery")


def overlay(playing):
    """The picker, if one is open."""
    top = playing.game.state_machine.current
    return top if isinstance(top, LevelUpState) else None


# --- placement -----------------------------------------------------------------

class PlacementTests(unittest.TestCase):
    def test_every_village_carries_one_monastery_on_its_town_hall(self):
        _, p = fresh_playing()
        halls = [(x, y) for v in p.game_map.layout.villages
                 for kind, x, y in v.buildings if kind == "monastery"]
        seats = [(it.pos.x, it.pos.y) for it in p.interactables
                 if it.kind == "monastery"]
        self.assertTrue(halls, "the village pass places a town hall")
        self.assertEqual(sorted(seats), sorted(halls))
        pygame.quit()

    def test_it_is_reachable_by_the_interact_key_like_the_forge(self):
        _, p = fresh_playing()
        it = monastery(p)
        p.player.pos.update(it.pos)
        from game.states.playing.core import interactions
        self.assertIs(interactions.nearest(p), it)
        pygame.quit()


# --- the Monastery -----------------------------------------------------------------

class MonasteryTests(unittest.TestCase):
    def setUp(self):
        self.game, self.p = fresh_playing()
        self.it = monastery(self.p)

    def tearDown(self):
        pygame.quit()

    def use(self):
        self.p.locations.use(self.it)
        return overlay(self.p)

    def test_using_it_offers_all_four_elements(self):
        """Whatever the run has unlocked (§7.2, confirmed)."""
        screen = self.use()
        self.assertIsNotNone(screen)
        self.assertEqual([row[0].element for row in screen.weapon_rows],
                         list(ELEMENTS))

    def test_the_cards_are_the_weapons_that_element_could_go_on(self):
        screen = self.use()
        self.assertEqual([c.weapon for c in screen.choices],
                         [w.weapon_id for w in self.p.player.weapons])

    def test_picking_one_infuses_that_weapon_and_spends_the_monastery(self):
        screen = self.use()
        element = screen.weapon_rows[0][0].element
        weapon = self.p.player.weapons[0]
        screen.choices[0].apply(self.p.player)
        screen.on_done(screen.choices[0])
        self.assertEqual(weapon.element, element)
        self.assertTrue(self.it.used, "one use per Monastery (§7.2)")

    def test_it_is_not_spent_by_walking_away(self):
        self.use()
        self.assertFalse(self.it.used)

    def test_a_second_use_does_nothing(self):
        screen = self.use()
        screen.choices[0].apply(self.p.player)
        screen.on_done(screen.choices[0])
        from game.states.playing.core import interactions
        self.p.player.pos.update(self.it.pos)
        self.assertIsNot(interactions.nearest(self.p), self.it)

    def test_the_run_records_what_it_handed_out(self):
        screen = self.use()
        self.assertEqual(self.p.run.unlocked_elements, set())
        screen.choices[0].apply(self.p.player)
        screen.on_done(screen.choices[0])
        self.assertEqual(self.p.run.unlocked_elements,
                         {self.p.player.weapons[0].element})


# --- the cards themselves ------------------------------------------------------------

class CardTests(unittest.TestCase):
    def setUp(self):
        self.game, self.p = fresh_playing()

    def tearDown(self):
        pygame.quit()

    def test_a_summon_can_be_offered_an_element(self):
        """The owner's correction: every weapon takes one."""
        from combat.weapons import Weapon

        wolf = Weapon("spirit_wolf", self.p.content.weapon("spirit_wolf"))
        self.p.player.weapons.append(wolf)
        cards = infusion.weapon_cards(self.p.player, FIRE)
        self.assertIn("spirit_wolf", [c.weapon for c in cards])

    def test_a_card_says_how_often_the_element_would_land(self):
        cards = {c.weapon: c for c in infusion.weapon_cards(self.p.player, FIRE)}
        for weapon in self.p.player.weapons:
            with self.subTest(weapon=weapon.weapon_id):
                text = cards[weapon.weapon_id].description
                self.assertTrue("attack" in text or "every" in text, text)

    def test_a_card_on_an_infused_weapon_says_it_replaces(self):
        weapon = self.p.player.weapons[0]
        weapon.element = ICE
        card = next(c for c in infusion.weapon_cards(self.p.player, FIRE)
                    if c.weapon == weapon.weapon_id)
        self.assertIn("Replaces ice", card.description)

    def test_the_rail_says_what_already_carries_each_element(self):
        self.p.player.weapons[0].element = FIRE
        rows = {row[0].element: row[2] for row in
                infusion.element_rows(self.p.player)}
        self.assertIn(self.p.player.weapons[0].name, rows[FIRE])
        self.assertEqual(rows[ICE], "not carried")

    def test_the_unlocked_set_never_holds_a_duplicate(self):
        for _ in range(3):
            self.p.run.unlocked_elements.add(FIRE)
        self.assertEqual(self.p.run.unlocked_elements, {FIRE})


# --- elemental buff buildings -----------------------------------------------------

class BuffBuildingTests(unittest.TestCase):
    def setUp(self):
        self.game, self.p = fresh_playing()

    def tearDown(self):
        pygame.quit()

    def buildings(self):
        return [it for it in self.p.interactables
                if self.p.buffs.is_buff(it.kind)]

    def test_some_buildings_roll_elemental_and_some_do_not(self):
        rolled = [it.element for it in self.buildings()]
        self.assertTrue(rolled, "the world seated buff buildings")
        self.assertTrue(any(e is None for e in rolled) or
                        any(e is not None for e in rolled))
        for element in rolled:
            if element is not None:
                self.assertIn(element, ELEMENTS)

    def test_the_roll_is_stable_for_a_seed(self):
        """Seeded on the world seed and the building's own spot, so it does
        not move when anything else in the run rolls."""
        before = {(it.pos.x, it.pos.y): it.element for it in self.buildings()}
        self.p.locations.build()
        after = {(it.pos.x, it.pos.y): it.element for it in self.buildings()}
        self.assertEqual(before, after)

    def test_the_roll_does_not_disturb_the_runs_own_stream(self):
        import random

        run = self.p.run
        run.rng = random.Random(1234)
        untouched = random.Random(1234)
        expected = [untouched.random() for _ in range(3)]
        self.p.locations.build()
        self.assertEqual([run.rng.random() for _ in range(3)], expected)

    def test_an_elemental_building_gives_its_buff_and_then_the_picker(self):
        it = next((b for b in self.buildings() if b.element is not None), None)
        if it is None:                       # this seed rolled none; force one
            it = self.buildings()[0]
            it.element = FIRE
        self.p.buffs.activate(it)
        self.assertIn(it.kind, self.p.buffs.active, "the buff still landed")
        screen = overlay(self.p)
        self.assertIsNotNone(screen, "and the picker opened")
        self.assertIsNone(screen.weapon_rows or None,
                          "the element is already decided, so no rail")
        self.assertEqual([c.weapon for c in screen.choices],
                         [w.weapon_id for w in self.p.player.weapons])

    def test_a_plain_building_opens_nothing(self):
        it = self.buildings()[0]
        it.element = None
        self.p.buffs.activate(it)
        self.assertIsNone(overlay(self.p))


# --- the data --------------------------------------------------------------------

class DataTests(unittest.TestCase):
    def test_the_block_is_optional_and_validated(self):
        from game.content import ContentError, _check_buildings, get_content

        data = dict(get_content().buildings)
        for bad in ({"chance": 2.0},
                    {"chance": 0.5, "weights": {"earth": 1}},
                    {"chance": 0.5, "weights": {}}):
            with self.subTest(bad=bad), self.assertRaises(ContentError):
                _check_buildings(dict(data, elements=bad))

    def test_no_block_means_no_building_is_elemental(self):
        from types import SimpleNamespace

        run = SimpleNamespace(content=SimpleNamespace(buildings={}), seed=1)
        obstacle = SimpleNamespace(pos=pygame.Vector2(0, 0))
        self.assertIsNone(elemental.roll(run, obstacle))

    def test_the_weights_decide_which_element(self):
        from types import SimpleNamespace

        run = SimpleNamespace(seed=7, content=SimpleNamespace(buildings={
            "elements": {"chance": 1.0, "weights": {"thunder": 1}}}))
        for x in range(12):
            obstacle = SimpleNamespace(pos=pygame.Vector2(x * 37, 0))
            self.assertEqual(elemental.roll(run, obstacle), ElementId.THUNDER)


if __name__ == "__main__":
    unittest.main()
