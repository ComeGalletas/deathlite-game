"""Take back the obstacles that seal part of the world off.

The scatter places obstacles against a set of keep-clear rectangles -- corridor
mouths, staircases and their landings, a special room's interaction disc. Those
protect the places a seal was *expected*, and they are not enough. Once the
obstacles grew (per-area density raised them from 1.8 to 47.5 per thousand
cells, and their radii with it), the widest navigating body started finding worlds where a
whole island was walled off behind two or three of them, and measurement said it
was not rare: on the large navigation class -- 48 px lattice, 22 px body -- four
of ten sample seeds lost between 1,300 and 6,300 reachable cells, one of them
69% of the world, while the same worlds with every obstacle removed lost none.

Widening the keep-clear rectangles is the obvious answer and it does not work.
Making the mouth test radius-aware (a rock one pixel outside a bridge mouth
still puts thirty pixels of itself across the way in) fixed some seeds outright
and left others exactly as they were, because the pinch is not always at a
mouth: two obstacles can close a neck of ordinary ground that no rule knew to
protect. Any geometry rule is a guess about where the choke will be.

So this does not guess. It asks the question that actually matters -- *can the
widest body still reach everywhere it could reach on bare terrain?* -- and, where
the answer is no, removes the specific obstacles standing in the way. It is the
same shape as `heightmap._carve_lakes`, which cuts a lake and puts it back if the
room came apart; here the check is against the navigation lattice the game itself
steers on rather than the generator's own adjacency, because it is the lattice
that decides whether a body fits.

**Why the widest class.** A route the 22 px body can walk, the 16 px one can too,
so repairing the coarse class repairs both. The class list is read from
`pathfinding` rather than restated, so a new class cannot silently go
unprotected.

Removals are minimal in a real sense: the Dijkstra's edge weight is *the number
of obstacles that would have to go*, so a region is reopened through its
cheapest pinch rather than by clearing the first path found. One sweep settles
every sealed region at once -- popping in cost order means the first cell of a
region off the queue is that region's cheapest entry -- which is what keeps the
pass to a round or two instead of one per seal.
"""
from __future__ import annotations

from array import array
from collections import deque

from world.pathfinding import NAV_DIRS, NavGrid, _NAV_CLASSES


def _widest_class():
    """`(cell px, body radius)` of the navigation class with the largest body."""
    _name, cell, _ceiling, clearance = max(_NAV_CLASSES, key=lambda c: c[3])
    return int(cell), float(clearance)


def _killers(grid, obstacles, radius):
    """For each cell, the indices of the obstacles that make it impassable.

    Mirrors `NavGrid._clearance_transform`'s obstacle pass exactly: an obstacle
    lowers a cell's clearance to `distance - obstacle radius`, so it blocks the
    cell when that falls below the body radius -- that is, when the cell centre
    is within `radius + obstacle radius`.
    """
    out = [()] * (grid.cols * grid.rows)
    ox, oy = grid.origin
    half = grid.cell * 0.5
    for oi, o in enumerate(obstacles):
        reach = radius + float(o.radius)
        c0 = max(0, int((o.pos.x - reach - ox) // grid.cell))
        c1 = min(grid.cols - 1, int((o.pos.x + reach - ox) // grid.cell))
        r0 = max(0, int((o.pos.y - reach - oy) // grid.cell))
        r1 = min(grid.rows - 1, int((o.pos.y + reach - oy) // grid.cell))
        for row in range(r0, r1 + 1):
            cy = oy + row * grid.cell + half
            base = row * grid.cols
            for col in range(c0, c1 + 1):
                cx = ox + col * grid.cell + half
                if (cx - o.pos.x) ** 2 + (cy - o.pos.y) ** 2 < reach * reach:
                    out[base + col] = out[base + col] + (oi,)
    return out


def _start_cell(grid, layout, open_):
    """A geometry-passable cell in the start room to flood from."""
    room = next((r for r in layout.rooms if r.kind == "start"), None)
    if room is None:
        room = layout.rooms[0] if layout.rooms else None
    if room is None:
        return None
    col, row = grid.cell_of(room.center.x, room.center.y)
    for rad in range(0, 24):
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                if max(abs(dc), abs(dr)) != rad:
                    continue
                c, r = col + dc, row + dr
                if grid.in_bounds(c, r) and open_[grid.idx(c, r)]:
                    return grid.idx(c, r)
    return None


def _regions(grid, dead):
    """Label the sealed-off cells by connected region.

    One Dijkstra can then reopen **every** region at once instead of one per
    round. That matters: the walk is over the whole lattice however small the
    seal is, so six rounds meant six full sweeps, and with nine islands
    the repair had grown to 60% of world generation.
    """
    cols, rows = grid.cols, grid.rows
    step_mask = grid.step_mask
    label = {}
    rid = 0
    for i in range(cols * rows):
        if not dead[i] or i in label:
            continue
        stack = [i]
        label[i] = rid
        while stack:
            j = stack.pop()
            col, row = j % cols, j // cols
            mask = step_mask[j]
            for bit, (dc, dr) in enumerate(NAV_DIRS):
                if not (mask >> bit) & 1:
                    continue
                c, r = col + dc, row + dr
                if not (0 <= c < cols and 0 <= r < rows):
                    continue
                k = r * cols + c
                if dead[k] and k not in label:
                    label[k] = rid
                    stack.append(k)
        rid += 1
    return label, rid


def _seals(grid, open_, killers, start, dead):
    """Dijkstra from `start` over geometry-passable cells, paying one unit per
    obstacle that would have to be removed to enter a cell.

    Returns the obstacles on the cheapest route into **each** sealed region --
    Dijkstra pops in cost order, so the first cell of a region to come off the
    queue is that region's cheapest entry, and one sweep settles them all.
    Weights are small integers, so this is a bucket queue rather than a heap.
    """
    label, count = _regions(grid, dead)
    if not count:
        return []
    cols, rows = grid.cols, grid.rows
    step_mask = grid.step_mask
    n = cols * rows
    inf = 1 << 30
    dist = array("l", [inf]) * n
    prev = array("l", [-1]) * n
    dist[start] = 0
    buckets = [deque([start])]
    solved = set()
    out: set = set()
    d = 0
    while d < len(buckets) and len(solved) < count:
        q = buckets[d]
        while q:
            i = q.popleft()
            if dist[i] != d:
                continue
            rid = label.get(i)
            if d and rid is not None and rid not in solved:
                solved.add(rid)
                j = i
                while j != -1:
                    out.update(killers[j])
                    j = prev[j]
                if len(solved) == count:
                    break
            col, row = i % cols, i // cols
            mask = step_mask[i]
            for bit, (dc, dr) in enumerate(NAV_DIRS):
                if not (mask >> bit) & 1:
                    continue
                c, r = col + dc, row + dr
                if not (0 <= c < cols and 0 <= r < rows):
                    continue
                j = r * cols + c
                if not open_[j]:
                    continue
                nd = d + len(killers[j])
                if nd < dist[j]:
                    dist[j] = nd
                    prev[j] = i
                    while len(buckets) <= nd:
                        buckets.append(deque())
                    buckets[nd].append(j)
        d += 1
    return sorted(out)


def _reachable(grid, open_, killers, start):
    """Cells the body can stand on and walk to, obstacles included."""
    cols, rows = grid.cols, grid.rows
    step_mask = grid.step_mask
    seen = bytearray(cols * rows)
    if killers[start]:
        return seen
    seen[start] = 1
    stack = [start]
    while stack:
        i = stack.pop()
        col, row = i % cols, i // cols
        mask = step_mask[i]
        for bit, (dc, dr) in enumerate(NAV_DIRS):
            if not (mask >> bit) & 1:
                continue
            c, r = col + dc, row + dr
            if not (0 <= c < cols and 0 <= r < rows):
                continue
            j = r * cols + c
            if seen[j] or not open_[j] or killers[j]:
                continue
            seen[j] = 1
            stack.append(j)
    return seen


def unseal(layout, rounds: int = 40):
    """Drop the obstacles that cut part of `layout` off, in place.

    Returns the obstacles removed. Deterministic -- no RNG, and the obstacle
    list is walked in order -- so a seed still produces the same world.

    `rounds` is a **safety valve, not a budget**: the loop already stops the
    moment nothing is sealed, and each round is one Dijkstra over a lattice the
    NavGrid build above dwarfs. It was 8, which quietly became too few when
    the island count went up -- seeds finished with a handful of cells
    still walled off, and the test that says obstacles never cut off more than
    bare terrain went red on five cells. Measured, the seeds that needed more
    wanted one or two extra rounds, not thirty.
    """
    obstacles = layout.obstacles
    if not obstacles or not layout.rooms:
        return []
    cell, radius = _widest_class()
    # Geometry only. Neither the chamfer nor the step mask depends on obstacles,
    # so this is built once and reused as they are taken away.
    grid = NavGrid(layout, [], cell)
    n = grid.cols * grid.rows
    # Exactly `NavGrid.passable` with no obstacles in it: on the floor, and far
    # enough from the terrain edge for this body.
    open_ = bytearray(1 if (grid.walkable[i] and grid.clearance[i] >= radius)
                      else 0 for i in range(n))

    start = _start_cell(grid, layout, open_)
    if start is None:
        return []

    removed = []
    for _ in range(rounds):
        killers = _killers(grid, obstacles, radius)
        if killers[start]:
            # An obstacle landed on the only cell we can flood from; it has to
            # go before anything else can be judged.
            drop = set(killers[start])
        else:
            seen = _reachable(grid, open_, killers, start)
            dead = bytearray(1 if (open_[i] and not killers[i] and not seen[i])
                             else 0 for i in range(n))
            if not any(dead):
                break
            hit = _seals(grid, open_, killers, start, dead)
            if not hit:
                break                 # sealed by terrain, not by obstacles
            drop = set(hit)
        removed.extend(obstacles[i] for i in sorted(drop))
        obstacles[:] = [o for i, o in enumerate(obstacles) if i not in drop]
    return removed
