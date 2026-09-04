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


def room_of(layout, x: float, y: float):
    """The island whose floor holds the point, or `None`."""
    px = config.TILE_PX
    for r in layout.rooms:
        rr = r.rect
        if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                and (int((x - rr.left) // px), int((y - rr.top) // px)) in r.cells):
            return r
    return None


def over_island(layout, x: float, y: float) -> bool:
    """Is the point over *any* cell of an island's height map -- ground, the
    cliff wall holding a terrace up, a flight, or an inland lake -- rather
    than over the open sea?

    The flying rule (`GameMap.is_walkable(flying=True)`). A body that walks
    needs `room_of`, the walkable subset; a body that flies only needs the
    island to be underneath it, so its own pond does not stop it dead. The
    sea stays the sea: a boss out over the water is one the player cannot
    fight, and the arena has to remain a fight.
    """
    px = config.TILE_PX
    for r in layout.rooms:
        rr = r.rect
        if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                and (int((x - rr.left) // px), int((y - rr.top) // px)) in r.grid):
            return True
    return False


def in_corridor(layout, x: float, y: float) -> bool:
    """On a plank bridge -- the narrow link between islands that gets
    clearance leniency in the navigation grid, so the big rare enemies can
    still thread it."""
    return any(c.rect.collidepoint(x, y) for c in layout.corridors)


def point_on_floor(layout, x: float, y: float) -> bool:
    """An island cell, or a bridge."""
    return room_of(layout, x, y) is not None or in_corridor(layout, x, y)


def inset_at(layout, x: float, y: float) -> int:
    """How far inside its own terrace the point stands, in px. `CAP` off any
    island floor -- on a bridge -- because a bridge is flat and carries no
    level boundary to keep away from."""
    room = room_of(layout, x, y)
    if room is None:
        return terrain_inset.CAP
    return terrain_inset.world_at(room, x, y)


def inset_ok(layout, x: float, y: float, margin: float) -> bool:
    """Is the point at least `margin` px inside its own terrace? A margin of
    zero (or less) switches the rule off."""
    if margin <= 0.0:
        return True
    return inset_at(layout, x, y) >= margin
