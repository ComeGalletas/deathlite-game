# `world/` — how a level is generated and drawn

This guide walks the whole pipeline by function name: **generate → bake →
draw**, then **how the tilesheet is split into slots** and **how a tile lands
in the world**. Every world is a height-map world: a chain of islands, each a
stack of terraces with walls, flights and lakes. (The earlier flat generator
and its flags were retired on 2026-09-02; nothing in this package gates on
them.)

The package is split into layers, and `tests/world/test_layering.py`
enforces the import direction:

| layer | where | job |
|---|---|---|
| **data model** | `world/layout.py` | `Cell`, `TileMeta`, `Room`, `Corridor`, `SpawnPoint`, `ResourcePoint`, `Chest`, `Village`, `FishHut`, `WorldLayout` — the shape `generate_world` produces; imports nothing else in `world/` |
| **rules** | `world/rules/` | `floor` (is a point on floor, and which island), `steps` (may a body step tile to tile), `inset` (how far inside its own terrace a point stands), `frontier` (where a prop may stand relative to a level change), `biome` (what a tileset is), `spacing` (a placement spatial hash). Read by generation, the bake and the runtime; import only the model and the terrain data |
| **elevation** | `world/elevation.py` | `LevelIndex` — the whole world's elevation rasterised once into flat per-tile arrays; the *only* place the runtime learns an elevation |
| **generation** | `world/gen/` | `generate_world` / `generate_world_steps` and one module per stage; `height/` builds one island's height map; `settings.py` snapshots the knobs; `validate.py` reads the promises back |
| **collider** | `world/map.py` | `GameMap` — walkability, wall sliding, spawn queries; holds the `LevelIndex`, the `BakedTerrain` and a `TerrainRenderer` |
| **terrain** | `world/terrain/` | `sheets` (the tileset adapter), `autotile` (slot maths), `grid_paint` (one surface per terrace off the height map), `decor/` (obstacle skins, tree shades, clutter, water scenery, building dressing), `bake` → `baked.BakedTerrain`, `render.TerrainRenderer` |
| **navigation** | `world/nav/` | `NavGrid` (the lattice), `clearance` (the chamfer transform), `FlowField` / `NavField` (the shared distance field enemies steer on) |
| **no-layout spawning** | `world/spawning.py` | `ring_point_around`, the placement rule of the one-room `GameMap(seed=None)` world the non-run tests use |

Generation is imported from `world.gen`, the model from `world.layout` and
navigation from `world.nav`; the old `world.procedural` / `world.pathfinding`
re-export shims are gone.

---

## Part 1 — Generating a level: `generate_world(seed)`

`world/gen/__init__.py`. Pure and deterministic — the same seed always yields a
byte-identical `WorldLayout`, with no asset loaded and no display. All
randomness comes from one `random.Random(seed)` stream except where a stage
says it keys a **private** RNG by seed and island so that it draws nothing
from the world's; the stage order below is the order the stream is consumed
in, and moving a stage moves every world.

The knobs come from one `GenSettings` (`world/gen/settings.py`), snapshotted
from `game.config` at the top (`HEIGHTMAP_*`, `TERRAIN_BUILDINGS`,
`SPAWN_POINTS_PER_FLOOR`) and handed to every stage that reads one, so a test
passes `GenSettings.from_config(unseal=False)` instead of mutating the global.

`generate_world_steps` is the same pipeline as a generator: it yields a label
after every stage (one per island for the two expensive ones) and *returns*
the layout when exhausted, so the loading screen can drive it a step per
frame. `generate_world` drives it to the end.

1. **Grow a tree of chunk cells.** From cell `(0, 0)`, repeatedly pick a random
   free cell orthogonally adjacent to an occupied one until
   `settings.room_count` cells exist. Every new cell records a tree `edge` to
   its parent, so the island graph is connected by construction.

2. **One island rect per cell** (`world/gen/rooms.py`). A tile-sized rect,
   `settings.room_cols × room_rows` tiles, snapped to the *world* tile lattice
   inside its chunk so two islands always share one grid and a bridge can sit
   squarely at both ends. Each starts as `kind="combat"`; tree edges become
   `Room.neighbors`.

3. **One bridge per tree edge** (`world/gen/links.py`). `_connection_lane(seed,
   a, b, …)` picks a stable, tile-aligned crossing lane on the two islands'
   shared span with a private RNG. The `Corridor` records its `axis`
   (`"h"`/`"v"`), which mouth is which (`end_low`/`end_high` = west/east or
   north/south) and the two rooms it joins. One per link *here*; how many a
   link carries is decided in step 6 once the beaches exist.

4. **Roles, then shape** (`world/gen/graph.py`, `placement.py`).
   `_distances` BFS from room 0; the farthest room is `boss_id`.
   `_assign_kinds` marks `start` and `boss`, picks the village islands
   (`_pick_villages`: `settings.villages` of them at a tree distance inside
   `settings.village_distance`, never the boss, at least one so the forge
   exists) and leaves the rest `combat` — `SPECIAL_KINDS` in `tuning.py` is
   empty today, so no shrine, treasure, altar or merchant island is
   generated. `assign_topography` gives each
   island a shape type — `volcanic`, `small`, `boss`, `human`
   (`config.HEIGHTMAP_TOPOGRAPHIES`) — separate from its kind; then
   `_resize_by_topography` and `_offset_in_chunk` size it and slide it off
   the centre of its chunk. *Yields "islands placed".*

5. **Height maps** (`world/gen/islands.py` → `world/gen/height/`). Every island
   starts as the full rectangle (`_full_cells`); `island_caps` says how many
   terraces each may carry; `build_island` runs `height.build_grid` and
   overwrites `Room.cells` and `Room.grid` wholesale. *Yields "island i of n".*
   Inside `build_grid`, in order:
   - `coast.py` — the outline, from a named preset
     (`config.HEIGHTMAP_COAST_PRESETS`: `rugged`, `square`), bays carved,
     spikes removed;
   - `terraces.py` — each cap is the one below it eroded inward, asymmetric
     (`cap_inset_s/n/w/e`) so it reads as a mountain, with canyons cut so the
     north has a way up;
   - `walls.py` — `_raise_walls` gives every southward drop its cliff face,
     `_face_the_sea` makes sure no raised ground hangs over open water;
   - `flights.py` — straight and east/west staircases cut through a wall,
     lateral crossings on the flanks, north flights on a plateau's back;
   - `water.py` — lakes carved (never smaller than three contiguous tiles on
     one terrace) and leftover holes filled;
   - `graph.py` — `walk_links` is the authority on which cells connect;
     `check_grid` asserts the invariants (a southward drop always has a wall,
     adjacent levels differ by at most 2, no floating ground, every walkable
     cell reachable). `to_ascii` prints a grid the way the level-design
     journal draws them.

6. **Seat the bridges** (`world/gen/bridges.py`). The only stage that runs
   *after* the grids exist: `_seat_corridors` stretches each bridge coast to
   coast (the coastline wanders inside the rect), picks the lane that lands on
   beach at both ends, clones a link into as many bridges as its two
   topographies allow (`bridges` in `HEIGHTMAP_TOPOGRAPHIES`,
   `settings.bridge_min_gap` / `bridge_max`), and `_add_shortcuts` may add a
   non-tree crossing. *Yields "bridges".*

7. **Palettes and insets.** `biomes.assign_palettes` decides which tileset
   each terrace wears (`Room.palette`, `{level: sheet}`; private RNG): level 0
   only from sheets that can meet the sea, each raised level a different
   biome from the one under it. Then `rules.inset.build` builds each island's
   inset field — distance, per 8 px sample, to the nearest floor of a different
   level — once, before anything is baked, scattered or spawned. *Yields
   "terraces i of n".*

8. **Bounds.** Union every rect plus a chunk of margin → `bounds`; shift the
   whole world so it starts at `(0, 0)` (keeps the camera clamp simple).

9. **Scatter obstacles** (`world/gen/scatter.py`). Rocks, trees, shrubs,
   pillars and houses as circular `Obstacle`s on floor cells, in final
   coordinates, per biome mix (`rules.biome.scatter_mix`), kept clear of every
   bridge mouth (`_blocks`), flight and landing (`_flight_keepouts`) and the
   terrace frontier (`rules.frontier`). `buildings.py` seats the buff
   buildings inside this pass (two to five distinct kinds per island, none on
   the village or the boss arena); `_topup_trees` and `_scatter_houses`
   finish it. *Yields "obstacles".*

10. **Villages** (`world/gen/village/` -- `site`, `seating`, `pen`,
    `scatter` -- and `village_tidy.py`). The scatter
    passes over a `village` island; this lays it out round a north axis —
    forge, heal zone, town hall — with the houses on the ring, a military row
    by each bridge road, a fenced pen on the far side, colours from a shuffled
    cycle. Every building is an `Obstacle` (wide ones a compound of circles);
    the tidy pass then keeps the art from painting over the forge, the heal
    and the hall. Returns one `Village` record per island. Private RNG.
    *Yields "villages".*

11. **Per-tile metadata.** `_grid_tile_meta` projects every finished grid
    into `Room.tile_meta` — one `TileMeta` per walkable cell (`floor`,
    `surface`, `foam`, `room_id`, `ramp`). No RNG.

12. **Repair** (`world/gen/repair.py`, if `settings.unseal`). Builds the
    widest navigation class's lattice and asks the question that matters —
    can the widest body still reach everywhere bare terrain allows? — and
    removes the specific obstacles standing in the way (village pens and
    protected buildings exempt). *Yields "repair".*

13. **Spawn points and resource anchors** (`world/gen/spawnpoints.py`). Per
    terrace, farthest-point-sampled candidates that are plain ground, inside
    the terrace margin, off obstacles and bridge mouths, clear of the hero's
    start, and passable on the lattice at the widest body → `layout.spawn_points`;
    eight sheltered anchors per island → `layout.resource_points`. Private
    RNG; villages get none. *Yields "spawn points i of n".*

14. **Chests** (`world/gen/chests.py`) on the anchors: how many, which tier,
    which anchor; private RNG. *Yields "chests".*

15. **Fish huts** (`world/gen/fish_huts.py`) moored beside the bridges on open
    water; private RNG. *Yields "fish huts".* Returns the `WorldLayout`.

`world/gen/validate.py` reads the promises back off a finished layout (the
tests run it on every cached world); `tools/verification/world_digest.py`
pins a fingerprint of the layout, the bake and one frame per cached seed.

### The height map (`world/layout.py::Cell`)

Each room's `grid` maps a room-relative `(col, row)` to a `Cell`:

```
=  ground   walkable surface at `level`
#  cliff    the wall holding up `level`; not walkable
0  vstair   straight N/S flight, `level` down to `level - drop`
^  vstair   the same, descending north: one rim cell on a plateau's back
>  ewstair  east/west flight; `tag` is the descent side
~  lake     inland water inside a terrace; not walkable
   void     open sea / nothing
```

`level` is always the **upper** surface a cell belongs to; `row` indexes a
cliff or stair cell within its own stack (0 = top) so the renderer never
re-derives the stack; `tag` is `"grass"` / `"rock"` for a flight's art or
`"w"` / `"e"` for a lateral one; `dir` is `"s"` (cut through a wall) or `"n"`
(a plateau's back rim). `Room.cells` is the walkable subset, derived from the
grid; `Room.floor` is the base level (always 0 today).

### Runtime queries on `WorldLayout`

- `layout.tile_at(wx, wy)` → the `TileMeta` under a world point (synthesised
  for a bridge cell), or `None` in the void. Slow — a scan of every room; the
  runtime reads `LevelIndex` instead.
- `layout.walkable_rects()`, `layout.room(id)`, `layout.bfs_distances(src)`,
  `layout.is_connected()`, `layout.buff_buildings(kinds)`.
- `layout.spawn_points`, `resource_points`, `chests`, `villages`, `fish_huts`
  — the records the run reads instead of sifting the obstacle list.

### Elevation at runtime: `LevelIndex` (`world/elevation.py`)

Built once by `GameMap` from the layout. Per absolute tile it holds `level`
(the walkable surface here, or `NONE`), `kind` (`GROUND` / `VSTAIR` /
`EWSTAIR` / `NOTHING`) and `top` (the elevation of whatever terrain stands
here, walkable or not — what a projectile has to die against). Flight cells
keep their `Cell` beside the arrays. `world/rules/steps.py` (`can_step`,
`can_cross`, `diagonal_blocked`) mirrors `walk_links` against it so the
collider and the flow field ask the same question without allocating;
`tests/world/test_elevation.py` checks the two agree on every cell.

---

## Part 2 — Baking the terrain: `bake_steps(layout)` → `BakedTerrain`

`world/terrain/bake.py`. Runs once, lazily, on the first draw (it needs a
display): `GameMap._build_tiles` stores the result as `GameMap.terrain` and
forwards the old field names (`_grid_surfs`, `_shore`, …) to it. `bake_steps`
yields one label per island and per finishing pass so the loading screen can
keep animating; `bake` drives it to the end. If `TileSheets.ok` is false the
tileset is missing, `BakedTerrain.ok` stays false and the renderer's flat
fallback is permanent.

1. `sheets = TileSheets(assets, layout.seed)` (`world/terrain/sheets.py`).

2. **One pass per island, one surface per terrace.**
   `grid_paint.paint_room_levels(t, sheets, layout, room)` returns
   `[(blit_rect, surface, level)]` → `t.grid_surfs`; `grid_paint.grid_shore(room)`
   → `t.shore` (the top-left world pixels of every cell that faces sea or a
   lake, plus cliff feet standing in water — the foam anchors). A band holds a
   terrace's own ground *and the stone that stands on it*: a wall belongs to
   the terrace it drops onto, not the one it holds up. Composited in level
   order the bands are pixel-identical to the single-surface
   `paint_room_grid` (`tests/render/test_level_bands.py`).
   *Yields "painting island i of n".*

3. **Bridges.** `paint_bridge_shadow` then `paint_bridge` per corridor, both
   tiled along the corridor's own rect (already stretched coast to coast) →
   `t.corr_shadows`, `t.corr_surfs`, tagged with sea level. *Yields "bridges".*

4. **Water.** `water_buffer` tiles the water tile over the visible extent plus
   one tile of scroll slack → `t.water_buf` / `t.water_tile`; the static
   `terrain_shadow` sprite → `t.shadow`; with `config.TERRAIN_FOAM` the
   `terrain_foam` frames → `t.foam` and the `foam_routines` (fps, phase)
   buckets → `t.foam_routines`. *Yields "water".*

5. **Obstacle skins** (`config.TERRAIN_DECORATIONS`;
   `decor/obstacle_skins.build_obstacle_decor`). Each obstacle gets a rig
   scaled so its footprint covers the collider → `t.decos`, `t.sprite_drop`,
   `t.art_rects`; trees get a shade patch → `t.tree_shadows`
   (`decor/shadows.py`); the ghost-silhouette parameters → `t.ghost`.
   *Yields "obstacle skins".*

6. **Scenery** (`config.TERRAIN_DECOR`). `decor/scatter_room.build_decor_scatter`
   seats seeded non-colliding clutter on each island's floor → `t.room_decor`
   (budget from `decor/budget.py`, frontier rules from `rules/frontier.py`,
   separation from `rules/spacing.py`); `decor/dressing.build_building_dressing`
   adds the props round each buff building; `decor/scatter_water.build_water_decor`
   places sea, shoreline and lake props → `t.void_decor`. *Yields "clutter",
   "dressing", "water scenery".*

7. `t.ok = True`.

---

## Part 3 — Drawing a frame

Drawing happens in `TerrainRenderer` (`world/terrain/render.py`) and nowhere
else; `GameMap.renderer` hands it out. The run composites the world **one
terrace at a time** (`scene.draw_world`, `game/states/playing/visual/scene.py`,
called from `PlayingState.draw`):

```
renderer.begin_frame()
renderer.draw_water(surface, camera)          # sea, foam, water scenery
for level in every terrace level in view:
    renderer.draw_ground_band(surface, camera, level)   # that level's bands
                                                        # (+ bridges on level 0)
    flat effects on that level                # interactables, chests, hazards,
                                              # gems, potions, explosions, the
                                              # player's shots, slash / slam fx
    scenery + actors on that level, sorted    # obstacles, clutter, tree shades,
      back-to-front by ground-contact y       # enemies, boss, summons, hero
renderer.ghost_pass(surface, camera)          # bodies hidden behind obstacle
                                              # art, redrawn as silhouettes
hostile projectiles, particles, damage numbers, dev overlays, hints
HUD on the UI box, feedback overlays
```

Banding is what lets a higher terrace occlude what stands below it while the
stone a character is standing *in front of* still sits behind them: the wall
is already down when their band is painted, and the higher ground is not.

- **`draw_water`** → `_draw_water_band`: the water buffer scrolled by
  `camera.pos % water_tile` (or a flat fill without the art); one foam frame
  at every `shore` anchor in view, each anchor on its own routine bucket
  (`BakedTerrain.foam_frame_at`) so neighbours do not lock-step; then the
  `void_decor` props, above the foam so a shoreline animation never washes
  over them.
- **`draw_ground_band(level)`**: every `grid_surfs` entry tagged `level`,
  south-first within the level so an island lower on the map overlaps the one
  above it; on the lowest level also every bridge shadow, then every bridge.
- **`banded_scenery(camera)`** → `[(level, depth_y, draw_fn)]` for every
  visible clutter instance and skinned obstacle (a tree's shade just before
  it), each tagged with the terrace it stands on (`level_at`). The run merges
  these with its own actors per band. `scenery_drawables` is the untagged
  view of the same list; `draw` (`draw_ground` + sorted scenery) is the
  whole-map single pass the tests and the flat world use.
- **`shade_character_frame`** overlays any intersecting tree shade through a
  character sprite's alpha, independent of sort order; `record_character` +
  `ghost_pass` redraw the bodies that ended up behind obstacle art as
  translucent silhouettes.
- Every blit goes through `_z_surf`, a zoom-scaled copy cached per surface
  (identity at zoom 1.0), positioned at `(world - camera.pos) * zoom`.
- **Flat fallback.** With no layout, a reference floor rect and a grid; with
  a layout but no tileset, `_draw_flat_layout` paints coloured rects per room
  kind with a grey border and obstacles as drawn circles.

---

## Part 4 — How the tilesheet is split into slots

All tile metadata lives in `data/world/terrain.json` and is read once per bake
by `TileSheets`. Tiles are **64 px** (`tile_px`); every ground sheet is a
**9×6 grid** (`grid`), and a slot is a flat index `row * 9 + col`.
`TileSheets.cell(sheet, idx)` returns the (cached) `Surface` for a slot.

### Which sheet a terrace wears

`floor_sheet` is the default ground (`tilemap_1`); `floor_sheets` maps a raised
level to a sheet (`1 → tilemap_2`, `2 → tilemap_3`, `3 → tilemap_5`);
`room_palettes` maps a room kind to one (`boss → tilemap_4`, …).
`sheet_biomes` names each sheet's biome (`meadow`, `forest`, `drab`,
`wetland`, `rock`, `sand`) and `sheet_flags` says which have no shoreline
surf. **Generation decides** (`Room.palette`, step 7 above);
`TileSheets.sheet_for(floor, kind, room)` reads the room's palette and only
falls back to the level table, then the kind palette, then the default when
no room is given. **Every sheet shares the same slot layout** — a slot index
means the same tile shape on all of them.

### The ground block (`slots`)

A complete sixteen-combination autotile, keyed by which sides are open:

```
 corner_nw  0    edge_n  1    corner_ne  2
 edge_w     9    interior 10  edge_e    11
 corner_sw 18    edge_s 19    corner_se 20
```

plus `strip_v [3, 12, 21]` (a north-south channel: top / mid / bottom),
`strip_h [27, 28, 29]` (an east-west one: west / mid / east) and `single 30`
(open on all four). `autotile.ground_slot(slots, sides)` maps a side string
(a subset of `"nswe"`, in that order) to the slot; `mask_slot(cells, col,
row, slots)` derives the sides from a cell set for callers that have only
that. Open sides have **transparent** edges, so a terrace surface is baked
`SRCALPHA` and the water shows through.

### Cliff block (`slots.cliff`)

Three rows — `top` 32–35, `body` 41–44, `bottom` 50–53 — with four run
positions each (`left` / `mid` / `right` / `single`).
`TileSheets.cliff_idx(row, edge)` looks one up; `grid_paint._run_var` picks
the position from the stone cells beside it; `Cell.row` picks top / body /
bottom. `cliff_shadow` is the soft drop shadow a wall casts on what it
stands on (the `terrain_shadow` rig).

### Raised block (`slots.raised`)

A second sixteen-tile block (cols 5–8, rows 0–3) fringed with dark cliff-grass
instead of surf, keyed **directly** by the open sides: `"" → 15`, `"n" → 6`,
`"nw" → 5`, `"nswe" → 35`, …

### Flights

- `slots.ramp` — `"w": [36, 45]`, `"e": [39, 48]` are the east/west wedge
  (top tile, bottom tile) by descent side; `"s"` / `"n"` → `[17, 17]` is the
  grass channel piece a straight flight lays. `TileSheets.channel_halves`
  splits it for the north flight, which straddles the seam between the rim
  and the landing.
- `vstair` — a separate sheet of stone flights (`vstairs.png`, one column,
  with `sheets` per drop). `TileSheets.vstair_sprite(drop, north)` is the
  stone drawn on a `"rock"` flight; `vstair_seam` is where it sits on a north
  flight.

### Bridges (`bridge`)

A separate 3-wide sheet (`bridge_all.png`): `h_left / h_mid / h_right`,
`v_top / v_mid / v_bot` and a `shadow` block. `autotile.bridge_slot(axis, i,
ncells)` returns the slot *name* for cell `i` of a run (end caps at `0` and
`ncells - 1`, `mid` between).

### Which sides of a ground cell are open — `grid_paint._floor_sides`

A ground tile autotiles **relative to its own floor**. A side is open (and
gets a fringe) where the neighbour is sea or a lake, ground at a *lower*
level, or stone at this cell's own level (its terrace's own rim). It is *not*
open where the neighbour is anything at a higher level — a cliff or a flight
standing on this cell, a terrace butting against it — because the floor runs
on underneath and ground is painted below everything. A flight at this level
is rim to the south only; the head of a grass channel is the one place even
the south rim goes (`_open_channel`), so the channel reads as continuous from
the terrace down through the wall.

Per cell, `grid_paint` then paints: nothing for a lake (the water buffer
shows through); the biome sheet's ground tile for ground; the stone face for
a cliff; the grass channel plus, when `"rock"`, the stone sprite for a
straight flight; the ramp wedge for an east/west one. Sprites taller than a
cell (a drop-2 stone flight) go on last so the cell they hang into does not
paint over them.

---

## Part 5 — How a tile lands in the world

### Coordinate model

- **Baked surfaces are 1:1 world pixels.** A band's `blit_rect` is in world
  pixels; the renderer blits it at `((rect.x - camera.pos.x) * zoom,
  (rect.y - camera.pos.y) * zoom)` after `_z_surf`. A band can reach further
  south than its island's rect: a terrace on the southern edge grows a wall
  below it that hangs into the sea.
- **Within an island**, cell `(col, row)` from `Room.grid` is at `(col * px,
  row * px)` on that island's surface. Grids are **room-relative** because
  island rects are tile-*sized* and lattice-aligned but each island has its
  own origin. Never compute a column from a world x by hand: at runtime go
  through `LevelIndex.tile_of(wx, wy)` (absolute tiles) or
  `GameMap.room_cell(room, x, y)` (that room's grid).
- The rules that answer "may a body stand / step here" — `rules.floor`,
  `rules.steps`, `rules.inset` — are the same functions for the collider
  (`GameMap.is_walkable`, `resolve_movement`), the navigation grid and the
  spawn-point stage, which is what keeps them from drifting.

### Adding a new terrain layer

1. Bake it in `bake_steps` (a new function under `world/terrain/`, writing a
   new field on `BakedTerrain`), and give it a yield label if it is slow.
2. Blit it in `TerrainRenderer` at the right point — inside
   `_draw_water_band` if it lies on the sea, inside `draw_ground_band` if it
   belongs to a terrace (tag it with the level), and cull against
   `camera.visible_rect()`.
3. If it should depth-sort with characters instead (like obstacles), return
   it from `banded_scenery` as `(level, depth_y, draw_fn)`.
4. If the tests' frame digest moves, it is meant to: rerun
   `python -m tools.verification.world_digest --write` and say so.

### Adding a generation stage

Add it beside the others in `world/gen/`, call it from `generate_world_steps`
at the point in the order it belongs, yield a label, and either consume the
world stream (which moves every later stage, and the layout digests with it)
or key a private `random.Random` by seed and island as the chests, huts,
palettes and villages do. Read knobs through `GenSettings`, never
`game.config`. If it places something a body must not stand on, it runs
**before** the repair; if it reads the obstacles as the game sees them, after.
