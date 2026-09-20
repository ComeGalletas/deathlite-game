"""The dressing round a buff building (journal: buff_buildings_journal.md):
gold stones round the mine, tools and logs by the tower, bones under the
dead tree.

Scenery, not obstacles -- the props here are walked over like any pebble --
so they are placed at bake time like the rest of the clutter, seeded by
`(layout.seed, room id)` so a world dresses the same way every time it is
baked. Each building draws `placement.dressing_count` props from its kind's
`dressing` list and seats them on the ring `placement.dressing_ring_tiles`
tiles out, on the building's own terrace, off every obstacle and off each
other. The colliding company (the rock by the mine) is the generator's
(`world/gen/buildings.py`); this pass only adds to `store.room_decor`.
"""
from __future__ import annotations

import math
import random

from game import config
from world.rules import frontier
from world.terrain.decor.rigs import load_rig

_TRIES = 10
# The dressing keeps the clutter's own rules (`tests/world/test_decor_*`):
# the widest `min_gap` any decoration entry asks for between props, the
# `+ 20` every prop keeps off an obstacle's collider, and the placement's
# edge inset and uphill keep-back off a frontier.
_PROP_GAP = 40.0
_OBSTACLE_PAD = 20.0


def build_building_dressing(store, a, buildings: dict | None = None) -> None:
    layout = store.layout
    if layout is None:
        return
    if buildings is None:
        from game.content import get_content
        buildings = get_content().buildings
    buffs = buildings.get("buffs", {})
    if not buffs:
        return
    place = buildings.get("placement", {})
    ring_lo, ring_hi = place.get("dressing_ring_tiles", (1.4, 2.8))
    lo, hi = place.get("dressing_count", (3, 6))
    scales = buildings.get("dressing_scale", {})
    px = config.TILE_PX
    ring_lo, ring_hi = ring_lo * px, ring_hi * px
    placement = a.terrain.get("decor_placement", {})
    inset = float(placement.get("edge_inset", 8))
    keepback = float(placement.get("uphill_keepback", 1.0))
    gap = max([_PROP_GAP] + [float(e.get("min_gap", 0))
                             for e in a.terrain.get("decorations", [])])
    resolved: dict = {}
    obstacles = list(store.obstacles)

    for room in layout.rooms:
        mine = [o for o in obstacles if o.kind in buffs
                and room.rect.collidepoint(o.pos.x, o.pos.y)]
        if not mine:
            continue
        rng = random.Random(f"{layout.seed}:{room.id}:dressing")
        interior = frontier.interior_cells(room)
        near = [o for o in obstacles
                if room.rect.inflate(2 * ring_hi, 2 * ring_hi).collidepoint(o.pos.x, o.pos.y)]
        out = store.room_decor.setdefault(room.id, [])
        # The clutter already seated on this island counts as neighbours
        # too: a gold stone may not crowd a pebble any more than a pebble may.
        placed: list[tuple[float, float]] = [(inst[4], inst[5]) for inst in out]
        for b in mine:
            rigs = list(buffs[b.kind].get("dressing", ()))
            if not rigs:
                continue
            level = frontier.tile_level(room, b.pos.x, b.pos.y, px)
            for _ in range(rng.randint(lo, hi)):
                rig = rng.choice(rigs)
                entry = load_rig(a, resolved, rig, float(scales.get(rig, 0.5)))
                if entry is None:
                    continue
                frs, ax, ay, fps = entry
                reach = (ay * keepback, ax * keepback, (frs[0].get_width() - ax) * keepback)
                at = _spot(room, b, rng, interior, level, near, placed,
                           ring_lo, ring_hi, px, gap, inset, reach)
                if at is None:
                    continue
                out.append((frs, ax, ay, fps, at[0], at[1]))
                placed.append(at)


def _spot(room, b, rng, interior, level, near, placed, ring_lo, ring_hi, px,
          gap, inset, reach):
    rr = room.rect
    north, west, east = reach
    for _ in range(_TRIES):
        ang = rng.uniform(0.0, math.tau)
        dist = rng.uniform(max(ring_lo, b.radius + _OBSTACLE_PAD), ring_hi)
        x = b.pos.x + math.cos(ang) * dist
        y = b.pos.y + math.sin(ang) * dist
        cell = (int((x - rr.left) // px), int((y - rr.top) // px))
        if cell not in interior or frontier.cell_level(room, cell) != level:
            continue
        if not frontier.frontier_clear(room, x, y, level, inset, px):
            continue
        if not frontier.uphill_clear(room, x, y, level, north, west, east, px):
            continue
        if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (o.radius + _OBSTACLE_PAD) ** 2
               for o in near):
            continue
        if any((x - qx) ** 2 + (y - qy) ** 2 < gap ** 2 for qx, qy in placed):
            continue
        return x, y
    return None
