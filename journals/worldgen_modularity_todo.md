# World generation — modularity & test rework TODO

Working list for the structural review of the generation pipeline. The full
reasoning, measurements and dependency diagram live in the review page; this
file is only the order of work and what each step is for.

Milestones are prefixed **R**. Each ends with the **full suite green**
(`python -m pytest -q`) and, where it touches the bake or the draw path, a
determinism A/B check (same seed → byte-identical `WorldLayout`). **Nothing is
committed unless the user asks.**

**Status:** not started. Written against the tree at `b0114d6`, suite at
945 passed / 1 skipped.

---

## Why the tests come first

The review put the structural moves first and the test rework third. That order
is wrong, and the census is what showed it: `tests/world` builds **2,561 worlds
to run 308 tests**, and a full run is 20–29 minutes. Every structural move is
verified by that suite, so each one pays the full cost twice — once to check the
move, once to check the fix when it is not right first time.

Doing the test work first is not tidiness. It is the difference between a
refactor you can iterate on and one you land blind.

Effort is given two ways, because they differ: **hands** is a developer's
working time, **agent** is what it costs an assistant, where the binding
constraint is suite runs rather than typing.

---

## Phase one — make the suite cheap to run

### R1 — Session-scoped world fixtures

- [ ] Add `tests/conftest.py` with a session-scoped fixture keyed by
      `(seed, built)`, returning a shared `GameMap`.
- [ ] Migrate the six modules that hand-rolled a module-level `_MAPS` /
      `_WORLDS` cache onto it.
- [ ] Migrate the rest, which currently rebuild per test.

**Why.** There is no `conftest.py` in the project at all. Six test modules
independently reinvented the same cache; everything else rebuilds. The suite
concentrates on four seeds (`35`, `7`, `1234`, `42`), so the shared set is
small — a dozen fully built worlds is under a minute.

**Expected return.** Most of the 462.7 s that `tests/world` currently spends in
`generate_world`. About a third of that suite. Not a cure on its own — see R4.

**Verified by.** Suite green, and the same instrumented census re-run: the
`generate_world` call count should fall by roughly an order of magnitude.

*Hands: half a day · Agent: ~1 h editing + 1 suite run*

---

### R2 — Tier the suite, and name the tiers

- [ ] Register `unit`, `world` and `sweep` markers in `pytest.ini`.
- [ ] Mark the existing suites. Most of what exists is tier `world` wearing
      tier `sweep`'s clothes.
- [ ] Make the default invocation run `unit` + `world` only.

| Tier | Builds | Target | When |
|---|---|---|---|
| `unit` | nothing — hand-built grids | < 5 s | every save |
| `world` | cached fixtures, 3–4 seeds | < 90 s | every change |
| `sweep` | many seeds, statistical | minutes | before a commit |

**Why.** A twenty-minute suite gets run once at the end of a change instead of
during it. That is exactly how four runs in the margin milestone ended up
straddling edits and certifying a tree that no longer existed.

`tests/world/test_repair.py` is the honest tier-three case: it pins bay
detection and bridge lanes seed by seed and is brittle *because* it is testing
the generator itself. It should stay in `sweep` and say so.

**Verified by.** `pytest -m "unit or world"` under 90 s; full run unchanged.

*Hands: half a day · Agent: ~1 h + 2 suite runs*

---

### R3 — Equivalence tests for the mirrored pairs

- [ ] `walk_links` ↔ `_flight_opens` — adjacency, every cell of a world.
- [ ] `GameMap._point_ok` ↔ `_point_on_floor` — the floor test.
- [ ] `GameMap.inset_ok` ↔ `_point_inset_ok` — the terrace margin.
- [ ] `can_step` ↔ the baked `step_mask` — already partly covered by
      `test_step_mask_matches_the_rule`; extend it to every direction.

**Why.** Five rules are implemented twice on purpose, each documented as a
mirror, because the runtime cannot import the generator and the generator
cannot afford the runtime's indirection. **Three bugs in the last milestone
came from these pairs drifting**, and every one was found by measurement rather
than by a test — no test asserts a pair agrees *in general*, only that each half
is individually correct.

This is the cheapest item on the list and the one with the clearest history of
paying for itself.

**Verified by.** Each test failing when its pair is deliberately broken. Write
the break, watch it fail, revert — a green test that has never been seen red is
not evidence.

*Hands: one day · Agent: ~45 min + the sweeps are slow to run*

---

### R4 — Push assertions down from worlds to rules

- [ ] Audit the per-cell sweeps: which need a *generated* world, and which need
      only *a* grid?
- [ ] Convert the second kind to hand-built grids in tier `unit`.
- [ ] Keep the generated sweeps for what only they can prove — that an
      invariant survives a world nobody imagined.

**Why.** This is where the other 70% is. World building is only ~30% of the
runtime; the rest is the tests' own work — exhaustive per-cell sweeps,
brute-force reference implementations, flood fills. A test that builds six
worlds to check a predicate is measuring the generator's mood, and one that
then sweeps every cell of all six pays for that measurement twice.

`FootStoneRuleTests` in `tests/world/test_elevation.py` is the model: hand-built
grids, every case visible, runs instantly, and it caught a two-cell-face case no
generated world happened to contain.

The margin work added some of the worst offenders.
`test_an_eight_pixel_inset_strands_nothing` flood-fills every sample of every
island — that one earns its cost, because connectivity was the single thing
phase 1 could have broken. Most of its neighbours do not.

**Verified by.** Suite green with the same assertions, tier `world` under its
90 s target.

*Hands: two to three days · Agent: several hours, incremental, one suite per
batch*

---

## Phase two — the structural moves

### R5 — Create `world/rules/`

- [ ] New package `world/rules/`.
- [ ] Move `world/frontier.py` and `world/inset.py` into it unchanged.
- [ ] Move the pure predicates out of `world/elevation.py` — `can_cross`,
      `can_step`, `diagonal_blocked`.
- [ ] Delete the header paragraphs in both leaf modules explaining why they sit
      at the root of `world/`. **That deletion is the tell that the move is
      right.**
- [ ] Add a layering guard test: nothing in `world/rules/` imports `world.gen`
      or `world.terrain`.

**Why.** `world.terrain` imports `world.gen`, so a rule shared by generation and
rendering can live in neither package without closing a cycle. Both
`frontier.py` and `inset.py` were written as dependency-free leaf modules at the
root of `world/` for exactly that reason, and both say so in their docstrings.
The workaround works; it is still a workaround, and the next shared rule makes
it three.

**Risk.** Low. Relocation plus imports, no logic.

*Hands: half a day · Agent: ~15 min + 1 suite run*

---

### R6 — Cut the `terrain → gen` edge

- [ ] Resolve each terrace's sheet at generation and store it on `Room` — it is
      already half there, on `Room.palette`.
- [ ] Point `world/terrain/biome.py`, `world/terrain/sheets.py` and
      `world/terrain/decor/budget.py` at the stored value.
- [ ] Extend the layering guard: `world.terrain` imports nothing from
      `world.gen`.

**Why.** Those three imports are all the same thing — a palette decision made at
generation and read at bake. That is data, not behaviour. Move the data and the
edge disappears, which is what makes R5 stable rather than a naming change.

**Risk.** Medium. Palette resolution moving earlier can shift world output; A/B
the layout for a fixed seed before and after, and if it shifts, understand why
before accepting it.

**Decision needed.** Whether shifted world output is acceptable, if it shifts.

*Hands: half a day · Agent: ~45 min + 1–2 suite runs + a world diff*

---

### R7 — Split `world/pathfinding.py`

- [ ] `nav/lattice.py` — `NavGrid`, the walkable/corridor/blocked masks.
- [ ] `nav/clearance.py` — the chamfer transform.
- [ ] `nav/field.py` — `FlowField` and `NavField`.
- [ ] Have the elevation mask import the real predicates from `world.rules`
      instead of reimplementing them, so it becomes a **cache** rather than a
      mirror.

**Why.** 732 lines covering three separable concerns. The last bullet is the
substantive one: it removes a mirrored pair rather than testing it, which is
strictly better than R3's guard for that pair.

**Risk.** Medium. The elevation mask change is behavioural — it is the thing
that drifted twice in the last milestone.

**Depends on.** R5.

*Hands: one to two days · Agent: ~1–2 h + 2 suite runs*

---

### R8 — Retire the flat and verticality world models *(optional)*

- [ ] Decide whether anything still ships on `WORLD_VERTICALITY` or the flat
      path.
- [ ] If not: delete `world/legacy/` (851 lines), the 21 flag references across
      `world/`, `game/` and `entities/`, and the 9 test modules pinning the
      flag-off path.

**Why.** `generate_world` branches on two flags to build one of three
fundamentally different worlds, and reads `config` fifteen times to decide
which. Every new rule has to answer for all three, and most answer "nothing"
with an early return on `if not room.grid`.

**Do not start this without deciding the first bullet.** It is the only item on
the list that removes capability rather than moving it.

*Hands: two to three days · Agent: several hours, several decisions*

---

## What not to change

Recorded so a later pass does not "tidy" them:

- **The comments.** This codebase explains *why*, not *what*. Several findings
  in the review were only findable because a past decision was written down
  where it was made.
- **The data-driven tuning.** Values live in `data/terrain.json` with no code
  defaults. It held for the margin work without argument.
- **Seeded determinism.** String-keyed RNG per room and per concern, with
  `getstate`/`setstate` around new passes, is what makes any of this measurable.
- **The `world/gen/height/` split.** Terraces, walls, flights, water, graph,
  const — one concern per module. It is the shape the rest should move toward.
