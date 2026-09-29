"""Where the floor is.

The one answer to "is this world point on something a body can stand on",
which island that is, and how far inside its terrace the point stands. Read
by the collider (`GameMap`) every frame and by the navigation grid once at
build.

The two used to carry a copy each, documented as mirrors of one another,
with a test sampling both to catch drift. Three bugs in one milestone came
from mirrored rules disagreeing, so one function with two callers replaced
the test.

A room's floor is tested by its **cells**, not its bounding box: island
rects overlap in the void, so a point inside two boxes belongs to whichever
one has a cell there -- and no two islands share a land cell.
"""
from __future__ import annotations

from game import config
from world.rules import inset as terrain_inset


class FloorIndex:
    """Which islands and bridges can hold a point, by square of the world
    (ENT-018.3).

    `room_of` and `in_corridor` test every island and every bridge in turn,
    and the collider asks them about six times per body per frame. This
    lists, for each `SQUARE` px square, the islands and bridges whose bounds
    reach it, **in `layout` order**, so the scans test only those, with the
    same condition, in the same order. Anything outside the square fails the
    bounds test anyway, so the first match, and so every answer, is the one
    the full scan gives.

    The squares are keyed the way each test reads a point. An island's
    bounds are compared as floats, so its square is the floored one. A
    bridge goes through `Rect.collidepoint`, which truncates a float toward
    zero (-0.5 counts as 0), so its square is the truncated one. A point
    that cannot be keyed (nan, inf) is given the whole list, which is the
    old answer.

    Built from a finished layout. Only world generation edits islands,
    cells or bridges, and the collider builds this on first use, after
    generation has returned; the navigation grid's build does not use it.
    """
    SQUARE = 256

    def __init__(self, layout) -> None:
        s = self.SQUARE
        self._layout = layout
        self._rooms: dict[tuple[int, int], tuple] = {}
        self._corridors: dict[tuple[int, int], tuple] = {}
        for into, items in ((self._rooms, layout.rooms), (self._corridors, layout.corridors)):
            lists: dict[tuple[int, int], list] = {}
            for item in items:
                rr = item.rect
                # `right // s` and `bottom // s` inclusive: a superset of the
                # squares the half-open bounds reach, which costs nothing.
                for sx in range(rr.left // s, rr.right // s + 1):
                    for sy in range(rr.top // s, rr.bottom // s + 1):
                        lists.setdefault((sx, sy), []).append(item)
            into.update((k, tuple(v)) for k, v in lists.items())

    def rooms_at(self, x: float, y: float):
        try:
            key = (int(x // self.SQUARE), int(y // self.SQUARE))
        except (ValueError, OverflowError):
            return self._layout.rooms
        return self._rooms.get(key, ())

    def corridors_at(self, x: float, y: float):
        try:
            key = (int(x) // self.SQUARE, int(y) // self.SQUARE)
        except (ValueError, OverflowError):
            return self._layout.corridors
        return self._corridors.get(key, ())


def room_of(layout, x: float, y: float, index: FloorIndex | None = None):
    """The island whose floor holds the point, or `None`. `index` narrows
    the scan to the islands that can hold it, same order, same answer."""
    px = config.TILE_PX
    for r in layout.rooms if index is None else index.rooms_at(x, y):
        rr = r.rect
        if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                and (int((x - rr.left) // px), int((y - rr.top) // px)) in r.cells):
            return r
    return None


def in_corridor(layout, x: float, y: float, index: FloorIndex | None = None) -> bool:
    """On a plank bridge -- the narrow link between islands that gets
    clearance leniency in the navigation grid, so the big rare enemies can
    still thread it."""
    corridors = layout.corridors if index is None else index.corridors_at(x, y)
    return any(c.rect.collidepoint(x, y) for c in corridors)


def point_on_floor(layout, x: float, y: float, index: FloorIndex | None = None) -> bool:
    """An island cell, or a bridge."""
    return (room_of(layout, x, y, index) is not None
            or in_corridor(layout, x, y, index))


def inset_at(layout, x: float, y: float, index: FloorIndex | None = None) -> int:
    """How far inside its own terrace the point stands, in px. `CAP` off any
    island floor -- on a bridge -- because a bridge is flat and carries no
    level boundary to keep away from."""
    room = room_of(layout, x, y, index)
    if room is None:
        return terrain_inset.CAP
    return terrain_inset.world_at(room, x, y)


def inset_ok(layout, x: float, y: float, margin: float) -> bool:
    """Is the point at least `margin` px inside its own terrace? A margin of
    zero (or less) switches the rule off."""
    if margin <= 0.0:
        return True
    return inset_at(layout, x, y) >= margin
