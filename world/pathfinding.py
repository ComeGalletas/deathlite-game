"""Navigation grid + shared flow field for enemy pathfinding.

See journals/journal.md "Planned Phase -- Enemy navigation (shared flow field)".
`NavGrid` -- static grid primitive (walkable / corridor / clearance).
`FlowField` -- per-cycle bucket-queue distance field toward a target, with
`direction_at` (pure gradient) and `steer_at` (gradient, else a bearing to the
nearest reached cell so a stranded enemy is not left to beeline blindly).
`NavField` -- coordinator: one grid + field per radius class, rebuilt toward the
player; `PlayingState` owns it and `entities/enemy_ai.path_chase` / `_approach`
sample it.

`NavGrid` rasterises a finished `WorldLayout` into a fixed lattice:

* `walkable[i]`  -- 1 if the cell centre is on room floor (`Room.cells`) or inside
  a corridor rect. This is exactly the geometry `GameMap._point_ok` tests, so
  room boundaries are blocked and rooms connect only through their corridors.
* `corridor[i]` -- 1 if that walkable cell centre is inside a corridor rect (the
  only inter-room links; M3 gives these cells clearance leniency so the big,
  rare enemies can still thread a one-tile hallway).
* `clearance[i]` -- world-pixel distance from the cell centre to the nearest
  wall (two-pass chamfer transform over the blocked cells) or obstacle edge
  (exact `dist - radius` to every obstacle), whichever is closer; 0 on blocked
  cells and inside an obstacle. A cell is *passable* for an enemy of radius `r`
  iff `walkable and clearance >= r`, so obstacle avoidance uses the true
  collision radius with no per-radius rebuild. The exact obstacle term matters:
  a tree ring (22 px) is narrower than a 32 px cell and can sit entirely between
  cell centres, so a pure cell raster would miss it.

Pure and deterministic: the same layout + obstacles + cell size always produce an
identical grid. Built once per run; never touched per frame.
"""
from __future__ import annotations

from array import array

import pygame

from game import config
from world import inset as terrain_inset
from world.elevation import LevelIndex, NONE, can_cross, diagonal_blocked

# The canonical neighbour order. `FlowField._NEI` and `NavGrid.step_mask` are
# both built from it, so bit *i* of a cell's mask is always the move in
# `NAV_DIRS[i]` and the two cannot drift apart.
NAV_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1))
_TILE_BIT = {d: 1 << i for i, d in enumerate(NAV_DIRS)}
_ORTH = ((1, 0), (-1, 0), (0, 1), (0, -1))

_SQRT2 = 2.0 ** 0.5
# Clearance is only ever compared against an enemy radius (<= 30 px today) and
# used as a "how much room is here" weight, so values above this are all "wide
# open" -- capping keeps the field bounded and the obstacle scan local.
_CLEARANCE_CAP = 96.0


def _point_on_floor(layout, x: float, y: float) -> bool:
    """Mirror of `GameMap._point_ok` for a finished (non-None) layout: a room
    floor cell, a corridor rect, or a stair rect (LD-1). `test_pathfinding`
    samples this against `GameMap.is_walkable` so the two cannot drift."""
    px = config.TILE_PX
    for r in layout.rooms:
        rr = r.rect
        if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                and (int((x - rr.left) // px), int((y - rr.top) // px)) in r.cells):
            return True
    for c in layout.corridors:
        if c.rect.collidepoint(x, y):
            return True
    for s in layout.stairs:
        if s.rect.collidepoint(x, y):
            return True
    return False


def _point_inset_ok(layout, x: float, y: float, margin: float) -> bool:
    """Mirror of `GameMap.inset_ok`: is the point far enough inside its own
    terrace for a body to stand?

    Same search as `_point_on_floor` -- the room whose *cells* hold the point,
    not merely whose bounding box does, since grown island rects overlap in the
    void. A point on a corridor or a plank stair belongs to no room and carries
    no margin, which is right: those are flat.
    """
    if margin <= 0.0:
        return True
    px = config.TILE_PX
    for r in layout.rooms:
        rr = r.rect
        if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                and (int((x - rr.left) // px), int((y - rr.top) // px)) in r.cells):
            return terrain_inset.world_at(r, x, y) >= margin
    return True


def _point_in_corridor(layout, x: float, y: float) -> bool:
    """A narrow inter-region link that gets M3 clearance leniency: a plank
    corridor or (LD-1) a stair -- both are the only ways between room groups, so
    the big rare enemies must be able to thread them."""
    return (any(c.rect.collidepoint(x, y) for c in layout.corridors)
            or any(s.rect.collidepoint(x, y) for s in layout.stairs))


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
        ox, oy = self.origin
        half = self.cell * 0.5

        # The terrace margin, baked in here rather than asked per step. The
        # collider refuses a body's centre within `margin` px of a level
        # change, so a field that still routed through those cells would send
        # an enemy at a boundary the collider will not let it cross, and it
        # would grind against the corner for ever. Same class of bug as
        # `walk_links` disagreeing with `_flight_opens`; same fix, which is
        # that both sides read one authority.
        margin = terrain_inset.body_inset()

        for row in range(self.rows):
            cy = oy + row * self.cell + half
            base = row * self.cols
            for col in range(self.cols):
                cx = ox + col * self.cell + half
                i = base + col
                if _point_on_floor(layout, cx, cy):
                    if not _point_inset_ok(layout, cx, cy, margin):
                        # Not walkable, and deliberately not `blocked` either:
                        # `blocked` seeds the wall chamfer, and treating a
                        # margin as stone would shrink the clearance of every
                        # cell near a rim -- which is exactly what stops the
                        # 48 px class threading a one-tile neck.
                        continue
                    walkable[i] = 1
                    if _point_in_corridor(layout, cx, cy):
                        corridor[i] = 1
                else:
                    blocked[i] = 1

        self.walkable = walkable
        self.corridor = corridor
        self.clearance = self._clearance_transform(blocked, obstacles)
        self.levels = LevelIndex(layout)
        self.level, self.flight, self.step_mask = self._elevation(walkable,
                                                                  corridor)

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
        M3 clearance leniency. A flight is one tile wide with stone either
        side; without it the 48 px nav class cannot thread one, exactly the
        case that leniency was added for in LD-3."""
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
        """Per-cell clearance in world px: the two-pass (1, sqrt2) chamfer
        distance to the nearest blocked cell, then lowered by the exact
        `dist - radius` to every nearby obstacle edge, clamped to
        `_CLEARANCE_CAP`. No queue, deterministic. Blocked cells stay 0."""
        cols, rows, step = self.cols, self.rows, float(self.cell)
        diag = step * _SQRT2
        big = _CLEARANCE_CAP
        d = array("f", bytes(4 * cols * rows))
        for i in range(cols * rows):
            d[i] = 0.0 if blocked[i] else big

        for row in range(rows):
            base = row * cols
            up = base - cols
            for col in range(cols):
                i = base + col
                if blocked[i]:
                    continue
                best = d[i]
                if col > 0:
                    best = min(best, d[i - 1] + step)
                if row > 0:
                    best = min(best, d[up + col] + step)
                    if col > 0:
                        best = min(best, d[up + col - 1] + diag)
                    if col < cols - 1:
                        best = min(best, d[up + col + 1] + diag)
                d[i] = best

        for row in range(rows - 1, -1, -1):
            base = row * cols
            dn = base + cols
            for col in range(cols - 1, -1, -1):
                i = base + col
                if blocked[i]:
                    continue
                best = d[i]
                if col < cols - 1:
                    best = min(best, d[i + 1] + step)
                if row < rows - 1:
                    best = min(best, d[dn + col] + step)
                    if col < cols - 1:
                        best = min(best, d[dn + col + 1] + diag)
                    if col > 0:
                        best = min(best, d[dn + col - 1] + diag)
                d[i] = best

        # The chamfer measures centre-to-blocked-centre; the actual wall sits
        # ~half a cell nearer than the blocked cell's centre. Pull every value in
        # by that half cell so the field is conservative against room / void
        # edges (keeps `passable` from ever out-running `GameMap.is_walkable`).
        pull = step * 0.5
        for i in range(cols * rows):
            if not blocked[i]:
                v = d[i] - pull
                d[i] = v if v > 0.0 else 0.0

        ox, oy = self.origin
        half = self.cell * 0.5
        for o in obstacles:
            orad = float(o.radius)
            # a cell further than this from the centre keeps a clearance already
            # >= the cap, so the obstacle cannot lower it
            margin = orad + _CLEARANCE_CAP
            c0 = max(0, int((o.pos.x - margin - ox) // self.cell))
            c1 = min(cols - 1, int((o.pos.x + margin - ox) // self.cell))
            r0 = max(0, int((o.pos.y - margin - oy) // self.cell))
            r1 = min(rows - 1, int((o.pos.y + margin - oy) // self.cell))
            for row in range(r0, r1 + 1):
                cy = oy + row * self.cell + half
                base = row * cols
                for col in range(c0, c1 + 1):
                    i = base + col
                    if blocked[i]:
                        continue
                    cx = ox + col * self.cell + half
                    edge = ((cx - o.pos.x) ** 2 + (cy - o.pos.y) ** 2) ** 0.5 - orad
                    if edge < d[i]:
                        d[i] = edge if edge > 0.0 else 0.0
        return d

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
        (M3) is applied by the caller, not here."""
        if not self.in_bounds(col, row):
            return False
        i = self.idx(col, row)
        return bool(self.walkable[i]) and self.clearance[i] >= radius

    def passable_world(self, wx: float, wy: float, radius: float = 0.0) -> bool:
        return self.passable(*self.cell_of(wx, wy), radius)


_INF = 1_000_000_000


class FlowField:
    """A cost-to-target distance field over a `NavGrid`, plus a smooth downhill
    direction sampler.

    `rebuild(target_world, min_clearance, corridor_lenient)` runs Dial's
    algorithm (integer bucket queue -- costs are sums of two fixed step weights,
    so no binary heap) from the target cell outward across **every** reachable
    cell, so an enemy two rooms away still gets a correct route. A cell is
    traversable iff `navgrid.passable(cell, min_clearance)` or -- when
    `corridor_lenient` -- it is a corridor cell (a one-tile hallway is only two
    cells wide, so the big rare enemies would otherwise never path between
    rooms). Diagonal steps that would cut a blocked corner are refused.

    `direction_at(world_pos)` returns a unit vector: the clearance-weighted blend
    of the steps to every strictly-lower-cost neighbour (any angle, hugs walls),
    or a zero vector on the target cell / an unreachable cell / before any
    rebuild. `resolve_movement` stays the final per-step guard.

    Pure and deterministic: same grid + args -> identical `cost`.
    """

    _NEI: tuple = ()   # per-instance (dcol, drow, weight, mask bit)

    def __init__(self, navgrid: NavGrid) -> None:
        self.navgrid = navgrid
        n = navgrid.cols * navgrid.rows
        # costs are sums of two small step weights; the max over any world is
        # well under 2**31, so a signed `long` array is plenty.
        self.cost = array("l", bytes(array("l").itemsize)) * n
        self._blank = array("l", [_INF]) * n
        w_o = navgrid.cell
        w_d = int(round(navgrid.cell * _SQRT2))
        self._w_orth = w_o
        self._w_diag = w_d
        # (dcol, drow, weight, mask bit). The bit is the neighbour's position
        # in `NAV_DIRS`, which is also how `NavGrid.step_mask` was baked, so the
        # rebuild loop can reject an illegal move with one AND.
        self._NEI = tuple((dc, dr, w_d if dc and dr else w_o, 1 << i)
                          for i, (dc, dr) in enumerate(NAV_DIRS))
        # runaway guard only -- a full-world fill visits every reachable cell once
        self.relax_cap = 8 * n
        self.relaxations = 0
        self.reachable = False
        self.target_cell: tuple[int, int] | None = None
        self._trav = bytearray(n)                 # last rebuild's traversable mask
        self._trav_cache: dict[tuple, bytearray] = {}

    # --- build -------------------------------------------------
    def _traversable(self, min_clearance: float, corridor_lenient: bool) -> bytearray:
        key = (round(min_clearance, 2), bool(corridor_lenient))
        cached = self._trav_cache.get(key)
        if cached is not None:
            return cached
        ng = self.navgrid
        n = ng.cols * ng.rows
        walk, corr, clear = ng.walkable, ng.corridor, ng.clearance
        m = bytearray(n)
        for i in range(n):
            if walk[i] and (clear[i] >= min_clearance
                            or (corridor_lenient and corr[i])):
                m[i] = 1
        self._trav_cache[key] = m
        return m

    def _nearest_traversable(self, col: int, row: int,
                             trav: bytearray, max_ring: int = 6):
        ng = self.navgrid
        cols, rows = ng.cols, ng.rows
        if 0 <= col < cols and 0 <= row < rows and trav[row * cols + col]:
            return (col, row)
        for ring in range(1, max_ring + 1):
            for dr in range(-ring, ring + 1):
                for dc in range(-ring, ring + 1):
                    if max(abs(dc), abs(dr)) != ring:
                        continue
                    c, r = col + dc, row + dr
                    if 0 <= c < cols and 0 <= r < rows and trav[r * cols + c]:
                        return (c, r)
        return None

    def rebuild(self, target_world, min_clearance: float = 0.0,
                corridor_lenient: bool = True, max_cost: int | None = None) -> None:
        """Fill the field outward from `target_world`.

        `max_cost` stops the fill once the frontier passes that path cost --
        **path**, not straight line, so a cell a few hundred pixels away across
        a drop can sit well beyond it. Costs are in world pixels for both nav
        classes (an orthogonal step costs `navgrid.cell`), so the bound reads
        directly as "how far will an enemy be asked to walk".

        Left `None` here and set by `NavField`, so the field's own contract is
        unchanged for anything constructing it directly."""
        ng = self.navgrid
        cols, rows = ng.cols, ng.rows
        n = cols * rows
        cost = self.cost
        # Slice-assign a prebuilt blank rather than looping. The fill itself is
        # bounded now (`max_cost`), so clearing 160k longs one at a time in
        # Python had become the single biggest cost in a repath -- more than the
        # search it was preparing for.
        cost[:] = self._blank
        self.relaxations = 0

        trav = self._traversable(min_clearance, corridor_lenient)
        self._trav = trav
        tc = ng.cell_of(target_world[0], target_world[1])
        seed = self._nearest_traversable(tc[0], tc[1], trav)
        self.target_cell = seed
        self.reachable = seed is not None
        if seed is None:
            return

        nei = self._NEI
        smask = ng.step_mask
        si = seed[1] * cols + seed[0]
        cost[si] = 0
        buckets: dict[int, list] = {0: [si]}
        cur = 0
        max_bucket = 0
        cap = self.relax_cap
        relax = 0
        limit = _INF if max_cost is None else int(max_cost)
        while cur <= max_bucket and cur <= limit:
            bucket = buckets.get(cur)
            if not bucket:
                cur += 1
                continue
            u = bucket.pop()
            if cost[u] != cur:
                continue                            # stale (re-queued lower)
            ucol = u % cols
            urow = u // cols
            base = urow * cols
            relax += 1
            if relax > cap:
                break
            umask = smask[u]
            for dcol, drow, w, bit in nei:
                if not (umask & bit):
                    continue          # the terrain forbids it: a flank, a back
                                      # edge, or the side of a staircase
                ncol = ucol + dcol
                if ncol < 0 or ncol >= cols:
                    continue
                nrow = urow + drow
                if nrow < 0 or nrow >= rows:
                    continue
                v = nrow * cols + ncol
                if not trav[v]:
                    continue
                if dcol and drow and (
                        not trav[base + ncol] or not trav[nrow * cols + ucol]):
                    continue                        # would clip a blocked corner
                nc = cur + w
                if nc < cost[v]:
                    cost[v] = nc
                    buckets.setdefault(nc, []).append(v)
                    if nc > max_bucket:
                        max_bucket = nc
        self.relaxations = relax

    # --- sample -------------------------------------------------
    def cost_at(self, world_pos) -> int:
        ng = self.navgrid
        col, row = ng.cell_of(world_pos.x, world_pos.y)
        if not ng.in_bounds(col, row):
            return _INF
        return self.cost[row * ng.cols + col]

    def direction_at(self, world_pos) -> pygame.Vector2:
        ng = self.navgrid
        zero = pygame.Vector2()
        if not self.reachable:
            return zero
        col, row = ng.cell_of(world_pos.x, world_pos.y)
        if not ng.in_bounds(col, row):
            return zero
        cols, rows = ng.cols, ng.rows
        i = row * cols + col
        ci = self.cost[i]
        if ci >= _INF or ci == 0:
            return zero
        trav = self._trav
        base = row * cols
        acc = pygame.Vector2()
        # The gradient is gated on the same mask the fill was: a downhill
        # neighbour across a drop is not a direction to steer in, even though
        # its cost is genuinely lower -- it was reached the long way round.
        umask = ng.step_mask[i]
        for dcol, drow, _w, bit in self._NEI:
            if not (umask & bit):
                continue
            ncol, nrow = col + dcol, row + drow
            if ncol < 0 or ncol >= cols or nrow < 0 or nrow >= rows:
                continue
            v = nrow * cols + ncol
            cv = self.cost[v]
            if cv >= ci:
                continue
            if dcol and drow and (
                    not trav[base + ncol] or not trav[nrow * cols + col]):
                continue
            step = pygame.Vector2(dcol, drow)
            step.scale_to_length(1.0)
            acc += step * float(ci - cv)
        if acc.length_squared() < 1e-9:
            return zero
        return acc.normalize()

    def steer_at(self, world_pos) -> pygame.Vector2:
        """`direction_at`, but when the enemy sits on a cell the fill never
        reached (clearance too tight for its class, a pocket behind a prop) fall
        back to the direction of the nearest cell that *was* reached, instead of
        letting the caller beeline blindly. A zero vector still means "no route
        anywhere near here" (or the enemy is on the target cell)."""
        d = self.direction_at(world_pos)
        if d.length_squared() > 1e-9 or not self.reachable:
            return d
        ng = self.navgrid
        col, row = ng.cell_of(world_pos.x, world_pos.y)
        if ng.in_bounds(col, row) and self.cost[ng.idx(col, row)] < _INF:
            return d                          # on / adjacent to the target -- trust the zero
        return self._escape_dir(col, row, world_pos)

    def _escape_dir(self, col: int, row: int, world_pos) -> pygame.Vector2:
        ng = self.navgrid
        cols, rows = ng.cols, ng.rows
        best = None
        best_cost = _INF
        for ring in (1, 2, 3):
            for dr in range(-ring, ring + 1):
                for dc in range(-ring, ring + 1):
                    if max(abs(dc), abs(dr)) != ring:
                        continue
                    c, r = col + dc, row + dr
                    if 0 <= c < cols and 0 <= r < rows:
                        cost = self.cost[r * cols + c]
                        if cost < best_cost:
                            best_cost, best = cost, (c, r)
            if best is not None:
                break                        # nearest ring with any reached cell wins
        if best is None:
            return pygame.Vector2()
        step = ng.world_of(*best) - world_pos
        return step.normalize() if step.length_squared() > 1e-9 else pygame.Vector2()


# Navigation classes: (name, cell px, radius ceiling, field min-clearance). An
# enemy uses the first class whose ceiling its radius fits under. Two grids keep
# the small common enemies precise while the big rare ones (tank/elite/summoner/
# brute) get a coarser field they can actually fit through. See the journal's
# reevaluation trigger: collapse to one 32 px grid if the two ever disagree in a
# way that misbehaves.
_NAV_CLASSES = (
    ("small", 32, 16.0, 16.0),
    ("large", 48, 1.0e9, 22.0),
)


class NavField:
    """Dual-resolution shared flow field toward a moving target (M3).

    Owns one static `NavGrid` and one `FlowField` per navigation class. `rebuild`
    refreshes every field toward `target_world`; `direction(pos, radius)` /
    `cost(pos, radius)` sample the class that fits `radius`. `target_cell_changed`
    lets the caller repath early when the target crosses a cell boundary.
    """

    def __init__(self, layout, obstacles=None, classes=_NAV_CLASSES) -> None:
        self.grids: dict = {}
        self.fields: dict = {}
        self._order: list = []          # (ceiling, name, min_clearance), sorted
        for name, cell, ceiling, min_clear in classes:
            g = NavGrid(layout, obstacles, cell)
            self.grids[name] = g
            self.fields[name] = FlowField(g)
            self._order.append((ceiling, name, float(min_clear)))
        self._order.sort()
        self._min_clear = {name: mc for _c, name, mc in self._order}
        self.classes = [name for _c, name, _mc in self._order]   # rebuild order
        self._ref_grid = self.grids[self.classes[0]]
        self._target_cell: tuple[int, int] | None = None
        self.reachable = False

    def _class_for(self, radius: float) -> str:
        for ceiling, name, _mc in self._order:
            if radius <= ceiling:
                return name
        return self._order[-1][1]

    def rebuild(self, target_world, only: str | None = None) -> None:
        """Refresh the flow field(s) toward `target_world`. `only` names a single
        class to rebuild (M6 staggering -- one grid per cycle keeps the ~8 ms
        both-grids spike off any one frame); default rebuilds every class."""
        tx, ty = float(target_world[0]), float(target_world[1])
        names = [only] if only is not None else self.classes
        for name in names:
            self.fields[name].rebuild((tx, ty), self._min_clear[name],
                                      corridor_lenient=True,
                                      max_cost=config.NAV_FILL_MAX_COST)
        self._target_cell = self._ref_grid.cell_of(tx, ty)
        self.reachable = any(f.reachable for f in self.fields.values())

    def target_cell_drift(self, target_world) -> int:
        """Chebyshev distance (in reference-grid cells) between `target_world`
        and the cell the field was last rebuilt toward. A large sentinel before
        the first rebuild."""
        if self._target_cell is None:
            return 1 << 30
        c, r = self._ref_grid.cell_of(float(target_world[0]), float(target_world[1]))
        return max(abs(c - self._target_cell[0]), abs(r - self._target_cell[1]))

    def target_cell_changed(self, target_world) -> bool:
        return self.target_cell_drift(target_world) > 0

    def direction(self, world_pos, radius: float) -> pygame.Vector2:
        return self.fields[self._class_for(radius)].steer_at(world_pos)

    def cost(self, world_pos, radius: float) -> int:
        return self.fields[self._class_for(radius)].cost_at(world_pos)
