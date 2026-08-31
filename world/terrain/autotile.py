"""Pure autotile slot maths -- pick a tile index from a cell's neighbourhood.

W3 of `journals/world_refactor.md`. Moved verbatim off `GameMap`; it holds
`GameMap._slot_for` / `_mask_slot` / `_bridge_slot` as `staticmethod` aliases so
existing call sites and `tests/rendering/test_terrain.py` keep working. No
pygame, no assets -- just ints, strings and a `slots` dict.
"""
from __future__ import annotations


def slot_for(slots: dict, row: int, col: int, rows: int, cols: int) -> int:
    """Rectangular-room autotile: pick the slot from the cell's position in the
    room's bounding grid (currently unused -- `mask_slot` superseded it)."""
    n, s = row == 0, row == rows - 1
    w, e = col == 0, col == cols - 1
    if n and w:
        return slots["corner_nw"]
    if n and e:
        return slots["corner_ne"]
    if s and w:
        return slots["corner_sw"]
    if s and e:
        return slots["corner_se"]
    if n:
        return slots["edge_n"]
    if s:
        return slots["edge_s"]
    if w:
        return slots["edge_w"]
    if e:
        return slots["edge_e"]
    return slots["interior"]


# The ground block's twelve slot names, keyed by which sides are open. The
# eight rectangle slots cover a cell with 0-2 *adjacent* open sides; the strips
# and the single cover the rest -- `strip_v` is a north-south channel (open west
# and east) as [top, mid, bottom], `strip_h` an east-west one as [west, mid,
# east], and `single` is open on all four. Together they are a complete
# sixteen-combination autotile, which earlier code did not use: it fell back to
# `interior` for opposite pairs and 3-gap nubs, so a one-wide spine of ground,
# or a cell pinched between a lake and a cliff, painted as a flat square with no
# fringe at all.
_GROUND_SLOT = {
    "":     ("interior", 0),
    "n":    ("edge_n", 0),   "s":  ("edge_s", 0),
    "w":    ("edge_w", 0),   "e":  ("edge_e", 0),
    "nw":   ("corner_nw", 0), "ne": ("corner_ne", 0),
    "sw":   ("corner_sw", 0), "se": ("corner_se", 0),
    "we":   ("strip_v", 1),  "ns":  ("strip_h", 1),
    "nwe":  ("strip_v", 0),  "swe": ("strip_v", 2),
    "nsw":  ("strip_h", 0),  "nse": ("strip_h", 2),
    "nswe": ("single", 0),
}


def _slot(slots: dict, name: str, index: int) -> int:
    """One slot by name. A strip is authored as a [start, mid, end] list; the
    rectangle slots are bare ints. Missing art falls back to `interior`."""
    v = slots.get(name)
    if isinstance(v, (list, tuple)):
        return int(v[index]) if index < len(v) else int(v[-1])
    if v is None:
        return int(slots.get("interior", 0))
    return int(v)


def ground_slot(slots: dict, sides: str) -> int:
    """The ground tile fringed on exactly `sides` (a subset of "nswe", in that
    order). Every one of the sixteen combinations has authored art."""
    return _slot(slots, *_GROUND_SLOT[sides])


def mask_slot(cells: frozenset, col: int, row: int, slots: dict) -> int:
    """`ground_slot` for callers whose floor is just a set of cells -- a side is
    open where the neighbour is not in it."""
    return ground_slot(slots, "".join(
        d for d, dx, dy in (("n", 0, -1), ("s", 0, 1),
                            ("w", -1, 0), ("e", 1, 0))
        if (col + dx, row + dy) not in cells))


def bridge_slot(axis: str, index: int, ncells: int) -> str:
    """The bridge tile for cell `index` of an `ncells`-long run. The corridor
    `axis` ('h' | 'v') fixes the tile family; the two ends get the matching
    cap (`Corridor.end_low` -> `h_left` / `v_top`, `end_high` -> `h_right` /
    `v_bot`), everything between gets `mid` (see data/terrain.json 'bridge')."""
    low, mid, high = (("h_left", "h_mid", "h_right") if axis == "h"
                      else ("v_top", "v_mid", "v_bot"))
    if ncells <= 1:
        return mid
    if index == 0:
        return low
    if index == ncells - 1:
        return high
    return mid
