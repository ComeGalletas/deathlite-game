"""LD-1..LD-5 elevation: ramp planning, staircase-unit annex, cliff carving
and the per-tile metadata pass (W1 split of world/procedural.py)."""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Stair, TileMeta
from world.gen.rooms import _four_connected
from world.gen.links import _relink_corridors


def _ramp_style(seed: int, hi_id: int, lo_id: int, hi_floor: int) -> str:
    """LD-8a: "rock" (the `vstairs.png` overlay) or "grass" (biome grass
    channel / wedge) for one cross-floor unit -- a seeded per-link roll biased
    by the plateau's floor. Pure render tag; consumes no world RNG state."""
    bias = config.RAMP_ROCK_BIAS.get(hi_floor, config.RAMP_ROCK_BIAS_DEFAULT)
    roll = random.Random(f"{seed}:ramp-style:{hi_id}:{lo_id}").random()
    return "rock" if roll < bias else "grass"


def _ramp_layout(seed: int, hi_id: int, lo_id: int) -> str:
    """LD-8 #1: "h" (the LD-4 side-landing unit -- stair column with a grass
    landing jogged one tile to each side) or "v" (a straight one-column flight)
    for one cross-floor link. Seeded per link; consumes no world RNG state."""
    roll = random.Random(f"{seed}:ramp-layout:{hi_id}:{lo_id}").random()
    return "h" if roll < config.RAMP_LANDING_BIAS else "v"


def _face_h(room) -> int:
    """Depth of the cliff band under a raised room's south rim, in tiles, when
    it drops all the way to the sea -- LD-8 #2: one tile per floor, uncapped
    (floor 3 is 3 tiles). `paint_cliff` shortens it per column where something
    is actually below (LD-2 E8)."""
    return max(1, room.floor * int(config.CLIFF_TILES))


def _drop_h(high, low) -> int:
    """LD-3 R8: the band depth between two *specific* rooms, in tiles -- the
    real floor difference (1 or 2, capped by the 2-floor connectivity rule),
    not the high room's drop to the sea."""
    return max(1, (high.floor - low.floor) * int(config.CLIFF_TILES))


def _ramp_candidates(rooms, edges):
    """Cross-floor tree edges that can carry a staircase unit: the two rooms
    share a chunk column and sit one chunk row apart, high room to the north, so
    the descent runs N->S down the plateau's south cliff band. The drop is 1 or
    2 floors (the 2-floor connectivity rule caps it). `_plan_ramps` picks the
    per-link layout (straight flight vs LD-4 side-landing unit). Yields
    `(high, low)`."""
    for a, b in edges:
        ra, rb = rooms[a], rooms[b]
        if ra.floor == rb.floor or ra.cell[0] != rb.cell[0]:
            continue
        hi, lo = (ra, rb) if ra.floor > rb.floor else (rb, ra)
        if hi.cell[1] < lo.cell[1]:          # high is north of low
            yield hi, lo


def _plan_ramps(rooms, edges, corridors, seed: int = 0) -> list:
    """LD-4 S1: place a **staircase unit** on every cross-floor pair that can
    take one. Mutates `rooms` (snaps a low room up against the plateau's cliff
    base) and re-seats every corridor; returns
    `[(high_id, low_id, col, orient, direction, style), ...]` with `col` in the
    **plateau's** tile grid, `orient` "v" (straight one-column flight) / "h"
    (LD-4 side-landing unit) from `_ramp_layout`, and `style` "grass" / "rock"
    from `_ramp_style`.

    The drop spans `(hi.floor - lo.floor) * CLIFF_TILES` band rows -- 1 tile for
    a one-floor link, 2 for a two-floor one (the 2-floor connectivity rule caps
    it). The footprint is probed 3 columns wide (`col-1..col+1`) so the cut
    reads as a clean channel; a "v" unit then walks only the centre column, an
    "h" unit jogs one column out to a landing at each end.

        row rim   :  = = = = = = = =      plateau surface
        band      :  # # # > # # #        "v": centre column only
        row below :  = = = = = = = =      low room surface

    A pair is skipped when the snap exceeds `RAMP_SNAP_TILES` per floor of drop,
    the moved rect would overlap another room, or no column offers the
    footprint. Deterministic -- the seeded rolls draw no world RNG and the edge
    order is the tree's own.
    """
    px = config.TILE_PX
    ct = max(1, int(config.CLIFF_TILES))
    snap = int(config.RAMP_SNAP_TILES) * px
    planned: list = []
    moved_any = False
    # A room may take part in at most one unit: snapping it a second time would
    # slide it out from under the unit already planned against it.
    locked: set = set()
    for hi, lo in _ramp_candidates(rooms, edges):
        if hi.id in locked or lo.id in locked:
            continue
        df = hi.floor - lo.floor
        if df not in (1, 2):               # 2-floor connectivity rule caps it
            continue
        drop = df * ct
        delta = (hi.rect.bottom + drop * px) - lo.rect.top
        if abs(delta) > snap * df:         # allow a deeper snap for a deeper drop
            continue
        seat = lo.rect.move(0, delta)
        if any(seat.colliderect(o.rect) for o in rooms
               if o.id not in (lo.id, hi.id)):
            continue

        cols_n, rows_n = hi.rect.width // px, hi.rect.height // px
        if rows_n < 2:
            continue

        orient = _ramp_layout(seed, hi.id, lo.id)

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
            # The approaches reach two tiles into each room, so those rows must
            # be real floor (two rows, not one -- a room-edge cell is within
            # 22 px of the boundary and fails the large nav class). A "v" unit
            # approaches down the centre column; an "h" unit's approaches sit
            # one column out (`col+d` on top, `col-d` at the bottom).
            hc = col if orient == "v" else col + d
            lc = col if orient == "v" else col - d
            if any((hc, rows_n - 1 - k) not in hi.cells for k in (0, 1)):
                return False
            return all((c, r) in lo.cells
                       for c in low_col(lc) for r in (0, 1))

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
        # rock is the straight `vstairs.png` sprite -- the side-landing unit
        # always renders as the biome grass wedge.
        style = ("grass" if orient == "h"
                 else _ramp_style(seed, hi.id, lo.id, hi.floor))
        planned.append((hi.id, lo.id, unit[0], orient, unit[1], style))
    if moved_any:
        _relink_corridors(rooms, corridors)
    return planned


def _ramp_steps(rooms, plan) -> list:
    """The walkable tiles of every staircase unit, as one-tile `Stair`s so
    collision, `walkable_rects` and the nav grid pick them up unchanged.

    A **vertical** unit is a straight chain of three rects in the stair column
    `col`: an approach two tiles into the plateau, the flight spanning the cliff
    band, and an approach two tiles into the low room. A **horizontal** unit
    keeps the LD-4 five-rect chain (approach / top landing at `col+d` / the 1x2
    stair / bottom landing at `col-d` / approach). The approaches exist for
    **clearance**, not looks -- without them the lenient cells stop at the room
    edge, where clearance is under the large nav class's 22 px. Consecutive
    tiles touch **orthogonally**, so nothing depends on diagonal movement -- the
    flow field refuses a diagonal step unless both orthogonal neighbours are
    open, which is what broke LD-3's diagonal chain."""
    px = config.TILE_PX
    ct = max(1, int(config.CLIFF_TILES))
    out: list = []
    for hi_id, lo_id, col, orient, direction, style in plan:
        hi = rooms[hi_id]
        y0 = hi.rect.bottom
        df = abs(hi.floor - rooms[lo_id].floor)
        band = df * ct                        # band rows the flight spans (1 or 2)

        def add(c, y, h, ax):
            out.append(Stair(lo_id, hi_id,
                             pygame.Rect(hi.rect.left + c * px, y, px, h),
                             ax, 1, df,
                             ramp=("s" if orient == "v" else direction),
                             orient=orient, style=style))

        if orient == "v":
            add(col, y0 - 2 * px, 2 * px, "v")        # approach, into the plateau
            add(col, y0, band * px, "v")              # the straight flight
            add(col, y0 + band * px, 2 * px, "v")     # approach, into the low room
        else:
            d = 1 if direction == "w" else -1
            add(col + d, y0 - 2 * px, 2 * px, "h")            # approach (plateau)
            add(col + d, y0, px, "h")                         # top landing
            add(col, y0, band * px, "h")                      # the stair piece
            add(col - d, y0 + (band - 1) * px, px, "h")       # bottom landing
            add(col - d, y0 + band * px, 2 * px, "h")         # approach (low room)
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
    for hi_id, lo_id, col, orient, direction, _style in plan:
        hi, lo = rooms[hi_id], rooms[lo_id]
        rows_hi = hi.rect.height // px
        if orient == "v":
            # The flight's own column must stay a south rim so
            # `_build_tile_meta` still tags it; the tag alone drops the rim
            # fringe there. Only the low room's landing cell is annexed.
            lc = (hi.rect.left + col * px - lo.rect.left) // px
            lo_ann.setdefault(lo_id, set()).add((lc, -1))
            continue
        d = 1 if direction == "w" else -1
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
    starts = {(hi_id, col): ("s" if orient == "v" else direction)
              for hi_id, _lo_id, col, orient, direction, _style in plan}
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
