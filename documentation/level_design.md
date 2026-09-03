# Level design — generation & display

How a level comes to exist and how it gets on screen. Four layers, each
reading the one below and never the one above:

- **Generation** (`world/gen/`) turns a seed into a `WorldLayout`: nine
  islands, each a height map of terraces, walls and flights, joined by plank
  bridges, with a palette per terrace and obstacles scattered on the floor.
  It loads no image and needs no display; it reads `data/terrain.json` for
  the biome tables. Same seed → identical layout, byte for byte
  (`tests/world/test_digest.py` pins it).
- **Rules** (`world/rules/`) are the questions every layer asks the same way:
  is this point on floor, how far inside its terrace is it, may a body step
  from this tile to that one, where may a prop stand, what a tileset *is*.
- **Runtime** (`world/map.py`, `world/elevation.py`, `world/nav/`) is the
  collider, the elevation index and the enemy flow field. Assetless.
- **Display** (`world/terrain/`) bakes the layout into one surface per terrace
  (`BakedTerrain`) and composites the world band by band, with the depth-sorted
  sprites slotted between bands. If the tileset is missing, a primitive flat
  renderer draws the same layout — the game is fully playable with an empty
  `assets/`.

> File references are `path — symbol`; line numbers drift, symbols don't.
> Related: `combat_calculations.md` (damage), `terrain_tile_slots_formula.md`
> (how a tilemap cell is addressed / cut / placed),
> `../journals/level_design_journal.md` (every design pass, with diagrams),
> `worldgen_refactor_plan.md` (why the code is shaped as it is).

---

## 1 · Generation — `world/gen/`

`generate_world(seed, room_count=None, settings=None) -> WorldLayout`
(`world/gen/__init__.py`) is the pipeline; each stage is a module beside it.
All randomness comes from one `random.Random(seed)` stream, consumed in the
order below, except where a stage keys its own RNG by seed and island so that
it draws nothing from the world's. Moving a stage moves every world.

The knobs are a frozen `GenSettings` (`gen/settings.py`), snapshotted from
`game.config` at the top and handed to every stage that reads one. A test
passes `GenSettings.from_config(unseal=False)` instead of mutating the global.
`TILE_PX` (64) stays a global: it is the world's grid unit, shared with the
data, the bake and the renderer.

### 1.1 Chunk lattice → spanning tree

The world is a lattice of chunk cells, `HEIGHTMAP_CHUNK_COLS × ROWS` tiles each
(50 × 30). Generation grows a **tree** of occupied cells outward from the start
cell `(0, 0)`: each step picks a random free cell orthogonally adjacent to an
occupied one and links it to its parent. Because it is a tree, **every island
is reachable from the start by construction.** Stops at `HEIGHTMAP_ROOM_COUNT`
(9) cells.

### 1.2 Islands, roles and topography

One island per cell. `Room(id, cell, rect, kind, neighbors, cells, grid,
topography, palette, inset, tile_meta)`.

`rect` is `HEIGHTMAP_ROOM_COLS × ROWS` tiles (46–52 × 28–32), centred in its
chunk and then **snapped to the world tile lattice**: a rect of odd tile
width centred in a chunk sits half a tile off the grid, and then no two
islands share one, so a bridge could never land square on a tile at both
ends. Every island rect is tile-aligned and tile-sized; `LevelIndex` and the
navigation grid depend on it, and `gen/validate.py` checks it.

Roles: `start_id = 0`; `boss_id` is the island farthest from the start by
tree distance; the rest are shuffled and the first few become one each of
`SPECIAL_KINDS = (shrine, treasure, fountain, altar, merchant)`; the
remainder stay `combat`.

**Topography** (`gen/graph.py — assign_topography`) is what *shape* an island
is, separate from `kind`, which is what happens on it: a shrine can stand on
a small island. The boss island is the one fixed assignment
(`HEIGHTMAP_BOSS_TOPOGRAPHY`); the rest are drawn by weight from
`HEIGHTMAP_TOPOGRAPHIES`, whose entries carry the island's size scale, coast
preset, terrace count range, bridge allowance per side and tileset pool.
`gen/placement.py` then resizes each island to its topography and slides it
within its chunk toward its neighbours, so islands are not all centred.

### 1.3 The height map — `world/gen/height/`

`islands._build_room_grids` gives every island a per-cell **height map**,
`Room.grid: {(col, row): Cell}`, room-relative. A `Cell` is `(kind, level,
drop, row, tag)`:

    `=` ground   walkable surface at `level`
    `#` cliff    the wall holding up `level`; not walkable
    `0` vstair   straight N/S flight, `level` down to `level - drop`
    `>` ewstair  east/west flight (or a lateral crossing on a flank)
    `~` lake     inland water inside a terrace; not walkable
    ` ` void     open sea

`height.build_grid` is the pipeline: a jittered **coast mask** from the
topography's preset (`coast.py`), then concentric **caps** pushed toward the
island's north side (`terraces.py` — the plateau stack is a mountain, not a
staircase; canyons cut into each cap from its southern rim), **walls** on
every southward drop (`walls.py` — the only face the camera sees; east, west
and north are open flanks drawn by the higher terrace's edge tile), **flights**
cut through the walls and **lateral crossings** on the flanks (`flights.py`),
**lakes** (`water.py`), then a prune of unreachable pockets, a hole fill and
one more re-facing. `graph.walk_links` is the authority on what joins what;
`check_grid` lists the invariants (a southward drop always has a wall,
adjacent levels differ by at most 2, no floating ground, a flight links other
terraces only at its ends, every walkable cell reachable).

`Room.cells` is the walkable subset of the grid; `Room.floor` is the base
level (0). Collision and navigation read `cells` and need to know nothing
about levels; the elevation index reads the grid.

### 1.4 Bridges — `gen/bridges.py`

One `Corridor` per tree edge, created on the tree's own lane and then
**seated by `_seat_corridors`** once the coastlines exist: the rect is
stretched beach to beach on a lane where both islands have shore, a link may
carry more than one crossing (per the two islands' `bridges` allowance, spent
per side), a crossing longer than `HEIGHTMAP_BRIDGE_MAX` tiles is refused,
and a **shortcut** pass adds a crossing between islands that ended up close,
so the world stops being a tree and a run need not backtrack over the bridge
it arrived by. One tile wide, always at sea level; each records its `axis`,
`end_low` / `end_high` and `room_low` / `room_high` so the bake draws the
matching end-cap tile at each mouth.

### 1.5 Palettes and the inset field

`gen/biomes.py — assign_palettes` decides which tileset each terrace wears
(`Room.palette: {level: sheet}`) with an RNG keyed by seed and island: a
seeded shuffle of the topography's pool, each raised level differing in
**biome** from the one below it, and level 0 only from sheets whose shoreline
block carries real surf. What a sheet *is* — its biome, its surf, its scatter
mix — is `world/rules/biome.py`, read by the scatter and the painters alike;
generation decides, rendering reads, so the rocks and the rock tiles land on
the same terrace.

`islands._build_inset_fields` then builds each island's **inset field**
(`world/rules/inset.py`): per 8 px sample, the distance to the nearest floor
of a different level, plus a second channel for the distance to anything
that is not floor. Built once, here, so the scatter, the decor, the collider
and the flow field all read one answer to "how far inside its terrace is
this point".

### 1.6 Bounds & shift

`bounds` = the union of every island and bridge rect, inflated by one chunk;
the whole world is then translated so `bounds` starts at `(0, 0)`.

### 1.7 Obstacles — `gen/scatter.py`

Every island scatters, the start and boss ones included. Per terrace, the
biome's `scatter` block gives the kinds, their weights and the density
(attempts per thousand cells); a slot draws its kind once and goes unfilled
if it cannot seat it, so the mix stays honest. A placement must be on a
floor cell, clear of every **keep-clear rect** — bridge mouths, every flight
and the ground it joins at both ends — by the obstacle's own radius, off the
island's **clear disc** (`_GRID_BOSS_CLEAR_RADIUS` round the boss island's
centre, `_GRID_SPAWN_CLEAR` round the hero's spawn pixel,
`_GRID_CLEAR_RADIUS` round a special island's interactable), far enough from
a terrace above that its art does not reach onto it (`rules/frontier.py`),
and spaced off every other obstacle (trees space their canopies, 55 px).
Houses go first, then a tree **top-up** thickens the groves already there.

Then `gen/repair.py — unseal`: can the widest navigating body still reach
everywhere bare terrain allows? Where not, the fewest obstacles that reopen
the region are taken back. The keep-clear rules protect the chokes we knew
about; this catches the ones nobody predicted.

### 1.8 What comes out

`islands._grid_tile_meta` projects the grids into `Room.tile_meta`
(`TileMeta(floor, surface, foam, room_id, ramp)`) for the renderer and any
later system. `WorldLayout(seed, rooms, corridors, bounds, start_id,
boss_id, obstacles)` is the seam: the camera clamps to `bounds`, the collider
reads rooms and bridges, the spawn director reads rooms, the bake reads
everything.

`gen/validate.py — validate(layout)` reads every promise above back off a
finished world as a list of sentences; the tests run it on every cached
world. `world/digest.py` fingerprints the layout, the bake and one drawn
frame; `python -m world.digest --write` re-pins them after an intended
change.

---

## 2 · Runtime — collision, elevation, navigation (assetless)

**`GameMap(seed)`** (`world/map.py`) wraps a `WorldLayout` (or, with
`seed=None`, one big `WORLD_WIDTH × WORLD_HEIGHT` room for tests and menus).

- `_point_ok(x, y)` — on an island cell or a bridge. The body of this rule is
  `world/rules/floor.py — point_on_floor`; the navigation grid reads the same
  function, so the two cannot drift.
- `inset_ok(x, y)` — at least `body_inset()` px (from `terrain.json`) inside
  its own terrace, read off the inset field; a body already inside the
  margin may still move as long as it does not go deeper.
- `path_ok(prev, new)` — the elevation rule: the segment is walked half a
  tile at a time and every tile change must satisfy `rules/steps.py —
  can_step` against the `LevelIndex`. A plateau's flank and back edge are
  level changes with no stone in them; only a flight crosses them.
- `is_walkable(pos, radius, frm)` combines the three with the obstacle
  circles; `resolve_movement` tries the move, then each axis slide, then a
  short hop in the compass direction nearest the intended heading.
- `blocking_obstacle_hit`, `random_point_in_room`, `offscreen_spawn_point`
  as before.

**`LevelIndex`** (`world/elevation.py`) rasterises every island grid into
flat per-tile arrays — `level` (the floor here, or none), `kind`, `top` (the
elevation of whatever stands here, walkable or not: what a shot has to
clear) and the flight cells verbatim. The only place the runtime learns an
elevation. **It answers elevation, not walkability.**

**`world/nav/`** — `NavGrid` (`lattice.py`) rasterises the floor outward
from the island cells and bridge rects at 32 or 48 px, marks bridges and
flights as leniency corridors, bakes a per-cell **step mask** from
`rules/steps.py`, and carries a per-cell **clearance** (`clearance.py`: a
chamfer distance to the nearest wall, lowered by the exact distance to each
obstacle edge). `FlowField` / `NavField` (`field.py`) build the shared
distance field enemies steer on, one per body class. `world/pathfinding.py`
re-exports the names.

---

## 3 · Display — `world/terrain/`

### 3.1 The bake — `bake.py` → `BakedTerrain`

Once, lazily, on the first draw (it needs a display). `TileSheets`
(`sheets.py`) adapts `terrain.json`'s tileset metadata and caches tiles;
`grid_paint.paint_room_levels` paints **one `SRCALPHA` surface per terrace
of every island** straight off its grid — ground autotiled against its own
terrace only, cliff faces from the sheet's cliff block (left / mid / right /
single × top / body / bottom), the stone flight sprites, the lateral ramp
wedges, the drop shadow a face casts, lakes left transparent for the water
buffer — and `grid_shore` lists the ground cells with sea or a lake beside
them, the foam anchors. `paint_bridge` tiles each bridge along its own rect
from the bridge sheet with the matching end caps. Then the water buffer, the
drop shadow sprite, the foam frames and their three routines, the obstacle
skins (`decor/obstacle_skins.py`), the tree shades (`decor/shadows.py`),
the interior clutter (`decor/scatter_room.py`) and the water scenery
(`decor/scatter_water.py`).

All of it lands on a `BakedTerrain` (`baked.py`), which `GameMap.terrain`
holds; the old private names (`_grid_surfs`, `_shore`, `_decos`, ...) are
forwarding properties on the map.

### 3.2 The frame — `render.py — TerrainRenderer`

`draw_water` paints the scrolling water buffer, then a foam frame under every
in-view shore anchor (three fps/phase routines assigned by a stable spatial
bucket, so the coastline does not advance in lock-step), then the void
scenery. `draw_ground_band(level)` paints every terrace surface of that
level, south-first within the level, and the bridges with level 0.
`PlayingState` calls the bands ascending and slots the depth-sorted layer
(`banded_scenery` / `scenery_drawables`: obstacles, their tree shades,
interior clutter, and the characters, ordered by ground-contact Y) between
them, so a sprite standing on a lower terrace is covered by the terrace
above it. Animation time comes from `TerrainRenderer.seconds()`, a seam the
frame digest pins.

Draw-time zoom: baked surfaces are 1:1 world pixels; `_z_surf` scales a
cached copy per zoom.

### 3.3 Flat fallback — `_draw_flat_layout`

Triggered when the `floor_sheet` is missing or unreadable. Pure
`pygame.draw`: `_VOID` fill, `_FLOOR` bridge strips, per-kind tinted island
rects with a 3 px `_WALL` border, obstacles as filled circles in
`Obstacle.color`. No water, foam, terraces or sprites — and fully playable.

### 3.4 Independent degradation

| missing / off | effect |
|---|---|
| `floor_sheet` | whole level falls back to §3.3 |
| `water_tile` | terraces still draw; void becomes `surface.fill(_VOID)` |
| `bridge.sheet` | bridges bake plain `interior` grass instead of planks |
| `Water_Foam.png` **or** `config.TERRAIN_FOAM = False` | no shoreline foam |
| a `deco_*` rig / `config.TERRAIN_DECORATIONS = False` | that obstacle draws a circle |
| `config.TERRAIN_SHADOWS = False` | no tree shade patch |
| `config.TERRAIN_DECOR = False` or empty `decorations` | no interior clutter, no water scenery |
| `config.TERRAIN_BUILDINGS = False` | no houses (a generation knob: the layout changes) |
| one `tilemap_N.png` of a palette | that terrace falls back to `floor_sheet` (`cell()` returns the probe tile) |

### 3.5 Non-colliding decoration scatter

Cosmetic scenery, built once from string seeds (`f"{seed}:{room.id}:decor"`,
`f"{seed}:{gx}:{gy}:void"` — stable regardless of `PYTHONHASHSEED`), drawn per
frame. **Nothing here touches `obstacles` or `is_walkable`.** The
`decorations` registry in `terrain.json` names each prop's rig, placement
(`room_interior`, `void`, `shore`, `lake`), tier and density; interior props
are budgeted per terrace by biome (`decor/budget.py`), placed on interior
cells clear of every frontier and obstacle (`decor/spacing.py`,
`rules/frontier.py`), and grouped by the biome's tree family. Water scenery
lands on a 160 px lattice over the open sea, on the shoreline ring of every
island, and on the lakes.

---

## 4 · `data/terrain.json` reference

| key | meaning |
|---|---|
| `tile_px` | cell size in the sheet (64) |
| `grid` | `[cols, rows]` of a ground tilemap sheet (`[9, 6]`) |
| `floor_sheet` | default ground tilemap; its presence is the tiled/flat switch |
| `water_tile` | single tile used to fill the void buffer |
| `slots` | semantic name → sheet index: the autotile ring, `cliff` (× top / body / bottom), `raised` (keyed by exposed sides), `ramp` (keyed by descent direction). **Index → cell → cut rect: `terrain_tile_slots_formula.md`.** |
| `bridge` | plank autotile — `{sheet, grid, slots: {h_left, h_mid, h_right, v_top, v_mid, v_bot}}` |
| `vstair` | the stone flight sprites, one per drop |
| `floor_sheets`, `room_palettes` | per-level and per-kind fallbacks for a terrace the island's palette does not name |
| `sheet_biomes`, `sheet_flags`, `biomes` | what each tileset *is*: its biome, whether its shoreline block carries surf, and per biome the `scatter` mix, the `decor` rates per tier and the `trees` family (`world/rules/biome.py`) |
| `decor_placement`, `decorations`, `rigs` | the prop registry, rig definitions and placement rules (§3.5) |
| `obstacle_decor` | obstacle skins: `rigs` per kind, `size_boost`, `render_radius`, `render_scale`, `sprite_drop`, `tree_shadow` |
| `foam_routines`, `tree_routines` | the desynchronised animation clocks |
| `body_inset`, `decor_placement.edge_inset` | the terrace margin a body / a prop keeps |

`game/assets.py — Assets.tile(sheet_rel, index, *, size=None, cols=None)`
slices one cell from a sheet loaded `convert_alpha()`, memoised by
`(sheet_rel, index, size, cols)`; returns `None` for a missing sheet or an
out-of-range index.

---

## 5 · Asset vs assetless — side by side

| aspect | assetless (flat) | asset-backed (tiled) |
|--------|------------------|----------------------|
| layout, height maps, roles, obstacles | `world/gen` — **identical** | identical |
| collision, elevation, navigation, spawn points | `GameMap`, `LevelIndex`, `NavField` — **identical** | identical |
| camera clamp | `bounds` — **identical** | identical |
| terraces | one tinted rect per island | one baked, autotiled surface per terrace, composited band by band |
| cliffs, flights | — (the elevation rule still applies) | cliff faces, stone flights, ramp wedges, drop shadows |
| void | `_VOID` fill | scrolling water buffer + water scenery |
| bridges | plain `_FLOOR` strip | directional plank bridge with end caps |
| shoreline | 3 px `_WALL` border | autotile fringe + animated foam at every water-facing ground cell |
| obstacles | filled circle | a decoration rig per biome; trees cast a round shade over the characters |
| interior detail | — | seeded clutter per terrace, by biome |
| draw order | map, then all entities | terrace bands with the depth-sorted sprites between them |

**Guarantee:** an empty `assets/` still boots, generates, and plays every
system — only the look changes to primitives.

---

## 6 · Extending

### Authored (non-procedural) levels

`generate_world` is the only producer of a `WorldLayout` today, but the
runtime and the bake only consume the dataclass. A hand-authored layout —
islands with a `grid`, bridges, obstacles, `start_id` / `boss_id` — dropped
into a `WorldLayout` would render and play with no renderer change; run
`gen/validate.py` over it first, and `assign_palettes` /
`_build_inset_fields` if the palette and the inset field are not authored.

### A new tileset

Add the sheet to a topography's pool in `config.HEIGHTMAP_TOPOGRAPHIES`, name
its biome in `sheet_biomes` (an unlisted sheet is its own biome, "unlike
everything"), flag it `shoreline: false` in `sheet_flags` if its shore block
has no surf, and give the biome a `scatter` mix, `decor` rates and a `trees`
family in `biomes`. No code.
