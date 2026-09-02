"""How far inside its own terrace a point stands.

A leaf module, like `world/frontier.py` and for the same reason: it is read at
generation, at bake and (later) by the collider, and `world/terrain` already
depends on `world/gen`, so it can live in neither package.

The problem: a body's position is a point, but a body is a disc, and a sprite
is wider still. Standing with your centre one pixel inside a terrace puts most
of you over the floor below, which reads as the two levels bleeding into each
other. `frontier.py` already keeps *props* off the boundary; this is the same
idea generalised into something a moving body can be asked about cheaply, every
frame.

**What counts as a frontier here is a level change and nothing else.** A
neighbouring terrace at another level counts, and so does a cliff face, which
is a level change with stone in it. Water, lake and open sea do not: a shore is
not a floor boundary, and insetting every coastline would take a slice off
every island for no reading. That is a deliberate difference from
`frontier.py`, whose prop rules *do* treat a lake edge as a frontier -- the two
answer different questions and are meant to.

The field is built once per room, right after the room's grid is final and
before anything is baked, scattered or spawned, so that every later stage reads
one answer instead of deriving its own. It stores, per sample, the distance in
world pixels to the nearest point of a different level, clamped to `CAP`.
Consumers ask `clear(x, y, margin)` with whatever margin they want.

Sampling, not sampling points: `frontier_clear` in `frontier.py` tests eight
rim points at exactly +/- margin, which has a hole -- a box can straddle a
narrow strip and miss every sample. A distance field has no such hole, which is
the other reason to build one.
"""
from __future__ import annotations

import math
from array import array

from world.layout import CLIFF, VSTAIR, EWSTAIR, WALKABLE_KINDS

# Sample pitch in world pixels. 8 is a quarter of a tile edge and matches the
# props' `decor_placement.edge_inset`, so the two rules can never disagree by
# more than half a sample.
STEP = 8
# Distances are stored in one byte. Nothing asks a question past this, and the
# clamp is what keeps the field to ~90 KB on the largest island.
CAP = 255

_SQRT2 = 1.4142135623730951

# A crossing exists to straddle a frontier, so the margin cannot apply to it.
# The exemption reaches one tile past the unit in every direction: a body has
# to be able to stand on the landing and line itself up, and the widest one in
# the game is 46 px of radius against a 64 px tile.
FLIGHT_SLACK = 1


class InsetField:
    """Distance to the nearest different-level point, on a `step` px lattice.

    Coordinates are **room-relative pixels**, not world ones, and deliberately:
    a room's `rect` is still being moved when the field is built -- the packing
    settles island positions after `_build_room_grids` -- so an absolute origin
    baked in here goes stale by the time anything reads it. The grid is
    room-relative for the same reason, and this matches it. `world_clear`
    below does the conversion for callers holding a world point.
    """

    __slots__ = ("step", "cols", "rows", "data", "edge", "exempt", "px")

    def __init__(self, step, cols, rows, data, edge, exempt, px):
        self.step = step
        self.cols = cols
        self.rows = rows
        # Distance to the nearest floor of another level, or to stone.
        self.data = data
        # Distance to the nearest thing that is not floor at all -- water,
        # lake, open sea, the edge of the island. A separate channel because
        # the two consumers want different answers: a body may stand at the
        # water's edge, a prop may not.
        self.edge = edge
        # Room-relative tiles the margin does not apply to at all: the flights
        # and their landings. Held as tiles rather than baked into `data`
        # because it is a rule about *movement*, not about geometry -- a prop
        # has no business standing on a staircase either way.
        self.exempt = exempt
        self.px = px

    def at(self, rx: float, ry: float) -> int:
        """Distance in px from a room-relative point to the nearest other level.

        The **minimum** over the four samples bracketing the point, not the one
        it happens to land in. A sample stores the distance measured at its own
        centre, so reading it raw over-reports for a point near the far corner
        of that sample -- by up to 9 px in a measured sweep, which is more than
        the margin itself. Taking the neighbouring samples into account bounds
        the error to under half a step and, as importantly, makes it
        *conservative*: this can hold a body a pixel or two further inside its
        terrace than asked, and never lets one stand closer.

        Off the field answers `CAP`: a point outside this room is not this
        room's boundary problem, and the caller has already decided the point
        is floor.
        """
        return self._min4(self.data, rx, ry)

    def _min4(self, plane, rx: float, ry: float) -> int:
        step = self.step
        c0 = int((rx / step - 0.5) // 1)
        r0 = int((ry / step - 0.5) // 1)
        cols, rows = self.cols, self.rows
        best = CAP
        for row in (r0, r0 + 1):
            if row < 0 or row >= rows:
                continue
            base = row * cols
            for col in (c0, c0 + 1):
                if col < 0 or col >= cols:
                    continue
                v = plane[base + col]
                if v < best:
                    best = v
        return best

    def edge_at(self, rx: float, ry: float) -> int:
        """As `at`, for the distance to the nearest non-floor."""
        return self._min4(self.edge, rx, ry)

    def clear(self, rx: float, ry: float, margin: float) -> bool:
        """Is a room-relative point at least `margin` px inside its terrace?

        The movement question: level changes only, and a crossing is exempt.
        """
        if self.exempt:
            step = self.px
            if (int(rx // step), int(ry // step)) in self.exempt:
                return True
        return self.at(rx, ry) >= margin

    def prop_clear(self, rx: float, ry: float, margin: float) -> bool:
        """Is it `margin` px clear of *any* frontier -- a level change or the
        water's edge?

        The placement question. A prop standing at a shoreline reads as
        floating on the sea, so `world/frontier.py`'s rules have always counted
        water; a body walking to the water's edge reads as standing on a beach,
        so the movement rule does not. No exemption here: nothing is placed on
        a staircase on purpose.
        """
        return (self.at(rx, ry) >= margin
                and self.edge_at(rx, ry) >= margin)


def _levels_and_seeds(room, px, step, cols, rows):
    """Per sample: its own level, and whether it is a frontier for other levels.

    One pass over the lattice rather than one per level, because the tile
    lookup is the expensive part.
    """
    own = array("h", [-1]) * (cols * rows)
    kinds = array("b", [0]) * (cols * rows)      # 1 = cliff, 2 = flight
    grid = room.grid
    half = step * 0.5
    for row in range(rows):
        y = row * step + half
        trow = int(y // px)
        base = row * cols
        for col in range(cols):
            x = col * step + half
            cell = grid.get((int(x // px), trow))
            if cell is None:
                continue
            if cell.kind == CLIFF:
                kinds[base + col] = 1
            elif cell.kind in WALKABLE_KINDS:
                own[base + col] = cell.level
                if cell.kind in (VSTAIR, EWSTAIR):
                    kinds[base + col] = 2
    return own, kinds


def _chamfer(seed, cols, rows, step) -> array:
    """Two-pass (1, sqrt2) chamfer distance in px from the seeded samples.

    The same shape as `NavField._clearance_transform`: no queue, deterministic,
    and accurate enough at this pitch that the error is under a pixel.
    """
    big = float(CAP)
    d = array("f", [big]) * (cols * rows)
    diag = step * _SQRT2
    fstep = float(step)
    for i, s in enumerate(seed):
        if s:
            d[i] = 0.0
    for row in range(rows):
        base = row * cols
        up = base - cols
        for col in range(cols):
            i = base + col
            v = d[i]
            if v == 0.0:
                continue
            if row:
                w = d[up + col] + fstep
                if w < v:
                    v = w
                if col:
                    w = d[up + col - 1] + diag
                    if w < v:
                        v = w
                if col + 1 < cols:
                    w = d[up + col + 1] + diag
                    if w < v:
                        v = w
            if col:
                w = d[i - 1] + fstep
                if w < v:
                    v = w
            d[i] = v
    for row in range(rows - 1, -1, -1):
        base = row * cols
        dn = base + cols
        for col in range(cols - 1, -1, -1):
            i = base + col
            v = d[i]
            if v == 0.0:
                continue
            if row + 1 < rows:
                w = d[dn + col] + fstep
                if w < v:
                    v = w
                if col:
                    w = d[dn + col - 1] + diag
                    if w < v:
                        v = w
                if col + 1 < cols:
                    w = d[dn + col + 1] + diag
                    if w < v:
                        v = w
            if col + 1 < cols:
                w = d[i + 1] + fstep
                if w < v:
                    v = w
            d[i] = v
    return d


def build(room, px: int, step: int = STEP) -> InsetField | None:
    """The field for one room, or `None` where there is nothing to measure.

    A room with no height grid -- the flat LD-8 world -- has no level changes
    at all, so it gets no field and every query against it answers "clear".
    """
    if not room.grid or not room.cells:
        return None
    levels = {cell.level for cell in room.grid.values()
              if cell.kind in WALKABLE_KINDS}
    if len(levels) < 2:
        # Single-terrace island: a cliff can still face the sea off its south
        # rim, but there is no *floor* boundary anywhere on it, and water is
        # explicitly not a frontier here.
        cliffs = any(cell.kind == CLIFF for cell in room.grid.values())
        if not cliffs:
            return None
    cols = max(1, math.ceil(room.rect.width / step))
    rows = max(1, math.ceil(room.rect.height / step))
    own, kinds = _levels_and_seeds(room, px, step, cols, rows)

    n = cols * rows
    out = array("B", [CAP]) * n
    seed = array("b", [0]) * n
    for level in sorted(levels):
        # Seeds for *this* terrace: stone, and any floor that is not it.
        for i in range(n):
            o = own[i]
            seed[i] = 1 if (kinds[i] == 1 or (o >= 0 and o != level)) else 0
        if not any(seed):
            continue
        d = _chamfer(seed, cols, rows, step)
        # The chamfer measures centre to centre, but what a body cares about is
        # the *boundary*, which lies half a step short of the first sample of
        # the other terrace: a sample sitting right against the edge is 8 px
        # from the neighbouring centre and 4 px from the edge itself. Without
        # this correction the nearest possible sample already scores a full
        # step and an 8 px margin forbids nothing at all.
        half = step * 0.5
        for i in range(n):
            if own[i] == level:
                v = d[i] - half
                out[i] = 0 if v <= 0 else (CAP if v >= CAP else int(v))

    # The second channel: distance to anything that is not floor. Water, the
    # open sea and stone all seed it, which is what makes a prop keep off a
    # shoreline as well as off a level change.
    for i in range(n):
        seed[i] = 1 if own[i] < 0 else 0
    edge = array("B", [CAP]) * n
    if any(seed):
        d = _chamfer(seed, cols, rows, step)
        half = step * 0.5
        for i in range(n):
            if own[i] >= 0:
                v = d[i] - half
                edge[i] = 0 if v <= 0 else (CAP if v >= CAP else int(v))

    return InsetField(step, cols, rows, out, edge, _flight_tiles(room), px)


def _flight_tiles(room) -> frozenset:
    """The tiles the margin does not apply to: every flight cell and every tile
    within `FLIGHT_SLACK` of one.

    A crossing *is* a level boundary you are meant to walk through, so a margin
    there would seal it -- and sealing it would not be visible as a bug, only
    as an island whose stairs mysteriously never get used. The slack covers the
    landing a body has to stand on to line up with the unit; the widest body in
    the game is 46 px of radius against a 64 px tile.
    """
    out = set()
    for (col, row), cell in room.grid.items():
        if cell.kind not in (VSTAIR, EWSTAIR):
            continue
        for dc in range(-FLIGHT_SLACK, FLIGHT_SLACK + 1):
            for dr in range(-FLIGHT_SLACK, FLIGHT_SLACK + 1):
                out.add((col + dc, row + dr))
    return frozenset(out)


def world_clear(room, wx: float, wy: float, margin: float) -> bool:
    """Is the world point `(wx, wy)` at least `margin` px inside its terrace?

    The movement question: level changes only, crossings exempt. Tolerates a
    room with no field at all -- the flat world, and any island with a single
    terrace and no stone -- by answering "clear", which is what "there is no
    level boundary here" means.
    """
    field = room.inset
    if field is None:
        return True
    return field.clear(wx - room.rect.x, wy - room.rect.y, margin)


def body_inset() -> float:
    """The terrace margin a body's centre must keep, in pixels.

    Read from `data/terrain.json` -- no default in code, which is this
    project's standing rule for tuning. Both authorities that enforce it call
    this: the collider in `world/map.py` and the baked step mask in
    `world/pathfinding.py`. They have drifted apart twice this milestone by
    each deriving their own answer, so there is exactly one place to read it.
    Zero switches the rule off.
    """
    try:
        from game.content import get_content
        return float(get_content().terrain["frontier"]["body_inset"])
    except Exception:
        return 0.0


def world_at(room, wx: float, wy: float) -> int:
    """How far inside its own terrace the world point stands, in pixels.

    `CAP` where there is no field or the point is on a crossing, which is the
    same "no boundary here" answer `world_clear` gives. Callers want the number
    rather than the verdict when they are asking whether a body already inside
    the margin is at least moving *out* of it.
    """
    field = room.inset
    if field is None:
        return CAP
    rx, ry = wx - room.rect.x, wy - room.rect.y
    if field.exempt and (int(rx // field.px), int(ry // field.px)) in field.exempt:
        return CAP
    return field.at(rx, ry)


def world_prop_clear(room, wx: float, wy: float, margin: float) -> bool:
    """Is the world point clear of *any* frontier by `margin` px?

    The placement question: level changes and the water's edge both count.
    """
    field = room.inset
    if field is None:
        return True
    return field.prop_clear(wx - room.rect.x, wy - room.rect.y, margin)
