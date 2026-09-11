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
                # A diagonal through a blocked corner is not a route the
                # field will take, so it cannot be a route the repair opens
                # by paying for the cell at its end.
                if _corner_clips(open_, killers, cols, col, row, dc, dr):
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


def _corner_clips(open_, killers, cols, col, row, dc, dr) -> bool:
    """Would a diagonal step from (col, row) cut a blocked corner? The flow
    field refuses such a step (`FlowField.step`: both orthogonal neighbours
    of the move must be traversable), and a body cannot squeeze through it
    either, so the repair must not count it as a way in. It did, until a
    collider trim made more gaps that were open only corner to corner: the
    field then found islands sealed that this pass had passed as reachable,
    and removed nothing."""
    if not (dc and dr):
        return False
    a = row * cols + col + dc
    b = (row + dr) * cols + col
    return (not open_[a] or killers[a]) or (not open_[b] or killers[b])


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
            if _corner_clips(open_, killers, cols, col, row, dc, dr):
                continue
            seen[j] = 1
            stack.append(j)
    return seen


def _exempt_pens(grid, layout, open_) -> None:
    """A village's sheep pen (HI-2) leaves the required set.

    The ring of fence posts encloses it on purpose: the hero fits through
    the gate, the sheep are leashed inside, and no enemy ever spawns on the
    island. Judged as enemy ground it failed anyway -- the 48 px lattice at
    the widest body read even a two-tile gate as sealed whenever a column
    landed off its middle, and the repair pulled a post out of the far side
    of the pen (seed 35, island 8; seed 7, island 5). So the pen's cells,
    fence ring included, are closed here before the flood: neither required
    nor walked through.

    One tile beyond the ring as well. A house may stand a body's width from
    the fence, and the sliver between them holds a cell or two that nothing
    kills yet nothing reaches -- the same false seal, one tile out."""
    from game import config
    px = config.TILE_PX
    pens = [v.pen.inflate(4 * px, 4 * px)
            for v in getattr(layout, "villages", ()) if v.pen is not None]
    if not pens:
        return
    ox, oy = grid.origin
    half = grid.cell * 0.5
    for pen in pens:
        c0 = max(0, int((pen.left - ox) // grid.cell))
        c1 = min(grid.cols - 1, int((pen.right - ox) // grid.cell))
        r0 = max(0, int((pen.top - oy) // grid.cell))
        r1 = min(grid.rows - 1, int((pen.bottom - oy) // grid.cell))
        for row in range(r0, r1 + 1):
            cy = oy + row * grid.cell + half
            for col in range(c0, c1 + 1):
                cx = ox + col * grid.cell + half
                if pen.collidepoint(cx, cy):
                    open_[row * grid.cols + col] = 0


def _open_villages(grid, layout, killers) -> None:
    """Inside a village's settlement disc (`Village.radius` round the forge)
    no obstacle kills a cell: the flood walks the square as open ground.

    The houses cluster a few px apart on purpose, and the slivers between
    them are cells the widest body can stand on but never reach -- the
    same false seal as the pen's, and the repair answered it by pulling a
    house out of the cluster (seeds 1, 2, 6). The village is not enemy
    ground: nothing spawns there, the hero fits the roads by construction
    (a tile of lane from every bridge to the forge), and an enemy in
    pursuit takes the road too. So the square is walked through rather
    than judged, which also keeps the flood connected across the island.

    The town hall gets a disc of its own (LD-Z): it stands five to six
    tiles up the axis, and its north half fell outside the settlement
    disc -- a hall against the north coast walled off a strip of beach
    behind it and the repair pulled the hall out (seed 21). Nothing lives
    behind the hall either."""
    from game import config
    discs = [(v.forge.x, v.forge.y, float(v.radius))
             for v in getattr(layout, "villages", ()) if float(v.radius) > 0]
    discs += [(x, y, 3.0 * config.TILE_PX)
              for v in getattr(layout, "villages", ())
              for kind, x, y in v.buildings if kind == "monastery"]
    if not discs:
        return
    ox, oy = grid.origin
    half = grid.cell * 0.5
    for fx, fy, r in discs:
        c0 = max(0, int((fx - r - ox) // grid.cell))
        c1 = min(grid.cols - 1, int((fx + r - ox) // grid.cell))
        r0 = max(0, int((fy - r - oy) // grid.cell))
        r1 = min(grid.rows - 1, int((fy + r - oy) // grid.cell))
        for row in range(r0, r1 + 1):
            cy = oy + row * grid.cell + half
            for col in range(c0, c1 + 1):
                cx = ox + col * grid.cell + half
                if (cx - fx) ** 2 + (cy - fy) ** 2 <= r * r:
                    killers[row * grid.cols + col] = ()


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
    _exempt_pens(grid, layout, open_)

    start = _start_cell(grid, layout, open_)
    if start is None:
        return []

    removed = []
    for _ in range(rounds):
        killers = _killers(grid, obstacles, radius)
        _open_villages(grid, layout, killers)
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
