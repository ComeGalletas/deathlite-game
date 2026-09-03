"""Water inside the island: lakes, and the holes that are not lakes.

Both halves answer the same rule -- any
inland water is at least three contiguous tiles on one terrace -- from opposite
directions: `_carve_lakes` makes water and refuses to make it too small,
`_fill_holes` finds water the other stages left behind and closes it.
"""
from __future__ import annotations

from world.layout import Cell, GROUND, CLIFF, LAKE, WALKABLE_KINDS
from world.gen.height.const import MAX_DROP, _NB
from world.gen.height.graph import reachable

# A lake must be at least this many tiles, contiguous and all on one terrace.
# Below it the water does not read as a lake at all: at this scale a lone tile
# surrounded by ground is a puddle, and the terrain's own shoreline fringe
# overdraws most of it. Three is the smallest shape that still reads -- a line
# or an L, the distribution does not matter.
_LAKE_MIN = 3

def _trim_lake_stubs(blob: set) -> set:
    """Drop single-tile arms from a lake.

    The size floor alone does not get what it is aimed at. A blob of a dozen
    cells routinely grows one-tile spurs off its rim, and a spur reads exactly
    like the one-tile pond the floor exists to forbid -- worse, really, because
    the ground's shore fringe eats most of it and what survives is a lone
    speck hanging off the shoreline.

    Leaves are peeled repeatedly, not once: taking a two-tile arm off exposes
    its base as a new leaf, and a single pass leaves that behind. The loop stops
    the moment another peel would drop the lake under `_LAKE_MIN`, which is what
    lets a bare line or L of three through -- every cell of those is a leaf, so
    a rule of "no leaves" would forbid exactly the shapes the brief allows.

    A long thin snake therefore erodes down to three tiles rather than being
    kept at length. That is the right trade: a one-tile-wide channel is a ditch,
    not a lake, and it suffers the same fringe overdraw as a spur.
    """
    while True:
        if len(blob) <= _LAKE_MIN:
            return blob
        stubs = {p for p in blob
                 if sum(1 for dx, dy in _NB
                        if (p[0] + dx, p[1] + dy) in blob) < 2}
        # Leaves cannot be cut points, so what is left is still connected.
        if not stubs or len(blob) - len(stubs) < _LAKE_MIN:
            return blob
        blob = blob - stubs


# A hole in an island smaller than a lake is allowed to be. The three-tile
# minimum the lakes carry (`_LAKE_MIN`) applies to *any* inland water, and the
# offenders were never lakes: measured over ten worlds, 43 one-tile and 156
# two-tile near-enclosed holes, and 199 of 205 were cells absent from the grid
# altogether -- open sea bitten in by `_carve_bays` and the coast walk, or left
# behind when `_prune_unreachable` took the ground around them away.
_HOLE_MIN = _LAKE_MIN

# How much land a hole has to be surrounded by before it counts as inland rather
# than as a bay still open to the sea. Three of four sides: a two-tile hole in a
# straight coast has two land sides and stays a bay, which is what we want.
_HOLE_ENCLOSED = 3




def _water_blobs(grid, limit: int):
    """Connected runs of cells **absent from the grid** inside the island's own
    bounding box, up to `limit` cells. Larger ones are the open sea and are not
    this pass's business, so the walk abandons them early.

    A `LAKE` counts as present, not as water to be closed. Lakes already have
    their own minimum and their own stub trim, and treating them as fillable
    was actively wrong: the bounding box was taken over non-lake cells only, so
    a lake straddling its edge had the outside half invisible to the walk and
    the inside half eaten as a two-tile hole. Measured on seed 0, a four-cell
    lake came out of this pass as two."""
    present = set(grid)
    if not present:
        return
    cs = [p[0] for p in present]
    rs = [p[1] for p in present]
    box = ((min(cs), max(cs)), (min(rs), max(rs)))
    holes = {(c, r)
             for c in range(box[0][0], box[0][1] + 1)
             for r in range(box[1][0], box[1][1] + 1)
             if (c, r) not in present}
    seen: set = set()
    for p in holes:
        if p in seen:
            continue
        stack, comp = [p], set()
        seen.add(p)
        too_big = False
        while stack:
            q = stack.pop()
            comp.add(q)
            if len(comp) > limit:
                too_big = True
                break
            for dx, dy in _NB:
                n = (q[0] + dx, q[1] + dy)
                if n in holes and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if not too_big:
            yield comp, present




def _fill_holes(grid) -> None:
    """Close every inland hole too small to read as water.

    The brief offered two ways out -- widen the hole to three tiles, or fill it
    with terrain that does not interrupt pathing. Filling wins outright, and
    widening is not implemented, for two reasons found while building it:

    * a hole with mixed neighbour levels sits at a **cliff foot**, and widening
      it there produces exactly the shape `_carve_lakes` already refuses --
      water lapping a wall, which the terrace boundary has no shoreline art for;
    * widening *removes* walkable ground and so has to be guarded against
      cutting the room in two, while filling only ever adds.

    So every hole is closed with terrain, and which terrain depends on one
    thing: whether the ground directly **north** of it is higher.

    * **Higher to the north** -- the hole is under a terrace, so it becomes part
      of that terrace's wall: a `CLIFF` at the north neighbour's level. Nothing
      else moves. The cell was never walkable, so reachability cannot change.
    * **Otherwise** -- ground at the *lowest* neighbouring level. A lateral step
      up to a taller terrace east or west needs no face; that edge is drawn from
      the raised block, and only a southward drop needs stone.

    Neither branch consumes walkable ground, so no connectivity check is needed
    and none is done.
    """
    for comp, present in list(_water_blobs(grid, _HOLE_MIN - 1)):
        sides = [(q[0] + dx, q[1] + dy) for q in comp for dx, dy in _NB]
        touching = [grid[n] for n in sides if n in present]
        if len(touching) < _HOLE_ENCLOSED:
            continue                            # still open to the sea: a bay
        solid = [c for c in touching if c.kind != LAKE]
        if not solid:
            # A gap in the middle of a pond. Closing it with ground would put a
            # one-tile island in the water; it is simply more of the pond.
            for q in comp:
                grid[q] = Cell(LAKE, level=touching[0].level)
            continue
        low = min(c.level for c in solid)
        for q in sorted(comp):
            north = grid.get((q[0], q[1] - 1))
            if (north is not None and north.kind in (GROUND, CLIFF)
                    and north.level > low):
                drop = min(north.level - low, MAX_DROP)
                grid[q] = Cell(CLIFF, level=north.level, drop=drop, row=0)
            else:
                grid[q] = Cell(GROUND, level=low)




def _carve_lakes(grid, rng, count: int, size=(4, 14)) -> None:
    """Flood a few blobs of a terrace to make inland lakes.

    `size` is the range of accretion steps a blob is grown for -- each step
    picks a cell already in the blob and tries one of its neighbours, so the
    shape wanders and comes out ragged rather than round, and a wider range
    gives both bigger pools and more variety between them. Fewer cells than
    steps survive, since a step onto another terrace or off the map does
    nothing.

    A lake is only cut where it stays wholly inside one terrace and leaves the
    room connected -- water that walls a shelf off would be indistinguishable
    from a generation bug, and water lapping a cliff foot would need shoreline
    art the terrace boundary does not have.

    It must also be at least `_LAKE_MIN` contiguous tiles with no single-tile
    arms; see `_trim_lake_stubs`. Accretion only ever steps onto ground of the
    seed cell's own level, so contiguity and one-terrace-ness hold by
    construction and the check below is a floor, not a filter."""
    ground = [p for p, cell in grid.items() if cell.kind == GROUND]
    if not ground:
        return
    for _ in range(count):
        seed = ground[rng.randrange(len(ground))]
        level = grid[seed].level
        blob = {seed}
        for _ in range(rng.randint(*size)):
            c, r = list(blob)[rng.randrange(len(blob))]
            nb = rng.choice(((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)))
            cell = grid.get(nb)
            if cell is not None and cell.kind == GROUND and cell.level == level:
                blob.add(nb)
        blob = _trim_lake_stubs(blob)
        if len(blob) < _LAKE_MIN:
            continue
        # never let a lake touch anything but its own terrace's ground
        edge = {(c + dx, r + dy) for c, r in blob
                for dx, dy in _NB} - blob
        if any(grid.get(p) is not None
               and (grid[p].kind != GROUND or grid[p].level != level)
               for p in edge):
            continue
        saved = {p: grid[p] for p in blob}
        for p in blob:
            grid[p] = Cell(LAKE, level=level)
        if len(reachable(grid)) != sum(
                1 for cell in grid.values() if cell.kind in WALKABLE_KINDS):
            grid.update(saved)               # it cut the room in two; put it back


