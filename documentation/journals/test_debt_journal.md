# Test debt — journal

**ID:** TST-004 · **System:** tests · **Type:** refactor ·
**Status:** in progress · **Branch:** claude/tst-004-test-debt (remote
session, owner 2026-09-24)

---

## TST-004 — Requirement (owner, 2026-09-24)

- **Objective:** Pay down the test debt recorded across the review and the
  journals.
- **Details:** Seven items, each with a source note: the digest test reads
  the same entry point as the digest writer (`test_suite_review.md` §1); the
  conditional skips become assertions or always-runnable checks
  (`cut_script_skips_journal.md`, `test_suite_review.md` §5); the worldgen
  R4 push-down of sweep assertions onto hand-built grids
  (`worldgen_modularity_todo.md`); the §6 organisation and §7 nits of
  `test_suite_review.md`; its balance-number audit (tests read tuning values
  from `data/` instead of hard-coding them); coverage for `world/gen/graph.py`,
  `world/gen/validate.py`, `village_tidy.py`, `mixer_backend.py` and
  `debug_overlay.py`, measured before and after; the WA5 summon render tests
  (`assets_journal.md`). The Bonepicker/Gaffjaw in-game screenshot (TST-004.9)
  stays with the owner's local session.
- **Constraint:** A parallel session is refactoring sprite blitting / death
  effects, the boss AI, enemy separation and the run-summary weapons table:
  leave `tests/**/test_enemy_sprite.py`, the boss tests and
  `tests/screens/test_victory.py` alone. Do not edit `INDEX.md` or any `data/`
  value. Game code changes only for a real bug a test exposes — and then stop
  on that item, describe it here and leave it pending. No CI, no declared
  `coverage` dependency, `sweep` only when asked.

## TST-004 — Confirmed reading

Filled per task as each is read, before its change.

### TST-004.2 — the digest tests

- `tests/world/test_digest.py` hashed `W.baked(seed)` / `W.layout(seed)` —
  the shared cached worlds of `tests/worlds.py` — while
  `python -m tools.verification.world_digest --write` hashes a fresh
  `GameMap(seed)` through `world_digests(seed)`. They agree today; nothing
  enforced it.
- **TST-004.D1 — One fresh build per seed, shared by the three pins.** The
  test now calls `digest.world_digests(seed)` once per seed (a module-level
  cache) and compares `layout`, `bake` and `draw` against `digests.json`. It
  also asserts that the pinned file, the writer's `SEEDS` and
  `tests/worlds.SEEDS` are the same set. The determinism test still compares
  the cached layout to a fresh one, so the shared world the rest of the suite
  reads is still tied to the pinned one. Cost: the module runs in 15 s.

### TST-004.3 — the conditional skips

`grep -rn "skipTest|skipIf|skipUnless|pytest.skip" tests` finds 18 live
sites in 12 modules (the `test_interactables.py:12` and `test_imp.py:224`
hits are prose). One subtask per module, the mixer pair together.

- **3.1** `test_elevation.py:136` skipped when `HEIGHTMAP_COAST_KEEP` was
  falsy; it is 2 in `game/config.py` and the room-overlap guarantee
  (`world/gen/placement.py:67`) depends on it, so the skip is now an
  assertion that the band is at least 1. The `if not room.grid: continue`
  under it was the retired flat world's guard and went with it.
- **3.2** `test_flying.py` skipped when the first blocking tree had no clear
  spot 40 px west, and (twice) when the world's top-left corner was not open
  sea. Both conditions hold on all four pinned seeds today (checked: the
  corner is sea on 35, 7, 1234 and 42; 186–255 trees have a clear approach).
  **TST-004.D2 — search, then assert.** The tree test takes the first
  blocking tree *with* a clear approach; a module helper `_open_sea(gm)`
  tries the corner, then 252 probes along the four edges, and fails if none
  is sea. A generator change moves the probe instead of retiring the test.
- **3.3** `test_npcs.py` boots `W.pinned(2)` (seed 1234). The aggro test
  skipped when none of twelve points three tiles past the lancer's aggro was
  clear of every lancer; the hero test skipped when no villager had open
  ground 20 px either side. Both find a spot on every pinned seed (run with
  `DEATHLITE_TEST_SEED` = 35, 7, 1234). The aggro search now also tries rings
  at five and eight tiles, and both end in an assertion.
- **3.4** `test_enemy_nav.py` already pins seed 1234 in `_playing`. The
  steering test skipped if none of three offsets from the player landed on
  the field; it now also tries 36 ring probes (160/240/320 px, every 30°)
  and fails if none does. The pocket test skipped if the small-class field
  held no unreached walkable cell beside a reached one; seed 1234 has one,
  so the skip is an assertion naming the seed.
- **3.5** `test_interactables.py` skipped the fountain test when the layout
  had no `fountain`. Since HI-1 the fountain is the village's sanctuary heal
  (`locations.py:52` builds one per village) and every world has a village
  (the forge test beside it already asserts that), so it is an assertion.
- **3.6** `test_ghost.py::test_a_kind_the_data_does_not_list_never_ghosts`
  hunted seed 7 for a skinned sign whose art no ghosting kind overlapped,
  and skipped without one. It is now built by hand on the module's own
  `_lone_tree` synthetic map (generalised to any obstacle kind and ghost
  list): one sign, the shipped `ghost.kinds` from `data/`, a body behind its
  foot → 0 ghost blits. Checked red: the same map with `sign` added to the
  kinds ghosts once.
- **3.7** `test_hostile_glow.py::test_alpha_is_steady_over_the_flight`
  fired a shot at the hero from 60 px, ran `update_projectiles` for half a
  second and skipped if the shot had hit something. `hostile_projectiles`
  (`visual/rendering.py:818`) reads only the shot's position and radius, so
  the shot is now aged by hand (life spent, `age` and position advanced)
  and the test asserts it is still live before comparing surfaces.
- **3.8** The four mixer skips fired when `AudioManager.enabled` was false.
  Both modules set `SDL_AUDIODRIVER=dummy` (setdefault) before pygame, and
  under the dummy driver `DesktopMixer.prepare` opens a 44100 Hz stereo
  device that plays nothing — checked: `enabled` is true with the variable
  exported and with it unset. So the mixer is always there under the suite,
  and the skips are assertions whose message names the driver in use. The
  `test_sound_effects.py` docstring claimed the mixing path was skipped
  under the dummy driver; it was rewritten. Only a machine that exports a
  *real* driver with no device behind it would fail these — that is a
  broken audio bring-up the test should report.
- **3.9** `test_element_colours.py::test_the_art_on_disk_is_what_the_tool_would_write_today`
  skipped without numpy. The test runs
  `tools.asset_pipeline.recolour_element_variants --check`, which reads the
  sheets through `pygame.surfarray` and so needs numpy; the game itself does
  not. The standing rule (`CLAUDE.md` §2, derived art keeps a `--check` a
  test runs) makes numpy a requirement of the suite, so a missing numpy is a
  failure that says `pip install numpy`. numpy 1.26.3 is installed here.
  **TST-004.D3 — for the owner:** the repo has no requirements file, so
  nothing declares numpy (or pygame). This session does not add one; if the
  owner wants the test environment written down, that is a separate call.
- **3.10** `test_native.py::test_the_window_wrapper_is_made_once_and_kept`
  skipped when `native._window()` found no SDL through ctypes. On Windows
  `ctypes.CDLL("SDL2.dll")` loads pygame's own copy, so it ran here; off
  Windows `find_library("SDL2")` cannot see a pip wheel's mangled bundled
  SDL and it skipped. The regression it pins (one kept `Window` wrapper —
  the 2026-09-15 dangling-pointer crash) is `_window`'s own Python, so it
  now runs against a stand-in library answering `SDL_GetWindowFromID` for
  pygame's real display window, on every platform. A second test asserts
  the real round trip on win32 (where the game ships) and, elsewhere, that
  `_window` answers a pointer or `(None, None)` — a branch, not a skip. The
  helper leaves the wrapper it made kept: dropping one is the crash itself.
- After 3.10, `grep -rn "skipTest|skipIf|skipUnless|pytest.skip" tests`
  finds only the two prose mentions.

### TST-004.4 — worldgen R4

R4 (`worldgen_modularity_todo.md`) asks for three things: audit the per-cell
sweeps for which need a *generated* world and which need only *a* grid,
convert the second kind to hand-built grids in the `unit` tier, and keep the
generated sweeps for what only they can prove.

What the tree does now: `tests/world/` is 343 tests, 2 min 56 s
(`--durations=40`, this session). The cost has moved since R4 was written —
the shared world cache (R1) removed the per-test rebuilds, and none of the
per-cell rule sweeps is in the slowest forty any more. The slow tests are
world builds and statistical checks (`test_repair.py::BuffBuildingCountTests`
33 s, `test_elevation.py::ScatterTests::test_both_nav_classes_can_use_every_flight`
11 s, the fresh-build digest pins 10 s), which are the generated-world kind
R4 says to keep. So this is R4 as a tiering and clarity change, not a speed
one. Every `tests/world/` module is `world` by path prefix, which also put
the hand-built rule tests that already existed in the slow tier.

The audit, for the modules with per-cell or hand-built rule checks:

| test | needs | outcome |
|---|---|---|
| `test_elevation` `CanCrossTests.test_a_diagonal_cannot_cut_the_corner_of_a_drop` | a grid (composition identity of `can_step`) | moved: `grids/test_steps.py` |
| `test_elevation` `CanCrossTests.test_the_endpoint_rule_is_load_bearing` | a grid (the corner beside a lateral head) | moved, now names the corner |
| `test_elevation` `CanCrossTests.test_a_level_change_needs_a_flight` | invariant over islands | kept; hand-built twin added |
| `test_elevation` `CanCrossTests.test_no_diagonal_ever_changes_level_between_two_terraces` | invariant over islands | kept; hand-built twin added |
| `test_elevation` `CanCrossTests.test_matches_walk_links_within_every_room` | mirror over every real cell (R3) | kept; hand-built twin added |
| `test_elevation` `FootStoneRuleTests` | already hand-built | moved: `grids/test_foot_stone.py` |
| `test_north_flights` `SiteRuleTests`, `LinkRuleTests` | already hand-built | moved: `grids/test_north_flight_rules.py` |
| `test_elevation` `ColliderTests`, `NavTests`, `ScatterTests`, `LateralCrossingEdgeTests`, `FootStoneTests` | a `GameMap`, the nav build or the generator's own placements | kept |
| `test_inset`, `test_pathfinding`, `test_repair` | the baked field, the nav grids, the repair pass over real layouts | kept (see below) |

- **TST-004.D4 — `tests/world/grids/`, tiered `unit` by an explicit list.**
  A new package beside the world tests holds the hand-built cases, with
  `scenes.py` drawing three one-room height maps in ASCII (a wall flight, a
  lateral crossing on a plateau flank, a north rim) and building the real
  `LevelIndex` over them. `tests/conftest.py` gains a `UNIT` tuple checked
  before `WORLD`, so the `tests/world/` prefix does not claim it.
- The moved endpoint check was seen red: with `diagonal_blocked` stubbed to
  `False` the corner test and the no-level-change test fail on the lateral
  scene's `(3, 1) -> (2, 2)`.
- Left for a later batch (recorded, not done): `test_inset.py` and
  `test_pathfinding.py` sweep baked fields and nav grids whose build needs a
  `GameMap`; a hand-built `GameMap` from a `scenes` layout is the next step
  if the owner wants the push-down carried further.

### TST-004.5 — §6 organisation, §7 nits

§6 lists six items and §7 four; §7's fourth (the balance numbers) is
TST-004.6. One subtask each, in the review's order.

- **5.1** `tests/flows/test_dev_mode.py` still defined `_settle()`, line for
  line `tests/boot.py::settle`; the copy is gone and its nine calls use the
  shared one. Module run: 63 passed.
- **5.2** Five modules (`test_summons`, `test_weapons`, `test_weapons_reach`,
  `test_weapons_special`, `test_manual_aim`) each defined a `FakeEnemy` that
  is only a position (plus `alive` in `test_summons`), and three a `FakeProj`
  bag of attributes. `tests/combat/fakes.py` already had a `FakeEnemy`, but
  a full one — hp, radius, status, ledger — that a damage path hits; putting
  that into the fire-path tests would change what targeting sees (radius).
  **TST-004.D5 — two new shared fakes, not one.** `fakes.FakeTarget` (a
  point, `alive = True`) and `fakes.FakeProj` sit beside `FakeEnemy`; the
  five modules import them and their local copies are gone. `tests/combat`
  + `test_manual_aim.py`: 624 passed.
- **5.3** `tests/screens/test_menu.py` was 1,076 lines, fifteen classes, nine
  of them the hero select. Split by subject: `test_menu.py` keeps the six
  title-screen classes (39 tests, 396 lines), the new
  `test_character_select.py` takes the nine (47 tests), and the four helpers
  both use (`_menu`, `_key`, `_mouse`, `_bright_pixels`) moved to
  `tests/screens/drive.py`, imported under their old names so no test body
  changed. The new module is listed in `conftest.INTEGRATION` beside
  `test_menu.py` (it boots a `Game`). Before 86 tests, after 39 + 47; the two
  modules and `test_dev_mode.py` together: 173 passed.
- **5.4** The six weapon modules were named for the plan phase that wrote
  them. Regrouped by the subjects §6 names, with `git mv` so history follows:

  | subject | module | was |
  |---|---|---|
  | roster / data | `test_weapon_roster.py` | `test_weapon_classes.py` + `CategoryTests` (`test_weapons_reach`) + `ProjectileSpreadDataTests` (`test_weapons`) |
  | fire path | `test_weapon_fire.py` | `test_weapons.py` + the seven reach-ring classes of `test_weapons_reach.py` |
  | special effects | `test_weapon_specials.py` | `test_weapons_special.py` |
  | blessings | `test_weapon_blessings.py` | `test_weapon_effects.py` |
  | the hammer's swing | `test_hammer_swing.py` | unchanged — one weapon's mechanics |

  `test_weapons_reach.py` is gone, its classes moved whole. The two modules
  that imported helpers from `tests.combat.test_weapons` (`make_context`,
  `BOLT`) import them from `test_weapon_fire`; `conftest.INTEGRATION` names
  `test_weapon_specials.py`. Test count unchanged: 9 + 20 + 18 before, 24 +
  23 after. `tests/combat` + `tests/playing/test_buffs.py`: 590 passed.
- **5.5** `tests/entities/ai/test_fsm_enemies.py` (4 tests) drove the
  shipped charger / teleporter / warlock enemies through a real `Enemy`;
  `test_ai_behaviors_fsm.py` (7) drives the same three behaviours on fakes.
  Not duplicates — one checks the behaviour, the other the shipped data
  wearing it — so the merge keeps both as the module's two halves, the
  real-`Enemy` half under its own section header with its helpers (`make`,
  `fs`, `ctx`) unchanged; no name collides with the fake half's `_enemy` /
  `_ctx`. Neither module is a boss test. 11 passed.
- **5.6** 56 module docstrings opened with the plan phase that wrote them
  (`Milestone 2:`, `Six-weapon system P3:`, `CB-5 group A:`, `R2 --`,
  `LD-9 D10:` …). Each now opens with its subject; the tag is dropped, and a
  parenthetical it carried that points somewhere useful — a design section
  (`design §20`) or a journal (`change request 1, weapon_system_journal.md`)
  — moves to the end of the first paragraph. Spec and design references
  already inside the sentence stay. 55 retitled by one script; the 56th,
  `tests/entities/ai/test_boss.py`, is left alone because the parallel boss
  refactor owns that file. The three chest modules that cite `(CB-9)` after
  their subject already read the way §6 asks. Collection unchanged (3,314
  tests + 8 sweep).
- **5.7** `test_one_multishot_upgrade_does_not_crash_any_weapon` (now in
  `test_weapon_roster.py`) computed `math.radians(spread) * (count - 1)` and
  threw it away; the `KeyError` it guards was only reachable in the data
  read. It now fires every weapon once through `Weapon.update` with one
  `projectiles` upgrade, a target at 60 px and a no-op summon hook, and for
  each projectile weapon asserts `count` shots fanned `spread_deg × (count −
  1)` edge to edge, `spread_deg` read from the data (bow, rod: 10°; bomb:
  16°). 23 passed, 9 subtests.
- **5.8** `tests/systems/test_events.py::test_clear_removes_everything`
  subscribed a no-op, cleared and published — nothing could fail. Two
  recording handlers on two events now, and the recorded list must be empty
  after `clear()`. 4 passed.
- **5.9** `tests/render/test_weapon_rigs.py::test_legacy_true_and_no_fx_keep_the_old_rig`
  pins what `cone.slash_rig` returns for `fx.slash: true` and for a shot
  with no `fx` — `soul_slash`, the current default, not a legacy path.
  Renamed `test_slash_true_or_no_fx_swings_the_default_soul_slash`, with a
  docstring saying so.

## TST-004 — Plan

One task per source note, in the order given; each is read first, its
current state recorded below, the change made, the covering tests run, and
the source note updated in place with a `*(TST-004, 2026-09-24: …)*` line.
The default suite (`python -m pytest -q`, sweep excluded) runs before the
last commit, and its counts go in Results with 0 skipped as the target.

## TST-004 — Tasks

- [x] TST-004.1 — This journal → `212e764`
- [x] TST-004.2 — Digest tests through `world_digests` → `f1e620f`
- [x] TST-004.3 — Remove the conditional skips
  - [x] TST-004.3.1 — `tests/world/test_elevation.py`: the dead void-band skip → `874f86f`
  - [x] TST-004.3.2 — `tests/entities/ai/test_flying.py` (3, seed) → `d76bed9`
  - [x] TST-004.3.3 — `tests/entities/test_npcs.py` (2, seed) → `d92dfef`
  - [x] TST-004.3.4 — `tests/playing/test_enemy_nav.py` (2, seed) → `0ce324e`
  - [x] TST-004.3.5 — `tests/playing/test_interactables.py` (1, seed) → `87086ac`
  - [x] TST-004.3.6 — `tests/render/test_ghost.py` (1, seed) → `fe87682`
  - [x] TST-004.3.7 — `tests/render/test_hostile_glow.py` (1, seed) → `7c1922a`
  - [x] TST-004.3.8 — `tests/systems/test_audio.py`, `test_sound_effects.py` (4, mixer) → `c616403`
  - [x] TST-004.3.9 — `tests/render/test_element_colours.py` (numpy) → `af7dc2a`
  - [x] TST-004.3.10 — `tests/display/test_native.py` (SDL through ctypes) → `d0e14a2`
- [x] TST-004.4 — Worldgen R4: push sweep assertions down to hand-built grids → `a292643`
- [x] TST-004.5 — The §6 organisation and §7 nits in `test_suite_review.md`
  - [x] TST-004.5.1 — §6: `test_dev_mode._settle` → `tests.boot.settle` → `7ed17ce`
  - [x] TST-004.5.2 — §6: one `FakeTarget` / `FakeProj` in `tests/combat/fakes.py` → `22c7a6b`
  - [x] TST-004.5.3 — §6: split `test_character_select.py` out of `test_menu.py` → `6c627e9`
  - [x] TST-004.5.4 — §6: regroup the six weapon modules by subject → `df68421`
  - [x] TST-004.5.5 — §6: merge `test_fsm_enemies` into `test_ai_behaviors_fsm` → `dbd372a`
  - [x] TST-004.5.6 — §6: retitle the modules that open with a plan phase → `13daf4f`
  - [x] TST-004.5.7 — §7: `test_one_multishot_upgrade_does_not_crash_any_weapon` asserts → `631043e`
  - [x] TST-004.5.8 — §7: `test_clear_removes_everything` observes the handler → `d618e61`
  - [x] TST-004.5.9 — §7: rename `test_legacy_true_and_no_fx_keep_the_old_rig`
- [ ] TST-004.6 — The balance-number audit in `test_suite_review.md`
- [ ] TST-004.7 — Coverage for `world/gen/graph.py`, `world/gen/validate.py`,
  `village_tidy.py`, `mixer_backend.py`, `debug_overlay.py`
- [ ] TST-004.8 — Summon render tests (WA5)
- [ ] TST-004.9 — Bonepicker/Gaffjaw in-game screenshot — local session

## TST-004 — Results

Pending.
