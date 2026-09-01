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
from world.elevation import LevelIndex, can_step
from world.procedural import Room, WorldLayout, generate_world
from world.terrain import autotile
from world.terrain import bake as terrain_bake
from world.legacy import terrain_cliffs
from world.terrain import decor as terrain_decor
from world.terrain import grid_paint
from world.legacy import terrain_rooms
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
            self._levels = None
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
            # LD-9 D0/D2: elevation lookup for the movement rule. Flat
            # (all level 0) with the height-map flag off, so it refuses
            # nothing there.
            self._levels = LevelIndex(self.layout)

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

    def path_ok(self, prev: pygame.Vector2, new: pygame.Vector2) -> bool:
        """May a body travel from `prev` to `new` given the terrain's elevation?

        Both points can be on floor and the move still be illegal: a plateau's
        flank and its back edge are level changes with no stone in them, so
        `_point_ok` sees floor either side. Only a flight crosses them.

        The segment is walked rather than end-checked. Ordinary movement is a
        few pixels a frame and never leaves the tile it started in, but a
        charger's lunge (`ai/behaviors/melee.py`, `ai/components/attacks.py`)
        resolves straight to the player's position and can span many tiles; a
        bare endpoint test would let it vault a cliff. Sampling every half tile
        cannot skip one.

        No index (the flag off, or no layout) means no elevation to respect."""
        ix = self._levels
        if ix is None:
            return True
        a = ix.tile_of(prev.x, prev.y)
        b = ix.tile_of(new.x, new.y)
        if a == b:
            return True
        step = ix.px * 0.5
        d = new - prev
        n = max(1, int(d.length() / step) + 1)
        cur = a
        for i in range(1, n + 1):
            t = i / n
            nxt = ix.tile_of(prev.x + d.x * t, prev.y + d.y * t)
            if nxt != cur:
                if not can_step(ix, cur, nxt):
                    return False
                cur = nxt
        return cur == b or can_step(ix, cur, b)

    def is_walkable(self, pos: pygame.Vector2, radius: float = 0.0,
                    frm: pygame.Vector2 | None = None) -> bool:
        """`frm` opts into the elevation rule: the move from there to here must
        be one the terrain allows. Callers that are only asking "is this spot
        free" -- the AI's `is_walkable` probe, spawn placement -- leave it None
        and get the pure floor test, unchanged.

        The rule is applied to the body's **centre only**. The radius probes
        below stay a plain floor test, as they always were: a terrace is a few
        tiles wide, so demanding that every probe sit on the centre's level
        would stop a large enemy standing anywhere near a rim, and overhanging
        a drop is exactly what those probes already tolerate against a wall."""
        if not self._point_ok(pos.x, pos.y):
            return False
        if frm is not None and not self.path_ok(frm, pos):
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
        if self.is_walkable(new, radius, frm=prev):
            return new
        slide_x = pygame.Vector2(new.x, prev.y)
        if self.is_walkable(slide_x, radius, frm=prev):
            return slide_x
        slide_y = pygame.Vector2(prev.x, new.y)
        if self.is_walkable(slide_y, radius, frm=prev):
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
            if self.is_walkable(hop, radius, frm=prev):
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
        """Bake the layout into surfaces. Body in `world/terrain/bake.py`."""
        terrain_bake.bake(self)

    # --- render -----------------------------------------------
    # Bodies live in `world/terrain/render.py` (`TerrainRenderer`, W6) and
    # callers reach them through the `renderer` property above. There used to be
    # eleven forwarders here doing nothing but `return self.renderer.<same
    # name>(...)`, and two of them were round trips: `TerrainRenderer` called
    # back through `GameMap` to reach its *own* methods. Naming the object that
    # owns the drawing is both shorter and truthful about where it happens.
