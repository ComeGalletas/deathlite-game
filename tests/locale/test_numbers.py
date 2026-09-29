"""Numbers in the language's style (UI-014.10, UI-014.D7): the decimal
mark, the thousands mark and the unit after a number come from the locale.

English is pinned to the text each formatter printed before -- the literals
below are the old f-strings' output -- and Spanish is the D7 style: "+0,3 s",
"+25 %", "x2,2", "1.234", with a no-break space (U+00A0) before a unit so it
never wraps from its number.
"""
import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game import locale
from game.content import get_content
from progression.blessings.catalog import DISPLAYS, format_value, get_catalog
from ui import run_summary
from ui.run_status import build, common

NB = " "


def both(fn):
    locale.set_language("en")
    en = fn()
    locale.set_language("es")
    try:
        return en, fn()
    finally:
        locale.set_language(locale.DEFAULT)


class FormatValueTests(unittest.TestCase):
    CASES = {  # (value, display): (English as it always printed, Spanish)
        (20, "flat"): ("+20", "+20"),
        (2.5, "flat"): ("+2.5", "+2,5"),
        (0.25, "pct"): ("+25%", f"+25{NB}%"),
        (1.15, "pct_gain"): ("+15%", f"+15{NB}%"),
        (0.84, "pct_drop"): ("16%", f"16{NB}%"),
        (0.35, "chance"): ("35%", f"35{NB}%"),
        (0.3, "seconds"): ("+0.3s", f"+0,3{NB}s"),
        (2.0, "duration"): ("2s", f"2{NB}s"),
        (1.5, "duration"): ("1.5s", f"1,5{NB}s"),
        (2.2, "mult"): ("x2.2", "x2,2"),
        (15, "degrees"): ("+15°", "+15°"),
        (7.5, "degrees"): ("+7.5°", "+7,5°"),
        (0.5, "raw"): ("0.5", "0,5"),
        (3, "hidden"): ("3", "3"),
    }

    def test_every_display_in_both_languages(self):
        self.assertEqual({d for _v, d in self.CASES}, set(DISPLAYS))
        for (value, display), want in self.CASES.items():
            with self.subTest(display=display, value=value):
                self.assertEqual(both(lambda: format_value(value, display)), want)

    def test_every_spanish_card_is_in_the_d7_style(self):
        """No decimal point between digits, and no breaking space before a
        unit, in any Spanish card at any level; English has neither a
        decimal comma nor a no-break space."""
        self.addCleanup(locale.set_language, locale.DEFAULT)
        cat = get_catalog(get_content())
        texts = {lang: [] for lang in ("en", "es")}
        for lang in texts:
            locale.set_language(lang)
            for b in cat.by_id.values():
                for lvl in range(1, b.max_level + 1):
                    texts[lang].append(b.describe(lvl))
        locale.set_language(locale.DEFAULT)
        for s in texts["es"]:
            with self.subTest(text=s):
                self.assertIsNone(re.search(r"\d\.\d", s))
                self.assertIsNone(re.search(r"\d [%s°]", s))
        for s in texts["en"]:
            with self.subTest(text=s):
                self.assertIsNone(re.search(r"\d,\d", s))
                self.assertNotIn(NB, s)
        self.assertTrue([s for s in texts["es"] if re.search(rf"\d,\d", s)])  # decimals occur
        self.assertTrue([s for s in texts["es"] if f"{NB}%" in s])


class LocaleNumberTests(unittest.TestCase):
    def test_grouped(self):
        self.assertEqual(both(lambda: locale.grouped(1234567)), ("1,234,567", "1.234.567"))
        self.assertEqual(both(lambda: locale.grouped(999.6)), ("1,000", "1.000"))
        self.assertEqual(both(lambda: locale.grouped(-4321)), ("-4,321", "-4.321"))
        self.assertEqual(both(lambda: locale.grouped(12)), ("12", "12"))

    def test_units(self):
        for kind, want in (("percent", ("7%", f"7{NB}%")), ("seconds", ("7s", f"7{NB}s")),
                           ("mult", ("x7", "x7")), ("degrees", ("7°", "7°"))):
            with self.subTest(kind=kind):
                self.assertEqual(both(lambda: locale.unit(kind, "7")), want)

    def test_a_malformed_mark_falls_back(self):
        """A mark that is not one character (a typo in a table) is never
        put inside a number: the English mark is used, then the default."""
        tables = {lang: dict(locale._table(lang)) for lang in locale.LANGUAGES}
        try:
            # English marks unlike the defaults, so "fell back to English"
            # and "fell back to the default" read differently.
            tables["en"]["format.thousands"] = "'"
            tables["en"]["format.decimal"] = "·"
            tables["es"]["format.thousands"] = "mil"
            tables["es"]["format.decimal"] = ""
            locale.load(tables)
            self.assertEqual(both(lambda: locale.grouped(1234)), ("1'234", "1'234"))
            self.assertEqual(both(lambda: locale.decimals("0.5")), ("0·5", "0·5"))
            del tables["en"]["format.thousands"]
            del tables["es"]["format.thousands"]
            locale.load(tables)
            self.assertEqual(both(lambda: locale.grouped(1234)), ("1,234", "1,234"))
        finally:
            locale.load(None)

    def test_the_seconds_unit_is_set_in_one_place(self):
        """The infusion rail, the TAB pace line and the menu's best line take
        their unit from `unit.seconds`: change it once, they all change."""
        from types import SimpleNamespace
        from combat.elements.ids import ElementId
        from combat.weapons.core import TIME_MODE
        from game.states.playing.core import infusion
        weapon = SimpleNamespace(element_mode=TIME_MODE, element_window=1.5,
                                 element_interval=0, element=ElementId.WIND)
        tables = {lang: dict(locale._table(lang)) for lang in locale.LANGUAGES}
        try:
            for lang in locale.LANGUAGES:
                tables[lang]["unit.seconds"] = "{n} seg"
            locale.load(tables)
            en, es = both(lambda: (infusion._pace(weapon),
                                   build.infusion_text(weapon).split("  ·  ")[1],
                                   locale.t("menu.summary", salvage=1, time=locale.unit(
                                       "seconds", "95"), level=2, kills=3, items=4)))
        finally:
            locale.load(None)
        self.assertEqual(en[:2], ("every 1.5 seg", "every 1.5 seg"))
        self.assertEqual(es[:2], ("cada 1,5 seg", "cada 1,5 seg"))
        self.assertIn("Best: 95 seg /", en[2])
        self.assertIn("Mejor: 95 seg /", es[2])
        # As shipped, English is what it always was.
        self.assertEqual(both(lambda: infusion._pace(weapon)),
                         ("every 1.5s", f"cada 1,5{NB}s"))

    def test_every_unit_reaches_its_call_sites(self):
        """Each `unit.*` is the one place its style is set: changed there,
        every screen that prints it changes -- the cards, the TAB numbers,
        the stats, an item's tag damage, the summary's share."""
        from types import SimpleNamespace
        from ui.run_status.overview import item_lines
        tables = {lang: dict(locale._table(lang)) for lang in locale.LANGUAGES}
        try:
            for lang in locale.LANGUAGES:
                tables[lang]["unit.mult"] = "×{n}"
                tables[lang]["unit.degrees"] = "{n} grad"
                tables[lang]["unit.percent"] = "{n} pct"
            locale.load(tables)
            en, _es = both(lambda: (
                format_value(2.2, "mult"), format_value(15, "degrees"),
                format_value(0.25, "pct"), build._fmt(22.5, "deg"),
                common.fmt_stat("damage_multiplier", 1.25),
                common.fmt_stat("crit_chance", 0.12),
                item_lines(SimpleNamespace(base_stat="armor", base_op="flat", base_value=2.0,
                                           affixes=[SimpleNamespace(kind="tag_damage",
                                                                    value=0.5, tag="elite")],
                                           unique_effect=None))[1],
                run_summary._share_text(0.98)))
        finally:
            locale.load(None)
        self.assertEqual(en, ("×2.2", "+15 grad", "+25 pct", "22.5 grad", "×1.25", "12 pct",
                              "+50 pct damage vs elite", "98 pct"))

    def test_the_menus_best_line_takes_the_seconds_unit(self):
        import tempfile
        from game.game import Game
        from game.states.menu_state import MenuState
        tables = {lang: dict(locale._table(lang)) for lang in locale.LANGUAGES}
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        seen = []

        class Rec:
            def __init__(self, font):
                self.font = font

            def render(self, text, *a, **k):
                seen.append(str(text))
                return self.font.render(text, *a, **k)

            def __getattr__(self, name):
                return getattr(self.font, name)
        try:
            for lang in locale.LANGUAGES:
                tables[lang]["unit.seconds"] = "{n} seg"
            locale.load(tables)
            menu = MenuState(game)
            game.state_machine.change(menu)
            menu._small = Rec(menu._small)
            menu.draw(game.screen)
        finally:
            locale.load(None)
        self.assertTrue([t for t in seen if re.search(r"Best: \d+ seg /", t)], seen)

    def test_the_rankings_seconds_match_the_unit_in_spanish(self):
        """`rankings.seconds` keeps its own English ("95 s", a plain space,
        as the rankings always read); its Spanish is the unit's."""
        es = get_content().locale["es"]
        self.assertEqual(es["rankings.seconds"], es["unit.seconds"])
        self.assertEqual(get_content().locale["en"]["rankings.seconds"], "{n} s")


class ScreenNumberTests(unittest.TestCase):
    def test_stats(self):
        cases = {("damage_multiplier", 1.25): ("x1.25", "x1,25"),
                 ("crit_chance", 0.12): ("12%", f"12{NB}%"),
                 ("melee_damage", 0.3): ("+30%", f"+30{NB}%"),
                 ("hp_regen", 1.5): ("1.5 / 5s", f"1,5 / 5{NB}s"),
                 ("move_speed", 150.5): ("150.5", "150,5")}
        for (stat, value), want in cases.items():
            with self.subTest(stat=stat):
                self.assertEqual(both(lambda: common.fmt_stat(stat, value)), want)

    def test_modifiers(self):
        cases = {("damage_multiplier", "pct", 0.2): ("+20% Damage", f"+20{NB}% Daño"),
                 ("attack_speed_multiplier", "mult", 0.1): ("x1.10 Attack speed",
                                                           "x1,10 Vel. ataque"),
                 ("crit_chance", "flat", 0.05): ("+5% Crit chance", f"+5{NB}% Prob. crítico"),
                 ("armor", "flat", 3.917): ("+3.9 Armor", "+3,9 Armadura"),
                 ("armor", "flat", 4.0): ("+4 Armor", "+4 Armadura")}
        for (stat, op, value), want in cases.items():
            with self.subTest(stat=stat, op=op):
                self.assertEqual(both(lambda: common.fmt_mod(stat, op, value)), want)

    def test_weapon_numbers(self):
        self.assertEqual(both(lambda: build._fmt(0.75, "s")), ("0.75s", f"0,75{NB}s"))
        self.assertEqual(both(lambda: build._fmt(22.5, "deg")), ("22.5°", "22,5°"))
        self.assertEqual(both(lambda: build._fmt(1.5, "n")), ("1.5", "1,5"))
        self.assertEqual(both(lambda: build._fmt([1.5, 2], "n")), ("1.5, 2", "1,5, 2"))

    def test_summary_figures(self):
        self.assertEqual(both(lambda: run_summary.fmt_damage(12345.4)), ("12,345", "12.345"))
        self.assertEqual(both(lambda: run_summary.fmt_dps(20.25)), ("20.2", "20,2"))


if __name__ == "__main__":
    unittest.main()
