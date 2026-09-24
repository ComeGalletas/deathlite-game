"""The run résumé: three columns drawn from a run-end `stats` dict.

Drawn by the game-over screen (and available to the victory screen) so the
readout is one piece of code with one layout. The panel is tolerant of the
dict it is given: a screen fed the older summary shape -- `weapons` as
`[(name, level)]`, `blessings` as `{id: level}`, no rows at all -- still
draws, with dashes where the ledger's numbers would be.

Columns, left to right, each under a Tiny Swords ribbon (blue / yellow / red,
dark text on the light art per the owner's rule for text on the sheets):

* **Run** -- survived (or cleared in, on a win), level, kills, the gold
  *earned*, potions, chests opened, elements, then the items acquired. Rows
  that set a new record for the difficulty carry a `best` marker beside the
  label.
* **Enemies slain** -- kills per enemy type (biggest first, the boss as its
  own row, a total that is the sum of the rows).
* **Weapons** -- weapon, level (its own cell), damage, share, DPS over the
  time the weapon was held; the blessing-proc rows under them; a total row with the run's
  damage and run DPS; then the blessings with their levels (owner, 2026-09-12:
  they belong with the build, not with the kills).
* **Hero** -- opt-in, the victory screen only: trait, the resolved stat
  block, what was equipped, and the first-clear unlock line.

The ribbon titles sit `TITLE_DY` above the ribbon's geometric centre: the
pack's ribbon art has its fork and shadow at the bottom, so a label on the
rect's centre reads low (owner, 2026-09-12).

Numbers are formatted here, once: damage as a thousands-grouped integer,
share as a percentage, DPS to one decimal, time as `mm:ss` like the HUD.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import text as uitext
from ui import widgets
from ui import scale

ROW_STEP = 28          # design px, scaled at the point of use with `S`
RIBBON_H = 48
TITLE_DY = -5


def S(n: float) -> int:
    """`n` design pixels in native pixels (`ui/scale.px`)."""
    return scale.px(n)
# Rows shown before a list is cut with "+n more"; sized so each column fits
# the 590 px between the title block and the buttons at 1600x900. The kill
# column has room for every type in `data/enemies/enemies.json` plus the boss; the
# weapon column's budget is four weapon rows (three slots and a summon), the
# proc rows, the total and the blessings.
BEST_FLAG = "best"
MAX_ITEMS = 10
MAX_KILL_ROWS = 13
MAX_OTHER_ROWS = 2
# The blessings come last in their column and take whatever room is left
# below the weapons table (six rows in the worst case above, more when the
# run has fewer weapons or no proc rows), so the cut is computed, not fixed.

# The weapons table (UI-013): the Damage / Share cells' right edges, in design
# px from the column's right edge; the gap before each cell; the widest
# damage and level a row is laid out for (`_widest`: the digits are
# proportional, so they are laid out in the font's widest one); the column's
# content inset.
_DAMAGE_X = 150
_SHARE_X = 84
_CELL_GAP = 12
_WIDEST_DAMAGE = "#,###,###"
_WIDEST_LEVEL = "Lv ##"
_COLUMN_PAD = 56


def _widest(font, pattern: str) -> int:
    """The width of `pattern` with each `#` as the font's widest digit."""
    digit = max("0123456789", key=lambda d: font.size(d)[0])
    return font.size(pattern.replace("#", digit))[0]


# The columns `draw` can lay out, and the default set. `hero` is opt-in: every
# extra column narrows all of them, so whether the run summary is worth four
# columns at this width is the caller's call.
COLUMNS = ("run", "kills", "weapons")
VICTORY_COLUMNS = ("run", "kills", "weapons", "hero")

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



def column_widths(space: int, minimums) -> list[int]:
    """Split `space` between columns, honouring any that declare a minimum.

    A column below its minimum is not merely tight, it is *wrong*: the weapons
    table right-aligns its Damage / Share / DPS cells at a fixed offset from
    the column's right edge, so once the column is short the weapon's name is
    drawn straight through its own damage figure.

    Columns needing more than the equal share take what they need; the rest
    divide what is left, and the last column absorbs the rounding so the row
    ends flush -- so the other columns can differ by a pixel.
    """
    minimums = list(minimums)
    n = len(minimums)
    equal = space // n
    greedy = [m for m in minimums if m > equal]
    rest = ((space - sum(greedy)) // (n - len(greedy))) if len(greedy) < n else 0
    widths = [m if m > equal else rest for m in minimums]
    widths[-1] += space - sum(widths)
    return widths


class RunSummaryPanel:
    def __init__(self, stats: dict) -> None:
        self.stats = stats
        self._ribbon = fonts.heading(22)
        self._sub = fonts.heading(20)
        self._row = fonts.body(22)
        self._small = fonts.body(17)

    # --- the three columns ----------------------------------------
    def draw(self, surface: pygame.Surface, assets, top: int, bottom: int,
             *, margin: int = 60, gap: int = 20,
             columns: tuple[str, ...] = COLUMNS) -> None:
        """`columns` names what to draw, left to right, out of `_COLUMNS`.

        The default is the three the game-over screen has always had. The
        victory screen asks for `hero` as well; every extra column narrows all
        of them, so the set is a caller's choice rather than a fixed layout.
        """
        picked = [_COLUMNS[name] for name in columns]
        margin, gap = S(margin), S(gap)
        space = surface.get_width() - 2 * margin - (len(picked) - 1) * gap
        widths = column_widths(space, column_minimums(columns, self._row))
        x = margin
        for (drawer, _min_w), col_w in zip(picked, widths, strict=True):
            drawer(self, surface, assets,
                   pygame.Rect(x, top, col_w, bottom - top))
            x += col_w + gap

    def _column(self, surface, assets, rect, title, colour) -> pygame.Rect:
        """Backdrop and ribbon; returns the content rect beneath the ribbon."""
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill(_PANEL_FILL)
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, _RULE, rect, width=1, border_radius=S(8))
        ribbon = pygame.Rect(rect.left + S(16), rect.top - S(RIBBON_H) // 2 + S(8),
                             rect.width - S(32), S(RIBBON_H))
        widgets.draw_ribbon(surface, assets, ribbon, None, colour=colour)
        text = self._ribbon.render(title, True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=(ribbon.centerx, ribbon.centery + S(TITLE_DY))))
        return pygame.Rect(rect.left + S(28), ribbon.bottom + S(18),
                           rect.width - S(56), rect.bottom - ribbon.bottom - S(30))

    # --- primitives -----------------------------------------------
    def _kv(self, surface, area, y, label, value, *, colour=None, font=None,
            flag: str = "") -> int:
        """A label / value row. `flag` is a small accent note set after the
        label -- the "best" marker. It goes on the *label* side because the
        value is right-aligned to the column edge and has nothing to spare."""
        font = font or self._row
        val = font.render(str(value), True, colour or config.COLOR_TEXT)
        note = self._small.render(flag, True, config.COLOR_ACCENT) if flag else None
        # The value is the data and is never trimmed; the label gives way to
        # it, and to the marker, rather than drawing over either.
        room = area.width - val.get_width() - S(12) - (note.get_width() + S(8) if note else 0)
        lab = font.render(uitext.ellipsize(font, str(label), room),
                          True, config.COLOR_TEXT_DIM)
        surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
        if note is not None:
            surface.blit(note, note.get_rect(midleft=(area.left + lab.get_width() + S(8), y)))
        surface.blit(val, val.get_rect(midright=(area.right, y)))
        return y + S(ROW_STEP)

    def _line(self, surface, area, y, text, *, colour=None, font=None) -> int:
        """One full-width line, trimmed to the column.

        Item names are rolled from affixes and run long -- "Ascendant Warded
        Weave of Scholarship" is 452 px against a 251 px column -- so without
        the trim they draw straight over the column beside them."""
        font = font or self._row
        t = font.render(uitext.ellipsize(font, str(text), area.width),
                        True, colour or config.COLOR_TEXT)
        surface.blit(t, t.get_rect(midleft=(area.left, y)))
        return y + S(ROW_STEP)

    def _subheader(self, surface, area, y, text) -> int:
        y += S(6)
        t = self._sub.render(text, True, config.COLOR_ACCENT)
        surface.blit(t, t.get_rect(midleft=(area.left, y)))
        pygame.draw.line(surface, _RULE, (area.left, y + S(15)), (area.right, y + S(15)))
        return y + S(ROW_STEP + 4)

    def _rule(self, surface, area, y) -> int:
        pygame.draw.line(surface, _RULE, (area.left, y - S(2)), (area.right, y - S(2)))
        return y + S(6)

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
        y = area.top + S(ROW_STEP) // 2
        # `new_records` names the save's own record keys this run beat, so a
        # row is only marked when the record was actually taken.
        best = set(s.get("new_records", ()))

        def mark(key):
            return BEST_FLAG if key in best else ""

        # A win is not a death with better numbers: "Survived" is the wrong
        # word for the run the hero finished on their feet.
        y = self._kv(surface, area, y,
                     "Cleared in" if s.get("victory") else "Survived", fmt_time(t),
                     flag=mark("time"))
        y = self._kv(surface, area, y, "Level", s.get("level", 1),
                     flag=mark("level"))
        y = self._kv(surface, area, y, "Kills",
                     f"{kills}   ({kills / rate * 60:.0f}/min)", flag=mark("kills"))
        # Gold *earned* over the run, not the balance left after the Merchant
        # (owner, 2026-09-12): pick up 200 and spend 50 and this says 200.
        # `gold` is the fallback for a summary written before the run kept a
        # total -- there it is the best answer available, if an undercount.
        y = self._kv(surface, area, y, "Gold earned",
                     s.get("gold_earned", s.get("gold", 0)),
                     colour=config.COLOR_ACCENT)
        # No "Salvage banked" row: it printed the raw `currency`, while
        # `Game._on_run_ended` banks that times the meta salvage multiplier, so
        # a player with those upgrades was told they earned less than they did.
        # The owner's call was to drop the line rather than fix the arithmetic.
        # CB-8: potions picked up, with the HP they actually restored.
        y = self._kv(surface, area, y, "Potions",
                     f'{s.get("potions", 0)}   ({round(s.get("potion_healing", 0.0))} HP)')
        # UI-012: chests opened (CB-9 counts them); they paid out the gold and
        # the potions above. A summary written before the count reads 0.
        y = self._kv(surface, area, y, "Chests", s.get("chests", 0))
        # The elements this run obtained (design §7.3). Tracked for the
        # summary only -- no gameplay system reads the set. A run with
        # no infusion says so rather than showing a blank.
        elements = list(s.get("unlocked_elements", ()))
        y = self._kv(surface, area, y, "Elements",
                     ", ".join(elements) if elements else "none",
                     colour=config.COLOR_ACCENT if elements else None)
        items = list(s.get("dropped_items", ()))
        y = self._subheader(surface, area, y, f"Items acquired  ({len(items)})")
        if not items:
            self._line(surface, area, y, "none", colour=config.COLOR_TEXT_DIM)
            return
        # As many as the column still holds, capped at MAX_ITEMS; when some
        # are left over, one row goes to the "+N more" line instead. UI-012's
        # Chests row made the 10th item's "more" line cross the frame.
        step = S(ROW_STEP)
        room = max(0, (area.bottom - step // 2 - y) // step + 1)
        shown = min(MAX_ITEMS, room)
        if len(items) > shown:
            shown = max(0, shown - (1 if shown == room else 0))
        for item in items[:shown]:
            name, rarity = _item_name(item)
            y = self._line(surface, area, y, name,
                           colour=_RARITY_ON_DARK.get(rarity, config.COLOR_TEXT))
        self._more(surface, area, y, len(items) - shown, "items")

    # --- optional column: the hero the run was played with -------
    def _draw_hero(self, surface, assets, rect) -> None:
        """Name, trait, the resolved stat block and what was equipped.

        The stat rows, their labels and their formatting come from
        `ui.run_status.common`, so the build reads the same here as it does on
        the in-run status screen rather than growing a second vocabulary.
        """
        # Imported here, not at module scope: `ui.run_status`'s package init
        # pulls in its Overview pane, which imports `fmt_time` from this
        # module -- so a top-level import is a cycle. By call time both
        # modules are built and the lookup is a dict hit.
        from ui.run_status import common as rs_common

        s = self.stats
        area = self._column(surface, assets, rect, "Hero", "blue")
        y = area.top + S(ROW_STEP) // 2
        if s.get("first_clear"):
            # Victory only, and only the first time with this hero: the clear
            # is what unlocks the main-weapon choice (design section 20).
            y = self._line(surface, area, y, "Main weapon unlocked",
                           colour=config.COLOR_ACCENT, font=self._small)
        y = self._kv(surface, area, y, "Hero", s.get("character", "-"))
        trait = s.get("trait")
        if trait:
            y = self._kv(surface, area, y, "Trait", str(trait).title())

        stats = dict(s.get("hero_stats", {}))
        if stats:
            y = self._subheader(surface, area, y, "Stats")
            rows = [(stat, label) for stat, label, _k in rs_common.STAT_ROWS
                    if stat in stats]
            # Leave room for the equipment block below; the list is cut the
            # way the blessings are rather than running off the column. The
            # two reserved rows are the subheader and its first line, and they
            # are reserved *even with nothing equipped* -- an empty block still
            # prints "Equipped (0)" and "none", and zeroing the reserve there
            # let the stats fill the column and pushed both off the bottom.
            items = list(s.get("equipment", ()))
            reserve = S(ROW_STEP) * (2 + min(len(items), MAX_ITEMS))
            fit = max(1, (area.bottom - reserve - y) // S(ROW_STEP))
            shown = len(rows) if len(rows) <= fit else max(1, fit - 1)
            for stat, label in rows[:shown]:
                y = self._kv(surface, area, y, label,
                             rs_common.fmt_stat(stat, float(stats[stat])))
            y = self._more(surface, area, y, len(rows) - shown, "stats")

        items = list(s.get("equipment", ()))
        y = self._subheader(surface, area, y, f"Equipped  ({len(items)})")
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
        y = area.top + S(ROW_STEP) // 2
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
        fit = max(1, (area.bottom - y) // S(ROW_STEP) + 1)
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
        total = s.get("damage_dealt", 0.0)
        by_source = s.get("damage_by_source")
        if by_source:
            total = sum(by_source.values())
        # Five cells: name (flexible) | Lv | damage | share | dps. The level has
        # its own cell (UI-013): tacked onto the name, a forge's longer name
        # ran it into the damage figure. The Lv cell sits clear of the widest
        # damage actually drawn (a 7-figure one at least), and every name is
        # trimmed to the room left of it, so no number can be overdrawn.
        x_dps, x_share = area.right, area.right - S(_SHARE_X)
        x_dmg = area.right - S(_DAMAGE_X)
        damages = [r.get("damage") for r in (*rows, *others)] + [total]
        dmg_w = max(_widest(self._row, _WIDEST_DAMAGE),
                    *(self._row.size(fmt_damage(d))[0] for d in damages if d is not None))
        x_lv = x_dmg - dmg_w - S(_CELL_GAP)
        level_room = x_lv - area.left
        name_room = level_room - _widest(self._row, _WIDEST_LEVEL) - S(_CELL_GAP)
        y = area.top + S(ROW_STEP) // 2
        for label, x in (("Lv", x_lv), ("Damage", x_dmg), ("Share", x_share),
                         ("DPS", x_dps)):
            h = self._small.render(label, True, config.COLOR_TEXT_DIM)
            surface.blit(h, h.get_rect(midright=(x, y)))
        h = self._small.render("Weapon", True, config.COLOR_TEXT_DIM)
        surface.blit(h, h.get_rect(midleft=(area.left, y)))
        y += S(ROW_STEP - 4)
        y = self._rule(surface, area, y)

        def row(name, level, dmg, share, dps, *, colour=None, flag=""):
            nonlocal y
            colour = colour or config.COLOR_TEXT
            note = self._small.render(flag, True, config.COLOR_ACCENT) if flag else None
            room = (name_room if level is not None else level_room) \
                - (note.get_width() + S(8) if note else 0)
            n = self._row.render(uitext.ellipsize(self._row, str(name), room), True, colour)
            surface.blit(n, n.get_rect(midleft=(area.left, y)))
            if note is not None:
                surface.blit(note,
                             note.get_rect(midleft=(area.left + n.get_width() + S(8), y)))
            if level is not None:
                lv = self._row.render(f"Lv {level}", True, colour)
                surface.blit(lv, lv.get_rect(midright=(x_lv, y)))
            cells = ((x_dmg, "-" if dmg is None else fmt_damage(dmg)),
                     (x_share, "-" if share is None else f"{share:.0%}"),
                     (x_dps, "-" if dps is None else fmt_dps(dps)))
            for x, text in cells:
                c = self._row.render(text, True, colour)
                surface.blit(c, c.get_rect(midright=(x, y)))
            y += S(ROW_STEP)

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
        y = self._rule(surface, area, y + S(4))
        row("Total", None, float(total), 1.0 if total else 0.0,
            float(total) / t if t > 0 else 0.0, colour=config.COLOR_ACCENT,
            flag=BEST_FLAG if "damage_dealt" in set(s.get("new_records", ())) else "")
        self._draw_blessings(surface, area, y)


def weapons_min_width(font: pygame.font.Font) -> int:
    """The weapons column's floor, measured from the data (UI-013).

    Not a taste call: the Lv / Damage / Share / DPS cells are right-aligned
    from the column's right edge, so a short column trims the weapon's name.
    The floor fits the widest name any held weapon can carry -- every
    `weapons.json` entry and every `forges.json` override, since a forged
    weapon shows the forge's name -- beside a two-digit level and a 7-figure
    damage. It was a hand-measured 498 against `weapons.json` alone, and
    "Meteor Hammer  Lv 9" ran its level into the damage. A new weapon or
    forge now widens the column by itself.
    """
    from game.content import get_content
    c = get_content()
    names = [v["name"] for table in (c.weapons, c.forges)
             for v in table.values() if isinstance(v, dict) and "name" in v]
    return (max(font.size(n)[0] for n in names) + S(_CELL_GAP)
            + _widest(font, _WIDEST_LEVEL) + S(_CELL_GAP)
            + _widest(font, _WIDEST_DAMAGE) + S(_DAMAGE_X) + S(_COLUMN_PAD))


# (drawer, minimum width). Only the weapons table has a floor, and it is
# measured (`weapons_min_width`) rather than a number, so it is a callable
# that takes the row font; `column_minimums` resolves it.
_COLUMNS = {
    "run": (RunSummaryPanel._draw_run, 0),
    "kills": (RunSummaryPanel._draw_kills, 0),
    "weapons": (RunSummaryPanel._draw_damage, weapons_min_width),
    "hero": (RunSummaryPanel._draw_hero, 0),
}


def column_minimums(columns, font: pygame.font.Font) -> list[int]:
    """Each named column's minimum width, with the measured ones resolved."""
    return [m(font) if callable(m) else m for _d, m in (_COLUMNS[c] for c in columns)]
