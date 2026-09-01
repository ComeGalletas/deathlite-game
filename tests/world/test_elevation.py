"""LD-9 phase D: nav and collision obey the height map.

The feature is gated on `config.HEIGHTMAP_ROOMS`, which is off by default, so
this module flips it for its own worlds and restores it in `tearDownModule`.

What is actually at stake: `Room.cells` is the walkable subset of the grid, so
cliffs and lakes already block by geometry alone. What does *not* block is a
level change with no stone in it -- a plateau's flank and its back edge -- where
both tiles are floor and only a flight legitimately crosses. Every test here
exists because a point-in-floor test cannot see that edge.

`heightmap.walk_links` / `heightmap.reachable` are the authority throughout:
they are what `check_grid` validates every generated room against, so checking
the runtime against them is what stops nav and generation drifting apart.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from world.elevation import LevelIndex, NONE, can_cross, can_step
from world.gen.heightmap import reachable, walk_links
from world.layout import GROUND, VSTAIR, EWSTAIR, WALKABLE_KINDS
from world.map import GameMap
from world.pathfinding import NavField, NavGrid, FlowField, NAV_DIRS, _INF
from world.procedural import generate_world

# Two seeds, not forty. Every case here is structural -- it holds for a
# neighbourhood, not for a lucky layout -- and each seed costs a world plus a
# nav build. The exhaustive sweeps below cover tens of thousands of tiles
# apiece, which is where the confidence comes from.
SEEDS = (35, 7)

_SAVED = None
_WORLDS: dict = {}


def setUpModule():
    global _SAVED
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    _SAVED = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = True


def tearDownModule():
    config.HEIGHTMAP_ROOMS = _SAVED
    _WORLDS.clear()


def _world(seed):
    """Layout + map + index, built once per seed for the whole module."""
    if seed not in _WORLDS:
        gm = GameMap(seed=seed)
        _WORLDS[seed] = (gm.layout, gm, gm._levels)
    return _WORLDS[seed]


def _centre(ix, tile):
    px = ix.px
    return pygame.Vector2(ix.origin[0] + tile[0] * px + px / 2,
                          ix.origin[1] + tile[1] * px + px / 2)


def _abs_tiles(room):
    """`(col, row) -> absolute tile` for a room's grid."""
    px = config.TILE_PX
    c0 = int(room.rect.left) // px
    r0 = int(room.rect.top) // px
    return lambda p: (c0 + p[0], r0 + p[1])


class LevelIndexTests(unittest.TestCase):
    def test_every_walkable_cell_round_trips(self):
        """The index places each grid cell at the tile its world centre falls
        in, with the right level, kind and flight record."""
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            checked = 0
            for room in layout.rooms:
                at = _abs_tiles(room)
                for pos, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    t = ix.tile_of(*_centre(ix, at(pos)))
                    self.assertEqual(t, at(pos))
                    self.assertEqual(ix.level_at(*t), cell.level)
                    self.assertEqual(ix.kind_at(*t), cell.kind)
                    if cell.kind in (VSTAIR, EWSTAIR):
                        self.assertIs(ix.flight_at(*t), cell)
                    checked += 1
            self.assertGreater(checked, 1000, f"seed {seed}: nothing to check")

    def test_cliffs_and_water_carry_no_surface(self):
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            for room in layout.rooms:
                at = _abs_tiles(room)
                for pos, cell in room.grid.items():
                    if cell.kind in WALKABLE_KINDS:
                        continue
                    t = at(pos)
                    if ix.has_surface(*t):
                        # only a bridge may overwrite a non-walkable grid cell
                        self.assertTrue(
                            any(c.rect.collidepoint(*_centre(ix, t))
                                for c in layout.corridors),
                            f"seed {seed}: {cell.kind} at {t} has a surface")

    def test_room_rects_are_tile_aligned(self):
        """`_add_grid` can only place cells when they are; it falls back to flat
        otherwise, which would silently mis-level the world."""
        px = config.TILE_PX
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            for room in layout.rooms:
                self.assertEqual((int(room.rect.left) % px,
                                  int(room.rect.top) % px), (0, 0))


class PackingTests(unittest.TestCase):
    def test_no_two_rooms_share_a_land_cell(self):
        """The height-map equivalent of `test_procedural`'s
        `test_all_geometry_within_bounds_and_nonoverlapping`, which asserts room
        *rects* never collide.

        That invariant is deliberately false here: rects overlap so the islands
        can sit closer and the bridges between them stay short. What must hold
        instead is the one that actually matters -- no world tile is land in two
        rooms at once. `HEIGHTMAP_COAST_KEEP` is what makes it safe, by
        guaranteeing a band of void inside every rect that the coast walk
        cannot eat into."""
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            land = {}
            for room in layout.rooms:
                at = _abs_tiles(room)
                land[room.id] = {at(p) for p, c in room.grid.items()
                                 if c.kind in WALKABLE_KINDS}
            ids = sorted(land)
            self.assertGreater(len(ids), 1)
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    shared = land[a] & land[b]
                    self.assertEqual(shared, set(),
                                     f"seed {seed}: rooms {a} and {b} share "
                                     f"{len(shared)} land cells")

    def test_the_coast_leaves_its_guaranteed_void_band(self):
        keep = config.HEIGHTMAP_COAST_KEEP
        if not keep:
            self.skipTest("no void band configured")
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            for room in layout.rooms:
                if not room.grid:
                    continue
                w, h = room.tile_dims
                land = [p for p, c in room.grid.items()
                        if c.kind in WALKABLE_KINDS]
                self.assertGreaterEqual(min(p[0] for p in land), keep)
                self.assertGreaterEqual(min(p[1] for p in land), keep)
                self.assertGreaterEqual(w - 1 - max(p[0] for p in land), keep - 1)
                self.assertGreaterEqual(h - 1 - max(p[1] for p in land), keep - 1)


class CanCrossTests(unittest.TestCase):
    def test_matches_walk_links_within_every_room(self):
        """The world-space rule and the generator's own rule agree cell for
        cell. Restricted to the room's own tiles: `can_cross` also finds
        room-to-bridge links, which `walk_links` cannot see because a bridge
        belongs to no room's grid."""
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            checked = 0
            for room in layout.rooms:
                at = _abs_tiles(room)
                own = {at(p) for p in room.grid}
                for pos, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    a = at(pos)
                    want = {at(p) for p in walk_links(room.grid, pos)}
                    got = {(a[0] + dc, a[1] + dr)
                           for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1))
                           if can_cross(ix, a, (a[0] + dc, a[1] + dr))}
                    self.assertEqual(got & own, want, f"seed {seed} at {pos}")
                    checked += 1
            self.assertGreater(checked, 1000)

    def test_a_level_change_needs_a_flight(self):
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            changes = flights = 0
            for row in range(ix.rows):
                for col in range(ix.cols):
                    a = (col, row)
                    if ix.kind_at(*a) != GROUND:
                        continue
                    for dc, dr in ((1, 0), (0, 1)):
                        b = (col + dc, row + dr)
                        if ix.kind_at(*b) != GROUND:
                            continue
                        if ix.level_at(*a) == ix.level_at(*b):
                            continue
                        changes += 1
                        # ground to ground across a drop is never a step
                        self.assertFalse(can_cross(ix, a, b),
                                         f"seed {seed}: {a}->{b} crosses a drop")
                    if ix.flight_at(*a) is not None:
                        flights += 1
            self.assertGreater(changes, 50, f"seed {seed}: no drops to test")

    def test_a_diagonal_cannot_cut_the_corner_of_a_drop(self):
        """`can_step` composes a diagonal from its right-angle detours, so a
        diagonal is open only where at least one of them is."""
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            for row in range(ix.rows):
                for col in range(ix.cols):
                    a = (col, row)
                    if not ix.has_surface(*a):
                        continue
                    for dc, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                        b = (col + dc, row + dr)
                        if not ix.has_surface(*b):
                            continue
                        h = (col + dc, row)
                        v = (col, row + dr)
                        legs = ((can_cross(ix, a, h) and can_cross(ix, h, b))
                                or (can_cross(ix, a, v) and can_cross(ix, v, b)))
                        self.assertEqual(can_step(ix, a, b), legs)


class ColliderTests(unittest.TestCase):
    def test_movement_matches_the_rule_on_every_adjacent_pair(self):
        """`resolve_movement`'s gate and `can_cross` never disagree. A pair may
        still be refused for a reason that is not elevation -- an obstacle on
        the destination -- so those are excluded by asking the plain floor test
        first."""
        for seed in SEEDS:
            layout, gm, ix = _world(seed)
            pairs = 0
            for row in range(ix.rows):
                for col in range(ix.cols):
                    a = (col, row)
                    if not ix.has_surface(*a):
                        continue
                    pa = _centre(ix, a)
                    if not gm._point_ok(pa.x, pa.y):
                        continue
                    for dc, dr in ((1, 0), (0, 1)):
                        b = (col + dc, row + dr)
                        if not ix.has_surface(*b):
                            continue
                        pb = _centre(ix, b)
                        if not gm.is_walkable(pb, 0.0):
                            continue            # obstacle / not floor
                        self.assertEqual(gm.is_walkable(pb, 0.0, frm=pa),
                                         can_cross(ix, a, b),
                                         f"seed {seed}: {a}->{b}")
                        pairs += 1
            self.assertGreater(pairs, 1000)

    def test_a_lunge_cannot_vault_a_cliff(self):
        """A charger resolves straight to the player's position, many tiles at
        once. The segment is walked, so a drop anywhere along it refuses the
        move -- an endpoint-only test would let it through."""
        for seed in SEEDS:
            layout, gm, ix = _world(seed)
            tried = 0
            for row in range(1, ix.rows - 1):
                for col in range(1, ix.cols - 4):
                    a = (col, row)
                    if ix.kind_at(*a) != GROUND:
                        continue
                    lv = ix.level_at(*a)
                    for d in (2, 3, 4):
                        b = (col + d, row)
                        span = [(col + k, row) for k in range(1, d + 1)]
                        if any(ix.kind_at(*t) != GROUND for t in span):
                            continue
                        if all(ix.level_at(*t) == lv for t in span):
                            continue
                        self.assertFalse(
                            gm.is_walkable(_centre(ix, b), 0.0,
                                           frm=_centre(ix, a)),
                            f"seed {seed}: lunge {a}->{b} vaulted a drop")
                        tried += 1
            self.assertGreater(tried, 100, f"seed {seed}: no lunges to test")

    def test_every_flight_is_walkable_head_to_foot(self):
        """The rule must not seal the routes it exists to protect.

        The entry tile comes from `walk_links`, not from "north of the head":
        a straight flight is entered from the terrace above it, but an
        east/west flight is entered from the *side*, because the wall jogs a
        row across it. Assuming the former walks a body into a cliff face."""
        for seed in SEEDS:
            layout, gm, ix = _world(seed)
            walked = 0
            for room in layout.rooms:
                at = _abs_tiles(room)
                grid = room.grid
                for pos, cell in grid.items():
                    if cell.kind not in (VSTAIR, EWSTAIR) or cell.row != 0:
                        continue
                    span = cell.drop if cell.kind == VSTAIR else cell.drop + 1
                    foot = (pos[0], pos[1] + span - 1)
                    entry = [p for p in walk_links(grid, pos)
                             if grid[p].kind == GROUND]
                    exits = [p for p in walk_links(grid, foot)
                             if grid[p].kind == GROUND]
                    self.assertTrue(entry and exits,
                                    f"seed {seed}: flight at {pos} has no landing")
                    route = ([entry[0]]
                             + [(pos[0], pos[1] + k) for k in range(span)]
                             + [exits[0]])
                    p = _centre(ix, at(route[0]))
                    for step_tile in route[1:]:
                        tgt = _centre(ix, at(step_tile))
                        for _ in range(12):
                            d = tgt - p
                            nxt = p + d.normalize() * 8 if d.length() > 8 else tgt
                            moved = gm.resolve_movement(p, nxt, 0.0)
                            self.assertGreater(
                                (moved - p).length(), 0.5,
                                f"seed {seed}: stuck at {step_tile} "
                                f"on the {cell.kind} at {pos}")
                            p = moved
                            if (p - tgt).length() <= 8:
                                break
                    walked += 1
            self.assertGreater(walked, 5, f"seed {seed}: no flights")


class NavTests(unittest.TestCase):
    def test_step_mask_matches_the_rule(self):
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            ng = NavGrid(layout, layout.obstacles)
            ix = ng.levels
            half = ng.cell * 0.5
            ox, oy = ng.origin
            edges = 0
            for row in range(ng.rows):
                for col in range(ng.cols):
                    i = row * ng.cols + col
                    if not ng.walkable[i]:
                        continue
                    t = ix.tile_of(ox + col * ng.cell + half,
                                   oy + row * ng.cell + half)
                    for k, (dc, dr) in enumerate(NAV_DIRS):
                        nc, nr = col + dc, row + dr
                        if not (0 <= nc < ng.cols and 0 <= nr < ng.rows):
                            continue
                        if not ng.walkable[nr * ng.cols + nc]:
                            continue
                        nt = ix.tile_of(ox + nc * ng.cell + half,
                                        oy + nr * ng.cell + half)
                        want = True if nt == t else can_step(ix, t, nt)
                        self.assertEqual(bool(ng.step_mask[i] & (1 << k)), want)
                        edges += 1
            self.assertGreater(edges, 10000)

    def test_flight_cells_get_corridor_leniency(self):
        """A flight is one tile wide with stone either side; without the M3
        leniency the large nav class cannot thread one."""
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            ng = NavGrid(layout, layout.obstacles)
            n = 0
            for i, f in enumerate(ng.flight):
                if f:
                    self.assertTrue(ng.corridor[i])
                    n += 1
            self.assertGreater(n, 20, f"seed {seed}: no flight cells")

    def test_the_field_reaches_exactly_what_the_rule_allows(self):
        """The fill's reachable set is a BFS over the same mask -- no cell is
        reached by a route the terrain forbids, and none is missed."""
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            ng = NavGrid(layout, layout.obstacles)
            ff = FlowField(ng)
            room = max(layout.rooms, key=lambda r: len(r.grid or {}))
            ff.rebuild(pygame.Vector2(room.center))
            self.assertTrue(ff.reachable)
            cols, rows = ng.cols, ng.rows
            trav = ff._trav
            si = ff.target_cell[1] * cols + ff.target_cell[0]
            seen = {si}
            stack = [si]
            while stack:
                u = stack.pop()
                uc, ur = u % cols, u // cols
                m = ng.step_mask[u]
                for k, (dc, dr) in enumerate(NAV_DIRS):
                    if not (m & (1 << k)):
                        continue
                    nc, nr = uc + dc, ur + dr
                    if not (0 <= nc < cols and 0 <= nr < rows):
                        continue
                    v = nr * cols + nc
                    if v in seen or not trav[v]:
                        continue
                    if dc and dr and (not trav[ur * cols + nc]
                                      or not trav[nr * cols + uc]):
                        continue
                    seen.add(v)
                    stack.append(v)
            field = {i for i in range(cols * rows) if ff.cost[i] < _INF}
            self.assertEqual(field, seen, f"seed {seed}")

    def test_the_field_reaches_every_cell_generation_says_is_connected(self):
        """End to end: `heightmap.reachable` is the generator's own answer to
        "what is joined to what", and `check_grid` validates every room against
        it. If the flow field misses a cell it says is connected, nav and
        generation have drifted -- which is the failure this whole phase exists
        to make impossible.

        Cells the field cannot reach for a reason that is not elevation (a nav
        cell centre off floor, clearance too tight, an obstacle) are excluded,
        so the assertion is about the level rule alone."""
        px = config.TILE_PX
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            ng = NavGrid(layout, layout.obstacles)
            ff = FlowField(ng)
            ix = ng.levels
            total = 0
            for room in layout.rooms:
                if not room.grid:
                    continue
                at = _abs_tiles(room)
                ff.rebuild(pygame.Vector2(room.center))
                for p in reachable(room.grid):
                    w = _centre(ix, at(p))
                    col, row = ng.cell_of(w.x, w.y)
                    i = row * ng.cols + col
                    if not ng.walkable[i] or not ff._trav[i]:
                        continue
                    self.assertLess(ff.cost[i], _INF,
                                    f"seed {seed} room {room.id}: {p} is "
                                    f"connected but the field never reached it")
                    total += 1
            self.assertGreater(total, 2000, f"seed {seed}: too little covered")

    def test_a_chase_up_a_terrace_goes_through_a_flight(self):
        """The point of the whole phase: an enemy at sea level chasing a player
        on a plateau walks to a staircase instead of through the cliff."""
        px = config.TILE_PX
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            ng = NavGrid(layout, layout.obstacles)
            ff = FlowField(ng)
            ix = ng.levels
            climbs = 0
            for room in layout.rooms:
                at = _abs_tiles(room)
                ups = [at(p) for p, c in room.grid.items()
                       if c.kind == GROUND and c.level > 0]
                lows = [at(p) for p, c in room.grid.items()
                        if c.kind == GROUND and c.level == 0]
                if not ups or not lows:
                    continue
                tgt = max(ups, key=lambda t: ix.level_at(*t))
                wt = _centre(ix, tgt)
                ff.rebuild(wt)
                start = max(lows, key=lambda t: (t[0] - tgt[0]) ** 2
                            + (t[1] - tgt[1]) ** 2)
                ws = _centre(ix, start)
                if not 0 < ff.cost_at(ws) < _INF:
                    continue
                pos = pygame.Vector2(ws)
                via = False
                for _ in range(4000):
                    d = ff.direction_at(pos)
                    if d.length_squared() < 1e-9:
                        break
                    pos += d * 12.0
                    if ix.flight_at(*ix.tile_of(pos.x, pos.y)) is not None:
                        via = True
                    if (pos - wt).length() < px:
                        break
                else:
                    self.fail(f"seed {seed}: chase never terminated")
                self.assertLess((pos - wt).length(), px,
                                f"seed {seed}: chase stalled short of the top")
                self.assertTrue(via, f"seed {seed}: reached the top without a flight")
                climbs += 1
            self.assertGreater(climbs, 0, f"seed {seed}: no terraced room")


class ScatterTests(unittest.TestCase):
    def test_no_obstacle_sits_on_a_flight_or_its_landings(self):
        from world.gen.scatter import _flight_keepouts
        for seed in SEEDS:
            layout, _gm, _ix = _world(seed)
            keep = _flight_keepouts(layout.rooms)
            self.assertGreater(len(keep), 20, f"seed {seed}: nothing protected")
            for o in layout.obstacles:
                for k in keep:
                    self.assertFalse(k.collidepoint(o.pos.x, o.pos.y),
                                     f"seed {seed}: {o.kind} blocks a flight")

    def test_both_nav_classes_can_use_every_flight(self):
        for seed in SEEDS:
            layout, _gm, ix = _world(seed)
            nf = NavField(layout, layout.obstacles)
            for cls, clearance in (("small", 16.0), ("large", 22.0)):
                ff = nf.fields[cls]
                checked = 0
                for room in layout.rooms:
                    at = _abs_tiles(room)
                    for pos, cell in room.grid.items():
                        if cell.kind not in (VSTAIR, EWSTAIR) or cell.row != 0:
                            continue
                        head = [p for p in walk_links(room.grid, pos)
                                if room.grid[p].kind == GROUND]
                        foot_row = pos[1] + (cell.drop - 1
                                             if cell.kind == VSTAIR else cell.drop)
                        foot = [p for p in walk_links(room.grid,
                                                      (pos[0], foot_row))
                                if room.grid[p].kind == GROUND]
                        if not head or not foot:
                            continue
                        ff.rebuild(_centre(ix, at(head[0])),
                                   min_clearance=clearance)
                        self.assertTrue(
                            any(0 <= ff.cost_at(_centre(ix, at(f))) < _INF
                                for f in foot),
                            f"seed {seed} {cls}: flight at {pos} is sealed")
                        checked += 1
                self.assertGreater(checked, 5, f"seed {seed} {cls}: no flights")


if __name__ == "__main__":
    unittest.main()
