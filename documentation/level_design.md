# Level design — generation & display

How a level comes to exist and how it gets on screen. The important split:

- **Generation** (`world/procedural.py`) is **pure data and never touches an
  asset.** Same seed → identical `WorldLayout`, with or without a single PNG on
  disk.
- **Display** (`world/map.py` + `game/assets.py`) has **two renderers** that
  draw the *same layout*: an **asset-backed tiled** renderer and a **primitive
  flat** renderer. The flat one is the permanent fallback — the game is fully
  playable with an empty `assets/`.

> File references are `path — symbol`; line numbers drift, symbols don't.
> Related: `COMBAT_CALCS.md` (damage), `terrain_tile_slots_formula.md` (how a
> tilemap cell is addressed / cut / placed), `../journals/assets_journal.md`
> (the terrain integration passes T1–T9).

---

## 1 · Generation — `world/procedural.py` (assetless, pure, deterministic)

`generate_world(seed, room_count=None) -> WorldLayout` is pure: the same seed and
the same code produce an identical layout (spec 8, "procedural generation
determinism"). All randomness goes through one `random.Random(seed)`.

### 1.1 Chunk lattice → spanning tree

The world is a lattice of square **chunk cells** (`config.CHUNK_SIZE`, 720 px).
Generation grows a **tree** of occupied cells outward from the start cell
`(0, 0)`: each step picks a random free cell orthogonally adjacent to an
occupied one and links it to its parent. Because it's a tree, **every room is
reachable from start by construction** (spec 5.4: "do not generate unreachable
critical rooms"). Stops at `config.WORLD_ROOM_COUNT` (16) cells.

### 1.2 Rooms

One room per cell. `Room(id, cell, rect, kind, neighbors)` where `rect` is an
axis-aligned world-pixel rectangle sized `55–86 %` of the cell
(`rng.uniform(0.55, 0.86)` per axis), then **each dimension is snapped to a
`config.TILE_PX` (64) multiple** — `round(dim / 64) * 64`, floor-clamped to
`3 × 64` — and re-centred (T7). Snapping means the tiled renderer's 64 px cell
grid covers a room exactly, with no clipped autotile edge tile. `room.center` is
the `Vector2` centre; `room.neighbors` is filled from the tree edges.

### 1.3 Corridors

One `Corridor` per tree edge — a straight axis-aligned rectangle, **one tile
wide** (`config.TILE_PX`, 64 px; T7), spanning **centre-to-centre** of the two
rooms (that overlap into both rooms is what keeps walkability seamless at the
mouths). Each corridor also records its **bridge edge identity**:

```python
axis: str          # "h"  -> west/east ends | "v" -> north/south ends
end_low:  str      # "west"  (h) | "north" (v)  — the edge at the smaller x / y
end_high: str      # "east"  (h) | "south" (v)  — the edge at the larger  x / y
room_low, room_high: int   # the room ids those two edges butt against
```

The tiled renderer uses `axis` + `room_low` / `room_high` to draw a directional
plank **bridge** whose end-cap tiles land on each room's shoreline tile — the
bake spans one tile *into* each room so the planks overlap the grass (§3.3); the
flat renderer draws a plain `_FLOOR` strip along `rect`. A 1-wide corridor is
deliberate — the bridge art is one tile on its short axis — and is accepted as a
pinch point for the largest enemy colliders (brute r30); revisit if playtests
show it bottlenecking.

### 1.4 Roles & special kinds

- `start_id = 0`.
- `boss_id` = the room with the greatest BFS distance from start.
- `_assign_kinds`: `start` and `boss` are fixed; the remaining ids are shuffled
  and the first few become one each of
  `SPECIAL_KINDS = (shrine, treasure, fountain, altar, merchant, elite_arena)`;
  the rest stay `"combat"`.

### 1.5 Obstacles — `_scatter_obstacles`

Per room, **skipping `start` and `boss`**, a few convex circular colliders:

| kind | radius | blocks projectiles | count rule |
|------|--------|--------------------|------------|
| `tree`   | 20 | yes | `rng.randint(3,7)` per combat room |
| `rock`   | 25 | yes | `10` in an `elite_arena` |
| `pillar` | 18 | yes | `2` in a shrine/treasure/fountain/altar/merchant |
| `shrub`  | 14 | no  | |

Never placed on a **corridor doorway** tile (`_corridor_doorways` — the mouth
cell of each corridor + one tile of margin) so an entrance is always walkable,
and ≥ 46 px from every other obstacle. **Special** rooms (`shrine` / `treasure`
/ `fountain` / `altar` / `merchant` / `elite_arena`) additionally keep a clear
central `min(w,h) * 0.22` disc for their interaction / fight space; plain
`combat` rooms may place obstacles anywhere. Each gets a cosmetic
`Obstacle.variant` (1–4, from the seed) used only by the renderer.
(`entities/obstacle.py — KINDS`.)

### 1.6 Bounds & shift

`bounds` = the union of every room + corridor rect, inflated by one chunk. The
**whole world is then translated so `bounds` starts at `(0, 0)`** — keeps the
camera clamp and collision math in a simple positive coordinate space.

### 1.7 `WorldLayout` — the seam

```python
@dataclass
class WorldLayout:
    seed: int
    rooms: list[Room]
    corridors: list[Corridor]
    bounds: pygame.Rect
    start_id: int
    boss_id: int
    obstacles: list        # entities.obstacle.Obstacle
```

Consumed by: the **camera** (clamp to `bounds`), **collision** (`GameMap`), the
**spawn director** (`world/spawning.py` reads rooms), and **both renderers**.
Helpers: `.room(id)`, `.walkable_rects()`, `.bfs_distances(src)`,
`.is_connected()`.

*(There is no decorations field on `WorldLayout`. Colliding scenery is a skin on
the obstacles; the non-colliding scatter — interior clutter + water scenery — is
built inside `GameMap` from a seed, never as entities. See §3.4 / §3.6.)*

---

## 2 · Collision & movement — `world/map.py` (assetless)

`GameMap(seed)` wraps a `WorldLayout` (or, with `seed=None`, one big
`WORLD_WIDTH × WORLD_HEIGHT` room used by tests and menus).

- `self._rects` = every room + corridor rect = the walkable set.
- `is_walkable(pos, radius=0)` — the point (and, if `radius>0`, the four cardinal
  offsets) must lie in some walkable rect **and** outside every obstacle circle.
- `resolve_movement(prev, new, radius)` — try the full move; if blocked, try
  sliding on X only, then Y only, else stay at `prev`. No physics engine.
- `blocking_obstacle_hit(pos, radius)` — first projectile-blocking obstacle
  overlapping a circle (used by the projectile resolver).
- `offscreen_spawn_point(camera, rng)` — a walkable point just outside the view,
  biased to the nearest rooms.

**None of this reads an asset.** Gameplay is identical whether or not the
tileset exists.

---

## 3 · Display — two renderers over one layout

`GameMap.draw(surface, camera)` picks a path **once**, on the first call, in
`_build_tiles()`:

```
layout is None                     -> §3.1 trivial renderer (tests / menus)
assets.tile(floor_sheet, interior) is None  -> §3.2 flat renderer  (assetless)
assets.tile(floor_sheet, interior) is a Surface -> §3.3 tiled renderer (asset-backed)
```

`self._tiles_ready` guards the one-time build; `self._tiles_ok` records which
renderer won. The build is deferred to the first `draw()` because it needs an
initialised display (`Surface.convert()`); headless tests that never draw never
build tiles.

### 3.1 No layout (`seed=None`)

`surface.fill(_VOID)` → one `_FLOOR` rect the size of the world → a 3 px `_WALL`
border → a 128 px debug grid (`_draw_grid`). Used by unit tests and any
non-run context.

### 3.2 Flat renderer — **assetless fallback** (`_draw_flat_layout`)

Triggered when `assets/terrain/tiles/tilemap_1.png` (the `floor_sheet`)
is missing or unreadable. Pure `pygame.draw`:

| element | how |
|---|---|
| void | `surface.fill(_VOID)` — `(10, 10, 14)` |
| corridors | `_FLOOR` rects — `(26, 26, 34)` |
| rooms | `_SPECIAL_FLOORS[kind]` rect if the kind has a tint (start / boss / shrine / treasure / fountain / altar / merchant / elite_arena), else `_FLOOR` |
| walls | 3 px `_WALL` border per room — `(68, 70, 92)` |
| obstacles | `_draw_obstacles`: filled circle in `Obstacle.color` + 2 px `_WALL` outline, at `Obstacle.radius` |

No water, no foam, no shoreline, no scenery sprites — just tinted rectangles and
circles. Fully playable.

### 3.3 Tiled renderer — **asset-backed** (`_build_tiles` + `_draw_tiled`)

**Bake (once).** `data/terrain.json` supplies the vocabulary (§4).

- **Rooms** — `paint_room(r)` allocates one **`Surface(rect.size, pygame.SRCALPHA)`**
  (T6: per-pixel alpha, so the autotile edge/corner tiles' transparent
  water-facing side is *kept*, not flattened to black), walks every 64 px cell,
  and blits the tile `_slot_for(row, col, rows, cols)` picks — `corner_*` at the
  four corners, `edge_*` along the sides, `interior` inside — from that room
  kind's palette (`room_palettes[kind]`, e.g. the boss floor is
  `tilemap_4.png`). Perimeter cells are added to `self._shore`.
- **Corridors** — `paint_corridor(c)` bakes a **directional plank bridge** from
  `bridge.sheet` (`terrain/bridge/bridge_all.png`, its *own* 3-wide grid — passed to
  `Assets.tile(..., cols=3)`). The surface spans from **one tile inside
  `room_low`** to **one tile inside `room_high`** (`edge ∓ tile_px`), *not* the
  centre-to-centre collision `rect`: the end-cap tiles land on each room's
  shoreline tile so the planks visibly meet the grass instead of falling short
  of it or being buried at the room centres. `_bridge_slot(c.axis, i, ncells)` gives the
  low cap (`h_left` / `v_top`) at cell 0, the high cap (`h_right` / `v_bot`) at
  the last cell, `h_mid` / `v_mid` between — matching `Corridor.end_low` /
  `end_high`. SRCALPHA (the plank gaps are transparent); every plank cell is
  added to `self._shore` so foam shows through the gaps over open water. No
  bridge sheet → the plain `interior` grass tile. `_corr_surfs` holds
  `(blit_rect, surface)` — the blit rect is this tight mouth-to-mouth span.
- **Doorway seam** (T9) — after both rings are collected, any `self._shore` cell
  whose 64 px tile touches *both* a room rect and a corridor rect (inflated by
  `tile_px`) is dropped: the bridge/room junction then reads as solid ground,
  while mid-bridge cells (corridor only) keep their gap foam and open room edges
  (room only) keep their shoreline.
- Also baked: `self._water_buf` (the `water_tile` tiled into a `SCREEN + 1 tile`
  scroll buffer, opaque `.convert()` — bottom layer, biggest blit); if enabled,
  `self._foam` (`Water_Foam.png`, 16 frames); `self._decos` (one scaled rig per
  obstacle) + `self._tree_shadows` (a round shade per tree — §3.4); and the seeded
  non-colliding scatter `self._room_decor` / `self._void_decor` (§3.6).

**Ground pass (per frame), `GameMap.draw_ground` → `_draw_tiled`** — bottom to top:

1. `self._water_buf` blitted at `(-(ox % wt), -(oy % wt))` — the scrolling water
   void (one blit). `water_tile` missing → `surface.fill(_VOID)` instead; the
   baked rooms still draw.
2. **void scenery** (`self._void_decor`) — water rocks / a duck on the open
   water, animated, view-culled (§3.6).
3. `config.TERRAIN_FOAM` → the current `Water_Foam` frame, centred on every
   in-view `self._shore` cell. Drawn **behind** the terrain (T6): it only shows
   through the transparent water-side of the `edge_*` / `corner_*` tiles and the
   bridge plank gaps, plus on the open water just outside a room.
4. each in-view room's baked surface at `room.rect - camera`.
5. each in-view corridor's baked bridge surface.

Interior clutter and obstacles are **not** drawn here — they go in the
depth-sorted layer (§3.7). `GameMap.draw` (the whole-map convenience used
outside `PlayingState`) instead follows `draw_ground` with `_draw_room_clutter`
+ `_draw_obstacles`, both unsorted.

**Per-frame cost** ≈ 1 water blit + ~5 baked-surface blits + ~30–60 foam blits
≈ 1 ms, plus ~50 scatter/decoration blits and the obstacle skins in §3.7.

### 3.4 Obstacles in each renderer

`_draw_one_obstacle(surface, camera, i, o)` is shared (looped by
`_draw_obstacles` for the unsorted path, and wrapped as a depth entry by
`scenery_drawables` for the sorted one):

- **tiled + `TERRAIN_DECORATIONS`**: the obstacle is skinned with a decoration
  rig (`obstacle_decor.rigs[kind]`, `Obstacle.variant` picks one of four) scaled
  so the rig's measured `footprint` covers `2 · radius · size_boost` on screen;
  `tree` → the animated `deco_tree_1..4` (8-frame sway), `shrub` → `deco_bush_*`,
  `rock` / `pillar` → `deco_rock_*`. No under-skin shadow — obstacles just blit
  their frame at the collider centre.
- **flat renderer, `TERRAIN_DECORATIONS` off, or a decoration rig missing**:
  the obstacle falls back to the drawn circle from §3.2.

So collision is always the circle; only the *pixels* differ.

**Tree shade (B3).** When `config.TERRAIN_SHADOWS` is on, each skinned `tree`
gets a soft round patch — a small SRCALPHA surface of concentric translucent
fills (`obstacle_decor.tree_shadow = {radius_scale, color, alpha}`,
`R = radius · 1.9`), precomputed once per distinct `R` in `_build_tree_shadows`.
`draw_tree_shadows` blits it centred on the trunk **after** the depth-sorted
layer (§3.7), so a hero / enemy standing under a tree is gently darkened. It is
the only obstacle that casts anything.

### 3.5 Independent degradation

| missing / off | effect |
|---|---|
| `floor_sheet` (`tilemap_1.png`) | whole level falls back to §3.2 flat |
| `water_tile` | tiled rooms still draw; void becomes `surface.fill(_VOID)` |
| `bridge.sheet` (`Bridge_All.png`) | corridors bake plain `interior` grass instead of planks |
| `Water_Foam.png` **or** `config.TERRAIN_FOAM = False` | no shoreline foam (autotile edge tiles are the boundary) |
| a `deco_*` rig / `config.TERRAIN_DECORATIONS = False` | that obstacle draws a circle |
| `config.TERRAIN_SHADOWS = False` | no tree shade patch (nothing else changes) |
| `config.TERRAIN_DECOR = False` or empty `decorations` | no interior clutter, no void scenery (§3.6) |
| one `tilemap_N.png` palette | that room kind falls back to `floor_sheet` (`cell()` returns the `probe` tile) |

Every flag is independent; hero / enemy / projectile sprites degrade the same
way — see `README.md` "Assets" and `COMBAT_CALCS.md`.

### 3.6 Non-colliding decoration scatter (T8) — `_build_decor_scatter`

Cosmetic scenery, built once from a **string seed** (`f"{layout.seed}:{room.id}:decor"`
/ `f"{seed}:{gx}:{gy}:void"` — stable regardless of `PYTHONHASHSEED`) and drawn
per frame. **Nothing here touches `self.obstacles` or `is_walkable`.**

- **Registry** — `terrain.json` `decorations` is an array; each entry is
  `{id, rig, placement, scale, per_room|chance, collision}` where `rig` names an
  existing entry in `rigs`. A new prop is a new rig + a new line — no code.
- **`placement: room_interior`** — clutter (`pebble_*` → `deco_rock_*` at ~0.5×)
  on a room's *interior* cells only, kept clear of the centre, ≥ 20 px off any
  obstacle, ≥ 40 px apart; `per_room: [lo, hi]` count.
- **`placement: void`** — water scenery (`water_rock_*` → `deco_water_rock_*`,
  `duck` → `deco_duck`) on a 160 px grid over `bounds` (inset `CHUNK//3`), placed
  only where the point *and* ±36 px all fail `_point_ok` (never clipping a
  shore); per-cell `chance`, capped at 240.
- Instances are `(frames, anchor_x·scale, anchor_y·scale, fps, world_x, world_y)`,
  resolved once. `_blit_one_decor` picks the current `get_ticks` frame and blits
  the base at `(world_x, world_y)`. `collision: true` entries are the world
  generator's job (trees are already obstacles), not this scatter.

### 3.7 Depth-sorted layer — scenery + characters interleaved

Obstacles, interior clutter and the characters (hero, enemies, boss, summons,
death animations) are painted in **one back-to-front pass ordered by
ground-contact world Y** — so a sprite lower on the map (larger Y) draws over the
ones above it, and a character standing behind (a *smaller* Y than) a tree is
hidden by its canopy.

- `GameMap.scenery_drawables(camera)` → `[(depth_y, fn), …]` — one entry per
  in-view obstacle (`depth_y = o.pos.y`, `fn` = `_draw_one_obstacle`, the skin
  frame) and per in-view clutter instance (`depth_y = world_y`,
  `fn` = `_blit_one_decor`).
- `PlayingState._depth_items()` appends the characters — `depth_y = entity.pos.y`
  (the sprite anchor sits on `pos`, i.e. the feet) — then `sort`s by `depth_y`
  (stable: on a tie, scenery < enemies < dying < boss < summons < player).
- `PlayingState._draw_depth_layer` just calls each `fn(surface)` in order.
- Immediately after, `GameMap.draw_tree_shadows` blits each visible tree's shade
  patch — *over* the characters, so anyone under a tree is darkened (§3.4).

Everything else keeps its fixed layer: `draw_ground` under this pass;
interactables / hazards / gems / explosions between the ground and this pass;
projectiles, particles, damage numbers, then the HUD on top. `GameMap.draw`
(non-`PlayingState` callers) still draws clutter + obstacles unsorted, then the
tree shades.

---

## 4 · `data/terrain.json` reference

| key | meaning |
|---|---|
| `tile_px` | cell size in the sheet (64) |
| `grid` | `[cols, rows]` of the tilemap sheet (`[9, 6]`) |
| `floor_sheet` | default floor tilemap; its presence is the tiled/flat switch |
| `water_tile` | single tile used to fill the void buffer |
| `slots` | semantic name → flat sheet index: `interior`, `edge_n/s/w/e`, `corner_nw/ne/sw/se`, `strip_v/h`, `single`. **Index → cell → cut rect and the position rule that picks a slot per room cell: `terrain_tile_slots_formula.md`.** |
| `bridge` | corridor plank autotile — `{sheet, grid: [cols, rows], slots: {h_left, h_mid, h_right, v_top, v_mid, v_bot}}`. Its own grid width (3), passed to `Assets.tile(..., cols=3)`. |
| `room_palettes` | room kind → tilemap path (`default`, `boss`, `treasure`, `shrine`, `fountain`); other kinds use `floor_sheet` |
| `decorations` | **array** of non-colliding scatter entries `{id, rig, placement, scale, per_room|chance, collision}` — see §3.6 |
| `obstacle_decor.size_boost` | how much bigger than the collider a skin draws (1.25) |
| `obstacle_decor.tree_shadow` | `{radius_scale, color, alpha}` for the round shade patch each tree casts over the characters (§3.4) |
| `obstacle_decor.rigs` | obstacle kind → list of interchangeable decoration rig names (`tree` → `deco_tree_*`, `shrub` → `deco_bush_*`, `rock`/`pillar` → `deco_rock_*`) |
| `rigs` | animation rigs (`deco_bush_1..4`, `deco_rock_1..4`, `deco_tree_1..4`, `deco_water_rock_*`, `deco_duck`, `terrain_foam`): `frame`, `anchor`, `footprint`, `anims.loop = {file, frames, fps, loop}` |

`game/assets.py — Assets.tile(sheet_rel, index, *, size=None, cols=None)` slices
one cell: `sheet.subsurface(rect).copy()` (the sheet is loaded `convert_alpha()`,
so cells keep their alpha), optional `pygame.transform.scale`, memoised by
`(sheet_rel, index, size, cols)`. `cols` defaults to `terrain.grid[0]` (the
floor sheet's width) — pass it for a sheet of a different width, e.g. the 3-wide
bridge sheet. Returns `None` for a missing sheet or an out-of-range index.

---

## 5 · Asset vs assetless — side by side

| aspect | assetless (flat) | asset-backed (tiled) |
|--------|------------------|----------------------|
| layout, room graph, roles | `world/procedural.py` — **identical** | identical |
| collision, `resolve_movement`, spawn points | `GameMap` — **identical** | identical |
| camera clamp | `bounds` — **identical** | identical |
| floor | tinted `pygame.draw.rect` per room / corridor | baked grass `tilemap_N` surface, autotiled edges |
| room-kind cue | `_SPECIAL_FLOORS` colour | `room_palettes` tileset (boss = color4, …) |
| void | `_VOID` fill | scrolling `Water_Background` buffer + water scenery scatter (§3.6) |
| corridors | plain `_FLOOR` strip, 64 px wide | directional plank **bridge** (`Bridge_All.png`), foam through the gaps |
| room boundary | 3 px grey `_WALL` rect border | autotile `edge_*` / `corner_*` tiles (+ optional foam), doorway seam trimmed |
| shoreline foam | — | `Water_Foam` 16-frame animation *behind* the perimeter tiles |
| obstacles | filled + outlined circle (`Obstacle.color`, `.radius`) | scaled decoration rig (`deco_tree_*` / `deco_bush_*` / `deco_rock_*`); circle if a rig is missing. Trees also cast a round shade patch over the characters |
| interior detail | — | seeded non-colliding clutter on room interiors (§3.6) |
| obstacle / character order | fixed: map first, then all entities | **depth-sorted by feet Y** (§3.7) — a hero above a tree is drawn behind it |
| draw cost | a few dozen `draw` calls | ~1 water blit + ~5 baked + ~30–60 foam + ~50 scatter + the sort ≈ 1–1.5 ms |
| config flags | none | `TERRAIN_FOAM`, `TERRAIN_DECORATIONS`, `TERRAIN_DECOR`, `TERRAIN_SHADOWS` (each independent) |

**Guarantee:** an empty `assets/` still boots, generates, and plays every
system — only the look changes to primitives.

---

## 6 · Extending

### Authored (non-procedural) levels

`generate_world` is the only producer of a `WorldLayout` today, but the renderer
and collision only consume the dataclass. A hand-authored layout — rooms /
corridors as rects, obstacles, `start_id` / `boss_id` — dropped into a
`WorldLayout` would render and play with **no renderer changes**.
`terrain.json` stays the tile *vocabulary*; the authored file is the *where*.
`slots` lets an authored map name tiles semantically instead of hand-placing
indices.

### Tile layering / transparency — **shipped** (T6–T9)

The baked room/corridor surfaces are `pygame.Surface(size, pygame.SRCALPHA)`
(T6): the autotile `edge_*` / `corner_*` tiles keep their transparent
water-facing side instead of baking it to black, so anything drawn *under* the
terrain (foam, water, void scenery) shows through the fringe with no black gaps.
The water buffer stays opaque `.convert()` (bottom layer, biggest blit). On top
of that:

- **T7** — rooms snap to a 64 px grid so the autotile ring always completes;
  corridors are directional plank **bridges** (`bridge` block), SRCALPHA, foam
  through the plank gaps.
- **T8** — a data-driven `decorations` registry feeds a seeded non-colliding
  scatter (interior clutter + void water scenery), drawn per frame between the
  water and the terrain / above the terrain (§3.6).
- **T9 / B3** — real animated tree skins for `tree` obstacles; a doorway-seam
  trim so bridge/room junctions read as solid ground; a soft round **tree
  shade** cast over the characters (B3 replaced the T9 per-obstacle contact
  shadow).

Blending two room palettes into one surface is now straightforward (the bake
carries alpha) but not yet done — it would be another `decorations`-style slot
list composited in `paint_room`. Full history: `../journals/assets_journal.md`
"Terrain layering — T6–T10".
