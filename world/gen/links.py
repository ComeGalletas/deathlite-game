"""Corridor lane geometry and the cross-floor link split into stairs
(W1 split of world/procedural.py)."""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Stair


def _connection_lanes(axis: str, first: pygame.Rect, second: pygame.Rect,
                      px: int, width: int | None = None) -> list[int]:
    """Tile-centre lanes whose requested width fits inside both rooms."""
    width = width or px
    if axis == "h":
        start = max(first.top, second.top)
        end = min(first.bottom, second.bottom)
        origin = first.top + px // 2
    else:
        start = max(first.left, second.left)
        end = min(first.right, second.right)
        origin = first.left + px // 2
    first_lane = origin + max(0, (start + width // 2 - origin + px - 1) // px) * px
    return [lane for lane in range(first_lane, end, px)
            if start <= lane - width // 2 and lane + width // 2 <= end]


def _interior_connection_lanes(axis: str, first: pygame.Rect,
                               second: pygame.Rect, px: int,
                               width: int | None = None) -> list[int]:
    """Connection lanes clear of the shared edge's two-tile corner margins."""
    width = width or px
    if axis == "h":
        start = max(first.top, second.top)
        end = min(first.bottom, second.bottom)
    else:
        start = max(first.left, second.left)
        end = min(first.right, second.right)
    return [lane for lane in _connection_lanes(axis, first, second, px, width)
            if start + 2 * px <= lane - width // 2
            and lane + width // 2 <= end - 2 * px]


def _connection_lane(seed: int, a: int, b: int, axis: str,
                     first: pygame.Rect, second: pygame.Rect, px: int) -> int:
    """Stable varied lane for one room pair without consuming world RNG state."""
    lanes = _interior_connection_lanes(axis, first, second, px)
    if lanes:
        return random.Random(f"{seed}:corridor:{min(a, b)}:{max(a, b)}").choice(lanes)
    all_lanes = _connection_lanes(axis, first, second, px)
    if all_lanes:
        midpoint = ((max(first.top, second.top) + min(first.bottom, second.bottom)) // 2
                    if axis == "h" else
                    (max(first.left, second.left) + min(first.right, second.right)) // 2)
        return min(all_lanes, key=lambda lane: abs(lane - midpoint))
    return ((max(first.top, second.top) + min(first.bottom, second.bottom)) // 2
            if axis == "h" else
            (max(first.left, second.left) + min(first.right, second.right)) // 2)


def _relink_corridors(rooms, corridors) -> None:
    """Re-seat every corridor's collision rect in the overlap of its two (now
    possibly grown) rooms, spanning mouth-to-mouth. Axis / end labels unchanged."""
    px = config.TILE_PX
    for c in corridors:
        lo, hi = rooms[c.room_low].rect, rooms[c.room_high].rect
        lanes = _connection_lanes(c.axis, lo, hi, px)
        if lanes:
            c.lane = min(lanes, key=lambda lane: abs(lane - c.lane))
        if c.axis == "h":
            x0, x1 = lo.right - px, hi.left + px
            c.rect = pygame.Rect(x0, c.lane - px // 2, max(px, x1 - x0), px)
        else:
            y0, y1 = lo.bottom - px, hi.top + px
            c.rect = pygame.Rect(c.lane - px // 2, y0, px, max(px, y1 - y0))


def _split_links(rooms, corridors, rng, ramped=()) -> list:
    """Every corridor whose two rooms differ in `floor` becomes a `Stair`
    (1-2 tiles wide, tagged with the elevation change); same-floor corridors are
    left alone. Mutates `corridors` in place, returns the stairs.

    LD-3: an edge in `ramped` already has a ramp run, so it gets **no** stair at
    all -- the run is the link (decision 5: a leftover strip is exactly what
    reads as a bridge)."""
    px = config.TILE_PX
    wide_p = 1.0 / max(1, int(config.STAIR_WIDE_EVERY))
    kept: list = []
    stairs: list = []
    for c in corridors:
        fa, fb = rooms[c.a].floor, rooms[c.b].floor
        if fa == fb:
            kept.append(c)
            continue
        if frozenset((c.a, c.b)) in ramped:
            continue
        low, high = (c.a, c.b) if fa < fb else (c.b, c.a)
        ra, rb = rooms[c.a].rect, rooms[c.b].rect
        if c.axis == "h":
            overlap = min(ra.bottom, rb.bottom) - max(ra.top, rb.top)
        else:
            overlap = min(ra.right, rb.right) - max(ra.left, rb.left)
        smallest = min(ra.width, ra.height, rb.width, rb.height)
        # LD-5: roughly one stair in `STAIR_WIDE_EVERY` is 2 wide -- drawn from
        # the world rng (deterministic per seed), gated on the geometry
        # actually fitting a wider strip (a gentle 1-floor step between rooms
        # with a generous shared edge). Everything renders as a plank bridge.
        fits_wide = abs(fa - fb) == 1 and smallest >= 4 * px
        width = 2 if (fits_wide and rng.random() < wide_p) else 1
        # Span the two room centres (like the pre-relink corridor), not just the
        # mouths -- the stair's clearance-lenient cells then punch past any tight
        # room-edge neck so the flow field can always route through it.
        span = width * px
        lanes = _interior_connection_lanes(c.axis, ra, rb, px, span)
        if not lanes:
            lanes = _connection_lanes(c.axis, ra, rb, px, span)
        lane = min(lanes, key=lambda value: abs(value - c.lane)) if lanes else c.lane
        if c.axis == "h":
            x0, x1 = sorted((ra.centerx, rb.centerx))
            rect = pygame.Rect(x0, lane - span // 2, x1 - x0, span)
        else:
            y0, y1 = sorted((ra.centery, rb.centery))
            rect = pygame.Rect(lane - span // 2, y0, span, y1 - y0)
        stairs.append(Stair(low, high, rect, c.axis, width, abs(fa - fb)))
    corridors[:] = kept
    return stairs
