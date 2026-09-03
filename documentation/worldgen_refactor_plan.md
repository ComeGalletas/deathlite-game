# World generation — refactor, modularity and test plan (final)

> **Outcome (2026-09-02):** every phase below is done, in the order
> P0 → P5 → P1 → P2 → P3 → P4 → P6 → P7 → P8, with the LD-8 generator
> retired. Evidence, numbers and what was deliberately left on the table:
> `journals/world_refactor_plan_journal.md`.

This reconciles `journals/worldgen_modularity_todo.md` (R1–R8, test-first,
measured) and `documentation/world_modularity_todo.md` (Phases 0–7,
behaviour-preserving, contract-first) into one ordered plan. Everything below
was checked against the tree at `b0114d6` on 2026-09-02; the numbers are
measured on this machine, not copied from either document.

**Recommendation in one paragraph.** Do the two documents' cheap parts first
and together: a shared world cache for the tests, a layout / bake / draw
digest, and equivalence tests for the rules that are implemented twice. Then
spend one phase on generation speed, because every world-building test pays
for it. Then make the structural moves both documents agree on (`world/rules/`,
cut the `terrain -> gen` edge, split navigation). The one real decision is
whether the LD-8 flat generator ships: the evidence says it does not, and
retiring it removes more complexity than any other single item. Only then
introduce a generation-settings snapshot and a baked-terrain object, both
scaled down from the documentation plan. Comments are rewritten under a rule,
not a sweep: keep every *why*, drop the milestone tags and the flag-off
apologies.

---

## 1. Where the code stands

### 1.1 Shape

| Layer | Modules | Lines | Notes |
|---|---|---|---|
| Data model | `world/layout.py` | 234 | `Cell`, `TileMeta`, `Room`, `Corridor`, `Stair`, `WorldLayout` |
| Generation | `world/gen/*` (13) + `world/gen/height/*` (8) | 3,300 | orchestrator + one module per stage; `height/` is the model shape |
| Legacy generator | `world/legacy/*` | 829 | reached only when `config.HEIGHTMAP_ROOMS` is false |
| Shared rules | `world/frontier.py`, `world/inset.py`, `world/elevation.py` | 961 | leaf modules at the package root to dodge a cycle |
| Runtime | `world/map.py`, `world/pathfinding.py`, `world/spawning.py` | 1,308 | collision, nav lattice + flow field, spawn director |
| Bake + draw | `world/terrain/*` (14) | 2,300 | painters and renderer take the whole `GameMap` as `gm` |
| Shims | `world/procedural.py`, `world/gen/heightmap.py`, `world/terrain/biome.py` | 57 | re-exports only |

### 1.2 Dependency facts that shape the plan

- `world.terrain` imports `world.gen.biomes` from three places (`sheets.py`,
  `decor/budget.py`, `biome.py`). That edge is why `frontier.py` and
  `inset.py` sit at the root of `world/` and say so in their headers.
- `world.gen.repair` imports `world.pathfinding` (`NavGrid`, `_NAV_CLASSES`).
  Generation deliberately repairs against the lattice the game steers on. Keep
  it, but it fixes the layering: navigation may never import `world.gen`.
- Generation is **not** assetless any more: `gen/biomes.py` and
  `gen/scatter.py` read `get_assets().terrain` lazily. `level_design.md`
  still claims the opposite.
- Five rules are implemented twice on purpose, documented as mirrors:
  `walk_links` / `_flight_opens`, `GameMap._point_ok` / `_point_on_floor`,
  `GameMap.inset_ok` / `_point_inset_ok`, `can_step` / `step_mask`, and
  `repair._clearance` / `NavGrid._clearance_transform`. No test asserts a pair
  agrees in general.
- `config.HEIGHTMAP_ROOMS` / `WORLD_VERTICALITY` are read in 19 places outside
  `config.py`; nine test modules pin one or both **off** at module scope and
  restore in `tearDownModule`. That is the "generated under one mode, baked
  under another" hazard the documentation plan warns about, and it is created
  by the tests, not the game.

### 1.3 Cost, measured

One height-map world (the shipping mode), release build, no profiler:

| Seed | `generate_world` | `GameMap` (gen + `LevelIndex`) | `NavField` |
|---|---|---|---|
| 35 | 2.04 s | 2.14 s | 0.54 s |
| 7 | 2.34 s | 2.49 s | 0.55 s |
| 1234 | 1.68 s | 1.77 s | 0.53 s |
| 42 | 1.45 s | 1.51 s | 0.50 s |

A flat LD-8 world builds in under 10 ms, so the forty-seed sweeps in
`test_verticality.py` are cheap; the suite's cost is height-map worlds and
the tests' own per-cell sweeps.

Where a height-map build goes (seed 7, cProfile, share of `generate_world`):

| Stage | Share | What it is doing |
|---|---|---|
| `_build_inset_fields` | 33 % | `inset._chamfer`, pure Python over 8 px samples, two passes per room |
| `_scatter_obstacles` | 30 % | 27 % is `_blocks`: every placement try scans every keep-clear rect in the world (2.1 M `collidepoint` calls) |
| `_build_room_grids` | 22 % | `reachable` flood fills, 172 of them; `_cut_lateral_stairs` runs one per candidate site |
| `unseal` | 14 % | builds a `NavGrid`, whose constructor point-tests 54 k cell centres against every room rect |

Test census: 946 tests; 309 under `tests/world`; 18 modules need a display;
6 modules hand-roll a module-level world cache; the rest rebuild per test.
There is no `conftest.py` and no `pytest.ini`. All 67 test modules are
`unittest.TestCase`; none import `pytest`.

The world-facing modules (`tests/world`, `test_pathfinding`, `test_terrain`,
`test_depth_sort`) run in **15 min 52 s** for 411 tests. Two modules are
three quarters of that, and both rebuild their worlds inside every test:

| Module | Tests | Time | Why |
|---|---|---|---|
| `tests/world/test_repair.py` | 25 of the 30 slowest | ~456 s | every test regenerates the same eight seeds (14–37 s each) |
| `tests/world/test_obstacle_families.py` | 5 | ~238 s | one test alone is 98 s: it builds worlds twice, with the tree boost on and off |
| everything else | 381 | ~260 s | |

Eight seeds cost about 16 s to build once. Caching them turns
`test_repair.py` from 456 s into roughly 30 s without touching a single
assertion, which is the whole argument for P0 in one row.

---

## 2. The two documents, compared

| Question | Journal todo (R1–R8) | Documentation todo (Phases 0–7) | Final plan |
|---|---|---|---|
| First move | Make the suite cheap (cache, tiers) | Characterise (layout / bake / draw digests) | Both, as one phase: the digest needs the cache to be affordable |
| Runner | `pytest`, markers | `unittest discover` | `pytest` is canonical (markers need it); `unittest discover` stays green as the "everything" run |
| Mirrored rules | Equivalence tests (R3), then remove one pair (R7) | Extract runtime geometry from `GameMap` (Phase 3) | Test first, then **share** the floor and inset predicates so two pairs stop existing; keep the flight rule mirrored and tested |
| Shared code home | `world/rules/` (R5) | "Neutral package only if import direction is clear; no dumping ground" (Phase 6) | `world/rules/` with an import-guard test. A named layer with a guard is what makes it not a dumping ground |
| `terrain -> gen` edge | Cut it: palette is data on `Room` (R6) | Centralise palette ownership (Phase 6) | Same item; R6's mechanics |
| Three world modes | Retire flat + flat-verticality (R8, optional) | Give both generators first-class pipelines, mode invariants, parameterised tests (Phases 1–2) | **Retire.** See §4 |
| Settings snapshot | not covered | `GenerationRequest` (Phase 1) | Yes, after the retire decision, when it is 30 knobs instead of 3 modes × 30 |
| Bake / render | "What not to change" | `BakedTerrain` + renderer contract (Phases 4–5) | A `BakedTerrain` dataclass only (the refactor journal's own `TerrainStore` follow-up); no renderer rewrite |
| Comments | Do not touch | not covered | Rewrite under a rule (§5) |
| Generation speed | not covered | not covered | One phase, digest-verified (§3, P2) |

Where they agree, the plan simply keeps it: `generate_world` and `GameMap`
stay the public surface; nothing changes seed, layout, collision, bake or
draw output unless a phase says so; every phase ends with the full suite
green; `journals/world_refactor.md` and `journals/journal.md` get an entry per
phase; nothing is committed unless asked.

---

## 3. The plan

Effort is given as **hands** (developer time) and **agent** (an assistant,
where the cost is suite runs). Each phase ends with the full suite green and,
from P0 on, the digest unchanged unless the phase says otherwise.

### P0 — Harness: one world cache, one digest, named tiers

1. `tests/worlds.py`: a process-level cache `world(seed) -> (layout, gm,
   levels, navfield)` that builds each seed once. Plain module, no fixture
   injection, so it works under both runners. Migrate the six hand-rolled
   caches (`test_decor_density`, `test_decor_frontiers`, `test_elevation`,
   `test_inset`, `test_prop_coverage`, `test_water_decor`) and then the
   rebuild-per-test modules. Bake is lazy and needs a display, so the cache
   holds `GameMap`s and lets a test that draws trigger the bake once.
2. `world/digest.py`: `layout_digest(layout)` over rooms, grids, cells,
   tile meta, corridors, stairs, obstacles, palettes, bounds;
   `bake_digest(gm)` over every baked surface's bytes and anchor list;
   `draw_digest(gm, camera)` over one composited frame. Pin the shipping
   seeds (35, 7, 1234, 42) in `tests/world/test_digest.py`. This is the
   fingerprint W7 used from a scratch script and did not keep.
3. `pytest.ini`: markers `unit`, `world`, `sweep`; `addopts = -m "not sweep"`.
   `test_repair.py` and the forty-seed loops are `sweep` and say why. README
   gets the three invocations.
4. Remove the module-scope flag flipping where the cache makes it
   unnecessary; where a module genuinely tests the other mode, the cache key
   carries the mode so a world is never built under one flag and read under
   another.

**Why first.** Every later phase is verified by this suite; the digest is what
turns "pure move" from a claim into a measurement.

**Verified by.** Suite green; `pytest` (default) under 90 s; `pytest -m
sweep` unchanged; `generate_world` call count down by an order of magnitude
(instrument once, before and after). Start with `test_repair.py` and
`test_obstacle_families.py`: measured at 456 s and 238 s, they are 73 % of
the world-facing run and both rebuild per test. `test_obstacle_families`'s
boost test needs two variants of the same seeds (tree boost on and off), so
the cache key carries the tuning override, not just the seed.

*Hands: one day · Agent: ~2 h + 2 suite runs*

### P1 — Equivalence tests for the mirrored pairs

One test per pair, each asserting agreement over **every** cell or sample of
the cached worlds, and each seen red once by deliberately breaking one half:

- `walk_links` ↔ `can_cross` / `_flight_opens`, every tile, every direction;
- `GameMap._point_ok` ↔ `_point_on_floor`, a dense sample plus every tile
  corner;
- `GameMap.inset_ok` ↔ `_point_inset_ok`;
- `can_step` ↔ `NavGrid.step_mask`, all eight directions (extends
  `test_step_mask_matches_the_rule`);
- `repair._clearance` ↔ `NavGrid._clearance_transform`'s obstacle pass.

**Why before any move.** Three of the last milestone's bugs were these pairs
drifting, all found by measurement. These are the cheapest tests on the list
and the ones with the clearest history of paying for themselves.

*Hands: one day · Agent: ~1 h + 1 suite run*

### P2 — Generation speed, digest-verified

Each item must leave `layout_digest` identical, which is what makes it safe:
none of these touch the RNG stream.

1. `scatter._blocks`: bucket the keep-clear rects per room before the
   placement loop (a room only ever collides with the doors touching its
   rect, inflated by the largest obstacle radius). Expected: most of the 27 %.
2. `NavGrid.__init__`: rasterise `walkable` from `Room.grid` / `Room.cells`
   and the corridor rects directly, instead of point-testing every cell
   centre against every room. `_point_on_floor` stays as the reference the
   P1 test compares against. Expected: most of the 11 %, twice (generation's
   `unseal` and the run-time `NavField`).
3. `_cut_lateral_stairs`: reuse one component labelling per wall instead of a
   `reachable` flood per candidate site.
4. `inset._chamfer`: hoist the per-sample work; consider propagating only
   from frontier seeds out to `CAP` rather than sweeping every sample twice.
   Measure before committing to it.

Target: a height-map world under 1 s. That halves every world-building test
as well as the load time the player sees.

*Hands: two days · Agent: ~2 h + 1 suite run per item*

### P3 — `world/rules/`, and share the predicates that can be shared

1. New package `world/rules/`. Move `frontier.py` and `inset.py` in
   unchanged; move `can_cross`, `can_step`, `diagonal_blocked` and
   `_flight_opens` out of `elevation.py` into `rules/steps.py`, leaving
   `LevelIndex` where it is.
2. `rules/floor.py`: `point_on_floor(layout, x, y)`, `room_of(layout, x, y)`,
   `inset_at(layout, x, y)` — the bodies of `GameMap._point_ok`,
   `GameMap._room_of` and `pathfinding._point_on_floor` /
   `_point_inset_ok`, which are already pure functions of the layout.
   `GameMap` and `NavGrid` both call them. Two mirrored pairs stop existing;
   their P1 tests become tests of one function.
3. Delete the header paragraphs in `frontier.py` and `inset.py` that explain
   why they sit at the root of `world/`. That deletion is the tell that the
   move is right.
4. `tests/world/test_layering.py`: `world.rules` imports nothing from
   `world.gen`, `world.terrain`, `world.map` or `world.pathfinding`.

**Risk.** Low for the moves; medium for step 2, which is why P1 precedes it.

*Hands: one day · Agent: ~1 h + 2 suite runs*

### P4 — Cut the `terrain -> gen` edge

`biome_of`, `has_shoreline` and `scatter_mix` are lookups into
`data/terrain.json`; move them to `rules/biome.py`. `floor_palette` and
`assign_palettes` stay in `gen/biomes.py` because they *decide*. `sheets.py`,
`decor/budget.py` then read `room.palette` and `rules.biome`; delete the
`terrain/biome.py` shim. Extend the layering test: `world.terrain` imports
nothing from `world.gen`.

**Risk.** Low. The palette is already decided at generation and stored on
`Room.palette`; this only moves where the reader looks. The digest guards it.

*Hands: half a day · Agent: ~45 min + 1 suite run*

### P5 — Decision: retire the LD-8 generator *(recommended)*

See §4 for the evidence. If retired, in this order:

1. Delete `world/legacy/` (829 lines) and the branches that select it:
   `generate_world`'s flat / verticality arms, `bake.py`'s painter arm,
   `render.py`'s `_cliff_surfs` / `_room_surfs` pass, `LevelIndex._add_flat`
   for rooms (keep `_add_rect` for bridges).
2. Delete the config flags `HEIGHTMAP_ROOMS`, `WORLD_VERTICALITY`,
   `RAMP_STAIRS`, `CLIFF_CARVE`, `STRUCT_ANNEX`, `IRREGULAR_ROOMS`,
   `CHUNK_SIZE`, `WORLD_ROOM_COUNT` and their 19 reads; `tuning.special_kinds`
   collapses to a constant; the `_TREE_*` / `_TREE_*_GRID` pairs collapse.
3. Data model: `Stair` and `Room.annex` go (a height-map flight is a `Cell`);
   `TileMeta.cliff` / `cliff_var` / `lip` go; `Room.floor` becomes the base
   level it already is; the "Empty unless `config.HEIGHTMAP_ROOMS`" clauses
   on `grid` / `topography` / `palette` / `inset` become "always set".
4. Tests: retire the nine flag-pinning modules' LD-8 coverage
   (`test_verticality.py` 1,321 lines, most of `test_room_shapes.py`,
   `test_houses.py`, `test_obstacles.py`, `test_procedural.py`, and the
   flat-pinned halves of `test_terrain.py`, `test_depth_sort.py`,
   `test_pathfinding.py`). Anything in them that tests a rule the height-map
   world still has is moved onto the cache, not deleted.
5. `GameMap(seed=None)` — the single rectangular room with no layout — is not
   the legacy generator and stays; it is what every non-run test uses.

If kept instead: do the documentation plan's Phase 2 (`_generate_flat_layout`
/ `_generate_heightmap_layout`, `legacy/verticality.py` becomes
`gen/verticality.py`), and accept that every rule added from then on keeps
answering for three worlds.

**Digest.** Height-map seeds identical; the flat seeds' digests are deleted
with the mode.

*Hands: two to three days · Agent: several hours, several suite runs*

### P6 — `GenSettings`: generation reads one frozen snapshot

A frozen dataclass built once at the top of `generate_world(seed,
settings=None)` from the `HEIGHTMAP_*` and `TILE_PX` values, passed to every
stage that reads `config` today (`gen/__init__` 15 reads, `islands` 17,
`bridges` 9, `scatter` 7, `placement` 5, `graph` 5). Tests construct a
settings object instead of mutating `config`. Add `validate(layout)` — the
layout-level invariants the documentation plan lists (tile-aligned rects,
`cells` derived from `grid`, links traversable) — run from tests and from
`GameMap` when `config.DEV_MODE`.

**Why after P5.** With one mode the snapshot is thirty knobs and one
constructor; with three it is three shapes of knob and a mode field.

*Hands: one day · Agent: ~1.5 h + 2 suite runs*

### P7 — `world/nav/` and `BakedTerrain`

1. Split `world/pathfinding.py` (732 lines): `nav/lattice.py` (`NavGrid`),
   `nav/clearance.py` (chamfer), `nav/field.py` (`FlowField`, `NavField`).
   `NavGrid._elevation` imports the P3 step rule and becomes a cache of it.
   `world/pathfinding.py` stays as a shim while `game/states/playing` and the
   tests import it by name.
2. `terrain/baked.py`: a `BakedTerrain` dataclass holding the twenty-odd
   `_*` containers `GameMap.__init__` declares today; `bake(layout, assets)
   -> BakedTerrain`; painters take it instead of `gm`; `GameMap._build_tiles`
   stores it and keeps forwarding properties for the names tests read
   (`_grid_surfs`, `_shore`, `_decos`, `_room_decor`, `_void_decor`).
   The renderer reads `gm.terrain`. That is the whole of the documentation
   plan's Phases 4–5 that earns its cost: a headless bake becomes testable
   without a `GameMap`, and the mode signal (`_grid_surfs` non-empty) is
   gone with the mode.

**Digest.** Layout, bake and draw all identical.

*Hands: two days · Agent: ~2 h + 3 suite runs*

### P8 — Comments, docs, shims

The comment rule from §5 applied across `world/`; `level_design.md` §1–3
rewritten around the height-map world (it still describes 720 px chunks,
sixteen rooms, corner bites and a generator in `world/procedural.py`);
README's layout section; retire `world/gen/heightmap.py` (a sed over the
dozen test imports) and, once P4 lands, `world/terrain/biome.py`.
`world/procedural.py` **stays** — both documents keep it as the public entry.

*Hands: one day · Agent: ~1.5 h + 1 suite run*

### Order and dependencies

```
P0 harness -> P1 equivalence -> P2 speed -> P3 rules -> P4 cut edge
                                                  |
                                                  +-> P5 retire LD-8 -> P6 settings -> P7 nav + baked -> P8 comments
```

P2 can run in parallel with P3–P4 (different files). P5 is the only phase
that removes capability and the only one that needs a decision before it
starts.

**Decided 2026-09-02:** the LD-8 generator is retired, and P5 was moved up
to run straight after P0, so that no test module was migrated only to be
deleted and no gate had to be preserved through P2–P4. Executed order:
P0 → P5 → P1 → P2 → P3 → P4 → P6 → P7 → P8. Progress and evidence per phase
are in `journals/world_refactor_plan_journal.md`.

---

## 4. The decision: does the LD-8 generator ship?

Evidence for retiring it:

- `config.HEIGHTMAP_ROOMS` defaults to true and every level-design pass since
  LD-9 (journal sections A–X) was designed, tuned and measured on the
  height-map world only. The flat world's tuning constants are kept "because
  a dozen pinned-seed tests describe it" — the tests are the last consumer.
- The legacy path is 829 lines in `world/legacy/` plus branches in eight
  live modules, 19 flag reads, two extra data types (`Stair`, `Room.annex`),
  three `TileMeta` fields, and roughly 3,600 lines of tests that exist to
  pin it seed by seed.
- Every rule written since LD-9 opens with `if not room.grid: return` or a
  `config.HEIGHTMAP_ROOMS` gate. The refactor journal's own words: every
  generation change "needed a gate precisely because the two models shared
  files".
- Three generation-stage behaviours already differ by mode on purpose
  (tree spacing, start / boss island scatter, obstacle radius in `_blocks`).
  That is two games' worth of rules in one function.

Evidence for keeping it: none in the tree. The flat renderer fallback
(`_draw_flat_layout`, "playable with an empty `assets/`") is a *rendering*
fallback over the same layout and is unaffected either way.

What retiring does **not** save: suite time. A flat world builds in
milliseconds; the forty-seed sweeps are cheap. The saving is in every future
rule, every comment, and the three-way branch in `generate_world`.

---

## 5. Comments: a rule, not a sweep

The journal todo says not to touch the comments, because this codebase
explains *why* and several findings were only findable because a decision
was written down where it was made. That is right and the rule below keeps
it. What has aged is not the reasoning but its **addressing**: milestone
tags that mean nothing without the journal, and sentences whose whole job
is to reassure a reader that a flag-off world stays byte-identical.

Census across `world/`: 30 `LD-8`, 24 `LD-9`, 21 `LD-10`, 39 `LD-1`…`LD-3`,
27 `W0`…`W6`, 8 `spec x.y`, and 32 lines whose subject is "flag-off",
"legacy" or "byte-identical".

**The rule.**

1. State the rule in the present tense. A tag (`LD-9 D8:`, `W1 split of`,
   `spec 5.4`) is not a reason; if the history matters, name the journal
   section by its title so it can be found after the tags are forgotten.
2. Keep every sentence that says *why* and every measurement that justified
   a choice. Those are the comments that paid for themselves.
3. Delete "with the flag off this is byte-identical" and "the legacy
   generator keeps the old rule" wherever P5 deletes the flag. If the flag
   is kept, say it **once**, at the gate, not at every site the gate protects.
4. A module header describes what the module is now, not the milestone that
   created it. `terrain/__init__.py` currently says W2–W6 are "all currently
   inside `GameMap`", which stopped being true on 2026-08-30.
5. Field comments on the data model say what a field holds; "Empty unless
   `config.HEIGHTMAP_ROOMS`" becomes "always set" or goes.

**Examples.**

`world/gen/__init__.py`, module header — before:

> Seeded procedural world generation (spec 5.2 / 5.4). Authored chunks
> assembled procedurally, not per-tile noise. […] W1 of
> journals/world_refactor.md split the stages into sibling modules; this
> module keeps only the orchestrator.

after:

> Seeded world generation. The world is a lattice of chunk cells grown as a
> tree from the start cell, so every island is reachable by construction;
> each island is then given a height map, bridges are seated on its beaches,
> a palette is chosen per terrace, and obstacles are scattered last, in
> final coordinates. `generate_world(seed)` is pure: one seed, one
> `WorldLayout`. This module is the pipeline; each stage lives beside it.

`world/gen/scatter.py`, the start / boss skip — before:

> LD-10: on a height-map world the start and boss islands scatter like any
> other. The LD-8 rule skipped them outright — a safe spawn and a clear fight
> arena — and it was written when a room was ~60 cells. On a 1,000-cell
> island it left two of the nine as bare slabs, a fifth of all the land.
> Each keeps a clear disc instead (below); the flat generator keeps the old
> skip, being pinned seed by seed in its tests.

after (P5 retired):

> The start and boss islands scatter like any other. Skipping them outright
> — a safe spawn, a clear arena — left two of nine islands as bare slabs, a
> fifth of all the land. Each keeps a clear disc instead: `_GRID_SPAWN_CLEAR`
> round the hero's pixel, `_GRID_BOSS_CLEAR_RADIUS` round the boss.

`world/layout.py`, `Room.palette` — before:

> LD-10: `{level: sheet}` — which ground tileset each terrace of this island
> wears. Decided at generation (`world/gen/biomes.py`) rather than at bake,
> because the obstacle scatter reads the biome as well as the tile painter
> does, and one authority is the point. Empty unless
> `config.HEIGHTMAP_ROOMS`.

after:

> `{level: sheet}` — which ground tileset each terrace wears. Decided at
> generation, not at bake, because the obstacle scatter reads the biome as
> well as the tile painter does, and one authority is the point.

`world/frontier.py`, header paragraph two — deleted outright by P3: "It is
deliberately free of every other world module — `world/terrain` already
depends on `world/gen`, so putting this in either package would close a
cycle." Once it lives in `world/rules/` with a layering test, the package
says this.

`world/elevation.py`, the four paragraphs on sub-tile room offsets with the
flag off — deleted by P5. The sentence that survives: "**This answers
elevation, not walkability.** `point_on_floor` is the authority on whether a
point is floor."

---

## 6. What not to change

Merged from both documents, so a later pass does not "tidy" them:

- **The reasoning in the comments** (§5 rewrites the addressing, never the
  argument).
- **Data-driven tuning.** Values live in `data/terrain.json` with no code
  defaults.
- **Seeded determinism.** String-keyed RNG per room and per concern, with
  `getstate` / `setstate` around passes that must not perturb the stream.
- **The `world/gen/height/` split.** One concern per module; it is the shape
  the rest moves toward.
- **The public surface.** `world.procedural.generate_world`,
  `world.map.GameMap`, the renderer-facing methods, and lazy baking: no
  asset work is required for headless generation or runtime geometry.
- **No generic `common` package.** `world/rules/` is a layer with a stated
  import direction and a test that enforces it. If something cannot be
  placed under that rule, it does not go there.
- `world/procedural.py` as the compatibility entry point.

---

## 7. Verification protocol

For every phase:

1. `pytest` (default tiers) green, then `pytest -m sweep` green, then
   `python -m unittest discover -s tests -t .` green (the README command; it
   must keep working).
2. `tests/world/test_digest.py` unchanged, unless the phase's notes say which
   digest moves and why. A phase that moves a digest it did not expect to
   stops until the cause is understood.
3. For P2 items and P0's cache: the same instrumented count of
   `generate_world` calls and the same wall-clock, before and after.
4. `journals/world_refactor.md` gets a section; `journals/journal.md` a
   paragraph pointing at it: what was done, what was verified, what was
   deferred, the exact next item.

## 8. Effort summary

| Phase | Hands | Agent | Removes | Adds |
|---|---|---|---|---|
| P0 harness | 1 d | 2 h + 2 runs | six private caches, per-test rebuilds | `tests/worlds.py`, `world/digest.py`, `pytest.ini` |
| P1 equivalence | 1 d | 1 h + 1 run | — | five tests |
| P2 speed | 2 d | 2 h + 4 runs | ~50 % of a world build | — |
| P3 rules | 1 d | 1 h + 2 runs | two mirrored pairs, two header apologies | `world/rules/`, layering test |
| P4 cut edge | ½ d | 45 min + 1 run | `terrain -> gen`, one shim | `rules/biome.py` |
| P5 retire LD-8 | 2–3 d | several h | 829 + ~3,600 lines, 8 flags, 19 reads | — |
| P6 settings | 1 d | 1.5 h + 2 runs | ~60 `config.` reads in `gen/` | `GenSettings`, `validate` |
| P7 nav + baked | 2 d | 2 h + 3 runs | 732-line module, 20 `_*` fields on `GameMap` | `world/nav/`, `BakedTerrain` |
| P8 comments | 1 d | 1.5 h + 1 run | ~150 tag references, two shims | rewritten `level_design.md` §1–3 |

Roughly twelve working days by hand, or a few sessions with an assistant
whose limiting cost is suite runs — which is the reason P0 is first.
