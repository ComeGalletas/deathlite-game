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
_SMALL_PX = 17         # the notes: the record marker, the "+n more" lines
_RIBBON_PX = 22        # a column's ribbon title
_RIBBON_PAD = 4        # a title's least margin inside the ribbon's raised front
_RIBBON_REACH = 8      # how far a widened ribbon may run past its column, each side
_SUB_PX = 20           # a section heading
_LABEL_GAP = 12        # the least room between a row's label (or marker) and its value
_ALONE_RATIO = 0.8     # a value steps alone beside a whole label down to this, then both step
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
        self._small = fonts.body(_SMALL_PX)

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
        # Never past the surface: the end screens place the panel for 900
        # rows, and the web profile's 720 would cut the last lines (UI-014.11).
        bottom = min(bottom, surface.get_height() - margin // 4)
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
        ribbon = _ribbon_rect(assets, rect, title, colour, self._ribbon)
        widgets.draw_ribbon(surface, assets, ribbon, None, colour=colour)
        # The title sits on the ribbon's raised front, clear of the forked
        # tails (UI-014.11); wider than that, it steps down to 60 % -- the
        # ribbon is one short line with nothing beside it -- and at the last
        # trims.
        room = _title_room(assets, ribbon, colour)
        font = (self._ribbon if self._ribbon.size(title)[0] <= room
                else uitext.fit_font(fonts.heading, _RIBBON_PX, title, room, min_ratio=0.6))
        text = font.render(uitext.ellipsize(font, title, room), True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=(ribbon.centerx, ribbon.centery + S(TITLE_DY))))
        # The side inset is 28 px, or a tenth of a narrower column: the web
        # profile's four Victory columns are ~150 px, and 56 px of padding
        # left a Spanish enemy name no room (UI-014.11).
        inset = min(S(28), rect.width // 10)
        return pygame.Rect(rect.left + inset, ribbon.bottom + S(18),
                           rect.width - 2 * inset, rect.bottom - ribbon.bottom - S(30))

    # --- primitives -----------------------------------------------
    def _kv(self, surface, area, y, label, value, *, colour=None, flag: str = "") -> int:
        """A label / value row; one line, or two (`_kv_fit`). `flag` is a
        small accent note set after the label -- the "best" marker. It goes
        on the *label* side because the value is right-aligned to the column
        edge and has nothing to spare."""
        label, text = str(label), str(value)
        lines, lab_font, val_font, _ = self._kv_fit(area, label, text, flag)
        if lines > 1:
            return self._kv_two_lines(surface, area, y, label, text, colour, flag)
        note = self._small.render(locale.t(flag), True, config.COLOR_ACCENT) if flag else None
        if not text.strip() or not label.strip():
            # One part alone (an empty value, a nameless row): it takes the
            # row, beside its marker, stepped and at the last trimmed.
            one = label if label.strip() else text
            if one is text or (note is not None and uitext.fit_font(
                    fonts.body, _ROW_PX, one, 0).size(one)[0] + note.get_width() + S(8)
                    > area.width):
                note = None                  # the label before its marker; no label, no marker
            room = area.width - (note.get_width() + S(8) if note else 0)
            f = uitext.fit_font(fonts.body, _ROW_PX, one, room)
            shown = uitext.ellipsize(f, one, room)
            if not one.strip() or f.size(shown)[0] > room:
                return y + S(ROW_STEP)
            t = f.render(shown, True, config.COLOR_TEXT_DIM if one is label
                         else colour or config.COLOR_TEXT)
            if one is label:
                surface.blit(t, t.get_rect(midleft=(area.left, y)))
                if note is not None:
                    surface.blit(note, note.get_rect(midleft=(area.left + t.get_width() + S(8), y)))
            else:
                surface.blit(t, t.get_rect(midright=(area.right, y)))
            return y + S(ROW_STEP)
        lab = lab_font.render(label, True, config.COLOR_TEXT_DIM)
        surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
        if note is not None:
            surface.blit(note, note.get_rect(midleft=(area.left + lab.get_width() + S(8), y)))
        val = val_font.render(text, True, colour or config.COLOR_TEXT)
        surface.blit(val, val.get_rect(midright=(area.right, y)))
        return y + S(ROW_STEP)

    def _kv_fit(self, area, label: str, value: str, flag: str = ""):
        """`(lines, label font, value font, marker width)` for a `_kv` row
        (measured, not drawn: `_kv_lines` asks it for a line budget).

        The value is the data and the label says what it is, so on one line
        neither is trimmed. In order: both at the row size; the value alone
        stepped down beside the whole label (UI-014.9, "fuego, viento"),
        while it keeps `_ALONE_RATIO` of the row size; both at the largest
        size they share ("Bajas récord 3877 (129/min)" at 1600, UI-014.11 --
        one size, not a 15 px label beside a 22 px value). When neither
        fits, the row takes two lines
        (`_kv_two_lines`): at the web profile's 120 px Victory columns a
        label used to shrink to "N..." or vanish."""
        font = self._row
        note = self._small.size(locale.t(flag))[0] + S(8) if flag else 0
        extra = S(_LABEL_GAP) + note
        if not value.strip() or not label.strip():
            return 1, font, font, note           # one part: `_kv` fits it to the row
        value_room = area.width - font.size(label)[0] - extra
        if font.size(value)[0] <= value_room:
            return 1, font, font, note
        stepped = uitext.fit_font(fonts.body, _ROW_PX, value, value_room)
        alone = stepped.size(value)[0] <= value_room
        if alone and _px_of(stepped, value) >= _ROW_PX * _ALONE_RATIO:
            return 1, font, stepped, note
        # A value that fits alone at any step fits beside the label at the
        # shared floor too (both floors are 70 %), so this is the last one-line
        # case.
        shared = _shared_step(label, value, area.width - extra)
        if shared is not None:
            return 1, shared, shared, note
        return 1 + len(_value_lines(value, area.width)[1]), None, None, note

    def _kv_lines(self, area, label, value, flag: str = "") -> int:
        """How many lines `_kv` takes for this row."""
        return self._kv_fit(area, str(label), str(value), flag)[0]

    def _kv_two_lines(self, surface, area, y, label, value, colour, flag) -> int:
        """A row whose label and value cannot share a line: the label and
        its marker take this line, the value the next, right-aligned as ever
        (UI-014.11) -- "Elementos" over "fuego, hielo, trueno, viento" at
        1600. Each part steps down and, wider than the whole column even
        then, trims; the marker gives way before the label does."""
        note = self._small.render(locale.t(flag), True, config.COLOR_ACCENT) if flag else None
        note_w = note.get_width() + S(8) if note else 0
        smallest = uitext.fit_font(fonts.body, _ROW_PX, label, 0)
        if note is not None and smallest.size(label)[0] + note_w > area.width:
            note, note_w = None, 0            # the label before its marker
        room = area.width - note_w
        font = uitext.fit_font(fonts.body, _ROW_PX, label, room)
        lab = font.render(uitext.ellipsize(font, label, room), True, config.COLOR_TEXT_DIM)
        surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
        if note is not None:
            surface.blit(note, note.get_rect(midleft=(area.left + lab.get_width() + S(8), y)))
        font, lines = _value_lines(value, area.width)
        for line in lines:
            y += S(ROW_STEP)
            val = font.render(line, True, colour or config.COLOR_TEXT)
            surface.blit(val, val.get_rect(midright=(area.right, y)))
        return y + S(ROW_STEP)

    def _line(self, surface, area, y, text, *, colour=None, font=None, step=True,
              wrap=False) -> int:
        """One full-width line, stepped down (UI-014.11) and then trimmed to
        the column; with `wrap`, wrapped onto more lines instead of trimmed.

        Item names are rolled from affixes and run long -- "Ascendant Warded
        Weave of Scholarship" is 452 px against a 251 px column -- so without
        the trim they draw straight over the column beside them. They pass
        `step=False`: a name is trimmed at the row size, as it always was;
        the other lines ("+12 estadísticas más") keep their words."""
        font = font or self._row
        text = str(text)
        if step and font.size(text)[0] > area.width:
            px = _SMALL_PX if font is self._small else _ROW_PX
            font = uitext.fit_font(fonts.body, px, text, area.width)
        lines = (uitext.wrap(font, text, area.width)
                 if wrap and font.size(text)[0] > area.width else [text])
        for line in lines:
            t = font.render(uitext.ellipsize(font, line, area.width),
                            True, colour or config.COLOR_TEXT)
            surface.blit(t, t.get_rect(midleft=(area.left, y)))
            y += S(ROW_STEP)
        return y

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
        """The "+n more" line; `what` picks its `summary.more.<what>` forms
        ("+1 more type", "+2 more types"). Not drawn when its line would
        fall below the column (a column with room for nothing at all)."""
        if n <= 0 or y > area.bottom:
            return y
        return self._line(surface, area, y, locale.plural(f"summary.more.{what}", n),
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
                           colour=_RARITY_ON_DARK.get(rarity, config.COLOR_TEXT), step=False)
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
                           colour=config.COLOR_ACCENT, font=self._small, wrap=True)
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
            fit = max(0, (area.bottom - reserve - y) // S(ROW_STEP))
            # A row can take two lines (`_kv_fit`), so the budget is in lines.
            values = [rs_common.fmt_stat(stat, float(stats[stat])) for stat, _l in rows]
            lines = [self._kv_lines(area, label, v) for (_s, label), v in zip(rows, values)]
            shown = _rows_that_fit(lines, fit)
            for (stat, label), v in zip(rows[:shown], values):
                y = self._kv(surface, area, y, label, v)
            y = self._more(surface, area, y, len(rows) - shown, "stats")

        items = list(s.get("equipment", ()))
        y = self._subheader(surface, area, y, locale.t("summary.equipped", n=len(items)))
        if not items:
            self._line(surface, area, y, locale.t("summary.none"), colour=config.COLOR_TEXT_DIM)
            return
        # As many as the column still holds, as the Run column's items do.
        step = S(ROW_STEP)
        room = max(0, (area.bottom - step // 2 - y) // step + 1)
        capped = items[:MAX_ITEMS]
        shown = _rows_that_fit([1] * len(capped), room, more=len(items) > len(capped))
        for item in items[:shown]:
            name, rarity = _item_name(item)
            y = self._line(surface, area, y, name,
                           colour=_RARITY_ON_DARK.get(rarity, config.COLOR_TEXT), step=False)
        self._more(surface, area, y, len(items) - shown, "items")

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
            # As many rows as the column holds above the rule and the total,
            # counted in lines: a row can take two (`_kv_fit`), and fourteen
            # Spanish names at the web profile ran the total off the bottom
            # (UI-014.11).
            step = S(ROW_STEP)
            total = sum(n for _n, n in rows)
            total_lines = self._kv_lines(area, locale.t("summary.total"), total)
            fit = (area.bottom - step // 2 - S(6) - y) // step + 1 - total_lines
            capped = rows[:MAX_KILL_ROWS]
            lines = [self._kv_lines(area, name, n) for name, n in capped]
            shown = _rows_that_fit(lines, fit, more=len(rows) > len(capped))
            for name, n in rows[:shown]:
                y = self._kv(surface, area, y, name, n)
            y = self._more(surface, area, y, len(rows) - shown, "types")
            y = self._rule(surface, area, y)
            self._kv(surface, area, y, locale.t("summary.total"), total,
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
        # Lines whose centre stays inside the column, a two-line row counted
        # as two; the last one is given to the "+n more" line when the list
        # does not fit.
        fit = max(0, (area.bottom - y) // S(ROW_STEP) + 1)
        levels = [locale.t("summary.level_value", n=lvl) for _n, lvl in blessings]
        shown = _rows_that_fit([self._kv_lines(area, name, lv)
                                for (name, _l), lv in zip(blessings, levels)], fit)
        for (name, _l), lv in zip(blessings[:shown], levels):
            y = self._kv(surface, area, y, name, lv)
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


def _shared_step(label: str, value: str, room: int):
    """The largest row font, down to `fit_font`'s floor, in which `label`
    and `value` together fit `room` (the row's width less the gap and the
    record marker); None when even the floor does not."""
    return next((f for f in _row_steps()
                 if f.size(label)[0] + f.size(value)[0] <= room), None)


def _px_of(font, text: str) -> int:
    """The row step `font` is, found by what it measures `text` at: the
    largest step whose width for `text` is `font`'s."""
    w = font.size(text)[0]
    return next((_ROW_PX - i for i, f in enumerate(_row_steps()) if f.size(text)[0] <= w),
                _ROW_PX)


def _rows_that_fit(lines: list[int], fit: int, *, more: bool = False) -> int:
    """How many rows, `lines[i]` lines tall each, to draw in `fit` lines.
    All of them when they fit; else as many as leave one line for the
    "+n more" line, which may be none (UI-014.11: a first row of two lines
    in two lines of room used to be drawn anyway, over what follows).
    `more` reserves that line even when the rows fit (a list already cut)."""
    if not more and sum(lines) <= fit:
        return len(lines)
    shown, used = 0, 0
    while shown < len(lines) and used + lines[shown] <= fit - 1:
        used += lines[shown]
        shown += 1
    return shown


def _title_room(assets, ribbon: pygame.Rect, colour: str) -> int:
    """Native px a title has on `ribbon`: its raised front, less a margin."""
    return widgets.ribbon_face(assets, ribbon, colour).width - S(2 * _RIBBON_PAD)


def _ribbon_rect(assets, rect: pygame.Rect, title: str, colour: str, full_font) -> pygame.Rect:
    """A column's ribbon: 16 px in from each side of the column; when its
    front is too narrow for `title` even at 60 % (the web profile's four
    Victory columns, "Enemigos abatidos" and "Enemies slain" alike), wider,
    as far as `_RIBBON_REACH` past each side of the column -- into the gap
    between columns, never to the next ribbon."""
    top = rect.top - S(RIBBON_H) // 2 + S(8)
    width = rect.width - S(32)
    ribbon = pygame.Rect(rect.left + S(16), top, width, S(RIBBON_H))
    if full_font.size(title)[0] <= _title_room(assets, ribbon, colour):
        return ribbon
    smallest = uitext.cached_font(fonts.heading, max(1, int(round(_RIBBON_PX * 0.6))))
    need = smallest.size(title)[0]
    widest = rect.width + 2 * S(_RIBBON_REACH)
    while width < widest:
        ribbon = pygame.Rect(0, top, width, S(RIBBON_H))
        ribbon.centerx = rect.centerx
        if _title_room(assets, ribbon, colour) >= need:
            return ribbon
        width = min(widest, width + S(4))
    ribbon = pygame.Rect(0, top, widest, S(RIBBON_H))
    ribbon.centerx = rect.centerx
    return ribbon


def _value_lines(value: str, width: int):
    """`(font, lines)` for a value on lines of its own: one line, stepped
    down to fit `width`; wider than that even at the smallest step (the
    four elements in Spanish at the web profile), wrapped there, each line
    trimmed only if one word alone is wider."""
    font = uitext.fit_font(fonts.body, _ROW_PX, value, width)
    if font.size(value)[0] <= width:
        return font, [value]
    return font, [uitext.ellipsize(font, line, width)
                  for line in uitext.wrap(font, value, width)]


def _row_steps():
    """The row font at each `fit_font` step, largest first."""
    floor = max(1, int(round(_ROW_PX * 0.7)))
    return [uitext.cached_font(fonts.body, px) for px in range(_ROW_PX, floor - 1, -1)]


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
