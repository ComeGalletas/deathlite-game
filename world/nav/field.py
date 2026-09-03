"""`FlowField` and `NavField`: the shared flow field enemies steer on.

`FlowField` -- per-cycle bucket-queue distance field over one `NavGrid`
toward a target, with `direction_at` (pure gradient) and `steer_at`
(gradient, else a bearing to the nearest reached cell so a stranded enemy is
not left to beeline blindly).

`NavField` -- coordinator: one grid + field per navigation class, rebuilt
toward the player; `PlayingState` owns it and the enemy AI samples it.
"""
from __future__ import annotations

from array import array

import pygame

from game import config
from world.nav.lattice import NAV_DIRS, NavGrid

_SQRT2 = 2.0 ** 0.5

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
        best = None
        best_cost = ci
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
            if cv < best_cost:
                best_cost, best = cv, step
        if acc.length_squared() < 1e-9:
            # Two opposite downhill neighbours of equal cost -- a rim cell
            # between two ways round a boulder -- sum to nothing, which read
            # as "no way on" and froze whoever stood there. Found by the
            # gradient-walk test the moment it ran on a height-map world.
            # The cell is not a dead end, so take the single best neighbour.
            return best if best is not None else zero
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
    """Dual-resolution shared flow field toward a moving target.

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
        class to rebuild (staggering -- one grid per cycle keeps the ~8 ms
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
