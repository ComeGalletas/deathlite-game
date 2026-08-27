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
        self._room_surfs: dict[int, pygame.Surface] = {}
        self._corr_surfs: list[tuple[pygame.Rect, pygame.Surface]] = []
        self._shore: list[tuple[int, int]] = []       # top-left world px of shoreline tiles
        self._foam: list[pygame.Surface] | None = None
        # Obstacle index -> (anchor_x, anchor_y, fps, [frame, ...]). Each obstacle
        # is skinned with a decoration rig scaled to its collider; obstacles with
        # no entry (missing tileset / flag off) fall back to a drawn circle.
        self._decos: dict[int, tuple] = {}
        # Obstacle index -> a soft contact-shadow Surface, scaled to the collider
        # and squashed for the oblique top-down view (T9). Drawn under the skin.
        self._obst_shadow: dict[int, pygame.Surface] = {}
        # Non-colliding scenery scatter (T8), resolved at build time. Each
        # instance is (frames, anchor_x, anchor_y, fps, world_x, world_y).
        self._room_decor: dict[int, list[tuple]] = {}   # room id -> interior clutter
        self._void_decor: list[tuple] = []              # water scenery in the void

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
    def _bridge_slot(horizontal: bool, row: int, col: int,
                     rows: int, cols: int) -> str:
        """Which bridge cell a corridor position needs: end caps at the run's
        extremes, `mid` in between (see data/terrain.json 'bridge')."""
        if horizontal:
            return ("h_left" if col == 0 else
                    "h_right" if col == cols - 1 else "h_mid")
        return ("v_top" if row == 0 else
                "v_bot" if row == rows - 1 else "v_mid")

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

        def paint_corridor(rect: pygame.Rect) -> pygame.Surface:
            horizontal = rect.width >= rect.height
            cols = max(1, -(-rect.width // px))       # ceil
            rows = max(1, -(-rect.height // px))
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            for row in range(rows):
                for col in range(cols):
                    if bridge_ok:
                        name = self._bridge_slot(horizontal, row, col, rows, cols)
                        tile_surf = cell(b_sheet, b_slots.get(name, b_slots["h_mid"]),
                                         b_cols)
                    else:
                        tile_surf = cell(floor_sheet, interior)
                    surf.blit(tile_surf, (col * px, row * px))
                    # Every corridor cell is a shore cell -- foam behind the
                    # bridge shows through the plank gaps over open water.
                    self._shore.append((rect.x + col * px, rect.y + row * px))
            return surf

        for r in self.layout.rooms:
            self._room_surfs[r.id] = paint_room(r)
        for c in self.layout.corridors:
            self._corr_surfs.append((c.rect.copy(), paint_corridor(c.rect)))

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
            buf = pygame.Surface((config.SCREEN_WIDTH + wt,
                                  config.SCREEN_HEIGHT + wt)).convert()
            for y in range(0, buf.get_height(), wt):
                for x in range(0, buf.get_width(), wt):
                    buf.blit(water, (x, y))
            self._water_buf = buf

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

        # A soft contact shadow (T9), one per distinct collider radius. Scaled
        # so the source's opaque blob (`shadow_blob` px within the frame) spans
        # ~2.2 * radius, then squashed to 0.55 h for the oblique view.
        shadow_src = None
        if config.TERRAIN_SHADOWS and conf.get("shadow"):
            shadow_src = a.picture(conf["shadow"])
        blob = float(conf.get("shadow_blob", 70)) or 70.0
        shadow_cache: dict[int, pygame.Surface] = {}

        def shadow_for(radius: int) -> pygame.Surface | None:
            if shadow_src is None:
                return None
            if radius not in shadow_cache:
                s = (2.2 * radius) / blob
                sw = max(1, round(shadow_src.get_width() * s))
                sh = max(1, round(shadow_src.get_height() * s * 0.55))
                shadow_cache[radius] = pygame.transform.smoothscale(shadow_src, (sw, sh))
            return shadow_cache[radius]

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
                sh = shadow_for(int(o.radius))
                if sh is not None:
                    self._obst_shadow[i] = sh

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
        if not self._tiles_ready:
            self._build_tiles()

        ox, oy = camera.pos.x, camera.pos.y

        if self.layout is None:
            surface.fill(_VOID)
            floor = pygame.Rect(-ox, -oy, self.width, self.height)
            pygame.draw.rect(surface, _FLOOR, floor)
            pygame.draw.rect(surface, _WALL, floor, width=3)
            self._draw_grid(surface, camera, floor)
            return

        if self._tiles_ok:
            self._draw_tiled(surface, camera)
        else:
            self._draw_flat_layout(surface, camera)
            for r in self.layout.rooms:      # grey wall border (flat mode only)
                pygame.draw.rect(surface, _WALL,
                                 r.rect.move(-camera.pos.x, -camera.pos.y), width=3)

        self._draw_obstacles(surface, camera)

    def _draw_tiled(self, surface, camera) -> None:
        ox, oy = camera.pos.x, camera.pos.y
        if self._water_buf is not None:
            wt = self._water_buf.get_width() - config.SCREEN_WIDTH
            surface.blit(self._water_buf, (-(ox % wt), -(oy % wt)))
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
            for wx, wy in self._shore:
                if fview.collidepoint(wx, wy):
                    surface.blit(frame, (wx - ox - half, wy - oy - half))
        # ... then the baked room floors (autotile edges baked in) ...
        for r in self.layout.rooms:
            if r.rect.colliderect(view):
                surface.blit(self._room_surfs[r.id], (r.rect.x - ox, r.rect.y - oy))
        # ... corridors, so their grass covers the foam at doorways ...
        for rect, surf in self._corr_surfs:
            if rect.colliderect(view):
                surface.blit(surf, (rect.x - ox, rect.y - oy))
        # ... then interior clutter, on the grass, below the entities.
        if self._room_decor:
            for r in self.layout.rooms:
                inst = self._room_decor.get(r.id)
                if inst and r.rect.colliderect(view):
                    self._blit_decor(surface, camera, inst, view)

    def _blit_decor(self, surface, camera, instances, view=None) -> None:
        """Blit a list of `(frames, anchor_x, anchor_y, fps, wx, wy)` scenery
        instances: current animation frame, base at `(wx, wy)`, view-culled."""
        ox, oy = camera.pos.x, camera.pos.y
        if view is None:
            view = camera.visible_rect()
        cull = view.inflate(256, 256)
        now = pygame.time.get_ticks() * 0.001
        for frs, ax, ay, fps, wx, wy in instances:
            if not cull.collidepoint(wx, wy):
                continue
            frame = frs[int(now * fps) % len(frs)] if fps else frs[0]
            surface.blit(frame, (round(wx - ax - ox), round(wy - ay - oy)))

    def _draw_flat_layout(self, surface, camera) -> None:
        ox, oy = camera.pos.x, camera.pos.y
        surface.fill(_VOID)
        for c in self.layout.corridors:
            pygame.draw.rect(surface, _FLOOR, c.rect.move(-ox, -oy))
        for r in self.layout.rooms:
            pygame.draw.rect(surface, _SPECIAL_FLOORS.get(r.kind, _FLOOR),
                             r.rect.move(-ox, -oy))

    def _draw_obstacles(self, surface, camera) -> None:
        """Each obstacle draws as its scaled decoration sprite (base on the
        collider centre); obstacles with no resolved rig fall back to a circle."""
        ox, oy = camera.pos.x, camera.pos.y
        view = camera.visible_rect().inflate(260, 260)
        decos = self._decos
        shadows = self._obst_shadow
        now = pygame.time.get_ticks() * 0.001
        for i, o in enumerate(self.obstacles):
            if not view.collidepoint(o.pos.x, o.pos.y):
                continue
            entry = decos.get(i)
            if entry is not None:
                sh = shadows.get(i)
                if sh is not None:
                    surface.blit(sh, (round(o.pos.x - sh.get_width() / 2 - ox),
                                      round(o.pos.y - sh.get_height() / 2
                                            + o.radius * 0.15 - oy)))
                ax, ay, fps, frs = entry
                frame = frs[int(now * fps) % len(frs)] if fps else frs[0]
                surface.blit(frame, (round(o.pos.x - ax - ox),
                                     round(o.pos.y - ay - oy)))
            else:
                pygame.draw.circle(surface, o.color,
                                   (int(o.pos.x - ox), int(o.pos.y - oy)), o.radius)
                pygame.draw.circle(surface, _WALL,
                                   (int(o.pos.x - ox), int(o.pos.y - oy)), o.radius, 2)

    def _draw_grid(self, surface, camera, floor_rect) -> None:
        step = 128
        for x in range(0, self.width + step, step):
            sx = x - camera.pos.x
            pygame.draw.line(surface, _GRID, (sx, floor_rect.top), (sx, floor_rect.bottom))
        for y in range(0, self.height + step, step):
            sy = y - camera.pos.y
            pygame.draw.line(surface, _GRID, (floor_rect.left, sy), (floor_rect.right, sy))
