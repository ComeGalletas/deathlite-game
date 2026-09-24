# Test suite review — 2026-09-11

A survey of `tests/` for dead weight and coverage gaps, and the record of what
was done about it. Sections 1–3 are complete; §4 is half done; §5–§7 are still
open.

## Where it started, and where it is now

Measured on `main` with the weapon-rework working tree in place.

| | before | after |
|---|---|---|
| Test functions | 1,633 | 1,644 (1,634 pass, 2 skip, 7 sweep) |
| Default run (`python -m pytest`) | 10 min 30 s | 8 min 21 s |
| **Fastest useful run** | — none — | **`-m unit`: 760 tests, 10 s** |
| Statement coverage, shipping code | 91.3 % | **92.2 %** |
| Headline number incl. dev tooling | 85.8 % | n/a — omitted by `.coveragerc` |
| Runtime statements | 14,875 | 14,750 (dead code removed) |
| Statements missed | 1,294 | 1,144 |
| Duplicate / shadowed test names | 0 | 0 |

Coverage needs `coverage` (7.16 here), installed by hand during this review; it
is still not a declared dependency. `.coveragerc` carries the commands.

The suite was in good shape to begin with. The docstrings explain *why* each
thing is pinned rather than restating the assertion, `tests/worlds.py` had
already solved the world-rebuild problem, and there was no test-name shadowing
or copy-paste rot. What had accumulated was **drift**: tier markers that no
longer described what the tests did, and tests the retired flat generator left
behind pinning branches that could no longer execute.

### Coverage by package (after)

| package | stmts | miss | cover |
|---|---:|---:|---:|
| `systems` | 442 | 84 | 81.0 % |
| `game` | 4,694 | 512 | 89.1 % |
| `world` | 5,318 | 379 | 92.9 % |
| `progression` | 620 | 30 | 95.2 % |
| `entities` | 1,652 | 74 | 95.5 % |
| `spawn` | 951 | 39 | 95.9 % |
| `combat` | 688 | 18 | 97.4 % |
| `ui` | 385 | 8 | 97.9 % |
| **total** | **14,750** | **1,144** | **92.2 %** |

---

## 1. The bake digest — RESOLVED

*An earlier draft of this section diagnosed the bake digest as
context-dependent, on the strength of three runs that produced three different
hashes. That was wrong: the three runs were taken hours apart while
`game/config.py` was being edited, so they measured three different trees, not
three contexts. The bake digest is deterministic — standalone, in a full suite
run, and from the CLI it produces byte-identical values, field for field across
all fifteen `_BAKE_FIELDS`.*

The real cause was a one-line config change. `CAMERA_ZOOM` went from 1.5 to 1.7,
and `world/terrain/bake.py:70` sizes the baked water buffer from
`SCREEN_WIDTH / CAMERA_ZOOM`, so the bake digest moved for every seed while
`layout` (pure generation, no display or scale) stayed put — exactly the shape
of the diff `digests.json` was carrying.

The same change broke the whole-pixel invariant that
`tests/systems/test_camera.py:114` pins: `64 × 1.7 = 108.8 px`, and a tile
grid on fractional boundaries shimmers at the seams.

**Done**

- [x] `CAMERA_ZOOM` set to **1.75** — the nearest value to the intended 1.7 that
      keeps a whole-pixel tile (`64 × 1.75 = 112`). `game/config.py` now carries
      the constraint and the legal steps (0.25) as a comment next to the value.
- [x] `digests.json` re-pinned with `python -m tools.verification.world_digest --write`. Seed 42's
      `draw` moved too, as the visible extent changed.
- [x] `tests/render/test_gem_glow.py::test_glow_breathes_on_the_gems_own_age`
      fixed. It separated halos from orbs with a hard-coded `width > 12` pixel
      threshold; a tier-0 orb is 8 world px, so at zoom 1.5 it drew exactly 12 px
      and the rule worked by luck. It now selects on the renderer's own
      `_glow.diameter(8, zoom)`, as its sibling test already did, and is
      zoom-independent.

### The loading-screen warm test — also fixed

`tests/flows/test_loading.py::test_the_view_is_warmed_before_the_run_starts` was
order-dependent: it passed alone and failed after a few hundred other tests.

Both foam and scenery pick their animation frame from
`TerrainRenderer.seconds()`, which falls back to `pygame.time.get_ticks()` —
process uptime. `LoadingState._warm_steps` samples three fixed phases
(`_WARM_FOAM_PHASES`), so whether the run's first draw landed on an
already-scaled frame depended on how long the process had been up. Measured
across seven clock values, the first draw added between 0 and 5 entries, every
one of them a foam or decor frame — never a terrace band or the water buffer,
which is the 62 ms work the warming exists to remove.

- [x] The test now pins `gm.renderer.clock` to a phase the warm ring covered
      before the first draw, so it measures the warming rather than the wall
      clock. No product change. *(RND-005, 2026-09-24: no longer pinned — every
      animation frame is warm now, so the test draws at five phases, ones the
      ring never drew among them, and asserts the cache does not grow at all.)*

**Worth deciding separately (not done):** in a real run the first frame *does*
land on an arbitrary phase, so it still scales a handful of small animation
frames. Warming every animation frame the world holds would remove that
entirely, at +190 cache entries / ~28 MB on top of the ~142 MB the ring already
holds at zoom 1.75. Probably not worth it for the desktop build and likely wrong
for the pygbag web build, but it is a real (small) first-frame cost and the
choice is yours. Warming just the 16 foam frames would be nearly free and covers
the most common case, since water is on screen continuously.

*(DOC-005, 2026-09-24: **decided by the owner — warm every frame that can be
warmed.** Taken up as **RND-005**, `journals/frame_warmup_journal.md`, the
session's next goal.)*

### Still open, smaller

*(DOC-005, 2026-09-24: still **pending** — `tests/world/test_digest.py` still hashes `W.baked(seed)` where the writer uses `world_digests`.)*
*(TST-004, 2026-09-24: done — the three pin tests read `digest.world_digests(seed)`, one fresh build per seed shared between them, and a new test asserts the suite, the writer and `digests.json` pin the same seeds; `test_debt_journal.md`, TST-004.2.)*

- [x] `test_the_bake_is_pinned` and `test_the_frame_is_pinned` hash
      `W.baked(seed)` — the *shared cached* world from `tests/worlds.py`, baked
      under whatever ambient config the first caller happened to have — while
      `python -m tools.verification.world_digest --write` hashes a fresh `GameMap`. They agree
      today, and the shared build is a default build, so this is latent rather
      than broken. But nothing enforces it. Worth having the test go through
      `digest.world_digests(seed)`, the same entry point as the writer, so the
      pinned file and the assertion cannot drift apart.

---

## 2. The tier contract — DONE

`pytest.ini` documented `unit` as "nothing generated; hand-built grids and
fakes. Every save", but 24 modules marked `unit` were building worlds or booting
a real `Game`, so the tier meant to run on every keystroke was as slow as the
whole suite. There was no fast inner loop at all.

Splitting on what a module actually costs gives a clean three-way division —
21 modules boot a `Game` and drive its states, 3 more only read the shared
cached worlds and belonged in `world` all along:

| tier | what it does | tests | time |
|---|---|---:|---:|
| `unit` | hand-built grids and fakes | 760 | **10 s** |
| `world` | the four cached worlds in `tests/worlds.py` | 483 | 2 min 45 s |
| `integration` | boots a real `Game` and drives its states | 380 | 5 min |
| `sweep` | many seeds, statistical | 7 | 2 min 8 s |

- [x] `integration` marker added to `pytest.ini` and `tests/conftest.py`, with
      `test_aggro`, `test_flying` and `test_hazard_sprite` moved into `world`.
      The default `pytest` still runs everything but `sweep`, so nothing about
      the pre-commit check changes.
- [x] README updated with the tier table and the `-m unit` command, and its
      stale "863 tests" count (in two places) corrected to 1,630.

**Still worth doing:** `tests/flows/test_dev_mode.py` is 63 tests driving ~40 full
boots through the menu and loading screen on an unpinned seed, and is most of
what makes `integration` five minutes. Pointing it at a pinned seed and reusing
one booted run per test class would cut the bulk of it — most of its tests are
menu-row assertions that do not need a fresh world each.

---

## 3. Legacy left by the retired flat generator — DONE

Three test classes existed only to pin the grid-less room fallback, each with a
matching dead branch in the source.

Verified unreachable before deleting anything: across **12 seeds, 108 rooms and
all eight room kinds**, every room has a grid, a palette and cells; and
`GameMap()` (the layout-less map used by non-run tests) has no layout at all, so
it produces no rooms. No room without a grid can exist.

- [x] `tests/world/test_decor_frontiers.py` `LegacyPathTests` → the grid-less
      arm of `world/rules/frontier.py:interior_cells`. The surviving
      no-cells case is kept as `EmptyRoomTests`.
- [x] `tests/render/test_biome.py::test_a_room_with_no_height_map_stays_one_group`
      → `not room.grid` dropped from `world/terrain/decor/budget.py:_cell_biomes`.
      The `not room.palette` guard stays: it is a different condition and still
      the documented contract, so the test was kept and renamed
      `test_a_room_with_no_palette_stays_one_group`.
- [x] `tests/world/test_inset.py::test_a_room_without_a_grid_answers_clear` →
      `not room.grid` dropped from `world/rules/inset.py:build`, test renamed
      `test_a_room_with_no_cells_answers_clear`.
- [x] `world/terrain/decor/scatter_water.py` — the `if not room.grid: continue`
      skip.
- [x] `world/terrain/autotile.py::slot_for()` — dead by its own docstring
      ("currently unused — `mask_slot` superseded it"), reachable only through
      the unused alias in `world/map.py`. Both deleted; 19 of that module's 21
      uncovered statements.
- [x] `game/config.py` `COLOR_GRID` — `world/terrain/render.py` keeps its own
      module-local fallback palette and inlines the same literal, so the config
      constant was a leftover.
- [x] `tests/world/test_pathfinding.py` `_SAVED_VERT` — assigned, never read.

The world digest is unchanged by all of this, which is the proof the deletions
were behaviour-preserving rather than merely test-passing.

### Stale prose — DONE

- [x] Six docstrings citing the deleted `test_procedural.py` /
      `test_verticality.py`, or describing the flat world as a live
      configuration: `test_digest.py`, `test_layout.py`, `test_elevation.py`,
      `test_pathfinding.py`, `test_water_decor.py` (which claimed to pin a
      `HEIGHTMAP_ROOMS` flag that no longer exists), and
      `test_projectile_elevation.py` (where the case is still live and only the
      prose was wrong).
- [x] Three orphaned `.pyc` files under `tests/world/__pycache__/`.

---

## 4. Coverage gaps worth closing

At 91.3 % the gaps are narrow and specific. In priority order:

- [x] **`game/states/game_over_state.py` — was 0 % (35 stmts).** The death
      summary was completely untested; `test_dev_mode.py` only asserted that a
      *dev* run never opens one. `tests/screens/test_game_over.py` now covers
      it — 11 tests in 0.2 s, in the `unit` tier, on a fake game rather than a
      booted one (the states it hands off to do their work in `enter`, which a
      recording state machine never calls). Includes the death-at-zero-seconds
      case, where the per-minute and dps rates divide by the survival time.
- [x] **`game/states/meta_state.py` — 22.5 % (86 missed).** Meta-progression
      screen. The same fake-game approach should reach most of it. *(DOC-005: 89.0 % in the 2026-09-22 coverage run — the Sanctuary mouse tests and the screen tests reach it)*
- [x] **`game/states/victory_state.py` — 31.4 %.** Win path. *(DOC-003: `tests/screens/test_victory.py` (42 tests) landed 2026-09-12; coverage not re-measured)*
- [ ] **`world/gen/village_tidy.py` — 67.8 %** and **`game/states/playing/slam_fx.py`
      — 70.8 %.** Both new in the current working tree; worth topping up before
      the rework lands rather than after. *(DOC-005, 2026-09-22 run: `slam_fx` is at 98.5 % — done; `village_tidy` rose to 79.9 % and is the half still open)*
- [ ] **`world/gen/graph.py` — 61 %**, **`world/gen/validate.py` — 75 %**,
      **`world/gen/height/graph.py` — 80.8 %.** Generation-stage validation is
      exactly the code a pinned-digest suite cannot check. *(DOC-005, 2026-09-22 run: `world/gen/graph.py` 59.7 %, `validate.py` 75.0 % — no better; still open)*
- [ ] **`systems/mixer_backend.py` — 45.5 %** and **`systems/debug_overlay.py` —
      52.8 %.** Lower value; the mixer is partly environment-gated by design. *(DOC-005, 2026-09-22 run: `mixer_backend` 65.5 %, `debug_overlay` 52.8 %; still open, still lower value)*

### Exclude the tooling from the number — DONE

`tools/asset_pipeline/` (1,489 LOC: `sprite_sheet_lab`, `build_ground_tilemaps`,
`key_sheet`, `prep_vstairs`, `slice_tree_sheet`) is imported by **no** runtime
module, and `spawn/stress.py` (94 stmts) is a `python -m` CLI harness. Together
they accounted for the whole gap between the headline 85.8 % and the real
91.3 %.

- [x] `.coveragerc` added: sources the eight runtime packages, omits
      `tools/*` and `tools/benchmarks/spawn_stress.py`, and carries the run/report commands
      in a comment at the top.
- [x] `.coverage`, `.coverage.*` and `htmlcov/` added to `.gitignore`.
- [-] Still open: decide whether `coverage` becomes a declared dev dependency. *(DOC-003: decided by the owner 2026-09-22: no — `coverage` is a test-only tool, run by hand with `.coveragerc`, never a declared dependency)*
      It is currently just `pip install coverage` by hand — the `.coveragerc`
      header says so, but nothing installs it.

---

## 5. Self-disabling tests

25 sites call `skipTest(...)` when the generated world does not happen to contain
the feature under test — `"no shrine in this layout"`, `"no villager standing in
the open on this seed"`, `"no open sea at the world's corner on this seed"`.
Today only 2 actually skip, but a generation change can silently retire any of
them without a single failure.

Concentrated in `tests/playing/test_interactables.py` (6), `tests/entities/ai/test_flying.py`
(3), `tests/entities/test_npcs.py` (2), `tests/playing/test_enemy_nav.py` (2), and
`tests/render/test_biome.py` (7, all `"tileset missing"`).

**Todo**

*(TST-004, 2026-09-24: done — the last 18 conditional skips (seed-dependent, mixer, numpy, SDL through ctypes, the dead void band) are assertions, hand-built cases or always-runnable checks; TST-004.3 in `test_debt_journal.md`. No live `skipTest` is left in `tests/`.)*

- [x] For the layout-content skips, search the four pinned seeds for one that has *(DOC-003: interactables fixed (`test_interactables.py`); the seed-dependent skips left are listed in `cut_script_skips_journal.md` (TST-002, *Follow-up candidates*))*
      the feature and assert it is found, rather than skipping. `tests/worlds.py`
      makes this nearly free.
- [x] For `"tileset missing"`, decide whether a missing tileset should be a *(DOC-003: decided by the owner 2026-09-22 — yes, a missing tileset fails; done as TST-003, `925502c`)*
      failure. The game ships the assets; a silent skip hides a broken checkout.
- [-] Add a CI-style check (or a line in the commit checklist) that the run *(DOC-003: superseded — the owner rules out CI and gates; the standing rule "a test never skips itself to green" (`CLAUDE.md` §2) covers it)*
      reports 0 skips, so a new conditional skip has to be deliberate.

---

## 6. Duplication and organisation

- [ ] `tests/flows/test_dev_mode.py:38` defines `_settle()`, a verbatim copy of
      `tests/boot.py::settle`. 17 other modules import the shared one. Delete the
      copy.
- [ ] Six `FakeEnemy` and three `FakeProj` definitions are scattered across
      `test_manual_aim`, `test_summons`, `test_weapons`, `test_weapons_reach` and
      `test_weapons_special`, although `tests/combat/fakes.py` is the designated
      home. Consolidate.
- [ ] `tests/screens/test_menu.py` is 952 lines and two subjects — 9 of its 15 *(DOC-003: now 1,076 lines)*
      classes are character-select. Split out `test_character_select.py`.
- [ ] The six weapon modules are keyed by the plan phase that produced them
      (`test_weapons` = Milestone 2, `test_weapons_special` = Milestone 4,
      `test_weapons_reach` = CB-2, `test_weapon_classes` = P1,
      `test_weapon_effects` = P2, `test_hammer_swing` = change request 1) rather
      than by concern. Now that the six-weapon rework is landing, regroup by
      subject: roster/data, fire path, special effects, blessings.
- [ ] `tests/entities/ai/test_fsm_enemies.py` (Milestone 9) and
      `tests/entities/ai/test_ai_behaviors_fsm.py` both cover charger / teleporter /
      warlock. Merge.
- [ ] 50 modules open with the plan phase they were written in (`"""Milestone 2:`, *(DOC-003: 39 modules still open with a phase tag (was 50))*
      `"""R4 --`, `"""CB-2:`, `"""LD-9 phase D7:`). Those plans are done; retitle
      by subject and keep the phase reference only where it explains *why* a
      thing is pinned.

---

## 7. Small, specific

- [ ] `tests/combat/test_weapons.py:128`
      `test_one_multishot_upgrade_does_not_crash_any_weapon` ends on a computed
      expression that is discarded (`math.radians(...) * (count - 1)`). The
      `KeyError` guard is real but invisible; make it an explicit assertion or
      drive the actual fire path.
- [ ] `tests/systems/test_events.py:26` `test_clear_removes_everything` subscribes a
      handler, clears, publishes — and never observes that the handler did not
      fire. Record calls and assert the list is empty.
- [ ] `tests/render/test_weapon_rigs.py:137`
      `test_legacy_true_and_no_fx_keep_the_old_rig` — `soul_slash` is the current
      default for a cone weapon with no visuals entry, not a legacy path. Rename.
- [ ] ~38 assertions across 20 modules pin exact balance numbers from the data
      JSONs (`aegis.stats["max_hp"] == 160`, `H["damage"] == 25`). Audit them:
      where the number is a contract, keep it; where it is tuning, assert the
      invariant (ordering, ratio, range) so a balance pass does not report a bug.
- [x] README says **863 tests** in two places (the "Run the tests" section and the *(DOC-003: no "863" left in `README.md`; §2 already records it)*
      tree at the bottom). Actual is 1,633.

---

## Where this stands

Done: **§1** (the digest), **§2** (the tier split), **§3** (the
retired-generator tests and their dead branches), and the structural half of
**§4** (`.coveragerc`, `.gitignore`, and the `game_over_state` hole).

Left, in the order worth taking them:

1. **§4, remaining gaps** — `meta_state.py` (22.5 %), `victory_state.py`
   (31.4 %), then `village_tidy.py` and `slam_fx.py` while the weapon rework is
   still in hand.
2. **§2 follow-up** — `test_dev_mode.py`'s ~40 boots are most of the five-minute
   `integration` tier.
3. **§5** — the 25 self-disabling `skipTest` sites.
4. **§6–§7** — duplication, module splits, and the brittle value assertions.

---

*Working note: this review left an untracked `.coverage` data file in the repo
root. `python -m coverage html` will turn it into a browsable report; delete it
otherwise.*

---

## 8. Folder reorganisation — DONE (2026-09-12)

The old folders mixed three axes: the package under test (`spawn`,
`progression`), the concern (`rendering`, `combat`) and the phase the tests were
written in (`core`, `characters`). Modules now live by the runtime code they
exercise, with one folder for the tests that drive whole flows through a
booted `Game`. 94 modules moved with `git mv`; 41 stayed.

| folder | what it covers | modules |
|---|---|---:|
| `combat/` | `combat/*` — damage, status, knockback, synergy, the weapons and their forgings | 15 |
| `entities/` | `entities/*` — player, pickup, NPCs; `entities/ai/` for the AI scaffold, behaviours, bosses and flyers | 6 + 12 |
| `progression/` | `progression/*` | 10 |
| `spawn/` | `spawn/*`, plus the no-layout spawn geometry (`test_spawning`) | 9 |
| `world/` | `world/*` — generation, rules, pathfinding, digest, layering | 21 |
| `playing/` | `game/states/playing/core` — aim, hit resolution, bumping, effects, nav wiring, ledger, gold, chests, potions, interactables | 10 |
| `render/` | `game/states/playing/visual` and the terrain renderer — projectiles, summons, glow, depth sort, terrain, biome, sprites | 16 |
| `screens/` | the menu, select, pause, level-up, options, end and run-status states and `ui/*` | 18 |
| `systems/` | `systems/*` plus `game/{assets,fonts,save,events,state}` | 10 |
| `flows/` | boots a real `Game` and walks its states — smoke, loading, dev mode, hero unlock, controls, LOD, window | 7 |
| `devtools/` | the training-dummy DPS meter and its bench arena | 1 |

`tests/worlds.py`, `boot.py`, `aictx.py`, `nearby.py`, `combat/fakes.py`
and `spawn/fakehost.py` stay where they were; `world/digests.json` and
`spawn/director_sequence.json` stay beside the modules that read them.

**What had to follow.** `tests/conftest.py`'s tier lists were repathed, and
`test_npcs` / `test_interactables` — which the old `tests/world/` prefix had
placed in `world` — are now listed there by name so their tier does not change.
`test_ghost` and `test_render_cull` import `fresh_playing` from
`test_depth_sort`, now under `tests.render`. `test_melee_enemies` builds the
repo root from its own path and moved one folder deeper (`parents[3]`). Path
mentions in code comments, `README.md`, `world/README.md` and
`designs/sprite_functionality.md` were rewritten; journals keep the old paths.

**Not done here, still open.** The six phase-keyed weapon modules were moved
into `combat/` unmerged (§6). The four negative tests that pin the absence of
long-removed code (`RETIRED` in `test_weapon_classes`,
`heightmap_floor_sheets` in `test_biome`, `three_slice_h` in `test_menu`,
`draw_room_clutter` in `test_decor_frontiers`) are still there.

### Tier drift fixed — DONE (2026-09-12, same day)

The six modules that booted a `Game` or read the cached worlds while tiered
`unit` are now where they belong: `test_bomb`, `test_chest_open`,
`test_potion_drops`, `test_window` and `test_hero_select_preview` in
`integration`, `test_boss_pig_rider` in `world`. A scan of every `unit`
module for `Game(`, `tests.boot` or `tests.worlds` now comes back empty.

`test_chests::CountingRuleTests::test_the_average_island_carries_two_to_three`
generates forty worlds for one mean (61 s, the slowest test in the suite)
and is now `sweep`; the per-seed caps and floors in the same class stay in
`world`. The two `test_master::PackTests` (38 s and 26 s) were listed
alongside it as statistical, which on a closer read they are not: each
simulates sixty seconds of one deterministic run to check a placement
guarantee. They stay in the default run; the honest way to make them cheaper
is a shorter simulation, which is a change to the tests themselves.

| tier | before | after |
|---|---:|---:|
| `unit` | 1,260 tests, 1 min 55 s | 1,133 tests, 50 s |
| `world` | 501 | 525 |
| `integration` | 401 | 503 |
| `sweep` | 7 | 8 |

**Where the suite's time goes** (durations run, 2026-09-12, 835 s total):
`flows/test_dev_mode.py` 172 s (21 %), `world/test_chests.py` 84 s,
`spawn/test_master.py` 64 s, `playing/test_chest_open.py` 50 s.
