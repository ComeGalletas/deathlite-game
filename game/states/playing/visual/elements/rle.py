"""RLE-encoded copies of the aura frames, for a cheaper blit (RND-010.6).

An aura is mostly clear pixels round a ring. Blitted plain, SDL blends
every one of them; from a copy marked `set_alpha(255, RLEACCEL)` it keeps
the per-pixel alpha but encodes the clear runs once, on the first blit, and
skips them from then on. On the owner's machine, in the packed fight at 250
(`crowd_draw_journal.md`, RND-010.6), that took 1.14 ms off the draw's p50.

Exact only for a frame whose every pixel is either clear (alpha 0) or
opaque (255). SDL's RLE path blends a translucent pixel by its own formula,
a channel off by one against the plain blit, so a frame with any is handed
back as it is (`binary_alpha`, checked once per frame). Every shipped aura
frame is binary at every size (`tests/render/test_aura_rle.py`).

The copies are an LRU of `_CAP`, keyed on `id(frame)` with the source kept
in the entry so its id cannot be recycled under the cache, as
`elements.washed` does. A packed fight asks for 342 distinct aura frames at
150 and 456 at 250 (four elements, their animation frames, a size per body
radius); the cap is over twice the larger (912), rounded up to 1024.
"""
from __future__ import annotations

from collections import OrderedDict

import pygame

_CAP = 1024
# id(frame) -> (frame, the RLE copy, or the frame itself where its alpha is
# not binary), the one used longest ago first.
_COPIES: OrderedDict[int, tuple] = OrderedDict()


def binary_alpha(frame: pygame.Surface) -> bool:
    """Is every pixel of `frame` either clear (alpha 0) or opaque (255)?
    The pixels over alpha 0 counted against those over 254, by
    `pygame.mask` (no numpy in the game)."""
    return (pygame.mask.from_surface(frame, 0).count()
            == pygame.mask.from_surface(frame, 254).count())


def ready(frame: pygame.Surface | None) -> pygame.Surface | None:
    """What to blit for `frame`: its RLE copy where its alpha is binary,
    `frame` itself where it is not (or for None)."""
    if frame is None:
        return None
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
