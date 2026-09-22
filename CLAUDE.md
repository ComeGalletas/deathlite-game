# CLAUDE.md — Death Lite Die (pygame roguelite)

Working rules for Claude in this repository. The process section is the
standard every request follows; the standing rules below it condense the
decisions saved in memory, so the two must be kept in step (see
"Keeping this file honest" at the end).

---

## 1. Process standard (DOC-001)

### 1.1 Every requirement gets an ID

A requirement is one request or requirement from the owner. Each gets a
permanent ID `<SYS>-<NNN>`, numbered in sequence within its system and
never reused:

| code | system | covers |
|---|---|---|
| `CMB` | combat | `combat/` — weapons, damage, elements, reactions, balance, DPS bench |
| `ENT` | entities | `entities/` — enemies, bosses, NPCs, summons, AI, colliders |
| `SPN` | spawning | `spawn/` — the spawn master, groups, budgets, despawn |
| `WLD` | world | `world/` — generation, terrain, elevation, navigation, placement, buildings |
| `RND` | rendering | drawing, VFX, sprites, asset pipeline, display/resolution |
| `UI`  | interface | `ui/` — menus, HUD, screens, input, cursor |
| `PRG` | progression | `progression/` — XP, blessings, items, chests, potions, meta |
| `AUD` | audio | music, sound effects, mixer |
| `SYS` | core systems | `game/`, `systems/` — states, save, config, data layout, dev tools, refactors |
| `TST` | tests | the suite itself — helpers, tiers, seeds, speed |
| `BLD` | build | packaging (.exe), web build |
| `DOC` | process | documentation and working standards |

- A request that touches several systems takes the code of the system it
  mainly changes; the index lists the others it touches.
- A follow-up request to an existing feature gets a **new** requirement ID
  and is appended to that feature's journal as a new requirement block, so
  one journal can hold several IDs. The journal's own ID is the ID of its
  first requirement.
- Bugs, balance changes and refactors are requirements too; the index's
  `type` column tells them apart (`feature`, `bug`, `balance`, `refactor`,
  `process`).

### 1.2 Tasks and subtasks carry their parent's ID

- Task: `<requirement ID>.<n>` — `CMB-007.1`, `CMB-007.2`.
- Subtask: `<task ID>.<n>` — `CMB-007.2.1`.
- Decisions made along the way: `<requirement ID>.D<n>` — `CMB-007.D1`, so
  a decision can be cited from a comment, a design doc or memory.

### 1.3 Every requirement lives in a journal

Journals are `documentation/journals/<feature>_journal.md`. A new feature
gets a new journal; a follow-up goes into the existing one. The journal is
the plan, the todo list and the record, in this order:

```markdown
# <Feature> — journal

**ID:** CMB-007 · **System:** combat (+ RND) · **Type:** feature ·
**Status:** in progress · **Branch:** claude/cmb-007-<slug>

---

## CMB-007 — Requirement (owner, YYYY-MM-DD)

- **Objective:** one imperative sentence naming what is to be done.
- **Details:** the specifics — numbers, scope, files, assets.
- **Constraint:** what must be confirmed first, left untouched, preserved.

## CMB-007 — Confirmed reading

What the code already does, each item of the request checked against it,
and every decision the request left open stated as `CMB-007.D<n>`.

## CMB-007 — Plan

Modules, hooks, data, tests, screenshots — the proposal.

## CMB-007 — Tasks

- [ ] CMB-007.1 — <task>
  - [ ] CMB-007.1.1 — <subtask>
- [x] CMB-007.2 — <task> → `abc1234`

## CMB-007 — Results

Test counts per tier, screenshots delivered, what was deferred and why.
```

- The requirement block is a **distilled statement**, never a quote or a
  retelling of the prompt. A second round of the same request inside one
  session is introduced with "and then:" in the same block; a later,
  separate request is a new ID and a new block.
- The todo list and the plan are written **before** the first code change
  and kept current: tick tasks as they land, add tasks discovered on the
  way (with the next free number, never renumbering), and strike through
  (`~~CMB-007.4~~ dropped: <why>`) rather than delete.
- "Confirm and propose" is the first section, not a stop: build in the
  same session unless the owner asked to wait or a decision is genuinely
  theirs to make.

### 1.4 The index

`documentation/journals/INDEX.md` lists every requirement ID: title,
system(s), type, status, journal, branch, date. It also maps plans and
design documents to the IDs they serve. Add the row when the ID is
allocated and update its status as it moves
(`proposed → in progress → done`, or `parked` / `superseded by <ID>`).
Before allocating an ID, read the index for the next free number.

### 1.5 Branch or worktree — ask first

Before starting any considerable requirement — more than a one-file fix,
or anything with more than one task — ask the owner whether to work in a
**new worktree** or **stay on the current branch**. Name a new branch or
worktree after the ID: `claude/cmb-007-<slug>`. Record the answer in the
journal header's `Branch:` field. Small fixes inside an ongoing
requirement do not need the question again.

### 1.6 One commit per task or subtask

- Each finished task or subtask is its own commit, made when it is done,
  not batched at the end.
- The subject starts with the ID, then the usual imperative summary:
  `CMB-007.2: Spread the aura to enemies inside the blast`.
- The same commit carries that task's journal tick (with the commit's
  hash filled in by the next commit, or left for the results section) and
  any index status change.
- Stage by path. Never sweep unrelated working-tree changes into a task
  commit.
- Run the tests that cover the task before committing and note failures
  honestly in the journal; do not commit a red task as done.
- Pushing, opening a PR or merging only happens when the owner asks.
- End every commit message with the attribution trailer the harness
  supplies.

---

## 2. Standing rules (condensed from memory)

Feature-specific decisions (weapons, elements, islands, HUD, spawn master,
chests, music, packaging …) stay in memory and in their journals; these are
the rules that apply to every change.

**Code and data**
- Content is data-driven: per-entity numbers and strings live in
  `data/*.json`; code keeps only taxonomy constants and reads fields
  without value fallbacks. Invalid spawn data fails soft at run start,
  never at load.
- New feature and rendering code goes in focused single-concern modules
  inside a sub-package behind a thin dispatcher, not more branches in a
  large file.
- When a value changes, every copy changes with it — dev/debug duplicates,
  comments, `_note` fields, `CREDITS.md`, docs, journals and baked assets.
- The height-map world is the only world. The LD-8 flat generator is
  retired: no `HEIGHTMAP_ROOMS` branches, no flag-off preservation.
  `GameMap(seed=None)` and the flat renderer fallback stay.

**Tests**
- No CI exists or is planned; the suite checks stability locally. Do not
  propose CI, hooks or gates. The `sweep` tier runs only when asked
  (`python -m pytest -m sweep`).
- A test never skips itself to green; make the check runnable instead.
- Tests that boot a run or consume a generated world pin a seed
  (`tests/boot.py: start_run(game, seed=...)`).
- The generator leads, the tests follow: a sanctioned world change may
  remove or replace a generation test; re-pin `tests/world/digests.json`
  with `python -m world.digest --write`. Prefer rates over seed sweeps to
  single pinned outcomes, recorded in docstrings and the journal.
- Share cached worlds between tests; avoid per-test rebuilds.

**Art and assets**
- Look in the `assets/unused/` reserve (and the Super Pixel Effects
  Gigapack inside it) before concluding art is missing.
- Derived art stays regenerable: a `tools/asset_pipeline/` script reading
  its inputs from data, full rewrites, and a `--check` mode a test runs.
- A spent source sheet is archived in an `unused/` folder beside the strip
  it was cut into; record the cut in `assets_journal.md`.
- Prefer authored tile/autotile variants over procedural edges; an
  authored sprite replaces the procedural indicator under it.

**Reporting**
- Deliver a rendered screenshot whenever a milestone of visual or
  world-generation work is finished (headless: `SDL_VIDEODRIVER=dummy`).
- A deviation measured and found not to break functionality is reported
  once, recorded where it belongs, and then closed — not re-raised.
- Balance knobs the owner turns are written down as arithmetic, not
  flagged as defects.

---

## 3. Keeping this file honest

- This file and the memory must not disagree. When a standing rule
  changes, change it here and in memory in the same step.
- Known inconsistency to resolve (DOC-001.D4): the spent-source-sheet
  memory says the cut's pinning test skips when the source is gone, which
  contradicts "a test never skips itself to green".
