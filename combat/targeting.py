"""Targeting strategies for auto-attacking weapons (Strategy pattern, spec 11).

A targeting function takes the firing origin and the candidate enemies and
returns an aim direction (unit vector) or None if there is nothing to shoot.
Basic weapons never require the player to aim (spec 3.2); with CB-5 a manual
aim narrows the candidates to a cone first (`enemies_in_cone`) and hands the
aim itself in as the fallback, so the same strategy serves both.
"""
from __future__ import annotations

import math

import pygame


def _nearest(origin: pygame.Vector2, enemies) -> object | None:
    best = None
    best_d2 = float("inf")
    for e in enemies:
        d2 = (e.pos - origin).length_squared()
        if d2 < best_d2:
            best_d2 = d2
            best = e
    return best


def aim_direction(mode: str, origin: pygame.Vector2, enemies,
                  fallback: pygame.Vector2 | None = None) -> pygame.Vector2 | None:
    """Return a unit aim vector for the given targeting mode.

    Supported now: "nearest", "random". Unknown modes fall back to "nearest".
    `fallback` (e.g. player's last move direction) is used when no enemy exists
    so weapons still fire into open space rather than stalling.
    """
    target = None
    if mode == "random" and enemies:
        import random
        target = random.choice(list(enemies))
    else:  # "nearest" and default
        target = _nearest(origin, enemies)

    if target is not None:
        direction = target.pos - origin
        if direction.length_squared() > 0:
            return direction.normalize()

    if fallback is not None and fallback.length_squared() > 0:
        return fallback.normalize()
    return None


def enemies_in_cone(origin: pygame.Vector2, direction: pygame.Vector2, enemies,
                    half_angle: float, reach: float) -> list:
    """CB-5 aim assist: the enemies within `reach` of `origin` whose bearing
    is within `half_angle` (radians) of `direction`. An enemy sitting on the
    origin has no bearing and counts as inside. `direction` must be unit."""
    cos_limit = math.cos(half_angle)
    r2 = reach * reach
    out = []
    for e in enemies:
        to = e.pos - origin
        d2 = to.length_squared()
        if d2 > r2:
            continue
        if d2 <= 1e-6 or to.dot(direction) >= cos_limit * math.sqrt(d2):
            out.append(e)
    return out
