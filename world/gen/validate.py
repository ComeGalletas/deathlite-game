"""What every generated world promises, checked after the fact.

`generate_world` builds its invariants in; this reads them back off a
finished layout and lists what does not hold, so a change to one stage that
quietly breaks another stage's assumption fails with a sentence rather than
somewhere downstream. The tests run it on every cached world. It is not run
inside the game: a run pays for generation once and these checks are a
flood fill per island.
"""
from __future__ import annotations

from game import config
from world.gen.height.graph import check_grid
from world.layout import WALKABLE_KINDS
from world.rules import floor


def validate(layout) -> list[str]:
    """Every broken promise, as a sentence each. Empty when the world is
    sound."""
    bad: list[str] = []
    px = config.TILE_PX
    for r in layout.rooms:
        tag = f"island {r.id}"
        if r.rect.x % px or r.rect.y % px:
            bad.append(f"{tag}: rect {tuple(r.rect)} is off the tile lattice")
        if r.rect.width % px or r.rect.height % px:
            bad.append(f"{tag}: rect {tuple(r.rect)} is not tile-sized")
        if not r.grid:
            bad.append(f"{tag}: no height map")
            continue
        walkable = frozenset(p for p, c in r.grid.items() if c.kind in WALKABLE_KINDS)
        if r.cells != walkable:
            bad.append(f"{tag}: `cells` is not the walkable subset of `grid` "
                       f"({len(r.cells ^ walkable)} cells differ)")
        w, h = r.tile_dims
        if any(not (0 <= c < w and 0 <= rr < h) for c, rr in r.grid):
            bad.append(f"{tag}: grid cells outside the rect")
        for complaint in check_grid(r.grid):
            bad.append(f"{tag}: {complaint}")
        if not r.topography:
            bad.append(f"{tag}: no topography")
        levels = {c.level for c in r.grid.values() if c.kind in WALKABLE_KINDS}
        if levels - set(r.palette):
            bad.append(f"{tag}: terraces {sorted(levels - set(r.palette))} "
                       f"have no palette sheet")
        if set(r.tile_meta) != r.cells:
            bad.append(f"{tag}: tile meta does not cover exactly the floor")
        if len(levels) > 1 and r.inset is None:
            bad.append(f"{tag}: terraces but no inset field")
    for c in layout.corridors:
        ra, rb = layout.room(c.a).rect, layout.room(c.b).rect
        if not (c.rect.colliderect(ra) and c.rect.colliderect(rb)):
            bad.append(f"bridge {c.a}-{c.b} does not reach both islands")
        if min(c.rect.width, c.rect.height) != px:
            bad.append(f"bridge {c.a}-{c.b} is not one tile wide")
    if not layout.is_connected():
        bad.append("an island is unreachable from the start")
    b = layout.bounds
    if (b.x, b.y) != (0, 0):
        bad.append(f"bounds start at {(b.x, b.y)}, not the origin")
    for i, o in enumerate(layout.obstacles):
        if not floor.point_on_floor(layout, o.pos.x, o.pos.y):
            bad.append(f"obstacle {i} ({o.kind}) stands off the floor")
    return bad
