"""Somewhere next to the hero an enemy can actually stand.

Three tests have now been caught assuming a fixed offset from the player is
usable ground: the boot smoke test, the projectile-trail tests, and the dev
menu's "stop attacking" check. All three build a world from an **unpinned**
run seed, so a fixed offset is a coin flip -- on a height-map world the hero
often starts on a summit whose southern rim is a cliff, and an enemy dropped
70 px south lands over the drop and never comes back to be killed. Measured on
the smoke test before it was fixed: four seeds in twenty.

`is_walkable(p, radius, frm=origin)` is the map's own question with the
elevation rule included -- the spot is floor, *and* the step to it from where
the hero stands is one the terrain allows -- so it rules out the far side of a
drop, which a plain floor test accepts.
"""
import math

import pygame


def spots_near(playing, want=1, radius=16.0, rings=(70, 96, 124, 156, 190),
               apart=30.0):
    """Up to `want` points around the hero that an enemy can occupy.

    Returns fewer than asked for only when the hero is somewhere genuinely
    cramped; callers that need exactly `want` should assert on the length so
    the failure names the real problem instead of showing up as "nothing died".
    """
    gm = playing.game_map
    origin = pygame.Vector2(playing.player.pos)
    out = []
    for ring in rings:
        for k in range(24):
            a = k * (math.tau / 24)
            p = origin + pygame.Vector2(math.cos(a), math.sin(a)) * ring
            if not gm.is_walkable(p, radius, frm=origin):
                continue
            if any((p - q).length_squared() < apart * apart for q in out):
                continue
            out.append(p)
            if len(out) == want:
                return out
    return out
