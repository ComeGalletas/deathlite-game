"""The Grave Totem: a stationary rounded pillar. Primitive draw moved verbatim
from `rendering.one_summon`.
"""
from __future__ import annotations

import pygame

from game.states.playing.summons import summon_style


@summon_style("totem")
def totem(surface, sx, sy, s, ctx) -> None:
    z = ctx.zoom
    pygame.draw.rect(surface, s.color,
                     (int(sx - 7 * z), int(sy - 12 * z),
                      round(14 * z), round(24 * z)), border_radius=3)
    pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(3 * z))
