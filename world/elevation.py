"""LD-9 phase D0: one flat lookup of *what elevation is here*, for the whole world.

The height-map grids already know every cell's level and kind, but they are
per-room and room-relative, and `WorldLayout.tile_at` answers a single point by
scanning every room. That is fine for a bake and far too slow for the collider
and the flow field, which ask thousands of times a frame. `LevelIndex`
rasterises the whole world once into flat arrays keyed by absolute tile, so a
lookup is an index computation and an array read.

It is deliberately the *only* place the runtime learns an elevation, so the
collider (D2), the navigation grid (D3) and the projectile rule cannot drift
apart the way three separate readings of the same grids would.

What it holds, per tile:

    level   the floor this tile's surface is on, or `NONE` where nothing
            walkable stands -- a cliff face, a lake, open sea, the void
    kind    `GROUND`, `VSTAIR`, `EWSTAIR`, or `NOTHING`
    top     the elevation of whatever terrain stands here, walkable or not:
            a cliff face reports the terrace it holds up, a lake its own
            surface. `NONE` only over the void. This is what the projectile
            rule (D10) needs and `level` cannot answer -- a shot fired up at a
            plateau has to die against the *face*, and a face has no walkable
            level at all, so testing `level` alone would let it through the
            wall and kill it on the rim above.

Flights need more than a level to answer "may I step from here to there" -- the
rule turns on which end of the flight a cell is and which way it faces -- so
their `Cell` records are kept verbatim in a small dict beside the arrays. There
are only a few hundred flight cells in a world against tens of thousands of
tiles, so this costs nothing and keeps the adjacency rule (D1) able to mirror
`heightmap.walk_links` exactly rather than approximate it.

**This answers elevation, not walkability.** `GameMap._point_ok` remains the
authority on whether a point is floor, and callers must keep asking it. The
distinction is not pedantic: a room rect is tile-*sized* but only tile-*aligned*
under the height-map generator. With `config.HEIGHTMAP_ROOMS` off, rooms sit at
arbitrary sub-tile offsets -- measured at (8, 40), (24, 56), (40, 8) and so on
in one sample world -- so a single absolute tile straddles two room cells and no
absolute-tile raster can reproduce `_point_ok` exactly. Sampled over 4,000
random points with the flag off, treating this index as a floor test disagreed
with `_point_ok` on 219 of them.

That costs nothing, because with the flag off every surface here is recorded as
ground at level 0, so every elevation query says "same floor" and nothing
downstream changes behaviour. The index is safe to build and consult
unconditionally; it is simply never a substitute for the floor test.

A grid room whose rect is *not* tile-aligned would put its cells at the wrong
absolute tiles, so `_add_grid` checks and falls back to flat rather than
recording an elevation it cannot place. Under the height-map generator every
room rect is aligned (verified: offset (0, 0) for every room), so the fallback
never fires today -- it is there so a future change to room placement fails
safe instead of silently mis-levelling the world.
"""
from __future__ import annotations

from array import array

from game import config
from world.layout import GROUND, VSTAIR, EWSTAIR, VOID, WALKABLE_KINDS

_FLIGHTS = (VSTAIR, EWSTAIR)

# `level` sentinel for a tile with no walkable surface. Stored in a signed byte
# array, so it has to be a real value rather than None.
NONE = -128

NOTHING = ""


class LevelIndex:
    """Absolute-tile elevation lookup over `layout.bounds`.

    Pure and deterministic: the same layout always produces the same index.
    Built once per run alongside the nav grid; never touched per frame."""

    __slots__ = ("px", "origin", "cols", "rows", "_level", "_kind", "_top",
                 "_flight")

    def __init__(self, layout) -> None:
        px = self.px = int(config.TILE_PX)
        b = layout.bounds
        # Snap the origin down to the world tile lattice. Room rects are
        # tile-aligned under the height-map generator, so this keeps a room's
        # own (col, row) a fixed offset from the index's -- no rounding drift
        # between the two coordinate systems.
        ox = (int(b.left) // px) * px
        oy = (int(b.top) // px) * px
        self.origin = (ox, oy)
        self.cols = max(1, -(-(int(b.right) - ox) // px))      # ceil division
        self.rows = max(1, -(-(int(b.bottom) - oy) // px))
        n = self.cols * self.rows

        self._level = array("b", [NONE]) * n
        self._kind: list = [NOTHING] * n
        self._top = array("b", [NONE]) * n
        self._flight: dict = {}

        for room in layout.rooms:
            if room.grid:
                self._add_grid(room)
            else:
                self._add_flat(room)
        # A bridge and an LD-8 stair strip are sea-level walkways that belong to
        # no room grid. Bridges only ever land on level-0 ground (the corridor
        # rule), so recording them flat is exact rather than an approximation.
        for c in layout.corridors:
            self._add_rect(c.rect)
        for s in getattr(layout, "stairs", ()):
            self._add_rect(s.rect)

    # --- build -------------------------------------------------------
    def _put(self, col: int, row: int, level: int, kind: str) -> None:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            i = row * self.cols + col
            self._level[i] = level
            self._kind[i] = kind
            self._top[i] = level

    def _put_top(self, col: int, row: int, level: int) -> None:
        """Terrain that stands here but cannot be walked on -- a cliff face, a
        lake. Recorded for the projectile rule only; `level` and `kind` stay
        untouched, so nothing that asks about walking sees any difference."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self._top[row * self.cols + col] = level

    def _room_offset(self, room) -> tuple[int, int]:
        ox, oy = self.origin
        return ((int(room.rect.left) - ox) // self.px,
                (int(room.rect.top) - oy) // self.px)

    def _aligned(self, room) -> bool:
        """Does this room's rect sit on the world tile lattice? Only then does
        a room-relative (col, row) map to an absolute tile without drift."""
        return (int(room.rect.left) % self.px == 0
                and int(room.rect.top) % self.px == 0)

    def _add_grid(self, room) -> None:
        if not self._aligned(room):
            self._add_flat(room)       # cannot place its cells; see module doc
            return
        c0, r0 = self._room_offset(room)
        for (col, row), cell in room.grid.items():
            ac, ar = c0 + col, r0 + row
            if cell.kind not in WALKABLE_KINDS:
                # Not walkable, so `level` and `kind` stay NONE. A cliff or a
                # lake is still *terrain* though, and `Cell.level` is already
                # the upper surface it belongs to -- for a face, the terrace it
                # holds up -- which is exactly the height a shot has to clear.
                if cell.kind != VOID:
                    self._put_top(ac, ar, cell.level)
                continue
            self._put(ac, ar, cell.level, cell.kind)
            if cell.kind in (VSTAIR, EWSTAIR):
                self._flight[(ac, ar)] = cell

    def _add_flat(self, room) -> None:
        """A room with no height map (flag off, or a plain rectangle): every
        floor cell is ground at level 0."""
        c0, r0 = self._room_offset(room)
        cells = room.cells
        if not cells:
            w, h = room.tile_dims
            cells = ((c, r) for r in range(h) for c in range(w))
        for col, row in cells:
            self._put(c0 + col, r0 + row, 0, GROUND)

    def _add_rect(self, rect) -> None:
        ox, oy = self.origin
        px = self.px
        for row in range((int(rect.top) - oy) // px,
                         -(-(int(rect.bottom) - oy) // px)):
            for col in range((int(rect.left) - ox) // px,
                             -(-(int(rect.right) - ox) // px)):
                if 0 <= col < self.cols and 0 <= row < self.rows \
                        and self._kind[row * self.cols + col] == NOTHING:
                    self._put(col, row, 0, GROUND)

    # --- query -------------------------------------------------------
    def tile_of(self, wx: float, wy: float) -> tuple[int, int]:
        """The absolute tile a world point falls in. Floor division, so it is
        correct for negative coordinates too."""
        ox, oy = self.origin
        px = self.px
        return (int((wx - ox) // px), int((wy - oy) // px))

    def level_at(self, col: int, row: int) -> int:
        """`NONE` where nothing walkable stands."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self._level[row * self.cols + col]
        return NONE

    def kind_at(self, col: int, row: int) -> str:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self._kind[row * self.cols + col]
        return NOTHING

    def flight_at(self, col: int, row: int):
        """The flight `Cell` at this tile, or `None`. Carries the `drop`, `row`
        and `tag` the step rule needs to tell one end of a staircase from the
        other."""
        return self._flight.get((col, row))

    def level_at_point(self, wx: float, wy: float) -> int:
        col, row = self.tile_of(wx, wy)
        return self.level_at(col, row)

    def top_at(self, col: int, row: int) -> int:
        """Elevation of the terrain standing at this tile, walls included.
        `NONE` over the void, where a shot has nothing to hit."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self._top[row * self.cols + col]
        return NONE

    def top_at_point(self, wx: float, wy: float) -> int:
        col, row = self.tile_of(wx, wy)
        return self.top_at(col, row)

    def has_surface(self, col: int, row: int) -> bool:
        """Is an elevation recorded for this tile? **Not** a floor test -- see
        the module docstring. Use `GameMap._point_ok` for walkability."""
        return self.kind_at(col, row) != NOTHING


# --- D1: may a body step from one tile to the next? -------------------------
#
# `heightmap.walk_links` is the authority on this -- it is what `check_grid`
# validates every generated room against -- but it reads a room-relative grid
# and allocates the whole neighbour list per call. These mirror it against the
# `LevelIndex` instead, in world tiles and without allocating, so the collider
# (D2) and the flow field (D4) can both ask the same question thousands of
# times a frame and cannot drift from generation or from each other.
#
# Kept faithful to the original down to the asymmetry in the two flight kinds:
# a straight flight's foot is row `drop - 1`, an east/west flight's is row
# `drop`, because the jogged unit spans one row more than it descends.


def _flight_opens(index: LevelIndex, ftile, gtile) -> bool:
    """Does the flight at `ftile` open onto the ground tile `gtile`?

    A flight is not walkable from just anywhere along its length -- only its
    head joins the terrace above and only its foot the terrace below, and an
    east/west flight also reaches sideways because the wall jogs a row across
    it. Asking the flight (rather than deriving it from the ground side) is
    what keeps the relation symmetric, exactly as `walk_links` does."""
    cell = index.flight_at(*ftile)
    if cell is None:
        return False
    c, r = ftile

    def ground(p, level) -> bool:
        return (p == gtile and index.kind_at(*p) == GROUND
                and index.level_at(*p) == level)

    if cell.kind == VSTAIR:
        return ((cell.row == 0 and ground((c, r - 1), cell.level))
                or (cell.row == cell.drop - 1
                    and ground((c, r + 1), cell.level - cell.drop)))

    entry = 1 if cell.tag == "w" else -1     # "w" descends west, entered east
    low = cell.level - cell.drop
    if cell.row == 0 and (ground((c + entry, r), cell.level)
                          or ground((c, r - 1), cell.level)):
        return True
    return cell.row == cell.drop and (ground((c - entry, r), low)
                                      or ground((c, r + 1), low))


def can_cross(index: LevelIndex, a, b) -> bool:
    """May a body move from tile `a` to the orthogonally adjacent tile `b`?

    Ground joins ground of its own level; a flight joins the flight cells above
    and below it in its own stack, and joins ground only at its head and foot.
    Anything else -- a lateral level change with no stone in it, a terrace's
    back edge, the middle of a staircase -- is a wall you cannot walk through
    even though both tiles are floor.

    Non-adjacent or diagonal pairs return False. A diagonal step is the
    caller's to compose from its two orthogonal parts, which is also what stops
    a body cutting the corner of a drop."""
    if a == b:
        return True
    dc = b[0] - a[0]
    dr = b[1] - a[1]
    if abs(dc) + abs(dr) != 1:
        return False
    ka = index.kind_at(*a)
    kb = index.kind_at(*b)
    if ka == NOTHING or kb == NOTHING:
        return False
    if ka == GROUND:
        if kb == GROUND:
            return index.level_at(*a) == index.level_at(*b)
        return _flight_opens(index, b, a)
    if kb == GROUND:
        return _flight_opens(index, a, b)
    # both flights: the next cell up or down the same stack, never sideways
    return dr != 0


def can_step(index: LevelIndex, a, b) -> bool:
    """`can_cross`, plus the diagonal case composed from its orthogonal parts.

    A diagonal is open only if one of its two right-angle detours is open end
    to end. That is what stops a body slipping across the corner of a drop --
    the one place a pure per-axis test would let it through."""
    if a == b:
        return True
    dc = b[0] - a[0]
    dr = b[1] - a[1]
    if dc and dr and abs(dc) == 1 and abs(dr) == 1:
        via_h = (a[0] + dc, a[1])
        via_v = (a[0], a[1] + dr)
        return ((can_cross(index, a, via_h) and can_cross(index, via_h, b))
                or (can_cross(index, a, via_v) and can_cross(index, via_v, b)))
    return can_cross(index, a, b)
