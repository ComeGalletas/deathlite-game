"""The sheep pen (`world/gen/village/`): a ring of fence tiles with a
two-tile gate, sought on the side of the island the bridges are not.
"""
from __future__ import annotations

import math

import pygame

from entities.obstacle import KINDS
from world.gen.scatter import _blocks
from world.gen.tuning import (
    _V_GAP, _V_PEN_DIST, _V_PEN_H, _V_PEN_SCALE, _V_PEN_SWEEPS, _V_PEN_W,
)
from world.layout import GROUND
from world.gen.village.site import FENCE_SLOTS, _Site


def _place_pen(site: _Site, forge: pygame.Vector2, back: pygame.Vector2):
    """A `w x h` ring of fence tiles with a two-tile gate in the middle of
    its south side, its centre `_V_PEN_DIST` tiles from the forge along
    `back`. Returns the interior as a world-px `Rect` (what the sheep are
    leashed to), or `None` when no size at no distance fits.

    The fence has its own pitch, `_V_PEN_SCALE` of a world tile (the owner
    asked for a corral 40% smaller): the ring's tiles are laid `pitch` px
    apart from the pen's own origin, not on the world grid, and the art is
    drawn at the same scale so it still meets post to post. Two tiles of
    gate rather than one, from when the repair still judged the pen: a
    one-tile gap read as sealed whenever a lattice column landed off its
    middle, and the repair pulled a gate post out."""
    for step, pad in _V_PEN_SWEEPS:
        pen = _pen_sweep(site, forge, back, step, pad)
        if pen is not None:
            return pen
    return None
def _pen_sweep(site: _Site, forge: pygame.Vector2, back: pygame.Vector2,
               step: float, pad: float):
    """One pass of the pen search: every size at every candidate centre, the
    fan stepping `step` radians either side of `back` and each candidate
    keeping `pad` tiles of ground round the rail. `_place_pen` runs the
    passes of `_V_PEN_SWEEPS` in turn and takes the first pen any of them
    finds."""
    px = site.px
    pitch = px * _V_PEN_SCALE
    # Smallest first: on the quarter-smaller island (HI-3) a shuffled order
    # lost a third of the pens to sizes that had no room anywhere.
    sizes = sorted(((w, h) for w in range(_V_PEN_W[0], _V_PEN_W[1] + 1)
                    for h in range(_V_PEN_H[0], _V_PEN_H[1] + 1)),
                   key=lambda s: s[0] * s[1])
    lo, hi = _V_PEN_DIST
    fence_r = float(KINDS["fence"][0])
    # The fan reaches all the way round, so a pen beside a road still beats
    # no pen; `step` is how finely it is combed. At 0.3 this is the same
    # twenty-one angles the single-pass search used.
    fan = [0] + [s * k for k in range(1, int(math.pi / step) + 1) for s in (1, -1)]
    # Nearest first, then fanning out from `back`.
    d = lo
    while d <= hi + 1e-9:
        for k in fan:
            a = math.atan2(back.y, back.x) + k * step
            cx = forge.x + math.cos(a) * d * px
            cy = forge.y + math.sin(a) * d * px
            for w, h in sizes:
                ox = round(cx - w * pitch / 2)
                oy = round(cy - h * pitch / 2)
                posts = [(ox + (col + 0.5) * pitch, oy + (row + 0.5) * pitch, slot)
                         for (col, row), slot in _pen_tiles(0, 0, w, h)]
                if _pen_fits(site, ox, oy, w * pitch, h * pitch, posts,
                             fence_r, pad):
                    for x, y, slot in posts:
                        site.add("fence", x, y, variant=FENCE_SLOTS.index(slot) + 1)
                    return pygame.Rect(round(ox + pitch), round(oy + pitch),
                                       round((w - 2) * pitch), round((h - 2) * pitch))
        d += 0.5
    return None
def _pen_tiles(c0: int, r0: int, w: int, h: int) -> list:
    """`((col, row), slot)` for the ring of a `w x h` pen whose top-left
    tile is `(c0, r0)`. The pack ships the south rail only as two gate
    halves, so the south side is corner, rail, gate-left, two open tiles,
    gate-right, rail, corner; the plain rail is the north tile, whose band
    the halves share."""
    c1, r1 = c0 + w - 1, r0 + h - 1
    gate = (c0 + w // 2 - 1, c0 + w // 2)   # the two open tiles
    out = [((c0, r0), "nw"), ((c1, r0), "ne"), ((c0, r1), "sw"), ((c1, r1), "se")]
    for i, col in enumerate(range(c0 + 1, c1)):
        out.append(((col, r0), "n1" if i % 2 == 0 else "n2"))
        if col == gate[0] - 1:
            out.append(((col, r1), "s_gate_l"))
        elif col == gate[1] + 1:
            out.append(((col, r1), "s_gate_r"))
        elif col not in gate:
            out.append(((col, r1), "n1" if i % 2 == 0 else "n2"))
    for row in range(r0 + 1, r1):
        out.append(((c0, row), "w"))
        out.append(((c1, row), "e"))
    return out
def _pen_fits(site: _Site, ox: float, oy: float, W: float, H: float, posts,
              fence_r, pad: float) -> bool:
    """`(ox, oy)` is the ring's top-left corner and `W x H` its size, in
    world px; `posts` the fence centres. The whole footprint and `pad`
    tiles round it must be plain ground (a whole tile when the posts stood
    0.6 of a tile apart; at 0.45 the margin outweighed the pen and the
    small islands lost theirs, so the first sweep asks half a tile and the
    fallback a quarter), so the pen never straddles the coast and a sheep
    never bounces over the sea; every post passes the village's own tests;
    nothing already stands inside."""
    px = site.px
    keep = px * pad
    c0, r0 = site.cell_of(ox - keep, oy - keep)
    c1, r1 = site.cell_of(ox + W + keep, oy + H + keep)
    for col in range(c0, c1 + 1):
        for row in range(r0, r1 + 1):
            cell = site.grid.get((col, row))
            if cell is None or cell.kind != GROUND:
                return False
    for x, y, _slot in posts:
        if (_blocks(site.doors, x, y, fence_r)
                or not site.free(x, y, fence_r, _V_GAP)
                or not site.off_lanes(x, y, fence_r)
                or not site.art_ok("fence", x, y)):
            return False
    inner = pygame.Rect(round(ox), round(oy), round(W), round(H))
    return not any(inner.collidepoint(o.pos.x, o.pos.y) for o in site.placed)
