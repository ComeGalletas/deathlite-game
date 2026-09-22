"""A shape per element, so hue is never the only thing telling them apart.

The design asks for this outright (§8, colourblind proposal). Each marker is
a tiny polygon in a unit square, scaled and drawn at the top of an aura
ring, so Fire and Thunder are a flame and a bolt as well as orange and
yellow.

They are shapes rather than glyphs because a five-pixel letter is unreadable
at this zoom and a five-pixel silhouette is not.
"""
from __future__ import annotations

import pygame

# Unit-square outlines, (0, 0) top-left to (1, 1) bottom-right.
SHAPES: dict[str, tuple[tuple[float, float], ...]] = {
    # A pointed teardrop.
    "flame": ((0.5, 0.0), (0.9, 0.55), (0.7, 1.0), (0.3, 1.0), (0.1, 0.55)),
    # A four-pointed shard.
    "shard": ((0.5, 0.0), (0.72, 0.5), (0.5, 1.0), (0.28, 0.5)),
    # A zigzag bolt.
    "bolt": ((0.62, 0.0), (0.2, 0.55), (0.45, 0.55), (0.34, 1.0),
             (0.82, 0.42), (0.55, 0.42)),
    # An open swirl, drawn as a thick comma.
    "swirl": ((0.15, 0.25), (0.75, 0.05), (1.0, 0.45), (0.55, 0.65),
              (0.85, 0.8), (0.2, 0.95), (0.0, 0.6)),
}

FALLBACK = "shard"


def points(marker: str, cx: float, cy: float, size: float):
    """The marker's outline, centred on `(cx, cy)` and `size` px across."""
    shape = SHAPES.get(marker) or SHAPES[FALLBACK]
    half = size * 0.5
    return [(cx + (x - 0.5) * size, cy + (y - 0.5) * size) for x, y in shape] \
        if half else []


def draw(surface, marker: str, cx: float, cy: float, size: float, colour,
         alpha: int = 255) -> None:
    """Fill the marker, with a dark outline so it survives a light
    background the way the dev inspector's labels do."""
    pts = points(marker, cx, cy, size)
    if len(pts) < 3:
        return
    pad = 3
    box = pygame.Rect(0, 0, int(size) + pad * 2, int(size) + pad * 2)
    layer = pygame.Surface(box.size, pygame.SRCALPHA)
    local = [(x - cx + box.width / 2, y - cy + box.height / 2) for x, y in pts]
    pygame.draw.polygon(layer, (*colour, alpha), local)
    pygame.draw.polygon(layer, (18, 16, 24, min(255, alpha)), local, 1)
    surface.blit(layer, (int(cx - box.width / 2), int(cy - box.height / 2)))
