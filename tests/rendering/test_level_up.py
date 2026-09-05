"""Mouse support, group D: the level-up / blessing cards.

Hover selects a card, one click picks it (spec 3.5's keyboard path is
untouched). Driven through a real headless run so the pick applies the
upgrade and pops back to PLAYING exactly as `1 / 2 / 3` would.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.level_up_state import LevelUpState
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState
from progression.experience import xp_for_level


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def _mouse(game, event_type, pos, button=1):
    kw = {"pos": pos}
    if event_type == pygame.MOUSEMOTION:
        kw.update(rel=(0, 0), buttons=(0, 0, 0))
    else:
        kw["button"] = button
    game.state_machine.handle_event(pygame.event.Event(event_type, **kw))


def _click(game, pos):
    _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
    _mouse(game, pygame.MOUSEBUTTONUP, pos)


def _run():
    from tests.boot import settle
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    for _ in range(2):
        _key(game, pygame.K_RETURN)
    ps = settle(game)
    assert isinstance(ps, PlayingState)
    return game, ps


def _taken(ps) -> int:
    """How much the hero has gained: stacks + weapons + blessing stacks."""
    p = ps.player
    return (sum(p.upgrade_stacks.values()) + len(p.weapons)
            + sum(p.blessings.values()))


class LevelUpMouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _run()

    def setUp(self):
        """Force a level-up overlay onto the shared run and draw it once so
        the cards are registered."""
        game, ps = self.game, self.ps
        if not isinstance(game.state_machine.current, PlayingState):
            game.state_machine.change(ps)
        ps._awaiting_level_up = False
        ps.levels.add_xp(xp_for_level(ps.levels.level) - ps.levels.xp_into_level)
        ps._open_level_up()
        self.lu = game.state_machine.current
        self.assertIsInstance(self.lu, LevelUpState)
        self.lu.draw(game.screen)

    def _card(self, i):
        return self.lu.panel.hits.rect_of(i).center

    def test_cards_are_registered_side_by_side(self):
        n = len(self.lu.choices)
        rects = [self.lu.panel.hits.rect_of(i) for i in range(n)]
        self.assertTrue(all(r is not None for r in rects))
        for a, b in zip(rects, rects[1:]):
            self.assertLessEqual(a.right, b.left)
            self.assertEqual(a.top, b.top)

    def test_hover_selects_without_picking(self):
        last = len(self.lu.choices) - 1
        _mouse(self.game, pygame.MOUSEMOTION, self._card(last))
        self.assertEqual(self.lu.selected, last)
        self.assertIs(self.game.state_machine.current, self.lu)

    def test_one_click_picks_applies_and_returns_to_the_run(self):
        before = _taken(self.ps)
        want = self.lu.choices[1]
        _click(self.game, self._card(1))
        self.assertIs(self.game.state_machine.current, self.ps)
        self.assertGreater(_taken(self.ps), before)
        self.assertFalse(self.ps._awaiting_level_up)
        self.assertGreaterEqual(self.ps.player.upgrade_stacks.get(want.id, 0), 1)

    def test_click_without_a_prior_hover_picks_that_card(self):
        want = self.lu.choices[0]
        _mouse(self.game, pygame.MOUSEMOTION, self._card(2))       # hovering elsewhere
        _click(self.game, self._card(0))
        self.assertIs(self.game.state_machine.current, self.ps)
        self.assertGreaterEqual(self.ps.player.upgrade_stacks.get(want.id, 0), 1)

    def test_release_on_another_card_does_nothing(self):
        before = _taken(self.ps)
        _mouse(self.game, pygame.MOUSEBUTTONDOWN, self._card(0))
        _mouse(self.game, pygame.MOUSEBUTTONUP, self._card(1))
        self.assertIs(self.game.state_machine.current, self.lu)
        self.assertEqual(_taken(self.ps), before)
        _key(self.game, pygame.K_1)                                 # clean up: pick

    def test_click_between_cards_does_nothing(self):
        r0, r1 = self.lu.panel.hits.rect_of(0), self.lu.panel.hits.rect_of(1)
        gap = ((r0.right + r1.left) // 2, r0.centery)
        before = _taken(self.ps)
        _click(self.game, gap)
        self.assertIs(self.game.state_machine.current, self.lu)
        self.assertEqual(_taken(self.ps), before)
        _key(self.game, pygame.K_1)

    def test_the_run_comes_back_with_the_mouse_disarmed(self):
        # `_open_level_up` disarmed it; the pick must not re-arm it -- only a
        # frame with the button up does (group C).
        self.assertFalse(self.ps._mouse_armed)
        _click(self.game, self._card(0))
        self.assertIs(self.game.state_machine.current, self.ps)
        self.assertFalse(self.ps._mouse_armed)
        self.assertFalse(self.ps._tap_pending)

    def test_keyboard_still_picks(self):
        before = _taken(self.ps)
        _key(self.game, pygame.K_2)
        self.assertIs(self.game.state_machine.current, self.ps)
        self.assertGreater(_taken(self.ps), before)


if __name__ == "__main__":
    unittest.main()


class LevelUpCardArtTests(unittest.TestCase):
    """UI art, group D: the cards on the panel sheets -- gold for the
    selected card, pressed while the button is held on one."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _run()

    def setUp(self):
        game, ps = self.game, self.ps
        if not isinstance(game.state_machine.current, PlayingState):
            game.state_machine.change(ps)
        ps._awaiting_level_up = False
        ps.levels.add_xp(xp_for_level(ps.levels.level) - ps.levels.xp_into_level)
        ps._open_level_up()
        self.lu = game.state_machine.current
        self.assertIsInstance(self.lu, LevelUpState)
        self.lu.draw(game.screen)

    def tearDown(self):
        if isinstance(self.game.state_machine.current, LevelUpState):
            _key(self.game, pygame.K_1)                            # leave the overlay

    def _states(self):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_button", wraps=widgets.draw_button) as m:
            self.lu.draw(self.game.screen)
        panels = [c for c in m.call_args_list if c.kwargs.get("shape") == "panel"]
        self.assertEqual(len(panels), len(self.lu.choices))
        self.assertTrue(all(c.args[1] is self.game.assets for c in panels))
        return [c.kwargs["state"] for c in panels]

    def test_selected_gold_rest_blue_and_it_follows_hover(self):
        self.assertEqual(self._states()[0], "hover")
        self.assertNotIn("pressed", self._states())
        last = len(self.lu.choices) - 1
        _mouse(self.game, pygame.MOUSEMOTION, self.lu.panel.hits.rect_of(last).center)
        states = self._states()
        self.assertEqual(states[last], "hover")
        self.assertEqual(states.count("hover"), 1)

    def test_held_button_presses_the_card_under_it(self):
        pos = self.lu.panel.hits.rect_of(1).center
        _mouse(self.game, pygame.MOUSEBUTTONDOWN, pos)
        self.assertEqual(self._states()[1], "pressed")
        self.assertIs(self.game.state_machine.current, self.lu)      # not picked yet
        _mouse(self.game, pygame.MOUSEBUTTONUP, (5, 5))              # released off
        self.assertNotIn("pressed", self._states())
        self.assertIs(self.game.state_machine.current, self.lu)

    def test_panel_without_assets_falls_back_and_still_registers_cards(self):
        from ui.level_up import LevelUpPanel
        panel = LevelUpPanel()
        panel.draw(self.game.screen, self.lu.choices, 0)           # assets=None
        self.assertEqual(len(panel.hits), len(self.lu.choices))

    def test_art_lands_on_screen(self):
        rect = self.lu.panel.hits.rect_of(0)                         # selected -> gold
        sheet = self.game.assets.image("btn_gold_panel")
        self.assertEqual(self.game.screen.get_at((rect.left + 12, rect.top + 12)),
                         sheet.get_at((12, 12)))


class LevelUpTextTests(unittest.TestCase):
    """Fonts, group F: the card name is a title (title face, black), the rest
    of the card text dark grey, and the cards are 15 px taller downwards."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _run()

    def setUp(self):
        game, ps = self.game, self.ps
        if not isinstance(game.state_machine.current, PlayingState):
            game.state_machine.change(ps)
        ps._awaiting_level_up = False
        ps.levels.add_xp(xp_for_level(ps.levels.level) - ps.levels.xp_into_level)
        ps._open_level_up()
        self.lu = game.state_machine.current
        self.assertIsInstance(self.lu, LevelUpState)
        self.lu.draw(game.screen)

    def tearDown(self):
        if isinstance(self.game.state_machine.current, LevelUpState):
            _key(self.game, pygame.K_1)

    @staticmethod
    def _has_colour(screen, rect, colour):
        want = tuple(colour) + (255,)
        return any(tuple(screen.get_at((x, y))) == want
                   for x in range(rect.left, rect.right) for y in range(rect.top, rect.bottom))

    def test_cards_grew_downwards_only(self):
        from game import config
        h = config.SCREEN_HEIGHT
        for i in range(len(self.lu.choices)):
            r = self.lu.panel.hits.rect_of(i)
            self.assertEqual(r.height, 215)
            self.assertEqual(r.top, h // 2 - 100)                     # where a 200-tall card sat

    def test_title_is_the_title_face(self):
        from game import fonts
        probe = "Fleet Foot"
        self.assertEqual(self.lu.panel._name.size(probe), fonts.heading(24).size(probe))
        self.assertNotEqual(self.lu.panel._name.size(probe), fonts.body(24).size(probe))

    def test_card_text_colours(self):
        from game import config
        screen = self.game.screen
        card = self.lu.panel.hits.rect_of(1)                            # unselected -> blue art
        title_band = pygame.Rect(card.left + 16, card.top + 44, card.width - 32, 30)
        desc_band = pygame.Rect(card.left + 16, card.top + 90, card.width - 32, 50)
        self.assertTrue(self._has_colour(screen, title_band, config.COLOR_ON_BUTTON))
        self.assertTrue(self._has_colour(screen, desc_band, config.COLOR_ON_BUTTON_DIM))
        self.assertFalse(self._has_colour(screen, card, config.COLOR_TEXT))
        self.assertFalse(self._has_colour(screen, card, config.COLOR_TEXT_DIM))
        self.assertFalse(self._has_colour(screen, card, (120, 130, 160)))   # the old tag colour
