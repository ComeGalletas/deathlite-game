"""Turn a flat-backdrop render of a tilesheet into a transparent 64px sheet.

Art keeps arriving as a large render on a solid white ground with no alpha
channel -- `rocky_temp_stairs.png`, then `new_tilemap_6.png`, a re-render of a
whole assembled sheet with one block recoloured. The structure is already
right; what is missing is the transparency and the scale. This does both.

Usage:  python -m utilities.key_sheet <in.png> <out.png>

Two things make it more than a resize.

**The backdrop is found by connectivity, not by colour alone.** A tilesheet is
full of enclosed light pixels -- the cream highlights in the rock, the pale
crack fills -- and a plain "near-white is transparent" test punches holes
through the middle of tiles. Instead the near-white mask is flood filled, so
only ground actually reachable from outside the art is cleared. The fill works
on row *runs* rather than pixels: a few thousand runs against four million,
which is what makes a pure-Python fill fast enough to not need scipy (which is
not installed here).

The fill is seeded from **every tile seam**, not just the image border. A sheet
is not one picture: its tiles butt against each other, so the notches between
the rock lobes along a tile's south fringe are enclosed by the *neighbouring*
tile's art and a border-only fill leaves them opaque. That is not theoretical
-- keying this sheet from the border alone left 891 white pixels wedged into
exactly those fringes, against zero in the hand-authored `tilemap_1`. Each tile
is its own drawing, so each tile's own edge is an outside.

**The downscale averages only the opaque pixels** under each output cell. Box
filtering the raw image instead would drag the white ground into every silhouette
edge and leave a bright halo around every tile; restricting the average to
covered pixels keeps the edge colour honest. A cell less than 45% covered stays
clear, which reproduces the hard alpha edge the hand-authored sheets have.
"""
from __future__ import annotations

import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

PX = 64
COLS, ROWS = 9, 6

# Near-white *and* neutral. The rock's own highlights are a warm cream,
# chromatic enough that a plain brightness test would eat them.
_LIGHT = 244
_CHROMA = 10
# Below this coverage an output cell is backdrop rather than a thin edge.
_COVER = 0.45
# The renders are upscales, so art meets ground across a few pixels of blend
# rather than a hard edge. Those pixels are mostly backdrop by weight and pull
# every silhouette edge toward white if they are counted as art. They are too
# dim for `_LIGHT` and too tinted for `_CHROMA`, so they are taken instead by
# growing the *known* backdrop into anything still this light -- which cannot
# run away into the rock's own cream highlights, because those do not touch the
# backdrop. Depth is capped near the upscale factor.
_BLEND_LIGHT = 205
_BLEND_DEPTH = 6


def backdrop_mask(rgb: np.ndarray) -> np.ndarray:
    """True where the pixel is the flat ground the art was rendered on.

    Colour is the candidate test; reachability from the border is the decision.
    """
    light = rgb.min(axis=2) > _LIGHT
    neutral = (rgb.max(axis=2).astype(int) - rgb.min(axis=2)) < _CHROMA
    cand = light & neutral
    return _erode_blend(_fill_from_seams(cand), rgb)


def _erode_blend(bg: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """Grow the backdrop into the anti-aliased ring around each silhouette."""
    soft = rgb.min(axis=2) > _BLEND_LIGHT
    for _ in range(_BLEND_DEPTH):
        nb = np.zeros_like(bg)
        nb[1:, :] |= bg[:-1, :]
        nb[:-1, :] |= bg[1:, :]
        nb[:, 1:] |= bg[:, :-1]
        nb[:, :-1] |= bg[:, 1:]
        grown = bg | (nb & soft)
        if grown.sum() == bg.sum():
            break
        bg = grown
    return bg


def _row_runs(row: np.ndarray) -> list[tuple[int, int]]:
    """Maximal True spans in a boolean row, as half-open (start, stop)."""
    edges = np.flatnonzero(np.diff(np.concatenate(([False], row, [False]))
                                   .astype(np.int8)))
    return list(zip(edges[0::2], edges[1::2]))


def _fill_from_seams(cand: np.ndarray) -> np.ndarray:
    """Flood fill `cand` from every tile edge, run by run.

    Runs in adjacent rows are neighbours when their x spans overlap, so the
    whole fill is a breadth-first walk over a few thousand nodes instead of a
    per-pixel one over four million.
    """
    h, w = cand.shape
    runs = [_row_runs(cand[y]) for y in range(h)]
    seen = [[False] * len(r) for r in runs]

    # Seed rows: the image's own top and bottom, and both sides of every
    # horizontal tile seam. Seed columns likewise -- a run is seeded when it
    # straddles one, which is how a notch that opens sideways is reached.
    seam_y = set()
    for y in _bounds(h, ROWS):
        seam_y.update((max(0, y - 1), min(h - 1, y)))
    seam_x = [min(w - 1, x) for x in _bounds(w, COLS)]

    stack = []
    for y in seam_y:
        stack.extend((y, i) for i in range(len(runs[y])))
    for y in range(h):
        for i, (a, b) in enumerate(runs[y]):
            if a == 0 or b == w or any(a <= x < b for x in seam_x):
                stack.append((y, i))

    while stack:
        y, i = stack.pop()
        if seen[y][i]:
            continue
        seen[y][i] = True
        a, b = runs[y][i]
        for ny in (y - 1, y + 1):
            if not 0 <= ny < h:
                continue
            for j, (c, d) in enumerate(runs[ny]):
                if c < b and a < d and not seen[ny][j]:
                    stack.append((ny, j))

    out = np.zeros((h, w), bool)
    for y in range(h):
        for i, (a, b) in enumerate(runs[y]):
            if seen[y][i]:
                out[y, a:b] = True
    return out


def _bounds(total: int, n: int) -> np.ndarray:
    """Tile boundaries for a sheet whose tiles are not a whole number of
    pixels wide -- 2528 across nine columns is 280.9, not 281."""
    return (np.arange(n + 1) * total / n).round().astype(int)


def downscale(rgb: np.ndarray, keep: np.ndarray) -> pygame.Surface:
    h, w = keep.shape
    out = pygame.Surface((COLS * PX, ROWS * PX), pygame.SRCALPHA)
    xs = _bounds(w, COLS * PX)
    ys = _bounds(h, ROWS * PX)
    src = rgb.astype(np.float64)
    cov = keep.astype(np.float64)
    for oy in range(ROWS * PX):
        y0, y1 = ys[oy], ys[oy + 1]
        for ox in range(COLS * PX):
            m = cov[y0:y1, xs[ox]:xs[ox + 1]]
            if m.size == 0 or m.mean() < _COVER:
                continue
            box = src[y0:y1, xs[ox]:xs[ox + 1]]
            col = (box * m[..., None]).sum(axis=(0, 1)) / m.sum()
            # Last guard, for a notch that really is sealed by art on all four
            # sides, and for a cell straddling a tile seam that catches a
            # sliver of blend from both neighbours. The discriminator is
            # *neutrality*, not brightness: this art is teal rock and yellow
            # sand, both strongly tinted, and `tilemap_1` contains no light
            # neutral pixel at all -- so a cell that averages to one is
            # backdrop however it got there.
            if col.min() > 225 and col.max() - col.min() < 12:
                continue
            out.set_at((ox, oy), (*col.round().astype(int), 255))
    return out


def convert(src_path: str, dst_path: str) -> pygame.Surface:
    img = pygame.image.load(src_path).convert_alpha()
    w, h = img.get_size()
    rgb = pygame.surfarray.array3d(img).transpose(1, 0, 2)
    keep = ~backdrop_mask(rgb)
    sheet = downscale(rgb, keep)
    pygame.image.save(sheet, dst_path)
    print(f"{src_path} {w}x{h} -> {dst_path} {sheet.get_size()}"
          f"   ({keep.mean() * 100:.1f}% of the render was art)")
    return sheet


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__.strip().splitlines()[6])
    pygame.init()
    pygame.display.set_mode((1, 1))
    convert(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
