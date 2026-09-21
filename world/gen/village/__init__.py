"""The village pass (HI-2): what stands on a human island.

`world/gen/scatter.py` passes over a `village` room and this decides
everything on it instead. The settlement is designed round a centre on a
north axis: the forge in the middle, the heal zone directly above it, the
town hall (the monastery) directly above that; the houses clustered on
adjacent slots of the ring round the forge; a military group -- barracks,
tower and, at the first bridge, the archery -- in a row beside the road in
from every bridge; a fenced sheep pen on the side of the island farthest
from the bridges; and the trees, rocks and clutter kept outside the
cluster, spread round it. Every
building is an `Obstacle` of its own kind (the houses reuse `house`), so
collision, navigation, the unseal repair, the ghost pass and the skins need
nothing new; a wide building is a *compound* of circles -- one primary that
carries the art plus the `satellites` its `terrain.json` entry declares,
which collide but are never drawn (`Obstacle.skin`).

What the run needs to know afterwards -- where the forge and the heal are,
which buildings stand where, where the guards post and where the pen is --
comes back as a `Village` record on the layout, so the interactables and
the NPCs (HI-3) read one source rather than sifting the obstacle list.

Colours are drawn from a shuffled cycle: no colour repeats until every one
has appeared, and there is deliberately no colour band per village.

Runs after the scatter and before the unseal repair, so a building that
seals the road is taken back like any other obstacle. Its RNG is private --
keyed by seed and island, the way the bridges and the palettes do it -- so
the pass draws nothing from the world stream: the tree top-up can change
and the village stays where it was, which `test_obstacle_families` pins.
The geometry rules -- every circle on `GROUND` with a tile of coast in
hand, clear of every bridge-mouth keep-clear rect, clear of each other, and
off the lanes from each bridge mouth to the forge -- are the same ones the
scatter keeps, so stepping off a bridge is never into a wall.
"""
from __future__ import annotations

import random

from world.gen.scatter import _blocks, _corridor_doorways  # noqa: F401  -- `_blocks` re-exported for the tests
from world.gen.settings import settings_or_config
from world.gen.tuning import VILLAGE_KIND
from world.gen.village.pen import _pen_fits, _pen_tiles, _place_pen  # noqa: F401
from world.gen.village.scatter import _edge_distance  # noqa: F401
from world.gen.village.seating import _lay_out
from world.gen.village.site import COLOURS, FENCE_SLOTS, _Cycle, _Site, _road  # noqa: F401

__all__ = ["place_villages", "COLOURS", "FENCE_SLOTS"]


def place_villages(rooms, corridors, seed: int, settings=None) -> tuple[list, list]:
    """`(obstacles, villages)` for every village island. `obstacles` go on
    the layout's list after the scatter's; `villages` is one `Village` per
    island, in island order. Draws nothing from the world stream."""
    s = settings_or_config(settings)
    doorways = _corridor_doorways(rooms, corridors)
    # The painted reach of every kind (LD-Z) comes off the rig data; the
    # import is local for the reason the scatter's is -- this module stays
    # importable without the asset layer.
    from game.assets import get_assets
    terrain = get_assets().terrain
    out: list = []
    villages: list = []
    for room in rooms:
        if room.kind != VILLAGE_KIND:
            continue
        rng = random.Random(f"{seed}:village:{room.id}")
        site = _Site(room, doorways.get(room.id, []), rng, terrain)
        village = _lay_out(site, s.town_hall)
        out.extend(site.placed)
        villages.append(village)
    return out, villages
