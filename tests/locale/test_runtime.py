"""`game.locale` lookups on hand-built tables (UI-014.2): the current
language, the English fallback, plurals, data fields and number style."""
import unittest

from game import locale

TABLES = {
    "en": {"format.decimal": ".", "menu.start": "Start",
           "chest.gold": "{gold} gold", "only.english": "Only English",
           "forge.needs.one": "needs {n} more blessing",
           "forge.needs.other": "needs {n} more blessings"},
    "es": {"format.decimal": ",", "menu.start": "Empezar",
           "chest.gold": "{gold} de oro",
           "forge.needs.one": "falta {n} bendición",
           "forge.needs.other": "faltan {n} bendiciones"},
}


class LocaleCase(unittest.TestCase):
    def setUp(self):
        locale.load(TABLES)
        locale.set_language("en")

    def tearDown(self):
        locale.set_language(locale.DEFAULT)
        locale.load(None)


class LanguageTests(LocaleCase):
    def test_english_is_the_default(self):
        self.assertEqual(locale.DEFAULT, "en")
        self.assertEqual(locale.LANGUAGES[0], "en")
        self.assertIn("es", locale.LANGUAGES)

    def test_set_language_returns_the_code_used(self):
        self.assertEqual(locale.set_language("es"), "es")
        self.assertEqual(locale.language(), "es")

    def test_unknown_language_falls_back_to_english(self):
        locale.set_language("es")
        with self.assertLogs("game.locale", "WARNING"):
            self.assertEqual(locale.set_language("fr"), "en")
        self.assertEqual(locale.language(), "en")
        for bad in (None, "", "ES", 3):
            with self.assertLogs("game.locale", "WARNING"):
                self.assertEqual(locale.set_language(bad), "en")


class LookupTests(LocaleCase):
    def test_t_reads_the_current_language(self):
        self.assertEqual(locale.t("menu.start"), "Start")
        locale.set_language("es")
        self.assertEqual(locale.t("menu.start"), "Empezar")

    def test_t_fills_fields(self):
        locale.set_language("es")
        self.assertEqual(locale.t("chest.gold", gold=40), "40 de oro")

    def test_a_key_missing_in_spanish_shows_english(self):
        locale.set_language("es")
        self.assertEqual(locale.t("only.english"), "Only English")

    def test_a_key_missing_everywhere_shows_the_key_and_logs_once(self):
        with self.assertLogs("game.locale", "WARNING") as logs:
            self.assertEqual(locale.t("no.such.key"), "no.such.key")
            self.assertEqual(locale.t("no.such.key"), "no.such.key")
        self.assertEqual(len(logs.records), 1)

    def test_escaped_braces_render_the_same_with_or_without_fields(self):
        locale.load({"en": {"esc": "Use {{x}}"}})
        self.assertEqual(locale.t("esc"), "Use {x}")
        self.assertEqual(locale.t("esc", extra=1), "Use {x}")

    def test_extra_fields_are_ignored(self):
        self.assertEqual(locale.t("menu.start", gold=3), "Start")

    def test_unfillable_spanish_falls_back_to_english_then_the_key(self):
        # The loader rejects what it can see; a call site passing the wrong
        # fields is caught here and never crashes a draw (UI-014.D11).
        locale.load({"en": {"k": "{n} kills", "e": "{n} only"},
                     "es": {"k": "{m} bajas"}})
        locale.set_language("es")
        with self.assertLogs("game.locale", "WARNING") as logs:
            self.assertEqual(locale.t("k", n=2), "2 kills")
            self.assertEqual(locale.t("e"), "e")
            self.assertEqual(locale.t("e"), "e")
        self.assertEqual(len(logs.records), 2)      # once per key

    def test_a_field_value_that_cannot_format_does_not_raise(self):
        # `load()` bypasses the loader's checks, and a value's own
        # __format__ can raise TypeError; `t` still returns text.
        class Hostile:
            def __format__(self, spec):
                raise TypeError("no")
        locale.load({"en": {"k": "{n:x}", "s": "{n}"}})
        with self.assertLogs("game.locale", "WARNING"):
            self.assertEqual(locale.t("k", n=None), "k")
            self.assertEqual(locale.t("s", n=Hostile()), "s")

    def test_a_field_named_key_or_n_can_be_filled(self):
        # `key` and `n` are lookup arguments, positional-only, so a
        # template may use them as field names ("Press {key} to talk").
        locale.load({"en": {"hint": "Press {key} to talk",
                            "p.one": "{n} {key}", "p.other": "{n} {key}s"}})
        self.assertEqual(locale.t("hint", key="E"), "Press E to talk")
        self.assertEqual(locale.plural("p", 2, key="orb"), "2 orbs")
        # The count owns `{n}`: a caller's own `n=` is overridden, not an error.
        self.assertEqual(locale.plural("p", 1, key="orb", n=9), "1 orb")

    def test_any_error_while_filling_returns_text(self):
        class Boom:
            def __format__(self, spec):
                raise RuntimeError("no")
        locale.load({"en": {"s": "{n}"}})
        with self.assertLogs("game.locale", "WARNING"):
            self.assertEqual(locale.t("s", n=Boom()), "s")

    def test_a_non_text_key_still_returns_text(self):
        with self.assertLogs("game.locale", "WARNING"):
            self.assertEqual(locale.t(5), "5")

    def test_load_resets_the_log_once_memory(self):
        with self.assertLogs("game.locale", "WARNING"):
            locale.t("gone")
        locale.load(TABLES)
        with self.assertLogs("game.locale", "WARNING"):
            locale.t("gone")

    def test_plural_picks_one_or_other(self):
        self.assertEqual(locale.plural("forge.needs", 1), "needs 1 more blessing")
        self.assertEqual(locale.plural("forge.needs", 2), "needs 2 more blessings")
        self.assertEqual(locale.plural("forge.needs", 0), "needs 0 more blessings")
        locale.set_language("es")
        self.assertEqual(locale.plural("forge.needs", 1), "falta 1 bendición")
        self.assertEqual(locale.plural("forge.needs", 3), "faltan 3 bendiciones")


class DataTextTests(LocaleCase):
    ENTRY = {"name": "Sword", "name_es": "Espada",
             "description": "A wide arc.", "description_es": ""}

    def test_english_reads_the_base_field(self):
        self.assertEqual(locale.text(self.ENTRY, "name"), "Sword")

    def test_spanish_reads_the_suffixed_field(self):
        locale.set_language("es")
        self.assertEqual(locale.text(self.ENTRY, "name"), "Espada")

    def test_an_empty_or_missing_translation_shows_english(self):
        locale.set_language("es")
        with self.assertNoLogs("game.locale", "WARNING"):   # "" = not yet
            self.assertEqual(locale.text(self.ENTRY, "description"),
                             "A wide arc.")
        self.assertEqual(locale.text({"desc": "x"}, "desc"), "x")

    def test_a_missing_english_field_is_an_error(self):
        # Required data surfaces as an error, never a silent default, in
        # either language.
        for lang in locale.LANGUAGES:
            locale.set_language(lang)
            with self.assertRaises(KeyError, msg=lang):
                locale.text({"name_es": "Espada"}, "name")

    def test_a_translation_that_is_not_text_shows_english(self):
        # A data typo must never reach font.render as a list or a number.
        locale.set_language("es")
        for bad in (5, ["Espada"], "   ", {"x": 1}, "Esp\x00ada", "\ud800",
                    "​", "﻿", "\xad", "‍⁠"):
            with self.subTest(bad=bad):
                with self.assertLogs("game.locale", "WARNING"):
                    self.assertEqual(
                        locale.text({"name": "Sword", "name_es": bad}, "name"),
                        "Sword")


class NumberTests(LocaleCase):
    def test_shortest_form(self):
        cases = [(0.3, "0.3"), (2, "2"), (2.0, "2"), (12.5, "12.5"),
                 (0.1 + 0.2, "0.3"), (-1.25, "-1.25"), (0, "0"), (-0.0, "0")]
        for value, want in cases:
            self.assertEqual(locale.num(value), want, value)

    def test_fixed_places_and_sign(self):
        self.assertEqual(locale.num(2.25, 1), "2.2")      # round-half-even
        self.assertEqual(locale.num(3, 2), "3.00")
        self.assertEqual(locale.num(0.3, sign=True), "+0.3")
        self.assertEqual(locale.num(-0.3, sign=True), "-0.3")
        self.assertEqual(locale.num(0, sign=True), "+0")

    def test_a_negative_that_rounds_to_zero_loses_its_sign(self):
        self.assertEqual(locale.num(-0.04, 1), "0.0")
        self.assertEqual(locale.num(-0.04, 1, sign=True), "+0.0")

    def test_places_zero_and_small_values(self):
        self.assertEqual(locale.num(2.6, 0), "3")
        self.assertEqual(locale.num(0.000001), "0.000001")

    def test_no_decimal_entry_means_a_point(self):
        # A table without `format.decimal` must not print the key into
        # every number ("1format.decimal5").
        locale.load({"en": {}, "es": {}})
        locale.set_language("es")
        self.assertEqual(locale.num(1.5), "1.5")
        locale.load({"en": {"format.decimal": "."}, "es": {}})
        self.assertEqual(locale.num(1.5), "1.5")

    def test_a_decimal_entry_that_is_not_one_character_is_ignored(self):
        for bad in ("ab", "", 3):
            locale.load({"en": {}, "es": {"format.decimal": bad}})
            locale.set_language("es")
            self.assertEqual(locale.num(1.5), "1.5", bad)

    def test_spanish_uses_a_decimal_comma(self):
        locale.set_language("es")
        self.assertEqual(locale.num(0.3), "0,3")
        self.assertEqual(locale.num(2.5, 2, sign=True), "+2,50")
        self.assertEqual(locale.num(12), "12")


class NameTests(LocaleCase):
    def test_each_language_is_named_in_itself_whatever_is_active(self):
        locale.load({"en": {"language.name": "English"},
                     "es": {"language.name": "Español"}})
        for active in locale.LANGUAGES:
            locale.set_language(active)
            self.assertEqual(locale.name_of("en"), "English")
            self.assertEqual(locale.name_of("es"), "Español")

    def test_a_missing_name_shows_the_code(self):
        locale.load({"en": {}, "es": {"language.name": "   "}})
        self.assertEqual(locale.name_of("es"), "es")
        self.assertEqual(locale.name_of("xx"), "xx")


class RealTablesTests(unittest.TestCase):
    """`load(None)` goes back to the tables the content loader built."""

    def tearDown(self):
        locale.set_language(locale.DEFAULT)
        locale.load(None)

    def test_reads_the_shipped_files(self):
        locale.load(None)
        self.assertEqual(locale.name_of("es"), "Español")
        locale.set_language("es")
        self.assertEqual(locale.num(1.5), "1,5")
        locale.set_language("en")
        self.assertEqual(locale.num(1.5), "1.5")


if __name__ == "__main__":
    unittest.main()
