"""Cutting the ways up: straight and east/west staircases through a wall.

Split out of `world/gen/heightmap.py`. A wall is the level boundary and a
flight is the only hole in it, so this stage is what makes an island walkable
rather than a stack of islands.
"""
from __future__ import annotations

from world.layout import Cell, GROUND, CLIFF, VSTAIR, EWSTAIR
from world.gen.height.const import (
    MAX_DROP, MIN_TERRACE_ROWS, REGION, STAIR_SPACING,
)
from world.gen.height.graph import reachable, _components
from world.gen.height.walls import _raise_walls

def _vstair_site(grid, c, r):
    """Is `(c, r)` the head of a straight flight? Needs solid wall in its own
    column and in both neighbours for the whole descent, terrace above and
    terrace below. Returns the drop, or `None`."""
    top = grid.get((c, r))
    if top is None or top.kind != CLIFF or top.row != 0:
        return None
    d = top.drop
    above, under = grid.get((c, r - 1)), grid.get((c, r + d))
    if above is None or above.kind != GROUND or above.level != top.level:
        return None
    if under is None or under.kind != GROUND or under.level != top.level - d:
        return None
    for k in range(d):
        for dx in (-1, 0, 1):
            nb = grid.get((c + dx, r + k))
            if nb is None or nb.kind != CLIFF:
                return None
    return d




def _ewstair_site(grid, c, r, side):
    """Is `(c, r)` the head of an east/west flight descending `side`?

    This wants the one-row jog the journal's diagram calls for::

        # > =        the wall has dropped on the exit side but not the entry
        = > #        ... and a row later, the other way round

    So the wall beside the flight starts a row earlier on the exit side than on
    the entry side, the upper terrace reaches the head from the entry side, and
    the lower terrace meets the foot from the exit side.

    The flight spans one row more than the wall is deep, so it eats a cell of
    terrace on the way past -- that is the jog, and it is why this cannot
    simply be a column of wall like a straight flight."""
    entry = 1 if side == "w" else -1
    d = None
    near = grid.get((c - entry, r))                 # exit side, wall starts here
    far = grid.get((c + entry, r + 1))              # entry side, a row later
    for w in (near, far):
        if w is None or w.kind != CLIFF or w.row != 0:
            return None
        d = w.drop if d is None else d
        if w.drop != d:
            return None
    head = grid.get((c + entry, r))                 # step on from up here
    foot = grid.get((c - entry, r + d))             # ... and off down there
    if head is None or head.kind != GROUND or head.level != near.level:
        return None
    if foot is None or foot.kind != GROUND or foot.level != near.level - d:
        return None
    above = grid.get((c, r - 1))
    if above is None or above.kind != GROUND or above.level != near.level:
        return None
    # the flight's own column must be free to take -- wall, or the terrace cell
    # the jog eats, but never another flight
    for k in range(d + 1):
        cell = grid.get((c, r + k))
        if cell is None or cell.kind not in (CLIFF, GROUND):
            return None
    return d




def _cut_flights(grid, rng, per_region: int, region: int = None,
                 spacing: int = None) -> None:
    """Cut ways up through the walls, using all four kinds of stair the tileset
    has: a straight flight in stone or in grass, and the east/west grass flight
    in either direction.

    Sites are *found* in the finished grid rather than forced into it -- with
    concentric caps there is no row of wall to plan against, and scanning means
    a site is valid by construction.

    Placement is then spread over a coarse grid of **regions** rather than
    drawn from one shuffled pile. A flat island-wide quota gets spent wherever
    the shuffle happens to fall, which on a large island reliably leaves whole
    stretches of rim -- the north especially, where the caps are widest --
    without a way up. A per-region quota guarantees every part of the coast has
    its own crossings."""
    region = REGION if region is None else region
    spacing = STAIR_SPACING if spacing is None else spacing
    buckets: dict = {}
    for (c, r), cell in list(grid.items()):
        if cell.kind not in (CLIFF, GROUND):
            continue
        found = []
        if cell.kind == CLIFF and cell.row == 0:
            d = _vstair_site(grid, c, r)
            if d:
                found.append((VSTAIR, rng.choice(("grass", "rock")), d))
        for side in ("w", "e"):
            d = _ewstair_site(grid, c, r, side)
            if d:
                found.append((EWSTAIR, side, d))
        if found:
            kind, tag, d = found[rng.randrange(len(found))]
            buckets.setdefault((c // region, r // region), []).append(
                (c, r, kind, tag, d))

    taken: list = []
    for key in sorted(buckets):
        here = buckets[key]
        rng.shuffle(here)
        cut = 0
        for c, r, kind, tag, d in here:
            if cut >= per_region:
                break
            if any(abs(c - tc) < spacing and abs(r - tr) < spacing
                   for tc, tr in taken):
                continue
            span = d if kind == VSTAIR else d + 1
            for k in range(span):
                grid[(c, r + k)] = Cell(kind, level=grid[(c, r)].level,
                                        drop=d, row=k, tag=tag)
            taken.append((c, r))
            cut += 1




def _link_levels(grid, rng) -> None:
    """Keep cutting flights until every plateau is reachable.

    `_cut_flights` places for looks, spreading crossings out; this places for
    need, so a cap whose only stair fell inside a lake or got roughened away is
    not left stranded."""
    for _ in range(16):
        parts = _components(grid)
        if len(parts) <= 1:
            return
        owner = {p: i for i, part in enumerate(parts) for p in part}
        cuts = []
        for (c, r), cell in grid.items():
            if cell.kind != CLIFF or cell.row != 0:
                continue
            d = _vstair_site(grid, c, r)
            if not d:
                continue
            if owner.get((c, r - 1)) == owner.get((c, r + d)):
                continue
            cuts.append((c, r, d))
        if not cuts:
            return
        c, r, d = cuts[rng.randrange(len(cuts))]
        tag = rng.choice(("grass", "rock"))
        for k in range(d):
            grid[(c, r + k)] = Cell(VSTAIR, level=grid[(c, r)].level,
                                    drop=d, row=k, tag=tag)
