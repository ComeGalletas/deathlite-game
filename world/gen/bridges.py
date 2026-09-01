"""Seating the bridges: where a crossing actually lands.

Split out of `world/gen/__init__.py`. This is the only stage that runs *after*
the island grids exist, which is why two decisions live here rather than where
the links are laid -- the lane a bridge takes, and how many bridges a link
carries at all (`bridges` in `config.HEIGHTMAP_TOPOGRAPHIES`).
"""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Corridor, GROUND
from world.gen.placement import topography_of

def _seat_corridors(rooms, corridors, seed: int = 0) -> list:
    """Slide each bridge along the rooms' shared edge until both of its mouths
    land on walkable ground, preferring a lane where the two ends are at the
    same level so the planks read as flat, then stretch it to actually reach
    that ground.

    Two things changed under these bridges. A height-map room's edge is no
    longer uniform floor -- it may be cliff, or lake, or a terrace met
    side-on -- so the lane the tree picked before the grids existed has to be
    re-seated. And the coastline now wanders *inside* the room's rect, so a
    bridge drawn between the two rects stops short and hangs over open water;
    it has to span coast to coast instead.

    A link may carry several bridges, and **how many is a property of the two
    islands** (`bridges` in `HEIGHTMAP_TOPOGRAPHIES`). The count is decided here
    rather than where the links are laid, because at that point neither the
    topographies nor the island shapes exist. Where the two ends disagree the
    lower wins -- both have to accept the crossing -- and the allowance is
    counted **per side of each island**, not per link. Today those are the same
    thing, since the lattice gives a room at most one neighbour per direction;
    writing it per side is what keeps it correct if a cell ever hosts two.

    The extras are placed **randomly** among the lanes that work rather than all
    taking the shortest crossing -- which is what they would otherwise do, being
    seated by the same deterministic rule -- and no two on one link may sit
    within `HEIGHTMAP_BRIDGE_MIN_GAP` tiles of each other. The draw is seeded
    per room pair so it does not consume world RNG, the same trick
    `_connection_lane` uses.

    Returns the corridors that found a home. A link's *first* bridge always
    survives, falling back to the shortest crossing if the random pass finds
    nothing, since dropping it would disconnect the world; the extras are
    optional and are discarded when there is no room for them."""
    px = config.TILE_PX

    def reach(room, axis, fixed, along, step, limit, strict=True):
        """The cell a bridge may land on along one line, scanning in from the
        rect edge, as `(index, cell)` -- or `(None, None)`.

        A bridge belongs on the beach. Taking the *first* land the scan reaches
        keeps it on the outer shore rather than striking inland, and it must be
        plain ground so it never meets the middle of a flight. `strict` also
        demands sea level, so the planks do not run up onto a terrace or stop
        on a cliff top; the caller drops that only when no lane at all offers a
        beach on both sides, since a bridge onto raised ground still beats one
        left hanging over the water."""
        for i in range(limit):
            idx = along + step * i
            # Grid keys are `(col, row)`. A horizontal bridge holds the row and
            # scans columns, a vertical one the reverse -- get this the wrong
            # way round and the scan silently reads a transposed cell, which is
            # how horizontal bridges ended up starting in open water.
            pos = (idx, fixed) if axis == "h" else (fixed, idx)
            cell = room.grid.get(pos)
            if cell is None:
                continue
            if cell.kind != GROUND:
                return None, None       # first land is a flight or a wall
            if strict and cell.level != 0:
                return None, None       # ... or a terrace: no beach on this line
            return idx, cell
        return None, None

    def options(c):
        """Every lane where both islands offer a beach, as
        `(lane, span, i0, i1)`. Computed once per link and shared by all the
        bridges on it."""
        a, b = rooms[c.a], rooms[c.b]
        out = []
        if c.axis == "h":
            west, east = (a, b) if a.rect.centerx < b.rect.centerx else (b, a)
            wcols, _ = west.tile_dims
            ecols, _ = east.tile_dims
            # Any lane where both islands offer a beach will do -- scan the
            # whole span either room reaches, not just where the two rects
            # happen to overlap.
            lo = min(west.rect.top, east.rect.top) + px // 2
            hi = max(west.rect.bottom, east.rect.bottom) - px // 2
            for y in range(lo, hi + 1, px):
                wi, wc = reach(west, "h", (y - west.rect.top) // px,
                               wcols - 1, -1, wcols, True)
                ei, ec = reach(east, "h", (y - east.rect.top) // px, 0, 1,
                               ecols, True)
                if wc is None or ec is None:
                    continue
                span = (east.rect.x + ei * px) - (west.rect.x + wi * px)
                out.append((y, span, wi, ei))
        else:
            north, south = (a, b) if a.rect.centery < b.rect.centery else (b, a)
            _, nrows = north.tile_dims
            _, srows = south.tile_dims
            lo = min(north.rect.left, south.rect.left) + px // 2
            hi = max(north.rect.right, south.rect.right) - px // 2
            for x in range(lo, hi + 1, px):
                ni, nc = reach(north, "v", (x - north.rect.left) // px,
                               nrows - 1, -1, nrows, True)
                si, sc = reach(south, "v", (x - south.rect.left) // px, 0, 1,
                               srows, True)
                if nc is None or sc is None:
                    continue
                span = (south.rect.y + si * px) - (north.rect.y + ni * px)
                out.append((x, span, ni, si))
        return out

    def apply(c, opt):
        a, b = rooms[c.a], rooms[c.b]
        lane, _span, i0, i1 = opt
        c.lane = lane
        if c.axis == "h":
            west, east = (a, b) if a.rect.centerx < b.rect.centerx else (b, a)
            # The end caps sit *on* the ground tile they meet, so the planks
            # land square on it rather than stopping beside it.
            x0 = west.rect.x + i0 * px
            x1 = east.rect.x + (i1 + 1) * px
            c.rect = pygame.Rect(x0, lane - px // 2, x1 - x0, px)
        else:
            north, south = (a, b) if a.rect.centery < b.rect.centery else (b, a)
            y0 = north.rect.y + i0 * px
            y1 = south.rect.y + (i1 + 1) * px
            c.rect = pygame.Rect(lane - px // 2, y0, px, y1 - y0)

    def side_of(room, other, axis):
        """Which edge of `room` a link to `other` leaves from."""
        if axis == "h":
            return "e" if other.rect.centerx > room.rect.centerx else "w"
        return "s" if other.rect.centery > room.rect.centery else "n"

    def allowance(c, used):
        """How many bridges this link may carry, given what its two islands
        have already spent on the sides it uses."""
        a, b = rooms[c.a], rooms[c.b]
        want = min(topography_of(a).get("bridges", 1),
                   topography_of(b).get("bridges", 1))
        for room, other in ((a, b), (b, a)):
            cap = topography_of(room).get("bridges", 1)
            spent = used.get((room.id, side_of(room, other, c.axis)), 0)
            want = min(want, cap - spent)
        return max(1, want)          # a link always keeps one: dropping it
                                     # would disconnect the world

    links: dict = {}
    for c in corridors:
        links.setdefault((min(c.a, c.b), max(c.a, c.b), c.axis), []).append(c)

    kept = []
    used: dict = {}
    gap = max(1, config.HEIGHTMAP_BRIDGE_MIN_GAP) * px
    for (a_id, b_id, _axis), group in sorted(links.items()):
        # LD-10: the group arrives with exactly one corridor. Clone it up to the
        # allowance before seating, so every copy is seated as a peer.
        want = allowance(group[0], used)
        base = group[0]
        while len(group) < want:
            group.append(Corridor(base.a, base.b, base.rect.copy(), base.axis,
                                  base.end_low, base.end_high, base.room_low,
                                  base.room_high, base.lane))
        opts = options(group[0])
        if not opts:
            kept.append(group[0])            # nothing worked; leave it as laid
            for room, other in ((rooms[a_id], rooms[b_id]),
                                (rooms[b_id], rooms[a_id])):
                key = (room.id, side_of(room, other, group[0].axis))
                used[key] = used.get(key, 0) + 1
            continue
        pick = random.Random(f"{seed}:bridges:{a_id}:{b_id}")
        order = list(opts)
        pick.shuffle(order)
        chosen: list = []
        for o in order:
            if all(abs(o[0] - taken[0]) >= gap for taken in chosen):
                chosen.append(o)
                if len(chosen) == len(group):
                    break
        if not chosen:                        # gap too wide for this span
            chosen = [min(opts, key=lambda o: o[1])]
        for c, o in zip(group, chosen):
            apply(c, o)
            kept.append(c)
        for room, other in ((rooms[a_id], rooms[b_id]), (rooms[b_id], rooms[a_id])):
            key = (room.id, side_of(room, other, group[0].axis))
            used[key] = used.get(key, 0) + min(len(group), len(chosen))
    return kept


