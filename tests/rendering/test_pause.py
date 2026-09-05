"""CB-5: the pause screen is a cursor menu -- Resume / Key layout / Quit to
menu. `Q` (the in-run auto-attack toggle) must never quit from here, and the
layout row cycles and persists exactly like the Options row.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, save as save_mod
from game.game import Game
from game.states.menu_state import MenuState
from game.states.paused_state import PausedState
from game.states.playing_state import PlayingState


def _paused():
    """A real run, paused. One world build per call -- the tests that need
    it are few."""
    from tests.boot import settle
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    for _ in range(2):
        _key(game, pygame.K_RETURN)
    ps = settle(game)
    assert isinstance(ps, PlayingState)
    _key(game, pygame.K_ESCAPE)
    assert isinstance(game.state_machine.current, PausedState)
    return game, ps, game.state_machine.current


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


class PauseMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps, cls.pause = _paused()

    def setUp(self):
        # Every test starts paused on the first row with the default layout.
        game = self.game
        if not isinstance(game.state_machine.current, PausedState):
            game.state_machine.change(self.ps)
            _key(game, pygame.K_ESCAPE)
        game.state_machine.current.sel = 0
        game.set_key_layout(config.DEFAULT_KEY_LAYOUT)

    def _row(self, name):
        from game.states.paused_state import _ROWS
        self.game.state_machine.current.sel = _ROWS.index(name)

    def test_escape_and_p_resume(self):
        _key(self.game, pygame.K_ESCAPE)
        self.assertIs(self.game.state_machine.current, self.ps)
        _key(self.game, pygame.K_ESCAPE)                 # pause again
        _key(self.game, pygame.K_p)
        self.assertIs(self.game.state_machine.current, self.ps)

    def test_resume_row(self):
        self._row("resume")
        _key(self.game, pygame.K_RETURN)
        self.assertIs(self.game.state_machine.current, self.ps)

    def test_q_does_nothing_here(self):
        for _ in range(3):
            _key(self.game, pygame.K_q)
        self.assertIsInstance(self.game.state_machine.current, PausedState)

    def test_up_down_wrap(self):
        from game.states.paused_state import _ROWS
        cur = self.game.state_machine.current
        _key(self.game, pygame.K_UP)
        self.assertEqual(cur.sel, len(_ROWS) - 1)
        _key(self.game, pygame.K_DOWN)
        self.assertEqual(cur.sel, 0)

    def test_key_layout_row_cycles_and_persists(self):
        self._row("key_layout")
        _key(self.game, pygame.K_RETURN)
        self.assertEqual(self.game.key_layout, "arrows_move")
        self.assertEqual(save_mod.load(self.game.save_path).settings["key_layout"],
                         "arrows_move")
        _key(self.game, pygame.K_RIGHT)                   # left / right cycle too
        self.assertEqual(self.game.key_layout, config.DEFAULT_KEY_LAYOUT)
        self.assertIsInstance(self.game.state_machine.current, PausedState)

    def test_left_right_off_the_layout_row_do_nothing(self):
        self._row("resume")
        _key(self.game, pygame.K_LEFT)
        self.assertEqual(self.game.key_layout, config.DEFAULT_KEY_LAYOUT)
        self.assertIsInstance(self.game.state_machine.current, PausedState)

    def test_draw_shows_the_layout(self):
        self.game.state_machine.current.draw(self.game.screen)   # must not raise

    def test_quit_row_returns_to_menu(self):
        self._row("quit")
        _key(self.game, pygame.K_RETURN)
        self.assertIsInstance(self.game.state_machine.current, MenuState)


if __name__ == "__main__":
    unittest.main()


class PauseMouseTests(unittest.TestCase):
    """Mouse support, group C: hover selects a pause row, a click picks it."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps, _ = _paused()

    def setUp(self):
        game = self.game
        if not isinstance(game.state_machine.current, PausedState):
            game.state_machine.change(self.ps)
            _key(game, pygame.K_ESCAPE)
        self.pause = game.state_machine.current
        self.pause.sel = 0
        self.pause.draw(game.screen)                     # registers the rows
        game.set_key_layout(config.DEFAULT_KEY_LAYOUT)

    def _row(self, name):
        from game.states.paused_state import _ROWS
        return self.pause._mouse.hits.rect_of(_ROWS.index(name)).center

    def test_rows_are_registered_without_overlap(self):
        from game.states.paused_state import _ROWS
        rects = [self.pause._mouse.hits.rect_of(i) for i in range(len(_ROWS))]
        self.assertTrue(all(r is not None for r in rects))
        for a, b in zip(rects, rects[1:]):
            self.assertLessEqual(a.bottom, b.top)

    def test_hover_selects_without_picking(self):
        _mouse(self.game, pygame.MOUSEMOTION, self._row("quit"))
        self.assertEqual(self.pause.sel, 2)
        self.assertIsInstance(self.game.state_machine.current, PausedState)

    def test_click_resume_resumes(self):
        _click(self.game, self._row("resume"))
        self.assertIs(self.game.state_machine.current, self.ps)

    def test_click_key_layout_cycles_and_persists(self):
        _click(self.game, self._row("key_layout"))
        self.assertEqual(self.game.key_layout, "arrows_move")
        self.assertEqual(save_mod.load(self.game.save_path).settings["key_layout"],
                         "arrows_move")
        self.assertIsInstance(self.game.state_machine.current, PausedState)

    def test_click_quit_returns_to_menu(self):
        _click(self.game, self._row("quit"))
        self.assertIsInstance(self.game.state_machine.current, MenuState)

    def test_click_off_every_row_is_inert(self):
        _click(self.game, (20, 20))
        self.assertIsInstance(self.game.state_machine.current, PausedState)
        self.assertEqual(self.pause.sel, 0)

    def test_release_on_another_row_is_inert(self):
        _mouse(self.game, pygame.MOUSEBUTTONDOWN, self._row("quit"))
        _mouse(self.game, pygame.MOUSEBUTTONUP, self._row("resume"))
        self.assertIsInstance(self.game.state_machine.current, PausedState)


class MouseArmingTests(unittest.TestCase):
    """The latch behind every overlay: after pause / level-up / dev menu
    covers the run, a button still reported down is ignored until it has been
    up for one frame -- so the click that closed the overlay can never fire
    an attack."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps, _ = _paused()
        _key(cls.game, pygame.K_ESCAPE)                  # back in the run

    def setUp(self):
        ps = self.ps
        self.game.state_machine.change(ps)
        ps._mouse_armed = True
        ps.consume_tap()
        ps.auto_attack = False
        ps.enemies.clear(); ps.boss = None
        ps.spawn.master.frozen = True
        for w in ps.player.weapons:
            w._cd = 0.0

    def _frame(self, left, n=1):
        from unittest import mock
        ps = self.ps
        before = len(ps.projectiles)
        with mock.patch.object(pygame.key, "get_pressed", return_value=_NoKeys()), \
             mock.patch.object(pygame.mouse, "get_pressed", return_value=(left, False, False)), \
             mock.patch.object(pygame.mouse, "get_pos",
                               return_value=ps.camera.world_to_screen(ps.player.pos + pygame.Vector2(100, 0))):
            for _ in range(n):
                ps.update(1 / 60)
        return len(ps.projectiles) - before

    def test_pause_disarms_and_the_first_up_frame_rearms(self):
        ps = self.ps
        _key(self.game, pygame.K_ESCAPE)                 # pause: disarmed
        self.assertFalse(ps._mouse_armed)
        pause = self.game.state_machine.current
        pause.draw(self.game.screen)                     # registers the rows
        _click(self.game, pause._mouse.hits.rect_of(0).center)   # Resume
        self.assertIs(self.game.state_machine.current, ps)
        # Button still reported down on the resume frame: nothing fires.
        self.assertEqual(self._frame(left=True, n=3), 0)
        self.assertFalse(ps._mouse_armed)
        self.assertFalse(ps._tap_pending)
        # One frame with the button up re-arms; a held click then attacks.
        self.assertEqual(self._frame(left=False), 0)
        self.assertTrue(ps._mouse_armed)
        self.assertGreater(self._frame(left=True), 0)

    def test_a_tap_queued_before_the_overlay_is_dropped(self):
        ps = self.ps
        ps._tap_pending = True
        _key(self.game, pygame.K_ESCAPE)
        self.assertFalse(ps._tap_pending)
        _key(self.game, pygame.K_ESCAPE)                 # resume
        self.assertEqual(self._frame(left=False), 0)

    def test_level_up_and_dev_menu_disarm_too(self):
        from progression.experience import xp_for_level
        ps = self.ps
        ps.levels.add_xp(xp_for_level(ps.levels.level) - ps.levels.xp_into_level)
        ps._open_level_up()
        self.assertFalse(ps._mouse_armed)
        self.game.state_machine.pop()                    # drop the level-up overlay
        ps._awaiting_level_up = False
        ps.levels.consume_pending()
        ps._mouse_armed = True
        ps.dev_mode = True
        try:
            _key(self.game, pygame.K_BACKQUOTE)
            self.assertFalse(ps._mouse_armed)
            self.game.state_machine.pop()
        finally:
            ps.dev_mode = False

    def test_armed_by_default_and_a_held_click_fires_at_once(self):
        self.assertTrue(self.ps._mouse_armed)
        self.assertGreater(self._frame(left=True), 0)


class _NoKeys:
    """A key-state stand-in that reports every key up."""
    def __getitem__(self, key):
        return False


class PauseButtonArtTests(unittest.TestCase):
    """UI art, group F: the pause rows are wide buttons -- the selected row
    gold, a held row sunk, Quit to menu red, the layout value on the right."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps, _ = _paused()

    def setUp(self):
        game = self.game
        if not isinstance(game.state_machine.current, PausedState):
            game.state_machine.change(self.ps)
            _key(game, pygame.K_ESCAPE)
        self.pause = game.state_machine.current
        self.pause.sel = 0
        self.pause.draw(game.screen)

    def _calls(self):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_button", wraps=widgets.draw_button) as m:
            self.pause.draw(self.game.screen)
        calls = [c for c in m.call_args_list if c.kwargs.get("shape") == "wide"]
        self.assertEqual(len(calls), 3)
        return calls

    def test_native_buttons_matching_the_hit_rects(self):
        for i, c in enumerate(self._calls()):
            self.assertEqual(c.args[2].height, 64)
            self.assertEqual(self.pause._mouse.hits.rect_of(i), c.args[2])

    def test_selected_gold_quit_red_held_sinks(self):
        calls = self._calls()
        self.assertEqual([c.kwargs["state"] for c in calls], ["hover", "normal", "normal"])
        self.assertEqual([c.kwargs["variant"] for c in calls], ["primary", "primary", "danger"])
        _mouse(self.game, pygame.MOUSEBUTTONDOWN, self.pause._mouse.hits.rect_of(1).center)
        self.assertEqual(self._calls()[1].kwargs["state"], "pressed")
        _mouse(self.game, pygame.MOUSEBUTTONUP, (5, 5))
        self.assertNotIn("pressed", [c.kwargs["state"] for c in self._calls()])

    def test_layout_value_is_drawn_on_the_row(self):
        # The value text is blitted inside the Key layout button's right half.
        class _Spy(pygame.Surface):
            def __init__(self, size):
                super().__init__(size); self.blits = []
            def blit(self, src, dest, *a, **k):
                self.blits.append((src.get_size(), pygame.Rect(dest, src.get_size())
                                   if not isinstance(dest, pygame.Rect) else dest))
                return super().blit(src, dest, *a, **k)
        screen = _Spy(self.game.screen.get_size())
        self.pause.draw(screen)
        want = self.pause._font.render(
            config.KEY_LAYOUT_LABELS[self.game.key_layout], True, config.COLOR_TEXT).get_size()
        row = self.pause._mouse.hits.rect_of(1)
        hits = [r for size, r in screen.blits if size == want and row.contains(r)]
        self.assertTrue(hits, "layout value not drawn on its row")
        self.assertGreater(hits[0].centerx, row.centerx)


class PauseTextTests(unittest.TestCase):
    """Fonts, group E: the row labels black and lifted onto the art's
    visual centre, the Key layout value dark grey, no light-palette text
    left on a row."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps, _ = _paused()

    def setUp(self):
        game = self.game
        if not isinstance(game.state_machine.current, PausedState):
            game.state_machine.change(self.ps)
            _key(game, pygame.K_ESCAPE)
        self.pause = game.state_machine.current
        self.pause.sel = 0
        self.pause.draw(game.screen)

    @staticmethod
    def _has_colour(screen, rect, colour):
        want = tuple(colour) + (255,)
        return any(tuple(screen.get_at((x, y))) == want
                   for x in range(rect.left, rect.right) for y in range(rect.top, rect.bottom))

    def _row(self, i):
        return self.pause._mouse.hits.rect_of(i)

    def test_colours_on_the_rows(self):
        screen = self.game.screen
        r0, r1 = self._row(0), self._row(1)
        left = pygame.Rect(r1.left + 40, r1.top + 8, r1.width // 2 - 40, r1.height - 16)
        right = pygame.Rect(r1.centerx, r1.top + 8, r1.width // 2 - 40, r1.height - 16)
        self.assertTrue(self._has_colour(screen, left, config.COLOR_ON_BUTTON))       # label
        self.assertTrue(self._has_colour(screen, right, config.COLOR_ON_BUTTON_DIM))  # value
        self.assertTrue(self._has_colour(screen, r0, config.COLOR_ON_BUTTON))         # gold row too
        for r in (r0, r1, self._row(2)):
            self.assertFalse(self._has_colour(screen, r, config.COLOR_TEXT))

    def test_labels_are_lifted_by_label_dy(self):
        from ui import widgets

        class _Spy(pygame.Surface):
            def __init__(self, size):
                super().__init__(size); self.blits = []
            def blit(self, src, dest, *a, **k):
                r = dest if isinstance(dest, pygame.Rect) else pygame.Rect(dest, src.get_size())
                self.blits.append((src.get_size(), pygame.Rect(r)))
                return super().blit(src, dest, *a, **k)

        screen = _Spy(self.game.screen.get_size())
        self.pause.draw(screen)
        for i, rid in enumerate(("resume", "key_layout", "quit")):
            from game.states.paused_state import _LABELS
            want = self.pause._font.render(_LABELS[rid], True, config.COLOR_ON_BUTTON).get_size()
            row = self._row(i)
            hits = [r for size, r in screen.blits if size == want and row.contains(r)]
            self.assertTrue(hits, f"label for {rid} not found on its row")
            self.assertEqual(hits[0].centery, row.centery + widgets.LABEL_DY)
        want = self.pause._font.render(
            config.KEY_LAYOUT_LABELS[self.game.key_layout], True, config.COLOR_ON_BUTTON_DIM).get_size()
        row = self._row(1)
        vals = [r for size, r in screen.blits if size == want and row.contains(r)
                and r.centerx > row.centerx]
        self.assertTrue(vals)
        self.assertEqual(vals[0].centery, row.centery + widgets.LABEL_DY)
