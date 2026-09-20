"""The buff timers over the hero (journal: buff_buildings_journal.md,
rev. 6): one mark per active buff -- the buff's still inside a dark disc,
ringed in the buff's colour, the ring draining clockwise as the time runs
out. They sit in a row centred above the hero's head and follow the hero;
the flying name rises from above them. Drawn in screen space at the
interface's own size, like the keycap, so they stay crisp whatever the
world zoom. Nothing is drawn when no buff is active.

The owner first had these under the top-left HUD cluster and moved them
onto the character on 2026-09-20.
"""
from __future__ import annotations

import math

import pygame

from game import config
from ui import scale

LIFT_PX = 40        # design px from the hero's centre to the marks' bottom edge
GAP_PX = 6          # design px between two marks


def draw(surface: pygame.Surface, assets, hero_screen_pos, rows) -> None:
    """`rows` is `BuffSystem.rows()`: `(kind, fraction_left, icon_rig,
    colour)` per active buff."""
    if not rows:
        return
    side = scale.px(config.BUFF_MARK_PX)
    gap = scale.px(GAP_PX)
    ring_w = max(2, scale.px(3))
    hx, hy = hero_screen_pos
    total = len(rows) * side + (len(rows) - 1) * gap
    left = int(hx - total / 2)
    top = int(hy - scale.px(LIFT_PX) - side)
    for i, (kind, frac, rig, colour) in enumerate(rows):
        rect = pygame.Rect(left + i * (side + gap), top, side, side)
        disc = pygame.Surface((side, side), pygame.SRCALPHA)
        pygame.draw.circle(disc, (18, 20, 26, 170), (side // 2, side // 2), side // 2)
        surface.blit(disc, rect.topleft)
        inner = side - 2 * ring_w - 2
        icon = assets.image(rig, size=(inner, inner)) if rig else None
        if icon is not None:
            surface.blit(icon, icon.get_rect(center=rect.center))
        if frac > 0.0:
            # pygame arcs run counter-clockwise from `start` to `end`;
            # ending at the top makes the ring drain clockwise.
            start = math.pi / 2 - 2 * math.pi * frac
            pygame.draw.arc(surface, colour, rect.inflate(-ring_w, -ring_w),
                            start, math.pi / 2, ring_w)
