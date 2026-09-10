"""The thrown Bomb (`bomb`): the `bomb` rig's `spin` strip while the throw
is in the air and its `fuse` strip -- the lit fuse sparking above the ball --
once `Projectile.update` has halted it (`stop_after`) and it waits for the
blast. Both loops run off the shared run clock like `orbit` / `thunder`; the
frame is blitted by the rig's anchor (the centre of the ball) so the fuse
rises above the projectile position. Rig / sheet missing -> the disc
`bolt` drew before.
"""
from __future__ import annotations

import pygame

from game.states.playing.projectiles import style

_RIG = "bomb"


def anim_for(p) -> str:
    """`spin` while the bomb still moves, `fuse` once it has landed."""
    return "spin" if (p.vel.x or p.vel.y) else "fuse"


@style("bomb")
def bomb(surface, sx, sy, p, ctx) -> None:
    a, z = ctx.assets, ctx.zoom
    anim = anim_for(p)
    n = a.frame_count(_RIG, anim)
    spr = None
    if n > 0:
        idx = int(ctx.now * a.fps(_RIG, anim)) % n
        bw, bh = a.scale_for(_RIG)
        sc = p.fx.get("scale") or (bw, bh)         # weapon_visuals.json fine-tune
        size = (max(1, round(sc[0] * z)), max(1, round(sc[1] * z)))
        spr = a.frame(_RIG, anim, idx, size=size)
    if spr is None:
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                           max(2, round(p.radius * z)))
        return
    ax, ay = a.anchor(_RIG)
    surface.blit(spr, (sx - ax * size[0] / bw, sy - ay * size[1] / bh))
