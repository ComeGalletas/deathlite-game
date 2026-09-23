# Cut-script test skips — journal

**ID:** TST-002 (+ TST-003) · **System:** tests (+ RND) · **Type:** bug ·
**Status:** done · **Branch:** claude/optimistic-poincare-e34af9
(existing worktree, rebased onto `claude/reaction-damage-rework` so the
DOC-001 index and `CLAUDE.md` §1 are present — owner's choice, 2026-09-22)

---

## TST-002 — Requirement (owner, 2026-09-22)

- **Objective:** Make the three cut-script tests assert that their script's
  `--check` passes, instead of skipping when the script reports its source
  sheet missing.
- **Details:** `tests/render/test_spawn_fx.py`, `test_totem_bolt.py` and
  `test_totem_sprite.py` call `skipTest` when `cut_spawn_sheet.py`,
  `cut_totem_bolt_sheets.py`, `cut_totem_sheets.py` or
  `recolour_totem_fire.py` exits 2 (source in neither its folder nor its
  `unused/` archive). Check each source sheet's git tracking and `.gitignore`
  status, make the sources available in every clone and worktree, and assert
  exit code 0. Model: `914039e` and
  `tests/entities/ai/test_imp.py::test_the_editor_source_is_archived_and_not_shipped`.
- **Constraint:** A test never skips itself to green. Scope is the cut-script
  tests only; the other conditional skips are listed below as follow-up
  candidates, not changed.

## TST-002 — Confirmed reading

Each source was checked with `git ls-files` and `git check-ignore -v` in the
main checkout, and every script's `--check` was run in this worktree (a fresh
checkout that holds only tracked files):

| script | source | tracked path | ignored? | `--check` in worktree |
|---|---|---|---|---|
| `cut_spawn_sheet.py` | `77.png` | `assets/effects/spawn/unused/77.png` | no | 0 |
| `cut_totem_bolt_sheets.py` | `proyectile.png` | `assets/effects/weapons/grave_totem/proyectile.png` | no | 0 |
| `cut_totem_sheets.py` | `Fire_Totem_blue-Sheet.png` | `assets/effects/weapons/grave_totem/unused/Fire_Totem_blue-Sheet.png` | no | 0 |
| `recolour_totem_fire.py` | `fire.png` | `assets/effects/weapons/grave_totem/fire.png` | no | 0 |

The copies that *are* ignored (`assets/unused/unordered-effects/Part 2/77.png`,
`assets/unused/effects/fire.png`) sit in the reserve library, which the scripts
do not read. Unlike the imp's `.aseprite` in `914039e`, nothing here is hidden
by `.gitignore`: the per-folder `unused/` archives under `assets/effects/` are
tracked, so all four sources already reach every clone and worktree.

- **TST-002.D1** — No `.gitignore` change. The sources are already tracked and
  not ignored; the fix is only in the tests.
- **TST-002.D2** — The tests assert `code == 0` and nothing more. A zero exit
  already proves the source is present (exit 2) and that the committed strips
  match a fresh cut (exit 1). A separate `git ls-files` check would need git at
  test time, which a packaged or exported copy does not have. The assertion
  message names the script so a failure says which source went missing.

## TST-002 — Plan

Replace each `if code == 2: self.skipTest(...)` with an assertion of exit 0,
and rewrite the docstrings that justified the skip to say why the assertion
now holds everywhere. One task per test module, then the results.

## TST-002 — Tasks

- [x] TST-002.1 — Open this journal and move the index row to in progress
- [x] TST-002.2 — `test_spawn_fx.py`: assert `cut_spawn_sheet --check` exits 0 → `e87dbdd`
- [x] TST-002.3 — `test_totem_bolt.py`: assert `cut_totem_bolt_sheets` and
  `recolour_totem_fire --check` exit 0 → `5dbfff0`
- [x] TST-002.4 — `test_totem_sprite.py`: assert `cut_totem_sheets --check`
  exits 0 → `29508e9`
- [x] TST-002.5 — Run the affected tests, record results, mark the index row done

## TST-002 — Follow-up candidates (not in scope)

Other conditional `skipTest` calls found by `grep -rn skipTest tests`. The four
the owner named come first; the rest turned up in the same sweep.

- `tests/entities/ai/test_flying.py:159, 258, 274` — seed-dependent (no clear
  approach to a tree, no open sea at the corner)
- `tests/entities/test_npcs.py:225, 287` — seed-dependent (no spot clear of
  lancer aggro, no villager in the open)
- `tests/playing/test_enemy_nav.py:137, 307` — seed-dependent (no probe on the
  field, no field pocket)
- `tests/display/test_native.py:32` — SDL not reachable through ctypes
- `tests/playing/test_interactables.py:108` — no fountain in this layout
- `tests/render/test_biome.py:211, 229, 242, 257, 274, 297, 596` — tileset missing
- `tests/render/test_element_colours.py:393` — numpy not installed
- `tests/render/test_ghost.py:124` — no skinned sign clear on this seed
- `tests/render/test_hostile_glow.py:83` — shot expired or hit something
- `tests/systems/test_audio.py:60, 69` and `test_sound_effects.py:157, 221` —
  mixer unavailable
- `tests/world/test_elevation.py:136` — no void band configured

## TST-002 — Results

- `tests/render/test_spawn_fx.py`, `test_totem_bolt.py`, `test_totem_sprite.py`
  together: **42 passed, 46 subtests passed, 0 skipped** (was: the three
  cut-check tests skip in any checkout missing a source). Each module was also
  run on its own before its commit: 13, 16 (+2 subtests), 13 (+44 subtests).
- No `.gitignore` or asset change was needed (TST-002.D1): all four sources
  were already tracked, and every `--check` exits 0 in this worktree.
- Deferred: the conditional skips listed under *Follow-up candidates*, per the
  requirement's scope.

---

## TST-003 — Requirement (owner, 2026-09-22)

- **Objective:** Make a missing tileset fail the biome tests instead of
  skipping them.
- **Details:** The seven `skipTest("tileset missing")` calls in
  `tests/render/test_biome.py` become assertions that the tileset loaded,
  with a message naming what is missing.
- **Constraint:** Decided by the owner under the never-skip-to-green rule
  (`test_suite_review.md` §5). Only the tileset skips; the seed-dependent
  skips in *Follow-up candidates* above stay out of scope.

## TST-003 — Confirmed reading

- Six skips (lines 211, 229, 242, 257, 274, 297) guard on
  `TileSheets(get_assets(), layout.seed).ok` in `_sheets(21)`; the seventh
  (596) guards on `W.baked(41)._tiles_ok`. `ok` is true when `floor_sheet`
  is a string and its probe tile loads (`world/terrain/sheets.py:69`);
  `_tiles_ok` is the baked map's `terrain.ok` (`world/map.py:415`).
- The sheets they need — `data/world/terrain.json` `floor_sheet`
  `terrain/tiles/tilemaps/tilemap_1.png` and its siblings — are tracked in
  git, so in a healthy checkout the skip never fires; it could only hide a
  broken one.
- **TST-003.D1 — One helper, not seven asserts.** A module-level
  `_require_tiles(ok, what)` that fails with the sheet path read from
  `terrain.json`, so the message says which file is missing.

## TST-003 — Plan

`tests/render/test_biome.py` only. Run `tests/render/test_biome.py`, then the
`render` folder and the world tier, before committing.

## TST-003 — Tasks

- [x] TST-003.1 — Replace the seven skips with the shared assertion
- [x] TST-003.2 — Run the biome module, `tests/render` and `tests/world`; record the counts
- [ ] TST-003.3 — Tick `test_suite_review.md` §5, results, index to done

## TST-003 — Results

- `tests/render/test_biome.py`: **37 passed, 5 deselected** (the sweep tier),
  0 skipped — the seven checks that could skip now always run.
- `tests/render` + `tests/world`: **758 passed, 8 deselected, 623 subtests
  passed, 0 skipped** (5 min 9 s). The 23 warnings are the headless
  "no fast renderer available" from `game/display/window.py:132`.
- The failure path was exercised by hand: `_require_tiles(test, False)`
  fails with `tileset missing: <assets>/terrain/tiles/tilemaps/tilemap_1.png
  did not load`.
- Commit: `925502c` (TST-003.1).
