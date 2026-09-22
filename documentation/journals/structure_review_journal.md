# Structure review — dev log

**Legacy ID:** SYS-007 · **Systems:** SYS · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

Follow-up to the 2026-09-20 read-through of the tree (package docstrings,
cross-package imports, the two big subsystems, the documentation set; no
tests run). The review found the architecture sound — layered `world/`, a
sealed `spawn/`, entities with no drawing, zero `TODO`s, zero orphan
modules — and the debt concentrated in four places: the docs describe a
previous tree, `PlayingState` regrew past its own refactor, ten menu screens
each roll their own cursor, and a handful of functions run past 180 lines.

## Requirement (owner, 2026-09-20)

- **Objective:** List the current fixable tasks, documentation included.
- **Details:**
  1. Create a second file, `FUNCTIONAL_README.md`, and move the sections
     related to the game's functionality there — testing documentation and
     everything else not relevant to a common player — leaving the current
     README as basic as possible: the game's concepts, the tools and asset
     references, and the current features and options.
  2. Review the menu screens toward a general cursor-movement and hover
     hit-testing implementation, to modularize them.
  3. Identify the outsized files and functions that could be split up, the
     growing god-object included.
- **Constraints:** The worktrees have already been deleted, and the unused
  asset folder's untracked state is intentional — do not touch it.

## Confirmed reading

**Out of scope, by the owner's word.** `.claude/worktrees/` is gone
(`git worktree prune` leaves only `main`). `assets/unused/` stays
gitignored and untouched.

**A. Documentation.** Two READMEs describe a tree that no longer exists:

- `world/README.md` (357 lines) walks the retired LD-8 generator —
  `config.IRREGULAR_ROOMS`, `config.WORLD_VERTICALITY`, a
  `world/gen/verticality.py`, painters `world/terrain/rooms.py` /
  `cliffs.py`. None of those symbols or files exist; the height-map world
  is the only world (`ld8-flat-generator-retired`, 2026-09-02).
- `README.md` "Project layout" omits `spawn/` (11 modules, 2,302 lines)
  and `tools/`, still lists `world/ … digest` (now
  `tools/verification/world_digest.py`), and its `tests/` tree
  (`ai/ rendering/ characters/ core/`) does not match the real folders
  (`combat devtools display entities flows playing progression render
  screens spawn systems world`).
- `README.md:359` and `game/assets.py:9` name
  `data/{character,enemy,weapon,prop}_sprites.json`; those live under
  `data/heroes|enemies|weapons|loot/` since the data reorganisation.

The split the owner asks for: `README.md` keeps what a player or a
first-time reader needs — what the game is, requirements, setup, run,
controls, the display / start screen / difficulty notes, the content
list, the asset credits pointer. `FUNCTIONAL_README.md` takes what a
developer needs — the browser build, the desktop packaging, the test
tiers and the world cache, the project layout, the terrain / sprite
plumbing, development status, the documentation map. Every moved section
is moved, not duplicated; each file links the other once at the top.

**B. Menu cursor + hover.** Every screen subclasses `State` directly and
re-implements the same shape in `handle_event`: ask `ui.mouse.MouseNav`
for a hover / click, set the index, activate on click; then on `KEYDOWN`
wrap the index on Up / W and Down / S, activate on Enter / Space, back on
Escape. `MouseNav` and `HitMap` (`ui/mouse.py`) already own the mouse
half; the keyboard half and the glue are copied ten times
(`menu_state`, `paused_state`, `options_state`, `meta_state`,
`rankings_state`, `level_up_state`, `run_status_state`,
`character_select_state`, `dev_menu_state`, and the two end screens
through `ui/end_screen.py`). Menus accept **both** WASD and the arrows
for navigation regardless of the key layout (README "Controls"), so the
shared module does not read `config.KEY_LAYOUTS`.

Decision the request left open: `MetaState` and `RankingsState` take no
mouse at all today. "General … hover hit testing" is read as every menu
getting it, so both gain hover-select and click through the shared module.

**C. Outsized functions and files.** Against a baseline of 13 functions
over 80 lines out of 2,051, the ones to split:

| lines | where | shape today |
|---:|---|---|
| 267 | `world/terrain/grid_paint.py:397 _paint_room` | four commented passes + a band trim, sharing ~10 locals |
| 191 | `world/gen/bridges.py:19 _seat_corridors` | five closures (`reach`, `options`, `apply`, `side_of`, `allowance`) over one loop |
| 183 | `world/gen/__init__.py:61 generate_world_steps` | five commented stages |
| 124 | `world/nav/lattice.py:168 _elevation` | pass-per-pass |
| 114 | `world/gen/height/graph.py:14 walk_links` | pass-per-pass |
| 104 | `game/states/playing/core/npcs.py:76 build` | one builder per NPC kind inline |
| 102 | `world/gen/scatter.py:217 _scatter_obstacles` | pass-per-pass |

Files: `game/states/playing/core/state.py` (1,302) is item D.
`world/gen/village.py` (965) is already 25 functions; it becomes a
`world/gen/village/` sub-package (site, seating, pen, scatter) per the
one-module-per-concern preference. `game/states/playing/visual/rendering.py`
(935) sheds the three dev overlays (~170 lines) to `devtools/overlays.py`.
`game/config.py` (1,093) is **left alone**: it is 193 constants with their
reasoning, and the flat `config.X` read surface is the point.

**D. `PlayingState`.** `playing_state_refactor.md` targeted ~320 lines
and landed at 735; the file is now 1,302 lines, ~90 methods, 71
attributes. The sub-systems were extracted but each holds `ps` and reads
it back — the pools (`enemies`, `projectiles`, `hostiles`, `gems`,
`chests`, `potions`, `hazards`, `summons`, `melee_hitboxes`,
`interactables`, `npcs`, `boats`, `fish_huts`), the services (`grid`,
`particles`, `damage_numbers`, `shake`, `camera`, `rng`, `stats`,
`content`, `game`, `game_map`, `player`, `boss`, `ledger`) and a few
callbacks (`_spawn_projectile`, `_targetables`, `notice`, `add_gold` /
`spend_gold`, `_drop_item`, `_apply_on_kill_effects`, `_on_boss_killed`,
`_spawn_impact`, `_in_world_margin`). That journal named the missing
piece — P7 `RunContext`, deliberately skipped — and it is what lets the
coordinator shrink for good.

**E. Compat shims** (found, not asked for; listed because they are
fixable): `game/states/playing_state.py`, `world/procedural.py`,
`world/pathfinding.py` and the `SpawnDirector` re-export in
`world/spawning.py`. `world/procedural.py` re-exports *private* names
(`_four_connected`, `_corridor_doorways`, `_HOUSE_RADIUS`,
`_VILLAGE_*`) for the tests. Retarget the imports and drop the shims;
`ring_point_around` in `world/spawning.py` is real code and stays.

## Proposal

### A. Documentation (first: no code moves, lowest risk)

1. `FUNCTIONAL_README.md` — new, at the root beside `README.md`. Sections,
   in this order, moved verbatim from `README.md` then edited for the
   fixes below: *Play in the browser*, *Build for distribution*, *Run the
   tests* (the tier table, the world cache, the digests), *Project layout*
   (fixed: add `spawn/` and `tools/`, drop `world/ … digest`, real `tests/`
   folders), *Assets — how it is wired* (the rig files at their real
   paths, `Assets`, the terrain bake, the start-menu backdrop rule),
   *Development status*, *Documentation map*.
2. `README.md` — keeps: title paragraph, Requirements, Setup, Run,
   Controls (with Display / Start screen / Difficulty), Content, a short
   *Assets and credits* pointer, and one line each to
   `FUNCTIONAL_README.md` and `dist/README.md`.
3. `world/README.md` — rewritten against the current pipeline:
   `generate_world_steps` stage by stage as the code has them (tree →
   islands → bridges → roles → height maps → bounds → obstacles →
   villages → tile meta → repair → spawn points → chests → fish huts),
   the `rules/` layer, the bake (`grid_paint`, `decor/`, `bake`), the
   renderer, and `nav/`. The tilesheet-slot section is kept where it is
   still true (checked against `data/world/terrain.json`).
4. `game/assets.py:9` docstring path fix.

### B. `ui/menu_nav.py` — `MenuNav`

One object a screen owns, replacing the copied `handle_event` prologue:

```python
nav = MenuNav(count=len(rows), mouse=MouseNav(hitmap), wrap=True)
verb = nav.event(event)     # -> ("move", i) | ("activate", i) | ("axis", ±1)
                            #    | ("number", n) | ("back", None) | None
```

- Vertical: Up / W and Down / S move `nav.index` (wrapping, or clamped
  for the Sanctuary's two panels); the screen may pass `skip=callable`
  for rows the Options screen greys out.
- Horizontal: Left / A and Right / D are reported as `("axis", ±1)`; the
  screen decides (Options nudges a bar, Pause cycles the key layout, the
  hero select steps the hero).
- Enter / Space → `("activate", index)`; Escape (and any extra keys the
  screen names in `back_keys`) → `("back", None)`; 1–9 → `("number", n)`.
- Mouse: hover sets `index` and reports `("move", i)`; a click reports
  `("activate", i)`. The `HitMap` stays the screen's — it registers rects
  as it draws, exactly as now.
- Screens keep their `_activate` / `_back`; they lose the key ladder.

Adopters, in order of simplicity: `menu_state`, `paused_state`,
`rankings_state`, `meta_state` (gains mouse; two `MenuNav`s, one per
panel, `wrap=False`), `options_state`, `dev_menu_state`, `level_up_state`
(horizontal cards: a `MenuNav(axis="h")`), `character_select_state`
(hero row horizontal, difficulty vertical), `run_status_state`
(tabs horizontal, rows through the pane), `ui/end_screen.py`.
`tests/screens/test_menu_nav.py` pins the verb table with synthetic
events; the existing per-screen tests stay as the behaviour guard.

### C. Function and file splits

Each split is behaviour-neutral and checked the same way: the `world`
tier's pinned digests (`tests/world/test_digest.py`) for anything under
`world/`, the screen tests for the rest.

- `_paint_room` → a `_RoomPaint` job (the shared locals as fields) with
  one method per pass: `sort_cells`, `paint_floors`, `paint_stone`,
  `paint_tall_and_seams`, `trim_bands`. Same module.
- `_seat_corridors` → the five closures lifted to module functions over
  a small `_SeatCtx`; the loop body becomes readable on one screen.
- `generate_world_steps` → `_grow_tree`, `_seat_rooms`, `_lay_bridges`,
  `_shift_to_origin`, each a plain function the generator calls in the
  same order, so the RNG stream is untouched.
- `_elevation`, `walk_links`, `_scatter_obstacles`, `npcs.build` →
  pass-per-pass helpers in place.
- `world/gen/village.py` → `world/gen/village/` (`__init__` keeps
  `place_villages`; `site.py`, `seating.py`, `pen.py`, `scatter.py`).
- `rendering.py` → `devtools/overlays.py` takes `collider_overlay`,
  `spawn_point_overlay`, `aim_overlay`.

### D. `PlayingState` → coordinator + `Run`

1. `core/run.py`: a `Run` dataclass built in `enter()` holding the pools,
   the services and the run facts (`seed`, `difficulty`, `dev_mode`,
   `elapsed`). Sub-systems take `run` instead of `ps`; the state keeps
   `self.run` and forwards the attribute names the tests read.
2. The callbacks the sub-systems reach for become services on `Run`:
   `spawn_projectile` / `spawn_impact` / `spawn_hazard` → a `Spawner` in
   `effects.py`; `targetables` → `perception.py`; `notice` → the HUD
   layer; `add_gold` / `spend_gold` → `run_ledger.py`.
3. What leaves the coordinator, each to its own module:
   - level-up flow, on-kill effects, potion drops, item drops →
     `core/rewards.py`
   - `_begin_end`, `_end_run`, `_snapshot_summary`, `_hand_off`,
     `_restart_dev_run`, `_run_ending_sequence` → `core/run_end.py`
   - hero animation naming and `_main_weapon_for` → `core/hero.py`
   - the `_dev_*` flags, `_apply_dev_unlimited_hp`, `_set_difficulty`,
     `_report_debug`, `handle_debug_key` → `devtools/dev_flags.py`
   - `_depth_items`, `_draw_world`, `_draw_flat_effects`, `_actor_items`
     → `visual/scene.py`
4. Target: `state.py` ≤ 450 lines — `enter` wiring, the four-phase
   `update`, `draw` layer order, event routing. The number is written
   down so it cannot drift silently again.
5. Determinism A/B (a fixed seed, N frames, the digest of the entity
   positions) before and after, as the earlier refactor did.

### E. Shims

Retarget every import of the four shims to the real modules (source and
tests), then delete `game/states/playing_state.py`, `world/procedural.py`,
`world/pathfinding.py`, and the `SpawnDirector` re-export in
`world/spawning.py`.

## Order and progress

Docs first (nothing moves), then the menu module (small, self-contained),
then the function splits (each independently verifiable), then the
coordinator (largest), then the shims (touches many imports; last so the
retargeting is done once against the final tree). Each step ends with
the relevant test tier green and its own entry below.

- [x] A1 `FUNCTIONAL_README.md` — 2026-09-20
- [x] A2 `README.md` cut to the player-facing sections — 2026-09-20
- [x] A3 `world/README.md` rewritten against the current pipeline — 2026-09-20
- [x] A4 `game/assets.py` docstring path — 2026-09-20

### A. Documentation — done 2026-09-20

`FUNCTIONAL_README.md` (371 lines) holds the browser build, the packaging,
the test tiers, the developer keys and `tools/`, the display internals, the
project layout, the asset wiring, the development status and the
documentation map. `README.md` went from 423 to 201 lines: intro,
requirements, setup, run, controls, display / start screen / difficulty,
content, a short assets-and-credits section, and one-line pointers to
`FUNCTIONAL_README.md`, `dist/README.md` and `world/README.md`. The F1–F8
rows left the player's controls table for the functional file.

`world/README.md` (450 lines) now walks `generate_world_steps` stage by
stage with the labels it yields, the `Cell` height map, `LevelIndex`,
`bake_steps` → `BakedTerrain` field by field, the banded frame composition
from `PlayingState._draw_world`, and the slot table checked against
`data/world/terrain.json` (the `raised`, `ramp` `s`/`n`, `vstair` and bridge
`shadow` entries the old text did not have).

Found while checking claims, and corrected in all three files: since
2026-09-20 `SPECIAL_KINDS` is empty (`world/gen/tuning.py`,
`game/states/playing/core/locations.py`), so no shrine, treasure, altar or
merchant island is generated — a run's interactables are the village forge
and fountain, the buff buildings and the chests; the old README's E-key row,
content bullet and blessing-offer line said otherwise. `data/ui/ui_sprites.json`
is loaded on its own by `Content`, not merged into the sprite namespace.

Not run: the test suite (no code moved). The per-workstream journals that
name `README.md` sections are historical and were left as written.
- [x] B1 `ui/menu_nav.py` + `tests/screens/test_menu_nav.py` — 2026-09-20
- [x] B2 adopt in the ten screens and `ui/end_screen.py` — 2026-09-20

### B. Menu navigation — done 2026-09-20

`ui/menu_nav.py::MenuNav` turns an event into one verb -- `("move", key)`,
`("activate", key)`, `("axis", ±1)`, `("number", i)`, `("back", None)` or
None -- over the screen's own `MouseNav`. The screen keeps its index and
hands it in (`nav.event(event, index=self.sel, count=len(rows))`), so
`menu._index`, `pause.sel`, `opt.sel`, `lu.selected`, `s.tab` and every
`state._mouse.hits` the tests read are unchanged. `axis="h"` for the
horizontal lists (cards, ribbons, hero cards, the end buttons), `wrap=False`
for the Sanctuary's clamped panels, `skip=` for the Options rows that grey
out, `back_keys=` per screen (ESC+P on pause, TAB+ESC on the build screen,
ESC+backtick on the dev menu, none on the end screen where ESC is a button),
`right_click_back` for the dev menu. Menus still take both WASD and the
arrows whatever the run's key layout says.

Adopted: `menu_state`, `paused_state`, `rankings_state`, `meta_state`,
`options_state` (the slider drag stays in front of it as `_handle_drag`),
`level_up_state` (the Forge rail's own `MouseNav` is still read first),
`run_status_state`, `character_select_state` (`_mouse_action` keeps the
arm-then-begin rule), `dev_menu_state`, `ui/end_screen.py` (a button's own
key and the confirm keys are read before the nav so ESC fires Main menu).
`options_state._move` and `dev_menu_state._move` went; nothing outside the
two called them.

New behaviour, as decided in the reading: the Sanctuary rows are mouse
targets keyed `(panel, i)` -- hover selects the row and its panel, a click
buys or equips -- and the Rankings' hint line is its one target, a click
leaves. Pinned by `tests/screens/test_sanctuary_mouse.py` (7 tests, listed
in `conftest.INTEGRATION`); the module by `tests/screens/test_menu_nav.py`
(19, pure). The behaviour guard: `tests/screens` + `flows/test_dev_mode`,
`test_hero_unlock`, `test_display_change_in_run`, `test_controls`,
`test_smoke` -- **624 passed, 24 subtests, 5 min 39 s**.
- [x] C1 `_paint_room` — 2026-09-20
- [x] C2 `_seat_corridors` — 2026-09-20
- [x] C3 `generate_world_steps` — 2026-09-20
- [x] C4 `_elevation`, `walk_links`, `_scatter_obstacles`, `npcs.build` — 2026-09-20
- [x] C5 `world/gen/village/` sub-package — 2026-09-20
- [x] C6 dev overlays out of `rendering.py` — 2026-09-20

### C. Function and file splits — done 2026-09-20

Every split is behaviour-neutral and was checked against the pinned
layout / bake / frame digests (`tests/world/test_digest.py`), which did not
move, plus the tests that read each area.

- **C1** `grid_paint._paint_room` (267 lines) → `_RoomPaint`, a job holding
  the shared locals with one method per pass: `sort_cells`, `paint_floors`,
  `paint_stone`, `paint_tall`, `paint_seams`, `trim`. Same blits in the
  same order; `_paint_room` is now the six calls. Longest method 78 lines.
  The docstring's reference to a `test_level_bands.py` that never existed
  was replaced with the digest that actually guards it.
- **C2** `bridges._seat_corridors` (191) → the five closures lifted to
  module functions -- `_reach`, `_lane_options`, `_apply_lane`,
  `_allowance`, and the duplicate `side_of` dropped for the `_side_of` the
  module already had -- plus `_seat_link` (one link's cloning, picking and
  seating) and `_charge` (the per-side bookkeeping that was written three
  times). `_add_shortcuts` no longer takes callables. `_seat_corridors`
  keeps its name and signature (`tests/world/test_repair.py` imports it).
- **C3** `generate_world_steps` (183) → `_grow_tree`, `_seat_rooms`,
  `_lay_bridges`, `_shift_to_origin`, called in the same order with the
  same yields; the RNG stream is untouched, which the layout digest pins.
- **C4** `NavGrid._elevation` (124) → `_cell_tiles`, `_tile_step_masks`,
  `_project_masks`. `height/graph.walk_links` (114) → the ground rule and
  one function per flight kind (`_north_flight_links`,
  `_wall_flight_links`, `_lateral_links`, `_ewstair_links`), the link
  order preserved. `scatter._scatter_obstacles` (102) → `_scatter_room`
  and `_spot_ok`. `Npcs.build` (104) → a `_Casting` (the seeded draws, the
  colour cycle, `spot_near`, one `npc()` constructor) and `_place_smith`,
  `_place_pawns`, `_place_lancers`, `_place_herd`; the draws run in the
  same order, so the villagers stand where they did.
- **C5** `world/gen/village.py` (965) → `world/gen/village/`: `site`
  (`_Site`, `_Cycle`, `_road`, `_seg_dist`, `_circles`, the colour and
  fence tables), `seating` (`_lay_out` and its eight steps, `_fill_beside`),
  `pen` (`_place_pen`, `_pen_sweep`, `_pen_tiles`, `_pen_fits`), `scatter`
  (the three prop sweeps and `_edge_distance`). `__init__` keeps
  `place_villages` and re-exports the private names the tests and
  `village_tidy` reach for (`_Site`, `_pen_tiles`, `_pen_fits`, `_blocks`,
  `_road`, `_place_pen`). Moved with `git mv` so the history follows the
  package init. `tests/world/test_layering.py` still passes.
- **C6** the three dev overlays (~170 lines) → `devtools/overlays.py` as
  functions of `(surface, ps)`, with their three constants;
  `WorldRenderer` keeps one-line forwarders so `PlayingState.draw` and
  `tests/flows/test_dev_mode.py` call them where they always did.
  `rendering.py` 935 → 777 lines and no longer imports `fonts`.

Not split, as planned: `game/config.py`. Source functions over 100 lines
went from five to three, none of them in `world/`: `dps_bench.to_markdown`
(a report writer), `CharacterSelectState.draw` (116, a single layout pass)
and `generate_world_steps` (104, the linear pipeline with its stage
comments). Undefined-name check over every split module clean.

Verification, three runs: C1+C2 digests / terrain / north flights /
repair / layout **149 passed**; C3+C4 digests / elevation / mirrors /
pathfinding / obstacles / families / npcs / enemy nav **147 passed**;
C5+C6 village / tidy / quality / houses / digests / layering / dev mode /
depth sort / ghost **143 passed, 81 subtests**. No digest rewritten.

Noted, not touched: the working tree also holds another session's
uncommitted "special facilities parked" change (`entities/interactable.py`,
`core/locations.py`, `world/gen/{graph,spawnpoints,tuning}.py`, four
tests, `digests.json`, `special_facilities_journal.md`); the digests above
are that change's.
- [x] D1 `core/run.py` and the sub-systems on `Run` — 2026-09-20
- [x] D2 callbacks → services — 2026-09-20
- [x] D3 `rewards.py`, `run_end.py`, `hero.py`, `dev_flags.py`, `scene.py` — 2026-09-20
- [x] D4 `state.py` 1,302 → 737 lines (see the note), determinism A/B recorded — 2026-09-20

### D. `PlayingState` → coordinator + `Run` — done 2026-09-20

**D1.** `core/run.py::Run` is a dataclass holding the run's facts (seed,
rng, difficulty, dev mode, content, game, character), the world and hero,
the entity pools, the services (grid, particles, damage numbers, shake,
levels, ledger, stats), the transient effect lists, the screen feedback
timers and the input state, with the four whole-run rules as methods
(`notice`, `add_gold` / `spend_gold`, `targetables`, `in_world_margin`).
`PlayingState` builds it first thing in `enter` and forwards every field
under its own name and the underscore aliases (`ps._explosions`,
`ps.run_seed`, `ps._aim`, ...) as generated properties, so every read and
write the tests and the older call sites make lands on the `Run`. The
twelve sub-systems now hold `self.run = getattr(ps, "run", ps)` and read
the run's fields from it (316 substitutions, mechanical); the `getattr`
is what lets a bare namespace standing in for the state -- the tests'
fakes for `TransientFx`, `CombatResolver` and the unbound gold / hero
rules -- count as its own run. `Run` carries the same aliases as
properties for the same reason.

**D2.** The callbacks the sub-systems reached back for became services:
`spawn_projectile` / `spawn_summon` / `resolve_visual` / `spawn_impact` /
`spawn_hero_hazard` / `update_summons` on `TransientFx`; `targetables`,
`in_world_margin`, the gold and `notice` on `Run`. `FireContext` and the
summon context still name the state's `_spawn_*` forwarders, so a test
that patches one on the instance still intercepts the weapons.

**D3.** Out of the coordinator, each with its own module docstring:
`core/rewards.py::Rewards` (kills, on-kill effects, potions, drops, the
boss reward, the level-up flow -- and the `gold_carry`, `drop_counter`,
`awaiting_level_up`, `boss_defeated` it used to keep on the state),
`core/run_end.py::RunEnd` (`begin` / `end` / `snapshot_summary` /
`hand_off` / `restart_dev_run` / `ending_sequence`, the `ending` flag),
`core/hero.py` (`HeroAnim`, and `main_weapon_for` /
`apply_persistent_bonuses` / `anim_name` / `has_anim` as functions so
the state's forwarders can apply them to a fake), `devtools/dev_flags.py::DevFlags`
(the six switches, the HP ratchet, the debug key table, the live
difficulty switch, the F1 metrics), `visual/scene.py` (`draw_world`,
`draw_flat_effects`, `actor_items`, `depth_items`; the actor draw calls go
through the state's `_draw_*` forwarders, which the depth-sort tests patch).

**D4.** `state.py` 1,302 → **737 lines**: `enter` and its five steps, the
event routing, `on_display_changed`, the four-phase `update`, `draw`, the
context builders, and the compatibility surface -- the generated field
properties, a `_FORWARDERS` table of forty-odd pass-throughs installed by
`_delegate`, and a dozen forwarders that need a signature of their own.
The coordinator proper is ~430 lines; the 450 written down in the plan was
for that part, and the surface the tests read is the rest. Every `_dev_*`,
`_hero_*`, `_awaiting_level_up`, `_ending` name still resolves.

**Determinism.** `tools/verification/run_digest.py` (new): two pinned
seeds, 720 frames each with debug spawns and a forced level-up, hashing
the hero, the stats, every enemy, the pools, the ledger, the run RNG's
state and the camera. Pre-D and post-D dumps are byte-identical for both
seeds. Two pre-existing sources of non-reproducibility surfaced while
building it and are neutralised in the tool, not in the game:
`spawn/watchdog.py::_stagger` keys an enemy's first sample off
`id(enemy)` (a memory address), and the enemy mix also depends on
Python's per-process string-hash seed (two stable outcomes per seed; the
roster sorts its names, so the set iterating in hash order sits further
down the spawn / placement path and is not located). Both are logged
under *Open* below.

**Verification.** The pre-D baseline was the full default suite, green:
2,799 passed, 683 subtests (15 min, contended). After D: the run-driving
modules first (43 failures, all the fakes and two patched names, fixed as
above → 113 passed), then the fast batch again (106 passed), then the
A/B, then the full suite: 8 failures left, all tests calling a forwarder
unbound on a bare namespace with no owner behind it (`_resolve_visual`,
`_apply_on_kill_effects`, `pick_boss`) -- `_delegate` now builds the
light owners (`TransientFx`, `Rewards`, `RunEnd`, `CombatResolver`) over
the fake, and `pick_boss` reads `run_seed` through the alias. Full suite
after that: **2,799 passed, 683 subtests, 0 failures (13 min 56 s)** --
the pre-D baseline exactly. `run_digest --check`: match on both seeds.
- [x] E shims retired — 2026-09-20

### E. Compat shims — done 2026-09-20

`game/states/playing_state.py`, `world/procedural.py` and
`world/pathfinding.py` removed (`git rm`); the `SpawnDirector` re-export and
its docstring left `world/spawning.py`, which keeps `ring_point_around`.
Every import retargeted to the real module, 33 files: `PlayingState` from
`game.states.playing.core.state`; `NavField` / `FlowField` / `_INF` /
`_NAV_CLASSES` from `world.nav.field`, `NavGrid` / `NAV_DIRS` / `_ORTH` /
`_TILE_BIT` / `_point_*` from `world.nav.lattice`, `CLEARANCE_CAP` from
`world.nav.clearance`; `generate_world` from `world.gen`, the model types
from `world.layout`, `SPECIAL_KINDS` / `_HOUSE_RADIUS` / `_VILLAGE_*` from
`world.gen.tuning`, `_corridor_doorways` from `world.gen.scatter`. The test
that pinned the `SpawnDirector` re-export (`test_budget.py`) went with it;
`test_layering.py`'s forbid-lists name `world.nav` instead. Docstrings in
`world/layout.py` and `world/nav/__init__.py`, `world/README.md` and
`FUNCTIONAL_README.md` updated. Full suite: **2,798 passed, 683 subtests, 0
failures (13 min 23 s)** -- one fewer than D's 2,799, the removed shim
test. `run_digests.json` re-pinned for the new import graph (see *Open*).

## Open

Found on the way and not part of this review's scope; each needs its own
decision.

- **The run is not reproducible across processes.** Two independent
  causes, both in the spawn path: `spawn/watchdog.py::_stagger` seeds an
  enemy's first sample from `id(enemy)`, and something further down the
  spawn / placement path iterates a set of strings, so the enemy mix of
  one seed takes one of two stable forms depending on Python's hash seed.
  Neither breaks a test today (`run-booting-tests-pin-the-seed` pins the
  *world*, which is unaffected), but "same seed, same run" does not hold
  for the enemies. `tools/verification/run_digest.py` works around both.
- **Seed 123's digest is not stable across processes.** With the hash
  seed pinned and the watchdog stagger flattened, seed 7 reproduces every
  time; seed 123 has come back with three different values over the day,
  and the same code gave two of them minutes apart -- so beyond the hash
  seed there is an object-order (memory layout) dependence somewhere on
  the spawn path. The population and placement iterate int-keyed dicts,
  so it is not there. Read the tool as: seed 7 is the pin, and a "moved"
  123 is evidence only when pre and post trees are dumped back to back
  and compared (which is how D was checked -- identical for both seeds).
- **`generate_world_steps`** is still 104 lines: the linear pipeline with
  its stage comments. Left as the one place the stage order can be read.
