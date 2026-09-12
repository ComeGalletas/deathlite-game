"""The run résumé: three columns drawn from a run-end `stats` dict.

Drawn by the game-over screen (and available to the victory screen) so the
readout is one piece of code with one layout. The panel is tolerant of the
dict it is given: a screen fed the older summary shape -- `weapons` as
`[(name, level)]`, `blessings` as `{id: level}`, no rows at all -- still
draws, with dashes where the ledger's numbers would be.

Columns, left to right, each under a Tiny Swords ribbon (blue / yellow / red,
dark text on the light art per the owner's rule for text on the sheets):

* **Run** -- survived, level, kills, gold, salvage, then the items acquired.
* **Enemies slain** -- kills per enemy type (biggest first, the boss as its
  own row, a total that is the sum of the rows).
* **Weapons** -- weapon, level, damage, share, DPS over the time the weapon
  was held; the blessing-proc rows under them; a total row with the run's
  damage and run DPS; then the blessings with their levels (owner, 2026-09-12:
  they belong with the build, not with the kills).

The ribbon titles sit `TITLE_DY` above the ribbon's geometric centre: the
pack's ribbon art has its fork and shadow at the bottom, so a label on the
rect's centre reads low (owner, 2026-09-12).

Numbers are formatted here, once: damage as a thousands-grouped integer,
share as a percentage, DPS to one decimal, time as `mm:ss` like the HUD.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import widgets

ROW_STEP = 28
RIBBON_H = 48
TITLE_DY = -5
# Rows shown before a list is cut with "+n more"; sized so each column fits
# the 590 px between the title block and the buttons at 1600x900. The kill
# column has room for every type in `data/enemies.json` plus the boss; the
# weapon column's budget is four weapon rows (three slots and a summon), the
# proc rows, the total and the blessings.
MAX_ITEMS = 10
MAX_KILL_ROWS = 13
MAX_OTHER_ROWS = 2
# The blessings come last in their column and take whatever room is left
# below the weapons table (six rows in the worst case above, more when the
# run has fewer weapons or no proc rows), so the cut is computed, not fixed.

_PANEL_FILL = (0, 0, 0, 110)
_RULE = config.COLOR_WORLD_BORDER
# Item names by rarity, for the dark backdrop. `config.RARITY_COLOURS` are the
# level-up cards' inks for the light button art and vanish on this ground.
_RARITY_ON_DARK = {"common": config.COLOR_TEXT, "uncommon": (130, 225, 150),
                   "rare": (150, 170, 255), "forge": (255, 185, 90)}


def fmt_time(seconds: float) -> str:
    t = max(0, int(seconds))
    return f"{t // 60:02d}:{t % 60:02d}"


def fmt_damage(v: float) -> str:
    return f"{v:,.0f}"


def fmt_dps(v: float) -> str:
    return f"{v:.1f}"


def _item_name(item) -> tuple[str, str]:
    """(display, rarity) for an item dict, or a bare string from an older
    summary."""
    if isinstance(item, dict):
        rarity = str(item.get("rarity", ""))
        tag = f"[{rarity[:1].upper()}] " if rarity else ""
        return tag + str(item.get("name", "?")), rarity
    return str(item), ""


class RunSummaryPanel:
    def __init__(self, stats: dict) -> None:
        self.stats = stats
        self._ribbon = fonts.heading(22)
        self._sub = fonts.heading(20)
        self._row = fonts.body(22)
        self._small = fonts.body(17)

    # --- the three columns ----------------------------------------
    def draw(self, surface: pygame.Surface, assets, top: int, bottom: int,
             *, margin: int = 60, gap: int = 20) -> None:
        w = surface.get_width()
        col_w = (w - 2 * margin - 2 * gap) // 3
        cols = [pygame.Rect(margin + i * (col_w + gap), top, col_w, bottom - top)
                for i in range(3)]
        self._draw_run(surface, assets, cols[0])
        self._draw_kills(surface, assets, cols[1])
        self._draw_damage(surface, assets, cols[2])

    def _column(self, surface, assets, rect, title, colour) -> pygame.Rect:
        """Backdrop and ribbon; returns the content rect beneath the ribbon."""
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill(_PANEL_FILL)
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, _RULE, rect, width=1, border_radius=8)
        ribbon = pygame.Rect(rect.left + 16, rect.top - RIBBON_H // 2 + 8,
                             rect.width - 32, RIBBON_H)
        widgets.draw_ribbon(surface, assets, ribbon, None, colour=colour)
        text = self._ribbon.render(title, True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=(ribbon.centerx, ribbon.centery + TITLE_DY)))
        return pygame.Rect(rect.left + 28, ribbon.bottom + 18,
                           rect.width - 56, rect.bottom - ribbon.bottom - 30)

    # --- primitives -----------------------------------------------
    def _kv(self, surface, area, y, label, value, *, colour=None, font=None) -> int:
        font = font or self._row
        lab = font.render(str(label), True, config.COLOR_TEXT_DIM)
        surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
        val = font.render(str(value), True, colour or config.COLOR_TEXT)
        surface.blit(val, val.get_rect(midright=(area.right, y)))
        return y + ROW_STEP

    def _line(self, surface, area, y, text, *, colour=None, font=None) -> int:
        font = font or self._row
        t = font.render(str(text), True, colour or config.COLOR_TEXT)
        surface.blit(t, t.get_rect(midleft=(area.left, y)))
        return y + ROW_STEP

    def _subheader(self, surface, area, y, text) -> int:
        y += 6
        t = self._sub.render(text, True, config.COLOR_ACCENT)
        surface.blit(t, t.get_rect(midleft=(area.left, y)))
        pygame.draw.line(surface, _RULE, (area.left, y + 15), (area.right, y + 15))
        return y + ROW_STEP + 4

    def _rule(self, surface, area, y) -> int:
        pygame.draw.line(surface, _RULE, (area.left, y - 2), (area.right, y - 2))
        return y + 6

    def _more(self, surface, area, y, n, what) -> int:
        if n <= 0:
            return y
        return self._line(surface, area, y, f"+{n} more {what}",
                          colour=config.COLOR_TEXT_DIM, font=self._small)

    # --- column 1: the run --------------------------------------
    def _draw_run(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, "Run", "blue")
        t = float(s.get("time", 0.0))
        rate = max(1e-6, t)
        kills = s.get("kills", 0)
        y = area.top + ROW_STEP // 2
        y = self._kv(surface, area, y, "Survived", fmt_time(t))
        y = self._kv(surface, area, y, "Level", s.get("level", 1))
        y = self._kv(surface, area, y, "Kills", f"{kills}   ({kills / rate * 60:.0f}/min)")
        y = self._kv(surface, area, y, "Gold", s.get("gold", 0), colour=config.COLOR_ACCENT)
        y = self._kv(surface, area, y, "Salvage banked", s.get("currency", 0),
                     colour=config.COLOR_ACCENT)
        items = list(s.get("dropped_items", ()))
        y = self._subheader(surface, area, y, f"Items acquired  ({len(items)})")
        if not items:
            self._line(surface, area, y, "none", colour=config.COLOR_TEXT_DIM)
            return
        for item in items[:MAX_ITEMS]:
            name, rarity = _item_name(item)
            y = self._line(surface, area, y, name,
                           colour=_RARITY_ON_DARK.get(rarity, config.COLOR_TEXT))
        self._more(surface, area, y, len(items) - MAX_ITEMS, "items")

    # --- column 2: kills and blessings ---------------------------
    def _draw_kills(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, "Enemies slain", "yellow")
        rows = list(s.get("kill_rows", ()))
        y = area.top + ROW_STEP // 2
        if not rows:
            y = self._line(surface, area, y, "nothing slain", colour=config.COLOR_TEXT_DIM)
        else:
            for name, n in rows[:MAX_KILL_ROWS]:
                y = self._kv(surface, area, y, name, n)
            y = self._more(surface, area, y, len(rows) - MAX_KILL_ROWS, "types")
            y = self._rule(surface, area, y)
            self._kv(surface, area, y, "Total", sum(n for _n, n in rows),
                     colour=config.COLOR_ACCENT)

    def _draw_blessings(self, surface, area, y) -> None:
        s = self.stats
        blessings = list(s.get("blessing_rows", ()))
        if not blessings:
            # The older summary shape: ids to levels, no names.
            blessings = [(str(k).replace("_", " ").title(), v)
                         for k, v in dict(s.get("blessings", {})).items()]
        y = self._subheader(surface, area, y, f"Blessings  ({len(blessings)})")
        if not blessings:
            self._line(surface, area, y, "none", colour=config.COLOR_TEXT_DIM)
            return
        # Rows whose centre stays inside the column; the last one is given
        # to the "+n more" line when the list does not fit.
        fit = max(1, (area.bottom - y) // ROW_STEP + 1)
        shown = len(blessings) if len(blessings) <= fit else max(1, fit - 1)
        for name, lvl in blessings[:shown]:
            y = self._kv(surface, area, y, name, f"Lv {lvl}")
        self._more(surface, area, y, len(blessings) - shown, "blessings")

    # --- column 3: weapons -----------------------------------------
    def _draw_damage(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, "Weapons", "red")
        t = float(s.get("time", 0.0))
        rows = list(s.get("weapon_rows", ()))
        if not rows:
            # The older summary shape: names and levels, no ledger.
            rows = [{"name": n, "level": lvl, "damage": None, "share": None, "dps": None}
                    for n, lvl in s.get("weapons", ())]
        others = list(s.get("other_rows", ()))
        # Four columns: name (flexible) | damage | share | dps, right-aligned.
        x_dps, x_share, x_dmg = area.right, area.right - 84, area.right - 150
        y = area.top + ROW_STEP // 2
        for label, x in (("Damage", x_dmg), ("Share", x_share), ("DPS", x_dps)):
            h = self._small.render(label, True, config.COLOR_TEXT_DIM)
            surface.blit(h, h.get_rect(midright=(x, y)))
        h = self._small.render("Weapon", True, config.COLOR_TEXT_DIM)
        surface.blit(h, h.get_rect(midleft=(area.left, y)))
        y += ROW_STEP - 4
        y = self._rule(surface, area, y)

        def row(name, level, dmg, share, dps, *, colour=None):
            nonlocal y
            colour = colour or config.COLOR_TEXT
            label = f"{name}  Lv {level}" if level is not None else str(name)
            n = self._row.render(label, True, colour)
            surface.blit(n, n.get_rect(midleft=(area.left, y)))
            cells = ((x_dmg, "-" if dmg is None else fmt_damage(dmg)),
                     (x_share, "-" if share is None else f"{share:.0%}"),
                     (x_dps, "-" if dps is None else fmt_dps(dps)))
            for x, text in cells:
                c = self._row.render(text, True, colour)
                surface.blit(c, c.get_rect(midright=(x, y)))
            y += ROW_STEP

        if not rows:
            y = self._line(surface, area, y, "no weapons", colour=config.COLOR_TEXT_DIM)
        for r in rows:
            row(r["name"], r.get("level"), r.get("damage"), r.get("share"), r.get("dps"))
        if others:
            y = self._subheader(surface, area, y, "Blessing procs & other")
            for r in others[:MAX_OTHER_ROWS]:
                row(r["name"], None, r.get("damage"), r.get("share"), r.get("dps"),
                    colour=config.COLOR_TEXT_DIM)
            y = self._more(surface, area, y, len(others) - MAX_OTHER_ROWS, "sources")
        y = self._rule(surface, area, y + 4)
        total = s.get("damage_dealt", 0.0)
        by_source = s.get("damage_by_source")
        if by_source:
            total = sum(by_source.values())
        row("Total", None, float(total), 1.0 if total else 0.0,
            float(total) / t if t > 0 else 0.0, colour=config.COLOR_ACCENT)
        self._draw_blessings(surface, area, y)
