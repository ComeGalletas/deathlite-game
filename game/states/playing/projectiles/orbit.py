"""The orbiting-ember look (`orbit`, Ember Ring): an animated flame that faces
its direction of travel around the player.

The `ember` rig (`effects/flame-loop`) points **south**; a `rotated()`-style
heading is 0 == +x, so we pass the tangent heading minus 90 deg. For
`orbit_speed > 0` the tangent is `orbit_angle + 90 deg`, so the value passed is
just `degrees(orbit_angle)` (`+ 180` if a blessing ever makes `orbit_speed`
negative). The animation frame comes from the shared run clock -- a phase-locked
ring of flames reads as intentional and needs no per-projectile state.
"""
from __future__ import annotations

import math

import pygame

from game.states.playing.projectiles import style

_RIG, _ANIM = "ember", "loop"


@style("orbit")
def orbit(surface, sx, sy, p, ctx) -> None:
    z = ctx.zoom
    assets = ctx.assets
    scale = assets.scale_for(_RIG) or (16, 34)
    size = (max(1, round(scale[0] * z)), max(1, round(scale[1] * z)))

    n = max(1, assets.frame_count(_RIG, _ANIM))
    idx = int(ctx.now * assets.fps(_RIG, _ANIM)) % n
    heading = math.degrees(p.orbit_angle) + (0.0 if p.orbit_speed > 0 else 180.0)

    spr = assets.frame_rotated(_RIG, _ANIM, idx, heading, size=size)
    if spr is not None:
        surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
    else:  # rig / sheet missing -> the plain disc it replaces
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                           max(2, round(p.radius * z)))
