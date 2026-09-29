"""ui/text_cache.py and the keycap's use of it (RND-008.3,
`frame_time_journal.md`): fonts and rendered text built once per owner and
render scale, drawing exactly what the uncached path draws.

What is pinned: a font is built once per role, size, weight and render
scale; a rendered or shadowed string comes back as the same surface, with
the pixels a fresh render gives; the text store is bounded; a cached cap is
pixel-identical to an uncached one in every label kind, colour and state,
and builds nothing on a second draw; an arrow or the mouse glyph builds no
font at all, cached or not.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, fonts
from game.assets import Assets, reset_assets
from ui import keycap, text
from ui.text_cache import TextCache


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


def _pixels(surface):
    return pygame.image.tobytes(surface, "RGBA")


def _loads():
    return mock.patch.object(fonts, "_load", wraps=fonts._load)


class TextCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def test_a_font_is_built_once_per_role_size_and_weight(self):
        cache = TextCache()
        with _loads() as m:
            a = cache.font("body", 18, bold=True)
            b = cache.font("body", 18, bold=True)
            cache.font("body", 18)
            cache.font("body", 20, bold=True)
            cache.font("heading", 18, bold=True)
        self.assertIs(a, b)
        self.assertEqual(m.call_count, 4)

    def test_another_render_scale_builds_the_font_at_its_size(self):
        cache = TextCache()
        with _loads() as m:
            cache.font("body", 18, bold=True)
            with mock.patch.object(config, "RENDER_SCALE", 1.2):
                cache.font("body", 18, bold=True)
                cache.font("body", 18, bold=True)
        self.assertEqual([c.args for c in m.call_args_list],
                         [("sans", fonts.native_px(18), True), ("sans", round(18 * 1.2), True)])

    def test_rendered_text_is_kept_and_matches_a_fresh_render(self):
        cache = TextCache()
        first = cache.render("body", 18, "Move", (250, 240, 200), bold=True)
        with _loads() as m:
            again = cache.render("body", 18, "Move", (250, 240, 200), bold=True)
        self.assertIs(first, again)
        self.assertEqual(m.call_count, 0)
        fresh = fonts.body(18, bold=True).render("Move", True, (250, 240, 200))
        self.assertEqual(first.get_size(), fresh.get_size())
        self.assertEqual(_pixels(first), _pixels(fresh))

    def test_a_different_colour_or_text_is_a_different_surface(self):
        cache = TextCache()
        a = cache.render("body", 18, "E", (0, 0, 0))
        self.assertIsNot(a, cache.render("body", 18, "E", (255, 255, 255)))
        self.assertIsNot(a, cache.render("body", 18, "Q", (0, 0, 0)))

    def test_shadowed_text_matches_the_uncached_helper(self):
        cache = TextCache()
        got = cache.shadowed("body", 18, "Attack", config.COLOR_TEXT)
        self.assertIs(got, cache.shadowed("body", 18, "Attack", config.COLOR_TEXT))
        fresh = text.shadowed(fonts.body(18), "Attack", config.COLOR_TEXT)
        self.assertEqual(got.get_size(), fresh.get_size())
        self.assertEqual(_pixels(got), _pixels(fresh))

    def test_the_shadow_follows_the_render_scale(self):
        cache = TextCache()
        plain = cache.shadowed("body", 18, "Move", config.COLOR_TEXT)
        with mock.patch.object(config, "RENDER_SCALE", 1.6):
            scaled = cache.shadowed("body", 18, "Move", config.COLOR_TEXT)
            fresh = text.shadowed(fonts.body(18), "Move", config.COLOR_TEXT)
        self.assertIsNot(plain, scaled)
        self.assertEqual(_pixels(scaled), _pixels(fresh))

    def test_the_text_store_is_bounded(self):
        cache = TextCache()
        with mock.patch.object(TextCache, "MAX_TEXTS", 3):
            for i in range(10):
                got = cache.render("body", 18, str(i), (0, 0, 0))
                self.assertLessEqual(len(cache._texts), 3)
            fresh = fonts.body(18).render("9", True, (0, 0, 0))
        self.assertEqual(_pixels(got), _pixels(fresh))


class CachedKeycapTests(unittest.TestCase):
    LABELS = ("E", "W", "TAB", "SPACE", "↑", "→", keycap.MOUSE)

    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def setUp(self):
        reset_assets()
        self.assets = Assets()

    def _cap(self, assets, label, *, cache=None, **kw):
        s = pygame.Surface((400, 120), pygame.SRCALPHA)
        s.fill((40, 90, 60, 255))
        r = keycap.draw_keycap(s, assets, (200, 60), label, cache=cache, **kw)
        return s, r

    def test_a_cached_cap_is_pixel_identical_to_an_uncached_one(self):
        cache = TextCache()
        for assets in (self.assets, None):
            for label in self.LABELS:
                for colour in keycap.COLOURS:
                    for state in keycap.STATES:
                        for size in (keycap.CAP_PX, 42):
                            with self.subTest(label=label, colour=colour, state=state,
                                              size=size, art=assets is not None):
                                kw = dict(colour=colour, state=state, size=size)
                                ref, r1 = self._cap(assets, label, **kw)
                                cold, r2 = self._cap(assets, label, cache=cache, **kw)
                                warm, r3 = self._cap(assets, label, cache=cache, **kw)
                                self.assertEqual(r1, r2)
                                self.assertEqual(r1, r3)
                                self.assertEqual(_pixels(ref), _pixels(cold))
                                self.assertEqual(_pixels(ref), _pixels(warm))

    def test_a_warm_cache_builds_nothing(self):
        cache = TextCache()
        for label in self.LABELS:
            self._cap(self.assets, label, cache=cache)
        with _loads() as m:
            for label in self.LABELS:
                self._cap(self.assets, label, cache=cache)
        self.assertEqual(m.call_count, 0)

    def test_arrows_and_the_mouse_build_no_font_even_uncached(self):
        with _loads() as m:
            for label in ("↑", "↓", "←", "→", keycap.MOUSE):
                self._cap(self.assets, label)
        self.assertEqual(m.call_count, 0)

    def test_a_given_font_still_wins(self):
        font = fonts.heading(20)
        cache = TextCache()
        with_font, _ = self._cap(self.assets, "E", cache=cache, font=font)
        ref, _ = self._cap(self.assets, "E", font=font)
        self.assertEqual(_pixels(with_font), _pixels(ref))

    def test_an_unknown_role_is_refused(self):
        with self.assertRaises(ValueError):
            TextCache().font("serif", 18)


class FootprintTests(unittest.TestCase):
    """`keycap.footprint` holds everything `draw_keycap` paints. The run's
    fading hint draws into a buffer that size, so anything outside it would
    be clipped: the mouse cap's `CLICK`, written when the cursor art is
    missing, is wider than its square cap (found by the RND-008.3 critic)."""

    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def test_everything_painted_lies_inside_the_footprint(self):
        reset_assets()
        assets = Assets()
        cache = TextCache()
        no_glyph = mock.patch.object(keycap, "mouse_glyph", return_value=None)
        for scale_ in (1.0, 1.5):
            for art in (assets, None):
                for glyph in (True, False):
                    for label in CachedKeycapTests.LABELS:
                        for colour in keycap.COLOURS:
                            for state in keycap.STATES:
                                for size in (keycap.CAP_PX, 42):
                                    with self.subTest(scale=scale_, art=art is not None,
                                                      glyph=glyph, label=label, colour=colour,
                                                      state=state, size=size), \
                                            mock.patch.object(config, "RENDER_SCALE", scale_):
                                        if not glyph:
                                            no_glyph.start()
                                        try:
                                            s = pygame.Surface((600, 200), pygame.SRCALPHA)
                                            kw = dict(state=state, colour=colour, size=size,
                                                      cache=cache)
                                            frame = keycap.draw_keycap(s, art, (300, 100), label, **kw)
                                            foot = keycap.footprint(art, (300, 100), label, **kw)
                                        finally:
                                            if not glyph:
                                                no_glyph.stop()
                                        painted = s.get_bounding_rect(min_alpha=1)
                                        self.assertTrue(foot.contains(frame), (foot, frame))
                                        self.assertTrue(foot.contains(painted), (foot, painted))

    def test_the_mouse_word_is_wider_than_its_square_cap(self):
        reset_assets()
        with mock.patch.object(keycap, "mouse_glyph", return_value=None):
            frame = keycap.cap_rect((300, 100))
            foot = keycap.footprint(Assets(), (300, 100), keycap.MOUSE)
        self.assertGreater(foot.width, frame.width)


if __name__ == "__main__":
    unittest.main()
