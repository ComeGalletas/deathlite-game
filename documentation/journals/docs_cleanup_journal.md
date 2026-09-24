# Documentation cleanup — journal

**ID:** DOC-003 (+ DOC-004, DOC-005, DOC-006) · **System:** process (+ CMB, WLD, SPN, ENT, TST, SYS) ·
**Type:** process · **Status:** done ·
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
- **and then:** the owner confirmed "one application per window" for the
  time mode, and said the W9 GitHub Pages deploy is not needed for now.
- **and then:** the owner closed CB-2 G (still feels active; the reach
  values were fine at the playtest but are still being tuned) and the G6
  remainder (reviewed and fine for the task, likewise still being tuned);
  asked for a new plan holding the remaining elemental extras and a faint
  glow behind elemental buff buildings; decided the "tileset missing" test
  skips become failures and that `coverage` stays a test-only tool, not a
  declared dependency (a coverage run with an HTML report was asked for
  separately); and asked for the PR.

## DOC-003 — Confirmed reading

A review on 2026-09-22 read every unticked box in `documentation/` and
checked each against the code, `data/`, `tests/` and `git log`. About 150
of the 184 describe work that shipped or was superseded; most sit in plans that a later "built"
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
- [x] DOC-003.6 — Stale text: `FUNCTIONAL_README.md` `MENU_SCRIM`, `spawn_tables.json` `_unused_comment`, `pending_plans.md` status
- [x] DOC-003.7 — Cross-references: ENT-012.D2 → WLD-011, WLD-011 → WLD-012, SYS-007 *Open* → SYS-008 and `state.py` size, CMB-007 → CMB-008
- [x] DOC-003.8 — Index: assign the unassigned plans, note CMB-006's legacy stamp, results, close
- [x] DOC-003.9 — Record the owner's answers: tick the time-mode confirmation, park W9
- [x] DOC-003.10 — `CLAUDE.md` §2/§3 and memory: the digest command moved to `tools.verification.world_digest`; TST-002 is done, not proposed
- [x] DOC-003.11 — Close CB-2 G and the G6 remainder; record the tileset and `coverage` decisions in `test_suite_review.md`; TST-003 proposed for the tileset skips
- [x] DOC-003.12 — CMB-009 proposed: `plans/elemental_extras_plan.md`, its requirement block in the elemental journal, pointers from the design doc, index rows

## DOC-003 — Results

No tests run: documentation only. The one `data/` edit is a comment string
(DOC-003.D3), re-parsed as JSON before it was written.

**Unticked boxes:** 184 before, **26 after**: 32 at DOC-003.8 (an earlier
"33" counted this journal's own D1 text, which contains the pattern), 30
after the owner's answers in DOC-003.9, 26 after DOC-003.11. The count was
taken with `grep -rn -- "- \[ \]" documentation`, leaving out this journal.
Every box that remains is real open work:

| where | open |
|---|---|
| `ELEMENTAL_SYSTEM_DESIGN.md` | buff buildings draw no element; 9.8 lacks jump-node and Wind-area counters; 10.3 dev extras — all three planned as CMB-009 |
| `worldgen_modularity_todo.md` | R4: push sweep assertions down to hand-built grids |
| `test_suite_review.md` | the digest tests' world source, coverage gaps, the seed skips, the tileset skips (decided: fail, TST-003), §6 organisation, §7 nits, the balance-number audit |
| `enemy_roster_expansion_journal.md` | an in-game screenshot of Bonepicker and Gaffjaw firing |
| `assets_journal.md` | WA5: the summon render tests |
| `pygbag.md` | the optional bundle trim (W9 parked by the owner) |

**New IDs, proposed:** CMB-008 (design §13 q.12), SYS-008 (cross-process run
reproducibility), WLD-012 (props beside bridge mouths), TST-003 (a missing
tileset fails), CMB-009 (elemental extras, `plans/elemental_extras_plan.md`).

**Closed by the owner, 2026-09-22:** CB-2 G and the G6 remainder — fine at
the review, still being tuned, so later values supersede the ones recorded.

**Corrected on the way:** the agent-assisted review said M6's time mode had
been built without `next_element_at`, but `Weapon._next_element_at` exists
(`combat/weapons/core.py`), so the box was noted as shipped as planned. The
elemental journal's M13 heading still read "PROPOSED" although its Progress
entry records it done; the heading now says "DONE".

**Deferred:** none of the open work above was in scope. The legacy
journals' own status lines were left alone, except
`worldgen_modularity_todo.md`, whose "not started" was plainly wrong, and
`training_dummy_journal.md`'s "Todo — not started".

---

## DOC-004 — Requirement (owner, 2026-09-23)

- **Objective:** Write the journals for the five proposed requirements
  CMB-008, SYS-008, WLD-012, TST-003 and CMB-009.
- **Details:** Each gets its requirement block, confirmed reading, plan and
  task list as the standard lays them out, from the expansion given to the
  owner on 2026-09-23. A follow-up to an existing feature goes into that
  feature's journal; SYS-008 opens a new one.
- **Constraint:** A new branch (`claude/doc-004-proposal-journals`, cut from
  DOC-003's tip because the index rows for these IDs exist only there).
  TST-003 is built first, on the same branch.

## DOC-004 — Confirmed reading

- **DOC-004.D1 — Where each journal lives.** TST-003 → `cut_script_skips_journal.md`
  (TST-002 listed the tileset skips among its follow-up candidates); WLD-012 →
  `bridge_clearance_journal.md` (found by WLD-011); CMB-008 →
  `reaction_damage_rework_journal.md` (the design question CMB-007 left open);
  CMB-009 → `elemental_system_journal.md` (its requirement and plan are already
  there); SYS-008 → a new `run_determinism_journal.md`.
- **DOC-004.D2 — Status.** All stay `proposed` except TST-003, which moves to
  `in progress` when its first task starts.

## DOC-004 — Tasks

- [x] DOC-004.1 — Open this block; index row
- [x] DOC-004.2 — TST-003 journal block
- [x] DOC-004.3 — WLD-012 journal block
- [x] DOC-004.4 — CMB-008 journal block
- [x] DOC-004.5 — SYS-008 journal (new file)
- [x] DOC-004.6 — CMB-009 confirmed reading and tasks
- [x] DOC-004.7 — Results; index to done

## DOC-004 — Results

All five requirements have a journal with requirement, confirmed reading,
plan and tasks; the index points at each directly (no "found in" left).
Decisions the journals leave to the owner: WLD-012.D1 (clearance follows the
data or a fixed number) and SYS-008's go-ahead for the open-ended
SYS-008.4. TST-003 was built on this branch and is done (`925502c`,
results in `cut_script_skips_journal.md`); the other four stay `proposed`.
No tests run for the journals themselves.

---

## DOC-005 — Requirement (owner, 2026-09-24)

- **Objective:** Record the second documentation review: the narrative
  "open / deferred / follow-up / still open" sections DOC-003 did not cover,
  each checked against the code, and the owner's answers to the decisions it
  raised.
- **Details:** The owner's answers (2026-09-24): boss HP stays on the +50 %
  curve with the second boss; no gold sink exists yet, so it is pending; the
  ranged wind-up and its playtest fold into the coming weapon rework; the
  "TAB build" hint stays on the pause screen only; the locality grace (6 s)
  and dwell (1 s) stay, deliberately constant so the difficulties stay
  apart; warm every animation frame the loading screen can, in its own
  journal as this session's next goal if it is too big for this
  requirement; split the 2026-09-16 music entry into its own journal, and
  close the web-only music options because the web build is not yet
  considered finished; Echo and Fragmentation stay dropped, closed pending
  the coming weapon rework; the sounds are fine for now (more and a
  whole-set tweak later), closed.
- **Constraint:** On the current branch (`claude/sys-008-run-determinism`).
  Documentation only.

## DOC-005 — Confirmed reading

Three read-only passes over about thirty sections (DOC-003.D1's box states
still apply; a prose item gets a `*(DOC-005: …)*` note instead of a box).

- **DOC-005.D1 — Answered decisions are closed where they were asked.** Each
  gets a note in its own section saying what the owner chose and when.
- **DOC-005.D2 — New IDs only where the owner asked for pending work.** The
  gold sink becomes **PRG-003** (proposed); the frame warm-up becomes
  **RND-005** (proposed, next). The other pending items stay recorded in
  their sections as pending, as DOC-003 left the open boxes, and get an ID
  when one is taken up.
- **DOC-005.D3 — "Weapon rework" is a future requirement, not yet an ID.**
  Items the owner deferred to it (the ranged wind-up playtest, Echo,
  Fragmentation) are closed with a pointer to it rather than left open.

## DOC-005 — Tasks

- [x] DOC-005.1 — Open this block; index rows for DOC-005, PRG-003, RND-005
- [x] DOC-005.2 — Combat, entities and UI sections: combat balance follow-ups, enemy AI, game over, ranged wind-up, run status, training dummy, PlayingState refactor, sprite functionality
- [x] DOC-005.3 — World, spawn and test sections: level design, rock collider, world refactor, the development journal, spawn groups, spawn master todo, test-suite review (fresh coverage, the warm-up decision), TST-002 follow-ups
- [x] DOC-005.4 — Assets, audio and build: assets follow-ups, music (split the 2026-09-16 entry, close the web options), sound effects, desktop packaging, pygbag, pending plans
- [x] DOC-005.5 — RND-005 journal (frame warm-up) and PRG-003 journal (gold sink), both proposed
- [x] DOC-005.6 — Results; index to done

## DOC-005 — Results

About thirty narrative sections annotated with a `*(DOC-005: …)*` note, each
item checked against the code by three read-only passes; the 23 open boxes
DOC-003 left were re-read on every branch tip. Documentation only, except
comments: the music split moved seven references (three code comments, two
test docstrings, the sound-effects journal, the index) and a memory entry to
`music_tracks_journal.md`; the touched Python files still compile.

**Closed by the owner, 2026-09-24:** boss HP keeps the +50 % curve; the TAB
hint stays on the pause screen; the locality grace and dwell stay constant;
the ranged wind-up playtest, Echo and Fragmentation fold into the coming
weapon rework; the web-only music options wait on the web build; the extra
sound cues are closed (more sounds and a whole-set tweak later); the music
entry is split.

**New IDs, proposed:** PRG-003 (a gold sink — none exists; the Merchant is
parked with the special facilities) and RND-005 (warm every animation frame,
the session's next goal).

**Still pending, recorded in place** — each gets an ID when taken up:

| area | pending |
|---|---|
| gameplay / UI | Warlock wind-up ground marker; skull `attack` at ~10 fps; chests opened on the run summary; auto-attack / aim toggle in Options; `mark` overlay; Kestrel / Nihil `attack2` and `guard` sheets; gamepad aim; a best-DPS record; absolute damage in the DPS overlay; unused chest skins (waits on a legendary tier) |
| architecture | the boss on the shared AI components; `push_radius`; `data/behaviors.json`; `_blit_rig` frame and anchor selection; `TimedVisual`; `MELEE_REACT_SCALE` to config if needed |
| rendering polish | soft shadow strip; pixel-perfect camera; live zoom slider |
| tests | digest tests through `world_digests`; ~16 conditional skips (`test_elevation.py:136` removable); worldgen R4; the §6/§7 tidy-ups; the balance-number audit; coverage of `world/gen/graph.py`, `validate.py`, `village_tidy.py`, `mixer_backend.py`, `debug_overlay.py`; WA5's summon render tests; the Bonepicker / Gaffjaw screenshot |
| web build (on hold) | wheel vendoring, loading steps and progress bar, manifest pack, browser spawn settings, the bundle trim |

---

## DOC-006 — Requirement (owner, 2026-09-24)

- **Objective:** Record the owner's answers to the items still pending after
  DOC-005 and set the order of the work that follows.
- **Details:** The owner's answers (2026-09-24):
  - The auto-attack / aim toggle stays a hint in the pause menu, with no
    Options row.
  - Kestrel and Nihil will not get `attack2` / `guard` animations: complete.
  - Gamepads are not considered for now.
  - The DPS extras (a best-DPS record, absolute damage in the overlay) are
    not needed. Instead, polish the run summary's weapons table, where
    forge names run their level into the damage figures.
  - No more chests for now. The design stays modular so tiers can be added
    later, but that is not a pending task.
  - Architecture:
    - Move the boss onto the shared AI's patterns.
    - Add a crowd push radius, set low enough that enemies can stack and
      cross bridges instead of getting stuck.
    - Move behaviour shape into the data files.
    - Items 4–6 (`_blit_rig`, `TimedVisual`, `MELEE_REACT_SCALE`) are easy,
      so they go first.
  - Split the test debt and hand it to a parallel remote session.
- **Constraint:** A new branch, `claude/doc-006-ui-013-dps-table`, cut from
  `main` after #33. Nothing was left to commit on the previous branch.

## DOC-006 — Confirmed reading

- The pause menu's Controls block (`ui/controls_block.py`) already lists the
  auto-attack key, "Q  Auto attack", so the toggle item closes without code.
- The run summary's weapons table (`ui/run_summary.py`, `_draw_damage`)
  prints `"<name>  Lv <n>"` from the left edge and the Damage / Share / DPS
  cells at 150 / 84 / 0 px from the right. The column's 498 px minimum was
  measured against `weapons.json` names only ("Grave Totem  Lv 9", 186 px).
  The forge names are longer ("Meteor Hammer  Lv 9" is 216 px), and a
  7-figure damage leaves only 199 px, so the level prints over the damage.
  Reproduced on the victory layout.
- The chest tiers are data: `data/loot/chests.json` holds each tier's payout,
  and `progression/chests.py` / `world/gen/chests.py` read the tiers by name.
- **DOC-006.D1 — IDs allocated:**
  - **UI-013:** the weapons table.
  - **TST-004:** the test debt, in a remote session on
    `claude/tst-004-test-debt`, journal `test_debt_journal.md`.
    TST-004.9, the Bonepicker / Gaffjaw screenshot, stays with this
    session.
  - **SYS-009:** `_blit_rig` + `TimedVisual` + `MELEE_REACT_SCALE`.
  - **ENT-015:** the boss on the shared AI components.
  - **ENT-016:** the crowd push radius.
  - **ENT-017:** behaviour shape moved into data.
- **DOC-006.D2 — "The data files need to be moved" is read as the
  architecture list's item 3:** behaviour shape moves from code into a data
  file (`data/enemies/behaviors.json`), beside the enemy data it configures.
- **DOC-006.D3 — The `mark` overlay stays pending.** It was expanded for the
  owner (an authored effect on marked enemies, declared on the status, shown
  only while a blessing reads the mark). The owner has not yet said whether
  it waits for the weapon rework.

## DOC-006 — Tasks

- [x] DOC-006.1 — Open this block; index rows; TST-004 handed to the remote session
- [ ] DOC-006.2 — In-place notes for the closed items; the chest docs say how a tier is added; the pending register rewritten

## DOC-006 — Order of work (kept current)

1. **UI-013:** the weapons table.
2. **SYS-009:** `_blit_rig` + `TimedVisual` + `MELEE_REACT_SCALE`
   (the owner's priority).
3. **ENT-015:** the boss on the shared AI.
4. **ENT-016:** the crowd push radius.
5. **ENT-017:** behaviour shape into data.
6. **TST-004.9:** the Bonepicker / Gaffjaw screenshot.
   TST-004.1–.8 run in the remote session in parallel.
7. **The `mark` overlay:** waits on the owner's call about the weapon
   rework.
8. **PRG-003:** the gold sink, when the owner has a design.

Parked: rendering polish (soft shadow strip, pixel-perfect camera, live zoom
slider). On hold: the web build.
