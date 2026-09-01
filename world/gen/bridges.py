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
    cap = config.HEIGHTMAP_BRIDGE_MAX * px
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
        # LD-10: a crossing longer than `HEIGHTMAP_BRIDGE_MAX` reads as a
        # causeway rather than a bridge. Lanes inside the cap are the pool; if
        # a link has none, its *first* bridge still has to exist, so it falls
        # back to the shortest lane there is -- refusing it would cut the world
        # in two -- and its extras are simply not built.
        short = [o for o in opts if o[1] <= cap]
        order = list(short)
        pick.shuffle(order)
        chosen: list = []
        for o in order:
            if all(abs(o[0] - taken[0]) >= gap for taken in chosen):
                chosen.append(o)
                if len(chosen) == len(group):
                    break
        if not chosen:                        # gap too wide, or nothing short
            chosen = [min(opts, key=lambda o: o[1])]
        for c, o in zip(group, chosen):
            apply(c, o)
            kept.append(c)
        for room, other in ((rooms[a_id], rooms[b_id]), (rooms[b_id], rooms[a_id])):
            key = (room.id, side_of(room, other, group[0].axis))
            used[key] = used.get(key, 0) + min(len(group), len(chosen))
    _add_shortcuts(rooms, kept, used, options, apply, seed)
    return kept


def _side_of(room, other, axis):
    """Which edge of `room` a link to `other` leaves from."""
    if axis == "h":
        return "e" if other.rect.centerx > room.rect.centerx else "w"
    return "s" if other.rect.centery > room.rect.centery else "n"


def _shortcut_axis(a, b):
    """`("h" | "v", gap in tiles)` for two islands that could be bridged, or
    `None` when no axis-aligned crossing exists between them.

    A `Corridor` is an axis, a rect and a lane, and the plank art is drawn from
    horizontal and vertical end caps -- so a pair with no shared row *or* column
    span cannot be joined at all without new art and a new corridor model.
    Measured over twenty worlds, that is 313 of the 560 unlinked pairs, and it
    is why this pass reaches for the other 247 only.
    """
    px = config.TILE_PX
    if min(a.rect.bottom, b.rect.bottom) - max(a.rect.top, b.rect.top) > 0:
        return "h", (max(a.rect.left, b.rect.left)
                     - min(a.rect.right, b.rect.right)) // px
    if min(a.rect.right, b.rect.right) - max(a.rect.left, b.rect.left) > 0:
        return "v", (max(a.rect.top, b.rect.top)
                     - min(a.rect.bottom, b.rect.bottom)) // px
    return None


def _add_shortcuts(rooms, kept, used, options, apply, seed) -> list:
    """Join islands that ended up close together but were never linked.

    The lattice grows a **tree**, so every route between two islands is unique
    and a run backtracks over the bridge it arrived by. Placement then moves
    islands off the centre of their cells, which regularly leaves two of them
    within a few tiles of each other with no crossing -- including orthogonal
    neighbours the tree simply never joined, and diagonal ones whose rects
    overlap on one axis after the offset.

    This runs last, once the grids exist and the tree's own bridges are seated,
    so it can see where the beaches are and how much of each island's bridge
    allowance is already spent. Nothing downstream assumes a tree: the flow
    field is geometric and just gains routes, and `boss_id` was fixed from the
    tree long before this, which keeps "farthest from the start" meaning what it
    always did.

    The yield is modest and that is the honest number: measured before building
    it, 44 candidates over twelve worlds and **16 that actually seat**, because
    `options` wants a *beach* on the same lane on both sides and ragged coasts
    rarely line up. About one extra crossing a world.
    """
    if not config.HEIGHTMAP_SHORTCUTS:
        return kept
    px = config.TILE_PX
    max_gap = config.HEIGHTMAP_SHORTCUT_GAP
    linked = {(min(c.a, c.b), max(c.a, c.b)) for c in kept}

    cand = []
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if (min(a.id, b.id), max(a.id, b.id)) in linked:
                continue
            got = _shortcut_axis(a, b)
            if got is None:
                continue
            axis, gap = got
            if not 0 <= gap <= max_gap:
                continue
            cand.append((gap, a.id, b.id, axis))
    # Shortest first, and deterministic: the gap breaks most ties and the ids
    # break the rest, so no RNG is drawn and the same seed still builds the
    # same world.
    cand.sort()

    for gap, a_id, b_id, axis in cand:
        a, b = rooms[a_id], rooms[b_id]
        room_low, room_high = ((a_id, b_id)
                               if (a.rect.centerx < b.rect.centerx if axis == "h"
                                   else a.rect.centery < b.rect.centery)
                               else (b_id, a_id))
        # The per-side allowance is the same rule the tree's own bridges obey:
        # a small island takes one crossing a side, and both ends have to have
        # room for it.
        if any(used.get((room.id, _side_of(room, other, axis)), 0)
               >= topography_of(room).get("bridges", 1)
               for room, other in ((a, b), (b, a))):
            continue
        c = Corridor(a_id, b_id, pygame.Rect(0, 0, px, px), axis,
                     "west" if axis == "h" else "north",
                     "east" if axis == "h" else "south",
                     room_low, room_high, 0)
        opts = [o for o in options(c)
                if o[1] <= config.HEIGHTMAP_BRIDGE_MAX * px]
        if not opts:
            continue        # no lane with a beach on both sides, or all too long
        apply(c, min(opts, key=lambda o: o[1]))
        kept.append(c)
        # Keep the layout graph and the corridor list agreeing -- several
        # callers read `Room.neighbors` rather than the corridors.
        if b_id not in a.neighbors:
            a.neighbors.append(b_id)
        if a_id not in b.neighbors:
            b.neighbors.append(a_id)
        for room, other in ((a, b), (b, a)):
            key = (room.id, _side_of(room, other, axis))
            used[key] = used.get(key, 0) + 1
    return kept
