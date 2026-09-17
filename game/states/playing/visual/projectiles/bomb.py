"""The thrown Bomb (`bomb`): the `bomb` rig's `spin` strip while the throw
is in the air and its `fuse` strip -- the lit fuse sparking above the ball --
once `Projectile.update` has halted it (`stop_after`) and it waits for the
blast. Both loops run off the shared run clock like `orbit` / `thunder`; the
frame is blitted by the rig's anchor (the centre of the ball) so the fuse
rises above the projectile position. Rig / sheet missing -> the disc
`bolt` drew before.

A Cluster Bomb bomblet wears this same rig at a smaller `fx.scale` and holds
`fuse` throughout, never `spin` (see `anim_for`).
"""
from __future__ import annotations

import pygame

from game.states.playing.visual.projectiles import style

_RIG = "bomb"


def anim_for(p) -> str:
    """`spin` while the bomb still moves, `fuse` once it has landed.

    A Cluster Bomb **bomblet** never rolls (owner, 2026-09-12): it wears the
    parent's sprite but holds the lit fuse from the moment it scatters, so a
    cluster reads as the explosion spreading outward rather than as three
    more bombs being thrown. It is identified by the `cluster` tag
    `TransientFx.scatter_bomblets` stamps on it -- the same tag that picks
    the smaller burst sheet and stops a bomblet scattering again.
    """
    if "cluster" in p.source_tags:
        return "fuse"
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
        tint = p.fx.get("tint")
        if tint:
            # An enemy's bomb is tinted the hostile red, the same way the
            # hostile arrow is, so a thrown bomb reads as incoming at a
            # glance (owner, 2026-09-17). `frame_rotated` at zero degrees is
            # the *additive* tint path -- plain `frame(tint=)` multiplies,
            # which on a dark bomb gives near-black rather than red. Zero
            # snaps to the identity rotation bucket, so nothing turns.
            spr = a.frame_rotated(_RIG, anim, idx, 0.0, size=size,
                                  tint=tuple(tint))
        else:
            spr = a.frame(_RIG, anim, idx, size=size)
    if spr is None:
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                           max(2, round(p.radius * z)))
        return
    ax, ay = a.anchor(_RIG)
    surface.blit(spr, (sx - ax * size[0] / bw, sy - ay * size[1] / bh))
