"""RLE-encoded copies of the aura frames, for a cheaper blit (RND-010.6).

An aura is mostly clear pixels round a ring. Blitted plain, SDL blends
every one of them; from a copy marked `set_alpha(255, RLEACCEL)` it keeps
the per-pixel alpha but encodes the clear runs once, on the first blit, and
skips them from then on. On the owner's machine, in the packed fight at 250
(`crowd_draw_journal.md`, RND-010.6, sitting 4), the under-layer's rows
fell by 1.66 ms.

Exact under two conditions, and where either fails the frame is blitted
plain:
* **The frame:** every pixel clear (alpha 0) or opaque (255), and no
  surface alpha of its own. SDL's RLE path blends a translucent pixel by
  its own formula, a channel off by one against the plain blit
  (`binary_alpha`, checked once per frame). Every shipped aura frame is
  binary at every size (`tests/render/test_aura_rle.py`).
* **The destination:** a 32-bit surface with no per-pixel alpha, as the
  display and the game's scratch surfaces are. Onto a surface with alpha,
  pygame's own blitter writes the colour of a clear source pixel into a
  clear destination pixel and the RLE path skips it (the same picture, not
  the same bytes); onto a surface of fewer bits, SDL re-encodes the copy
  in that format and it no longer blits exactly anywhere (`fits`).

The copies are an LRU of `_CAP`, keyed on `id(frame)` with the source kept
in the entry so its id cannot be recycled under the cache, as
`elements.washed` does. A packed fight asks for 342 distinct aura frames at
150 and 456 at 250 (four elements, their animation frames, a size per body
radius); the cap is over twice the larger (912), rounded up to 1024. SDL
frees an encoded copy's pixel buffer and keeps only the runs; anything
that locks a copy (`get_at`, `copy`, a transform) decodes it again, so
nothing but `ready`'s caller should touch one.
"""
from __future__ import annotations

from collections import OrderedDict

import pygame

_CAP = 1024
# id(frame) -> (frame, the RLE copy, or the frame itself where it is not
# binary), the one used longest ago first.
_COPIES: OrderedDict[int, tuple] = OrderedDict()


def binary_alpha(frame: pygame.Surface) -> bool:
    """Is every pixel of `frame` either clear (alpha 0) or opaque (255),
    with no surface alpha below 255 on top? The pixels over alpha 0 counted
    against those over 254, by `pygame.mask` (no numpy in the game)."""
    if frame.get_alpha() not in (None, 255):
        return False
    return (pygame.mask.from_surface(frame, 0).count()
            == pygame.mask.from_surface(frame, 254).count())


def fits(dest: pygame.Surface) -> bool:
    """Is `dest` a surface an RLE copy blits onto exactly: 32 bits a pixel,
    no per-pixel alpha?"""
    return dest.get_bitsize() == 32 and not dest.get_flags() & pygame.SRCALPHA


def ready(frame: pygame.Surface | None, dest: pygame.Surface) -> pygame.Surface | None:
    """What to blit onto `dest` for `frame`: its RLE copy where the frame is
    binary and `dest` fits, `frame` itself otherwise (or None for None)."""
    if frame is None or not fits(dest):
        return frame
    key = id(frame)
    hit = _COPIES.get(key)
    if hit is not None and hit[0] is frame:
        _COPIES.move_to_end(key)
        return hit[1]
    if binary_alpha(frame):
        out = frame.copy()
        out.set_alpha(255, pygame.RLEACCEL)
    else:
        out = frame
    if hit is not None:                     # another frame's entry under this key: replace it
        del _COPIES[key]
    elif len(_COPIES) >= _CAP:
        _COPIES.popitem(last=False)
    _COPIES[key] = (frame, out)
    return out
