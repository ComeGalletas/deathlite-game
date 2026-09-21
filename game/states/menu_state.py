"""MENU: title screen and entry point into a run.

A keyboard-navigated option list sits under the title. ENTER / SPACE activates
the highlighted entry; Up / Down (also W / S and the arrow keys) move the cursor
and wrap; ESC quits. The mouse drives the same cursor: hovering a row selects
it, a click (press and release on one row) activates it (`ui.mouse`). Each row
is one of the pack's wide buttons (`ui.widgets`): the selected row is the gold
one -- that is the cursor -- a held row sinks, and Exit is red.

Start-screen milestones: M1 gave the list its navigation; M2 wired "Options" to
the Options screen; M3 gave this screen its own black / white palette and an
optional full-screen title image (`config.MENU_TITLE_IMAGE`) drawn over a text
fallback. The rows sat on a parchment "scroll" panel until 2026-09-11, when the
owner asked for it gone: they now draw straight over the ocean backdrop
(`config.MENU_BACKGROUND_IMAGE`). Developer-mode milestone D1 wired the
"developer mode" entry to a non-persistent sandbox run. The game instructions that M4 put in a
left-hand column here later moved to the character-select screen (they read
better next to the hero preview); see `config.MENU_INSTRUCTIONS`.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import scale, widgets
from ui.menu_nav import MenuNav

# The option rows: 64-px `wide` buttons (the pack's native height) on a
# 68-px step -- a 4-px gap -- inset from the layout band's edges. The top is
# high enough that the last row clears the save summary at the screen foot.
_ROW_TOP, _ROW_STEP, _ROW_H, _ROW_INSET = 525, 68, 64, 60
_DANGER = {"exit"}          # drawn on the red sheet


class MenuState(State):
    music = "menu"
    def enter(self, **kwargs) -> None:
        self._menu_font_px = 24
        self._title_font = fonts.heading(64)
        self._font = fonts.body(self._menu_font_px)
        self._small = fonts.body(16)

        # (label, action). `action` is dispatched in _activate(); an entry whose
        # action is None is drawn but does nothing when selected.
        self._options: list[tuple[str, str | None]] = [
            ("Start new game", "start"),
            ("Start new developer mode game", "dev_start"),
            ("Rankings", "rankings"),
            ("Options", "options"),
            ("Exit", "exit"),
        ]
        self._index = 0
        self._nav = MenuNav()        # the cursor keys and the mouse (ui/menu_nav.py)
        self._mouse = self._nav.mouse   # rows registered in draw(); see ui/mouse.py

    # --- input ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        verb = self._nav.event(event, index=self._index, count=len(self._options))
        if verb is None:
            return
        what, i = verb
        if what == "move":
            self._index = i
        elif what == "activate":
            self._index = i
            self._activate(self._options[i][1])
        elif what == "back":
            self.game.quit()

    def _activate(self, action: str | None) -> None:
        # Imported here to avoid a circular import at module load.
        if action in ("start", "dev_start"):
            from game.states.character_select_state import CharacterSelectState
            self.game.state_machine.change(CharacterSelectState(self.game),
                                           dev=(action == "dev_start"))
        elif action == "rankings":
            from game.states.rankings_state import RankingsState
            self.game.state_machine.change(RankingsState(self.game))
        elif action == "options":
            from game.states.options_state import OptionsState
            self.game.state_machine.change(OptionsState(self.game))
        elif action == "exit":
            self.game.quit()
        # action is None -> inert (drawn but does nothing).

    # --- render ------------------------------------------------------
    backdrop = config.MENU_BG    # a 21:9 render's margins match the screen

    def _wide(self) -> bool:
        """An ultrawide render (owner, 2026-09-16): Borderless on a 21:9
        desktop, or a 21:9 size picked in Windowed."""
        display = getattr(self.game, "display", None)
        return getattr(display, "render_aspect", "16:9") == "21:9"

    def draw_backdrop(self, surface: pygame.Surface) -> None:
        super().draw_backdrop(surface)                    # the menu's black
        if not self._wide():
            return
        # The long strip across the whole surface, scaled to cover its
        # height and centred (never stretched: 3.12:1 art on a 2.33-2.39:1
        # surface loses a sliver of each end).
        base = self.game.assets.picture(config.MENU_BACKGROUND_LONG_IMAGE)
        if base is None:
            return
        w, h = surface.get_size()
        iw, ih = base.get_size()
        f = max(w / float(iw), h / float(ih))
        sw, sh = max(1, round(iw * f)), max(1, round(ih * f))
        art = self.game.assets.picture(config.MENU_BACKGROUND_LONG_IMAGE, size=(sw, sh))
        surface.blit(art, ((w - sw) // 2, (h - sh) // 2))

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        cx = w // 2
        if not self._wide():
            surface.fill(config.MENU_BG)
            bg = (self.game.assets.picture(config.MENU_BACKGROUND_IMAGE, size=(w, h))
                 or self.game.assets.picture(config.MENU_TITLE_IMAGE, size=(w, h)))
            if bg is not None:
                surface.blit(bg, (0, 0))

        # Layout band only -- nothing is drawn for it. It anchors the logo above
        # and gives the rows their x inset and width.
        panel_width, panel_height = scale.px(625), scale.px(495)   # +25% on both axes (was 500x320)
        band = pygame.Rect((w - panel_width) // 2, scale.px(890) - panel_height,
                           panel_width, panel_height)  # bottom pinned at 890, clear of the save summary

        logo_native = self.game.assets.picture(config.MENU_LOGO_IMAGE)
        if logo_native is not None:
            logo_h = scale.px(390)
            logo_w = round(logo_h * logo_native.get_width() / logo_native.get_height())
            logo = self.game.assets.picture(config.MENU_LOGO_IMAGE, size=(logo_w, logo_h))
            surface.blit(logo, logo.get_rect(center=(cx, band.top - logo_h // 2 + scale.px(50))))
        else:
            # Fallback: the title as text when the logo art is absent.
            title = self._title_font.render(config.TITLE, True, config.MENU_FG)
            surface.blit(title, title.get_rect(center=(cx, band.top - scale.px(60))))

        # --- option list: one button per row, the selected one gold ---
        hits = self._mouse.hits
        hits.clear()
        for i, (label, action) in enumerate(self._options):
            inset = scale.px(_ROW_INSET)
            rect = pygame.Rect(band.left + inset, 0, band.width - 2 * inset, scale.px(_ROW_H))
            rect.centery = scale.px(_ROW_TOP + i * _ROW_STEP)
            hits.add(rect, i)                 # the button *is* the mouse target
            state = ("pressed" if self._mouse.pressed_on == i
                     else "hover" if i == self._index else "normal")
            widgets.draw_button(surface, self.game.assets, rect, label, state=state,
                                shape="wide",
                                variant="danger" if action in _DANGER else "primary",
                                font=self._font)          # black, lifted (ui.widgets)

        # --- save summary, bottom centre ---
        save = self.game.save
        best = save.best
        summary = (f"Salvage {save.currency}    "
                   f"Best: {best.get('time', 0):.0f}s / Lv {int(best.get('level', 1))} / "
                   f"{int(best.get('kills', 0))} kills    "
                   f"Items found {len(save.discovered_items)}")
        s = self._small.render(summary, True, config.MENU_FG_DIM)
        surface.blit(s, s.get_rect(center=(cx, h - scale.px(40))))
