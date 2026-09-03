"""`NavGrid`: the static navigation lattice over a finished `WorldLayout`.

* `walkable[i]` -- 1 if the cell centre is on an island cell or inside a
  bridge rect *and* far enough inside its terrace for a body to stand
  (`world/rules/floor.py` is the authority; the mask is rasterised from the
  floor outward and checked against the point test in the tests).
* `corridor[i]` -- 1 if that walkable cell centre is on a bridge or a flight,
  the narrow links that get clearance leniency so the big, rare enemies can
  still thread them.
* `clearance[i]` -- world-pixel distance to the nearest wall or obstacle edge
  (`world/nav/clearance.py`).
* `level[i]`, `flight[i]`, `step_mask[i]` -- the terrain's elevation per cell
  and the baked mask of which neighbour moves it allows, a cache of the rules
  in `world/rules/steps.py`.

Pure and deterministic: the same layout + obstacles + cell size always produce
an identical grid. Built once per run; never touched per frame.
"""
from __future__ import annotations

import math
from array import array

import pygame

from game import config
from world.elevation import LevelIndex, NONE
from world.nav.clearance import clearance_transform
from world.rules import floor as floor_rules
from world.rules import inset as terrain_inset
from world.rules.steps import can_cross, diagonal_blocked

# The canonical neighbour order. `FlowField._NEI` and `NavGrid.step_mask` are
# both built from it, so bit *i* of a cell's mask is always the move in
# `NAV_DIRS[i]` and the two cannot drift apart.
NAV_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1))
_TILE_BIT = {d: 1 << i for i, d in enumerate(NAV_DIRS)}
_ORTH = ((1, 0), (-1, 0), (0, 1), (0, -1))



# The floor and margin tests are `world/rules/floor.py`'s -- one body, read
# by the collider too. These names stay for the callers and tests that grew
# up with them.
_point_on_floor = floor_rules.point_on_floor
_point_inset_ok = floor_rules.inset_ok
_point_in_corridor = floor_rules.in_corridor


class NavGrid:
    """Immutable navigation lattice over `layout.bounds` at `cell` px resolution."""

    def __init__(self, layout, obstacles=None, cell: int = 32) -> None:
        if cell <= 0:
            raise ValueError("cell size must be positive")
        b = layout.bounds
        self.layout = layout
        self.cell = int(cell)
        self.origin = (float(b.left), float(b.top))
        self.cols = max(1, -(-int(b.width) // self.cell))     # ceil division
        self.rows = max(1, -(-int(b.height) // self.cell))
        n = self.cols * self.rows

        obstacles = list(obstacles if obstacles is not None
                         else getattr(layout, "obstacles", ()))

        walkable = bytearray(n)
        corridor = bytearray(n)
        blocked = bytearray(n)       # geometry-only source for the wall chamfer

        # The terrace margin, baked in here rather than asked per step. The
        # collider refuses a body's centre within `margin` px of a level
        # change, so a field that still routed through those cells would send
        # an enemy at a boundary the collider will not let it cross, and it
        # would grind against the corner for ever. Same class of bug as
        # `walk_links` disagreeing with `_flight_opens`; same fix, which is
        # that both sides read one authority.
        margin = terrain_inset.body_inset()

        # Rasterised from the floor *outward* -- each island cell and each
        # bridge rect marks the nav cells whose centres it holds -- rather
        # than asking `_point_on_floor` for every one of the ~50 k cell
        # centres against every island. Same answer, cell for cell:
        # `test_pathfinding` and `test_mirrors` check it against the point
        # test, which stays the reference.
        floor = bytearray(n)
        owner = [None] * n           # the island whose cell holds the centre
        on_bridge = bytearray(n)
        for room in layout.rooms:
            self._mark_cells(room, floor, owner)
        for c in layout.corridors:
            self._mark_rect(c.rect, floor, on_bridge)

        ox, oy = self.origin
        half = self.cell * 0.5
        cols = self.cols
        for i in range(n):
            if not floor[i]:
                blocked[i] = 1
                continue
            room = owner[i]
            if room is not None and margin > 0.0:
                cx = ox + (i % cols) * self.cell + half
                cy = oy + (i // cols) * self.cell + half
                if terrain_inset.world_at(room, cx, cy) < margin:
                    # Not walkable, and deliberately not `blocked` either:
                    # `blocked` seeds the wall chamfer, and treating a
                    # margin as stone would shrink the clearance of every
                    # cell near a rim -- which is exactly what stops the
                    # 48 px class threading a one-tile neck.
                    continue
            walkable[i] = 1
            if on_bridge[i]:
                corridor[i] = 1

        self.walkable = walkable
        self.corridor = corridor
        self.clearance = self._clearance_transform(blocked, obstacles)
        self.levels = LevelIndex(layout)
        self.level, self.flight, self.step_mask = self._elevation(walkable,
                                                                  corridor)

    def _span(self, lo: float, hi: float, origin: float) -> range:
        """The lattice indices along one axis whose cell *centre* lies in
        `[lo, hi)` -- the same half-open test `Rect.collidepoint` and the
        island cell lookup apply to a point."""
        half = self.cell * 0.5
        k0 = math.ceil((lo - origin - half) / self.cell)
        k1 = math.ceil((hi - origin - half) / self.cell)      # exclusive
        return range(max(0, k0), k1)

    def _mark_cells(self, room, floor: bytearray, owner: list) -> None:
        """Every nav cell whose centre falls in one of `room.cells`."""
        px = config.TILE_PX
        rx, ry = room.rect.left, room.rect.top
        ox, oy = self.origin
        cols, rows = self.cols, self.rows
        for col, row in room.cells:
            x0 = rx + col * px
            y0 = ry + row * px
            for r in self._span(y0, y0 + px, oy):
                if r >= rows:
                    break
                base = r * cols
                for c in self._span(x0, x0 + px, ox):
                    if c >= cols:
                        break
                    i = base + c
                    floor[i] = 1
                    if owner[i] is None:
                        owner[i] = room

    def _mark_rect(self, rect, floor: bytearray, flag: bytearray) -> None:
        """Every nav cell whose centre falls inside `rect`."""
        ox, oy = self.origin
        cols, rows = self.cols, self.rows
        for r in self._span(rect.top, rect.bottom, oy):
            if r >= rows:
                break
            base = r * cols
            for c in self._span(rect.left, rect.right, ox):
                if c >= cols:
                    break
                floor[base + c] = 1
                flag[base + c] = 1

    def _elevation(self, walkable: bytearray, corridor: bytearray):
        """Per-cell elevation, and the baked mask of which neighbour moves the
        terrain allows.

        Asking `can_step` inside `FlowField.rebuild` was measured at ~300 ns a
        call, which is ~24 ms of rebuild on a full world -- far too much for a
        field that repaths as the player moves. The geometry is static, so the
        answer is baked here once instead: bit *i* of `step_mask[cell]` is set
        when moving in `NAV_DIRS[i]` is legal, and the rebuild loop reads one
        byte and ANDs it.

        Two lattices are in play -- nav cells are 32 px, terrain tiles 64 px --
        so the work is done per *tile* first (a quarter as many, and only those
        with a surface) and projected onto the cells. Two nav cells inside one
        tile are always connected: a tile has a single elevation.

        Flight cells are also marked `corridor`, which is what gives them the
        clearance leniency. A flight is one tile wide with stone either
        side; without it the 48 px nav class cannot thread one, exactly the
        case that leniency exists for."""
        ix = self.levels
        n = self.cols * self.rows
        level = array("b", [NONE]) * n
        flight = bytearray(n)
        mask = bytearray(n)
        ox, oy = self.origin
        half = self.cell * 0.5
        tcols = ix.cols

        # Per cell: the *linear* index of the tile it sits in, -1 where the cell
        # is not floor. Linear rather than (col, row) so the neighbour test below
        # is integer arithmetic instead of tuple building.
        tile = array("i", [-1]) * n
        live = []
        for row in range(self.rows):
            base = row * self.cols
            cy = oy + row * self.cell + half
            for col in range(self.cols):
                i = base + col
                if not walkable[i]:
                    continue
                tc, tr = ix.tile_of(ox + col * self.cell + half, cy)
                tile[i] = tr * tcols + tc
                live.append(i)
                level[i] = ix.level_at(tc, tr)
                if ix.flight_at(tc, tr) is not None:
                    flight[i] = 1
                    corridor[i] = 1

        # Per tile, once: which of the eight moves the terrain allows.
        #
        # In two passes, because a diagonal is defined as its two right-angle
        # detours and asking `can_step` for it re-derives orthogonal answers we
        # already have. Doing the four orthogonals first and reading the
        # diagonals off those bits cuts the rule evaluations by half and the
        # diagonal ones to pure bit tests -- measured at a third of the build
        # time this pass used to take.
        seen = set(tile[i] for i in live)
        orth: dict = {}
        for tl in seen:
            tc, tr = tl % tcols, tl // tcols
            m = 0
            for k, (dc, dr) in enumerate(_ORTH):
                if can_cross(ix, (tc, tr), (tc + dc, tr + dr)):
                    m |= 1 << k
            orth[tl] = m

        tmask: dict = {}
        for tl in seen:
            om = orth[tl]
            tc, tr = tl % tcols, tl // tcols
            m = 0
            for d, bit in _TILE_BIT.items():
                dc, dr = d
                if not (dc and dr):
                    if om & (1 << _ORTH.index(d)):
                        m |= bit
                    continue
                # Same endpoint rule the collider applies before it looks at
                # any detour: two ground tiles of different levels are never
                # one move apart. Without it here the field would route an
                # enemy diagonally past a lateral crossing that the collider
                # then refuses to let it through, and it would push against the
                # corner for ever.
                if diagonal_blocked(ix, (tc, tr), (tc + dc, tr + dr)):
                    continue
                h = tl + dc                       # step east/west first, ...
                v = tl + dr * tcols               # ... or north/south first
                if ((om & (1 << _ORTH.index((dc, 0)))
                     and orth.get(h, 0) & (1 << _ORTH.index((0, dr))))
                        or (om & (1 << _ORTH.index((0, dr)))
                            and orth.get(v, 0) & (1 << _ORTH.index((dc, 0))))):
                    m |= bit
            tmask[tl] = m

        # Project onto cells. Two cells inside one tile are always connected --
        # a tile has a single elevation -- so only a tile *change* consults the
        # mask, keyed by the linear delta between the two tiles.
        by_delta = {0: -1}                       # -1 marks "same tile, always ok"
        for (dc, dr), bit in _TILE_BIT.items():
            by_delta[dr * tcols + dc] = bit
        cols = self.cols
        rows = self.rows
        for i in live:
            tl = tile[i]
            tm = tmask[tl]
            col = i % cols
            row = i // cols
            m = 0
            for k, (dc, dr) in enumerate(NAV_DIRS):
                ncol = col + dc
                if ncol < 0 or ncol >= cols:
                    continue
                nrow = row + dr
                if nrow < 0 or nrow >= rows:
                    continue
                ntl = tile[nrow * cols + ncol]
                if ntl < 0:
                    continue
                bit = by_delta.get(ntl - tl)
                if bit == -1 or (bit is not None and (tm & bit)):
                    m |= 1 << k
            mask[i] = m
        return level, flight, mask

    # --- build helpers -------------------------------------------------
    def _clearance_transform(self, blocked: bytearray, obstacles) -> array:
        """See `world/nav/clearance.py`."""
        return clearance_transform(blocked, obstacles, self.cols, self.rows,
                                   self.cell, self.origin)

    # --- coordinates -------------------------------------------------
    def in_bounds(self, col: int, row: int) -> bool:
        return 0 <= col < self.cols and 0 <= row < self.rows

    def idx(self, col: int, row: int) -> int:
        return row * self.cols + col

    def cell_of(self, wx: float, wy: float) -> tuple[int, int]:
        return (int((wx - self.origin[0]) // self.cell),
                int((wy - self.origin[1]) // self.cell))

    def world_of(self, col: int, row: int) -> pygame.Vector2:
        return pygame.Vector2(self.origin[0] + (col + 0.5) * self.cell,
                              self.origin[1] + (row + 0.5) * self.cell)

    # --- queries -------------------------------------------------
    def is_floor(self, col: int, row: int) -> bool:
        return self.in_bounds(col, row) and bool(self.walkable[self.idx(col, row)])

    def is_corridor(self, col: int, row: int) -> bool:
        return self.in_bounds(col, row) and bool(self.corridor[self.idx(col, row)])

    def clearance_at(self, col: int, row: int) -> float:
        if not self.in_bounds(col, row):
            return 0.0
        return self.clearance[self.idx(col, row)]

    def passable(self, col: int, row: int, radius: float = 0.0) -> bool:
        """Walkable and wide enough for an enemy of `radius`. Corridor leniency
        is applied by the caller, not here."""
        if not self.in_bounds(col, row):
            return False
        i = self.idx(col, row)
        return bool(self.walkable[i]) and self.clearance[i] >= radius

    def passable_world(self, wx: float, wy: float, radius: float = 0.0) -> bool:
        return self.passable(*self.cell_of(wx, wy), radius)
