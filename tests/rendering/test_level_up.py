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
        from ui.level_up import _CARD_H, _CARD_TOP_H
        h = config.SCREEN_HEIGHT
        self.assertGreater(_CARD_H, _CARD_TOP_H)                      # growth, not a re-centre
        for i in range(len(self.lu.choices)):
            r = self.lu.panel.hits.rect_of(i)
            self.assertEqual(r.height, _CARD_H)
            self.assertEqual(r.top, h // 2 - _CARD_TOP_H // 2)        # where a 200-tall card sat
            self.assertLess(r.bottom + 60 + 20, h)                    # the hint still fits under it

    def test_title_is_the_title_face(self):
        from game import fonts
        probe = "Fleet Foot"
        self.assertEqual(self.lu.panel._name.size(probe), fonts.heading(24).size(probe))
        self.assertNotEqual(self.lu.panel._name.size(probe), fonts.body(24).size(probe))

    def test_card_text_colours(self):
        from game import config
        screen = self.game.screen
        from ui.level_up import _DESC_GAP, _DESC_TOP, _TAG_UP
        card = self.lu.panel.hits.rect_of(1)                            # unselected -> blue art
        title_band = pygame.Rect(card.left + 16, card.top + 44, card.width - 32, 30)
        # The band the description may occupy. It is centred in that band rather
        # than pinned to its top (change request 5 option B), so a short card
        # draws well below `_DESC_TOP` -- this has to be the whole band, not the
        # old fixed 50 px slice. It still stops short of the category line,
        # which is drawn in the same dim colour and would pass the check for it.
        band_bottom = (card.height - _TAG_UP
                       - self.lu.panel._hint.get_height() - _DESC_GAP)
        desc_band = pygame.Rect(card.left + 16, card.top + _DESC_TOP,
                                card.width - 32, band_bottom - _DESC_TOP)
        self.assertTrue(self._has_colour(screen, title_band, config.COLOR_ACCENT))      # card titles: gold
        self.assertTrue(self._has_colour(screen, desc_band, config.COLOR_ON_BUTTON_DIM))
        # (The descriptions are white again by the owner's 2026-09-10 rule, so the
        # old "no light text on the card" check no longer applies.)
        self.assertFalse(self._has_colour(screen, card, config.COLOR_TEXT_DIM))
        self.assertFalse(self._has_colour(screen, card, (120, 130, 160)))   # the old tag colour


class TitleShadowAndBadgeTests(unittest.TestCase):
    """Owner (2026-09-10): the card number sits 25 px further in, and card
    titles carry a dark drop shadow under the gold."""

    def test_shadowed_puts_the_shadow_two_pixels_down_right(self):
        from game import config, fonts
        from ui.text import shadowed
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        font = fonts.heading(24)
        plain = font.render("Aegis", True, config.COLOR_ACCENT)
        s = shadowed(font, "Aegis", config.COLOR_ACCENT)
        self.assertEqual(s.get_size(), (plain.get_width() + 2, plain.get_height() + 2))
        gold = {(x, y) for x in range(plain.get_width()) for y in range(plain.get_height())
                if plain.get_at((x, y))[3] == 255}                # fully opaque: no AA blend
        self.assertTrue(gold)
        # every opaque gold pixel stays gold on top (anti-aliased edges blend
        # a little with the shadow beneath, hence the tolerance)
        for x, y in list(gold)[:200]:
            got = s.get_at((x, y))[:3]
            for a, b in zip(got, config.COLOR_ACCENT):
                self.assertLessEqual(abs(a - b), 24, (x, y, got))
        # a pixel that is gold in the plain render but empty two px up-left
        # in it shows the shadow colour in the composite
        edge = next(((x, y) for x, y in gold
                     if (x + 2 >= plain.get_width() or y + 2 >= plain.get_height()
                         or plain.get_at((x + 2, y + 2))[3] < 20)), None)
        self.assertIsNotNone(edge)
        self.assertEqual(s.get_at((edge[0] + 2, edge[1] + 2))[:3], (28, 28, 34))

    def test_the_card_number_sits_25px_further_right(self):
        import inspect
        from ui import level_up
        src = inspect.getsource(level_up.LevelUpPanel.draw)
        self.assertIn("(x + 39, y + 10 + dy)", src)
        self.assertIn('f"#{i + 1}"', src, "the badge reads #1, #2, #3 (owner, 2026-09-10)")


class CategoryLineTests(unittest.TestCase):
    """Owner (2026-09-10): the category line sits 25 px higher and every
    word is capitalised ("Sword Power", "Hero Power")."""

    def test_the_line_is_capitalised_and_25px_higher(self):
        import inspect
        from ui import level_up
        src = inspect.getsource(level_up.LevelUpPanel.draw)
        self.assertIn("y + card_h - 39 + dy", src)
        self.assertNotIn("y + card_h - 14 + dy", src)
        words = " ".join(t[:1].upper() + t[1:] for t in ("hero", "power"))
        self.assertEqual(words, "Hero Power")
        words = " ".join(t[:1].upper() + t[1:] for t in ("Magic Rod", "behavior"))
        self.assertEqual(words, "Magic Rod Behavior")


class DescriptionCentringTests(unittest.TestCase):
    """Change request 5 option B (owner, 2026-09-11): the card is 50 px taller
    and the description is *centred* in the band between the title and the
    category line, instead of being pinned under the title.

    316 of the catalog's 345 rendered descriptions are one or two lines, so
    pinning them left the text stranded over an empty half-card once the card
    grew. A description long enough to fill the band still starts at the band's
    top, so the longest cards are laid out exactly as they were.

    The panel is driven directly with synthetic choices -- no run and no
    assets -- so these cost milliseconds. The module still sits in the
    `integration` tier, because the tier is assigned by path and its other
    classes boot a real `Game`.
    """

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def setUp(self):
        from ui.level_up import LevelUpPanel
        self.panel = LevelUpPanel()

    def _band(self, card):
        from ui.level_up import _DESC_GAP, _DESC_TOP, _TAG_UP
        top = card.top + _DESC_TOP
        bottom = (card.bottom - _TAG_UP
                  - self.panel._hint.get_height() - _DESC_GAP)
        return top, bottom

    def _text_span(self, description):
        """(top, bottom) of the description's painted pixels, and the band it
        was laid out in. Drawn without assets so the card is the flat fallback
        and the only dim-coloured text in the band is the description."""
        from types import SimpleNamespace
        from game import config
        surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        choice = SimpleNamespace(title="Probe", description=description,
                                 tags=("hero", "power"), rarity="common")
        self.panel.draw(surface, [choice], 0, assets=None)
        card = self.panel.hits.rect_of(0)
        band_top, band_bottom = self._band(card)
        want = tuple(config.COLOR_ON_BUTTON_DIM) + (255,)
        ys = [y for y in range(band_top, band_bottom)
              for x in range(card.left + 16, card.right - 16)
              if tuple(surface.get_at((x, y))) == want]
        self.assertTrue(ys, "no description text found in the band")
        return min(ys), max(ys), band_top, band_bottom

    def test_a_one_line_description_is_centred_not_pinned(self):
        from ui.level_up import _DESC_TOP
        top, bottom, band_top, band_bottom = self._text_span("+3% critical hit chance.")
        self.assertGreater(top, band_top + 20,
                           "a short description is still pinned under the title")
        self.assertAlmostEqual((top + bottom) // 2, (band_top + band_bottom) // 2,
                               delta=8)

    def test_the_longest_catalog_description_is_still_centred(self):
        """`bow_crossfire` is the catalog's worst case at four lines, and the
        band holds five -- so even it has slack and is centred, not pinned."""
        crossfire = ("+70% Bow damage against Rod-marked enemies, and +70% Rod "
                     "damage against enemies the Bow hit in the last 1.5 s.")
        top, bottom, band_top, band_bottom = self._text_span(crossfire)
        self.assertGreater(top, band_top)
        self.assertAlmostEqual((top + bottom) // 2, (band_top + band_bottom) // 2,
                               delta=8)

    def test_a_description_that_overflows_the_band_starts_at_its_top(self):
        """Nothing in the catalog is this long, but the clamp is what keeps a
        future one from riding up over the title instead of down over the tag."""
        overflowing = ("Every arrow that lands on a Rod-marked enemy within the "
                       "last 1.5 seconds deals a great deal more damage, and "
                       "marks spread to any enemy standing close enough to be "
                       "caught.")
        top, _bottom, band_top, _bb = self._text_span(overflowing)
        self.assertLess(top - band_top, 12, "the block rode above the band's top")

    def test_the_description_never_reaches_the_category_line(self):
        """The band stops short of the category line, which is drawn in the
        same colour -- so text and tag can never collide."""
        from ui.level_up import _CARD_H, _DESC_GAP, _TAG_UP
        for desc in ("+3% critical hit chance.",
                     "A wide sweeping arc. Reliable when enemies close in.",
                     "+70% Bow damage against Rod-marked enemies, and +70% Rod "
                     "damage against enemies the Bow hit in the last 1.5 s."):
            with self.subTest(lines=desc[:30]):
                _top, bottom, _bt, band_bottom = self._text_span(desc)
                self.assertLessEqual(bottom, band_bottom)

    def test_the_card_is_50px_taller_than_it_was(self):
        from ui.level_up import _CARD_H, _CARD_TOP_H
        self.assertEqual(_CARD_H, 295)                 # 245 + 50 (2026-09-11)
        self.assertEqual(_CARD_TOP_H, 200)             # the top edge did not move


if __name__ == "__main__":
    unittest.main()
