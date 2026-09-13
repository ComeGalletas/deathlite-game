"""The Forge's weapon picker (change request 6).

The Forge used to reforge `eligible[0]`, so a player carrying two qualifying
weapons could not choose the second one at all. What is pinned here: the rail
lists every non-summon weapon and says *why* each one can or cannot be forged,
selecting a weapon swaps the cards to that weapon's Forgings, an ineligible row
cannot be chosen by key or by click, and the level-up screen is untouched.

Driven with fakes and a recording state machine -- no run, no world -- so these
stay in the `unit` tier.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.states.level_up_state import LevelUpState
from progression.upgrades import Upgrade
from ui.forge_rail import ForgeRail, rows_for
from ui.level_up import CARD_W, CARD_W_NARROW


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class _Weapon:
    def __init__(self, wid, name, levels=0, forge=None, is_summon=False):
        self.weapon_id = wid
        self.name = name
        self.forge = forge
        self.is_summon = is_summon
        self._levels = levels


def _levels(w):
    return w._levels


def _upgrade(wid, title):
    return Upgrade(id=f"forge:{title}", title=title, description="", weight=1.0,
                   apply=lambda p: None, max_stacks=1, tags=(), kind="forge",
                   rarity="forge", level=1, weapon=wid)


class _Recorder:
    def __init__(self):
        self.popped = 0

    def pop(self):
        self.popped += 1


def _state(rows, offers=None):
    game = SimpleNamespace(state_machine=_Recorder(), assets=None)
    s = LevelUpState(game)
    s.enter(player=SimpleNamespace(), weapon_rows=rows, cancelable=True,
            offers_for=offers or (lambda w: [_upgrade(w.weapon_id, f"Forge {w.name} A"),
                                             _upgrade(w.weapon_id, f"Forge {w.name} B")]))
    return s


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


class RowTests(unittest.TestCase):
    """`rows_for` turns the roster into what the rail shows."""

    def test_an_eligible_weapon_says_its_count(self):
        rows = rows_for([_Weapon("sword", "Sword", levels=3)], 2, _levels)
        self.assertEqual(len(rows), 1)
        weapon, eligible, note = rows[0]
        self.assertTrue(eligible)
        self.assertEqual(note, "3 / 2 blessings")

    def test_a_short_weapon_says_how_many_more(self):
        rows = rows_for([_Weapon("bow", "Bow", levels=1)], 2, _levels)
        self.assertFalse(rows[0][1])
        self.assertEqual(rows[0][2], "1 / 2 - needs 1 more blessing")

    def test_the_plural_is_right_for_two_short(self):
        rows = rows_for([_Weapon("bow", "Bow", levels=0)], 2, _levels)
        self.assertEqual(rows[0][2], "0 / 2 - needs 2 more blessings")

    def test_an_already_forged_weapon_names_what_it_became(self):
        w = _Weapon("sword", "Whirlwind", levels=5, forge="whirlwind")
        rows = rows_for([w], 2, _levels, forged_name=lambda x: x.name)
        self.assertFalse(rows[0][1])
        self.assertEqual(rows[0][2], "already forged into Whirlwind")

    def test_a_summon_is_never_listed(self):
        """It can never qualify, so a row for it would be a permanent dead
        entry the player cannot act on."""
        rows = rows_for([_Weapon("ember_ring", "Ember Ring", levels=9, is_summon=True),
                         _Weapon("sword", "Sword", levels=2)], 2, _levels)
        self.assertEqual([r[0].weapon_id for r in rows], ["sword"])

    def test_exactly_the_requirement_qualifies(self):
        """"Two or more" -- the owner confirmed the existing `>=` rule."""
        self.assertTrue(rows_for([_Weapon("s", "S", levels=2)], 2, _levels)[0][1])
        self.assertFalse(rows_for([_Weapon("s", "S", levels=1)], 2, _levels)[0][1])


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def setUp(self):
        self.rows = rows_for(
            [_Weapon("sword", "Sword", levels=2),
             _Weapon("hammer", "Hammer", levels=0),     # ineligible, in the middle
             _Weapon("bow", "Bow", levels=3)], 2, _levels)

    def test_it_opens_on_the_first_eligible_weapon(self):
        s = _state(self.rows)
        self.assertEqual(s.weapon_sel, 0)
        self.assertTrue(all("Sword" in c.title for c in s.choices))

    def test_down_skips_the_ineligible_weapon(self):
        """Landing on a row with no cards behind it would empty the middle."""
        s = _state(self.rows)
        s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(s.weapon_sel, 2)               # the Bow, not the Hammer
        self.assertTrue(all("Bow" in c.title for c in s.choices))

    def test_up_wraps_the_other_way(self):
        s = _state(self.rows)
        s.handle_event(_key(pygame.K_UP))
        self.assertEqual(s.weapon_sel, 2)

    def test_changing_weapon_resets_the_card_cursor(self):
        s = _state(self.rows)
        s.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(s.selected, 1)
        s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(s.selected, 0)

    def test_an_ineligible_weapon_cannot_be_selected_directly(self):
        s = _state(self.rows)
        s._select_weapon(1)                              # the Hammer
        self.assertEqual(s.weapon_sel, 0)

    def test_the_rail_only_registers_selectable_rows(self):
        """So a click on a weapon that cannot be forged does nothing."""
        s = _state(self.rows)
        surface = pygame.Surface((1600, 900))
        s.draw(surface)
        self.assertIsNotNone(s.rail.hits.rect_of(0))     # Sword
        self.assertIsNone(s.rail.hits.rect_of(1))        # Hammer
        self.assertIsNotNone(s.rail.hits.rect_of(2))     # Bow

    def test_escape_still_leaves(self):
        s = _state(self.rows)
        s.handle_event(_key(pygame.K_ESCAPE))
        self.assertEqual(s.game.state_machine.popped, 1)

    def test_the_cards_are_narrower_so_the_rail_fits(self):
        s = _state(self.rows)
        self.assertEqual(s.card_width, CARD_W_NARROW)

    def test_with_only_one_eligible_weapon_the_picker_stays_put(self):
        rows = rows_for([_Weapon("sword", "Sword", levels=2),
                         _Weapon("bow", "Bow", levels=0)], 2, _levels)
        s = _state(rows)
        s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(s.weapon_sel, 0)


class LevelUpIsUntouchedTests(unittest.TestCase):
    """Without the two new arguments this is the level-up screen it was."""

    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def _plain(self):
        game = SimpleNamespace(state_machine=_Recorder(), assets=None)
        s = LevelUpState(game)
        s.enter(player=SimpleNamespace(),
                choices=[_upgrade("sword", "A"), _upgrade("sword", "B")])
        return s

    def test_no_rail_and_the_full_card_width(self):
        s = self._plain()
        self.assertIsNone(s.rail)
        self.assertEqual(s.card_width, CARD_W)
        self.assertEqual(s.weapon_rows, [])

    def test_up_and_down_do_nothing(self):
        """They are the rail's keys; the level-up screen never had them."""
        s = self._plain()
        s.handle_event(_key(pygame.K_DOWN))
        s.handle_event(_key(pygame.K_UP))
        self.assertEqual(s.selected, 0)

    def test_left_and_right_still_move_the_cards(self):
        s = self._plain()
        s.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(s.selected, 1)


class RailLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def test_the_rail_sits_left_of_the_cards_on_both_profiles(self):
        """It is placed relative to the cards, not at a fixed x, so it stays
        beside them at 1600 and at the 1280 web profile."""
        from ui.forge_rail import WIDTH
        rows = rows_for([_Weapon("sword", "Sword", levels=2),
                         _Weapon("bow", "Bow", levels=2)], 2, _levels)
        for w, h in ((1600, 900), (1280, 720)):
            with self.subTest(f"{w}x{h}"):
                s = _state(rows)
                s.draw(pygame.Surface((w, h)))
                card = s.panel.hits.rect_of(0)
                rail = s.rail.hits.rect_of(0)
                self.assertLess(rail.right, card.left, "the rail overlaps the cards")
                self.assertGreaterEqual(rail.left, 0, "the rail runs off screen")
                self.assertEqual(rail.width, WIDTH)


if __name__ == "__main__":
    unittest.main()
