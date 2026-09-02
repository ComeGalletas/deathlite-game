"""LD-9: build a room's **height map** -- the per-cell grid that replaces the
old "one `floor` integer plus a cliff band hanging off the south rim" model.

A room is a stack of terraces running north to south, highest at the top, each
separated from the next by a wall of cliff tiles. The walls are the level
boundary and the only way through them is a stair, so the drop reads as real
verticality even though the game is top-down (see the level-design journal).

The grid this emits is the machine form of the ASCII layouts in the journal::

    = = = = = =      terrace, level 2
    # # 0 # # #      the wall, with a straight flight cut through it
    = = = = = =      terrace, level 1
    # # # # > =      ... and an east/west flight, which jogs the wall one row
    = = = = = #
    = = = = = =      terrace, level 0

Invariants every grid satisfies (asserted by `check_grid`):

* the whole boundary between two levels is cliff, except where a stair crosses;
* adjacent levels differ by at most 2, so level 0 never touches level 3;
* no floating ground -- a ground cell above sea level always has ground or
  cliff directly south of it;
* a stair touches ground of another level only at its two ends;
* every walkable cell is reachable from every other one.

Rendering reads the grid and nothing else.

Split into stages under `world/gen/height/` -- this module is the pipeline and
the package's public face. Everything that imported `world.gen.heightmap` still
works: that module is now a shim re-exporting these names.
"""
from __future__ import annotations

from world.layout import Cell, GROUND
from world.gen.height.const import (            # noqa: F401  (re-exported)
    MIN_TERRACE_ROWS, MAX_LEVEL, MAX_DROP, CAP_INSET_S, CAP_INSET_N,
    CAP_INSET_W, CAP_INSET_E, CAP_ROUGHNESS, MIN_CAP_CELLS, REGION,
    STAIR_SPACING, CANYONS, CANYON_DEPTH, CANYON_WIDTH, _NB,
)
from world.gen.height.coast import (            # noqa: F401
    coast_shape, coast_mask, _coast_once, _carve_bays, _one_piece, _walk,
    _despike,
)
from world.gen.height.terraces import _all_neighbours_in, _cap, _carve_canyons
from world.gen.height.walls import (
    _raise_walls, _face_the_sea, _wall_flight_sides,
    _free_flight_feet,
)
from world.gen.height.flights import (          # noqa: F401
    _vstair_site, _ewstair_site, _cut_flights, _cut_lateral_stairs, _link_levels,
)
from world.gen.height.water import (            # noqa: F401
    _trim_lake_stubs, _water_blobs, _fill_holes, _carve_lakes,
)
from world.gen.height.graph import (            # noqa: F401
    walk_links, reachable, _components, _prune_unreachable, check_grid,
    to_ascii,
)


def build_grid(mask: frozenset, cols: int, rows: int, rng, base: int = 0,
               stairs_per_wall: int = 1, lakes: int = 0, lake_size=(4, 14),
               top: int = MAX_LEVEL, shore: int = 1, tiers: int = MAX_LEVEL,
               cap_inset=None, cap_roughness: float = None,
               cap_min_cells: int = None, region: int = None,
               spacing: int = None, canyons: int = None,
               canyon_depth=None, canyon_width=None,
               **_legacy) -> dict:
    """The height map for one island: a **mountain**, not a staircase.

    The whole island is sea-level ground. On top of it sits a smaller,
    irregular plateau, and on top of that a smaller one again -- concentric
    caps, each eroded in from the one below and pushed toward the island's
    north side. Seen from the south that stacks into a slope of rims; the
    north side is the high back of the mountain. `tiers` caps how many caps are
    attempted, `top` how high they may reach.

    Only the **south** face of a cap becomes a cliff, because that is the only
    face the camera sees. East and west show the plateau's flank and north its
    back, both of which the `slots.raised` edge tile already draws -- so this
    needs no art beyond what the tileset has.

    The sea-level ring around the outside is never built on. That keeps a
    walkable shore all the way round, which is what lets a bridge always find a
    mouth (bridges only ever meet sea level).

    `**_legacy` swallows the row-band tuning that the previous terracing took;
    it has no meaning for concentric caps."""
    grid = {p: Cell(GROUND, level=base) for p in mask}

    ring = max(1, shore)
    room = mask
    for _ in range(ring):
        room = frozenset(p for p in room if _all_neighbours_in(p, room))

    floor_cells = MIN_CAP_CELLS if cap_min_cells is None else cap_min_cells
    current = room
    for level in range(base + 1, min(top, base + tiers) + 1):
        cap = _cap(current, rng, cap_inset, cap_roughness)
        if len(cap) < floor_cells:
            break
        cap = _carve_canyons(cap, rng, canyons, canyon_depth, canyon_width)
        if len(cap) < floor_cells:
            break
        for p in cap:
            grid[p] = Cell(GROUND, level=level)
        current = cap

    _raise_walls(grid)
    _face_the_sea(grid, mask)
    for p in mask:                       # anything the walls consumed is beach
        if p not in grid:
            grid[p] = Cell(GROUND, level=base)
    _cut_flights(grid, rng, stairs_per_wall, region, spacing)
    _wall_flight_sides(grid)
    if lakes:
        _carve_lakes(grid, rng, lakes, lake_size)
    # After the lakes, not before: a lake accretes over ground of its own
    # terrace, and four crossings in six worlds had their foot's landing eaten
    # out from under them that way -- a stair that looks like a way down and
    # is not.
    #
    # The stream is put back exactly as it was found. This pass draws from it
    # like any other, but every stage below -- `_link_levels`, the prune, the
    # hole fill, and the corridor seating outside this function -- would
    # otherwise see a different stream purely because side stairs exist, and
    # start producing different coastlines and bridges. Two `test_repair`
    # failures came from precisely that, neither of them anything to do with a
    # staircase. `floor_palette` guards the same way, for the same reason.
    state = rng.getstate()
    _cut_lateral_stairs(grid, rng)
    rng.setstate(state)
    # Every flight is cut by now, so this is the first moment the leftover
    # faces can all be seen at once. It draws nothing from the stream.
    _free_flight_feet(grid)
    _link_levels(grid, rng)
    _prune_unreachable(grid)
    # LD-10: last, because every stage above can leave a one-tile hole behind --
    # a bay bitten in by the coast walk, a pocket the prune emptied.
    _fill_holes(grid)
    # Once more at the end: carving lakes and pruning stranded pockets both
    # take cells away, and any of them may have been the ground a plateau was
    # standing on. Re-facing here is what keeps the "no floating ground" rule
    # true of the grid that actually ships, not just the one mid-build.
    #
    # It also has to run *after* `_fill_holes`, and that is not a formality:
    # 73 of the 156 measured holes have their south side open, so nearly half
    # the fills put new ground over open sea with no face beneath it.
    _face_the_sea(grid, mask)
    return grid


