# World generation refactor — execution journal

Progress log for `documentation/worldgen_refactor_plan.md`. One section per
phase: what was done, what was verified, what was deferred, the next item.
The plan document is the *what*; this is the *when* and the *evidence*.

**Baseline** (2026-09-02, tree `b0114d6`): 946 tests; the world-facing
modules (`tests/world`, `test_pathfinding`, `test_terrain`,
`test_depth_sort`) take 15 min 52 s for 411 tests, 73 % of it in
`test_repair.py` (456 s) and `test_obstacle_families.py` (238 s), both of
which rebuild their worlds inside every test. A height-map world costs 1.5 to
2.3 s to generate.

---

## Decisions (2026-09-02)

- **The LD-8 generator is retired.** The user's call, after §4 of the plan.
  Only the height-map world ships; `GameMap(seed=None)` (no layout) and the
  flat *renderer* fallback stay.
- **P5 moves up to run straight after P0.** The plan had P1–P4 before it so
  the digest and the equivalence tests would guard the moves. With the
  decision made, migrating nine flag-pinning test modules onto the world
  cache only to delete them in P5 is wasted work, and every gate P2–P4 would
  otherwise have to preserve disappears first. New order:
  **P0 → P5 → P1 → P2 → P3 → P4 → P6 → P7 → P8.**
- **Tests are refined as each phase touches them**, not in a separate pass:
  any module a phase opens moves onto the shared cache and loses its
  per-test rebuilds and module-scope flag flipping.

---

## P0 — Harness — DONE (2026-09-02)

**What was done.**

- `tests/worlds.py`: one `GameMap` per `(seed, config overrides, module
  patches)` per process; `layout` / `game_map` / `levels` / `baked` / `nav`
  accessors, `fresh()` for tests that mutate, `settings()` to apply and
  restore overrides. Plain functions, so the unittest runner is untouched.
- `world/digest.py` + `tests/world/test_digest.py` + `tests/world/digests.json`:
  a sha256 walk of the whole data model (layout), every baked surface and
  anchor list (bake), and one composited frame (draw), pinned for seeds
  35 / 7 / 1234 / 42. Stable across processes. `python -m world.digest
  --write` re-pins after an intended change.
- `pytest.ini` + `tests/conftest.py`: `unit` / `world` / `sweep` markers
  assigned by path; the default run excludes `sweep`. README updated with
  the three invocations.
- Migrated onto the cache: `test_repair`, `test_obstacle_families`, the six
  modules with private caches (`test_decor_density`, `test_decor_frontiers`,
  `test_prop_coverage`, `test_water_decor`, `test_elevation`, `test_inset`),
  `test_enemy_nav`, `test_biome`, `test_projectile_elevation`, and the
  formerly flat-pinned `test_pathfinding`, `test_depth_sort`, `test_terrain`.
  Every module-scope `config.HEIGHTMAP_ROOMS` flip is gone; the two override
  variants that remain (`HEIGHTMAP_UNSEAL`, `HEIGHTMAP_SHORTCUTS`) are cache
  keys.
- Retired with the LD-8 decision (their LD-8-only tests) and re-homed where
  a rule still applies: `test_procedural` → `test_layout` (structure, tile
  alignment, floor mask); `test_room_shapes` → `test_layout` (random point
  on floor); `test_houses` and `test_obstacles` rewritten on the cache;
  `test_verticality` deleted. Determinism tests everywhere replaced by the
  single digest determinism test.

**Production changes along the way** (none moves the digest):

- `TerrainRenderer.seconds()` / `.clock`: the four `pygame.time.get_ticks()`
  reads now go through one seam so the frame digest can pin animation time.
- `GameMap._build_tiles()` is idempotent. A second call appended every
  terrace surface again; the shared maps made that visible.
- `FlowField.direction_at`: when two opposite downhill neighbours of equal
  cost cancel the gradient to zero, steer to the single best neighbour
  instead of reporting "no direction". Found by `test_pathfinding`'s
  gradient walk the moment it ran on a height-map world; an enemy on such a
  cell froze.

**Verified.** Default tier green (943 passed) in 8 min 31 s on the first
checkpoint, which still included the LD-8 modules; the end-of-phase run is
recorded below. Digest unchanged throughout. `test_repair` 456 s → 65 s
(one 20-seed sweep deselected); `test_obstacle_families` 238 s → 12 s
outside its one sweep.

**Deferred.** The 90 s target for the default tier is not met yet: the
remaining cost is the tests' own per-cell sweeps (`test_elevation`'s
flight sweep, 20 s) and the game-level tests that boot a run
(`test_dev_mode`, `test_smoke`). P2's generation speed-up halves the
build cost that is left; the rest is P4-era R4 work (push assertions from
worlds to hand-built grids) and is not on the critical path.

**Next.** P5: delete `world/legacy/`, the flags and the branches.

---

## P5 — Retire the LD-8 generator — DONE (2026-09-02)

**What was done.**

- Deleted `world/legacy/` (829 lines) and every branch that selected it:
  `generate_world` is the height-map pipeline only (276 → 190 lines, one
  path); `bake.py` keeps the terrace painter and the shared finish;
  `render.py` lost the band compositor and its foam closure; `sheets.py`
  lost `raised_idx`, `vstair_overlay`, `three_sided`; `elevation.py` lost
  `_add_flat` and now raises on an unaligned island instead of falling back.
- Deleted the flags and their reads: `HEIGHTMAP_ROOMS`, `WORLD_VERTICALITY`,
  `IRREGULAR_ROOMS`, `ROOM_SIZE_MAX_CELLS`, `CHUNK_SIZE`, `WORLD_ROOM_COUNT`,
  `CLIFF_TILES`, `CLIFF_CARVE`, `RAMP_*`, `STRUCT_ANNEX`, `STAIR_WIDE_EVERY`.
  `tuning.py` is half its size; `special_kinds()` collapsed into
  `SPECIAL_KINDS` (elite arenas stay dormant in the interactable code).
- Data model: `Stair`, `Room.annex`, `TileMeta.cliff / cliff_var / lip`,
  `WorldLayout.stairs` are gone; `gen/rooms.py` keeps only the lattice
  rect, the full mask and the connectivity check; `gen/links.py` keeps only
  the lane geometry; `gen/graph.py` lost `_assign_floors`.
- Tests: `test_verticality`, `test_room_shapes`, `test_procedural` retired
  (their still-valid invariants live in `test_layout`); `test_houses`,
  `test_obstacles`, `test_pathfinding`, `test_depth_sort`, `test_terrain`
  run on height-map worlds. Fourteen assertions that only held for the flat
  world were ported or dropped -- each is named in the module.

**Verified.** The world is byte-identical: a schema-independent fingerprint
(rooms, grids, tile meta, palettes, inset fields, bridges, obstacles,
bounds) matched the committed tree for all four pinned seeds, and the bake
and frame digests did not move. The layout digest *did* move, because it
walks every dataclass field and five fields no longer exist; it was re-pinned
with that explanation. Default tier: 845 passed.

**Found on the way.** Two order-dependent failures in the shared-cache
world, both fixed: a depth-sort test replaced three painter methods on the
shared seed-7 renderer and never restored them (now `mock.patch.object`),
and `test_water_decor`'s determinism test baked fresh maps after another
module had quit the display.

---

## P1 — Equivalence tests — DONE (2026-09-02)

`tests/world/test_mirrors.py`: `_point_on_floor` ↔ `GameMap._point_ok`
(every tile corner of every island, nudged both ways, plus bridge mouths
and 4,000 random points), `_point_inset_ok` ↔ `GameMap.inset_ok` (same
sample), and `repair._killers` ↔ `NavGrid._clearance_transform` (every
walkable cell at the widest class). `test_elevation` already covered
`walk_links` ↔ `can_cross` and `can_step` ↔ `step_mask`. Each new test was
seen red by breaking its mirror on purpose (a one-pixel shift, a halved
margin, a shortened reach) before being trusted.

---

## P2 — Generation speed — DONE (2026-09-02)

The profile in the plan overstated `scatter._blocks` (cProfile inflates
tiny hot functions); wall-clock timers per stage gave the real picture for
seed 7: inset field 1.33 s of 2.10 s, of which 28 chamfer sweeps 0.88 s;
`build_grid` 0.35 s; `unseal` 0.20 s; the whole scatter 0.19 s.

**What was done**, every item leaving the layout digest untouched:

- `NavGrid` rasterises its floor mask from the island cells and bridge
  rects outward instead of point-testing ~50 k cell centres against every
  island; the terrace margin is read off the owning island directly.
  `NavGrid(32)` 0.48 s → 0.25 s, paid at generation (`unseal`) and again at
  run time.
- `scatter`: keep-clear rects are bucketed per island (`_doors_near`), so a
  placement try scans ~150 rects instead of ~1,400. Small in wall-clock
  terms; kept because it is free.
- `inset`: seeds are filled per tile rather than per sample (64× fewer
  lookups); the per-level seed masks are byte translations instead of
  Python loops; and each upper terrace's chamfer runs on its own bounding
  box widened by the clamp distance, which cannot change any stored value
  (a chamfer path shorter than `CAP` spans fewer samples than the widening).
  The chamfer sweep itself is untouched: it stores float32 after every
  sample, and a vectorised version would round differently.

**Result.** Per world: seed 35 2.04 → 1.42 s, seed 7 2.34 → 1.64 s,
seed 1234 1.68 → 1.24 s, seed 42 1.45 → 1.10 s (about 30 %). The remaining
cost is the chamfer sweep (0.57–0.90 s a world). Going further means either
numpy (a new dependency, and a different float path) or a lower sample
pitch (a behaviour change); both are decisions, not refactors, and are left
on the table.

**Next.** P3: `world/rules/`.

---

## P3 — `world/rules/` — DONE (2026-09-02)

- `world/rules/` holds `frontier.py` and `inset.py` (moved, `git mv`, with
  the header paragraphs explaining why they sat at the root of `world/`
  deleted -- the tell that the move was right), `steps.py` (`can_cross`,
  `can_step`, `diagonal_blocked`, `_flight_opens`, lifted out of
  `elevation.py`, which keeps `LevelIndex` and its sentinels), and
  `floor.py`.
- `floor.py` is the one body of the floor test and the terrace-margin test:
  `point_on_floor`, `room_of`, `in_corridor`, `inset_at`, `inset_ok`.
  `GameMap._point_ok` / `_room_of` / `inset_at` call it; the navigation
  grid's `_point_on_floor` / `_point_inset_ok` / `_point_in_corridor` are
  aliases of it. Two mirrored pairs stopped existing; `test_mirrors` pins
  that they stay one function rather than sampling two.
- `tests/world/test_layering.py`: `world.rules` imports nothing from
  `world.gen`, `world.terrain`, `world.map`, `world.pathfinding` or
  `world.elevation`; `elevation.py` and `layout.py` have their own bans.
  The first run caught a typing-only import of `LevelIndex` in `steps.py`,
  which went.

**Verified.** Digest unchanged; the P3 guards (layering, mirrors, inset,
elevation, pathfinding, digest) 95 passed.

**Next.** P4: cut the `terrain -> gen` edge.

---

## P4 — Cut the `terrain -> gen` edge — DONE (2026-09-02)

`biome_of`, `has_shoreline` and `scatter_mix` -- lookups into
`data/terrain.json` saying what a sheet *is* -- moved to
`world/rules/biome.py`. `world/gen/biomes.py` keeps the decisions
(`floor_palette`, `assign_palettes`) and re-exports the lookups for the
callers that grew up with them. `sheets.py`, `decor/budget.py` and the
scatter read the rules module; the `terrain/biome.py` shim is deleted. The
layering test now also bans `world.gen` from `world.terrain`.

**Verified.** Digest unchanged; layering, biome, decor and digest tests 77
passed.

**Next.** P6: the generation settings snapshot.

---

## P6 — `GenSettings` and `validate` — DONE (2026-09-02)

- `world/gen/settings.py`: a frozen `GenSettings` snapshotting the thirty
  `HEIGHTMAP_*` knobs and `TERRAIN_BUILDINGS` from `game.config`, built once
  at the top of `generate_world(seed, settings=None)` and passed to every
  stage that reads a knob (`assign_topography`, `_resize_by_topography`,
  `_build_room_grids`, `_seat_corridors` and its shortcut pass,
  `assign_palettes`, `_scatter_obstacles`, the `unseal` gate;
  `coast_shape` takes the preset table as an argument). Every stage still
  accepts `settings=None` and reads today's config, so a test driving one
  stage alone needs nothing new. `TILE_PX` stays a global: it is the
  world's grid unit, shared with the data, the bake and the renderer.
  `GenSettings.from_config(unseal=False)` is the test-side replacement for
  mutating the global, pinned by `test_layout.SettingsTests` to produce the
  same world.
- `world/gen/validate.py`: every promise a finished world makes, read back
  as a list of sentences -- tile-aligned rects, `cells` the walkable subset
  of `grid`, `check_grid` per island, a palette for every terrace, tile meta
  covering exactly the floor, an inset field wherever there are terraces,
  bridges reaching both islands and one tile wide, connectivity, bounds at
  the origin, obstacles on floor. `test_layout` runs it on every cached
  world and checks it notices a broken one.
- It found a stale invariant on its first run: `check_grid` still said a
  flight may *touch* ground of another level only at its ends (the band-era
  rule), and seed 35 has a straight flight cut on a plateau's west flank
  with the low terrace beside it. The runtime treats that edge as it
  treats every flank -- a wall with no stone -- and `walk_links` never
  linked it, so the world is sound and the check was wrong. The check is
  gone and the invariant list in `world/gen/height/__init__.py` now says
  what the terrain actually promises.

**Verified.** Digest unchanged; `test_layout`, digest, repair, houses,
biome, layering green.

**Next.** P7: `world/nav/` and `BakedTerrain`.

---

## P7 — `world/nav/` and `BakedTerrain` — DONE (2026-09-02)

- `world/pathfinding.py` (732 lines) is `world/nav/lattice.py` (`NavGrid`,
  335), `nav/clearance.py` (the chamfer transform as a function, 105) and
  `nav/field.py` (`FlowField`, `NavField`, 350), moved by slicing the source
  at its class boundaries. `world/pathfinding.py` is an 11-line shim
  re-exporting every name the game and the tests import, private ones
  included. Two things the slice missed and the guards caught at once: the
  `_SQRT2` constant `FlowField` weights its diagonals with, and the `config`
  import.
- `world/terrain/baked.py`: `BakedTerrain`, a dataclass holding what the
  bake produces -- the terrace and bridge surfaces, the shore anchors, the
  water buffer, foam frames and routines, obstacle skins, tree shades,
  interior clutter and water scenery -- plus `point_ok` (the collider's
  floor rule, from `world/rules/floor.py`) and the foam frame picker.
  `bake(layout) -> BakedTerrain` no longer touches the map; the painters
  and the decor builders take the baked result as their store.
  `GameMap.terrain` holds it after the first draw, and the old private
  names (`_grid_surfs`, `_decos`, `_shore`, ...) are forwarding properties,
  so the renderer, the digest and the tests read what they always read.
  `GameMap` is 20 fields lighter.
- Retained on purpose: the renderer still reads the baked fields through
  `GameMap`'s forwarders rather than `gm.terrain` directly. The plan scaled
  P7 to "a `BakedTerrain` dataclass only, no renderer rewrite", and the
  forwarders cost nothing.

**Verified.** All three digests unchanged (the bake digest reads through the
same names it always did); nav, elevation, mirrors, repair, inset, terrain,
depth-sort, decor, biome, projectile and layering guards green.

**Next.** P8: comments and docs.

---

## P8 — Comments, docs, shims — DONE (2026-09-02)

- The comment rule from the plan (§5) applied across `world/`: every
  milestone tag (`LD-n`, `Wn`, `Dn`, `Mn`, `Tn`, `spec x.y` where it meant a
  milestone) is gone or restated as the rule in the present tense; every
  "with the flag off this is byte-identical" and "the legacy world keeps the
  old rule" sentence is gone with the flag; module headers say what the
  module is now. Every *why* and every measurement stayed. The `spec 3.4` /
  `spec 6.3` references in `spawning.py` stayed too: they name a real
  document (`documentation/death_must_die_lite_game_spec.md`), not a
  milestone.
- `documentation/level_design.md` §1–3 and §5 rewritten around the island
  world (they still described 720 px chunks, sixteen rooms, corner bites and
  a generator in `world/procedural.py`); §4 updated for the biome tables.
  README's layout block and test section updated.
- Shims retired: `world/gen/heightmap.py` (importers repointed at
  `world.gen.height.*`) and `world/terrain/biome.py` (P4).
  `world/procedural.py` stays as the public entry, as both plans required;
  `world/pathfinding.py` stays as the nav re-export.
- `build_grid` lost its `**_legacy` keyword swallower; `check_grid` and the
  height-map invariant list say what the terrain promises today.

---

## Outcome (2026-09-02)

Every phase of `documentation/worldgen_refactor_plan.md` is done, in the
reordered sequence P0 → P5 → P1 → P2 → P3 → P4 → P6 → P7 → P8.

| | before (`b0114d6`) | after |
|---|---|---|
| default test run | ~20 min (946 tests, no tiers) | **6 min 36 s** (855 passed, 1 skipped; 7 sweep tests deselected) |
| sweep tier | — | 2 min 10 s (7 tests) |
| `python -m unittest discover -s tests -t .` | green | green (everything, no tiers) |
| height-map world, seed 35 / 7 | 2.04 s / 2.34 s | 1.42 s / 1.64 s |
| `world/` source | 8,100 lines incl. 829 legacy | 66 files changed, 1,444 added, 6,388 removed (tree-wide) |
| mode flags read outside `config.py` | 19 | 0 |
| rules implemented twice | 5, none tested for agreement | 2 (flight rule, clearance), both tested; 3 became one function |

The world is byte-identical to the committed tree for every pinned seed: the
bake and frame digests never moved; the layout digest moved once, for the
schema (five deleted fields), with a field-by-field comparison against the
committed tree proving the world itself unchanged.

**Left on the table, deliberately.**

- The 90 s target for the default tier is not met (6:36). What is left is
  the tests' own work, not world building: `test_passable_never_out_runs...`
  (40 s, every cell at every enemy radius), the flight sweeps in
  `test_elevation` (20 s), and the game-level tests that boot a run
  (`test_dev_mode`, `test_smoke`). The plan's R4 -- push assertions from
  generated worlds down to hand-built grids -- is the next lever and was
  not on the critical path.
- The inset chamfer is 0.6–0.9 s of every world. Going further means numpy
  (a new dependency and a different float path) or a coarser sample pitch
  (a behaviour change): a decision, not a refactor.
- The renderer reads the baked fields through `GameMap`'s forwarding
  properties rather than `gm.terrain` directly (P7, by design).
- `_lateral_site` can cut a straight flight on a plateau's flank with the
  low terrace beside it (seed 35, island 3). The runtime treats that edge
  consistently as a wall; whether generation should avoid it is a design
  question for the level-design journal.
- Line endings: the rewritten files are LF; git will normalise them to the
  repository's CRLF on commit (`core.autocrlf`), which is why `git status`
  warns.

Nothing is committed.
