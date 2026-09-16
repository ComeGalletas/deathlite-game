"""OPTIONS: audio settings, the key layout, the window, and the entry point
into the Sanctuary.

Start-screen milestone M2. Reached from the menu's "Options" entry. Up / Down
(also W / S) move the cursor; Left / Right adjust the master volume, cycle
the key layout (CB-5: WASD move / arrows aim, or the swap), switch the
display mode or step the resolution; ENTER toggles mute, cycles the layout
or the mode, steps the resolution, or opens the selected screen; ESC (or the
"Back" row) returns to the menu. Every change is persisted immediately, the
same as the `M` mute key.

The window rows (journal "Dynamic window scaling", 2026-09-15) are the only
place the display changes -- no hotkey, nothing in the pause menu:

  * Display mode  -- Windowed / Borderless (`game.display.set_mode`).
  * Resolution    -- in Windowed, the listed sizes that fit this desktop
                     (a dragged window reads "Custom WxH"); in Borderless it
                     reads the desktop size, is drawn dim, and the cursor
                     skips it. That difference is how the two modes are
                     told apart at a glance (owner, 2026-09-15). Both rows
                     read "Unavailable" when the scaled window was refused.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import scale

_LABELS = {"volume": "Master volume", "mute": "Mute", "key_layout": "Key layout",
           "display": "Display mode", "resolution": "Resolution",
           "sanctuary": "Sanctuary", "back": "Back"}


class OptionsState(State):
    def enter(self, **kwargs) -> None:
        self.audio = self.game.audio
        self._rows = ("volume", "mute", "key_layout", "display", "resolution",
                      "sanctuary", "back")
        self.sel = 0
        self._title = fonts.heading(40)
        self._row = fonts.body(26)
        self._hint = fonts.body(16)

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k == pygame.K_ESCAPE:
            self._back()
        elif k in (pygame.K_UP, pygame.K_w):
            self._move(-1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self._move(+1)
        elif k in (pygame.K_LEFT, pygame.K_a):
            self._nudge(-1)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self._nudge(+1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()

    def _row_id(self) -> str:
        return self._rows[self.sel]

    def _skipped(self, rid: str) -> bool:
        """A row the cursor passes over: the Resolution row while it is not
        selectable (borderless), and both window rows when there is no
        scaled window to change."""
        if rid == "display":
            return not self.game.display.available
        if rid == "resolution":
            return not self.game.display.resolution_selectable()
        return False

    def _move(self, direction: int) -> None:
        for _ in range(len(self._rows)):
            self.sel = (self.sel + direction) % len(self._rows)
            if not self._skipped(self._row_id()):
                return

    def _toggle_display_mode(self) -> None:
        other = "borderless" if self.game.display.mode == "windowed" else "windowed"
        if self.game.display.set_mode(other):
            self.game.persist()

    def _step_resolution(self, direction: int) -> None:
        if self.game.display.cycle_resolution(direction):
            self.game.persist()

    def _nudge(self, direction: int) -> None:
        """Left / Right: the volume slider, the layout cycle (either way
        round -- there are two layouts), the display mode (likewise two),
        or a step through the resolutions."""
        rid = self._row_id()
        if rid == "key_layout":
            self.game.cycle_key_layout()
            return
        if rid == "display":
            self._toggle_display_mode()
            return
        if rid == "resolution":
            self._step_resolution(direction)
            return
        if rid != "volume":
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
        elif rid == "key_layout":
            self.game.cycle_key_layout()
        elif rid == "display":
            self._toggle_display_mode()
        elif rid == "resolution":
            self._step_resolution(+1)
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
        surface.blit(title, title.get_rect(center=(cx, scale.px(96))))

        x0 = cx - scale.px(250)          # label column
        vx = x0 + scale.px(250)          # value / bar column
        y0, step = scale.px(240), scale.px(74)
        for i, rid in enumerate(self._rows):
            y = y0 + i * step
            selected = i == self.sel
            colour = config.COLOR_ACCENT if selected else config.COLOR_TEXT
            if self._skipped(rid):
                colour = config.COLOR_TEXT_DIM           # greyed out, not selectable

            if selected:
                mark = self._row.render(">", True, config.COLOR_ACCENT)
                surface.blit(mark, mark.get_rect(midright=(x0 - scale.px(14), y)))
            lab = self._row.render(_LABELS[rid], True, colour)
            surface.blit(lab, lab.get_rect(midleft=(x0, y)))

            if rid == "volume":
                bar = pygame.Rect(vx, y - scale.px(11), scale.px(220), scale.px(22))
                pygame.draw.rect(surface, config.COLOR_WORLD_BORDER, bar,
                                 width=max(1, scale.px(2)), border_radius=scale.px(4))
                fill = bar.inflate(-scale.px(6), -scale.px(6))
                fill.width = int(fill.width * self.audio.volume)
                if fill.width > 0:
                    pygame.draw.rect(surface, colour, fill, border_radius=3)
                pct = self._row.render(f"{round(self.audio.volume * 100)}%",
                                       True, colour)
                surface.blit(pct, pct.get_rect(midleft=(vx + scale.px(236), y)))
            elif rid == "mute":
                val = self._row.render("On" if self.audio.muted else "Off",
                                       True, colour)
                surface.blit(val, val.get_rect(midleft=(vx, y)))
            elif rid == "key_layout":
                val = self._row.render(
                    config.KEY_LAYOUT_LABELS[self.game.key_layout], True, colour)
                surface.blit(val, val.get_rect(midleft=(vx, y)))
            elif rid == "display":
                val = self._row.render(self.game.display.mode_label(), True, colour)
                surface.blit(val, val.get_rect(midleft=(vx, y)))
            elif rid == "resolution":
                val = self._row.render(self.game.display.resolution_label(), True, colour)
                surface.blit(val, val.get_rect(midleft=(vx, y)))

        hint = self._hint.render(
            "Up / Down select    -    Left / Right adjust    -    "
            "ENTER toggle / open    -    ESC back", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, surface.get_height() - scale.px(40))))
