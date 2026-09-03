"""Per-cell clearance: how much room there is around each cell of the lattice.

The two-pass (1, sqrt2) chamfer distance to the nearest blocked cell, then
lowered by the exact `dist - radius` to every nearby obstacle edge, clamped to
`CLEARANCE_CAP`. No queue, deterministic. A cell is *passable* for an enemy of
radius `r` iff it is walkable and its clearance is at least `r`, so obstacle
avoidance uses the true collision radius with no per-radius rebuild. The
exact obstacle term matters: a tree ring (22 px) is narrower than a 32 px
cell and can sit entirely between cell centres, so a pure cell raster would
miss it.

`world/gen/repair.py` mirrors the obstacle pass (`_killers`), and
`tests/world/test_mirrors.py` checks the two agree on every cell.
"""
from __future__ import annotations

from array import array

_SQRT2 = 2.0 ** 0.5
# Clearance is only ever compared against an enemy radius (<= 30 px today) and
# used as a "how much room is here" weight, so values above this are all "wide
# open" -- capping keeps the field bounded and the obstacle scan local.
CLEARANCE_CAP = 96.0


def clearance_transform(blocked: bytearray, obstacles, cols: int, rows: int,
                        cell: int, origin) -> array:
    """The clearance array for a `cols` x `rows` lattice of `cell` px whose
    top-left is `origin`; blocked cells stay 0."""
    step = float(cell)
    diag = step * _SQRT2
    big = CLEARANCE_CAP
    d = array("f", bytes(4 * cols * rows))
    for i in range(cols * rows):
        d[i] = 0.0 if blocked[i] else big

    for row in range(rows):
        base = row * cols
        up = base - cols
        for col in range(cols):
            i = base + col
            if blocked[i]:
                continue
            best = d[i]
            if col > 0:
                best = min(best, d[i - 1] + step)
            if row > 0:
                best = min(best, d[up + col] + step)
                if col > 0:
                    best = min(best, d[up + col - 1] + diag)
                if col < cols - 1:
                    best = min(best, d[up + col + 1] + diag)
            d[i] = best

    for row in range(rows - 1, -1, -1):
        base = row * cols
        dn = base + cols
        for col in range(cols - 1, -1, -1):
            i = base + col
            if blocked[i]:
                continue
            best = d[i]
            if col < cols - 1:
                best = min(best, d[i + 1] + step)
            if row < rows - 1:
                best = min(best, d[dn + col] + step)
                if col < cols - 1:
                    best = min(best, d[dn + col + 1] + diag)
                if col > 0:
                    best = min(best, d[dn + col - 1] + diag)
            d[i] = best

    # The chamfer measures centre-to-blocked-centre; the actual wall sits
    # ~half a cell nearer than the blocked cell's centre. Pull every value in
    # by that half cell so the field is conservative against room / void
    # edges (keeps `passable` from ever out-running `GameMap.is_walkable`).
    pull = step * 0.5
    for i in range(cols * rows):
        if not blocked[i]:
            v = d[i] - pull
            d[i] = v if v > 0.0 else 0.0

    ox, oy = origin
    half = cell * 0.5
    for o in obstacles:
        orad = float(o.radius)
        # a cell further than this from the centre keeps a clearance already
        # >= the cap, so the obstacle cannot lower it
        margin = orad + CLEARANCE_CAP
        c0 = max(0, int((o.pos.x - margin - ox) // cell))
        c1 = min(cols - 1, int((o.pos.x + margin - ox) // cell))
        r0 = max(0, int((o.pos.y - margin - oy) // cell))
        r1 = min(rows - 1, int((o.pos.y + margin - oy) // cell))
        for row in range(r0, r1 + 1):
            cy = oy + row * cell + half
            base = row * cols
            for col in range(c0, c1 + 1):
                i = base + col
                if blocked[i]:
                    continue
                cx = ox + col * cell + half
                edge = ((cx - o.pos.x) ** 2 + (cy - o.pos.y) ** 2) ** 0.5 - orad
                if edge < d[i]:
                    d[i] = edge if edge > 0.0 else 0.0
    return d
