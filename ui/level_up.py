"""Rendering for the level-up choice screen (spec 3.5 / 3.6).

Pure presentation: given the list of `Upgrade` choices and the highlighted
index, draw three cards. Input handling stays in `LevelUpState`; the panel
only *records* where it painted each card (`hits`, a `ui.mouse.HitMap`) so
the state can answer the mouse without knowing the geometry.

The cards are the pack's 9-slice buttons (`ui.widgets.draw_button`, shape
`panel`): gold for the selected card, the pressed sheet while the mouse
button is held on a card (`pressed`), blue otherwise. Without `assets` the
flat rounded rectangles of old are drawn instead.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import widgets
from ui.mouse import HitMap
from ui.text import wrap

# The cards grew 15 px downwards (owner, 2026-09-04) so the description's
# last line and the tag line sit inside the art's flat centre, not on its
# bottom bevel: the top edge still centres as a 200-tall card did.
_CARD_TOP_H = 200
_CARD_H = 215
_CARD_TEXT_INSET = 19       # description wraps to the card width minus this each side (16 + 3 px)


class LevelUpPanel:
    def __init__(self) -> None:
        self._title = fonts.heading(40)
        self._name = fonts.heading(24)
        self._desc = fonts.body(18)
        self._hint = fonts.body(16)
        self.hits = HitMap()          # card index -> rect, rebuilt every draw

    def draw(self, surface: pygame.Surface, choices, selected: int, *,
             assets=None, pressed=None) -> None:
        w, h = surface.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((8, 6, 16, 200))
        surface.blit(dim, (0, 0))

        title = self._title.render("Level Up  -  choose one", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, 110)))

        n = len(choices)
        card_w, card_h = 340, _CARD_H
        gap = 40
        total = n * card_w + (n - 1) * gap
        x0 = (w - total) // 2
        y = h // 2 - _CARD_TOP_H // 2       # the top edge stays where the 200-tall card had it

        self.hits.clear()
        for i, up in enumerate(choices):
            x = x0 + i * (card_w + gap)
            rect = self.hits.add(pygame.Rect(x, y, card_w, card_h), i)
            state = ("pressed" if pressed == i
                     else "hover" if i == selected else "normal")
            widgets.draw_button(surface, assets, rect, None, state=state, shape="panel")
            dy = widgets.PRESSED_DY if state == "pressed" else 0

            # Text on the light card: the name is a title (title face, black);
            # badge, description and tags are the dark grey.
            key_badge = self._name.render(f"{i + 1}", True, config.COLOR_ON_BUTTON_DIM)
            surface.blit(key_badge, (x + 14, y + 10 + dy))

            name = self._name.render(up.title, True, config.COLOR_ON_BUTTON)
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + 46 + dy)))

            for j, line in enumerate(wrap(self._desc, up.description,
                                          card_w - 2 * _CARD_TEXT_INSET)):
                d = self._desc.render(line, True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(d, d.get_rect(midtop=(rect.centerx, y + 92 + j * 24 + dy)))

            if up.tags:
                tag = self._hint.render(" ".join(up.tags), True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(tag, tag.get_rect(midbottom=(rect.centerx, y + card_h - 14 + dy)))

        hint = self._hint.render(
            "1/2/3 or Left/Right + Enter to pick    -    or click a card",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, y + card_h + 60)))

