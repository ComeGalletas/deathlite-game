"""Blessings pane: the owned blessings down the left, the selected one's
detail on the right.

The list row is the name with its level in roman numerals, the weapon it
belongs to (or "Hero") and its rarity colour. The detail is the blessing's
card text at the **owned level** -- `BlessingDef.describe(level)`, the same
call the level-up card makes -- with the level as "II of V", the rarity and
the category. Only the current level is shown (owner, 2026-09-12): no next
level, no ladder.

The list scrolls: Up / Down (W / S), the mouse wheel and a click move the
selection, and the window follows it. Blessings are listed in the order they
were taken, which is the order `player.blessings` keeps.
"""
from __future__ import annotations

import pygame

from game import config
from progression.blessings.catalog import roman
from ui.run_status import common as c
from ui.text import wrap

LIST_ROW = 32


class BlessingsPane:
    def __init__(self, fonts: c.Fonts) -> None:
        self.f = fonts
        self.sel = 0
        self.scroll = 0
        self._count = 0

    def move(self, delta: int) -> None:
        if self._count:
            self.sel = max(0, min(self._count - 1, self.sel + delta))

    def select(self, index: int) -> None:
        if 0 <= index < self._count:
            self.sel = index

    def rows(self, ps) -> list[tuple[str, int, object]]:
        """`[(id, level, BlessingDef | None)]` in the order taken."""
        cat = ps.catalog.by_id
        return [(bid, lvl, cat.get(bid)) for bid, lvl in ps.player.blessings.items()]

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ps, hits) -> None:
        f = self.f
        rows = self.rows(ps)
        self._count = len(rows)
        self.sel = max(0, min(self.sel, max(0, len(rows) - 1)))
        list_w = int(area.width * 0.42)
        lst = pygame.Rect(area.left, area.top, list_w, area.height)
        detail = pygame.Rect(area.left + list_w + 40, area.top, area.width - list_w - 40, area.height)

        y = c.subheader(surface, f.sub, lst, lst.top + 2, f"Blessings  ({len(rows)})")
        if not rows:
            c.line(surface, f.row, lst, y, "none yet", colour=config.COLOR_TEXT_DIM)
            c.line(surface, f.row, detail, detail.top + c.ROW_STEP,
                   "Blessings come from level-ups and the village.", colour=config.COLOR_TEXT_DIM)
            return

        visible = max(1, (lst.bottom - y) // LIST_ROW)
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + visible:
            self.scroll = self.sel - visible + 1
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - visible)))

        names = {wid: d.get("name", wid) for wid, d in ps.content.weapons.items()}
        for i in range(self.scroll, min(len(rows), self.scroll + visible)):
            bid, lvl, bdef = rows[i]
            r = pygame.Rect(lst.left, y - LIST_ROW // 2 + 2, lst.width, LIST_ROW)
            hits.add(r, ("row", i))
            if i == self.sel:
                pygame.draw.rect(surface, (40, 36, 60), r, border_radius=6)
                pygame.draw.rect(surface, config.COLOR_ACCENT, r, width=1, border_radius=6)
            name = bdef.name if bdef else bid.replace("_", " ").title()
            colour = c.RARITY_ON_DARK.get(bdef.rarity if bdef else "common", config.COLOR_TEXT)
            t = f.row.render(f"{name} {roman(lvl)}", True, colour)
            surface.blit(t, t.get_rect(midleft=(lst.left + 10, y)))
            owner = names.get(bdef.weapon, "Hero") if bdef and bdef.weapon else "Hero"
            o = f.small.render(owner, True, config.COLOR_TEXT_DIM)
            surface.blit(o, o.get_rect(midright=(lst.right - 10, y)))
            y += LIST_ROW
        if self.scroll > 0:
            up = f.small.render("^ more", True, config.COLOR_TEXT_DIM)
            surface.blit(up, up.get_rect(midright=(lst.right - 10, lst.top + 12)))
        if self.scroll + visible < len(rows):
            c.line(surface, f.small, lst, min(y, lst.bottom - 8),
                   f"+{len(rows) - self.scroll - visible} more  (scroll)", colour=config.COLOR_TEXT_DIM)

        self._draw_detail(surface, detail, rows[self.sel], names)

    def _draw_detail(self, surface, area, row, names) -> None:
        f = self.f
        bid, lvl, bdef = row
        y = area.top + 20
        if bdef is None:
            c.line(surface, f.title, area, y, bid, step=34)
            return
        y = c.line(surface, f.title, area, y, f"{bdef.name} {roman(lvl)}",
                   colour=c.RARITY_ON_DARK.get(bdef.rarity, config.COLOR_TEXT), step=34)
        owner = names.get(bdef.weapon, bdef.weapon) if bdef.weapon else "Hero"
        y = c.line(surface, f.small, area, y,
                   f"{bdef.rarity}  ·  {bdef.category}  ·  {owner}", colour=config.COLOR_TEXT_DIM, step=24)
        y = c.rule(surface, area, y + 6)
        y += 10
        for text_line in wrap(f.row, bdef.describe(lvl), area.width):
            y = c.line(surface, f.row, area, y, text_line, step=28)
        y += 10
        c.kv(surface, f.row, area, y, "Level", f"{roman(lvl)} of {roman(bdef.max_level)}",
             colour=config.COLOR_ACCENT)
