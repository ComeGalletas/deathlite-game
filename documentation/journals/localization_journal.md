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
- **UI-014.D16 — key legends stay, key words translate** (UI-014.8).
  - A keycap shows what the key prints: `ENTER`, `ESC`, `TAB`, `CTRL`,
    `ALT`, the arrows and the letters are the same in every language. The
    Spanish hint lines from UI-014.7 already say "ENTER" and "ESC", so a cap
    and the line beside it never disagree.
  - The words a player reads are translated: `SPACE` "ESPACIO", `SHIFT`
    "MAYÚS", `BKSP` "BORRAR", and `CLICK` "CLIC" (drawn only when the cursor
    art is missing).
  - A word too wide for its cap steps its font down (`keycap.WORD_ROOM`,
    75 % of the cap) instead of spilling over the bevel. English too: no key
    the game shows is that long, but "CAPS LOCK" or "PAGE DOWN" would now
    step down where it used to spill.
- **UI-014.D17 — when run text is read** (UI-014.8).
  - A notice (a chest's payout, the Forge's answer, an infusion) is composed
    when it is raised. It is gone in a few seconds, like a floating damage
    word, so a switch shows from the next one.
  - A Forge or Monastery overlay composes its rows, title and keys when it
    opens. It is modal and the pause menu cannot open over it, so nothing can
    change the language while it is up. The rail's heading is a key read
    when drawn, as the level-up hint already was.
  - English notices keep the weapon's name in lower case in mid-sentence
    ("The sword carries wind."), exactly as before. Spanish is phrased so the
    lower-case name needs no article or agreement: "Infusión de viento en
    espada.", "Reforja de espada: Mandoble.".
- **UI-014.D18 — the name tables** (UI-014.9).
  - Every id a screen printed as text reads a table: `stat.*`,
    `weapon_stat.*`, `forge_field.*`, `class.*`, `weapon_category.*`,
    `special.*`, `tag.*`, `targeting.*`, `slot.*`, through
    `locale.name(table, id, fallback)`. An id a table does not list (new
    data) shows as the id, never as the dotted key.
  - English is the text drawn before: the ids themselves where the screen
    printed ids ("melee  ·  cone", "cluster damage mult"), the old labels
    elsewhere. A test holds both.
  - An item's rarity tag is the initial of its `rarity.*` name, so a Spanish
    list reads `[P]` for "Poco común" beside cards that say "Poco común"
    (`progression.items.rarity_tag`). The English log form (`Item.short`)
    keeps the id's initial (UI-014.D6).
  - A Forging that clears a field (Fan of Blades removes the Daggers'
    special effect) printed Python's `+ None` on the Build pane; it prints
    `+ none` / `+ ninguno`. That one English row changes.
- **UI-014.D19 — the Spanish summary columns are narrow** (UI-014.9).
  - The Victory screen's four columns leave a stat label about 165 px beside
    its value. The Spanish stat names use the compact forms Spanish stat
    sheets use: "Regen. PV", "Vel. ataque", "Daño c. a c.", "Daño a dist.",
    "Prob. crítico", "Radio recogida". A test fits each one beside the
    widest value its kind prints.
  - The time row is "Tiempo" on a loss and on a win; the screen's title
    already says which ("Completada en" did not fit beside "récord").
  - A summary row whose label and value do not both fit now steps its value
    down, to 70 %, before the label trims -- when that leaves the label
    whole; otherwise the value keeps its size and the label trims, as
    before. A value wider than the whole column on its own (the four
    elements in Spanish) steps to the column's width, so it can never run
    past the column's edge.
  - The web profile (1280x720, scale 1) draws the summary's columns about
    120 px wide, where English already ran text past the columns and over
    its neighbours. Every row now stays in its column and alone, in both
    languages, three columns or four: a value that cannot keep its label
    steps to fit beside the record marker, then drops the marker and fits
    the column, and at the last trims; a label with no room for even "..."
    is left out rather than pushing the marker on; a ribbon title or a
    subheader wider than its space steps down (then trims -- a subheader's
    words, never its "(n)" count: "Objetos obt...  (14)"). At 1600x900
    English is unchanged by any of this (pixel comparison). This fixes English too: a run
    that set a kill record at three digits drew "Ki… best 845 (83/min)" and
    now draws "Kills best". Every other English row is unchanged, by a
    pixel comparison against the previous commit.
  - The Sanctuary's upgrade rows stay the one padded string they were
    (`f"{name:<14} {lvl}/{mx}   {cost:>4}"`), so English is the old line in
    any face, the web build's proportional one included; a longer name (a
    translation) pushes its own level on, never into it. Splitting the row
    into a name and a level cell drifted a pixel in faces with fractional
    advances (found by the critic). The equipped-slot lines align their
    item names after the widest slot name (they were space-padded in a
    proportional face and never lined up); that is the one Sanctuary change
    in English.
  - At the 1280x720 web profile, four weapon cards share the Build pane: a
    card title ("Lobo espiritual  Nv. 10") steps its font down rather than
    losing its level to the trim. The empty-synergy line is "ninguna aún  -
    una sinergia une dos armas", which fits there.

- **UI-014.D20 — the web profile's 900-row screens are not this task's**
  (UI-014.11). At the 1280x720 web profile (`config.apply_web_profile`,
  render scale 1) the title menu, the hero select, Options and the end
  screens are laid out for 900 rows: their lower buttons, hints and the
  menu's summary land below or onto each other past y 620-780, in English
  as much as in Spanish. That is the web build's layout, not the
  translation's, and it goes to a task of its own (started 2026-09-29 in a
  separate session, "Fit the 900-row screens to the 720 web canvas"; its
  ID is assigned there). The fit test lists these screens in `WEB_UNFIT`
  with the row their 900-row part starts at: below it a problem is exempt
  while Spanish has no more of them than English; above it every screen is
  held to the full rule. An entry whose screen fits fails the test, so the
  list goes when that task lands.
- **UI-014.D21 — a summary label is never trimmed** (UI-014.11; replaces
  the trimming half of D19). A label / value row takes, in order: both at
  the row size; the value alone stepped beside the whole label while it
  keeps 80 % of the row size; both at the largest size they share; the
  value alone stepped further; and when nothing fits, two lines -- the
  label and its record marker over the value, the value wrapping if it is
  wider than the column. The marker gives way before the label. Columns
  budget in lines (kills, hero stats, equipment), so a two-line row can
  never push the column past its bottom. In English at 1600 two rows of a
  wordy run change: "Elements" beside four elements is drawn (it was left
  out), and a kill record's "Kills best 3880 (129/min)" takes one shared
  size (the value had stepped to 70 % beside a 22 px label).

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
- [x] UI-014.6 — Item names built when shown (UI-014.D9):
  - `base_id` on `Item`, and recovery for old saves;
  - names built from the locale template;
  - the item tests.
- [x] UI-014.7 — UI strings to keys, part one: the menus, the hero select, the
  Options screen, the pause screen, the level-up screen, the loading screen and
  the rankings, plus the `config.py` label maps.
- [x] UI-014.8 — UI strings to keys, part two, the run:
  - hints and keycaps;
  - chest notices, forge, infusion and buffs;
  - reaction labels and the boss warning;
  - end banners (UI-014.D10) and end screens.
- [x] UI-014.9 — UI strings to keys, part three: the run summary, the TAB
  screen and the sanctuary. Name tables replace every id shown as text, and
  the sanctuary's columns are measured in pixels. Plan (2026-09-28):
  - name tables in the locale files for every id these screens print:
    `stat.*` (the 19 hero stats), `weapon_stat.*` (a card's numbers),
    `forge_field.*` (the 33 keys a Forging can change), `class.*`,
    `weapon_category.*`, `special.*`, `tag.*`, `targeting.*`, `slot.*`;
    English is the text drawn today, so English stays byte-identical;
  - `ui/run_summary.py` (about 35 strings, the rarity tag, the element list,
    the older-summary blessing fallback through the catalog);
  - `game/states/run_status_state.py` and `ui/run_status/` (tabs, hint, the
    three panes; `STAT_ROWS` loses its English labels, read through
    `stat_label` when drawn);
  - `game/states/meta_state.py`: the text, and pixel columns in place of
    `:<14` / `:<10` padding. The upgrade columns keep today's positions in
    English (a column is at least 14 characters of the mono face, wider when
    a translation needs it);
  - numbers keep their current formatting; UI-014.10 moves them to
    `locale.num`. Words in number templates ("Lv", "HP") move here;
  - tests: English byte-identity against the old strings, every screen drawn
    in Spanish with its text checked where drawn, the name tables complete
    for the data; screenshots; cold critic loop; full suite.
- [x] UI-014.10 — Numbers through `locale.num` (UI-014.D7), with the
  `format_value` tests in both languages. Plan (2026-09-29):
  - every player-facing number keeps the exact f-string it has (so English
    stays byte-identical by construction) and goes through the locale for
    its style: `locale.decimals` for the decimal mark, a new
    `format.thousands` for the damage figures ("1,234" / "1.234"), and new
    `unit.*` templates for what follows a number -- `unit.percent`
    ("{n}%" / "{n} %"), `unit.seconds` ("{n}s" / "{n} s"), `unit.mult`
    ("x{n}"), `unit.degrees` ("{n}°"), with the no-break space of D7;
  - the sites: `progression/blessings/catalog.format_value` (every card and
    data description), `ui/run_status/common` (`fmt_stat`, `fmt_mod`),
    `ui/run_status/build` (`_fmt`, the crit line), `ui/run_status/overview`
    (tag damage), `ui/run_summary` (damage, share, DPS);
    `options.percent` folds into `unit.percent`;
  - unchanged: the `mm:ss` timers (D7), whole numbers (HP, kills, gold,
    levels), the developer tools (D6);
  - tests: `format_value` and every site in both languages, English pinned
    to the old strings (and the English layout gate of UI-014.9), Spanish
    checked for the D7 style; the full suite; a cold critic loop.
- [x] UI-014.11 — The "no stray English" AST test and the fit test, and fixes
  for everything they flag. Plan (2026-09-29): (1) `tests/locale/test_no_stray_english.py`
  parses every module under `ui/`, `game/states/` (not the developer tools,
  D6), `progression/` and `game/display/`, and fails on any string literal
  with words that is not a docstring, a log or error message, a locale key,
  an identifier, or an entry of its allowlist -- each allowlist entry carries
  its reason (a key legend of D16, a class name, a step name nothing draws)
  and must still exist, so the list cannot go stale; (2)
  `tests/screens/test_fit.py` draws every screen in both languages at
  1600x900 and at the web profile's 1280x720 -- the menus, Options, the
  rankings, the Sanctuary, the run's HUD with its hints and notices, pause,
  a level-up offer, the Forge and the Monastery, the TAB panes, the end
  banner, Game Over and Victory -- and fails when a text leaves the screen,
  sits on another text, or Spanish trims more than English does there;
  (3) fixes for everything they flag.
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


### UI-014.6 — item names built when shown (UI-014.D9)

- **The model (`progression/items.py`):**
  - An `Item` saves `base_id`.
  - `Item.name` stays the English identity: built at generation by
    `stored_name`, saved in the stash, and used by logs and the dev menu.
  - The player reads `item_name(item, content)`: base, rarity word and first
    affix in the current language, joined by the locale's `item.name` /
    `item.name_affix` templates.
    - English is "{prefix} {base} {affix}".
    - Spanish is "{base} {prefix} {affix}", with the adjective from
      `prefixes_es[rarity][gender_es]`: "Pulsera de viaje refinada de
      vitalidad", "Amuleto de urraca refinado de presteza".
  - `item_label` puts the rarity tag in front. The tag letters are
    UI-014.9.
- **Old saves:**
  - An item without `base_id` finds its base by slot and base stat. A test
    holds the base stats unique per slot, so this is exact.
  - Its stored English name is left as it is and is not shown.
  - The critic walked an old `save.json` end to end: it loads, shows in
    Spanish and equips; the stash re-saves byte-identical. Nothing localized reaches
    the file.
- **Screens:**
  - the Sanctuary's stash list and equipped line;
  - the TAB overview's equipped items;
  - the run summary's dropped and equipped items.

  The summary's `equipment` rows became whole item dicts. `dropped_items`
  is what `Game._on_run_ended` saves, so the summary resolves names when
  drawn and adds nothing to it.
- **English is unchanged:** `item_name` equals the stored name for every
  slot × base × rarity × possible first affix (150 combinations), for a new
  item and for an old save. This is enumerated, not sampled.
- **The summary's fallback** covers only a dict that is not a whole item. An
  error inside `item_name` raises, as it does on the other screens, rather
  than hiding behind English (critic, round 1).
- **Tests:** `tests/progression/test_item_names.py`, plus the item screens
  in `tests/playing/test_spanish_run.py`.
- **Tests run:**
  - Full default suite: 3614 passed, 0 failed, 0 skipped (19 min 54 s).
    It started before the round-1 fixes.
  - After those fixes, the suites they reach (`tests/progression`,
    `tests/screens`, `tests/playing`, `tests/locale`, the save and dev-mode
    tests): 1296 passed.
- **Cold critic loop:**
  - Round 1: the English-equality test sampled 120 of the 150 combinations,
    and the summary's fallback swallowed real `item_name` errors. Both fixed,
    and `stored_name` was extracted so the test compares two code paths.
  - Round 2: a complete mutation pass, with 43 fine mutants and every hunk
    reverted. The only meaningful survivor was the run-end `equipment` rows,
    which had no test; now pinned. The Sanctuary equipped-line format is
    pinned too.
  - Round 3: PASS. Every production hunk's revert is caught, apart from four
    with no observable effect: the two journal hunks, the `short()`
    docstring and an import move. The accepted equivalent nits are listed in
    the round-2 report. A whole old-save item dict (no `base_id` key) now has
    its own summary test.

### UI-014.7 — the menu screens' own text

- **What moved to `data/locale/`:**
  - screens: the main menu (with its save line), the hero select (with the
    instructions block), Options, pause (with the Controls block), the
    level-up screen, loading and the rankings;
  - labels: the display-mode and resolution labels;
  - word tables: difficulty, key layout, rarity, blessing category and
    weapon class.

  97 keys in each language.
- **`config.py` no longer holds English:**
  - `DIFFICULTY_LABELS` and `KEY_LAYOUT_LABELS` are gone. A difficulty's
    name is `difficulty.<id>`.
  - `MENU_INSTRUCTIONS` holds row and note ids and the literal key names
    (WASD, TAB).
  - One source for each word (`no-stale-duplicated-references`).
- **The developer tools stay English (D6)** through `locale.english(key)`.
  `locale.has(key)` lets a screen show an id when there is no name for it
  (an unknown difficulty).
- **Word order:** the level-up card's category line was the tags joined word
  by word ("Melee Weapon Grant"). It is now one phrase per card kind, with
  its word order in the locale ("Arma cuerpo a cuerpo", "Poder del héroe",
  "Espada · Cobertura"). English equals the old formula for all 106 real
  offers (critic check) and for every kind × category × weapon the data
  allows (test).
- **Fit (`ui.text.fit_font`):** a label steps down in size, to at most 70 %,
  when its translation does not fit its slot. It is used only then, so
  English keeps its sizes. Screenshots found three overflows:
  - "Volumen de la música" into the slider;
  - the pause key-layout value into its label;
  - "Nueva arma: Tótem sepulcral" across the card.

  The Options mouse band was widened to cover the longest value.
- **Everything is read when drawn**, so a switch in Options shows on the
  next frame, the Options screen itself included. This covers the menu
  labels (a property), the level-up hint and the loading label.
- **Spanish choices:**
  - Nv. for Lv;
  - "Teclas" for the key-layout row, so the Controls block heading can keep
    "Controles";
  - "En ventana", "Sí" / "No";
  - U+00A0 before "s" and "%".

  "Normal" is the same word in both languages, and is listed as such.
- **Tests:** `tests/screens/test_spanish_menus.py`.
  - English byte-identity of the built strings.
  - Every screen drawn in Spanish, with each string checked where it is
    drawn.
  - The live switch from Options.
  - `fit_font` and each fitted slot.
  - The display labels.
  - The dev menu's English difficulty (in `test_spanish_run`).
  - Eight existing tests moved from the removed config maps to the locale.
- **Screenshots:** the menu, hero select, Options, pause, rankings and a
  level-up offer, in Spanish.
- **Open for the owner:** the TAB screen has three names across screens
  (Stat screen, Build, Run status), in English as well as Spanish.
  Unifying them is a wording decision, left as it is.
- **Tests run:**
  - Full default suite on the final production code: 3641 passed,
    0 failed, 0 skipped (20 min 17 s).
  - After the last test-only edits, the affected suites (`tests/screens`,
    `tests/locale`, the Spanish run, the controls, dev-mode and display
    tests): 893 passed.
  - An earlier full run had two transient failures in
    `tests/screens/test_level_up.py`. Both tests read the panel's source
    text, and the file was mid-edit during that run. Both pass on the final
    code.
- **Cold critic loop:** four rounds.
  - Round 1: a stale test assertion, font sizes written twice, and draw
    paths without a Spanish check. Also fixed: the cached level-up hint and
    loading label, the unknown-difficulty fallback (`locale.has`), the
    mouse band, "Teclas" and "En ventana".
  - Round 2: no production bugs, but nine surviving mutants, all gaps in
    the tests:
    - the pause title;
    - the pause key-layout value;
    - five Controls rows;
    - the On / Off order;
    - the band width;
    - the unknown difficulty;
    - `locale.english` restoring the language;
    - the fit cache's scale key;
    - the rankings subtitle.

    Plus two tests hard-coding the font sizes. All are now pinned.
  - Round 3: every mutant killed except `_LABEL_GAP = 0`, since the tests
    read the room from the same constant. It is now measured on the drawn
    gap against a literal 16 px.
  - Round 4: PASS. Across 54 hunk reverts and the fine mutants, the only
    survivors are equivalent: the dead config maps, `26` in place of its
    constant, "fit always", and the card-shape length guards. No state
    leaks from the new tests.

### UI-014.8 — the run's own text

- **Locale keys (76, `data/locale/en.json` and `es.json`):**
  - `hints.*` (Move / Attack / Aim), `keys.*` (the key words, UI-014.D16);
  - `chest.*` with separate `chest.rarity.*` and `potion.rarity.*` tables, because
    Spanish agrees the rarity with its noun ("cofre raro", "poción rara");
    `list.pair` and `list.separator` join the payout;
  - `forge.*` (title, keys, the reforged and requirements notices, the rail's
    heading and notes, `forge.needs` and `forge.rail.short` as plurals);
  - `element.*`, `infusion.*` (titles, hints, rail, card text, pace, notices);
  - `effect.<id>` for the 14 damage labels ("Sobretensión" for Overload, since
    "Sobrecarga" is the Overcharge blessing);
  - `boss.approaches`, `banner.loss` / `banner.win`, `end.*`.
- **English is byte-identical** everywhere it was reachable. The tests keep the old
  f-strings as the reference: every rarity, plural, element held or replaced, pace
  mode and window (the `.2g` text, `1e+02` included, through the new
  `locale.decimals`), unknown ids.
- **Code:**
  - `ui/keycap.py`: `_NAMES` (legends) and `_WORDS` (locale keys); a word too wide
    for a wide cap steps down (`WORD_ROOM`, 75 %), never a caller's own font.
  - `ui/forge_rail.py`: the heading is a key read when drawn; names, notes and the
    heading step down to fit, and are trimmed with `...` at the smallest step (five
    carriers in one note overflow even then, in English too).
  - `game/states/playing/core/infusion.py`: `element_name`; notes, card text and
    notices from the locale. `locations.py`: `_base_name` names the reforged weapon
    from its base definition. `chests.py`: `_rarity_word`.
  - `combat/elements/tracking.py`: the label table is gone; `label` reads
    `effect.<id>`.
  - `game/states/end_banner_state.py` (UI-014.D10): in a language with no rig of its
    own (`end_banner_loss_es`), the words are drawn in the heading face with a drop
    shadow for the English rig's play, which keeps the clock.
  - `ui/end_screen.py`: `Button.label` is a key, `Button.text` reads it.
- **Two fixes found on the way:**
  - The `fit_font` cache from UI-014.7 kept `Font` objects across
    `pygame.quit()` / `init()`, which `game/fonts.py` warns is an access violation.
    The keycaps made it reachable and `test_pause` crashed. `ui/text.py` now drops
    the cache from a `pygame.register_quit` hook, re-armed each cycle, and
    `cached_font` is the one place fonts are cached.
  - The Spanish Forge cards ran their description into the category line. A card
    description now steps down, a size at a time, to `_DESC_MIN_PX` (13 px) with the
    line height, until it fits the band (`LevelUpPanel.desc_block`). Across all 452
    blessing and forge descriptions, in both languages and both card widths, every
    one fits. At render scale 1 two English cards step down too, Whirlwind and
    Minefield on the narrow Forge card; at the smallest windows (scale 0.65-0.75)
    Greatsword does as well. Each had been drawing over its category line.
- **Tests:**
  - `tests/screens/test_spanish_run_text.py` (unit tier): keycaps, the fit cache, chest
    text, the rail, card descriptions, infusion text, effect labels, the end screens,
    the end banner.
  - `tests/playing/test_spanish_run_notices.py` (integration tier, one pinned run):
    hints, a chest's payout, the Forge (overlay, notices, requirements), the
    Monastery, the infusion notice, a buff building's title.
  - `test_spanish_run.py`: the boss warning's exact line in both languages.
  - `test_level_up.py`: the overflow test now steps down and fits; the clamp test
    uses a text too long even at the floor. `test_end_screen.py` fixtures use real
    keys. `test_controls_block.py` expects the drawn word.
- **Spanish details the critics caught:** "e" for "y" before an /i/ sound that
  is not a diphthong ("… una poción común e Imán II.", but "y Hielo"), chosen by
  `chests._I_SOUND` through `list.pair_i`; the no-break space in "cada 1,2 s";
  "ya tiene forja" (the rail names mostly masculine weapons); one hint style
  across the level-up overlay family ("Enter para forjar", "ESC para salir").
- **Screenshots** (Spanish): the hints, a chest notice, the Forge, the Monastery,
  the boss warning, the end banner, Game Over and Victory.
- **Tests run:**
  - Full default suite after the round 2 fixes: 3699 passed, 0 failed (17 min).
  - The touched suites after the round 4 fixes: 1860 passed, 0 failed.
  - The final full suite: 3717 passed, 0 failed, 0 skipped (16 min 36 s).
- **Cold critic loop:** eight rounds, each a fresh critic with a mutation sweep
  over every changed production and locale line.
  - Round 1: the rail and keycap fitting untested; the pace not byte-identical
    for large windows; the chest test changing the shared run; a mixed Spanish
    hint style; an unreachable banner guard.
  - Round 2: the card draw never checked to use the stepped font; the banner
    shadow scaled twice; the floor, the quit-hook guard, the cache's scale key
    and the rail's font roles unpinned; "ya forjada".
  - Round 3: the step sizes only checked against themselves; the loop and
    early-return boundaries; which English cards step.
  - Round 4: 44 survivors in rewritten lines (rail sizes and room, card width,
    antialias, the English banner, the Victory keys, the boss colour, the
    Spanish tables); the plain space in the pace.
  - Round 5: "y" before an /i/ sound; a duplicated width; the font cache
    untested.
  - Rounds 6 and 7: the y/e rule's boundaries (a later "i", each diphthong
    vowel, u and ú); the rail's room to the pixel; the keycap's 75 % room.
  - Round 8: PASS. The only survivors are equivalent (dead initialisations,
    loop starts that cannot fit, regex spellings of the same language).

### UI-014.9 — the run summary, the TAB screen and the Sanctuary

- **Locale keys (178):** `summary.*`, `status.*`, `meta.*`, and the name
  tables of UI-014.D18: `stat.*` (19), `weapon_stat.*` (10), `forge_field.*`
  (33), `class.*`, `weapon_category.*`, `special.*`, `tag.*`, `targeting.*`,
  `slot.*`. `locale.name(table, id, fallback)` reads them; an id a table does
  not list shows as the id.
- **Code:**
  - `ui/run_summary.py`: every label, header, "+n more" line and the record
    marker read the locale; the level cell is measured from
    `summary.level_value` ("Lv ##", "Nv. ##"); the element list reads
    `element.*`; an older summary names its blessings through the catalog;
    `_kv` steps a value down before its label trims (UI-014.D19).
  - `game/states/run_status_state.py`, `ui/run_status/`: the tabs, the hint
    and the three panes. `common.STAT_ROWS` is `(stat, kind)`, the label read
    by `stat_label` when drawn. The Build pane's class, category, special,
    number labels and Forging fields read their tables, a Forging's text
    values too (`_VALUE_TABLES`); a card title steps down at the web profile.
  - `game/states/meta_state.py`: the text; the upgrade rows stay the one
    padded string; the equipped-slot lines in a pixel column.
  - `progression/items.py`: `rarity_tag`, the translated rarity's initial,
    for every item list.
- **English:** every screen state of the TAB screen and of a current summary,
  in both layouts, renders byte-identical to UI-014.8 (a hand-run pixel
  comparison of 40 states against the previous commit). The changes are the
  deliberate ones of UI-014.D18 and D19, each confined to its rows.
- **Spanish choices:** "Arsenal" for the Build tab, "Resumen" for Overview;
  "Tiempo" for the time row; "sin bajas"; "Arma principal liberada"; the
  compact stat names of D19; "con forja", "sin forja", "puede ir a la
  Forja"; "Inventario" for the stash; "ninguna" under "Bendiciones (0)"
  (`summary.blessings_none`), "ninguno" under the other lists.
- **Tests:**
  - `tests/screens/test_spanish_status.py` (new, unit tier): the name tables
    complete for the data and English equal to what was drawn; every
    Spanish name pinned; the TAB panes, the summary and the Sanctuary drawn
    in both languages with their text checked where drawn; the Forging rows
    through their tables, the "+n more" lines, the scroll lines, a
    tag-damage item line; `_kv`'s geometry; the Sanctuary placement driven
    through `MetaState`; the fit of the Spanish at the Victory screen and
    the 1280x720 web profile (every text inside its area and alone, three
    columns or four, both languages).
  - `tests/screens/test_english_layout.py` with `english_layout.json` (new):
    404 English texts with their rects -- TAB panes full and empty, the
    summary in four, three and empty, the Sanctuary's upgrades -- captured
    from UI-014.8's code and compared on every run. It holds what the old
    strings drew, values and layout included; re-pin with `--write`.
  - Updated: `test_regen.py` (`STAT_ROWS`), `test_data_readers.py`,
    `test_locale_files.py` (the words that are the same in both languages),
    `test_spanish_run.py` and `test_item_names.py` (the `[P]` tag, the
    Spanish Build pane).
- **Tests run:**
  - Full default suite after the round-5 fixes: 3788 passed, 0 failed.
  - Final full suite: 3790 passed, 0 failed, 0 skipped (18 min 41 s).
  - A hand-run English pixel comparison of 40 screen states against
    UI-014.8, after each round: the TAB panes and the current summaries are
    identical; the differences are the D18/D19 rows.
- **Cold critic loop:** eight rounds, a fresh critic each, with mutation
  sweeps of about a thousand mutants over every changed line.
  - Round 1: the Spanish synergy line and card titles overflowing at 1280;
    the Sanctuary split into cells assuming a mono face; unpinned Spanish
    tables; untested templates, forge rows, scroll lines, `_kv` geometry.
  - Round 2: the split rows drifting a pixel in proportional faces (back to
    one padded string); "ninguno" under "Bendiciones"; `_kv` shrinking a
    value that freed nothing; weak test inputs.
  - Round 3: the Spanish four elements running off the Victory column; the
    Total's record marker, the empty lists and five bonus keys untested.
  - Round 4: at the 1280 web profile, a ribbon title, subheaders and a
    record marker overlapping (English overflowed there too).
  - Round 5: a subheader trim that ate its "(n)" count; the fit test
    measuring the column, not its area; the marker-drop steps unpinned.
  - Rounds 6 and 7: the label gap after a dropped marker (now
    `_LABEL_GAP`, pinned at its exact boundary); values and layout
    constants unasserted (the English layout gate).
  - Round 8: PASS. The survivors are equivalent (S() rounding, defaults
    unchanged from the old code, comments).
- **Left for UI-014.11:** the Run column trims "Kills" when a kill record,
  a four-digit count and a long rate all meet; English does too.

### UI-014.10 — numbers in the language's style

- **Locale:** `unit.percent`, `unit.seconds`, `unit.mult`, `unit.degrees`
  ("25%" / "25 %", "0.3s" / "0,3 s", with the no-break space of D7) and
  `format.thousands` ("," / "."). `options.percent` folded into
  `unit.percent`. The seconds unit is set in one place: the infusion rail,
  the TAB pace line and the menu's best line take the number with its unit
  (`infusion.pace.time` "every {s}", `menu.summary` "Best: {time}").
  `rankings.seconds` keeps its own English "95 s" (a plain space, as the
  rankings always read) and is pinned to `unit.seconds` in Spanish.
- **`game/locale.py`:** `grouped(value)` (the thousands mark), `unit(kind,
  n)`, and `_mark`, the one lookup of a one-character number mark: the
  current language, then English, then the default, so a malformed table
  never puts a word inside a number.
- **Sites:** `format_value` (every card and data description),
  `ui/run_status/common` (`fmt_stat`, `fmt_mod`, `_one_decimal`),
  `ui/run_status/build` (`_fmt`, the crit line, the pace),
  `ui/run_status/overview` (tag damage), `ui/run_summary` (damage, DPS,
  share). Each keeps the exact f-string it had; only its decimal mark,
  grouping and unit go through the locale, so English is byte-identical by
  construction -- checked over 26,565 values against the old functions, and
  by the English layout gate.
- **The share cell:** Spanish "100 %" is wider than "100%". The damage cell
  moves left by exactly that extra (`_damage_offset`), so Spanish keeps
  English's gap on every row and English stays at `_DAMAGE_X` at every
  render scale (a first version moved English a pixel at 0.8; tested now
  over 15 scales). `weapons_min_width` grows by the same extra.
- **Decision (for the owner to overrule):** "." is the Spanish thousands
  mark ("12.345"), the traditional style in Spain; D7 did not name one. RAE
  prefers no grouping under five digits and a thin space above.
- **Tests:** `tests/locale/test_numbers.py` (new): every `format_value`
  display in both languages, every Spanish card at every level in the D7
  style, the marks and their fallback, each unit reaching its call sites,
  the menu's best line, the stats, modifiers, weapon numbers and summary
  figures. `test_spanish_status.py`: the share cell's gap in both languages
  and at three scales, English's offset at 15 scales, the Spanish minimum
  width. Four UI-014.9 expectations moved to the D7 style.
- **Tests run:** the full default suite on the final code: 3806 passed, 0 failed,
  0 skipped (21 min 2 s).
- **Cold critic loop:** three rounds.
  - Round 1: the English step of the mark fallback untested (the English
    marks equal the defaults); the Spanish share crowding the damage
    figure (7 px of a 12 px gap); the seconds unit repeated in four
    templates.
  - Round 2: English moving a pixel at non-1.0 render scales; the total's
    share, the menu's best line, the Spanish minimum width and the unit
    routing untested; a test that could leave Spanish on.
  - Round 3: PASS. The one survivor (`+ [1.0]` to `+ [0.0]`) is equivalent:
    the extra width is the no-break space's, the same whatever number it
    follows (measured for 0-100 at 17 scales).

### UI-014.11 — no stray English, and every screen fits

- **`tests/locale/test_no_stray_english.py`:** parses every module under
  `ui/`, `game/states/`, `progression/` and `game/display/` (the developer
  tools left out, D6) and fails on a string literal with words that is not
  a docstring, a log call on a logger, an error, a locale key passed to
  `locale.*`, an id (no spaces, no "..."), an upper-snake constant, a type
  annotation, a `getattr` / library / registry name, or an `ALLOWED` entry
  with its reason (key legends of D16, roman numerals, loading steps
  nothing draws, the developer overlays). An `ALLOWED` entry nothing
  matches fails. What it cannot tell: a lone lowercase word ("paused")
  reads as an id. Nothing player-facing was left in English.
- **The fit harness** (`tests/screens/fit_harness.py`): every drawn text
  followed from its font through the panels, copies and scales it is
  composed on to where its ink lands; a text cut by a panel, off the
  screen, on another text (the same string only within a shadow's offset),
  over the edge of a button, card or ribbon, or on a button that carries
  its own label, is a problem; a text rendered and never placed is lost.
- **The scenes** (`tests/screens/fit_scenes.py`), 37 of them, drawn in both
  languages at 1600x900 and 1280x720: the menu over a played save, the hero
  select (and with every hero's main weapon unlocked), Options (and with a
  desktop's display rows), the rankings, the Sanctuary (upgrades, stash,
  every slot equipped), loading, pause, the TAB panes (a full and an empty
  run), Game Over, Victory and the end banners with their art, the HUD
  (the hints' two stages, a notice and the boss warning, the boss bar, a
  buff's name), a level-up offer (the wordiest of 200 rolls), the Forge
  (two weapons), the Monastery and a buff building's picker. The in-run
  data is the wordiest a run shows, measured in Spanish: four weapons, the
  longest blessing names and every other blessing, every enemy kind, every
  element.
- **`tests/screens/test_fit.py`:** at 1600 nothing is a problem in either
  language; at 1280 the same, but for the rows `WEB_UNFIT` exempts (D20);
  Spanish trims no more than English (generated item names aside); no text
  is lost; each screen draws in the language asked for.
  `tests/screens/test_fit_rules.py` pins what the scenes cannot reach: a
  label never trimmed at any column width, the shared size, the line
  budgets at every column height, the ribbon titles on the art's raised
  front, the Controls words, the cards and rail between the margins, the
  hero cards clear of their bevel.
- **Fixed**, all found by the fit test or its critics:
  - the run summary (D21): labels kept whole, two-line rows, line budgets
    for the kills, stats and equipment, the panel held above the surface's
    bottom, a narrower column inset in a narrow column, ribbon titles on
    the ribbon's raised front (measured from the art), the ribbon widened
    up to 8 px past a narrow column, "+1 more type" / "+1 tipo más";
  - the pause screen's Controls block: a word steps down, then takes two
    lines, never past the edge ("Ataque automático" at 1280);
  - the Forge, Monastery and buff-building pickers: the cards narrow and
    shift so the cards and rail stay between the margins (four cards ran
    off the screen at 1600 and at 1280); the keys hint names the cards'
    own keys ("1/2/3/4");
  - the hero cards: an unlocked hero's two main-weapon rows ran off
    Aegis's card in Spanish; the rows lose their gaps, then step down;
  - "+1 more synergy" and the other "+n more" lines have their singular.
- **Found and handed on:** the web profile's 900-row screens (D20); at
  the web profile the summary's rows change size row to row (D21's shared
  step and two-line rows), which that task can revisit with the layout.
- **Found, not fixed** (older art spacing, the same in both languages, out
  of this task): text on a 9-slice's inner border -- the Forge and
  Monastery rail's sub-lines ("sin portar", "not carried"), some card
  descriptions ("Porta fuego en 1 de cada 3", "Carries fire on 1 attack in
  3.") and a hero card's widest line. The harness checks a frame's outer
  rect, so it does not see the border.
- **Tests run:** full suite 3865 passed, 4747 subtests (20 min); the fit, rules, stray-English, English layout and Spanish suites on every round.
- **Cold critic loop:** five rounds.
  - Round 1: the kills column ran off 720 in Spanish; the ribbon fix did
    not match the art; the end screens were checked without their art; the
    boss bar was never drawn; lost text and same-text overlaps passed; the
    web exemption compared counts; seven surviving mutations.
  - Round 2: text past a card's art edge was invisible (the unlocked hero
    card); the web exemption still loose; the scenes not the wordiest; a
    15 px label beside a 22 px value; five surviving mutations.
  - Round 3: the buff building's four-card picker ran off both edges at
    1280; the menu's summary never drawn with a played save; the web
    exemption not recorded as a decision; seven surviving mutations.
  - Round 4: the 80 % rule and the web below-row comparison not pinned;
    the notice scene not the run's longest notice.
  - Round 5: PASS. Its notes tied off before the commit: the crossing
    check pinned inside `problems`, a dead branch removed, two docstrings
    that claimed more than their tests check. Two survivors left are
    equivalent (a fallback both destination forms reach alike, and the
    branch it confirmed dead).
