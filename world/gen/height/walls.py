"""Stone: the cliff faces that hold a terrace up.

Split out of `world/gen/heightmap.py`. Two rules, and both run more than once
during a build because later stages take cells away: `_raise_walls` gives every
southward drop its face, `_face_the_sea` makes sure no raised ground is left
hanging over open water.
"""
from __future__ import annotations

from world.layout import Cell, GROUND, CLIFF, VSTAIR, EWSTAIR
from world.gen.height.const import MAX_DROP
from world.gen.height.graph import walk_links

def _raise_walls(grid) -> None:
    """Give every southward drop its cliff.

    A cap's south rim is the one face the camera sees, so the cells directly
    below it become stone. They are consumed from the terrace underneath -- the
    wall has to occupy real cells, exactly as it did when terraces were bands."""
    for (c, r), cell in sorted(grid.items(), key=lambda kv: -kv[0][1]):
        if cell.kind != GROUND:
            continue
        south = grid.get((c, r + 1))
        if south is None or south.kind != GROUND or south.level >= cell.level:
            continue
        drop = min(cell.level - south.level, MAX_DROP)
        for k in range(drop):
            below = grid.get((c, r + 1 + k))
            if below is None or below.kind != GROUND:
                break
            grid[(c, r + 1 + k)] = Cell(CLIFF, level=cell.level, drop=drop,
                                        row=k)




def _face_the_sea(grid, mask) -> None:
    """No floating ground: a terrace cell with open sea directly south grows a
    wall under it, so the plateau visibly stands on something. Capped at
    `MAX_DROP` -- a level-3 shelf over water still shows two tiles of rock."""
    for (c, r), cell in list(grid.items()):
        if cell.kind != GROUND or cell.level <= 0:
            continue
        if (c, r + 1) in grid:
            continue
        # How far it has to fall: down to whatever the beach will be, or to
        # the sea if there is no beach here.
        drop = min(cell.level, MAX_DROP)
        for k in range(drop):
            grid[(c, r + 1 + k)] = Cell(CLIFF, level=cell.level, drop=drop,
                                        row=k)


# --- connectivity ---------------------------------------------------------



def _stone_run(grid, foot):
    """The unbroken run of stone directly south of `foot`, and the ground it
    bottoms out on -- `(cells, ground_cell_or_None)`. An empty run means there
    is nothing under the foot to argue about."""
    c, r = foot
    run, rr = [], r + 1
    while True:
        below = grid.get((c, rr))
        if below is None or below.kind != CLIFF:
            break
        run.append((c, rr))
        rr += 1
    beyond = grid.get((c, rr))
    return run, (beyond if beyond is not None and beyond.kind == GROUND
                 else None)


def _foot_stone_frees(grid, foot, low) -> bool:
    """May a flight foot be put at `foot`, arriving on level `low`?

    Only where whatever stone lies below it is stone `_free_flight_feet` will
    be able to lift: none at all, or a run bottoming out on ground at `low`.
    Where the ground beyond is higher the drop is real, the face would stay
    standing under the ramp, and a staircase descending into a wall is the one
    thing these crossings must not be. That site is simply the wrong place."""
    run, beyond = _stone_run(grid, foot)
    return not run or (beyond is not None and beyond.level == low)


def _free_flight_feet(grid) -> None:
    """Take the stone back out from under a staircase's foot.

    `_raise_walls` gives every southward drop its face, and it runs long before
    any flight is cut. Carve a flight into that ground afterwards and the face
    it used to hold up is still standing -- one tile of stone directly below
    the foot, with ground at the foot's own level on the far side of it. It
    reads as a staircase descending into a wall, and it is one: the collider
    refuses the edge because stone is stone.

    Nothing is facing on it any more. A cliff cell is the wall of the ground
    directly north of it, and that cell is the staircase now, so the drop the
    stone records no longer exists. It goes back to floor at the level the foot
    arrives on -- which is the level its own south neighbour is already at, so
    the tile joins ground that is there rather than inventing a terrace.

    Only where the run bottoms out at the foot's level. Anywhere else the drop
    below it is real and the stone stays."""
    for (c, r), cell in list(grid.items()):
        if cell.kind not in (VSTAIR, EWSTAIR):
            continue
        # The asymmetry `_flight_opens` documents: a straight flight's foot is
        # row `drop - 1`, an east/west one's is `drop`.
        foot = cell.drop - 1 if cell.kind == VSTAIR else cell.drop
        if cell.row != foot:
            continue
        low = cell.level - cell.drop
        run, beyond = _stone_run(grid, (c, r))
        if not run or beyond is None or beyond.level != low:
            continue
        for p in run:
            grid[p] = Cell(GROUND, level=low)


def _wall_flight_sides(grid) -> None:
    """Put stone back beside any flight the beach opened up.

    Eroding the core to make room for the shore can take away the wall a
    flight was cut into, and the beach then fills that cell with sea-level
    ground -- leaving a staircase you could step onto sideways, halfway down.
    Anything touching a flight that is not one of its own two ends becomes
    wall again."""
    for pos, cell in list(grid.items()):
        if cell.kind not in (VSTAIR, EWSTAIR):
            continue
        ends = set(walk_links(grid, pos))
        c, r = pos
        for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            nb = grid.get(p)
            if (nb is not None and nb.kind == GROUND
                    and nb.level != cell.level and p not in ends):
                grid[p] = Cell(CLIFF, level=cell.level, drop=cell.drop,
                               row=cell.row)


