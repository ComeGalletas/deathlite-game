"""Bridge lane geometry: where along two islands' shared span a bridge runs."""
from __future__ import annotations

import random

import pygame



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


