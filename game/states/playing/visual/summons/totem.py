"""The Grave Totem: a planted pillar of blue flame.

Blits the `grave_totem` rig frame the summon's own `Animator` is holding --
`appear` as it is planted, `idle` between bolts, `attack` (the burst) once
per bolt, `disappear` over its last second (`entities/summon.py`, the totem
phases). The frame lands by the rig's anchor, bottom-centre on the base
ring, so the pillar stands on its collider as the primitive did.

Falls back to the rounded rectangle + core dot when the rig or a sheet is
absent (an empty `assets/` still plays).
"""
from __future__ import annotations

import pygame

from game.states.playing.visual.summons import summon_style
from game.states.playing.visual import elements as element_fx


@summon_style("totem")
def totem(surface, sx, sy, s, ctx) -> None:
    z = ctx.zoom
    anim = getattr(s, "anim", None)
    if anim is not None:
        assets = ctx.assets
        # A summon wears its summoning weapon's element (M13): summons are
        # infusable, and the pillar is recoloured offline, one sheet per
        # action per element. The Animator still times the strip.
        rig = element_fx.variant_rig(assets, anim.rig,
                                     getattr(s, "infusion", None))
        bw, bh = assets.scale_for(rig) or (32, 48)
        frame = assets.frame(rig, anim.anim, anim.index,
                             size=(max(1, round(bw * z)), max(1, round(bh * z))))
        if frame is not None:
            ax, ay = assets.anchor(rig)
            surface.blit(frame, (int(sx - ax * z), int(sy - ay * z)))
            return

    pygame.draw.rect(surface, s.color,
                     (int(sx - 7 * z), int(sy - 12 * z),
                      round(14 * z), round(24 * z)), border_radius=3)
    pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(3 * z))
