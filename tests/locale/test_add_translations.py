"""`tools/localization/add_translations.py` (UI-014.4): places `<field>_es`
keys beside their English fields without reformatting the file."""
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from game.content import DATA_DIR
from tools.localization.add_translations import apply, dumps, main, place


class PlacementTests(unittest.TestCase):
    def test_after_its_english_sibling(self):
        doc = apply({"a": {"name": "N", "hp": 3, "desc": "D"}},
                    {"a/desc_es": "De", "a/name_es": "Ne"})
        self.assertEqual(list(doc["a"]), ["name", "name_es", "hp", "desc", "desc_es"])

    def test_without_a_sibling_after_the_last_key_in_that_language(self):
        doc = apply({"b": {"id": "x", "name": "N", "stat": 1}},
                    {"b/name_es": "Ne", "b/gender_es": "f"})
        self.assertEqual(list(doc["b"]), ["id", "name", "name_es", "gender_es", "stat"])

    def test_with_nothing_in_that_language_at_the_end(self):
        doc = apply({"b": {"id": "x", "stat": 1}}, {"b/gender_es": "m"})
        self.assertEqual(list(doc["b"]), ["id", "stat", "gender_es"])

    def test_a_top_level_object_value(self):
        doc = apply({"prefixes": {"rare": "Runed"}, "tail": 1},
                    {"prefixes_es": {"rare": {"m": "rúnico", "f": "rúnica"}}})
        self.assertEqual(list(doc), ["prefixes", "prefixes_es", "tail"])

    def test_list_items_by_index(self):
        doc = apply({"bases": {"armor": [{"name": "A"}, {"name": "B"}]}},
                    {"bases/armor/1/name_es": "Be"})
        self.assertEqual(doc["bases"]["armor"][1], {"name": "B", "name_es": "Be"})

    def test_an_existing_key_is_replaced_where_it_stands(self):
        doc = apply({"a": {"name": "N", "name_es": "old", "hp": 1}},
                    {"a/name_es": "new"})
        self.assertEqual(list(doc["a"].items()),
                         [("name", "N"), ("name_es", "new"), ("hp", 1)])

    def test_twice_is_the_same_as_once(self):
        src = {"a": {"name": "N", "desc": "D"}}
        tr = {"a/name_es": "Ne", "a/desc_es": "De"}
        once = dumps(apply(json.loads(json.dumps(src)), tr))
        self.assertEqual(dumps(apply(json.loads(once), tr)), once)


class ErrorTests(unittest.TestCase):
    def test_a_missing_parent_names_the_path(self):
        for path in ("nope/name_es", "a/0/name_es", "l/5/name_es", "l/1/name_es",
                     "a/name/x_es", "l/٠/name_es", "l/０/name_es",
                     "l/²/name_es"):
            with self.assertRaises(KeyError, msg=path) as ctx:
                apply({"a": {"name": "N"}, "l": [{}]}, {path: "x"})
            self.assertIn(path, str(ctx.exception))
            # The text view refuses the same paths the document view does.
            with self.assertRaises(KeyError, msg=path):
                place('{"a": {"name": "N"}, "l": [{"k": 1}]}\n', {path: "x"})

    def test_a_key_without_a_language_suffix_is_refused(self):
        for key in ("name", "_es", "es_", "name_en", "name_fr"):
            with self.assertRaises(KeyError):
                apply({"a": {}}, {f"a/{key}": "x"})

    def test_the_last_member_of_a_shared_line_is_placed_inline(self):
        # Only a member alone on its line gets a line of its own; the last
        # member of a shared line must not drag its line-mates along.
        text = '{\n  "a": {\n    "hp": 3, "name": "N",\n    "x": 1\n  }\n}\n'
        self.assertEqual(place(text, {"a/name_es": "Ne"}),
                         '{\n  "a": {\n    "hp": 3, "name": "N", "name_es": "Ne",\n'
                         '    "x": 1\n  }\n}\n')

    def test_the_self_check_refuses_a_repeated_key(self):
        from tools.localization.add_translations import _no_duplicates
        with self.assertRaises(RuntimeError):
            json.loads('{"a": 1, "a": 1}', object_pairs_hook=_no_duplicates)
        self.assertEqual(json.loads('{"a": 1, "b": {"a": 2}}',
                                    object_pairs_hook=_no_duplicates),
                         {"a": 1, "b": {"a": 2}})

    def test_place_parses_its_result_strictly(self):
        # A file already holding a duplicate `name_es`: a lax parse keeps
        # one copy and the edit looks right, the strict one refuses.
        text = '{"a": {"name": "N", "name_es": "x", "hp": 1, "name_es": "y"}}\n'
        with self.assertRaises(RuntimeError):
            place(text, {"a/name_es": "z"})

    def test_the_self_check_refuses_an_edit_that_means_something_else(self):
        # A duplicate key: json keeps the last "name", the text edit anchors
        # on the first, so the document the edit produces differs from the
        # one `apply` builds. Without the self-check this is written.
        text = '{"a": {"name": "N", "k": 1, "name": "M"}}\n'
        with self.assertRaises(RuntimeError):
            place(text, {"a/name_es": "Ne"})

    def test_a_translation_of_anything_but_text_is_refused(self):
        doc = {"o": {"name": "N", "damage": 5, "tags": ["a"], "flag": True,
                     "none": None, "values": {"common": 8}, "empty": {},
                     "deep": {"common": {"x": 8}}, "mixed": {"m": "a", "f": 5}}}
        for field in ("damage", "tags", "flag", "none", "values", "empty",
                      "deep", "mixed"):
            with self.assertRaises(KeyError, msg=field):
                apply(json.loads(json.dumps(doc)), {f"o/{field}_es": "x"})

    def test_a_translation_value_must_be_text(self):
        for value in (5, None, ["x"], {"m": 1}, {}, {"r": {"m": 1}},
                      {"m": "x", "f": 5}):
            with self.assertRaises(KeyError, msg=repr(value)):
                apply({"o": {"name": "N"}}, {"o/name_es": value})
        doc = apply({"p": {"rare": "Runed"}}, {"p_es": {"rare": {"m": "rúnico"}}})
        self.assertEqual(doc["p_es"], {"rare": {"m": "rúnico"}})

    def test_with_two_keys_in_the_language_it_goes_after_the_last(self):
        doc = apply({"b": {"name": "N", "name_es": "Ne", "desc": "D",
                           "desc_es": "De", "hp": 1}}, {"b/gender_es": "f"})
        self.assertEqual(list(doc["b"]),
                         ["name", "name_es", "desc", "desc_es", "gender_es", "hp"])

    def test_a_gameplay_field_can_never_be_overwritten(self):
        # Found by the UI-014.4.1 critic: `sword/projectile_count` passed as
        # a "translation" and set the count to 99 with exit 0.
        text = '{"sword": {"name": "Sword", "projectile_count": 1}}\n'
        with self.assertRaises(KeyError):
            place(text, {"sword/projectile_count": 99})


class LayoutTests(unittest.TestCase):
    """`place` edits the text, so a hand-formatted file keeps its layout."""

    def test_a_member_alone_on_its_line_gets_a_line_below(self):
        text = '{\n  "a": {\n    "name": "N",\n    "hp": 3\n  }\n}\n'
        self.assertEqual(place(text, {"a/name_es": "Ne"}),
                         '{\n  "a": {\n    "name": "N",\n    "name_es": "Ne",\n'
                         '    "hp": 3\n  }\n}\n')

    def test_the_last_member_passes_its_missing_comma_on(self):
        text = '{\n  "a": {\n    "hp": 3,\n    "name": "N"\n  }\n}\n'
        self.assertEqual(place(text, {"a/name_es": "Ne"}),
                         '{\n  "a": {\n    "hp": 3,\n    "name": "N",\n'
                         '    "name_es": "Ne"\n  }\n}\n')

    def test_a_member_sharing_its_line_gets_the_new_one_inline(self):
        text = ('{\n  "husk": {\n    "name": "Husk", "hp": 20,\n'
                '    "tags": ["a", "b"]\n  },\n'
                '  "c": {"name": "C", "desc": "D"}\n}\n')
        got = place(text, {"husk/name_es": "Casca", "c/desc_es": "De"})
        self.assertEqual(got, '{\n  "husk": {\n    "name": "Husk", "name_es": "Casca", '
                              '"hp": 20,\n    "tags": ["a", "b"]\n  },\n'
                              '  "c": {"name": "C", "desc": "D", "desc_es": "De"}\n}\n')

    def test_an_object_value_is_laid_out_under_its_key(self):
        text = '{\n  "prefixes": {\n    "rare": "Runed"\n  },\n  "tail": 1\n}\n'
        got = place(text, {"prefixes_es": {"rare": {"m": "rúnico"}}})
        self.assertEqual(got, '{\n  "prefixes": {\n    "rare": "Runed"\n  },\n'
                              '  "prefixes_es": {\n    "rare": {\n      "m": "rúnico"\n'
                              '    }\n  },\n  "tail": 1\n}\n')

    def test_replacing_keeps_the_layout_and_twice_is_once(self):
        text = '{"a": {"name": "N", "name_es": "old", "hp": 1}}\n'
        once = place(text, {"a/name_es": "new"})
        self.assertEqual(once, '{"a": {"name": "N", "name_es": "new", "hp": 1}}\n')
        self.assertEqual(place(once, {"a/name_es": "new"}), once)

    def test_space_before_a_comma_is_kept_valid(self):
        # Found by the UI-014.4.1 critic: the comma was skipped by length
        # from the value's end, so the space before it went and ",," came out.
        text = '{\n  "a": {\n    "name": "N" ,\n    "x": 1\n  }\n}\n'
        got = place(text, {"a/name_es": "Ne"})
        self.assertEqual(json.loads(got), {"a": {"name": "N", "name_es": "Ne", "x": 1}})

    def test_a_key_that_needs_escaping_is_written_escaped(self):
        got = place('{"a": {"name": "N"}}\n', {'a/na"me_es': "x"})
        self.assertEqual(json.loads(got)["a"]['na"me_es'], "x")

    def test_escapes_and_accents_survive(self):
        text = json.dumps({"a": {"name": 'Say "hi"', "hp": 1}}) + "\n"
        got = place(text, {"a/name_es": 'Di «hola» "ñ"'})
        self.assertEqual(json.loads(got)["a"]["name_es"], 'Di «hola» "ñ"')

    def test_on_every_data_file_the_tool_only_inserts(self):
        # Every text field of every real data file translated at once: the
        # original must survive as a subsequence of the result (nothing
        # deleted or reordered, whatever the file's layout), and `place`'s
        # own check -- the result means what `apply` says -- must hold.
        from tests.locale.test_data_text import text_pairs
        for path in sorted(DATA_DIR.rglob("*.json")):
            rel = path.relative_to(DATA_DIR).as_posix()
            if rel.startswith("locale/"):
                continue
            text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            # A field already translated is passed its own value back: a
            # replacement with the same text must leave those bytes alone.
            pairs = list(text_pairs(json.loads(text)))
            tr = {f"{p.lstrip('/')}_es": es if es is not None else f"ñ {en}"
                  for p, en, es in pairs}
            if not tr:
                continue
            with self.subTest(file=rel):
                got = place(text, tr)
                it = iter(got)
                self.assertTrue(all(c in it for c in text), "a character was lost")
                if all(es is not None for _, _, es in pairs):
                    self.assertEqual(got, text)
                else:
                    self.assertGreater(len(got), len(text))


class FileTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(a) for a in args])
        return code, out.getvalue() + err.getvalue()

    def test_write_then_check(self):
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        target.write_text(dumps({"a": {"name": "N"}}), encoding="utf-8")
        tr.write_text(json.dumps({"a/name_es": "Ne"}), encoding="utf-8")
        before = target.read_bytes()
        self.assertEqual(self.run_main(target, tr, "--check")[0], 1)
        self.assertEqual(target.read_bytes(), before)        # --check writes nothing
        self.assertEqual(self.run_main(target, tr)[0], 0)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["a"]["name_es"], "Ne")
        self.assertEqual(self.run_main(target, tr, "--check")[0], 0)

    def test_a_malformed_or_bom_file_is_an_error_not_a_traceback(self):
        tmp = Path(tempfile.mkdtemp())
        tr = tmp / "es.json"
        tr.write_text(json.dumps({"a/name_es": "Ne"}), encoding="utf-8")
        broken = tmp / "broken.json"
        broken.write_text('{"a": {"name": "N",}}', encoding="utf-8")
        code, msg = self.run_main(broken, tr)
        self.assertEqual(code, 2)
        self.assertIn("error:", msg)
        empty = tmp / "empty.json"
        empty.write_text('{"a": {}}\n', encoding="utf-8")
        self.assertEqual(self.run_main(empty, tr)[0], 2)
        bom = tmp / "bom.json"
        bom.write_bytes(b"\xef\xbb\xbf" + b'{"a": {"name": "N"}}\n')
        self.assertEqual(self.run_main(bom, tr)[0], 0)
        self.assertEqual(json.loads(bom.read_text(encoding="utf-8"))["a"]["name_es"], "Ne")

    def test_file_problems_are_errors_not_tracebacks(self):
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        target.write_text('{"a": {"name": "N"}}\n', encoding="utf-8")
        tr.write_text(json.dumps({"a/name_es": "Ne"}), encoding="utf-8")
        for args in ((tmp / "missing.json", tr), (target, tmp / "missing.json"),
                     (tmp, tr)):
            code, msg = self.run_main(*args)
            self.assertEqual(code, 2, args)
            self.assertIn("error:", msg)
        listed = tmp / "list.json"
        listed.write_text("[]", encoding="utf-8")
        code, msg = self.run_main(target, listed)
        self.assertEqual(code, 2)
        self.assertIn("JSON object", msg)

    def test_a_crlf_file_stays_crlf(self):
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        target.write_bytes(b'{\r\n  "a": {\r\n    "name": "N"\r\n  }\r\n}\r\n')
        tr.write_text(json.dumps({"a/name_es": "Ne", "p_es": {"m": "x"}}),
                      encoding="utf-8")
        self.assertEqual(self.run_main(target, tr)[0], 0)
        data = target.read_bytes()
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        self.assertEqual(json.loads(data)["a"]["name_es"], "Ne")
        self.assertEqual(self.run_main(target, tr, "--check")[0], 0)

    def test_text_that_cannot_be_encoded_leaves_the_file_whole(self):
        # Found by the UI-014.4.1 critic: the write opened (and truncated)
        # the target before encoding failed on a lone surrogate.
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        before = b'{"a": {"name": "N"}}\n'
        target.write_bytes(before)
        tr.write_text('{"a/name_es": "x\\ud83d"}', encoding="utf-8")
        code, msg = self.run_main(target, tr)
        self.assertEqual(code, 2)
        self.assertIn("error:", msg)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in tmp.iterdir()), ["es.json", "t.json"])

    def test_a_path_given_twice_is_refused(self):
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        before = b'{"a": {"name": "N"}}\n'
        target.write_bytes(before)
        tr.write_text('{"a/name_es": "Uno", "a/name_es": "Dos"}', encoding="utf-8")
        code, msg = self.run_main(target, tr)
        self.assertEqual(code, 2)
        self.assertIn("a/name_es", msg)
        self.assertEqual(target.read_bytes(), before)

    def test_a_failed_replace_leaves_no_temp_file(self):
        from unittest import mock
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        before = b'{"a": {"name": "N"}}\n'
        target.write_bytes(before)
        tr.write_text('{"a/name_es": "Ne"}', encoding="utf-8")
        with mock.patch("tools.localization.add_translations.os.replace",
                        side_effect=PermissionError("locked")):
            code, msg = self.run_main(target, tr)
        self.assertEqual(code, 2)
        self.assertIn("locked", msg)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in tmp.iterdir()), ["es.json", "t.json"])

    def test_a_bad_path_writes_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        target, tr = tmp / "t.json", tmp / "es.json"
        before = dumps({"a": {"name": "N"}})
        target.write_text(before, encoding="utf-8")
        tr.write_text(json.dumps({"a/name_es": "Ne", "zz/name_es": "Z"}),
                      encoding="utf-8")
        code, msg = self.run_main(target, tr)
        self.assertEqual(code, 2)
        self.assertIn("zz/name_es", msg)
        self.assertEqual(target.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
