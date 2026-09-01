"""Assemble the rocky ground tilesheets.

Two paths, because the sheet was derived here and then re-rendered by hand.

**Default -- import.** `new_tilemap_6.png` and `new_tilemap_8.png` are
re-renders of the assembled sheets with each one's stair wedges recoloured to
its own ground, delivered flat on white with no alpha. `utilities.key_sheet`
restores the transparency and the 64px scale. The sand sheet additionally has
its cliff faces swapped for `tilemap_1`'s, since it was re-rendered carrying
`tilemap_rocky`'s stratified rock. This is what is on disk.

**`--derive`** rebuilds `tilemap_6` from the source art, which is how the
structure the re-render is based on was arrived at, and how `tilemap_7` and
`tilemap_8` were made.

The derivation's first cut took the whole look from `tilemap_rocky` -- the pale
rubble for the ground rows and the same sheet's stratified rock for the cliffs.
Only the rubble was right. `tilemap_rocky` has **no south-fringed ground row at
all**: in that art a rocky surface's south edge is always drawn as a *face*,
chunky columns seen from the side, so that build put a wall texture flat on the
ground for every `sw s se swe` tile, and the cliff rows never matched the faces
every other tileset renders. So the derivation keeps only the top-down rubble
and takes everything vertical from `tilemap_1`:

    ground rows      rocky r0 (north-fringed) and r1 (plain)
    south row        r0 flipped vertically -- the north rim becomes a south rim
    thin row         top half of the north row over the bottom half of the south
    cliff body/bottom  tilemap_1
    ramp wedges      rocky_temp_stairs.png, keyed and downscaled

`cliff.top` (slots 32-35) is the **same four slots** as the raised block's thin
row, so it stays rubble rather than coming from `tilemap_1` with the other cliff
slots. That sharing is deliberate in the original sheets: a cliff top is the
ground lip seen from above, so it has to match the ground, not the face.
"""
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from utilities import key_sheet

PX = 64
COLS, ROWS = 9, 6
TILES = "assets/terrain/tiles"
# The large renders and the raw source sheets are inputs, not shipped art, and
# live in a sibling folder so the tiles directory holds only what the game
# actually loads.
SRC = f"{TILES}/extras"

# Where each of the sixteen combinations lives, in the sheet's two blocks.
ORDER = ("nw", "n", "ne", "nwe",
         "w", "", "e", "we",
         "sw", "s", "se", "swe",
         "nsw", "ns", "nse", "nswe")
SHORELINE = (0, 1, 2, 3, 9, 10, 11, 12, 18, 19, 20, 21, 27, 28, 29, 30)
RAISED = (5, 6, 7, 8, 14, 15, 16, 17, 23, 24, 25, 26, 32, 33, 34, 35)
CLIFF_BODY = (41, 42, 43, 44)
CLIFF_BOTTOM = (50, 51, 52, 53)
RAMP_W = (36, 45)
RAMP_E = (39, 48)


def load(name, src=False):
    root = SRC if src else TILES
    return pygame.image.load(f"{root}/{name}.png").convert_alpha()


def tile(sheet, slot, cols=COLS):
    r, c = divmod(slot, cols)
    return sheet.subsurface((c * PX, r * PX, PX, PX)).copy()


def at(sheet, col, row):
    return sheet.subsurface((col * PX, row * PX, PX, PX)).copy()


def put(sheet, slot, surf):
    r, c = divmod(slot, COLS)
    sheet.fill((0, 0, 0, 0), (c * PX, r * PX, PX, PX))
    sheet.blit(surf, (c * PX, r * PX))


def thin(top, bot):
    """A tile open north *and* south: the top half of the north-fringed tile
    over the bottom half of the south-fringed one, same column. They share a
    base texture, so the join at mid-tile does not read as a seam."""
    out = pygame.Surface((PX, PX), pygame.SRCALPHA)
    out.blit(top.subsurface((0, 0, PX, PX // 2)), (0, 0))
    out.blit(bot.subsurface((0, PX // 2, PX, PX // 2)), (0, PX // 2))
    return out


def ground_block(rocky):
    """The sixteen ground tiles, all derived from rocky's two top-down rows."""
    north = [at(rocky, c, 0) for c in range(4)]          # nw n ne nwe
    mid = [at(rocky, c, 1) for c in range(4)]            # w  '' e  we
    # Flipping the north row vertically moves its rim to the bottom, which is
    # exactly the south row: vflip(nw) is fringed south and west, vflip(nwe)
    # south, west and east. The rubble itself has no up/down reading, so the
    # flip is invisible in the texture.
    south = [pygame.transform.flip(s, False, True) for s in north]
    return dict(zip(ORDER, north + mid + south
                    + [thin(north[i], south[i]) for i in range(4)]))


# --- the supplied stair art -------------------------------------------------
#
# `rocky_temp_stairs.png` arrives as a 2892x1440 render on a flat white
# backdrop with no alpha at all. It holds the two ramp wedges side by side, and
# their silhouettes match the wedges already in `tilemap_1` to within about two
# pixels of a 64px tile, so they drop straight into the ramp slots once the
# backdrop is removed and they are scaled down.

def _is_backdrop(rgb):
    """Near-white *and* neutral. The rock's own highlights are a warm cream,
    chromatic enough that a plain brightness test would eat them."""
    light = rgb.min(axis=2) > 244
    neutral = (rgb.max(axis=2).astype(int) - rgb.min(axis=2)) < 10
    return light & neutral


def _column_runs(solid):
    """The x spans the two wedges occupy, found before any row filling -- the
    shapes sit side by side, so filling rows first would bridge the gap between
    them and read as one shape."""
    occ = solid.any(axis=0)
    runs, s = [], None
    for x, on in enumerate(occ):
        if on and s is None:
            s = x
        elif not on and s is not None:
            if x - s > 20:
                runs.append((s, x))
            s = None
    if s is not None:
        runs.append((s, len(occ)))
    return runs


def _keyed(img):
    """Alpha mask for the art. Within each wedge's own column span the backdrop
    is eroded inward from the row's two ends, so a white highlight enclosed by
    rock survives while everything outside the silhouette is cleared."""
    rgb = pygame.surfarray.array3d(img).transpose(1, 0, 2)   # (h, w, 3)
    solid = ~_is_backdrop(rgb)
    runs = _column_runs(solid)
    keep = np.zeros(solid.shape, bool)
    ys = np.arange(solid.shape[0])
    for x0, x1 in runs:
        idx = np.arange(x0, x1)
        span = np.zeros((solid.shape[0], x1 - x0), bool)
        for y in range(solid.shape[0]):
            row = solid[y, x0:x1]
            if row.any():
                span[y, np.flatnonzero(row)[0]:np.flatnonzero(row)[-1] + 1] = True
        # Erode from the columns too. The wedge's foot is a row of rock lobes
        # with backdrop in the notches between them; those notches are enclosed
        # left-to-right, so a row scan alone keeps them and they come through
        # the downscale as white specks along the bottom edge.
        for x in range(x1 - x0):
            col = solid[:, x0 + x]
            if col.any():
                lo, hi = ys[col][0], ys[col][-1]
                span[:lo, x] = False
                span[hi + 1:, x] = False
            else:
                span[:, x] = False
        keep[:, x0:x1] = span
    return rgb, keep, runs


def _wedge(rgb, keep, x0, x1):
    """Box-downscale the slice [x0, x1) to one 64x128 wedge, averaging only the
    opaque source pixels so the backdrop never bleeds into the edge."""
    sub_rgb = rgb[:, x0:x1].astype(np.float64)
    sub_a = keep[:, x0:x1].astype(np.float64)
    h, w = sub_a.shape
    out = pygame.Surface((PX, PX * 2), pygame.SRCALPHA)
    ys = (np.arange(PX * 2 + 1) * h / (PX * 2)).round().astype(int)
    xs = (np.arange(PX + 1) * w / PX).round().astype(int)
    for oy in range(PX * 2):
        for ox in range(PX):
            m = sub_a[ys[oy]:ys[oy + 1], xs[ox]:xs[ox + 1]]
            if m.size == 0 or m.mean() < 0.45:
                continue                       # mostly backdrop -> stays clear
            box = sub_rgb[ys[oy]:ys[oy + 1], xs[ox]:xs[ox + 1]]
            col = (box * m[..., None]).sum(axis=(0, 1)) / m.sum()
            # Belt and braces for the enclosed specks the two erosions cannot
            # reach: nothing in this rock is a neutral near-white, so a cell
            # that averages to one is backdrop that leaked through.
            if col.min() > 238 and col.max() - col.min() < 10:
                continue
            out.set_at((ox, oy), (*col.round().astype(int), 255))
    return out


def stair_wedges():
    img = load("rocky_temp_stairs", src=True)
    rgb, keep, runs = _keyed(img)
    if len(runs) != 2:
        sys.exit(f"expected two wedges in the stair art, found {len(runs)}")

    def lean(x0, x1):
        """Where the mass sits, across the top quarter, as a fraction of width.
        The westward wedge is the one whose narrow top end is on the right."""
        top = keep[: keep.shape[0] // 4, x0:x1]
        xs = np.arange(x1 - x0)[None, :] * np.ones((top.shape[0], 1))
        return float(xs[top].mean() / (x1 - x0))

    left, right = lean(*runs[0]), lean(*runs[1])
    # Asserted rather than assumed, so a re-render that swaps the two fails
    # loudly instead of silently mirroring every staircase in the game.
    if not (left > 0.6 > 0.4 > right):
        sys.exit(f"cannot tell the wedges apart: top-quarter lean "
                 f"{left:.2f} / {right:.2f}")
    return {"w": _wedge(rgb, keep, *runs[0]),
            "e": _wedge(rgb, keep, *runs[1])}


def _keyed_wedges(sheet):
    """Split the two ramp columns of an assembled sheet back into wedges."""
    return {side: (tile(sheet, slots[0]), tile(sheet, slots[1]))
            for side, slots in (("w", RAMP_W), ("e", RAMP_E))}


def derive():
    """Build `tilemap_6` from the source art. See the module docstring."""
    rocky = load("tilemap_rocky", src=True)
    faces = load("tilemap_1")
    ground = ground_block(rocky)
    wedges = stair_wedges()

    sheet = pygame.Surface((COLS * PX, ROWS * PX), pygame.SRCALPHA)
    for slots in (SHORELINE, RAISED):
        for key, slot in zip(ORDER, slots):
            put(sheet, slot, ground[key])
    for slot in CLIFF_BODY + CLIFF_BOTTOM:
        put(sheet, slot, tile(faces, slot))
    for side, slots in (("w", RAMP_W), ("e", RAMP_E)):
        w = wedges[side]
        put(sheet, slots[0], w.subsurface((0, 0, PX, PX)).copy())
        put(sheet, slots[1], w.subsurface((0, PX, PX, PX)).copy())
    pygame.image.save(sheet, f"{TILES}/tilemap_6.png")
    print(f"derived {TILES}/tilemap_6.png  {sheet.get_size()}")
    return sheet


def _swap_cliff_faces(sheet, faces):
    """Give a sheet the cliff faces every other tileset already renders.

    Body and bottom only. `cliff.top` (32-35) is the *same four slots* as the
    raised block's thin row, so it has to keep the sheet's own ground: a cliff
    top is the ground lip seen from above, and taking it from `tilemap_1` would
    put green grass on the rim of a sand terrace and break the thin ground
    strips at the same time.
    """
    for slot in CLIFF_BODY + CLIFF_BOTTOM:
        put(sheet, slot, tile(faces, slot))
    return sheet


def main(argv):
    pygame.init()
    pygame.display.set_mode((1, 1))
    faces = load("tilemap_1")
    if "--derive" in argv:
        derive()
    else:
        # The rocky sheet's faces already came from `tilemap_1`, but they made
        # the round trip through the re-render's upscale and back down, which
        # left them about 4/255 off and carrying the same blend artefacts at
        # their edges that the keying fights everywhere else. Taking them
        # verbatim costs nothing and makes all three sheets literally the same
        # stone.
        rock = key_sheet.convert(f"{SRC}/new_tilemap_6.png",
                                 f"{TILES}/tilemap_6.png")
        pygame.image.save(_swap_cliff_faces(rock, faces), f"{TILES}/tilemap_6.png")
        # The sand sheet was re-rendered with `tilemap_rocky`'s stratified rock
        # in its cliff rows, which is the one part of that source that never
        # matched the rest of the game. Its ground and its own sand-coloured
        # ramp wedges are kept; only the faces are swapped out.
        sand = key_sheet.convert(f"{SRC}/new_tilemap_8.png",
                                 f"{TILES}/tilemap_8.png")
        pygame.image.save(_swap_cliff_faces(sand, faces), f"{TILES}/tilemap_8.png")
        print("swapped tilemap_8 cliff faces for tilemap_1's")
    _finish_green(faces)


def _finish_green(faces):
    """`tilemap_7` gets by borrowing, being the one sheet with no re-render.

    Two separate repairs, both taking from `tilemap_1` --- whose grass is the
    same art this sheet's ground came from, so nothing here is a compromise.

    **Ramp slots.** It was assembled without them. Nothing complained, because a
    missing ramp is not an error: `grid_paint` blits slots 36/45 and 39/48
    unconditionally and an empty slot simply draws nothing, so an east/west
    staircase on that floor would render as bare cliff with a walkable but
    invisible flight over it.

    **Cliff faces.** It was built carrying `tilemap_rocky`'s stratified rock,
    the one part of that source that never matched the rest of the game --- the
    same problem that prompted the `tilemap_6` rebuild and the `tilemap_8`
    swap. Body and bottom only; see `_swap_cliff_faces` for why the top row
    stays with the sheet's own ground.
    """
    sheet = _swap_cliff_faces(load("tilemap_7"), faces)
    for side, slots in (("w", RAMP_W), ("e", RAMP_E)):
        for slot in slots:
            put(sheet, slot, tile(faces, slot))
    pygame.image.save(sheet, f"{TILES}/tilemap_7.png")
    print("tilemap_7: filled ramp slots, swapped cliff faces for tilemap_1's")


if __name__ == "__main__":
    main(sys.argv)
