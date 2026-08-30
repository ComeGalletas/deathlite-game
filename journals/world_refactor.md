# World refactor — dev log

Splitting the two 1.4k-line world files —
[`world/map.py`](../world/map.py) (1414 lines, one `GameMap` class doing four
unrelated jobs) and [`world/procedural.py`](../world/procedural.py) (1360 lines,
data models + every generation stage in one module) — into focused
sub-packages, one concern per module. Same play `journals/playing_state_refactor.md`
ran on `PlayingState` (1386 → 735); the general `journal.md` gets a
one-paragraph pointer here once this lands.

Milestones are **W0–W7**. Each ends with the **full suite green**
(`python -m unittest discover -s tests -t .` — the `-t .` is required) and,
where it touches the bake or the draw path, a determinism A/B check and/or a
headless screenshot. **Nothing is committed unless the user asks.**

**Baseline:** suite **714 green** (2026-08-30), `world/map.py` 1414,
`world/procedural.py` 1360.

**Status:** **COMPLETE** (W0-W7, 2026-08-30). `world/procedural.py`
1360 -> 22 (shim); `world/map.py` 1414 -> 418. Ten focused modules under
`world/gen/` and `world/terrain/`. Suite **714 green** throughout; generation,
the terrain bake, and the composited draw output each A/B-verified
byte-identical. Nothing committed.

Earlier: W5 -- decor bakes -> `world/terrain/decor.py`; bake identical
(`78d7ed0d...`). W4 -- room / corridor / cliff / stair painters ->
`world/terrain/{rooms,cliffs}.py`; bake identical (`755d77b3...`). W3 --
autotile helpers -> `world/terrain/autotile.py`. W2 -- tileset closures ->
`world/terrain/sheets.py` `TileSheets`.

Earlier: W3 — autotile helpers → `world/terrain/autotile.py` (`GameMap` keeps
`staticmethod` aliases); bake identical. W2 — nine tileset closures →
`world/terrain/sheets.py` `TileSheets`; bake identical. W1 —
`world/procedural.py` 1360 → 22 shim; five `world/gen/` stage modules +
orchestrator; generation byte-identical (`801f92e7…`). W0 — models →
`world/layout.py`.

---

## Why

`world/map.py`'s `GameMap` is four things welded together:

1. **Physics / queries** (~200 ln) — `is_walkable`, `resolve_movement`,
   `room_at`, `random_point_in_room`, `offscreen_spawn_point`. Its original
   Phase-3 identity: the world as a collision surface.
2. **Terrain bake** (~750 ln) — `_build_tiles` is *one method* holding nine
   nested closures (`three_sided`, `cell`, `sheet_for`, `cliff_idx`,
   `raised_idx`, `paint_room`, `paint_corridor`, `paint_cliff` ≈ 250 ln alone,
   `paint_stair`), plus `_build_obstacle_decor` / `_build_tree_shadows` /
   `_build_decor_scatter`. Every LD-1…LD-6 milestone landed here. It is the
   most-churned, least-isolated code in the repo.
3. **Terrain draw** (~350 ln) — `draw_ground`, `_draw_tiled`,
   `scenery_drawables`, `draw_room_clutter`, `draw_tree_shadows`,
   `_draw_obstacles`, `shade_character_frame`, `_z_surf`, foam-frame picking.
4. **Autotile math** — `_slot_for`, `_mask_slot`, `_bridge_slot` (pure, static).

`world/procedural.py` is flatter — the five data models (`TileMeta`, `Room`,
`Corridor`, `Stair`, `WorldLayout`), the `generate_world` orchestrator
(~155 ln), then room-shape carving, graph / floor assignment, link splitting,
ramp planning, cliff carving, tile-meta derivation, and obstacle / tree / house
scatter — all in one file.

### The key seam: `TileSheets`

Nine closures inside `_build_tiles` capture ~15 locals (`px`, `interior`,
`slots`, `cliff_slots`, `raised_slots`, `ramp_slots`, `palettes`,
`floor_sheets`, `bridge_ok`, the two caches, …). That capture is the reason the
painters cannot move out. Extract **one object** that owns the tileset-metadata
adapter and the caches — `cell()` / `sheet_for()` / `cliff_idx()` /
`raised_idx()` / `three_sided()` + the slot constants — and hand it to
`paint_room(sheets, store, r)` etc. The closure nest collapses into ordinary
module functions.

Painters take the `TerrainStore` the same way the playing sub-systems take `ps`;
each module docstring lists which fields it reads and which it appends to.

---

## Target structure

```
world/
├── map.py              GameMap — FACADE. __init__ wiring, the physics/query
│                       API (is_walkable, resolve_movement, room_at, spawn
│                       points), and 3-line delegators for draw_*.        (~260)
├── layout.py           TileMeta, Room, Corridor, Stair, WorldLayout
│                       (+ tile_at, bfs_distances, is_connected).
├── procedural.py       shim: `from world.gen import generate_world` +
│                       re-export the models. Keeps every existing import.
├── gen/
│   ├── __init__.py     generate_world — the orchestrator body ONLY, still
│   │                   readable top-to-bottom as a sequence of stage calls.
│   ├── rooms.py        room-shape carving + growth + relink.
│   ├── graph.py        adjacency, spanning tree, floor assignment, kinds.
│   ├── links.py        connection lanes, _split_links, corridor doorways.
│   ├── verticality.py  ramps, annex, cliff carving, _build_tile_meta.
│   └── scatter.py      obstacles, tree top-up, houses.
└── terrain/
    ├── __init__.py
    ├── sheets.py       TileSheets — the closure nest as one object:
    │                   cell() / sheet_for() / cliff_idx() / raised_idx() /
    │                   three_sided() + the slot constants. Reads
    │                   assets.terrain. Passed to every painter.
    ├── autotile.py     slot_for / mask_slot / bridge_slot (pure).
    ├── bake.py         TerrainStore — holds the baked Surfaces + anchor
    │                   lists (_room_surfs, _corr_surfs, _cliff_surfs,
    │                   _cliff_foam, _cliff_shadow, _shore, decor, tree
    │                   shadows). build() sequences the painters.
    ├── rooms.py        paint_room, paint_corridor.
    ├── cliffs.py       paint_cliff, paint_stair (the LD beast, isolated).
    ├── decor.py        obstacle-decor / tree-shadow / decor-scatter bakes.
    └── render.py       TerrainRenderer — draw_ground / _draw_tiled /
                        scenery_drawables / draw_room_clutter /
                        draw_tree_shadows / _draw_obstacles / _draw_grid /
                        shade_character_frame / _z_surf / foam picking.
```

`world/map.py` keeps exporting `GameMap`; `world/procedural.py` re-exports
`generate_world` + the models. No call site outside `world/` changes.

### How the pieces talk

- **Pass the store / layout in**, don't invent an abstraction — the proven
  pattern from the playing refactor (P1–P6 passed `self`). Generation stages
  take `(rng, rooms, edges, …)` explicitly and stay pure; terrain painters take
  `(sheets, store, …)`.
- Every new module's docstring **must** list the exact attributes / fields it
  reads and the ones it writes.
- For the internals the tests reach (`gm._cliff_surfs`, `gm._build_tiles()`,
  `gm._mask_slot`, `gm._cliff_foam`, …), keep a one-line forwarder on `GameMap`
  (`@property` for the moved attributes, a re-bind for the static helpers) —
  the same "delegator only for what a test touches" rule the playing refactor
  used. **8 test files** reach in today: `tests/ai/test_pathfinding.py`,
  `tests/rendering/test_depth_sort.py`, `tests/rendering/test_terrain.py`,
  `tests/world/test_houses.py`, `tests/world/test_obstacles.py`,
  `tests/world/test_obstacle_families.py`, `tests/world/test_room_shapes.py`,
  `tests/world/test_verticality.py`.

---

## Milestones

| # | Scope | Risk | Ends when |
|---|-------|------|-----------|
| **W0** | Scaffold. Create `world/gen/` + `world/terrain/` packages. Move the five data models verbatim to `world/layout.py`; `procedural.py` imports them back and re-exports. No logic moves. | ~zero | all import paths (`world.procedural`, `world.map`, `world.layout`) resolve; suite green |
| **W1** | `procedural.py` generation functions → `world/gen/{rooms,graph,links,verticality,scatter}.py` (flat moves + import fixups). `generate_world` orchestrator body → `world/gen/__init__.py`. | low | **determinism A/B**: seeds 0–40 → byte-identical `WorldLayout` (rooms, cells, tile_meta, corridors, stairs, obstacles) |
| **W2** | Extract `TileSheets` from the `_build_tiles` closure nest into `world/terrain/sheets.py`. `_build_tiles` constructs one and the closures become method calls. Bake output unchanged. | medium | `test_terrain` green + bake pixel-hash A/B (seeds 0–40) |
| **W3** | `_slot_for` / `_mask_slot` / `_bridge_slot` → `world/terrain/autotile.py` (pure). `GameMap._mask_slot` re-bound for tests. | low | suite green |
| **W4** | `paint_room` / `paint_corridor` → `world/terrain/rooms.py`; `paint_cliff` / `paint_stair` → `world/terrain/cliffs.py`, taking `(sheets, store)`. `_build_tiles` becomes a readable bake sequence. | **high** | bake pixel-hash A/B (seeds 0–40) identical |
| **W5** | `_build_obstacle_decor` / `_build_tree_shadows` / `_build_decor_scatter` → `world/terrain/decor.py`. | low | `test_terrain` decor + `test_obstacles` green; scatter still deterministic per seed |
| **W6** | Draw half → `world/terrain/render.py` as `TerrainRenderer`; `GameMap.draw_ground` / `scenery_drawables` / `draw_room_clutter` / `draw_tree_shadows` / `shade_character_frame` become 3-line delegators. `GameMap` down to physics + facade (~260 ln). | low (pure output) | screenshots identical (ground, cliffs, foam, room clutter, F7 grid, tree shadows) |
| **W7** | Docs. This file finished (status + "Where things live now" table). One-paragraph pointer in `journals/journal.md`. `README.md` project-layout — `world/` line updated. | — | — |

### Sequencing note

W0+W1 alone take `procedural.py` from 1360 → ~155 (orchestrator) + five focused
modules at near-zero risk, and prove the pattern before anything touches the
bake. **W2 is the unlock** — the `TileSheets` extraction is what lets every
painter leave `map.py`. **W4 carries the risk** (the painters are where LD-1…6
churn lives); gate it on a pixel-hash A/B. W6 is pure output — screenshots.

## Verification per milestone

- `python -m unittest discover -s tests -t .` green before moving on.
- **Generation determinism (W1):** an A/B script generates seeds 0–40 before
  and after and diffs the full `WorldLayout` — room rects / cells / tile_meta,
  corridor + stair fields, obstacle list. Expect identical.
- **Bake determinism (W2, W4, W5):** the same seeds, baked headless; SHA-256
  every entry of `_room_surfs` / `_corr_surfs` / `_cliff_surfs` and every anchor
  list (`_cliff_foam`, `_cliff_shadow`, `_shore`, decor instances). Expect
  identical.
- **Draw (W2, W6):** windowed / headless screenshots of a ground scene, a
  raised room with a cliff run + foam, a plank stair, room clutter, tree
  shadows, and the F7 dev grid.
- Flag-off paths (`WORLD_VERTICALITY`, `STRUCT_ANNEX`, ramps, the terrain flags)
  stay byte-identical to now at every step.

---

## Checklist

### W0 — Scaffold — DONE (2026-08-30)
- [x] `world/layout.py` — `TileMeta`, `Room`, `Corridor`, `Stair`,
      `WorldLayout` moved verbatim (imports: `deque`, `dataclass`/`field`,
      `NamedTuple`, `pygame`, `game.config`).
- [x] `world/procedural.py` — `from world.layout import (Corridor, Room, Stair,
      TileMeta, WorldLayout)` right after the `game`/`entities` imports; class
      block spliced out; now-unused `dataclass`/`field`/`NamedTuple` imports
      dropped (`deque` kept — still used by the graph helpers). 1360 → 1206.
- [x] `world/gen/__init__.py`, `world/terrain/__init__.py` — empty packages
      with a docstring pointing back here.
- [x] Suite **714 green** on `unittest -t .`. Verified `from world.procedural
      import Room, WorldLayout, generate_world, SPECIAL_KINDS`, `from world.map
      import GameMap`, and `from world.layout import Room` all resolve to the
      same objects; `generate_world(7)` + `GameMap(seed=7)` build clean.
- Only other `world.procedural` consumers: `world/map.py` (models +
      `generate_world`) and `game/states/playing/locations.py` (`SPECIAL_KINDS`)
      — both unaffected by the re-export.

### W1 — procedural.py → world/gen/* — DONE (2026-08-30)
- [x] Split by the real internal call graph (mapped with an AST pass first):
      - `world/gen/tuning.py` — every tuning constant + `SPECIAL_KINDS` +
        `_DIRS`, a leaf module so the siblings import it with no cycle.
      - `world/gen/rooms.py` — `_cell_rect`, `_room_frac`, `_full_cells`,
        `_four_connected`, `_borders_intact`, `_try_one_notch`,
        `_carve_room_shapes`, `_grow_rooms`.
      - `world/gen/graph.py` — `_adjacency`, `_rooted_tree`, `_grow_subtree`,
        `_assign_floors`, `_distances`, `_assign_kinds`.
      - `world/gen/links.py` — `_connection_lanes` /
        `_interior_connection_lanes` / `_connection_lane`, `_relink_corridors`,
        `_split_links`.
      - `world/gen/verticality.py` — `_face_h`, `_drop_h`, `_ramp_candidates`,
        `_plan_ramps`, `_ramp_steps`, `_collect_annex`, `_carve_cliffs`,
        `_is_south_rim`, `_cliff_variant`, `_build_tile_meta`. Imports
        `_four_connected` from `.rooms` and `_relink_corridors` from `.links`
        (the only cross-stage edges; direction is rooms → links → verticality).
      - `world/gen/scatter.py` — `_corridor_doorways`, `_scatter_obstacles`,
        `_topup_trees`, `_scatter_houses`.
      - `world/gen/__init__.py` — `generate_world` verbatim; imports only the
        stage functions it calls directly.
- [x] `world/procedural.py` is now a 22-line shim re-exporting `generate_world`,
      `SPECIAL_KINDS`, the five models, and the private names tests still pull
      from it (`_four_connected`, `_corridor_doorways`, `_HOUSE_RADIUS`,
      `_VILLAGE_MIN_ROOM_CELLS`, `_VILLAGE_RADIUS`).
- [x] One test edit: `tests/world/test_obstacle_families.py` monkey-patches the
      `_TREE_DENSITY_BOOST` knob — a value binding, not a call — so its
      `import world.procedural as P` had to become `import world.gen.scatter as
      P` to patch the module `_topup_trees` actually reads. No assertion
      changed.
- [x] Retired-but-not-deleted: `_STAIR_WIDE_OVERLAP_TILES` /
      `_STAIR_WIDE_ROOM_TILES` in `tuning.py` are unreferenced (LD-5 replaced
      the geometry gate with `config.STAIR_WIDE_EVERY`). Left defined to keep
      W1 a pure move; drop in a later cleanup.
- [x] **Determinism A/B:** `scratchpad/ab_worldgen.py` serialises the full
      `WorldLayout` (room rects / cells / tile_meta, corridors, stairs,
      obstacles) for seeds 0–40 under three config profiles and hashes the lot.
      Identical before and after: `801f92e72b3c5a96cc621fea30929644d5a0195b6ad77a725a2e80022e16b877`.
- [x] Suite **714 green** (`unittest -t .`).

### W2 — TileSheets — DONE (2026-08-30)
- [x] `world/terrain/sheets.py` `TileSheets(assets)` owns: `px`, `slots`,
      `interior`, `palettes`, `floor_sheet`, `floor_sheets`, `cliff_slots`,
      `raised_slots`, `ramp_slots`, the bridge fields, the tile-surface cache
      and the 3-sided-grass cache, plus `.ok` (tileset present) and the methods
      `cell` / `sheet_for` / `cliff_idx` / `raised_idx` / `three_sided`.
- [x] `GameMap._build_tiles` builds one `TileSheets`, bails to the flat
      renderer on `not sheets.ok`, and aliases `px = sheets.px`,
      `cell = sheets.cell`, … so `paint_room` / `paint_corridor` / `paint_cliff`
      / `paint_stair` are **unchanged** (they move in W4). The one non-alias
      edit: `raised_idx(m)` → `sheets.raised_idx(m)` (its only call site).
- [x] **Bake A/B:** `scratchpad/ab_bake.py` hashes every baked `Surface`
      (raw RGBA) and every anchor list (`_room_surfs`, `_corr_surfs`,
      `_cliff_surfs`, `_stair_surfs`, `_ramp_surfs`, `_cliff_foam`,
      `_cliff_shadow`, `_shore`, `_cliff_underlay`, `_cliff_capped`) for seeds
      0–40 × three config profiles. Identical before/after:
      `755d77b3e30f2000fe78ea4b42d085015f83aae81b9413f11bb17c702eff129b`.
      (Baseline captured by reverse-applying the W2 edit to a copy — `git
      stash` is unusable here, `world/map.py` carries a large pile of
      pre-session uncommitted LD-1…LD-6 work.)
- [x] Suite **714 green**.

### W3 — autotile helpers — DONE (2026-08-30)
- [x] `world/terrain/autotile.py` — `slot_for`, `mask_slot`, `bridge_slot` as
      pure module functions (no pygame, no assets). `GameMap._slot_for` /
      `_mask_slot` / `_bridge_slot` are now `staticmethod(autotile.*)` aliases,
      the same pattern `game/states/playing/state.py` uses for
      `_rendering.hit_tinted`. No call site or test edited.
- [x] `_slot_for` has no caller anywhere (superseded by `mask_slot`); moved
      as-is rather than deleted to keep W3 a pure move.
- [x] Bake A/B identical (`755d77b3...`); suite **714 green**.

### W4 — room / corridor / cliff / stair painters — DONE (2026-08-30)
- [x] `world/terrain/rooms.py` — `paint_room(store, sheets, layout, r)` (bakes
      the grass surface, appends `store._shore`, reads `store._cliff_capped`)
      and `paint_corridor(sheets, layout, c)` (plank bridge, no run state).
- [x] `world/terrain/cliffs.py` — `paint_cliff(store, sheets, layout, r)`
      (the ~250-line LD-1…LD-7 beast, with `face` / `ground_k` / `south_room`
      kept as nested helpers; appends `store._cliff_foam` / `_cliff_shadow` /
      `_cliff_underlay` / `_ramp_surfs`) and `paint_stair(sheets, layout, st)`.
      Bodies lifted verbatim; `self._X` → `store._X`, `self._bridge_slot` →
      `autotile.bridge_slot`, and the tileset closures read off `sheets` via a
      short local-alias block at the top of each function.
- [x] `_build_tiles` shrank to: build `TileSheets` → bail if `not sheets.ok` →
      LD-7a `cliff_capped` pass → call the four painters in order → shore
      filter → water / shadow / foam / decor buffers. The now-redundant
      `if not isinstance(floor_sheet, str): return` (dead after `sheets.ok`)
      and every unused closure alias were dropped.
- [x] **Bake A/B identical** (`755d77b3…`) across seeds 0–40 ×
      {default, vert, vert+irregular} — every baked `Surface`'s raw RGBA and
      every anchor list. Suite **714 green**. `world/map.py` 1288 → 919.
- Note: the painters were sliced from a saved copy of `world/map.py` (post-W2)
  by a scratch script, dedented, and re-parsed — hand-splicing 290 lines of
  nested closure was not worth the transcription risk.

### W5 -- decor bakes -> world/terrain/decor.py -- DONE (2026-08-30)
- [x] `build_obstacle_decor(store, a)`, `build_tree_shadows(store, conf)`,
      `build_decor_scatter(store, a)` -- bodies verbatim, `self._X` -> `store._X`.
      `_build_tiles` calls the first and third; the first calls the second.
- [x] No test reaches these methods by name (tests check the outputs via
      `_build_tiles()`), so no delegator and no test edit.
- [x] `scratchpad/ab_bake.py` grew a decor section (hashes every skin / shadow
      / clutter frame + anchor + fps). A/B identical before/after:
      `78d7ed0d0f39ef33462db1315b456d00ad9621f3d2e63da3b1fdffb3810096e1`.
      Baseline captured by re-inlining the three functions into a copy of
      `world/map.py`.
- [x] Suite **714 green**. `world/map.py` 919 -> 719.

### W6 — draw path → TerrainRenderer — NOT STARTED

Heavier test coupling than the bake milestones, so it needs its own pass:
`tests/rendering/test_depth_sort.py` **monkey-patches** `gm._draw_one_obstacle`
and `gm._draw_one_tree_shadow` on the instance and then calls
`gm.scenery_drawables(cam)` expecting the patched callables to be used — so the
extracted `TerrainRenderer.scenery_drawables` must call back through
`self.gm._draw_one_*`, not its own methods. `gm._draw_tiled` is called directly
by three tests (`test_terrain`, `test_verticality`), plus `gm._z_surf`,
`gm._foam_frame_at`, `gm._foam_routine_index`, `gm._draw_obstacles`,
`gm.draw_tree_shadows`, `gm.shade_character_frame`. All need delegators on
`GameMap`. Verification: headless screenshots (ground, cliff+foam, room
clutter, tree shadows, F7 grid) — the bake A/B already pins the inputs.

### W6 -- draw path -> TerrainRenderer -- DONE (2026-08-30)
- [x] `world/terrain/render.py` `TerrainRenderer(game_map)` -- the contiguous
      `draw` .. `_draw_grid` block, bodies verbatim. Cross-method calls stay
      `self.*`; state and the two instance-monkey-patched painters
      (`_draw_one_obstacle`, `_draw_one_tree_shadow`) go through `self.gm.*`.
      Its own copies of `_VOID` / `_FLOOR` / `_WALL` / `_GRID` / `_SPECIAL_FLOORS`.
- [x] `GameMap` delegators: `draw`, `draw_ground`, `draw_room_clutter`,
      `scenery_drawables`, `shade_character_frame`, `draw_tree_shadows`,
      `_draw_obstacles`, `_draw_tiled`, `_z_surf`, `_draw_one_obstacle`,
      `_draw_one_tree_shadow`. `_foam_routine_index` / `_foam_frame_at` stay
      real (pure, small; the renderer calls `self.gm._foam_*`).
- [x] `renderer` is a **lazy cached property**, not an `__init__` attribute:
      `tests/rendering/test_terrain.py` builds `GameMap.__new__(GameMap)` and
      calls `_z_surf` / `shade_character_frame` straight off it, so the property
      builds a `TerrainRenderer` on first access. No test edited.
- [x] Dead-after-move constants + stale LD-6 / LD-7a painter comments removed
      from `world/map.py`; module docstring rewritten (GameMap = wrap layout +
      walkability + bake + hand off drawing).
- [x] `scratchpad/ab_render.py` freezes `pygame.time.get_ticks` (foam / decor
      animation is wall-clock) and hashes composited frames. Identical
      before/after: `5e12b249a9001e8b7b4d877fec37f85465bba28929bb77ed604d61daf071d056`.
- [x] Suite **714 green**. `world/map.py` 719 -> 418.

### W7 -- docs -- DONE (2026-08-30)
- [x] This file: status + the "Where things live now" table below.
- [x] `journals/journal.md`: a "World refactor" section (what / verified / next).
- [x] `README.md` project-layout: the `world/` line now names `map` (facade),
      `layout`, `gen/`, `terrain/`, `pathfinding`, `spawning`.

## Where things live now (post-W7)

`world/map.py` -- **418 lines** (was 1414). `GameMap`: `__init__` state decl,
the lazy `renderer` property, the collision / spawn API (`is_walkable`,
`resolve_movement`, `room_at`, `random_point_in_room`, `offscreen_spawn_point`,
`blocking_obstacle_hit`), `_foam_routine_index` / `_foam_frame_at`, the terrain
**bake sequence** `_build_tiles` (build `TileSheets` -> LD-7a cliff-cap pass ->
call the four painters -> shore filter -> water / shadow / foam / decor
buffers), and 11 render delegators.

| Concern | Module | Shape |
|---|---|---|
| world data model | `world/layout.py` | `TileMeta` / `Room` / `Corridor` / `Stair` / `WorldLayout` |
| generation entry | `world/procedural.py` | 22-line re-export shim |
| gen orchestrator | `world/gen/__init__.py` | `generate_world` only |
| gen tuning consts | `world/gen/tuning.py` | leaf module, no imports |
| room shapes | `world/gen/rooms.py` | carve / notch / multi-chunk grow |
| connectivity | `world/gen/graph.py` | adjacency, floors, kinds, distances |
| links | `world/gen/links.py` | lane geometry, `_split_links` |
| verticality | `world/gen/verticality.py` | ramps, annex, cliff carve, `_build_tile_meta` |
| scatter | `world/gen/scatter.py` | obstacles, trees, houses |
| tileset adapter | `world/terrain/sheets.py` | `TileSheets` (metadata + tile cache) |
| autotile maths | `world/terrain/autotile.py` | `slot_for` / `mask_slot` / `bridge_slot` (pure) |
| room painters | `world/terrain/rooms.py` | `paint_room`, `paint_corridor` |
| cliff painters | `world/terrain/cliffs.py` | `paint_cliff`, `paint_stair` |
| decor bakes | `world/terrain/decor.py` | obstacle skins, tree shadows, scatter |
| draw path | `world/terrain/render.py` | `TerrainRenderer(game_map)` |

Painters take `(store, sheets, layout, ...)` -- `store` is the `GameMap`, which
still owns the baked `Surface` lists and anchor lists. Each module's docstring
lists which `store` fields it reads and appends to.

## Follow-ups (not blocking)

- Drop the unused `_slot_for` (superseded by `mask_slot`) and the retired
  `_STAIR_WIDE_OVERLAP_TILES` / `_STAIR_WIDE_ROOM_TILES` constants.
- A real `TerrainStore` dataclass so the painters and `TerrainRenderer` take a
  narrow object instead of the whole `GameMap` (the P7 `RunContext` question
  from the playing refactor -- do it only if a painter needs isolated tests).
- The bake sequence in `_build_tiles` could itself move to
  `world/terrain/bake.py` as a `build(store, layout, assets)` function, leaving
  `GameMap` purely collision + facade.
