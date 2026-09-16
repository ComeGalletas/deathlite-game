"""Text layout helpers shared by the screens.

`wrap` breaks a string into lines that fit a pixel width *as the given font
renders them* -- greedy by word, measured with `Font.size`, so a line of wide
glyphs wraps sooner than a line of narrow ones. It replaced two
character-count wrappers (34 chars on the hero cards, 30 on the level-up
cards) that only approximated the card width. A single word wider than the
limit is emitted on its own line rather than broken mid-word. There is no
vertical clamp here; a caller that needs one caps the list it gets back.
"""
from __future__ import annotations

import pygame

from game import config


def wrap(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Lines of `text` no wider than `max_width` px in `font`."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        candidate = f"{cur} {word}".strip()
        if cur and font.size(candidate)[0] > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


def ellipsize(font: pygame.font.Font, text: str, max_width: int) -> str:
    """`text` trimmed with a trailing `...` until it renders inside
    `max_width`, measured in the font that will draw it.

    `wrap`'s sibling for the places a second line is not available: a column
    row, where the next line belongs to the next item. Nothing here clips at
    the blit, so without this a long name simply draws over its neighbour --
    38 % of generated item names are wider than the victory screen's Run
    column, and the widest is nearly double it.

    Returns `text` unchanged when it already fits, and never returns more than
    the ellipsis: a width too small for even that yields `...`.
    """
    text = str(text)
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    dots = "..."
    room = max_width - font.size(dots)[0]
    if room <= 0:
        return dots
    # Longest prefix that still fits beside the ellipsis. Linear from the end
    # rather than bisected: these are short strings drawn once per frame at
    # most, and a scan cannot disagree with `size()` about where to cut.
    cut = len(text)
    while cut > 0 and font.size(text[:cut])[0] > room:
        cut -= 1
    return text[:cut].rstrip() + dots


def shadowed(font: pygame.font.Font, text: str, colour, *, shadow=(28, 28, 34),
             offset=(2, 2)) -> pygame.Surface:
    """`text` in `colour` over a copy in `shadow` displaced by `offset`: the
    drop shadow that lifts a light title off light card art (owner,
    2026-09-10). The result is `offset` larger than the plain render, with
    the plain text at its top-left."""
    top = font.render(text, True, colour)
    under = font.render(text, True, shadow)
    # Design px: the drop grows with the interface (`ui/scale`).
    dx = int(round(offset[0] * config.RENDER_SCALE))
    dy = int(round(offset[1] * config.RENDER_SCALE))
    out = pygame.Surface((top.get_width() + abs(dx), top.get_height() + abs(dy)), pygame.SRCALPHA)
    out.blit(under, (max(0, dx), max(0, dy)))
    out.blit(top, (max(0, -dx), max(0, -dy)))
    return out
