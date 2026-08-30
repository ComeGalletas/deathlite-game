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


def mask_slot(cells: frozenset, col: int, row: int, slots: dict) -> int:
    """Autotile a floor cell by which of its 4 orthogonal neighbours are also
    floor (a 4-bit mask). Concave (inner) corners and 1-wide spines fall back
    to `interior` -- the sheet has only the 8 rectangle slots (W3)."""
    gap_n = (col, row - 1) not in cells
    gap_s = (col, row + 1) not in cells
    gap_w = (col - 1, row) not in cells
    gap_e = (col + 1, row) not in cells
    gaps = gap_n + gap_s + gap_w + gap_e
    if gaps == 0:
        return slots["interior"]
    if gaps == 1:
        return slots["edge_n" if gap_n else "edge_s" if gap_s
                     else "edge_w" if gap_w else "edge_e"]
    if gaps == 2:
        if gap_n and gap_w:
            return slots["corner_nw"]
        if gap_n and gap_e:
            return slots["corner_ne"]
        if gap_s and gap_w:
            return slots["corner_sw"]
        if gap_s and gap_e:
            return slots["corner_se"]
    return slots["interior"]           # opposite pair / nub -> best effort


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
