"""The shipped `data/locale/*.json` files and their loader (UI-014.2).

The loader is fail-soft (a bad entry is dropped and shown in English); these
tests are what hold the files to full parity, so a hole fails here instead
of reaching a player as an English word in a Spanish screen."""
import json
import unittest

from game import locale
from game.content import DATA_DIR, _check_locale, get_content


def _raw(lang):
    with (DATA_DIR / "locale" / f"{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


class ShippedFilesTests(unittest.TestCase):
    def test_every_language_has_a_file(self):
        for lang in locale.LANGUAGES:
            self.assertTrue((DATA_DIR / "locale" / f"{lang}.json").is_file(), lang)

    def test_the_loader_drops_nothing(self):
        # Validating the raw files must neither log nor drop: every entry is
        # well-formed and every translation matches its English key.
        raw = {lang: _raw(lang) for lang in locale.LANGUAGES}
        with self.assertNoLogs("game.content", "WARNING"):
            tables = _check_locale(raw)
        self.assertEqual(tables, get_content().locale)

    def test_every_language_has_every_english_key(self):
        tables = get_content().locale
        ref = tables[locale.DEFAULT]
        self.assertTrue(ref)
        for lang in locale.LANGUAGES:
            self.assertEqual(sorted(ref.keys() - tables[lang].keys()), [],
                             f"{lang}.json lacks these keys")
            self.assertEqual(sorted(tables[lang].keys() - ref.keys()), [],
                             f"{lang}.json has keys English lacks")

    def test_placeholders_match_english(self):
        tables = get_content().locale
        ref = tables[locale.DEFAULT]
        for lang in locale.LANGUAGES:
            for key, template in tables[lang].items():
                self.assertEqual(locale.placeholders(template),
                                 locale.placeholders(ref[key]), f"{lang}: {key}")

    def test_plurals_come_in_pairs(self):
        for lang, table in get_content().locale.items():
            for key in table:
                stem, _, form = key.rpartition(".")
                if form in ("one", "other"):
                    twin = "other" if form == "one" else "one"
                    self.assertIn(f"{stem}.{twin}", table, f"{lang}: {key}")

    def test_spanish_is_not_a_copy_of_english(self):
        # A key whose Spanish is byte-identical to English is almost always
        # an untranslated paste. Exceptions must be listed here on purpose.
        same_on_purpose = set()
        tables = get_content().locale
        copied = sorted(k for k, v in tables["es"].items()
                        if v == tables["en"][k] and k not in same_on_purpose
                        and any(c.isalpha() for c in v))
        self.assertEqual(copied, [])


class LoaderTests(unittest.TestCase):
    def check(self, en, es):
        return _check_locale({"en": en, "es": es})

    def test_nested_groups_flatten_to_dotted_keys(self):
        tables = self.check({"_doc": "x", "a": {"b": {"c": "C"}, "_n": "x"}},
                            {"a": {"b": {"c": "Ce"}}})
        self.assertEqual(tables, {"en": {"a.b.c": "C"}, "es": {"a.b.c": "Ce"}})

    def test_a_non_text_leaf_is_dropped(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"a": "A", "n": 3, "e": "", "l": ["x"]},
                                {"a": "Ae"})
        self.assertEqual(tables["en"], {"a": "A"})

    def test_text_a_font_cannot_draw_is_dropped(self):
        # JSON allows "\u0000" and lone surrogates; Font.render raises on
        # both, and a blank label would show nothing instead of English.
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"a": "A", "b": "B", "c": "C"},
                                {"a": "A\x00e", "b": "\ud800", "c": "   "})
        self.assertEqual(tables["es"], {})
        # Only zero-width / format / combining characters: Font.render
        # raises "Text has zero width" on each, so they are not drawable.
        for invisible in ("​", "‌", "‍", "⁠", "﻿",
                          "\xad", "́"):
            with self.subTest(invisible=repr(invisible)):
                with self.assertLogs("game.content", "WARNING"):
                    tables = self.check({"a": "A"}, {"a": invisible})
                self.assertEqual(tables["es"], {})

    def test_the_drawable_rule_matches_pygame(self):
        # Whatever `renderable` accepts renders with the shipped fonts, and
        # the invisible strings it rejects make Font.render raise. It is
        # stricter than pygame in one place on purpose: a lone combining
        # accent draws a floating mark, but is never a real label.
        import pygame
        from game.fonts import body, heading
        pygame.font.init()
        good = ["A", "¿Qué?", "Niño​", "x́", "¡Sí!"]
        bad = ["​", "﻿", "\xad"]
        self.assertFalse(locale.renderable("́"))
        for font in (body(16, scaled=False), heading(16, scaled=False)):
            for s in good:
                self.assertTrue(locale.renderable(s), repr(s))
                font.render(s, True, (0, 0, 0))
            for s in bad:
                # Rejected: pygame either raises ("Text has zero width") or,
                # depending on the font's state, draws nothing visible.
                self.assertFalse(locale.renderable(s), repr(s))
                try:
                    surface = font.render(s, True, (0, 0, 0))
                except pygame.error:
                    continue
                self.assertIsNone(surface.get_bounding_rect().size[0] or None,
                                  repr(s))

    def test_an_empty_key_is_dropped(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"": "X", "a": {"": "Y"}, "b": "B"}, {"b": "Be"})
        self.assertEqual(tables["en"], {"b": "B"})

    def test_a_translation_of_a_dropped_english_key_says_so(self):
        with self.assertLogs("game.content", "WARNING") as logs:
            self.check({"a": "{"}, {"a": "x"})
        self.assertTrue(any("a was dropped from en.json" in m
                            for m in logs.output), logs.output)

    def test_every_shipped_text_can_be_drawn(self):
        # Rendering alone proves little (a missing glyph draws as a box, no
        # error), so every character is checked for a real glyph as well.
        from tests.locale.test_data_text import has_glyph, shipped_faces
        faces = shipped_faces()
        for lang, table in get_content().locale.items():
            for key, template in table.items():
                with self.subTest(lang=lang, key=key):
                    for name, face in faces:
                        face.render(template, True, (0, 0, 0))
                        self.assertEqual(
                            [c for c in template if not has_glyph(face, c)], [], name)

    def test_a_malformed_template_is_dropped(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"a": "A {x}", "b": "B {"}, {"a": "Ae {x"})
        self.assertEqual(tables["en"], {"a": "A {x}"})
        self.assertEqual(tables["es"], {})

    def test_only_plain_named_fields_are_allowed(self):
        # Each of these keeps its field *names* equal to English's yet would
        # crash (or silently misrender) at draw time, so all are rejected.
        bad = ["{n:d} bajas", "{n:{w}} bajas", "{n!x} bajas", "{n!r} bajas",
               "{0} bajas", "{} bajas", "{n.real} bajas", "{n[0]} bajas"]
        for template in bad:
            with self.subTest(template=template):
                with self.assertLogs("game.content", "WARNING"):
                    tables = self.check({"k": "{n} kills"}, {"k": template})
                self.assertEqual(tables["es"], {})
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"p": "{0} kills", "a": "{} kills"}, {})
        self.assertEqual(tables["en"], {})

    def test_escaped_braces_are_text_not_fields(self):
        tables = self.check({"k": "{{x}} {n}"}, {"k": "{{x}} {n}!"})
        self.assertEqual(tables["es"], {"k": "{{x}} {n}!"})

    def test_a_dotted_key_is_dropped_rather_than_colliding(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"a.b": "X", "a": {"b": "Y"}}, {"a": {"b": "Ye"}})
        self.assertEqual(tables["en"], {"a.b": "Y"})
        self.assertEqual(tables["es"], {"a.b": "Ye"})

    def test_a_key_english_lacks_is_dropped(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"a": "A"}, {"a": "Ae", "z": "Z"})
        self.assertEqual(tables["es"], {"a": "Ae"})

    def test_mismatched_placeholders_are_dropped(self):
        with self.assertLogs("game.content", "WARNING") as logs:
            tables = self.check({"g": "{gold} gold", "k": "{n} kills"},
                                {"g": "{oro} de oro", "k": "{n} bajas"})
        self.assertEqual(tables["es"], {"k": "{n} bajas"})
        self.assertTrue(any("g uses" in m for m in logs.output))

    def test_untranslated_keys_are_counted_not_fatal(self):
        with self.assertLogs("game.content", "WARNING") as logs:
            tables = self.check({"a": "A", "b": "B"}, {"a": "Ae"})
        self.assertEqual(tables["es"], {"a": "Ae"})
        self.assertTrue(any("1 key(s) untranslated" in m for m in logs.output))

    def test_a_dropped_translation_falls_back_to_english_at_runtime(self):
        with self.assertLogs("game.content", "WARNING"):
            tables = self.check({"g": "{gold} gold"}, {"g": "{oro} de oro"})
        locale.load(tables)
        try:
            locale.set_language("es")
            self.assertEqual(locale.t("g", gold=5), "5 gold")
        finally:
            locale.set_language(locale.DEFAULT)
            locale.load(None)


if __name__ == "__main__":
    unittest.main()
