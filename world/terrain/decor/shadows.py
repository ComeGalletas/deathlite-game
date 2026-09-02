"""Tree drop shadows.

One soft round shade patch per skinned tree. Split from the skinning that calls
it because it is the only part of the decor bake that paints its own art rather
than placing authored art.
"""
from __future__ import annotations

import pygame


def build_tree_shadows(store, conf: dict) -> None:
    """Build one soft round shade patch for every skinned tree obstacle."""
    spec = conf.get("tree_shadow", {})
    rs = float(spec.get("radius_scale", 1.9))
    padding = int(spec.get("radius_padding", 0))
    render_radius = conf.get("render_radius", {})
    color = tuple(spec.get("color", (12, 18, 22)))[:3]
    alpha = int(spec.get("alpha", 66))
    cache: dict[int, pygame.Surface] = {}

    def disc(r: int) -> pygame.Surface:
        if r not in cache:
            surf = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            # a few concentric fills -> denser at the centre, soft at the rim
            for k in range(4, 0, -1):
                aa = max(1, round(alpha * k / 4 * 0.62))
                pygame.draw.circle(surf, (*color, aa), (r, r), r * k / 4)
            cache[r] = surf
        return cache[r]

    for i, o in enumerate(store.obstacles):
        if o.kind == "tree" and i in store._decos:
            draw_r = float(render_radius.get(o.kind, o.radius))
            r = max(1, round(draw_r * rs) + padding)
            store._tree_shadows[i] = (o.pos.x, o.pos.y, r, disc(r))
