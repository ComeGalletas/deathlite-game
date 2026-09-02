"""Terrace frontiers: where a prop may stand relative to a level change.

A leaf module, imported by both `world/gen/scatter.py` (obstacles, at
generation) and `world/terrain/decor.py` (clutter, at bake). It is deliberately
free of every other world module -- `world/terrain` already depends on
`world/gen`, so putting this in either package would close a cycle. The same
trick `world/gen/height/const.py` plays for the height stages.

Everything here reads a `Room`'s `grid` / `cells` / `rect` and nothing else, and
every rule answers trivially "clear" for a room with no grid. The flat LD-8
world has none, is pinned seed by seed in its tests, and is untouched by all of
this.

The problem being solved: an island's terraces bake into a **single** ground
surface (`world/terrain/bake.py`), composited before any sprite is drawn. A
prop standing below a terrace therefore paints over that terrace's tiles no
matter how the depth layer sorts it. Sorting cannot fix that. Not standing
there can, which is why these are placement rules.
"""
from __future__ import annotations

ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))
AROUND = ((1, 0), (1, 1), (0, 1), (-1, 1),
          (-1, 0), (-1, -1), (0, -1), (1, -1))


def cell_level(room, pos):
    """Level of a walkable room cell, or `None` where nothing walkable stands.

    Water and void both answer `None`, so every rule below reads a lake edge
    and a coastline as the same kind of frontier that a level change is.
    """
    cell = room.grid.get(pos)
    return cell.level if cell is not None and pos in room.cells else None


def tile_level(room, wx: float, wy: float, px: int):
    """Level of the terrace a world point falls on, or `None` off the floor."""
    return cell_level(room, (int((wx - room.rect.x) // px),
                            int((wy - room.rect.y) // px)))


def interior_cells(room):
    """Cells a prop may stand on: floor whose four orthogonal neighbours are
    floor *of the same terrace*.

    The test this replaces asked only whether a neighbour was in `room.cells` --
    the walkable set across every level of the island -- so a cell at the foot
    of a terrace read as fully interior and a prop could stand hard against a
    level change. `Room.grid` is what knows the levels; a legacy room has none
    and keeps the membership test exactly as it was.
    """
    if not room.cells:
        return None
    if not room.grid:
        return [c for c in sorted(room.cells)
                if all((c[0] + dc, c[1] + dr) in room.cells for dc, dr in ORTHO)]
    out = []
    for c in sorted(room.cells):
        level = cell_level(room, c)
        if level is None:
            continue
        if all(cell_level(room, (c[0] + dc, c[1] + dr)) == level
               for dc, dr in ORTHO):
            out.append(c)
    return out


def frontier_clear(room, x, y, level, margin, px) -> bool:
    """Is every point `margin` px around `(x, y)` still on this terrace?

    `interior_cells` keeps a prop a whole cell from a level change in the four
    cardinal directions but says nothing about the corner it can still sit in
    when the *diagonal* neighbour is another terrace. This is the sub-tile half
    of the same rule: the few pixels of air that stop a prop reading as glued
    to the boundary line between two tilesets.
    """
    return all(tile_level(room, x + dx * margin, y + dy * margin, px) == level
               for dx, dy in AROUND)


def uphill_clear(room, x, y, level, north, west, east, px) -> bool:
    """Would this sprite's art reach onto a *higher* terrace?

    The reach is measured off the rig's own anchor and frame, so a 96 px bush
    keeps a bush's distance and a pebble keeps a pebble's.

    Every tile the art covers is checked, not a handful of points on its rim.
    Sampling the corners and edge midpoints looks equivalent and is not: a
    *wider* box can straddle a narrow terrace strip and land both its samples
    beyond it, so a conservative reach could pass where the true one fails --
    which is exactly what the obstacle scatter needs, since it must place with
    a per-kind worst case before the rig is even drawn.

    Downhill is deliberately not tested. Art hanging south over a rim reads as
    a prop on the edge of a cliff, which is exactly what it is.
    """
    if north <= 0 and west <= 0 and east <= 0:
        return True
    ox, oy = room.rect.x, room.rect.y
    c0 = int((x - west - ox) // px)
    c1 = int((x + east - ox) // px)
    r0 = int((y - north - oy) // px)
    r1 = int((y - oy) // px)
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            got = cell_level(room, (col, row))
            if got is not None and got > level:
                return False
    return True


# --- how far a rig's art reaches ------------------------------------------

def rig_scale(meta: dict, radius: float, boost: float,
              override=None) -> float:
    """Draw scale for an obstacle rig: the factor that makes the rig's measured
    `footprint` (content width in source px) cover `2 * radius * boost` on
    screen. The one authority for this -- `world/terrain/decor.py` skins each
    obstacle with it, and `obstacle_reach` below predicts the result at
    generation time, so the two cannot drift.

    `override` is a fixed scale for a kind whose art must keep the size it was
    painted at instead of being fitted to its collider. A signpost is a
    signpost whatever hitbox it carries, and fitting one to an 8 px post would
    shrink it to nothing; `1.0` draws the sheet exactly as authored.
    """
    if override is not None:
        return float(override)
    fw = meta["frame"][0]
    footprint = float(meta.get("footprint") or fw)
    return (2.0 * radius * boost) / footprint if footprint else 0.0


def obstacle_reach(terrain: dict) -> dict:
    """`kind -> (north, west, east)`: how far the art of the *largest* rig a
    kind can wear reaches from its anchor, in world px.

    Conservative on purpose. Which rig an obstacle actually gets depends on a
    `variant` drawn in a later pass, and on the biome it lands on -- neither is
    known while it is being placed -- so the reach is the worst case over every
    rig the kind could end up wearing, biome tree lists included.
    """
    conf = terrain.get("obstacle_decor", {})
    rigs = terrain.get("rigs", {})
    obstacles = terrain.get("obstacles", {})
    boost = float(conf.get("size_boost", 1.25))
    render_radius = conf.get("render_radius", {})
    render_scale = conf.get("render_scale", {})

    # A biome may substitute its own tree list (LD-10); take the union.
    extra: dict = {}
    for spec in terrain.get("biomes", {}).values():
        if spec.get("trees"):
            extra.setdefault("tree", []).extend(spec["trees"])

    out: dict = {}
    for kind, names in conf.get("rigs", {}).items():
        radius = float(render_radius.get(
            kind, obstacles.get(kind, {}).get("radius", 0.0)))
        north = west = east = 0.0
        for rig in list(names) + extra.get(kind, []):
            meta = rigs.get(rig)
            if not meta:
                continue
            fw, fh = meta["frame"]
            ax, ay = meta.get("anchor", (fw * 0.5, fh))
            scale = rig_scale(meta, radius, boost, render_scale.get(kind))
            north = max(north, ay * scale)
            west = max(west, ax * scale)
            east = max(east, (fw - ax) * scale)
        out[kind] = (north, west, east)
    return out
