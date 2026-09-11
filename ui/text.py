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


def shadowed(font: pygame.font.Font, text: str, colour, *, shadow=(28, 28, 34),
             offset=(2, 2)) -> pygame.Surface:
    """`text` in `colour` over a copy in `shadow` displaced by `offset`: the
    drop shadow that lifts a light title off light card art (owner,
    2026-09-10). The result is `offset` larger than the plain render, with
    the plain text at its top-left."""
    top = font.render(text, True, colour)
    under = font.render(text, True, shadow)
    dx, dy = int(offset[0]), int(offset[1])
    out = pygame.Surface((top.get_width() + abs(dx), top.get_height() + abs(dy)), pygame.SRCALPHA)
    out.blit(under, (max(0, dx), max(0, dy)))
    out.blit(top, (max(0, -dx), max(0, -dy)))
    return out
