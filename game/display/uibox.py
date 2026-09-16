"""The UI box: the centred `config.UI_WIDTH x UI_HEIGHT` region of the
render surface that the HUD, the menus and the overlay panels draw into.

On a 16:9 render the box *is* the surface. On the 21:9 render
(journal "Dynamic window scaling", "Ultrawide render extent",
2026-09-15) the surface is 2100x900 and the box is the middle 1600x900:
the world fills the width, the interface stays where a 16:9 player sees
it. Screens get the box as a subsurface, so their code is untouched;
mouse events are shifted by the box's offset before a screen sees them
(`translate_event`), so their hit rects keep matching.

Pure helpers over a surface; nothing here knows about the window.
"""
from __future__ import annotations

import pygame

from game import config


def rect(surface: pygame.Surface) -> pygame.Rect:
    """The box, centred on `surface` and never larger than it: the 1600x900
    design at `config.RENDER_SCALE` (`ui/scale.py`), so on a native 3440x1440
    surface it is 2560x1440 with 440 px margins."""
    w, h = surface.get_size()
    bw = min(int(round(config.UI_WIDTH * config.RENDER_SCALE)), w)
    bh = min(int(round(config.UI_HEIGHT * config.RENDER_SCALE)), h)
    return pygame.Rect((w - bw) // 2, (h - bh) // 2, bw, bh)


def offset(surface: pygame.Surface) -> tuple[int, int]:
    r = rect(surface)
    return (r.x, r.y)


def box(surface: pygame.Surface) -> pygame.Surface:
    """`surface` itself when the box covers it, else the box subsurface."""
    r = rect(surface)
    if r.size == surface.get_size():
        return surface
    return surface.subsurface(r)


def translate_event(event: pygame.event.Event, surface: pygame.Surface) -> pygame.event.Event:
    """The same event with `pos` in box coordinates. Events without a
    position, and surfaces the box covers, come back unchanged."""
    pos = getattr(event, "pos", None)
    if pos is None:
        return event
    ox, oy = offset(surface)
    if ox == 0 and oy == 0:
        return event
    d = dict(event.dict)
    d["pos"] = (pos[0] - ox, pos[1] - oy)
    return pygame.event.Event(event.type, d)
