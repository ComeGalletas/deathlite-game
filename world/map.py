"""The playable world.

Phase 3: `GameMap` wraps a procedural `WorldLayout` (rooms + corridors). It
answers "is this walkable?", slides entities along walls, picks legal spawn
points, and draws the floor / walls / void. Without a seed it degrades to one
big rectangular room (used by tests and any non-run context).

Terrain pass (T2): when the tileset assets load, the flat floor/void rects are
replaced by a tiled grass floor (one pre-rendered `Surface` per static room /
corridor) over a tiled water void. If the tileset is missing, the flat renderer
below is the permanent fallback.
"""
from __future__ import annotations

import random

import pygame

from game import config
from game.assets import get_assets
from world.procedural import Room, WorldLayout, generate_world

_VOID = (10, 10, 14)
_FLOOR = (26, 26, 34)
_WALL = (68, 70, 92)
_GRID = (32, 33, 44)

_SPECIAL_FLOORS = {
    "start": (24, 34, 30), "boss": (44, 22, 26),
    "shrine": (30, 34, 48), "treasure": (44, 40, 24),
    "fountain": (22, 38, 44), "altar": (40, 24, 40),
    "merchant": (40, 36, 28), "elite_arena": (46, 26, 30),
}


class GameMap:
    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            self.layout: WorldLayout | None = None
            self.width = config.WORLD_WIDTH
            self.height = config.WORLD_HEIGHT
            self._rects = [pygame.Rect(0, 0, self.width, self.height)]
            self.obstacles = []
        else:
            self.layout = generate_world(seed)
            b = self.layout.bounds
            self.width, self.height = b.width, b.height
            self._rects = self.layout.walkable_rects()
            self.obstacles = self.layout.obstacles

        # Tiled-terrain state, built lazily on the first draw() (needs a display).
        self._tiles_ready = False
        self._tiles_ok = False
        self._water_buf: pygame.Surface | None = None
        self._water_tile = 0            # water tile size in world px (scroll stride)
        self._room_surfs: dict[int, pygame.Surface] = {}
        self._corr_surfs: list[tuple[pygame.Rect, pygame.Surface]] = []
        self._shore: list[tuple[int, int]] = []       # top-left world px of shoreline tiles
        self._foam: list[pygame.Surface] | None = None
        # Obstacle index -> (anchor_x, anchor_y, fps, [frame, ...]). Each obstacle
        # is skinned with a decoration rig scaled to its collider; obstacles with
        # no entry (missing tileset / flag off) fall back to a drawn circle.
        self._decos: dict[int, tuple] = {}
        # (world_x, world_y, radius, surf) per tree -- a soft round canopy shadow
        # drawn *over* the characters (B3), so anyone under a tree is darkened.
        self._tree_shadows: list[tuple] = []
        # Non-colliding scenery scatter (T8), resolved at build time. Each
        # instance is (frames, anchor_x, anchor_y, fps, world_x, world_y).
        self._room_decor: dict[int, list[tuple]] = {}   # room id -> interior clutter
        self._void_decor: list[tuple] = []              # water scenery in the void

        # Draw-time zoom (C3): the baked terrain surfaces are 1:1 world pixels;
        # every render method scales blit positions by `camera.zoom` and blits a
        # `_z_surf()`-scaled copy so the tiled world matches the zoomed entities.
        # `_z_surf` caches by source-surface id for the current zoom.
        self._render_zoom: float = 1.0
        self._blit_cache: dict[int, pygame.Surface] = {}

    # --- geometry ------------------------------------------------
    @property
    def center(self) -> pygame.Vector2:
        if self.layout is not None:
            return self.layout.room(self.layout.start_id).center
        return pygame.Vector2(self.width / 2, self.height / 2)

    def rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.width, self.height)

    def room_at(self, pos: pygame.Vector2) -> Room | None:
        if self.layout is None:
            return None
        for r in self.layout.rooms:
            if r.rect.collidepoint(pos.x, pos.y):
                return r
        return None

    # --- walkability / movement -------------------------------
    def _point_ok(self, x: float, y: float) -> bool:
        for rc in self._rects:
            if rc.collidepoint(x, y):
                return True
        return False

    def is_walkable(self, pos: pygame.Vector2, radius: float = 0.0) -> bool:
        if not self._point_ok(pos.x, pos.y):
            return False
        if radius > 0 and not (
                self._point_ok(pos.x + radius, pos.y)
                and self._point_ok(pos.x - radius, pos.y)
                and self._point_ok(pos.x, pos.y + radius)
                and self._point_ok(pos.x, pos.y - radius)):
            return False
        for o in self.obstacles:
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return False
        return True

    def blocking_obstacle_hit(self, pos: pygame.Vector2, radius: float):
        """First projectile-blocking obstacle overlapping the circle, or None."""
        for o in self.obstacles:
            if not o.blocks_projectiles:
                continue
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return o
        return None

    def resolve_movement(self, prev: pygame.Vector2, new: pygame.Vector2,
                         radius: float) -> pygame.Vector2:
        """Move toward `new`; if it hits a wall, slide along one axis."""
        if self.is_walkable(new, radius):
            return new
        slide_x = pygame.Vector2(new.x, prev.y)
        if self.is_walkable(slide_x, radius):
            return slide_x
        slide_y = pygame.Vector2(prev.x, new.y)
        if self.is_walkable(slide_y, radius):
            return slide_y
        return pygame.Vector2(prev)

    def random_point_in_room(self, room: Room, rng: random.Random,
                             margin: float = 24.0) -> pygame.Vector2:
        r = room.rect
        return pygame.Vector2(
            rng.uniform(r.left + margin, r.right - margin),
            rng.uniform(r.top + margin, r.bottom - margin))

    def offscreen_spawn_point(self, camera, rng: random.Random) -> pygame.Vector2:
        """A walkable point just outside the view: prefer the closest rooms that
        are not fully on screen, so pressure stays on the player even though the
        world is large."""
        view = camera.visible_rect()
        vc = pygame.Vector2(view.center)

        if self.layout is None:
            for _ in range(20):
                p = pygame.Vector2(rng.uniform(0, self.width), rng.uniform(0, self.height))
                if not view.collidepoint(p.x, p.y):
                    return p
            return pygame.Vector2(self.width / 2, self.height / 2)

        rooms = sorted(self.layout.rooms, key=lambda r: (r.center - vc).length_squared())
        room = rng.choice(rooms[:3])
        min_dist_sq = 220.0 ** 2
        best = room.center
        for _ in range(12):
            p = self.random_point_in_room(room, rng)
            if not view.collidepoint(p.x, p.y) and (p - vc).length_squared() > min_dist_sq:
                return p
            best = p
        return best

    # --- tiled terrain (built once, on the first draw) ----------
    @staticmethod
    def _slot_for(slots: dict, row: int, col: int, rows: int, cols: int) -> int:
        n, s = row == 0, row == rows - 1
        w, e = col == 0, col == cols - 1
        if n and w:
            return slots["corner_nw"]
        if n and e:
            return slots["corner_ne"]
        if s and w:
            return slots["corner_sw"]
        if s and e:
            return slots["corner_se"]
        if n:
            return slots["edge_n"]
        if s:
            return slots["edge_s"]
        if w:
            return slots["edge_w"]
        if e:
            return slots["edge_e"]
        return slots["interior"]

    @staticmethod
    def _bridge_slot(axis: str, index: int, ncells: int) -> str:
        """The bridge tile for cell `index` of an `ncells`-long run. The corridor
        `axis` ('h' | 'v') fixes the tile family; the two ends get the matching
        cap (`Corridor.end_low` -> `h_left` / `v_top`, `end_high` -> `h_right` /
        `v_bot`), everything between gets `mid` (see data/terrain.json 'bridge')."""
        low, mid, high = (("h_left", "h_mid", "h_right") if axis == "h"
                          else ("v_top", "v_mid", "v_bot"))
        if ncells <= 1:
            return mid
        if index == 0:
            return low
        if index == ncells - 1:
            return high
        return mid

    def _build_tiles(self) -> None:
        self._tiles_ready = True
        if self.layout is None:
            return
        a = get_assets()
        t = a.terrain
        px = int(t.get("tile_px", 64))
        floor_sheet = t.get("floor_sheet")
        slots = t.get("slots", {})
        interior = slots.get("interior", 10)
        palettes = t.get("room_palettes", {})
        probe = a.tile(floor_sheet, interior)
        if probe is None:
            return                                   # tileset missing -> flat fallback

        cell_cache: dict[tuple, pygame.Surface] = {}

        def cell(sheet: str, idx: int, cols: int | None = None) -> pygame.Surface:
            key = (sheet, idx, cols)
            if key not in cell_cache:
                cell_cache[key] = a.tile(sheet, idx, cols=cols) or probe
            return cell_cache[key]

        # Bridge tiles for corridors (own sheet / grid). Missing -> plain grass.
        bridge = t.get("bridge", {})
        b_sheet = bridge.get("sheet")
        b_cols = int(bridge.get("grid", [3, 4])[0])
        b_slots = bridge.get("slots", {})
        bridge_ok = (b_sheet is not None and "h_mid" in b_slots
                     and a.tile(b_sheet, b_slots["h_mid"], cols=b_cols) is not None)

        def paint_room(r) -> pygame.Surface:
            sheet = palettes.get(r.kind, floor_sheet)
            cols = max(1, -(-r.rect.width // px))     # ceil
            rows = max(1, -(-r.rect.height // px))
            # SRCALPHA: the autotile edge / corner tiles are transparent on their
            # water-facing side -- keep that alpha so foam / water show through
            # instead of the surface's black ground (see assets_journal.md T6).
            surf = pygame.Surface(r.rect.size, pygame.SRCALPHA)
            for row in range(rows):
                for col in range(cols):
                    idx = self._slot_for(slots, row, col, rows, cols)
                    surf.blit(cell(sheet, idx), (col * px, row * px))
                    if row in (0, rows - 1) or col in (0, cols - 1):
                        self._shore.append((r.rect.x + col * px, r.rect.y + row * px))
            return surf

        def paint_corridor(c) -> tuple[pygame.Rect, pygame.Surface]:
            """Bake the plank bridge for corridor `c`. It spans mouth to mouth
            and **one tile past each mouth into the room**, so the end-cap tile
            overlaps the room's shoreline tile (the bridge reads as anchored to
            the shore, not falling short of it) -- not buried at the room centres
            the collision rect runs between. Returns the blit rect (differs from
            `c.rect`) and the surface."""
            lo = self.layout.room(c.room_low).rect
            hi = self.layout.room(c.room_high).rect
            if c.axis == "h":
                span0, span1 = lo.right - px, hi.left + px   # 1 tile into each room
                ncells = max(2, round((span1 - span0) / px))
                w, h = ncells * px, px
                bx = span0 - (w - (span1 - span0)) // 2      # centre the run
                blit = pygame.Rect(bx, c.rect.y, w, h)
            else:
                span0, span1 = lo.bottom - px, hi.top + px
                ncells = max(2, round((span1 - span0) / px))
                w, h = px, ncells * px
                by = span0 - (h - (span1 - span0)) // 2
                blit = pygame.Rect(c.rect.x, by, w, h)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(ncells):
                if bridge_ok:
                    name = self._bridge_slot(c.axis, i, ncells)
                    tile_surf = cell(b_sheet, b_slots.get(name, b_slots["h_mid"]),
                                     b_cols)
                else:
                    tile_surf = cell(floor_sheet, interior)
                pos = (i * px, 0) if c.axis == "h" else (0, i * px)
                surf.blit(tile_surf, pos)
                # Each plank cell is a shore cell -- foam behind the bridge shows
                # through the plank gaps over open water.
                self._shore.append((blit.x + pos[0], blit.y + pos[1]))
            return blit, surf

        for r in self.layout.rooms:
            self._room_surfs[r.id] = paint_room(r)
        for c in self.layout.corridors:
            self._corr_surfs.append(paint_corridor(c))

        # Doorway seam (T9): where a bridge end meets a room edge the two shore
        # rings overlap and foam would bite into the connection. Drop any shore
        # cell whose tile touches *both* a room and a corridor -- the join then
        # reads as solid ground. Mid-bridge cells (corridor only) keep their
        # plank-gap foam; open room edges (room only) keep their shoreline.
        corr_hit = [rect.inflate(px, px) for rect, _ in self._corr_surfs]
        room_hit = [rm.rect for rm in self.layout.rooms]
        if corr_hit:
            kept = []
            for sx, sy in self._shore:
                c = pygame.Rect(sx, sy, px, px)
                if (any(c.colliderect(h) for h in corr_hit)
                        and any(c.colliderect(h) for h in room_hit)):
                    continue
                kept.append((sx, sy))
            self._shore = kept

        water = a.tile(t.get("water_tile"), 0)
        if water is not None:
            wt = water.get_width()
            # Big enough to cover the visible world extent (SCREEN / zoom) plus
            # one tile of scroll slack; `_z_surf` blows it up to the screen.
            span_w = round(config.SCREEN_WIDTH / config.CAMERA_ZOOM) + wt
            span_h = round(config.SCREEN_HEIGHT / config.CAMERA_ZOOM) + wt
            buf = pygame.Surface((span_w, span_h)).convert()
            for y in range(0, span_h, wt):
                for x in range(0, span_w, wt):
                    buf.blit(water, (x, y))
            self._water_buf = buf
            self._water_tile = wt

        if config.TERRAIN_FOAM:
            self._foam = a.frames("terrain_foam", "loop")

        if config.TERRAIN_DECORATIONS:
            self._build_obstacle_decor(a)

        if config.TERRAIN_DECOR:
            self._build_decor_scatter(a)

        self._tiles_ok = True

    def _build_obstacle_decor(self, a) -> None:
        """Skin each obstacle with a decoration rig scaled to its collider.

        `obstacle_decor.rigs` maps the obstacle kind to a list of interchangeable
        rigs; `Obstacle.variant` (from the run seed) picks one. The rig's frame
        is scaled so its measured `footprint` (content width in source px) covers
        `2 * radius * size_boost` on screen, and its anchor scales to match.
        """
        conf = a.terrain.get("obstacle_decor", {})
        rig_map = conf.get("rigs", {})
        if not rig_map:
            return
        boost = float(conf.get("size_boost", 1.25))
        resolved: dict[tuple, tuple | None] = {}      # (rig, size) -> entry | None

        for i, o in enumerate(self.obstacles):
            choices = rig_map.get(o.kind)
            if not choices:
                continue
            rig = choices[(int(getattr(o, "variant", 1)) - 1) % len(choices)]
            meta = a.rig(rig)
            if not meta:
                continue
            fw, fh = meta["frame"]
            footprint = float(meta.get("footprint") or fw)
            scale = (2.0 * o.radius * boost) / footprint
            size = (max(1, round(fw * scale)), max(1, round(fh * scale)))
            key = (rig, size)
            if key not in resolved:
                frs = a.frames(rig, "loop", size=size)
                if not frs:
                    resolved[key] = None
                else:
                    ax0, ay0 = a.anchor(rig)
                    fps = a.fps(rig, "loop") if len(frs) > 1 else 0.0
                    resolved[key] = (ax0 * scale, ay0 * scale, fps, frs)
            entry = resolved[key]
            if entry is not None:
                self._decos[i] = entry

        if config.TERRAIN_SHADOWS:
            self._build_tree_shadows(conf)

    def _build_tree_shadows(self, conf: dict) -> None:
        """A soft round shade patch under every skinned `tree` obstacle. Drawn
        after the characters (see `draw_tree_shadows`) so a hero / enemy under a
        tree is slightly obscured -- the only obstacle that casts one."""
        spec = conf.get("tree_shadow", {})
        rs = float(spec.get("radius_scale", 1.9))
        color = tuple(spec.get("color", (12, 18, 22)))[:3]
        alpha = int(spec.get("alpha", 66))
        cache: dict[int, pygame.Surface] = {}

        def disc(r: int) -> pygame.Surface:
            if r not in cache:
                surf = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
                # a few concentric fills -> denser at the centre, soft at the rim
                for k in range(4, 0, -1):
                    aa = max(1, round(alpha * k / 4 * 0.62))
                    pygame.draw.circle(surf, (*color, aa), (r, r), r * k / 4)
                cache[r] = surf
            return cache[r]

        for i, o in enumerate(self.obstacles):
            if o.kind == "tree" and i in self._decos:
                r = max(1, round(o.radius * rs))
                self._tree_shadows.append((o.pos.x, o.pos.y, r, disc(r)))

    def _build_decor_scatter(self, a) -> None:
        """Seeded, non-colliding scenery from `terrain.json` "decorations":
        interior clutter per room + water scenery in the void.

        Deterministic per `(layout.seed, room id / void grid cell)` -- a string
        seed so it is stable regardless of `PYTHONHASHSEED`. These are cosmetic:
        nothing here touches `self.obstacles` or `is_walkable`. A new prop is a
        new rig + a new "decorations" entry, no code. `collision: true` entries
        are handled by world generation (trees, T9), not here.
        """
        reg = a.terrain.get("decorations", [])
        if not reg:
            return
        px = int(a.terrain.get("tile_px", 64))
        resolved: dict[tuple, tuple | None] = {}       # (rig, size) -> entry|None

        def load(rig: str, scale: float):
            meta = a.rig(rig)
            if not meta:
                return None
            fw, fh = meta["frame"]
            size = (max(1, round(fw * scale)), max(1, round(fh * scale)))
            key = (rig, size)
            if key not in resolved:
                frs = a.frames(rig, "loop", size=size)
                if not frs:
                    resolved[key] = None
                else:
                    ax, ay = a.anchor(rig)
                    fps = a.fps(rig, "loop") if len(frs) > 1 else 0.0
                    resolved[key] = (frs, ax * scale, ay * scale, fps)
            return resolved[key]

        seed = self.layout.seed
        room_reg = [e for e in reg if e.get("placement") == "room_interior"
                    and not e.get("collision")]
        void_reg = [e for e in reg if e.get("placement") == "void"]

        # --- room interiors: clutter on interior cells, clear of the centre ---
        for room in self.layout.rooms:
            rng = random.Random(f"{seed}:{room.id}:decor")
            r = room.rect
            cols, rows = max(3, r.width // px), max(3, r.height // px)
            cx, cy = r.center
            clear_sq = (min(r.width, r.height) * 0.22) ** 2
            placed: list[tuple] = []
            for e in room_reg:
                lo, hi = e.get("per_room", [0, 2])
                entry = load(e["rig"], float(e.get("scale", 1.0)))
                if entry is None:
                    continue
                frs, ax, ay, fps = entry
                for _ in range(rng.randint(lo, hi)):
                    for _try in range(6):
                        col = rng.randint(1, cols - 2)
                        row = rng.randint(1, rows - 2)
                        x = r.x + col * px + rng.uniform(6, px - 6)
                        y = r.y + row * px + rng.uniform(6, px - 6)
                        if (x - cx) ** 2 + (y - cy) ** 2 < clear_sq:
                            continue
                        if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                               < (o.radius + 20) ** 2 for o in self.obstacles):
                            continue
                        if any((x - p[4]) ** 2 + (y - p[5]) ** 2 < 40 * 40
                               for p in placed):
                            continue
                        placed.append((frs, ax, ay, fps, x, y))
                        break
            if placed:
                self._room_decor[room.id] = placed

        # --- the void: water scenery on the open water near the play area ----
        if not void_reg:
            return
        weights = [max(0.0, float(e.get("chance", 0.1))) for e in void_reg]
        total = sum(weights)
        if total <= 0:
            return
        b = self.layout.bounds
        step = 160
        inset = config.CHUNK_SIZE // 3
        out: list[tuple] = []
        gy = b.y + inset
        while gy < b.bottom - inset and len(out) < 240:
            gx = b.x + inset
            while gx < b.right - inset and len(out) < 240:
                rng = random.Random(f"{seed}:{gx}:{gy}:void")
                if rng.random() < total:
                    x = gx + rng.uniform(0, step)
                    y = gy + rng.uniform(0, step)
                    on_land = self._point_ok(x, y) or any(
                        self._point_ok(x + dx, y + dy)
                        for dx in (-36, 36) for dy in (-36, 36))
                    if not on_land:
                        e = rng.choices(void_reg, weights=weights, k=1)[0]
                        entry = load(e["rig"], float(e.get("scale", 1.0)))
                        if entry is not None:
                            frs, ax, ay, fps = entry
                            out.append((frs, ax, ay, fps, x, y))
                gx += step
            gy += step
        self._void_decor = out

    # --- render -----------------------------------------------
    def draw(self, surface: pygame.Surface, camera) -> None:
        """Whole map in one pass: ground, then interior clutter + obstacles
        unsorted on top. `PlayingState` uses `draw_ground` + `scenery_drawables`
        instead, so scenery interleaves with the characters by depth."""
        self.draw_ground(surface, camera)
        if self.layout is None:
            return
        #self._draw_room_clutter(surface, camera)
        self._draw_obstacles(surface, camera)
        self.draw_tree_shadows(surface, camera)

    def _z_surf(self, surf: pygame.Surface | None) -> pygame.Surface | None:
        """`surf` scaled by the current render zoom (cached by source id).
        Identity at zoom 1.0 -- callers and tests see the original object."""
        z = self._render_zoom
        if z == 1.0 or surf is None:
            return surf
        got = self._blit_cache.get(id(surf))
        if got is None:
            w, h = surf.get_size()
            got = pygame.transform.smoothscale(
                surf, (max(1, round(w * z)), max(1, round(h * z))))
            self._blit_cache[id(surf)] = got
        return got

    def draw_ground(self, surface: pygame.Surface, camera) -> None:
        """Terrain only -- water, void scenery, foam, room floors, bridges (or
        the flat fallback). The depth-sorted layer (`scenery_drawables` +
        entities) is composited on top by the caller."""
        if not self._tiles_ready:
            self._build_tiles()

        z = getattr(camera, "zoom", 1.0)
        if z != self._render_zoom:
            self._render_zoom = z
            self._blit_cache.clear()

        ox, oy = camera.pos.x, camera.pos.y
        if self.layout is None:
            surface.fill(_VOID)
            floor = pygame.Rect(round(-ox * z), round(-oy * z),
                                round(self.width * z), round(self.height * z))
            pygame.draw.rect(surface, _FLOOR, floor)
            pygame.draw.rect(surface, _WALL, floor, width=3)
            self._draw_grid(surface, camera, floor)
            return

        if self._tiles_ok:
            self._draw_tiled(surface, camera)
        else:
            self._draw_flat_layout(surface, camera)
            for r in self.layout.rooms:      # grey wall border (flat mode only)
                pygame.draw.rect(surface, _WALL, self._screen_rect(r.rect, camera),
                                 width=3)

    def _screen_rect(self, rect: pygame.Rect, camera) -> pygame.Rect:
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        return pygame.Rect(round((rect.x - ox) * z), round((rect.y - oy) * z),
                           round(rect.width * z), round(rect.height * z))

    def scenery_drawables(self, camera) -> list:
        """`(depth_y, draw_fn)` for every visible interior-clutter decoration and
        obstacle. `depth_y` is the world y of the sprite's ground contact; the
        caller merges these with the entities and paints them back-to-front, so
        a sprite lower on the map overlaps the ones above it and a character
        standing behind (a lower y than) an obstacle is hidden by it."""
        if self.layout is None:
            return []
        cull = camera.visible_rect().inflate(320, 320)
        out: list = []
        """
        for inst_list in self._room_decor.values():
            for inst in inst_list:
                if cull.collidepoint(inst[4], inst[5]):
                    out.append((inst[5],
                                lambda s, c=camera, it=inst:
                                self._blit_one_decor(s, c, it)))
        """
        for i, o in enumerate(self.obstacles):
            if cull.collidepoint(o.pos.x, o.pos.y):
                out.append((o.pos.y,
                            lambda s, c=camera, idx=i, ob=o:
                            self._draw_one_obstacle(s, c, idx, ob)))
        return out

    def _draw_tiled(self, surface, camera) -> None:
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        if self._water_buf is not None:
            wt = self._water_tile
            surface.blit(self._z_surf(self._water_buf),
                         (-(ox % wt) * z, -(oy % wt) * z))
        else:
            surface.fill(_VOID)

        view = camera.visible_rect()
        # Void scenery sits straight on the water, under the foam / terrain.
        if self._void_decor:
            self._blit_decor(surface, camera, self._void_decor, view)
        # Foam first, on the water -- the room surfaces (SRCALPHA) then sit on
        # top, so foam only shows through the transparent water-side of the
        # autotile edge/corner tiles and on the open water just outside a room.
        if self._foam:
            frame = self._foam[int(pygame.time.get_ticks() * 0.001 * 12) % len(self._foam)]
            half = frame.get_width() // 2 - 32
            fview = view.inflate(frame.get_width(), frame.get_height())
            zframe = self._z_surf(frame)
            for wx, wy in self._shore:
                if fview.collidepoint(wx, wy):
                    surface.blit(zframe, ((wx - ox - half) * z, (wy - oy - half) * z))
        # ... then the baked room floors (autotile edges baked in) ...
        for r in self.layout.rooms:
            if r.rect.colliderect(view):
                surface.blit(self._z_surf(self._room_surfs[r.id]),
                             ((r.rect.x - ox) * z, (r.rect.y - oy) * z))
        # ... corridors last, so their grass covers the foam at doorways.
        for rect, surf in self._corr_surfs:
            if rect.colliderect(view):
                surface.blit(self._z_surf(surf),
                             ((rect.x - ox) * z, (rect.y - oy) * z))
        # Interior clutter is NOT drawn here -- it is depth-sorted with the
        # obstacles and the characters (see `scenery_drawables`).

    def draw_room_clutter(self, surface, camera) -> None:
        """All interior clutter, unsorted -- only the whole-map `draw()` path.
            Public method so it can be called from outside the class to draw room clutter and don't belong in the depth culling / sorting of the main draw pass.
        """
        view = camera.visible_rect()
        for r in self.layout.rooms:
            inst = self._room_decor.get(r.id)
            if inst and r.rect.colliderect(view):
                self._blit_decor(surface, camera, inst, view)

    def _blit_one_decor(self, surface, camera, inst) -> None:
        """Blit one `(frames, anchor_x, anchor_y, fps, wx, wy)` scenery instance:
        current animation frame, base on `(wx, wy)`."""
        frs, ax, ay, fps, wx, wy = inst
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        frame = (frs[int(pygame.time.get_ticks() * 0.001 * fps) % len(frs)]
                 if fps else frs[0])
        surface.blit(self._z_surf(frame),
                     (round((wx - ox) * z - ax * z), round((wy - oy) * z - ay * z)))

    def _blit_decor(self, surface, camera, instances, view=None) -> None:
        """View-culled batch blit of scenery instances (void scatter + the
        unsorted `draw()` clutter path)."""
        if view is None:
            view = camera.visible_rect()
        cull = view.inflate(256, 256)
        for inst in instances:
            if cull.collidepoint(inst[4], inst[5]):
                self._blit_one_decor(surface, camera, inst)

    def _draw_flat_layout(self, surface, camera) -> None:
        surface.fill(_VOID)
        for c in self.layout.corridors:
            pygame.draw.rect(surface, _FLOOR, self._screen_rect(c.rect, camera))
        for r in self.layout.rooms:
            pygame.draw.rect(surface, _SPECIAL_FLOORS.get(r.kind, _FLOOR),
                             self._screen_rect(r.rect, camera))

    def _draw_one_obstacle(self, surface, camera, i, o) -> None:
        """One obstacle: the scaled decoration skin, seated below the collider
        centre by `config.SPRITE_ANCHOR_DROP` (same as the characters -- more of
        the skin sits inside the collision circle), or a fallback circle if no
        rig resolved. Trees also cast a canopy shadow, but that is a separate
        late pass (`draw_tree_shadows`) and stays on the world anchor."""
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        sx, sy = (o.pos.x - ox) * z, (o.pos.y - oy) * z
        entry = self._decos.get(i)
        if entry is not None:
            ax, ay, fps, frs = entry
            frame = (frs[int(pygame.time.get_ticks() * 0.001 * fps) % len(frs)]
                     if fps else frs[0])
            drop = config.SPRITE_ANCHOR_DROP * o.radius * z
            surface.blit(self._z_surf(frame),
                         (round(sx - ax * z), round(sy - ay * z + drop)))
        else:
            pygame.draw.circle(surface, o.color, (int(sx), int(sy)),
                               round(o.radius * z))
            pygame.draw.circle(surface, _WALL, (int(sx), int(sy)),
                               round(o.radius * z), 2)

    def draw_tree_shadows(self, surface, camera) -> None:
        """Blit each visible tree's soft canopy shadow. The caller runs this
        *after* the depth-sorted character layer, so a hero / enemy standing
        under a tree is gently darkened by its shade."""
        if not self._tree_shadows:
            return
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        view = camera.visible_rect().inflate(200, 200)
        for wx, wy, r, surf in self._tree_shadows:
            if view.collidepoint(wx, wy):
                surface.blit(self._z_surf(surf),
                             (round((wx - ox) * z - r * z),
                              round((wy - oy) * z - r * z)))

    def _draw_obstacles(self, surface, camera) -> None:
        """Every visible obstacle, unsorted -- only the whole-map `draw()` path."""
        view = camera.visible_rect().inflate(260, 260)
        for i, o in enumerate(self.obstacles):
            if view.collidepoint(o.pos.x, o.pos.y):
                self._draw_one_obstacle(surface, camera, i, o)

    def _draw_grid(self, surface, camera, floor_rect) -> None:
        z = self._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        step = 128
        for x in range(0, self.width + step, step):
            sx = (x - ox) * z
            pygame.draw.line(surface, _GRID, (sx, floor_rect.top), (sx, floor_rect.bottom))
        for y in range(0, self.height + step, step):
            sy = (y - oy) * z
            pygame.draw.line(surface, _GRID, (floor_rect.left, sy), (floor_rect.right, sy))
