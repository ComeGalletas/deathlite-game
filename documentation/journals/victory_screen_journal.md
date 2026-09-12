# Victory screen — execution journal

## Requirement (owner, 2026-09-12)

Review the victory screen as it stands and rework it to show more information,
in the manner of the game-over screen. Proposal first; nothing coded yet.

---

## Review: what the screen is today

`game/states/victory_state.py` is 60 lines and its own docstring still calls
itself a **"Milestone 1 stub"**. It fills a dark green rectangle, centres the
word *Victory*, and prints nine `label  value` lines in a single column:

```
Hero       Aegis            Salvage    265   (banked)
Survived   612.4 s          Blessings  9
Level      21               Loot       3 item(s) to the stash
Kills      734  (72/min)    Build      Sword Lv6, Bow Lv4, Spirit Wolf Lv3
Damage     486200  (794 dps)
```

Input is keyboard only: ENTER for a new run, S for the Sanctuary, ESC for the
menu. There are no buttons and no mouse targets, which puts it at odds with the
standing rule that the menus are mouse-drivable.

### The finding that shapes everything else

`PlayingState._end_run` builds **one** summary dict and hands *the same object*
to both screens. The victory screen therefore already receives every number the
game-over résumé draws, and uses about a quarter of it. Untouched today:

| key in the dict | what it holds | victory does |
|---|---|---|
| `weapon_rows` | per weapon: level, damage, share, DPS over the span it was held | ignores — prints `name Lv n` |
| `other_rows` | blessing-proc damage rows | ignores |
| `kill_rows` | kills per enemy type, boss as its own row | ignores — prints one total |
| `blessing_rows` | blessing names with levels | ignores — prints a count |
| `damage_by_source` | the damage split | ignores |
| `dropped_items` | item names **and rarities** | ignores — prints a count |
| `gold`, `potions`, `potion_healing`, `chests` | run economy and healing | ignores |
| `seed`, `difficulty` | how the run was set up | ignores |

And `ui/run_summary.py` — the three-column panel the game-over screen draws —
says in its own first paragraph that it is *"Drawn by the game-over screen (and
available to the victory screen) so the readout is one piece of code with one
layout."* The reuse was designed for and then never taken up. The panel reads
its stats entirely through `.get()` with fallbacks, so it renders whatever it is
given; feeding it the victory dict needs no change to the panel at all.

**So the bulk of this work is adoption, not new rendering.**

---

## Confirmed design (owner, 2026-09-12)

Every open question answered. Nothing below is coded yet.

| # | decision |
|---|---|
| 1 | **Modularise the end screen** so victory and game over share it and each supplies only its specifics. |
| 2 | **Mouse control** on the victory screen too. |
| 3 | **Boss name, hero details, and `mm:ss`** for the run clock. |
| 4 | **Fix the currency bug** — see the gold section below, which replaces it outright. |
| 5 | **Add the fourth column now**; check visually whether it fits. Records go in it, but records are the **last** step — "not required but helps". |
| Backdrop | **Gold / bright**, not the current dark green. |
| Boss name | In the **subtitle**, as proposed. |
| Ribbons | **Reuse** game over's blue / yellow / red — but change the *other* elements so the screen reads as a win rather than a recolour of a defeat. |

---

## Gold is reported gross (owner, 2026-09-12)

> "for currency only keep a total amount of accumulated gold, not salvages, so
> if the player gets a total of 200 gold, and spends 50 during the run, the 200
> is the value to show."

Two changes, and the second cancels the bug reported earlier rather than fixing
it in place.

### The number shown is accumulated, not held

`stats["gold"]` is a **live balance**, not a total: `locations.use_merchant`
does `ps.stats["gold"] -= it.cost` on a purchase. So a run that earns 200 and
spends 50 currently reports 150, and the field cannot simply be relabelled.

Gold moves at three places today:

| | site | direction |
|---|---|---|
| kills | `playing/state.py` (`_gold_carry`, scaled by the Gold Rush blessing) | income |
| chests | `playing/chests.py` | income |
| merchant | `playing/locations.py` | spend |

The accumulator should **not** be a second `+=` bolted onto the two income
sites: the next income source added will forget it, and the total will
under-report silently. Proposed instead: a small `add_gold(n)` / `spend_gold(n)`
pair on `PlayingState`, with the three sites above converted to call them, so
the balance and the running total are updated together and a stray `+=` cannot
bypass the accounting. `_end_run` then carries `gold_earned` alongside `gold`.

### Salvage comes off the screen

The earlier finding was that both screens print raw `currency` as "Salvage
banked" while `Game._on_run_ended` actually banks
`currency * meta_catalog.salvage_multiplier(...)` — so a player with salvage
upgrades is told they banked less than they did. The owner's answer removes the
line rather than correcting the arithmetic, which resolves it.

**Consequence worth stating:** salvage is the Sanctuary's currency, and the end
screens were the only place a player learned how much a run earned — on a screen
with a Sanctuary button right on it. Flagged, not argued: if it should reappear
somewhere, the Sanctuary screen is the natural home.

---

## Plan

### Step 1 — `ui/end_screen.py`

Lift the frame both screens share out of `game_over_state.py`: backdrop fill,
title, subtitle, the `RunSummaryPanel` call, the wide-button row with
`ui.mouse.MouseNav`, and the hint line. `_PANEL_TOP` / `_PANEL_BOTTOM` and the
button metrics move with it instead of being copied. Each state then supplies
only: title text and colour, backdrop, button set, and its own subtitle parts.

This is what stops the two screens drifting apart again — which is how the
victory screen got four milestones behind in the first place.

### Step 2 — victory adopts it

`VictoryState` becomes the frame plus its specifics. It gains the button row and
mouse handling for free; ENTER / S / ESC keep working from anywhere, as on game
over.

### Step 3 — the victory-only facts

* **Subtitle** — `The Tusked Lance   -   Aegis   -   Fast   -   seed 35`. The
  boss name is not in the summary today; `Events.BOSS_KILLED` already publishes
  it, so `_end_run` needs `boss` and `boss_id` set where `character` and
  `character_id` are.
* **Clear time** — `Cleared in 10:12`, via the panel's existing `fmt_time`.
* **First-clear unlock** — `Game._on_run_ended` calls
  `save.mark_cleared(character_id)` on a victory and only on a victory. Announce
  it **only when the clear is new**, or it is noise on every later win.

### Step 4 — the fourth column, "Hero"

Hero name and trait, the resolved stat block, the equipped items, and the
first-clear unlock line.

Two things this needs, both worth knowing before it is built:

* **The summary does not carry the hero's stats.** The run-status screen reads
  `ps.player.stats` live; a run-end screen cannot. `_end_run` needs
  `summary["hero_stats"] = self.player.stats.as_dict()` plus the trait and the
  equipped items.
* **`RunSummaryPanel.draw` hard-codes three columns** (`col_w = (w - 2*margin -
  2*gap) // 3`). A fourth takes every column from **480 px to 355 px** at
  1600x900 — a 26 % narrowing. The Weapons column carries a four-field table
  (Weapon / Damage / Share / DPS) and is the one at risk; that is the visual
  check to make. If it does not fit, the fallbacks are a narrower Hero column
  rather than four equal ones, or moving the hero block into the Run column.

### Step 5 — making it look like a win

Ribbon colours stay blue / yellow / red. What changes:

* backdrop from dark green to a warm gold/bright ground,
* the title ink and face (game over's is `(230, 90, 90)` red),
* the button variants — game over puts `danger` on Main menu; a win should not
  lead with red.

### Step 6 (last, optional) — records

`save.record_best` tracks per-difficulty bests. Marking "new best" needs the
**old** values read before `record_best` overwrites them, which means threading
them through the run-ended event. Deliberately last, and droppable.

---

## Progress

* **2026-09-12** — Screen reviewed against the game-over screen with both fed
  the same run-end dict; proposal written.
* **2026-09-12** — Owner confirmed every point (above) and set the gold rule.
  Plan sequenced into six steps.
* **2026-09-12** — **Steps 1 and 2 built.**
  * `ui/end_screen.py` — the shared frame. `EndScreen` holds the selection and
    the mouse bookkeeping and decides nothing: `handle_event` returns the `bid`
    of the button to fire and the owning state acts on it, so the frame never
    imports a state. A `Button` dataclass carries the label, the hint text, an
    optional direct key and the art variant; `run_subtitle` builds the
    `hero - difficulty - seed` line both screens show. `PANEL_TOP`,
    `PANEL_BOTTOM` and the button metrics moved here from the game-over module
    rather than being copied.
  * `game/states/game_over_state.py` — down to the words, the red and the three
    destinations. `sel` and `_mouse` are forwarded to the frame as properties,
    which is what keeps the 23 existing tests passing untouched.
  * `game/states/victory_state.py` — the same shell. It gains the full résumé
    and mouse support; the nine hand-laid text lines are gone.
  * `tests/rendering/test_end_screen.py` (19) — the frame's contract on its own,
    never touching a state: which `bid` each key and click returns, the cursor
    wrapping, that a direct key beats the A/D cursor letters, that the row is
    centred and registers one rect per button, and that an empty stats dict
    still draws.
  * `tests/rendering/test_victory.py` (16) — the state's wiring: the three keys
    and the three clicks reach the three destinations, hovering selects, and
    all three résumé columns actually paint. The screen previously had no
    coverage beyond a smoke test that it opens.

  Deliberately **not** changed yet, per the agreed sequencing: the victory
  screen still wears the game-over palette — dark green backdrop, a red
  `danger` variant on Main menu — and still says "Survived" with salvage on the
  Run column. Steps 3 to 5 are what make it read as a win.
* **2026-09-12** — **Steps 3 and 4 built.**

  Step 3, the victory-only facts:
  * `_on_boss_killed` keeps `(boss_id, name)` before dropping the boss, and
    `_end_run` puts `boss` / `boss_id` in the summary — so the subtitle now
    reads `The Tusked Lance   -   Aegis   -   Fast   -   seed 35`.
    `run_subtitle` grew a `lead` argument for it.
  * `summary["victory"]` travels in the dict, so the Run column says
    **"Cleared in"** on a win and "Survived" on a death without either screen
    needing to know which it is.
  * `summary["first_clear"]` is read **before** the RUN_ENDED publish, because
    `Game._on_run_ended` calls `save.mark_cleared` — asking afterwards always
    answers "already cleared" and the reward could never be announced.

  Step 4, the Hero column:
  * `_end_run` snapshots `trait`, `hero_stats` (`player.stats.as_dict()`) and
    `equipment`. The run-status screen reads `player.stats` live; a screen
    shown after the run is over cannot.
  * `RunSummaryPanel.draw` takes a `columns` tuple. `hero` is opt-in, so the
    game-over screen keeps its three and the experiment is one word to undo.
  * The Hero column reuses `ui.run_status.common`'s `STAT_ROWS`, `stat_label`
    and `fmt_stat`, so the build reads the same as it does in-run rather than
    growing a second vocabulary. That import is deferred inside the method:
    `ui.run_status`'s package init pulls its Overview pane, which imports
    `fmt_time` back from `run_summary`, so a top-level import is a cycle.

  **The visual check you asked for failed, and the fix found an existing bug.**
  At four equal columns each is 355 px, and the weapons table right-aligns its
  Damage / Share / DPS cells at a fixed 150 px from the column's right edge —
  so the weapon's name was drawn straight through its own damage figure.
  Columns now declare a minimum width (`column_widths`), and only the weapons
  column has one: a measured 498 px, from the widest row label over
  `data/weapons.json` ("Grave Totem  Lv 9", 186 px) plus a seven-figure damage
  (94 px) plus the 150 px cell block plus 56 px of padding.

  The surprise was that **three** columns were already under it. The equal
  share there is 480 px, leaving 424 px of content for a row that can want 430,
  so the game-over screen could already overlap with a long weapon name and a
  large damage figure — it simply had not been hit yet. The minimum widens that
  column to 498 (the other two to 471) rather than leaving it latent. An
  earlier version of this note claimed three columns were unaffected; that was
  wrong and the code comment has been corrected.

  Tests: `test_victory.py` grew `ColumnWidthTests` (the split is pure
  arithmetic, so it is asserted directly — the overlap it prevents is invisible
  to a "did anything draw" check) and `HeroColumnTests`. The first-clear and
  "Cleared in" assertions spy on the text the panel renders rather than
  counting pixels, because the stat list shrinks to fill whatever room is left
  and the column paints the same amount either way. 69 tests across the three
  end-screen files.

  **One bug of my own, caught by an existing test.** `_end_run` called
  `self.player.stats.as_dict()`. `player.stats` is *already* the resolved plain
  dict — the `StatSet` is `player.statset` beside it, as the player module's
  own docstring says — so this raised `AttributeError` on every run end. It is
  now a plain copy. Worth noting the shape of the mistake: the run-status
  screen only ever calls `.get()` on that field, so nothing in the codebase
  had to know which of the two it was until something wanted the whole dict.

  Verified end to end once `data/spawn_tables.json` (broken mid-edit in another
  session) loaded again: a real run, a real boss kill, and the resulting
  `VictoryState.stats` carrying `victory`, `boss`, `boss_id`, `first_clear`,
  `trait`, `hero_stats` and `equipment`, with the boss's name in the subtitle.
  Two tests in `tests/core/test_hero_unlock.py` pin it — including that a
  *second* clear with the same hero is not a first clear, which is the half of
  the ordering rule a single test would have missed.
* **2026-09-12** — **The gold rule and step 5 built.**

  Gold is now reported gross. `stats["gold"]` was a live balance that
  `locations.use_merchant` subtracted from, so the total earned needed its own
  counter — and bolting a second `+=` onto the two income sites would drift the
  first time a third was added. `PlayingState` grew an `add_gold` /
  `spend_gold` pair instead, and all three sites (kill gold, chest gold, the
  merchant) go through it; `stats["gold_earned"]` rides along in the summary
  for free. The Run column reads **"Gold earned"**, falling back to the
  balance for a summary written before the total existed — an undercount, but
  the best answer available.

  The **"Salvage banked" row is gone**. It printed the raw `currency` while
  `Game._on_run_ended` banks that times the meta salvage multiplier, so a
  player with those upgrades was told they earned less than they had. Dropping
  the row was the owner's call and it removes the wrong number rather than
  correcting it. Salvage is still earned and still banked — it is only no
  longer reported here, which leaves the Sanctuary as the place to learn it.

  Step 5, the win palette: backdrop `(38, 28, 14)` (warm, and brighter than
  the game-over `(22, 10, 12)`), the title in `(255, 214, 112)`, and no
  `danger` variant on any button — leading a win with a red Main menu was the
  tell that the screen was a recolour of a loss. The ribbon colours are reused
  exactly as asked, so the two screens stay one family.

  Tests: `tests/systems/test_gold.py` (9) for the accounting pair, including
  the owner's own example; `GoldTests` and `PaletteTests` in `test_victory.py`.
  Two tests I wrote and then replaced are worth noting — both asserted on
  `inspect.getsource` strings, which is not a behavioural check: one became an
  assertion on the real summary in `test_hero_unlock.py`, the other a spy on
  the ribbon colours the panel actually asks for.

  Outstanding: **step 6 (records)** only, which was always last and optional.
* **2026-09-12** — **Step 6 built; the rework is complete.**

  `SaveData.beaten_records(stats, difficulty)` answers which of the four
  tracked records (`time`, `level`, `kills`, `damage_dealt`) a run would take.
  It deliberately shares `_RECORD_KEYS` and the comparison with `record_best`,
  so a screen can never advertise a record the save did not actually store —
  a test asserts the two agree by storing a better run and comparing what
  moved against what was claimed.

  `_end_run` reads it **before** the RUN_ENDED publish, the same ordering trap
  `first_clear` hit: `Game._on_run_ended` calls `record_best`, which overwrites
  the values the comparison needs, so afterwards no run has ever beaten
  anything. A dev run banks nothing, so it reports no records either.

  The marker is drawn in place rather than as a list: `_kv` grew an optional
  `flag`, set after the *label* because the value is right-aligned to the
  column edge and has nothing to spare. Three of the four keys are Run rows and
  the fourth is the Weapons total, so a run that broke two records reads
  "Kills *best* 734" and "Total *best* 486,200" with no extra vertical space
  and nothing shifted.

  The clock row is marked under whichever label it is wearing that run —
  "Cleared in" on a win, "Survived" on a death — which is the one place the
  step-3 wording change and this one meet.

  Tests: `BeatenRecordsTests` in `tests/core/test_save.py` (7) and
  `RecordMarkerTests` in `test_victory.py` (4). Verified end to end over three
  consecutive runs on one save: a clean sweep, then a worse run claiming
  nothing, then a run beating only kills.

  **One thing left alone, and worth stating.** `record_best` takes the *maximum*
  of each key, so a longer run is always the better `time`. On a victory that is
  arguably backwards — a faster clear is the achievement — but changing it would
  rewrite what every existing save means and what the rankings screen shows.
  Flagged rather than done.

