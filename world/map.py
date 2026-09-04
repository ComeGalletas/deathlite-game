"""The playable world.

`GameMap` wraps a procedural `WorldLayout` (islands + bridges). It answers "is
this walkable?", slides entities along walls, and picks legal spawn points;
without a seed it degrades to one big rectangular room (tests and any non-run
context). It also **bakes** the tiled terrain (`_build_tiles` -> one `Surface`
per terrace, the bridges, the decor and the anchor lists, via
`world/terrain/`) and hands a `TerrainRenderer` (`world/terrain/render.py`) the
job of drawing it. If the tileset is missing, that renderer's flat fallback is
permanent.
"""
from __future__ import annotations

import random

import pygame

from game import config
from game.assets import get_assets
from world.elevation import LevelIndex
from world.rules import floor as floor_rules
from world.rules import inset as terrain_inset
from world.rules.steps import can_step
from world.procedural import Room, WorldLayout, generate_world
from world.terrain import autotile
from world.terrain import bake as terrain_bake
from world.terrain.baked import BakedTerrain
from world.terrain.render import TerrainRenderer

# Compass directions for the last-resort unwedge hop in `resolve_movement`.
_R2 = 2.0 ** -0.5
_ESCAPE_DIRS = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
                (_R2, _R2), (_R2, -_R2), (-_R2, _R2), (-_R2, -_R2))


class _ObstacleIndex:
    """The obstacles bucketed by a coarse world grid, so a collision probe
    asks the handful near a point instead of every obstacle in the world.

    `is_walkable` used to end with a scan of the whole list -- 565
    obstacles on a shipping seed, five probes a call, up to three calls a
    move -- and that scan was 44 % of the update loop at a hundred live
    enemies (93 us a call; 4 us with this). Rebuilt whenever the list is
    assigned (`GameMap.obstacles`); obstacles never move once placed.
    """

    __slots__ = ("cell", "reach", "_buckets")

    def __init__(self, obstacles, cell: int = 128) -> None:
        self.cell = int(cell)
        self.reach = 0.0                        # the widest obstacle's radius
        self._buckets: dict[tuple[int, int], list] = {}
        for o in obstacles:
            key = (int(o.pos.x // self.cell), int(o.pos.y // self.cell))
            self._buckets.setdefault(key, []).append(o)
            if o.radius > self.reach:
                self.reach = float(o.radius)

    def near(self, x: float, y: float, radius: float) -> list:
        """Every obstacle whose disc could overlap a disc of `radius` at
        (x, y) -- a superset; the caller does the exact test."""
        if not self._buckets:
            return []
        r = radius + self.reach
        c = self.cell
        x0, x1 = int((x - r) // c), int((x + r) // c)
        y0, y1 = int((y - r) // c), int((y + r) // c)
        if x0 == x1 and y0 == y1:
            return self._buckets.get((x0, y0), [])
        out: list = []
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                b = self._buckets.get((gx, gy))
                if b:
                    out.extend(b)
        return out


class GameMap:
    def __init__(self, seed: int | None = None, *, layout: WorldLayout | None = None) -> None:
        """`seed` generates the world here; `layout` hands one in that was
        generated elsewhere (the loading screen, a step at a time)."""
        if seed is None and layout is None:
            self.layout: WorldLayout | None = None
            self._levels = None
            self.width = config.WORLD_WIDTH
            self.height = config.WORLD_HEIGHT
            self._rects = [pygame.Rect(0, 0, self.width, self.height)]
            self.obstacles = []
        else:
            self.layout = layout if layout is not None else generate_world(seed)
            b = self.layout.bounds
            self.width, self.height = b.width, b.height
            self._rects = self.layout.walkable_rects()
            self.obstacles = self.layout.obstacles
            # Elevation lookup for the movement rule.
            self._levels = LevelIndex(self.layout)

        # The terrace margin (`world/rules/inset.py`): how far inside its own floor a
        # body's centre has to stand. Read from the data rather than defaulted
        # in code; 0 switches the whole rule off.
        self._body_inset = terrain_inset.body_inset()

        # The baked terrain (`world/terrain/baked.py`), built lazily on the
        # first draw() -- it needs a display. `None` until then.
        self.terrain: BakedTerrain | None = None

        # Draw-time zoom: the baked terrain surfaces are 1:1 world pixels;
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
    def obstacles(self) -> list:
        return self._obstacles

    @obstacles.setter
    def obstacles(self, value) -> None:
        self._obstacles = value
        self._obstacle_index = _ObstacleIndex(value)

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
        """Is the point on floor? `world/rules/floor.py` is the one body of
        this rule; the navigation grid reads the same function."""
        if self.layout is None:
            return self._rects[0].collidepoint(x, y)
        return floor_rules.point_on_floor(self.layout, x, y)

    def _over_island(self, x: float, y: float) -> bool:
        """The flying floor test: any cell of an island's grid, or a bridge.
        `world/rules/floor.py` is the one body of this rule."""
        if self.layout is None:
            return self._rects[0].collidepoint(x, y)
        return (floor_rules.over_island(self.layout, x, y)
                or floor_rules.in_corridor(self.layout, x, y))

    def _room_of(self, x: float, y: float):
        """The island whose floor the point actually stands on, or `None`."""
        if self.layout is None:
            return None
        return floor_rules.room_of(self.layout, x, y)

    def inset_at(self, x: float, y: float) -> float:
        """How far inside its own terrace `(x, y)` stands, in pixels. `CAP`
        off any island floor -- on a bridge -- because a bridge is flat and
        carries no level boundary to keep away from."""
        if self.layout is None:
            return float(terrain_inset.CAP)
        return float(floor_rules.inset_at(self.layout, x, y))

    def inset_ok(self, x: float, y: float) -> bool:
        """Is `(x, y)` far enough inside its own terrace for a body to stand?"""
        return (self._body_inset <= 0.0
                or self.inset_at(x, y) >= self._body_inset)

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

        No index (no layout) means no elevation to respect."""
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
                    frm: pygame.Vector2 | None = None, flying: bool = False) -> bool:
        """`frm` opts into the elevation rule: the move from there to here must
        be one the terrain allows. Callers that are only asking "is this spot
        free" -- the AI's `is_walkable` probe, spawn placement -- leave it None
        and get the pure floor test, unchanged.

        The rule is applied to the body's **centre only**. The radius probes
        below stay a plain floor test, as they always were: a terrace is a few
        tiles wide, so demanding that every probe sit on the centre's level
        would stop a large enemy standing anywhere near a rim, and overhanging
        a drop is exactly what those probes already tolerate against a wall.

        The **terrace margin** is applied to the centre as well, and for the
        same reason it is a fixed number of pixels rather than a body radius:
        it exists so that two floors read as separate, not so that bodies are
        physically excluded. Scaling it by radius would forbid the boss, at 46
        px, from most of a 64 px terrace.

        A body already inside the margin -- spawned there before the rule
        existed, knocked back into it, or standing where a crossing's exemption
        ends -- may still move, as long as it does not go *deeper*. "Cannot
        enter, may leave" is what stops the rule wedging anything; refusing
        outright would freeze a body the moment anything put it there."""
        # A flyer (`flying` tag, `The First Hunger`) is over the world, not on
        # it: no terrace margin, no elevation rule, no obstacle, and no radius
        # probe -- it passes above a boulder and across a cliff in one line,
        # and over its own island's lake, which is a cell of the height map
        # like any other. It still may not leave the island: the sea is where
        # a body goes to become unreachable, and the arena has to stay a fight.
        if flying:
            return self._over_island(pos.x, pos.y)
        if not self._point_ok(pos.x, pos.y):
            return False
        if self._body_inset > 0.0 and not self.inset_ok(pos.x, pos.y):
            if frm is None:
                return False
            if self.inset_at(pos.x, pos.y) < self.inset_at(frm.x, frm.y):
                return False
        if frm is not None and not self.path_ok(frm, pos):
            return False
        if radius > 0 and not (
                self._point_ok(pos.x + radius, pos.y)
                and self._point_ok(pos.x - radius, pos.y)
                and self._point_ok(pos.x, pos.y + radius)
                and self._point_ok(pos.x, pos.y - radius)):
            return False
        for o in self._obstacle_index.near(pos.x, pos.y, radius):
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return False
        return True

    def blocking_obstacle_hit(self, pos: pygame.Vector2, radius: float):
        """First projectile-blocking obstacle overlapping the circle, or None."""
        for o in self._obstacle_index.near(pos.x, pos.y, radius):
            if not o.blocks_projectiles:
                continue
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return o
        return None

    def resolve_movement(self, prev: pygame.Vector2, new: pygame.Vector2,
                         radius: float, flying: bool = False) -> pygame.Vector2:
        """Move toward `new`; if it hits a wall, slide along one axis; if that
        also fails, hop one short step to an open compass direction so a wedged
        entity always has an out. Unchanged if every hop is blocked too."""
        if self.is_walkable(new, radius, frm=prev, flying=flying):
            return new
        slide_x = pygame.Vector2(new.x, prev.y)
        if self.is_walkable(slide_x, radius, frm=prev, flying=flying):
            return slide_x
        slide_y = pygame.Vector2(prev.x, new.y)
        if self.is_walkable(slide_y, radius, frm=prev, flying=flying):
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
            if self.is_walkable(hop, radius, frm=prev, flying=flying):
                return hop
        return pygame.Vector2(prev)

    def random_point_in_room(self, room: Room, rng: random.Random,
                             margin: float = 24.0) -> pygame.Vector2:
        px = config.TILE_PX
        if not room.cells:                          # no mask: a plain rect
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
        world is large.

        Since spawn master S3 this is the **fallback** only -- the world with
        no layout, or one generated with no spawn points. A generated world
        places on its `layout.spawn_points` (`spawn/placement.py`)."""
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
    # The autotile slot maths lives in world/terrain/autotile.py; these
    # aliases keep `GameMap._bridge_slot` (test_terrain) working.
    _slot_for = staticmethod(autotile.slot_for)
    _mask_slot = staticmethod(autotile.mask_slot)
    _bridge_slot = staticmethod(autotile.bridge_slot)

    _foam_routine_index = staticmethod(BakedTerrain.foam_routine_index)

    def _foam_frame_at(self, wx: float, wy: float, seconds: float) -> pygame.Surface:
        return self.terrain.foam_frame_at(wx, wy, seconds)

    def _build_tiles(self) -> None:
        """Bake the layout into `self.terrain`, once. Body in
        `world/terrain/bake.py`. Idempotent: tests that share one map through
        `tests/worlds.py` rely on a second call being free."""
        if self.terrain is None:
            self.terrain = terrain_bake.bake(self.layout)

    # The baked fields under the names the renderer and the tests read them
    # by. Each forwards to `self.terrain`; before the bake they answer empty.
    # `__dict__.get`, not `self.terrain`: the pure-helper tests build a map
    # with `GameMap.__new__` and never run `__init__`.
    _tiles_ready = property(lambda self: self.__dict__.get("terrain") is not None)
    _tiles_ok = property(lambda self: bool(self.__dict__.get("terrain")
                                           and self.terrain.ok))
    _sheets = property(lambda self: getattr(self.__dict__.get("terrain"), "sheets", None))

    def _baked(name, empty):
        def get(self):
            t = self.__dict__.get("terrain")
            return empty() if t is None else getattr(t, name)

        def put(self, value):
            if self.__dict__.get("terrain") is None:
                self.terrain = BakedTerrain(self.__dict__.get("layout"),
                                            list(self.__dict__.get("obstacles", ())))
            setattr(self.terrain, name, value)
        return property(get, put)

    _water_buf = _baked("water_buf", lambda: None)
    _water_tile = _baked("water_tile", lambda: 0)
    _grid_surfs = _baked("grid_surfs", list)
    _corr_surfs = _baked("corr_surfs", list)
    _shore = _baked("shore", list)
    _shadow = _baked("shadow", lambda: None)
    _foam = _baked("foam", lambda: None)
    _foam_routines = _baked("foam_routines", lambda: BakedTerrain.foam_routines)
    _decos = _baked("decos", dict)
    _sprite_drop = _baked("sprite_drop", dict)
    _tree_shadows = _baked("tree_shadows", dict)
    _art_rects = _baked("art_rects", dict)
    _ghost = _baked("ghost", dict)
    _room_decor = _baked("room_decor", dict)
    _void_decor = _baked("void_decor", list)
    del _baked

    # --- render -----------------------------------------------
    # Bodies live in `world/terrain/render.py` (`TerrainRenderer`) and
    # callers reach them through the `renderer` property above. There used to be
    # eleven forwarders here doing nothing but `return self.renderer.<same
    # name>(...)`, and two of them were round trips: `TerrainRenderer` called
    # back through `GameMap` to reach its *own* methods. Naming the object that
    # owns the drawing is both shorter and truthful about where it happens.
