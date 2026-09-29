"""RND-008.3: once a run has drawn a frame, drawing another builds no font
(`frame_time_journal.md`).

Building a `Font` every frame, and rendering with its empty glyph cache,
cost the run's opening hints about 17 ms of draw at 2560 x 1080. The check
here is on the whole `PlayingState.draw`, not on the three files that were
fixed, so the next per-frame font anywhere in the draw path fails it too.

What is pinned: no `fonts._load` in a warm frame with the Move hint up,
with a key held, while it fades, with the Attack hint, with the interact
cap shown, and all at once; a display re-opened at another render scale
gives the run a new cache, whose first frame builds the fonts at the new
size and whose second builds none; and the fading block, now drawn into a
buffer the size of the block, is pixel-identical to the whole-screen fade
it replaced. Seed 1234 is pinned, as in the hint and marker tests.
"""
import contextlib
import os
import tempfile
import unittest
from unittest import mock

import pygame

from entities.chest import Chest
from game import config, fonts
from game.content import get_content
from game.game import Game
from game.states.playing.core import interactions
from game.states.playing.core.hints import RunHints
from game.states.playing.core.state import PlayingState
from game.states.playing.visual import hints as hints_draw
from progression import chests as chest_rules
from ui import keycap
from ui.text_cache import TextCache

SEED = 1234


def _run():
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    p = PlayingState(g)
    p.enter(seed=SEED)
    p.chests, p.interactables = [], []
    return g, p


class _Pressed:
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def _loads_in_a_warm_frame(p, surface, pressed=None):
    """The fonts built by the second of two frames."""
    keys = mock.patch.object(pygame.key, "get_pressed", return_value=pressed or _Pressed())
    with keys:
        p.draw(surface)
        with mock.patch.object(fonts, "_load", wraps=fonts._load) as m:
            p.draw(surface)
    return [c.args for c in m.call_args_list]


class WarmFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g, cls.p = _run()
        cls.surface = pygame.Surface(cls.g.screen.get_size())

    def setUp(self):
        p = self.p
        p.chests = []
        p.hints = RunHints(p)                   # the Move stage, from the top
        self.assertTrue(p.hints.visible)

    def _chest_in_reach(self):
        p = self.p
        p.chests.append(Chest(p.player.pos.x + 10, p.player.pos.y, "common",
                              radius=chest_rules.radius(get_content().chests)))
        self.assertIsNotNone(interactions.nearest(p))

    def test_the_move_hint(self):
        self.assertEqual(_loads_in_a_warm_frame(self.p, self.surface), [])

    def test_a_held_key(self):
        self.assertEqual(
            _loads_in_a_warm_frame(self.p, self.surface, _Pressed(pygame.K_d)), [])

    def test_a_fading_stage(self):
        p = self.p
        p.hints._advance("attack")
        p.hints.update(config.HINT_FADE / 4)
        self.assertEqual(_loads_in_a_warm_frame(p, self.surface), [])
        self.assertIsNotNone(p.hints.fading)

    def test_the_attack_hint(self):
        p = self.p
        p.hints._advance("attack")
        p.hints.update(config.HINT_FADE * 2)
        self.assertEqual(p.hints.stage, "attack")
        self.assertIsNone(p.hints.fading)
        self.assertEqual(_loads_in_a_warm_frame(p, self.surface), [])

    def test_the_interact_cap(self):
        self.p.hints.dismiss()
        self._chest_in_reach()
        self.assertEqual(_loads_in_a_warm_frame(self.p, self.surface), [])

    def test_everything_at_once(self):
        p = self.p
        p.hints._advance("attack")
        p.hints.update(config.HINT_FADE / 4)
        self._chest_in_reach()
        self.assertEqual(
            _loads_in_a_warm_frame(p, self.surface, _Pressed(config.KEY_INTERACT)), [])

    def test_the_cache_is_what_saves_the_frame(self):
        # The control: with the run's cache replaced before each frame, the
        # same frame builds fonts again, so the checks above are not
        # passing on a draw path that simply never asks for one.
        p = self.p
        p.draw(self.surface)
        p.text_cache = TextCache()
        with mock.patch.object(fonts, "_load", wraps=fonts._load) as m:
            p.draw(self.surface)
        self.assertGreater(m.call_count, 0)


class PausedFrameTests(unittest.TestCase):
    """The pause menu draws every frame over the frozen run, and its
    Controls block is a column of keycaps."""

    def test_a_warm_paused_frame_builds_no_font(self):
        from game.states.menu_state import MenuState
        from game.states.paused_state import PausedState
        from tests.boot import start_run

        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        start_run(g, SEED)
        g.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIsInstance(g.state_machine.current, PausedState)
        surface = pygame.Surface(g.screen.get_size())
        g.state_machine.draw(surface)
        with mock.patch.object(fonts, "_load", wraps=fonts._load) as m:
            g.state_machine.draw(surface)
        self.assertEqual([c.args for c in m.call_args_list], [])


class DisplayReopenTests(unittest.TestCase):
    """Its own run: the re-open leaves the camera at the new zoom."""

    def test_a_new_scale_gets_a_new_cache_at_its_size(self):
        g, p = _run()
        surface = pygame.Surface(g.screen.get_size())
        p.draw(surface)
        old = p.text_cache
        with mock.patch.object(config, "RENDER_SCALE", 1.2):
            p.on_display_changed()
            self.assertIsNot(p.text_cache, old)
            with mock.patch.object(fonts, "_load", wraps=fonts._load) as m:
                p.draw(surface)
            first = [c.args for c in m.call_args_list]
            with mock.patch.object(fonts, "_load", wraps=fonts._load) as m:
                p.draw(surface)
            second = [c.args for c in m.call_args_list]
        # The hint's word at 18 and the caps' letters at 18 bold, both x1.2,
        # and nothing at the old scale's 18. (The floating damage numbers
        # also build their fonts once for the new camera zoom: their own
        # per-zoom cache, `ui/damage_numbers.py`.)
        self.assertLessEqual({("sans", 22, False), ("sans", 22, True)}, set(first))
        self.assertFalse([a for a in first if a[1] == fonts.native_px(18)], first)
        self.assertEqual(second, [])


class FadePixelTests(unittest.TestCase):
    """The block-sized fade against the whole-screen fade it replaced,
    drawn here the old way as the oracle.

    Both stages, at two render scales, with the art as shipped, without the
    cursor glyph (the mouse cap then writes `CLICK`, wider than its square
    cap: the case a frame-sized buffer clipped, found by the RND-008.3
    critic), and with no keycap art at all (the empty-`assets/` build)."""

    @classmethod
    def setUpClass(cls):
        cls.g, cls.p = _run()

    def _base(self):
        s = pygame.Surface(self.g.screen.get_size(), pygame.SRCALPHA)
        s.fill((40, 90, 60, 255))
        return s

    def _old_fade(self, surface, clusters, alpha):
        p = self.p
        cx, top = hints_draw.hero_top(p)
        items = hints_draw.layout(p, clusters, top, cx, TextCache())
        target = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for kind, a, b in items:
            if kind == "cap":
                keycap.draw_keycap(target, p.game.assets, b, a, colour="blue", state="raised")
            else:
                target.blit(a, b)
        target.set_alpha(alpha)
        surface.blit(target, (0, 0))

    def _stage(self, stage):
        p = self.p
        p.hints = RunHints(p)
        if stage == "attack":
            p.hints._advance("attack")
            p.hints.update(config.HINT_FADE * 2)
        clusters = p.hints.clusters()
        p.hints._advance(None)
        return clusters

    def _check(self, clusters):
        p = self.p
        for frac in (0.95, 0.3, 0.05):
            with self.subTest(frac=frac):
                left = config.HINT_FADE * frac
                p.hints.fading = (clusters, left)
                alpha = max(0, min(255, int(255 * left / max(1e-6, config.HINT_FADE))))
                got, want = self._base(), self._base()
                rect = hints_draw.draw(got, p)
                self._old_fade(want, clusters, alpha)
                self.assertEqual(pygame.image.tobytes(got, "RGBA"),
                                 pygame.image.tobytes(want, "RGBA"))
                # Everything painted lies inside the rect `draw` returns.
                clear = pygame.Surface(got.get_size(), pygame.SRCALPHA)
                self.assertEqual(hints_draw.draw(clear, p), rect)
                painted = clear.get_bounding_rect(min_alpha=1)
                self.assertTrue(painted.width and rect.contains(painted), (rect, painted))

    def test_each_stage_and_art_case_at_two_scales(self):
        no_glyph = mock.patch.object(keycap, "mouse_glyph", return_value=None)
        no_art = mock.patch.object(type(self.g.assets), "image", return_value=None)
        cases = {"as shipped": (), "no cursor glyph": (no_glyph,),
                 "no keycap art": (no_glyph, no_art)}
        for scale_ in (1.0, 1.5):
            for stage in ("move", "attack"):
                for name, patches in cases.items():
                    with self.subTest(scale=scale_, stage=stage, case=name), \
                            mock.patch.object(config, "RENDER_SCALE", scale_), \
                            contextlib.ExitStack() as stack:
                        for patch in patches:
                            stack.enter_context(patch)
                        self.p.text_cache = TextCache()
                        self._check(self._stage(stage))

    def test_the_mouse_cap_without_its_glyph_does_paint_past_its_frame(self):
        # The case above is only a test of the clip if CLICK really is
        # wider than the square cap.
        with mock.patch.object(keycap, "mouse_glyph", return_value=None):
            frame = keycap.cap_rect((400, 300))
            painted = keycap.footprint(self.g.assets, (400, 300), keycap.MOUSE)
        self.assertLess(painted.left, frame.left)
        self.assertGreater(painted.right, frame.right)


if __name__ == "__main__":
    unittest.main()
