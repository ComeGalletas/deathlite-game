"""Full-screen overlays at constant alpha (RND-010.2).

The dims, the hurt flash, the low-HP vignette and the buff tint used to blit a
full-frame per-pixel-alpha (`SRCALPHA`) surface, the browser's slow blend
(8.3 ms a frame in Chrome, BLD-003.6). They now blend an opaque RGB surface at
constant alpha (`ui/veil.py`). The owner accepted a difference of at most 1
per colour channel against the old result (RND-010.D2); black is exact.

Each overlay is drawn over the same noisy frame both ways, the old per-pixel
path written out here as the reference, and compared pixel by pixel.
"""
import os
import random
import types
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.states.end_banner_state import EndBannerState
from game.states.paused_state import PausedState
from game.states.playing.visual import rendering
from game.states.run_status_state import RunStatusState
from ui import veil
from ui.level_up import LevelUpPanel

SIZE = (320, 180)


def _noise(size=SIZE, seed=7) -> pygame.Surface:
    """An opaque frame of random colours, every third row, so blends are
    tested over the whole colour range rather than one background."""
    rng = random.Random(seed)
    s = pygame.Surface(size)
    s.fill((90, 140, 60))
    for y in range(0, size[1], 3):
        for x in range(size[0]):
            s.set_at((x, y), (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    return s


def _old_fill(surface, rgb, alpha):
    """The old path: a full-frame SRCALPHA surface filled and blitted."""
    f = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    f.fill((*rgb, alpha))
    surface.blit(f, (0, 0))


def _max_diff(a: pygame.Surface, b: pygame.Surface) -> tuple[int, int]:
    """(largest channel difference, pixels that differ at all)."""
    worst = changed = 0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            p, q = a.get_at((x, y)), b.get_at((x, y))
            d = max(abs(p[i] - q[i]) for i in range(3))
            worst = max(worst, d)
            changed += d > 0
    return worst, changed


class VeilTests(unittest.TestCase):
    def test_the_fill_surface_has_no_per_pixel_alpha_and_is_cached(self):
        a = veil.fill_surface((64, 32), (1, 2, 3))
        self.assertEqual(a.get_masks()[3], 0, "no alpha channel")
        self.assertIs(veil.fill_surface((64, 32), (1, 2, 3)), a)
        self.assertIsNot(veil.fill_surface((64, 32), (1, 2, 4)), a)

    def test_alpha_zero_and_empty_rects_draw_nothing(self):
        s = _noise(); before = s.copy()
        veil.veil(s, (255, 0, 0), 0)
        veil.veil(s, (255, 0, 0), 200, (10, 10, 0, 40))
        self.assertEqual(_max_diff(s, before), (0, 0))

    def test_a_rect_veil_touches_only_its_rect(self):
        s = _noise(); before = s.copy()
        veil.veil(s, (255, 0, 0), 128, (40, 20, 50, 30))
        self.assertEqual(s.get_at((10, 10)), before.get_at((10, 10)))
        self.assertNotEqual(s.get_at((60, 30)), before.get_at((60, 30)))

    def test_the_cache_stays_bounded(self):
        for i in range(veil._CACHE_CAP * 3):
            veil.fill_surface((8 + i, 8), (0, 0, 0))
        self.assertLessEqual(len(veil._CACHE), veil._CACHE_CAP)


class FrameStripTests(unittest.TestCase):
    """`frame_strips` covers exactly the pixels `pygame.draw.rect(width=t)`
    covers, so the vignette's shape does not change."""

    def test_the_strips_are_the_rect_border(self):
        for size, t in (((320, 180), 24), ((1280, 720), 24), ((100, 60), 7), ((50, 40), 30)):
            with self.subTest(size=size, t=t):
                ref = pygame.Surface(size); ref.fill((0, 0, 0))
                pygame.draw.rect(ref, (255, 255, 255), (0, 0, *size), t)
                got = pygame.Surface(size); got.fill((0, 0, 0))
                for r in veil.frame_strips(size, t):
                    got.fill((255, 255, 255), r)
                self.assertEqual(_max_diff(ref, got), (0, 0))

    def test_the_strips_do_not_overlap(self):
        rects = veil.frame_strips((320, 180), 24)
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                self.assertFalse(a.colliderect(b), (a, b))


class OverlayParityTests(unittest.TestCase):
    """Every converted overlay against the old per-pixel-alpha result."""

    def _check(self, draw_new, draw_old, exact=False, via_veil=True):
        a, b = _noise(), _noise()
        with mock.patch.object(veil, "veil", wraps=veil.veil) as spy:
            draw_new(a)
        if via_veil:
            self.assertTrue(spy.called, "not drawn through the constant-alpha veil")
        draw_old(b)
        worst, changed = _max_diff(a, b)
        self.assertLessEqual(worst, 0 if exact else 1, f"{changed} pixels differ")
        self.assertNotEqual(_max_diff(a, _noise()), (0, 0), "the overlay drew nothing")

    def test_level_up_dim(self):
        self._check(LevelUpPanel.draw_dim, lambda s: _old_fill(s, (8, 6, 16), 200))

    def test_pause_dim_is_exact(self):
        self._check(lambda s: PausedState.draw_backdrop(None, s),
                    lambda s: _old_fill(s, (0, 0, 0), 150), exact=True)

    def test_run_status_dim_is_exact(self):
        self._check(lambda s: RunStatusState.draw_backdrop(None, s),
                    lambda s: _old_fill(s, (0, 0, 0), 150), exact=True)

    def test_end_banner_dim_at_every_step_of_its_fade(self):
        for alpha in (1, 40, 128, 200, 255):
            with self.subTest(alpha=alpha):
                fake = types.SimpleNamespace(_dim_alpha=lambda a=alpha: a)
                self._check(lambda s: EndBannerState.draw_backdrop(fake, s),
                            lambda s: _old_fill(s, (0, 0, 0), alpha), exact=True)

    def test_hurt_flash(self):
        for alpha in (6, 60, 120):
            with self.subTest(alpha=alpha):
                self._check(lambda s: rendering.hurt_flash(s, alpha),
                            lambda s: _old_fill(s, (200, 30, 30), alpha))

    def test_low_hp_vignette(self):
        def old(s, alpha):
            vig = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(vig, (180, 20, 20, alpha), (0, 0, *s.get_size()), 24)
            s.blit(vig, (0, 0))
        for alpha in (20, 60, 100):
            with self.subTest(alpha=alpha):
                self._check(lambda s: rendering.low_hp_vignette(s, alpha),
                            lambda s: old(s, alpha))

    def test_buff_tint(self):
        palette = [(255, 200, 40), (200, 60, 220), (40, 120, 255)]
        feedback = {"tint_seconds": 0.9, "tint_peak_alpha": 55}

        def fake(left):
            return types.SimpleNamespace(ps=types.SimpleNamespace(
                buffs=types.SimpleNamespace(tint=(left, palette), feedback=feedback)))

        def old(s, left):
            alpha = int(55 * max(0.0, min(1.0, left / 0.9)))
            steps = 64
            column = pygame.Surface((1, steps), pygame.SRCALPHA)
            for i in range(steps):
                t = i / (steps - 1) * (len(palette) - 1)
                k, f = int(t), t - int(t)
                a_col, b_col = palette[min(k, 2)], palette[min(k + 1, 2)]
                column.set_at((0, i), tuple(int(a_col[c] + (b_col[c] - a_col[c]) * f)
                                            for c in range(3)) + (255,))
            grad = pygame.transform.smoothscale(column, s.get_size())
            grad.set_alpha(alpha)
            s.blit(grad, (0, 0))

        for left in (0.9, 0.45, 0.1):
            with self.subTest(left=left):
                self_ = fake(left)
                self._check(lambda s: rendering.WorldRenderer.buff_tint(self_, s),
                            lambda s: old(s, left), via_veil=False)
                # No alpha channel. `get_flags()` reports SRCALPHA once
                # `set_alpha` has run, even on an RGB surface, so read the mask.
                self.assertEqual(self_._tint_cache[1].get_masks()[3], 0)


if __name__ == "__main__":
    unittest.main()
