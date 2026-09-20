"""The Controls block: the run's bindings as a column of grey keycaps with
a word beside each (journal: key_icons_journal.md, pass 4).

Drawn on the pause menu, to the right of its buttons. The rows follow the
chosen key layout (`config.KEY_LAYOUTS[game.key_layout]`), so swapping
WASD and the arrows on the Key layout row re-labels the Move and Aim rows
at once; the rest come from the same constants the run handles
(`KEY_INTERACT`, `KEY_TOGGLE_AUTO_ATTACK`) or the keys `PlayingState`
answers to (TAB, ESC). Reference caps are grey -- the blue cap is reserved
for "press this now" -- and a word (`TAB`, `ESC`, `CLICK`) takes the wide
cap.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import keycap, scale

CAP = keycap.CAP_PX     # design px
CAP_GAP = 6             # between caps of one cluster (W A S D)
LABEL_GAP = 16          # cluster -> word
ROW_STEP = 44
HEADING_GAP = 40        # heading baseline -> first row
CLICK = "CLICK"         # the mouse has no keycode; the attack row's wide cap says this

_DIRECTIONS = ("up", "left", "down", "right")


def rows(game) -> list[tuple[list[str], str]]:
    """`[(cap labels, what they do), ...]` for the current layout."""
    layout = config.KEY_LAYOUTS[game.key_layout]
    move = [keycap.label_for(layout["move"][d][0]) for d in _DIRECTIONS]
    aim = [keycap.label_for(layout["aim"][d][0]) for d in _DIRECTIONS]
    return [
        (move, "Move"),
        (aim, "Aim (hold)"),
        ([CLICK], "Attack"),
        ([keycap.label_for(config.KEY_INTERACT)], "Interact"),
        ([keycap.label_for(config.KEY_TOGGLE_AUTO_ATTACK)], "Auto attack"),
        ([keycap.label_for(pygame.K_TAB)], "Build"),
        ([keycap.label_for(pygame.K_ESCAPE)], "Pause"),
    ]


def cluster_width(labels: list[str]) -> int:
    """Design px across a cluster of caps."""
    w = sum(CAP * (keycap.WIDE_RATIO if keycap.is_wide(l) else 1) for l in labels)
    return w + CAP_GAP * (len(labels) - 1)


def draw(surface: pygame.Surface, assets, topleft, game, *,
         font=None, heading_font=None, colour="grey") -> pygame.Rect:
    """Paint the block with its top-left at `topleft` (native px); returns
    the rect it covered."""
    font = font or fonts.body(20)
    heading_font = heading_font or fonts.heading(26)
    x0, y0 = int(topleft[0]), int(topleft[1])
    head = heading_font.render("Controls", True, config.COLOR_ACCENT)
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
                               state="raised", colour=colour, wide=wide)
            x += w + scale.px(CAP_GAP)
        text = font.render(what, True, config.COLOR_TEXT)
        tx = x0 + scale.px(widest + LABEL_GAP)
        surface.blit(text, text.get_rect(midleft=(tx, y)))
        right = max(right, tx + text.get_width())
        y += scale.px(ROW_STEP)
    return pygame.Rect(x0, y0, right - x0, y - y0)
