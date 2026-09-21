"""RANKINGS: per-difficulty best-run records (Phase 4 D5).

Reached from the menu's "Rankings" entry. One column per difficulty
(Normal / Fast / Super Fast), each showing that bucket's own best time survived,
level, kills and damage dealt. Records are never compared across buckets -- a
Fast run's time only ranks against other Fast runs. ESC, ENTER, SPACE or
BACKSPACE returns to the menu, as does a click on the hint line at the foot
(the one mouse target here; `ui.menu_nav`).
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import scale
from ui.menu_nav import MenuNav

# (stat key in save.records, row label, formatter)
_ROWS = (
    ("time", "Survived", lambda v: f"{v:.0f} s"),
    ("level", "Level", lambda v: f"{int(v)}"),
    ("kills", "Kills", lambda v: f"{int(v)}"),
    ("damage_dealt", "Damage", lambda v: f"{v:.0f}"),
)


class RankingsState(State):
    music = "menu"
    def enter(self, **kwargs) -> None:
        self.records = dict(self.game.save.records)
        self._title = fonts.heading(40)
        self._head = fonts.heading(24)
        self._row = fonts.body(20)
        self._hint = fonts.body(16)
        # One "row": the hint line, registered in draw(); activating it or
        # any back key leaves.
        self._nav = MenuNav(back_keys=(pygame.K_ESCAPE, pygame.K_BACKSPACE))
        self._mouse = self._nav.mouse

    def handle_event(self, event: pygame.event.Event) -> None:
        verb = self._nav.event(event, index=0, count=1)
        if verb is not None and verb[0] in ("activate", "back"):
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        w = surface.get_width()
        cx = w // 2

        S = scale.px
        title = self._title.render("Rankings", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, S(84))))
        sub = self._hint.render("Best run per difficulty  -  never compared across difficulties",
                                True, config.COLOR_TEXT_DIM)
        surface.blit(sub, sub.get_rect(center=(cx, S(120))))

        order = config.DIFFICULTY_ORDER
        col_w = S(300)
        x0 = cx - (len(order) * col_w) // 2
        y_head, y_rows, step = S(180), S(232), S(40)
        for c, diff in enumerate(order):
            bucket = self.records.get(diff, {})
            colx = x0 + c * col_w + col_w // 2

            head = self._head.render(config.DIFFICULTY_LABELS[diff], True,
                                     config.COLOR_TEXT)
            surface.blit(head, head.get_rect(midtop=(colx, y_head)))
            pygame.draw.line(surface, config.COLOR_WORLD_BORDER,
                             (colx - S(120), y_head + S(34)), (colx + S(120), y_head + S(34)))

            if not bucket:
                none = self._row.render("no runs yet", True, config.COLOR_TEXT_DIM)
                surface.blit(none, none.get_rect(midtop=(colx, y_rows + step)))
                continue

            for r, (key, label, fmt) in enumerate(_ROWS):
                y = y_rows + r * step
                lab = self._row.render(label, True, config.COLOR_TEXT_DIM)
                surface.blit(lab, lab.get_rect(midright=(colx - S(12), y)))
                val_s = fmt(bucket[key]) if key in bucket else "-"
                val = self._row.render(val_s, True, config.COLOR_TEXT)
                surface.blit(val, val.get_rect(midleft=(colx + S(12), y)))

        hits = self._mouse.hits
        hits.clear()
        lit = self._mouse.hover == 0
        hint = self._hint.render("ENTER / ESC  -  back to menu", True,
                                 config.COLOR_TEXT if lit else config.COLOR_TEXT_DIM)
        rect = hint.get_rect(center=(cx, surface.get_height() - S(40)))
        surface.blit(hint, rect)
        hits.add(rect.inflate(S(24), S(16)), 0)      # the hint is the Back target
