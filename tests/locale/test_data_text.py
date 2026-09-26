"""Spanish data text (UI-014.4): every player-facing field in `data/` has a
drawable `<field>_es` beside it, carrying the same numbers and placeholders.

`game.locale.text` falls back to English on a hole, so a missing translation
never crashes the game; these tests are what keep the holes out. A data file
with player-facing text is either in `TRANSLATED` (checked field by field) or
in `PENDING` (not translated yet, named with the task that will do it).
Nothing is skipped: a new text-bearing file fails until it is placed in one
of the two.
"""
import json
import re
import unittest
from collections import Counter
from string import Formatter

from game import locale
from game.content import DATA_DIR

LANG = "es"

# English field names that hold player-facing text, wherever they appear.
TEXT_FIELDS = ("name", "description", "desc", "identity", "trait_name",
               "trait_desc")

TRANSLATED = (
    "weapons/weapons.json",        # UI-014.4.1
    "weapons/items.json",          # UI-014.4.1
)
PENDING = {
    "weapons/forges.json": "UI-014.4.2",
    "weapons/blessings.json": "UI-014.4.2",
    "heroes/characters.json": "UI-014.4.3",
    "heroes/meta_upgrades.json": "UI-014.4.3",
    "enemies/enemies.json": "UI-014.4.3",
    "enemies/bosses.json": "UI-014.4.3",
    "world/buildings.json": "UI-014.4.3",
}

# `_es` keys that are data about the Spanish text rather than a translation
# of an English key: an item base's grammatical gender (UI-014.D9).
NO_ENGLISH_SIBLING = ("gender_es",)

# A number with its sign and an optional percent sign ("+25%", "+25 %",
# "-0,4 s"). No data text uses a thousands separator, so a comma between
# digits is read as the decimal comma.
_NUMBER = re.compile(r"([+\-−]?)(\d+(?:[.,]\d+)?)(\s?%)?")
_PLACEHOLDER = ""         # private use: defined by neither shipped font


# UI-014.D7 number style in Spanish text: what each pattern catches.
_STYLE = (
    (re.compile(r"\d\.\d"), "decimal point (use a comma)"),
    (re.compile(r"\d(?:%|s\b)"), "unit touching the number (use a no-break space)"),
    # Any space `ui.text.wrap` may break at (thin, em, ideographic, a
    # newline...), which is every whitespace but the no-break ones.
    # One such space anywhere in the run is enough to split the pair.
    (re.compile(r"\d\s*[^\S   ]\s*(?:%|s\b)"),
     "breaking space before the unit (use U+00A0)"),
)


def style_problems(text):
    """The UI-014.D7 rules a Spanish text breaks, as short descriptions."""
    return [why for pattern, why in _STYLE if pattern.search(text)]


def shipped_faces():
    """The two bundled faces. `game.fonts` falls back to a system font when a
    file is missing, which would make the glyph checks test the wrong font,
    so the files must be there."""
    import pygame
    from game import fonts
    for fname in fonts._FILES.values():
        assert (fonts.FONTS_DIR / fname).is_file(), f"bundled font missing: {fname}"
    pygame.font.init()
    return (("body", fonts.body(16, scaled=False)),
            ("heading", fonts.heading(16, scaled=False)))


def _pixels(face, text):
    import pygame
    surf = face.render(text, True, (255, 255, 255), (0, 0, 0))
    return surf.get_size(), pygame.image.tobytes(surf, "RGB")


def has_glyph(face, char):
    """False when `char` renders exactly as the missing-glyph box does.
    Whitespace has no ink to compare and counts as present."""
    if char.isspace():
        return True
    return _pixels(face, char) != _pixels(face, _PLACEHOLDER)


def _load(rel):
    with (DATA_DIR / rel).open(encoding="utf-8") as fh:
        return json.load(fh)


def _walk(node, path=""):
    """Every object in `node`, with its slash path."""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            if not k.startswith("_"):
                yield from _walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}/{i}")


def text_pairs(doc):
    """(path, English, translation-or-None) for every player-facing field."""
    for path, obj in _walk(doc):
        for field in TEXT_FIELDS:
            if isinstance(obj.get(field), str):
                yield f"{path}/{field}", obj[field], obj.get(f"{field}_{LANG}")


def untranslated(pairs):
    """The paths among `(path, English, translation)` whose translation is
    missing or not drawable text."""
    return [p for p, _, es in pairs if not locale.renderable(es)]


def orphans(doc):
    """`_es` keys with no English sibling (bar `NO_ENGLISH_SIBLING`)."""
    return [f"{path}/{key}" for path, obj in _walk(doc) for key in obj
            if key.endswith(f"_{LANG}") and key not in NO_ENGLISH_SIBLING
            and key[:-len(LANG) - 1] not in obj]


def numbers(text):
    """The numbers in a text as a multiset of (sign, value, percent): the
    decimal comma reads as a point and the space before `%` is ignored, so
    "+0.4s, 30%" and "+0,4 s, 30 %" match, while "+25%" / "-25" and
    "30%" / "30" do not. Numbers written as words are not compared."""
    return Counter((sign.replace("−", "-"), float(value.replace(",", ".")),
                    bool(pct))
                   for sign, value, pct in _NUMBER.findall(text))


def fields(text):
    """The `{…}` fields of a text with their format spec and conversion,
    positional ones included (blessing descriptions are filled with `{0}` /
    `{1}` by `catalog.describe`): `{0:.0%}` and `{0}` differ."""
    return Counter((name, spec, conv) for _, name, spec, conv
                   in Formatter().parse(text) if name is not None)


class RegistryTests(unittest.TestCase):
    def test_every_text_bearing_file_is_translated_or_pending(self):
        found = set()
        for path in sorted(DATA_DIR.rglob("*.json")):
            rel = path.relative_to(DATA_DIR).as_posix()
            if rel.startswith("locale/"):
                continue
            if any(True for _ in text_pairs(_load(rel))):
                found.add(rel)
        placed = set(TRANSLATED) | set(PENDING)
        self.assertEqual(sorted(found - placed), [],
                         "text-bearing data files in neither list")
        self.assertEqual(sorted(placed - found), [],
                         "listed files that carry no text")
        self.assertFalse(set(TRANSLATED) & set(PENDING))


class TranslatedFileTests(unittest.TestCase):
    """Field by field, for every file in `TRANSLATED`."""

    def pairs(self):
        for rel in TRANSLATED:
            for path, en, es in text_pairs(_load(rel)):
                yield f"{rel}{path}", en, es

    def test_every_field_has_a_drawable_translation(self):
        self.assertEqual(untranslated(self.pairs()), [])

    def test_numbers_match_english(self):
        # A translation must not quietly change "30%" to "35 %" or drop
        # "0.4s": the numbers in the text are gameplay facts.
        for path, en, es in self.pairs():
            with self.subTest(path=path):
                self.assertEqual(numbers(es), numbers(en), f"{en!r} / {es!r}")

    def test_placeholders_match_english(self):
        for path, en, es in self.pairs():
            with self.subTest(path=path):
                self.assertEqual(fields(es), fields(en), f"{en!r} / {es!r}")

    def test_numbers_follow_the_spanish_style(self):
        # UI-014.D7: decimal comma, and a no-break space between a number
        # and "%" or "s" ("+25 %", "0,4 s").
        bad = [(p, es, style_problems(es)) for p, _, es in self.pairs()
               if style_problems(es)]
        self.assertEqual(bad, [])

    def test_spanish_is_not_a_copy_of_english(self):
        # Proper names that stay the same in Spanish go here, on purpose.
        same_on_purpose = set()
        copied = [p for p, en, es in self.pairs()
                  if es == en and p not in same_on_purpose]
        self.assertEqual(copied, [])

    def test_every_character_has_a_real_glyph_in_the_shipped_fonts(self):
        # pygame draws a missing glyph as a placeholder box without raising,
        # and `Font.metrics` reports every character present, so neither can
        # tell. A character is missing when it renders pixel-identical to a
        # private-use codepoint no font here defines.
        faces = shipped_faces()
        chars = sorted({c for _, _, es in self.pairs() for c in es})
        missing = [(name, c) for name, face in faces for c in chars
                   if not has_glyph(face, c)]
        self.assertEqual(missing, [])


class OrphanTests(unittest.TestCase):
    def test_no_translation_without_its_english_field(self):
        # A `name_es` whose `name` was renamed away would be dead text that
        # nothing reads. Checked across every data file, pending ones too.
        found = []
        for path in sorted(DATA_DIR.rglob("*.json")):
            rel = path.relative_to(DATA_DIR).as_posix()
            if not rel.startswith("locale/"):
                found += [f"{rel}{o}" for o in orphans(_load(rel))]
        self.assertEqual(found, [])


class ItemGrammarTests(unittest.TestCase):
    """UI-014.D9: a Spanish item name puts the rarity adjective after the
    base and agrees with its gender, so every base carries `gender_es` and
    every rarity has both forms."""

    def setUp(self):
        self.items = _load("weapons/items.json")

    def test_every_base_has_a_gender(self):
        for slot, bases in self.items["bases"].items():
            for base in bases:
                self.assertIn(base.get("gender_es"), ("m", "f"),
                              f"{slot}/{base['id']}")

    def test_every_rarity_prefix_has_both_forms(self):
        es = self.items["prefixes_es"]
        self.assertEqual(sorted(es), sorted(self.items["prefixes"]))
        faces = shipped_faces()
        for rarity, forms in es.items():
            self.assertEqual(sorted(forms), ["f", "m"], rarity)
            for form in forms.values():
                self.assertTrue(locale.renderable(form), rarity)
                self.assertNotEqual(form, self.items["prefixes"][rarity], rarity)
                missing = [(n, c) for n, face in faces for c in form
                           if not has_glyph(face, c)]
                self.assertEqual(missing, [], rarity)


class HelperTests(unittest.TestCase):
    """The comparison rules themselves."""

    def test_numbers_read_a_decimal_comma_and_ignore_spacing(self):
        self.assertEqual(numbers("after 0.4s, take 30% less"),
                         numbers("tras 0,4 s, recibes un 30 % menos"))
        self.assertNotEqual(numbers("+25%"), numbers("+35 %"))
        self.assertNotEqual(numbers("2 arrows at 65%"), numbers("flechas al 65 %"))
        self.assertNotEqual(numbers("+25% Salvage"), numbers("-25 de chatarra"))
        self.assertNotEqual(numbers("30% less"), numbers("30 menos"))
        self.assertEqual(numbers("+25% Salvage"), numbers("+25 % de chatarra"))
        self.assertNotEqual(numbers("+25%"), numbers("-25 %"))       # sign alone
        self.assertNotEqual(numbers("+25%"), numbers("25 %"))
        self.assertNotEqual(numbers("1.5s"), numbers("15 s"))        # decimals
        self.assertEqual(numbers("1.5s"), numbers("1,5 s"))

    def test_untranslated_flags_missing_and_undrawable(self):
        pairs = [("/a", "A", "Ae"), ("/b", "B", None), ("/c", "C", ""),
                 ("/d", "D", "   "), ("/e", "E", 5), ("/f", "F", "​")]
        self.assertEqual(untranslated(pairs), ["/b", "/c", "/d", "/e", "/f"])

    def test_orphans_flags_a_translation_without_english(self):
        doc = {"a": {"name": "N", "name_es": "Ne", "gender_es": "m"},
               "b": {"desc_es": "sin inglés"}, "l": [{"x_es": "y"}]}
        self.assertEqual(orphans(doc), ["/b/desc_es", "/l/0/x_es"])

    def test_the_style_rules(self):
        nb = " "
        for good in (f"+25{nb}% de chatarra", f"tras 0,4{nb}s", "Invoca 2 sombras",
                     "dura 3 segundos", "Sello de batalla", f"+1,5{nb}s y 30{nb}%"):
            self.assertEqual(style_problems(good), [], good)
        for bad in ("+25% de chatarra", "+25 % de chatarra", "tras 0,4 s",
                    "tras 0,4s", f"+0.4{nb}s", "30 % menos", "30 %",
                    "0,4　s", "30 %", "30\n%"):
            self.assertNotEqual(style_problems(bad), [], repr(bad))
        # The rule and `wrap` agree on which spaces break: whatever the style
        # check accepts between a number and "%", wrap keeps on one line.
        from ui import text as text_mod
        from ui.text import wrap
        spaces = [chr(cp) for cp in range(0x110000) if chr(cp).isspace()]
        for ch in spaces:
            joined = not text_mod._BREAK.fullmatch(ch)
            self.assertEqual(style_problems(f"30{ch}%") == [], joined, hex(ord(ch)))
        # Runs of two: the check passes a run exactly when wrap keeps
        # "30" and "%" on one line.
        face = shipped_faces()[0][1]
        for a in spaces:
            for b in (" ", nb, " ", "\t"):
                for run in (a + b, b + a):
                    text = f"30{run}%"
                    one_line = len(wrap(face, text, 1)) == 1
                    self.assertEqual(style_problems(text) == [], one_line, repr(text))

    def test_the_glyph_check_sees_a_missing_glyph(self):
        # Neither shipped font has CJK: the check must say so, and must see
        # every Spanish letter as present.
        for name, face in shipped_faces():
            self.assertFalse(has_glyph(face, "中"), name)
            for c in "áéíóúüñÁÉÍÓÚÜÑ¿¡«»":
                self.assertTrue(has_glyph(face, c), f"{name} {c}")

    def test_fields_count_positional_and_named(self):
        self.assertEqual(fields("{0} max HP"), fields("{0} de PV máx."))
        self.assertNotEqual(fields("{0} and {1}"), fields("{0}"))
        self.assertNotEqual(fields("{0:.0%} more"), fields("{0} más"))
        self.assertEqual(fields("no fields"), Counter())

    def test_the_walk_finds_nested_and_listed_fields(self):
        doc = {"a": {"name": "A", "name_es": "Ae"},
               "l": [{"desc": "D"}], "_doc": {"name": "skip"}}
        self.assertEqual(sorted(text_pairs(doc)),
                         [("/a/name", "A", "Ae"), ("/l/0/desc", "D", None)])


if __name__ == "__main__":
    unittest.main()
