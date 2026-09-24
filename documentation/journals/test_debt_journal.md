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

## TST-004 — Plan

One task per source note, in the order given; each is read first, its
current state recorded below, the change made, the covering tests run, and
the source note updated in place with a `*(TST-004, 2026-09-24: …)*` line.
The default suite (`python -m pytest -q`, sweep excluded) runs before the
last commit, and its counts go in Results with 0 skipped as the target.

## TST-004 — Tasks

- [x] TST-004.1 — This journal → `212e764`
- [x] TST-004.2 — Digest tests through `world_digests` → `f1e620f`
- [ ] TST-004.3 — Remove the conditional skips
  - [x] TST-004.3.1 — `tests/world/test_elevation.py`: the dead void-band skip → `874f86f`
  - [x] TST-004.3.2 — `tests/entities/ai/test_flying.py` (3, seed) → `d76bed9`
  - [x] TST-004.3.3 — `tests/entities/test_npcs.py` (2, seed) → `d92dfef`
  - [x] TST-004.3.4 — `tests/playing/test_enemy_nav.py` (2, seed) → `0ce324e`
  - [x] TST-004.3.5 — `tests/playing/test_interactables.py` (1, seed) → `87086ac`
  - [x] TST-004.3.6 — `tests/render/test_ghost.py` (1, seed) → `fe87682`
  - [x] TST-004.3.7 — `tests/render/test_hostile_glow.py` (1, seed) → `7c1922a`
  - [x] TST-004.3.8 — `tests/systems/test_audio.py`, `test_sound_effects.py` (4, mixer)
  - [ ] TST-004.3.9 — `tests/render/test_element_colours.py` (numpy)
  - [ ] TST-004.3.10 — `tests/display/test_native.py` (SDL through ctypes)
- [ ] TST-004.4 — Worldgen R4: push sweep assertions down to hand-built grids
- [ ] TST-004.5 — The §6 organisation and §7 nits in `test_suite_review.md`
- [ ] TST-004.6 — The balance-number audit in `test_suite_review.md`
- [ ] TST-004.7 — Coverage for `world/gen/graph.py`, `world/gen/validate.py`,
  `village_tidy.py`, `mixer_backend.py`, `debug_overlay.py`
- [ ] TST-004.8 — Summon render tests (WA5)
- [ ] TST-004.9 — Bonepicker/Gaffjaw in-game screenshot — local session

## TST-004 — Results

Pending.
