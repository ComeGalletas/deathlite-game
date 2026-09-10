"""The Bomb's blast (`blast`, six-weapon system P1): a translucent disc the
size of the hit collider, brightest at spawn and gone within
`blast_lifetime`. The expanding ring on top is the shared `_explosions`
visual drawn by `WorldRenderer.explosions`.
"""
from __future__ import annotations

import pygame

from game.states.playing.projectiles import style

_ALPHA = 150


@style("hidden")
def hidden(surface, sx, sy, p, ctx) -> None:
    """Draws nothing: a hero hazard's one-frame bite (P3) -- the pool itself
    is what the player sees."""


@style("blast")
def blast(surface, sx, sy, p, ctx) -> None:
    r = max(2, round(p.radius * ctx.zoom))
    disc = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(disc, (*p.color, _ALPHA), (r, r), r)
    surface.blit(disc, (int(sx) - r, int(sy) - r))
