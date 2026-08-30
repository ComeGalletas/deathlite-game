"""LD-1..LD-5 elevation: ramp planning, staircase-unit annex, cliff carving
and the per-tile metadata pass (W1 split of world/procedural.py)."""
from __future__ import annotations

import pygame

from game import config
from world.layout import Stair, TileMeta
from world.gen.rooms import _four_connected
from world.gen.links import _relink_corridors


def _face_h(room) -> int:
    """Depth of the cliff band under a raised room's south rim, in tiles, when
    it drops all the way to the sea. `paint_cliff` shortens it per column where
    something is actually below (LD-2 E8)."""
    return max(1, min(room.floor, 2) * int(config.CLIFF_TILES))


def _drop_h(high, low) -> int:
    """LD-3 R8: the band depth between two *specific* rooms, in tiles -- the
    real floor difference, not the high room's drop to the sea.

    `_face_h` answers "how deep is this plateau's face over water", which is
    what the renderer needs where the rim overhangs nothing. Between a floor-2
    plateau and a floor-1 room the actual step is one floor, so a run there is
    2 tiles, not 4. Using `_face_h` for the snap put the low room twice as far
    down as the elevation says and made the run twice as long."""
    return max(1, min(high.floor - low.floor, 2) * int(config.CLIFF_TILES))


def _ramp_candidates(rooms, edges):
    """Cross-floor tree edges that could carry a sideways ramp run: the two
    cells vertically adjacent, and the **high room to the north** so its south
    cliff band faces the low room. Yields `(high, low)`."""
    for a, b in edges:
        ra, rb = rooms[a], rooms[b]
        if ra.floor == rb.floor or ra.cell[0] != rb.cell[0]:
            continue
        hi, lo = (ra, rb) if ra.floor > rb.floor else (rb, ra)
        if hi.cell[1] < lo.cell[1]:          # high is north of low
            yield hi, lo


def _plan_ramps(rooms, edges, corridors) -> list:
    """LD-4 S1: place a **staircase unit** on every cross-floor pair that can
    take one. Mutates `rooms` (snaps a low room up against the plateau's cliff
    base) and re-seats every corridor; returns
    `[(high_id, low_id, col, direction), ...]` with `col` in the **plateau's**
    tile grid.

    A unit is 3 tiles wide and 2 tall, cut into the band (`#` cliff, `=` ground,
    `>` the 1x2 stair piece)::

        row rim   :  = = = = = = = =      plateau surface
        band row 0:  # # # # > = # #      stair top    + top landing at c+d
        band row 1:  # # # = > # # #      bottom landing at c-d + stair bottom
        row below :  = = = = = = = =      low room surface

    `d` is +1 descending west (the high side is east), -1 descending east.

    **One-floor changes only** (decision 2, option c): the drop is exactly
    `CLIFF_TILES` band rows, so one piece spans it. Deeper links keep their
    plank bridge -- stacking units is understood but needs the band depth
    reworked first.

    A pair is skipped when the snap exceeds `config.RAMP_SNAP_TILES`, the moved
    rect would overlap another room, or no column offers the full footprint:
    three consecutive columns inside the x-overlap, plateau floor above the top
    landing, and low-room floor below the bottom landing. Deterministic -- no
    RNG draw, and the edge order is the tree's own.
    """
    px = config.TILE_PX
    cap = int(config.RAMP_SNAP_TILES) * px
    drop = max(1, int(config.CLIFF_TILES))
    planned: list = []
    moved_any = False
    # A room may take part in at most one unit: snapping it a second time would
    # slide it out from under the unit already planned against it.
    locked: set = set()
    for hi, lo in _ramp_candidates(rooms, edges):
        if hi.id in locked or lo.id in locked:
            continue
        if hi.floor - lo.floor != 1:        # option (c): one floor at a time
            continue
        delta = (hi.rect.bottom + drop * px) - lo.rect.top
        if abs(delta) > cap:
            continue
        seat = lo.rect.move(0, delta)
        if any(seat.colliderect(o.rect) for o in rooms
               if o.id not in (lo.id, hi.id)):
            continue

        cols_n, rows_n = hi.rect.width // px, hi.rect.height // px
        if rows_n < 2:
            continue

        def spans(col: int) -> bool:
            """That plateau column's whole tile sits inside the low room's
            span, and it is a south-rim column so there is band to cut."""
            return (hi.rect.left + col * px >= seat.left
                    and hi.rect.left + (col + 1) * px <= seat.right
                    and _is_south_rim(hi.cells, col, rows_n - 1))

        def low_col(col: int):
            """The low room's columns under a plateau column -- the two grids
            are offset, so a 64 px tile can straddle two of them."""
            x0 = hi.rect.left + col * px
            return range((x0 - seat.left) // px,
                         (x0 + px - 1 - seat.left) // px + 1)

        def fits(col: int, d: int) -> bool:
            if not all(spans(col + o) for o in (-1, 0, 1)):
                return False
            # You step onto the top landing from the plateau directly above it
            # and off the bottom landing into the low room directly below --
            # and the unit's *approach* reaches two tiles into each room, so
            # both of those rows have to be real floor. Two rows, not one,
            # because of clearance: a room-edge cell is within 22 px of the
            # boundary and so fails the large nav class, which would leave the
            # unit reachable only by the small one.
            if any((col + d, rows_n - 1 - k) not in hi.cells for k in (0, 1)):
                return False
            return all((c, r) in lo.cells
                       for c in low_col(col - d) for r in (0, 1))

        unit = None
        for direction, d in (("w", 1), ("e", -1)):
            for col in sorted(range(1, cols_n - 1),
                              reverse=(direction == "w")):
                if fits(col, d):
                    unit = (col, direction)
                    break
            if unit is not None:
                break
        if unit is None:
            continue

        lo.rect = seat
        moved_any = True
        locked.update((hi.id, lo.id))
        planned.append((hi.id, lo.id, unit[0], unit[1]))
    if moved_any:
        _relink_corridors(rooms, corridors)
    return planned


def _ramp_steps(rooms, plan) -> list:
    """The walkable tiles of every staircase unit, as one-tile `Stair`s so
    collision, `walkable_rects` and the nav grid pick them up unchanged.

    Five rects: an approach reaching two tiles into the plateau, the top
    landing, the 1x2 stair piece, the bottom landing, and an approach two tiles
    into the low room. The approaches exist for **clearance**, not looks --
    without them the lenient cells stop at the room edge, where clearance is
    under the large nav class's 22 px, so only the small class could reach the
    unit. LD-1 solved the same problem by spanning plank stairs centre-to-centre.
    Consecutive tiles touch **orthogonally** (landing beside stair, stair beside
    landing, and each landing directly under / over its room), so none of this
    depends on diagonal movement -- the flow field refuses a diagonal step
    unless both orthogonal neighbours are open, which is what broke LD-3's
    diagonal chain."""
    px = config.TILE_PX
    out: list = []
    for hi_id, lo_id, col, direction in plan:
        hi = rooms[hi_id]
        d = 1 if direction == "w" else -1
        y0 = hi.rect.bottom
        df = abs(hi.floor - rooms[lo_id].floor)

        def add(c, y, h):
            out.append(Stair(lo_id, hi_id,
                             pygame.Rect(hi.rect.left + c * px, y, px, h),
                             "h", 1, df, ramp=direction))

        add(col + d, y0 - 2 * px, 2 * px)     # approach, into the plateau
        add(col + d, y0, px)                  # top landing
        add(col, y0, 2 * px)                  # the stair piece
        add(col - d, y0 + px, px)             # bottom landing
        add(col - d, y0 + 2 * px, 2 * px)     # approach, into the low room
    return out


def _collect_annex(rooms, plan) -> None:
    """LD-5 fix (b): mark each staircase-unit landing as an **annex** cell of
    the room it belongs to, room-relative, so `_build_tile_meta` and the
    renderer's autotiler fold it into the room's shape -- the plateau rim cell
    above a top landing stops being a south rim, and the low room's edge cell
    below a bottom landing drops its foam. Gated on `config.STRUCT_ANNEX`;
    empty otherwise, so `Room.annex` stays `frozenset()` and nothing changes."""
    if not config.STRUCT_ANNEX:
        return
    px = config.TILE_PX
    hi_ann: dict = {}
    lo_ann: dict = {}
    for hi_id, lo_id, col, direction in plan:
        hi, lo = rooms[hi_id], rooms[lo_id]
        d = 1 if direction == "w" else -1
        rows_hi = hi.rect.height // px
        # top landing: high room's grid, band row 0 == room-relative row `rows`
        hi_ann.setdefault(hi_id, set()).add((col + d, rows_hi))
        # bottom landing: low room's grid, band row 1 == room-relative row -1
        lc = (hi.rect.left + (col - d) * px - lo.rect.left) // px
        lo_ann.setdefault(lo_id, set()).add((lc, -1))
    for rid, cells in {**hi_ann, **lo_ann}.items():
        merged = hi_ann.get(rid, set()) | lo_ann.get(rid, set())
        rooms[rid].annex = frozenset(merged)


def _carve_cliffs(rooms, corridors, stairs) -> None:
    """Turn every raised room into a mesa: pull its walkable cell mask in by
    `CLIFF_TILES` along each edge that has **no** link attached (those become the
    non-walkable cliff band). A `CLIFF_TILES`-deep throat is kept in front of
    every corridor / stair mouth so the room stays reachable. Skips a room where
    the carve would break 4-connectivity or drop it below the min cell count --
    pathing is still correct there (the rim already borders void), it just will
    not show an inset cliff."""
    px = config.TILE_PX
    ct = max(1, int(config.CLIFF_TILES))

    keep_by_room: dict = {}
    for link in (*corridors, *stairs):
        a = getattr(link, "a", getattr(link, "low_room", -1))
        b = getattr(link, "b", getattr(link, "high_room", -1))
        for rid in (a, b):
            rr = rooms[rid].rect
            m = link.rect.clip(rr)
            if m.width <= 0 or m.height <= 0:
                continue
            w, h = rooms[rid].tile_dims
            c0 = max(0, int((m.left - rr.left) // px))
            c1 = min(w - 1, int((m.right - 1 - rr.left) // px))
            r0 = max(0, int((m.top - rr.top) // px))
            r1 = min(h - 1, int((m.bottom - 1 - rr.top) // px))
            keep = keep_by_room.setdefault(rid, set())
            for cc in range(c0, c1 + 1):
                for rr_ in range(r0, r1 + 1):
                    xs = (range(cc, cc + ct + 1) if cc < ct
                          else range(cc - ct, cc + 1) if cc >= w - ct else (cc,))
                    ys = (range(rr_, rr_ + ct + 1) if rr_ < ct
                          else range(rr_ - ct, rr_ + 1) if rr_ >= h - ct else (rr_,))
                    for x in xs:
                        for y in ys:
                            keep.add((x, y))

    for room in rooms:
        if room.floor <= 0:
            continue
        w, h = room.tile_dims
        # Skip the rim inset on a room too small to keep a comfortable core --
        # pathing is already correct (the rim borders void, the stair is the
        # link); it just will not carry an inset cliff face.
        if min(w, h) < 2 * ct + 4:
            continue
        keep = keep_by_room.get(room.id, set())
        trial = {c for c in room.cells
                 if (ct <= c[0] < w - ct and ct <= c[1] < h - ct) or c in keep}
        if len(trial) >= _MIN_ROOM_CELLS and _four_connected(trial):
            room.cells = frozenset(trial)


# --- LD-2 E0: per-tile metadata -------------------------------------------
def _is_south_rim(cells: frozenset, col: int, row: int) -> bool:
    """A cell with no floor cell directly below it -- the lip of a cliff."""
    return (col, row) in cells and (col, row + 1) not in cells


def _cliff_variant(cells: frozenset, col: int, row: int) -> str:
    """Pick the face tile for a south-rim cell by what abuts the cliff on each
    side, not just whether the neighbour is itself a rim.

    A side is **closed** -- takes the seamless solid `mid`-style edge -- when
    the neighbouring column has floor at the rim row: it either continues the
    rim run, or the plateau's own grass sits against the face there (an L /
    stepped edge where the land wraps south). A side is **open** -- takes the
    rounded run-end edge with a transparent outer margin -- only when it faces
    the void. So `left` / `right` mark a real drop-off end; `mid` covers both a
    run interior and a rim cell butting up against solid land; `single` is a
    true 1-wide overlook with void on both sides."""
    left = (col - 1, row) in cells
    right = (col + 1, row) in cells
    if left and right:
        return "mid"
    if right:
        return "left"
    if left:
        return "right"
    return "single"


def _build_tile_meta(rooms, plan=()) -> None:
    """Fill every room's `tile_meta` (one `TileMeta` per `Room.cells` entry).
    Pure, deterministic, no RNG. A flat room -> `floor 0 / foam True / cliff ""`
    for every cell. `plan` is the LD-3 ramp plan, whose entries tag the one rim
    cell each run starts at."""
    starts = {(hi_id, col): direction
              for hi_id, _lo_id, col, direction in plan}
    for room in rooms:
        cells = room.cells
        # LD-5: a landing in the cliff band counts as floor for edge
        # derivation -- so a rim cell with a landing below it is no longer a
        # south rim, and an `n`/`e`/`w` lip next to a landing closes up.
        shape = cells | room.annex
        f = room.floor
        raised = f > 0
        meta: dict = {}
        for (col, row) in cells:
            cliff = cvar = ""
            lip = ""
            if raised:
                if _is_south_rim(shape, col, row):
                    cliff = "top"
                    cvar = _cliff_variant(shape, col, row)
                lip = "".join(
                    d for d, exposed in (
                        ("n", (col, row - 1) not in shape),
                        ("e", (col + 1, row) not in shape),
                        ("w", (col - 1, row) not in shape))
                    if exposed)
            # LD-3: the rim cell a ramp run starts at. Only ever the run's
            # first column, and only on a south-rim cell -- `_plan_ramps`
            # already required that, so this just tags it.
            ramp = starts.get((room.id, col), "") if cliff == "top" else ""
            meta[(col, row)] = TileMeta(
                floor=f, surface="room", foam=(f == 0),
                cliff=cliff, cliff_var=cvar, lip=lip, room_id=room.id,
                ramp=ramp)
        room.tile_meta = meta
