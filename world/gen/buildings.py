"""Buff buildings: two to five interactive buildings per island (journal:
buff_buildings_journal.md).

Runs inside the obstacle scatter right after the houses and before the
trees, so the small obstacles space themselves off a building the way they
do off a house. Every island but the village (the village pass owns it) and
the boss arena (its clear disc is the fight) draws a count from
`placement.per_island`, and seats that many *distinct* kinds -- an island
with five shows all five. Each building is an ordinary `Obstacle` whose kind
is the buff it grants (`magnet`, `turbo`, ...); the run finds them by kind
(`WorldLayout.buff_buildings`) and seats the interactable on the obstacle.

Beside each building one or two ordinary colliding obstacles from the
kind's `colliders` list (a rock by the mine, a tree by the dead tree) stand
inside the dressing ring; the non-colliding props of the ring are the
bake's job (`world/terrain/decor/dressing.py`), because they are scenery.
"""
from __future__ import annotations

import math

from entities.obstacle import Obstacle, satellites_of
from game import config
from world.gen.tuning import (
    VILLAGE_KIND, _BUFF_PER_ISLAND, _BUFF_MIN_ROOM_CELLS, _BUFF_MIN_ROOM_TILES,
    _BUFF_GAP_TILES, _BUFF_RING_TILES, _BUFF_PLACE_TRIES, _OBSTACLE_GAP,
)


def buff_kinds(buildings: dict) -> tuple[str, ...]:
    """The buff kinds `buildings.json` declares, in file order."""
    return tuple(buildings.get("buffs", {}))


def _placement(buildings: dict) -> dict:
    p = buildings.get("placement", {})
    return {
        "per_island": tuple(p.get("per_island", _BUFF_PER_ISLAND)),
        "min_cells": int(p.get("min_room_cells", _BUFF_MIN_ROOM_CELLS)),
        "min_tiles": int(p.get("min_room_tiles", _BUFF_MIN_ROOM_TILES)),
        "gap": float(p.get("building_gap_tiles", _BUFF_GAP_TILES)),
        "ring": tuple(p.get("dressing_ring_tiles", _BUFF_RING_TILES)),
        # Never more than two close together (owner, 2026-09-20): inside a
        # ring of `cluster_ring_px` round any building at most
        # `cluster_max_neighbours` other buildings.
        "cluster_ring": float(p.get("cluster_ring_px", 0.0)),
        "cluster_max": int(p.get("cluster_max_neighbours", 1)),
    }


def _crowds(x, y, primaries, ring2: float, max_nb: int) -> bool:
    """Would a building at `(x, y)` make a cluster: itself, or any building
    inside the ring round it, ending up with more than `max_nb` neighbours
    inside their own rings?"""
    if ring2 <= 0.0:
        return False
    near = [o for o in primaries if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < ring2]
    if len(near) > max_nb:
        return True
    for o in near:
        others = sum(1 for q in primaries
                     if q is not o and (q.pos - o.pos).length_squared() < ring2)
        if others + 1 > max_nb:
            return True
    return False


def _inland(cellset, col, row) -> bool:
    return all((col + dc, row + dr) in cellset
               for dc in (-1, 0, 1) for dr in (-1, 0, 1))


def _footprint(kind: str, radius: float) -> float:
    """How far a building of `kind` reaches from its position: its primary
    circle, or the farthest edge of a satellite -- the two-tile tree (owner,
    2026-09-20) is placed and kept clear of doors by its whole base."""
    return max([radius] + [abs(dx) + r for dx, _dy, r in satellites_of(kind)])


def _seat(kind: str, x: float, y: float, out: list) -> Obstacle:
    """The building's circles into `out`: the primary carries the skin, the
    satellites collide only, as the village pass seats its wide buildings."""
    primary = Obstacle(kind, x, y)
    out.append(primary)
    for dx, dy, r in satellites_of(kind):
        sat = Obstacle(kind, x + dx, y + dy)
        sat.radius = r
        sat.skin = False
        out.append(sat)
    return primary


def _scatter_buildings(rooms, all_doors, rng, boss_id, out, reach, buildings,
                       *, blocks, doors_near, uphill_ok, radius_of, keep_pad,
                       biome_at) -> None:
    """Seat the buff buildings and their colliding company. Appends to
    `out`. The scatter's own helpers are handed in (`blocks`, `doors_near`,
    `uphill_ok`, `radius_of`, `keep_pad`) so the two modules share one set
    of placement rules without a circular import."""
    kinds = buff_kinds(buildings)
    if not kinds:
        return
    px = config.TILE_PX
    place = _placement(buildings)
    lo, hi = place["per_island"]
    gap = place["gap"] * px
    ring2 = place["cluster_ring"] ** 2
    max_nb = place["cluster_max"]
    ring_lo, ring_hi = (r * px for r in place["ring"])
    door_pad = int(2 * max(_footprint(k, radius_of(k)) for k in kinds))
    fat_doors = [d.inflate(door_pad, door_pad) for d in all_doors]

    for room in rooms:
        if room.id == boss_id or room.kind == VILLAGE_KIND or not room.cells:
            continue
        rr = room.rect
        if (min(rr.width, rr.height) < place["min_tiles"] * px
                or len(room.cells) < place["min_cells"]):
            continue
        doors = doors_near(fat_doors, rr, keep_pad)
        want = rng.randint(lo, hi)
        order = list(kinds)
        rng.shuffle(order)
        cells = sorted(room.cells)
        cellset = room.cells
        centres = ((room.center.x, room.center.y), (rr.centerx, rr.centery))
        keep = max(min(rr.width, rr.height) * 0.22, 2 * px)

        def _spot(kind, r_k):
            wide = _footprint(kind, r_k) > r_k        # a compound: its base spans cells
            for _try in range(_BUFF_PLACE_TRIES):
                col, row = rng.choice(cells)
                if not _inland(cellset, col, row):
                    continue
                if wide and not (_inland(cellset, col - 1, row) and _inland(cellset, col + 1, row)):
                    continue
                x = rr.left + col * px + px * 0.5
                y = rr.top + row * px + px * 0.5
                if any((x - mx) ** 2 + (y - my) ** 2 < keep ** 2 for mx, my in centres):
                    continue
                if blocks(doors, x, y, r_k):
                    continue
                if not uphill_ok(room, x, y, kind, reach, px):
                    continue
                # Off every obstacle already standing, and a full ring from
                # the other buildings -- the scatter's houses included, so a
                # buff building never crowds a house into a choke the repair
                # then has to open by taking the house away (seed 35 lost
                # its only house that way, rev. 6) -- so each keeps its own
                # dressing.
                if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                       < (gap if (o.kind in kinds or o.kind == "house")
                          else o.radius + r_k + _OBSTACLE_GAP) ** 2
                       for o in out):
                    continue
                if _crowds(x, y, [o for o in out if o.kind in kinds and o.skin],
                           ring2, max_nb):
                    continue
                return x, y
            return None

        placed = 0
        for kind in order:
            if placed >= want:
                break
            spot = _spot(kind, _footprint(kind, radius_of(kind)))
            if spot is None:
                continue
            building = _seat(kind, spot[0], spot[1], out)
            col = int((spot[0] - rr.left) // px)
            row = int((spot[1] - rr.top) // px)
            building.biome = biome_at(room, col, row)
            placed += 1
            _company(room, building, buildings["buffs"][kind].get("colliders", ()),
                     rng, out, reach, doors, ring_lo, ring_hi, px,
                     blocks=blocks, uphill_ok=uphill_ok, radius_of=radius_of,
                     biome_at=biome_at)


def _company(room, building, colliders, rng, out, reach, doors, ring_lo, ring_hi, px,
             *, blocks, uphill_ok, radius_of, biome_at) -> None:
    """The building's colliding company: each kind in `colliders`, once,
    somewhere on the dressing ring, on the building's own terrace."""
    from world.rules import frontier
    rr = room.rect
    cellset = room.cells
    level = frontier.tile_level(room, building.pos.x, building.pos.y, px)
    for kind in colliders:
        r_k = radius_of(kind)
        for _try in range(_BUFF_PLACE_TRIES):
            ang = rng.uniform(0.0, math.tau)
            dist = rng.uniform(max(ring_lo, building.radius + r_k + 8.0), ring_hi)
            x = building.pos.x + math.cos(ang) * dist
            y = building.pos.y + math.sin(ang) * dist
            col = int((x - rr.left) // px)
            row = int((y - rr.top) // px)
            if not _inland(cellset, col, row):
                continue
            if frontier.tile_level(room, x, y, px) != level:
                continue
            if blocks(doors, x, y, r_k):
                continue
            if not uphill_ok(room, x, y, kind, reach, px):
                continue
            if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                   < (o.radius + r_k + (8.0 if o is building else _OBSTACLE_GAP)) ** 2
                   for o in out):
                continue
            ob = Obstacle(kind, x, y, rng.randint(1, 4))
            ob.biome = biome_at(room, col, row)
            out.append(ob)
            break
