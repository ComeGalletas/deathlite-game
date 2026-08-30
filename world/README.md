# `world/` — how a level is generated and drawn

This guide walks the whole pipeline by function name: **generate → bake →
draw**, plus a section on **how the tilesheet is split into slots** and **how to
draw a tile into the world**.

The package is split into three layers:

| layer | where | job |
|---|---|---|
| **data model** | `world/layout.py` | `TileMeta`, `Room`, `Corridor`, `Stair`, `WorldLayout` — the shape `generate_world` produces |
| **generation** | `world/gen/` | `generate_world` + six stage modules (`tuning`, `rooms`, `graph`, `links`, `verticality`, `scatter`) |
| **terrain** | `world/terrain/` | `TileSheets` (tilesheet adapter), `autotile` (slot maths), the painters (`rooms`, `cliffs`, `decor`), and `TerrainRenderer` (the draw path) |
| **facade** | `world/map.py` | `GameMap` — collision / spawn queries, the bake **sequence** (`_build_tiles`), and thin delegators to `TerrainRenderer` |

`world/procedural.py` is a 22-line re-export shim kept for old imports
(`from world.procedural import Room, generate_world, SPECIAL_KINDS`). New code
should import from `world.layout` / `world.gen`.

---

## Part 1 — Generating a level: `generate_world(seed, room_count=None)`

`world/gen/__init__.py`. Pure and deterministic — the same seed always yields a
byte-identical `WorldLayout`. Steps, in order:

1. **Grow a tree of chunk cells.** Starting from cell `(0, 0)`, repeatedly pick
   a random free cell orthogonally adjacent to an occupied one
   (`rng.choice(frontier)`) until `config.WORLD_ROOM_COUNT` cells exist. Every
   new cell records a tree `edge` to its parent, so the room graph is always
   fully connected.

2. **Build one `Room` per cell.** For each cell, `_cell_rect(cell, chunk)` is
   the full chunk box; `_room_frac(rng, irregular)` (`world/gen/rooms.py`)
   rolls a size fraction, snapped to `config.TILE_PX` so the tiled renderer's
   grid covers the room exactly. The `Room` starts as `kind="combat"`.
   Tree edges become `Room.neighbors`.

3. **Lay a `Corridor` on every tree edge.** `_connection_lane(seed, a, b, …)`
   (`world/gen/links.py`) picks a stable, tile-aligned crossing lane on the two
   rooms' shared edge span (using a *local* RNG so it doesn't disturb the world
   stream). The `Corridor` records its `axis` (`"h"`/`"v"`), which mouth is
   which (`end_low`/`end_high` = west/east or north/south), and the two rooms
   it butts against.

4. **Assign roles.** `_distances(rooms, start_id)` (`world/gen/graph.py`) BFS
   from room 0; the farthest room becomes `boss_id`. `_assign_kinds(…)` labels
   the six special rooms (`SPECIAL_KINDS` in `world/gen/tuning.py`:
   `shrine`, `treasure`, `fountain`, `altar`, `merchant`, `elite_arena`).

5. **Carve room floor shapes.** Each `Room.cells` is a `frozenset` of
   **room-relative** `(col, row)` tile coordinates.
   - Default: `_full_cells(w, h)` — the whole rectangle.
   - `config.IRREGULAR_ROOMS`: `_grow_rooms(…)` may extend a combat room a
     tile-aligned block into one empty neighbour chunk, then
     `_carve_room_shapes(…)` bites 2–3-cell notches out of corners (L / T /
     plus / stepped). `_relink_corridors(…)` re-snaps corridor lanes if any
     room grew.

6. **Verticality** (only if `config.WORLD_VERTICALITY`; otherwise `stairs` stays
   empty and every room is `floor 0`). In `world/gen/verticality.py` /
   `graph.py`:
   - `_assign_floors(…)` raises 1–2 connected plateaus to floor 1, escalates
     inner parts to floor 2, and may sprout a 1-room floor-3 pocket.
   - Cross-floor corridor lanes are re-centred on the shared span, then
     `_relink_corridors(…)` again.
   - `_plan_ramps(…)` (if `config.RAMP_STAIRS`) picks room pairs that can carry
     a diagonal ramp run and snaps them into contact.
   - `_split_links(rooms, corridors, rng, ramped)` (`world/gen/links.py`)
     replaces every remaining cross-floor `Corridor` with a `Stair`
     (1–2 tiles wide; `config.STAIR_WIDE_EVERY` sets the wide rate).
   - `_ramp_steps(…)` emits the five one-tile `Stair` steps of each ramp run
     (tagged `Stair.ramp`).
   - `_collect_annex(…)` gives each staircase-unit landing an owning room via
     `Room.annex` (so its edges autotile flat).
   - `_carve_cliffs(…)` trims room cells so a cliff band has somewhere to hang.

7. **Finalise coordinates.** Union every rect + margin → `bounds`; shift the
   whole world so `bounds` starts at `(0, 0)` (keeps the camera clamp simple).

8. **Scatter obstacles.** `_scatter_obstacles(rooms, corridors, rng, …,
   stairs=…)` (`world/gen/scatter.py`) — rocks / pillars / trees / houses as
   circular `Obstacle`s, deterministic per room, keeping room centres and
   corridor doorways clear. Internally calls `_topup_trees` and
   `_scatter_houses`.

9. **Per-tile metadata.** `_build_tile_meta(rooms, plan)` fills every
   `Room.tile_meta` — one `TileMeta` per `Room.cells` entry — recording
   `floor`, `surface` (`"room"`), `foam` (may this edge join the shoreline),
   `cliff` (`""` / `"top"` for a south-rim cell), `cliff_var`
   (`left`/`mid`/`right`/`single` run position), `lip` (exposed n/e/w edges of a
   plateau), `room_id`, and `ramp` (descent direction on a ramp's start cell).
   This runs **unconditionally and draws no RNG**, so a flat world stays
   byte-identical — it just gets `floor 0 / foam True` everywhere.

Returns `WorldLayout(seed, rooms, corridors, bounds, start_id, boss_id,
obstacles, stairs)`.

### Runtime queries on `WorldLayout`

- `layout.tile_at(wx, wy)` → the `TileMeta` under a world point (room cell from
  `Room.tile_meta`; synthesised for corridor / stair cells), or `None` in the
  void.
- `layout.walkable_rects()` → every room + corridor + stair rect.
- `layout.room(id)`, `layout.bfs_distances(src)`, `layout.is_connected()`.

---

## Part 2 — Baking the terrain: `GameMap._build_tiles()`

`world/map.py`. Called **lazily** on the first `draw_ground` (guarded by
`self._tiles_ready`). It turns the `WorldLayout` into pre-rendered `Surface`s
and anchor lists stored on the `GameMap`. If the tileset assets are missing it
returns early and the flat fallback renderer takes over permanently.

1. `get_assets()`, then `sheets = TileSheets(a)` (`world/terrain/sheets.py`).
   Bail to the flat renderer if `not sheets.ok`.

2. **LD-7a cliff-cap pass.** Find every ground-room edge cell that sits
   directly under a raised room's cliff band; collect them in
   `self._cliff_capped` (a set of `(room_id, col, row)`). `paint_room` closes
   the north side of those cells so they don't autotile / foam as a shoreline.

3. **`terrain_rooms.paint_room(self, sheets, layout, r)`** for every room →
   `self._room_surfs[r.id]`. Also appends sea-facing edges to `self._shore`.

4. **`terrain_rooms.paint_corridor(sheets, layout, c)`** for every corridor →
   `self._corr_surfs` (list of `(blit_rect, surface)`).

5. **`terrain_cliffs.paint_cliff(self, sheets, layout, r)`** for every raised
   room → `self._cliff_surfs` (list of `(blit_rect, surface, floor)`). Also
   appends `self._cliff_foam` (feet over open water), `self._cliff_shadow`
   (feet over a lower room), `self._cliff_underlay` (a lower-room grass tile
   drawn under a cliff foot), and `self._ramp_surfs` (LD-4 staircase-unit
   tiles, lifted out of the cliff surface).

6. **`terrain_cliffs.paint_stair(sheets, layout, st)`** for every non-ramp
   `Stair` → `self._stair_surfs`. Ramp steps (`Stair.ramp` set) are skipped —
   `paint_cliff` already drew them as part of the run.

7. **Shore filter.** Keep only `self._shore` anchors that are *still*
   sea-facing now that corridors, stairs and cliffs are all placed.

8. **Water + foam.** Tile `water_tile` into a `SCREEN + 1 tile` scroll buffer
   (`self._water_buf`); load the static `terrain_shadow` sprite
   (`self._shadow`); load the `terrain_foam` frames (`self._foam`) and parse
   `foam_routines` into `self._foam_routines`.

9. **Decor.** `terrain_decor.build_obstacle_decor(self, a)` skins each obstacle
   with a rig scaled to its collider (`self._decos`) and calls
   `build_tree_shadows(self, conf)` (`self._tree_shadows`);
   `terrain_decor.build_decor_scatter(self, a)` seeds non-colliding clutter
   (`self._room_decor`, `self._void_decor`).

10. `self._tiles_ok = True`.

---

## Part 3 — Drawing a frame

### `GameMap.draw_ground(surface, camera)` → `TerrainRenderer.draw_ground`

`world/terrain/render.py`.

1. Lazily `_build_tiles()` on first call.
2. If `camera.zoom` changed, update `self.gm._render_zoom` and clear the
   scaled-surface cache `self.gm._blit_cache`.
3. No layout → fill `_VOID`, draw a reference floor rect + `_draw_grid`, return.
4. `_tiles_ok` → `_draw_tiled(surface, camera)`. Otherwise `_draw_flat_layout`
   (coloured rects per room kind) + grey wall borders.

### `TerrainRenderer._draw_tiled(surface, camera)` — the layer order

Bottom to top (everything blitted through `_z_surf` for zoom, and positioned as
`(world_x - camera.pos.x) * zoom`):

1. **Water** — `self.gm._water_buf` scrolled by `camera.pos % water_tile`
   (or `_VOID` fill if no water tile).
2. **Foam** — one animated frame at every `self.gm._shore` and
   `self.gm._cliff_foam` anchor, via `self.gm._foam_frame_at(wx, wy, seconds)`
   (which picks a routine bucket with `_foam_routine_index`). The foam sprite is
   larger than a tile and blitted centred on the shore cell.
3. **Void decor** — `self.gm._void_decor` via `_blit_decor` (water props sit
   *above* foam so a shoreline animation never washes over them).
4. **Cliff-foot underlay** — `self.gm._cliff_underlay` `(rect, tile)` pairs: one
   lower-room grass tile under each cliff foot that has a room to its south, so
   the cliff sits on grass, not sea.
5. **Cliff drop-shadow** — `self.gm._cliff_shadow` accumulated onto a scratch
   `SRCALPHA` surface with `BLEND_RGBA_MAX` (so overlapping blobs of a
   continuous run merge into one soft strip), then blitted once.
6. **Cliff faces** — every `self.gm._cliff_surfs` entry, regardless of the
   owning room's floor. Cliffs are the lowest terrain layer proper, so a
   walkable surface always covers the stone where they meet.
7. **Room floors** — `self.gm._room_surfs`, **bottom floor up** (sorted by
   `r.floor`), so a higher plateau's grass overlaps the one below it.
8. **Stairs** — `self.gm._stair_surfs`.
9. **Ramp units** — `self.gm._ramp_surfs` (LD-4 landings + stair pieces).
10. **Corridors** — `self.gm._corr_surfs` last, so bridge grass renders over
    nearby shoreline foam.

Interior clutter is **not** drawn here — it is depth-sorted with the obstacles
and characters.

### `GameMap.scenery_drawables(camera)` → `TerrainRenderer.scenery_drawables`

Returns `[(depth_y, draw_fn), …]` for every visible obstacle and its tree
shade. `depth_y` is the sprite's ground-contact world y. The caller merges these
with the entity draw calls and paints back-to-front, so a character with a
smaller y than an obstacle is hidden behind it. Each `draw_fn` calls
`self.gm._draw_one_obstacle` / `self.gm._draw_one_tree_shadow` (routed through
`self.gm` so a test can monkey-patch them on the instance).

### Whole-frame composition (`game/states/playing/state.py::PlayingState.draw`)

```
game_map.draw_ground(surface, camera)        # Part 3 layer order above
game_map.draw_room_clutter(surface, camera)  # room interior props (unsorted)
renderer.interactables / hazards / gems / explosions
_draw_player_projectiles                      # weapon fx behind characters
_draw_depth_layer                             # scenery_drawables + enemies + boss
                                              #   + summons + player, sorted by y
_draw_hostile_projectiles                     # enemy shots on top
particles / damage_numbers / collider_overlay (dev)
hud.draw / feedback_overlays
```

`GameMap.shade_character_frame(frame, dest, camera, character_y)` is called by
the entity painters to overlay any intersecting tree shade through a character
sprite's alpha, independent of depth-sort order.

---

## Part 4 — How tiles are split up

All tile metadata lives in `data/terrain.json` and is read once per bake by
`TileSheets` (`world/terrain/sheets.py`). Tiles are **64 px** (`tile_px`).

### The grass sheets

`floor_sheet` is the ground (`tilemap_1.png`). `floor_sheets` maps a raised
floor index to an elevation sheet (`1→tilemap_2`, `2→tilemap_3`, `3→tilemap_5`),
and `room_palettes` maps a room *kind* to a recolour (`boss→tilemap_4`, …).
`TileSheets.sheet_for(floor, kind)` resolves which one a room uses: elevation
sheet if raised, else the kind palette, else the ground sheet. **Every sheet
shares the same slot layout** — a slot index means the same tile shape on all of
them.

### Slots (`slots` in `terrain.json`)

Each sheet is a **9-wide grid**; a slot is a flat index (`row*9 + col`).
`TileSheets.cell(sheet, idx)` returns the (cached) `Surface` for a slot.

**Ground autotile block** — a 3×3 rectangle at cols 0–2, rows 0–2:

```
 corner_nw  0    edge_n  1    corner_ne  2
 edge_w     9    interior 10  edge_e    11
 corner_sw 18    edge_s 19    corner_se 20
```

plus `single 30`, `strip_v [3,12,21]` (1-wide vertical), `strip_h [27,28,29]`
(1-wide horizontal). These have **transparent water-facing edges**, so a room
surface is baked `SRCALPHA` and foam / water show through.

**Cliff block** (`slots.cliff`) — three rows (`top` 32–35, `body` 41–44,
`bottom` 50–53), four run positions each (`left` / `mid` / `right` / `single`).
`TileSheets.cliff_idx(row, edge)` looks one up. `top` is the grass fringe at the
rim, `body` the stone face, `bottom` the scalloped foot.

**Raised block** (`slots.raised`) — a second 16-tile autotile block (cols 5–8,
rows 0–3) fringed with dark cliff-grass instead of shoreline surf, **keyed
directly by exposed sides**: `""→15`, `"n"→6`, `"nw"→5`, `"nswe"→35`, …
`TileSheets.raised_idx(meta)` builds the key from `TileMeta.lip` (+ south if
`cliff` is set and it's not a ramp start) and reads it — no re-derivation.

**Ramp pieces** (`slots.ramp`) — `"w": [36, 45]`, `"e": [39, 48]`
(top tile + bottom tile), keyed by descent direction.

**Bridge sheet** (`bridge`) — a *separate* 3-wide sheet (`bridge_all.png`) for
plank corridors and non-ramp stairs: `h_left/h_mid/h_right` and
`v_top/v_mid/v_bot`. `autotile.bridge_slot(axis, i, ncells)` returns the slot
*name* for cell `i` of a run (end caps at `0` and `ncells-1`, `mid` between).

### Autotiling a ground room — `autotile.mask_slot(cells, col, row, slots)`

`world/terrain/autotile.py`. Looks at the 4 orthogonal neighbours of `(col,
row)` in the room's `cells` set and counts the **gaps** (neighbour not a floor
cell):

- 0 gaps → `interior`
- 1 gap → the matching `edge_*`
- 2 gaps forming a convex corner → that `corner_*`
- anything else (opposite pair, nub, 3–4 gaps) → `interior` (best effort — the
  sheet has no concave-corner tile)

### The synthetic 3-sided grass tile — `TileSheets.three_sided(sheet, open_sides)`

The sheet has a 4-sided grass tile (`raised.nswe`) but no 3-sided one. For a
staircase-unit landing, `three_sided` starts from the flat `interior` tile and
blits a 15-px strip of the 4-sided tile back over each edge named in
`open_sides` (a subset of `"nswe"`) — flat toward the stair, strands toward the
open cut. Results are cached.

---

## Part 5 — How to draw a tile into the world

### Coordinate model

- **Baked surfaces are 1:1 world pixels.** A room's surface is blitted at
  `((r.rect.x - camera.pos.x) * zoom, (r.rect.y - camera.pos.y) * zoom)`, and
  the surface itself is passed through `TerrainRenderer._z_surf(surf)` — which
  returns a zoom-scaled copy (cached by `id(surf)`, identity at zoom 1.0).
- **Within a room surface**, a cell `(col, row)` from `Room.cells` is blitted at
  `(col * px, row * px)`. `Room.cells` is **room-relative** because room rects
  are tile-*sized* but **not** aligned to each other — every room has its own
  private grid. Never compute a global column from a world x; go through
  `Room.cells` / `Room.tile_meta` and the room's own origin.
- World-point lookup at runtime is `WorldLayout.tile_at(wx, wy)`.

### What each painter does (all in `world/terrain/`)

| painter | signature | returns / writes |
|---|---|---|
| `rooms.paint_room` | `(store, sheets, layout, r)` | a `Surface` for `store._room_surfs[r.id]`; appends `store._shore` |
| `rooms.paint_corridor` | `(sheets, layout, c)` | `(blit_rect, surface)` |
| `cliffs.paint_cliff` | `(store, sheets, layout, r)` | `(blit_rect, surface, floor)` or `None`; appends `store._cliff_foam` / `_cliff_shadow` / `_cliff_underlay` / `_ramp_surfs` |
| `cliffs.paint_stair` | `(sheets, layout, st)` | `(blit_rect, surface, high_room_id)` |
| `decor.build_obstacle_decor` / `build_tree_shadows` / `build_decor_scatter` | `(store, a)` / `(store, conf)` / `(store, a)` | fill `store._decos` / `_tree_shadows` / `_room_decor` / `_void_decor` |

`store` is the `GameMap`; each painter's docstring lists exactly which `store`
fields it reads and appends to.

### `paint_room` in one paragraph

Make a `SRCALPHA` surface the size of `r.rect`. For each `(col, row)` in
`r.cells`: pick the slot — `sheets.raised_idx(m)` if the room is raised,
`autotile.mask_slot(r.cells | r.annex, …)` if it's a ground room (closing the
north side for a `_cliff_capped` cell) — then
`surf.blit(sheets.cell(sheet, idx), (col*px, row*px))`. If the ground cell has
any non-floor orthogonal neighbour, append `(r.rect.x + col*px, r.rect.y +
row*px)` to `store._shore` so the foam pass laps against it.

### Adding a new terrain layer

1. Bake it in `GameMap._build_tiles` (call a new `world/terrain/…` function),
   storing `Surface`s / anchors on `self`.
2. Blit it in `TerrainRenderer._draw_tiled` at the right point in the layer
   order (§Part 3) — use the local `_blit(rect, surf)` helper (it view-culls and
   `_z_surf`-scales).
3. If it should depth-sort with characters instead (like obstacles), add it to
   `TerrainRenderer.scenery_drawables` as `(ground_contact_y, draw_fn)`.
4. If anything reads it from a bare `GameMap.__new__` instance (some rendering
   unit tests do), add a one-line delegator on `GameMap`.
5. Keep it deterministic: no RNG in a painter, and gate any new asset behind a
   `config` flag so a flag-off bake stays byte-identical (verified by the
   scratch A/B harnesses described in `journals/world_refactor.md`).
