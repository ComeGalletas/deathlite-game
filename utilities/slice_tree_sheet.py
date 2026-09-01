"""Turn `tree_sheet.png` into the horizontal strip the other trees use.

The sheet arrived as a 4x3 grid of 192 px cells: six animation frames of a pine
in the first row and a half, one lone stump in the bottom-left, and five empty
cells. Every other tree in `assets/terrain/props` is a **horizontal strip** --
`frame` width 192, `frames` frames, sheet width 192 * frames -- and
`Assets.frames` slices on that, so a grid cannot be declared at all.

The stump is not an animation frame; it is a prop that happens to share the
sheet. It comes out as its own file and its own decoration rig, which is also
the only way it can ever be placed, since a decoration draws frame 0 of its rig.
"""
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

SRC = "assets/terrain/props/tree_sheet.png"
CELL = 192
# Row-major, and the two empty cells at the end of row 1 are skipped rather
# than trusted: a strip with a blank frame reads as the tree vanishing.
FRAMES = [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1)]
STUMP = (0, 2)


def _bounds(surf):
    a = pygame.surfarray.array_alpha(surf).T > 8
    if not a.any():
        return None
    ys = np.nonzero(a.any(axis=1))[0]
    xs = np.nonzero(a.any(axis=0))[0]
    return xs.min(), xs.max(), ys.min(), ys.max(), a


def _anchor_and_footprint(surf):
    """Where the prop meets the ground, and how wide its base is.

    Calibrated against `deco_tree_3`, whose art bottoms out at row 169 and is
    declared `anchor [96, 170]`, `footprint 43` against a widest base of 42 --
    so the anchor sits one row under the lowest pixel, on the horizontal centre
    of the base, and the footprint is the widest the base gets.
    """
    x0, x1, y0, y1, a = _bounds(surf)
    widest = 0
    centres = []
    for r in range(max(y0, y1 - 14), y1 + 1):
        xs = np.nonzero(a[r])[0]
        if len(xs) < 4:            # the last row or two taper to a point
            continue
        widest = max(widest, int(xs.max() - xs.min() + 1))
        centres.append(int((xs.min() + xs.max()) // 2))
    return (int(round(sum(centres) / len(centres))), int(y1) + 1), widest


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheet = pygame.image.load(SRC).convert_alpha()

    def cell(cx, cy):
        return sheet.subsurface((cx * CELL, cy * CELL, CELL, CELL)).copy()

    strip = pygame.Surface((CELL * len(FRAMES), CELL), pygame.SRCALPHA)
    for i, (cx, cy) in enumerate(FRAMES):
        piece = cell(cx, cy)
        if _bounds(piece) is None:
            sys.exit(f"cell {(cx, cy)} is empty -- the frame list is wrong")
        strip.blit(piece, (i * CELL, 0))
    pygame.image.save(strip, "assets/terrain/props/tree_5.png")
    anchor, foot = _anchor_and_footprint(cell(*FRAMES[0]))
    print(f"  tree_5.png  {strip.get_size()}  {len(FRAMES)} frames"
          f"   anchor {list(anchor)}  footprint {foot}")

    stump = cell(*STUMP)
    pygame.image.save(stump, "assets/terrain/props/stump_5.png")
    s_anchor, _ = _anchor_and_footprint(stump)
    print(f"  stump_5.png {stump.get_size()}  1 frame"
          f"    anchor {list(s_anchor)}")


if __name__ == "__main__":
    main()
