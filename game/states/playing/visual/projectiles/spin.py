"""A tumbling projectile: a short strip played on the shot's own clock (`spin`).

The Gnoll's thrown bone is four frames of a bone turning end over end, and it
is the first projectile in the game whose *art* animates -- every other shot is
a still (`thrown`, `arrow`) or a drawn shape (`bolt`). The frames already carry
the rotation, so this style does not rotate anything: turning a tumbling strip
by its heading would spin it twice.

The frame is picked from `proj.age`, which the pool resets on every reuse, so
two bones in flight are not in lockstep. `fx.fps` overrides the rig's own rate;
`fx.rig` names the strip, whose single animation is called `spin`. Falls back
to the `bolt` disc when the rig or its sheet is missing, exactly as `thrown`
does, so a missing file is a dull shot rather than a crash.

Wiring recorded in `journals/enemy_roster_expansion_journal.md` (R2).
"""
from __future__ import annotations

from game.states.playing.visual.projectiles import style
from game.states.playing.visual.projectiles.simple import bolt

ANIM = "spin"


def frame_index(assets, rig: str, age: float, fps: float | None) -> int | None:
    """Which frame of `rig`'s `spin` strip a shot of this age is showing, or
    None when the rig declares no such strip."""
    n = assets.frame_count(rig, ANIM)
    if n <= 0:
        return None
    rate = fps if fps else assets.fps(rig, ANIM)
    return int(max(0.0, age) * float(rate)) % n


@style("spin")
def spin(surface, sx, sy, p, ctx) -> None:
    rig = p.fx.get("rig") if p.fx else None
    if not rig:
        bolt(surface, sx, sy, p, ctx)
        return
    i = frame_index(ctx.assets, rig, getattr(p, "age", 0.0),
                    p.fx.get("fps") if p.fx else None)
    if i is None:
        bolt(surface, sx, sy, p, ctx)
        return
    z = ctx.zoom
    scale = ctx.assets.scale_for(rig)
    size = (max(1, round(scale[0] * z)), max(1, round(scale[1] * z))) if scale else None
    spr = ctx.assets.frame(rig, ANIM, i, size=size)
    if spr is None:
        bolt(surface, sx, sy, p, ctx)
        return
    surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
