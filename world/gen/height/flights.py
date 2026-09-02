"""Cutting the ways up: straight and east/west staircases through a wall.

Split out of `world/gen/heightmap.py`. A wall is the level boundary and a
flight is the only hole in it, so this stage is what makes an island walkable
rather than a stack of islands.
"""
from __future__ import annotations

from world.layout import (Cell, GROUND, CLIFF, VSTAIR, EWSTAIR,
                          WALKABLE_KINDS)
from world.gen.height.const import (
    MAX_DROP, MIN_TERRACE_ROWS, REGION, STAIR_SPACING,
    SIDE_STAIRS, SIDE_STAIRS_HIGH, SIDE_STAIRS_HIGH_FROM, SIDE_SPACING,
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




# A lateral crossing carries this tag prefix, so the step rules and the painter
# can tell it from a wall-cut flight without re-deriving the geometry: it stands
# on a bare boundary with no stone behind it, and it opens east/west.
LATERAL = "side_"


def _lateral_site(grid, c, r, side):
    """The upper level a two-tile crossing at `(c, r)` would join, or `None`.

    A plateau's east and west boundary is a bare level change -- `_raise_walls`
    only stones southward drops -- so there is nothing here to cut through. The
    crossing is two cells of the boundary handed over to the ramp, and it comes
    in two alignments. `=` is terrace, `>` the stair:

        notched into the terrace          protruding from its side
            = = =                             = = =
            = = >                             = = = >
            = = =                             = = =

    They look different and test the same. Whichever pair of cells the unit
    takes, one step against the drop has to be the upper terrace and one step
    with it the lower; the alignment is just *which* of those two terraces the
    cells themselves came from. Notched cells were upper terrace, so the
    terrace closes over the stair again above and below it; protruding cells
    were lower terrace, so nothing stands over it.

    That difference is what decides the backdrop at paint time -- a notch has a
    terrace tile directly above it and needs its wall drawn, a protrusion has
    nothing to draw. See `grid_paint`.

    **Both** rows are required either way: the ramp is a two-tile unit and each
    half needs a face beside it to connect to.
    """
    dc = 1 if side == "e" else -1          # the direction the ground drops
    top, bot = grid.get((c, r)), grid.get((c, r + 1))
    if top is None or bot is None:
        return None
    if top.kind != GROUND or bot.kind != GROUND or top.level != bot.level:
        return None
    # one step against the drop: the terrace it is entered from
    up, up2 = grid.get((c - dc, r)), grid.get((c - dc, r + 1))
    if up is None or up.kind != GROUND:
        return None
    level = up.level
    if up2 is None or up2.kind != GROUND or up2.level != level:
        return None
    low = level - 1
    # one step with the drop: the floor it descends to
    for rr in (r, r + 1):
        d = grid.get((c + dc, rr))
        if d is None or d.kind != GROUND or d.level != low:
            return None
    # the cells taken must belong to one of those two terraces and no other
    if top.level not in (level, low):
        return None
    # The landing has to be somewhere you can actually stand. A crossing whose
    # foot drops into a one-cell pocket of lower terrace is walkable for a
    # small enemy and sealed for a large one: the coarse navigation class uses
    # 48 px cells against 64 px tiles, and a pocket like that measures 15.9 px
    # of clearance against the 22 it needs.
    foot = (c + dc, r + 1)
    for nb in ((foot[0] + dc, foot[1]), (foot[0], foot[1] - 1),
               (foot[0], foot[1] + 1)):
        cell = grid.get(nb)
        if cell is None or cell.kind != GROUND or cell.level != low:
            return None
    return level


def _cut_lateral_stairs(grid, rng, spacing: int = None) -> None:
    """Two or three crossings on each side face of every plateau.

    The scanner in `_cut_flights` can only find sites where stone already is,
    which is the south rim and nowhere else. This puts the same `EWSTAIR` --
    same cells, same art, same step rules -- on the bare east and west faces,
    which is the only way onto a plateau from its sides.

    Every cut is provisional: it is rolled back unless the room is still one
    connected piece afterwards, since handing two cells of a rim to a stair can
    sever a terrace as easily as open one.
    """
    spacing = SIDE_SPACING if spacing is None else spacing
    levels = sorted({cl.level for cl in grid.values() if cl.kind == GROUND},
                    reverse=True)
    walkable = {p for p, cl in grid.items() if cl.kind in WALKABLE_KINDS}
    taken = [p for p, cl in grid.items()
             if cl.kind in (VSTAIR, EWSTAIR) and cl.row == 0]

    for level in levels:
        if level <= 0:
            continue
        want = (SIDE_STAIRS_HIGH if level >= SIDE_STAIRS_HIGH_FROM
                else SIDE_STAIRS)
        for side in ("w", "e"):
            quota = rng.randint(*want)
            if quota <= 0:
                continue
            # Every ground cell of *either* terrace is a candidate, not only
            # those on this one: a protruding crossing is cut from the lower
            # terrace, and `_lateral_site` is what says which plateau a pair
            # actually joins. Shuffling them together is what mixes the two
            # alignments, off the room's own seeded stream.
            here = [(c, r) for (c, r), cl in grid.items()
                    if cl.kind == GROUND and cl.level in (level, level - 1)]
            rng.shuffle(here)
            cut = 0
            for c, r in here:
                if cut >= quota:
                    break
                if any(abs(c - tc) < spacing and abs(r - tr) < spacing
                       for tc, tr in taken):
                    continue
                if _lateral_site(grid, c, r, side) != level:
                    continue
                undo = [((c, r + k), grid[(c, r + k)]) for k in range(2)]
                for k in range(2):
                    grid[(c, r + k)] = Cell(EWSTAIR, level=level, drop=1,
                                            row=k, tag=LATERAL + side)
                now = {p for p, cl in grid.items() if cl.kind in WALKABLE_KINDS}
                if len(reachable(grid)) < len(now):
                    for p, cell in undo:
                        grid[p] = cell
                    continue
                walkable = now
                taken.append((c, r))
                cut += 1


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
