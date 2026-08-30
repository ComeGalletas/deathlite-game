"""`arcane` -- the Arcane Bolt's layered FX (assets journal, AB4).

Over the bolt's disc: a blue-tinted `dust_puff` trailing behind, and a spinning
`arcane_circle` ring (row 2, already blue) in front. Both loop on the shared run
clock like `thunder` / `orbit`; per-weapon tuning (`circle_scale`,
`circle_spin_dps`, `dust_scale`, `dust_tint`) comes from `weapon_visuals.json`
`fx`. A missing sheet -> that layer is skipped, disc still drawn.
"""
from __future__ import annotations

import pygame

from game.states.playing.projectiles import style

_ANIM = "loop"


def _size(sc, z):
    return (max(1, round(sc[0] * z)), max(1, round(sc[1] * z))) if sc else None


@style("arcane")
def arcane(surface, sx, sy, p, ctx) -> None:
    z, a = ctx.zoom, ctx.assets
    cx, cy = int(sx), int(sy)
    fx = getattr(p, "fx", None) or {}

    # the bolt itself still reads through the FX
    pygame.draw.circle(surface, p.color, (cx, cy), max(2, round(p.radius * z)))

    # dust trail -- white pack recoloured via the multiply tint
    n = max(1, a.frame_count("dust_puff", _ANIM))
    idx = int(ctx.now * a.fps("dust_puff", _ANIM)) % n
    dust = a.frame("dust_puff", _ANIM, idx,
                   size=_size(fx.get("dust_scale") or a.scale_for("dust_puff"), z),
                   tint=fx.get("dust_tint"))
    if dust is not None:
        surface.blit(dust, dust.get_rect(center=(cx, cy)))

    # arcane ring -- spun when `circle_spin_dps` is set, else a plain frame
    n = max(1, a.frame_count("arcane_circle", _ANIM))
    idx = int(ctx.now * a.fps("arcane_circle", _ANIM)) % n
    size = _size(fx.get("circle_scale") or a.scale_for("arcane_circle"), z)
    spin = fx.get("circle_spin_dps")
    ring = (a.frame_rotated("arcane_circle", _ANIM, idx, ctx.now * float(spin), size=size)
            if spin else a.frame("arcane_circle", _ANIM, idx, size=size))
    if ring is not None:
        surface.blit(ring, ring.get_rect(center=(cx, cy)))
