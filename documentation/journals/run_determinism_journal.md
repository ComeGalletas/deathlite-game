# Run determinism — journal

**ID:** SYS-008 · **System:** core systems (+ SPN) · **Type:** bug ·
**Status:** in progress · **Branch:** claude/sys-008-run-determinism

---

## SYS-008 — Requirement (owner, 2026-09-22)

- **Objective:** Make a seed reproduce the whole run, enemies included, in
  any process.
- **Details:** The world is reproducible; the enemies are not. The
  structure review (SYS-007, *Open*) found three causes on the spawn path:
  the watchdog's address-based stagger, an iteration in string-hash order,
  and a further memory-order dependence that makes seed 123 drift even with
  the other two pinned.
- **Constraint:** Found during SYS-007 and allocated by DOC-003; whether
  full same-seed determinism is a goal is the owner's call before the
  investigation in SYS-008.4 is started. No gameplay change: a fixed run
  must play as it does now, only reproducibly.
- **and then:** the owner confirmed full same-seed determinism is the goal
  and gave the go for SYS-008.4 (2026-09-23).

## SYS-008 — Confirmed reading

- **The watchdog.** `spawn/watchdog.py::_stagger` returns
  `(id(enemy) // 16 % 1000) / 1000 * sample_interval`, so each enemy's
  first stuck-check lands at a memory-address-dependent time; a flagged
  enemy is recycled, which moves the run's RNG stream. Its `_tracks` dict
  is keyed by `id(e)` as well, so a freed address reused by a new enemy in
  the same frame could inherit a track — a candidate for the third cause.
- **The hash seed.** One seed gives one of two enemy mixes depending on
  `PYTHONHASHSEED`. The roster sorts its names, so the unsorted iteration
  sits further down the spawn or placement path. `SpawnTables.enemy_ids()`
  (`spawn/tables.py`) returns an unsorted `set[str]` and is one candidate;
  not yet confirmed.
- **The workarounds.** `tools/verification/run_digest.py` re-executes
  itself with `PYTHONHASHSEED=0` and replaces the watchdog stagger with
  `lambda enemy: 0.0`. Its note reads seed 7 as the reliable pin and seed
  123 as evidence only when compared back to back.
- **SYS-008.D1 — The stagger keeps its spread.** It exists so enemies are
  not all sampled on one frame; the replacement keeps that spread, derived
  from a per-run spawn serial instead of the address.
- **SYS-008.D2 — Sort where the order is consumed.** An unsorted collection
  is sorted at the point it is iterated into something order-sensitive,
  not by changing every producer to return a list.

## SYS-008 — Plan

A failing cross-process test first, so every step has something to turn
green; then the three causes in order of certainty; then remove the
workarounds so the digest tool proves the result on its own.

## SYS-008 — Tasks

- [ ] SYS-008.1 — A test that runs the run digest in two child processes with different `PYTHONHASHSEED` values and compares; expected to fail, recorded as the baseline
- [x] SYS-008.2 — Watchdog stagger and tracks keyed by a spawn serial, not `id()` (D1)
- [ ] SYS-008.3 — Locate the hash-order iteration (bisect the spawn path under fixed hash seeds) and sort it where it is consumed (D2)
- [ ] SYS-008.4 — Locate the memory-order dependence behind seed 123 (object sets, `id()`-keyed dicts that are iterated) and remove it — open-ended; the owner gave the go on 2026-09-23
- [ ] SYS-008.5 — Remove both workarounds from `run_digest.py`, re-pin `run_digests.json`, and make SYS-008.1 an ordinary test; index to done

## SYS-008 — Results

**Branch:** `claude/sys-008-run-determinism`, cut from
`claude/doc-004-proposal-journals` (which carries this journal), owner's
instruction to continue with SYS-008 (2026-09-23).

### The baseline, and how the causes were found (2026-09-23)

- `run_digest` (its two workarounds in place) under `PYTHONHASHSEED` 0, 1,
  2, 3, run one after another: seed 7 identical all four times; seed 123
  two values — 0/1 one, 2/3 the other. That looked like the hash-seed
  cause.
- It was not. Dumping seed 123's full snapshot under hash seeds 0 and 2
  gave **identical** snapshots; running the same hash seed four times gave
  **two** values (one run in four). What differed was the RNG state, the
  camera, the hero and one enemy's position.
- A per-frame probe (the digest's own script, fingerprinting the RNG state,
  the enemy list and the hero each frame) run six times **in parallel**,
  under load: five of the six parted from the first at frames 628–629, in
  the enemies. Load changing the outcome pointed at the wall clock.

### SYS-008.4 — The wall clock (the "memory order" cause)

**SYS-008.D3 — The third cause is time, not memory order.** The flow-field
fill is sliced across frames (fluidity plan 3a), and the slice was
**3 ms of `time.perf_counter()`** (`world/nav/field.py`, both `step`s). How
far a fill got in a frame — so the frame a new field swapped in, and every
enemy's steering after it — depended on how fast the machine ran that
frame. Under load the runs split; on a quiet machine they mostly agreed,
which is why seed 7 looked stable and seed 123 "drifted over the day".

- The budget is now **work**: `ENEMY_NAV_FILL_BUDGET` = 1600 relaxations a
  frame (was 0.003 s). A whole fill measures 530–670 relaxations per ms
  here (seeds 35, 7, 123 — small class 10,067–15,087 relaxations in
  17.4–28.4 ms, large 3,999–5,788 in 6.0–9.2 ms), so 1600 is what 3 ms
  bought on this machine, and the same work on every machine.
  `FlowField.step` / `NavField.step` take a relaxation count;
  `last_step_relax` lets `NavField` share one budget between the classes
  in class order, as the seconds were shared. No clock is read.
- After it, six parallel probes of seed 123 under hash seeds 0–2 (the
  watchdog still flattened): **identical over all 721 frames**.

### SYS-008.2 — The watchdog

- `_stagger(serial)`: the first sample lands `serial × 0.618… (mod 1)` of
  an interval in — the golden-ratio step, so consecutive bodies never
  bunch — where `serial` is the order the watchdog first saw the body. It
  was `id(enemy)`, a memory address.
- A track also remembers its enemy, and a track found by `id()` is reused
  only if it belongs to the same body: an address freed by a death can be
  handed to the next spawn, which used to inherit the dead body's samples
  and could be judged stuck on them.
- With the real stagger back (the probe's `--stagger`): six parallel runs
  of seed 123 under hash seeds 0–2, **identical over 721 frames**.

**Tests:** `tests/spawn` + `tests/entities` + `test_enemy_nav` +
`test_pathfinding` — 569 passed, 217 subtests, 0 skipped.
