# Run determinism — journal

**ID:** SYS-008 · **System:** core systems (+ SPN) · **Type:** bug ·
**Status:** proposed · **Branch:** —

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
- [ ] SYS-008.2 — Watchdog stagger and tracks keyed by a spawn serial, not `id()` (D1)
- [ ] SYS-008.3 — Locate the hash-order iteration (bisect the spawn path under fixed hash seeds) and sort it where it is consumed (D2)
- [ ] SYS-008.4 — Locate the memory-order dependence behind seed 123 (object sets, `id()`-keyed dicts that are iterated) and remove it — open-ended; the owner gave the go on 2026-09-23
- [ ] SYS-008.5 — Remove both workarounds from `run_digest.py`, re-pin `run_digests.json`, and make SYS-008.1 an ordinary test; index to done

## SYS-008 — Results

*(filled in as the tasks land)*
