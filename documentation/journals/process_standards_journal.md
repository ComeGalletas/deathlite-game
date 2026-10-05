# Process standards — journal

**ID:** DOC-001 (+ DOC-002, DOC-007, DOC-008) · **System:** process · **Type:** process ·
**Status:** done · **Branch:** claude/reaction-damage-rework (reaches `main` by PR)

---

## DOC-001 — Requirement (owner, 2026-09-22)

- **Objective:** Write a `CLAUDE.md` context file that sets the project's
  working standard on top of the rules already saved in memory.
- **Details:** Every main feature keeps a journal in the current structure,
  requirement block included. Every request gets a todo list and a plan in
  its journal, and every finished task or subtask gets a commit. Before a
  considerable request, ask whether to work in a new worktree or stay on
  the current branch. Every requirement and journal carries an ID tied to
  the system it touches (combat, world, systems, rendering, …); every task
  and subtask carries an ID derived from its parent requirement; an index
  lists all of them for search.
- **Constraint:** Confirm the requirements and propose further ones where
  useful.

## DOC-001 — Confirmed reading

| # | requirement | where it lands |
|---|---|---|
| 1 | journal per main feature, current structure, distilled requirement block | `CLAUDE.md` §1.3 (the structure already used since 2026-09-22) |
| 2 | todo list and plan in the journal for every request | §1.3 — Plan and Tasks sections, written before the first code change |
| 3 | a commit per finished task or subtask | §1.6 |
| 4 | ask worktree vs. current branch for considerable requests | §1.5 |
| 5 | system-scoped ID on every requirement and journal | §1.1 |
| 6 | an index of every ID | `documentation/journals/INDEX.md`, §1.4 |
| 7 | task/subtask IDs derived from the parent | §1.2 |
| 8 | on top of current memory | §2 condenses the cross-cutting memory rules |

Decisions the request left open:

- **DOC-001.D1 — ID shape.** `<SYS>-<NNN>` with twelve codes (CMB, ENT,
  SPN, WLD, RND, UI, PRG, AUD, SYS, TST, BLD, DOC) matching the top-level
  packages; tasks `CMB-007.2`, subtasks `CMB-007.2.1`.
- **DOC-001.D2 — Requirement vs. journal.** The requirement is the atomic
  unit. A follow-up to an existing feature gets a new ID, appended to the
  same journal; the journal's ID is its first requirement's.
- **DOC-001.D3 — Legacy journals.** The 60 existing journals got
  retroactive IDs in creation order within their system, listed in the
  index with status `legacy`. Each file carries a `**Legacy ID:**` line under
  its title (DOC-001.3); their sections are not rewritten to the standard.
- **DOC-001.D4 — Memory conflict, resolved.** The spent-source-sheet rule
  had the cut's pinning test skip when the source was gone; the later rule
  says a test never skips to green. The owner pointed to the imp fix
  (`914039e`: `.gitignore` re-includes editor sources, the archive test
  asserts unconditionally), so "never skip" wins. The review found three
  cut-script tests still skipping on exit 2 (`tests/render/test_spawn_fx.py`,
  `test_totem_bolt.py`, `test_totem_sprite.py`), logged as TST-002 (proposed).
- **DOC-001.D5 — This request's own branch.** Owner chose `main`, with no
  test run since no code is touched; still one commit per task. The commits
  were made in the main checkout, which was later moved to
  `claude/reaction-damage-rework`; local and remote `main` stayed at
  `c63b126`, so DOC-001 reaches `main` through that branch's PR.

## DOC-001 — Proposed additions (included in `CLAUDE.md`)

1. **Decision IDs** (`CMB-007.D1`) so decisions can be cited from code,
   design docs and memory.
2. **Type and status columns** in the index (`feature/bug/balance/refactor/
   process`; `proposed → in progress → done / parked / superseded`).
3. **Commit subject starts with the ID** (`CMB-007.2: …`) so
   `git log --grep` finds every commit for a requirement.
4. **Branch names carry the ID** (`claude/cmb-007-<slug>`).
5. **Stage by path**: never sweep unrelated working-tree changes into a
   task commit.
6. **Tests before each task commit**, results written in the journal; no
   commit of a red task as done.
7. **Tasks are never renumbered or deleted**: new tasks take the next
   number, dropped ones are struck through with the reason.
8. **Plans and designs map to IDs** in the index.
9. **Push, PR and merge only on request.**
10. **CLAUDE.md and memory are kept in step**, changed together.

## DOC-001 — Tasks

- [x] DOC-001.1 — Write `CLAUDE.md` (process standard + condensed standing rules) → `1e1225e`
- [x] DOC-001.2 — Create `INDEX.md` with retroactive IDs for existing journals → `712775d`
- [x] DOC-001.3 — Stamp a `**Legacy ID:**` line under each legacy journal's title (owner approved; tagged as legacy so they grep apart) → `a4bd438`
- [x] DOC-001.4 — Resolve DOC-001.D4 and update memory + `CLAUDE.md`; open TST-002 as proposed
- [x] DOC-001.5 — Commit on `main`, one commit per task

## DOC-001 — Results

Four commits (`1e1225e`, `712775d`, `a4bd438`, `1bb3c0a`), now on
`claude/reaction-damage-rework`. No tests run: documentation only, as the owner directed. Memory
updated in step: a pinned `requirement-ids-journals-commits` entry, a pointer
from the journal-per-request entry, and the spent-source-sheet entry no
longer prescribes a skip.

---

## DOC-002 — Requirement (owner, 2026-09-22)

- **Objective:** Add a rule for owner balance tweaks found in the `data/`
  JSON while other work is in progress.
- **Details:** When such a change is seen, point it out and ask whether to
  ignore it for the current work or commit it in a separate commit that
  names the balance change.
- **Constraint:** Hold commits until the owner confirms the other agents
  have finished and settles which branch is `main`.

## DOC-002 — Confirmed reading

- **DOC-002.D1 — What counts.** Any `data/` value change the current task
  did not make. It is reported as file, actor, old → new.
- **DOC-002.D2 — The separate commit.** It carries a `balance`-type
  requirement ID in the actor's system, matching what the ENT-012 session
  already did (`ENT-012.1: Drop Stoutpaw's shield from 41 to 7`).
- **DOC-002.D3 — Before the answer.** No folding into a task commit, no
  revert, and no code or test changed to agree with the tweak.

## DOC-002 — Tasks

- [x] DOC-002.1 — Add `CLAUDE.md` §1.7 and the index row; save the rule to memory
- [x] DOC-002.2 — Commit once the other agents finished, on `claude/reaction-damage-rework`

---

## DOC-007 — Requirement (owner, 2026-09-28)

- **Objective:** `CLAUDE.md` names no person. It was copied from a public
  template and still called its original author by first name (21 times)
  and linked the template's GitHub handle.
- **Details:** Replace every name and handle with `"owner"`. People who use
  the software are written as a quoted role (`"owner"`), not a name.
- **Constraint:** Wording only; no rule changes.

## DOC-007 — Confirmed reading

- **DOC-007.D1 — Form.** `"owner"` in quotes, no article, in place of the
  name (`ask "owner"`, `How "owner" wants to be talked to`).
- **DOC-007.D2 — Pronouns.** "his to execute" and "until he answers" become
  `"owner"` phrasings, so no gendered pronoun is left.
- **DOC-007.D3 — The handle.** The link to the template's repository
  carried the author's GitHub handle; it now reads "the upstream CLAUDE.md
  template repository", with no handle or URL.

## DOC-007 — Tasks

- [x] DOC-007.1 — Replace the name, pronouns and handle in `CLAUDE.md`; add the index row and this entry; save the rule to memory

## DOC-007 — Results

One commit. No tests run: documentation only. Checked with
a case-insensitive grep of `CLAUDE.md` for the old name and handle (no
matches) and a read of the 21 changed lines.

---

## DOC-008 — Requirement (owner, 2026-10-05)

- **Objective:** Repair `CLAUDE.md`: restore the project standard (§1 to
  §3) next to the general template, and settle where the two disagree.
- **Details:** `ddd4677` replaced the whole file with a generic template
  and dropped §1 to §3 (last full copy: `7c72ca4`, 226 lines). `58fdf16`
  pasted back two fragments in the wrong places: §2's Tests block inside
  the first bash snippet in "Branching", which broke it (`bash -n`:
  `syntax error near unexpected token '.'`), and §3's tail under
  "How "owner" wants to be talked to". `INDEX.md` still pointed at a §1
  that no longer existed.
- **Constraint:** Keep both halves. Ask "owner" which wins for each
  conflict before writing. The template's branching snippets must come out
  intact.

## DOC-008 — Confirmed reading

`diff ddd4677:CLAUDE.md HEAD` showed only DOC-007's 21 "owner" lines plus
the two misplaced pastes, so cutting the pastes out restores the template
exactly. Conflicts, asked and answered on 2026-10-05 (recorded in
`CLAUDE.md` §4):

- **DOC-008.D1 — Push and PR: the template wins.** Push and open the PR
  when a requirement is done, without being asked. A human merges. §1.6's
  "only when the owner asks" line is replaced.
- **DOC-008.D2 — Branching: §1.5 wins.** Ask "new worktree or current
  branch?" before a considerable requirement, and name branches
  `claude/<id>-<slug>`. When the answer is a worktree, the template's setup
  block still makes it, and the branch is renamed. When the current branch
  is `main`, the work goes on a new `claude/<id>-<slug>` branch, because
  "never commit to `main`" still holds. That last part is my reading of how
  D1 and D2 fit together, flagged for "owner" to confirm in the PR.
- **DOC-008.D3 — Tests: §2 wins, evals mapped.** No hooks, gates or CI.
  Gate tests are run by hand before each task commit. "Full suite" means
  the default pytest tiers, and `sweep` still runs only when asked. An
  "eval" is a rate measurement or a sweep check where one applies.
- **DOC-008.D4 — Layout and assets: the project wins.** System
  sub-packages stand in for `services/`. `assets/` art and audio
  (493 tracked files) are source. "No binaries" still covers build
  outputs.
- **DOC-008.D5 — Task vocabulary.** A template "task" is a requirement:
  one triage block, one self-rating and one PR each. Commits stay one per
  §1.2 task. Self-rating fixes become new task IDs.
- **DOC-008.D6 — Wording and placement.** Part one comes first, under the
  project title, and keeps the §1 to §3 numbering that `INDEX.md` and older
  journals cite. Restored prose says `"owner"` (DOC-007.D1) where `7c72ca4`
  said "the owner". The journal heading token `(owner, date)` is unchanged.
  Part two is the template verbatim, minus its own `# CLAUDE.md` title. Its
  conflicts are settled in §4 instead of by editing it, so the snippets
  stay byte-identical to the template's tested copy.

## DOC-008 — Tasks

- [x] DOC-008.1 — Rebuild `CLAUDE.md` (part one restored with §4 added,
  part two cleaned); journal entry and index row; memory updated to match

## DOC-008 — Results

One commit. No pytest run, because no code changed. Checks on the result:

1. The template part, compared with `ddd4677` from line 3 on, differs only
   in the 21 DOC-007 lines (diff filtered for the name, handle and
   `"owner"`: no other lines).
2. All five ```` ```bash ```` snippets are byte-identical to `ddd4677`
   (94 lines total), and each passes `bash -n`. HEAD's first snippet fails
   `bash -n`, which confirms the break this repairs.
3. Part one, diffed against `7c72ca4`, shows only the intended hunks: the
   intro, six `"owner"` rewordings, the §1.5 pointer, the §1.6 push line,
   and the new §3 bullet and §4. The Tests block and the "must not
   disagree" bullet each appear exactly once.

Branch: this session's worktree was made by the template's setup block
before D2 was decided, then renamed to `claude/doc-008-restore-process`.
