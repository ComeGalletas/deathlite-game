"""The default projectile looks: a flat disc (`bolt`) and the rotated hostile
arrow sprite (`arrow`). Bodies moved verbatim from `rendering.py`.
"""
from __future__ import annotations

import math

import pygame

from game import config
from game.states.playing.projectiles import style



@style("bolt")
def bolt(surface, sx, sy, p, ctx) -> None:
    pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                       max(2, round(p.radius * ctx.zoom)))


@style("arrow")
def arrow(surface, sx, sy, p, ctx) -> None:
    # Enemy / boss shots: a rotated arrow (falls back to a dot if the sprite is
    # missing). Rotation is cached in 8-degree buckets by `Assets.rotated`.
    z = ctx.zoom
    aw, ah = ctx.assets.scale_for("arrow")
    size = (max(1, round(aw * z)), max(1, round(ah * z)))
    tint = p.fx.get("tint")                 # P1: the hero's Bow is not hostile red
    spr = ctx.assets.rotated(
        "arrow", math.degrees(math.atan2(p.vel.y, p.vel.x)),
        size=size, tint=tuple(tint) if tint else config.HOSTILE_ARROW_TINT)
    if spr is not None:
        surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
    else:
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                           max(3, round(p.radius * z)))
