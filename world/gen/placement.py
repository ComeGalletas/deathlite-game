"""Where each island sits and how big it is.

Split out of `world/gen/__init__.py`, which had become the pipeline plus two
large stages. These three run between the role assignment and the grids: the
topography record decides a room's size, and the offset then moves it off the
centre of its lattice cell.
"""
from __future__ import annotations

from game import config
from world.gen.rooms import _cell_rect

def topography_of(room) -> dict:
    """The room's topography record, defaulting to the first weighted entry so
    a room built before `assign_topography` ran still has somewhere to read
    from."""
    table = config.HEIGHTMAP_TOPOGRAPHIES
    if room.topography in table:
        return table[room.topography]
    return next(spec for spec in table.values() if spec.get("weight", 0) > 0)




def _resize_by_topography(rooms) -> None:
    """Shrink or grow each room's rect to its topography's `size`.

    Done by resizing the finished rect rather than by drawing a different size
    up front, because the topography cannot be known until the tree is grown and
    the boss island identified -- and that happens after the rooms are built.
    The rect keeps its centre and is re-snapped to the world tile grid, which is
    the same guarantee the original placement makes: a room off the lattice
    cannot share a tile with its neighbour, and a bridge between them lands
    mid-tile at one end.

    Every dimension stays **even** in tiles. An odd one puts the centred rect
    half a tile off the grid, and the snap would then move the island rather
    than resize it.
    """
    if not config.HEIGHTMAP_ROOMS:
        return
    px = config.TILE_PX
    for room in rooms:
        scale = topography_of(room).get("size", 1.0)
        if scale == 1.0:
            continue
        w, h = room.tile_dims
        nw = max(8, int(round(w * scale / 2)) * 2)
        nh = max(8, int(round(h * scale / 2)) * 2)
        centre = room.rect.center
        room.rect.size = (nw * px, nh * px)
        room.rect.center = centre
        room.rect.x = round(room.rect.x / px) * px
        room.rect.y = round(room.rect.y / px) * px




def _offset_in_chunk(rooms, chunk, rng) -> None:
    """Nudge each island off the centre of its lattice cell.

    Centring every room made the world read as a grid of islands however ragged
    their coasts became, and it wasted the space a smaller island leaves in its
    cell. The bound is what keeps the packing guarantee intact rather than
    weakening it: **a rect may overhang its own chunk by at most one tile on
    each side**, which is exactly what a full-size room already does, since the
    chunk is deliberately two tiles narrower than the largest room. Two adjacent
    rooms therefore overlap by at most two tiles, and `HEIGHTMAP_COAST_KEEP`
    holds each island two tiles inside its own rect, so their land can never
    meet.

    Bounding the *rect against its chunk* rather than deriving a slack from the
    nominal sizes is deliberate. The first cut computed `(chunk - room) // 2`,
    which is wrong for an odd-width room: centring one leaves it half a tile off
    the lattice, the snap moves it, and the offset then stacks on top of that.
    Measured, that produced two shared land cells between neighbouring islands
    -- the exact failure the guarantee exists to prevent.

    A full-size room has no room to move and is left alone; a small island, at
    about 37 tiles in a 50-tile cell, gets six tiles of travel each way, which
    is where the variety actually comes from. Offsets are drawn after the
    resize, because how much slack a room has depends on the size its
    topography settled on.
    """
    if not config.HEIGHTMAP_ROOMS:
        return
    px = config.TILE_PX
    for room in rooms:
        cell = _cell_rect(room.cell, chunk)
        lo_x = ((cell.left - px) - room.rect.left) // px
        hi_x = ((cell.right + px) - room.rect.right) // px
        lo_y = ((cell.top - px) - room.rect.top) // px
        hi_y = ((cell.bottom + px) - room.rect.bottom) // px
        lo_x, hi_x = _toward_neighbours(room, rooms, 0, lo_x, hi_x)
        lo_y, hi_y = _toward_neighbours(room, rooms, 1, lo_y, hi_y)
        if lo_x <= hi_x:
            room.rect.x += rng.randint(lo_x, hi_x) * px
        if lo_y <= hi_y:
            room.rect.y += rng.randint(lo_y, hi_y) * px


def _toward_neighbours(room, rooms, axis, lo, hi):
    """Narrow an offset range so an island never drifts *away* from the
    islands it is linked to.

    The offset is what gives the world its variety, and it is also what
    lengthened the bridges: two neighbours are free to move apart inside their
    own cells, and a crossing that started at the lattice spacing ends up ten
    tiles longer. A cap on bridge length cannot fix that -- the long ones are
    already taking the shortest lane they have, measured -- so it has to be
    fixed where the distance is created.

    The rule is deliberately weak: it removes the half of the range that opens
    the gap, and only when every linked neighbour is on the same side of this
    axis. A room with neighbours both east and west keeps its full range,
    because moving either way shortens one crossing and lengthens the other.
    """
    sides = {(rooms[n].cell[axis] > room.cell[axis])
             - (rooms[n].cell[axis] < room.cell[axis])
             for n in room.neighbors}
    sides.discard(0)
    if len(sides) != 1:
        return lo, hi                   # pulled both ways, or not linked here
    return (0, hi) if sides.pop() > 0 else (lo, 0)


