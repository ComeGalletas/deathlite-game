"""Water scenery: the open sea, the ring hugging each island, and the lakes.

The water half of the decoration scatter; `scatter_room.py` is the land half.
All three passes here feed the one
`store._void_decor` list, because all three draw at the same moment: the
renderer paints the water buffer, then the shoreline foam, then this, and only
*then* the islands' baked ground surfaces. A lake cell is left transparent by
that bake ("the water buffer shows through" -- `grid_paint.paint_room_grid`),
so a prop dropped on one is still visible through the island it sits inside.

An entry's `placement` selects the pass:

  "void"   -- open sea, on a lattice across the whole world
  "shore"  -- the water tiles orthogonally touching an island
  "lake"   -- inland water (`layout.LAKE` cells)

`chance` is a probability per candidate: per lattice cell for the sea, per
water tile for the other two.
"""
from __future__ import annotations

import random

from game import config
from world.layout import GROUND, LAKE
from world.terrain.decor.rigs import load_rig

# Lattice pitch for the open sea, in world px. Two and a half tiles: fine
# enough that a rock is never lonely, coarse enough that the whole sea of a
# 19,000 px world is a few thousand draws rather than a few hundred thousand.
_SEA_STEP = 160

# Safety ceiling, in instances per million square world px. The sea pass is
# bounded by its own lattice anyway; this only exists so that raising a
# `chance` in the data cannot quietly turn into a hundred thousand surfaces.
_MAX_PER_MP = 12.0

_ORTH = ((-1, 0), (1, 0), (0, -1), (0, 1))


def build_water_decor(store, a) -> None:
    """Seeded water scenery for the whole world. Deterministic per
    `(layout.seed, position)` -- a string seed, so it is stable regardless of
    `PYTHONHASHSEED`."""
    reg = a.terrain.get("decorations", [])
    if not reg or store.layout is None:
        return
    resolved: dict = {}
    out: list[tuple] = []

    def place(entry, x, y):
        got = load_rig(a, resolved, entry["rig"], float(entry.get("scale", 1.0)))
        if got is not None:
            frs, ax, ay, fps = got
            out.append((frs, ax, ay, fps, x, y))

    _open_sea(store, [e for e in reg if e.get("placement") == "void"], place)
    _shorelines(store, [e for e in reg if e.get("placement") == "shore"], place)
    _lakes(store, [e for e in reg if e.get("placement") == "lake"], place)

    b = store.layout.bounds
    cap = max(240, int(_MAX_PER_MP * b.width * b.height / 1_000_000))
    store._void_decor = out[:cap]


def _pick(rng, entries, weights, total):
    """One entry, drawn by `chance`. The caller has already rolled `total`."""
    return rng.choices(entries, weights=weights, k=1)[0]


def _weights(entries):
    w = [max(0.0, float(e.get("chance", 0.1))) for e in entries]
    return w, sum(w)


def _open_sea(store, entries, place) -> None:
    """Scenery on the open water, on a lattice across the whole world.

    This used to stop after 240 instances. The scan runs north to south, so the
    cap was not a density limit but a *horizon*: on a 19,136 x 7,680 world it
    ran out a quarter of the way down and every island below the first row sat
    in an empty sea. The lattice bounds the count on its own -- one candidate
    per cell, probability at most one -- so nothing needs to stop it early.
    """
    if not entries or store.layout is None:
        return
    weights, total = _weights(entries)
    if total <= 0:
        return
    seed = store.layout.seed
    b = store.layout.bounds
    inset = config.CHUNK_SIZE // 3
    gy = b.y + inset
    while gy < b.bottom - inset:
        gx = b.x + inset
        while gx < b.right - inset:
            rng = random.Random(f"{seed}:{gx}:{gy}:void")
            if rng.random() < total:
                x = gx + rng.uniform(0, _SEA_STEP)
                y = gy + rng.uniform(0, _SEA_STEP)
                # Clear of land by a margin, so an open-sea rock never crowds
                # a beach -- that band is the `shore` pass's job.
                if not (store._point_ok(x, y) or any(
                        store._point_ok(x + dx, y + dy)
                        for dx in (-36, 36) for dy in (-36, 36))):
                    place(_pick(rng, entries, weights, total), x, y)
            gx += _SEA_STEP
        gy += _SEA_STEP


def _water_ring(room) -> list:
    """Tile positions of the water orthogonally touching this island's ground.

    Derived from the room's own grid rather than from a global water mask: a
    position absent from the grid is sea by construction, and the ground cell
    next to it is what makes that sea a *shore*. The land-side twin of this is
    `grid_paint.grid_shore`, which anchors the foam.
    """
    grid = room.grid
    if not grid:
        return []
    ring = set()
    for (col, row), c in grid.items():
        if c.kind != GROUND:
            continue
        for dc, dr in _ORTH:
            p = (col + dc, row + dr)
            if grid.get(p) is None:
                ring.add(p)
    return sorted(ring)


def _lake_cells(room) -> list:
    """This island's inland water, `layout.LAKE` cells."""
    return sorted(p for p, c in room.grid.items() if c.kind == LAKE) \
        if room.grid else []


def _scatter_tiles(store, entries, place, tiles_of, tag: str) -> None:
    """Shared body of the shore and lake passes: roll each candidate water tile
    of every island, and place at a jittered point inside it.

    `store._point_ok` is the final word in both cases. The grid says a tile is
    water; only the collision layer knows whether some *other* island's rect
    overlaps it, which the height-map generator allows.
    """
    if not entries or store.layout is None:
        return
    weights, total = _weights(entries)
    if total <= 0:
        return
    px = config.TILE_PX
    seed = store.layout.seed
    for room in store.layout.rooms:
        if not room.grid:
            continue
        rng = random.Random(f"{seed}:{room.id}:{tag}")
        for col, row in tiles_of(room):
            if rng.random() >= total:
                continue
            x = room.rect.x + col * px + rng.uniform(px * 0.25, px * 0.75)
            y = room.rect.y + row * px + rng.uniform(px * 0.25, px * 0.75)
            if store._point_ok(x, y):
                continue
            place(_pick(rng, entries, weights, total), x, y)


def _shorelines(store, entries, place) -> None:
    """Scenery in the water hugging each island -- the band the open-sea pass
    deliberately holds off from, and which was empty before this existed."""
    _scatter_tiles(store, entries, place, _water_ring, "shore")


def _lakes(store, entries, place) -> None:
    """Scenery on inland water.

    Lakes got nothing at all before: the sea pass is a 160 px lattice testing
    for land 36 px out in four directions, and a lake is three to fourteen
    tiles across, so it failed both tests almost everywhere. Rolling the LAKE
    cells directly is exact and costs nothing -- the generator already knows
    which tiles they are.
    """
    _scatter_tiles(store, entries, place, _lake_cells, "lake")
