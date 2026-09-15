"""Cutting the ways up: straight and east/west staircases through a wall,
lateral crossings on the flanks, and north flights on a plateau's back.

A wall is the level boundary and a
flight is the only hole in it, so this stage is what makes an island walkable
rather than a stack of islands. The flanks and the back have no wall, so a
crossing there is not a hole but a rim cell handed over to the stair.
"""
from __future__ import annotations

from world.layout import (Cell, GROUND, CLIFF, VSTAIR, EWSTAIR,
                          WALKABLE_KINDS)
from world.gen.height.const import (
    MAX_DROP, REGION, STAIR_SPACING, SIDE_STAIRS, SIDE_STAIRS_HIGH,
    SIDE_STAIRS_HIGH_FROM, SIDE_SPACING,
)
from world.gen.height.graph import reachable, _components
from world.gen.height.walls import _foot_stone_frees

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


def _nstair_site(grid, c, r):
    """Is `(c, r)` a rim cell on a plateau's back that a north flight could
    take? Returns the drop, or `None`.

    A north face has no wall -- `_raise_walls` only stones southward drops --
    so there is nothing to cut through. The flight is the rim cell itself,
    handed over whole::

        = = = = = =            = = = = = =
        # # # # # #     ->     # # # ^ # #
        # # # # # #            # # # # # #

    It takes nothing from the ground floor and needs no notch to already be
    there. What it needs: the cell is terrace ground, the low ground is
    directly north of it, its own terrace continues south of it and on both
    flanks (so it is part of the rim, not a spur), and the landing beyond
    the foot is somewhere a large body can stand -- the two cells beside it
    and the one north of it are that floor too, the same clearance rule the
    lateral crossings apply to theirs."""
    cell = grid.get((c, r))
    if cell is None or cell.kind != GROUND or cell.level <= 0:
        return None
    level = cell.level
    north = grid.get((c, r - 1))
    if north is None or north.kind != GROUND or north.level >= level:
        return None
    d = level - north.level
    if d > MAX_DROP:
        return None
    for p in ((c - 1, r), (c + 1, r), (c, r + 1)):
        nb = grid.get(p)
        if nb is None or nb.kind != GROUND or nb.level != level:
            return None
    low = north.level
    for p in ((c - 1, r - 1), (c + 1, r - 1), (c, r - 2)):
        nb = grid.get(p)
        if nb is None or nb.kind != GROUND or nb.level != low:
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


def _clear_above(grid, c, r) -> bool:
    """Is there nothing standing on top of a crossing that would start at
    `(c, r)`?

    Everything else about siting one reasons east/west -- the terrace it is
    entered from on one side, the floor it descends to on the other -- and the
    unit is two cells tall. Without this a crossing could be cut directly
    beneath a southward cliff face: the stone lands on the head, and the one
    edge meant to be the way in from the north is a wall. The wall is right;
    it is the crossing that is in the wrong place, so the site is refused and
    the shuffle takes another candidate off the same face."""
    over = grid.get((c, r - 1))
    return over is None or over.kind != CLIFF


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
    if not _clear_above(grid, c, r):
        return None
    # And the stone under the foot has to be stone that can be given back.
    # `_free_flight_feet` lifts the leftover face a crossing is cut in front
    # of, but only where it bottoms out on the floor the foot arrives at; where
    # the ground below is higher, the wall would stay standing under the ramp.
    if not _foot_stone_frees(grid, (c, r + 1), low):
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


def _cut(grid, c, r, kind, tag, d, dir="s") -> bool:
    """Hand the cells of one flight over to it. A wall-cut straight flight
    spans its `d` cells of stone, an east/west one a row more (the jog), and
    a north flight is the single rim cell it was found at.

    A north cut is **provisional**, like a lateral one: the rim cell was
    terrace ground, and a flight links only at its two ends, so where the
    rim is the only thing joining a strip of terrace to the rest -- a thin
    band of level 1 pinched between the low ground and a higher cap, say --
    taking the cell severs that strip. The prune would then delete it, and
    the flight would be left with no flank on that side. The cut is kept
    only if both flanks still reach the terrace south of the flight by some
    other way; returns whether it stood."""
    if kind == VSTAIR and dir == "n":
        was = grid[(c, r)]
        grid[(c, r)] = Cell(VSTAIR, level=was.level, drop=d, row=0,
                            tag=tag, dir="n")
        keep = reachable(grid, (c, r + 1))
        if (c - 1, r) in keep and (c + 1, r) in keep:
            return True
        grid[(c, r)] = was
        return False
    span = d if kind == VSTAIR else d + 1
    for k in range(span):
        grid[(c, r + k)] = Cell(kind, level=grid[(c, r)].level,
                                drop=d, row=k, tag=tag)
    return True


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
    its own crossings.

    The north rim has no wall and so no candidate here; `_cut_north_flights`
    serves it, in its own pass and off a restored stream, so that its draws
    never move anything this pass or the stages after it decide."""
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
            _cut(grid, c, r, kind, tag, d)
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
        _cut(grid, c, r, VSTAIR, rng.choice(("grass", "rock")), d)


def _cut_north_flights(grid, rng, per_region: int = 1, region: int = None,
                       spacing: int = None) -> None:
    """A north flight on the back of every plateau, and one more wherever a
    cap is still stranded.

    Placed by region, spacing and quota exactly as `_cut_flights` places the
    wall-cut and east/west flights, against the crossings already standing,
    so a region of the north rim -- which has no wall and so never had a
    candidate -- gets its own way up. Then the stranded caps: any part not
    joined to the rest is given a north flight where its rim cell and the
    low ground north of it lie in different parts, as `_link_levels` does
    with wall sites.

    Runs after every other flight is cut and **off a restored stream**, like
    the lateral crossings, because it draws once per candidate cell and the
    stages after it -- the prune, the hole fill, the corridor seating outside
    `build_grid`, the village -- would otherwise see a different stream purely
    because north flights exist. That is not a formality: with the draws
    left in, seed 42's village lost its hall and its pen to a layout the tidy
    pass could not save, and nothing about it had a staircase in it."""
    region = REGION if region is None else region
    spacing = STAIR_SPACING if spacing is None else spacing
    taken = [p for p, cl in grid.items()
             if cl.kind in (VSTAIR, EWSTAIR) and cl.row == 0]
    buckets: dict = {}
    for (c, r), cell in list(grid.items()):
        if cell.kind != GROUND:
            continue
        d = _nstair_site(grid, c, r)
        if d:
            buckets.setdefault((c // region, r // region), []).append((c, r, d))
    for key in sorted(buckets):
        here = buckets[key]
        rng.shuffle(here)
        cut = 0
        for c, r, d in here:
            if cut >= per_region:
                break
            if any(abs(c - tc) < spacing and abs(r - tr) < spacing
                   for tc, tr in taken):
                continue
            # An earlier cut in this pass may have spent this site's landing.
            if _nstair_site(grid, c, r) != d:
                continue
            if not _cut(grid, c, r, VSTAIR, rng.choice(("grass", "rock")), d,
                        "n"):
                continue
            taken.append((c, r))
            cut += 1

    for _ in range(16):
        parts = _components(grid)
        if len(parts) <= 1:
            return
        owner = {p: i for i, part in enumerate(parts) for p in part}
        cuts = [(c, r, d) for (c, r), cell in grid.items()
                if cell.kind == GROUND
                and (d := _nstair_site(grid, c, r))
                and owner.get((c, r)) != owner.get((c, r - 1))]
        if not cuts:
            return
        # One draw picks where to start; a cut that would sever its own
        # flank is rolled back, so carry on round the list from there rather
        # than spend a whole iteration on nothing.
        start = rng.randrange(len(cuts))
        tag = rng.choice(("grass", "rock"))
        for c, r, d in cuts[start:] + cuts[:start]:
            if _cut(grid, c, r, VSTAIR, tag, d, "n"):
                break
        else:
            return
