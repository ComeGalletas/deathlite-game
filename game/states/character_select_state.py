"""CHARACTER_SELECT: pick a hero before a run (spec 4.1).

Shows each character's identity line, defining trait and starting weapon so the
choice is about playstyle, not just numbers. Under the hero cards a looping
preview plays the focused hero's idle -> walk -> attack animation; below that the
difficulty line, the game-instructions block (`config.MENU_INSTRUCTIONS`, moved
here from the start menu), then the nav hint.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.content import get_content
from game.state import State
from systems.animation import Animator

# The preview cycles these; idle / walk are held for a beat, attack plays once.
_PREVIEW_PHASES = ("idle", "walk", "attack")
_PREVIEW_HOLD = 1.4          # seconds a looping phase (idle / walk) is shown
_PREVIEW_PX = 130           # base preview box height
_PREVIEW_W = _PREVIEW_PX + 30   # base preview box width (sprites read wider than tall)
# Per-hero (dw, dh) tweak on the base box so each hero sits right.
_PREVIEW_ADJUST = {"nihil": (24, 0), "kestrel": (0, -18)}


class CharacterSelectState(State):
    def enter(self, **kwargs) -> None:
        self._dev = bool(kwargs.get("dev", False))   # forwarded to the run
        self.content = get_content()
        self.ids = list(self.content.characters.keys())
        self.index = 0
        # Per-run difficulty (never persisted). Up / Down cycles it.
        self.diff_index = config.DIFFICULTY_ORDER.index(config.DIFFICULTY_DEFAULT)
        self._title = fonts.heading(44)
        self._name = fonts.heading(30)
        self._body = fonts.body(20)
        self._instr = fonts.body(17)   # ~85% of the body font
        self._hint = fonts.body(16)

        # Hero animation preview -- one Animator, rebuilt when the pick changes.
        self._preview: Animator | None = None
        self._preview_index = -1
        self._phase_i = 0
        self._phase_t = 0.0
        self._sync_preview()

    def _sync_preview(self) -> None:
        """(Re)build the preview Animator for the focused hero, if it has a rig."""
        self._preview_index = self.index
        self._phase_i = 0
        self._phase_t = 0.0
        rig = self.content.characters[self.ids[self.index]].get("sprite")
        self._preview = Animator(self.game.assets, rig) if rig else None
        if self._preview is not None:
            self._preview.play(_PREVIEW_PHASES[0], restart=True)

    @property
    def difficulty(self) -> str:
        return config.DIFFICULTY_ORDER[self.diff_index]

    def update(self, dt: float) -> None:
        if self.index != self._preview_index:
            self._sync_preview()
        if self._preview is None:
            return
        self._preview.update(dt)
        self._phase_t += dt
        phase = _PREVIEW_PHASES[self._phase_i]
        done = self._preview.finished if phase == "attack" else self._phase_t >= _PREVIEW_HOLD
        if done:
            self._phase_i = (self._phase_i + 1) % len(_PREVIEW_PHASES)
            self._phase_t = 0.0
            self._preview.play(_PREVIEW_PHASES[self._phase_i], restart=True)

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

        self._draw_preview(surface, cx, y + card_h + 12)

        diff_label = config.DIFFICULTY_LABELS[self.difficulty]
        diff_y = y + card_h + 178
        diff = self._name.render(f"Difficulty:  {diff_label}", True, config.COLOR_ACCENT)
        surface.blit(diff, diff.get_rect(center=(cx, diff_y)))

        instr_bottom = self._draw_instructions(surface, cx, diff_y + 34)

        hint = self._hint.render(
            "Left / Right hero    -    Up / Down difficulty    -    ENTER begin    -    ESC back",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, instr_bottom + 18)))

    def _draw_preview(self, surface: pygame.Surface, cx: int, top: int) -> None:
        """The focused hero's looping animation preview, centred. Falls back to
        the hero's primitive colour disc if the rig / frame is unavailable."""
        cid = self.ids[self.index]
        c = self.content.characters[cid]
        cy = top + _PREVIEW_PX // 2
        dw, dh = _PREVIEW_ADJUST.get(cid, (0, 0))
        frame = None
        if self._preview is not None:
            frame = self._preview.frame(size=(_PREVIEW_W + dw, _PREVIEW_PX + dh))
        if frame is not None:
            surface.blit(frame, frame.get_rect(center=(cx, cy)))
        else:
            pygame.draw.circle(surface, tuple(c.get("color", config.COLOR_PLAYER)),
                               (cx, cy), _PREVIEW_PX // 3)

    def _draw_instructions(self, surface: pygame.Surface, cx: int, top: int) -> int:
        """The game-instructions block from `config.MENU_INSTRUCTIONS`, centred:
        the key bindings on one line, then the free notes. Returns the y of the
        last line so the caller can place the hint below it."""
        instr = config.MENU_INSTRUCTIONS
        line_h = self._instr.get_linesize()
        keys = "      ".join(f"{label}  {combo}" for label, combo in instr["rows"])
        y = top
        surf = self._instr.render(keys, True, config.COLOR_TEXT_DIM)
        surface.blit(surf, surf.get_rect(center=(cx, y)))
        for note in instr["notes"]:
            y += line_h
            surf = self._instr.render(note, True, config.COLOR_TEXT_DIM)
            surface.blit(surf, surf.get_rect(center=(cx, y)))
        return y

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
