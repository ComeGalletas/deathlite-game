"""Write translated data fields into a `data/` JSON file (UI-014.4).

A translation sits beside its English field as `<field>_<lang>`
(`description_es` next to `description`, UI-014.D1). Hand-editing nine files
for that is slow and easy to get wrong, so the translations are written as a
flat mapping and this tool places them:

    python -m tools.localization.add_translations data/weapons/weapons.json es.json

`es.json` maps a slash path to the new key to its value:

    {"sword/name_es": "Espada",
     "bases/weapon/0/name_es": "Sello de batalla",
     "bases/weapon/0/gender_es": "m"}

**Where a key goes.** Right after its English sibling (`name_es` after
`name`). With no such sibling (`gender_es` has no `gender`), after the last
key already in that language, else after the object's last member. An
existing key has its value replaced where it stands, so running the tool
twice changes nothing.

**The file keeps its layout.** Several `data/` files are hand-formatted
(inline arrays, several keys to a line), so the file is edited as text, not
re-dumped:

* a member alone on its line gets the new member on a line of its own below
  it, at the same indent (an object value is laid out `indent=2` under it);
* a member sharing its line gets the new member inline, straight after it:
  `"name": "Husk", "name_es": "Casca", "hp": 20`.

Before anything is written, the edited text is parsed and must equal the
document `apply()` builds from the parsed original, key order included. That
proves the text edit means what the document view says; the placement rule
both share is covered by the tool's own tests. A mismatch, a malformed file,
a path whose parent does not exist, or an empty target object (nothing to
place a key after) is reported as `error:` with exit 2, and nothing is
written. `--check` writes nothing and exits 1 if the file would change.

Any key ending in `_<lang>` counts as that language's; `data/` has no English
key ending in `_es`, and `tests/locale/test_data_text.py` flags a `_es` key
with no English sibling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from json.decoder import scanstring
from pathlib import Path
from typing import Any

# --- the document view: what the file must mean afterwards ------------------


def _parent(doc: Any, parts: list[str], path: str) -> Any:
    node = doc
    for part in parts:
        if isinstance(node, list):
            if not (part.isascii() and part.isdigit()) or int(part) >= len(node):
                raise KeyError(f"{path}: no list item {part!r}")
            node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                raise KeyError(f"{path}: no key {part!r}")
            node = node[part]
        else:
            raise KeyError(f"{path}: {part!r} is inside a plain value")
    if not isinstance(node, dict):
        raise KeyError(f"{path}: the parent is not an object")
    return node


def _split(path: str) -> tuple[list[str], str, str]:
    """(parents, key, language). Only a key ending in a translated language
    (`locale.LANGUAGES` bar English) is accepted, so a path can never reach
    a gameplay field: `sword/projectile_count` is refused, not overwritten."""
    from game.locale import DEFAULT, LANGUAGES
    *parents, key = path.split("/")
    sibling, _, suffix = key.rpartition("_")
    if not sibling or suffix not in LANGUAGES or suffix == DEFAULT:
        langs = ", ".join(f"_{c}" for c in LANGUAGES if c != DEFAULT)
        raise KeyError(f"{path}: {key!r} does not end in a translated "
                       f"language ({langs})")
    return parents, key, suffix


def _is_text(value: Any) -> bool:
    """A string, or a non-empty object whose every value is text."""
    if isinstance(value, str):
        return True
    return (isinstance(value, dict) and bool(value)
            and all(_is_text(v) for v in value.values()))


def _anchor(keys: list[str], key: str, suffix: str) -> str | None:
    """The existing key the new `key` goes after (None: the object is empty)."""
    sibling = key.rpartition("_")[0]
    if sibling in keys:
        return sibling
    same = [k for k in keys if k.endswith(f"_{suffix}")]
    if same:
        return same[-1]
    return keys[-1] if keys else None


def apply(doc: Any, translations: dict[str, Any]) -> Any:
    """`doc` with every translation placed, by the rules in the module
    docstring. Raises KeyError (naming the path) when a parent is missing or
    a key has no language suffix."""
    for path, value in translations.items():
        parents, key, suffix = _split(path)
        parent = _parent(doc, parents, path)
        english = key.rpartition("_")[0]
        if english in parent and not _is_text(parent[english]):
            # Text (or an object of text, like `prefixes`) is translated; a
            # number, list, flag, null or object of numbers (`values`) is
            # gameplay, and its `_es` would be dead data nothing reads.
            raise KeyError(f"{path}: {english!r} is not text")
        if not _is_text(value):
            raise KeyError(f"{path}: the translation must be text "
                           "(or an object of text)")
        if key in parent:
            parent[key] = value
            continue
        after = _anchor(list(parent), key, suffix)
        out: dict = {}
        for k, v in parent.items():
            out[k] = v
            if k == after:
                out[key] = value
        if after is None:
            out[key] = value
        parent.clear()
        parent.update(out)
    return doc


def dumps(doc: Any) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --- the text view: where things are in the file ----------------------------


@dataclass
class _Member:
    key: str
    key_start: int                 # offset of the key's opening quote
    value_start: int
    value_end: int                 # one past the value's last character
    value: "_Node"


@dataclass
class _Node:
    kind: str                      # "object", "array" or "scalar"
    start: int
    end: int
    members: list[_Member] = field(default_factory=list)   # objects
    items: list["_Node"] = field(default_factory=list)     # arrays


_WS = re.compile(r"[ \t\r\n]*")
_SCALAR = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null")


class _Parser:
    """A JSON parser that keeps the character span of every value."""

    def __init__(self, text: str):
        self.text = text

    def ws(self, i: int) -> int:
        return _WS.match(self.text, i).end()

    def value(self, i: int) -> _Node:
        i = self.ws(i)
        c = self.text[i]
        if c == "{":
            return self.obj(i)
        if c == "[":
            return self.arr(i)
        if c == '"':
            _, end = scanstring(self.text, i + 1)
            return _Node("scalar", i, end)
        m = _SCALAR.match(self.text, i)
        if not m:
            raise ValueError(f"unexpected {c!r} at offset {i}")
        return _Node("scalar", i, m.end())

    def obj(self, i: int) -> _Node:
        node = _Node("object", i, i)
        i = self.ws(i + 1)
        if self.text[i] == "}":
            node.end = i + 1
            return node
        while True:
            key_start = i
            key, i = scanstring(self.text, i + 1)
            i = self.ws(i)
            assert self.text[i] == ":", f"':' expected at {i}"
            val = self.value(i + 1)
            node.members.append(_Member(key, key_start, val.start, val.end, val))
            i = self.ws(val.end)
            if self.text[i] == "}":
                node.end = i + 1
                return node
            assert self.text[i] == ",", f"',' expected at {i}"
            i = self.ws(i + 1)

    def arr(self, i: int) -> _Node:
        node = _Node("array", i, i)
        i = self.ws(i + 1)
        if self.text[i] == "]":
            node.end = i + 1
            return node
        while True:
            val = self.value(i)
            node.items.append(val)
            i = self.ws(val.end)
            if self.text[i] == "]":
                node.end = i + 1
                return node
            assert self.text[i] == ",", f"',' expected at {i}"
            i = self.ws(i + 1)


def _find(root: _Node, parts: list[str], path: str) -> _Node:
    node = root
    for part in parts:
        if (node.kind == "array" and part.isascii() and part.isdigit()
                and int(part) < len(node.items)):
            node = node.items[int(part)]
        elif node.kind == "object":
            match = [m for m in node.members if m.key == part]
            if not match:
                raise KeyError(f"{path}: no key {part!r}")
            node = match[-1].value
        else:
            raise KeyError(f"{path}: no item {part!r}")
    if node.kind != "object":
        raise KeyError(f"{path}: the parent is not an object")
    return node


def _render(value: Any, indent: str) -> str:
    """`value` as JSON, an object or array laid out `indent=2` under `indent`."""
    return json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)


def _edit(text: str, path: str, value: Any) -> str:
    """`text` with one translation placed (see the module docstring)."""
    parents, key, suffix = _split(path)
    obj = _find(_Parser(text).value(0), parents, path)
    existing = [m for m in obj.members if m.key == key]
    if existing:
        m = existing[-1]
        line_start = text.rfind("\n", 0, m.key_start) + 1
        indent = text[line_start:m.key_start]
        return (text[:m.value_start] + _render(value, indent if not indent.strip() else "")
                + text[m.value_end:])
    after = _anchor([m.key for m in obj.members], key, suffix)
    if after is None:
        raise KeyError(f"{path}: cannot place a key in an empty object")
    m = [x for x in obj.members if x.key == after][-1]
    line_start = text.rfind("\n", 0, m.key_start) + 1
    alone_before = not text[line_start:m.key_start].strip()
    rest = re.match(r"[ \t]*(,?)[ \t]*(\r?\n|$)", text[m.value_end:])
    name = json.dumps(key, ensure_ascii=False)
    if alone_before and rest:
        # Its own line: a new line below, at the same indent. The comma
        # moves with the line order -- the new member takes the old one's
        # trailing comma (or lack of it) and the old one gets a comma. With
        # a comma, everything up to it (spaces before it too) is replaced.
        indent = text[line_start:m.key_start]
        newline = rest.group(2) or "\n"
        comma = rest.group(1)
        skip = rest.end(1) if comma else 0
        line = f"{indent}{name}: {_render(value, indent)}{comma}"
        return (text[:m.value_end] + "," + newline + line
                + text[m.value_end + skip:])
    # Sharing its line: inline, straight after the member's value.
    return (text[:m.value_end] + f", {name}: {_render(value, '')}"
            + text[m.value_end:])


def place(text: str, translations: dict[str, Any]) -> str:
    """Place every translation into `text`, keeping its layout. Raises
    KeyError for a bad path, and RuntimeError when the edited text does not
    mean exactly what `apply()` says it should."""
    want = apply(json.loads(text), dict(translations))
    for path, value in translations.items():
        text = _edit(text, path, value)
    # `json.loads` keeps one of two duplicate keys without a word, which
    # would hide an edit that wrote a key twice; parse strictly instead.
    got = json.loads(text, object_pairs_hook=_no_duplicates)
    if json.dumps(got, ensure_ascii=False) != json.dumps(want, ensure_ascii=False):
        raise RuntimeError("the edited file does not match the intended document")
    return text


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    keys = [k for k, _ in pairs]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise RuntimeError(f"repeated key(s) {dupes}")
    return dict(pairs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", type=Path, help="the data/ JSON file to change")
    ap.add_argument("translations", type=Path,
                    help='JSON object {"slash/path/field_es": value}')
    ap.add_argument("--check", action="store_true",
                    help="write nothing; exit 1 if the file would change")
    args = ap.parse_args(argv)
    try:
        raw = args.target.read_bytes().decode("utf-8-sig")
        # Edited as LF and written back with the line ending it came with.
        newline = "\r\n" if "\r\n" in raw else "\n"
        before = raw.replace("\r\n", "\n")
        # Strict: a path given twice would otherwise keep only its last value.
        translations = json.loads(args.translations.read_text(encoding="utf-8-sig"),
                                  object_pairs_hook=_no_duplicates)
        if not isinstance(translations, dict):
            raise ValueError(f"{args.translations}: must hold a JSON object "
                             '{"slash/path/field_es": value}')
        after = place(before, translations)
        # Encoded before the file is touched: a lone surrogate in a
        # translation fails here, not halfway through a write that has
        # already truncated the target.
        payload = after.replace("\n", newline).encode("utf-8")
        changed = after != before
        if changed and not args.check:
            # A sibling temp file, then an atomic replace: the target is
            # either the old file or the new one, never a partial one.
            tmp = args.target.with_name(args.target.name + ".tmp")
            try:
                tmp.write_bytes(payload)
                os.replace(tmp, args.target)
            finally:
                tmp.unlink(missing_ok=True)     # gone after a replace, left after a failure
    except (OSError, KeyError, RuntimeError, ValueError, AssertionError,
            IndexError) as exc:
        # OSError: a missing file, a directory, a failed write. ValueError:
        # a malformed file (JSONDecodeError) or text that cannot be encoded
        # (UnicodeError). AssertionError / IndexError: a layout the parser
        # rejects.
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
        print(f"error: {msg or type(exc).__name__}", file=sys.stderr)
        return 2
    if args.check:
        print(f"{args.target}: {'would change' if changed else 'up to date'}")
        return 1 if changed else 0
    print(f"{args.target}: {len(translations)} field(s), "
          f"{'written' if changed else 'already up to date'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
