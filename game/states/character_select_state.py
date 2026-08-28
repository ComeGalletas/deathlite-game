"""CHARACTER_SELECT: pick a hero before a run (spec 4.1).

Shows each character's identity line, defining trait and starting weapon so the
choice is about playstyle, not just numbers.
"""
from __future__ import annotations

import pygame

from game import config
from game.content import get_content
from game.state import State


class CharacterSelectState(State):
    def enter(self, **kwargs) -> None:
        self._dev = bool(kwargs.get("dev", False))   # forwarded to the run
        self.content = get_content()
        self.ids = list(self.content.characters.keys())
        self.index = 0
        # Per-run difficulty (never persisted). Up / Down cycles it.
        self.diff_index = config.DIFFICULTY_ORDER.index(config.DIFFICULTY_DEFAULT)
        self._title = pygame.font.SysFont("georgia", 44, bold=True)
        self._name = pygame.font.SysFont("georgia", 30, bold=True)
        self._body = pygame.font.SysFont("georgia", 20)
        self._hint = pygame.font.SysFont("georgia", 16)

    @property
    def difficulty(self) -> str:
        return config.DIFFICULTY_ORDER[self.diff_index]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.index = (self.index - 1) % len(self.ids)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.index = (self.index + 1) % len(self.ids)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.diff_index = (self.diff_index - 1) % len(config.DIFFICULTY_ORDER)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.diff_index = (self.diff_index + 1) % len(config.DIFFICULTY_ORDER)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from game.states.playing_state import PlayingState
            self.game.state_machine.change(PlayingState(self.game),
                                           character_id=self.ids[self.index],
                                           difficulty=self.difficulty,
                                           dev=self._dev)
        elif event.key == pygame.K_ESCAPE:
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        w = surface.get_width()
        cx = w // 2

        title = self._title.render("Choose your hero", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 80)))

        n = len(self.ids)
        card_w, gap = 340, 36
        x0 = (w - (n * card_w + (n - 1) * gap)) // 2
        y, card_h = 170, 340
        for i, cid in enumerate(self.ids):
            c = self.content.characters[cid]
            x = x0 + i * (card_w + gap)
            rect = pygame.Rect(x, y, card_w, card_h)
            focused = i == self.index
            pygame.draw.rect(surface, (46, 42, 70) if focused else (26, 24, 38),
                             rect, border_radius=12)
            pygame.draw.rect(surface,
                             config.COLOR_ACCENT if focused else config.COLOR_WORLD_BORDER,
                             rect, width=3 if focused else 2, border_radius=12)

            name = self._name.render(c["name"], True, config.COLOR_TEXT)
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + 16)))

            rows = _wrap(c["identity"], 34) + [
                "", f"Trait - {c['trait_name']}",
            ] + _wrap(c["trait_desc"], 34) + [
                "", f"Starts with: {self._weapon_name(c['starting_weapon'])}",
            ]
            for j, line in enumerate(rows):
                colour = config.COLOR_TEXT_DIM
                if line.startswith("Trait") or line.startswith("Starts"):
                    colour = config.COLOR_TEXT
                surf = self._body.render(line, True, colour)
                surface.blit(surf, surf.get_rect(midtop=(rect.centerx, y + 66 + j * 24)))

        diff_label = config.DIFFICULTY_LABELS[self.difficulty]
        diff = self._name.render(f"Difficulty:  {diff_label}", True, config.COLOR_ACCENT)
        surface.blit(diff, diff.get_rect(center=(cx, y + card_h + 30)))

        hint = self._hint.render(
            "Left / Right hero    -    Up / Down difficulty    -    ENTER begin    -    ESC back",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, y + card_h + 62)))

    def _weapon_name(self, wid: str) -> str:
        return self.content.weapons.get(wid, {}).get("name", wid)


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 <= width:
            cur = f"{cur} {word}".strip()
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines
