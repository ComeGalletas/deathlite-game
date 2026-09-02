"""Interior clutter: seeded, non-colliding scenery on a room's own floor.

The land half of the decoration scatter; `scatter_water.py` is the other. What
this owns is *placement* -- the rules about where a prop may stand. How many of
them there should be lives in `budget.py`, the frontier rules in
`world/frontier.py`, and the separation test in `spacing.py`.
"""
from __future__ import annotations

import random

from world import frontier
from world.terrain.decor.budget import _terraces, _tier_scales
from world.terrain.decor.rigs import load_rig
from world.terrain.decor.spacing import _Neighbourhood


def build_decor_scatter(store, a) -> None:
    """Seeded, non-colliding scenery from `terrain.json` "decorations":
    interior clutter per room + water scenery in the void.

    Deterministic per `(layout.seed, room id / void grid cell)` -- a string
    seed so it is stable regardless of `PYTHONHASHSEED`. These are cosmetic:
    nothing here touches `store.obstacles` or `is_walkable`. A new prop is a
    new rig + a new "decorations" entry, no code. `collision: true` entries
    are handled by world generation (trees, T9), not here.

    LD-10 step 4: an entry may name the `biomes` it belongs to, and is then
    only placed on terraces wearing one of them -- bones on sand, fungi in the
    forest, mossy stone in the wetland. An entry that names none is universal,
    which is the default a new prop gets and what keeps every terrace from
    being able to come out bare. The filter is per **terrace**, not per island:
    a volcanic island can be wetland at the waterline and rock at the summit,
    and the pumpkins have no business up top.

    The same split fixes a density mismatch that predates it: `per_room` was
    authored for LD-8 rooms of ~60 cells and was being applied whole to islands
    of 700-1000, so a terrace could come out with four pebbles on it. A biome's
    `decor.per_1000` now sets each terrace's budget and the authored counts are
    the weights by which its legal props share it.
    """
    reg = a.terrain.get("decorations", [])
    if not reg:
        return
    px = int(a.terrain.get("tile_px", 64))
    place = a.terrain.get("decor_placement", {})
    inset = float(place.get("edge_inset", 6))
    keepback = float(place.get("uphill_keepback", 1.0))
    resolved: dict[tuple, tuple | None] = {}       # (rig, size) -> entry|None

    def load(rig: str, scale: float):
        return load_rig(a, resolved, rig, scale)
    if store.layout is None:
        return
    seed = store.layout.seed
    # One index over every obstacle, built once. Queried with `gap = 0` so the
    # stored `(radius + 20)` is the whole rule, exactly as the scan it replaces.
    obstacles = _Neighbourhood(
        max((o.radius for o in store.obstacles), default=0.0) + 20.0)
    for o in store.obstacles:
        obstacles.add(o.pos.x, o.pos.y, o.radius + 20.0)
    room_reg = [e for e in reg if e.get("placement") == "room_interior"
                and not e.get("collision")]
    # The index's cell must be at least the widest separation any prop asks
    # for, or a rejecting neighbour could sit outside the nine cells searched.
    prop_cell = max((float(e.get("min_gap", 40)) for e in room_reg), default=40.0)

    # --- room interiors: clutter on interior cells, clear of the centre ---
    for room in store.layout.rooms:
        rng = random.Random(f"{seed}:{room.id}:decor")
        r = room.rect
        cols, rows = max(3, r.width // px), max(3, r.height // px)
        # clutter only on fully-interior cells (all four neighbours floor
        # *of the same terrace*), so a pebble never sits on a half-water
        # shoreline, a notch edge, or hard against a level change
        floor = frontier.interior_cells(room)
        cx, cy = room.center
        # A fraction of the room's own size, which is the LD-8 rule and right
        # for a 60-cell room -- but on a 3200 x 1792 island it is a 394 px
        # radius, blanking a 788 px circle out of the middle of every island.
        # The obstacle scatter hit this exact wall and swapped the fraction for
        # a fixed few tiles (`tuning._GRID_CLEAR_RADIUS`); interior clutter
        # never did, and no amount of raising the biome rates would have shown
        # through it. Height-map islands take the fixed disc; the legacy world
        # keeps the fraction, being pinned seed by seed in its tests.
        clear_sq = (float(place.get("centre_clear", 0.0)) ** 2 if room.grid
                    else (min(r.width, r.height) * 0.22) ** 2)
        placed: list[tuple] = []
        # Separations live in the index rather than in a list parallel to
        # `placed`: at ground-cover densities the old pairwise scan was the
        # dominant cost of the whole bake. See `_Neighbourhood`.
        near = _Neighbourhood(prop_cell)
        # One pass per terrace rather than one per island. An island can be
        # wetland at the waterline and rock at the summit, so neither "which
        # props suit this island" nor "how many does it want" is a question
        # with a single answer.
        for fam, where in _terraces(room, floor):
            legal = ([e for e in room_reg
                      if not e.get("biomes") or fam in e["biomes"]]
                     if fam else room_reg)
            scales = _tier_scales(a.terrain, fam, len(where), legal)
            for e in legal:
                lo, hi = e.get("per_room", [0, 2])
                k = scales.get(e["tier"], 1.0)
                entry = load(e["rig"], float(e.get("scale", 1.0)))
                if entry is None:
                    continue
                frs, ax, ay, fps = entry
                # How far this rig's art reaches from its anchor. `ax` / `ay`
                # are the scaled anchor, so they *are* the west and north
                # reaches; east is whatever frame is left to the right of it.
                north = ay * keepback
                west = ax * keepback
                east = (frs[0].get_width() - ax) * keepback
                my_gap = float(e.get("min_gap", 40))
                for _ in range(round(rng.randint(lo, hi) * k)):
                    for _try in range(6):
                        if where:
                            col, row = rng.choice(where)
                        else:
                            col = rng.randint(1, cols - 2)
                            row = rng.randint(1, rows - 2)
                        x = r.x + col * px + rng.uniform(inset, px - inset)
                        y = r.y + row * px + rng.uniform(inset, px - inset)
                        if (x - cx) ** 2 + (y - cy) ** 2 < clear_sq:
                            continue
                        if room.grid:
                            lvl = frontier.cell_level(room, (col, row))
                            if not frontier.frontier_clear(room, x, y, lvl, inset, px):
                                continue
                            if not frontier.uphill_clear(room, x, y, lvl,
                                                 north, west, east, px):
                                continue
                        if obstacles.blocked(x, y):
                            continue
                        if near.blocked(x, y, my_gap):
                            continue
                        placed.append((frs, ax, ay, fps, x, y))
                        near.add(x, y, my_gap)
                        break
        if placed:
            store._room_decor[room.id] = placed
