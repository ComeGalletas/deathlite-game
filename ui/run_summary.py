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

import re

import pygame

from game import config, fonts, locale
from game.content import get_content
from progression.items import Item, item_name, rarity_tag
from ui import text as uitext
from ui import widgets
from ui import scale

ROW_STEP = 28          # design px, scaled at the point of use with `S`
_ROW_PX = 22           # the row font's design size
_RIBBON_PX = 22        # a column's ribbon title
_SUB_PX = 20           # a section heading
_LABEL_GAP = 12        # the least room between a row's label (or marker) and its value
_COUNT = re.compile(r"\s*\(\d+\)$")   # a heading's "  (14)", kept whole by a trim
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
BEST_FLAG = "summary.best"     # a locale key: the marker is drawn in the current language
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
_WIDEST_LEVEL = "##"         # a two-digit level, inside `summary.level_value`
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
    return locale.grouped(v)


def fmt_dps(v: float) -> str:
    return locale.decimals(f"{v:.1f}")


# The keys `Item.from_dict` needs; a dict without them is a row from before
# items carried their parts, shown by its stored name.
_ITEM_KEYS = ("item_id", "slot", "name", "rarity", "level",
              "base_stat", "base_op", "base_value")


def _localized_item_name(d: dict) -> str:
    """An item dict's name in the current language (UI-014.6), built from
    its parts. Only the "is this a whole item" check falls back: an error
    inside `item_name` (bad data, a code bug) is raised, as it is on the
    TAB screen and in the Sanctuary, never hidden behind English."""
    if not all(k in d for k in _ITEM_KEYS):
        return str(d.get("name", "?"))
    return item_name(Item.from_dict(d), get_content())


def _item_name(item) -> tuple[str, str]:
    """(display, rarity) for an item dict, or a bare string from an older
    summary."""
    if isinstance(item, dict):
        rarity = str(item.get("rarity", ""))
        tag = f"{rarity_tag(rarity)} " if rarity else ""
        return tag + _localized_item_name(item), rarity
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
        self._ribbon = fonts.heading(_RIBBON_PX)
        self._sub = fonts.heading(_SUB_PX)
        self._row = fonts.body(_ROW_PX)
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
        # A title wider than its ribbon (the web profile's four columns,
        # "Enemigos abatidos") steps down rather than running off the art.
        font = (self._ribbon if self._ribbon.size(title)[0] <= ribbon.width
                else uitext.fit_font(fonts.heading, _RIBBON_PX, title, ribbon.width))
        text = font.render(title, True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=(ribbon.centerx, ribbon.centery + S(TITLE_DY))))
        return pygame.Rect(rect.left + S(28), ribbon.bottom + S(18),
                           rect.width - S(56), rect.bottom - ribbon.bottom - S(30))

    # --- primitives -----------------------------------------------
    def _kv(self, surface, area, y, label, value, *, colour=None, flag: str = "") -> int:
        """A label / value row. `flag` is a small accent note set after the
        label -- the "best" marker. It goes on the *label* side because the
        value is right-aligned to the column edge and has nothing to spare."""
        font, text = self._row, str(value)
        note = self._small.render(locale.t(flag), True, config.COLOR_ACCENT) if flag else None
        extra = S(_LABEL_GAP) + (note.get_width() + S(8) if note else 0)
        # The value is the data. When it and the label cannot both fit (a
        # translated list, "fuego, viento"), the value steps its font down
        # (UI-014.9) -- when that leaves the label whole. Otherwise the label
        # gives way, as it always did, and the value keeps its size unless it
        # would cross the column's edge or the record marker: then, in order,
        # it steps to fit beside the marker, drops the marker and steps to
        # the column, and at the last trims. Nothing leaves the column and
        # nothing is drawn over anything (the web profile's four Victory
        # columns are about 120 px).
        val_font = font
        value_room = area.width - font.size(str(label))[0] - extra
        if font.size(text)[0] > value_room:
            stepped = uitext.fit_font(fonts.body, _ROW_PX, text, value_room)
            if stepped.size(text)[0] <= value_room:
                val_font = stepped
            else:
                room_v = area.width - (extra if note else 0)
                if font.size(text)[0] > room_v:
                    val_font = uitext.fit_font(fonts.body, _ROW_PX, text, room_v)
                    if val_font.size(text)[0] > room_v and note is not None:
                        note, extra = None, S(_LABEL_GAP)
                        val_font = uitext.fit_font(fonts.body, _ROW_PX, text, area.width)
                    text = uitext.ellipsize(val_font, text, area.width)
        val = val_font.render(text, True, colour or config.COLOR_TEXT)
        room = area.width - val.get_width() - extra
        shown = uitext.ellipsize(font, str(label), room)
        if font.size(shown)[0] > room:
            shown = ""                     # not even "..." fits: it would push the marker on
        lab = font.render(shown, True, config.COLOR_TEXT_DIM)
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
        """A section heading, stepped down and then trimmed to the column:
        at the web profile's four columns "Objetos obtenidos  (14)" would
        run into the next one. A trim takes words, never the "(n)" count."""
        y += S(6)
        font = (self._sub if self._sub.size(text)[0] <= area.width
                else uitext.fit_font(fonts.heading, _SUB_PX, text, area.width))
        shown = text
        if font.size(text)[0] > area.width:
            count = _COUNT.search(text)
            head, tail = (text[:count.start()], text[count.start():]) if count else (text, "")
            shown = uitext.ellipsize(font, head, area.width - font.size(tail)[0]) + tail
        t = font.render(shown, True, config.COLOR_ACCENT)
        surface.blit(t, t.get_rect(midleft=(area.left, y)))
        pygame.draw.line(surface, _RULE, (area.left, y + S(15)), (area.right, y + S(15)))
        return y + S(ROW_STEP + 4)

    def _rule(self, surface, area, y) -> int:
        pygame.draw.line(surface, _RULE, (area.left, y - S(2)), (area.right, y - S(2)))
        return y + S(6)

    def _more(self, surface, area, y, n, what) -> int:
        """The "+n more" line; `what` picks its `summary.more.<what>` text."""
        if n <= 0:
            return y
        return self._line(surface, area, y, locale.t(f"summary.more.{what}", n=n),
                          colour=config.COLOR_TEXT_DIM, font=self._small)

    # --- column 1: the run --------------------------------------
    def _draw_run(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, locale.t("summary.run"), "blue")
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
                     locale.t("summary.cleared" if s.get("victory") else "summary.survived"),
                     fmt_time(t), flag=mark("time"))
        y = self._kv(surface, area, y, locale.t("summary.level"), s.get("level", 1),
                     flag=mark("level"))
        y = self._kv(surface, area, y, locale.t("summary.kills"),
                     locale.t("summary.kills_value", kills=kills,
                              rate=f"{kills / rate * 60:.0f}"), flag=mark("kills"))
        # Gold *earned* over the run, not the balance left after the Merchant
        # (owner, 2026-09-12): pick up 200 and spend 50 and this says 200.
        # `gold` is the fallback for a summary written before the run kept a
        # total -- there it is the best answer available, if an undercount.
        y = self._kv(surface, area, y, locale.t("summary.gold_earned"),
                     s.get("gold_earned", s.get("gold", 0)),
                     colour=config.COLOR_ACCENT)
        # No "Salvage banked" row: it printed the raw `currency`, while
        # `Game._on_run_ended` banks that times the meta salvage multiplier, so
        # a player with those upgrades was told they earned less than they did.
        # The owner's call was to drop the line rather than fix the arithmetic.
        # CB-8: potions picked up, with the HP they actually restored.
        y = self._kv(surface, area, y, locale.t("summary.potions"),
                     locale.t("summary.potions_value", n=s.get("potions", 0),
                              hp=round(s.get("potion_healing", 0.0))))
        # UI-012: chests opened (CB-9 counts them); they paid out the gold and
        # the potions above. A summary written before the count reads 0.
        y = self._kv(surface, area, y, locale.t("summary.chests"), s.get("chests", 0))
        # The elements this run obtained (design §7.3). Tracked for the
        # summary only -- no gameplay system reads the set. A run with
        # no infusion says so rather than showing a blank.
        elements = [_element_word(e) for e in s.get("unlocked_elements", ())]
        y = self._kv(surface, area, y, locale.t("summary.elements"),
                     locale.t("list.separator").join(elements) if elements
                     else locale.t("summary.none"),
                     colour=config.COLOR_ACCENT if elements else None)
        items = list(s.get("dropped_items", ()))
        y = self._subheader(surface, area, y, locale.t("summary.items", n=len(items)))
        if not items:
            self._line(surface, area, y, locale.t("summary.none"), colour=config.COLOR_TEXT_DIM)
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
        area = self._column(surface, assets, rect, locale.t("summary.hero_title"), "blue")
        y = area.top + S(ROW_STEP) // 2
        if s.get("first_clear"):
            # Victory only, and only the first time with this hero: the clear
            # is what unlocks the main-weapon choice (design section 20).
            y = self._line(surface, area, y, locale.t("summary.main_weapon"),
                           colour=config.COLOR_ACCENT, font=self._small)
        y = self._kv(surface, area, y, locale.t("summary.hero"), s.get("character", "-"))
        trait = s.get("trait_name") or str(s.get("trait") or "").title()
        if trait:
            y = self._kv(surface, area, y, locale.t("summary.trait"), trait)

        stats = dict(s.get("hero_stats", {}))
        if stats:
            y = self._subheader(surface, area, y, locale.t("summary.stats"))
            rows = [(stat, rs_common.stat_label(stat)) for stat, _k in rs_common.STAT_ROWS
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
        y = self._subheader(surface, area, y, locale.t("summary.equipped", n=len(items)))
        if not items:
            self._line(surface, area, y, locale.t("summary.none"), colour=config.COLOR_TEXT_DIM)
            return
        for item in items[:MAX_ITEMS]:
            name, rarity = _item_name(item)
            y = self._line(surface, area, y, name,
                           colour=_RARITY_ON_DARK.get(rarity, config.COLOR_TEXT))
        self._more(surface, area, y, len(items) - MAX_ITEMS, "items")

    # --- column 2: kills and blessings ---------------------------
    def _draw_kills(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, locale.t("summary.kills_title"), "yellow")
        rows = list(s.get("kill_rows", ()))
        y = area.top + S(ROW_STEP) // 2
        if not rows:
            y = self._line(surface, area, y, locale.t("summary.nothing_slain"),
                           colour=config.COLOR_TEXT_DIM)
        else:
            for name, n in rows[:MAX_KILL_ROWS]:
                y = self._kv(surface, area, y, name, n)
            y = self._more(surface, area, y, len(rows) - MAX_KILL_ROWS, "types")
            y = self._rule(surface, area, y)
            self._kv(surface, area, y, locale.t("summary.total"), sum(n for _n, n in rows),
                     colour=config.COLOR_ACCENT)

    def _draw_blessings(self, surface, area, y) -> None:
        s = self.stats
        blessings = list(s.get("blessing_rows", ()))
        if not blessings:
            # The older summary shape: ids to levels, no names.
            blessings = [(_blessing_name(k), v)
                         for k, v in dict(s.get("blessings", {})).items()]
        y = self._subheader(surface, area, y, locale.t("summary.blessings", n=len(blessings)))
        if not blessings:
            # Its own key: the Spanish agrees with "bendiciones" ("ninguna").
            self._line(surface, area, y, locale.t("summary.blessings_none"),
                       colour=config.COLOR_TEXT_DIM)
            return
        # Rows whose centre stays inside the column; the last one is given
        # to the "+n more" line when the list does not fit.
        fit = max(1, (area.bottom - y) // S(ROW_STEP) + 1)
        shown = len(blessings) if len(blessings) <= fit else max(1, fit - 1)
        for name, lvl in blessings[:shown]:
            y = self._kv(surface, area, y, name, locale.t("summary.level_value", n=lvl))
        self._more(surface, area, y, len(blessings) - shown, "blessings")

    # --- column 3: weapons -----------------------------------------
    def _draw_damage(self, surface, assets, rect) -> None:
        s = self.stats
        area = self._column(surface, assets, rect, locale.t("summary.weapons"), "red")
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
        shares = [r.get("share") for r in (*rows, *others)] + [1.0]
        x_dmg = area.right - _damage_offset(self._row, [s for s in shares if s is not None])
        damages = [r.get("damage") for r in (*rows, *others)] + [total]
        dmg_w = max(_widest(self._row, _WIDEST_DAMAGE),
                    *(self._row.size(fmt_damage(d))[0] for d in damages if d is not None))
        x_lv = x_dmg - dmg_w - S(_CELL_GAP)
        level_room = x_lv - area.left
        name_room = level_room - _widest(self._row, _widest_level()) - S(_CELL_GAP)
        y = area.top + S(ROW_STEP) // 2
        for key, x in (("level", x_lv), ("damage", x_dmg), ("share", x_share),
                       ("dps", x_dps)):
            h = self._small.render(locale.t(f"summary.head.{key}"), True, config.COLOR_TEXT_DIM)
            surface.blit(h, h.get_rect(midright=(x, y)))
        h = self._small.render(locale.t("summary.head.weapon"), True, config.COLOR_TEXT_DIM)
        surface.blit(h, h.get_rect(midleft=(area.left, y)))
        y += S(ROW_STEP - 4)
        y = self._rule(surface, area, y)

        def row(name, level, dmg, share, dps, *, colour=None, flag=""):
            nonlocal y
            colour = colour or config.COLOR_TEXT
            note = self._small.render(locale.t(flag), True, config.COLOR_ACCENT) if flag else None
            room = (name_room if level is not None else level_room) \
                - (note.get_width() + S(8) if note else 0)
            n = self._row.render(uitext.ellipsize(self._row, str(name), room), True, colour)
            surface.blit(n, n.get_rect(midleft=(area.left, y)))
            if note is not None:
                surface.blit(note,
                             note.get_rect(midleft=(area.left + n.get_width() + S(8), y)))
            if level is not None:
                lv = self._row.render(locale.t("summary.level_value", n=level), True, colour)
                surface.blit(lv, lv.get_rect(midright=(x_lv, y)))
            cells = ((x_dmg, "-" if dmg is None else fmt_damage(dmg)),
                     (x_share, "-" if share is None else _share_text(share)),
                     (x_dps, "-" if dps is None else fmt_dps(dps)))
            for x, text in cells:
                c = self._row.render(text, True, colour)
                surface.blit(c, c.get_rect(midright=(x, y)))
            y += S(ROW_STEP)

        if not rows:
            y = self._line(surface, area, y, locale.t("summary.no_weapons"),
                           colour=config.COLOR_TEXT_DIM)
        for r in rows:
            row(r["name"], r.get("level"), r.get("damage"), r.get("share"), r.get("dps"))
        if others:
            y = self._subheader(surface, area, y, locale.t("summary.procs"))
            for r in others[:MAX_OTHER_ROWS]:
                row(r["name"], None, r.get("damage"), r.get("share"), r.get("dps"),
                    colour=config.COLOR_TEXT_DIM)
            y = self._more(surface, area, y, len(others) - MAX_OTHER_ROWS, "sources")
        y = self._rule(surface, area, y + S(4))
        row(locale.t("summary.total"), None, float(total), 1.0 if total else 0.0,
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
    return (widest_weapon_name(font) + S(_CELL_GAP)
            + _widest(font, _widest_level()) + S(_CELL_GAP)
            + _widest(font, _WIDEST_DAMAGE) + _damage_offset(font, [1.0]) + S(_COLUMN_PAD))


def _share_text(share: float) -> str:
    return locale.unit("percent", f"{share * 100:.0f}")


def _damage_offset(font, shares) -> int:
    """How far left of the column's right edge the damage cell ends: the
    design `_DAMAGE_X`, plus however much wider the widest share drawn is
    in this language than in English ("100 %" against "100%"). English is
    at `_DAMAGE_X` at every render scale, as it always was, and a
    translation keeps English's gap before its share rather than eating it."""
    here = max(font.size(_share_text(s))[0] for s in shares)
    english = max(font.size(locale.english("unit.percent", n=f"{s * 100:.0f}"))[0]
                  for s in shares)
    return S(_DAMAGE_X) + max(0, here - english)


def widest_weapon_name(font) -> int:
    """The widest name a weapons row can show, in any language (UI-014.5):
    every weapon and every forge, English and each translation, so a
    language switch never clips the column."""
    c = get_content()
    keys = ("name", *(f"name_{lang}" for lang in locale.LANGUAGES if lang != locale.DEFAULT))
    # A forged weapon shows its forge's `overrides` name; measured too, so
    # the two can never drift apart unnoticed.
    entries = [v for table in (c.weapons, c.forges) for v in table.values()
               if isinstance(v, dict)]
    entries += [v["overrides"] for v in c.forges.values()
                if isinstance(v, dict) and isinstance(v.get("overrides"), dict)]
    names = [v[k] for v in entries for k in keys if isinstance(v.get(k), str)]
    return max(font.size(n)[0] for n in names)


def _widest_level() -> str:
    """The level cell's widest text, `#` for a digit, in the current
    language ("Lv ##", "Nv. ##")."""
    return locale.t("summary.level_value", n=_WIDEST_LEVEL)


def _element_word(key: str) -> str:
    """An element id as the Run column lists it: its name, lower case."""
    return locale.name("element", key, str(key).title()).lower()


def _blessing_name(bid) -> str:
    """A blessing id from an older summary, named through the catalog in
    the current language; the id, titled, when the catalog lacks it."""
    from progression.blessings.catalog import get_catalog
    bdef = get_catalog(get_content()).by_id.get(str(bid))
    return bdef.display_name if bdef is not None else str(bid).replace("_", " ").title()


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
