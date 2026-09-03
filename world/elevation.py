"""One flat lookup of *what elevation is here*, for the whole world.

The height-map grids already know every cell's level and kind, but they are
per-room and room-relative, and `WorldLayout.tile_at` answers a single point by
scanning every room. That is fine for a bake and far too slow for the collider
and the flow field, which ask thousands of times a frame. `LevelIndex`
rasterises the whole world once into flat arrays keyed by absolute tile, so a
lookup is an index computation and an array read.

It is deliberately the *only* place the runtime learns an elevation, so the
collider, the navigation grid and the projectile rule cannot drift apart the
way three separate readings of the same grids would. The rules that read it
-- may a body step from this tile to that one -- are `world/rules/steps.py`.

What it holds, per tile:

    level   the floor this tile's surface is on, or `NONE` where nothing
            walkable stands -- a cliff face, a lake, open sea, the void
    kind    `GROUND`, `VSTAIR`, `EWSTAIR`, or `NOTHING`
    top     the elevation of whatever terrain stands here, walkable or not:
            a cliff face reports the terrace it holds up, a lake its own
            surface. `NONE` only over the void. This is what the projectile
            rule needs and `level` cannot answer -- a shot fired up at a
            plateau has to die against the *face*, and a face has no walkable
            level at all, so testing `level` alone would let it through the
            wall and kill it on the rim above.

Flights need more than a level to answer "may I step from here to there" -- the
rule turns on which end of the flight a cell is and which way it faces -- so
their `Cell` records are kept verbatim in a small dict beside the arrays. There
are only a few hundred flight cells in a world against tens of thousands of
tiles, so this costs nothing and keeps the step rule (`world/rules/steps.py`)
able to mirror `walk_links` exactly rather than approximate it.

**This answers elevation, not walkability.** `GameMap._point_ok` remains the
authority on whether a point is floor, and callers must keep asking it: a
bridge rect is not tile-aligned along its length, so an absolute-tile raster
cannot reproduce the floor test exactly at a bridge mouth.

Every island rect is tile-aligned (generation snaps them), which is what lets
a room-relative `(col, row)` map to one absolute tile. `_add_grid` checks
rather than assumes, so a future change to room placement fails loudly
instead of silently mis-levelling the world.
"""
from __future__ import annotations

from array import array

from game import config
from world.layout import GROUND, VSTAIR, EWSTAIR, VOID, WALKABLE_KINDS

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
            self._add_grid(room)
        # A bridge is a sea-level walkway that belongs to no room grid. It only
        # ever lands on level-0 ground, so recording it flat is exact.
        for c in layout.corridors:
            self._add_rect(c.rect)

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
            raise ValueError(f"room {room.id} rect {tuple(room.rect)} is off "
                             f"the tile lattice; see the module doc")
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
