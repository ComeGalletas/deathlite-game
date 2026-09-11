"""A thrown blade: one still sprite rotated to the shot's heading (`thrown`).

The Fan of Blades (Daggers Forge) throws four daggers; each draws the
`throwing_dagger` rig turned so its tip leads. The rig is named by the
weapon visual's `fx.rig`; the art's own heading (the direction its tip
points in the file, screen-CW degrees, 0 = +x) is the rig's `heading_deg`,
so any diagonal or vertical art can be dropped in without re-drawing it.
Falls back to the `bolt` disc when the rig or its sheet is missing.

Wiring recorded in `journals/assets_journal.md` ("Throwing dagger").
"""
from __future__ import annotations

import math

from game.states.playing.projectiles import style
from game.states.playing.projectiles.simple import bolt


def heading_of(p) -> float:
    """The shot's screen-CW heading in degrees (0 = +x)."""
    return math.degrees(math.atan2(p.vel.y, p.vel.x))


def rotation_for(assets, rig: str, heading: float) -> float:
    """How far to turn the rig's art so its tip leads along `heading`."""
    r = assets.rig(rig) or {}
    return heading - float(r.get("heading_deg", 0.0))


@style("thrown")
def thrown(surface, sx, sy, p, ctx) -> None:
    rig = p.fx.get("rig") if p.fx else None
    if not rig:
        bolt(surface, sx, sy, p, ctx)
        return
    z = ctx.zoom
    scale = ctx.assets.scale_for(rig)
    size = (max(1, round(scale[0] * z)), max(1, round(scale[1] * z))) if scale else None
    spr = ctx.assets.rotated(rig, rotation_for(ctx.assets, rig, heading_of(p)), size=size)
    if spr is None:
        bolt(surface, sx, sy, p, ctx)
        return
    surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
