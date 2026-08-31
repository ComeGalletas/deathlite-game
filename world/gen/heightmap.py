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
"""
from __future__ import annotations

from world.layout import (
    Cell, GROUND, CLIFF, VSTAIR, EWSTAIR, LAKE, WALKABLE_KINDS,
)

MIN_TERRACE_ROWS = 3          # walkable rows a terrace needs to be worth having
MAX_LEVEL = 2                 # sea level plus two floors
MAX_DROP = 2                  # "max two stacked cliffs"

# How far each plateau is inset from the one below it, per side. South is the
# deepest because that face is the one the camera sees -- pulling the cap back
# from the south rim is what gives the mountain a visible slope, while barely
# insetting the north keeps it hugging the island's back. `CAP_ROUGHNESS` then
# nibbles the rim so it does not read as a smooth contour line.
CAP_INSET_S = 5
CAP_INSET_N = 1
CAP_INSET_W = 3
CAP_INSET_E = 3
CAP_ROUGHNESS = 0.35
MIN_CAP_CELLS = 24            # below this a plateau is not worth having
# Crossings are placed per **region** rather than per island, so every stretch
# of rim gets its own way up instead of the quota being spent wherever a global
# shuffle happens to fall. `REGION` is the region's side in tiles and
# `STAIR_SPACING` how far apart two crossings must sit.
REGION = 8
STAIR_SPACING = 4
# Canyons cut up into a plateau from its southern rim. Their heads are the only
# south-facing wall the northern half of an island can have, so these are what
# put ways up there at all -- see `_carve_canyons`.
CANYONS = 3
CANYON_DEPTH = (4, 10)
CANYON_WIDTH = (3, 5)


# --- terrace planning -----------------------------------------------------

def _plan_levels(rows: int, rng, base: int, top: int = MAX_LEVEL
                 ) -> list[tuple[int, int]]:
    """`[(level, drop_into_it), ...]` from the **top** terrace down, where
    `drop` is the wall depth above that terrace (0 for the topmost).

    Built from the bottom up: the lowest terrace is the room's base level, then
    stepped up by 1 or 2 while there is level headroom (`top`, which a caller
    lowers when a link lands on this room's north edge) and row budget left."""
    levels = [base]
    drops = [0]
    while len(levels) < 4:
        step = rng.choice((1, 1, 2))
        if levels[-1] + step > top:
            step = 1
        if levels[-1] + step > top:
            break
        need = (len(levels) + 1) * MIN_TERRACE_ROWS + sum(drops) + step
        if need > rows:
            break
        levels.append(levels[-1] + step)
        drops.append(step)
    # bottom-up -> top-down: the drop listed against a terrace is the wall
    # *above* it, which is the step that was taken to reach the terrace below.
    out = [(levels[i], drops[i]) for i in range(len(levels) - 1, -1, -1)]
    return [(lvl, out[i - 1][1] if i else 0) for i, (lvl, _d) in enumerate(out)]


def _split_rows(rows: int, n: int, rng) -> list[int]:
    """`n` terrace heights summing to `rows`, each at least the minimum."""
    out = [MIN_TERRACE_ROWS] * n
    for _ in range(rows - MIN_TERRACE_ROWS * n):
        out[rng.randrange(n)] += 1
    return out


def coast_mask(cols: int, rows: int, rng, margin: int = 3) -> frozenset:
    """An irregular outer shape for a room -- its coastline.

    Each of the four sides gets its own clamped random walk of inset, so the
    island's silhouette wanders instead of ruling four straight lines. This is
    what breaks the "fixed staircase" read: the terraces still band north to
    south, but they no longer all start and stop in the same column, so the
    coast cuts across them at a different place on every row.

    It needs no new art either. A terrace's east and west edges are grass
    meeting open water, which the `slots.raised` fringe already draws -- only a
    *southward* drop needs a cliff face, and the bands still run that way."""
    # Erosion compounds: the four insets, then the bays, then the de-spiking
    # can between them eat most of a room, leaving an islet too small to carry
    # terraces and with bridges running to almost nothing. Back the margin off
    # until enough of the room survives.
    for attempt in range(margin, -1, -1):
        out = _coast_once(cols, rows, rng, attempt)
        if len(out) >= 0.45 * cols * rows:
            return out
    return frozenset((c, r) for c in range(cols) for r in range(rows))


def _coast_once(cols: int, rows: int, rng, margin: int) -> frozenset:
    west = _walk(rows, rng, margin)
    east = _walk(rows, rng, margin)
    north = _walk(cols, rng, max(0, margin - 1))
    south = _walk(cols, rng, margin)
    out = set()
    for r in range(rows):
        for c in range(west[r], cols - east[r]):
            if north[c] <= r < rows - south[c]:
                out.add((c, r))
    if not out:
        return frozenset()
    _carve_bays(out, cols, rows, rng)
    return _despike(out) if out else frozenset()


def _carve_bays(mask: set, cols: int, rows: int, rng, count: int = 3) -> None:
    """Bite a few bays into the coast so the terraces themselves come out
    ragged, not just the island's outline.

    Each bay starts on the shore and eats inward, so it opens onto the sea
    rather than leaving a landlocked hole (that is what a lake is for). A bay
    reaching across a terrace narrows it to a neck, which is where the wide
    lower floor with a slim path above it comes from."""
    for _ in range(count):
        edge = [p for p in mask
                if any((p[0] + dx, p[1] + dy) not in mask
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
        if not edge:
            return
        bay = {edge[rng.randrange(len(edge))]}
        for _ in range(rng.randint(6, 22)):
            c, r = list(bay)[rng.randrange(len(bay))]
            nb = rng.choice(((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)))
            if nb in mask:
                bay.add(nb)
        trial = mask - bay
        if trial and _one_piece(trial):
            mask -= bay


def _one_piece(mask) -> bool:
    """Is this cell set 4-connected? A bay that severs the island would leave
    an unreachable half once the walls go in."""
    start = next(iter(mask))
    seen, stack = {start}, [start]
    while stack:
        c, r = stack.pop()
        for nb in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            if nb in mask and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(mask)


def _walk(n: int, rng, hi: int) -> list[int]:
    """An inset per column / row, wandering over `[0, hi]`.

    Two things stop this looking like a ruled line. Each value is held for a
    short run, because stepping every column gives a comb of one-tile spikes
    rather than headlands. And the step is pulled back toward mid-range, since
    a free random walk drifts to one end and then hugs it -- which is exactly
    how the first attempt produced a straight west coast."""
    if hi <= 0:
        return [0] * n
    out = []
    v = rng.randint(0, hi)
    while len(out) < n:
        out.extend([v] * rng.randint(2, 3))
        pull = (hi / 2 - v) / max(1, hi)          # -0.5 .. 0.5
        step = rng.choice((-2, -1, -1, 1, 1, 2)) + round(pull * 2)
        v = max(0, min(hi, v + step))
    return out[:n]


def _despike(mask: set) -> frozenset:
    """Trim the coast until no tile is left clinging on by a single side.

    A one-tile peninsula or isthmus reads as a rendering fault rather than
    land, and is too narrow to walk down anyway."""
    keep = set(mask)
    while True:
        thin = {(c, r) for c, r in keep
                if sum(((c + dx, r + dy) in keep)
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))) < 2}
        if not thin:
            return frozenset(keep)
        keep -= thin


def _wander(cols: int, rng, amp: int = None, step: int = None) -> list[int]:
    """A per-column offset for one wall: a clamped random walk, so the wall
    breaks in and out like a natural ridge instead of ruling a straight line.
    `amp` sets how far it may stray, `step` how fast -- between them they set
    how granular the terrace edge is."""
    amp = WANDER if amp is None else amp
    step = STEP if step is None else step
    out = [0] * cols
    v = 0
    for c in range(cols):
        v = max(-amp, min(amp, v + rng.randint(-step, step)))
        out[c] = v
    return out


def _crevasses(wall: list, cols: int, rng, count: int = None,
               depth_range=None, width_range=None) -> None:
    """Push stretches of one wall north, so the terrace *below* it reaches up
    into the terrace above as a crevasse.

    Wandering alone only ripples the boundary. A crevasse is a deliberate
    incursion -- a bay of the lower floor biting into the higher one -- which
    is what stops the upper terraces reading as unbroken slabs of grass. The
    ordering clamp in `_settle_walls` afterwards stops one cutting so deep that
    it swallows the terrace above."""
    count = CREVASSES if count is None else count
    depth_range = depth_range or CREVASSE_DEPTH
    width_range = width_range or CREVASSE_WIDTH
    for _ in range(count):
        width = rng.randint(*width_range)
        depth = rng.randint(*depth_range)
        start = rng.randrange(max(1, cols - width))
        for i in range(width):
            c = start + i
            if 0 <= c < cols:
                # taper the ends so it reads as an inlet, not a slot
                edge = min(i, width - 1 - i, 2)
                wall[c] -= depth * (edge + 1) // 3


# --- the grid ------------------------------------------------------------

def build_grid(mask: frozenset, cols: int, rows: int, rng, base: int = 0,
               stairs_per_wall: int = 1, lakes: int = 0,
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
        _carve_lakes(grid, rng, lakes)
    _link_levels(grid, rng)
    _prune_unreachable(grid)
    # Once more at the end: carving lakes and pruning stranded pockets both
    # take cells away, and any of them may have been the ground a plateau was
    # standing on. Re-facing here is what keeps the "no floating ground" rule
    # true of the grid that actually ships, not just the one mid-build.
    _face_the_sea(grid, mask)
    return grid


def _all_neighbours_in(p, cells) -> bool:
    return all((p[0] + dx, p[1] + dy) in cells
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))


def _cap(below: frozenset, rng, inset=None, roughness: float = None
         ) -> frozenset:
    """The next plateau up: `below` eroded inward, harder from the south than
    the north, then roughened.

    The asymmetry is what makes a mountain rather than a dome -- each cap hugs
    the island's back, so the rims stack into a slope facing the camera. The
    roughening then keeps the rim from reading as a smooth contour line.

    `inset` is `(south, north, west, east)`; `roughness` the chance a rim cell
    is nibbled off. Both come from `game.config` (`HEIGHTMAP_CAP_*`)."""
    if not below:
        return frozenset()
    s, n, w, e = inset or (CAP_INSET_S, CAP_INSET_N, CAP_INSET_W, CAP_INSET_E)
    rough = CAP_ROUGHNESS if roughness is None else roughness
    keep = set()
    for p in below:
        c, r = p
        if all((c, r + k) in below for k in range(1, s + 1)) \
                and all((c, r - k) in below for k in range(1, n + 1)) \
                and all((c - k, r) in below for k in range(1, w + 1)) \
                and all((c + k, r) in below for k in range(1, e + 1)):
            keep.add(p)
    # roughen: nibble the rim in a few places and let a few nubs stand proud
    edge = [p for p in keep if not _all_neighbours_in(p, keep)]
    for p in edge:
        if rng.random() < rough:
            keep.discard(p)
    return _despike(keep) if keep else frozenset()


def _carve_canyons(cap: frozenset, rng, count: int = None, depth=None,
                   width=None) -> frozenset:
    """Cut canyons up into a plateau from its southern rim.

    A south-facing wall only exists where the level *drops* going south, and
    around a concentric cap that is the southern arc alone -- which is why the
    north of an island ends up with no way up. A canyon fixes that at the
    source: it is a finger of lower ground reaching north into the cap, and its
    **head** is a south-facing wall sitting deep in the northern half. Its
    flanks face east and west, so they stay open ground.

    It also breaks a big cap into lobes, which stops the upper floors reading
    as one unbroken slab."""
    count = CANYONS if count is None else count
    depth = depth or CANYON_DEPTH
    width = width or CANYON_WIDTH
    keep = set(cap)
    if not keep:
        return cap
    for _ in range(count):
        rim = [p for p in keep if (p[0], p[1] + 1) not in keep]
        if not rim:
            break
        c, r = rim[rng.randrange(len(rim))]
        cut = set()
        w = rng.randint(*width)
        for step in range(rng.randint(*depth)):
            row = r - step
            here = {(c + dx, row) for dx in range(-(w // 2), w - w // 2)}
            if not (here & keep):
                break
            cut |= here
            c += rng.choice((-1, 0, 0, 1))          # let it meander
        # Step the head. Left flat, a canyon's head is a short level run of
        # wall, and a level run only ever fits a *straight* flight -- an
        # east/west one needs the wall a row lower on one side than the other.
        # Pushing a single column of the head one row further north creates
        # exactly that jog, which is what lets side stairs appear up here at
        # all. Without it the northern half gets straight flights and nothing
        # else.
        if cut:
            head = min(r for _c, r in cut)
            at_head = [cc for cc, rr in cut if rr == head]
            lean = min(at_head) if rng.random() < 0.5 else max(at_head)
            cut.add((lean, head - 1))
        trial = keep - cut
        if trial and _one_piece(trial) and len(trial) >= MIN_CAP_CELLS:
            keep = trial
    return frozenset(keep)


def _raise_walls(grid) -> None:
    """Give every southward drop its cliff.

    A cap's south rim is the one face the camera sees, so the cells directly
    below it become stone. They are consumed from the terrace underneath -- the
    wall has to occupy real cells, exactly as it did when terraces were bands."""
    for (c, r), cell in sorted(grid.items(), key=lambda kv: -kv[0][1]):
        if cell.kind != GROUND:
            continue
        south = grid.get((c, r + 1))
        if south is None or south.kind != GROUND or south.level >= cell.level:
            continue
        drop = min(cell.level - south.level, MAX_DROP)
        for k in range(drop):
            below = grid.get((c, r + 1 + k))
            if below is None or below.kind != GROUND:
                break
            grid[(c, r + 1 + k)] = Cell(CLIFF, level=cell.level, drop=drop,
                                        row=k)


def _vstair_site(grid, c, r):
    """Is `(c, r)` the head of a straight flight? Needs solid wall in its own
    column and in both neighbours for the whole descent, terrace above and
    terrace below. Returns the drop, or `None`."""
    top = grid.get((c, r))
    if top is None or top.kind != CLIFF or top.row != 0:
        return None
    d = top.drop
    above, under = grid.get((c, r - 1)), grid.get((c, r + d))
    if above is None or above.kind != GROUND or above.level != top.level:
        return None
    if under is None or under.kind != GROUND or under.level != top.level - d:
        return None
    for k in range(d):
        for dx in (-1, 0, 1):
            nb = grid.get((c + dx, r + k))
            if nb is None or nb.kind != CLIFF:
                return None
    return d


def _ewstair_site(grid, c, r, side):
    """Is `(c, r)` the head of an east/west flight descending `side`?

    This wants the one-row jog the journal's diagram calls for::

        # > =        the wall has dropped on the exit side but not the entry
        = > #        ... and a row later, the other way round

    So the wall beside the flight starts a row earlier on the exit side than on
    the entry side, the upper terrace reaches the head from the entry side, and
    the lower terrace meets the foot from the exit side.

    The flight spans one row more than the wall is deep, so it eats a cell of
    terrace on the way past -- that is the jog, and it is why this cannot
    simply be a column of wall like a straight flight."""
    entry = 1 if side == "w" else -1
    d = None
    near = grid.get((c - entry, r))                 # exit side, wall starts here
    far = grid.get((c + entry, r + 1))              # entry side, a row later
    for w in (near, far):
        if w is None or w.kind != CLIFF or w.row != 0:
            return None
        d = w.drop if d is None else d
        if w.drop != d:
            return None
    head = grid.get((c + entry, r))                 # step on from up here
    foot = grid.get((c - entry, r + d))             # ... and off down there
    if head is None or head.kind != GROUND or head.level != near.level:
        return None
    if foot is None or foot.kind != GROUND or foot.level != near.level - d:
        return None
    above = grid.get((c, r - 1))
    if above is None or above.kind != GROUND or above.level != near.level:
        return None
    # the flight's own column must be free to take -- wall, or the terrace cell
    # the jog eats, but never another flight
    for k in range(d + 1):
        cell = grid.get((c, r + k))
        if cell is None or cell.kind not in (CLIFF, GROUND):
            return None
    return d


def _cut_flights(grid, rng, per_region: int, region: int = None,
                 spacing: int = None) -> None:
    """Cut ways up through the walls, using all four kinds of stair the tileset
    has: a straight flight in stone or in grass, and the east/west grass flight
    in either direction.

    Sites are *found* in the finished grid rather than forced into it -- with
    concentric caps there is no row of wall to plan against, and scanning means
    a site is valid by construction.

    Placement is then spread over a coarse grid of **regions** rather than
    drawn from one shuffled pile. A flat island-wide quota gets spent wherever
    the shuffle happens to fall, which on a large island reliably leaves whole
    stretches of rim -- the north especially, where the caps are widest --
    without a way up. A per-region quota guarantees every part of the coast has
    its own crossings."""
    region = REGION if region is None else region
    spacing = STAIR_SPACING if spacing is None else spacing
    buckets: dict = {}
    for (c, r), cell in list(grid.items()):
        if cell.kind not in (CLIFF, GROUND):
            continue
        found = []
        if cell.kind == CLIFF and cell.row == 0:
            d = _vstair_site(grid, c, r)
            if d:
                found.append((VSTAIR, rng.choice(("grass", "rock")), d))
        for side in ("w", "e"):
            d = _ewstair_site(grid, c, r, side)
            if d:
                found.append((EWSTAIR, side, d))
        if found:
            kind, tag, d = found[rng.randrange(len(found))]
            buckets.setdefault((c // region, r // region), []).append(
                (c, r, kind, tag, d))

    taken: list = []
    for key in sorted(buckets):
        here = buckets[key]
        rng.shuffle(here)
        cut = 0
        for c, r, kind, tag, d in here:
            if cut >= per_region:
                break
            if any(abs(c - tc) < spacing and abs(r - tr) < spacing
                   for tc, tr in taken):
                continue
            span = d if kind == VSTAIR else d + 1
            for k in range(span):
                grid[(c, r + k)] = Cell(kind, level=grid[(c, r)].level,
                                        drop=d, row=k, tag=tag)
            taken.append((c, r))
            cut += 1


def _link_levels(grid, rng) -> None:
    """Keep cutting flights until every plateau is reachable.

    `_cut_flights` places for looks, spreading crossings out; this places for
    need, so a cap whose only stair fell inside a lake or got roughened away is
    not left stranded."""
    for _ in range(16):
        parts = _components(grid)
        if len(parts) <= 1:
            return
        owner = {p: i for i, part in enumerate(parts) for p in part}
        cuts = []
        for (c, r), cell in grid.items():
            if cell.kind != CLIFF or cell.row != 0:
                continue
            d = _vstair_site(grid, c, r)
            if not d:
                continue
            if owner.get((c, r - 1)) == owner.get((c, r + d)):
                continue
            cuts.append((c, r, d))
        if not cuts:
            return
        c, r, d = cuts[rng.randrange(len(cuts))]
        tag = rng.choice(("grass", "rock"))
        for k in range(d):
            grid[(c, r + k)] = Cell(VSTAIR, level=grid[(c, r)].level,
                                    drop=d, row=k, tag=tag)


def _carve_lakes(grid, rng, count: int) -> None:
    """Flood a few blobs of a terrace to make inland lakes.

    A lake is only cut where it stays wholly inside one terrace and leaves the
    room connected -- water that walls a shelf off would be indistinguishable
    from a generation bug, and water lapping a cliff foot would need shoreline
    art the terrace boundary does not have."""
    ground = [p for p, cell in grid.items() if cell.kind == GROUND]
    if not ground:
        return
    for _ in range(count):
        seed = ground[rng.randrange(len(ground))]
        level = grid[seed].level
        blob = {seed}
        for _ in range(rng.randint(4, 14)):
            c, r = list(blob)[rng.randrange(len(blob))]
            nb = rng.choice(((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)))
            cell = grid.get(nb)
            if cell is not None and cell.kind == GROUND and cell.level == level:
                blob.add(nb)
        if len(blob) < 3:
            continue
        # never let a lake touch anything but its own terrace's ground
        edge = {(c + dx, r + dy) for c, r in blob
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))} - blob
        if any(grid.get(p) is not None
               and (grid[p].kind != GROUND or grid[p].level != level)
               for p in edge):
            continue
        saved = {p: grid[p] for p in blob}
        for p in blob:
            grid[p] = Cell(LAKE, level=level)
        if len(reachable(grid)) != sum(
                1 for cell in grid.values() if cell.kind in WALKABLE_KINDS):
            grid.update(saved)               # it cut the room in two; put it back


def _plan_stairs(plan, starts, cols, rng, per_wall):
    """Choose where each wall is crossed. Returns `[(wall_i, col, kind, tag)]`.

    A straight flight needs its own column and both neighbours to have the wall
    at the same row, so the flight is walled on both sides. An east/west flight
    instead *needs* the one-row jog the journal's diagram shows, so it forces
    its right-hand neighbour a row down (or up, descending east) and bridges the
    step."""
    picks = []
    for i in range(1, len(plan)):
        wall = starts[i]
        spots = list(range(2, cols - 2))
        rng.shuffle(spots)
        taken: list = []
        for c in spots:
            if len(taken) >= per_wall:
                break
            if any(abs(c - t) < 4 for t in taken):
                continue
            # A straight flight needs the wall flat across its own column and
            # both neighbours, so stone stands either side of it the whole way
            # down. An east/west flight instead needs exactly the one-row jog
            # the journal's diagram shows -- `# > =` over `= > #`.
            flat = wall[c - 1] == wall[c] == wall[c + 1]
            west = wall[c - 1] == wall[c] and wall[c + 1] == wall[c] + 1
            east = wall[c + 1] == wall[c] and wall[c - 1] == wall[c] + 1
            options = []
            if flat:
                options.append((VSTAIR, rng.choice(("grass", "rock"))))
            if west:
                options.append((EWSTAIR, "w"))
            if east:
                options.append((EWSTAIR, "e"))
            if not options:
                continue
            kind, tag = options[rng.randrange(len(options))]
            picks.append((i, c, kind, tag))
            taken.append(c)
        if not taken:
            # No stretch of this wall suited a crossing. Flatten a window in the
            # middle and put a straight flight there -- a wall with no way
            # through would strand everything above it.
            c = cols // 2
            wall[c - 1] = wall[c + 1] = wall[c]
            picks.append((i, c, VSTAIR, rng.choice(("grass", "rock"))))
    return picks


def _settle_walls(plan, starts, cols, rows) -> None:
    """Make the walls consistent before anything is cut through them.

    Walls wander and are cut by crevasses, so two of them can end up crossing
    and squeeze the terrace between them out of existence. Clamping each wall
    to leave its neighbours their minimum height fixes that.

    Note there is no longer any limit on how far a wall may move *between*
    columns. There used to be one, because a big sideways step left upper
    ground touching lower ground with no stone between. That only matters on a
    southward drop, which is still walled; east and west the plateau shows its
    flank, which its own edge tile draws. Lifting the limit is what lets a
    crevasse cut in sharply instead of as a shallow V."""
    n = len(plan)
    for _ in range(4):
        for c in range(cols):
            floor_row = 0
            for i in range(1, n):
                floor_row += plan[i - 1][1] + MIN_TERRACE_ROWS
                starts[i][c] = max(starts[i][c], floor_row)
            ceil_row = rows
            for i in range(n - 1, 0, -1):
                ceil_row -= MIN_TERRACE_ROWS + plan[i][1]
                starts[i][c] = min(starts[i][c], ceil_row)


def _stamp_stairs(grid, plan, laid, picks) -> bool:
    """Replace the cliff cells a chosen crossing occupies with stair cells.
    Returns whether every pick landed."""
    ok = True
    for i, c, kind, tag in picks:
        level, drop = plan[i - 1][0], plan[i][1]
        top = laid.get((i, c))
        span = drop if kind == VSTAIR else drop + 1
        if top is None or any((c, top + k) not in grid for k in range(span)):
            ok = False                       # the mask cut this crossing away
            continue
        for k in range(span):
            grid[(c, top + k)] = Cell(kind, level=level, drop=drop, row=k,
                                      tag=tag)
    return ok


def _face_the_sea(grid, mask) -> None:
    """No floating ground: a terrace cell with open sea directly south grows a
    wall under it, so the plateau visibly stands on something. Capped at
    `MAX_DROP` -- a level-3 shelf over water still shows two tiles of rock."""
    for (c, r), cell in list(grid.items()):
        if cell.kind != GROUND or cell.level <= 0:
            continue
        if (c, r + 1) in grid:
            continue
        # How far it has to fall: down to whatever the beach will be, or to
        # the sea if there is no beach here.
        drop = min(cell.level, MAX_DROP)
        for k in range(drop):
            grid[(c, r + 1 + k)] = Cell(CLIFF, level=cell.level, drop=drop,
                                        row=k)


# --- connectivity ---------------------------------------------------------

def walk_links(grid, pos) -> list:
    """Walkable cells reachable from `pos` in one step.

    Ground joins ground of the same level. A straight flight joins the terrace
    directly north of its top cell and the one directly south of its foot. An
    east/west flight joins the upper terrace beside its top cell and the lower
    terrace on the opposite side of its foot -- the entry and exit tiles the
    journal's diagram calls for."""
    cell = grid.get(pos)
    if cell is None or cell.kind not in WALKABLE_KINDS:
        return []
    c, r = pos
    out = []

    def ground(p, level):
        g = grid.get(p)
        if g is not None and g.kind == GROUND and g.level == level:
            out.append(p)

    def stair(p):
        g = grid.get(p)
        if g is not None and g.kind in (VSTAIR, EWSTAIR):
            out.append(p)

    if cell.kind == GROUND:
        for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            ground(p, cell.level)
        # ... plus any flight whose own end opens onto this cell. Asking the
        # flight keeps the relation symmetric instead of re-deriving it here.
        for p in ((c, r - 1), (c, r + 1), (c - 1, r), (c + 1, r)):
            g = grid.get(p)
            if g is not None and g.kind in (VSTAIR, EWSTAIR) \
                    and pos in walk_links(grid, p):
                out.append(p)
        return out

    # inside a flight: the cell above and below in the same stack
    stair((c, r - 1))
    stair((c, r + 1))
    if cell.kind == VSTAIR:
        if cell.row == 0:
            ground((c, r - 1), cell.level)
        if cell.row == cell.drop - 1:
            ground((c, r + 1), cell.level - cell.drop)
    else:
        # East/west flight. The wall jogs one row across it, so the upper
        # terrace reaches the flight's head from the side the wall has not
        # dropped yet, and the lower terrace meets its foot on the opposite
        # side -- the `= > #` / `# > =` pair in the journal's diagram. The head
        # and foot also open along the column, north onto the terrace above and
        # south onto the one below, exactly as a straight flight does.
        entry = 1 if cell.tag == "w" else -1     # "w" descends west, enters east
        if cell.row == 0:
            ground((c + entry, r), cell.level)
            ground((c, r - 1), cell.level)
        if cell.row == cell.drop:
            ground((c - entry, r), cell.level - cell.drop)
            ground((c, r + 1), cell.level - cell.drop)
    return out


def reachable(grid, start=None) -> set:
    """Every walkable cell reachable from `start` (or the lowest-then-westmost
    walkable cell, which is always on the outer shore)."""
    walk = [p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS]
    if not walk:
        return set()
    if start is None:
        start = min(walk, key=lambda p: (-p[1], p[0]))
    seen = {start}
    stack = [start]
    while stack:
        for nb in walk_links(grid, stack.pop()):
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return seen


def _wall_flight_sides(grid) -> None:
    """Put stone back beside any flight the beach opened up.

    Eroding the core to make room for the shore can take away the wall a
    flight was cut into, and the beach then fills that cell with sea-level
    ground -- leaving a staircase you could step onto sideways, halfway down.
    Anything touching a flight that is not one of its own two ends becomes
    wall again."""
    for pos, cell in list(grid.items()):
        if cell.kind not in (VSTAIR, EWSTAIR):
            continue
        ends = set(walk_links(grid, pos))
        c, r = pos
        for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            nb = grid.get(p)
            if (nb is not None and nb.kind == GROUND
                    and nb.level != cell.level and p not in ends):
                grid[p] = Cell(CLIFF, level=cell.level, drop=cell.drop,
                               row=cell.row)


def _components(grid) -> list[set]:
    """Walkable cells grouped into connected components, largest first."""
    todo = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    out = []
    while todo:
        part = reachable(grid, next(iter(todo)))
        out.append(part)
        todo -= part
    out.sort(key=len, reverse=True)
    return out


def _repair_links(grid, plan, laid, cols, rng) -> None:
    """Cut extra flights until the room is one connected piece.

    Terracing plus an eroded outline can strand a shelf -- its planned crossing
    fell outside the mask, or the wall wandered past it. Rather than throw the
    shelf away, look for a wall cell with one component directly above it and
    another directly below, and open a straight flight there."""
    for _ in range(12):
        parts = _components(grid)
        if len(parts) <= 1:
            return
        owner = {p: i for i, part in enumerate(parts) for p in part}
        cuts = []
        for (c, r), cell in grid.items():
            if cell.kind != CLIFF or cell.row != 0:
                continue
            above, below = grid.get((c, r - 1)), grid.get((c, r + cell.drop))
            if above is None or below is None:
                continue
            if above.kind != GROUND or below.kind != GROUND:
                continue
            if above.level != cell.level or below.level != cell.level - cell.drop:
                continue
            if owner.get((c, r - 1)) == owner.get((c, r + cell.drop)):
                continue
            # the flight's own column must be solid wall, and so must both
            # neighbours across the whole descent, or it would open sideways
            # onto the wrong level
            span = [(c + dx, r + k) for k in range(cell.drop)
                    for dx in (-1, 0, 1)]
            if any(grid.get(p, Cell("")).kind != CLIFF for p in span):
                continue
            cuts.append((c, r, cell))
        if not cuts:
            return                       # nothing left to join; prune will tidy
        c, r, cell = cuts[rng.randrange(len(cuts))]
        tag = rng.choice(("grass", "rock"))
        for k in range(cell.drop):
            grid[(c, r + k)] = Cell(VSTAIR, level=cell.level, drop=cell.drop,
                                    row=k, tag=tag)


def _prune_unreachable(grid) -> None:
    """Drop walkable pockets nothing can reach -- an eroded corner that ended up
    walled off, say. They become void rather than teasing the player with floor
    they cannot stand on."""
    walk = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    keep = reachable(grid)
    for p in walk - keep:
        del grid[p]
    # a wall with nothing left above it is not holding anything up
    for p, cell in list(grid.items()):
        if cell.kind == CLIFF and (p[0], p[1] - 1) not in grid:
            del grid[p]


# --- verification ---------------------------------------------------------

def check_grid(grid) -> list[str]:
    """Every invariant in the module docstring, as a list of complaints (empty
    when the grid is sound). Used by the tests and the ASCII dumper."""
    bad = []
    for (c, r), cell in grid.items():
        if cell.kind == GROUND:
            if cell.level > 0 and (c, r + 1) not in grid:
                bad.append(f"floating ground at ({c},{r}) level {cell.level}")
            # Only a drop to the *south* needs a wall: that is the face the
            # camera sees. A rise to the north, east or west is the back or
            # flank of a plateau, drawn by the higher terrace's own edge tile.
            south = grid.get((c, r + 1))
            if south is not None and south.kind == GROUND \
                    and south.level < cell.level:
                bad.append(f"level drops {cell.level}->{south.level} south of "
                           f"({c},{r}) with no wall between")
            for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
                nb = grid.get(p)
                if nb is not None and nb.kind == GROUND \
                        and abs(nb.level - cell.level) > MAX_DROP:
                    bad.append(f"levels {cell.level}/{nb.level} touch at "
                               f"({c},{r}) -- more than {MAX_DROP} apart")
        if cell.kind in (VSTAIR, EWSTAIR):
            if cell.drop > MAX_DROP:
                bad.append(f"stair drop {cell.drop} at ({c},{r})")
            # a flight must meet other levels only at its own two ends
            ends = set(walk_links(grid, (c, r)))
            for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
                nb = grid.get(p)
                if (nb is not None and nb.kind == GROUND
                        and nb.level != cell.level and p not in ends):
                    bad.append(f"flight at ({c},{r}) is open to level "
                               f"{nb.level} at its side")
    walk = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    if walk and reachable(grid) != walk:
        bad.append(f"{len(walk - reachable(grid))} unreachable walkable cells")
    return bad


_GLYPH = {GROUND: "=", CLIFF: "#", VSTAIR: "0", LAKE: "~"}


def to_ascii(grid) -> str:
    """The grid in the journal's own notation -- the quickest way to eyeball a
    generated room."""
    if not grid:
        return ""
    cs = [p[0] for p in grid]
    rs = [p[1] for p in grid]
    lines = []
    for r in range(min(rs), max(rs) + 1):
        line = []
        for c in range(min(cs), max(cs) + 1):
            cell = grid.get((c, r))
            if cell is None:
                line.append(" ")
            elif cell.kind == EWSTAIR:
                line.append(">" if cell.tag == "w" else "<")
            else:
                line.append(_GLYPH.get(cell.kind, "?"))
        lines.append(" ".join(line))
    return "\n".join(lines)
