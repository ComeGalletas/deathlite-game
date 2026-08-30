"""`thunder` -- the Thunder Orb's layered lightning FX (assets journal, TO3).

Two looping animations centred on the orb: `thunder_aura` (an amber energy ring)
behind, `thunder_ball` (a grey crackling lightning ball) in front, over the orb's
own disc. Neither faces travel, so they blit straight -- no rotation, no
per-frame crop. Both run off the shared run clock (`ctx.now`), like the `orbit`
flame: phase-locked, no per-projectile state. A missing sheet -> that layer is
skipped, so the style degrades to the plain disc.
"""
from __future__ import annotations

import pygame

from game.states.playing.projectiles import style

_ANIM = "loop"
# (rig, `fx` key) -- aura first (outer glow, behind), then the ball, in front.
_LAYERS = (("thunder_aura", "aura_scale"), ("thunder_ball", "ball_scale"))


@style("thunder")
def thunder(surface, sx, sy, p, ctx) -> None:
    z, a = ctx.zoom, ctx.assets
    cx, cy = int(sx), int(sy)
    fx = getattr(p, "fx", None) or {}

    # the orb itself still reads through the sparks
    pygame.draw.circle(surface, p.color, (cx, cy), max(2, round(p.radius * z)))

    for rig, fx_key in _LAYERS:
        n = max(1, a.frame_count(rig, _ANIM))
        idx = int(ctx.now * a.fps(rig, _ANIM)) % n
        sc = fx.get(fx_key) or a.scale_for(rig)   # weapon_visuals.json fine-tune
        size = None if sc is None else (max(1, round(sc[0] * z)),
                                        max(1, round(sc[1] * z)))
        spr = a.frame(rig, _ANIM, idx, size=size)
        if spr is not None:
            surface.blit(spr, spr.get_rect(center=(cx, cy)))
