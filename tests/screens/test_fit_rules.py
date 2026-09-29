"""The fitting rules UI-014.11 added, pinned where the fit test cannot see
them: a label the summary leaves out draws nothing, so `test_fit.py` has
nothing to catch.

* The run summary's label / value rows (`RunSummaryPanel._kv`): a label is
  never trimmed or left out -- one line with both whole, or the label over
  its value; a value wider than the column wraps.
* Its full-width lines step down before they trim (item names excepted),
  its ribbon titles clear the ribbon's end caps, and the panel never draws
  below the surface.
* The pause screen's Controls words stay on the surface: stepped, then
  two lines, never three.
* The Forge / Monastery cards and their rail stay between the margins at
  any card count, and the layout with room is unchanged.
"""
import os
import re
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts, locale
from game.states.level_up_state import LevelUpState
from tests.screens import fit_harness as H
from ui import controls_block, scale
from ui import text as uitext
from ui import run_summary as rs
from ui.level_up import CARD_W, CARD_W_NARROW

DOTS = "..."


def setUpModule():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()


def _in(lang):
    class _Lang:
        def __enter__(self):
            self.was = locale.language()
            locale.set_language(lang)

        def __exit__(self, *exc):
            locale.set_language(self.was)
    return _Lang()


def _row(width, label, value, flag=""):
    """`(placed, y after, lines)` for one `_kv` row in a `width`-wide area."""
    out = {}
    area = pygame.Rect(10, 10, width, 600)

    def draw(surface):
        panel = rs.RunSummaryPanel({})
        out["lines"] = panel._kv_lines(area, label, value, flag)
        out["y"] = panel._kv(surface, area, 30, label, value, flag=flag)
    placed, _ = H.record(draw, (width + 20, 640))
    return placed, out["y"], out["lines"], area


def _cases():
    """(label, value, flag) rows the summary draws, both languages' words."""
    kills = locale.t("summary.kills_value", kills=3877, rate="129")
    elements = locale.t("list.separator").join(
        rs._element_word(e) for e in ("fire", "ice", "thunder", "wind"))
    return [
        (locale.t("summary.kills"), kills, rs.BEST_FLAG),
        (locale.t("summary.kills"), kills, ""),
        (locale.t("summary.elements"), elements, ""),
        (locale.t("summary.gold_earned"), "1840", ""),
        (locale.t("summary.cleared"), "29:59", rs.BEST_FLAG),
        (locale.t("summary.potions"),
         locale.t("summary.potions_value", n=12, hp=1234), ""),
        ("Invocamaldiciones", "2400", ""),
        ("Vel. movimiento", "150", ""),
    ]


class SummaryRowTests(unittest.TestCase):
    def test_a_label_is_never_trimmed_or_left_out(self):
        """Every row, both languages, a record marker or none, every column
        width from narrower than any shipped column to 1600's: the label is drawn
        whole, the value whole (or wrapped, its lines rejoining it), all of
        it inside the column, and the row as tall as `_kv_lines` says."""
        step = scale.px(rs.ROW_STEP)
        for lang in ("en", "es"):
            with _in(lang):
                cases = _cases()
                for width in range(70, 320, 16):
                    for label, value, flag in cases:
                        placed, y, lines, area = _row(width, label, value, flag)
                        texts = [p.text for p in placed]
                        with self.subTest(lang=lang, width=width, label=label, value=value):
                            smallest = uitext.fit_font(fonts.body, rs._ROW_PX, label, 0)
                            if smallest.size(label)[0] > width:
                                # One word wider than the column at its
                                # smallest: its own line, trimmed.
                                self.assertTrue(any(t.endswith(DOTS) and label.startswith(
                                    t[:-len(DOTS)]) for t in texts))
                                continue
                            self.assertIn(label, texts)
                            parts = [t for t in texts if t not in (label, locale.t(flag))]
                            if not any(t.endswith(DOTS) for t in parts):
                                self.assertEqual(" ".join(parts).split(), value.split())
                            for p in placed:
                                self.assertGreaterEqual(p.rect.left, area.left, p.text)
                                self.assertLessEqual(p.rect.right, area.right, p.text)
                            self.assertEqual(y, 30 + lines * step)

    def test_the_spanish_record_kill_row_keeps_its_label_at_1600(self):
        """The Victory Run column at 1600 (228 px): "Bajas récord 3877
        (129/min)" on one line. It used to draw the value at full size and
        leave the label out."""
        with _in("es"):
            label = locale.t("summary.kills")
            value = locale.t("summary.kills_value", kills=3877, rate="129")
            placed, _y, lines, _a = _row(228, label, value, rs.BEST_FLAG)
        self.assertEqual(lines, 1)
        self.assertEqual({p.text for p in placed}, {label, "récord", value})

    def test_a_row_that_fits_is_unchanged(self):
        """Room for both: the row size, one line -- the path every English
        row at 1600 takes (the English layout gate pins them)."""
        placed, _y, lines, _a = _row(228, "Level", "38")
        self.assertEqual(lines, 1)
        heights = {p.text: p.rect.h for p in placed}
        self.assertEqual(heights["Level"], fonts.body(rs._ROW_PX).render(
            "Level", True, (0, 0, 0)).get_bounding_rect().h)

    def test_a_wide_value_goes_under_its_label(self):
        with _in("es"):
            label = locale.t("summary.elements")
            value = locale.t("list.separator").join(
                rs._element_word(e) for e in ("fire", "ice", "thunder", "wind"))
            placed, _y, lines, _a = _row(228, label, value)
        self.assertEqual(lines, 2)
        by = {p.text: p.rect for p in placed}
        self.assertLess(by[label].bottom, by[value].top)

    def test_a_value_wider_than_the_column_wraps(self):
        with _in("es"):
            value = locale.t("list.separator").join(
                rs._element_word(e) for e in ("fire", "ice", "thunder", "wind"))
            placed, _y, lines, _a = _row(110, locale.t("summary.elements"), value)
        self.assertGreater(lines, 2)
        self.assertFalse(any(p.text.endswith(DOTS) for p in placed))


class SummaryRowSizeTests(unittest.TestCase):
    """One size per row where a size has to give: the value steps alone
    while it keeps 80 % of the row size, then label and value share one."""

    def fit(self, lang, width, label, value, flag=""):
        with _in(lang):
            panel = rs.RunSummaryPanel({})
            return panel, panel._kv_fit(pygame.Rect(0, 0, width, 400), label, value, flag)

    def test_a_small_step_leaves_the_label_at_the_row_size(self):
        panel, (lines, lab, val, _n) = self.fit("es", 226, "Elementos", "fuego, viento")
        self.assertEqual(lines, 1)
        self.assertIs(lab, panel._row)
        self.assertLess(val.get_height(), panel._row.get_height())
        self.assertGreaterEqual(rs._px_of(val, "fuego, viento"), 22 * 0.8)

    def test_past_80_percent_label_and_value_share_a_size(self):
        """"Bajas récord 3880 (129/min)" at 1600: the value alone would drop
        under 80 %; both take one size instead of a 15 px label beside a
        22 px value."""
        with _in("es"):
            label = locale.t("summary.kills")
            value = locale.t("summary.kills_value", kills=3880, rate="129")
        panel, (lines, lab, val, _n) = self.fit("es", 228, label, value, rs.BEST_FLAG)
        self.assertEqual(lines, 1)
        self.assertIs(lab, val)
        self.assertLess(lab.get_height(), panel._row.get_height())

    def test_the_80_percent_line_decides_between_the_two(self):
        """A value that fits beside the whole label only at 17 px (77 %) makes
        both share a size; at 18 px (82 %) it steps alone."""
        panel = rs.RunSummaryPanel({})
        label, value = "Nivel", "3880   (129/min)"
        gap = scale.px(rs._LABEL_GAP)
        for px, alone in ((17, False), (18, True)):
            width = panel._row.size(label)[0] + gap + fonts.body(px).size(value)[0]
            fitted, (lines, lab, val, _n) = self.fit("es", width, label, value)
            with self.subTest(px=px):
                self.assertEqual(lines, 1)
                if alone:
                    self.assertIs(lab, fitted._row)
                    self.assertEqual(rs._px_of(val, value), px)
                else:
                    self.assertIs(lab, val)

    def test_px_of_names_the_step(self):
        for px in (22, 20, 18, 15):
            f = uitext.cached_font(fonts.body, px)
            self.assertEqual(rs._px_of(f, "3880   (129/min)"), px)


class SummaryOnePartTests(unittest.TestCase):
    """A row with an empty label or value takes one line and draws what it
    has; nothing at all when both are empty."""

    def test_an_empty_value_draws_its_label_and_marker(self):
        with _in("es"):
            placed, y, lines, area = _row(60, "Bajas", "", rs.BEST_FLAG)
        self.assertEqual(lines, 1)
        self.assertEqual(y, 30 + scale.px(rs.ROW_STEP))
        self.assertIn("Bajas", [p.text for p in placed])
        for p in placed:
            self.assertLessEqual(p.rect.right, area.right, p.text)

    def test_an_empty_label_draws_its_value_alone(self):
        placed, y, lines, area = _row(120, "", "38", rs.BEST_FLAG)
        self.assertEqual((lines, [p.text for p in placed]), (1, ["38"]))
        self.assertEqual(placed[0].rect.right, area.right)
        # No label, no marker: a value that fills the row keeps its size.
        value = "3880   (129/min)"
        width = fonts.body(rs._ROW_PX).size(value)[0] + 2
        placed, _y, _l, _a = _row(width, "", value, rs.BEST_FLAG)
        self.assertEqual([p.text for p in placed], [value])
        self.assertEqual(placed[0].rect.h, fonts.body(rs._ROW_PX).render(
            value, True, (0, 0, 0)).get_bounding_rect().h)

    def test_nothing_draws_nothing(self):
        placed, y, lines, _a = _row(20, "", "")
        self.assertEqual((lines, placed, y), (1, [], 30 + scale.px(rs.ROW_STEP)))


class MoreLineRoomTests(unittest.TestCase):
    def test_no_more_line_below_a_column_with_no_room(self):
        area = pygame.Rect(0, 0, 200, 100)

        def draw(surface):
            rs.RunSummaryPanel({})._more(surface, area, area.bottom + 1, 3, "types")
        placed, _ = H.record(draw, (200, 200))
        self.assertEqual(placed, [])


class SummaryLineTests(unittest.TestCase):
    def _line(self, text, width, **kw):
        area = pygame.Rect(0, 0, width, 400)

        def draw(surface):
            panel = rs.RunSummaryPanel({})
            panel._line(surface, area, 20, text, font=panel._small, **kw)
        return [p.text for p in H.record(draw, (width, 400))[0]]

    def test_a_line_steps_down_before_it_trims(self):
        with _in("es"):
            text = locale.plural("summary.more.stats", 17)
        width = fonts.body(rs._SMALL_PX).size(text)[0] - 10
        self.assertEqual(self._line(text, width), [text])

    def test_an_item_name_trims_at_its_size(self):
        text = "[C] Cota de malla serena"
        width = fonts.body(rs._SMALL_PX).size(text)[0] - 10
        (shown,) = self._line(text, width, step=False)
        self.assertTrue(shown.endswith(DOTS))

    def test_a_wrapped_line_keeps_every_word(self):
        with _in("es"):
            text = locale.t("summary.main_weapon")
        got = self._line(text, 90, wrap=True)
        self.assertGreater(len(got), 1)
        self.assertEqual(" ".join(got), text)


class SummaryPanelTests(unittest.TestCase):
    def _stats(self):
        return {"time": 1799.0, "level": 38, "kills": 3877, "gold_earned": 1840,
                "potions": 12, "potion_healing": 1234.5, "chests": 14,
                "unlocked_elements": ["fire", "ice", "thunder", "wind"],
                "dropped_items": [f"Item {i}" for i in range(12)],
                "kill_rows": [("Skitter", 2400)], "new_records": ["kills"]}

    def test_the_panel_never_draws_below_the_surface(self):
        """The end screens place it for 900 rows; on a 720-row surface at
        scale 1 (the web profile before UI-016, which now draws at 0.8) it
        ends at the surface's edge and says "+n more" instead."""
        def draw(surface):
            rs.RunSummaryPanel(self._stats()).draw(surface, None, 178, 762,
                                                   columns=rs.VICTORY_COLUMNS)
        for lang in ("en", "es"):
            with _in(lang):
                placed, _ = H.record(draw, (1280, 720))
            with self.subTest(lang):
                self.assertTrue(placed)
                self.assertLessEqual(max(p.rect.bottom for p in placed), 720)

    def test_a_ribbon_title_sits_on_the_raised_front_of_the_art(self):
        """With the real ribbon art: the title's ink lies over the band's
        raised front, read from the art's alpha, in both languages; whole at the Victory columns' real
        widths (284 at 1600; 172 on the scale-1 web surface before UI-016),
        trimmed on the
        front below them; a widened ribbon stays within 8 px of its column."""
        game = _game()
        for lang in ("en", "es"):
            for width in (130, 150, 172, 284):
                rect = pygame.Rect(30, 60, width, 400)
                seen = {}

                def draw(surface):
                    with _in(lang):
                        seen["title"] = locale.t("summary.kills_title")
                    real = rs.widgets.draw_ribbon

                    def spy(surf, assets, r, *a, **k):
                        seen["ribbon"] = pygame.Rect(r)
                        return real(surf, assets, r, *a, **k)
                    with mock.patch.object(rs.widgets, "draw_ribbon", spy):
                        rs.RunSummaryPanel({})._column(surface, game.assets, rect,
                                                       seen["title"], "yellow")
                placed, _ = H.record(draw, (400, 500))
                ribbon = seen["ribbon"]
                (p,) = [p for p in placed if p.rect.colliderect(ribbon)]
                left, right = _raised_front(game.assets, ribbon, "yellow")
                with self.subTest(lang=lang, width=width):
                    if width >= 172:
                        self.assertEqual(p.text, seen["title"])          # whole
                    else:
                        self.assertTrue(seen["title"].startswith(p.text.rstrip(DOTS)))
                    self.assertGreaterEqual(p.rect.left, left + 4)        # its margin
                    self.assertLessEqual(p.rect.right, right - 4)
                    self.assertGreaterEqual(ribbon.left, rect.left - 8)
                    self.assertLessEqual(ribbon.right, rect.right + 8)


def _raised_front(assets, ribbon, colour):
    """Screen x range of the ribbon art's columns whose top is within 2 px
    of the highest: the band's front, where the tails are not. The same
    reading `widgets.ribbon_face` makes, written again here; what checks
    the reading itself is the screenshots of the Victory ribbons."""
    from ui import panels
    art = panels.slice(assets, f"ribbon_{colour}", ribbon.size)
    tops = [next((y for y in range(art.get_height()) if art.get_at((x, y))[3] > 128),
                 art.get_height()) for x in range(art.get_width())]
    front = [x for x, t in enumerate(tops) if t <= min(tops) + 2]
    return ribbon.left + front[0], ribbon.left + front[-1] + 1


def _game():
    import tempfile
    from game.game import Game
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


class SummaryBudgetTests(unittest.TestCase):
    """Rows of two lines count as two: the Hero and kills columns stop where
    the column does."""

    def _column(self, drawer, stats, width, lang="es", height=520):
        area = []

        def draw(surface):
            panel = rs.RunSummaryPanel(stats)
            real = panel._column

            def column(*a, **k):
                area.append(real(*a, **k))
                return area[-1]
            panel._column = column
            drawer(panel, surface, None, pygame.Rect(10, 60, width, height))
        with _in(lang):
            placed, _ = H.record(draw, (width + 20, height + 80))
        return placed, area[0]

    def _in_column(self, placed, area):
        for p in placed:
            if p.rect.top < area.top:
                continue                                  # the ribbon title
            self.assertLessEqual(p.rect.bottom, area.bottom + scale.px(rs.ROW_STEP) // 2, p.text)
            self.assertGreaterEqual(p.rect.left, area.left, p.text)
            self.assertLessEqual(p.rect.right, area.right, p.text)
        self.assertEqual(H.overlaps(placed), [])

    def test_two_line_stats_leave_the_equipment_its_room_at_any_height(self):
        """Columns narrow enough that stat rows take two lines, at every
        height from cramped to roomy: the three equipped items are drawn,
        inside the column, on nothing."""
        stats = {"character": "Aegis", "trait_name": "Baluarte",
                 "hero_stats": {"max_hp": 1600.0, "hp_regen": 0.2, "move_speed": 150.0,
                                "armor": 4.0, "melee_damage": 0.1, "ranged_damage": 0.1,
                                "crit_chance": 0.45, "cooldown": 0.6, "area": 1.8},
                 "equipment": [f"Item {i}" for i in range(3)]}
        two_lines = 0
        for width in (96, 110):
            for height in range(300, 560, 11):
                placed, area = self._column(rs.RunSummaryPanel._draw_hero, stats, width,
                                            height=height)
                texts = [p.text for p in placed]
                two_lines += sum(1 for t in texts if t in ("PV máximos", "Vel. movimiento"))
                with self.subTest(width=width, height=height):
                    self._in_column(placed, area)
                    # Every item drawn, or counted on its "+n" line.
                    drawn = sum(1 for i in range(3) if f"Item {i}" in texts)
                    more = [int(re.match(r"\+(\d+) obj", t).group(1)) for t in texts
                            if re.match(r"\+(\d+) obj", t)]           # "+2 objetos más", maybe trimmed
                    self.assertEqual(drawn + sum(more), 3)
        self.assertGreater(two_lines, 0)                  # the premise: rows went two-line

    def test_a_capped_kill_list_keeps_its_more_line_inside_at_any_height(self):
        """One kind more than the list shows, at every column height: the
        "+1" line and the total stay inside, whatever fits."""
        rows = [(f"Kind {i}", 100 - i) for i in range(rs.MAX_KILL_ROWS + 1)]
        for height in range(300, 640, 7):
            placed, area = self._column(rs.RunSummaryPanel._draw_kills,
                                        {"kill_rows": rows}, 228, height=height)
            texts = [p.text for p in placed]
            with self.subTest(height=height):
                self._in_column(placed, area)
                self.assertIn("Total", texts)
                self.assertTrue([t for t in texts if t.startswith("+")])

    def test_the_hero_stats_leave_the_equipment_its_room(self):
        stats = {"character": "Aegis", "trait_name": "Baluarte", "first_clear": True,
                 "hero_stats": {"max_hp": 1600.0, "hp_regen": 0.2, "move_speed": 150.0,
                                "armor": 4.0, "damage_mult": 1.0, "melee_damage": 0.1,
                                "ranged_damage": 0.1, "crit_chance": 0.45, "crit_mult": 2.5,
                                "cooldown": 0.6, "area": 1.8, "luck": 2.0},
                 "equipment": [f"Item {i}" for i in range(3)]}
        for width in (130, 150, 200, 280):
            placed, area = self._column(rs.RunSummaryPanel._draw_hero, stats, width, height=420)
            texts = [p.text for p in placed]
            with self.subTest(width=width):
                self._in_column(placed, area)
                for i in range(3):
                    self.assertIn(f"Item {i}", texts)            # the reserve held

    def test_a_first_row_of_two_lines_is_not_drawn_into_the_reserve(self):
        """Room for two lines above the equipment: a two-line first stat does
        not fit beside the "+n more" line, so only that line is drawn."""
        self.assertEqual(rs._rows_that_fit([2, 1, 1], 2), 0)
        self.assertEqual(rs._rows_that_fit([1, 1, 1], 2), 1)
        self.assertEqual(rs._rows_that_fit([1, 1], 2), 2)
        self.assertEqual(rs._rows_that_fit([1, 1], 3, more=True), 2)
        self.assertEqual(rs._rows_that_fit([1, 1, 1], 3, more=True), 2)

    def test_every_kind_killed_ends_above_the_column_bottom(self):
        rows = [(f"Invocamaldiciones {i}", 100 - i) for i in range(18)]
        for width in (64, 130, 150, 228):         # at 64 even the Total takes two lines
            placed, area = self._column(rs.RunSummaryPanel._draw_kills,
                                        {"kill_rows": rows}, width, height=480)
            texts = [p.text for p in placed]
            with self.subTest(width=width):
                self._in_column(placed, area)
                self.assertIn("Total", texts)
                self.assertTrue([t for t in texts if t.startswith("+")])

    def test_the_main_weapon_line_wraps_at_its_call_site(self):
        stats = {"character": "Aegis", "first_clear": True}
        placed, area = self._column(rs.RunSummaryPanel._draw_hero, stats, 110)
        with _in("es"):
            words = locale.t("summary.main_weapon").split()
        lines = [p for p in placed if p.rect.top >= area.top and
                 set(p.text.split()) <= set(words)]
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(p.text for p in sorted(lines, key=lambda p: p.rect.y)).split(),
                         words)


class MoreLineTests(unittest.TestCase):
    def test_one_more_is_singular_in_both_languages(self):
        want = {"en": ("+1 more type", "+2 more types", "+1 more synergy"),
                "es": ("+1 tipo más", "+2 tipos más", "+1 sinergia más")}
        for lang, (one, two, syn) in want.items():
            got = {}
            area = pygame.Rect(0, 0, 400, 400)

            def draw(surface):
                panel = rs.RunSummaryPanel({})
                panel._more(surface, area, 20, 1, "types")
                panel._more(surface, area, 60, 2, "types")
                from ui.run_status import common
                common.more(surface, fonts.body(17), area, 100, 1, "status.more_synergies")
            with _in(lang):
                placed, _ = H.record(draw, (400, 400))
            with self.subTest(lang):
                self.assertEqual(sorted(p.text for p in placed), sorted([one, two, syn]))


class ControlsWordTests(unittest.TestCase):
    def test_a_word_takes_one_line_or_two_at_the_larger_size(self):
        font = fonts.body(controls_block.WORD_PX)
        with _in("es"):
            word = locale.t("controls.auto_attack")
        f, lines = controls_block._word_lines(font, word, 122)
        self.assertEqual(lines, ["Ataque", "automático"])
        self.assertEqual(f.get_height(), font.get_height())
        f, lines = controls_block._word_lines(font, word, 400)
        self.assertEqual((f, lines), (font, [word]))

    def test_never_three_lines_and_each_fits(self):
        font = fonts.body(controls_block.WORD_PX)
        for room in range(40, 260, 6):
            for word in ("Apuntar (mantener)", "Ataque automático", "Interactuar",
                         "Uno dos tres cuatro cinco"):
                f, lines = controls_block._word_lines(font, word, room)
                with self.subTest(room=room, word=word):
                    self.assertLessEqual(len(lines), 2)
                    if " ".join(lines) == word and len(lines) == 2 and \
                            all(f.size(l)[0] <= room for l in lines):
                        continue
                    if len(lines) == 1 and f.size(word)[0] <= room:
                        continue
                    # Nothing fits even at the smallest size: the draw trims.
                    smallest = max(1, int(round(controls_block.WORD_PX * 0.7)))
                    self.assertEqual(f.get_height(), fonts.body(smallest).get_height())

    def test_the_block_stays_on_a_1280_surface_in_spanish(self):
        from game.game import Game
        import tempfile
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        for x in (980, 1060, 1100):          # the pause screen's, and closer to the edge
            with _in("es"):
                placed, _ = H.record(lambda s: controls_block.draw(
                    s, game.assets, (x, 300), game), (1280, 720))
            with self.subTest(x=x):
                self.assertTrue(placed)
                for p in placed:
                    self.assertLessEqual(p.rect.right, 1280 - 16, p.text)
                self.assertEqual(H.overlaps(placed), [])


class HeroCardTests(unittest.TestCase):
    """The hero cards keep their text inside the art, bevel included."""

    def test_every_unlocked_card_clears_its_bottom_bevel_in_both_languages(self):
        from game.states.character_select_state import CharacterSelectState
        from tests.screens.fit_scenes import hero_select
        for lang in ("en", "es"):
            seen = {}

            def draw(surface):
                real = CharacterSelectState.draw

                def spy(state, surf):
                    seen["cards"] = [state._mouse.hits.rect_of(("hero", i))
                                     for i in range(len(state.ids))]
                    real(state, surf)
                    seen["cards"] = [state._mouse.hits.rect_of(("hero", i))
                                     for i in range(len(state.ids))]
                with mock.patch.object(CharacterSelectState, "draw", spy):
                    hero_select(0, unlocked=True)(surface)
            with _in(lang):
                placed, _ = H.record(draw, (1600, 900))
            for card in seen["cards"]:
                inside = [p for p in placed if card.contains(p.rect)]
                with self.subTest(lang=lang, card=tuple(card)):
                    self.assertTrue(inside)
                    self.assertLessEqual(max(p.rect.bottom for p in inside), card.bottom - 22)

    def test_the_shrink_path_fits_its_rows_and_the_trait_with_them(self):
        from game.states.character_select_state import CharacterSelectState
        from tests.screens.fit_scenes import _game
        with _in("es"):
            st = CharacterSelectState(_game())
            st.enter()
            c = st.content.characters[st.ids[0]]
            trait = locale.t("hero_select.trait", name=locale.text(c, "trait_name"))
            full_body, full_trait, full_step, _r = st._card_rows(
                c, trait, "<  Espada  >", True, 302, 10_000)
            for room in (210, 190, 170):             # under the 9 rows without their gaps
                body, trait_f, step, rows = st._card_rows(c, trait, "<  Espada  >", True, 302,
                                                          room)
                with self.subTest(room=room):
                    self.assertLessEqual(len(rows) * step, room)
                    self.assertLess(step, full_step)
                    self.assertLess(trait_f.get_height(), full_trait.get_height())
                    self.assertLessEqual(trait_f.get_height(), step + 4)


class CardLayoutTests(unittest.TestCase):
    def _state(self, n, rail=True):
        from tests.screens.test_forge_rail import _levels, _Recorder, _upgrade, _Weapon
        from ui.forge_rail import rows_for
        game = SimpleNamespace(state_machine=_Recorder(), assets=None)
        s = LevelUpState(game)
        rows = rows_for([_Weapon("sword", "Sword", levels=3)], 2, _levels)
        if rail:
            s.enter(player=SimpleNamespace(), weapon_rows=rows, cancelable=True,
                    offers_for=lambda w: [_upgrade("sword", f"F{i}") for i in range(n)])
        else:
            s.enter(player=SimpleNamespace(),
                    choices=[_upgrade("sword", f"F{i}") for i in range(n)])
        return s

    def test_the_rail_and_every_card_stay_between_the_margins(self):
        for width, height in ((1280, 720), (1600, 900), (1920, 1080)):
            for n in (1, 2, 3, 4):
                s = self._state(n)
                surface = pygame.Surface((width, height))
                s.draw(surface)
                cards = [s.panel.hits.rect_of(i) for i in range(n)]
                rail = [s.rail.hits.rect_of(0)]
                with self.subTest(width=width, n=n):
                    self.assertGreaterEqual(rail[0].left, 20)
                    self.assertLessEqual(cards[-1].right, width - 20)
                    self.assertLess(rail[0].right, cards[0].left)

    def test_the_layout_with_room_is_unchanged(self):
        """Three cards at 1600: the narrow width, centred, as before; the
        level-up's three at 1280 too."""
        s = self._state(3)
        self.assertEqual(s.card_layout(1600), (CARD_W_NARROW, 0))
        self.assertEqual(self._state(3, rail=False).card_layout(1600), (CARD_W, 0))
        self.assertEqual(self._state(3, rail=False).card_layout(1280), (CARD_W, 0))

    def test_every_card_without_a_rail_stays_between_the_margins(self):
        """The buff building's picker: four weapon cards and no rail. At
        1280 four level-up cards are 1480 px; they narrow to fit."""
        for width, height in ((1280, 720), (1600, 900)):
            for n in (1, 2, 3, 4, 5):
                s = self._state(n, rail=False)
                s.draw(pygame.Surface((width, height)))
                cards = [s.panel.hits.rect_of(i) for i in range(n)]
                with self.subTest(width=width, n=n):
                    self.assertGreaterEqual(cards[0].left, 20)
                    self.assertLessEqual(cards[-1].right, width - 20)

    def test_the_hint_names_the_cards_number_keys(self):
        s = self._state(4, rail=False)
        s.cancelable = True
        self.assertIn("1/2/3/4 ", s.hint)
        self.assertIn("1/2/3 ", self._state(3).hint)

    def test_with_no_cards_the_rail_stays_on_a_narrow_surface(self):
        for width in (800, 1000, 1280):
            s = self._state(0)
            s.draw(pygame.Surface((width, 600)))
            with self.subTest(width=width):
                self.assertGreaterEqual(s.rail.hits.rect_of(0).left, 20)

    def test_four_cards_shift_at_1600_and_narrow_at_1280(self):
        """Four cards at 1600 keep their width and move right, clear of the
        rail; at 1280 they narrow too."""
        w, shift = self._state(4).card_layout(1600)
        self.assertEqual(w, CARD_W_NARROW)
        self.assertGreater(shift, 0)
        w, shift = self._state(4).card_layout(1280)
        self.assertLess(w, CARD_W_NARROW)
        self.assertGreater(shift, 0)


if __name__ == "__main__":
    unittest.main()
