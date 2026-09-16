"""The level medallion: `assets/ui/01.png`'s gem seated in its socket ring.

The socket (sheet row 0) and the gem body (row 1) are concentric inside their
own 48x48 cells, so the pair composites at a shared origin with no offset
table. Order matters: the gem goes down first and the ring over it, so the
ring's inner edge covers the gem's outline rather than the gem covering the
ring -- which is what makes it read as a stone set into metal.

The cells are square, so `size` scales both axes and the art keeps its shape.
"""
from __future__ import annotations

import pygame

_cache: dict[tuple, pygame.Surface | None] = {}


def medallion(assets, *, socket: str, core: str, size: int):
    """The seated gem at `size` px square, or `None` when the art is missing."""
    size = int(size)
    key = (socket, core, size)
    if key in _cache:
        return _cache[key]

    ring = assets.image(socket)
    if ring is None or size <= 0:
        _cache[key] = None
        return None

    out = pygame.Surface(ring.get_size(), pygame.SRCALPHA)
    gem = assets.image(core)
    if gem is not None:
        out.blit(gem, (0, 0))
    out.blit(ring, (0, 0))
    if out.get_width() != size:
        out = pygame.transform.scale(out, (size, size))

    _cache[key] = out
    return out


def core_centre(assets, *, core: str, size: int) -> tuple[float, float]:
    """Where the seated gem's face is, in a `size` px medallion: the centre
    of the core art's opaque bounding box at that size (the ring's outline
    is not symmetric around it, so the sprite's own centre is ~half a pixel
    off). The level number is centred here (`ui/hud.py`). Falls back to the
    sprite centre when the core art is missing."""
    size = int(size)
    key = ("centre", core, size)
    if key in _cache:
        return _cache[key]
    gem = assets.image(core)
    if gem is None or size <= 0:
        out = (size / 2.0, size / 2.0)
    else:
        if gem.get_width() != size:
            gem = pygame.transform.scale(gem, (size, size))
        ink = gem.get_bounding_rect()
        out = (ink.x + ink.w / 2.0, ink.y + ink.h / 2.0)
    _cache[key] = out
    return out


def clear_cache() -> None:
    """Test helper: drop cached medallions."""
    _cache.clear()
