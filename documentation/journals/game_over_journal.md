# Game over screen — execution journal

**Legacy ID:** UI-001 · **Systems:** UI · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-12)

A game over screen with a résumé of the run:

- the items acquired,
- gold,
- time elapsed,
- number of kills per enemy type,
- weapons and blessings with their levels,
- the total damage done in the run per weapon, with a DPS figure.

Confirm and propose, then build, and keep the record here.

---

## Confirmed reading

Each item, read against what the run already tracks (`PlayingState.stats`,
`game/states/playing/state.py:214`), and what the screen will show for it:

| Requirement | What exists today | What the screen shows |
|---|---|---|
| Items acquired | `stats["dropped_items"]` — every item the run dropped (elite drops, the Merchant's purchase, the boss reward), each a serialised `Item` with name, rarity, slot and level. They are banked to the stash at run end (`Game._on_run_ended`). | An "Items" list: rarity letter and name, capped with "+n more". |
| Gold | `stats["gold"]` is the in-run Merchant gold (earned per kill, spent at the Merchant, never banked). `stats["currency"]` is the Salvage banked to the save. They are different currencies. | Both, labelled: **Gold** (what the run ended with) and **Salvage** (banked). |
| Time elapsed | `stats["time"]`, the run clock in seconds. | `mm:ss`, as the HUD clock shows it. |
| Kills per enemy type | Only the total `stats["kills"]`. The dead enemy is in hand at the count (`CombatResolver.cull_dead_enemies`) with its `enemy_id` and display `name`; the boss dies through `_on_boss_killed` and is not in the total. | A per-type table, biggest first, with the boss as its own row and a total row that is the sum of the table. |
| Weapons with levels | `summary["weapons"] = [(name, level)]`, built at run end. | Kept, shown in the damage table as "Name  Lv n". |
| Blessings with levels | `player.blessings` is `{blessing_id: level}`; the catalog (`blessing_lib.by_id[id].name`) has the display names. | A "Blessings" list of `name  Lv n`. |
| Damage per weapon, with DPS | Only the run total `stats["damage_dealt"]`. The per-weapon split exists **only** on the training dummy (`DpsMeter`, armed on one enemy). Every damage path already names its source: projectile hits (`source=proj.weapon_id`), burn ticks (the status keeps the weapon that applied it), blessing procs (`fire_nova`), summons (their bolts carry the weapon id). | A table: weapon, level, damage, share, DPS. DPS is damage over the time the weapon was **held**, not over the whole run — a weapon picked up at minute eight is not charged for the seven minutes it did not exist. Blessing procs (a source that is not a weapon) get their own rows under the weapons, over the whole run. A total row gives the run's damage and run DPS. |

Two things the requirement does not say that are decided here:

- **Where the per-weapon numbers come from.** The `DpsMeter` is the wrong
  tool: it is armed on one enemy and disarmed with it. The run needs a
  ledger that hears every hit on every enemy for the whole run. `Enemy._absorb`
  is already "the one place damage lands" (it is why the dummy cannot be
  bypassed), so the ledger hooks there — one attribute on every enemy, set by
  the spawner — and the `Boss` gets the same seam instead of subtracting HP by
  hand. Nothing in the combat loop has to remember to report.
- **The screen is mouse-driven like every other menu** (owner's rule of
  2026-09-04): three wide Tiny Swords buttons — New run, Sanctuary, Main menu —
  hovered and clicked through `ui.mouse.MouseNav`; the keys the old stub
  advertised (ENTER, S, ESC) keep working, and Left/Right move the cursor.

---

## Proposal

### 1. `RunLedger` — `game/states/playing/run_ledger.py`

One object per run, created next to `stats`. It keeps:

- `damage[source]` — damage landed per source id (a weapon id, a blessing proc
  id, or `"other"` for an unnamed path). The villager source is dropped, as
  the meter drops it: a lancer stabbing a husk is not the hero's damage.
- `held_since[weapon_id]` — the run clock when the hero first held each
  weapon. Tracked by the update loop looking at `player.weapons` each frame
  (three dictionary look-ups), so no weapon-granting site has to report.
- `first_hit[source]` — the clock at a source's first damage; the fallback
  span for a source that is not a held weapon.
- `kills[enemy_id]` and `kill_names[enemy_id]` — the per-type count and the
  display name, boss included.

Readouts: `weapon_rows(weapons)` (id, name, level, damage, share, dps),
`other_rows(names)` for the non-weapon sources, `kill_rows()`, `total`.

### 2. The hook

- `Enemy.ledger = None`; `_absorb` calls `ledger.record(dealt, source)` after
  the meter's `damage_sink`. The two never conflict: the sink is the dummy's,
  the ledger is the run's.
- `Boss` gains the same `_absorb`, used by `take_damage` and `_status_damage`,
  so boss damage is attributed too (today `Boss.take_damage` ignores
  `source`).
- `Spawner.make_enemy`, `Spawner.wake` and the boss spawn set the attribute.
- `cull_dead_enemies` and `_on_boss_killed` call `ledger.kill(enemy)`.

### 3. The summary

`_end_run` adds to the dict it already builds: `weapon_rows`, `other_rows`,
`kill_rows`, `blessing_rows` (name, level), `damage_by_source`. Nothing
existing is renamed — the save's `record_best`, the rankings and the
victory screen read the same keys they read now.

### 4. The screen — `game/states/game_over_state.py` + `ui/run_summary.py`

The readout is one panel class in `ui/run_summary.py` (one module per
concern), so the victory screen can adopt it in one line later. Layout at
1600×900:

- **Title** "You Died" (NunitoSans, red) with the hero, difficulty and seed
  under it.
- **Three columns**, each headed by a Tiny Swords ribbon (blue / yellow /
  red, dark text on the light art):
  - *Run* — survived, level, kills, gold, salvage, then the items acquired.
  - *Enemies slain* — the per-type table with its total, then the blessings
    with levels.
  - *Damage by weapon* — weapon, level, damage, share, DPS; the proc rows;
    the total row.
- **Three wide buttons** at the bottom: New run (ENTER), Sanctuary (S),
  Main menu (ESC). Mouse hover selects, click activates.

The backdrop colour and the three exit keys stay as the existing tests pin
them (`tests/rendering/test_game_over.py`).

### 5. Tests

- `tests/combat/test_run_ledger.py` (unit) — attribution, the villager drop,
  held-span vs. first-hit DPS, kill rows with a boss duck-type, the
  "other" rows.
- `tests/rendering/test_game_over.py` — the new keys draw, the buttons take a
  click, the cursor keys move the selection, the legacy stats shape still
  draws.
- `tests/core/test_smoke.py` — after the real run's kills: the ledger's total
  equals `stats["damage_dealt"]` (every path that counts damage is also
  attributed), and a death lands on a `GameOverState` whose stats carry the
  rows.

### Progress

- [x] 1. ledger — `game/states/playing/run_ledger.py`
- [x] 2. hook — `Enemy.ledger` in `_absorb`; `Boss._absorb` (new, used by
      `take_damage` and `_status_damage`); the spawner's `make_enemy`, `wake`
      and `spawn_boss` set it; `cull_dead_enemies` and `_on_boss_killed`
      count the kill
- [x] 3. summary keys — `weapon_rows`, `other_rows`, `kill_rows`,
      `blessing_rows`, `damage_by_source` in `_end_run`
- [x] 4. screen — `ui/run_summary.py` (the panel), `game/states/game_over_state.py`
- [x] 5. tests green — see below
- [x] screenshot delivered

---

## Built (2026-09-12)

### What changed, file by file

| File | Change |
|---|---|
| `game/states/playing/run_ledger.py` | new: `RunLedger` — damage per source, held-since per weapon, first-hit per source, kills per type with names; `weapon_rows`, `other_rows`, `kill_rows`, `dps_of`, `span_of` |
| `entities/enemy.py` | `ledger` attribute; `_absorb` reports to it after the meter's sink |
| `entities/boss.py` | `ledger` attribute; a `_absorb` that is now the one place boss HP comes off, so boss damage is attributed and a burn tick is no longer subtracted by hand |
| `game/states/playing/spawning.py` | the three construction sites hand the run's ledger over |
| `game/states/playing/combat.py` | `cull_dead_enemies` counts the kill by type |
| `game/states/playing/state.py` | the ledger is built with `stats`; the update loop sets its clock and tracks the held weapons; `_on_boss_killed` counts the boss; `_end_run` adds the rows |
| `game/states/playing/dps_meter.py` | comment only: `VILLAGER` now has two readers |
| `ui/run_summary.py` | new: `RunSummaryPanel`, the three ribboned columns |
| `game/states/game_over_state.py` | rewritten around the panel and three mouse-driven buttons |
| `tests/combat/test_run_ledger.py` | new, unit: 19 tests |
| `tests/rendering/test_game_over.py` | 12 new tests (summary shapes, overflow, mouse, cursor keys); one renamed |
| `tests/core/test_smoke.py` | the ledger total equals `damage_dealt` after the real kills; a new death test lands on the summary with the rows |

### Decisions made while building

- **Per-weapon DPS does not sum to the run DPS, on purpose.** In the
  screenshot run the Ember Ring reads 51.9 over the time it was held and the
  total row 83.6 over the whole run; the four weapon figures add up to more
  than the total because each is over its own, shorter, span. The table's
  *share* column is what adds to 100 %.
- **The ledger's total is the run's `damage_dealt`.** The smoke test pins
  them equal after the real kills, so a new damage path that counts toward
  one but not the other fails loudly. The villager's hits are in neither.
- **The screen keeps the old keys and tolerates the old shape.** `weapons`
  as `[(name, level)]` and `blessings` as `{id: level}` still draw (dashes
  in the damage columns); the existing tests that feed that shape pass
  unchanged. The rankings, the save's `record_best` and the victory screen
  read what they always did.
- **Lists are cut, not overflowed.** Ten items, eight kill rows, six
  blessings, four proc rows, each followed by "+n more". Nine kill rows plus
  a cut blessing list ran 8 px into the button strip; a test now paints
  twenty of everything and asserts the strip between the columns and the
  buttons stays dark.
- **Rarity colours on the dark backdrop are local to the panel.**
  `config.RARITY_COLOURS` are the level-up cards' inks for the light button
  art and vanish on this ground.
- **The boss now counts as a kill row but not in `stats["kills"]`**, which
  the rankings compare across runs. The table's total is the sum of its
  rows, so it can read one higher than the "Kills" line after a victory.
  The game-over screen never follows a boss kill, so the two never differ
  on it; the victory screen does not draw the table yet.

### Test results

The three touched modules, then the whole default suite:

```
python -m pytest tests/combat/test_run_ledger.py tests/rendering/test_game_over.py tests/core/test_smoke.py -q
44 passed in 15.17s
```

Full default suite (unit + world + integration), same day:

```
python -m pytest -q
5 failed, 1710 passed, 2 skipped, 7 deselected, 58 subtests passed in 514.06s (0:08:34)
```

The five failures are not this work. They are in the tree's uncommitted
edits from before it: `data/weapons.json` raises the hammer's damage from 25
to 27 (and another weapon's from 14 to 15) while
`tests/combat/test_hammer_swing.py` and `test_weapon_classes.py` still pin
25; `test_manual_aim.py::test_held_key_fires_once_per_cooldown` counts 2
shots where it expects 3 on the same edited data; and
`tests/rendering/test_menu.py::test_content_comes_from_config` reads the
edited `character_select_state.py` instruction text one character longer
than the config's. Nothing in the failing modules touches the ledger, the
enemy or boss damage seam, or the screen.

### Screenshot

Rendered from a real headless run (Aegis, Normal, 90 s of mixed spawns next
to the hero, then a scripted death): four weapons with their damage, share
and DPS; eleven enemy types slain with the boss and the brood-mother among
them; seven blessings; three items; 317 gold. Delivered to the owner on
2026-09-12.

---

## Revision 1 (owner, 2026-09-12, after the first screenshot)

Three requests, confirmed as read:

1. **Raise the ribbon titles 5 px, nothing else.** Read as the *text* on
   the ribbons: the pack's ribbon art has its fork and shadow at the bottom,
   so a label centred on the rect reads low. The ribbon art, the columns and
   every row stay where they were. `ui/run_summary.py` now draws the ribbon
   unlabelled and blits the title itself at `TITLE_DY = -5` from the
   ribbon's centre.
2. **Blessings move to the weapons column.** They belong with the build,
   not with the kills. They are drawn under the weapons table's total row,
   as a "Blessings (n)" list with levels. The kills column is now kills
   alone, so its cap rose from 8 rows to 13 — every type in
   `data/enemies.json` plus the boss — and "+n more types" cannot occur
   with the current roster. To keep the weapons column inside its budget
   (four weapon rows: three slots and a summon; the proc rows; the total;
   six blessings) the proc rows are capped at 2 instead of 4; a run rarely
   has more than one proc source, and the "+n more sources" line covers the
   rest.
3. **"Damage by weapon" becomes "Weapons."** Title only; the table's
   columns are unchanged.

`tests/rendering/test_game_over.py::test_long_lists_are_cut_not_overflowed`
now paints four weapon rows too, since the weapons column is the tight one.

### Two things the revision's screenshots showed

- **The blessings list was cut at six with the column half empty.** The
  fixed cap was sized for the worst case (four weapons, two proc rows). The
  list now takes whatever room is left below the weapons table — six rows
  in that worst case, eight or more in the usual one — and gives its last
  row to "+n more" only when the list does not fit. Checked with a
  synthetic ten-blessing, four-weapon, one-proc summary: eight rows and
  "+2 more", the last line 13 px above the column's edge.
- **A proc row with no name and 28 % of the damage.** The Spirit Wolf's
  bites (and the Grave Totem's bolts) were spawned without their
  `weapon_id`, so they arrived at the ledger as `""`: the wolf's own row
  read 0 and its damage sat under a blank label. `entities/summon.py` now
  passes `weapon_id=self.weapon_id` on both projectiles, and the ledger
  files an empty source under `other` like `None` (unit test added). A 40 s
  check with the wolf and the totem held: `spirit_wolf` 288, `grave_totem`
  98, no blank key. Side effect worth knowing: a summon's hit now carries
  its weapon id through the resolver too (`killed_by`, synergy hit memory,
  the summon weapon's own `effects`), which is what those paths expect of a
  weapon's projectile.

### Tests after the revision

```
python -m pytest tests/combat tests/rendering/test_game_over.py tests/core/test_smoke.py tests/ai -q
4 failed, 546 passed, 1 skipped, 27 subtests passed in 127.91s
```

The four failures are the pre-existing hammer / held-key ones listed under
the first full-suite run. Screenshot v2 (revision) delivered.

## Check: a real death reaches the screen (owner, 2026-09-12)

Asked whether the screen appears on an actual game over -- the health bar
depleted by enemies -- rather than only on the scripted death the tests
used. Checked by simulation: a normal run, the hero's weapons removed, six
chasers spawned beside the hero every two seconds, no input.

| Hero | HP / armour / block | Died at | Screen up at |
|---|---|---|---|
| Aegis | 160 / 4 / 30 % | 13.1 s | 14.2 s |
| Kestrel | 92 / 0 / 0 % | 4.2 s | 5.2 s |

The path: `Player.take_damage` (evasion, block, trait multiplier, armour)
takes `hp` to 0 and clears `alive`; `PlayingState.update` opens the 1.05 s
death window for the poof (`_death_seq_t`); `_run_death_sequence` calls
`_end_run(victory=False)`, which builds the summary and changes to
`GameOverState`. The summary's clock is the moment of death (the window
does not advance `stats["time"]`).

Two things done on the back of the check:

- `tests/core/test_smoke.py` gains
  `test_an_unarmed_hero_dies_to_enemies_and_sees_the_game_over_screen`, the
  simulation above as a regression test (cap 120 s of run time).
- The earlier scripted-death test called `take_damage(10 ** 9)` once, and
  that call goes through the 5 % evasion roll -- one run in twenty would
  have shrugged the hit off and timed out. It now hits until the hero is
  down.

## Revision 2 (owner, 2026-09-12)

The title reads **"Game Over"** instead of "You Died". One string in
`game/states/game_over_state.py`; same font, size, colour and position.

### Deferred

*(DOC-005, 2026-09-24: the victory screen's summary panel is **done** (`ui/end_screen.py`). A "best DPS" record is still **pending**, never asked for (`game/save.py` `_RECORD_KEYS`))*

*(DOC-006, 2026-09-24: the best-DPS record is **closed**, not needed (owner). The weapons table's forge names running their level into the damage figure are fixed as UI-013, below)*

- **The victory screen** still draws the old nine-line readout. It can take
  the panel in one line (`RunSummaryPanel(self.stats).draw(...)`) — the
  summary it receives already carries the rows. Left out because the request
  was the game-over screen.
- **A "best DPS" record** in the rankings would be one key in
  `save._RECORD_KEYS`; not asked for.

---

**ID:** UI-013 · **System:** interface · **Type:** bug · **Status:** done ·
**Branch:** claude/doc-006-ui-013-dps-table (the current worktree, owner 2026-09-24)

This block follows the DOC-001 layout; the entries above predate it.

## UI-013 — Requirement (owner, 2026-09-24)

- **Objective:** Stop weapon names in the run summary's weapons table from
  running their level into the damage figures.
- **Details:** It shows on some weapons and especially on forges. Polish the
  table only; the DPS extras (a best-DPS record, absolute damage in the
  overlay) are not wanted (DOC-006).
- **Constraint:** The table's cells and numbers stay as they are.

## UI-013 — Confirmed reading

- `ui/run_summary.py::_draw_damage` draws `"<name>  Lv <n>"` from the left
  edge. Damage / Share / DPS are right-aligned 150 / 84 / 0 px from the
  right edge.
- The weapons column's 498 px minimum (content 442) was measured against
  `weapons.json` only ("Grave Totem  Lv 9", 186 px). The forge names in
  `forges.json` are longer ("Meteor Hammer  Lv 9", 216 px). A 7-figure
  damage is 93 px, so a label has 199 px before the damage starts.
  Reproduced: "Meteor Hammer  Lv 9" prints over "1,212,400".
- A weapon's level is 1 + its blessing levels. Six blessings of five levels
  each put it as high as 31, so the level takes two digits.
- **UI-013.D1 — The level gets its own cell.** A right-aligned "Lv" column
  sits before Damage, so the level never shares space with a number.
- **UI-013.D2 — The column's minimum is measured from the data.** It is the
  widest name in `weapons.json` and `forges.json`, plus the level cell and
  the numeric cells, rather than a hand-measured 498. A new weapon or forge
  widens the column itself.
- **UI-013.D3 — A name that still does not fit is ellipsized** to the room
  left of its level. This covers an 8-figure damage, which also pushes the
  level cell left. Nothing can overlap, whatever the numbers are.

## UI-013 — Plan

- In `_draw_damage`: place the level cell from the widest damage drawn (at
  least a 7-figure one), and trim every name to the room it has.
- A module helper for the weapons minimum, measured with the row font and
  used by `draw` and the tests.
- Tests:
  - Every weapon and forge name at `Lv 31`, with 7- and 8-figure damage, on
    the 3- and 4-column layouts: no name or level reaches the damage cell.
  - The other victory columns still meet their contents.
- A screenshot with the widest forge build.

## UI-013 — Tasks

- [x] UI-013.1 — The level cell, the trimmed names, the measured minimum; tests; screenshot

## UI-013 — Results

- `ui/run_summary.py`:
  - The weapons table has a right-aligned **Lv** cell, placed clear of the
    widest damage drawn.
  - Every name is ellipsized to the room left of its level.
  - `weapons_min_width(font)` measures the column's floor from every weapon
    and forge name, and `column_minimums` resolves it for `draw` and the
    tests.
- **UI-013.D4 — Laid out in the widest digit.** The body font's digits are
  proportional, so "8,888,888" was not the widest 7-figure damage
  ("2,424,800" is wider). The layout patterns use `#` for the font's widest
  digit. The first test run caught this: "Meteor Hammer" was trimmed at a
  damage of 2,424,800.
- **Widths at 1600 × 900:**
  - Victory screen: the weapons column is 549–550 px (was 498), and the other
    three are 293 px (were 307). They still fit their contents.
  - Game-over screen: 550 px, with 445 px for each of the other two.
- **Tests:**
  - `tests/screens/test_victory.py::WeaponsTableTests`: every weapon and forge
    name at `Lv 31`, with 7- and 8-figure damage, on both layouts. The name
    stops before its level and the level before its damage (84 subtests).
    "Meteor Hammer" shows in full.
  - `ColumnWidthTests` now reads the measured floor.
  - `test_text.py`'s item-name test uses `column_minimums`.
  - `tests/screens`, `test_hero_unlock`, `test_damage_numbers`: **575 passed,
    135 subtests, 0 skipped**.
- **Screenshot:** the widest forge build (Meteor Hammer, Fan of Blades,
  Arcane Storm, Grave Totem at Lv 9, a 7-figure damage) on the game-over and
  victory layouts, with no overlap.
- The old 498 is annotated where it was recorded
  (`victory_screen_journal.md`, `elemental_system_journal.md`).
