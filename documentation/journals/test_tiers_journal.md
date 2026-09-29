# Test tiers — journal

**ID:** TST-006 · **System:** tests · **Type:** bug ·
**Status:** in progress · **Branch:** ComeGalletas/tst-006-tier-booting-tests-bb480b0c
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
- [ ] TST-006.3 — Split the five `world` modules that boot a Game (D2);
  the suite-wide "nothing under-tiered" test.
- [ ] TST-006.4 — `pytest.ini` note; before/after measurements; close.

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
