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


