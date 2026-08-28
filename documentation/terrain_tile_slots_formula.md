# Terrain tiles — slot formula (how a cell is cut and placed)

How the tiled floor renderer turns a tilemap PNG (`tilemap_1.png`) into a
room's grass floor: address a cell by a flat index, cut it, pick the right one
for each position in the room, bake, blit.

Companion to `level_design.md` (§3.3 covers the same renderer at a higher
level). Source: `data/terrain.json`, `game/assets.py — Assets.tile`,
`world/map.py — GameMap._slot_for` / `_build_tiles` / `_draw_tiled`.

---

## 1 · The asset — `assets/terrain/tiles/tilemap_1.png`

- **`576 × 384` px**, loaded once via `pygame.image.load(...).convert_alpha()`
  → a **32-bit surface with a real alpha channel** (`game/assets.py —
  _load_image`).
- Read as a **grid of `64 × 64` cells**: `576 / 64 = 9` columns, `384 / 64 = 6`
  rows → **54 cells**, indices `0 … 53`, numbered **row-major**
  (`0` top-left, `8` top-right, `9` first cell of row 1, …).
- The cells in **columns 0–3 + row 3** are a **grass-on-water "blob" autotile**:
  a 3×3 core (corners / edges / interior) plus 1-wide strips and a 1×1 island.
  The core's **edge and corner cells are transparent on their water-facing
  side**; the `interior` cell is fully opaque. (Columns 5–8 hold a second grass
  tint and a grey stone set — unused today.)
- `tilemap_2..5.png` have the **identical grid layout**, only a different
  grass tint; `room_palettes` picks which file a room kind uses.

## 2 · The vocabulary — `data/terrain.json`

```json
{
  "tile_px": 64,
  "grid": [9, 6],
  "floor_sheet": "terrain/tiles/tilemap_1.png",
  "slots": {
    "interior": 10,
    "edge_n": 1, "edge_s": 19, "edge_w": 9, "edge_e": 11,
    "corner_nw": 0, "corner_ne": 2, "corner_sw": 18, "corner_se": 20,
    "strip_v": [3, 12, 21], "strip_h": [27, 28, 29], "single": 30
  },
  "room_palettes": {
    "default": "terrain/tiles/tilemap_1.png",
    "boss": "terrain/tiles/tilemap_4.png",
    "treasure": "terrain/tiles/tilemap_2.png",
    "shrine": "terrain/tiles/tilemap_3.png",
    "fountain": "terrain/tiles/tilemap_5.png"
  }
}
```

- `tile_px` — cell size. Every slot cuts a `tile_px × tile_px` square; only its
  position moves.
- `grid` — `[cols, rows]` of the sheet. Only `cols` is used (for the index
  arithmetic).
- `slots` — a **semantic name → flat index** table. **Hand-authored**: the
  indices were read off a grid-numbered render of the sheet during the T1
  terrain pass and typed in. There is **no auto-detection** — a different
  tileset needs its `slots` re-mapped by hand (§8).
- `room_palettes` — room `kind` → sheet path; missing kinds fall back to
  `floor_sheet`.

## 3 · Formula — flat index → cell coordinates → pixel rect

```
cols = terrain.grid[0]          # 9
px   = terrain.tile_px          # 64

col  = index % cols
row  = index // cols
rect = (col * px, row * px, px, px)
```

Examples on `tilemap_1.png` (`cols = 9`, `px = 64`):

| slot | index | `index % 9` → col | `index // 9` → row | pixel rect |
|------|------:|:-----------------:|:------------------:|------------|
| `corner_nw` | 0  | 0 | 0 | `(0, 0, 64, 64)` |
| `edge_n`    | 1  | 1 | 0 | `(64, 0, 64, 64)` |
| `corner_ne` | 2  | 2 | 0 | `(128, 0, 64, 64)` |
| `strip_v[0]`| 3  | 3 | 0 | `(192, 0, 64, 64)` |
| `edge_w`    | 9  | 0 | 1 | `(0, 64, 64, 64)` |
| `interior`  | 10 | 1 | 1 | `(64, 64, 64, 64)` |
| `edge_e`    | 11 | 2 | 1 | `(128, 64, 64, 64)` |
| `strip_v[1]`| 12 | 3 | 1 | `(192, 64, 64, 64)` |
| `corner_sw` | 18 | 0 | 2 | `(0, 128, 64, 64)` |
| `edge_s`    | 19 | 1 | 2 | `(64, 128, 64, 64)` |
| `corner_se` | 20 | 2 | 2 | `(128, 128, 64, 64)` |
| `strip_v[2]`| 21 | 3 | 2 | `(192, 128, 64, 64)` |
| `strip_h[0]`| 27 | 0 | 3 | `(0, 192, 64, 64)` |
| `strip_h[1]`| 28 | 1 | 3 | `(64, 192, 64, 64)` |
| `strip_h[2]`| 29 | 2 | 3 | `(128, 192, 64, 64)` |
| `single`    | 30 | 3 | 3 | `(192, 192, 64, 64)` |

(The 3×3 core — `corner_*` / `edge_*` / `interior` — is the top-left block of
the sheet: rows 0–2, cols 0–2. `strip_v` is col 3, `strip_h` is row 3,
`single` is their intersection.)

## 4 · Cutting the cell — `game/assets.py — Assets.tile(sheet_rel, index, *, size=None)`

```python
sheet = self._load_image(sheet_rel)          # 32-bit convert_alpha() surface, cached
if sheet is None:
    return None                              # missing file -> caller falls back
px   = int(self.terrain.get("tile_px", 64))
cols = int(self.terrain.get("grid", [9, 6])[0])
col, row = index % cols, index // cols
rect = pygame.Rect(col * px, row * px, px, px)
if not sheet.get_rect().contains(rect):
    self._frames[key] = None                 # out-of-range index -> cached None
else:
    cell = sheet.subsurface(rect).copy()     # <-- the cut
    if size is not None:
        cell = pygame.transform.scale(cell, size)
    self._frames[key] = [cell]
```

- `sheet.subsurface(rect)` is a **zero-copy view** into the loaded sheet at that
  rectangle; `.copy()` makes it a standalone surface so caching / scaling never
  touch the sheet.
- Because the sheet is `convert_alpha()`, the copy **keeps its alpha** — this is
  why an `edge_w` cell's transparent left strip survives all the way to the
  screen (and, since T6, shows the water / foam through it).
- Memoised by `("<tile>", sheet_rel, index, size)` — each cell is cut once.

## 5 · Choosing the slot for a room cell — `world/map.py — GameMap._slot_for`

A room is a `rows × cols` grid of cells (`cols = ceil(room.rect.width / 64)`,
`rows = ceil(height / 64)`). `_slot_for` picks the slot **from the cell's
position only** — no neighbour inspection:

```python
@staticmethod
def _slot_for(slots, row, col, rows, cols) -> int:
    n, s = row == 0, row == rows - 1        # top / bottom row of the room
    w, e = col == 0, col == cols - 1        # left / right column
    if n and w: return slots["corner_nw"]
    if n and e: return slots["corner_ne"]
    if s and w: return slots["corner_sw"]
    if s and e: return slots["corner_se"]
    if n:       return slots["edge_n"]
    if s:       return slots["edge_s"]
    if w:       return slots["edge_w"]      # left column, not a corner
    if e:       return slots["edge_e"]
    return slots["interior"]                # anything inside
```

It's **position-based**, not a neighbour-bitmask autotiler. That is sufficient
because rooms are plain axis-aligned rectangles — no concave corners, no
diagonal seams. (The sheet's inner-corner pieces `#36 #39 #45 #48` exist for
concave shapes and are currently unused. `strip_v` / `strip_h` / `single` are
for regions ≤ 1 tile wide/tall — also unused by the current room sizes.)

## 6 · Baking a room — `world/map.py — _build_tiles → paint_room`

```python
def paint_room(r):
    sheet = palettes.get(r.kind, floor_sheet)
    cols  = max(1, -(-r.rect.width  // px))          # ceil
    rows  = max(1, -(-r.rect.height // px))
    surf  = pygame.Surface(r.rect.size, pygame.SRCALPHA)   # per-pixel alpha (T6)
    for row in range(rows):
        for col in range(cols):
            idx = self._slot_for(slots, row, col, rows, cols)
            surf.blit(cell(sheet, idx), (col * px, row * px))
            if row in (0, rows-1) or col in (0, cols-1):
                self._shore.append((r.rect.x + col*px, r.rect.y + row*px))
    return surf
```

- One SRCALPHA `Surface` per room, cached in `self._room_surfs[r.id]` — the
  autotiling is baked **once**, not per frame.
- `cell(sheet, idx)` = `Assets.tile(sheet, idx)` with the `interior` tile as a
  fallback if a slot is missing/out-of-range.
- Each blit lands at `(col * 64, row * 64)` — the cell's own place in the grid.
- Perimeter cells are recorded in `self._shore` for the foam pass.
- Corridors use `paint_plain` — the same, but every cell is `interior`.

## 7 · Displaying — `world/map.py — _draw_tiled` (per frame)

```
1. blit self._water_buf              (Water_Background tiled, opaque, scrolls)
2. blit the current Water_Foam frame centred on every in-view self._shore cell
3. blit each in-view room surface at (room.rect.x - cam.x, room.rect.y - cam.y)
4. blit each in-view corridor surface
```

The room surface is SRCALPHA, so where its edge/corner tiles are transparent the
foam (step 2) and water (step 1) show through; where it's `interior` it is
opaque grass. Camera offset is a plain `world_pos - camera.pos` translation.

## 8 · Worked example — the left shore of a room

A cell in a room's **leftmost column** (not a corner):

1. `_slot_for(row, col=0, rows, cols)` → `w` is true, `n/s` false →
   returns `slots["edge_w"]` → **`9`**.
2. `Assets.tile("terrain/tiles/tilemap_1.png", 9)`:
   `col = 9 % 9 = 0`, `row = 9 // 9 = 1` → `rect = (0, 64, 64, 64)` →
   `sheet.subsurface((0, 64, 64, 64)).copy()` — grass on the right ~90 %,
   pixel-art shore fringe + transparent water on the **left** ~10 %.
3. `paint_room` blits it at `(0 * 64, row * 64)` — straight down the room's left
   edge.

The tile "points left" because the artist drew that art in sheet cell
`(col 0, row 1)`, `terrain.json` names that cell `edge_w`, and `_slot_for`
requests `edge_w` for the left column. Nothing rotates or mirrors — every
direction is a separate authored cell.

## 9 · Per-room-kind palettes

`paint_room` starts with `sheet = room_palettes.get(r.kind, floor_sheet)`. The
`slots` indices are the same for every `tilemap_N.png` (identical layout),
so a boss room bakes exactly the same autotile pattern out of
`tilemap_4.png` and just looks a different colour.

## 10 · Re-mapping `slots` for a different tileset

There is no detector. To swap in a new sheet:

1. Render it with a grid + per-cell index overlay (a ~20-line pygame script;
   the T1 scratchpad `inspect_terrain.py` does this).
2. Read which cell holds the NW corner, the N edge, the interior, … and write
   those indices into `data/terrain.json`'s `slots`.
3. Set `floor_sheet` (and `room_palettes`) to the new path(s); keep `tile_px`
   and `grid` matching the new sheet.

`Assets.tile` and `_slot_for` need no changes — they only read the JSON.

## 11 · Degradation

- **Missing `floor_sheet`** → `_build_tiles` probes `Assets.tile(floor_sheet,
  interior)`, gets `None`, and `_tiles_ok` stays `False` → the primitive flat
  renderer (`_draw_flat_layout`, tinted rects) draws instead.
- **A slot index outside the grid** → `Assets.tile` returns `None` → `cell()`
  substitutes the `interior` tile, so the room still bakes (just without that
  edge piece).
- **A missing palette file** for one room kind → that room falls back to
  `floor_sheet`.
