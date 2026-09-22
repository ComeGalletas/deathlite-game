# Documentation cleanup — journal

**ID:** DOC-003 · **System:** process (+ CMB, WLD, SPN, ENT, TST, SYS) ·
**Type:** process · **Status:** in progress ·
**Branch:** claude/doc-003-doc-cleanup (worktree `.claude/worktrees/doc-003-doc-cleanup`)

---

## DOC-003 — Requirement (owner, 2026-09-22)

- **Objective:** Bring the journals, plans and index in line with the code
  so that an unticked box means work that is really still pending.
- **Details:** Tick the boxes whose work shipped, mark the ones a later
  decision replaced, fix documentation text that describes code that no
  longer exists, add the missing cross-references, and give the open items
  that have no ID one, as `proposed`.
- **Constraint:** Work in a new worktree. No code or balance value changes;
  legacy journals are annotated, not rewritten to the standard.

## DOC-003 — Confirmed reading

A review on 2026-09-22 read every unticked box in `documentation/` and
checked each against the code, `data/`, `tests/` and `git log`. About 90
boxes describe work that shipped; most sit in plans that a later "built"
section replaced. The genuinely open work is listed under *Results*.

- **DOC-003.D1 — Box states.** `- [x]` done; `- [-]` superseded or obsolete,
  with a pointer to what replaced it; `- [ ]` still pending. A
  `grep -rn -- "- \[ \]" documentation` then lists only real work. Each
  touched box carries a short `*(DOC-003: …)*` note with its evidence;
  a block of boxes replaced by one later section gets a single note on the
  block instead.
- **DOC-003.D2 — New IDs for open items.** Three open items had no ID and
  get one as `proposed`: CMB-008 (particle limits under the reaction
  cascade, design §13 question 12), SYS-008 (a seed does not reproduce the
  same run across processes, from SYS-007's *Open*), WLD-012 (a prop beside
  a bridge mouth can block a wide body, from WLD-011). They get journals
  when they are taken up; until then the index points at the journal that
  found them.
- **DOC-003.D3 — The `data/` note.** `spawn_tables.json`'s `_unused_comment`
  is documentation, not a balance value; correcting it is in scope and
  does not fall under DOC-002.

## DOC-003 — Plan

Documentation only, so no test tier covers it; one commit per task, staged
by path.

## DOC-003 — Tasks

- [x] DOC-003.1 — Open this journal; index rows for DOC-003, CMB-008, SYS-008, WLD-012
- [x] DOC-003.2 — Elemental: tick/mark `ELEMENTAL_SYSTEM_DESIGN.md` and the M3–M8 plan boxes in `elemental_system_journal.md`; update §6.3's `elementInterval` text
- [x] DOC-003.3 — Combat: `combat_balance_journal.md` CB-2 G and `training_dummy_journal.md` bench rebuild
- [x] DOC-003.4 — World, spawn and tests: `worldgen_modularity_todo.md`, `journal.md` flow field, `spawn_master_todo.md` S8, `spawn_master_journal.md`, `spawn_groups_journal.md`, `test_suite_review.md`
- [x] DOC-003.5 — Entities and UI: bomb fish, roster expansion, gnome split, imp, spear goblin, key icons, buff buildings, assets WA5
- [ ] DOC-003.6 — Stale text: `FUNCTIONAL_README.md` `MENU_SCRIM`, `spawn_tables.json` `_unused_comment`, `pending_plans.md` status
- [ ] DOC-003.7 — Cross-references: ENT-012.D2 → WLD-011, WLD-011 → WLD-012, SYS-007 *Open* → SYS-008 and `state.py` size, CMB-007 → CMB-008
- [ ] DOC-003.8 — Index: assign the unassigned plans, note CMB-006's legacy stamp, results, close

## DOC-003 — Results

*(filled in by DOC-003.8)*
