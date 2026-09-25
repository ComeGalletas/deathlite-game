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
- **Fonts:** `Font.metrics` confirms that both Fredoka and NunitoSans have
  á é í ó ú ñ ü (upper and lower case), ¿ ¡ and °. `mono()` is the system
  Consolas, used by the developer tools only.
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
- [ ] UI-014.2 — The locale core:
  - `game/locale.py` and the loading and checks in `content.py`;
  - an empty `data/locale/en.json` and `es.json`;
  - the parity and runtime tests.
- [ ] UI-014.3 — The language setting:
  - `settings["language"]`, the Options row and boot;
  - switching takes effect immediately;
  - the save tests.
- [ ] UI-014.4 — Spanish data: a `_es` next to every player-facing field in
  the 9 files, with the data-coverage and number-match tests.
  - [ ] UI-014.4.1 — `weapons.json` and `items.json` (the requested part), with
    `gender_es` and `prefixes_es`.
  - [ ] UI-014.4.2 — `forges.json`, `blessings.json`.
  - [ ] UI-014.4.3 — `characters.json`, `meta_upgrades.json`,
    `enemies.json`, `bosses.json`, `buildings.json`.
- [ ] UI-014.5 — Data text read through `locale.text` in:
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

_Not started._
