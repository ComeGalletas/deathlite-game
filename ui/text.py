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
