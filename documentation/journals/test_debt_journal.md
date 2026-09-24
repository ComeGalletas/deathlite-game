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

## TST-004 — Plan

One task per source note, in the order given; each is read first, its
current state recorded below, the change made, the covering tests run, and
the source note updated in place with a `*(TST-004, 2026-09-24: …)*` line.
The default suite (`python -m pytest -q`, sweep excluded) runs before the
last commit, and its counts go in Results with 0 skipped as the target.

## TST-004 — Tasks

- [x] TST-004.1 — This journal
- [ ] TST-004.2 — Digest tests through `world_digests`
- [ ] TST-004.3 — Remove the conditional skips
- [ ] TST-004.4 — Worldgen R4: push sweep assertions down to hand-built grids
- [ ] TST-004.5 — The §6 organisation and §7 nits in `test_suite_review.md`
- [ ] TST-004.6 — The balance-number audit in `test_suite_review.md`
- [ ] TST-004.7 — Coverage for `world/gen/graph.py`, `world/gen/validate.py`,
  `village_tidy.py`, `mixer_backend.py`, `debug_overlay.py`
- [ ] TST-004.8 — Summon render tests (WA5)
- [ ] TST-004.9 — Bonepicker/Gaffjaw in-game screenshot — local session

## TST-004 — Results

Pending.
