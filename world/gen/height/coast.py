"""The island's outline: where land meets sea.

The coastline is the first stage of `build_grid` and the
only one whose parameters are a named preset -- see
`config.HEIGHTMAP_COAST_PRESETS`, and `world/terrain/biome.py` for the same idea
applied to tilesets.
"""
from __future__ import annotations

from world.gen.height.const import _NB

# --- terrace planning -----------------------------------------------------

def coast_shape(name: str = None, presets: dict = None,
                default: str = None) -> dict:
    """The coastline's shape parameters, by preset name.

    How ragged a shore is. `classic` is the older, squarer coast, kept one
    setting away and pinned by a test that compares whole generated worlds
    rather than judging by eye. The preset is a dict rather than four loose
    constants because each **topography** has its own coastline: a "castle"
    island is described as more squared, which is this table with a low
    margin, not a new algorithm."""
    if presets is None:
        # Generation passes its settings' table; a test driving one stage
        # alone gets today's config.
        from game import config
        presets = config.HEIGHTMAP_COAST_PRESETS
        default = default or config.HEIGHTMAP_COAST_PRESET
    if default is None:
        from game import config
        default = config.HEIGHTMAP_COAST_PRESET
    return presets[name or default]




def coast_mask(cols: int, rows: int, rng, margin: int = 3,
               keep: int = 0, shape=None) -> frozenset:
    """An irregular outer shape for a room -- its coastline.

    Each of the four sides gets its own clamped random walk of inset, so the
    island's silhouette wanders instead of ruling four straight lines. This is
    what breaks the "fixed staircase" read: the terraces still band north to
    south, but they no longer all start and stop in the same column, so the
    coast cuts across them at a different place on every row.

    It needs no new art either. A terrace's east and west edges are grass
    meeting open water, which the `slots.raised` fringe already draws -- only a
    *southward* drop needs a cliff face, and the bands still run that way.

    `keep` is a hard band of void left inside the rect on all four sides, which
    the random walk cannot eat into. The walk on its own leaves *no* guaranteed
    inset -- measured over 14 seeds, land reached the rect edge on every side --
    so a room rect is not a safe proxy for where its island is. That in turn is
    what stopped neighbouring rooms being packed any closer: rects had to stay
    apart because land could be anywhere in them. With a guaranteed band the
    rects can overlap by up to `2 * keep` on each side and the islands still
    cannot meet.
    """
    shape = shape or coast_shape()
    inner = frozenset((c, r)
                      for c in range(keep, max(keep, cols - keep))
                      for r in range(keep, max(keep, rows - keep)))
    # Erosion compounds: the four insets, then the bays, then the de-spiking
    # can between them eat most of a room, leaving an islet too small to carry
    # terraces and with bridges running to almost nothing. Back the margin off
    # until enough of the room survives.
    for attempt in range(margin, -1, -1):
        out = _coast_once(cols, rows, rng, attempt, shape) & inner
        if len(out) >= shape["mask_keep"] * cols * rows:
            return out
    return inner




def _coast_once(cols: int, rows: int, rng, margin: int, shape=None) -> frozenset:
    shape = shape or coast_shape()
    hold, cap = tuple(shape["hold"]), shape["run_cap"]
    north_margin = max(0, margin + shape["north_delta"])
    west = _walk(rows, rng, margin, hold, cap)
    east = _walk(rows, rng, margin, hold, cap)
    north = _walk(cols, rng, north_margin, hold, cap)
    south = _walk(cols, rng, margin, hold, cap)
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
                       for dx, dy in _NB)]
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




def _walk(n: int, rng, hi: int, hold=(2, 3), run_cap: int = 0) -> list[int]:
    """An inset per column / row, wandering over `[0, hi]`.

    Two things stop this looking like a ruled line. Each value is held for a
    short run, because stepping every column gives a comb of one-tile spikes
    rather than headlands. And the step is pulled back toward mid-range, since
    a free random walk drifts to one end and then hugs it -- which is exactly
    how the first attempt produced a straight west coast.

    Neither was enough. Measured on the shipped worlds, 24% of west-shore runs
    were five tiles or longer with a hard spike at twelve-plus, and the cause
    was not the hold at all: it was **clamping at a small amplitude**. With
    `hi` at 4 and steps of one or two, the walk reaches 0 or `hi` constantly
    and the clamp pins it there for hold after hold. The north wall, which used
    a smaller `hi` still, had the worse histogram -- exactly as that predicts.

    `run_cap` is the brief's rule: never hold a value for more than this many
    positions, and make sure the step that follows actually moves. Without the
    second half the clamp can hand back the same value and the cap does
    nothing. It is worth little on its own -- forcing a step on a walk with no
    room to wander just draws a one-tile sawtooth along a straight line -- which
    is why the preset raises `hi` at the same time."""
    if hi <= 0:
        return [0] * n
    lo_hold, hi_hold = hold
    if run_cap:
        lo_hold = min(lo_hold, run_cap)
        hi_hold = min(hi_hold, run_cap)
    out = []
    v = rng.randint(0, hi)
    while len(out) < n:
        out.extend([v] * rng.randint(lo_hold, hi_hold))
        pull = (hi / 2 - v) / max(1, hi)          # -0.5 .. 0.5
        step = rng.choice((-2, -1, -1, 1, 1, 2)) + round(pull * 2)
        nxt = max(0, min(hi, v + step))
        if run_cap and nxt == v:
            # The clamp swallowed the step. Move one the only way there is
            # room to, so a capped run is really capped.
            nxt = v - 1 if v >= hi else v + 1
        v = nxt
    return out[:n]




def _despike(mask: set) -> frozenset:
    """Trim the coast until no tile is left clinging on by a single side.

    A one-tile peninsula or isthmus reads as a rendering fault rather than
    land, and is too narrow to walk down anyway."""
    keep = set(mask)
    while True:
        thin = {(c, r) for c, r in keep
                if sum(((c + dx, r + dy) in keep)
                       for dx, dy in _NB) < 2}
        if not thin:
            return frozenset(keep)
        keep -= thin


