"""The fish huts, moored beside the bridges (journals/fish_hut_journal.md).

The last stage of `generate_world_steps`. Each island that has a bridge rolls
one to three huts (`placement.fish_huts` in the NPC data) and moors them off
the side of its own bridges: `_FH_ALONG` tiles along the span out from where
the planks meet the island, `_FH_OUT` tiles to one side of the bridge's
centre line. Every candidate is a spot beside one of the island's bridges; an
island keeps the first `count` of them, in a seeded order, whose clearance
disc (`_FH_CLEAR` tiles: the hut's own art plus the ring its seahorse boats
drift on) is open water -- off every island cell and every bridge -- and
which stand `_FH_APART` tiles from every hut already moored, its own island's
or another's. Fewer passing candidates means fewer huts; never a hut on land,
and none on a lake.

The mouth is found on the bridge's centre line by stepping out from the
rect's island end until the point is no longer on the island's cells: the
rect edge alone is not the coast, because the coast wanders inside the
island's rect (`_corridor_doorways` learnt the same lesson).

**RNG.** A private `random.Random` keyed by seed and island, the way the
chests and the resource anchors do it, so this stage draws nothing from the
world's stream and moves no room, bridge, obstacle, spawn point or chest. It
does move the layout fingerprint: `layout.fish_huts` is a new field the
digest walks.
"""
from __future__ import annotations

import math
import random

from game import config
from game.content import get_content
from world.gen.tuning import _FH_ALONG, _FH_APART, _FH_CLEAR, _FH_OUT
from world.layout import FishHut
from world.rules import floor as floor_rules

__all__ = ["place_fish_huts", "bridge_ends", "clear_water"]

# The clearance disc is sampled, not rasterised: the centre, a ring at the
# full radius and one at half of it. Seventeen probes per candidate.
_RING = 8
# Stepping out along the bridge to find the coast, px.
_STEP = 8.0
_MAX_STEPS = 24


def bridge_ends(layout) -> list:
    """`(room_id, corridor_index, mouth_x, mouth_y, along_x, along_y,
    side_x, side_y)` for every end of every bridge: the point where the
    planks leave the island's cells, the unit vector along the span away
    from the island, and one unit vector across it."""
    out = []
    rooms = layout.rooms
    for ci, c in enumerate(layout.corridors):
        r = c.rect
        if c.axis == "h":
            ends = ((c.room_low, (r.left, r.centery), (1.0, 0.0)),
                    (c.room_high, (r.right, r.centery), (-1.0, 0.0)))
            side = (0.0, 1.0)
        else:
            ends = ((c.room_low, (r.centerx, r.top), (0.0, 1.0)),
                    (c.room_high, (r.centerx, r.bottom), (0.0, -1.0)))
            side = (1.0, 0.0)
        for rid, (ex, ey), (ax, ay) in ends:
            if rid < 0:
                rid = c.a if rooms[c.a].rect.collidepoint(ex, ey) else c.b
            room = rooms[rid]
            # Walk out along the span until the island's cells end.
            mx, my = float(ex), float(ey)
            for _ in range(_MAX_STEPS):
                if floor_rules.room_of(layout, mx, my) is not room:
                    break
                mx, my = mx + ax * _STEP, my + ay * _STEP
            out.append((rid, ci, mx, my, ax, ay, side[0], side[1]))
    return out


def clear_water(layout, x: float, y: float, radius: float) -> bool:
    """Is the disc of `radius` px round the point open water, inside the
    world? Sampled at the centre and on two rings."""
    b = layout.bounds
    if not (b.left + radius <= x <= b.right - radius
            and b.top + radius <= y <= b.bottom - radius):
        return False
    if floor_rules.point_on_floor(layout, x, y):
        return False
    for rr in (radius, radius * 0.5):
        for i in range(_RING):
            ang = 2.0 * math.pi * i / _RING
            if floor_rules.point_on_floor(layout, x + rr * math.cos(ang),
                                          y + rr * math.sin(ang)):
                return False
    return True


def place_fish_huts(layout) -> None:
    px = config.TILE_PX
    place = get_content().npcs["placement"]
    lo, hi = place.get("fish_huts", (1, 3))
    clear = _FH_CLEAR * px
    apart = _FH_APART * px
    ends = bridge_ends(layout)
    huts: list[FishHut] = []
    for room in layout.rooms:
        mine = [e for e in ends if e[0] == room.id]
        if not mine:
            continue
        rng = random.Random(f"{layout.seed}:{room.id}:fish_huts")
        count = rng.randint(lo, hi)
        # Every spot beside every one of this island's bridges: both sides
        # of the span, a seeded distance along it. Shuffled, so which bridge
        # and which side an island favours is the seed's.
        cands = []
        for _rid, ci, mx, my, ax, ay, sx, sy in mine:
            for sign in (1.0, -1.0):
                along = rng.uniform(*_FH_ALONG) * px
                out = _FH_OUT * px * sign
                cands.append((ci, mx + ax * along + sx * out,
                              my + ay * along + sy * out))
        rng.shuffle(cands)
        got = 0
        for ci, x, y in cands:
            if got >= count:
                break
            if not clear_water(layout, x, y, clear):
                continue
            if any(math.hypot(x - h.x, y - h.y) < apart for h in huts):
                continue
            huts.append(FishHut(room.id, ci, x, y))
            got += 1
    layout.fish_huts = huts
