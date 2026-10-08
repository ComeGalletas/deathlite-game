"""RND-010.6: the aura frames blitted from RLE copies
(`game/states/playing/visual/elements/rle.py`, `crowd_draw_journal.md`).

What is pinned:
* **exactness:** a binary-alpha frame's copy keeps its per-pixel alpha and
  blits the same bytes; a frame with a translucent pixel is handed back as
  it is, and why (its RLE blit is a channel off);
* **the art:** every shipped aura frame is binary at every size, so the
  saving applies to all of them;
* **the cache:** one copy per frame, checked once; an LRU of `_CAP` that
  drops only the entry used longest ago; a stale entry under a recycled id
  is replaced, not served;
* **the wiring:** `layers._aura` blits the copy.
"""
import os
import unittest
from collections import OrderedDict
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.states.playing.visual.elements import layers, rle


def _frame(alphas, size=(40, 30)):
    """Column `i` of alpha `alphas[i % len(alphas)]`, a colour per column."""
    frame = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(size[0]):
        frame.fill((200, (100 + i * 3) % 256, 50, alphas[i % len(alphas)]), (i, 0, 1, size[1]))
    return frame


# A destination as the display and the game's scratch surfaces are: 32 bits,
# no per-pixel alpha.
_DEST = pygame.Surface((8, 8))


def _canvas():
    s = pygame.Surface((120, 120))
    for i in range(0, 120, 7):
        s.fill(((i * 37) % 256, (i * 11) % 256, (i * 5) % 256), (i, 0, 7, 120))
    return s


def _blitted(frame):
    s = _canvas()
    s.blit(frame, (17, 33))
    s.blit(frame, (60, 70))
    return pygame.image.tobytes(s, "RGB")


class RleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((64, 64))

    def setUp(self):
        self._saved = rle._COPIES
        rle._COPIES = OrderedDict()

    def tearDown(self):
        rle._COPIES = self._saved

    def test_a_binary_frame_is_blitted_from_an_rle_copy_with_the_same_pixels(self):
        frame = _frame((0, 255, 255, 0, 255))
        out = rle.ready(frame, _DEST)
        self.assertIsNot(out, frame)
        self.assertTrue(out.get_flags() & pygame.SRCALPHA)        # the alpha kept
        self.assertTrue(out.get_flags() & pygame.RLEACCELOK)
        self.assertEqual(_blitted(out), _blitted(frame))
        self.assertEqual(frame.get_flags() & pygame.RLEACCELOK, 0)  # the source untouched

    def test_a_translucent_frame_is_handed_back_as_it_is(self):
        frame = _frame((0, 40, 128, 200, 255))
        self.assertFalse(rle.binary_alpha(frame))
        self.assertIs(rle.ready(frame, _DEST), frame)
        # Why: SDL's RLE path blends a translucent pixel by its own formula.
        copy = frame.copy()
        copy.set_alpha(255, pygame.RLEACCEL)
        self.assertNotEqual(_blitted(copy), _blitted(frame))

    def test_a_destination_that_does_not_fit_gets_the_frame_itself(self):
        # Onto a surface with alpha the RLE path skips what pygame's blitter
        # writes; onto fewer bits SDL re-encodes the copy for good. Neither
        # ever sees a copy, and neither fills the cache.
        frame = _frame((0, 255))
        for dest in (pygame.Surface((8, 8), pygame.SRCALPHA), pygame.Surface((8, 8), 0, 24),
                     pygame.Surface((8, 8), 0, 16)):
            with self.subTest(bits=dest.get_bitsize(), alpha=bool(dest.get_flags() & pygame.SRCALPHA)):
                self.assertFalse(rle.fits(dest))
                self.assertIs(rle.ready(frame, dest), frame)
        self.assertEqual(len(rle._COPIES), 0)
        self.assertTrue(rle.fits(_DEST))
        self.assertTrue(rle.fits(pygame.display.get_surface()))

    def test_why_a_destination_with_alpha_does_not_fit(self):
        frame = _frame((0, 255))
        copy = frame.copy()
        copy.set_alpha(255, pygame.RLEACCEL)

        def onto(src):
            s = pygame.Surface((60, 60), pygame.SRCALPHA)
            s.fill((10, 20, 30, 0))
            s.blit(src, (5, 7))
            return pygame.image.tobytes(s, "RGBA")
        self.assertNotEqual(onto(copy), onto(frame))

    def test_surface_alpha_is_not_binary(self):
        frame = _frame((0, 255))
        frame.set_alpha(128)
        self.assertFalse(rle.binary_alpha(frame))
        self.assertIs(rle.ready(frame, _DEST), frame)

    def test_binary_alpha(self):
        self.assertTrue(rle.binary_alpha(_frame((0, 255))))
        self.assertTrue(rle.binary_alpha(_frame((0,))))             # all clear
        self.assertTrue(rle.binary_alpha(_frame((255,))))           # all opaque
        for alpha in (1, 127, 254):
            with self.subTest(alpha=alpha):
                self.assertFalse(rle.binary_alpha(_frame((0, 255, alpha))))

    def test_none_is_none(self):
        self.assertIsNone(rle.ready(None, _DEST))

    def test_one_copy_per_frame_checked_once(self):
        frame = _frame((0, 255))
        with mock.patch.object(rle, "binary_alpha", wraps=rle.binary_alpha) as check:
            first = rle.ready(frame, _DEST)
            for _ in range(5):
                self.assertIs(rle.ready(frame, _DEST), first)
        self.assertEqual(check.call_count, 1)
        translucent = _frame((0, 128))
        with mock.patch.object(rle, "binary_alpha", wraps=rle.binary_alpha) as check:
            for _ in range(3):
                self.assertIs(rle.ready(translucent, _DEST), translucent)
        self.assertEqual(check.call_count, 1)                      # the "no" is kept too

    def test_a_full_cache_drops_only_the_entry_used_longest_ago(self):
        frames = [_frame((0, 255), (8, 8)) for _ in range(4)]
        with mock.patch.object(rle, "_CAP", 3):
            copies = [rle.ready(f, _DEST) for f in frames[:3]]
            rle.ready(frames[0], _DEST)                                  # 0 now the newest
            rle.ready(frames[3], _DEST)                                  # drops 1, used longest ago
            self.assertEqual([e[0] for e in rle._COPIES.values()],
                             [frames[2], frames[0], frames[3]])
            self.assertIs(rle.ready(frames[0], _DEST), copies[0])        # kept
            self.assertIs(rle.ready(frames[2], _DEST), copies[2])

    def test_an_entry_under_another_frames_id_is_replaced_not_served(self):
        frame, other = _frame((0, 255)), _frame((255,))
        stale = pygame.Surface((3, 3), pygame.SRCALPHA)
        rle._COPIES[id(frame)] = (other, stale)                  # as if the id was recycled
        out = rle.ready(frame, _DEST)
        self.assertIsNot(out, stale)
        self.assertEqual(_blitted(out), _blitted(frame))
        self.assertEqual(len(rle._COPIES), 1)
        self.assertIs(rle._COPIES[id(frame)][0], frame)

    def test_the_cap_holds_a_fights_aura_frames(self):
        # A packed fight asks for 342 distinct aura frames at 150 and 456 at
        # 250 (RND-010.6, sitting 1's count); the cap is over twice the
        # larger, rounded up.
        self.assertEqual(rle._CAP, 1024)
        self.assertGreaterEqual(rle._CAP, 2 * 456)

    def test_every_shipped_aura_frame_is_binary(self):
        from game.assets import get_assets
        assets = get_assets()
        for rig in ("element_fire", "element_ice", "element_thunder", "element_wind"):
            for i in range(assets.frame_count(rig, "loop")):
                for size in (None, (40, 39), (60, 58), (140, 135), (260, 251)):
                    with self.subTest(rig=rig, frame=i, size=size):
                        self.assertTrue(rle.binary_alpha(assets.frame(rig, "loop", i, size=size)))

    def test_the_aura_is_blitted_from_its_copy(self):
        frame = _frame((0, 255))

        class _Profile:
            colour = (1, 2, 3)

            def aura_size(self, width):
                return (40, 30)

            def aura_frame(self, size=None):
                return frame

        class _Style:
            ring_pad, rig_scale = 2, 1.0

        class _Cam:
            zoom = 1.0

            def world_to_screen(self, pos):
                return pos

        class _Body:
            pos, radius = (50, 50), 10

        blits = []

        class _Target(pygame.Surface):
            def blit(self, source, *a, **k):
                blits.append(source)
                return super().blit(source, *a, **k)

        layers._aura(_Target((100, 100)), _Cam(), _Body(), _Profile(), _Style())
        blitted = blits[0]
        self.assertIs(blitted, rle._COPIES[id(frame)][1])
        self.assertIsNot(blitted, frame)


if __name__ == "__main__":
    unittest.main()
