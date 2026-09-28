# Localization — journal

**ID:** UI-014 · **System:** UI (+ SYS, PRG) · **Type:** feature ·
**Status:** in progress · **Branch:** claude/ui-014-localization (its own
worktree, cut from `main` at `58fdf16` — owner, 2026-09-25)

---

## UI-014 — Requirement (owner, 2026-09-25)

- **Objective:** Make the game playable in Spanish, with English staying the
  default.
- **Details:**
  - Spanish is the only language added.
  - Locale files follow the shape of the existing `data/` folder.
  - The current on-screen text is reviewed and moved into those files.
  - Descriptions of items and weapons get a Spanish version next to the
    English one, and the current texts are translated.
- **Constraint:**
  - Confirm and plan before building, under the DOC-001 rules.
  - English text and behaviour do not change.
  - Game data stays the one source for per-entity text
    (`data-driven-no-code-defaults`).

**Owner's answers (2026-09-25), recorded as decisions:**

- **UI-014.D1 — field naming.** A Spanish value sits next to the English one
  as `<field>_es`: `description_es`, `desc_es`, `name_es`, `trait_desc_es`,
  `trait_name_es`, `identity_es`. This was chosen over `spanish_desc` because
  one rule covers every field and a later language is just another suffix.
- **UI-014.D2 — data scope.** All player-facing data is translated, not only
  the descriptions: weapons, items, forges, blessings, heroes, meta upgrades,
  enemies, bosses and buffs. Without this, a Spanish card would show an English
  name above a Spanish description.
- **UI-014.D3 — depth.** Everything ships in this request: the locale files,
  the runtime lookup, the Options row, the UI strings moved to keys, and the
  tests.
- **UI-014.D4 — where.** A new worktree and branch.

## UI-014 — Confirmed reading

Survey of `main` at `58fdf16`.

### Data text (9 files, all loaded by `game/content.py`)

| file | player-facing fields | count |
|---|---|---|
| `weapons/weapons.json` | `name`, `description` | 9 weapons |
| `weapons/items.json` | `bases.*[].name`, `affixes.*.name`, `prefixes.*`, `unique_effects.*.{name,desc}` | 6 bases, 15 affixes, 5 prefixes, 3 uniques |
| `weapons/forges.json` | `name`, `identity`, `description`, `overrides.name` | 12 |
| `weapons/blessings.json` | `name`, `description` (templates with `{0}` / `{1}`) | 88 |
| `heroes/characters.json` | `name`, `identity`, `trait_name`, `trait_desc` | 3 |
| `heroes/meta_upgrades.json` | `name`, `desc` | 6 |
| `enemies/enemies.json`, `bosses.json` | `name` | 19 + 2 |
| `world/buildings.json` | `buffs.*.name` | 5 |

- Blessing values are filled in by `progression/blessings/catalog.py`
  (`format_value`, `describe`). The card title is `name` followed by a Roman
  numeral.
- A forged card joins its text as `f"{description} ({identity}.)"`
  (`progression/blessings/offer.py:137`).
- **Item descriptions** exist only as the three legendary `unique_effects`
  `desc` lines. The rest of an item's text is its name, built from its parts.
- Hero names stay as they are (UI-014.D5).

### Hardcoded UI text

About 330 on-screen strings live in Python, plus about 110 in the developer
tools.

- **Menus:**
  - `game/config.py`: `TITLE`, `MENU_INSTRUCTIONS`, `DIFFICULTY_LABELS`,
    `KEY_LAYOUT_LABELS`.
  - `game/display/window.py`: mode labels, "Custom WxH".
  - `menu_state.py`, `character_select_state.py`, `options_state.py`,
    `paused_state.py`, `meta_state.py`, `rankings_state.py`,
    `loading_state.py`.
- **Level up:** `ui/level_up.py`, `level_up_state.py` and
  `progression/blessings/offer.py`. The last one writes "New: …" and
  "… Weapon Grant", and `rarity.upper()` shows the raw id.
- **In the run:**
  - forge: `playing/core/locations.py`, `ui/forge_rail.py` (an English plural
    at line 120);
  - infusion: `playing/core/infusion.py` (`element.key.title()` and the raw
    element id inside sentences);
  - buffs: `playing/core/buffs.py`;
  - chest notice: `playing/core/chests.py:85-101` (English article, "a",
    ", … and");
  - boss warning: `visual/rendering.py:201` "{boss} APPROACHES";
  - tutorial words: `playing/core/hints.py`;
  - reaction labels: `combat/elements/tracking.py` `_LABELS`, with a
    `.title()` fallback;
  - key names: `ui/keycap.py` and `ui/controls_block.py`.
- **End of run:**
  - `end_banner_state.py`, `game_over_state.py` and `victory_state.py`;
  - `ui/end_screen.py`;
  - `ui/run_summary.py`, about 35 strings. Two of them are ids passed through
    `.title()`, and `BEST_FLAG` is drawn as it is.
- **TAB screen:**
  - `run_status_state.py`;
  - `ui/run_status/common.py`: `STAT_LABELS` (19), with a fallback built from
    the id;
  - `overview.py`, `build.py` and `blessings.py`. `build.py` shows raw effect
    and special ids.
- **Numbers:** `format_value` and other code write `+0.3s`, `x2.2`, `Lv 4`,
  `{} s`.
  - `meta_state.py:135` pads columns to a fixed width
    (`f"{name:<14} …"`). Longer Spanish words break that alignment.

### Other findings

- **Item names are stored in English in the save.**
  - `progression/items.py:148` builds `"{prefix} {base}{ of affix}"` and puts
    the string into the `Item`. It is then saved in `save.json` `stash` and
    `equipped`.
  - An item stores its base stat but not its base id. Each slot's two bases
    have different stats, so the base can be recovered from the slot and the
    stat.
  - "Runed Iron Plating of Vitality" cannot become Spanish word by word. The
    adjective follows the noun and agrees with its gender: "Placas de hierro
    rúnicas de Vitalidad".
- **Fonts:** both Fredoka and NunitoSans have á é í ó ú ñ ü (upper and
  lower case), ¿ ¡ « » and U+00A0. `mono()` is the system Consolas, used by
  the developer tools only.
  - **Correction (UI-014.4.1):** this was first "confirmed" with
    `Font.metrics`, which reports every character present, CJK and
    private-use included, so that check proved nothing.
  - The real check compares each character's render with the missing-glyph
    box (`tests/locale/test_data_text.py` `has_glyph`). It sees 中 as missing
    and every Spanish letter as present.
- **Text inside images:**
  - `assets/ui/end_banners/game_over.png` and `you_won.png`;
  - the logo `text_title.png`, a brand name that stays as it is.
- **Settings:**
  - The key goes in `game/save.py` `SaveData.settings`, checked in `_coerce`
    the same way `key_layout` is. The row goes in `options_state.py`.
  - The web build runs with `SAVE_ENABLED=False`, so there the language lasts
    only for the session (UI-014.D8).
- **Tests:** about 60 assertions check English text or labels. They stay
  valid because English is the default, and no test starts in Spanish unless
  it asks to.

## UI-014 — Decisions left open by the request (taken here, owner may overrule)

- **UI-014.D5 — proper names stay.** Hero names (Aegis, Kestrel, Nihil), the
  game title and the logo are not translated. Enemy, boss, weapon, forge,
  blessing and item names are translated, because they are descriptive words.
- **UI-014.D6 — developer tools stay in English.** This covers the dev menu,
  the dev overlays and `systems/debug_overlay.py`. They are for the owner,
  not the player.
- **UI-014.D7 — Spanish number style.** Decimal comma, a space before units,
  Spanish abbreviations:
  - `+0,3 s`, `x2,2`, `+25 %`, `Nv. 4`, `12 s`;
  - dates and the timer (`mm:ss`) are unchanged.
  - The space between a number and its unit is a **no-break space**
    (U+00A0), so the unit can never wrap onto a line of its own (added in
    UI-014.4.1). `ui.text.wrap` keeps U+00A0 inside a word, and the data test
    `style_problems` flags a decimal point, a unit touching its number, or
    any breaking space before `%` / `s`.

  All numbers go through one formatter in the locale module, so the style is
  set in one place.
- **UI-014.D8 — the language setting.** `settings["language"]` is `"en"` or
  `"es"`, with `"en"` as the default. An unknown value falls back to `"en"`.
  The switch takes effect as soon as it is made in Options, with no restart.
  The web build keeps it for the session only, as it does every other setting.
- **UI-014.D9 — item names are built when shown, not stored.**
  - The `Item` carries its parts: `base_id`, the first affix id and the
    rarity. Its name is built for the current language when drawn.
  - Old saves: `base_id` is recovered from the slot and the stat. The stored
    English `name` is left in the save, and is ignored when all the parts are
    known.
  - Spanish gender: each base gets `gender_es` (`m`/`f`) and each prefix
    gets `prefixes_es` `{m, f}`. The locale's `item.name` template sets the
    word order for each language.
- **UI-014.D10 — the end banners.** `game_over.png` and `you_won.png` are art
  with English words.
  - In Spanish, the banner state draws its text fallback ("FIN DE LA PARTIDA",
    "¡VICTORIA!") in the heading font, with the banner's gold and shadow.
  - It does not show the English art.
  - Spanish banner art can replace this later without any code change: the
    sprite key would take a `_es` variant.
- **UI-014.D11 — missing translations never crash.**
  - A missing `_es` field or locale key shows the English text.
  - The tests make sure nothing is missing, so the fallback exists only to
    protect a player from a hole in the data.

- **UI-014.D12 — templates take plain `{name}` fields only** (found by
  the UI-014.2 critic).
  - `{0}`, `{}`, `{n:.1f}`, `{n!r}` and `{a.b}` are rejected at load.
    Numbers reach a template already formatted by `num()`, which is what
    adds the decimal comma, so a format spec has no job to do. A spec or a
    conversion is also exactly where a translation could keep English's
    field names and still crash at draw time.
  - Keys are plain names; a dot in a key is rejected, because `{"a.b": ..}`
    would collide with `{"a": {"b": ..}}` once flattened.
  - This applies to `data/locale/` only. Blessing descriptions keep their
    positional `{0}` / `{1}`, filled by `catalog.describe`; UI-014.4 checks
    those separately.
- **UI-014.D13 — the glossary.** One Spanish term per game word, so the data,
  the UI and later tasks agree:

  | English | Spanish |
  |---|---|
  | run | partida |
  | Salvage (meta currency) | chatarra |
  | blessing | bendición |
  | forge / forged | forja / forjado |
  | HP | PV |
  | XP | EXP |
  | enemy, foe | enemigo |
  | knockback | empuje |
  | elite | élite |
  | hero | héroe |
  | the player ("you") | tú (informal) |

  Weapon names: Espada, Martillo, Dagas (plural: verbs agree, as in
  "Destrozan"), Arco, Vara mágica, Bomba, Anillo de brasas, Tótem sepulcral,
  Lobo espiritual.
- **UI-014.D14 — data is translated with a tool, not by hand.**
  `tools/localization/add_translations.py` places `<field>_es` keys from a
  flat `{"slash/path/field_es": value}` mapping. It edits the text in place,
  because several `data/` files are hand-formatted. It refuses anything that
  is not a translation of text, runs a strict self-check, and writes
  atomically. The mappings are working files; the data file is the only
  record of a translation.
- **UI-014.D15: a share or a length never reads as a bonus.** This was
  found by the UI-014.4.2 critics while filling the blessing cards. It fixes
  the English cards too.
  - A threshold (Executioner "below 35% health"), a fraction of a hit
    (Lacerate, Scorch, Split Arrow, Powder Keg) and a slow's potency
    (Chilling Bolts, a raw fraction the totem applies with no base) use the
    unsigned `chance` display, not `pct`.
  - A fixed duration (the 2 s bleed and burn, the 1.5 s slow) uses a new
    unsigned `duration` display in `format_value`, not `seconds`. Before,
    these read "below +35% health" and "for +2s".
  - The data display changed; no value and no combat path did.
  - `documentation/designs/weapon_blessing_forge_tables.md` had its 9
    generated rows re-synced by script, aligned with the generator's
    output. Regenerating the file would drop its
    hand-written sections.

## UI-014 — Plan

### Files

- **`data/locale/en.json` and `data/locale/es.json`.**
  - UI text keyed by dotted id and grouped by screen, like the rest of `data/`:
    `menu.*`, `options.*`, `hero_select.*`, `pause.*`, `level_up.*`,
    `run.*` (hints, chests, forge, infusion, buffs, boss), `summary.*`,
    `status.*`, `meta.*`, `rankings.*`, `end.*`, `keys.*`;
  - plus the name tables that code currently builds from ids: `element.*`,
    `reaction.*`, `rarity.*`, `stat.*`, `special.*`, `difficulty.*`,
    `key_layout.*`, `display_mode.*`;
  - plus `format.*` for the number styles and `item.name` for the word order.
  - Placeholders are named (`{gold}`, `{name}`) in both files.
  - Plurals are written out as separate `one` / `other` keys (for example
    `forge.needs.one` and `forge.needs.other`). No English "s" is added
    in code.
- **`data/*/*.json`:** a `<field>_es` next to every player-facing field in
  the 9 files above. Items also get `gender_es` on each base and
  `prefixes_es`.

### Code

- **`game/locale.py`**, one module:
  - `set_language` / `language`;
  - `t(key, **fields)`, with English fallback;
  - `text(entry, field)`, which reads `field_es` and falls back to `field`;
  - `plural(key, n, **fields)`;
  - `num(value, style)`, the one number formatter.

  Only this module imports the locale files, through `game/content.py`.
- **`game/content.py`:**
  - loads `data/locale/*.json`;
  - checks that every `es` key exists in `en` with the same placeholders.
    A bad key is reported and skipped, in the same fail-soft way invalid
    spawn data is handled.
- **Save and Options:** `settings["language"]` in `game/save.py`, and a
  Language row in `options_state.py` (English / Español). The language is set
  at boot from the save.
- **Readers:**
  - every data text read goes through `locale.text(...)`. That covers
    `catalog.py`, `offer.py`, the level-up cards, hero select, the TAB screen,
    the run summary, the sanctuary, the buff banner and the boss warning;
  - every hardcoded string goes through `locale.t(...)`;
  - text built from ids (`.title()`, `.upper()`, `replace('_', ' ')`) is
    replaced by name tables.
- **Layout:** `meta_state.py` gets columns measured in pixels, not a fixed
  character width. Single-line labels that can outgrow their space are checked
  by the width test below and shortened with `ellipsize` or wrapped where they
  fail.

### Tests

These go under `tests/locale/`, the gate lane.

- **Parity:** every `en` key has an `es` key, the placeholders match, and
  there are no empty values.
- **Data coverage:**
  - every player-facing field in the 9 files has a non-empty `_es`;
  - blessing templates keep the same `{0}` / `{1}` set as the English;
  - the fixed numbers inside descriptions (for example "30%" and "0.4s") match
    between the languages. Tests extract and compare them, so a translation
    cannot quietly change a number.
- **Runtime:** `t`, `text`, `plural` and `num` in both languages, the fallback
  on a missing key or field, and an unknown language.
- **Save:** `language` defaults to `en`, an invalid value is replaced, and the
  value round-trips.
- **Items:**
  - the Spanish name has the right word order and gender;
  - an old save without `base_id` recovers its base;
  - the English name is identical to today's for the same seed.
- **No stray English:**
  - an AST check fails when a text-drawing call in `ui/`, `game/states/` or
    `progression/` gets a string literal instead of a `t(...)` result;
  - the dev tools are exempt, per UI-014.D6.
- **Fit:** every screen is drawn in Spanish at the base resolution, and no
  label may overflow its box. Each overflow is reported with the screen and
  the key.
- **Existing tests:** run unchanged in English. One Spanish run of the
  screen tests confirms that nothing crashes.

### Screenshot

In Spanish: hero select, a level-up offer, the TAB screen, the run summary and
Options.

## UI-014 — Tasks

- [x] UI-014.1 — This journal and the index row.
- [x] UI-014.2 — The locale core:
  - `game/locale.py` and the loading and checks in `content.py`;
  - an empty `data/locale/en.json` and `es.json`;
  - the parity and runtime tests.
- [x] UI-014.3 — The language setting:
  - `settings["language"]`, the Options row and boot;
  - switching takes effect immediately;
  - the save tests.
- [x] UI-014.4 — Spanish data: a `_es` next to every player-facing field in
  the 9 files, with the data-coverage and number-match tests.
  - [x] UI-014.4.1 — `weapons.json` and `items.json` (the requested part), with
    `gender_es` and `prefixes_es`.
  - [x] UI-014.4.2 — `forges.json`, `blessings.json`.
  - [x] UI-014.4.3 — `characters.json`, `meta_upgrades.json`,
    `enemies.json`, `bosses.json`, `buildings.json`.
- [x] UI-014.5 — Data text read through `locale.text` in:
  - `catalog.py`, `offer.py` and the level-up cards;
  - hero select, the sanctuary and the buff banner;
  - the boss warning, the run summary and the TAB screen.
- [ ] UI-014.6 — Item names built when shown (UI-014.D9):
  - `base_id` on `Item`, and recovery for old saves;
  - names built from the locale template;
  - the item tests.
- [ ] UI-014.7 — UI strings to keys, part one: the menus, the hero select, the
  Options screen, the pause screen, the level-up screen, the loading screen and
  the rankings, plus the `config.py` label maps.
- [ ] UI-014.8 — UI strings to keys, part two, the run:
  - hints and keycaps;
  - chest notices, forge, infusion and buffs;
  - reaction labels and the boss warning;
  - end banners (UI-014.D10) and end screens.
- [ ] UI-014.9 — UI strings to keys, part three: the run summary, the TAB
  screen and the sanctuary. Name tables replace every id shown as text, and
  the sanctuary's columns are measured in pixels.
- [ ] UI-014.10 — Numbers through `locale.num` (UI-014.D7), with the
  `format_value` tests in both languages.
- [ ] UI-014.11 — The "no stray English" AST test and the fit test, and fixes
  for everything they flag.
- [ ] UI-014.12 — The full suite, the Spanish screenshots, the results, and
  the index row set to done.

## UI-014 — Results

### UI-014.2 — the locale core

- **`game/locale.py`:**
  - `LANGUAGES = ("en", "es")`, `set_language`, `language`;
  - `t`, `plural`, `text`, `num`, `placeholders`, `load`.
  - `t` never raises: an unfillable template falls back to English, then to
    the key, logged once per key.
  - `text` reads the English field first, so an entry that has only
    `name_es` fails in both languages, not first in English.
  - `num` uses a one-character `format.decimal`, and `.` otherwise.
  - `renderable(s)` defines drawable text: a str with a visible character,
    no NUL and no lone surrogate. Both the loader and `text` use it.
  - `t` and `plural` take `key` and `n` positional-only, so `{key}` and
    `{n}` work as template fields.
- **`game/content.py`:** `_flatten` and `_check_locale`. The loader is
  fail-soft: it logs and drops malformed templates, non-drawable leaves,
  dotted or empty keys, keys English lacks, placeholder mismatches, and any
  field that is not a plain `{name}` (UI-014.D12). It counts untranslated
  keys in one warning. `Content.locale` holds the flat tables.
- **`data/locale/en.json`, `es.json`:** only `format.decimal` (`.` / `,`)
  so far. The screens fill them in from UI-014.7 on. Both builds already ship
  the whole `data/` folder (`dist/desktop/DeathliteGame.spec:88`), so no
  packaging change was needed.
- **Tests:** `tests/locale/` (unit tier), 50 tests and 27 subtests.
  - `test_runtime.py`: language switching, fallback, log-once, escaped
    braces, plurals, data fields, drawable text, numbers.
  - `test_locale_files.py`: the shipped files load with no warning, have
    full key parity and matching placeholders, plurals in pairs, no Spanish
    entry copied from English, and every entry draws with Fredoka and
    NunitoSans. Also the loader's fail-soft cases.
- **Cold critic loop:** five rounds, each judged by a fresh critic with no
  memory of the others. The count of bug and should-fix findings went
  5 → 2 → 2 → 1 → 0, and round five was a PASS. Each fix has a test.
  - **Round 1:**
    - a `{n:d}` spec or a `!x` conversion passed the name check and crashed
      in Spanish;
    - positional `{0}` and `{}` could never be filled;
    - `{{`/`}}` rendered differently with and without fields;
    - a missing `format.decimal` printed the key into every number;
    - a dotted key silently collided with a nested one.
  - **Round 2:**
    - a non-string `_es` value (`5`, a list) reached `font.render`;
    - `TypeError` escaped `t()`.
  - **Round 3:**
    - a `{key}` field clashed with `t()`'s own `key` argument;
    - NUL and lone surrogates passed and made `Font.render` raise.
  - **Round 4:** strings made only of zero-width characters, a BOM or a soft
    hyphen passed; pygame raises "Text has zero width" on them.
  - **Round 5:** PASS. Every Unicode codepoint that `renderable` accepts,
    alone and after "A", draws with both shipped fonts with no failure. Two
    of its nits were taken: the draw test uses the shipped fonts, and an empty
    `_es` ("not translated yet") no longer logs.
  - **Left as they are:**
    - an empty `{n:}` spec, which formats like `{n}`;
    - nan/inf in `num`, which never reach the UI;
    - caller misuse, such as a negative `places` or an unhashable key;
    - a non-text English field, which UI-014.4's data-coverage test checks.
- **Also run** (216 passed with `tests/locale`): `tests/systems/test_save.py`,
  `tests/systems/test_fonts.py`,
  `tests/progression/test_blessings.py`,
  `tests/combat/test_elements_config.py`,
  `tests/spawn/test_data_integrity.py`, `tests/systems/test_assets.py`,
  `tests/flows/test_smoke.py` and `tests/flows/test_loading.py`: all pass.

### UI-014.3 — the language setting

- **Save (`game/save.py`):** `settings["language"]` defaults to `"en"`. On
  load, any value not in `locale.LANGUAGES` (`"fr"`, `"ES"`, `None`, `3`, a
  list) becomes `"en"`. A save written before UI-014 loads in English and
  keeps its other settings.
  - The list of languages is imported from `game.locale` rather than copied
    into the save module, as the key layouts are (`no-stale-duplicated-
    references`). `game.locale` imports nothing from the game at load time,
    so `import game.save` still pulls in neither pygame nor the content layer.
- **Game (`game/game.py`):** the language is set from the save at boot,
  before the state machine exists.
  - `set_language(code)` and `cycle_language(direction)` switch it and
    persist at once, as the key layout does.
  - The change shows on the next frame, because every screen draws its text
    each frame; nothing restarts.
  - With `SAVE_ENABLED` off (the web build), a new session starts in English
    (UI-014.D8).
- **Options (`game/states/options_state.py`):** a Language row directly
  after Tutorials, on the menu screen and on the in-run (pause) screen.
  - ENTER and a click step forward; Left and Right step either way, with wrap.
  - The value is each language's own name ("English", "Español"), read by
    `locale.name_of` from that language's file (`language.name`), so a player
    who cannot read the current language still finds theirs.
  - Eleven rows no longer fit the old step, so `_ROW_TOP, _ROW_STEP` went
    from 180, 68 to 170, 64. The last row sits at 810, clear of the hint at
    860.
  - The row labels stay English until UI-014.7.
- **Test isolation (found by the critic):** the language is process-global,
  and two tests (`tests/flows/test_lod.py`, `tests/flows/test_window.py`)
  booted `Game()` from the repo's own `save.json`. After a developer picked
  Español while playing, every later test in that process would have run in
  Spanish.
  - Both tests now use a temp save.
  - `tests/locale/test_isolation.py` fails on any `Game()` a test builds
    without a `save_path`, which covers the plain unittest runner too.
  - An autouse fixture in `tests/conftest.py` sets English before and after
    every test.
- **Tests:**
  - `test_save.py`: the default and round trip, and junk values.
  - `test_options.py` `LanguageRowTests` (8): the default at boot, the row's
    place on both screens, ENTER / Left / Right / click, persistence, set at
    boot from the save, the unsaved build starting in English, and each name
    drawn in its own language.
  - `test_runtime.py` `NameTests`.
  - `test_isolation.py`.
  - Two `test_options.py` tests changed with the layout: the skip walk now
    starts from Language, and the hint check counts eleven rows.
- **Runs:**
  - `tests/screens`, `tests/systems`, `tests/display`, `tests/flows` and
    `tests/locale`: 993 passed.
  - After the critic fixes, the touched modules: 166 passed.
  - `unittest discover -s tests/locale`: OK.
  - **Full default suite: 3503 passed, 0 failed, 0 skipped** (11 sweep
    deselected, 19 min 2 s). The conftest fixture now wraps every test.
- **Critic:** one cold pass, verdict PASS with one should-fix (the leak
  above) and two nits (the in-run row position was not asserted; a test
  class did not restore the tables). All three are fixed.
- **Screenshot:** the Options screen with Español selected. The row labels
  are still English, as planned.

### UI-014.4.1 — Spanish for weapons and items

- **Data:**
  - `data/weapons/weapons.json`: `name_es` and `description_es` on all 9
    weapons.
  - `data/weapons/items.json`:
    - `name_es` and `gender_es` on the 6 bases;
    - `name_es` on the 15 affixes ("de vitalidad", "de la caza");
    - `prefixes_es`, with each rarity in both genders (sencillo, refinado,
      rúnico, excelso, mítico);
    - `name_es` and `desc_es` on the 3 legendary effects.

  Nothing reads these fields yet: UI-014.5 and UI-014.6 do. So the game is
  unchanged in both languages until then.
- **Item names read correctly in every combination.** Each base's gender
  ties the rarity adjective to the item, not to the noun inside its name:
  "Sello de batalla rúnico", "Coraza de hierro rúnica de vitalidad",
  "Pulsera de viaje mítica de la caza". The critics built and read every
  base × rarity × allowed affix.
- **The tool:** `tools/localization/add_translations.py` (UI-014.D14).
  - The first version re-dumped the whole file. The round-trip test showed
    that only 3 of the 9 text-bearing files are in `json.dump` form, so it
    now edits the text:
    - a member alone on its line gets a new line at the same indent;
    - a member that shares a line gets the new pair inline.
  - A strict parse of the result, with no duplicate keys, must equal the
    document `apply()` builds from the original.
  - It refuses:
    - a suffix that is not a translated language;
    - a sibling or value that is not text (a number, list, flag, null, or an
      object of numbers such as `values`);
    - a path given twice.
  - It encodes the output before touching the target and writes through a
    temp file with an atomic replace. It keeps CRLF or LF as found.
- **`ui/text.py` `wrap`:** it no longer breaks at a no-break space (U+00A0,
  U+2007, U+202F). Everywhere else it breaks exactly where `str.split()` did,
  proved for every whitespace codepoint. It keeps a no-break space at a
  word's edge.
- **Tests:**
  - `tests/locale/test_data_text.py`:
    - the registry of `TRANSLATED` and `PENDING` files, where a new
      text-bearing file fails until it is placed;
    - a drawable `_es` for every field;
    - the same signed, percent and decimal numbers;
    - the same placeholders, with their format spec;
    - Spanish that differs from English;
    - a real glyph for every character, `prefixes_es` included;
    - the D7 number style;
    - no orphan `_es` key;
    - the item grammar;
    - each helper tested on its own data.
  - `tests/locale/test_add_translations.py`: placement, the layouts, errors,
    the self-check, file handling, and every real data file translated at
    once changing by insertion only.
  - `tests/screens/test_text.py`: the no-break space, the edges, and the full
    whitespace sweep.
  - `tests/locale/test_locale_files.py` now checks glyphs the same way.
  - Red checks, run by hand: a blank translation and a changed number each
    failed the coverage tests; the file was restored afterwards.
- **Full default suite: 3558 passed, 0 failed, 0 skipped** (11 sweep
  deselected, 17 min 47 s).
- **Cold critic loop:** nine rounds, each judged by a fresh critic. From
  round 7 the critics used mutation testing, up to 94 mutants. Round 9 was a
  PASS.
  - **Spanish fixed along the way:**
    - "Brazalete del viajero ascendente" read as "the rising traveller's
      bracelet", so the base became "Pulsera de viaje" (f).
    - ascendente → excelso/a, and fino/a ("thin") → refinado/a.
    - "Malla protectora … de protección" repeated its root, so the base
      became "Cota de malla".
    - The daggers' verb was made plural ("Destrozan").
    - retroceso → empuje, borra → arrasa, and the ward family was unified.
  - **Tool bugs found and fixed:**
    - a space before a comma produced `,,`;
    - `sword/projectile_count` was overwritten as if it were a translation;
    - a lone surrogate truncated the target to 0 bytes;
    - a key duplicated by an edit passed the self-check.
  - **Test gaps closed:**
    - `Font.metrics` saw no missing glyph (see the Fonts correction above);
    - the sign was not compared;
    - the style check had a false positive on words starting with "s", and
      missed "+25%" and runs of mixed spaces;
    - `--check` could have written the file unnoticed.
  - **Left as nits:** keys containing "/", an inline object value starting at
    column 0, numbers written as words, and only `%` and `s` known as units.

### UI-014.4.2 — Spanish for forges and blessings

- **Data:**
  - `data/weapons/forges.json`: `name_es`, `identity_es` and
    `description_es` on all 12 forges, and `overrides.name_es`, so a forged
    weapon carries its Spanish name.
  - `data/weapons/blessings.json`: `name_es` and `description_es` on all 88
    blessings.
  - Every filled card was read at level I and max in Spanish.
  - Counts use "{0} al número de …", so "+1" reads correctly: "+1 al número
    de lobos que corren contigo", not "+1 lobos más".
- **Forge code (`combat/weapons/forge.py`):**
  - `TEXT_OVERRIDES`, `TEXT_TRANSLATIONS` and `TEXT_OVERRIDE_KEYS` are the
    one list of forge text keys. The translated keys are built from
    `locale.LANGUAGES`. The parser, `apply_forge`, `forge_changes` and
    `tools/gen_weapon_tables.py` all read it.
  - `OVERRIDABLE` accepts `name_es` and `description_es`.
  - A translated override without its English field is refused at load.
  - `apply_forge` drops the base's translation of any text field the forge
    overrides. A forge with no translation then reads its own English name,
    never the base's "Espada".
- **Bug found by the critic and fixed:** `forge_changes` kept its own copy of
  the text keys, so the TAB screen would have drawn "name es  Espada ->
  Torbellino" for every forged weapon, in English too. Its test hard-coded
  the same copy and would have locked the bug in. Both now read
  `TEXT_OVERRIDE_KEYS`, and a regression test checks that no `_es` key comes
  back.
- **Card displays:** UI-014.D15 above.
- **For UI-014.5:** `ForgeDef` keeps only the English `name`, `identity`
  and `description`. The forge offer (`offer.py:137`), the TAB screen
  (`ui/run_status/build.py:117,236`) and the dev menu read them. UI-014.5
  has to carry the `_es` fields on `ForgeDef` or read through `locale.text`
  on the raw entry.
- **Tests:**
  - `tests/locale/test_data_text.py` now holds forges and blessings in
    `TRANSLATED`: 536 subtests in that module, covering drawable text,
    numbers, placeholders, glyphs and number style.
  - `tests/combat/test_forge.py`:
    - the Spanish forged name;
    - dropped inherited translations;
    - overridable keys;
    - offered name equals forged name;
    - a translation without its English field is refused.
  - `tests/combat/test_forge_changes.py`: no text key is reported as a
    change.
  - `tests/progression/test_blessings.py`: the `duration` display, and the
    six English cards that used to show a "+" where none belongs.
- **Checked by script:** `tools/gen_weapon_tables.py` output is identical
  with and without the `_es` keys.
- **Full default suite: 3565 passed, 0 failed, 0 skipped** (11 sweep
  deselected, 16 min 42 s). The run started before the last two data edits,
  the Chilling Bolts display and two Spanish strings. The tests that read
  them were rerun after: `tests/progression`, `tests/locale` and the forge
  tests, 317 passed.
- **Cold critic loop:** five rounds.
  - Round 1: the `forge_changes` bug; plural counts at "+1"; three broken
    sentences.
  - Round 2: Scorch "hasta 5 veces" (meaning), and the stale doc row.
  - Round 3: signed shares and lengths (D15); Split Arrow, Gold Rush and
    "Brazo escudo"; "vida" changed to "PV" per the glossary.
  - Round 4: the Chilling Bolts slow is a share too (added to D15), and four
    journal inaccuracies.
  - Round 5: PASS on the data, code, tests and doc tables. Every changed
    display was checked against the combat code that reads its key, and
    all 176 generated table rows appear verbatim in the design doc. Its
    only finding was this journal's round count. One taste fix was taken:
    Siege Bolt and Impale say "atraviesa {1} enemigos más".

### UI-014.4.3 — Spanish for heroes, meta upgrades, enemies, bosses, buffs

This task closes UI-014.4: every player-facing field in `data/` now has a
Spanish sibling, and `PENDING` in `tests/locale/test_data_text.py` is empty.

- **`heroes/characters.json`:**
  - `name_es` (unchanged, UI-014.D5), `identity_es`, `trait_name_es` and
    `trait_desc_es` for Aegis, Kestrel and Nihil.
  - The English never states a hero's gender, so the identity lines avoid
    gendered adjectives: "Velocidad y fragilidad", "Magia y fragilidad",
    "Premia no moverse".
  - Trait names match the blessings where the English does: Nihil's "Quick
    Cast" is "Lanzamiento rápido" in both places.
- **`heroes/meta_upgrades.json`:** the 6 Sanctuary upgrades. Constitución,
  Presteza, Fortuna, Erudito, Ferocidad and Chatarrero, with PV, EXP and
  chatarra as in the glossary.
- **`enemies/enemies.json`, `bosses.json`:** 19 enemy names and 2 bosses.
  - Names read as creatures and none repeat another's meaning: Cascarón,
    Escurridiza, Caparazón, Aguijón, Hondero, Hinchado, Zarpa recia,
    Devastador, Gnomo martillero, Giralanzas, Apicultor, Rencor, Pavesa,
    Cornasangre, Parpadeo, Roehuesos, Fauces de garfio, Invocamaldiciones,
    Muñeco de entrenamiento.
  - The bosses are El Hambre Primigenia and La Lanza Colmilluda. Both read
    well in the boss warning, which is not wired yet (UI-014.8).
- **`world/buildings.json`:** the 5 buff names. Imán and Celeridad match the
  blessings of the same English name; Turbo and Pinball stay.
- **Tests (`tests/locale/test_data_text.py`):**
  - all nine files are in `TRANSLATED`, and `PENDING` is empty;
  - `SAME_ON_PURPOSE` lists the five fields that stay identical on purpose
    (the three hero names, Turbo and Pinball), each by exact path, with a
    test that fails when an entry goes stale;
  - the copy check ignores case and edge spaces ("turbo " counts as a
    copy).
- **Loaders:** none of the five files' loaders rejects unknown keys. The
  loaders' suites pass (`tests/entities`, `tests/progression`,
  `tests/playing/test_buffs.py`, `tests/spawn/test_data_integrity.py`,
  hero select).
- **Full default suite: 3566 passed, 0 failed, 0 skipped** (11 sweep
  deselected, 15 min 50 s). The three taste edits from round 2 landed while
  it ran; `tests/locale` passed after them (106).
- **Cold critic loop:** two rounds.
  - Round 1: Nihil's line made the magic fragile, not the hero; "Cáscara"
    collided with "Caparazón"; Aegis's trait switched person.
  - Round 2: PASS. Three taste points taken ("Premia no moverse",
    "Cascarón", "de cada partida").

### UI-014.5 — the game reads its data text through `locale.text`

This is the first task where Spanish shows in the game. Every player-facing
read of a data text field goes through `game.locale.text`. Screen chrome
("Level Up - choose one", "Trait -", "Starts with:", stat labels) is
UI-014.7 to .9. Values ("+5%") are UI-014.10. Item names are UI-014.6.

- **The rule, since the language can change mid-run** (Options from the
  pause menu).
  - Text held for the process or the run is resolved when shown, never
    copied once.
  - `Weapon.name`, `Enemy.name` and `Boss.name` are properties over the
    definition they already keep. A forged weapon's merged definition
    carries the forge's translations.
  - `BlessingDef` and `ForgeDef` keep their data entry (`texts`). The
    player reads `display_name`, `describe`, `title` and the `display_*`
    properties. The English `name` / `identity` / `description` stay as
    identities: dev-menu order and logs.
  - The ledger keeps each killed type's definition and resolves its name
    when the list is read, not at the first kill.
  - The boss warning reads the live boss's name.
- **Built once, on purpose:**
  - The level-up, Forge and Monastery cards, at roll time. Those overlays
    cannot reach the pause menu, so a card never outlives a switch (the
    critics checked the state machine).
  - The end-of-run summary, when the run ends. The end screens cannot
    change the language.
  - Transient notices and the 7-second buff banner.
- **Surfaces wired:**
  - the level-up, Forge and grant cards (title, text, the weapon tag);
  - hero select (name, identity, trait, weapon);
  - the Sanctuary upgrades;
  - the TAB overview (hero, trait, unique item effects), build pane (card
    name, forge line, Forging header and text, synergies) and blessings
    pane (list row, owner, detail);
  - the buff banner, the boss warning, the HUD boss bar;
  - the run summary (character, trait, weapons, blessings, boss, kill and
    proc rows).
- **Fixes along the way:**
  - The TAB overview and the run summary showed the trait's id
    (`double_shot`, "Double_Shot"). They now show the data's `trait_name`,
    in English too.
  - The run summary's weapons column is measured over every language's
    name (`widest_weapon_name`), forge overrides included, so a switch
    never clips it.
- **Developer tools stay English (D6):** the dev menu reads English names
  through `_english_name`, at each of its six call sites.
- **Missing fields:**
  - Where the old code fell back to an id (a weapon, enemy, boss or trait
    without a name), it still does, and each fallback has a test.
  - Where it raised on hero select, the Sanctuary and the offer cards
    (`c["name"]`, `d["desc"]`), it still raises.
  - The TAB overview used to raise on a hero without a name. It now falls
    back to the hero's id, which is more lenient.
- **Tests:**
  - `tests/locale/test_data_readers.py`:
    - each reader in Spanish, and following a switch made after the object
      exists;
    - the offers;
    - the dev-menu helper;
    - the fallbacks;
    - a sweep that fails on any new raw read of a data text field
      (`d["name"]`, `.get` / `.pop` / `.setdefault`), with a counted,
      reasoned allowlist and its blind spots documented.
  - `tests/playing/test_spanish_run.py` (integration tier): one run built
    up in English, switched to Spanish, then checked on every surface above.
    Text is captured at the font or the draw helper, and every assertion
    uses text that differs between the languages.
- **Screenshots:** hero select, a level-up offer and the TAB build pane in
  Spanish.
- **Full default suite: 3603 passed, 0 failed, 0 skipped** (11 sweep
  deselected, 20 min 20 s). The round-5 nits, test-only edits, landed while
  it ran; `tests/locale` and `tests/playing/test_spanish_run.py` passed
  after them (144).
- **Cold critic loop:** five rounds. From round 3 the critics used mutation
  testing over every production hunk.
  - Round 1: the sweep let a repeated read through; several surfaces were
    working but unguarded.
  - Round 2: the width test passed against the English-only code.
  - Round 3: a boss or hero without `name` / `trait_name` crashed the
    summary (a third instance, in the ledger, was found by the new test);
    the blessings list row was unguarded.
  - Round 4: the six dev-menu call sites, a `.title()` revert and the forge
    card description survived their reverts.
  - Round 5: PASS. All 74 production change groups were reverted one at a
    time, and each revert is caught by a test. Its nits were taken:
    - a test for each of the four untested id fallbacks;
    - the shared-content test restores key order (`mock.patch.dict`);
    - the sweep docstring names `BUFF_FIELDS`;
    - this section's wording on missing fields.

