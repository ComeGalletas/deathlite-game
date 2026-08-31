"""Prep the raw `vertical_stairs.png` art into the stone stair overlay sprites.

The source (`assets/terrain/tiles/vertical_stairs.png`) is an authored preview
on an opaque brown-grey background: a north-south rock staircase flanked by two
big foliage bushes. The bushes are **not** wanted -- the vertical pathway is a
bare stone flight that has to read against whatever biome grass surrounds it,
so this crops the stone column only and drops the greenery.

A vertical pathway spans one or two levels (`CLIFF_TILES` each), so two sprites
are written, each one tile wide and cropped at its own aspect so the steps stay
square-ish rather than being squashed by a runtime rescale:

    vstairs_1.png   64 x 64    a one-level drop
    vstairs_2.png   64 x 128   a two-level drop

The stone column is located by colour rather than hard-coded pixels, so a
re-crop of the source keeps working. Run once after the source art changes:

    python -m utilities.prep_vstairs
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

TILES = Path(__file__).resolve().parent.parent / "assets" / "terrain" / "tiles"
SRC = TILES / "vertical_stairs.png"
# (destination, tiles tall) -- the sprite for each supported drop.
OUTS = ((TILES / "vstairs_1.png", 1), (TILES / "vstairs_2.png", 2))
PX = 64
# Fraction of a column's height that must be stone for it to count as part of
# the flight, and how far the crop is inset from the detected stone edges so
# the step end-caps keep their dark outline.
COL_MIN = 0.30
PAD = 2


def _is_bg(px) -> bool:
    """The warm grey-brown backdrop (~55,51,52 with a soft gradient). The near
    black step outlines (cooler / bluer) are art -- kept."""
    r, g, b, _a = px
    return (38 <= r <= 74 and 36 <= g <= 68 and 36 <= b <= 70
            and abs(r - b) < 11 and abs(r - g) < 13 and g <= r + 5)


def _is_foliage(px) -> bool:
    """The flanking bushes: strongly green (green well clear of blue). Keyed
    out along with the backdrop so no leaf sliver survives at the sprite's
    edges -- the overlay shows the biome grass through there instead."""
    r, g, b, a = px
    return a > 0 and g > b + 25 and g > 80


def _is_stone(px) -> bool:
    """Stone is neutral-to-blue (blue at least matches green). Backdrop,
    foliage and fully dark pixels are excluded."""
    r, g, b, a = px
    return (a > 0 and not _is_bg(px) and not _is_foliage(px)
            and b + 6 >= g and (r + g + b) > 90)


def _stone_column(surf: pygame.Surface) -> pygame.Rect:
    """Bounding box of the stone flight, excluding the foliage wings."""
    w, h = surf.get_size()
    counts = [sum(1 for y in range(h) if _is_stone(surf.get_at((x, y))))
              for x in range(w)]
    need = COL_MIN * h
    cols = [x for x, n in enumerate(counts) if n >= need]
    if not cols:
        raise SystemExit("no stone column found -- check the source art")
    # widest contiguous run of stone columns == the flight (the wings are
    # green, so they never qualify)
    best = run = [cols[0]]
    for x in cols[1:]:
        if x == run[-1] + 1:
            run.append(x)
        else:
            run = [x]
        if len(run) > len(best):
            best = list(run)
    x0, x1 = best[0], best[-1]
    rows = [y for y in range(h)
            if any(_is_stone(surf.get_at((x, y))) for x in range(x0, x1 + 1))]
    return pygame.Rect(x0, rows[0], x1 - x0 + 1, rows[-1] - rows[0] + 1)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    src = pygame.image.load(str(SRC)).convert_alpha()
    keyed = pygame.Surface(src.get_size(), pygame.SRCALPHA)
    for y in range(src.get_height()):
        for x in range(src.get_width()):
            px = src.get_at((x, y))
            clear = _is_bg(px) or _is_foliage(px)
            keyed.set_at((x, y), (0, 0, 0, 0) if clear else px)

    col = _stone_column(keyed)
    col = pygame.Rect(col.x - PAD, col.y, col.w + 2 * PAD, col.h)
    col = col.clip(keyed.get_rect())
    print(f"stone column at {tuple(col)} of {src.get_size()}")

    for dst, tiles in OUTS:
        # Crop from the *bottom* of the flight (the foot is where it meets the
        # low ground) at the output's own aspect, so the steps are never
        # stretched: taller sprite -> more steps, not longer ones.
        want_h = min(col.h, round(col.w * tiles * PX / PX))
        take = pygame.Rect(col.x, col.bottom - want_h, col.w, want_h)
        piece = keyed.subsurface(take.clip(keyed.get_rect()))
        out = pygame.transform.smoothscale(piece, (PX, tiles * PX))
        pygame.image.save(out, str(dst))
        print(f"wrote {dst.name}  ({PX}x{tiles * PX}, from {tuple(take)})")


if __name__ == "__main__":
    main()
