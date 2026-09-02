# Level design — dev log

A separate log for **world / level generation** work, the same way
`enemy_ai_journal.md` tracks the AI split and `assets_journal.md` the art
passes. The general `journal.md` gets a one-paragraph pointer here once the
first milestone lands.

Milestones are prefixed **LD**. Each ends with the **full suite green**
(`python -m unittest discover -s tests -t .`) plus, where it touches rendering,
a windowed / headless-screenshot check. Determinism is A/B-checked at every
generation milestone (same seed -> byte-identical `WorldLayout`). Nothing is
committed unless the user asks.

**Status:** LD-1 **COMPLETE** (2026-08-29) — V1-V7. Multi-floor levels generate,
render with stone cliff faces + stairs, path correctly (enemies and the boss
climb stairs after the player), and `WORLD_VERTICALITY` is **on by default**.
Suite 648 -> 667. LD-2 (elevation tilesets + seamless cliffs), LD-3 (sideways
ramp stairs), LD-4 (2-tall staircase units with carved landings), LD-5
(structure-tile ownership via `Room.annex`, plank-bridge stairs, synthesized
3-sided grass) and **LD-6** (cliff-foot drop shadow + native-size cliff
rendering, retiring E7's stretch) all **COMPLETE** (2026-08-29). Suite -> 710.

---

## LD-1 — Layered verticality (multi-floor levels)

**Status:** COMPLETE (2026-08-29, V1-V7). Design + milestone plan below.
Reference: the "Tiny Swords" overworld — side-by-side grass terraces at
different heights, stone cliff faces between them, stairs/ramps connecting.

### Why

Rooms today are single-elevation rectilinear floors (`Room.cells` + corner
notches) joined by 1-tile plank bridges. The map reads flat. We want genuine
tiered terrain — plateaus a floor or two up, cliff faces marking the drop,
stairs as the only way between tiers — while keeping generation deterministic,
the collision layer simple, and **enemy pathing unchanged in spirit**.

### Core principle: one plane, `floor` is a tag

The world stays a **single (x, y) plane**. "Floors" are an integer label on
rooms, not a Z axis. Two rules make everything else fall out:

* **A cliff is a wall.** The band between a low floor and a high floor is just
  non-walkable tiles — carved out of the geometry exactly like the corner
  notches already are (`_carve_room_shapes`). A render pass skins the empty
  band with the stone cliff-face asset. ("Cliffs and height differences are
  represented as empty spaces that will be filled with the respective asset.")
* **A stair is a door.** The only walkable crossing of a cliff band is a
  1-2-tile strip, treated by every system exactly like a corridor bridge.

**Consequence — no 3-D pathfinding, no new flow-field code.** The existing 2-D
`FlowField` (Dial's-algorithm distance fill from the player, `world/pathfinding.py`)
already routes an enemy up a staircase to a player on a higher floor: the cliff
band is blocked, the stair is the sole traversable link across it, so the
gradient an enemy on floor 0 reads points it -> stair -> up -> player. Same
algorithm, same cost model.

Floors **never overlap in x, y** — side-by-side terraces, not rooms stacked on
rooms. That keeps "on a flat 2D space, levels appear the same" true and the
camera / zoom untouched.

### Decisions (locked 2026-08-29)

1. **Max 3 floors above ground is 0..3.** Floors **1 and 2 can be wide**
   (3-5-room plateaus, may nest). **Floor 3 is small** — 1-2 rooms, and
   **interior** to a floor-2 region (all its tree-neighbours are floor 2 or 3),
   which is what keeps decision 3 satisfiable.
2. **Bosses chase the player**, including up/down stairs — `Boss._approach` and
   the no-pattern fallback switch from a beeline to `ctx.nav_dir(self.pos,
   self.radius)` (the same flow field enemies use; boss radius lands in the
   `large` nav class, which already has corridor/stair leniency). Committed
   attack patterns (`charge` / dash phases) stay beeline — telegraphed, brief.
3. **Stairs go any direction** — N, S, E, W. South stairs reuse the up-stair
   sheet rotated/flipped for v1 (no dedicated art needed). Stairs are just
   corridors; placeable on any tree edge whose two rooms are in different floor
   regions. **Each stair climbs Δfloor ∈ {1, 2} — never 3.** Reaching floor 3
   is always two stairs in series (0->2 then 2->3, or 0->1 then 1->3).
   **Hard constraint:** no two tree-adjacent rooms differ by more than **2**
   floors — grow the higher regions inward so a floor-0 room is never next to a
   floor-3 room.
4. **Cliff band = 2 tiles** of walkable carve along any edge facing a lower
   floor (minus the stair columns). The **render skirt scales with Δfloor** —
   ~2 tiles of stone face per floor step, so a Δ2 drop draws a ~4-tile wall.
5. **Stair width = 1 or 2 tiles, chosen by the generator** per stair, from how
   the two rooms and the gap between them come out (a wide shared edge / big
   rooms -> 2 tiles; a tight fit -> 1). Bridges stay 1. A N-S stair is N
   **columns** wide (spanning the y gap); an E-W stair is N **rows** tall
   (spanning the x gap) — "wider corridor" on whichever axis it runs.

### Data model

```python
# world/procedural.py
@dataclass
class Room:
    ...
    floor: int = 0              # elevation index, 0 = ground

@dataclass
class Stair:                    # replaces a Corridor on a cross-floor tree edge
    low_room: int
    high_room: int
    rect: pygame.Rect          # the walkable strip
    axis: str                  # "h" | "v" — the run direction
    width_tiles: int           # 1 or 2 (decision 5)
    d_floor: int               # 1 or 2 (decision 3)
```

`WorldLayout` gains `stairs: list[Stair]`. `walkable_rects()` and
`is_connected()` include them (a stair replaces a corridor on an existing tree
edge, so `Room.neighbors` / boss-distance `_distances` are unchanged — only the
link *type* differs). `config.WORLD_VERTICALITY: bool = False` gates the whole
feature; off is byte-identical to today (same pattern as `IRREGULAR_ROOMS`,
`TERRAIN_BUILDINGS`).

The cliff band is **not** a stored object — it's the absence of `Room.cells`
along a boundary plus a render-time skirt, same as the void between rooms is
just "no cells".

### Generation (`generate_world`, after the room tree, before corridors)

**a. Floor-region flood-fill.** Floor 0 = the region containing `start` (grown
outward greedily to cover most of the tree). Then carve 1-2 floor-1 blobs
(3-5 rooms), 1-2 floor-2 blobs (adjacent to floor 1 *or* straight off floor 0
via a Δ2 stair; may nest inside a floor-1 blob), and one floor-3 pocket (1-2
rooms) seeded only on a room whose tree-neighbours are **all** already floor
>= 2. After assignment, validate every tree edge has `|Δfloor| <= 2`; re-roll or
shrink the offending blob if not.

**b. Edge -> link type.** For each tree edge:
* same floor -> `Corridor` (plank bridge), unchanged.
* different floor -> `Stair`: strip on the shared-edge midpoint, snapped to the
  tile grid, running along the edge axis; `width_tiles` picked from the overlap
  of the two room rects (>= ~4 tiles of shared edge -> 2, else 1); `d_floor` =
  the elevation difference.

**c. Cliff-band carve.** For every high room, walk its edge cells that face a
lower floor (or void). Remove a 2-tile strip of those cells from `Room.cells`
on the **low** side — they become blocked, exactly like a notch — **except**
the columns/rows a stair passes through. The high room keeps its full rect; its
low-facing edge is now "grass on top of a cliff".

**d. Cloggy pinch tuning.** Each higher region connects to the rest through
**one stair** (drop redundant same-region-pair tree edges into it). Higher-floor
rooms may roll a touch larger (open plateau) against the 1-2-tile stair throat,
so enemies from below funnel and clog — the stated goal. Stair rects join
`_corridor_doorways` keep-clear so **no obstacle ever lands on a stair**.

### Collision — near-zero change

`GameMap._point_on_floor` already returns `False` for any cell not in
`Room.cells`, so carved cliff bands are non-walkable for free. Add stairs
alongside corridors in `_point_ok` / `_point_on_floor` /
`world.pathfinding._point_on_floor`:

```python
for c in (*layout.corridors, *layout.stairs):   # both are just walkable rects
    if c.rect.collidepoint(x, y): return True
```

`resolve_movement` (wall-slide + escape hop) then works unchanged — walking off
a plateau edge slides you along the cliff; the stair is the one gap.

### Pathing — fold stairs into the corridor leniency mask

`world/pathfinding.py`:

* `_point_in_corridor` (the M3 clearance-leniency tag) -> also true inside a
  `Stair.rect`. A stair is a narrow inter-region link with the same "let the big
  rare enemies thread it" need as a bridge; the nav layer does not care that one
  is horizontal-over-water and the other a vertical climb.
* Nothing else. `FlowField.rebuild` fills from the player across every
  traversable cell; with cliff bands blocked and stair cells traversable, the
  gradient routes cross-floor. The diagonal-corner refusal already stops an
  enemy clipping the corner where a stair meets a plateau edge.
* `NavField`'s two grids (`small` 32 px / `large` 48 px) are unaffected — a
  1-2-tile stair with `corridor_lenient` behaves like a bridge, which already
  works for tank / brute.
* **Boss:** `Boss._approach` and the no-pattern fallback in `Boss.update` call
  `ctx.nav_dir(self.pos, self.radius)` instead of `player_pos - self.pos`
  (decision 2).

### Rendering — paint bottom-up, bake the skirt

`world/map.py`:

* **Draw order:** in `_draw_tiled`, blit room surfaces sorted by
  `(room.floor, y)` — all floor 0, then 1, 2, 3. Bridges with floor 0; a stair
  with its high room's floor.
* **Cliff skirt baked into the surface:** extend a high room's canvas downward
  by `d_floor * CLIFF_TILES * TILE_PX` and paint the stone cliff-face tiles
  there (the "Tiny Swords" `tilemap_1.png` already carries the grass-on-plinth
  autotile set; the rows below slot 30 are the faces). Because floor 1 is
  blitted after floor 0, the skirt overhangs the carved band.
* **Stair tiles:** a small dedicated sub-sheet (steps up-screen); S/E/W stairs
  reuse it rotated/flipped. Blitted along `Stair.rect`, same mechanism as the
  bridge end-caps.
* **Depth sort with elevation:** `scenery_drawables` and entity depth use
  ground-contact `y`. For anything on floor `n`, sort key =
  `world_y - n * CLIFF_TILES * TILE_PX`, so a hero on the plateau always paints
  in front of the cliff he stands above and the skirt tucks behind him. No
  parallax, no Z — just a sort offset.

### Milestone checklist (flag stays off until V7)

| | scope | status |
|--|--|--|
| **V1** | `Room.floor`, `Stair` dataclass, `config.WORLD_VERTICALITY` (off). `WorldLayout.stairs`, `walkable_rects` includes stairs. | **DONE** — A/B byte-identical (7 seeds), suite green |
| **V2** | Generation: floor-region flood-fill, edge->link split, `width_tiles` / `d_floor` pick, one-stair-per-region pinch. | **DONE** — see notes below |
| **V3** | Collision: `_point_ok` + `pathfinding._point_on_floor` accept stairs. | **DONE** — parity check `_point_ok` == `_point_on_floor` over 800 random samples / seed, 0 drift |
| **V4** | Nav: stairs into the `_point_in_corridor` leniency test. Boss `nav_dir` switch. | **DONE** — flow field from `start` reaches >60% of every raised room's cells over 80 seeds; `Boss._seek` = nav field, straight-line fallback |
| **V5** | Render: bottom-up floor paint, baked cliff skirts (scaled by `min(floor,2)*CLIFF_TILES`), stair strips, `slots.cliff` tile block. | **DONE** — `CLIFF_CARVE` left off (skirt hangs off the rect edge into the void, no walkable inset needed). Depth-sort offset skipped — with no parallax, naive y-sort is already right (a sprite at a cliff base is nearer the camera -> in front). |
| **V6** | Subtree-grown floor regions -> one boundary edge -> a clean 1-stair pinch; floor-3 = a leaf of the floor-2 tail; obstacles already skip stair rects. | **DONE** — stairs/region mean 1.68 (was 2.0); floor 3 in ~36% of seeds, always 1 room; raised regions 1-6 rooms. |
| **V7** | `WORLD_VERTICALITY` **on by default**. Full suite green; headless playtest. | **DONE** — 667 green (3 pinned-seed base-nav / base-obstacle modules pin the flag off via `setUpModule`; verticality has its own coverage). Playtest: hero on floor 2, a chaser pack on floor 0 -> up to 12 climb two stair levels to reach him within 20 s. |

### V1-V4 as built (2026-08-29)

**Files:** `game/config.py` (`WORLD_VERTICALITY`, `CLIFF_TILES`, `CLIFF_CARVE`
— all off), `world/procedural.py` (`Room.floor`, `Stair`, `WorldLayout.stairs`,
`_assign_floors` / `_grow_blob` / `_split_links` / `_carve_cliffs`, gated block
in `generate_world`, `_scatter_obstacles(..., stairs=)`), `world/map.py`
(`_point_ok` iterates stairs), `world/pathfinding.py` (`_point_on_floor` +
`_point_in_corridor` accept stairs), `entities/boss.py` (`_seek` helper; the
no-pattern fallback and `_approach` steer by it),
`tests/world/test_verticality.py` (18 cases). Suite 648 -> 666.

**`_assign_floors`** — `_grow_blob` (deterministic BFS) floods 1-2 raised
plateaus (`_VERT_REGION_ROOMS` 3-6 rooms) onto the room tree; a plateau escalates
an inner sub-blob to floor 2 (`_VERT_F2_CHANCE`), and a floor-2 area may sprout a
**single** floor-3 room, seeded only where every tree-neighbour is already >= 2.
`start` pinned to 0. A final monotone settle pass drops any tree edge back to a
`<= 2` floor gap. Observed: floors 0-3 all appear across seeds, floor 3 is always
0-1 rooms and interior, no neighbour pair exceeds 2.

**`_split_links`** — every corridor whose two rooms differ in `floor` becomes a
`Stair`; same-floor corridors are untouched, so `Room.neighbors` /
`is_connected` / boss-distance are unchanged (link *type* differs, not the
graph). Width is **2 tiles** only for a gentle 1-floor step between two roomy
rooms with a >= 6-tile shared edge, else **1** — across 40 seeds ~17% come out
wide, the rest narrow. The stair rect spans **room centre to room centre** (not
mouth-to-mouth): its clearance-lenient cells then punch past any tight
room-edge neck so the flow field can always route through it (a mouth-to-mouth
rect left ~10% of seeds with a raised room the small nav class could not enter).

**`_carve_cliffs`** — written but **gated behind `CLIFF_CARVE` (still off after
V5)**. Insetting a raised room's walkable mask repeatedly choked the flow field
through smaller rooms. It turned out not to be needed: the render skirt hangs
*off* the room's rect edge into the void (like a bridge over water), so the full
walkable mask stays and pathing stays correct — a plateau rim borders void, the
stair is the only cross-floor link.

### V5-V7 as built (2026-08-29)

**V5 render** (`world/map.py`, `data/terrain.json`): `slots.cliff`
(`top` / `body` / `bottom`, four column variants each, from `tilemap_1.png`
cols 5-8 rows 3-5). `_build_tiles` bakes, per raised room, a **south-facing
cliff-face skirt** surface `min(floor, 2) * CLIFF_TILES` tiles tall (drop shown
capped at two floors), spanning only the columns with a real bottom-row floor
cell, blitted from `room.bottom - px` down into the void. Stairs bake a plain
grass strip (a dedicated step sheet is later polish). `_draw_tiled` now paints
**floor-ascending**: for each floor level, its rooms' skirts (onto the floor
below), then the room surfaces, then that floor's stairs; corridors last
(doorway-foam cover). Depth-sort offset was **not** added — with no parallax
the naive ground-contact-`y` sort is already correct (a sprite at a cliff base
is nearer the camera, so it should draw in front, which it does).

**V6 region shaping** (`world/procedural.py`): `_assign_floors` rewritten around
`_rooted_tree` + `_grow_subtree` — a raised region is now always a **subtree**,
so its only edge to lower ground is the seed's parent edge = **one stair**
(mean stairs/region 2.0 -> 1.68). The floor-2 area is the deep tail of that
subtree; floor 3 is a single **leaf** of the floor-2 tail whose parent is also
floor 2. Observed over 80 seeds: floors 0-3 all appear, floor 3 in ~36% (always
1 room), regions 1-6 rooms, every neighbour pair within 2, all connected,
>= 72% of every raised room's cells fill-reached.

**V7** (`game/config.py`): `WORLD_VERTICALITY = True` by default. Fallout: three
pinned-seed modules that validate the *base* generator on fixed seeds
(`tests/ai/test_pathfinding.py`, `tests/world/test_obstacles.py`) pin the flag
off in `setUpModule` — verticality changes the RNG stream and has its own
coverage in `test_verticality.py` (which also pins the pre-LD-1 flat-world
hashes so that path can never silently drift). Headless playtest (seed 5, hero
on floor 2, a 10-chaser pack spawned on floor 0): up to **12 enemies climb two
stair levels** onto the hero's plateau within 20 s. Suite **648 -> 667**.

**Boss** — `Boss._seek(ctx)` returns `ctx.nav_dir(pos, radius).normalize()` when
non-zero, else the straight line to the player (mirrors `SeekTarget` /
`entities/ai/components/seek.py`). The no-pattern movement fallback and
`_approach` both use it; committed `charge` / dash phases still beeline. On a
flat world the gradient ~= the old beeline, so no behaviour change there; on a
vertical world the boss now climbs stairs after the player (decision 2).

### Touch list (as built, V1-V7)

* **New:** `journals/level_design_journal.md`, `tests/world/test_verticality.py`
  (24 cases).
* **`game/config.py`** — `WORLD_VERTICALITY` (True), `CLIFF_TILES` (2),
  `CLIFF_CARVE` (False).
* **`world/procedural.py`** — `Room.floor`, `Stair`, `WorldLayout.stairs`,
  `_rooted_tree` / `_grow_subtree` / `_assign_floors` / `_split_links` /
  `_carve_cliffs` (gated, off), gated block in `generate_world`,
  `_scatter_obstacles(..., stairs=)` keep-clear.
* **`world/map.py`** — `_point_ok` iterates stairs; `_cliff_surfs` / `_stair_surfs`,
  `paint_cliff` / `paint_stair` in `_build_tiles`; floor-ascending paint in
  `_draw_tiled`.
* **`world/pathfinding.py`** — `_point_on_floor` + `_point_in_corridor` accept
  stairs.
* **`entities/boss.py`** — `_seek` helper; `_approach` + the no-pattern fallback
  steer by it.
* **`data/terrain.json`** — `slots.cliff` tile block.
* **Tests** — `tests/ai/test_pathfinding.py` + `tests/world/test_obstacles.py`
  pin the flag off (`setUpModule`); `tests/rendering/test_terrain.py` slot
  walker handles the nested `cliff` dict.
* **No** new dependencies. **Nothing** committed.

### Later polish (not blocking)

* Stair strips render as plain grass — a dedicated "steps" sub-sheet (rotated
  for S/E/W) would sell the climb.
* Same-floor corridors between two raised plateaus still draw as a plank bridge
  over water ("sky bridge") — fine, but a stone causeway would read better.
* `CLIFF_CARVE` + an inset cliff face, if the flow-field choke can be avoided
  (carve only rooms with a comfortable core, or widen the small nav class near
  raised rims).
* N/E/W cliff faces (only S is skirted today).

---

## LD-2 — Elevation tilesets & seamless cliffs

**Status:** **LD-2 COMPLETE** (2026-08-29, E0-E10). Per-tile meta layer at
generation + elevation grass sheets + seamless granular cliff faces (no flat
backfill) + foam-free plateaus / sky bridges + E8 foamy vs. grounded cliff feet
by what sits below (E8a: judged across the column's full width, not one centre
pixel) + **E10: raised rooms autotile against the sheet's real non-foam
16-tile block (`slots.raised`), selected straight from `TileMeta`** -- which
retired E6's `top`-tile crop and E9's rotated fringe bands.
Suite 667 -> 685. Checklist below. LD-1 shipped
verticality with a single ground tileset, per-**room** floor only, and a coarse
4-tile cliff strip; the screenshots show visible cracks in a multi-tile face and
every floor is the same grass. LD-2 adds a **per-tile meta layer at generation**
(E0 -- required by later systems, not just the renderer) and makes the tile
layer elevation-aware on top of it (E1-E5).

### What we have

* `data/terrain.json`: one `floor_sheet` (`tilemap_1.png`) + `room_palettes`
  keyed by `room.kind`. `slots` is a flat name -> index map; `slots.cliff` is
  `{top, body, bottom}` each a 4-entry `[left, mid, mid, right]` list.
* `world/map.py` `_build_tiles`: `paint_room` picks the sheet from
  `room_palettes.get(r.kind, floor_sheet)`. `paint_cliff` /
  `paint_corridor` / `paint_stair` all pull from `floor_sheet`. Every plank
  cell and every room-edge cell is registered in `self._shore`, which drives
  the animated foam.

### Findings (assets already support this)

* **`tilemap_1..5.png` are all 576x384, identical 9x6 slot layout** — only the
  grass palette differs (interior tile: t1 yellow-green `(151,181,83)`, t2
  `(131,173,87)`, t3 greener `(96,169,99)`, t4 olive `(129,152,94)`, t5 teal
  `(86,152,139)`). The **cliff-face region is byte-for-byte the same grey stone
  in all five**. So "a different tileset per floor" = swap the grass sheet;
  the cliff stays one stone.
* **The cliff region is a 4-variant x 3-row autotile** (top 32-35 / body 41-44 /
  bottom 50-53): col 5 = **left end** (open left edge, solid right), col 6 =
  **mid** (solid both), col 7 = **right end** (solid left, open right), col 8 =
  **single** (open both). LD-1's crack bug: it used `[left, mid, mid, right]`
  and dropped `right` (43 = an open-right-edge tile) into the middle of a run
  -> the gap on its right is the visible crack.
* **The `top` row (32-35) is a grass->stone *merge* tile** -- its top ~70% is
  grass (matching the plateau), its bottom ~30% is stone, so it must sit **at
  the plateau's south edge cell row** (replacing that cell's grass tile) with
  its stone base aligned to the `body` tops; the `body` rows are pure stone,
  the `bottom` rows are stone with a lit ground-contact rim. So a face is
  `top` (at the edge) + N x `body` + `bottom` (below, in the void), and the
  per-column variant must be the **same** top->body->bottom so the vertical
  stone seam lines up.
* The `body` / `bottom` tiles are ~4-5 px shy of opaque on each side (the dark
  cracks are real transparency), so two neighbours leave a hairline seam. Fix:
  a solid stone backfill on the skirt surface before blitting, or a 1-2 px
  column overlap.
* `bridge_all.png` is 192x256 = a 3x4 grid of 64 px tiles; the same 6 slots
  serve any floor.
* A small 1-wide x 2-tall standalone cliff nub also exists (idx 36/39 tops,
  45/48 bodies) -- an optional dedicated "tiny mesa" look for a lone raised
  tile.
* **Checked (2026-08-29): the raised sheets carry the *same white foam
  shoreline* as the ground sheet.** `tilemap_1..5` differ *only* in the flat
  grass tiles (interior + strips are fully recoloured); their autotile
  **edge / corner tiles are the same shoreline art** in every sheet -- the
  ~65-250 near-white foam pixels per edge tile are pixel-identical across all
  five. So there is **no foam-free / cliff-edge variant** of the grass
  autotile. A plateau must therefore be drawn with **no autotiled shoreline at
  all** -- interior grass clipped to the mask, a cliff face on the south edge
  (LD-1 skirt + E2), and a thin cliff *lip* on N/E/W (no ready tile -> a
  programmatic darkened overhang strip, or a rotated crop of the cliff `top`
  row). And **no `self._shore` entry for any raised-room cell**, so foam never
  appears around a plateau. LD-1 currently *does* register raised-room edges in
  `_shore` -> foam draws around plateaus today; E1/E3 fixes that.

### E0 — Tile-meta layer (do first; E1-E5 read from it)

Generation today records elevation only per **room** (`Room.floor`,
`WorldLayout.stairs`). Every per-**tile** fact (is this an edge cell? does it
start a cliff? should it foam?) is re-derived inside the renderer and thrown
away. E0 makes that a first-class, deterministic output of `generate_world` so
the renderer, and any later system (decoration sets per floor, elevation tint /
lighting, footstep audio, minimap, fall / drop gameplay), share one source of
truth.

**Shape** -- `world/procedural.py`:

```python
class TileMeta(NamedTuple):     # stdlib typing.NamedTuple -- pure, no pygame
    floor: int                  # 0..3
    surface: str                # "room" | "corridor" | "stair"
    foam: bool                  # register this cell in _shore (ground shoreline)
    cliff: str                  # "" | "top"  -- plateau south-edge cell that starts a face
    cliff_var: str              # "" | "left" | "mid" | "right" | "single"
    lip: str                    # "" | "n" | "e" | "w"  -- raised non-south rim
    room_id: int                # -1 for a corridor / stair cell
```

* `Room.tile_meta: dict[(col, row), TileMeta]` -- **room-relative** keys, one
  per `Room.cells` entry (room rects are tile-*sized* but not world-tile-
  *aligned*, so a global world grid would not line up -- mirror `Room.cells`).
* Corridors / stairs: their cells resolve on the fly in the accessor (they are
  uniform -- `surface` set, `foam = not raised`, `floor` from the low / high
  room).
* `WorldLayout.tile_at(wx, wy) -> TileMeta | None` -- same room-then-corridor-
  then-stair walk as `_point_ok` / `room_at`.
* `_build_tile_meta(rooms, corridors, stairs)` runs **at the end of
  `generate_world`** (post-shift, post-carve) -- reads only finalized geometry,
  **draws no RNG**, so flag-off stays byte-identical. Built always (a flat
  world gets `floor 0 / foam True / cliff "" ` everywhere -- a uniform API).
* The **cliff `cliff_var` picker** (`left/mid/right/single` from the south-edge
  neighbours in `Room.cells`) lives here, pure; E2's `paint_cliff` just reads
  `meta.cliff_var`. The base grass autotile `slot` stays derived in the
  renderer's `_mask_slot` for now -- promote it into `TileMeta` only when a
  second consumer needs it.

**Tests** -- every `Room.cells` entry has a `TileMeta`; `tile_at(centre)`
`.floor == room_at(centre).floor`; flag-off -> all `floor 0 / foam True /
cliff ""`; deterministic (same seed -> same `tile_meta`); a raised room's south
rim -> `cliff == "top"` with a contiguous `left..right` (or `single`) run and
`foam == False`; a raised bridge plank -> `foam == False`.

### Milestones

| | scope | done when |
|--|--|--|
| **E0** | **Tile-meta layer** (above): `TileMeta`, `Room.tile_meta`, `_build_tile_meta`, `WorldLayout.tile_at`, cliff-variant picker moved to gen. | suite green; flag-off byte-identical (no RNG draw); determinism A/B; the E0 tests above |
| **E1** | **Per-floor ground sheet + foam-free plateau edges.** `terrain.json` gains `floor_sheets: {"1": "...tilemap_2.png", "2": "...tilemap_3.png", "3": "...tilemap_5.png"}` (shared slot layout). `paint_room` reads **`meta.floor`** for the sheet (`floor > 0` -> `floor_sheets`, else `room_palettes` / `kind`) and **`meta.foam`** for whether to add the cell to `self._shore` -- so raised rooms drop the shoreline autotile (interior grass clipped) and never foam. `paint_stair` uses the **high room's** floor sheet. | headless 3-tier shot: each floor a visibly different grass tone; **zero white foam anywhere touching a plateau**; `test_verticality` asserts a floor-2 room's baked surface samples the floor-2 palette and registers no shore cells |
| **E2** | **Granular cliff autotile + N/E/W lip.** `slots.cliff` -> `{top,body,bottom}` each `{left, mid, right, single}` (32-35 / 41-44 / 50-53). `paint_cliff` reads **`meta.cliff` / `meta.cliff_var`** (picked in E0) -- no neighbour re-derivation. The **same variant runs top->body->bottom** so the vertical stone seam aligns; the `top` tile sits **at the edge cell row itself** (grass->stone merge from `sheet_for(floor)`), `body` x `(min(floor,2)*CLIFF_TILES - 1)` + `bottom` hang below into the void, on a **solid stone-filled** skirt surface (or 1-2 px column overlap) so no hairline shows. **N/E/W lip:** `paint_room` draws a `CLIFF_TILES`-fraction-tall darkened overhang strip on any cell with `meta.lip` set (rotated crop of `top`, or a programmatic gradient). | headless zoom-in: a >=3-wide face has **zero** interior gaps or vertical seams; grass->stone merge clean at the edge row; a lone south-edge tile draws `single`; a stepped / L plateau's face follows its real edge; N/E/W rims show a lip, not foam |
| **E3** | **Raised bridges & no foam.** `paint_corridor` reads **`meta.foam`** for each plank cell -- a `floor > 0` corridor keeps the **same bridge tiles** but registers no shore -> no foam beneath (spans a cliff gap, not the ocean). Floor-0 bridges unchanged. (Raised-room-edge foam is already gone via E1.) | headless: a same-floor raised "sky bridge" renders with no foam; a ground bridge still foams; `_shore` count for a flat world is unchanged (regression) |
| **E4** | **Sheet / slot resolver + tests.** `terrain.json` load normalises `floor_sheets` (str keys -> int) and `slots.cliff` (nested dict); `GameMap._sheet_for(floor, kind)` / `_cliff_idx(row, edge)` helpers so `_build_tiles` stays readable. `tests/rendering/test_terrain.py` slot walker (already recurses dicts) -- require all 12 `cliff` indices in range + the 3 x 4 shape. | full suite green; determinism A/B (flag on) unchanged; flat-world baseline hashes unchanged |
| **E5** | **Playtest + screenshot.** Windowed / headless 3-tier run: distinct grass per floor, a seamless multi-tile cliff, a raised bridge with no foam, a `single` overlook tile. Tune the floor->sheet mapping (t2/t3/t5 vs t2/t4/t5) for the clearest read. | screenshots; feels tiered and clean |

### Decisions to confirm

1. **Floor -> sheet mapping.** Proposed floor 1 -> `tilemap_2` (subtle), floor 2
   -> `tilemap_3` (clearly greener), floor 3 -> `tilemap_5` (teal, "sky
   island"). Or keep it monotone (2/3/4)?
2. **Cliff stone stays one grey for all floors** (it's identical in every
   sheet) -- OK, or do you want a darkening tint per floor for depth?
3. **The `single` cliff tile** is the col-8 variant (open both sides). Use the
   dedicated 1x2 "tiny mesa" nub (idx 36/45) instead for a lone *raised tile*
   (as opposed to a lone *column of a bigger room's edge*)? Or col-8 for both?
4. **Stair grass** = the high room's floor sheet (raised look). Agree, or keep
   stairs on the ground sheet so the climb reads as "going up from here"?
5. **N/E/W plateau lip** (no ready asset): a programmatic darkened overhang
   strip (fast, "good enough") vs. cropping/rotating the cliff `top` tiles
   (nicer, more work) -- which for v1?

### Checklist

#### E0 - Tile-meta layer -- DONE (2026-08-29)
- [x] `world/procedural.py`: `TileMeta(NamedTuple)` -- `floor, surface, foam,
      cliff, cliff_var, lip, room_id` (stdlib `typing`, no pygame).
- [x] `Room.tile_meta: dict[(col,row), TileMeta]` field, one entry per
      `Room.cells`.
- [x] `_is_south_rim(cells, col, row)` + `_cliff_variant(cells, col, row)` pure
      helpers -> `left` / `mid` / `right` / `single` from the same-row rim
      neighbours (handles multiple runs per row on an L / stepped edge).
- [x] `_build_tile_meta(rooms)` -- per room cell: `floor`, `surface="room"`,
      `room_id`, `foam = floor == 0`; a raised room's south-rim cell ->
      `cliff="top"` + `cliff_var`; every raised non-south exposed side ->
      `lip` (a subset of `"new"`). Called at the **end** of `generate_world`
      (post-shift, post-obstacle), **no RNG**, unconditional.
- [x] `WorldLayout.tile_at(wx, wy)` -- room walk (room-relative key) then a
      synthesised `TileMeta` for a corridor (`floor` from `room(c.a)`,
      `foam = floor==0`) or stair (`floor` from the high room, `foam=False`);
      `None` in the void.
- [x] `tests/world/test_verticality.py::TileMetaTests` (5): every cell has a
      meta with the right `room_id`/`surface`/`floor`; `tile_at(centre).floor`
      matches, a stair centre -> `surface=="stair"`, deep void -> `None`;
      deterministic; a raised south rim is a seamless `left..right` (or
      `single`) run with `foam=False` on every raised cell; flag-off -> all
      `(0, True, "", "", "")`.
- [x] Flag-off `_layout_sig` baseline hashes unchanged; suite 667 -> 672.

#### E1 - Per-floor ground sheet + foam-free edges -- DONE (2026-08-29)
- [x] `data/terrain.json`: `floor_sheets` -- `1 -> tilemap_2`, `2 -> tilemap_3`,
      `3 -> tilemap_5` (decision 1, recommended default; can retune in E5).
- [x] `world/map.py` `_build_tiles`: `floor_sheets = {int(k): v ...}` (JSON
      string keys) + a `sheet_for(floor, kind)` closure -- elevation sheet for
      `floor > 0`, else `room_palettes.get(kind, floor_sheet)`.
- [x] `paint_room`: `sheet = sheet_for(r.floor, r.kind)`; a **raised room paints
      plain `interior` grass** (the autotile edge/corner tiles bake in the
      white foam shoreline -- ground-level only); `_shore` is seeded per cell
      **only when `tile_meta.foam`**, so plateaus never foam.
- [x] `paint_stair`: `sheet_for(high_room.floor)` grass (raised look --
      decision 4).
- [x] `tests/world/test_verticality.py::ElevationSheetTests` (3): a raised
      room's baked grass tone is closer to its own `floor_sheets` sheet than to
      `tilemap_1`; **no `_shore` point lands inside a `floor > 0` room** over 20
      seeds; ground rooms still seed the shore.
- Suite 672 -> 675. Screenshot: raised rooms show clean elevation grass with a
      hard edge (E2 lip pending), zero white foam; ground rooms unchanged. The
      N/E/W edges are a hard cut until E2.

#### E2 - Granular cliff autotile + N/E/W lip -- DONE (2026-08-29)
- [x] `data/terrain.json`: `slots.cliff` -> `{top,body,bottom}` each nested
      `{left, mid, right, single}` (32-35 / 41-44 / 50-53).
- [x] `world/map.py`: `cliff_idx(row, edge)` closure; `_CLIFF_STONE`,
      `_LIP_FRAC`, `_LIP_MULT` module constants.
- [x] `paint_cliff` rewritten off `Room.tile_meta` -- per south-rim cell
      `(col, row, cliff_var)`: pour a **solid `_CLIFF_STONE` column** first
      (seam plug), then the `top` merge tile at that cell row + `body` x
      `(face_h - 1)` + `bottom` below, **all in the cell's one `cliff_var`**,
      from `sheet_for(r.floor)`. Skirt surface now spans the room's full height
      + `face_h` tiles, blitted at `r.rect.topleft`.
- [x] `_draw_tiled` floor pass reordered: **rooms first, then that floor's
      cliff faces** -- so the `top` tile's grass->stone merge actually sits over
      the room's edge grass (before it was covered by the room and never seen).
- [x] `paint_room`: on a `meta.lip` cell, a `_LIP_FRAC` (0.34) band on each
      exposed n/e/w side via `fill(..., BLEND_RGBA_MULT)` -> a shadowed
      overhang, not a hard cut (decision 5: programmatic).
- [x] `tests/rendering/test_terrain.py`: `slots.cliff` is a full
      `{top,body,bottom} x {left,mid,right,single}`; `floor_sheets` values are
      real files. `tests/world/test_verticality.py`: a cliff-face body scanline
      has **no transparent seam** between its opaque extremes (over 20 seeds); a
      raised room's `meta.lip` cell rim pixel is darker than a plain interior
      cell.
- Suite 675 -> 679. Screenshots: seamless multi-tile stone face, visible
      grass->stone merge, subtle N/E/W lip (could go stronger -- E5 tune), a
      floor-3 room on `tilemap_5` teal grass. A faint horizontal line remains
      between the `body` and `bottom` tile rows -- that is the tile art's own
      edge, not a gap.

#### E3 - Raised bridges, no foam -- DONE (2026-08-29)
- [x] `paint_corridor`: `raised = layout.room(c.a).floor > 0` (a `Corridor` is
      always same-floor -- cross-floor links are `Stair`s); when raised, keep
      the bridge tiles but **skip the `self._shore.append`** for its planks
      (matches `tile_meta.foam == floor == 0`).
- [x] `tests/world/test_verticality.py`: no `_shore` point lands inside a
      raised corridor's blit rect over 25 seeds; a ground bridge still foams.
- [x] `tests/rendering/test_terrain.py` pins `WORLD_VERTICALITY` off in
      `setUpModule` (its pinned-seed foam-order / decoration checks assume the
      flat layout; LD-2's render has its own coverage). Suite 679 -> 680.

#### E4 - Resolver polish + terrain tests -- DONE (2026-08-29)
- [x] Every cliff / floor / bridge-fallback sheet lookup in `_build_tiles` goes
      through the `sheet_for(floor, kind)` / `cliff_idx(row, edge)` closures --
      no inline tile-index literals remain (only `a.tile(water_tile, 0)`, a
      single-tile sheet). `paint_corridor`'s non-bridge fallback now uses the
      corridor's own elevation sheet.
- [x] `tests/rendering/test_terrain.py` (added in E2): `slots.cliff` is a full
      `{top,body,bottom} x {left,mid,right,single}` with indices in range;
      `floor_sheets` values are real files.
- [x] Flag-off baseline hashes unchanged; flag-on layout **and** `tile_meta`
      A/B identical over 20 seeds; suite 680.

#### E5 - Playtest + tune + screenshots -- DONE (2026-08-29)
- [x] Headless renders: 3 grass tones (t1 ground / t2-t3-t5 raised), seamless
      multi-tile cliff faces (no cracks), grass->stone merge at every rim,
      same-floor "sky bridges" between plateaus with **no foam**, stairs cutting
      through cliffs.
- [x] Kept `floor_sheets` = `t2 / t3 / t5` (decision 1 default -- reads clearly:
      subtle -> greener -> teal "sky island").
- [x] Tuned the N/E/W lip: `_LIP_MULT` `(140,152,140)` -> `(112,126,112)` --
      the first pass was too faint to read; now the rim reads as a shadowed
      overhang. `_LIP_FRAC` kept at 0.34.
- [x] Screenshots sent; journal updated below.

#### E6 - Crop the cliff `top` merge tile to its strand band -- DONE (2026-08-29)
- Finding: the `top` tiles (32-35) are ~70% a **full grass field** with a dark
  clumpy fringe at *both* edges and only a ~14-24 px "strands meet the drop"
  band at the bottom. Blitting the whole tile at the south-rim cell row dropped
  a differently-textured grass row with a visible seam line one tile inside the
  plateau (user report: "the cliff tile also has the ground tile attached to
  it").
- [x] `_CLIFF_TOP_KEEP = 24` (world/map.py). `paint_cliff` blits **only the
      bottom `keep` px** of the `top` tile
      (`area=Rect(0, px - keep, px, keep)`), landing it at
      `(row + 1) * px - keep` so the strand band sits at the cell's south edge;
      the room's own `interior` grass (painted first) fills the rest of the
      cell -> the plateau grass is now uniform right up to the rim. Seam-plug
      fill extended up 8 px so nothing hairlines between the band and the first
      `body` row.
- [x] `tests/world/test_verticality.py`: the cliff surface is **transparent**
      above the strand band (`alpha <= 8` at `(row+1)*px - keep - 8`), i.e. the
      room grass shows through. Suite 680 -> 681.
- Screenshot: the grass field is continuous, only the edge strands + stone
  face show at the rim -- mixes with the general ground tiles.

#### E7 - Kill the frontier line + the squared stone margin -- DONE (2026-08-29)
- User report (on the E6 result): "there's a line that clearly denotes the
  frontier between the two tiles and makes it look jarring, and cliffs have a
  squared margin as well. Remove the line and clean the cliff tiles so there's
  transparency for the darker outside sections."
- Root cause was the E2 **seam plug**: `paint_cliff` poured an opaque
  `_CLIFF_STONE` rect (`px` wide, per column, starting 8 px *above* the tile
  row) behind every cliff column. That rect had (a) a hard top edge = the
  horizontal "frontier line" against the plateau grass, (b) hard square corners
  poking past the rounded `left`/`right`/`single` run ends = the "squared
  margin", (c) it backed the tiles' dark void-facing outline pixels with solid
  teal instead of leaving them transparent.
- [x] `_CLIFF_STONE` **deleted**. New constants `_CLIFF_SEAM_OV = 8`,
      `_CLIFF_TOP_FEATHER = 10` (world/map.py).
- [x] `paint_cliff` rewritten (no backfill rect):
  * every face tile is **widened** to `px + 2*ov` (`pygame.transform.scale`)
    and blitted at `col*px - ov`, so neighbouring columns' *solid cores*
    overlap by `2*ov` and close the inter-column hairline -- while the run's
    void-facing outer edges stay transparent (the underlay uses the column's
    **own** `left`/`right`/`single` variant, never a solid `mid`).
  * each column is backed by its own `body` variant **tiled at a half-tile
    vertical stagger** (`px//2`), from just under the feather down to the last
    body row, so the transparent gap between stacked face tiles never shows the
    void through (this was the E6 "deferred" faint body/bottom line -- now
    fixed, not deferred).
  * the kept strand band is composited on a small `cap` surface (body stone
    underlay + `top` tile) and its top `_CLIFF_TOP_FEATHER` px are multiplied
    by a `0 -> 255` alpha ramp, so it **dissolves into the plateau grass** with
    no hard edge.
- [x] `tests/world/test_verticality.py`:
      `test_strand_band_top_feathers_into_the_plateau` (alpha <= 60 at the band
      top, > 180 a few px below); `test_cliff_face_bakes_with_no_transparent_seam`
      comment updated to the widen-and-overlap mechanism (assertion unchanged --
      still green). Suite 681 -> 682.
- Screenshots (`e7_cliff_*.png`): grass melts into the strand fringe with no
  line; the stone face follows the tile silhouette (rounded run ends, scalloped
  base) with the void showing past every outer edge; no teal between rows.

#### E8 - Foam vs. non-foam cliff foot by what sits below -- DONE (2026-08-29)
- User request: "switch between the foam cliff or the non foam one depending if
  there's a tile adjacent vertically to it ... if there's a tile use the non
  foam version, if there's empty space use the foam one and add the foam effect
  as well."
- Finding: the tileset already carries both feet -- `bottom` (50-53) is the
  stone face with a **pale scalloped shoreline** baked in; `body` (41-44) is the
  plain repeat with a flat foot. No new art.
- [x] `paint_cliff` now walks each rim column down with `layout.tile_at`
      (`ground_k`, steps `1..face_h+1`):
  * **void the whole way** -> full `face_h` face, foot = the foamy `bottom`
    tile, and -- unless the foot hangs over a bridge / stair span -- a
    `_cliff_foam` point so the animated `terrain_foam` frames lap against it.
  * **hits a tile** (lower room / corridor / stair) at step `k` -> the face is
    cut to `min(face_h, k-1)` rows and capped with a plain `body` tile (no foam
    art, no foam point) so the stone reads as sunk into the ground; `k == 1`
    (a flush neighbour / a stair mouth) -> only the strand band, no face.
- [x] New list `GameMap._cliff_foam` (world/map.py `__init__`), drawn in the
      same foam pass as `_shore` (`self._shore + self._cliff_foam`). Kept **out
      of `_shore`** so the E1 "no shoreline inside a plateau" invariant and the
      T9 doorway-seam filter are untouched; a foot in a plateau-bbox *bite*
      (visually open water) is free to foam.
- [x] `tests/world/test_verticality.py`:
      `test_cliff_foot_foams_over_void_and_grounds_over_a_tile` (void feet in
      `_cliff_foam`, grounded / sky-gap feet not);
      `test_cliff_face_bakes_with_no_transparent_seam` now only samples column
      pairs that both drop a full void face (E8 legitimately shortens the rest).
      Suite 682 -> 683.
- Screenshots: `e8_grounded2.png` -- a floor-1 rim dropping 2 tiles onto a
  ground room, plain `body` foot flush on the lower grass, a stair gap where the
  connection is, one lone column past the shore still foaming; `e8_void.png` --
  a floor-2 rim over open water, scalloped `bottom` foot with foam lapping.

#### E8a - `ground_k` must sample the column's full width -- DONE (2026-08-29)
- User report, on the E8 result: "why there's that empty space between the left
  most cliffs and the grass stairs" -- a strip of void hanging under a rim
  column that should have had a stone face.
- **Root cause (an E8 regression, same session).** `ground_k` probed a single
  pixel, the column's horizontal centre. Corridor and stair rects are
  tile-*sized* but **not aligned to any room's column grid** -- a room's
  columns fall on `room.rect.x + n*px`, while a corridor rect is centred on the
  room centre-line and can land on a half-tile offset. Worked example, seed 2
  room 12 (floor 2, a 2x2 corner bite so it has two rims -- the bite rim at
  cols 0-1 row 3 and the real south rim at cols 2-5 row 5): the vertical bridge
  to room 13 has rect `(1240, 808, 64, 400)`, and rim col 2 spans world x
  1208-1272 with its centre at exactly **1240** -- the bridge's left edge,
  which `collidepoint` includes. So `gk = 1`, `draw_h = min(4, 0) = 0`, and the
  **whole column's face was dropped** -- but the bridge only covers the
  column's right half, leaving 32 px of open void beside the leftmost cliffs.
- Sweep over 60 seeds: 2232 rim columns, **191 (8.6%) partially covered**, and
  **98 (4.4%) where the single-centre probe gave the wrong verdict**, across 48
  of 60 seeds. Mostly hidden behind the plank, but not always.
- [x] `ground_k` now samples **three x positions** -- left edge + 2, centre,
      right edge - 3 -- and returns `k` only where **all** of them hit a tile.
      A partially covered column therefore keeps its full face. That costs
      nothing visually: corridors and stairs are painted *after* the cliff
      pass, so the covered part is drawn over anyway.
- [x] `tests/world/test_verticality.py`:
      `test_a_partly_covered_rim_column_keeps_its_full_face` -- for every rim
      column where the full-width and any-probe verdicts differ, the cliff
      surface must be opaque (alpha > 100) at the *uncovered* probe's x on that
      row. Asserts such columns actually occur in the sample, so the test
      cannot pass vacuously. `test_cliff_foot_foams_over_void_and_grounds_over_a_tile`
      updated to the same full-width rule. Suite 683 -> 684.
- Lesson for later elevation work: **never classify a tile-grid cell from one
  sample point** when the thing being sampled (corridor / stair rects) lives on
  a different alignment.

#### E9 - Cliff-grass fringe on the N/E/W rim too -- DONE (2026-08-29)
- User request: "Remember the cliff ground tiles, the ones above the cliff that
  have the grass strands on the south side. Also for the other directions so
  the raised floor doesn't have the edge tiles with the foam."
- Asset survey (tilemap_*.png, measured): the `top` tiles 32-35 carry a dark
  clumpy grass fringe on **every closed side**, not just the strand band at the
  bottom -- north ~6-8 px on all four variants, west ~13 px on `left`, east
  ~13 px on `right`, all round on `single`. There is **no** dedicated N/E/W
  grass-edge tile; 36/39 are diagonals and 45/48 are cliff inner corners.
- [x] `_LIP_BAND_N = 16`, `_LIP_BAND_EW = 22`, `_LIP_FEATHER = 7`
      (world/map.py). `cliff_slots` / `cliff_idx` moved above `paint_room` so
      it can cut from the cliff set.
- [x] `paint_room`, on a `meta.lip` cell: crop the `top` tile's fringe to that
      side and blit it at the cell's edge, inner `_LIP_FEATHER` px ramped to
      alpha 0 so it melts into the interior grass (same trick as E7's strand
      band). A plateau is now bordered by cliff grass on all four sides.
- [x] **User correction, mid-implementation:** "the top left tiles ... only
      cover horizontal lines so if they are placed as they look the grass
      strands in the other sides, non south, will clash with the inland tiles."
      Correct -- `slots.cliff` autotiles a *horizontal* run only, so
      `left`/`right` are that run's **end caps**. The first pass cut the west
      band from `left` and the east band from `right`, which stacks an end-cap
      motif down a column and breaks at every tile boundary. Fixed: every band
      is now cut from **`mid`** alone -- the only variant drawn to continue
      into its neighbours -- with the vertical sides being that same north
      fringe **rotated** a quarter turn (`rotate(+90)` west, `rotate(-90)`
      east). Seamless down a run, and consistent with the north.
      `lip_variant()` deleted.
- [x] The `top` tiles' outer edges are ragged (tile 33 row 0 is opaque on only
      15 of 64 px). Composited straight onto the interior tile those gaps fill
      with bright grass and the fringe reads as a thin bright rim, so
      `paint_room` **clears** the band's outer `band - feather` px first and
      lets the art's own silhouette stand against the void. All clears run
      before any blit, so a corner cell's two bands don't erase each other.
- [x] **Second user correction:** "that black shadowed line that breaks the
      seam of the tiles, it is not needed at all." The E2/E5 overhang wash was
      a flat `_LIP_FRAC`-deep `BLEND_RGBA_MULT` fill just inside the rim; with
      the fringe now on top of it, its hard inner edge read as exactly the
      frontier line E7 removed from the south. I first softened it to a
      gradient (`lip_wash`) starting where the fringe ends -- but a gradient
      still has a hard *outer* end, so a dark line still followed the rim and
      broke at the tile seams. **The wash is now gone entirely** (`lip_wash`,
      `_LIP_MULT`, `_LIP_SHADE`, `_LIP_FRAC` all deleted) and nothing replaces
      it: the fringe art already reads as an edge. Lesson: a shadow band laid
      *next to* tile art will always terminate somewhere, and that termination
      is a line -- let the art carry the edge.
- [x] `tests/world/test_verticality.py::test_raised_rim_wears_the_cliff_grass_fringe`:
      a west-lip cell's band alpha equals `rotate(mid_top_tile, 90)` over the
      cleared region (this is what pins the fix -- it fails against the
      end-cap variants), and the outer column is a ragged silhouette (has both
      near-transparent and near-opaque pixels), not a solid grass edge.
      Suite 684 -> 685.
- Screenshots: `e9_after.png` (whole plateau ringed by cliff grass, no foam),
  `e9_west.png` (fringe continuous across four tile seams), `e9_north.png` /
  `e9_nw.png` (fringe meets the interior grass with no shadow line, corner
  wraps as one piece).

#### E10 - Use the sheet's real non-foam autotile block -- DONE (2026-08-29)
- User request: "finally consider corner tiles, the one there is is using a mix
  of both vertical and horizontal grass tiles, in that case the corner tile is
  a better fit, this what the metadata is for."
- **The finding that reframes E6 and E9.** Labelling the whole sheet by which
  edges each tile closes shows **cols 5-8 x rows 0-3 is a complete 16-tile
  autotile block** -- the exact parallel of the foam block at cols 0-2, but
  fringed with dark cliff grass instead of white surf:

  |        | w      | mid   | e      | w+e     |
  |--------|--------|-------|--------|---------|
  | **n**  | 5 nw   | 6 n   | 7 ne   | 8 nwe   |
  | **-**  | 14 w   | 15    | 16 e   | 17 we   |
  | **s**  | 23 sw  | 24 s  | 25 se  | 26 swe  |
  | **n+s**| 32 nsw | 33 ns | 34 nse | 35 all  |

  Only 32-35 were ever mapped, as `slots.cliff.top`. That row is the block's
  **horizontal strip** (fringed n *and* s) -- which is the entire reason E6
  had to crop the `top` tile: its north fringe was never wanted. The real
  south-edge tiles are 23-26, and real corners existed all along.
- [x] `data/terrain.json`: new `slots.raised`, the 16 tiles keyed by their
      **exposed sides** (`""`, `"n"`, `"nw"`, ... `"nswe"`).
- [x] `world/map.py` `raised_idx(m)`: a raised cell's tile is read straight off
      `TileMeta` -- `lip` already records exposed n/e/w and `cliff == "top"`
      records an exposed south -- with no re-derivation in the renderer. This
      is what the E0 metadata layer was built for.
- [x] `paint_room`: a raised room autotiles against `slots.raised` exactly as a
      ground room autotiles against the foam block.
- [x] `paint_cliff`: **stops drawing the rim cell.** The room now paints its own
      south-edge tile (grass + strand fringe), so the face starts one row below
      the rim. The staggered `body` underlay starts flush at `(row+1)*px` --
      body tiles are fully opaque along their top row and 23-26 are opaque
      throughout, so the two meet with neither a gap nor the face covering the
      rim tile's fringe.
- [x] **Deleted:** `_CLIFF_TOP_KEEP`, `_CLIFF_TOP_FEATHER` (E6's crop),
      `_LIP_BAND_N`, `_LIP_BAND_EW`, `_LIP_FEATHER`, `lip_band`, `edge_band`,
      `band_cache` (E9's rotated bands and silhouette clears). ~90 lines of
      render-time workaround replaced by one dict lookup.
- [x] Tests: `test_raised_room_uses_the_non_foam_autotile_block` (every raised
      cell matches the `slots.raised` tile its metadata selects, pixel-exact;
      asserts real north **and** south corners were exercised, since corners
      are the point) and `test_cliff_face_starts_below_the_rim_cell` +
      `test_cliff_face_is_opaque_straight_under_the_rim` (the face is
      transparent over the rim cell and opaque immediately under it). The three
      tests pinning E6's crop and E9's bands were retired. Suite stays 685.
- Screenshots: `e10_nw.png` (real `nw` corner tile, one piece), `e10_sw.png`
  (south-edge tile meeting the face with no gap and no second grass row),
  `e10_after.png` (whole plateau).

### E0-E10 as built (2026-08-29)

**Files:** `world/procedural.py` (`TileMeta`, `Room.tile_meta`, `_is_south_rim`
/ `_cliff_variant` / `_build_tile_meta`, `WorldLayout.tile_at`, call in
`generate_world`), `data/terrain.json` (`floor_sheets`, nested `slots.cliff`),
`data/terrain.json` (`floor_sheets`, nested `slots.cliff`, E10 `slots.raised`),
`world/map.py` (`_CLIFF_SEAM_OV`; `GameMap._cliff_foam`; `_build_tiles`:
`floor_sheets` normalise + `sheet_for` / `cliff_idx` / E10 `raised_idx`
closures; `paint_room` elevation sheet + foam gated on `tile_meta.foam` + E10
autotile against `slots.raised`; `paint_cliff` rewritten off `tile_meta` -- E7
widen-and-overlap tiles + half-tile-staggered `body` underlay (no flat backfill
rect), E8 `ground_k` picks the foamy `bottom` foot + a `_cliff_foam` lap over
void vs. a plain `body` foot cut flush onto a tile, E8a `ground_k` samples the
column's full width, E10 the face starts below the rim cell; `paint_stair` /
`paint_corridor` elevation sheet + no raised foam; `_draw_tiled` paints rooms
before their floor's cliff faces, foam pass covers `_shore + _cliff_foam`),
tests in `tests/world/test_verticality.py` (+14: `TileMetaTests` 5,
`ElevationSheetTests` 9 incl. sky-bridge / cliff-seam / lip /
foamy-vs-grounded-foot / partly-covered-column / raised-autotile-block /
face-starts-below-rim / face-opaque-under-rim) and
`tests/rendering/test_terrain.py` (+2, and a `setUpModule` flag pin).
Suite 667 -> 685.

**Key mechanic:** generation now emits a `TileMeta` per walkable cell
(`floor` / `surface` / `foam` / `cliff` / `cliff_var` / `lip`); the renderer
reads it instead of re-deriving edges, and any future system (per-floor decor,
tint, audio, minimap) has `WorldLayout.tile_at(wx, wy)` as one source of truth.
A raised room autotiles against `slots.raised` -- the sheet's second, non-foam
16-tile block -- keyed directly by the sides its `TileMeta` says are exposed, so
corners, strips and singles are all real authored tiles and nothing is rotated,
cropped or washed at render time. The stone face below the south rim autotiles
too (`left/mid/right/single` picked at gen; E7 widens each tile so the column
seams overlap closed and staggers a `body` underlay so the row seams never show
the void, with **no** opaque backfill rect -- the run's outer edges and their
dark outline pixels stay transparent), each floor has its own grass, and E8
gives each rim column the foamy `bottom` foot + a lapping-foam point only where
it drops into open water (a foot that lands on a lower room / bridge / stair is
cut flush and capped with plain stone).

**Deferred (later polish):** stairs still render as plain grass (a step
sub-sheet). `CLIFF_CARVE` stays off -- the skirt hangs off the rect edge, no
walkable inset needed.

### Touch list (anticipated)

* **E0:** `world/procedural.py` (`TileMeta` NamedTuple, `Room.tile_meta`,
  `_build_tile_meta` + cliff-variant picker, `WorldLayout.tile_at`, call in
  `generate_world`), `tests/world/test_verticality.py`.
* **E1-E4:** `data/terrain.json` (`floor_sheets`, `slots.cliff` -> nested edge
  dicts), `world/map.py` (`_build_tiles`: `paint_room` reads `meta.floor` /
  `meta.foam` / `meta.lip`, `paint_stair` sheet-per-floor, `paint_cliff` reads
  `meta.cliff` / `meta.cliff_var`, `paint_corridor` reads `meta.foam`;
  `_sheet_for` / `_cliff_idx` helpers), `game/content.py` or the terrain load
  (normalise `floor_sheets` keys), `tests/rendering/test_terrain.py`.
* **No** new dependencies. **No** new art (all five tilemaps already in
  `assets/terrain/tiles/`). **Nothing** committed.

---

## LD-3 — Ramp stairs (sideways) & plateau-adjacent layout

**Status:** **LD-3 COMPLETE** (2026-08-29, R0-R8). `config.RAMP_STAIRS` is
**on** by default: 50 ramp runs across 47 of 120 seeds, each as long as the real
floor difference, with carved obstacle-free landings at both ends and a darkened
crevasse wall behind the run. Both nav classes and the player collider traverse
them; everything that cannot take a run still renders as a plank bridge.
Suite 685 -> 698.

Replaces the cross-floor "stair" (today a plain grass strip spanning
room-centre to room-centre, which reads as a hanging bridge) with the
tileset's **ramp** pieces: a slope cut into the existing south-facing cliff
band, with the lower ground brought up against the cliff foot so the height
change is *beside* the ground floor rather than across a gap.

### The asset (already in `assets/terrain/tiles/tilemap_*.png`)

Slots **36 + 45** and **39 + 48** -- the four "unmapped but drawn" slots in
every sheet. Not literal steps: a rough model of the geography, a diagonal
grass slope with a stone wedge at its foot. Each set is **1 tile wide x 2 tiles
tall**; measured off the art:

| set | flush vertical edge | slope descends toward | high side |
|--|--|--|--|
| **36 / 45** | right (opaque rows 0-121) | west | east -- "up from left to right" |
| **39 / 48** | left (opaque rows 0-122) | east | west |

The flush edge is the join against a cliff `body` column; the diagonal is the
walkable surface. **2 tiles tall == `CLIFF_TILES`**, so one set covers exactly a
**one-floor** drop. Sideways only -- there is no north/south-facing ramp art,
and per the user north/south is out of scope for now.

### Why today's stairs read as bridges (measured over 60 seeds)

- 167 stairs: **92 h-axis, 75 v-axis**; 140 are a 1-floor drop, 27 a 2-floor.
- **No h-stair has adjacent rooms** -- min gap 80 px, median 240 px (3.75
  tiles). The `Stair` rect runs centre-to-centre, so it is always a long strip
  over open water.
- Only **16 of 168** floor-1 plateaus have any south-rim column whose foot
  currently lands flush at the cliff base (87 columns land flush, 1150 drop
  into void).

**The axis that matters is `v`, not `h`.** The cliff band faces *south*, so the
ground a ramp descends to must be south of the plateau; "sideways" is the
descent direction *within* the band. Of the 75 v-stairs:

- **61 are a 1-floor drop** (the ramp art's range).
- **39 have the plateau north of the ground room** -- the usable configuration.
  The other 36 have the plateau to the south and cannot use a south-facing ramp.
- Vertical gap **minus** the cliff band: median **+16 px**, range -144..+272.
  So the typical pair is a quarter-tile from being flush -- a nudge, not a
  redesign. None are flush today.
- X-overlap of the two rooms: min 5, median 7 tiles. Never the constraint.

### Core principle: a ramp *run* is a staircase cut into the cliff band

The band is already painted `face_h` tiles deep under every south rim. A ramp
run is a diagonal staircase inside it: **`face_h` ramp pieces, each stepping
one column and one row** from the plateau's edge toward the low ground, with
the rest of each ramp column's band rows filled with ordinary `body` / `bottom`
so the run sits on rock. Every flush edge lines up with its neighbour for free.
E8's `ground_k` already computes the landing condition (`k == face_h + 1`).

A run is therefore `face_h` tiles tall **and `face_h` tiles wide** -- 2x2 for a
floor-1 plateau, 4x4 for floor 2. That footprint is the new layout constraint.

### Milestones

| | scope | done when |
|--|--|--|
| **R0** | ~~**Map the art + render spike.**~~ **DONE 2026-08-29** -- findings below. Still to land: `data/terrain.json` `slots.ramp = {"w": [36, 45], "e": [39, 48]}` keyed by descent direction. | done: registration, stepping and cliff-fill all settled by hand-composited mocks; no code changed |
| **R1** | **Layout snap (the real work).** New `config.RAMP_STAIRS` (default **off**) and `config.RAMP_SNAP_TILES = 2` (**not** hard-coded -- decision 2). For a v-axis cross-floor edge where the high room is *north*: snap the low room's top edge to `high.rect.bottom + face_h * px`, and require **`face_h` free columns** on the descending side within the rooms' x-overlap (median overlap is 7 tiles, so this is usually fine at `face_h = 2` and tight at 4). Skip the pair -- leave it a bridge -- if the snap exceeds `RAMP_SNAP_TILES` or the footprint does not fit. Must not create room/room overlap, orphan a corridor rect, or invalidate obstacle keep-clear discs. | flag **off** -> every baseline hash byte-identical; flag on -> each snapped pair satisfies `low.top == high.bottom + face_h*px` and has room for its run; layout still fully connected on 30 seeds; suite green |
| **R2** | **`TileMeta.ramp` marks where a run *starts*.** New field `ramp: "" \| "w" \| "e"` (descent direction) set on the **one rim cell** the run begins at -- the band cells themselves are outside `Room.cells`, so the renderer and the nav layer walk the run from that cell (`face_h` steps, one column and one row each). Chosen deterministically, no RNG draw: inside the low room's x-range, with a rim neighbour on the high side so the first flush edge has a cliff column to join. | at most one `ramp` cell per snapped pair; walking the run stays inside the band and lands at `k == face_h + 1`; neighbouring `cliff_var` run still valid; determinism A/B |
| **R3** | **Walkability + nav.** The run **replaces that edge's `Stair`** (decision 5 -- the old rect is deleted, not kept). It contributes `face_h` **1-tile rects stepping diagonally** to `walkable_rects`, and each joins the corridor leniency mask so the flow field routes through it. | flow field reaches every raised room on 30 seeds with the flag on; no unreachable room; `test_pathfinding` / `test_obstacles` green |
| **R4** | **Render.** `paint_cliff` walks the run: per step blit the 1x2 piece with its **top tile at that step's surface row** (R0 finding 1), then fill that column's remaining band rows below it with `body`, using `bottom` on the band's last row (R0 finding 3). Skip the E8 foam foot at ramp columns -- they land on ground, not water. Decide whether the rim cell above the topmost ramp keeps its E10 `s` edge tile or reverts to plain interior so the slope reads continuous. | screenshot matches the reference; no seam against either neighbour column; no foam at a ramp foot; **no ground grass visible under the run** |
| **R5** | **Clearance + clipping (decision 1).** The run is a 1-tile-wide *diagonal* path -- verify the smallest nav class traverses it without wedging, and that the ramp does not **clip** into the plateau or the low room (correct registration between the two floors, sideways only). Widen to 2 columns only if the clearance check fails. | the small class traverses every run on 30 seeds; no wedging; no overlap of ramp art with room tiles |
| **R6** | **Playtest, screenshots, flag on by default, journal.** | windowed run; ramps read as terrain, not bridges; suite green; `RAMP_STAIRS = True` |

### R0 findings (spike done 2026-08-29, no code changed)

Hand-composited the ramp into a cliff band to fix its registration before
writing any generation code. Two results that change the plan:

**1. The piece straddles the rim -- it is not two band rows.** Classifying the
stacked pair's right (flush) edge pixel by pixel:

```
36/45 right edge, top -> bottom (128 px)
  ooo GGGG..........GGGG (y 3-66)   oooo SSSS.....SSSS (y 71-118)  oooo ....
      ^ one tile of GRASS                ^ one tile of STONE
```

A cliff `body` tile's edge is stone for all 64 px, so the ramp's **top tile
sits at the surface level** (level with the grass it leaves) and its **bottom
tile is the first cliff row**. One ramp therefore descends **one tile**.

**2. Ramps step one column *and* one row at a time.** The first mock spaced
them 2 rows apart and they came out disconnected; on the user's correction
("lower the top stairs one tile") they join into a single continuous diagonal.
So a run of `n` ramps descends `n` tiles and is `n` tiles wide.

Consequences:
- **floor 1** (`face_h = 2`) needs **2 ramps**, footprint 2 tiles wide.
- **floor 2** (`face_h = 4`) needs **4 ramps**, footprint 4 tiles wide.
- Two ramps do **not** reach the second floor -- they leave the top 2 rows of
  the band with no connection (rendered and confirmed). This answers decision 4
  below.
- The run's horizontal footprint is a new layout constraint: the plateau needs
  `face_h` free columns on the descending side.

**3. Each ramp column needs cliff texture *below* the ramp.** The ramp piece
only carries a small stone wedge at its foot, so on its own the run appears to
float with ground grass showing beneath it. Filling each ramp column's
remaining band rows -- from the ramp's bottom tile down to the band's last row
(`bottom` variant on that last row) -- puts the staircase on solid rock and
closes the gap between the run and the ground. Rendered four ways (no fill /
below / above / both): **below only** is correct. Filling *above* the ramp
walls off the top of the run and is wrong.

### Decisions (locked 2026-08-29)

1. **Ramp width = 1 column** for now (art-native). R5 additionally has to check
   the ramp does not **clip** and registers correctly between the two floors --
   sideways ramps only.
2. **Snap cap = 2 tiles**, but **not hard-coded** -- a `config` constant
   (proposed `RAMP_SNAP_TILES = 2`) so longer approaches are possible later.
   At 2 tiles, 27 of 32 usable pairs qualify (84%); 1 tile would give 53%.
3. **Plateau-south pairs (36 of 75) stay bridges**, rendered with the existing
   bridge assets even though the result is visually inconsistent for now.
4. **2-floor drops:** two ramps are **not** enough -- see R0 finding 2. A
   4-tile band needs a 4-ramp run, which renders correctly. Treat the run
   length as `face_h` rather than a fixed pair, and keep a pair as bridge if
   there is not room for the full run.
5. **The old `Stair` is deleted** when a ramp replaces it. A leftover strip is
   exactly what reads as a bridge.
6. **The 92 h-stairs keep bridge rendering.** No change to edge selection --
   biasing the room tree is out of scope.

### Risks

- **R1 perturbs the RNG stream and room geometry**, so every pinned baseline in
  `test_verticality`, `test_pathfinding` and `test_obstacles` moves. Expected,
  but it makes the diff noisy -- hence the flag and the flag-off byte-identical
  gate.
- **Flow field.** Pulling raised rooms into contact with their neighbours is the
  same territory that made `_carve_cliffs` break pathing in LD-1 (~9/30 seeds
  had unreachable floor-1 rooms), which is why `CLIFF_CARVE` is still off. R3
  and R5 exist to catch that; A/B every step the way `WORLD_VERTICALITY` was.
- **Snapping rooms together removes the water gap** between them, which is what
  the plank bridge and its foam currently occupy. Check that no orphan bridge or
  shoreline is left behind at a snapped pair.
- **The run's footprint may not fit at `face_h = 4`.** A floor-2 run is 4x4
  tiles; room x-overlap is 5-10 tiles (median 7), so it usually fits, but the
  run also has to stay inside the plateau's own cell mask. Expect some floor-2
  pairs to fall back to bridges.
- **A 1-tile-wide diagonal path is the tightest pinch in the game.** LD-1 chose
  pinch points deliberately ("enemies clog in them"), but R5 has to confirm the
  small nav class can actually traverse a diagonal one.

### Touch list (anticipated)

* **R0 (done):** scratch mocks only. Still to land: `data/terrain.json`
  (`slots.ramp`).
* **R1:** `game/config.py` (`RAMP_STAIRS`, `RAMP_SNAP_TILES`),
  `world/procedural.py` (`generate_world` -- a snap pass after `_assign_floors`
  / `_split_links`, before the bounds union and the obstacle scatter).
* **R2:** `world/procedural.py` (`TileMeta.ramp`, `_build_tile_meta`).
* **R3:** `world/procedural.py` (`Stair` deletion, `walkable_rects` gains the
  run's stepped rects), `world/map.py` (`_point_ok`), `world/pathfinding.py`
  (leniency mask).
* **R4:** `world/map.py` (`paint_cliff` ramp-run branch + below-ramp cliff fill,
  `_cliff_foam` skip).
* **Tests:** `tests/world/test_verticality.py` (new `RampTests`),
  `tests/ai/test_pathfinding.py`, `tests/world/test_obstacles.py` (baselines).
* **No** new art, **no** new dependencies. **Nothing** committed.

### Checklist

#### R1 - Layout snap -- DONE (2026-08-29)
- [x] `game/config.py`: `RAMP_STAIRS = False` (default off) and
      `RAMP_SNAP_TILES = 2` (a constant, not a literal -- decision 2).
- [x] `world/procedural.py`: `_face_h(room)`, `_ramp_candidates(rooms, edges)`
      (cross-floor tree edges whose cells are vertically adjacent with the high
      room **north**, so its south band faces the low room), and
      `_plan_ramps(rooms, edges, corridors)` -- snaps the low room's top to
      `high.rect.bottom + face_h*px`, then `_relink_corridors`. Runs before
      `_split_links`, so the links are cut against the snapped geometry.
- [x] A pair is skipped (and stays a plank stair) when the move exceeds
      `RAMP_SNAP_TILES`, the moved rect would overlap another room, or the run's
      footprint does not fit. **A room may join at most one run** -- a `locked`
      set; without it a second snap slid a room out from under an already
      planned run (2 of 32 runs were malformed).
- [x] **Footprint bug found and fixed twice.** First pass required the run to sit
      *outside* the plateau's rect: 30 of 39 candidates rejected, 3 runs total.
      The band hangs *below* the plateau, so the run belongs in the two rooms'
      **x-overlap**. Second pass indexed columns in world space (`x // px`) --
      but room rects are tile-*sized* and **not tile-aligned**, so the two
      rooms' grids do not line up; 5 runs had steps outside the low room. Now
      indexed in the **plateau's own grid** (`hi.rect.left + i*px`).
- [x] Yield: **57 runs over 53 of 120 seeds**, all well-formed, none
      disconnected.

#### R2 - `TileMeta.ramp` -- DONE (2026-08-29)
- [x] `TileMeta` gains `ramp: str = ""`. `_build_tile_meta(rooms, plan)` tags
      the **one rim cell** each run starts at with its descent direction; the
      run's own cells are in the band, outside `Room.cells`, so consumers walk
      out from the tag. No RNG draw.
- [x] 29 tags over 60 seeds, one per run, every one on a `cliff == "top"` cell
      at the run's first step column.

#### R3 - Walkability + nav -- DONE (2026-08-29)
- [x] `Stair` gains `ramp: str = ""`. A run emits `face_h` one-column `Stair`
      steps (`_ramp_steps`), so `walkable_rects`, `GameMap._point_ok`,
      `_point_in_corridor` and `NavGrid` all pick them up **unchanged** -- the
      cheapest possible R3.
- [x] `_split_links(..., ramped)` emits **no** stair for a ramped edge
      (decision 5).
- [x] **The flow field broke, exactly as the risk section predicted.** With one
      1x1 rect per step, 16 of 137 raised rooms went unreachable (whole
      plateaus at 0.00). Cause: the Dial expansion refuses a diagonal move
      unless *both* orthogonal neighbours are traversable ("would clip a
      blocked corner"), so a chain of single diagonal cells is impassable.
      **Fix:** each step's rect is its whole **1x2 art footprint**, so step `i`
      (rows `i-1..i`) and step `i+1` (rows `i..i+1`, one column over) share a
      row band in touching columns and connect orthogonally. The art stays one
      column wide, so decision 1 is untouched. 0 of 137 unreachable after.
- [x] `tests/world/test_verticality.py::RampTests` (9): flag-off plans nothing;
      some seeds do get a run; a run is `face_h` steps one column and one row
      apart; it lands flush between its two rooms; steps are orthogonally
      adjacent (the pathing invariant above); a ramped edge keeps no leftover
      stair; metadata tags exactly the first column; the flow field still
      reaches every raised room; layout stays connected and deterministic.
      Suite 685 -> 694.
- Flag **off** is the default and the whole suite is green, so the LD-2
  baselines are untouched; flag on differs only on seeds where a run is planned.

#### R4 - Render the run -- DONE (2026-08-29), one choice open
- [x] `data/terrain.json`: `slots.ramp = {"w": [36, 45], "e": [39, 48]}`, keyed
      by descent direction -> `[top, bottom]`.
- [x] `paint_cliff` builds `ramp_step` by walking the run out from the single
      `meta.ramp` rim cell (`face_h` steps, one column and one row each), and
      hands those columns to a ramp branch instead of the normal face. Pieces
      are painted in a **second pass** so a widened neighbour never clips the
      slope, and are **not** widened themselves -- the flush side is already
      opaque and the neighbour's own overlap reaches into the column.
- [x] `raised_idx` drops the **south** side for a cell tagged `ramp`, so the
      plateau's grass flows off into the run instead of an `s` edge tile
      cutting a cliff fringe across the top of it.
- [x] **Two bugs, both found by looking at the render:**
  * *Flat grass instead of the slope.* Ramp steps are `Stair` objects (that is
    how R3 got walkability for free), so `paint_stair` baked a plain grass
    strip for each and `_draw_tiled` painted it **after** the cliff face,
    covering the art. `_build_tiles` now skips `st.ramp` stairs.
  * *Water inside the rock.* The piece's slope is a cutout; with only the rows
    *below* it filled, its transparent upper wedge showed the sea. Each ramp
    column now fills every band row from the piece down to the base -- behind
    the piece as well as below it. The first step's top tile lands on the rim
    row, which is the room's own grass, so that row is never backed.
- [x] **The notch above each step stays open** -- settled by the user, and for
      a reason worth recording because it is not a rendering argument at all:
      "the notchs are necessary to allow for enough space for the characters to
      properly use the stairs in a 2d environment without looking disjointed,
      both at the bottom and on the upper floor." A character sprite is drawn
      extending *upward* from the tile its feet occupy, so cliff face directly
      above a step would swallow anyone standing on it and make the top and
      bottom of the climb read as disjointed. I had it backwards -- I read the
      open rows as a hole in the rock and was ready to fill them.
      `_RAMP_FILL_ABOVE` stays **False**; kept as a constant only so the
      alternative is one edit away. `r4_above.png` compares the two.
- **General rule this implies:** at any elevation transition, check whether a
  gap is load-bearing for character rendering before treating it as an
  artifact. Fix "the void shows through" by changing what is *behind* the gap,
  never by closing it.
- Suite still 694 green (flag off by default).

#### R5 - Clearance + clipping -- DONE (2026-08-29)
- **Scoping correction:** R5 was written as "verify the *smallest* nav class
  fits". Wrong way round. `_NAV_CLASSES` is `small` (cell 32, min clearance 16)
  and `large` (cell 48, min clearance 22) -- the **large** class is the one a
  1-tile pinch threatens. R3's reachability check had also used
  `cost(..., 14) or cost(..., 30)`, so a small-class success was masking
  large-class failure.
- [x] **Bug found: the run's foot could land on a bitten-out cell.** With both
      classes checked separately, 4 small / 8 large step centres were
      unreachable across 40 seeds, and 4 plateaus were unreachable by the large
      class. Not obstacles (identical with the scatter disabled) -- dumping the
      nav grid showed the last step's columns walkable but the low room's cells
      beneath them missing. `_plan_ramps` had tested the low room's **rect**;
      an irregular room has bitten-out cells, so the staircase ended over void.
      New `foot_lands(col)` check requires every low-room cell the last step
      spans to be present at row 0. After: **0 unreachable at either class,
      obstacles included**, and the yield is unchanged (29 runs / 26 of 60
      seeds) -- the check moves the chosen column rather than dropping runs.
- [x] **Clipping is clean.** Sampling the baked cliff surface above every run:
      68 opaque samples, **all** inside the +/-`_CLIFF_SEAM_OV` (8 px)
      neighbour-overlap zone, **0 in the column core**. Nothing painted below
      the band either. So the notch stays open exactly as R4 intends.
- [x] Visual check with a real hero sprite seated the way the game seats it
      (rig anchor on the collider centre, then `SPRITE_ANCHOR_DROP * radius`):
      walked down a 2-step and a 4-step run, plus the plateau landing above and
      the low-room landing below. Sprites stand clear on every step -- the
      notch does its job. Screenshots `r5_floor1.png` / `r5_floor2.png`.
- [x] `RampTests` +3: both nav classes traverse every run (obstacles included);
      the run's foot lands on real low-room cells; ramp art does not clip into
      the notch. Suite 694 -> 697.

#### R6 - Playtest + flag on -- DONE (2026-08-29)
- [x] `config.RAMP_STAIRS = True`. Full suite with the flag **on**: only **2**
      failures, both LD-2 tests encoding the pre-LD-3 rule, both correct new
      behaviour rather than regressions:
  * `test_cliff_face_starts_below_the_rim_cell` -- the face must be transparent
    over a rim cell, but a run's first piece deliberately puts its top tile on
    the rim row. Now skips `m.ramp` cells.
  * `test_raised_room_uses_the_non_foam_autotile_block` -- recomputed `sides`
    including `"s"`, while `raised_idx` drops the south side on a ramp cell.
    Now mirrors the `south = m.cliff and not m.ramp` rule.
- [x] **Playtest through the real game, not a synthetic map.** A `PlayingState`
      run on a ramp seed, player dropped on the plateau above the run's head and
      walked down it waypoint by waypoint through `Player.update` /
      `GameMap.resolve_movement` -- the game's own collision, no shortcuts.
      Seed 10 (floor 2, 4 steps): **5/5 waypoints**. Seed 0 (floor 1, 2 steps):
      **3/3**. So the run is traversable by the player collider, not just by the
      flow field.
- [x] Screenshots from the live game with HUD and decor: `r6_floor2_top.png`
      (about to descend), `r6_floor2_mid.png` (mid-run -- the one that shows the
      point), `r6_floor2_bottom.png`, `r6_floor1_bottom.png`. A plank bridge is
      visible in the same frame for contrast with the old look.
- Yield with the flag on: **29 runs over 26 of 60 seeds**. Everything else --
  the 92 h-axis links, 2-floor drops with no room for a 4-wide run, and pairs
  where the plateau sits south -- keeps bridge rendering, per decisions 3, 4
  and 6.
- Suite **697 green with `RAMP_STAIRS = True`**.

#### R7 - Guaranteed landings at both ends -- DONE (2026-08-29)
- User request, with an annotated screenshot marking the two tiles with an X:
  "there needs to be an empty tile in front of the stairs at the bottom to
  enter the stairs with a proper level and there needs to be another empty tile
  at the arrival floor". Confirmed as a **generation** condition, not a render
  one -- the "crevasse" (the notch through the band) already exists; what was
  missing was any guarantee about the floor at each end.
- Measured first, and the answer was not what it looked like: across 120 seeds
  / 57 runs **all four checks already passed**. But for two different reasons,
  and only one was a mechanism:
  * *Obstacles* were genuinely protected -- ramp steps are `Stair`s, so
    `_scatter_obstacles`' `s.rect.inflate(2*px, 2*px)` already kept scenery a
    tile clear of every step.
  * *The cells existing* was *luck*. Nothing checked it. It held because rooms
    are >= 3 tiles and runs sit in the x-overlap, but a bite could land there
    and `_plan_ramps` would have planned the run anyway -- the same rect-vs-cells
    class of bug that already bit twice (R1 footprint, R5 foot).
- [x] `_plan_ramps`: `foot_lands` now requires **two** rows of low-room floor
      (`(c, 0)` *and* `(c, 1)`) under the last step, and a new `head_lands`
      requires the plateau tile behind the head (`(col0, rows_n - 2)`). Both are
      pure predicates on the cell masks -- deterministic, no RNG draw, and they
      only ever reject a candidate (it stays a plank bridge).
- [x] `_scatter_obstacles`: a **ramp** step's keep-clear is one tile deeper than
      an ordinary stair's. One tile only covered the cell the foot lands on; the
      guaranteed landing is two rows deep, and a rock on the second row blocks
      the approach just as well as one on the first. This was the only real
      violation left -- 6 of 57 runs.
- **Yield unchanged: 57 runs over 53 of 120 seeds**, no disconnections. As
  expected -- the conditions codify what already held, so their value is
  preventing drift, not changing today's output.
- [x] `RampTests::test_every_run_has_a_landing_at_both_ends` pins all of it, so
      the incidental obstacle protection is now an asserted invariant instead of
      a side effect nobody knew they depended on. Suite 697 -> 698.

#### R8 - Carved landings, filled notch, true drop height -- DONE (2026-08-29)
Three fixes from one round of user feedback on a live screenshot.

**1. The landings are now carved, not merely required.** R7 implemented the
user's two X-marked tiles as a *precondition* -- only plan a run where they
already exist. Measurement said they always did, so the yield was unchanged and
**nothing appeared on screen**, which is what prompted "why are the end tiles
not placed". That answered a different question than the one asked.
`landings()` now returns the cells and `_plan_ramps` **adds them to the room
masks**, so the guarantee holds by construction. It still only rejects a
candidate when a landing would fall outside a room's rect entirely.

**2. The notch is filled and darkened.** R4 left the band rows above a step
open because the user said the notch is load-bearing for character sprites --
correct, but I stopped there and never dealt with what shows *behind* it, which
was the sea ("why is the blue empty space in the middle of the stairs"). It is
now filled with the ordinary cliff face and multiplied down by
`_RAMP_NOTCH_MULT`, so it reads as the recessed far wall of the crevasse:
present, but clearly behind whoever is on the stairs. Full brightness was
rejected earlier for exactly the swallowing reason, so the darkening is what
makes filling it compatible with the sprite-space requirement.

**3. `face_h` was the drop to the *sea*, not to the neighbour.** `_face_h` is
`min(room.floor, 2) * CLIFF_TILES` -- correct for a rim overhanging water, wrong
for a boundary between two raised rooms. A floor-2 plateau meeting a floor-1
room was snapped **4** tiles apart and given a **4**-step run when the real step
is one floor. New `_drop_h(high, low)` uses the actual floor difference; the
renderer already adapted, since E8's `ground_k` shortens a face to whatever it
lands on. Run lengths are now `f1->f0: 2, f2->f0: 4, f2->f1: 2, f3->f2: 2`.
`_face_h` stays for the over-water case.
- **Yield 57 -> 50 runs over 47 of 120 seeds.** The snap distance changed, so
  some pairs no longer fit inside `RAMP_SNAP_TILES`. Fewer but geometrically
  honest.
- `paint_cliff` counts a run's steps off `layout.stairs` rather than assuming
  `face_h`, since the two now differ. `ground_k` cannot serve here -- ramp steps
  *are* `Stair`s, so it finds the run itself one row down and reports a
  zero-height face.
- Tests: `test_a_run_is_drop_steps_one_column_and_row_apart` and the flush test
  use `_drop_h`; `test_ramp_art_does_not_clip_above_the_run` replaced by
  `test_the_notch_is_recessed_not_open_and_not_full_brightness` (notch opaque
  **and** darker than the face below it). Suite 698 green.
- Re-playtested through the live game: 5/5 and 3/3 waypoints, unchanged.

### LD-3 as built (2026-08-29)

**Files:** `game/config.py` (`RAMP_STAIRS`, `RAMP_SNAP_TILES`),
`world/procedural.py` (`Stair.ramp`, `TileMeta.ramp`, `_face_h`,
`_ramp_candidates`, `_plan_ramps` + `foot_lands`, `_ramp_steps`,
`_split_links(..., ramped)`, `_build_tile_meta(rooms, plan)`),
`data/terrain.json` (`slots.ramp`), `world/map.py` (`_RAMP_FILL_ABOVE`,
`ramp_slots`, `raised_idx` south-drop, `paint_cliff` ramp branch + second-pass
piece blit, `_build_tiles` skips `st.ramp` in `paint_stair`),
`tests/world/test_verticality.py` (`RampTests`, 13).
R8 adds `_drop_h` / carved landings / `_RAMP_NOTCH_MULT`.

**Key mechanic:** a cross-floor link whose rooms can be brought into contact
becomes a **ramp run** -- `face_h` one-column pieces stepping one column and one
row each, cut into the cliff band, with the band filled behind and below them
and the notch above left open for character sprites. Each step is a one-tile
`Stair`, so collision, `walkable_rects` and the nav grid pick the run up with no
changes; each step's rect is the full 1x2 art footprint so consecutive steps
touch orthogonally, which is what the flow field needs.

**Still bridges:** h-axis links, 2-floor drops without room for a 4-wide run,
and pairs whose plateau sits south of the low room.

### Scratch mocks (R0, in the session scratchpad)

`ramp_pieces.png` (36/45 and 39/48 as 1x2 pieces on a checkerboard),
`ramp_mock.png` / `ramp_mock3.png` (the stepping sweep that fixed the 1-row
offset), `ramp_floors.png` (2-ramp floor-1 run vs 4-ramp floor-2 run vs a
too-short 2-ramp attempt at floor 2), `ramp_fill.png` (no fill / below / above /
both -- **below** is correct).

---

## LD-4 — Staircase units (2-tile-tall stairs with carved landings)

**Status:** **LD-4 COMPLETE** (2026-08-29, S0-S4). Reworks LD-3's ramp runs into 3x2 staircase units. 40 units over 38 of 120 seeds, one-floor links only. Suite 696 green, `RAMP_STAIRS` on.

### Why LD-3's model was wrong

LD-3 placed **one piece per tile of descent**, each overlapping its neighbour by
a row, stepping diagonally. A 2-tile drop was 2 pieces in 2 columns. The art
wants **two vertical tiles per piece**, so squeezing one into a single tile of
drop is what made the result read as vertically compressed.

The user's reference, in their notation (`#` cliff, `=` ground, `>` stair):

```
row r-1:  = = = = = = = = = =     plateau surface (the rim row)
row r:    # # # # # # > = # #     stair top   + TOP landing at c+1
row r+1:  # # # # # = > # # #     BOTTOM landing at c-1 + stair bottom
row r+2:  = = = = = = = = = =     low room surface
```

A staircase is a **3-wide x 2-tall unit** cut into the band: the 1x2 piece at
column `c` spanning *both* band rows, a ground landing at `(c+1, r)` and another
at `(c-1, r+1)`. Descending west; mirrored for east.

**The art confirms the layout.** R0 measured the piece's flush edge as grass for
the top 64 px then stone for ~52 px. That is exactly this placement -- the
stair's top-right grass meets the grass landing at `(c+1, r)`, its bottom-right
stone meets the cliff at `(c+1, r+1)`. The R0 pixel measurement was right; the
placement inferred from it was wrong.

**This also fixes the "end tiles".** R7/R8 carved landings at the run's own
column. They belong one column *out* at the top and one column *in* at the
bottom -- which is why nothing looked placed.

### Decisions (from the user, 2026-08-29)

1. **Landings use the sheet of the floor they sit on** -- high room's for the
   top landing, low room's for the bottom, so each matches its own terrain.
2. **Multi-floor: option (c) for now.** Stairs only for a **one-floor** change;
   deeper cross-floor links stay plank bridges.
   Multi-floor stacking is drawn and understood -- units sit in adjacent columns
   sharing a row, so N floors -> N stairs -> **N+1** band rows -- but that
   contradicts the existing band depth (`min(floor,2) * CLIFF_TILES` gives a
   floor-2 plateau 4 rows, the stacked model wants 3). Option (c) avoids
   touching the LD-2 cliff look; (a) reshapes band depth, (b) uses 3 stairs for
   a 4-row band. Deferred, not discarded.
3. **Crevasse edges use the `left` / `right` cliff variants** so the cut has
   finished ends instead of blunt `mid` tiles.
4. **Trigger on adjacency**, not on converting a long corridor: a staircase goes
   where high and low ground end up beside each other.

### Milestones

| | scope | done when |
|--|--|--|
| **S0** | **Placement spike.** Hand-composite the 3x2 unit against the real tiles, including `left`/`right` variants at the cut. No generation change, no RNG. | the piece's edges meet both landings and the cliff with no seam; screenshot |
| **S1** | **Structure model.** `_plan_ramps` -> one unit per link, `d_floor == 1` only. Footprint: 3 consecutive columns in the x-overlap, 2 band rows. Landings at `(c+1, r)` / `(c-1, r+1)`, and their approach cells (plateau above `c+1`, low room below `c-1`) must exist. | flag off byte-identical; flag on -> every unit well-formed, layout connected, suite green |
| **S2** | **Walkability.** Four tiles per unit chained `(c+1,r) -> (c,r) -> (c,r+1) -> (c-1,r+1)`, every link **orthogonal** -- removes the diagonal-corner hazard that broke pathing in LD-3 R3. | both nav classes and the player collider traverse every unit |
| **S3** | **Render.** Piece blits once across both rows; landings use their own floor's sheet; cliff fills behind the piece's transparent top; cut edges use `left`/`right` variants. | screenshot matches the reference; no seam, no void, no foam at the cut |
| **S4** | **Playtest + screenshots + flag on.** | live run walks a unit end to end |

### Checklist

#### S0 - Placement spike -- DONE (2026-08-29)
- [x] Hand-composited the 3x2 unit against the real tiles, both directions, with
      and without `left`/`right` variants at the cut (`s0_unit.png`). The piece's
      edges meet both landings and the cliff cleanly, and the end variants are
      clearly better than blunt `mid`. No generation change, no RNG.

#### S1 - Structure model -- DONE (2026-08-29)
- [x] `_plan_ramps` rewritten: one **unit** per link, `hi.floor - lo.floor == 1`
      only (option c). Snap distance is now `CLIFF_TILES` flat -- there is only
      one drop size a unit can span.
- [x] `fits(col, d)` requires three consecutive columns in the x-overlap, all
      south-rim, plus **two rows** of real floor in each room at the approach
      columns (see S2 for why two).
- [x] `_ramp_steps` emits the unit's tiles. `_drop_h` retained but no longer
      drives the run length.
- **40 units over 38 of 120 seeds**, all well-formed, none disconnected. Fewer
  than LD-3's 50 runs because option (c) drops every multi-floor link.

#### S2 - Walkability -- DONE (2026-08-29)
- [x] Five one-tile `Stair`s per unit, so collision, `walkable_rects` and the
      nav grid pick them up unchanged.
- [x] **Bug: the large nav class could not reach a unit.** 3 of 40 seeds had
      every unit tile unreachable at radius 30 while the small class was fine.
      Cause: the unit's lenient cells stopped at the room edge, and a room-edge
      cell is within 22 px of the boundary, so it fails the large class's
      clearance test -- there was no lenient cell bridging the gap. **This is
      the same problem LD-1 solved for plank stairs** by spanning them
      centre-to-centre ("the stair's clearance-lenient cells then punch past any
      tight room-edge neck"). Fixed by giving each unit two **approach** rects
      reaching two tiles into each room. After: 0 unreachable at either class,
      obstacles included.
- The chain is `top approach -> top landing -> stair -> bottom landing ->
  bottom approach`, every link sharing a full edge, so nothing depends on
  diagonal movement -- LD-3 R3's diagonal-corner hazard is gone by construction.

#### S3 - Render -- DONE (2026-08-29)
- [x] `paint_cliff` rewritten around `unit[col] = (part, direction, low_room)`.
      Per unit column: cliff first (so the piece's transparent parts show rock,
      not sea), then the part's own tile. The stair piece blits once across both
      band rows in a second pass, so no widened neighbour clips it.
- [x] Landings use **the sheet of the floor they sit on** (decision 1) -- the
      plateau's for the top, the low room's for the bottom.
- [x] `cut_var(col, band, fallback)` gives the cliff beside the cut its
      `left` / `right` / `single` end variant per band row (decision 3), instead
      of a blunt `mid`.

#### S4 - Playtest -- DONE (2026-08-29)
- [x] Live `PlayingState` run, player walked the whole unit through
      `Player.update` / `resolve_movement`: **4/4 waypoints** on two seeds.
      Screenshots `r6_ld4_mid.png` (mid-unit) and `r6_ld4_bottom.png`.
- [x] `RampTests` rewritten for the unit model (11): flag-off plans nothing;
      all five tiles in the right places; flush and one-floor-only; the chain is
      orthogonal end to end; approaches reach two tiles into each room; both nav
      classes traverse; no obstacle on a unit; metadata tags the stair column;
      connected and deterministic; and the render puts a stair piece plus two
      grass landings in with no void showing.
- Suite 698 -> **696** (the LD-3 run-shape tests are gone, replaced by fewer,
  sharper unit tests). `RAMP_STAIRS` stays **on**.

### LD-4 as built (2026-08-29)

**Files:** `world/procedural.py` (`_plan_ramps` + `fits` / `spans` / `low_col`,
`_ramp_steps`, `_drop_h`), `world/map.py` (`paint_cliff` unit branch,
`cut_var`, `_RAMP_NOTCH_MULT` removed), `tests/world/test_verticality.py`
(`RampTests` rewritten, `tile_at` test taught about approach tiles).

**Key mechanic:** a cross-floor link between rooms one floor apart becomes a
3x2 staircase unit cut into the cliff band -- a 1x2 stair piece spanning both
band rows, a landing one column out at the top and one column in at the bottom,
each landing in its own floor's grass, cliff behind everything, and `left` /
`right` cliff variants finishing the cut. Five one-tile `Stair`s carry
collision and nav, chained orthogonally with approaches reaching two tiles into
each room for clearance.

**Deferred:** multi-floor flights (units stacking in adjacent columns sharing a
row -- N floors -> N stairs -> N+1 band rows) need the band depth reworked
first, since `min(floor,2) * CLIFF_TILES` gives a floor-2 plateau 4 rows where
the stacked model wants 3. Options (a) and (b) from the decisions are still on
the table.

---

## LD-5 — Structure-tile ownership, floor-shape unification, synthesized 3-sided tile

**Status:** **LD-5 COMPLETE** (2026-08-29, U0-U5). `config.STRUCT_ANNEX` on:
structure tiles have an owning room, plank stairs render as bridges (~1 wide
per 7 narrow), and staircase-unit landings fold into their room's autotiled
shape as synthesized 3-sided grass. Suite 696 -> 701.

### The three defects (measured over 120 seeds)

A **structure tile** = a tile placed by generation that is in *no* `Room.cells`
mask: a plank-corridor plank, a plank-`Stair` strip, an LD-4 staircase-unit
landing / approach / stair-piece.

1. **No ownership.** `TileMeta` has `room_id` + `floor`, but only for room
   cells. `WorldLayout.tile_at` synthesises corridor / stair meta with
   `room_id = -1`. Structure tiles have no meta at all. So a renderer cannot ask
   "which room's palette does this tile belong to".
2. **Single-sheet strips -> palette bleed.** `paint_stair` fills the whole strip
   with `cell(sheet_for(high.floor), interior)` -- one elevation sheet, no edge
   tiles, no planks. **All 294** non-ramp plank stairs cross a floor boundary
   (by definition); **212** also cross a room-*kind* boundary
   (`room_palettes` differ). Every strip therefore meets at least one room in
   the wrong grass tone -- the "right biome bleeding into the left floor" in
   the screenshot. **52 of 294 are `width_tiles = 2`**, so the bleed is a
   2-tile-tall slab of bare grass with no bridge drawn.
3. **Floor shape stops at the mask.** `_build_tile_meta`, `_mask_slot` and
   `raised_idx` all derive a cell's autotile edges from 4-neighbour membership
   in `Room.cells` only. A landing tile that visually extends room X is not in
   X's mask, so: (i) it is never autotiled -- it gets flat `interior` and reads
   as a pasted square; (ii) X's own edge cell *next to* the landing still sees a
   gap there and draws a foam `edge_s`, cutting a shoreline through what should
   be solid ground.

Rooms never actually overlap or touch (0 / 0 pairs over 60 seeds), so none of
this is room-rect bleed -- it is entirely un-owned, un-autotiled structure
tiles.

### The fixes

#### (a) Ownership -- every structure tile gets an owning room + palette

- `TileMeta` already has `room_id`. A new `_annex_structure_tiles` pass right
  after `_build_tile_meta` emits a `TileMeta` for every structure tile, keyed
  in **that owner's** room-relative grid, with `surface` in
  `{"corridor", "stair", "ramp"}` and `room_id` set.
- **Ownership rule:**
  - plank corridor: split at the run midpoint -- each half to its nearer room.
  - plank stair strip: the part inside the high room's rect -> high; inside the
    low room's rect -> low; the gap span -> **high** (consistent, arbitrary).
  - LD-4 unit: top landing + top approach -> high; bottom landing + bottom
    approach -> low; the 1x2 stair piece -> high (it is cut into the high
    room's band).
- `tile_at` returns these instead of synthesising, so gameplay systems
  (footstep audio, minimap, per-floor decor) get a real `room_id` / `floor`.
- **Renderer:** `paint_stair` and the LD-4 landing blits pick the sheet from
  each tile's own `room_id` (`sheet_for(owner.floor, owner.kind)`), not one
  sheet for the whole strip.

#### (b) Floor-shape unification -- the room's outline includes its annex tiles

- Per room, build `annex: set[(col,row)]` (room-relative, may be negative or
  outside the rect) = the structure tiles it owns from (a).
- `_build_tile_meta` derives `lip` / `cliff` / `_mask_slot` sides over
  **`cells | annex`**, not `cells`. So:
  - an annex tile is autotiled as part of the room (correct edges + corners);
  - a real edge cell next to an annex tile sees floor there, not a gap, and
    drops its foam `edge_s`.
- **Paint:** `paint_room` needs to draw annex tiles that fall outside
  `r.rect.size`. Options: enlarge the room surface to the annex bounding box, or
  a second per-tile blit pass. Decide in the spike.
- This is the far-reaching fix: it changes what "a room's shape" means for
  **every** raised room's edge derivation, not only near stairs. Gate behind a
  flag, A/B flag-off byte-identical, exactly like LD-1's `WORLD_VERTICALITY`.

#### (c) Synthesized 3-sided grass tile (user's two-layer idea)

The sheet has a **4-sided** closed-grass tile (`slots["single"] = 30` ground /
`slots.raised["nswe"] = 35` raised) but **no 3-sided** variant, which a landing
needs (grass strands on its open sides, flat where it meets the structure).

Two-layer composite:
- **base** = the 4-sided grass tile of the tile's own biome -- grass strands on
  all four edges;
- **overlay** = the biome's flat `interior`, blitted over the base but **inset**
  on the side(s) that must stay grassy, so the base's strands peek out there and
  the flat top hides the rest.
- One `_three_sided(sheet, open_sides)` helper, cached. `open_sides` from the
  annex tile's own edge derivation in (b).
- Exact inset px / whether to offset instead of inset -> **spike** (like LD-4
  S0), the concept is confirmed.

### Decisions (from the user, 2026-08-29)

1. **Keep wide (`width_tiles = 2`) plank stairs**, but add
   `config.STAIR_WIDE_EVERY` (default **7**) so roughly one stair in seven is
   wide -- deterministic count, no RNG draw. A wide stair renders as **two
   plank-bridge strips side by side**, same bridge tile family as a corridor
   (touching is fine -- the user will make matching assets later). **Also fix:
   every non-ramp stair, 1-wide included, must render as a plank bridge** --
   `paint_stair` currently fills the strip with bare `interior` grass, which is
   the palette bleed in the screenshot.
2. **Plank stairs should read as terrain.** (a)+(b)+(c) is the interim approach
   until tiles that match the terrain better exist. The gap span is bridge
   planks; the room-adjacent tiles are owned + autotiled into their room.
3. **Grow each room surface to its annex bbox** (decision on U2's paint
   strategy).
4. **Corridor end-caps get ownership too**, so the plank-to-grass join fits the
   room it belongs to.

### Milestones

| | scope | done when |
|--|--|--|
| **U0** | **3-sided tile spike** (fix c). Hand-composite base + inset overlay for each `open_sides` combo, both a ground and a raised biome. | a synthesized N/E/W-open tile is indistinguishable from an authored 3-sided tile; screenshot |
| **U1** | **Ownership** (fix a). `_annex_structure_tiles`, `TileMeta` for every structure tile, `tile_at` returns them, `paint_stair` / LD-4 landings pick the per-tile sheet. **No shape change yet** -- tiles still autotile as isolated `interior`. | every structure tile has a `room_id`; a stair strip meeting a floor-0 room draws that room's ground sheet on the low half; flag-off byte-identical |
| **U2** | **Shape unification** (fix b), behind `config.STRUCT_ANNEX` (default off). `cells | annex` feeds `_mask_slot` / `raised_idx` / `lip` / `cliff`. `paint_room` draws annex tiles. | flag off -> baseline hashes unchanged; flag on -> a landing autotiles into its room with correct corners, and the room's adjacent edge cell drops its foam; suite green |
| **U3** | **3-sided tiles wired** (fix c). Annex tiles whose derived shape is 3-sided use `_three_sided`. | landings render with grass strands only on their open sides, flat toward the structure; screenshot matches the reference |
| **U4** | **Wide-stair + fallback dressing** (decision 1 / 2). | per the decisions; no bare 2-wide slab, no palette bleed anywhere |
| **U5** | **Playtest, screenshots, flag on, journal.** | live run crosses a plank stair and an LD-4 unit; both read as their own biome |

### Risks

- **(b) touches every raised-room edge.** Keep `annex` empty-by-default and
  assert it, so `_build_tile_meta` is unchanged for rooms with no structure
  tiles. Flag + A/B.
- **Annex tiles outside the room rect** break the assumption that
  `r.tile_meta` keys are inside `r.rect`. Audit every consumer of `tile_meta`
  (`tile_at`, `paint_room`, the LD-2/3/4 cliff code, tests) for that.
- **Determinism:** the annex pass must not draw RNG and must be order-stable
  (iterate `layout.stairs` / `corridors` in list order).
- **Ownership of the gap span** is arbitrary (-> high room). Revisit if a future
  system needs the exact floor under a mid-gap tile.

### Touch list (anticipated)

* **U0 / U3:** `world/map.py` (`_three_sided` helper + cache), a spike script.
* **U1:** `world/procedural.py` (`_annex_structure_tiles`, `TileMeta` for
  structure tiles, `WorldLayout.tile_at`), `world/map.py` (`paint_stair`,
  LD-4 landing sheet pick).
* **U2:** `game/config.py` (`STRUCT_ANNEX`), `world/procedural.py`
  (`_build_tile_meta` over `cells | annex`), `world/map.py` (`paint_room` annex
  pass).
* **Tests:** `tests/world/test_verticality.py` (new `AnnexTests`),
  `tests/rendering/test_terrain.py`.
* **No** new art. **Nothing** committed.

### Checklist

#### U0 - 3-sided tile spike -- DONE (2026-08-29)
- [x] Hand-composited: **interior tile** (flat, no strands) with a `band=15` px
      strip of the **4-sided grass tile** (`slots.raised["nswe"]`) blitted back
      over each open edge. First attempt inset the *overlay* instead and covered
      every strand -- the working order is flat base, strand strips on the open
      sides. All 10 `open_sides` combos read as a clean 3-sided tile, both a
      ground and a raised biome (`u0_three.png`).

#### U4 - Plank stairs render as bridges + wide-stair rate -- DONE (2026-08-29)
- [x] `config.STAIR_WIDE_EVERY = 7`. `_split_links` now draws `width = 2` from
      the **world rng** (`rng.random() < 1/every`) among 1-floor stairs whose
      smaller room is >= 4 tiles -- the old strict overlap/room-size gate only
      let ~1/7 of stairs even be *eligible*, so `1/7 of eligible` came out
      1/49. Measured: **1 wide per ~7.6 narrow** over 120 seeds.
- [x] `paint_stair` rewritten: a non-ramp `Stair` is a **plank bridge** (mouth
      to mouth + 1 tile into each room, `width_tiles` strips side by side, same
      bridge tile family as a corridor). It used to fill the strip with bare
      `interior` grass from one sheet -- which every stair crosses a floor
      boundary and 212/294 a room-kind boundary, so it always met a room in the
      wrong tone. That palette bleed is gone; a wide stair is two plank strips
      touching (fine per decision 1).
- [x] Foam: only under the gap planks (`cellr.colliderect` against **every**
      room rect, not just the two), and none at all when the low room is itself
      raised (E3 sky-bridge rule restored).

#### U1-U3 - Structure-tile ownership + shape + 3-sided -- DONE (2026-08-29)
- [x] `config.STRUCT_ANNEX` (**on** by default; off -> `Room.annex` empty and
      `tile_meta` / baked terrain byte-identical to LD-4).
- [x] `Room.annex: frozenset` -- room-relative coords of structure tiles the
      room owns outside `cells`. `_collect_annex(rooms, plan)` fills it for the
      two staircase-unit landings: top landing -> high room at row `rows_hi`
      (band row 0), bottom landing -> low room at row `-1` (band row 1).
- [x] `_build_tile_meta` derives `_is_south_rim` / `_cliff_variant` / `lip`
      over **`cells | annex`**; `paint_room` autotiles ground rooms over the
      same union. So the plateau rim cell above a top landing loses its
      `cliff="top"` and the plateau grass runs flat into the landing; a ground
      room's edge cell above a bottom landing drops its foam.
- [x] `three_sided(sheet, open_sides)` in `_build_tiles` (cached). The LD-4
      landing blits use it -- the top landing gets strands on the cut side
      (`+d`) + south, the bottom landing on the cut side (`-d`) + north; flat
      toward the stair and toward its room.
- [x] **Bug the annex introduced:** stripping `cliff="top"` from the
      top-landing column dropped it from `paint_cliff`'s `rim` list, so the
      landing stopped being painted (fully transparent -> the void). Fixed:
      `paint_cliff` appends any `unit` column missing from `rim` at the stair's
      row with a `mid` face.

#### U5 - Playtest + tests + flag on -- DONE (2026-08-29)
- [x] Live `PlayingState`: player crossed a **wide plank stair** (two strips,
      foam beneath, each room's own grass at the mouths, no bleed --
      `ld5_live_wide.png`) and walked an **LD-4 unit** end to end (5/5 tiles).
- [x] `tests/world/test_verticality.py` +5: `StructAnnexTests` (flag-off annex
      empty; flag-on folds the top landing into the plateau and clears its rim
      `cliff`; deterministic) and `PlankStairRenderTests` (wide rate ~1/7; a
      non-ramp stair bakes plank pixels, not bare grass). Suite 696 -> **701**.

### LD-5 as built (2026-08-29)

**Files:** `game/config.py` (`STRUCT_ANNEX`, `STAIR_WIDE_EVERY`),
`world/procedural.py` (`Room.annex`, `_collect_annex`, `_build_tile_meta` over
`cells | annex`, `_split_links` rng-driven width), `world/map.py`
(`three_sided` helper + cache, `paint_stair` rewritten as a plank bridge,
`paint_room` autotiles over `mask | annex`, `paint_cliff` paints unit columns
missing from `rim`, LD-4 landings use `three_sided`),
`tests/world/test_verticality.py` (`StructAnnexTests`, `PlankStairRenderTests`).

**Key mechanic:** a generation-placed tile in no room's `cells` mask now has an
owning room. A non-ramp stair is a plank bridge in the bridge tile family
(never bare grass in a mismatched sheet); a staircase-unit landing is folded
into its room's autotiled shape via `Room.annex`, so its edges connect flat and
it renders as a synthesized 3-sided grass tile of its own biome.

**Deferred:** plank-*corridor* end-caps still autotile as isolated `interior`
(decision 4 -- lower priority, corridors already read fine); a real 3-sided
grass tile in the sheet would replace the `three_sided` composite.

---

## LD-6 — Cliff-foot drop shadow & native-size cliff rendering

**Status:** COMPLETE (2026-08-29). Two rendering fixes, no generation change,
no new flag. Suite 707 -> **710**. `ld6_sea.png` (seam closed, no stretch),
`ld6_runend.png` (run end, no stretch), `ld6_shadow4.png` (continuous soft
shadow strip), `ld6_ramp.png` (LD-4 unit still renders).

### Why

Two problems the user flagged with screenshots:

1. **A cliff foot on solid ground had no grounding cue.** E8 already cuts the
   face flush when a lower room / bridge / stair covers the column, and caps it
   with a plain `body` tile (no foam). But nothing sat *below* the foot, so a
   cliff dropping onto a lower plateau looked like it was floating a pixel above
   it. The art pack ships a single static `shadow.png` (192 px, same rig shape
   as `terrain_foam`) meant to pool at the foot the way foam laps at a sea
   edge.
2. **E7's 64 -> 80 px tile scale stretched the cliff art.** E7 widened every
   face tile by `_CLIFF_SEAM_OV` (8 px per side) and blitted it at
   `col * px - ov` so adjacent columns' opaque cores overlapped and the
   inter-column hairline closed. The cost: the run's **void-facing outer
   edge** — the transparent side — was scaled outward too, so a `left` /
   `right` / `single` end column visibly smeared toward the transparent side
   (both side cliffs in the first screenshot, the left side only in the
   second), and the horizontal cut between two stacked rows no longer lined up
   cleanly because the whole tile was a non-integer scale.

### Cliff positions & the shadow rule

A rim column's foot is now classified into three cases (the user's "sea / above
another cliff / above ground"):

| foot lands on | face | foot art | shadow |
|---|---|---|---|
| **void (sea)** | full `face_h` | foamy `bottom.<var>` + `_cliff_foam` point | — |
| **a lower room floor** (`surface == "room"`, `floor < r.floor`) | cut flush (`draw_h = gk - 1`) | plain `body.<var>` cap | **`_cliff_shadow` point** |
| **a bridge / stair span** (`surface` in `{"corridor", "stair"}`) | cut flush | plain `body.<var>` cap | — |

"Above another cliff" is not a distinct code path — a lower cliff's rim belongs
to a lower room, so its floor tile is `surface == "room"` and the upper foot
gets a shadow, which is the intended look. Only a foot over the literal void
(`ground_k` returns `None`) gets foam.

`paint_cliff`, grounded branch:

```python
fx = r.rect.x + col * px
fyw = r.rect.y + (row + gk) * px
m = layout.tile_at(fx + px // 2, fyw + px // 2)
if m is not None and m.surface == "room" and m.floor < r.floor:
    self._cliff_shadow.append((fx, fyw))
```

### Rendering the shadow

`shadow.png` is loaded once (`terrain_shadow` rig in `data/terrain.json`,
`a.frames("terrain_shadow", "loop")[0]`) into `self._shadow`. It is **not**
animated and **not** part of the foam pass:

- **Foam** is drawn in the foam pass, before the room floor surfaces, because
  foam shows through the transparent water-side of an edge tile. A shadow sits
  on **solid ground** — if it were drawn there, the floor-0 room surface
  painted afterward would cover it. So the shadow blit moved to **after every
  floor pass** (after `self._corr_surfs`), before entities.
- The sprites are 192 px but rim columns are 64 px apart, so six overlapping
  semi-transparent blits stacked into lumpy over-darkened blobs. Fixed by
  accumulating onto a scratch `SRCALPHA` surface with
  `special_flags=pygame.BLEND_RGBA_MAX` (take the max alpha/channel per pixel,
  no additive stacking), then one plain blit of the scratch — one continuous
  soft strip regardless of how many feet contribute.

```python
if self._shadow is not None and self._cliff_shadow:
    sh_half = self._shadow.get_width() // 2 - config.TILE_PX // 2
    sview = view.inflate(self._shadow.get_width(), self._shadow.get_height())
    zsh = self._z_surf(self._shadow)
    vis = [(wx, wy) for wx, wy in self._cliff_shadow if sview.collidepoint(wx, wy)]
    if vis:
        scratch = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for wx, wy in vis:
            scratch.blit(zsh, ((wx - ox - sh_half) * z, (wy - oy - sh_half) * z),
                         special_flags=pygame.BLEND_RGBA_MAX)
        surface.blit(scratch, (0, 0))
```

`_shore` (the foam-point list) is filtered before the terrain bake: any shore
point within one tile of a shadow point is dropped, so a foot never shows both
foam and a shadow.

### Native-size cliff tiles + `mid` seam patch

E7's widen is gone. `face(idx)` returns `cell(sheet, idx)` at native 64 px;
tiles blit at `col * px` (no `- ov`). The inter-column hairline is now closed
by a **half-tile-offset `mid` patch**, not by overlap:

- `run_cols = {c for c, _ro, _v in rim}`.
- A column gets a patch only if it has a **right neighbour in the same run**
  *and* its own variant is opaque on the right: `seam_r = var in ("mid",
  "left") and (col + 1) in run_cols`. A `right` / `single` column is the run's
  east end and keeps its transparent outer edge untouched.
- For every row the column draws (`body`, `bottom`, the void foot, the LD-4
  unit's two bands), when `seam_r` the same-row **`mid`** tile (`body_mid` /
  `bot_mid`, precomputed once) is also blitted at `x + lap` (`lap = px // 2`).
  A `mid` tile is opaque on both edges, so its core straddles the 8-px
  transparent gap between the two columns' cores and the seam reads solid;
  offsetting it half a tile keeps its own edges away from the seam line.
- The LD-4 **staircase-unit** branch also switched its hidden cliff-behind
  layer from the old `left` / `right` end variants to `body_mid` / `bot_mid`
  — native tiles no longer overlap, so an end variant there left a void seam
  against the stair piece. The crevasse's finished edge comes from the
  landing's 3-sided grass, not that layer.

### Touch list (as built)

* **`data/terrain.json`** — `terrain_shadow` rig (1 frame, `fps: 0`).
* **`world/map.py`** — `self._cliff_shadow` list + `self._shadow` surface;
  `terrain_shadow` load; `paint_cliff` reworked (native `face()`, `seam_r` +
  `body_mid` / `bot_mid` patch, grounded-foot shadow point, unit branch uses
  `body_mid` / `bot_mid`); `_shore` filtered against shadow points;
  `_draw_tiled` shadow strip after the floor passes with `BLEND_RGBA_MAX`.
  Removed: `_CLIFF_SEAM_OV` constant + its E7 comment, the `wide()` scale
  alias, the dead `open_row` dict + `cut_var()` helper.
* **`tests/world/test_verticality.py`** — `CliffFootAndSeamTests` (3):
  shadow points resolve to `surface == "room"` and never coincide with a
  `_cliff_foam` point; no `_shore` cell under a shadow; an interior seam
  between two adjacent rim columns is opaque across ±6 px. Two earlier
  run-end-edge tests were dropped (wrong premise — a finished run end's outer
  edge is opaque *outline art*, not void; L-shaped rim rows gave false
  positives on a bleed check). `test_a_partly_covered_rim_column_keeps_its_full_face`
  gained an `edge_ok` guard so it skips the legitimately-transparent outer
  edge of a native `left` / `single` column.

### LD-6 as built (2026-08-29)

**Key mechanic:** a cliff foot that lands on a lower room floor gets a static
`shadow.png` pooled below it (rendered after all floor passes, merged with
`BLEND_RGBA_MAX` into one soft strip); a foot over the void still gets animated
foam; the two never coincide. Cliff face tiles are drawn at native 64 px — no
more E7 stretch toward the transparent side — and the inter-column seam is
closed by a half-tile-offset opaque `mid` patch on interior seams only, so run
ends keep their transparent outer edge.

**Determinism:** generation is untouched (no `WorldLayout` change, no RNG); the
baked terrain differs from LD-5 only in the added shadow strip and the
un-stretched cliff art, both unconditional rendering.

**Deferred:** a faint residual seam is still visible where a `mid` patch meets
the LD-4 ramp piece (`ld6_ramp.png`); a dedicated cliff-over-cliff tile (rather
than reusing the grounded-foot shadow) if the stacked-plateau look needs it.

---

## LD-6b — `_cliff_variant` picks the end cap by what abuts the face, not by rim kind

**Status:** COMPLETE (2026-08-30). Generation-only, `world/procedural.py`.

- **User report** (on a plus-shaped floor-1 plateau, seed 1 room 15): the last
  column of a south-rim run that sits *beside the plateau's own grass* — where
  the land wraps south past the drop-off (an L / stepped / cross edge) — was
  rendering as a `right` (or `left`) run-end: the rounded stone cap with a
  transparent outer margin and the dark curved outline, pulled back from the
  grass it butts against. "There is land on the right side, the cliff should be
  of type middle, not right facing."
- **Root cause.** `_cliff_variant` decided `left` / `mid` / `right` / `single`
  purely from whether the same-row horizontal neighbour was *itself a south-rim
  cell* (`_is_south_rim`). A neighbour that is floor but has floor below it
  (so it is not a rim) counted as "open", i.e. void — so a rim cell with solid
  plateau land immediately east/west of it still got a void-facing end cap.
- **Fix.** A side is **closed** (seamless solid `mid`-style edge) whenever the
  neighbouring column has floor at the rim row at all — `(col ± 1, row) in
  cells` — whether that neighbour continues the run or is the plateau's own
  land. A side is **open** (`left` / `right` / `single`, rounded cap with the
  transparent outer margin) only when it truly faces the void. `mid` now covers
  both a run interior and a rim cell butting land; `single` is a genuine 1-wide
  overlook with void on both sides.
- **Renderer unchanged.** `paint_cliff`'s `seam_r` half-tile `mid` patch keys on
  `(col + 1) in run_cols`, and a land neighbour is not a rim cell, so no patch
  is drawn toward it — the `mid` body/bottom tile is opaque to its own edge and
  meets the adjacent grass tile flush. The void-side run ends keep their
  transparent outer edge exactly as before.
- **Tiles keep native size** — no `pygame.transform.scale` in `paint_cliff`
  (the E7 64→80 px widen was retired in LD-6); the only scale is `_z_surf`'s
  uniform camera zoom. **Bottom feet over open water** still take the scalloped
  `bottom` (foam) variant + a `_cliff_foam` lap point via E8's full-width
  `ground_k`; the fix only changes which *edge* those feet use (`mid` against
  land instead of `left` / `right`).
- **Tests.** `test_raised_south_rim_is_a_seamless_left_to_right_run` rewritten
  to derive the expected variant from `(c ± 1, row) in r.cells` and to assert a
  rim-cell-butting-solid-land case is actually exercised across the 40 seeds.
  Full suite 710 green. `_layout_sig` / `_vert_sig` are unaffected (they hash
  rects / cells / obstacles / stairs, not `tile_meta`); the only thing that
  moved is `TileMeta.cliff_var` on L / stepped rim cells, and `tile_meta`
  determinism is still covered by `TileMetaTests.test_deterministic`.

---

## LD-7 — Cliffs are the lowest terrain layer + near-grounded fill

**Status:** COMPLETE (2026-08-30). Render-only, `world/map.py`. Generation and
`WorldLayout` untouched.

### Why

Screenshots (seed 5 especially) showed cliff faces **clipping on top of**
adjacent lower terrain: the dark grass fringe and scalloped foot of a rim
column bled over the green stair channel between two plateaus, over plank-bridge
ends, and over lower-room grass; and a higher plateau's skirt overhung a lower
floor's stair because it painted in a later per-floor pass. A 40-seed probe
found 134 cliff-skirt-vs-geometry overlaps. Root causes:

* **Draw order.** `_draw_tiled` painted, per floor ascending, `room -> that
  floor's cliff -> that floor's stairs`. A floor-2 cliff therefore drew after a
  floor-1 stair / room.
* **E8a.** `ground_k` cuts a column's face only where **all three** width probes
  hit a tile. Corridors / stairs / ramp channels are 64 px wide and not aligned
  to the plateau column grid, so a straddling rim column stays full-height and
  its uncovered half hangs over whatever the 64 px neighbour tile does not
  reach.

> **Point 3 (shadow layer) and point 4 (near-ground handling) below were
> revised the same day by LD-7a — the shadow anchor moved to the cliff-foot
> cell and draws *before* the cliff faces, and `near_ground_k` / `_cliff_fill`
> were replaced by `_cliff_underlay` + `_cliff_capped` (no gap filling). The
> full LD-7a write-up lives in `journals/assets_journal.md`.**

### What changed (user decision, 2026-08-30)

1. **Cliff faces paint before everything walkable.** New `_draw_tiled` order
   (as revised by LD-7a): water -> foam -> void decor -> `_cliff_underlay` ->
   drop shadows -> **all `_cliff_surfs` (one pass, floor-independent)** -> room
   floors (bottom floor up) -> `_stair_surfs` -> `_ramp_surfs` -> corridors. A
   cliff now shows only where it hangs over the void or over genuinely lower
   ground; any room / bridge / stair covers the stone where they meet.
   `_cliff_surfs` / `_stair_surfs` keep their `_fl` field (now unused at draw
   time; tests still unpack the 3-tuple).

2. **The LD-4 staircase unit is lifted out of the cliff surface.** `paint_cliff`
   still bakes the hidden `body_mid` / `bot_mid` cliff-behind into the cliff
   surface (so the crevasse never shows the sea), but the unit's own walkable
   tiles — the two 3-sided landings and the 1x2 stair piece — are collected and
   baked into a small per-room surface in the new `self._ramp_surfs`
   (`(blit_rect, surf, high_floor)`), drawn in the walkable-structure layer.
   Otherwise "cliffs under the room floors" would bury the landings.

3. **Drop shadows moved up one layer.** `self._cliff_shadow` was drawn dead
   last (after corridors); it now draws right after the room floors and
   `_cliff_fill`, **before** stairs / ramp units / corridors — so it still
   pools on the lower-room grass it belongs to but a bridge / stair / ramp
   crossing the cliff base is not darkened.

4. **Near-grounded cliff fill** ("if there are cliffs too close to a ground
   tile, just place another ground tile under the cliff and under the shadow
   even if the level layout doesn't show a path"). New `near_ground_k` in
   `paint_cliff`: a column that `ground_k` says drops into the void, but whose
   full width sits over a **lower room floor** within `_CLIFF_FILL_MAX` (2)
   tiles below the full face, is *near-grounded*. It draws a plain `body` foot
   (no scalloped `bottom`, no `_cliff_foam`), pours that room's `interior`
   grass into every void row of the gap as `self._cliff_fill`
   (`(rect, tile)`, painted with the room floors), and seeds a `_cliff_shadow`
   at the contact tile. The fill is cosmetic only — not in `Room.cells`, not in
   the nav layer. Genuinely open-water feet are unchanged (still foam).

### Tests

* `tests/world/test_verticality.py`
  * `test_cliff_foot_foams_over_void_and_grounds_over_a_tile` — added the
    `near` branch (a near-grounded foot asserts **no** foam).
  * `test_near_grounded_cliff_gap_is_grassed_not_foamed` (new) — every
    `_cliff_fill` tile is opaque grass and every filled seed also seeded a
    shadow.
  * `test_cliff_faces_paint_below_rooms_and_ramp_units_above` (new) — a blit
    recorder over `_draw_tiled`: last cliff blit precedes the first room blit;
    the first room blit precedes the first ramp-unit blit.
  * `test_the_unit_renders_its_three_parts` — landings are now read from
    `_ramp_surfs`, not the cliff surface; the cliff surface is still checked
    opaque across all six unit tiles (the cliff-behind).
* Full suite **714** green. Determinism unaffected (no `WorldLayout` / RNG
  change). `_CLIFF_FILL_MAX` is a `world/map.py` module constant.

### Deferred

* The `shadow.png` blob still reads a little hard-edged / large where a run of
  near-grounded columns each seed one; a dedicated soft strip could replace the
  `BLEND_RGBA_MAX` accumulation.
* N/E/W plateau rims still have no hanging face (only the south rim is skirted) —
  unchanged from LD-1.

---

## LD-8 — "Tiny Swords" world redesign (in progress)

**Goal.** Make generated levels read like the Tiny Swords overworld: large
irregular grass plateaus in a water moat, joined by narrow necks with **wide
water gaps**, cliff walls marking elevation, **grass / rock staircases** the only
way up or down, per-floor biomes, seeded houses and structures. Hard rule: **no
more than a 2-floor difference** between any two connected areas or a bridge.

### Plan (workstreams, each flag-gated so flag-off stays byte-identical)

| | scope | key touch points |
|--|--|--|
| **L8-1** | Bigger world, fewer + larger rooms, organic edge erosion (not just corner notches) | `config` (`CHUNK_SIZE`, `WORLD_ROOM_COUNT`, world size), `world/gen/rooms.py` (`_room_frac`, `_grow_rooms` default-on, a perimeter-inset pass), `tuning.py` |
| **L8-2** | Wider connections (`CORRIDOR_WIDTH_TILES` 2–3), bigger gaps; optional same-floor **grass causeway** instead of a plank bridge | `world/gen/__init__.py` (`width = px`), `links.py`, a `paint_causeway` |
| **L8-3** | Cap floors at 2; every cross-floor link is a **grass/rock staircase** (2-tall for a Δ2 drop), no plank stairs for elevation | `world/gen/graph.py` (`_assign_floors`), `verticality.py` (`_plan_ramps` Δ2, `_ramp_steps`), `links.py` (`_split_links`) |
| **L8-4** | Orientation-aware stairs: **N/S = rock stairs**, E/W = biome grass (future) | `world/layout.py` (`Stair.orient`), `verticality.py`, `world/terrain/cliffs.py`, `data/terrain.json` |
| **L8-5** | Per-floor **biomes** — grass sheet + tree/prop sets by floor | `data/terrain.json` (`biomes` block, `decorations.floors`), `world/gen/scatter.py`, `world/terrain/sheets.py` |
| **L8-6** | Biome-matched houses + kind-keyed **structures** (castle / tower / tents) | `world/gen/scatter.py` (`_scatter_houses`), `data/terrain.json` (`structures`) |

Decisions (resolved with the user, 2026-08-30):

1. **World size** — go with the suggested value for now, big enough to hold
   large multi-floor rooms.
2. **Plank bridges** — kept: used when two rooms are far apart, and as the
   fallback placeholder wherever a grassy staircase cannot be used.
3. **Floor 3** — kept, as a capped pocket. The verticality rule still holds:
   no jump greater than 2 floors between connected areas (no ground → floor 3).
4. **Biome trees** — reuse the tinted trees; match each tree's tint to its
   biome's palette and group the tree sets by biome.
5. **Structures** — placed as blocking `Obstacle`s, only in sufficiently large
   open spaces, following the existing placement rules; multiple buildings are
   clustered into a small village-like layout rather than scattered.

---

### LD-8a — rock N/S stair overlay + per-link style pick — ✅ DONE (2026-08-30)

First L8-4 slice. A cross-floor staircase unit now renders in **one of two
styles**, chosen per link:

- **grass** — the biome `slots.ramp` sideways tiles + 3-sided grass landings,
  exactly as LD-4 built them.
- **rock** — a single `vstairs.png` **overlay sprite** (1 walkable tile wide,
  2 tiles tall, with foliage wings) drawn on top of *all* terrain so its
  foliage feathers over the plateau grass, the cliff face and the low-room
  grass, hiding the unit's seams while the grass textures show through
  underneath.

**Part A — per-link style (seeded, render-only)**
- `world/layout.py` — `Stair.style` field (`"grass"` | `"rock"`, default grass).
- `game/config.py` — `RAMP_ROCK_BIAS` `{1:.35, 2:.8, 3:1.0}` + `..._DEFAULT .5`:
  the rock probability, keyed by the plateau's floor (higher floors lean rock).
- `world/gen/verticality.py` — `_ramp_style(seed, hi, lo, hi_floor)` rolls a
  private `random.Random(f"{seed}:ramp-style:{hi}:{lo}")` against the bias.
  `_plan_ramps` takes `seed`, its plan tuples grow a 5th `style` field, threaded
  through `_ramp_steps` (into the `Stair`), `_collect_annex`, `_build_tile_meta`
  and `world/gen/__init__.py`. No world-RNG draw → per-seed geometry byte-identical.

**Part B — the rock overlay sprite**
- `utilities/prep_vstairs.py` — one-shot: colour-keys the opaque backdrop of the
  user's re-crop (`vertical_stairs.png`, 582×595), crops the lower flight + both
  foliage wings, `smoothscale` → `assets/terrain/tiles/vstairs.png` (**192×128**,
  ~1-tile stone core + a foliage wing each side, SRCALPHA).
- `data/terrain.json` — `"vstair"` block simplified to `{ sheet, core_cols 1 }`.
- `world/terrain/sheets.py` — `vstair_overlay(band_tiles)`: the sheet scaled to
  `band_tiles` tiles tall (aspect kept), cached; `None` → caller renders grass.
- `world/map.py` — `GameMap._stair_overlays: list[(blit_rect, surf)]`.
- `world/terrain/cliffs.py` `paint_cliff` — a `rock` unit appends its sprite to
  `_stair_overlays` centred on the stair column; under it the stair column is
  filled with plain grass (plateau tone on the upper band cell, low-room tone on
  the lower) so the sprite's feathered edges reveal grass, never void. All three
  unit columns stamp the solid `body` mid tile at a half-tile stagger across both
  band rows (was `body_mid` + scalloped `bot_mid`) so no row seam leaks the void.
- `world/terrain/render.py` — `_draw_tiled` blits `_stair_overlays` last, after
  the corridors.
- Render-only, no flag: `Stair.style` + `vstairs.png` presence are the switch.
- Tests: `test_ramp_units_render_as_rock_overlay_or_grass_by_style` (rock → a
  `_stair_overlays` sprite, stone centre; grass → a `_ramp_surfs` entry, no
  overlay; both styles seen across 40 seeds), `test_vstair_overlay_sprite_is_a_
  real_srcalpha_file`. Full suite **730** green.

**Deferred**
- E/W (side-by-side) cross-floor links are not produced yet, so a `grass` unit is
  still the LD-4 N/S sideways ramp; the true E/W biome set is L8-4's other half.
- Δ2 links still fall through to a plank `Stair` (`_split_links`) — L8-3's job.

---

### LD-8b — per-level terrain compositing — ✅ DONE (2026-08-30)

`world/terrain/render.py` `_draw_tiled` used to paint globally by *type*: all
cliff underlay, then all cliff faces, then room floors bottom-up, then all
stairs / ramps / corridors / overlays. It now paints one **elevation at a
time**, bottom up:

    water + sea shoreline foam + open-water scenery      (base, once)
    for f in sorted(floors):
        cliff-foot foam over open water  (floor f)
        LD-7a cliff-foot underlay grass  (floor f)
        LD-6 contact drop shadow         (floor f)
        cliff faces                      (floor f)
        room grass                       (floor f)
        plank stairs / ramp units / corridors / rock stair overlay  (floor f)

So a higher floor's cliff wall is always painted onto the *finished* floor
below it. Every per-floor container gained a floor tag: `_corr_surfs` and
`_stair_overlays` grew a 3rd element in `world/map.py` / `world/terrain/cliffs.py`;
`_cliff_underlay` / `_cliff_foam` / `_cliff_shadow` grew one in `paint_cliff`
(the raised room's own floor). `_cliff_surfs` / `_stair_surfs` / `_ramp_surfs`
already carried it.

Test `test_cliff_faces_paint_below_rooms_and_ramp_units_above` →
`test_map_composites_one_floor_at_a_time`: within a floor `underlay < faces <
grass < ramp`, and a lower floor's grass paints before the wall above it.

---

### LD-8a Phase 1 — stair orientation is a generation property — ✅ DONE (2026-08-30)

Per the "generate the stair as vertical / horizontal, *then* pick the asset"
decision. Every cross-floor link the generator makes today is N/S-stacked, but
the LD-4 unit modelled it as a **sideways** E/W ramp (`slots.ramp` tiles,
landings at `c0±d`), whose start/end tiles leaked around the rock overlay.

- `world/layout.py` — `Stair.orient` (`"v"` | `"h"`, default `"v"`); `ramp`
  value is now `"s"` for a vertical unit, `"w"`/`"e"` for a horizontal one.
- `world/gen/verticality.py`
  - `_ramp_candidates` yields `(hi, lo, "v")` — still only stacked pairs; the
    `"h"` classification is reserved for L8-4's E/W half.
  - `_plan_ramps` plan tuple → `(hi, lo, col, orient, direction, style)`. The
    footprint is still probed 3 columns wide, so **per-seed `col` is unchanged**.
  - `_ramp_steps` — a `"v"` unit is a straight 3-rect chain in column `col`
    (approach 2 into the plateau / the flight spanning the band / approach 2
    into the low room), `axis="v"`; `"h"` keeps the LD-4 5-rect chain.
  - `_collect_annex` — `"v"` annexes only the low room's landing cell; the
    flight's own rim cell stays a south rim so `_build_tile_meta` can tag it
    (the tag alone suppresses the cliff fringe there).
- `world/terrain/cliffs.py` `paint_cliff` — reads `Stair.orient`. A `"v"` unit
  builds `unit = {c0: stair}` only; the flight column is filled with the biome
  grass (plateau tone above, low-room tone below), plus the `vstairs.png`
  overlay when `style == "rock"`. No sideways landings. The `"h"` branch (dead
  until E/W links exist) still holds the LD-4 landing code.

Determinism: flag-off worlds byte-identical; per-seed vertical layout changes
once (3 straight rects replace the 5-rect ±d chain). ~6 `RampTests` /
`StructAnnexTests` rewritten for the straight chain. Full suite **730** green.

---

### LD8-0 — vertical grass flight tile — ✅ DONE (2026-08-30)

Phase 1 left a `"grass"` `"v"` flight as a flat `interior` fill, so it read as
invisible grass through a gap in the cliff. The tilesheet has no authored N/S
ramp (slots 37/38/40/46/47/49 are blank; the only slope art, 36/45 + 39/48, is
diagonal E/W), but `strip_v` — idx **3 / 12 / 21** — is an authored **vertical
grass channel**: grass with a dark bush fringe down the left and right edges.

- `data/terrain.json` — `slots.ramp` gains `"s"`. First `[12, 12]` (the plain
  `strip_v` mid tile); LD-8 #1/#2 changed it to `[3, 21]` -- the top and bottom
  `strip_v` caps, which carry the dark navy + white-foam **cliff-outline
  border** so the channel merges into the flanking stone.
- `world/terrain/cliffs.py` — a `"grass"` `"v"` flight now paints
  `ramp_slots["s"]` (plateau sheet on the upper band cell, low-room sheet on
  the lower) instead of `interior`. `"rock"` flights keep the plain `interior`
  fill under the `vstairs.png` sprite.

Data-only + one render branch; no layout / RNG change, no new test churn. Full
suite **730** green. Result: the grass flight reads as a bush-lined grassy path
cut straight down through the rock wall, flanked by the stone cliff faces.

---

### LD-8 #1/#2 — flatter elevation + two-floor links + layout choice — ✅ DONE (2026-08-30)

**#2 elevation model.** `config.CLIFF_TILES` 2 → **1**: one cliff tile per
floor, and the plateau face height is now the floor number **uncapped** --
`_face_h` / `paint_cliff` / `map.py` drop the `min(floor, 2)` cap, so a floor-3
plateau has a 3-tile face and floor 3 sits one tile above floor 2. A cross-floor
link drops 1 tile (Δ1) or 2 (Δ2). Every `min(floor,2)*CLIFF_TILES` in the tests
became `floor*CLIFF_TILES`.

**#1 two-floor links + per-link layout.**
- `world/gen/verticality.py` `_plan_ramps` — accepts `hi.floor - lo.floor` in
  `(1, 2)` (was `== 1`); `drop = df * CLIFF_TILES`; the snap allowance scales
  with the drop (`RAMP_SNAP_TILES` per floor). `_ramp_candidates` yields
  `(hi, lo)` and the layout is a seeded roll: `_ramp_layout` → `"h"`
  (`config.RAMP_LANDING_BIAS`, 0.4) or `"v"`. The `fits` probe checks the
  approaches at the centre column for `"v"`, one column out for `"h"`.
- `_ramp_steps` / `_collect_annex` / `paint_cliff` — a `band` of 1 or 2 rows
  everywhere the unit was hard-coded to 2. `"v"` grass uses `ramp_slots["s"]`
  (`[21]` for a 1-tile drop, `[3, 21]` for 2); `"v"` rock uses
  `sheets.vstair_overlay(band)` (the sprite scaled to 1 or 2 tiles); `"h"` is
  the LD-4 wedge (`ramp_slots[direction]`) + 3-sided landings, band-scaled.
- rock is the straight-`"v"` sprite only -- an `"h"` unit is always
  `style = "grass"`.
- Determinism: flag-off byte-identical; per-seed vertical layout changes
  (shorter bands, the layout roll). ~8 `RampTests` / `StructAnnexTests`
  rewritten to be layout- and band-aware. Full suite **730** green.

Provisional: `CLIFF_TILES = 1` is flagged in `config.py` -- raise back toward 2
if a 1-tile ledge clips character sprites.

---

## LD-9 — rooms are height maps (in progress)

**The reframe.** Stop modelling the map as separate floors and model it as
*levels within one continuous map*, where cliffs are natural barriers that sell
verticality as y grows. A room stops being "one `floor` int + a cliff band
hanging off its south rim" and becomes a **per-cell height map**: generation
emits a grid, rendering is a pure function of it. This is the machine form of
the ASCII layouts the user writes.

### Phase A — the grid + generator — ✅ DONE (2026-08-30)

- `world/layout.py` — `Cell(kind, level, drop, row, tag)` plus the `GROUND` /
  `CLIFF` / `VSTAIR` / `EWSTAIR` / `LAKE` / `VOID` names and `WALKABLE_KINDS`.
  `level` is always the *upper* surface a cell belongs to; `row` indexes a
  cliff / stair cell down its own stack so the renderer never re-derives it.
- `world/gen/heightmap.py` — new. `build_grid(mask, cols, rows, rng, base)`:
  1. `_plan_levels` picks terraces bottom-up, stepping 1 or 2 levels while
     there is level headroom (0..3) and row budget.
  2. `_wander` gives each wall a clamped random walk so it reads as a ridge.
  3. `_settle_walls` alternates a smoothing pass (a wall never steps further
     between columns than it is deep — otherwise upper ground would touch
     lower ground with no stone between) with an ordering clamp (walls cannot
     cross and squeeze a terrace out of existence).
  4. `_plan_stairs` *finds* crossings that already fit the settled wall rather
     than forcing the wall to fit them — flat across three columns for a
     straight flight, a one-row jog for an east/west one (`# > =` over
     `= > #`, exactly the journal's diagram, generalised to a Δ2 wall as a
     three-row flight).
  5. `_face_the_sea` — no floating ground: a terrace cell with open sea south
     grows a wall under it, capped at two tiles.
  6. `_repair_links` cuts extra straight flights until the room is one
     connected piece; `_prune_unreachable` voids anything still stranded.
- `walk_links` is the single source of truth for connectivity: ground joins
  same-level ground; a flight joins the terrace at its head and the one at its
  foot; an east/west flight additionally opens sideways at each end (its entry
  and exit tiles) as well as along its column.
- `check_grid` asserts every invariant — no floating ground, no two levels
  touching without a wall, no flight open sideways onto the wrong level, drops
  never over two, everything reachable. **0 violations over 60 plain rooms and
  60 eroded ones.** `to_ascii` dumps a grid in the journal's own notation.

### Still to do

- **B** wire `build_grid` into `generate_world`; fewer, bigger rooms
  (~14-22 tiles a side, ~6-9 per world); inland lakes; between-room links.
- **C** render from the grid; retire `paint_cliff`'s rim-band machinery
  (`_cliff_underlay` / `_ramp_surfs` / `_stair_overlays` collapse into one pass).
- **D** nav + collision read the grid (`WALKABLE_KINDS`, `walk_links`).

### Phase B1 — wired into generation — ✅ DONE (2026-08-30)

Behind `config.HEIGHTMAP_ROOMS` (default **off**), so the LD-8 renderer keeps
working and flag-off layouts stay byte-identical until Phase C lands.

- `game/config.py` — the flag plus its sizing: `HEIGHTMAP_CHUNK_SIZE` 1280,
  `HEIGHTMAP_ROOM_COUNT` 8, `HEIGHTMAP_ROOM_TILES` (14, 22),
  `HEIGHTMAP_STAIRS_PER_WALL` 2, `HEIGHTMAP_LAKES` 1. Fewer, far larger rooms:
  a room now has to hold several terraces *and* the walls between them.
- `world/layout.py` — `Room.grid`.
- `world/gen/__init__.py` — `_build_room_grids` calls `build_grid` per room,
  then re-derives what the rest of the engine reads: `cells` becomes the
  walkable subset (so collision and the nav grid need no changes at all) and
  `floor` collapses to the room's base level, which is all the palette lookup
  still wants. `_grid_tile_meta` projects `TileMeta` straight off the grid --
  no rim/lip derivation, which is the point of LD-9.
- `world/gen/heightmap.py` — `_carve_lakes`: floods blobs of a terrace, and
  backs a lake out again if it touches anything but its own terrace's ground or
  would cut the room in two.

Measured over 20 generated worlds: 8 rooms each, 15-22 tiles a side, 3-4 levels
per room, **0 grid violations**, and generation is deterministic per seed. Full
suite **730** green (flag off).

**Known gap, B2.** Cross-room corridors do not yet match levels: of 140 corridor
ends, 37 land on equal levels and 103 do not (65 of them level 0 against level
3 -- a room's north edge is its *highest* terrace while its south edge is its
base, so a vertically stacked pair meets 0 against 3). Cliffs in this tileset
only face south, so a room's levels must descend northward; the fix is to cap a
room's top terrace where a north link attaches and carry the remaining
difference on a cross-room stair, the way LD-8's `_plan_ramps` did.

### Phase B2 — cross-room links — ✅ DONE (2026-08-30)

Rooms are islands in open sea, so the cliff rules govern *contiguous land*; a
bridge between two islands may span levels the way a real bridge does. What
must hold is the standing two-level cap and that both mouths land on ground.

- `world/gen/heightmap.py` — `build_grid(..., top=)` caps the highest terrace.
- `world/gen/__init__.py` `_build_room_grids` — cliffs only face south, so a
  room's terraces descend northward: its south edge is the base level and its
  north edge its summit. A bridge dropping onto a room's north edge therefore
  meets that room at its summit, so any room entered from the north has its
  summit capped at two.
- `_seat_corridors` — slides each bridge along the rooms' shared edge until
  both mouths land on walkable ground, preferring a lane where the two ends are
  at the same level. A height-map room's edge is no longer uniform floor (it may
  be cliff, or lake, or a terrace met side-on), so the lane the tree picked
  before the grids existed has to be re-seated against them.

Measured over 20 worlds: **0 mouths on non-walkable ground** (before: several),
73 of 140 same-level (before: 37), and every remaining span is 1 or 2 — the
Δ3 mouths, 65 of them, are gone.

### Phase C — rendering from the grid — ✅ DONE (2026-08-30)

- `world/terrain/grid_paint.py` — new, and it is now the whole terrain painter
  for a room: one pass over `Room.grid`, one tile per cell. It replaces the LD-8
  arrangement where the floor, the cliff band, the band's underlay, the drop
  shadow and the ramp units were five collections stitched together in a fixed
  order by `_draw_tiled`. Generation already decided every cell's kind and
  level, so rendering derives nothing.
  - a side counts as **open** (grass fringe / shoreline edge) only where the
    neighbour is water or void, or where it is the *south* side looking over
    this terrace's own drop. A cell at the foot of a wall keeps its north side
    flat -- the stone stands on it, and a fringe there would read as a beach
    running under the cliff;
  - a cliff cell is underlaid with the terrace it drops onto, because the
    run-end face variants keep their outer edge transparent and would otherwise
    show the sea straight through a wall standing on land;
  - `vstair` paints the grass channel and, when "rock", the stone sprite over
    it; `ewstair` paints the biome wedge; `lake` paints nothing at all, so the
    world's water buffer shows through as real water.
- `world/terrain/sheets.py` — `vstair_sprite(drop)` picks `vstairs_1` /
  `vstairs_2` (authored per depth rather than one rescaled, so the steps stay
  square); `data/terrain.json` `vstair.sheets` maps them.
- `world/map.py` — `_grid_surfs`, and `_finish_tiles` factored out so the water
  buffer, drop shadow, foam frames and scenery scatter are shared by both
  painters, which differ only in how the land is baked.
- `world/terrain/render.py` — with `_grid_surfs` set, the only ordering left is
  between rooms: south-first, so a room lower down the map overlaps the one
  above it, the same way its own terraces do.
- `config.HEIGHTMAP_CHUNK_SIZE` 1280 -> 1984: the largest room (22 tiles =
  1408 px) was wider than its chunk, so neighbours fused instead of staying
  islands.

Full suite **730** green with the flag off.

### Still to do

- **D** nav + collision from the grid. `Room.cells` is already the walkable
  subset so both work, but neither yet knows a flight is the *only* way
  between two terraces -- they treat the whole room as one connected floor.
- Obstacle scatter is unaware of terraces and can drop trees onto a flight.
- Level 3 uses the teal sheet, which reads oddly as the highest ground.
- Walls wander only one row (`JITTER`); the terraces still read as bands.

### Phase C1 — tile corrections + wider rooms — ✅ DONE (2026-08-30)

Three corrections from a screenshot review.

- **The vertical pathway used the wrong tile.** `slots.ramp.s` was `[3, 21]`,
  the `strip_v` pair -- white shoreline outline, and capped top and bottom so a
  one-tile flight rendered as a lone "bottom" tile. It is now `[17, 17]`:
  `slots.raised.we`, the grey cliff-fringed vertical channel, continuous at any
  depth. A Δ1 flight is one of them, a Δ2 flight two.
- **A lip run needs corners where it ends.** `_edges` now states the rule
  plainly: water and void are edges anywhere; a cliff *at this cell's own
  level* is this terrace's wall, so the terrace stops against it; a cliff at a
  higher level is standing on this cell, so the ground runs flat beneath it;
  a flight is never an edge. `_open_sides` then adds the corner: where a
  neighbour along the run has no lip -- at a flight cut through the wall, or
  where the wall jogs -- the facing side opens too, picking the `sw` / `se`
  tile so the fringe turns rather than stopping in mid-air.
- **Rooms read as one long staircase.** They are now markedly **wider than
  tall** (`HEIGHTMAP_ROOM_COLS` 24-34 against `HEIGHTMAP_ROOM_ROWS` 14-20):
  height only buys more of the same climb, width buys room for several separate
  ways up on the same wall. `HEIGHTMAP_STAIRS_PER_WALL` 2 -> 4, and the chunk
  grew to 2560 so the widest room still leaves a water gap.

Over 20 worlds: 0 grid violations, 3.1 terraces per room, and both flight kinds
common (1221 straight cells, 758 east/west). Full suite **730** green.

**Not done: the coastline.** A level-0 shore ring right around a room is not
compatible with this tileset, and the reason is worth recording. The cliff art
is south-facing only (`slots.cliff` is a horizontal run with left/mid/right
ends), so a room's levels must decrease northward -- which makes its north edge
the summit and its south edge the base. A ring would put level 0 north of a
raised terrace, and the boundary there faces *north*, which there is no tile
for. Either the terraces stay banded, or the sheet needs north/east/west facing
cliff faces.

### Phase C2 — coastline — ✅ DONE (2026-08-30)

The earlier note said a shore ring was impossible without north-facing cliff
art. That was answering the wrong question. What the coastline needs is not a
level-0 ring but an **irregular outer margin**: every terrace simply reaches a
different distance out on every row, so the island's silhouette wanders. No new
art at all, because a terrace's east and west edges are grass meeting open
water -- which `slots.raised` already draws. Only a *southward* drop needs a
cliff face, and the bands still run that way.

- `world/gen/heightmap.py` `coast_mask(cols, rows, rng, margin)` -- one clamped
  random walk of inset per side. `_walk` holds each value for a run of 2-4
  instead of stepping every column: stepping every column gave a comb of
  one-tile spikes, holding gives headlands and bays. `_despike` then trims
  until no tile clings on by a single side, since a one-tile peninsula reads as
  a rendering fault and is too narrow to walk anyway.
- `world/gen/__init__.py` -- replaces the tree's corner-bite shape with the
  coast mask. `config.HEIGHTMAP_COAST_MARGIN` 4.

Terraces no longer all begin and end in the same column, which is what made the
rooms read as a fixed staircase. 0 grid violations over 20 worlds; suite green.

### Phase C3 — bays, wandering coast, bridges that reach — ✅ DONE (2026-08-30)

**Why a bridge could end in open water.** `paint_corridor` derived the plank
span from the two rooms' *rects*. Once the coastline started wandering inside
the rect, the land it was supposed to land on had receded two to four rows, so
the bridge stopped short and hung over the sea. `_seat_corridors` now scans
inward from each rect edge for the first walkable cell (`reach`) and stretches
the corridor rect coast to coast, overlapping one tile into the land at each
end; `grid_paint.paint_bridge` tiles the planks along that rect, so the rect
*is* the bridge. This also fixes collision, which reads the same rect. 138 of
140 bridges re-seat; the two that cannot are pairs whose shared span has no
column with land on both sides.

**The west coast was a straight line** because `_walk` was a free random walk:
it drifts to one end of its range and then hugs it. The step is now pulled back
toward mid-range, so the inset oscillates instead of drifting.

**`_carve_bays`** bites a few bays into the coast so the *terraces* come out
ragged, not just the island's outline. Each bay starts on the shore and eats
inward, so it opens onto the sea rather than leaving a landlocked hole -- that
is what a lake is for -- and is rolled back unless the island stays one piece.
A bay reaching across a terrace narrows it to a neck, which is where a wide
lower floor with a slim path above it comes from.

0 grid violations over 20 worlds; suite **730** green.

### Next

- A bridge *inside* a room, spanning a bay between two stretches of the same
  terrace -- the gap at the top of the reviewed screenshot.
- **D**: nav and collision still treat a room as one flat floor, so enemies
  path through cliffs instead of using the flights. This is the real blocker
  on turning the flag on.

### Phase C4 — the shore ring — ✅ DONE (2026-08-30)

The earlier entry claimed a shore ring needed north-facing cliff art. That was
wrong, and the mistake is worth keeping: **only the *southern* face of a rise
is ever seen.** Looking from the south you see the wall there; on the other
three sides you are looking at the plateau's grassy back or flank, which the
`slots.raised` edge tile already draws. So the island can be ringed in
sea-level ground and rise inward with no new art at all.

- `build_grid(..., shore=n)` erodes the mask by `n` to get a core, terraces the
  core, and fills the ring with sea-level ground.
- **Order matters**: the wall goes in before the beach. A terrace reaching the
  core's southern edge needs its face built into the ring first; the sand then
  fills only what is left. Filling the beach first put sea-level ground
  directly below raised ground and the drop lost the very wall that sells it
  (1649 violations).
- `_wall_flight_sides` puts stone back beside any flight the beach opened up --
  eroding the core can take away the wall a flight was cut into, leaving a
  staircase you could step onto sideways, halfway down (127 violations).
- `check_grid` now only requires a wall on a **southward** drop; a rise to the
  north, east or west is legal and unwalled.
- `MAX_LEVEL` 3 -> 2: sea level plus two floors, as the ASCII diagrams show.
- `reach` (bridge seating) now demands plain **ground**, not merely a walkable
  cell -- a bridge was landing on a flight, its planks meeting the middle of a
  staircase.
- Erosion is now guarded twice: `coast_mask` retries with a smaller margin, and
  `_build_room_grids` judges the *finished* grid and backs the coast off until
  the island is worth calling one. Before, the four insets plus bays plus
  de-spiking could compound down to a dozen tiles, leaving bridges running to
  almost nothing (min fill was 2%; now 51%).
- Rooms grew a long way and the count fell to pay for it (36-50 x 22-30 tiles,
  6 per world, 3712 px chunks): a room has to hold a shore ring, several
  terraces and the walls between them, and the coast erodes it further.

0 grid violations over 20 worlds, no room under 150 ground cells, average fill
64%. Suite **730** green.

### Phase C5 — granularity + crevasses, both tunable — ✅ DONE (2026-08-30)

Upper terraces read as slabs of grass because the wall between two of them
barely moved. Two knobs now shape that, both in `game/config.py`:

- `HEIGHTMAP_WALL_WANDER` / `HEIGHTMAP_WALL_STEP` -- how far the wall strays
  from its nominal row and how fast it may move between neighbouring columns.
  Together they set how granular a terrace edge is: 1/1 gives smooth bands,
  higher values a broken ridge.
- `HEIGHTMAP_CREVASSES` (+ `_DEPTH`, `_WIDTH`) -- fingers of the *lower*
  terrace driven up into the one above. Wandering alone only ripples the
  boundary; a crevasse is a deliberate incursion, a bay of the lower floor
  biting into the higher one, tapered at the ends so it reads as an inlet
  rather than a slot.

The unlock was retiring the old `|Δ| <= depth` limit on how far a wall could
move between columns. That existed because a big sideways step left upper
ground touching lower ground with no stone between -- which, since Phase C4,
only matters on a *southward* drop. East and west the plateau shows its flank,
drawn by its own edge tile. Lifting the limit is what lets a crevasse cut in
sharply instead of as a shallow V. `_settle_walls` keeps only the ordering
clamp, which stops a crevasse swallowing the terrace above.

Defaults settled at wander 2 / step 1 / 4 crevasses of 1-3 rows: depth 5 ate
whole terraces. 0 grid violations over 20 worlds; suite **730** green.

### Phase C6 — bridges, properly — ✅ DONE (2026-08-30)

Three rules, and one real bug behind most of the mess.

**The bug: `reach` was reading a transposed cell.** Grid keys are `(col, row)`,
but the scan built its key as `(fixed, idx)` regardless of axis. A *vertical*
bridge holds the column and scans rows, so that was right by luck; a
*horizontal* one holds the row and scans columns, so every lookup landed on a
completely different cell. Horizontal bridges were therefore seated against
cells chosen at random -- which is why they started in open water. `reach` now
takes the axis and keys `(idx, fixed)` for "h", `(fixed, idx)` for "v".

**Rule 2, end caps square on the ground tile.** Room rects were centred in
their chunk, so a room of odd tile-width sat half a tile off the world grid and
no two rooms shared one -- a bridge could not land square at both ends. Rooms
are now snapped to the global grid, and `_grow_rooms` / `_carve_room_shapes`
are skipped entirely in the height-map path: the coastline overwrites `cells`
anyway, and the growth pass was moving rects back off the grid.

**Rule 3, bridges belong on the shore.** `reach` takes the *first* land the
scan meets, so it can never strike inland, and it now requires plain ground at
**sea level** -- it will not run up onto a terrace or stop on a cliff top. If
no lane at all offers a beach on both sides it retries without the sea-level
demand, since a bridge onto raised ground still beats one hanging over water.

**Rule 1, any island will do.** The lane search covers the whole span either
room reaches rather than only where the two rects overlap, and prefers the
shortest crossing among the lanes that work.

Over 20 worlds, 100 bridges: **100/100 tile-aligned to both rooms, 100/100 with
both mouths on ground** (was 55), 75/100 with both on the shore. 0 grid
violations; suite **730** green.

### Phase C7 — volcano islands: concentric plateaus — ✅ DONE (2026-08-30)

Terraces as north-to-south **bands** made every island read as one long
staircase, however irregular the boundary got. Replaced with concentric caps:
the island is sea-level ground all over, a smaller irregular plateau sits on
top of it, and a smaller one again on that -- a mountain.

- `_cap(below, rng)` erodes the plateau below it, **harder from the south than
  the north** (`CAP_INSET_S` 5 against `CAP_INSET_N` 1), then roughens the rim.
  The asymmetry is the whole trick: each cap hugs the island's back, so the
  rims stack into a slope facing the camera instead of a dome.
- `_raise_walls` gives every southward drop its cliff, consuming cells from the
  terrace below exactly as the band walls did. East, west and north faces get
  no cliff -- they are the plateau's flank and back, which `slots.raised` draws.
- The sea-level ring is never built on, so a walkable shore runs right round
  every island. That is what lets **bridges meet sea level only**: a mouth is
  always there to be found and no bridge ever reconciles a height difference.
  100/100 bridges now land on shore at both ends.
- `_cut_flights` **finds** stair sites by scanning the finished grid instead of
  planning against a row of wall, since concentric caps have no such row. All
  four of the tileset's stairs are placed: straight in stone, straight in
  grass, and the east/west grass flight either way. `_link_levels` then cuts
  more until every plateau is reachable.
- Not every island is a mountain: `HEIGHTMAP_VOLCANO_CHANCE` (0.65) leaves the
  rest plain one-level ground, so the world mixes silhouettes.

Retired with the band model: `_plan_levels`, `_split_rows`, `_wander`,
`_crevasses`, `_settle_walls`, `_plan_stairs`, `_stamp_stairs`, `_repair_links`
and their config. Kept and unchanged: `check_grid`, `walk_links`, `coast_mask`,
`_carve_bays`, `_despike`, `_carve_lakes`, `_face_the_sea`, `_prune_unreachable`
and all of `grid_paint` -- which is why this was a contained rewrite.

One bug worth recording: `_face_the_sea` has to run **again at the very end**.
Carving lakes and pruning stranded pockets both take cells away, and any of
them may have been the ground a plateau stood on; without the second pass 36
cells of floating ground survived into the shipped grid.

Over 20 worlds: 0 grid violations, 72 volcano / 48 flat islands, all four stair
types in use (117 stone, 120 grass straight; 608 east/west). Suite **730** green.

### Phase C8 — the cap knobs live in config — ✅ DONE (2026-08-30)

The band model's tuning (`HEIGHTMAP_WALL_WANDER` / `_STEP`, `HEIGHTMAP_CREVASSE*`)
described a wall row wandering across columns and has no meaning for concentric
caps, so it went with the bands. Its replacements were left as module constants
in `heightmap.py`, which is not where anyone would look for them. They are now
in `game/config.py` alongside the rest:

- `HEIGHTMAP_CAP_INSET_S` / `_N` / `_W` / `_E` -- how far each plateau steps in
  from the one below, per side. **South is the one that matters**: it is the
  only face the camera sees, so raising it lengthens the visible climb, while
  raising north flattens the mountain toward a dome.
- `HEIGHTMAP_CAP_ROUGHNESS` -- chance a rim cell is nibbled away. 0 gives smooth
  contour lines, higher values a broken rocky edge. This is the granularity
  dial the wall wander used to be.
- `HEIGHTMAP_CAP_MIN_CELLS` -- below this a plateau is not worth having and the
  stack stops, which is what decides how often an island gets a summit at all.

Threaded through `build_grid(cap_inset=, cap_roughness=, cap_min_cells=)` and
`_cap`. Swept over 12 worlds each, 0 grid violations at every setting.

### Phase C9 — crossings placed per region — ✅ DONE (2026-08-30)

Whole stretches of rim -- the north-east and north-west especially -- came out
with no way up. Not a geometry problem: `_cut_flights` spent a flat island-wide
quota drawn from one shuffled pile, so on a large island the crossings clustered
wherever the shuffle fell and the rest of the coast simply lost the draw.

Sites are now bucketed into a coarse grid of **regions** and each region gets
its own quota, which guarantees every part of the coast has crossings of its
own. `HEIGHTMAP_STAIRS_PER_REGION` (2), `HEIGHTMAP_STAIR_REGION` (8 tiles) and
`HEIGHTMAP_STAIR_SPACING` (4) replace `HEIGHTMAP_STAIRS_PER_WALL`.

Also: where a cell offered both a straight and an east/west flight, the
straight one always won, because the scan `continue`d on the first match. Both
are collected now and one is chosen at random, so the mix is honest.

Over 20 worlds: 773 flights -- 250 east/west descending west, 244 east, 153
straight grass, 126 straight stone -- and 182 of them in the northern half
(previously the north was routinely empty). 0 grid violations; suite **730**
green.

A structural note for later: the north can never be as dense as the south,
because a cap's north edge is its *back* and gets no cliff, so there is nothing
to cut through. The flights that do appear up there sit on the zigzag
south-facing segments of the cap's east and west flanks.

### Phase C10 — side stairs in the north — ✅ DONE (2026-08-30)

Split an island in half horizontally and the north had almost no **side**
stairs, specifically on the ground-to-first-floor boundary. Counted over 16
worlds, the gap was stark and specific:

    north side 1->0    21        south side 1->0   201
    north side 2->1    54        south side 2->1    25

So it was not "the north has fewer stairs" in general -- 2->1 is actually
*better* up there, because a level-2 cap's southern arc sits in the middle of
the island. It was the **0->1 boundary** that was missing, and only in the
north, because a cap's north edge is its back and grows no cliff. The one
south-facing 0->1 wall the north can have is a canyon head.

Two fixes, and the first was a mistake worth recording:

1. **Step the canyon head.** A flat run of wall only ever fits a *straight*
   flight; an east/west one needs the wall a row lower on one side than the
   other. Pushing one column of the head a row further north creates that jog.
   On its own this made things **worse** -- straight flights at heads collapsed
   from 17 to 1 and side stairs did not appear -- because the jog needs three
   columns and canyons were 1-3 wide, so most heads had no room for it.
2. **`HEIGHTMAP_CANYON_WIDTH` (1, 3) -> (3, 5)**, so a head is wide enough to
   carry the jog. That is what actually paid: north side 1->0 went 21 -> 51,
   and straight flights recovered to 16. Raising `HEIGHTMAP_CANYONS` to 5 took
   it to **63**, three times the original.

Final: north side 1->0 **63** (was 21), north straight 1->0 29 (was 17), with
the south unchanged. 0 grid violations; suite **730** green.

### Phase C11 — tile selection corrections — ✅ DONE (2026-08-31)

Three changes to `world/terrain/grid_paint.py`, and one of them I got wrong
first and had to back out -- worth recording, because the reasoning that led me
there was plausible and false.

1. **A cliff run is per wall, not per stone.** `_run_var` asked only whether the
   neighbour was stone. Concentric plateaus put one terrace's wall right
   alongside another's, and a two-level wall beside a one-level one, so two
   separate rims merged into a single run and the face where a rim genuinely
   ended was drawn as a squared-off `mid`. `_same_wall` now matches the level
   *and* the drop. Measured: 7 cliff cells across 12 worlds change variant --
   real, but rarer than I expected.

2. **A cliff face stands behind every sideways stair** -- see the assets
   journal for the rule. Plain grass used to sit under the wedge, so the
   wedge's transparent corners showed grass in the middle of a rock wall and
   the rim appeared to break at every crossing.

3. **Reverted: using `slots.raised` for sea level.** I argued that
   `autotile.mask_slot` falls back to `interior` on concave corners, that a
   wandering coastline hits those constantly, and that `slots.raised`'s sixteen
   combinations would fix it. Two of those are true and the conclusion is
   still wrong: `raised` is the *cliff-fringe* block, not the *shoreline*
   block. Applying it to sea level drew a grey fringe round every tile on the
   island -- and `raised[""]` is not a plain tile either. The shoreline block
   genuinely has only eight slots, so `mask_slot` is as far as the art goes;
   representing a concave shore corner needs new art, not new code.

   I should have looked at the rendered result before asserting the diagnosis.
   The visible shoreline had never actually been wrong.

Suite **730** green.

### C13 -- cliff faces default to `mid`

Three rules from the brief, replacing `_same_wall`:

1. A face is `mid` unless a side is **open**, where open means lower ground,
   lake or void. Same-level terrace grass alongside a face closes it -- that
   was the miss, and it was 1,027 of the 3,888 sides sampled.
2. An open west takes `left`, an open east takes `right`.
3. `single` needs west, east *and* the ground under the wall's **foot** open,
   so it is a genuine free-standing pillar. Foot rather than the face's own
   south neighbour, because a two-deep wall's upper cell sits on its own second
   row; walking to the foot keeps a one-wide column reading as one pillar.

Plus: the ground cell above a `single` is pinned to `raised["swe"]`, the
three-sided cap -- a pillar's terrace tile always continues north.

Measured over twelve worlds, variants go
`single 613 / mid 328 / left 502 / right 501` ->
`single 25 / mid 774 / left 561 / right 584`, and all 23 pillars that had
ground above them already resolved to `swe` unaided.

Full rule text in the assets journal. Suite **730** green (221 in the terrain
and world subsets re-run for this change).

### C14 -- cliffs cast a shadow on the terrace they stand on

The band renderer has had this since LD-5 (`_cliff_shadow` / `_shadow` in
`world/map.py`, drawn in `terrain/render.py`); the height-map painter never
did, so plateaus read as painted flat onto the ground rather than standing
above it. Same asset -- the `terrain_shadow` rig, one 192x192 blob with a
feathered bleed a cell wide on each side.

Ordering is the whole point: **ground, shadow, stone**. That forced
`paint_room_grid` out of its single row-sorted loop into four passes:

1. ground cells, plus the terrace tile each wall stands on
2. `_shade` -- the shadow layer
3. the stone: cliff faces, e/w wedges, vertical-flight channels
4. sprites taller than one cell

Pass 4 is new and currently latent: a drop-2 stone flight is 64x128 and hangs
into the row below, so under the old row-sorted single loop the grass of that
row painted over its bottom half. Every flight generated today is drop 1
(72 rock + 64 grass across twelve worlds, zero drop 2), so nothing visibly
changes -- but the ordering is now correct for when drop-2 flights appear.

Shadows accumulate on a scratch layer with `BLEND_RGBA_MAX`, not straight
alpha: the blobs are three cells wide and sit one cell apart, so six overlap on
every tile of a continuous run and normal compositing stacks into lumpy
over-darkened patches. Same fix the band renderer arrived at.

Vertical flights are excluded -- a channel you walk down is not a wall.

### C15 -- ground tiles are floor-relative

The rule, from the brief: a ground tile autotiles **against its own floor and
nothing else**, and is drawn underneath everything. Own-floor ground continues
on a side or it does not; cliff, flight, another terrace, lake and open sea are
all equally "not my floor". Where that puts a fringe somewhere it should not
be, the stone on top covers it.

`_edges` + `_open_sides` + `_is_pillar` collapse into one `_floor_sides`. What
went, and what each was papering over:

* cliffs at a *higher* level not counting as an edge (ground "runs flat under
  the wall standing on it") -- this is what left sea-level tiles tucked against
  a plateau as flat squares with no fringe at all;
* flights never breaking a fringe;
* the corner-closure pass, which added `w` + `e` wherever the neighbouring
  cell's south run stopped. Combined with the cliff rule it produced tiles like
  `raised[26]` (`swe`, fringed on three sides) sitting in the middle of a flat
  plateau -- the blocky outline in the report;
* the explicit `swe` cap above a `single` pillar from C13. Measured: all 23
  pillar caps across twelve worlds still resolve to `swe` on the plain mask, so
  the special case was doing nothing. Cliff variants are unchanged
  (`mid` 774 / `left` 561 / `right` 584 / `single` 25).

**Two corrections to earlier entries.**

1. C-series claimed "the shoreline block genuinely has only eight slots, so
   `mask_slot` is as far as the art goes". Wrong -- `slots` also holds
   `strip_v` `[3, 12, 21]`, `strip_h` `[27, 28, 29]` and `single` `30`, which
   are exactly the missing eight combinations (opposite pairs and 3-gap nubs).
   `autotile.mask_slot` fell back to `interior` for all of them; it now maps all
   sixteen via `_GROUND_SLOT`. That is the second half of the flat-square fix --
   a cell pinched between a lake and a cliff is an opposite pair.
2. The same entry concluded the visible shoreline "had never actually been
   wrong". It was: `solid` counted **every non-lake cell** as ground, cliffs and
   higher terraces included, so a sea-level tile against stone saw four solid
   neighbours and painted plain interior.

**Block choice is a separate axis from the mask.** Keying sea level off its own
floor made white surf trace the inland foot of every cliff. The mask stays
purely floor-relative; `_at_water` picks which of the sheet's two fringe blocks
draws it -- shoreline (white surf) when any side fronts sea or lake, raised
(dark rim) otherwise. Applies at every level, so a lake on a plateau gets surf
too.

Suite **730** green.

### C16 -- a higher floor is not the end of the floor beneath it

C15 fringed a ground tile wherever its own floor's ground stopped. That drew
*both* sides of every level boundary: the upper terrace's rim, and a second rim
on the lower floor tracing the upper floor's outline back at it. The brief:
plain mid tiles under every cliff and staircase, no strands, with the floor's
own topography still respected.

One clause does it -- **anything at a higher level is not an edge**; the floor
runs on underneath, and since ground is painted below everything, the structure
on top covers it. That covers both halves of the doubled rim: a higher terrace
butting against the cell with no wall between (4,903 sides across twelve
worlds) and a cliff or flight standing on it (3,540).

Still fringed, unchanged: void 13,216, ground at a *lower* level 4,903 (the
floor really does end and overlook a drop), stone at the cell's own level 3,735
-- its terrace's rim -- and lake 395. Flights at the cell's own level keep the
lip too, so a rim carries straight past a crossing; that was the one point the
brief left open and it was settled that way for consistency with the cliff
standing behind those flights.

Result: 30,692 fringed sides -> 22,249, and ground tiles with no fringe at all
go 37,426 -> 43,608. One rim per boundary, on the upper side.

`autotile.mask_slot` splits into `ground_slot(slots, sides)` (name-keyed, what
the grid painter wants) and the old cell-set wrapper (what `rooms.py` wants),
because both fringe blocks are now keyed off the same `_floor_sides` string --
the sea-level path was still deriving its own mask from the per-level cell set
and would have kept the doubled rim.

Suite **730** green.

### C17 -- stairs continue the outline; depth at the water's edge

Three fixes from one report.

**1. A flight is part of its floor's outline, not a break in it.** C16 kept a
flight as rim on every side, so the terrace tile beside one turned a corner
into the gap -- seed 1 `(13,20)` came out `raised[25]` (`se`) where the wall
either side of the crossing wants a plain bottom line. A flight at the cell's
own level is now rim to the **south only** (the lip still carries over it),
never west or east. `(13,20)` -> `raised[24]` (`s`); `(8,18)` -> `sw` instead
of `swe`, keeping only the west edge it genuinely has against lower ground.

**2. The shoreline block was painting surf against stone.** 40 tiles across
twelve worlds fringed against stone or a lower terrace while drawn from the
shoreline block, because block choice asked only "does any side touch water".
White surf wrapping a cliff foot reads as the water sitting up on the plateau.
The block is now chosen by whether **every** fringed side fronts water; a mixed
tile takes the dark rim, which is the lesser error. Now zero.

**3. A wall standing at the water's edge showed plain grass under it.** The
underlay beneath a cliff was a flat `interior` tile, and the run-end face
variants are transparent down one side, so 48 stone cells adjacent to sea or
lake exposed a sliver of plain grass floating on the water. The underlay is now
the same `_ground_tile` call as real ground, at the floor below -- the floor
genuinely does run on under the stone. Inland it still comes out plain (2,502
of 2,554), which is what the C15 brief asked for; the 48 at the water's edge
come out as proper shore tiles.

`_at_water` splits into `_wet_sides` (which sides front water) and
`_ground_tile` (sides -> block -> slot), the latter shared by ground and
underlay.

Suite **730** green.

### C18 -- a land-facing fringe needs the floor below behind it

Reported as "cliff tiles appearing with a blueish square outline as if they
didn't have transparency" on an upper terrace. The transparency is real and
intended, and that is the whole problem.

Every fringe tile is authored with a ragged, part-transparent outer margin --
grass strands and surf are meant to composite over whatever lies beyond them.
For a shoreline tile that beyond is the sea, and the world's water buffer
showing between the strands is exactly right. For a **raised** tile the fringe
faces land, but the room surface starts empty and nothing had been drawn in
that cell, so the same water buffer showed through: a blue hairline round every
cell of every upper rim.

`_ground_tile` now returns `(slot, over_water)`, and where it is false the
painter lays `sheet_for(level - 1)`'s interior behind the tile first -- the
floor that genuinely runs on underneath it, so the strands sit against grass.
Same for the underlay beneath a wall.

Measured on the baked room surfaces (alpha < 200, sampled every 2px) over seeds
1/3/5/7: ground tiles with see-through pixels whose fringe faces **land** go
1,088 -> **0** in seed 7 alone; across all four seeds 2,622 remain and every one
fronts water. Stone cells: 23 with see-through pixels, every one transparent
only on a side that fronts water -- a wall hanging over the sea, where the
`bottom` variant is meant to show it.

Suite **730** green.

### C19 -- a grass vertical pathway is not capped

C17 made a flight rim to the south only. That still drew a grass lip straight
across the head of every vertical pathway -- fencing off the opening the
pathway is meant to be, since you walk into one from the north rather than
from the side.

`_open_channel`: a **grass** vertical flight at this cell's level is not a
south rim either, so the tile above it is flat and the channel reads as
continuous from the terrace down through the wall. Only the grass ones -- a
stone-cut staircase keeps its rim, because the stair sprite drawn on top is
what fills that channel. East/west flights keep theirs too; they are notches
entered from the side, where the rim above is the wall's own.

Only the south side goes, on the brief's instruction ("maybe in the future it
can connect in other ways") -- a pathway lying *north* of a ground cell still
reads as the floor ending.

Measured over twelve worlds, the tile north of a flight:

| flight | before | after |
|---|---|---|
| grass (62) | `s` | `-` |
| grass (1) | `se` | `e` |
| grass (1) | `ns` | `n` |
| rock (72) | `s` / `ns` / `sw` | unchanged |

**Also fixed here:** `_floor_sides`' docstring still described the pre-C17 rule
("a flight counts as rim too"). The C17 patch had used a string replace with no
assertion and it silently failed to match, so the code changed and the prose
did not. Every edit in this file now asserts its match first.

Suite **730** green.

### C20 -- stone stairs cast, and so do plateau flanks

Two additions to the caster set, `_casts` becoming `_shadow_clips`:

* **Stone-cut vertical staircases cast** (+72 cells over twelve worlds). They
  are structures standing on the floor like any wall. Grass pathways still cast
  nothing -- a channel you walk down (64 cells).
* **Plain ground casts sideways** where a ground tile at a *lower* level lies
  directly east or west and this is the higher of the two (2,866 cells). That
  is the plateau's flank: a north-south level change is where cliff faces live
  and those already cast, but an east-west one is often bare, the wall having
  jogged away, so the shadow band hugging the side of a plateau stopped and
  restarted wherever the flank had no stone in it.

Total casters 2,418 -> 5,356.

**The clip is the whole trick, and the first attempt got it wrong.** The
shadow sprite is flat alpha-80 with a core a shade wider than one cell, so an
unclipped blob spills a few pixels past the caster onto every neighbour. Under
stone that is invisible and on the terrace below it reads as the soft edge we
want. Cast unclipped from open ground it traced a hard rectangle **outline**
around each tile -- over the plateau top and to north and south as well.

I first tried re-laying the caster's own ground tile over its shadow, on the
brief's "under the ground tile". That covers the core but not the spill, which
lands *outside* the tile, so the outlines stayed -- an A/B difference image
(max channel delta 39/255) showed them as clean rectangles, which is what
finally identified the mechanism. Clipping a ground caster's blob to the lower
neighbour cell removes the outline entirely and leaves exactly the soft line
hugging the flank that a cliff draws at the foot of a wall. The re-lay pass is
gone with it.

Suite **730** green. (One run failed on the known intermittent `spread_deg`
`KeyError` in `combat/weapons.py`; it passes in isolation and is unrelated to
terrain.)

### C21 -- water at a cliff foot, and bigger pools

A one-tile pool ringed by a level-1 terrace showed three faults at once. It was
not a lake, incidentally, but an **enclosed void** -- a hole the coast mask
punched that the terracing then built around.

**1. A wall's foot is not a beach.** The cliff west of the water had a shoreline
underlay (`edge_e`, white surf), and a cliff face's outer margin is transparent,
so the surf leaked out around the stone and put the waterline at the wall's own
height. `_ground_tile` takes `under=True` for the floor behind a wall and never
picks the shoreline block there. 37 underlays at a water edge, all now on the
raised block. This was mine from C17, which had swung too far the other way
from walls showing plain grass.

**2. Water outvotes a drop.** Block choice required *every* fringed side to
front water, so a tile with water north and a drop west fell to the raised
block and got no foam at all. It now takes the shoreline block whenever **any**
side fronts water, with one exception kept from C17: stone at the cell's own
level still wins, since surf wrapping a cliff foot reads as water on the
plateau. 25 tiles flip, 11 stay raised.

*Known cost, flagged at the time:* one tile, one block. Those 25 now draw surf
along their dry side too -- visible as a short white line running down a terrace
flank away from the pool.

**3. Foam anchors at any level.** `grid_shore` was restricted to level 0, so a
pool in a hollow ringed by a raised terrace had no moving water at its edge.
Any floor now anchors; 127 of the anchors are above sea level. This matters
more than it looks: foam is drawn *beneath* the room surfaces and shows through
the shoreline tiles' transparent margin, so it only reaches the water where fix
2 put a shoreline tile.

**Bigger pools.** `_carve_lakes` gains a `size` range (accretion steps, so more
steps means both bigger and raggeder); `HEIGHTMAP_LAKES` 1 -> 2 and
`HEIGHTMAP_LAKE_SIZE` (4,14) -> (10,34). Over twelve worlds: rooms with water
33 -> 37, cells 211 -> 645, median 6 -> 16, largest 11 -> 34. Note this shifts
the shared RNG, so every seed's layout changes.

Suite **730** green.

### C22 -- the floor order is what makes a shadow read as cast

C20's ground-flank shadows were clipped to the lower neighbour cell. Rendering
the shadow layer alone at 8x shows why that was wrong: the clip admits the
sprite's sparse fringe and its few-pixel core spill, never the core itself, so
what landed was a ragged hairline a couple of pixels off the tile edge,
attached to nothing.

The brief's fix, and it is the right one: the shadow is a **whole tile square
at the caster's own cell**, laid *after the floor below and before the tile
that casts it*. That means painting terrain **floor by floor in ascending
level order**, each level's shadows going down between the floor beneath and
that level's own tiles -- not "all ground, then all shadows".

The ordering does all the hiding that the clip was attempting:

| the core's spill lands on | painted | result |
|---|---|---|
| the caster's own cell | after | covered |
| same-level neighbours | after | covered |
| the floor below | before | **visible -- the cast shadow** |

So `_shadow_clips` collapses back to a `_casts` predicate and `_shade` takes
plain positions again. `paint_room_grid`'s passes go from
`ground -> shadow -> stone -> tall` to: sort every cell into the floor it
paints on; then per level ascending, that level's shadows followed by its
ground and wall underlays; then stone; then tall sprites.

Measured over seeds 35/7/2, cells whose pixels change when shadows are turned
off: 2,049 ground cells receive an edge band (the floor below, as intended),
584 cliffs and 158 e/w flights receive one through their faces' transparent
margins, and only **5** caster cells are touched at all -- level-2 casters
spilling onto level-1 casters painted a step earlier, which is a higher floor
casting onto a lower one and so correct. Under C20's first attempt every one of
the 2,866 casters carried a rectangle outline.

Suite **730** green.

### C23 -- a north edge is a level change too

C20 let ground cast only where the lower neighbour lay east or west, reasoning
that north-south changes are where the cliff faces live. That holds on a
terrace's **south** rim and nowhere else: a plateau's north edge is its back
and never grows a face, so those tiles cast nothing. The only shadow along a
north edge was the sideways spill from the corner tile at each end -- two short
horizontal stubs with a gap between them, which is what the report described as
"a straight line ... attached to nothing".

`_casts` now returns true for ground with a lower orthogonal neighbour on
**any** side. Over twelve worlds: ground casters 2,409 -> 3,271, the 862 new
ones being exactly the north-edge runs the old rule skipped. Rendering the
shadow layer alone at 8x, the two stubs become one band running the length of
the edge and turning the corner into the flank.

South rims are unaffected -- their south neighbour is a cliff, and a cliff is
not ground, so they still cast from the stone.

Suite **730** green (one run tripped the known intermittent `spread_deg`
`KeyError` in `combat/weapons.py`; it passes in isolation and on re-run).

### C24 -- the shadow sprite has no corners

Reported: north-east and north-west corner tiles still shadowed wrongly.
Confirmed, and it is the art, not the ordering. `shadow.png` is a plus, not a
square -- opaque pixels per cell of its 3x3 layout run

    0   200    7
  184  4028  181
    0   170    8

so the four **diagonal** cells are empty while the orthogonal ones carry
~180-200. A caster lays its band along both edges of a corner and leaves a bite
out of the outside corner; no draw order can fix that, because one caster
physically cannot wrap its own corner. Measured over seeds 0-5, the two edge
cells came out at a 7-9% median coverage and the diagonal at **0.0%** (NW) and
**0.2%** (NE) -- the NE figure being the 7 stray pixels, which is also what had
made an earlier boolean check report the corner as "covered".

Only north corners exist to be wrong: the convex-corner census is 482 NE, 480
NW and **zero** SW/SE, because a terrace's south rim has a cliff at the corner
and a cliff is not ground.

`_corner_fills` adds two more blits of the same sprite per corner, centred on
each orthogonal neighbour so their *side* fringes fall on the diagonal cell.
**Clipped to a `px // 8` square at the inner corner**, not to the whole cell:
each of those blits lays a full-length strip down one side of the diagonal, and
unclipped they read as whiskers poking a whole tile past the corner into open
ground -- tried, rendered, and visibly worse than the notch. All that is wanted
is the joint.

Density in that joint square, against 46.9% for the band itself:
NW **0.0% -> 45.3%**, NE **10.9% -> 73.4%**. The NE corner comes out heavier
than the band; it is 8x8 pixels and reads fine, but it is not symmetric.

These are the only clipped entries in the shadow pass -- a caster's own blob
still goes down whole (C22).

Suite **730** green.

### C25 -- no shadow ever falls north

The brief, after seeing C23/C24 in place: a shadow only ever falls **south or
sideways**, and a sideways caster casts only on the side facing the drop. A
tile whose only drop is northward casts nothing -- a north-cast shadow reads as
inconsistent with the rest of the lighting, and is better absent than present.

`_casts` + `_corner_fills` become one `_shadow_casts` returning the blits a
cell contributes. Stone is unchanged: one unclipped blob. Ground emits one blit
per lower side **except north**, each clipped to that side's cell -- and the
clip is what suppresses the north half on a corner tile, which drops both ways.

Census over twelve worlds of ground with a drop beside it:

| lower ground on | count | now |
|---|---|---|
| north only | 862 | silent |
| west only / east only | 718 / 715 | that side only |
| north+west / north+east | 480 / 482 | sideways only |
| west+east / north+west+east | 10 / 4 | both sides |

**No ground tile anywhere drops to the south** -- zero cases, because a south
rim always has a cliff on it. South is entirely the stone's job.

C23 and C24 are both undone by this: with no north band there is no corner to
join, so `_corner_fills` is deleted rather than adjusted.

**A prediction of mine that was wrong.** I said the lateral bands would be
unchanged to the pixel, since the core is covered by the caster's own tile
either way. 735 of 1,165 lateral cells did change: a north-edge caster used to
spill sideways onto its neighbours too, and those casters are now silent.
Median coverage 5.27% -> 5.08%, so the effect is slight, but "unchanged" was
not right and the code comment saying so has been corrected.

*(A blank first diagnostic was my scratch script, not the code -- a `sed`
pattern missed, so both halves of the A/B rendered identically.)*

Suite **730** green.

### C26 -- a north corner casts nothing either

C25 suppressed the northward half of a corner tile's shadow and let it keep its
sideways one. Still wrong to the eye. The rule is simpler than that: a ground
tile with **any** drop to the north casts nothing at all.

`_shadow_casts` gains one early return. Ground casters over twelve worlds:

| lower ground on | count | now |
|---|---|---|
| north only | 862 | silent (as C25) |
| north + west / north + east / all three | 480 / 482 / 4 | **silent (new)** |
| west / east / west+east | 718 / 715 / 10 | unchanged |

1,828 tiles emit no blit; 1,443 remain, 1,433 of them one-sided and 10 casting
both ways. That is the same caster population C20 had, now with C22's
floor-by-floor ordering and per-side clipping instead of C20's single clipped
blob.

The accepted cost: a flank's band starts one tile below the top of the flank,
since that top tile is a corner. Visible in the diagnostic as the vertical band
beginning a cell lower than the terrace does.

`_corner_fills` (C24) and the north-edge casters (C23) are both gone; the rule
has ended up narrower than either.

Suite **730** green.

## Phase D — nav and collision read the grid

Settled first, from the brief:

* **Nothing falls off a ledge.** Movement between elevations is by flight only,
  both directions, player and enemies alike, so links stay undirected. Extra
  mobility may come later; nothing today assumes one-way edges.
* **Projectiles respect elevation upward only.** A shot crosses its own floor
  and higher ground freely; one entering a *lower* tile than it was fired from
  dies at that boundary.
* **Enemies get an aggro range and a pursuit timer.** Once aggroed they take
  the whole route however long -- no path-cost cap -- but the timer ends it.
  The timer refreshes while the player is in range and counts down from the
  moment they leave; being attacked also triggers it. On giving up they idle in
  place with a light wander. Aggro range is straight-line and elevation-blind.

A consequence of the last two, accepted deliberately: **high ground is
asymmetrically strong.** A ranged enemy on a terrace can shoot down at the
player while the player's return fire hits the cliffside.

### D0 — one elevation index — ✅ DONE

`world/elevation.py`: `LevelIndex` rasterises the whole world once into flat
per-tile arrays (`level`, `kind`) keyed by absolute tile, plus a small dict
holding the flight `Cell` records verbatim -- a flight's `drop` / `row` / `tag`
are what tell one end of a staircase from the other, and D1 needs them to mirror
`walk_links` exactly rather than approximate it. 1.1 ms for a 279x145 world.

Round-tripped across 8 seeds: **40,128 walkable cells (367 of them flight
cells), zero mismatches** in level, kind or flight identity.

**It answers elevation, not walkability, and that distinction is load-bearing.**
A room rect is tile-*sized* but only tile-*aligned* under the height-map
generator: with the flag off, rooms sit at offsets like (8, 40) / (24, 56) /
(40, 8), so one absolute tile straddles two room cells and no absolute raster
can reproduce `_point_ok`. Sampled over 4,000 random points with the flag off,
using this as a floor test disagreed with `_point_ok` **219 times**. It costs
nothing -- with the flag off every surface is ground at level 0, so every
elevation query says "same floor" -- but the method is named `has_surface`, not
`walkable_at`, so it cannot be mistaken for the floor test.

`_add_grid` checks alignment and falls back to flat rather than placing cells
at the wrong tiles. Every room rect is aligned today (offset (0, 0)); the
fallback exists so a future change to room placement fails safe.

Suite **730** green.

### D1 — `can_cross`, one adjacency rule — ✅ DONE

`world/elevation.py` gains `can_cross(index, a, b)` and its helper
`_flight_opens`: `heightmap.walk_links` mirrored against the `LevelIndex`, in
world tiles, without allocating. `walk_links` stays the authority -- it is what
`check_grid` validates every generated room against -- but it reads a
room-relative grid and builds the whole neighbour list per call, which the
collider and the flow field cannot afford thousands of times a frame.

Faithful down to the asymmetry between the two flight kinds: a straight
flight's foot is row `drop - 1`, an east/west flight's is row `drop`, because
the jogged unit spans one row more than it descends.

**Parity, 12 seeds, 60,028 walkable cells: 60,028 agree, zero missing links.**
The comparison is against `walk_links` restricted to the room's own tiles,
because `can_cross` legitimately finds 122 links that `walk_links` structurally
cannot see -- every one of them a **bridge tile**, since `walk_links` only ever
knows one room's grid and a bridge belongs to none. Verified by classifying
each extra against the corridor rects rather than assuming.

Flag off: 1,779 adjacent surface pairs across a world, **zero refused** -- every
surface is ground at level 0, so nothing changes until the flag is on.

Cost: **298 ns/call**. Fine for the collider (a few hundred calls a frame) but
*not* for the flow field, which would spend ~24 ms per rebuild asking it per
edge. Level geometry is static, so **D4 must bake a per-edge passability mask
once at `NavGrid` build time** rather than calling `can_cross` during
`rebuild`. Noting it here because it shapes D3/D4's design.

Diagonals return False by construction: a diagonal step is the caller's to
compose from its two orthogonal parts, which is also what stops a body cutting
the corner of a drop.

Suite **730** green.

### D2 — collision obeys elevation — ✅ DONE

`GameMap.path_ok(prev, new)` + `is_walkable(pos, radius, frm=)`, threaded
through the three `is_walkable` calls in `resolve_movement` -- the single choke
point every mover already goes through (player, enemy, boss). `frm=None` is
the pure floor test, unchanged, which is what the AI's "is this spot free"
probe and spawn placement keep getting.

**The rule applies to the body's centre only.** The radius probes stay a plain
floor test. Demanding that every probe sit on the centre's level would stop a
large enemy standing anywhere near a rim -- terraces are only a few tiles wide
-- and overhanging a drop is exactly what those probes already tolerate against
a wall. This was the wrinkle flagged when the phase was planned; the fix turned
out to be *not* extending the rule to them.

**The segment is walked, not end-checked.** Ordinary movement is a few pixels a
frame and never leaves its tile, but a charger's lunge
(`ai/behaviors/melee.py:79`, `ai/components/attacks.py:44`) resolves straight to
the player's position and spans many tiles; a bare endpoint test would let it
vault a cliff. Sampling every half tile cannot skip one.
`elevation.can_step` handles the diagonal case by composing its two orthogonal
parts, which is what stops a body slipping across the corner of a drop.

Verified over 6 seeds:

* **55,570 adjacent tile pairs**: the collider's verdict matches `can_cross`
  everywhere. 76 pairs are refused for a reason that is not elevation -- all 76
  have an obstacle sitting on the destination, confirmed by testing rather than
  assumed. **Zero** cases where the elevation rule disagrees.
* **2,336 level-change pairs**: 2,073 blocked, 263 open -- and the 263 are
  flights. Enemies can no longer walk up a drop.
* **52,868 same-level ground pairs** still open.
* **9,185 / 9,185** multi-tile lunges across a level change refused.
* **160 / 160** flights walkable head to foot through `resolve_movement` in
  realistic 8 px steps.

Cost, A/B on one world (the two flags generate *different* worlds, so comparing
across them measures the world, not the rule): **+0.58 us/call, +15%**, on a
call that was 3.93 us. Negligible beside the room and obstacle loops
`_point_ok` already runs.

Suite **730** green with the flag off.

### D3 — `NavGrid` learns elevation — ✅ DONE

Three new per-cell arrays beside `walkable` / `corridor` / `clearance`:
`level`, `flight`, and `step_mask` -- bit *i* set when the move in
`NAV_DIRS[i]` is one the terrain allows. `NAV_DIRS` is now the single source of
the neighbour order, with `FlowField._NEI` built from it, so a mask bit and a
neighbour can never drift apart.

**Baked, not asked.** D1 measured `can_cross` at ~300 ns; consulting it inside
`rebuild` would cost ~24 ms a repath. The geometry is static, so the answer is
computed once here and the rebuild loop (D4) reads one byte and ANDs it.

**Flight cells are also marked `corridor`**, which hands them the M3 clearance
leniency. A flight is one tile wide with stone either side; without it the
48 px nav class cannot thread one -- the exact case that leniency was added for
in LD-3.

Nav cells are 32 px (48 for the large class) and tiles are 64, so the work is
done per *tile* and projected onto cells; two cells inside one tile are always
connected, a tile having a single elevation.

**Cost, and two attempts at it.** The first version cost +86 ms per grid, ×2
classes. I assumed tuple building and dict lookups in the projection and
rewrote it around integer tile indices — **no change at all**, +86 ms still.
Profiling instead of guessing showed the real cost: 42,504 `can_step` calls,
106 ms of a 200 ms pass. A diagonal is *defined* as its two right-angle
detours, so asking `can_step` for one re-derives orthogonal answers already
computed. Doing the four orthogonals first and reading the diagonals off those
bits gives **+58 ms** per grid, NavField 384 → 322 ms. Anything further would
mean duplicating the rule out of `elevation.py`, which is what D1 exists to
prevent.

Verified: the baked mask agrees with `can_step` on **157,328 / 157,328** edges,
re-checked after each rewrite. 404 flight cells, all marked corridor; 3 levels
present.

Suite **730** green.

### D4 — the flow field obeys elevation — ✅ DONE

`FlowField._NEI` carries its `NAV_DIRS` bit alongside the weight, and both
`rebuild` and `direction_at` reject a neighbour whose bit is clear in
`NavGrid.step_mask`.

**The gradient had to be gated as well as the fill**, which was not in the
plan. A cell across a drop can be genuinely downhill -- the fill reached it the
long way round, so its cost really is lower -- and an ungated `direction_at`
would steer straight at it, walking an enemy into the cliff it just spent a
detour avoiding.

That in turn changed a test rather than breaking one:
`test_every_cell_has_a_strictly_downhill_neighbour` asserts the invariant M4
relies on, and the invariant is only the one M4 needs if the downhill
neighbour is also one the terrain allows. It now gates on the same mask. (With
the flag off the mask is all-open, so the test is unchanged there.) A second
test failure was mine: `direction_at` still unpacked `_NEI` as 3-tuples.

Verified with the flag on:

* **The field's reach is exactly a BFS over the mask.** Cell-for-cell identical
  on seeds 35 / 7 / 2 -- 21,252 / 20,560 / 20,716 cells.
* **20 / 20 gradient walks** from sea level to a top terrace reached it,
  **every one through a flight, none over a cliff**. This is the phase's actual
  goal, tested end to end rather than inferred from the mask.

Cost: **+0%**. A/B on one world, mask all-open against mask gating, 48 repaths:
33.8 → 33.9 ms each. Exactly what baking it in D3 was for -- calling
`can_cross` here would have added ~24 ms a repath.

**Flagged for D7, not introduced here:** 33.9 ms *is* a lot for one repath, and
height-map worlds are far bigger than the LD-8 ones the field was tuned on.
Pre-existing and unchanged by this phase, but it wants looking at before the
flag goes on for real.

Suite **730** green.

### D5 — scatter keeps flights clear — ✅ DONE

`_flight_keepouts(rooms)` in `world/gen/scatter.py`, appended to the existing
`all_doors` list so it protects the top-up tree pass as well. The tiles come
straight from `heightmap.walk_links` rather than being re-derived -- it already
knows a straight flight opens north at its head and south at its foot, and that
an east/west flight also reaches sideways because the wall jogs a row across
it. Empty for a room with no height map, so the legacy world is byte-identical.

Verified over 6 seeds: **160 / 160 flights** have their foot reachable from
their head for **both** nav classes, small and large, with obstacles in place.

**But the fix is nearly a no-op today, and the reason matters more than the
fix.** A/B over 8 seeds: without the keep-out, exactly **1 obstacle in 73**
landed on a flight. Chasing that number found the real problem --

| | rooms | floor cells | obstacles | per 1000 cells |
|---|---|---|---|---|
| flag off | 128 | 7,476 | 420 | **56.2** |
| flag on | 48 | 40,128 | 73 | **1.8** |

**A 31x drop in obstacle density.** Two compounding causes. Every height-map
room is a *special* kind -- there are no `combat` rooms at all in a height-map
world -- and a special room gets `base = 2` with `bonus = 0`, so it attempts two
placements no matter how large it is. On top of that the room count fell 16 → 6
per world (fewer, bigger rooms, as asked), spreading that fixed budget over five
times the floor.

So the islands are bare, which is exactly what every screenshot in the C-series
shows. This is out of D5's scope -- D5 is "do not block a flight", and that is
done and verified -- but it is a blocker for D7, and the density rule needs
rewriting for rooms of this size before the flag goes on.

Suite **730** green.

### D6 — the verification pass — ✅ DONE

`tests/world/test_elevation.py`, 16 tests over two seeds. Every ad-hoc check
run during D0–D5 is now a standing one, so the phase cannot silently rot.

`heightmap.walk_links` / `heightmap.reachable` are the authority throughout --
they are what `check_grid` validates every generated room against -- so the
suite is really one chain: generator → `can_cross` → `step_mask` → the field,
each link checked against the one before it.

| what | covers |
|---|---|
| index round-trip, cliffs carry no surface, rects tile-aligned | D0, including the alignment guard that would otherwise fail silently |
| `can_cross` vs `walk_links` within every room | D1 |
| a level change needs a flight; a diagonal cannot cut a drop's corner | D1 |
| collider vs the rule on every adjacent pair; a lunge cannot vault a cliff; every flight walkable head to foot | D2 |
| `step_mask` vs the rule; flights get corridor leniency | D3 |
| the field reaches exactly a BFS over the mask | D4 |
| **the field reaches every cell `heightmap.reachable` says is connected** | end to end |
| a chase from sea level to a plateau goes through a flight | the phase's actual goal |
| no obstacle on a flight or its landings; both nav classes can use every flight | D5 |

The end-to-end one is the strongest: **10,233 generator-connected cells, zero
unreached**. Cells blocked for a reason that is not elevation (nav centre off
floor, clearance, an obstacle) are excluded so the assertion is about the level
rule alone -- and in the event none of them occurred either.

**One test failure was the test's own fault, and worth recording** because the
same wrong assumption is easy to make again: `test_every_flight_is_walkable_head_to_foot`
first entered each flight from the tile *north of its head*. That is right for
a straight flight and wrong for an east/west one, which is entered from the
**side** -- the wall jogs a row across it. It walked a body into a cliff face
and reported the collider as broken. The entry and exit tiles now come from
`walk_links`, which already knows the difference.

Two seeds rather than forty: each costs a world plus a nav build, and every
case is structural -- the sweeps cover tens of thousands of tiles apiece.
Module adds ~6 s.

Suite **746** green (730 + 16).

### D7 — aggro range and the pursuit timer — ✅ DONE

`entities/ai/components/aggro.py`, wired in at `registry.build_behavior` so all
twelve enemy types and the boss are covered from one place rather than in
twelve builders. `aggro_range` / `pursuit_seconds` are per-type values in
`data/enemies.json`; a type carrying **neither** comes back untouched, so the
module's existence retunes nothing by itself and a missing key never gets a
number chosen in code.

* `AggroSense` runs in `Behavior.always`, so the countdown continues through an
  attack cycle and a hit landed mid-swing still refreshes it. It **refreshes**
  rather than extends -- while the player is in range the deadline is always
  `pursuit_seconds` away, so it starts counting from the moment they leave.
* `Enemy.take_damage` calls `provoke()`. A flag, not a timestamp, because
  nothing there has the clock; `AggroSense` consumes it next tick.
* `Wander` gives the idle state a slow drift with occasional standstills, so a
  bored enemy is not a statue.

**The machine only drops back to idle from the behaviour's *initial* state.**
Letting the timer yank an enemy out of a telegraph or an active swing would cut
that attack's timing short and strand the melee hitbox it had committed to.
The attack finishes, the machine returns to chase as it always does, and gives
up from there.

Measured on the chaser (range 420, pursuit 6 s, speed 95):

| | result |
|---|---|
| 2,000 px away, 4 s | 106 px travelled -- the wander only |
| 294 px away | closes to x=2 and attacks |
| 2,000 px away, hit once | 379 px travelled: full pursuit |
| in range 2 s, then gone | aggro held to **t=8.02 s**, i.e. **6.02 s** after leaving |
| after giving up | 95 → 26.6 px/s, which is the 0.28 wander |

**One real behaviour change, and it cost a test.** Every behaviour now starts
in the aggro machine's idle state and reaches its own initial state through a
transition, which `Behavior.tick` evaluates *after* the frame's components have
run. So an enemy spends its first tick idle even with the player on top of it,
and acts from the second -- one frame at 60 fps.
`test_exploder_dies_when_it_reaches_player` asserted a detonation in a single
update and now ticks twice. The alternative, checking transitions before
components, would have cut every attack's own timing short.

`tests/ai/test_aggro.py`, 7 tests: every type declares both values (a new type
that forgets them silently reverts to chasing for ever), a type with neither is
untouched, and the five behaviours above.

Suite **753** green.

### D8 — obstacle size and density — ✅ DONE

**Size was in two places, one of them code.** `entities/obstacle.py` held the
collider radii as literals while the *drawn* size lived in `terrain.json`
`obstacle_decor` -- two files to resize one prop, and against the standing rule
that entity tuning belongs in the data. `KINDS` is now a lazy mapping over a
new `terrain.json` `obstacles` block, keeping `from entities.obstacle import
KINDS` working.

Sizes were chosen by sweeping against the legacy world rather than picked:

| | old | tried | **kept** |
|---|---|---|---|
| tree | 11 | 16 | **15** (+36%) |
| rock | 25 | 34 | **30** (+20%) |
| pillar | 15 | 24 | **21** (+40%) |
| house | 31 | 36 | **34** (+10%) |

The first set broke `test_flow_field_routes_across_floors_to_every_raised_room`
-- an LD-8 raised room is ~60 cells and a rock of radius 34 is more than a tile
across. `15 / 30 / 21 / 34` is the largest set that world still tolerates. The
tree's canopy (`render_radius`) went 15 → 22 to match.

**Density.** The legacy rule is `base + cells // 48` capped at 14, with `base`
= 2 and no area bonus for a "special" room. Every height-map room is a special
kind, so each island got two obstacles. Now area-proportional for grid rooms
only, so the legacy path stays byte-identical:

| | rooms | cells | obstacles | per 1000 | floor covered |
|---|---|---|---|---|---|
| flag off | 128 | 7,476 | 418 | 55.9 | 2.2% |
| flag on, before | 48 | 40,128 | 73 | **1.8** | 0.1% |
| flag on, after | 48 | 40,128 | **1,907** | **47.5** | 1.7% |

Placement lands on level 0 / 1 / 2 in 82 / 16 / 2 %, against a cell split of
79 / 17 / 4 % -- proportional, no bias toward the shore.

Also: the special-room "keep the interaction space clear" disc is a fraction of
the room's own size, which works out at ~460 px on an island -- and the middle
of a concentric island *is* its upper plateau, so it blanked the whole thing.
Grid rooms use a fixed 176 px instead.

**Two corrections to earlier reporting.**

1. **The screenshots were never drawing obstacles.** `_draw_tiled` is terrain
   only; obstacles come from `TerrainRenderer.scenery_drawables`, which the
   scratch render scripts never called. So every island shot in the C-series
   would have looked bare whatever the density was. The density really was
   1.8/1000, but "the islands are bare" was being read off images that could
   not have shown otherwise.
2. Two edits to the render script silently did nothing -- they matched a
   variable name from a different script -- and I reported "still nothing
   drawn" twice before checking. String edits in the scratch scripts now assert
   their anchor, the same rule already applied to the source files after C19.

**A test fixture pinned to the old radii.**
`test_resolve_movement_hops_a_fully_wedged_entity_free` placed its three trees
at hardcoded offsets sized for radius 11; at 15 they also blocked the escape
hop and it fled backwards. It now derives the offsets from the tree's own
radius, so it tests the behaviour rather than one obstacle size.

Suite **753** green.

### D9 — the bounded repath — ✅ DONE

`FlowField.rebuild` takes `max_cost` and stops once the frontier passes it;
`NavField` passes `config.NAV_FILL_MAX_COST`. Left `None` in `FlowField`'s own
signature, so anything constructing one directly is unchanged.

Safe only because of D7: an enemy that is not pursuing needs no route, and one
that is has an aggro range in the hundreds of pixels plus a timer.

**Bounding the fill was only half of it.** The first cut gave 43.5 → 12.4 ms, a
3.5x win against the 6-7x the cell counts predicted. Profiling the gap found
`rebuild` clearing 160k longs one at a time in a Python loop -- with the search
now bounded, *resetting* the cost array had become more expensive than the
search it was preparing for. Slice-assigning a prebuilt blank took it to
**6.3 ms**, and improved the unbounded case too (43.5 → 37.9).

**The cap is measured, not guessed, and my first value was wrong.** At 3000, a
spot check said 89.8% of cells within 600 px of the target had a route -- and
every one of the misses was on the *same island*. That is the exact failure
this phase exists to remove: an enemy 300 px away with no path, beelining into
a cliff. The reason is that the bound is on **path** cost, and on a terraced
island a cell 300 px away can be a long walk to a staircase and back.

Sampled over three worlds, path cost for cells within 600 px straight-line:
p50 513, p90 1858, p95 2590, p99 3655, max 6058.

| cap | routed | ms/repath |
|---|---|---|
| 3000 | 97.5% | 6.3 |
| **4500** | **99.7%** | **9.4** |
| 6000 | 99.8% | 14.1 |
| unbounded | 100% | 37.9 |

**4500**: 4x faster than unbounded for 0.3% of nearby cells, which keep
`steer_at`'s bearing fallback and whose pursuit timer ends the attempt anyway.

**Three tests asserted a contract this removes** -- all three seeded at the
start room and checked something on the far side of the world, using world span
as a vehicle for testing connectivity rather than as the thing under test. Two
now seed next to the feature (a raised room's *connected* neighbour from the
layout graph, not merely the nearest by centre distance -- the closest room can
sit across a gap and reach nothing) and test exactly what they meant. The third
was genuinely about world span; it now asserts everything *inside* the bound is
routed for both classes, and a new `test_the_fill_bound_actually_bounds` checks
the bound holds -- with slack for one final step, since the loop stops when the
frontier passes the cap and the last bucket can still hand a neighbour a
diagonal.

Suite **754** green.

### D10 — projectiles respect elevation — ✅ DONE

**The rule as written here was inverted, and the brief is what settled it.** The
paragraph below used to read "travels onto higher ground; dies on entering a
lower tile" -- which is backwards, and contradicted this same entry's own
consequence paragraph two paragraphs further down. The brief: *"projectiles only
work on the same floor or above floors, if a projectile is shot from a lower
floor, it will collide with the closest cliffside."*

**The rule**: a projectile travels over its own floor and over anything
**lower** -- so firing *down* off a terrace works, and a shot still crosses the
open sea between islands. Terrain standing **above** the floor it was fired from
stops it, against the cliffside.

**It is cheap, and that was checked rather than assumed.** `block_on_obstacle`
in `game/states/playing/effects.py` already runs a circle test against every
blocking obstacle for every projectile every frame. The elevation test is one
array read on `LevelIndex` (D0) -- strictly less work than what sits beside it.
The brief allowed dropping the rule if it proved expensive; it does not.

**Where it went.** `effects.py`, alongside `block_on_obstacle`:
`stamp_fire_level` records the floor at the muzzle and `block_on_terrain` kills
the shot with the existing particle burst.

**`level_at_point` was the wrong reading, and this is the part worth keeping.**
A cliff face is not walkable, so it has no `level` at all -- testing that would
let an upward shot pass *through* the wall and only stop it on the plateau
beyond, which reads as the shot going through solid rock and dying in mid-air.
`LevelIndex` gained a second array, `top`: the elevation of whatever terrain
stands on a tile, walkable or not. `Cell.level` is already documented as "the
upper surface a cell belongs to -- for a cliff or a stair, the terrace it hangs
from", so a face reports the height a shot has to clear and nothing had to be
derived. Verified against the grid: `top_at` matches `Cell.level` on all 5,964
cells of a sample world, across ground, cliff, lake and both stair kinds, while
`level_at` still reports `NONE` on every face. The void keeps no top, which is
what lets a shot cross between islands.

The level is stamped **at the muzzle**, not on the projectile's first update: a
400 px/s shot has already moved ~7 px by then, which at a rim is enough to
sample the tile past the edge and judge the shot against the wrong floor.

Measured end to end on seed 21, at a column with three tiles of level 1 below
three of level 2: fired **up** from the low terrace the shot dies after 100 px,
about a tile and a half, at the wall; fired **down** from the high terrace it
flies the full 450 px. Orbiters are exempt, for the same reason they skip the
obstacle test -- they are anchored to the player and are not travelling.

`fire_level` defaults to `NONE`, which disables the rule, so a flat world and
every unit test that builds a projectile by hand are untouched. `reset` clears
it, because the pool recycles and a stale level would judge the next shot
against the last one's ground.

**The consequence to keep in view.** Together with elevation-blind aggro, this
makes **high ground asymmetrically strong**: a ranged enemy on a terrace can
shoot down at the player while the player's return fire hits the cliff face.
That is deliberate and was confirmed as wanted, but it is a balance lever, and
the first place to look if ranged enemies on plateaus feel unfair.

Nothing else in the phase depended on this, which is why the flag went on
without it.

Suite **793** green, nine new tests.

### D11 — shorter bridges, tighter islands — ✅ DONE

**The lattice cell was square.** One 58-tile chunk per room, while a height-map
room is 36-50 tiles wide and only 22-30 tall -- so every island carried a
chunk-height of empty sea above and below it and the vertical bridges ran at a
median of **34 tiles against 17** for the horizontal ones. `_cell_rect` now
takes a per-axis cell.

**Packing them closer needed two changes together, and neither works alone.**

1. `coast_mask` gains `keep`: a hard band of void inside the rect that the walk
   cannot eat into. Without it a rect is not a safe proxy for where its island
   is -- measured over 14 seeds, land reached the rect edge on *all four sides*,
   because the erosion fallback returns the whole rect. That is what made rect
   overlap unsafe.
2. The room size **range** narrows, 44-50 x 26-30 rather than 36-50 x 22-30.
   This mattered more than expected: a 36-wide island in a 50-wide cell leaves
   14 tiles of pointless sea, so the *variance* was as much of the gap as the
   spacing.

Measured over 14 seeds, zero land-cell collisions in every row:

| | bridges h (med/max) | bridges v | island |
|---|---|---|---|
| square 58, rooms 36-50 | 18 / 25 | 34 / 37 | -- |
| 50x30, rooms 36-50 | 10 / 15 | 7 / 10 | 43 x 26 |
| 46x26, rooms 36-50 | 9 / 15 | 6 / 9 | 39 x 22 |
| **46x26 + keep 2, rooms 44-50** | **5 / 8** | **4 / 6** | **43 x 24** |

Half the bridge length for two tiles of island height. Tighter merges islands:
46x26 with the old wide range gave 92 shared land cells.

**A test asserts the opposite invariant, correctly.**
`test_procedural.test_all_geometry_within_bounds_and_nonoverlapping` requires
room *rects* never to collide -- true under LD-8, where a rect *is* the floor.
Height-map rects overlap by design. The equivalent that matters is now asserted
in `test_elevation.PackingTests`: no world tile is land in two rooms at once,
and the void band is really there.

**Also: the world renders never drew obstacles.** `world.py` had the same bug
the island shots did -- `_draw_tiled` is terrain only, and the scenery pass
lives in `TerrainRenderer.scenery_drawables`.

### Turning the flag on — the fallout

`HEIGHTMAP_ROOMS = True` left **53 failures across 8 modules**, not the one I
first guessed from a truncated log (`test_verticality` is 29 of them). Read
rather than assumed: every failure is an LD-8 geometry assumption -- room
counts, chunk-derived sizes, room-local void, foam on cliff bands, rect
non-overlap. None indicates a height-map bug.

Those eight modules exist to cover the LD-8 world, which the flag still
selects, so each now pins `HEIGHTMAP_ROOMS = False` for its own run -- the
convention `test_pathfinding` already used for `WORLD_VERTICALITY`. The
height-map path keeps its own coverage in `test_elevation.py`, now 18 tests.

*(Two self-inflicted detours worth recording: a background suite run that
reported 293 failures in 15 s was measuring a half-edited tree -- it was in
flight while `HEIGHTMAP_CHUNK_SIZE` was being removed from config, and the
number is meaningless. And the first attempt at adding these fixtures inserted
them **inside** parenthesised import statements, because the regex matched the
opening line; eight files had to be repaired in place rather than reverted,
since they carried uncommitted work from D6 and D9.)*

**The last failure was mine, and it was an assertion, not a bug.**
`test_rebuild_routes_both_classes_within_the_fill_bound` (D9) counted how many
*room centres* the bounded fill reached and required more than one. On an LD-8
world rooms are small and close, so that held. On a height-map world the room
centres are **3,500-13,000 of path cost apart** -- seed 3 measures
`[0, 4585, 8344, 3829, 8602, 12939]` -- so most sit outside the 4,500 bound and
the count says nothing.

Checked before rewriting it, because "one room reachable" would also be the
symptom of bridges failing under the tighter packing: with the cap lifted, **all
six rooms route on every seed tried**. The islands are connected; the centres
are simply far apart in walking terms. The test now samples reached *cells* and
asserts each has a gradient, which is the contract it meant.

Worth stating plainly, since it follows from D9 + D11 together: a cross-island
chase is impossible under the bound. That is by design -- aggro range is at most
600 px straight-line and a neighbouring island is thousands of pixels of path
away, so no enemy would be pursuing across one anyway.

### D12 — several bridges per link, placed at random — ✅ DONE

Two config values:

* `HEIGHTMAP_BRIDGES_PER_LINK` (default 1) -- how many plank bridges each link
  between two islands carries.
* `HEIGHTMAP_BRIDGE_MIN_GAP` (default 6 tiles) -- the closest two bridges on the
  same link may sit.

`_seat_corridors` is restructured from a per-corridor loop into a per-*link*
one. It has to be: seating picks the lane with the shortest crossing, which is
deterministic, so every bridge on a link would have landed on the same lane.
The viable lanes -- those where both islands offer a sea-level beach -- are now
computed once per link, shuffled with a per-pair seeded RNG (the trick
`_connection_lane` already uses, so no world RNG is consumed), and taken
greedily subject to the gap.

A link's *first* bridge always survives, falling back to the shortest crossing
when the gap leaves no room, since dropping it would disconnect the world; the
extras are discarded. `_seat_corridors` returns the survivors rather than
mutating in place.

Verified over 14 seeds: at 1/2/3 per link every link gets its full count, and
the **minimum observed gap is exactly 6 tiles**, matching the config.

### A connectivity regression, found while testing the above

Checking that extra bridges did not break routing turned up something worse
that was already there:

| bridges per link | seeds (of 16) with an unroutable room |
|---|---|
| 1 | **3** |
| 2 | 1 |
| 3 | 0 |

**Obstacles are sealing islands.** Rebuilding the same worlds with the obstacle
list emptied: **0 cells unreachable** on all three bad seeds, against 1,036 /
1,194 / 2,216 with them. It is not the bridges -- both ends land on plain
ground, confirmed by testing each end against whichever room contains it.

Density is clearly implicated: at `_GRID_OBSTACLES_PER_1000` 85 the three seeds
lose **4,446** cells between them, at 44 they lose **406**. So D8's density
bump made a pre-existing problem an order of magnitude worse rather than
creating it.

*I could not separate size from density.* The A/B reported identical numbers
for old and new radii, which is not credible -- `entities.obstacle._Kinds`
caches the radii on first use and the module reload in that harness did not
clear it, so both runs almost certainly used the same values. The density
figures come from a path that does not have that problem and are the ones to
trust.

More bridges only **mask** this: a second crossing gives the fill another way
in when one mouth is walled off. The root cause is that `_flight_keepouts`
(D5) protects flights and nothing protects a one-tile shore neck or a terrace's
narrow waist, where a radius-30 rock closes the gap outright.

**Proposed fix**, mirroring a pattern already in the generator -- `_carve_lakes`
undoes a lake that cuts a room in two: after scattering, flood each room over
`walk_links` treating a cell as blocked when an obstacle covers its centre, and
drop the obstacles that strand anything. Prevention is the cheaper alternative:
refuse a placement on a cell with too few walkable neighbours, which is where a
neck is.

Not implemented -- it is a generation change and wants deciding, not guessing.

---

## LD-9: the per-island biome pool

`tilemap_7` was the last of the three ground sheets with nowhere to go. The
height-map worlds read a fixed `heightmap_floor_sheets` map --- floor 1 sand,
floor 2 rock, on every island of every seed --- which had only ever been
labelled a stand-in. That key is gone. The tilesets are now listed in
`data/terrain.json` as `heightmap_biome_pool` **with no floor attached**, and
each island draws its own terraces from the list.

The rule was *at least three tilemaps per island, and no two adjacent floors
share one*. It lands in two halves.

**Level 0 is never drawn from the pool**, and that is a constraint rather than
taste: it is the only terrace that meets the sea, so it is the only one that
needs a shoreline block with real surf in it, and all three pool sheets are
flagged `shoreline: false`. Level 0 keeps the room-kind palette and thereby
supplies the island's first tileset for free; the pool only has to cover the
raised terraces. A test asserts the pool offers at least one material the kind
palettes do not, since otherwise level 1 would have no legal choice.

**Each raised level differs from the one below**, level 1 included.

### The rule compares materials, not filenames

The first cut compared sheet paths, passed its tests, and rendered islands whose
shore and first terrace were one continuous green with a cliff line drawn
through it. `tilemap_7` is a different *file* from `tilemap_1` but its ground was
built from `tilemap_1`'s grass: measured on the interior tile it sits **6.4 RGB
units** away, against 104 for the rock sheet and 110 for the sand. Two files,
one material.

So `data/terrain.json` now names each sheet's material in `sheet_biomes`
(`tilemap_1`--`5` and `tilemap_7` grass, `tilemap_6` rock, `tilemap_8` sand) and
the adjacency rule compares those. An unlisted sheet is its own family, so a new
tileset defaults to "unlike everything" rather than silently pairing itself with
something it happens to resemble.

The effect is visible immediately: with every level 0 grass, level 1 can only be
rock or sand, while level 2 is free to be grass again --- which is how
`tilemap_7` finally gets used, as a grassy summit above a rock or sand terrace.

### Mechanics

`world/terrain/biome.py` holds the picking rule and nothing else.
`floor_palette(seed, room_id, levels, pool, base, family)` shuffles the pool
under a `random.Random(f"{seed}:biome:{room_id}")` --- constructed there, so it
consumes nothing from the world's own stream and the same seed still generates
the same world whether or not anything asks for a palette --- then walks the
levels upward taking the next sheet whose material is not the one below. A
shuffle over a pool at least as large as the terrace count cannot repeat at all,
so the walk only does real work when the pool is smaller; with a pool of one it
returns that sheet throughout rather than raising.

`TileSheets.sheet_for` grew a third parameter, `room`, which is what makes the
answer per-island; palettes are computed once per room and cached, because the
painters ask for the same room's sheet dozens of times a bake and every answer
has to agree. Every call site already had a room in hand.

Three of those sites originally passed no `kind` at all, and adding one would
have changed what an LD-8 floor-0 room renders (kind palette instead of the
plain ground sheet). They pass `room=` by keyword and leave `kind` alone.

---

## LD-9: obstacles no longer seal the world, and lakes read as lakes

### The seal

D8 raised obstacle density from 1.8 to 47.5 per thousand cells and their radii
with it, and something went quiet rather than loud: enemies that could not route
simply stood still. Measured on the **large** navigation class -- 48 px lattice,
22 px body -- four of ten sample seeds lost between 1,300 and 6,300 reachable
cells, one of them **69% of the world**, while the same worlds with every
obstacle removed lost **none**. The small class was barely affected (1--86 cells,
nooks behind a rock), which is why nothing had shown it: the common enemies fit.

Two things were wrong.

**The keep-clear test used the obstacle's centre.** `rect.collidepoint(x, y)`
let a rock sit one pixel outside a bridge mouth and still put thirty pixels of
itself across the only way in. It now tests the circle. On its own this fixed
some seeds outright -- one went from 6,315 unreachable cells to 20 -- and left
others exactly as they were.

**Which is the second thing: the pinch is not always at a mouth.** Two obstacles
can close a neck of ordinary ground that no keep-clear rule knew to protect. Any
geometry rule is a guess about where the choke will be, and this one guessed
wrong often enough to matter.

So `world/gen/repair.py` does not guess. It asks the question that actually
matters -- can the widest body still reach everywhere bare terrain allows -- and
removes the specific obstacles standing in the way. Same shape as
`_carve_lakes`, which cuts a lake and puts it back if the room came apart, but
checked against the **navigation lattice the game steers on** rather than the
generator's own adjacency, because it is the lattice that decides whether a body
fits.

Each round is a Dijkstra whose edge weight is *the number of obstacles that
would have to go*, so a region is reopened through its cheapest pinch rather
than by clearing the first path found. Result: **0 sealed cells on 20/20 seeds**
at the large class, for an average of **4 obstacles removed out of ~261**. On
the small class the residue is 2--6 cells per world of ~21,000 -- single 32 px
nooks, not regions -- and repairing the coarse class is what repairs both, since
a route the 22 px body walks the 16 px one walks too.

The radius-aware mouth test now earns much less than it did alone: with the
repair in place it saves 47 removals against 52 over fifteen worlds. It is kept
because preventing a seal beats repairing one, and because testing an obstacle's
body rather than its centre is simply the correct question.

**Both are height-map only**, and `config.HEIGHTMAP_UNSEAL` can switch the
repair off. The seals were measured on the height-map worlds; the LD-8
generator is pinned seed by seed in the tests that describe it, and widening a
rule there would rewrite those worlds for no benefit. The off switch is not
decoration -- `test_the_repair_has_teeth` uses it to prove the seals are still
there without it, so the passing case cannot pass trivially.

**Cost, honestly:** one coarse navigation grid per world. Generation goes from
0.18 s to 0.35 s, and the suite from 110 s to 199 s. Profiling puts 0.19 s of
the 0.23 s in `NavGrid.__init__` (`_point_on_floor` and `_elevation`), not in
the repair's own code, so cutting it further means optimising shared navigation
code rather than this stage.

### One-tile lakes

The brief: a lake is at least three contiguous tiles on one terrace, line or L,
no single-tile ponds.

Measured first, and the floor was already met -- the smallest lake across twenty
seeds was **five** cells and every one sat on a single level, because accretion
only ever steps onto ground of the seed cell's own level. There were no
landlocked void pockets either.

What the eye was actually catching was a **one-tile arm hanging off a bigger
blob**. Rendered, a spur is worse than a lone pond: the surrounding ground's
shore fringe overdraws most of it and what survives is a speck stuck to the
shoreline. Forty-three of them across twenty seeds.

`_trim_lake_stubs` peels leaves -- cells with fewer than two water neighbours --
**repeatedly**, because taking a two-tile arm off exposes its base as a new leaf
and one pass leaves that behind. The loop stops the moment another peel would
drop the lake under three, which is exactly what lets a bare line or L of three
through: every cell of those is a leaf, so a flat "no leaves" rule would forbid
the shapes the brief allows. A long thin snake therefore erodes to three tiles
rather than being kept at length -- the right trade, since a one-tile-wide
channel is a ditch and suffers the same fringe overdraw.

After: sizes 3--22, **zero** lakes under three, **zero** multi-level lakes,
**zero** spurs on any lake bigger than three.

---

## The `test_smoke` flake was two bugs, one of them the game's

The smoke test drew a fresh `run_seed` every run and failed about one run in
three on `kills >= 5`. It seeds five chasers next to the player and asserts the
starting weapon kills them. Two independent causes, found by pinning the seed
and sweeping twenty of them.

**Four seeds in twenty had nowhere to put the enemies.** The five went to fixed
offsets 70 px *south* of the player. On a height-map world the player often
starts on a summit whose southern rim is a cliff, so four of the five landed
over the drop -- `level_at_point` returned the no-surface sentinel -- and never
came back to be killed. The test now asks the map where a body can stand:
`is_walkable(p, radius, frm=origin)`, which is the map's own question with the
elevation rule included, so a spot across a drop is rejected rather than
merely being off the floor.

**Then it failed twenty in twenty**, which is how the second cause surfaced. The
third kill is usually enough XP to level up, and a level-up pushes an overlay
that stops the world until it is answered. The first loop never answered it, so
the state machine sat in `LevelUpState` for the remaining fourteen seconds and
the count froze wherever it was. Whether that landed before or after the fifth
kill was the race. The boss loop further down had always dismissed level-ups;
the first one now does too.

Both fixed: 20/20 pinned seeds kill five, and 40 consecutive runs of the real
test with its random seed all pass. The seed stays random deliberately --
booting a different world every run is most of this test's value -- so the fix
had to be making the assertions independent of the world, not pinning it.

### And a real crash found on the way

The intermittent `KeyError: 'spread_deg'` seen alongside the flake is not a test
problem. `Weapon._fire_projectiles` reads `spread_deg` with a hard subscript
once a weapon fires more than one shot, and a `<weapon>:projectiles` Multishot
upgrade is generated for **every owned weapon**. `arcane_bolt` and `thunder_orb`
are both `category: projectile` and both shipped without the field, so taking
their Multishot crashed the run outright.

Fixed in `data/weapons.json` -- 10 degrees for the homing bolt, 14 for the slow
orb -- and not with a default in code: a fallback there would be per-weapon
tuning living outside the data, against the standing rule. Two tests now cover
it, one asserting every projectile weapon declares a spread and one actually
pushing each weapon past one shot, since the failure is a KeyError deep in a
firing path rather than something the data check alone would catch.

---

# LD-10 — room generation tweaks

Four things the ten full-world screenshots exposed that room-level crops never
did. Recorded as a plan before any of it was written, with the measurement that
motivates each, so the intent survives if the work is picked up cold.

## The brief

1. **Single inland water tiles.** The minimum-three rule the lakes got must
   cover these too -- either grow the hole to three tiles without breaking the
   floor's connections, or fill it with an adjacent floor tile that does not
   interrupt pathing.
2. **Shores are too straight.** A run of 4-5 tiles at the same coordinate should
   force the next one to step in or out.
3. **Three topographies.** Boss islands: big and relatively flat, revisited
   later. Volcanic: what we have been building, up to three floors -- *and it
   must also be able to be only two*, which today it cannot. Small: at most two
   floors, about half the area. Elite rooms are gone.
4. **More rooms**, with more variety in where they sit.

## What the measurements said

**The single water tiles are not lakes.** 43 one-tile and 156 two-tile
near-enclosed holes across seeds 1-10, and **199 of 205 are cells absent from
the grid entirely** -- open sea bitten into the coastline, not `LAKE` cells. The
lake minimum re-verified clean over 30 seeds: zero components under three. So
the rule added in LD-9 works and simply guards the wrong stage. These come from
`_carve_bays` and the coast walk, and from `_prune_unreachable` /
`_face_the_sea` taking cells away afterwards.

Of those holes, **147 of 156 have uniform neighbour levels**, so a safe fill
covers 94% and the grow fallback has to handle nine. **73 of 156 (47%) have
their south side open**, which is what justifies a third `_face_the_sea` call:
nearly half the fills would otherwise leave ground with open sea below it and no
face under it.

**The straight shores are an amplitude problem, not a hold-length one.**
`_walk` already holds each inset only 2-3 columns. The coast margin is 4 (and
the north wall uses `margin - 1` = 3), so a walk stepping +/-1 or +/-2 hits 0 or
`hi` constantly and *sticks there*. The north shore has the smaller amplitude
and the worse histogram, exactly as that predicts: 24% of west-shore runs are 5
tiles or longer, with a hard spike at 12+ (23 runs west, 50 north). Islands fill
**90% of their own bounding box**; 8 of 120 are perfect rectangles, which is the
margin-0 fallback firing and returning a ruled line.

**"Up to 3 floors" and `HEIGHTMAP_TIERS = 2` mean the same thing** --- the code
counts tiers above the base, so `tiers 2` is levels 0/1/2. The brief's *"it can
also be of only 2 floors"* is `tiers 1`, and that case **does not exist today**:
generation is a coin flip, 65% get all three floors and 35% get one, nothing
between.

**Land is 24% of the world bounds** (min 20.1%, max 32.6%) and every world has
exactly two undecorated islands -- start gets 0-2 obstacles, boss always 0.

## Design notes settled before starting

**Topography is not a room kind.** Kind (start / boss / shrine) and topography
(volcanic / small / castle) are orthogonal -- a shrine can sit on a small
island. Topography gets its own declared table, following the shape of
`SPECIAL_KINDS` rather than joining it.

**The coast parameters belong in that table.** A future `castle` type is
described as "more squared", which is a coast setting, not a new algorithm: it
declares a low margin and gets squared shores. That also gives the coastline
work its off switch for free -- reverting is selecting the `classic` preset
rather than a special-cased flag.

**The bridge count is decided in the wrong place.**
`HEIGHTMAP_BRIDGES_PER_LINK` duplicates corridors at link-creation time, before
kinds are assigned and before any grid exists. Per-topography allowances need
that decision moved into `_seat_corridors`, which already runs after the grids
are built, already groups per link, and is the only place that knows where each
island's beaches are. Where two endpoints disagree the lower wins, and a small
island's cap is written **per side** rather than per link -- the two coincide
today, since the lattice gives at most one neighbour per side, but they will not
if a chunk ever hosts two islands.

## A — inland holes — ✅ DONE

`_fill_holes` runs last in `build_grid`, after `_prune_unreachable`, because
every stage above it can leave a hole behind: a bay bitten in by the coast walk,
a pocket the prune emptied. `_face_the_sea` then runs once more, and that is not
a formality -- 73 of the 156 measured holes have their south side open, so
nearly half the fills put new ground over open sea with nothing under it.

**Filling won outright; widening is not implemented.** The brief offered either,
and building both made the choice obvious. A hole with mixed neighbour levels
sits at a **cliff foot**, and widening it there produces exactly the shape
`_carve_lakes` already refuses -- water lapping a wall, which the terrace
boundary has no shoreline art for. It also *removes* walkable ground, so it has
to be guarded against cutting the room in two, while filling only ever adds. The
first cut did implement widening, and it showed: 25 lake components of one and
two tiles appeared, because a widened hole is part absent cell and part `LAKE`
and only the taken half is a lake.

So every hole is closed with terrain, and which terrain turns on one question:
**is the ground directly north of it higher?**

* **Higher to the north** -- the hole is under a terrace, so it becomes part of
  that terrace's wall: a `CLIFF` at the north neighbour's level.
* **Otherwise** -- ground at the *lowest* neighbouring level. A lateral step up
  to a taller terrace east or west needs no face at all; that edge is drawn from
  the raised block, and only a southward drop needs stone.

Neither branch consumes walkable ground, so no connectivity check is needed and
none is done -- which is what makes this pass cheap and unable to strand
anything.

Measured after, over the same ten worlds: **0 one-tile and 0 two-tile** enclosed
holes, against 43 and 156 before; 0 lake components under three; 0 `check_grid`
failures. Suite **796** green, four new tests -- including one asserting no
raised ground anywhere has open sea directly beneath it, which is the invariant
the extra `_face_the_sea` call exists to keep.

## B — the coastline — ✅ DONE

`rugged` is now the active preset; `classic` restores the old shore, and a test
pins it. Measured over ten worlds:

| | runs of 5+ | runs of 12+ | box fill | rectangles | mean land |
|---|---|---|---|---|---|
| classic | 38.1% | 89 | 0.92 | 2 | 952 tiles |
| **rugged** | **11.2%** | **33** | **0.84** | **0** | **976 tiles** |

### The brief's rule, on its own, does almost nothing

Forcing a step after four held positions at the *old* amplitude moved runs-of-5
from 37.9% only to 29.9%, left the 12+ spike at 84, and produced **more**
perfect rectangles than before -- five against two. That is worth stating
plainly because it was the obvious fix and it is not the fix.

The cause was never the hold length. It was **clamping at a small amplitude**:
with the margin at 4 and steps of one or two, the walk reaches 0 or the margin
constantly and the clamp pins it there for hold after hold. The north wall used
`margin - 1`, a smaller amplitude still, and had the worse histogram -- exactly
as that predicts. Raising the amplitude alone got to 13.1%; the two together to
11.2%. So the run cap does earn its place, but only once there is room to
wander, and it also needs a second half nobody would guess at: when the clamp
hands back the same value the cap is silently defeated, so `_walk` forces a move
in the only direction there is room for.

### Two things that fight the ragged coast

**`keep` clips it straight again.** Raising `HEIGHTMAP_COAST_KEEP` to 3 or 4 --
the obvious way to let rooms grow without growing the chunks -- undid most of
the work: runs-of-5 back to 18.5% and 20.0%, the 12+ spike back to 74 and 82,
and rectangles reappearing. `coast_mask` intersects the walk with a rectangle
inset by `keep`, so a bigger band chops the wander back to a ruled edge wherever
it strays. `keep` stays at 2.

**A bigger margin eats the top terrace.** At the old room size a margin of 6-8
cost the islands their level-2 cap outright -- the count fell to 25 of 60 at
margin 7, and to 18 at margin 8. That is *topography deciding itself by
erosion*, which is precisely what C exists to choose deliberately, so it cannot
be left to the coast. The room grows in step to pay for it: 46-52 x 28-32
against 44-50 x 26-30, and the chunk with it. Land per island came out slightly
**up**, 976 tiles against 952, and the bridges no worse -- the horizontal
maximum actually improved, 41 tiles to 29.

### Two bugs found on the way

**`_fill_holes` was eating lakes.** `_water_blobs` took its bounding box over
*non-lake* cells, so a lake straddling that box had its outside half invisible
to the walk and its inside half swallowed as a two-tile hole. On seed 0 a
four-cell lake came out of the pass as two. A `LAKE` now counts as present, not
as water to be closed -- lakes have their own minimum and their own stub trim --
and a gap entirely surrounded by pond becomes more pond rather than a one-tile
island in the water.

**A chunk must be an even number of tiles.** Setting 29 rows put every room half
a tile off the world grid and `LevelIndex` could no longer place a room's cells
at all -- eleven tests in `test_elevation` and three in
`test_projectile_elevation` went red at once. The world's bounds are inflated by
one whole chunk before everything is shifted to the origin, and `Rect.inflate`
moves the top-left by *half* of that. Now commented at the constant.

### One test was asserting the wrong thing

`test_no_seed_is_sealed_by_its_obstacles` compared against **zero**, and the
ragged coast broke it -- 279 unreachable nav cells on seed 0. Measured, that is
terrain, not obstacles: bare terrain leaves 293. A 22 px body cannot stand on a
one-tile spit, and the ragged coast makes many more of them. The regions are
fringe rather than territory -- on seed 0, thirty single cells, twenty pairs,
nineteen triples, largest anything 29 cells, about four tiles.

So the test now asserts what the repair actually promises: **obstacles never cut
off more than bare terrain does**. The teeth test compares the same difference,
so it still cannot pass trivially.

Suite **800** green, five new tests.

## C — topography — ✅ DONE

`classic` is gone; `rugged` is the only coast preset. The table stays a table
because a topography **names** the preset it wants, which is how a future
"castle" island gets squared shores without new code.

### The table

`config.HEIGHTMAP_TOPOGRAPHIES`, declared in the spirit of `SPECIAL_KINDS` --
adding a type is an entry, not a branch. Topography is deliberately **not** a
room kind and does not join `SPECIAL_KINDS`: kind says what happens on an
island, topography says what shape it is, and a shrine can stand on a small one.
A test asserts the two vary independently, because if they did not this would
just be `SPECIAL_KINDS` again.

Measured over fourteen worlds:

| | islands | mean walkable | floors above sea |
|---|---|---|---|
| `volcanic` | 42 | 923 tiles | 15 two-floor, 27 three-floor |
| `small` | 28 | 449 tiles | 15 flat, 13 two-floor |
| `boss` | 14 | 1,334 tiles | always flat |

**The two-floor volcanic island now exists.** The old generator could not
express it at all -- a coin flip between all three floors and one, nothing
between. `tiers` is an inclusive range drawn per island instead.

**`size` is a linear scale on the rect, not an area ratio**, and the difference
matters: the coast margin is an absolute number of tiles, so it eats
proportionally more of a smaller island. 0.7 linear measured out at 0.38 of a
volcanic island's walkable area; **0.76 gives 0.49**, the "about half" the brief
asked for. Boss lands at 1.44x.

Rooms are **resized after** the tree is grown rather than drawn at a different
size, because the topography cannot be known until the boss island is
identified, and that happens after the rooms are built. The rect keeps its
centre, every dimension stays even in tiles, and it is re-snapped to the world
grid -- the same guarantee the original placement makes.

### Elite rooms: gone from the height-map worlds only

Dropping `elite_arena` outright re-labels rooms in the **legacy** generator too,
and a re-labelled room is shaped and scattered differently: four pinned-seed
LD-8 tests moved, none of which have anything to do with elite arenas. So
`special_kinds(heightmap)` retires it for the height-map worlds and leaves the
legacy pool alone -- the same gate `_blocks` and `unseal` already use. The
feature's own code stays in place and dormant.

### Two tests were measuring the world instead of themselves

**`test_the_repair_has_teeth` needed a wider seed range.** Since the islands were
reshaped, a bad obstacle seal is rare but severe rather than common and small:
across twenty seeds the deltas run 0, 0, 1, 2 ... 10, 14, 80, 567, **2319**. The
first eight top out at 14, so the range the rest of the module uses would have
let it pass while proving nothing.

**`ProjectileTrailTests` was firing into a random world.** It builds a game with
an unpinned run seed and shoots 300 px east to count trail puffs; with D10 live,
the shot dies the moment it crosses onto higher ground, so on the seeds where the
hero starts below a terrace the count collapsed to 0 or 1 against the expected
4-6. It failed in the suite and passed alone -- a different random world each
time. `_shoot` now sets `fire_level = NONE`, the documented opt-out, with the
reason written down; the elevation rule has its own module.

Suite **807** green, eight new tests.

## D — more islands, off-centre, with per-island bridges — ✅ DONE

Nine islands a world, drawn off the centre of their lattice cells, and how many
bridges a link carries is now a property of the two islands. Suite **817** green,
nine new tests.

### Bridges are decided where the beaches are

`HEIGHTMAP_BRIDGES_PER_LINK` is gone. Links are laid one apiece and cloned in
`_seat_corridors`, which is the only place that runs after the grids exist. The
allowance is `min` of the two ends -- both have to accept a crossing -- and it
is counted **per side of each island**, not per link. Those are the same thing
today, since the lattice gives a room at most one neighbour per direction;
writing it per side is what keeps it correct if a cell ever hosts two. Volcanic
islands take two, small and boss one, so a world runs 8 to 15 bridges against
the tree's minimum of 8.

### The offset, and the bound that makes it safe

Bounding the *rect against its chunk* -- at most one tile of overhang per side --
rather than deriving a slack from the nominal sizes. The first cut used
`(chunk - room) // 2`, which is wrong for an odd-width room: centring one leaves
it half a tile off the lattice, the snap moves it, and the offset stacks on top.
That produced **two shared land cells** between neighbouring islands, the exact
failure the guarantee exists to prevent.

**And it caught a second one that centring had been hiding.** The boss island
was declared at `size: 1.15`, which puts a 52-tile room at 60 in a 50-tile cell
-- five tiles of overhang against everyone else's one. Centred, coast erosion
and luck had covered it; offset, it shared land cells reliably. `size` may not
take a room past the chunk plus two tiles, and a test now asserts that of the
table itself.

**Boss islands are flat but not big.** 1.0 is the cap, and at 1.0 a boss island
measures about the same as a volcanic one, so the "pretty big" half of the brief
is *not* delivered. It needs either a bigger lattice cell or a per-topography
`HEIGHTMAP_COAST_KEEP` -- a boss island could overhang five tiles safely if its
own land were held five tiles inside its rect, at the cost of a straighter shore
on that island. Boss islands are a deferred conversation, so the test asserts
only flatness and says why.

The offset costs nothing measurable in bridge length: median 12 tiles with it
against 13 without, and the long tail (max 53 against 47) is the nine-room tree,
not the offsets.

### Two bugs the room count exposed

**`unseal`'s round cap was silently too few.** It was 8, which was enough for six
islands; at nine, seeds finished with a handful of cells still walled off and the
"obstacles never cut off more than bare terrain" test went red on five. The cap
is a safety valve, not a budget -- the loop already stops when nothing is sealed
-- so it is 40 now.

**Which made the repair the largest cost in generation.** At 60% of a 713 ms
world, profiled to `_cheapest_seal` and `_reachable`. Two changes: inlining
`in_bounds` and `idx` in the inner loops (three and a half million calls apiece,
and the arithmetic is cheaper than the call) took it to 651 ms; then labelling
the sealed regions and reopening **all of them in one Dijkstra sweep** instead of
one per round took it to **511 ms**, with sweeps per world dropping from about
six to **one**. Popping in cost order means the first cell of a region off the
queue is that region's cheapest entry, so nothing is given up in exchange.

### Land is still 19% of the bounds

Down from 22.8% at six islands -- more rooms means a longer tree and more sea
between the branches. The offsets help how the world *reads* rather than how
densely it packs; genuinely tighter packing is the lattice change that was
scoped out of this item.

## E — shortcut bridges: the world stops being a tree — ✅ DONE

The lattice grows a **spanning tree**, so every route between two islands was
unique and a run backtracked over the bridge it arrived by. `_add_shortcuts`
runs last, once the grids exist and the tree's own bridges are seated, and joins
islands that ended up close together but were never linked -- orthogonal
neighbours the tree simply skipped, and diagonal ones whose rects overlap on one
axis after the placement offset.

### It was surveyed before it was built, and the survey was right

Over twenty worlds there are 560 unlinked pairs, but they thin out fast: **313
(56%) share no row *or* column span at all**. A `Corridor` is an axis, a rect
and a lane, and the plank art comes from horizontal and vertical end caps, so
those cannot be joined without new art and a new corridor model -- left alone.
Of the 247 that do have a lane, only 71 are within fifteen tiles, and running
the real seating machinery on them beforehand said **16 of 44 candidates would
actually seat**, about 1.3 a world. That is what it delivers: 10.6 bridges a
world becomes 11.9.

The limit is not distance. `options` wants a *beach* -- plain sea-level ground,
the first land the scan reaches -- on the same lane on **both** islands, and
ragged coasts rarely line up. `reach` still carries a `strict` flag its own
docstring says the caller drops "when no lane at all offers a beach on both
sides", and nothing has ever passed `strict=False`. That is where the remaining
yield is, at the cost of planks running up onto a terrace.

### One bridge does far more than its share

| | links/world | of them the only way there | worlds with a loop |
|---|---|---|---|
| tree only | 8.00 | **8.00 (100%)** | 0/20 |
| with shortcuts | 9.30 | **4.35 (47%)** | 18/20 |

A single cycle in a nine-island tree takes a whole *chain* of links off the
critical path at once, which is why +1.3 links halves the count of crossings
that are the only way to somewhere. The softer measures move as expected but far
less: mean hops from the start 2.19 -> 2.06, mean pairwise 2.78 -> 2.49.

### What it has to respect, and what it deliberately does not touch

* **The per-side allowance**, via the same `used` counter the tree's own bridges
  fill -- a small island still takes one crossing a side.
* **`Room.neighbors` and the corridor list**, together: several callers read the
  graph and never look at the corridors.
* **`boss_id` is not recomputed.** It was fixed from the tree long before this,
  so "farthest from the start" keeps meaning what it always did rather than
  quietly moving when a shortcut lands.

No RNG is drawn -- candidates are sorted by gap and then by room id -- so a seed
still builds the same world. Nothing downstream assumed a tree: the flow field
is geometric and simply gains routes.

Suite **817** green, six new tests, one of which turns the pass off and asserts
every link *is* a cut edge without it, so the 47% cannot be read as a property
of the lattice.

## F — bridges that are not causeways — ✅ DONE

A crossing of thirty-odd tiles reads as a causeway, not a bridge. Before:
median 12, p90 21, p95 24, p99 30, **max 38**.

### The obvious fix would not have worked, and measuring said so first

A length cap can only *refuse* a bridge, and a link the tree needs cannot be
refused -- dropping it cuts the world in two. So the question was whether the
long ones were long by choice. They were not: of 238 bridges, only **8 were more
than two tiles longer than the shortest lane their link had**, and none of those
eight was in the long tail. Every genuinely long bridge was already taking the
best lane available.

The distance is created in **placement**. The offset that gives the world its
variety also lets two linked neighbours drift apart inside their own cells, and
a crossing that started at the lattice spacing ends up ten tiles longer.

### So the fix is in two halves

**`_toward_neighbours`** narrows an offset range so an island never drifts
*away* from what it is linked to. Deliberately weak: it removes the half of the
range that opens the gap, and only when every linked neighbour sits on the same
side of that axis. A room pulled both east and west keeps its full range,
because moving either way shortens one crossing and lengthens the other.

**`HEIGHTMAP_BRIDGE_MAX`** (20 tiles) then handles what placement cannot. Lanes
inside the cap are the pool a link draws from; an **optional** crossing -- a
second bridge on a link, or a shortcut -- is simply not built when none
qualifies, while a link's *first* bridge falls back to the shortest lane there
is. That also fixes the eight sub-optimal picks, since a short lane is now
preferred rather than drawn at random from all of them.

| | median | p90 | p95 | p99 | max | over 24 |
|---|---|---|---|---|---|---|
| before | 12 | 21 | 24 | 30 | 38 | 12 of 238 |
| after | **11** | **18** | **19** | **23** | **25** | **2 of 236** |

Loops fall slightly, 1.30 a world to 1.20, because the cap refuses the longest
shortcuts -- which is the trade being asked for. No island collisions; land fill
unchanged at 19.5%.

### A test that could not be written the obvious way

Asserting the placement rule from a finished layout does not work, and the
failed attempt is worth recording: the world is shifted to the origin at the end
of generation so a room's rect no longer relates to its cell, **and**
`Room.neighbors` has by then gained the shortcut links, which are added after
placement and were never part of the bias. The rule is a pure function of the
tree, so it is tested as one.

Suite **826** green.

### The cap swept, and settled at 16

Five seeds each at 8 / 12 / 16 / 20 / 24:

| cap | bridges | links | loops | links that are the only way | median / p90 / max |
|---|---|---|---|---|---|
| 8 | 10.4 | 8.2 | 0.20 | **90%** | 9 / 12 / 18 |
| 12 | 11.2 | 9.0 | 1.00 | 56% | 10 / 13 / 18 |
| **16** | 11.8 | 9.6 | 1.60 | 38% | 10 / 16 / **18** |
| 20 | 11.8 | 9.6 | 1.60 | 38% | 10 / 17 / 20 |
| 24 | 11.8 | 9.6 | 1.60 | 38% | 11 / 17 / **25** |

**16 and 20 build the same graph** -- same bridges, links, loops and cut-edge
share -- and 16 is simply shorter, so it is strictly better and is the default
now. **8 is too tight and costs the feature**: loops collapse to 0.2 a world
and 90% of links go back to being the only way somewhere, and it does not even
buy short bridges, because half the crossings are tree links already on their
shortest lane. **24 is where the cap stops filtering** and the maximum runs away
again.

A first pass at 1--4 was run before this and is worth recording as a null
result: the shortest bridge any world can build is about four tiles, so a cap
below that refuses every *optional* crossing and nothing else. Loops went to
zero in all twenty worlds, and caps 1 and 2 produced byte-identical worlds.

### The test that came with it was the wrong shape

`test_almost_no_bridge_exceeds_the_cap` asserted a percentage, and tightening
the cap broke it -- from 0% over at 20 to 7.9% over at 16. That is not a
regression: the bridges "over" are tree links the cap was never able to refuse,
so lowering it mechanically raises the count. The tests now assert what the
code actually guarantees -- **at most one bridge on any link may exceed the
cap** (a second bridge or a shortcut is always refusable) and **that one had no
shorter lane**, checked by re-seating the link on its own.

## G — topography chooses the tilesets, level 0 included — ✅ DONE

Which tilesets an island may wear is a property of its **topography** now, and
that covers level 0. `boss` owns 4, 5 and 6; `small` owns 1--5; `volcanic` owns
all eight.

**`room_palettes` was choosing level 0 by room *kind***, which is orthogonal to
shape -- a shrine on a small island was picking its ground from the wrong axis
entirely. It stays in the data for the LD-8 generator, which has no
topographies, and the height-map path no longer reads it.

**The "no beachless sheet at the waterline" rule is derived, not listed.** Level
0 is the only terrace that meets the sea, so a sheet flagged `shoreline: false`
has no surf block for it. The filter is that flag, which means a ninth tileset
cannot silently end up on a shoreline it has no art for; a topography opts out
with `allow_beachless_shore`, and `boss` does, on purpose.

Measured over eight worlds: boss islands wear only 4/5/6, small only 1--5, and
volcanic take 1--5 at level 0 with 6 and 8 above -- 6, 7 and 8 never reach the
waterline without being asked to.

### What the boss island on `tilemap_6` actually looks like

Three of twelve seeds drew it. It reads as a large flat slab of pale blue-grey
stone, and **the missing surf block is much less visible than expected**: the
animated foam is a separate layer keyed off `grid_shore`, not off the tileset,
so the island still gets a white outline where it meets the water. Verified
rather than assumed -- `has_shoreline` is `False` for that sheet and the world
still carries its full set of foam anchors.

Whether it is *wanted* is a taste call, but nothing about it is broken, and a
bare stone arena arguably reads more deliberate than the bare green one it
replaces. Boss islands carry no obstacles at all (the scatter skips them by id),
so every one of them is a big empty slab whatever tileset it wears -- which is
the thing worth fixing before the tileset choice matters much.

### A consequence of the rules meeting each other

**A `small` island cannot satisfy the adjacency rule.** Its five tilesets are
all filed as one material, so every terrace boundary on a small island is
green-on-green with only a cliff line between. That is rule 3 ("small islands
use 1--5") meeting the material table, and the fix is the finer material split
that step 2 of the proposal was already going to make -- `tilemap_4` is olive
and `tilemap_5` teal, both currently called "grass". The test now asserts the
adjacency rule only where an island owns more than one material, and says why.

## H — six biomes instead of three materials — ✅ DONE

The old split was `grass / rock / sand`, and G showed it was too coarse the
moment a topography owned a fixed set of sheets: a `small` island owns tilemaps
1--5 and **all five were "grass"**, so every terrace boundary on one was
green-on-green with only a cliff line between, and the adjacency rule had
nothing to reach for.

Regrouped on the **measured** mean ground colour of each sheet's interior tile,
which is the honest basis for saying two tilesets read alike:

| biome | sheets | interior RGB |
|---|---|---|
| `meadow` | 1, 7 | 152,182,83 / 152,179,88 |
| `forest` | 2, 3 | 132,174,87 / 97,169,99 |
| `drab` | 4 | 130,152,94 |
| `wetland` | 5 | 87,153,139 |
| `rock` | 6 | 137,185,186 |
| `sand` | 8 | 244,224,125 |

`tilemap_1` and `tilemap_7` are **6.4 RGB units apart** -- one biome by
measurement, not by taste. `tilemap_4` and `tilemap_5` were 40 and 60 units from
the greens they had been filed with, which is the error the coarse table was
making.

**The coarse `family` layer is gone rather than kept underneath.** It existed
only to feed the adjacency rule, and the fine biome now does that directly --
one lookup instead of two, and one fewer place for the two to disagree.

Result over twelve worlds: **108 terrace boundaries, zero with the same biome on
both sides**, where before every small island had one. `small` islands now stack
things like `drab -> forest` and `meadow -> wetland`; `volcanic` reaches
`wetland -> forest -> rock`.

Two data guards came with it, both of which the old table would have failed:
every sheet a topography can wear must name a **declared** biome -- an unlisted
sheet falls back to being its own, which quietly exempts it from the rule -- and
every topography must own **at least two** biomes, which is the precondition for
the rule to be satisfiable at all.

The `biomes` table carries each biome's measured tint and a one-word note for
now; the obstacle and decoration weights land in it next.


## I — a scatter mix per biome — ✅ DONE

*"A rocky layout for tilemap_6 needs a lot more rocks than trees."* Every island
in the world drew from one weighted bag -- `tree 4 / rock 3 / pillar 2 / shrub 3`
at 85 attempts per thousand floor cells -- so a rock summit and a forest shore
scattered identically and only the tiles under them differed.

### The mix belongs to the terrace, not to the island

A volcanic island can wear `wetland -> forest -> rock` up its three levels, so
"this island is rocky" is not a thing that can be said. The floor is split by
**level** first and each terrace scattered on its own terms: its own weights and
its own density, read from its biome's `scatter` block in `data/terrain.json`.

| biome | tree / rock / pillar / shrub | attempts /1000 | achieved /1000 | stone share |
|---|---|---|---|---|
| `meadow` | 5 / 2 / 1 / 4 | 85 | 52.8 | 28% |
| `forest` | 7 / 1 / 1 / 4 | 100 | 74.5 | 19% |
| `drab` | 4 / 3 / 2 / 3 | 80 | 53.0 | 46% |
| `wetland` | 3 / 4 / 2 / 3 | 75 | 38.2 | 56% |
| `rock` | 1 / 6 / 4 / 1 | 140 | 44.3 | 88% |
| `sand` | 1 / 3 / 1 / 1 | 25 | 18.8 | 84% |

Measured over twelve worlds. A forest terrace comes out **80% trees**, a rock
terrace **88% stone** -- the two ends of the same knob.

### Attempts are not obstacles, and rock is where that bites

`per_1000` has always counted *attempts*: placement rejects whatever will not
clear the doorways, the flights and the other obstacles' spacing. That rejection
rate is not the same for every kind -- a rock is radius 30 and keeps a 46 px gap,
so it needs 76 px of clear ground, where a tree is radius 15 and keeps only 22
off another tree. A rock-weighted bag therefore *lands* about a third of what it
draws, against four fifths for a tree-weighted one.

First pass at the numbers gave `rock` 95 attempts and it rendered at 31 per
thousand, sparser than the meadow beside it -- the opposite of a boulder field.
Raised to 140 it lands at 44. `sand` went the other way, 40 down to 25, because
open sand is meant to read as open.

### The palette had to move into generation first

The island's `{level: sheet}` was worked out at **bake** time, from the seed and
the room id. That was a fine place for it while the tile painter was the only
consumer. The scatter is a second consumer, and it runs in a different layer at
a different time -- so either it re-derives the same answer from the same seed,
or the answer moves somewhere both can read.

Two derivations of one answer is exactly how this feature broke once already
(the adjacency rule comparing filenames while the eye compared colours), so the
palette is generation output now: `world/gen/biomes.py` decides it, `Room.palette`
carries it, and `TileSheets.biome_palette` returns it rather than computing
anything. Same shape as the stair rule -- generation classifies, rendering picks
the art. `world/terrain/biome.py` is a re-export shim.

### What was deliberately left alone

The **legacy** mix stays a literal in `world/gen/scatter.py`, frozen. The flat
generator is pinned seed by seed in a dozen tests that exist to describe how it
behaved, and re-weighting it would rewrite those worlds for no gain.

The **tree top-up** (+25%, clumped next to existing trees) still runs world-wide
and unweighted, and it does not need to be biome-aware: it picks its anchors
uniformly from the trees that exist, so a terrace that grew five trees gets five
trees' worth of thickening and a forest gets a forest's worth. It is
proportional by construction.

The fallback for a biome that declares no `scatter` block is the LD-8 mix. That
is a floor, not a per-biome default -- a test asserts every declared biome
carries its own block, so the fallback stays unreachable.


## J — decorations belong to a biome too — ✅ DONE

Same rule as I, one layer down: an entry in `decorations` may name the `biomes`
it belongs to and is then only placed on terraces wearing one of them. An entry
that names none is universal -- the default a new prop gets, and what stops a
terrace being able to come out with nothing on it.

### The registry was lying about what the art is

Half the ids described something the rig does not show. `sprout_a` is a red
mushroom, `sprout_b` a flat grey stone, `twig` a boulder cluster, `flower_a` a
green shrub, and both `mushroom` entries are pumpkins. Tagging them by name
would have put stones in the meadow and shrubs on the summit, so they were
renamed to the art first -- nothing but the registry referenced the ids.

Twelve rigs were sitting unused. They are exactly what the stony biomes needed:
`deco_ground_14/15` are **bones**, `deco_rock_2/4` are big boulders, and
`deco_ground_7/8` are mossy stone. Room props went 19 -> 31.

| biome | what it draws |
|---|---|
| `meadow` | grass, pumpkins, stumps, bushes |
| `forest` | fungi (three), moss, grass, stumps, bushes |
| `drab` | stone, grass, pumpkins, stumps |
| `wetland` | mossy stone, fungi, grass, boulder piles |
| `rock` | stone, boulders, moss, bones |
| `sand` | stone, boulders, bones |

Measured over eight worlds, with no prop found standing outside its tags.

### And a density bug the split uncovered

`per_room` counts were authored against LD-8 rooms of ~60 cells and were being
applied whole to islands of 700-1000 -- the same mismatch the obstacle scatter
had before D8 gave it a per-thousand rate, and nobody had noticed because decor
is small. A sand terrace of 484 cells was drawing about six props.

So each biome carries a `decor.per_1000` alongside its `scatter` block. It sets
the terrace's whole budget and the authored counts become the **weights** by
which its legal props share it, which keeps the hand-tuned ratios (four pebbles
to one stump) while the total follows the ground. Rates: forest 75, meadow and
drab 60, wetland 55, rock 45, sand 40. Achieved, over eight worlds:

| biome | props /1000 before | after |
|---|---|---|
| `meadow` | 23.1 | 45.2 |
| `forest` | 34.3 | 50.1 |
| `drab` | 30.9 | 43.2 |
| `wetland` | 30.9 | 38.8 |
| `rock` | 25.0 | 35.2 |
| `sand` | 24.7 | 41.8 |

Achieved lands under the rate because placement still refuses a spot that is
too near an obstacle, another prop, or the island's centre disc.

A biome that declares no rate scales by 1.0 and uses the counts as written --
a floor, not a default, and the only thing the legacy world ever sees, since a
room with no height map has no palette and stays one unsplit group.

### An hour lost to a screenshot script

The A/B renders showed decor markers with nothing drawn under them, which
looked like the scatter placing invisible props. It was the *script*: room
clutter is not part of `scenery_drawables` -- that block is commented out --
and is drawn by its own `draw_room_clutter` pass, which `PlayingState.draw`
calls and my harness did not. The game was right the whole time. Worth
remembering that clutter is deliberately **not** depth-sorted: it renders under
every obstacle and character, which is why it is all flat ground litter.


## K — the bare islands, and two groups of tree — ✅ DONE

An audit of five worlds said every terrace of 40+ cells carried something --
except that two of the nine islands in **every** world carried no obstacles at
all.

### start and boss were still on an LD-8 rule

`_scatter_obstacles` skipped both by id. The reasons were good when a room was
~60 cells: a safe spawn and a clear fight arena. On a 1,000-cell island it left
about a fifth of all the land as bare slabs with nothing but flat ground litter
on them.

Both scatter like any other island now, each keeping a disc instead of being
skipped whole:

* **boss** -- `_GRID_BOSS_CLEAR_RADIUS`, 8 tiles, about a fifth of the island.
  Enough to fight in; the rim is a boulder field.
* **start** -- `_GRID_SPAWN_CLEAR`, 1.5 tiles. Not special treatment of the
  island, just not dropping a boulder on the pixel the hero materialises at:
  `GameMap.center` is the start room's centroid and the hero spawns exactly
  there. Everything outside it scatters normally.

The **legacy** generator keeps the skip, being pinned seed by seed in tests
that exist to describe it. (Houses were never in that skip: `_scatter_houses`
has always been allowed to build in the start room and only ever excluded the
boss. The test that says the legacy skip still holds had to be written to
allow for that.)

**A bug the arena test caught.** The tree top-up decided its own keep-clear
disc and kept the LD-8 fraction-of-the-room rule even on a height-map island,
so a thicket could grow into the arena the scatter had just held open. Both now
call one `_clear_radius`.

### Two groups of tree, named by the biome

The five tree rigs fall into two groups the eye reads immediately -- pines
(`deco_tree_1/2/5`) and autumn crowns (`deco_tree_3/4`) -- and mixing them
across a terrace was the last thing keeping an island from looking like one
place. Each biome names its group in the `biomes` table: no new file and no new
metadata layer, per the brief.

| group | biomes |
|---|---|
| pine | `forest`, `wetland`, `rock` |
| autumn | `meadow`, `drab`, `sand` |

Assigned the same way the biomes themselves were: by what the ground colour
does with the crown. The pines carry a teal shadow that reads with the deep
green, the damp teal and the blue-grey stone; the yellow crowns belong on the
warm greens and the sand.

The obstacle carries the biome the scatter stamped on it -- generation
classifies, rendering picks the art, the same rule as the palette and the
stairs -- so the bake looks nothing up twice.

**This also un-hid `deco_tree_5`.** The global list holds five rigs and the
variant is a `randint(1, 4)`, so `(variant - 1) % 5` could never reach the last
one: the tree sheet built two sessions ago had never once appeared in a world.
Groups of three and two are both shorter than the draw, so every rig comes up.

### Fewer trees on stone and sand, more dead ones

`rock` and `sand` drop their tree weight from 1 to **0.3** -- reduced, not
banned, because a lone pine on a boulder field is worth having -- and all five
stump props are tagged into both biomes to stand in for what no longer grows
there.


## L — stumps at trunk size, and a forest that does not breathe in step — ✅ DONE

Two small passes over the props, both about the field reading as many things
rather than one.

**Stumps +40%.** Every stump prop's `scale` went up by 1.4 (`stump_a` 0.55 to
0.77, `stump_b` 0.5 to 0.7, `stump_c` 0.7 to 0.98, `stump_d` and `stump_e` 0.55
to 0.77), which puts them at 17-37 px of visible width against a tree's ~115.
A stump should read as the trunk that is left, and at 12-26 px they read as
specks -- which mattered more once the stony biomes started using them in place
of the trees they no longer grow.

**Three tree routines.** Every tree in the world took its frame from one
`pygame.time.get_ticks()` at one fps, so an entire forest swayed as a single
object. This is the same problem the shoreline had, and it takes the same fix:
`tree_routines` in `data/terrain.json`, shaped exactly like `foam_routines` --

| fps | phase |
|---|---|
| 4 | 0 |
| 5 | 2 |
| 6 | 4 |

-- picked per tree by a stable spatial bucket, so a rebake never reshuffles
them and the same seed animates identically twice running. Bucketed at **half**
a tile rather than the foam's full tile: `_TREE_TREE_GAP` is 22 px, so trees
stand closer together than shore patches do and a whole-tile bucket would hand
a pair in the same tile the same clock. Measured on seed 45: 66 / 65 / 86 trees
on the three routines, and 34% of tree pairs within two tiles share one --
which is the floor for three buckets.

The skin entry grew a fifth field: `(anchor_x, anchor_y, fps, frames, phase)`.
Only an animated tree takes a routine; everything else keeps its rig's fps and
a phase of 0, since a one-frame rock has nothing to offset.




## M — side stairs on the plateau flanks — ✅ DONE

An island was crossable only from the south. Every way up sat in a south-facing
wall, so a plateau's east and west faces were sheer for their whole length and
the player walked around to the bottom of the island to change level.

### Why, and the one measurement that decided the approach

`walls._raise_walls` gives stone to **southward** drops only -- a cap's south
rim is the face the camera sees, and the face the tileset draws.
`flights._cut_flights` then *finds* its sites by scanning for `CLIFF` cells, so
the two rules compose into an unintended one: a crossing can only exist where
the camera can see a wall.

The first attempt was a new kind of crossing for the bare flanks entirely --
one tile, its own step rules, its own art. It worked, and it was the wrong
shape for the problem. Measuring the sides properly is what showed why:

| on the east/west quarters of a plateau, over six worlds | |
|---|---|
| positions with usable wall beside them | **722** |
| ...refused **only** for want of the one-row jog | **667 (92%)** |
| refused on anything else (no head / foot / above) | 10 |
| real sites | 45 |

The stone is already there. What is missing is the jog -- and the jog is not
arbitrary: without it the cell you would step on from the side is itself stone,
so relaxing the test would place flights nobody could reach.

So the pass makes the jog and cuts an ordinary flight into it. Same `EWSTAIR`
cells, same art, same `walk_links` and `can_step`. Nothing downstream knows
this pass exists.

### `_cut_side_stairs`

Two or three crossings per **side** of a plateau -- a long east face and a long
west face each want their own way up. A plateau above the first floor takes
about a quarter of that (`SIDE_STAIRS_HIGH`, 0-1): those are small and already
well served by the south rim, and stacking ways up onto a summit nobody
struggles to reach is wasted terrain.

`_carve_side_jog` hands the entry column's top wall cell back to the terrace
and pushes the wall down a row underneath it -- one column, one row, the same
size of edit `_raise_walls` already makes. Every carve is **provisional**: it
is rolled back unless `_ewstair_site` then accepts the site *and* the room is
still one connected piece. Moving a wall cell can seal a terrace as easily as
open one, and only the round trip through the real site test proves it did not.

### The carve may not eat a ledge

The first build sealed a flight. Not one of the new ones -- an ordinary
straight staircase on seed 35, which the large nav class (radius 22) could no
longer thread. Pushing a wall down a row necessarily **consumes a cell of the
terrace below it**, exactly the trade `_raise_walls` makes, and that is fine on
open ground and not fine on a narrow shelf: it pinches the ledge under the
clearance a big body needs.

So a carve now refuses unless the lower terrace runs on past the cell it would
take. That is the honest cost of this pass: it drops the yield from 1.95
crossings a side to **1.36**, because a lot of side wall on these islands sits
on exactly such a ledge. Correctness first -- a stair only half the bestiary
can climb is worse than no stair.

Worth recording because the failure did not look like this pass at all: the
sealed flight was one the scanner had placed, several tiles away, and the
carve had only narrowed the floor it landed on.

### The knob that mattered was not the quota

The quota was never the binding constraint. `STAIR_SPACING` was: it is a square
keep-clear sized for a rim that runs east-west, and crossings on a side quarter
run *up* the rim instead, so they kept landing inside each other's square. That
one rule refused **508** carves against 49 refused on their geometry, and held
the sides to 1.6 crossings where two or three were asked for.

`SIDE_SPACING = 2` is its own separation for this pass. It was briefly 3, on a
measurement taken before the ledge guard existed; with the guard in place the
guard is the limit and not the spacing, and 3 costs a fifth of the yield for
nothing (1.11 a side against 1.36). 1 is indistinguishable from 2.

### Where it landed

| crossings, by zone, over six worlds | before | after |
|---|---|---|
| east/west side | 47 | **91** |
| south rim | 239 | 232 |
| north back / middle | 42 | 37 |

| per plateau side | |
|---|---|
| level 1 | mean **1.36** (target was 2-3) |
| level 2+ | mean **0.64** (target 0-1) |
| disconnected rooms | **0** |

Level 1 lands under the two-to-three that was asked for, and the ledge guard is
why: roughly 45% of otherwise-good carves sit above a shelf too thin to give a
cell up. Raising it further means either accepting pinched ledges -- the sealed
flight again -- or a wider change to how the caps are inset so the sides are
not ledges in the first place. Neither is worth doing quietly.

Crossings per multi-level island went 7.7 -> 9.8: the sides gained without the
south losing much, which is what preferring a side candidate inside each
region's bucket buys. The south rim had 223 spare candidates and the sides 24,
so spending a region's quota on a side costs the south nothing.


## M — lateral stairs: climbing a plateau from its sides — ✅ DONE

An island was crossable only from the south. Every way up sat in a south-facing
wall, so a plateau's east and west faces were sheer for their whole length and
the player walked round to the bottom of the island to change level.

### Two wrong turns first, both worth recording

**A metric that measured the wrong thing.** The first attempt spread the
existing scanner's crossings into the left and right *columns* of a terrace and
reported side crossings rising 47 to 91. The classifier only looked at the
column and ignored the row, so a stair in the bottom-left corner scored as a
"side" stair: 79% of what it counted sat in the southern third of its terrace,
median row fraction 0.85 against 0.86 for crossings generally. The number moved
and the picture did not, which is exactly what a proxy metric does when nobody
checks it against the thing it stands for.

**Stone that nothing could read.** The second attempt faced every east/west
drop with cliff, so the existing site tests would have something to cut. It
gave 2.5x the stone, ate 2,900 cells of walkable ground, and changed the
distribution not at all -- 78% to 79% in the southern third. `_vstair_site` and
`_ewstair_site` both require ground directly *north* of the wall and ground
directly *south* at the foot; a side wall has ground east and west, so both
still refuse it. Adding stone cannot help when nothing can read it, and once
the site tests can read sideways the stone is not needed. It also looked wrong:
every cliff tile in the project is a horizontal run drawn as if seen from the
south, and standing one on end reads as a garden wall.

### What a lateral face actually is

Measured over six worlds: **zero** vertical stone runs. Every cliff cell is
part of a horizontal south-facing run (37%) or an isolated single (63%). A
plateau's east and west boundary carries no stone at all -- on the sample
island, 46 stone cells, all south-facing, against 66 bare lateral drop cells.

So a crossing there stands on nothing and must bring its own art.

### The crossing

The two-tile ramp unit the tileset already ships (`slots.ramp`, at the same
indices in all eight tilemaps, each in its own material) laid straight onto the
bare boundary. No stone added, no new art, no new cell kind -- an ordinary
`EWSTAIR` tagged `side_*`, so the step rules and the painter can tell it from a
wall cut without re-deriving anything.

`_lateral_site` requires **both** rows: the ramp is two tiles and each half
needs a face beside it to connect to. 508 runs of two or more exist over six
worlds and every multi-level island has one, so insisting costs little.

Two guards, both added after a test caught something real:

**Head and foot, not both at once.** The first step rule let *either* cell of
the unit reach both terraces. A body could then cut the corner diagonally from
the low ground to the high ground *past* the crossing, never standing on it,
because `can_step` only asks whether one right-angle detour is open end to end
-- the exact hole the diagonal rule exists to close. Row 0 is the head and
reaches only the upper terrace; row `drop` is the foot and reaches only the
lower, precisely as a wall-cut flight already worked.

**A landing you can stand on.** A crossing whose foot dropped into a one-cell
pocket of lower terrace was walkable for a small enemy and sealed for a large
one: the coarse navigation class uses 48 px cells against 64 px tiles, and such
a pocket measures 15.9 px of clearance against the 22 it needs. Every cell
around the landing, bar the one the stair occupies, must be more of that
terrace.

And one ordering fix: the pass runs **after** `_carve_lakes`, because a lake
accretes over ground of its own terrace and had eaten the landing out from
under four crossings in six worlds.

### The art faces the way the ground drops

The side is taken straight from the tag -- a crossing that drops east draws
`ramp.e`. It was mirrored at first, reasoning from a one-tile prototype about
which way the riser should face; in the finished two-tile unit that points every
ramp the wrong way, which is plain on screen and was not in the numbers.

### Two alignments, and the backdrop one of them needs

A crossing can sit in the boundary two ways, and the first build only ever made
the first. `=` is terrace, `>` the stair:

```
    notched into the terrace          protruding from its side
        = = =                             = = =
        = = >                             = = = >
        = = =                             = = =
```

They look different and test the same. Whichever pair of cells the unit takes,
one step against the drop has to be the upper terrace and one step with it the
lower; the alignment is only *which* of those two terraces the cells came from.
Notched cells were upper terrace, so it closes over the stair again above and
below; protruding cells were lower terrace, so nothing stands over it. So the
site test is unchanged in shape and the candidate list simply widened to both
terraces -- the room's own seeded shuffle then mixes them, 56% protruding to
44% notched.

**A notch needs its wall drawn and was not getting one.** The backdrop was
removed wholesale when this was built, on the reasoning that a side face has no
stone. True of the face and false of the notch: once the stair is cut in, the
terrace tile standing directly above it drops into the notch, and with no wall
there the crossing reads as a hole rather than a way down. It is painted on the
**head** only -- the drop is one level, so one tile of face is the whole wall --
and only when a terrace tile of the crossing's own level actually sits above
it, which is what tells the two alignments apart at paint time.

### The pass puts the stream back

Two `test_repair` failures arrived with the second alignment, and neither was
about a staircase. A two-tile bay in the corner of an island's bounding box was
read as an inland hole; a bridge took a lane four tiles longer than the best
available. Both were the same cause: this pass draws from the shared `rng`, so
every stage below it -- `_link_levels`, the prune, the hole fill, and the
corridor seating outside `build_grid` entirely -- saw a different stream purely
because side stairs exist, and produced different coastlines and bridges.

Measured over thirty seeds, the bridge lane was exact (span == best) on all 25
over-cap bridges without the pass and on 27 of 28 with it. One tail case, and
nothing to do with the feature.

So the pass saves the stream and restores it. It still draws like any other
stage, and the world below it is bit-for-bit what it would have been. This is
the guard `floor_palette` already carries, for the same reason -- and the right
default for any pass added late to a generator whose every later stage is
pinned by seed.

**A blind spot it exposed, fixed separately.** `test_repair`'s hole detector
floods within the island's bounding box, so a notch in the box's own *corner*
-- draining south and west past rows the box does not cover -- counts its three
land neighbours and reads as enclosed. The generator is right to leave it: it
is a bay. A component touching the box edge is now skipped, because there is by
definition no land beyond that edge or the box would be bigger.

### The rim ran out at every crossing

The island's boundary line vanished for the two rows of each lateral crossing
and picked up again below it. Two rules met and neither drew it: the floor
under the crossing is *lower* ground, which never fringes against something
higher, and the terrace cell beside it is suppressed by `_floor_sides`'s flight
rule -- a flight is normally part of its own floor's outline, so a terrace
carries its rim straight past one rather than stopping either side of it. True
of a wall-cut flight, which sits inside the wall. Not true of a lateral
crossing, which sits on the far side of the boundary.

The first attempt put the rim on the floor *under* the crossing, and it was the
wrong tile: measured against the art's alpha, `ramp.e`'s leftmost eight columns
carry 60 to 64 opaque pixels of 64 -- the ramp is solid on the side facing the
upper terrace, necessarily, because that is where it joins it, and transparent
on the downhill side. So the rim was painted and then covered. It moved 356
pixels, almost all of them hidden, which is the shape of a fix that measures as
working and does not look like anything.

The rim belongs on the **terrace cell beside the crossing**, and only beside
its **foot**. The head tile of the ramp carries a grass fringe in its own art
and a second one next to it reads as a doubled line; the foot tile has stone
there instead and leaves the terrace's grass running flat into it. So the
suppression is lifted for `row == drop` and nowhere else.

### It casts a shade like anything else standing on a terrace

`_shadow_casts` excluded lateral crossings at first, on the reasoning that a
side face carries no stone so nothing is there to cast. Wrong on its own terms:
the crossing stands proud of the floor below it whichever alignment it takes,
and without the shade it reads as painted flat onto that floor rather than
stepping down onto it.

Deleting the exclusion is the whole change -- a crossing then falls through to
the same line a `CLIFF` uses, an unclipped blob at its own cell bound for the
terrace below. The ordering was already right: `_shade` is pass 2 and the ramp
is pass 3, which is the contract that pass has always stated -- ground, shadow,
stone. Only the **foot** casts, though, which is where this differs from a cliff. Both
cells did at first, by falling through to the cliff branch, and that is right
for a cliff -- every cell of a run is wall standing the full height. It is
wrong for a ramp: the upper tile is the ramp's own surface, level with the
terrace it leaves, and only the lower one stands proud of the floor below.
`row == drop` picks it, the same test `walk_links` uses to find the end that
opens onto that floor.

Both alignments take it. The notched one is unarguable -- there is a wall above
it -- and the protruding one carries the ramp's own rocky step, so it earns a
shade too.

**And a north-facing tile casts nothing, whatever gave it that edge.** The rule
is older than this milestone -- a shadow falling north fights the rest of the
lighting, so a plateau's back edge and the corners where it meets a flank are
left clean -- but it was implemented as "does lower *ground* drop away to the
north", and a north edge has three other causes. The tile directly below a
crossing's foot is the one that showed it up: its north neighbour is the stair,
so the old test saw nothing and let it cast sideways onto the terrace below,
which reads as the shade bleeding into the tile next door rather than sitting
under anything. Asking `_floor_sides` for the edge instead catches all four
causes. Over six worlds it silences 125 casters of 1,194 -- 78 with stone to
the north, 38 with a flight, 9 with open sea -- and every one that still casts
has no north edge at all.

### Where it landed

| | |
|---|---|
| lateral crossings, six worlds | **147** |
| protruding / notched | **59% / 41%** |
| per plateau side, level 1 | mean **1.60**, 65% on exactly 2-3 |
| per plateau side, level 2+ | 0.20 |
| crossings failing to link two levels | **0** |
| disconnected rooms | **0** |
| stone cells added | **0** |

`SIDE_SPACING = 2`: the unit is two tiles tall, so a pair can sit back to back
but never overlap.

---

## N — the blue seams were a fractional tile, and only in the browser — ✅ DONE

Thin bluish lines along tile frontiers, reported off a screenshot. Reproduced,
and the cause is not the terrain at all.

Terrain is not one surface. It is composited from several that are scaled and
blitted independently -- per room, per corridor, per cliff band, and since A5
one per terrace on top of that -- and each lands at a *truncated* screen
position. When the scaled tile size is fractional the neighbours round to
positions that do not quite meet, and the sea buffer painted underneath shows
through the 1 px crack.

The correlation is exact: seams appear if and only if `TILE_PX * zoom` is not
an integer.

| zoom | tile px | | seam px |
|---|---|---|---|
| 0.75 | 48.00 | integer | 1 |
| 1.00 | 64.00 | integer | 0 |
| 1.25 | 80.00 | integer | 0 |
| 1.50 | 96.00 | integer | 0 |
| 2.00 | 128.00 | integer | 0 |
| 0.90 | 57.60 | fractional | 239 |
| **1.20** | **76.80** | fractional | **252** |
| 1.30 | 83.20 | fractional | 32 |

Which matters because `apply_web_profile()` set `CAMERA_ZOOM = 1.2`. Desktop
runs at 1.5 -- 96 px, clean -- so this was a defect the browser build shipped
and the desktop build never showed.

1.2 was not arbitrary: it was picked so `1280 / 1.2 == 1600 / 1.5`, giving the
web canvas exactly the desktop build's visible world extent. That parity is
what the fix spends. At 1.25 the web view shows 1024 x 576 of world against
desktop's 1067 x 600 -- about 4% tighter, and sprites 4% larger. Across five
worlds and three islands each, **3,402 seam pixels to 0**.

The alternative was to snap every surface's size and destination onto one
integer grid, which fixes any zoom instead of one. It is the better repair and
it stays on the table; it also moves surfaces a pixel relative to the entities
drawn over them, which is a bigger thing to land for a defect that has exactly
one shipping trigger.

`tests/rendering/test_camera.py::ZoomGranularityTests` pins the invariant for
every zoom the game ships, so the next zoom change has to notice.

### A different hole, found while measuring

The seam counter never quite reached zero, and the residue was informative: all
of it exactly `(71, 171, 169)` -- `water_background.png`'s fill -- all of it on
`vstair` tiles, in two thin vertical strips one tile apart, and *present at
every zoom including the integer ones*, desktop's 1.5 among them. So it is not
rounding. A vertical staircase's art does not fill the full width of its tile,
nothing is painted behind the flanks, and the sea shows through. 25 to 52 px
per island, pre-existing, unrelated to this milestone, and left alone here.
