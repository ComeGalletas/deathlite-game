"""The Controls block: the run's bindings as a column of grey keycaps with
a word beside each (journal: key_icons_journal.md, pass 4).

Drawn on the pause menu, to the right of its buttons. The rows follow the
chosen key layout (`config.KEY_LAYOUTS[game.key_layout]`), so swapping
WASD and the arrows on the Key layout row re-labels the Move and Aim rows
at once; the rest come from the same constants the run handles
(`KEY_INTERACT`, `KEY_TOGGLE_AUTO_ATTACK`) or the keys `PlayingState`
answers to (TAB, ESC). Reference caps are grey -- the blue cap is reserved
for "press this now" -- a word (`TAB`, `ESC`) takes the wide cap, and the
mouse is the cursor arrow on a square one (`keycap.MOUSE`).
"""
from __future__ import annotations

import pygame

from game import config, fonts, locale
from ui import keycap, scale
from ui import text as uitext

CAP = keycap.CAP_PX     # design px
CAP_GAP = 6             # between caps of one cluster (W A S D)
LABEL_GAP = 16          # cluster -> word
ROW_STEP = 44
HEADING_GAP = 40        # heading baseline -> first row
WORD_PX = 20            # the words' design size
EDGE = 16               # the least room left between a word and the surface's edge
CLICK = keycap.MOUSE    # the mouse has no keycode; the attack row's cap draws the cursor

_DIRECTIONS = ("up", "left", "down", "right")


def rows(game) -> list[tuple[list[str], str]]:
    """`[(cap labels, what they do), ...]` for the current layout."""
    layout = config.KEY_LAYOUTS[game.key_layout]
    move = [keycap.label_for(layout["move"][d][0]) for d in _DIRECTIONS]
    aim = [keycap.label_for(layout["aim"][d][0]) for d in _DIRECTIONS]
    return [
        (move, locale.t("controls.move")),
        (aim, locale.t("controls.aim")),
        ([CLICK], locale.t("controls.attack")),
        ([keycap.label_for(config.KEY_INTERACT)], locale.t("controls.interact")),
        ([keycap.label_for(config.KEY_TOGGLE_AUTO_ATTACK)], locale.t("controls.auto_attack")),
        ([keycap.label_for(pygame.K_TAB)], locale.t("controls.build")),
        ([keycap.label_for(pygame.K_ESCAPE)], locale.t("controls.pause")),
    ]


def cluster_width(labels: list[str]) -> int:
    """Design px across a cluster of caps."""
    w = sum(CAP * (keycap.WIDE_RATIO if keycap.is_wide(l) else 1) for l in labels)
    return w + CAP_GAP * (len(labels) - 1)


def draw(surface: pygame.Surface, assets, topleft, game, *,
         heading_font=None, colour="grey", cache=None) -> pygame.Rect:
    """Paint the block with its top-left at `topleft` (native px); returns
    the rect it covered. A caller that draws it every frame passes `cache`
    (a `ui.text_cache.TextCache`) for the caps' labels (RND-008.3).

    A word wider than the room left before the surface's edge steps down,
    then takes two lines, then trims (`_word_lines`, UI-014.11): the web
    profile's 1280 px pause screen puts the block's words at x 1142, and
    "Ataque automático" ran off it."""
    font = uitext.cached_font(fonts.body, WORD_PX)     # built once, kept across frames
    right_edge = surface.get_width() - scale.px(EDGE)
    heading_font = heading_font or fonts.heading(26)
    x0, y0 = int(topleft[0]), int(topleft[1])
    head = heading_font.render(locale.t("controls.title"), True, config.COLOR_ACCENT)
    surface.blit(head, (x0, y0))
    y = y0 + head.get_height() + scale.px(HEADING_GAP - 26)
    widest = max(cluster_width(labels) for labels, _ in rows(game))
    right = x0
    for labels, what in rows(game):
        x = x0
        for label in labels:
            wide = keycap.is_wide(label)
            w = scale.px(CAP * (keycap.WIDE_RATIO if wide else 1))
            keycap.draw_keycap(surface, assets, (x + w // 2, y), label,
                               state="raised", colour=colour, wide=wide, cache=cache)
            x += w + scale.px(CAP_GAP)
        tx = x0 + scale.px(widest + LABEL_GAP)
        room = right_edge - tx
        word_font, lines = _word_lines(font, what, room)
        line_h = word_font.get_linesize()
        for i, line in enumerate(lines):
            shown = uitext.ellipsize(word_font, line, room)
            if word_font.size(shown)[0] > room:
                continue                    # not even "..." fits: nothing past the edge
            text = word_font.render(shown, True, config.COLOR_TEXT)
            cy = y + int((i - (len(lines) - 1) / 2) * line_h)
            surface.blit(text, text.get_rect(midleft=(tx, cy)))
            right = max(right, tx + text.get_width())
        y += scale.px(ROW_STEP)
    return pygame.Rect(x0, y0, right - x0, y - y0)


def _word_lines(font, what: str, room: int):
    """`(font, lines)` for a row's word in `room` native px: whole at the
    block's size; else one line or two, whichever keeps the larger size
    (down to 70 %; one line on a tie) -- a 44 px row holds two ("Apuntar /
    (mantener)", "Ataque / automático"); else two lines at the smallest
    size, trimmed at the draw. Never a third line: it would crowd the
    next row."""
    if font.size(what)[0] <= room:
        return font, [what]
    floor = max(1, int(round(WORD_PX * 0.7)))
    for px in range(WORD_PX, floor - 1, -1):
        f = uitext.cached_font(fonts.body, px)
        if f.size(what)[0] <= room:
            return f, [what]
        lines = _two(f, what, room)
        if all(f.size(line)[0] <= room for line in lines):
            return f, lines
    smallest = uitext.cached_font(fonts.body, floor)
    return smallest, _two(smallest, what, room)


def _two(font, what: str, room: int) -> list[str]:
    """`what` wrapped to `room`, the rest folded into the second line."""
    lines = uitext.wrap(font, what, room)
    return lines[:1] + ([" ".join(lines[1:])] if len(lines) > 1 else [])
