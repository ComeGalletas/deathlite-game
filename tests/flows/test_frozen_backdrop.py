"""The frozen backdrop under the level-up, pause and TAB screens (RND-012.3).

Those overlays freeze the run (`update_below` False), and the state machine
used to redraw the whole world under them every frame: 47 ms of the level-up
screen's render in Chrome (BLD-003.6). With `State.freeze_backdrop` the
states below are drawn once and that frame is blitted while the overlay is
on top; the overlay's own dim and panel still draw every frame.

Pinned here: the run is drawn once over many frames; a cached frame is
byte-identical to a full redraw (the run's draw has no side effect since
RND-011 moved the aura shed into the update; before it, the kept frame was
what stopped the shed under a pause: `AuraShedTests`, RND-012.D7); every
change that could alter the frame
below (a push or pop, a display change, another target surface, the pause
menu's key-layout toggle, an explicit invalidation) redraws it; a
per-pixel-alpha target and the overlays that do not opt in (the dev menu,
the end banner) are drawn in full every frame; and the overlay itself stays
live. The renderer's wall clock is pinned so animated water and scenery do
not differ between frames for reasons of their own.
"""
import math
import os
import random
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ElementId
from game import config
from game.states.dev_menu_state import DevMenuState
from game.states.end_banner_state import BANNER, EndBannerState
from game.states.level_up_state import LevelUpState
from game.states.paused_state import PausedState
from game.states.playing.core import interactions
from game.states.playing.visual import key_marker
from game.states.run_status_state import RunStatusState
from progression.blessings.offer import roll_offering
from tests.flows import test_lod as L


def _frame(surface) -> bytes:
    return pygame.image.tobytes(surface, "RGB")


class FrozenBackdropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps = L._run()
        cls.game = cls.ps.game
        cls.sm = cls.game.state_machine
        cls.renderer = cls.ps.game_map.renderer
        cls._clock = cls.renderer.clock
        cls.renderer.clock = lambda: 3.0          # water and scenery hold still

    @classmethod
    def tearDownClass(cls):
        cls.renderer.clock = cls._clock

    def setUp(self):
        self.assertIs(self.sm.current, self.ps, "a test left an overlay open")
        self.screen = self.game.screen
        self.assertEqual(self.screen.get_masks()[3], 0, "the screen has no alpha")

    def tearDown(self):
        while self.sm.current is not self.ps:
            self.sm.pop()

    # --- helpers ----------------------------------------------------------
    def _push(self, kind):
        if kind == "level_up":
            choices = roll_offering(self.ps.run.player, self.ps.run.content, random.Random(3))
            self.sm.push(LevelUpState(self.game), player=self.ps.run.player,
                         choices=choices, on_done=lambda u: None)
        elif kind == "pause":
            self.sm.push(PausedState(self.game))
        elif kind == "status":
            self.sm.push(RunStatusState(self.game), playing=self.ps)
        return self.sm.current

    def _run_draws(self, frames, surface=None):
        """How many times the run is drawn over `frames` frames."""
        surface = surface or self.screen
        with mock.patch.object(self.ps, "draw", wraps=self.ps.draw) as spy:
            for _ in range(frames):
                self.sm.draw(surface)
        return spy.call_count

    # --- the cache --------------------------------------------------------
    def test_each_opted_overlay_draws_the_run_once(self):
        for kind in ("level_up", "pause", "status"):
            with self.subTest(overlay=kind):
                self._push(kind)
                self.assertEqual(self._run_draws(6), 1)
                self.sm.pop()

    def test_a_cached_frame_is_the_full_redraw(self):
        for kind in ("level_up", "pause", "status"):
            with self.subTest(overlay=kind):
                self._push(kind)
                self.sm.draw(self.screen)                 # draws the run, keeps it
                first = _frame(self.screen)
                self.sm.draw(self.screen)                 # from the kept frame
                cached = _frame(self.screen)
                self.sm.invalidate_backdrop()
                self.sm.draw(self.screen)                 # in full again
                full = _frame(self.screen)
                self.assertEqual(cached, first)
                self.assertEqual(cached, full)
                self.sm.pop()

    def test_closing_the_overlay_drops_the_kept_frame(self):
        self._push("pause")
        self.sm.draw(self.screen)
        self.assertIsNotNone(self.sm._frozen)
        self.sm.pop()
        self.assertIsNone(self.sm._frozen)
        self.assertEqual(self._run_draws(3), 3, "the run itself draws every frame")

    # --- what redraws it --------------------------------------------------
    def test_a_stack_change_redraws_below(self):
        self._push("pause")
        self.assertEqual(self._run_draws(3), 1)
        self._push("status")                               # TAB from the pause menu
        self.assertEqual(self._run_draws(3), 1)
        self.sm.pop()                                      # back to the pause menu
        self.assertEqual(self._run_draws(3), 1)

    def test_a_display_change_redraws_below(self):
        self._push("pause")
        self.assertEqual(self._run_draws(2), 1)
        with mock.patch.object(self.ps, "on_display_changed"), \
                mock.patch.object(self.sm.current, "on_display_changed"):
            self.sm.on_display_changed()
        self.assertEqual(self._run_draws(2), 1)

    def test_another_target_surface_redraws_below(self):
        self._push("level_up")
        self.assertEqual(self._run_draws(2), 1)
        other = pygame.Surface(self.screen.get_size())
        self.assertEqual(self._run_draws(2, other), 1)
        self.assertEqual(self._run_draws(2), 1, "back on the screen: drawn again, once")

    def test_the_pause_menus_key_layout_toggle_redraws_below(self):
        """The run's opening hints spell out the keys."""
        self._push("pause")
        self.assertEqual(self._run_draws(2), 1)
        was = self.game.key_layout
        try:
            self.game.cycle_key_layout()
            self.assertEqual(self._run_draws(2), 1)
        finally:
            self.game.set_key_layout(was)

    def test_an_explicit_invalidation_redraws_below(self):
        self._push("status")
        self.assertEqual(self._run_draws(2), 1)
        self.sm.invalidate_backdrop()
        self.assertEqual(self._run_draws(2), 1)

    # --- where it does not apply -------------------------------------------
    def test_a_per_pixel_alpha_target_is_always_drawn_in_full(self):
        self._push("pause")
        target = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        self.assertEqual(self._run_draws(3, target), 3)
        self.assertIsNone(self.sm._frozen)

    def test_the_dev_menu_does_not_freeze_the_run(self):
        self.sm.push(DevMenuState(self.game), playing=self.ps)
        self.assertEqual(self._run_draws(3), 3)

    def test_the_end_banner_does_not_freeze_the_run(self):
        self.sm.push(EndBannerState(self.game), victory=False, on_done=None)
        banner = self.sm.current
        banner.phase, banner.update_below = BANNER, False   # its frozen phase
        self.assertEqual(self._run_draws(3), 3)

    # --- the overlay stays live -------------------------------------------
    def test_the_overlay_still_changes_frame_to_frame(self):
        pause = self._push("pause")
        with mock.patch.object(self.ps, "draw", wraps=self.ps.draw) as spy:
            self.sm.draw(self.screen)
            before = _frame(self.screen)
            pause.sel = (pause.sel + 2) % 5                # another row highlighted
            self.sm.draw(self.screen)
            after = _frame(self.screen)
        self.assertEqual(spy.call_count, 1, "the run was not redrawn")
        self.assertNotEqual(before, after, "the new selection reached the screen")

    # --- held input (RND-012.D6) --------------------------------------------
    def test_a_held_hint_key_is_not_kept_pressed_under_the_overlay(self):
        """The opening hints draw a held key pressed. Under an overlay the
        run is frozen: a key held on the frame the overlay opened must not
        stay pressed in the kept frame (critic pass, RND-012.4)."""
        self.assertTrue(self.ps.hints.visible, "the opening hints must be on screen here")
        with mock.patch.object(self.ps.hints, "held", return_value=True):
            self.sm.draw(self.screen)
            held = _frame(self.screen)
        self.sm.draw(self.screen)
        self.assertNotEqual(held, _frame(self.screen), "with the run on top a held key shows")
        self._push("level_up")
        with mock.patch.object(self.ps.hints, "held", return_value=True):
            self.sm.draw(self.screen)                      # the frame that is kept
        self.sm.draw(self.screen)
        kept = _frame(self.screen)
        self.sm.invalidate_backdrop()
        self.sm.draw(self.screen)
        self.assertEqual(kept, _frame(self.screen))

    def test_the_level_up_selection_reaches_the_screen(self):
        lu = self._push("level_up")
        self.sm.draw(self.screen)
        before = _frame(self.screen)
        lu.selected = (lu.selected + 1) % max(1, len(lu.choices))
        self.sm.draw(self.screen)
        self.assertNotEqual(before, _frame(self.screen))


class HeldInteractTests(unittest.TestCase):
    """The E keycap over a location draws pressed while E is held. Opening
    the location with E pushes an overlay while E is still down; the kept
    frame must not carry the pressed cap (critic pass, RND-012.4). Its own
    run: the hero is moved onto a location."""

    def test_the_e_cap_is_not_kept_pressed_after_opening_a_location(self):
        ps = L._run()
        game, sm, screen = ps.game, ps.game.state_machine, ps.game.screen
        ps.game_map.renderer.clock = lambda: 3.0
        ps.hints.dismiss()
        usable = [o for o in ps.interactables if interactions.usable(o)]
        self.assertTrue(usable, "seed 35 has a usable location")
        press = pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT,
                                   mod=0, unicode="e", scancode=0)
        for target in usable:
            for _ in range(30):
                ps.player.pos.update(target.pos)
                sm.update(1 / 60)
            with mock.patch.object(key_marker, "interact_held", lambda: True):
                sm.draw(screen)
                held = _frame(screen)
            with mock.patch.object(key_marker, "interact_held", lambda: False):
                sm.draw(screen)
                raised = _frame(screen)
            if held == raised:
                continue                                   # no cap drawn here
            sm.handle_event(press)
            if sm.current is not ps:
                break
        self.assertIsNot(sm.current, ps, "E opened a location")
        self.assertTrue(sm.current.freeze_backdrop)
        with mock.patch.object(key_marker, "interact_held", lambda: True):
            sm.draw(screen)                                # E still down: this is kept
        with mock.patch.object(key_marker, "interact_held", lambda: False):
            sm.draw(screen)
            kept = _frame(screen)
            sm.invalidate_backdrop()
            sm.draw(screen)
            full = _frame(screen)
        self.assertEqual(kept, full)


class AuraShedTests(unittest.TestCase):
    """Before RND-011 the run's draw shed aura particles: each draw of an
    aura'd body rolled `run.rng` and could add a particle, so the old
    per-frame redraw under a frozen overlay piled particles up and used up
    the run's random stream for as long as the game was paused. The kept
    frame drew the run once (RND-012.D7), which stopped that; RND-011 then
    moved the shed into the update, so no draw sheds at all. Pinned: under
    the pause nothing piles up, the stream is untouched and the frame holds
    still, and even a full redraw every frame adds nothing (critic pass 2,
    revised for RND-011)."""

    def test_nothing_piles_up_under_the_pause(self):
        ps = L._run()
        game, sm, screen = ps.game, ps.game.state_machine, ps.game.screen
        ps.game_map.renderer.clock = lambda: 3.0
        run, now = ps.run, ps.run.stats["time"]
        for i in range(8):
            ang = i * math.tau / 8
            e = ps.spawn.spawn_enemy("skull", at=ps.player.pos + pygame.Vector2(
                140 * math.cos(ang), 140 * math.sin(ang)))
            self.assertIsNotNone(e)
            e.elemental.set_aura(ElementId.FIRE, now, 1e6)
        with mock.patch.object(ps, "draw", wraps=ps.draw) as drawn:
            sm.push(PausedState(game))
            sm.draw(screen)                                # the run, drawn once
            kept, particles, rng = _frame(screen), len(run.particles), run.rng.getstate()
            for _ in range(60):
                sm.draw(screen)
        # The kept frame itself: since RND-011 a redraw would add nothing
        # either, so the particle checks below cannot tell the two apart.
        self.assertEqual(drawn.call_count, 1, "the run was redrawn under the pause")
        self.assertEqual(len(run.particles), particles, "no aura particles piled up")
        self.assertEqual(run.rng.getstate(), rng, "the run's random stream is untouched")
        self.assertEqual(_frame(screen), kept)
        # A full redraw every frame, as before RND-012, adds nothing either
        # since RND-011: the shed is the update's, never the draw's.
        for _ in range(60):
            sm.invalidate_backdrop()
            sm.draw(screen)
        self.assertEqual(len(run.particles), particles, "a redraw shed particles")
        self.assertEqual(run.rng.getstate(), rng, "a redraw rolled run.rng")
        # The control: these auras do shed, in the update, once the pause
        # is gone.
        sm.pop()
        for _ in range(30):
            ps.update(1 / 62)
        self.assertGreater(len(run.particles.layer(True)), 0, "the auras never shed")


if __name__ == "__main__":
    unittest.main()
