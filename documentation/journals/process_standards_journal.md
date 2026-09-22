# Process standards — journal

**ID:** DOC-001 · **System:** process · **Type:** process ·
**Status:** in progress · **Branch:** main (not committed yet — see DOC-001.D5)

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
  index with status `legacy`. Their files are not edited yet (one has
  uncommitted owner changes); stamping the header is DOC-001.3.
- **DOC-001.D4 — Memory conflict found.** The spent-source-sheet rule has
  the cut's pinning test skip when the source is gone; the later rule says
  a test never skips to green. Flagged in `CLAUDE.md` §3 for the owner.
- **DOC-001.D5 — This request's own branch.** It only adds three new
  documentation files, so it was written on `main` without committing, and
  the owner is asked which branch to commit it on.

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

- [x] DOC-001.1 — Write `CLAUDE.md` (process standard + condensed standing rules)
- [x] DOC-001.2 — Create `INDEX.md` with retroactive IDs for existing journals
- [ ] DOC-001.3 — Stamp the ID header onto each legacy journal (awaiting owner)
- [ ] DOC-001.4 — Resolve DOC-001.D4 with the owner and update memory + `CLAUDE.md`
- [ ] DOC-001.5 — Commit on the branch the owner chooses
