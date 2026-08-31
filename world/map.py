"""The playable world.

`GameMap` wraps a procedural `WorldLayout` (rooms + corridors). It answers "is
this walkable?", slides entities along walls, and picks legal spawn points;
without a seed it degrades to one big rectangular room (tests and any non-run
context). It also **bakes** the tiled terrain (`_build_tiles` -> the room /
corridor / cliff / stair / decor `Surface`s and anchor lists, via
`world/terrain/`) and hands a `TerrainRenderer` (`world/terrain/render.py`) the
job of drawing it. If the tileset is missing, that renderer's flat fallback is
permanent.
"""
from __future__ import annotations

import random

import pygame

from game import config
from game.assets import get_assets
from world.procedural import Room, WorldLayout, generate_world
from world.terrain import autotile
from world.terrain import cliffs as terrain_cliffs
from world.terrain import decor as terrain_decor
from world.terrain import grid_paint
from world.terrain import rooms as terrain_rooms
from world.terrain.sheets import TileSheets
from world.terrain.render import TerrainRenderer

# Compass directions for the last-resort unwedge hop in `resolve_movement`.
_R2 = 2.0 ** -0.5
_ESCAPE_DIRS = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
                (_R2, _R2), (_R2, -_R2), (-_R2, _R2), (-_R2, -_R2))


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
        # `(blit_rect, surf, floor)` -- LD-8b: every terrain container below
        # carries the floor it belongs to so `_draw_tiled` can composite the
        # map one elevation at a time (a floor's grass, then the next floor's
        # cliff wall dropping onto it, then that floor's grass, ...).
        self._corr_surfs: list[tuple] = []
        # LD-1 verticality: one baked south-facing cliff-face skirt per raised
        # room, and one baked strip per stair. `(blit_rect, surf, floor)`.
        self._cliff_surfs: list[tuple] = []
        self._stair_surfs: list[tuple] = []
        # LD-9: `(blit_rect, surf, base_level)` -- one baked surface per
        # height-map room, covering its terraces, walls and flights together.
        # Used instead of every other terrain collection when
        # `config.HEIGHTMAP_ROOMS` is on.
        self._grid_surfs: list[tuple] = []
        # LD-7: the LD-4 staircase-unit tiles (landings + the 1x2 stair piece),
        # lifted out of the cliff surface so they paint in the walkable-structure
        # layer, above the drop shadow, not under the room floors. Same
        # `(blit_rect, surf, high_floor)` shape as `_stair_surfs`.
        self._ramp_surfs: list[tuple] = []
        # LD-8a: `(blit_rect, surf, high_floor)` -- the rock stair overlay
        # sprite for a "rock"-style ramp unit, drawn on top of its own floor's
        # terrain so its foliage feathers over the neighbouring grass/cliff.
        self._stair_overlays: list[tuple] = []
        # LD-7a: `(blit_rect, tile, floor)` -- one lower-room grass tile drawn
        # at a cliff-face foot cell that has a room floor directly south of it,
        # in a pass *before* that floor's cliff faces so the stone sits on
        # grass, not sea. `floor` is the raised room whose face it carries.
        self._cliff_underlay: list[tuple] = []
        # LD-7a: `(room_id, col, row)` ground-room edge cells with a cliff band
        # flush overhead -- painted with the north side closed (no shoreline
        # autotile) and seeded with no foam.
        self._cliff_capped: set = set()
        self._shore: list[tuple[int, int]] = []       # top-left world px of shoreline tiles
        # LD-2 E8: `(x, y, floor)` -- top-left world px of a cliff foot that
        # drops into open water, plus the raised room's floor so it laps in
        # that level's pass. Kept out of `_shore` (sea-facing ground tiles only).
        self._cliff_foam: list[tuple] = []
        # LD-6: `(x, y, floor)` -- top-left world px of a cliff foot that lands
        # on a lower room's floor -- a static drop shadow, no animation, drawn
        # just under that level's cliff faces. `floor` is the raised room's.
        self._cliff_shadow: list[tuple] = []
        self._shadow: pygame.Surface | None = None
        self._foam: list[pygame.Surface] | None = None
        self._foam_routines: tuple[tuple[float, int], ...] = (
            (9.0, 0), (12.0, 5), (15.0, 10))
        # Obstacle index -> (anchor_x, anchor_y, fps, [frame, ...]). Each obstacle
        # is skinned with a decoration rig scaled to its collider; obstacles with
        # no entry (missing tileset / flag off) fall back to a drawn circle.
        self._decos: dict[int, tuple] = {}
        self._sprite_drop: dict[str, float] = {}
        # Obstacle index -> (world_x, world_y, radius, surf) for tree shades.
        # Each is depth-sorted immediately before its owning tree.
        self._tree_shadows: dict[int, tuple] = {}
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

    @property
    def renderer(self) -> TerrainRenderer:
        """The draw path (world/terrain/render.py). Lazily built and cached so
        the pure-helper unit tests that use `GameMap.__new__` and then call
        `_z_surf` / `shade_character_frame` directly keep working."""
        r = self.__dict__.get("_renderer")
        if r is None:
            r = self.__dict__["_renderer"] = TerrainRenderer(self)
        return r

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
    @staticmethod
    def room_cell(room: Room, x: float, y: float) -> tuple[int, int]:
        """The room-relative (col, row) tile a world point falls in."""
        px = config.TILE_PX
        return (int((x - room.rect.left) // px), int((y - room.rect.top) // px))

    def _point_ok(self, x: float, y: float) -> bool:
        if self.layout is None:
            return self._rects[0].collidepoint(x, y)
        for r in self.layout.rooms:
            rr = r.rect
            if (rr.left <= x < rr.right and rr.top <= y < rr.bottom
                    and self.room_cell(r, x, y) in r.cells):
                return True                # W5: grown-room bboxes can overlap in
                                           # the void -> check every room, no break
        for c in self.layout.corridors:
            if c.rect.collidepoint(x, y):
                return True
        for s in self.layout.stairs:          # LD-1: a stair is a walkable strip
            if s.rect.collidepoint(x, y):
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
        """Move toward `new`; if it hits a wall, slide along one axis; if that
        also fails, hop one short step to an open compass direction so a wedged
        entity always has an out. Unchanged if every hop is blocked too."""
        if self.is_walkable(new, radius):
            return new
        slide_x = pygame.Vector2(new.x, prev.y)
        if self.is_walkable(slide_x, radius):
            return slide_x
        slide_y = pygame.Vector2(prev.x, new.y)
        if self.is_walkable(slide_y, radius):
            return slide_y
        # Fully wedged (move + both axis slides blocked). Try a `radius`-length
        # hop in the eight compass directions, the one nearest the intended
        # heading first, so enemies whose behaviour has no unstick of its own
        # still recover. Purely a last resort -- normal movement never reaches
        # here.
        want = new - prev
        step = max(radius, 12.0)
        for dx, dy in sorted(_ESCAPE_DIRS,
                             key=lambda d: -(d[0] * want.x + d[1] * want.y)):
            hop = pygame.Vector2(prev.x + dx * step, prev.y + dy * step)
            if self.is_walkable(hop, radius):
                return hop
        return pygame.Vector2(prev)

    def random_point_in_room(self, room: Room, rng: random.Random,
                             margin: float = 24.0) -> pygame.Vector2:
        px = config.TILE_PX
        if not room.cells:                          # plain rect (flag off)
            r = room.rect
            return pygame.Vector2(
                rng.uniform(r.left + margin, r.right - margin),
                rng.uniform(r.top + margin, r.bottom - margin))
        col, row = rng.choice(sorted(room.cells))   # sorted -> deterministic
        m = min(margin, px * 0.35)
        return pygame.Vector2(
            room.rect.left + col * px + rng.uniform(m, px - m),
            room.rect.top + row * px + rng.uniform(m, px - m))

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
    # W3 (journals/world_refactor.md): the autotile slot maths moved verbatim to
    # world/terrain/autotile.py. These aliases keep `self._mask_slot(...)` (in
    # the painters) and `GameMap._bridge_slot` (test_terrain) working.
    _slot_for = staticmethod(autotile.slot_for)
    _mask_slot = staticmethod(autotile.mask_slot)
    _bridge_slot = staticmethod(autotile.bridge_slot)

    @staticmethod
    def _foam_routine_index(wx: float, wy: float, count: int) -> int:
        """Stable spatial bucket so neighboring shore patches do not lock-step."""
        col = int(wx) // config.TILE_PX
        row = int(wy) // config.TILE_PX
        return (col * 31 + row * 17) % max(1, count)

    def _foam_frame_at(self, wx: float, wy: float, seconds: float) -> pygame.Surface:
        assert self._foam
        routine = self._foam_routines[
            self._foam_routine_index(wx, wy, len(self._foam_routines))
        ]
        fps, phase = routine
        return self._foam[(int(seconds * fps) + phase) % len(self._foam)]

    def _build_tiles(self) -> None:
        self._tiles_ready = True
        if self.layout is None:
            return
        layout = self.layout
        a = get_assets()
        t = a.terrain
        sheets = TileSheets(a)
        if not sheets.ok:
            return                                   # tileset missing -> flat fallback
        self._sheets = sheets

        # W2/W4 (journals/world_refactor.md): the tileset adapter + tile cache
        # are `sheets` now; the room / corridor / cliff / stair painters live in
        # world/terrain/. `_build_tiles` only sequences them and still owns the
        # LD-7a cliff-cap pass, the shore filter, and the water / foam / decor
        # buffers below.
        px = sheets.px

        # LD-7a: ground-room edge cells that sit directly under a raised room's
        # cliff band. Their north side is stone, not open sea -- so `paint_room`
        # closes that side (interior tile, no shoreline autotile) and seeds no
        # foam there. Paired with the `_cliff_underlay` tile at the cliff foot
        # cell itself, this reads as the lower room extending one tile up under
        # the cliff. Only a cliff *flush* above the cell counts; a real gap
        # keeps its shoreline.
        band_rects = []
        for R in layout.rooms:
            if R.floor <= 0:
                continue
            fh = max(1, R.floor * int(config.CLIFF_TILES))
            for (bc, bro), bm in R.tile_meta.items():
                if bm.cliff == "top":
                    band_rects.append(pygame.Rect(
                        R.rect.x + bc * px, R.rect.y + (bro + 1) * px,
                        px, fh * px))
        cliff_capped: set = set()
        if band_rects:
            for r in layout.rooms:
                if r.floor != 0:
                    continue
                for (col, row) in r.cells:
                    if (col, row - 1) in r.cells:
                        continue
                    strip = pygame.Rect(r.rect.x + col * px + 4,
                                        r.rect.y + row * px - px // 2,
                                        px - 8, px)
                    if any(strip.colliderect(b) for b in band_rects):
                        cliff_capped.add((r.id, col, row))
        self._cliff_capped = cliff_capped

        if config.HEIGHTMAP_ROOMS:
            # LD-9 Phase C: one pass per room, straight off its height map.
            # Nothing else to stitch -- no separate cliff band, underlay,
            # drop shadow or ramp collection, because the grid already says
            # what every cell is. Falls through to the shared water / foam /
            # scenery setup below.
            self._shore = []
            for r in layout.rooms:
                got = grid_paint.paint_room_grid(self, sheets, layout, r)
                if got is not None:
                    self._grid_surfs.append((got[0], got[1], r.floor))
                self._shore.extend(grid_paint.grid_shore(r))
            for c in layout.corridors:
                rc = grid_paint.paint_bridge(sheets, c)
                self._corr_surfs.append((rc[0], rc[1], layout.room(c.a).floor))
            self._finish_tiles(a, sheets)
            return

        for r in layout.rooms:
            self._room_surfs[r.id] = terrain_rooms.paint_room(
                self, sheets, layout, r)
        for c in layout.corridors:
            rc = terrain_rooms.paint_corridor(sheets, layout, c)
            self._corr_surfs.append((rc[0], rc[1], layout.room(c.a).floor))
        for r in layout.rooms:
            if r.floor > 0:
                cl = terrain_cliffs.paint_cliff(self, sheets, layout, r)
                if cl is not None:
                    self._cliff_surfs.append(cl)
        for st in layout.stairs:
            # LD-3: a ramp step is drawn by `paint_cliff` as part of the run.
            # It is a `Stair` only so collision and nav pick it up for free --
            # baking a plain grass strip here would cover the slope.
            if st.ramp:
                continue
            sc = terrain_cliffs.paint_stair(sheets, layout, st)
            self._stair_surfs.append((sc[0], sc[1], layout.room(st.high_room).floor))

        # Keep every ground-room edge which still faces sea after all corridors,
        # stairs, and cliff geometry are known. Corridors render over this foam
        # but never create or suppress anchors of their own.
        self._shore = list(dict.fromkeys(
            (sx, sy) for sx, sy in self._shore
            if self._point_ok(sx + px / 2, sy + px / 2)
            and any(not self._point_ok(sx + px / 2 + dx, sy + px / 2 + dy)
                    for dx, dy in ((px, 0), (-px, 0), (0, px), (0, -px)))
        ))

        self._finish_tiles(a, sheets)

    def _finish_tiles(self, a, sheets) -> None:
        """The water buffer, drop shadow, foam frames and scenery scatter --
        shared by the LD-8 painter and the LD-9 height-map one, which differ
        only in how the land itself is baked."""
        t = a.terrain
        water = a.tile(str(t.get("water_tile")), 0)
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

        _shdw = a.frames("terrain_shadow", "loop")
        self._shadow = _shdw[0] if _shdw else None

        if config.TERRAIN_FOAM:
            self._foam = a.frames("terrain_foam", "loop")
            routines = t.get("foam_routines", [])
            parsed = tuple((max(0.1, float(r["fps"])), int(r.get("phase", 0)))
                           for r in routines if float(r.get("fps", 0)) > 0)
            if parsed:
                self._foam_routines = parsed

        if config.TERRAIN_DECORATIONS:
            terrain_decor.build_obstacle_decor(self, a)

        if config.TERRAIN_DECOR:
            terrain_decor.build_decor_scatter(self, a)

        self._tiles_ok = True

    # --- render -----------------------------------------------
    # --- render: bodies in world/terrain/render.py TerrainRenderer (W6) ---
    def draw(self, surface, camera):
        return self.renderer.draw(surface, camera)

    def draw_ground(self, surface, camera):
        return self.renderer.draw_ground(surface, camera)

    def draw_room_clutter(self, surface, camera):
        return self.renderer.draw_room_clutter(surface, camera)

    def scenery_drawables(self, camera):
        return self.renderer.scenery_drawables(camera)

    def shade_character_frame(self, frame, dest, camera, character_y):
        return self.renderer.shade_character_frame(frame, dest, camera, character_y)

    def draw_tree_shadows(self, surface, camera):
        return self.renderer.draw_tree_shadows(surface, camera)

    def _draw_obstacles(self, surface, camera):
        return self.renderer._draw_obstacles(surface, camera)

    def _draw_tiled(self, surface, camera):
        return self.renderer._draw_tiled(surface, camera)

    def _z_surf(self, surf):
        return self.renderer._z_surf(surf)

    def _draw_one_obstacle(self, surface, camera, i, o):
        return self.renderer._draw_one_obstacle(surface, camera, i, o)

    def _draw_one_tree_shadow(self, surface, camera, shadow):
        return self.renderer._draw_one_tree_shadow(surface, camera, shadow)
