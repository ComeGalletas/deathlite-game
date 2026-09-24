"""The faint element glow behind an elemental buff building (CMB-009.1).

A buff building that rolled an element carries it on `Interactable.element`
(M7), but the obstacle draws the building and nothing drew the element, so
the player learnt it only by using the building. This paints a soft disc in
the element's tint at the building's foot, from the flat terrace pass that
runs before the actors -- so the building art covers its centre and only
the rim shows, the standing order for element effects (they sit under
sprites; only reactions draw on top).

The disc is `visual/glow.py`'s `GlowCache` with the glow block of
`data/world/buildings.json` -> `elements.glow` as its config: `scale` is
the diameter as a multiple of the building's interaction diameter, and the
alpha breathes between `alpha_min` and `alpha_max` over `period` seconds,
quantised to `steps` so every value hits a cached surface. It goes out once
the building is used. The Monastery rolls no element, so it never glows.
"""
from __future__ import annotations

from game.states.playing.visual.glow import GlowCache, pulse_alpha, quantise


class BuildingGlow:
    __slots__ = ("cfg", "cache")

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.cache = GlowCache(cfg)

    def draw(self, surface, camera, it, tint, now: float) -> bool:
        """Blit the glow under interactable `it` if it carries an element and
        is unused. `tint` maps an element to its colour. Returns whether a
        glow was drawn."""
        if it.element is None or it.used:
            return False
        d = self.cache.diameter(2.0 * it.radius, camera.zoom)
        alpha = quantise(pulse_alpha(now, self.cfg), self.cfg)
        surf = self.cache.surface(d, alpha, tint(it.element))
        if surf is None:
            return False
        sx, sy = camera.world_to_screen(it.pos)
        surface.blit(surf, (round(sx - d / 2), round(sy - d / 2)))
        return True
