"""Rendering for the level-up choice screen (spec 3.5 / 3.6).

Pure presentation: given the list of `Upgrade` choices and the highlighted
index, draw three cards. Input handling stays in `LevelUpState`.
"""
from __future__ import annotations

import pygame

from game import config, fonts


class LevelUpPanel:
    def __init__(self) -> None:
        self._title = fonts.heading(40)
        self._name = fonts.heading(24)
        self._desc = fonts.body(18)
        self._hint = fonts.body(16)

    def draw(self, surface: pygame.Surface, choices, selected: int) -> None:
        w, h = surface.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((8, 6, 16, 200))
        surface.blit(dim, (0, 0))

        title = self._title.render("Level Up  -  choose one", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, 110)))

        n = len(choices)
        card_w, card_h = 340, 200
        gap = 40
        total = n * card_w + (n - 1) * gap
        x0 = (w - total) // 2
        y = h // 2 - card_h // 2

        for i, up in enumerate(choices):
            x = x0 + i * (card_w + gap)
            rect = pygame.Rect(x, y, card_w, card_h)
            focused = (i == selected)
            pygame.draw.rect(surface, (28, 26, 40) if not focused else (48, 44, 74),
                             rect, border_radius=12)
            pygame.draw.rect(surface,
                             config.COLOR_ACCENT if focused else config.COLOR_WORLD_BORDER,
                             rect, width=3 if focused else 2, border_radius=12)

            key_badge = self._name.render(f"{i + 1}", True, config.COLOR_TEXT_DIM)
            surface.blit(key_badge, (x + 14, y + 10))

            name = self._name.render(up.title, True, config.COLOR_TEXT)
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + 46)))

            for j, line in enumerate(_wrap(up.description, 30)):
                d = self._desc.render(line, True, config.COLOR_TEXT_DIM)
                surface.blit(d, d.get_rect(midtop=(rect.centerx, y + 92 + j * 24)))

            if up.tags:
                tag = self._hint.render(" ".join(up.tags), True, (120, 130, 160))
                surface.blit(tag, tag.get_rect(midbottom=(rect.centerx, y + card_h - 14)))

        hint = self._hint.render(
            "1/2/3 or Left/Right + Enter to pick", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, y + card_h + 60)))


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if len(cur) + len(word) + 1 <= width:
            cur = f"{cur} {word}".strip()
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines
