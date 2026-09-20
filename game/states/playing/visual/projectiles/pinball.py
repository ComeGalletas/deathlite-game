"""The pinball (buff buildings): the pack's yellow orb, spun along its
travel so a bounce reads as a roll, over a soft glow in the buff's colour.
"""
from __future__ import annotations

import math

import pygame

from game.states.playing.visual.projectiles import style

_SPIN_DEG_PER_PX = 2.2


@style("pinball")
def pinball(surface, sx, sy, p, ctx) -> None:
    z = ctx.zoom
    r = max(3, round(p.radius * z))
    glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*p.color, 70), (r * 2, r * 2), r * 2)
    surface.blit(glow, glow.get_rect(center=(int(sx), int(sy))))
    size = (r * 2 + 4, r * 2 + 4)
    # Rolled distance stands in for a spin; `age * speed` is what a straight
    # ball has travelled, and a bounce does not reset it.
    spun = (p.age * p.vel.length() * _SPIN_DEG_PER_PX) % 360.0
    spr = ctx.assets.rotated("pinball", spun, size=size)
    if spr is not None:
        surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
    else:
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)), r)
        pygame.draw.circle(surface, (255, 255, 255), (int(sx), int(sy)), r, 2)
