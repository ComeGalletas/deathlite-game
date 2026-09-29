# Test tiers — journal

**ID:** TST-006 · **System:** tests · **Type:** bug ·
**Status:** done · **Branch:** ComeGalletas/tst-006-tier-booting-tests-bb480b0c
(the session worktree `.claude/worktrees/sad-williams-838fee`, cut from
`origin/main` at `5176c0c`)

---

## TST-006 — Requirement (owner, 2026-09-29)

- **Objective:** `-m unit` runs only tests that generate nothing and boot
  no `Game`, so it is fast enough to run on every save.
- **Details:**
  - Found during RND-008.3: `tests/playing/test_run_hints.py` and
    `tests/playing/test_key_marker.py` each build a real
    `Game(save_path=...)` and call `PlayingState.enter(seed=1234)`, but
    neither is listed in `INTEGRATION`, so they run in `unit`.
  - Find every test module or class that boots a `Game`, enters a
    `PlayingState` or generates a world and is not in `WORLD`,
    `INTEGRATION` or `SWEEP`, with a deterministic script, and cross-check
    it against the tuples in `tests/conftest.py`.
  - Register each one in the right tier: `world` for cached or generated
    worlds only, `integration` for booted Games. Register by class where a
    module mixes pure and booting classes, the way RND-008.2 registers
    `tests/devtools/test_spawn_stress.py::ClassName`.
  - Show `python -m pytest -m unit --durations=15` before and after.
- **Constraint:**
  - No test is lost: every test is still collected once and still runs in
    the default invocation (`unit + world + integration`).
  - The test modules stay plain unittest (tiers by path in conftest).
  - No CI, hooks or gates (`CLAUDE.md` Tests): the check is a unit test in
    the suite, like every other.

## TST-006 — Confirmed reading

- **How a tier is decided.** `pytest_collection_modifyitems` matched each
  nodeid against `SWEEP`, `UNIT`, `WORLD`, `INTEGRATION`, in that order, by
  prefix; anything unmatched is `unit`. So `WORLD` wins over
  `INTEGRATION`, and a class entry in `INTEGRATION` cannot pull a class out
  of a module that `WORLD` lists whole.
- **Why grep alone is not the tool.** A plain grep over the unit-tier
  modules for `Game(`, `PlayingState(`, `.enter(`, `start_run(`,
  `tests.worlds`, `LoadingState` hits 23 modules. Seven are false:
  `_Game(` fakes (`test_controls_block.py`), menu states' own
  `.enter(stats=...)` (`test_game_over.py`, `test_victory.py`,
  `test_forge_rail.py`, `test_run_status.py`), `LoadingState.music`
  attribute reads (`test_music.py`), and a docstring
  (`grids/test_village_tidy_rules.py`). Grep also misses the boots that go
  through a helper in another module: `tools.benchmarks.dps_bench._start_dev_run`
  boots a run for `test_forge.py`, `test_dps_bench.py`, `test_dps_meter.py`,
  none of which says `Game(`. And it cannot tell which *class* of a module
  boots.
- **So the script reads calls, not text** (`tools/verification/tier_audit.py`).
  It parses every `tests/**/test_*.py` with `ast` and follows each test's
  calls through its module's helpers, `self.`/`cls.`/`super()` methods,
  base classes, and any in-repo module it imports, to three primitives,
  keyed by where they are *defined* so aliases and re-exports resolve:
  - `integration`: constructing `game.game.Game`, `PlayingState`,
    `LoadingState` (or a subclass).
  - `world`: `generate_world`, `generate_world_steps`, or `GameMap` handed a
    seed. `GameMap()` / `GameMap(seed=None)` is the one hand-built room
    (not the retired generator, per the LD-8 decision) and
    `GameMap(layout=...)` takes a layout built elsewhere.
  - A test needs the highest tier reached from the method, its class's
    fixtures (through the bases), the class body, and the module body and
    `setUpModule`.
  - The tier it *gets* comes from `tier(nodeid)`, now a function in
    `tests/conftest.py` that the collection hook also calls, so the audit
    and pytest cannot disagree about it.
  - It reads 3450 tests; pytest collects 2250 selected + 1200 deselected
    under `-m unit` = 3450. Same set.
- **Findings, before any change** (`python -m tools.verification.tier_audit`):

  In `unit`, needs `integration`:

  | module | classes that boot | pure classes staying `unit` |
  |---|---|---|
  | `tests/playing/test_run_hints.py` | all three | — |
  | `tests/playing/test_key_marker.py` | both | — |
  | `tests/playing/test_buffs.py` | all five | — |
  | `tests/flows/test_display_change_in_run.py` | both | — |
  | `tests/screens/test_ui_scale.py` | both | — |
  | `tests/combat/test_forge.py` | `ArcaneStormOnTheDummyTests`, `ForgeWeaponPickerTests` | seven |
  | `tests/devtools/test_dps_bench.py` | `BuildTests`, `DamageScaleTests`\*, `BlessingDamageScaleTests`\*, `MeasurementTests` | `ClassificationTests`, `StatisticsTests` |
  | `tests/devtools/test_dps_meter.py` | `BenchArenaTests`\* | seven |
  | `tests/entities/ai/test_ranged_windup.py` | `FiringTests` | `ShapeTests` |
  | `tests/entities/test_fish_huts.py` | `BoatTests` | — (`PlacementTests` is `world`) |
  | `tests/render/test_element_layers.py` | `DrawOrderTests` | three |
  | `tests/render/test_enemy_hp_bar.py` | `BossExclusionTests` | three |
  | `tests/render/test_spawn_fx.py` | `RunTests` | `SheetTests` |
  | `tests/screens/test_ultrawide.py` | `DimCoversTheMarginsTests`\*, `ScreenBackdropTests`\*, `PanelsStayInTheBoxTests`\* | `LongBackgroundStripTests` |

  In `unit`, needs `world`: `tests/entities/test_fish_huts.py::PlacementTests`
  (`tests.worlds.layout`).

  In `world`, needs `integration` (outside the request's scope, same rule —
  TST-006.D2):

  | module | booting classes | other classes |
  |---|---|---|
  | `tests/playing/test_interactables.py` | both | — |
  | `tests/entities/test_npcs.py` | `VillagerTests` | `PenSpotTests` (pure) |
  | `tests/playing/test_infusion_sources.py` | four | `DataTests` (pure) |
  | `tests/playing/test_enemy_nav.py` | `PlayingStateNavWiringTests`, `NavRebuildStaggerTests`\* | `NavFieldTests` (world) |
  | `tests/render/test_depth_sort.py` | `DepthOrderTests` | `SceneryDrawablesTests` (world\*), `ConeWeaponVisualTests` (pure) |

  \* the class mixes pure and booting (or world) tests; see TST-006.D1.

## TST-006 — Decisions

- **D1 — granularity.** A module whose every test needs the same tier is
  registered whole. A module that mixes is registered class by class. A
  class that mixes goes whole to the highest tier any of its tests needs,
  not method by method: method entries break silently on a rename, and the
  pure methods that ride up (two in `DamageScaleTests`, three in
  `BlessingDamageScaleTests`, one in `BenchArenaTests`, three across the
  `test_ultrawide.py` classes, one in `NavRebuildStaggerTests`, one in
  `SceneryDrawablesTests`) still run in the default invocation.
- **D2 — the `world` modules that boot a Game move too.** `pytest.ini`
  defines `world` as "reads the shared cached worlds", and `integration` as
  "boots a real Game"; the five modules above were carried into `WORLD`
  whole in the folder reorganisation. Their own task (TST-006.3), so the
  owner can drop it without touching the request's own fix. Splitting them
  lets the pure classes (`PenSpotTests`, `DataTests`,
  `ConeWeaponVisualTests`) fall to `unit`, where they belong.
- **D3 — over-tiered tests are reported, not moved.** `--over` lists pure
  tests sitting in `world` or `integration` (mostly `tests/world/` classes
  that check data or tile sheets). Moving them only widens `unit`; it is
  not what was asked, and each would need its own look.
- **D4 — the audit is a test, the trace is a tool.** `tests/devtools/test_tier_audit.py`
  runs the audit over the real suite in `unit` (under 2 s) and fails with
  the conftest lines to add. The runtime trace
  (`-p tools.verification.tier_trace`) watches the same primitives while
  the tests run, and is the cross-check for what reading source cannot
  see; it fails nothing.

- **D5 — a child process is read, not trusted.** The critic showed
  `test_run_determinism.py` could leave `INTEGRATION` unnoticed: it boots
  four runs in child interpreters, where neither the reader nor the trace
  looks. The reader now follows `subprocess` calls into the child's
  program (`-c` code, `-m` module, script path), and a child it cannot
  resolve counts as `integration`. The three cut-script checks
  (`--check` runs of `tools/asset_pipeline/`) read as `unit`, which is
  what they are.

## TST-006 — Plan

- `tests/conftest.py`: `tier(nodeid)` shared by the hook and the audit;
  the new entries, each with a line on why.
- `tools/verification/tier_audit.py`: the static reader; exit 1 when
  anything is under-tiered, `--over` for the other direction.
- `tools/verification/tier_trace.py`: the pytest plugin.
- `tests/devtools/test_tier_audit.py`: the reader's rules on small source
  trees (boots, worlds, fakes, `GameMap()` without a seed, inherited
  fixtures, import-time boots, grouping) and the real suite.
- `pytest.ini`: say how to check the tiers.

## TST-006 — Todo

- [x] TST-006.1 — `tier()` in conftest; `tier_audit.py`, `tier_trace.py`;
  the reader's tests.
- [x] TST-006.2 — Register the `unit` findings (the request's own scope);
  pin `test_run_hints.py` / `test_key_marker.py` as `integration`.
- [x] TST-006.3 — Split the five `world` modules that boot a Game (D2);
  the suite-wide "nothing under-tiered" test.
- [x] TST-006.4 — The cold critic pass's findings fixed in the reader
  (cycles, `--over` grouping, child processes, module-level test
  functions); its remaining blind spots written into the docstring.
- [x] TST-006.5 — `pytest.ini` note; before/after measurements; close.

## TST-006 — Log

### 2026-09-29 — TST-006.1: the audit

- `tests/conftest.py`: `tier(nodeid)` is the matching loop the hook used,
  as a function; the hook marks with `tier(item.nodeid)`. Same order, same
  answer (the 2250 / 1200 split under `-m unit` is unchanged).
- `tools/verification/tier_audit.py` reads 3450 tests in ~1.5 s and finds
  173 under-tiered: 28 prefixes in `unit` needing `integration`, one needing
  `world`, and five `world` modules needing `integration` (the tables
  above).
- `tools/verification/tier_trace.py` over `-m unit` (163 s): 92 tests
  reached a primitive above their tier. **All 92 are in the audit's 173,
  with the same tier; 0 the audit missed.** The 81 the trace did not see
  are the rest of a class after its `setUpClass` paid (`FiringTests`,
  `BoatTests`, `DrawOrderTests`), a module run cache (`test_buffs.py`'s
  `_RUN`), a cached world (`PlacementTests`), and the `world` modules,
  which `-m unit` does not run.
- `tests/devtools/test_tier_audit.py`: 17 tests on small source trees,
  0.16 s. The grep false positives listed above are among the cases pinned
  as `unit` (`_Game(` fakes, a menu's own `.enter(...)`).

### 2026-09-29 — TST-006.2: the `unit` findings registered

- `INTEGRATION` gains five whole modules and fifteen classes;
  `WORLD` gains `test_fish_huts.py::PlacementTests`. 132 tests leave `unit`:
  70 in the five whole modules, 62 in the sixteen classes, of which 9 are
  the pure tests that ride up with a mixed class (TST-006.D1). pytest
  agrees: 2250 selected before, 2138 after = 2250 - 132 + this task's 20
  audit tests.
- They pass where they now live: `-m "world or integration"` over the
  fourteen touched modules, 132 passed, 101 deselected (the pure classes,
  still in `unit`), 150 s.
- `SuiteTests` pins it: nothing in `unit` is under-tiered, and
  `test_run_hints.py` / `test_key_marker.py` are `integration` by need and
  by registration.

### 2026-09-29 — TST-006.3: the `world` modules that boot a Game

- `WORLD` no longer lists `test_npcs.py`, `test_interactables.py`,
  `test_infusion_sources.py` whole; `test_enemy_nav.py` and
  `test_depth_sort.py` keep only their world classes (`NavFieldTests`,
  `SceneryDrawablesTests`). `INTEGRATION` gains `test_interactables.py` and
  eight classes. `PenSpotTests` (4), `DataTests` (3) and
  `ConeWeaponVisualTests` (2) fall to `unit`: 9 tests, under 0.2 s
  together.
- Every test is in exactly one tier: `-m unit` 2147, `world` 515,
  `integration` 797, `sweep` 11; sum 3470 = everything collected.
- The five modules under the trace, all tiers: 74 passed, 0 reached a
  primitive above their tier (132 s).
- `SuiteTests.test_no_test_is_under_tiered` now covers every tier; the
  audit reads 0 under-tiered.

### 2026-09-29 — TST-006.4: the critic pass

A cold adversarial reviewer (deliverable only, no build context) ran for
22 minutes and returned FAIL. It confirmed that the tiering is correct:
0 under-tiered, 0 false positives (the 184 `integration` and 150 `world`
tests the reader calls pure touch no primitive under the trace), every
`::Class` entry exists, nothing is shadowed, and removing entries one at a
time is caught. It FAILed the reader on:

| finding | severity | fix | pinned by |
|---|---|---|---|
| `f -> g -> f` cached a partial answer mid-cycle, so the second-read end came out `unit` | bug | a body that met an open key is not cached until the cycle closes | `CycleTests` (fails on the TST-006.1 reader) |
| `--over` named mixed classes whole (`test_window.py::WindowTests` "needs unit", yet one test builds a `Game`) with an empty `via` | bug | moving down, a class is named only if every test in it is pure; an empty chain prints "reaches nothing" | `GroupingTests.test_moving_down_...` (fails on the old one) |
| a boot in a child interpreter is invisible: dropping `test_run_determinism.py` from `INTEGRATION` passed `SuiteTests` | gap present in the repo | D5 | `ChildProcessTests`, `SuiteTests.test_the_child_process_run_...` (both fail on the old one); the mutation now fails |
| module-level `def test_*` functions skipped | gap, none today | read as nodeid `path::name` | `CollectionTests.test_module_level_...` |
| helper-instance methods, aliases by assignment, `partial`, `getattr`, template-method `setUp`, decorators, `GameMap(**kw)`, a name imported twice | gaps, none today | listed in the module docstring as what the reading cannot see | — |
| the trace credits a `setUpClass` boot to the first test only | doc | the trace docstring says so, and names child processes | — |

Also here: imports are collected by walking statements only (an import is
always a statement). The whole read is 1.1 s for 3480 tests; the answers
for all 3470 existing tests, call chains included, were identical to the
TST-006.1 version before the critic fixes went in.

The critic also found `test_ultrawide.py::PanelsStayInTheBoxTests::
test_a_level_up_draw_without_the_dim_leaves_the_margins_alone` fails when
run alone ("font not initialized"): it leans on an earlier test in its class
having booted a Game. The file is untouched here and the class keeps its
order in `integration`, so this branch does not expose it. Raised as its
own task.

### 2026-09-29 — TST-006.5: measured, documented, closed

`python -m pytest -m unit --durations=15`, same machine, nothing else
running:

| | tests | wall | slowest test |
|---|---|---|---|
| before (`5176c0c`) | 2250 | 181.0 s | 7.9 s, `test_fish_huts.py::PlacementTests` (a world build) |
| after TST-006.2 | 2138 | 21.2 s | 2.4 s, `test_victory.py::WeaponsTableTests` |
| after TST-006.3 | 2147 | **18.1 s** | 1.9 s, the same |
| final (after TST-006.4) | 2157 | **19.4 s** | 2.3 s, the same |

Before, the fifteen slowest were all world builds or booted runs, 3.5 to
7.9 s each (`test_spawn_fx.py::RunTests` alone had seven of them). After,
the slowest is `test_victory.py`'s weapons table (1.9 to 2.3 s, pure by both
the audit and the trace), then the audit's own read of the suite (1.3 s
setup), then spawn-director and cut-script checks around 1 s. The 18.1 /
19.4 s spread is run-to-run noise (10 more tests, all under 0.1 s): the
tier is **9 to 10 times faster**.

- `pytest.ini` and the conftest docstring say how to check the tiers.

---

## TST-007 — Requirement (owner, 2026-09-29)

**ID:** TST-007 · **System:** tests · **Type:** bug · **Status:** done ·
**Branch:** ComeGalletas/tst-007-ultrawide-font-init-83009add (stacked on
TST-006's branch; the session worktree `.claude/worktrees/busy-shtern-6bb78d`)

- **Objective:** `tests/screens/test_ultrawide.py::PanelsStayInTheBoxTests::
  test_a_level_up_draw_without_the_dim_leaves_the_margins_alone` passes when
  run on its own, not only after another test has booted a `Game`.
- **Details:**
  - Found in TST-006.4 (critic pass): run alone it fails with
    `pygame.error: font not initialized` from `LevelUpPanel.draw`. In a full
    run it passes only because `test_the_pause_buttons_are_centred_in_the_box_not_the_surface`
    sorts first in the class and boots a real `Game`, which initialises
    pygame's font module.
  - Give the test the setup it needs, the way the neighbouring pure tests
    in `tests/screens/` do (`pygame.display.init()`,
    `pygame.display.set_mode((64, 64))`, `pygame.font.init()` in
    `setUpClass`), without booting a `Game`.
  - Check the tier: `python -m tools.verification.tier_audit` reports 0
    under-tiered; if the test no longer needs a Game, decide whether it
    belongs in `unit` (its class is registered in `INTEGRATION`).
- **Constraint:** no `Game` boot added; the test keeps checking the same
  thing; nothing else in the module changes behaviour.

## TST-007 — Decisions

- **D1 — the test gets its own class, and falls to `unit`.** It builds a
  `LevelUpPanel` and draws it on a plain surface; it needs a display and
  the font module, never a `Game`. Left in `PanelsStayInTheBoxTests`, the
  class would stay whole in `INTEGRATION` (TST-006.D1: a mixed class goes
  whole to its highest tier), so adding a `setUpClass` there fixes the
  order dependence but keeps a pure test in the slow tier. Moved to
  `LevelUpPanelMarginTests`, which no tuple in `tests/conftest.py` names,
  so it is `unit`; `PanelsStayInTheBoxTests` keeps only the pause test,
  which boots a `Game` and stays `integration`. No conftest change.
- **D2 — the module's other pure tests stay where they are.**
  `DimCoversTheMarginsTests::test_level_up` and
  `ScreenBackdropTests::test_overlays_declare_no_backdrop_colour` ride up
  with booting classes (TST-006.D1) but each passes alone (checked); they
  are over-tiered, not order-dependent, and TST-006.D3 reports those
  rather than moving them.

## TST-007 — Plan

- `tests/screens/test_ultrawide.py`: `LevelUpPanelMarginTests` with a
  `setUpClass` that initialises the display and font modules; the test
  moves there unchanged.
- Verify: the test alone (fails before, passes after), the whole module,
  the module's `unit` slice (no Game in the process at all),
  `tier_audit` (0 under-tiered), `tests/devtools/test_tier_audit.py`.

## TST-007 — Todo

- [x] TST-007.1 — Move the level-up margin test into its own pure class
  with its own setup (D1).
- [x] TST-007.2 — Verify and close: runs, tier audit, index.

## TST-007 — Log

### 2026-09-29 — TST-007.1: the test gets its own class

- Before (`9cf0139`, run alone):
  `python -m pytest -p no:cacheprovider "tests/screens/test_ultrawide.py::PanelsStayInTheBoxTests::test_a_level_up_draw_without_the_dim_leaves_the_margins_alone"`
  → 1 failed, `pygame.error: font not initialized` from `pygame.sysfont`
  under `LevelUpPanel.draw`.
- After, the same test under its new node
  `tests/screens/test_ultrawide.py::LevelUpPanelMarginTests::test_a_level_up_draw_without_the_dim_leaves_the_margins_alone`:
  1 passed alone (0.5 s); `python -m unittest
  tests.screens.test_ultrawide.LevelUpPanelMarginTests` OK.

### 2026-09-29 — TST-007.2: verified, closed

- Whole module: 12 passed (the one warning, "no fast renderer available",
  is the dummy video driver in `game/display/window.py`, there before).
- Tiers: `-m unit` on the module selects `LongBackgroundStripTests` and
  `LevelUpPanelMarginTests` (2 passed); `-m integration` selects the other
  ten, `PanelsStayInTheBoxTests` now holding only the pause test.
- `python -m tools.verification.tier_audit`: 3480 tests read; 0
  under-tiered. `--over` listed three tests of this module before and lists
  two now (the D2 pair); the moved test is no longer over-tiered.
- `tests/devtools/test_tier_audit.py`: 30 passed, `SuiteTests` included.
- **Only the isolated run proves the fix.** With `setUpClass` deleted from
  the new class, the module's `unit` slice still passed: it runs
  `LongBackgroundStripTests` first, and the cut script it checks calls
  `pygame.init()` (`tools/asset_pipeline/cut_menu_background_long.py`).
  So any run with an earlier test in the process can hide this bug again;
  running the class or test alone is the check.
