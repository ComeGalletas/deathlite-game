"""The frame the two run-end screens share.

Game over and victory are the same screen with different words on it: a
backdrop, a title and subtitle, the three-column `RunSummaryPanel`, a row of
the pack's wide buttons driven by `ui.mouse`, and a hint line. Only the title,
the colours and the button set differ.

They were not always the same. The victory screen sat at a "Milestone 1 stub"
-- nine centred text lines, keyboard only -- while the game-over screen grew a
résumé, buttons and mouse support, even though `PlayingState._end_run` hands
*both* the identical stats dict. Keeping the frame here is what stops that
drifting apart again (owner, 2026-09-12; see
`documentation/journals/victory_screen_journal.md`).

`EndScreen` owns the selection and the mouse bookkeeping but never acts:
`handle_event` returns the id of the button to fire and the state decides what
that means, so the frame knows nothing about states it would have to import.

It also owns the **input lock**: for `config.END_SCREEN_INPUT_LOCK` seconds
after the screen appears, every input is refused, so the keypress or click
that was already in flight when the run ended cannot dismiss the summary
before it has been read (owner, 2026-09-16;
`documentation/journals/end_screen_input_lock_journal.md`). The state ticks it
from `update`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from game import config, fonts
from ui import widgets
from ui import scale
from ui.mouse import MouseNav
from ui.run_summary import COLUMNS, RunSummaryPanel

# 64-px `wide` buttons in a row above the hint line, and the band the summary
# panel is given between the title block and those buttons.
BTN_W, BTN_H, BTN_GAP, BTN_CY = 400, 64, 40, 812
PANEL_TOP, PANEL_BOTTOM = 178, 762
TITLE_CY, SUBTITLE_CY = 66, 118


@dataclass(frozen=True)
class Button:
    """One button in the row.

    `hint` is what the hint line calls its key. `key` is the pygame key that
    fires it from anywhere on the screen regardless of what is selected;
    `None` means the confirm keys (ENTER / SPACE) are its only way in, which
    is how the first button doubles as the default action.
    """
    bid: str
    label: str
    hint: str
    key: int | None = None
    variant: str = "primary"


def run_subtitle(stats: dict, *, lead: tuple[str, ...] = ()) -> str:
    """`hero - difficulty - seed` for the line under the title.

    `lead` goes in front of it -- the victory screen puts the boss that fell
    there, which with a pool to draw from is the one fact that tells two wins
    apart.
    """
    parts = [p for p in lead if p]
    parts.append(str(stats.get("character", "-")))
    diff = stats.get("difficulty")
    if diff:
        parts.append(config.DIFFICULTY_LABELS.get(diff, str(diff)))
    if stats.get("seed") is not None:
        parts.append(f"seed {stats['seed']}")
    return "   -   ".join(parts)


class EndScreen:
    def __init__(self, stats: dict, *, title: str, title_colour,
                 backdrop, buttons: tuple[Button, ...], subtitle: str = "",
                 title_px: int = 64, columns: tuple[str, ...] = COLUMNS,
                 lock: float | None = None) -> None:
        self.stats = stats
        self.title = title
        self.title_colour = title_colour
        self.backdrop = backdrop
        self.buttons = tuple(buttons)
        self.subtitle = subtitle
        self.columns = tuple(columns)
        self.sel = 0
        # Seconds of input lock left (see the module docstring). `lock=0`
        # is how the frame's own tests ask for an unlocked screen.
        self.lock_remaining = float(
            config.END_SCREEN_INPUT_LOCK if lock is None else lock)
        self.mouse = MouseNav()      # button rects registered in draw()
        self._panel = RunSummaryPanel(stats)
        self._title_font = fonts.heading(title_px)
        self._sub_font = fonts.body(22)
        self._btn_font = fonts.body(26)
        self._hint_font = fonts.body(16)

    # --- input -------------------------------------------------------
    @property
    def locked(self) -> bool:
        return self.lock_remaining > 0.0

    def tick(self, dt: float) -> None:
        """Run the input lock down. The states call this from `update`."""
        if self.lock_remaining > 0.0:
            self.lock_remaining = max(0.0, self.lock_remaining - max(0.0, dt))

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """The `bid` of the button to fire, or None. Nothing is acted on
        here -- the state that owns this decides what each id does."""
        if self.locked and event.type != pygame.MOUSEMOTION:
            # Refused, not deferred: a press dropped here never reaches
            # `MouseNav`, so the release that follows it matches nothing and
            # cannot fire the button late. Motion is the one exception --
            # it can only move the hover highlight, and letting it through
            # keeps the screen from looking frozen while the lock runs.
            return None
        act = self.mouse.event(event)
        if act is not None:
            kind, i = act
            self.sel = i                       # hovering selects, as in the menus
            return self.buttons[i].bid if kind == "click" else None
        # Only KEYDOWN leaves: the *release* of the key that ended the run must
        # not skip the summary before it was read.
        if event.type != pygame.KEYDOWN:
            return None
        k = event.key
        if k in (pygame.K_RETURN, pygame.K_SPACE):
            return self.buttons[self.sel].bid
        # Direct keys before the cursor keys, so a button bound to one of the
        # cursor letters would still fire rather than move the selection.
        for b in self.buttons:
            if b.key is not None and k == b.key:
                return b.bid
        if k in (pygame.K_LEFT, pygame.K_a):
            self.sel = (self.sel - 1) % len(self.buttons)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.sel = (self.sel + 1) % len(self.buttons)
        return None

    # --- render ------------------------------------------------------
    def draw(self, surface: pygame.Surface, assets) -> None:
        surface.fill(self.backdrop)
        cx = surface.get_width() // 2

        S = scale.px
        title = self._title_font.render(self.title, True, self.title_colour)
        surface.blit(title, title.get_rect(center=(cx, S(TITLE_CY))))
        if self.subtitle:
            sub = self._sub_font.render(self.subtitle, True, config.COLOR_TEXT_DIM)
            surface.blit(sub, sub.get_rect(center=(cx, S(SUBTITLE_CY))))

        self._panel.draw(surface, assets, S(PANEL_TOP), S(PANEL_BOTTOM),
                         columns=self.columns)
        self._draw_buttons(surface, assets, cx)

        hint = self._hint_font.render(
            "   -   ".join(f"{b.hint} {b.label.lower()}" for b in self.buttons)
            + "   -   Left / Right select",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, S(BTN_CY + BTN_H // 2 + 30))))

    def _draw_buttons(self, surface: pygame.Surface, assets, cx: int) -> None:
        hits = self.mouse.hits
        hits.clear()
        S = scale.px
        n = len(self.buttons)
        bw, bh, gap = S(BTN_W), S(BTN_H), S(BTN_GAP)
        total_w = n * bw + (n - 1) * gap
        x0 = cx - total_w // 2
        for i, b in enumerate(self.buttons):
            rect = pygame.Rect(x0 + i * (bw + gap), 0, bw, bh)
            rect.centery = S(BTN_CY)
            hits.add(rect, i)                 # the button *is* the mouse target
            state = ("pressed" if self.mouse.pressed_on == i
                     else "hover" if i == self.sel else "normal")
            widgets.draw_button(surface, assets, rect, b.label, state=state,
                                shape="wide", variant=b.variant,
                                font=self._btn_font)
