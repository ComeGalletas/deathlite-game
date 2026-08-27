"""OPTIONS: audio settings and the entry point into the Sanctuary.

Start-screen milestone M2. Reached from the menu's "Options" entry. Up / Down
(also W / S) move the cursor; Left / Right adjust the master volume; ENTER
toggles mute or opens the selected screen; ESC (or the "Back" row) returns to
the menu. Every change is persisted immediately, the same as the `M` mute key.
"""
from __future__ import annotations

import pygame

from game import config
from game.state import State

_LABELS = {"volume": "Master volume", "mute": "Mute",
           "sanctuary": "Sanctuary", "back": "Back"}


class OptionsState(State):
    def enter(self, **kwargs) -> None:
        self.audio = self.game.audio
        self._rows = ("volume", "mute", "sanctuary", "back")
        self.sel = 0
        self._title = pygame.font.SysFont("georgia", 40, bold=True)
        self._row = pygame.font.SysFont("georgia", 26)
        self._hint = pygame.font.SysFont("georgia", 16)

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k == pygame.K_ESCAPE:
            self._back()
        elif k in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % len(self._rows)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % len(self._rows)
        elif k in (pygame.K_LEFT, pygame.K_a):
            self._nudge_volume(-1)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self._nudge_volume(+1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()

    def _row_id(self) -> str:
        return self._rows[self.sel]

    def _nudge_volume(self, direction: int) -> None:
        if self._row_id() != "volume":
            return
        step = config.VOLUME_STEP
        stepped = round(self.audio.volume / step + direction) * step
        self.audio.set_volume(stepped)
        self.game.persist()
        self.audio.play("xp")            # a blip at the new level as feedback

    def _activate(self) -> None:
        rid = self._row_id()
        if rid == "mute":
            self.audio.toggle_mute()
            self.game.persist()
        elif rid == "sanctuary":
            from game.states.meta_state import MetaState
            self.game.state_machine.change(MetaState(self.game))
        elif rid == "back":
            self._back()

    def _back(self) -> None:
        from game.states.menu_state import MenuState
        self.game.state_machine.change(MenuState(self.game))

    # --- render ----------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        cx = surface.get_width() // 2

        title = self._title.render("Options", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 96)))

        x0 = cx - 250          # label column
        vx = x0 + 250          # value / bar column
        y0, step = 240, 74
        for i, rid in enumerate(self._rows):
            y = y0 + i * step
            selected = i == self.sel
            colour = config.COLOR_ACCENT if selected else config.COLOR_TEXT

            if selected:
                mark = self._row.render(">", True, config.COLOR_ACCENT)
                surface.blit(mark, mark.get_rect(midright=(x0 - 14, y)))
            lab = self._row.render(_LABELS[rid], True, colour)
            surface.blit(lab, lab.get_rect(midleft=(x0, y)))

            if rid == "volume":
                bar = pygame.Rect(vx, y - 11, 220, 22)
                pygame.draw.rect(surface, config.COLOR_WORLD_BORDER, bar,
                                 width=2, border_radius=4)
                fill = bar.inflate(-6, -6)
                fill.width = int(fill.width * self.audio.volume)
                if fill.width > 0:
                    pygame.draw.rect(surface, colour, fill, border_radius=3)
                pct = self._row.render(f"{round(self.audio.volume * 100)}%",
                                       True, colour)
                surface.blit(pct, pct.get_rect(midleft=(vx + 236, y)))
            elif rid == "mute":
                val = self._row.render("On" if self.audio.muted else "Off",
                                       True, colour)
                surface.blit(val, val.get_rect(midleft=(vx, y)))

        hint = self._hint.render(
            "Up / Down select    -    Left / Right adjust volume    -    "
            "ENTER toggle / open    -    ESC back", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, surface.get_height() - 40)))
