"""Player-facing text in the chosen language (UI-014).

Two sources, one rule each:

* **UI text** lives in `data/locale/<lang>.json`, nested by screen and read as
  dotted keys (`t("options.title")`). English is the reference file; a key
  missing from another language shows the English text.
* **Data text** stays in the entity's own JSON entry. A translation sits beside
  the English field as `<field>_<lang>` (`description_es` next to
  `description`, UI-014.D1) and `text(entry, "description")` picks it, falling
  back to the English field.

A missing translation never crashes the game (UI-014.D11): it shows English.
The tests in `tests/locale/` are what keep the files complete.

The tables are validated and flattened by `game/content.py`; this module reads
them from the content singleton on first use. Tests install their own with
`load()` and put the real ones back with `load(None)`.
"""
from __future__ import annotations

import logging
import unicodedata
from string import Formatter
from typing import Any, Mapping

log = logging.getLogger(__name__)

# Taxonomy: the languages the game ships, in the order the Options row cycles
# through them. The first is the reference every other file is checked against.
LANGUAGES: tuple[str, ...] = ("en", "es")
DEFAULT: str = LANGUAGES[0]

_language: str = DEFAULT
_tables: dict[str, dict[str, str]] | None = None
_reported: set[str] = set()


def placeholders(template: str) -> frozenset[str]:
    """The `{field}` names a template uses.

    Templates take plain named fields only: `{gold}`, never `{0}`, `{}`,
    `{n:.1f}`, `{n!r}` or `{a.b}`. Numbers reach a template already formatted
    by `num()` (which is what puts the decimal comma in), so a format spec has
    no job to do, and a spec or conversion is where a translation could crash
    at draw time while its field names still match English. Raises ValueError
    on anything else, and on a malformed template (an unmatched brace); the
    loader reports and drops such an entry."""
    names = set()
    for _, name, spec, conversion in Formatter().parse(template):
        if name is None:
            continue
        if not name.isidentifier() or spec or conversion:
            raise ValueError(f"only plain {{name}} fields are allowed, "
                             f"not {{{name}{'!' + conversion if conversion else ''}"
                             f"{':' + spec if spec else ''}}}")
        names.add(name)
    return frozenset(names)


def renderable(value: Any) -> bool:
    """True when `value` is text a font can draw: a str with at least one
    visible character, no NUL and no lone surrogate. `Font.render` raises on
    NUL and on surrogates (JSON allows both), and on a string of only
    zero-width, format or combining characters ("Text has zero width": a
    zero-width space, a BOM, a soft hyphen); a blank one would show nothing
    where English should be."""
    if not isinstance(value, str) or "\x00" in value:
        return False
    if not any(unicodedata.category(c)[0] not in "CZM" for c in value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def load(tables: Mapping[str, Mapping[str, str]] | None) -> None:
    """Install flattened tables `{lang: {dotted.key: text}}`. `None` goes back
    to reading them from the content singleton on next use."""
    global _tables
    _tables = None if tables is None else {k: dict(v) for k, v in tables.items()}
    _reported.clear()


def _table(lang: str) -> dict[str, str]:
    global _tables
    if _tables is None:
        from game.content import get_content
        _tables = get_content().locale
    return _tables.get(lang, {})


def set_language(code: Any) -> str:
    """Switch the language. An unknown code falls back to the default and is
    logged; the code actually used is returned so a caller can store it."""
    global _language
    if code not in LANGUAGES:
        log.warning("unknown language %r, using %r", code, DEFAULT)
        code = DEFAULT
    _language = code
    return code


def language() -> str:
    return _language


def _report(key: str, message: str, *args: Any) -> None:
    if key not in _reported:
        _reported.add(key)
        log.warning(message, *args)


def t(key: str, /, **fields: Any) -> str:
    """The text for `key` in the current language, English when this language
    lacks it, and the key itself (logged once) when neither has it.

    Never raises (UI-014.D11): a template that cannot be filled with `fields`
    falls back to the English one, then to the key, logged once. The loader
    already rejects what it can see; this covers a call site that passes the
    wrong fields."""
    candidates = [_table(_language).get(key)]
    if _language != DEFAULT:
        candidates.append(_table(DEFAULT).get(key))
    for template in candidates:
        if template is None:
            continue
        try:
            return template.format(**fields)
        except Exception as exc:        # the last line before font.render
            _report(key, "text key %r cannot be filled with %s: %r",
                    key, sorted(fields), exc)
    if all(c is None for c in candidates):
        _report(key, "missing text key %r", key)
    return str(key)


def plural(key: str, n: int, /, **fields: Any) -> str:
    """`key.one` when `n` is 1, else `key.other`, with `n` passed to the
    template. English and Spanish share this rule; a language that needs more
    forms would add them here, not at the call sites. The count always
    fills `{n}`; a caller's own `n=` field is overridden by it."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", **{**fields, "n": n})


def text(entry: Mapping[str, Any], field: str) -> str:
    """A data entry's text in the current language: `field_<lang>` when it is
    drawable text (`renderable`), else the English `field`. A missing English
    field raises
    KeyError, as any other missing required data does, in every language --
    so a Spanish-only entry fails in a Spanish run too, not first in English."""
    base = entry[field]
    if _language != DEFAULT:
        key = f"{field}_{_language}"
        value = entry.get(key)
        if renderable(value):
            return value
        if value not in (None, ""):          # "" is "not translated yet"
            # A typo (a number, a list, a blank) must not reach font.render.
            _report(f"{key}={value!r}", "data %s is not text (%r), shown in %s",
                    key, value, DEFAULT)
    return base


def num(value: float, places: int | None = None, sign: bool = False) -> str:
    """A number in the current language's style: the decimal separator comes
    from `format.decimal` (`.` when no table has it). `places=None` prints up
    to six decimals with trailing zeros dropped (`0.3`, `2`, `12.5`); an int
    `places` fixes the decimals. `sign` adds `+` to a value that is not
    negative."""
    if places is None:
        body = f"{value:.6f}".rstrip("0").rstrip(".")
    else:
        body = f"{value:.{places}f}"
    if body.startswith("-") and not body.strip("-0."):
        body = body[1:]                      # -0.0 and -0.04 at 1 place -> 0
    if sign and not body.startswith("-"):
        body = "+" + body
    decimal = next((d for d in (_table(_language).get("format.decimal"),
                                _table(DEFAULT).get("format.decimal"))
                    if isinstance(d, str) and len(d) == 1), ".")
    return body.replace(".", decimal) if decimal != "." else body
