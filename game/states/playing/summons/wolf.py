"""The Spirit Wolf: a roaming melee summon.

Blits the `spirit_wolf` rig frame the summon's own `Animator` is holding
(`run_{side}` while chasing / poised, `bite_{side}` for ~0.3 s after a bite --
see `entities/summon.py`). Falls back to the WA1 colour disc + bright core when
the rig / sheet is absent.
"""
from __future__ import annotations

import pygame

from game.states.playing.summons import summon_style


@summon_style("wolf")
def wolf(surface, sx, sy, s, ctx) -> None:
    z = ctx.zoom
    anim = getattr(s, "anim", None)
    if anim is not None:
        assets = ctx.assets
        rig = anim.rig
        bw, bh = assets.scale_for(rig) or (32, 21)
        frame = anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))))
        if frame is not None:
            ax, ay = assets.anchor(rig)
            surface.blit(frame, (int(sx - ax * z), int(sy - ay * z)))
            return

    pygame.draw.circle(surface, s.color, (int(sx), int(sy)), round(9 * z))
    pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(3 * z))
