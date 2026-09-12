# Run status screen — execution journal

## Requirement (owner, 2026-09-12)

A screen that lets the player see, during a run:

- the current status of the run,
- the current weapons and blessings,
- the Forge and synergy upgrades,
- the descriptions of the blessings and the numerical value each level adds.

"Similar to the game over screen": confirm and propose what is understood.
Nothing is coded yet. This entry is the confirmed reading, what the code
already gives, the proposal, and the questions left for the owner.

---

## Confirmed reading

Each item against what the run already keeps, and what the screen would show
for it. Everything in the "exists" column is live data on `PlayingState` or
the `Player`; no new bookkeeping is needed for any of it.

| Requirement | What exists today | What the screen shows |
|---|---|---|
| Current status of the run | `stats` (time, level, kills, gold, salvage, dropped items); `levels.progress_fraction` (XP to next level); `player.hp / max_hp`; the hero, difficulty and seed; `player.stats` (a `StatSet`: `as_dict()` gives every resolved stat — max HP, move speed, armor, pickup radius, block, evasion, damage / attack-speed / projectile-speed multipliers, crit, luck, XP and gold gain); `player.equipment` (the items equipped from the stash); the run ledger built for the game-over screen (damage and DPS per weapon so far, kills per type). | An **Overview** pane: the run line (survived, level with the XP bar, kills, gold, salvage), the hero's stats with what each is worth right now, the equipped items, and a "so far" line per weapon from the ledger. |
| Current weapons | `player.weapons`: each `Weapon` has `name`, `level`, `weapon_class`, `forge`, its `definition` numbers plus the `bonus` the blessings added (damage, cooldown multiplier, projectile count, area, pierce, crit chance, weight, stun, blast radius, chain, cone), and `effects` (the behaviour keys). `blessing_levels(w)` is the count the Forge gates on. | A **Build** pane, one card per weapon: name, level, class, the live numbers (base → with blessings), the blessing levels it has taken, and its Forging if any. |
| Current blessings | `player.blessings` is `{id: level}`; the catalog (`BlessingDef`) has the name, rarity, category, the weapon it belongs to, and `describe(level)` — the card text with the values for that level filled in. Every effect carries its full `levels` ladder (cumulative values, one per level) and a `display` that formats it (`+20`, `+6%`, `x1.5`, `+0.4s`, …). | A **Blessings** pane: the list of owned blessings (name, level in roman numerals, rarity colour, weapon or "hero"); the selected one shows its description at the current level, the same description at the next level, and the value ladder with the current level marked — e.g. `+20 · +40 · [+60] · +80 · +100 max HP`. This is the "numerical value increases" the requirement asks for. |
| Forge upgrades | `weapon.forge` names the Forging; `content.forges[id]` has its `name`, `identity`, `description`, the `overrides` it merged over the base weapon and the `effects` it added. `forge_requires_levels` is the gate. | On the weapon's card in the Build pane: the Forging's name and identity, its description, and the numbers it changed as `before → after` (Whirlwind: cooldown 0.5 → 0.24, damage 12 → 6, cone → 180°). An unforged weapon shows the gate instead: "Forge at 2 blessings — has 1". |
| Synergy upgrades | The eight blessings in category `synergy` (Blood in the Water, Linebreaker, Demolition, Marked Prey, Crowd Cleaner, Crossfire, Weak Point, Demolitionist). Each is a weapon blessing whose `requires.weapons` names the partner weapon and whose card text states the bonus and the 1.5 s window. Natural synergies (design §11) are deliberately rule-free, so there is nothing to list for them. | A **Synergies** section of the Build pane: each owned synergy blessing as "Sword ↔ Daggers — Blood in the Water II: +30 % Dagger damage against enemies the Sword hit in the last 1.5 s", with the pair drawn from the blessing's weapon and its `requires.weapons`. An empty section says so rather than vanishing. |

Three things the requirement does not say that are decided here, and stated
so the owner can overrule them:

- **It is an overlay that freezes the run**, like PAUSED: `draw_below` so the
  world stays visible under a dim layer, `update_below = False` so nothing
  moves while the player reads. Reading a build mid-fight is not a thing to
  do at 60 fps.
- **One key opens it from the run, and the pause menu gets a row.** TAB is
  unused in the run (Q is auto-attack, M mute, E interact, ESC / P pause,
  backquote the dev menu, F1–F7 the overlay). TAB or ESC closes it. The pause
  menu gains a "Run status" row between Resume and Key layout.
- **Three panes under one ribbon strip, not one wall of text.** The game
  over screen fits its three columns because a run has at most four weapons
  and a dozen enemy types; a run's blessings run to fifteen or more, each
  with three lines of text, so the blessing list scrolls and its detail is
  shown for one selected row at a time.

---

## What the code already gives us

**The catalog already formats every value.** `BlessingDef.describe(level)`
fills the card template from `Effect.value_at(level)` through
`format_value(value, display)`; the level-up card and the dev menu both go
through it. The ladder is the same `levels` list read at every index, so the
"current / next / all levels" view is three calls into code that exists.

**The Forge's changes are already a diff.** A Forging is `overrides` merged
over the base `definition`, so `before → after` is
`{k: (base[k], overrides[k]) for k in overrides}` against
`content.weapon(weapon_id)`. Nothing has to be reconstructed.

**The pause overlay is the template.** `PausedState` is an overlay with a
cursor menu, wide buttons and `ui.mouse.MouseNav`; the run status screen is
the same shape with panes instead of rows. `RunSummaryPanel`'s ribbon
columns, fonts and number formatting carry over as they are.

**The ledger is live during the run.** `ps.ledger` accumulates from the
first hit, so the Overview can show damage and DPS per weapon *so far*
without waiting for the run to end — the same rows the game-over screen
draws, called mid-run.

**The Forge rail is a weapon list.** `ui/forge_rail.py` draws a weapon per
row with a title, a note and a selectable state; the Build pane's weapon
cards are a wider version of the same idea and can share its row art.

---

## Proposal

### 1. The state — `game/states/run_status_state.py`

An overlay pushed on top of PLAYING (`draw_below = True`,
`update_below = False`). Three panes, one ribbon each across the top —
**Overview** (blue), **Build** (yellow), **Blessings** (red) — switched with
Left / Right (also A / D, or 1 / 2 / 3) and by clicking the ribbon. Up / Down
and the mouse wheel move the selection inside a pane; ESC or TAB closes and
pops back to the run. Opened by TAB in `PlayingState._phase_input` and by a
"Run status" row in `PausedState`.

### 2. The panes — `ui/run_status/` (one module per pane)

- `overview.py` — the run line, the XP bar, the hero stats (label, value as
  the stat's unit: HP and speed as numbers, chances and multipliers as
  percentages), equipped items, the ledger's per-weapon "so far" table.
- `build.py` — a card per weapon (name, level, class, base → live numbers,
  blessing levels taken, its Forging with the `before → after` list or the
  Forge gate), then the Synergies section.
- `blessings.py` — the scrolling list on the left (name, roman level,
  rarity colour, "Sword" / "hero"), the detail on the right: description at
  the current level, description at the next level (or "max level"), and the
  value ladder with the current level marked.

Shared: the ribbon strip and the dim layer; the number formatting comes from
`ui/run_summary.py` (`fmt_time`, `fmt_damage`, `fmt_dps`) and the catalog's
`format_value`. Layout targets 1600×900 and must also fit the 1280×720 web
profile, which is why the blessing list scrolls rather than columns.

### 3. Two small data helpers, next to the data they read

- `BlessingDef.ladder()` in `progression/blessings/catalog.py`: per effect,
  the formatted value at every level — the list the detail pane prints.
- `forge_changes(content, weapon)` in `combat/weapons/forge.py`: the
  `(key, before, after)` triples for a forged weapon.

Both are pure and unit-testable without a display.

### 4. Tests

- `tests/progression/test_blessing_ladder.py` (unit): the ladder matches
  `describe()` at each level; formatting per display type; max level.
- `tests/combat/test_forge_changes.py` (unit): the diff against the base
  definition for a data Forging; an unforged weapon yields nothing.
- `tests/rendering/test_run_status.py` (unit, fake game as the game-over
  tests do): each pane draws with a full build and with an empty one; TAB
  and ESC pop; the ribbons take a click; the blessing list scrolls and
  clamps.
- `tests/core/test_smoke.py`: TAB during a real run pushes the overlay,
  the world does not advance while it is up, TAB again resumes.

### 5. Screenshot

One per pane from a real headless run with a forged weapon and a synergy
blessing granted through the dev menu, delivered when built.

---

## Questions for the owner

1. **TAB** to open, or another key (C, I)? TAB is free in the run today.
2. **Freeze the run** while it is open (proposed), or let it play on behind a
   translucent panel?
3. **Show the equipped items and the hero stats** on the Overview (proposed:
   yes — they are the rest of "the current status"), or keep it to the run
   line?
4. **Blessing detail**: current description + next level + the full ladder
   (proposed), or only the current and next?
5. **Live per-weapon damage** from the ledger on the Overview (proposed:
   yes, it is free now), or leave that to the game-over screen?

### Answers (owner, 2026-09-12)

1. **TAB** opens and closes it. Confirmed.
2. **Freeze the run** while it is open. Confirmed.
3. **Equipped items are shown** on the Overview. The owner notes they give
   no bonuses today and will in the future, so the item rows list the item
   (rarity, name, slot, level) without claiming an effect. (For the record:
   `PlayingState._apply_persistent_bonuses` does fold an equipped item's
   stat affixes into the hero's `StatSet` and its tag affixes into the
   blessing effects, so whatever they contribute is already inside the stat
   values the Overview prints; the items are just not annotated with it.)
4. Blessing detail shows **"current" only**: the description with the
   owned level's values, plus the level as "II of V". No next-level line, no
   ladder. (Settled after the same-day explanation of the three pieces.)
5. **No live per-weapon damage** on the Overview: that stays on the game
   over screen. The ledger is not read by this screen.

Second round (owner, 2026-09-12): **items do claim their bonuses** — each
equipped item row is followed by its details: the base stat, every affix
(stat or tag damage) with its value, and the unique effect's text where it
has one. Point 3 above is superseded to that extent. Confirmed and started.

### Progress

- [x] 1. state and the TAB / pause-row entry — `game/states/run_status_state.py`;
      TAB in `PlayingState.handle_event`; the "Run status" row in `PausedState`
- [x] 2. panes — `ui/run_status/{common,overview,build,blessings}.py`
- [x] 3. data helpers — `combat/weapons/forge.py::forge_changes`; the ladder
      helper was dropped with the owner's "current only" answer
- [x] 4. tests green — see below
- [x] 5. screenshots delivered — three panes at 1600×900 and the Build pane at
      the 1280×720 web size

---

## Built (2026-09-12)

### What changed, file by file

| File | Change |
|---|---|
| `game/states/run_status_state.py` | new: the overlay (`draw_below`, no update below), three panes, TAB / ESC close, Left / Right / 1-3 switch, Up / Down / wheel select, `MouseNav` over ribbons and rows; `find_playing` locates the run under the pause overlay |
| `ui/run_status/common.py` | new: dim layer, panel, ribbon tabs (active lit, others shaded), row primitives, `STAT_ROWS` with `fmt_stat` / `fmt_mod` |
| `ui/run_status/overview.py` | new: the run line with the XP bar, the equipped items with `item_lines` (base, affixes, unique effect), the hero stats |
| `ui/run_status/build.py` | new: weapon cards (`weapon_numbers`: base → now), the Forge gate line, the selected weapon's Forging strip, `synergy_rows` |
| `ui/run_status/blessings.py` | new: the scrolling list and the current-level detail |
| `combat/weapons/forge.py` | `forge_changes(content, weapon)`: overrides against the base definition, then the added effects |
| `game/states/playing/state.py` | TAB pushes the screen |
| `game/states/paused_state.py` | "Run status" row (four rows now) |
| `tests/rendering/test_run_status.py` | new, unit: 21 tests — draws (full, empty, web size, no run), readouts, keys, mouse, entry points |
| `tests/combat/test_forge_changes.py` | new, unit: 4 tests over every Forging in the data |
| `tests/rendering/test_pause.py` | six tests re-pinned from three rows to `_ROWS` |
| `tests/core/test_smoke.py` | the state walk opens the screen with TAB, draws all panes, checks the clock did not move, closes |

### Decisions made while building

- **The Forging detail left the card.** The first Build layout put the
  Forging's description and its changes inside the weapon's card. At
  1600×900 that fit; at the 1280×720 web profile the card was cut after the
  "Forging:" header with the numbers gone. The cards now hold the numbers
  and the gate; a strip under them shows the **selected** card's Forging
  (changes first, description in the room left) beside the synergies, and
  Up / Down or a click selects a card. Both sizes fit deterministically;
  at 720 p a card with more number rows than room shows "+n more".
- **Item values are rounded to one decimal.** Rolls are unrounded floats
  (`+3.917 Armor`); the readout prints `+3.9 Armor`, and a whole number stays
  whole. The stat list is unaffected.
- **"melee · melee" and "summon · summon" are gone.** A card's second line
  is the class, then the category and the special effect only where they
  say something the class does not.
- **The XP bar sits in the gap under the Level row** (it overlapped the row
  in the first render).
- **The hero's multipliers are not folded into the weapon numbers.** Damage
  ×, attack speed × and area × sit on the Overview and apply to every weapon
  alike; a card shows what is the weapon's own, so `base → now` reads the
  blessings on *that* weapon.

### Tests

```
python -m pytest tests/rendering/test_run_status.py tests/rendering/test_pause.py tests/combat/test_forge_changes.py -q
47 passed, 32 subtests passed in 22.80s
python -m pytest tests/core/test_smoke.py -q -k boot_and_state_walk
1 passed in 10.92s
```

The wider run, same day:

```
python -m pytest tests/rendering tests/core tests/combat tests/progression -q
1 failed, 1156 passed, 5 deselected, 52 subtests passed in 420.61s (0:07:00)
```

The one failure is `tests/rendering/test_menu.py::test_content_comes_from_config`,
the hero-select instruction test already noted as needing re-pinning in the
commit "Hero select: instruction rows start one line higher". Nothing in it
touches this screen.

### Deferred

- **Next-level and ladder detail** for a blessing: the owner chose the
  current level only. `BlessingDef.describe(level + 1)` and the effects'
  `levels` lists are there if that changes.
- **A HUD hint** ("TAB build") is not drawn; the pause menu row and the
  README say it.
