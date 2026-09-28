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

import re

import pygame

from game import config


# Where a line may break: any whitespace `str.split()` breaks at, except the
# no-break spaces (U+00A0, figure U+2007, narrow U+202F). Spanish text puts
# one between a number and its unit ("+25 %", UI-014.D7) precisely so the
# two stay on one line.
_BREAK = re.compile(r"[^\S   ]+")


def wrap(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Lines of `text` no wider than `max_width` px in `font`. A no-break
    space (U+00A0) keeps the words either side of it on one line."""
    lines: list[str] = []
    cur = ""
    for word in (w for w in _BREAK.split(text) if w):
        # Not `.strip()`: that would eat a no-break space at a word's edge.
        candidate = f"{cur} {word}" if cur else word
        if cur and font.size(candidate)[0] > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


_FIT_CACHE: dict[tuple, pygame.font.Font] = {}
_quit_hooked = False


def _forget_fonts() -> None:
    """`pygame.quit()` invalidates every `Font`: one used after a
    quit / init cycle is an access violation (see `game/fonts.py`, which
    keeps no cache for this reason). `pygame.register_quit` calls this on
    the next quit, once; `cached_font` re-arms it when it caches again."""
    global _quit_hooked
    _FIT_CACHE.clear()
    _quit_hooked = False


def fit_font(role, px: int, text: str, max_width: int, *,
             min_ratio: float = 0.7, **kwargs) -> pygame.font.Font:
    """The largest `role(size)` font, from design size `px` down to
    `px * min_ratio`, in which `text` is no wider than `max_width` native px;
    the smallest when none fits. `role` is a `game.fonts` role (`body`,
    `heading`); `kwargs` pass through to it.

    For a label whose slot is fixed and whose text is not: a translation
    longer than the English it was laid out for (UI-014.7) steps down in
    size rather than running into its neighbour. Fonts are cached by role,
    native size and options, so a label drawn every frame builds none; the
    cache is dropped when pygame quits (`_forget_fonts`)."""
    floor = max(1, int(round(px * min_ratio)))
    font = None
    for size in range(int(px), floor - 1, -1):
        font = cached_font(role, size, **kwargs)
        if font.size(text)[0] <= max_width:
            return font
    return font


def cached_font(role, px: int, **kwargs) -> pygame.font.Font:
    """`role(px, **kwargs)`, built once per render scale and kept until
    pygame quits: for text that steps down in size every frame (`fit_font`,
    the level-up card descriptions)."""
    global _quit_hooked
    if not _quit_hooked:
        pygame.register_quit(_forget_fonts)
        _quit_hooked = True
    key = (role, config.RENDER_SCALE, int(px), tuple(sorted(kwargs.items())))
    font = _FIT_CACHE.get(key)
    if font is None:
        font = _FIT_CACHE[key] = role(int(px), **kwargs)
    return font


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
