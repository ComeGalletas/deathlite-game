"""OPTIONS: audio settings, the key layout, the window, and the entry point
into the Sanctuary.

Three volume rows make up the mixer (journal `audio_mixer_journal.md`,
2026-09-16): **Master volume** sits over everything, and under it **Music
volume** is the streamed score (`systems/music.py`) and **Sound effects** is
every cue `systems/audio.py` plays -- the synthesised ones and the recorded
clips alike, the growl included. A cue is heard at `master * sfx * per-cue
gain` and the stream at `master * music`, so the per-cue balance the data
sets (a quiet footstep, a quieter room growl) holds wherever the sliders are.
All three step on `config.VOLUME_STEP` and all three are saved on every
change; Mute silences the lot.

Start-screen milestone M2. Reached from the menu's "Options" entry. Up / Down
(also W / S) move the cursor; Left / Right adjust the master volume, cycle
the key layout (CB-5: WASD move / arrows aim, or the swap), switch the
display mode or step the resolution; ENTER toggles mute, cycles the layout
or the mode, steps the resolution, or opens the selected screen; ESC (or the
"Back" row) returns to the menu. Every change is persisted immediately, the
same as the `M` mute key.

The mouse drives the same cursor (journal `options_mouse_journal.md`,
2026-09-16): hovering a row selects it and a click picks it (`ui.mouse`),
exactly as on the menu and pause screens -- a click does what ENTER does, so
a value row steps *forward* only. A skipped row registers no hit rect, so the
pointer passes over it as the cursor does. The wheel and the right button are
ignored here on purpose: a stray tick over the Resolution row must never
resize the window.

The two volume bars are the one place in any menu that acts on the mouse
*press* rather than the release. Everywhere else the release rule protects
the run -- `PlayingState` polls the held button for manual aim, so a pick on
the press would fire an attack the instant an overlay closed -- but a drag
never pops a state, so the button is always up again before the run resumes.
Back and Sanctuary, the two rows that do leave the screen, still activate on
the release through `MouseNav`.

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
from game.state import MUSIC_INHERIT, State
from ui import scale
from ui.mouse import BUTTON_LEFT, MouseNav

_LABELS = {"master": "Master volume", "music": "Music volume",
           "sfx": "Sound effects", "mute": "Mute", "key_layout": "Key layout",
           "display": "Display mode", "resolution": "Resolution",
           "sanctuary": "Sanctuary", "back": "Back"}

_SLIDER_ROWS = ("master", "music", "sfx")

# Design-pixel layout, all of it relative to the screen centre. The label
# column sits `_LABEL_DX` left of centre and the value column `_VALUE_DX`
# right of it; the mouse band spans from just left of the `>` marker to past
# the percentage, and is exactly `_ROW_STEP` tall so bands touch but never
# overlap.
_ROW_TOP, _ROW_STEP = 200, 74        # nine rows from here still clear the hint
_LABEL_DX, _VALUE_DX = -250, 250
_BAR_W, _BAR_H, _PCT_DX = 220, 22, 236
_BAND_DX, _BAND_W = -40, 590         # from the label column

_MOUSE_EVENTS = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                 pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)


class OptionsState(State):
    # Reached from the menu, this is a menu screen -- and you need to hear
    # the track to set the slider. Pushed from the pause menu over a live
    # run (`in_run`), it is an overlay and inherits instead; `enter` sets
    # that per instance, before `StateMachine` reads the declaration.
    music = "menu"

    def enter(self, *, in_run: bool = False, **kwargs) -> None:
        """`in_run`: pushed from the pause menu over a live run (stage 1b of
        the native-resolution journal). The Sanctuary row is hidden -- it is
        the meta shop, not part of a run -- and Back / ESC pop to the pause
        menu instead of leaving for the main menu."""
        self.audio = self.game.audio
        self.in_run = bool(in_run)
        if self.in_run:
            self.music = MUSIC_INHERIT   # keep the run's track playing
        self._rows = ("master", "music", "sfx", "mute", "key_layout", "display",
                      "resolution", "back") if self.in_run else (
            "master", "music", "sfx", "mute", "key_layout", "display",
            "resolution", "sanctuary", "back")
        self.sel = 0
        self._mouse = MouseNav()     # rows registered in draw(); see ui/mouse.py
        self._bars: dict[str, pygame.Rect] = {}   # slider row -> its bar, from draw()
        self._drag: str | None = None             # the slider row the held button owns
        self._build_fonts()

    def _build_fonts(self) -> None:
        self._title = fonts.heading(40)
        self._row = fonts.body(26)
        self._hint = fonts.body(16)

    def on_display_changed(self) -> None:
        self._build_fonts()          # the screen that made the change redraws at the new scale

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self._handle_mouse(event):
            return
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

    def _handle_mouse(self, event: pygame.event.Event) -> bool:
        """True when `event` was a mouse event, handled or deliberately
        dropped -- the wheel and the right button are dropped (owner,
        2026-09-16), so nothing can resize the window by accident.

        A press inside a slider bar takes the drag and never reaches
        `MouseNav`, so the matching release cannot also read as a click on
        that row. Every other row goes through the shared hover / click
        path, which activates on the release."""
        if event.type not in _MOUSE_EVENTS:
            return False
        if event.type == pygame.MOUSEMOTION and self._drag is not None:
            self._drag_to(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == BUTTON_LEFT:
            rid = self._bar_at(event.pos)
            if rid is not None:
                self.sel = self._rows.index(rid)
                self._drag = rid
                self._drag_to(event.pos)
                return True
        if (event.type == pygame.MOUSEBUTTONUP and event.button == BUTTON_LEFT
                and self._drag is not None):
            self._drag = None
            self.game.persist()          # once, at the end of the drag
            return True
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self.sel = i
            if kind == "click":
                self._activate()
        return True

    def _bar_at(self, pos) -> str | None:
        """The slider row whose bar covers `pos`, else None."""
        for rid, bar in self._bars.items():
            if bar.collidepoint(pos):
                return rid
        return None

    def _drag_to(self, pos) -> None:
        """Set the dragged row's level from the cursor's x. Leaving the bar
        vertically keeps the drag (that is what a slider does); leaving it
        horizontally clamps at 0 / 100 %."""
        bar = self._bars.get(self._drag)
        if bar is not None:
            self._set_level(self._drag, (pos[0] - bar.left) / max(1, bar.width))

    def _level_of(self, rid: str) -> float:
        if rid == "master":
            return self.audio.master
        return self.audio.volume if rid == "sfx" else self.game.music.volume

    def _apply_level(self, rid: str, level: float) -> None:
        """Hand one slider row's value to whoever owns it. The master goes
        through `Game`, which keeps the two players' copies in step."""
        if rid == "master":
            self.game.set_master_volume(level, persist=False)
        elif rid == "sfx":
            self.audio.set_volume(level)
        else:
            self.game.music.set_volume(level)

    def _set_level(self, rid: str, level: float) -> None:
        """Apply `level` (0..1) to a slider row, snapped to the same
        `config.VOLUME_STEP` grid Left / Right lands on. The master row blips
        once per step crossed, never per pixel dragged; the music row stays
        silent, the track being its own feedback. Persisting is the
        caller's -- a drag writes the save once, on release."""
        step = config.VOLUME_STEP
        snapped = round(max(0.0, min(1.0, level)) / step) * step
        before = self._level_of(rid)
        self._apply_level(rid, snapped)
        if rid != "music" and abs(self._level_of(rid) - before) > 1e-9:
            self.audio.play("xp")

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
        if rid not in _SLIDER_ROWS:
            return
        # Not `_set_level`: Left / Right steps from wherever the value sits
        # and blips on every press, including at the ends of the bar.
        step = config.VOLUME_STEP
        self._apply_level(rid, round(self._level_of(rid) / step + direction) * step)
        if rid != "music":
            # A blip at the new level as feedback -- but not on the music row,
            # where the track itself is the feedback, changing under the
            # cursor as Left / Right is held.
            self.audio.play("xp")
        self.game.persist()

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
        if self.in_run:
            self.game.state_machine.pop()        # back to the pause menu
            return
        from game.states.menu_state import MenuState
        self.game.state_machine.change(MenuState(self.game))

    # --- render ----------------------------------------------------
    def _draw_slider(self, surface, vx: int, y: int, level: float,
                     colour) -> pygame.Rect:
        """One volume bar plus its percentage. Shared by all three levels --
        independent values on the same step grid. Returns the bar, which is
        the rect the mouse drags inside."""
        bar = pygame.Rect(vx, y - scale.px(_BAR_H // 2),
                          scale.px(_BAR_W), scale.px(_BAR_H))
        pygame.draw.rect(surface, config.COLOR_WORLD_BORDER, bar,
                         width=max(1, scale.px(2)), border_radius=scale.px(4))
        fill = bar.inflate(-scale.px(6), -scale.px(6))
        fill.width = int(fill.width * level)
        if fill.width > 0:
            pygame.draw.rect(surface, colour, fill, border_radius=3)
        pct = self._row.render(f"{round(level * 100)}%", True, colour)
        surface.blit(pct, pct.get_rect(midleft=(vx + scale.px(_PCT_DX), y)))
        return bar

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        cx = surface.get_width() // 2

        title = self._title.render("Options", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, scale.px(96))))

        x0 = cx + scale.px(_LABEL_DX)    # label column
        vx = x0 + scale.px(_VALUE_DX)    # value / bar column
        y0, step = scale.px(_ROW_TOP), scale.px(_ROW_STEP)
        hits = self._mouse.hits
        hits.clear()
        self._bars.clear()
        for i, rid in enumerate(self._rows):
            y = y0 + i * step
            selected = i == self.sel
            colour = config.COLOR_ACCENT if selected else config.COLOR_TEXT
            if self._skipped(rid):
                colour = config.COLOR_TEXT_DIM           # greyed out, not selectable
            else:
                # One band per selectable row, exactly `step` tall so bands
                # touch and never overlap. A skipped row registers nothing,
                # so the pointer passes over it as the cursor does.
                band = pygame.Rect(x0 + scale.px(_BAND_DX), y - step // 2,
                                   scale.px(_BAND_W), step)
                hits.add(band, i)

            if selected:
                mark = self._row.render(">", True, config.COLOR_ACCENT)
                surface.blit(mark, mark.get_rect(midright=(x0 - scale.px(14), y)))
            lab = self._row.render(_LABELS[rid], True, colour)
            surface.blit(lab, lab.get_rect(midleft=(x0, y)))

            if rid in _SLIDER_ROWS:
                self._bars[rid] = self._draw_slider(
                    surface, vx, y, self._level_of(rid), colour)
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
