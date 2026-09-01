"""M1 -- the static navigation grid (`world/pathfinding.NavGrid`).

Covers: the walkable mask matches the map geometry exactly; clearance is 0 on
blocked / obstacle cells and grows into open floor; `passable(r)` never
out-runs `GameMap.is_walkable(center, r)` at enemy radii; corridor cells are
flagged; a normal-size enemy can route start -> boss; one-tile corridors need
the M3 clearance leniency for the big rare enemies; deterministic; fast to build.
"""
import time
import unittest
from collections import deque

import pygame

from game import config
from world.map import GameMap
from world.pathfinding import NavGrid, FlowField, _CLEARANCE_CAP, _INF
from world.procedural import generate_world


SEEDS = (1, 3, 7, 42, 99)

# These validate the nav algorithm against the flat base layout on pinned seeds;
# LD-1 verticality changes the RNG stream and adds cliffs/stairs, and gets its
# own routing coverage in tests/world/test_verticality.py.
_SAVED_VERT = None


# LD-9: this module covers the **LD-8 world model** -- grown room shapes,
# corridors, cliff bands, one `floor` per room. `config.HEIGHTMAP_ROOMS`
# defaults on now and selects a different generator entirely, whose rooms are
# height maps with overlapping bounding rects and no cliff band. Pin the flag
# off here so this coverage keeps testing the path it was written for; the
# height-map path has its own in `tests/world/test_elevation.py`.
_SAVED_HEIGHTMAP = None


def _pin_heightmap_off():
    global _SAVED_HEIGHTMAP
    _SAVED_HEIGHTMAP = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = False


def _restore_heightmap():
    config.HEIGHTMAP_ROOMS = _SAVED_HEIGHTMAP


def setUpModule():
    _pin_heightmap_off()
    global _SAVED_VERT
    _SAVED_VERT = config.WORLD_VERTICALITY
    config.WORLD_VERTICALITY = False


def tearDownModule():
    _restore_heightmap()
    config.WORLD_VERTICALITY = _SAVED_VERT


def _grid(seed, cell=32):
    w = generate_world(seed)
    return w, GameMap(seed=seed), NavGrid(w, w.obstacles, cell)


def _bfs_reaches(ng, start, goal, radius, corridor_lenient=False):
    seen = {start}
    q = deque([start])
    while q:
        c, r = q.popleft()
        if (c, r) == goal:
            return True
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                nxt = (c + dc, r + dr)
                if nxt in seen:
                    continue
                ok = ng.passable(nxt[0], nxt[1], radius) or (
                    corridor_lenient and ng.is_corridor(*nxt))
                if ok:
                    seen.add(nxt)
                    q.append(nxt)
    return False


class NavGridGeometryTests(unittest.TestCase):
    def test_walkable_mask_matches_map_point_geometry_exactly(self):
        for seed in SEEDS:
            _w, gm, ng = _grid(seed)
            mismatch = sum(
                1 for i in range(ng.cols * ng.rows)
                if bool(ng.walkable[i]) != gm._point_ok(
                    *ng.world_of(i % ng.cols, i // ng.cols)))
            self.assertEqual(mismatch, 0, f"seed {seed}: {mismatch} cells")

    def test_world_cell_roundtrip(self):
        _w, _gm, ng = _grid(3)
        for c in range(0, ng.cols, 5):
            for r in range(0, ng.rows, 5):
                self.assertEqual(ng.cell_of(*ng.world_of(c, r)), (c, r))

    def test_out_of_bounds_queries_are_safe(self):
        _w, _gm, ng = _grid(3)
        self.assertFalse(ng.in_bounds(-1, 0))
        self.assertFalse(ng.in_bounds(ng.cols, 0))
        self.assertFalse(ng.passable(-1, -1, 8))
        self.assertFalse(ng.passable(ng.cols + 4, ng.rows + 4, 8))
        self.assertEqual(ng.clearance_at(-1, -1), 0.0)

    def test_rejects_a_non_positive_cell_size(self):
        w = generate_world(1)
        with self.assertRaises(ValueError):
            NavGrid(w, w.obstacles, 0)


class NavGridClearanceTests(unittest.TestCase):
    def test_blocked_cells_are_zero_open_floor_is_wide(self):
        for seed in SEEDS:
            _w, _gm, ng = _grid(seed)
            wide = 0
            for i in range(ng.cols * ng.rows):
                if ng.walkable[i]:
                    self.assertGreaterEqual(ng.clearance[i], 0.0)
                    self.assertLessEqual(ng.clearance[i], _CLEARANCE_CAP)
                    if ng.clearance[i] >= 2 * ng.cell:
                        wide += 1
                else:
                    self.assertEqual(ng.clearance[i], 0.0)
            self.assertGreater(wide, 50, f"seed {seed}: no open interior")

    def test_no_cell_inside_an_obstacle_disc_is_passable(self):
        for seed in SEEDS:
            w, _gm, ng = _grid(seed)
            for o in w.obstacles:
                rad = o.radius
                c0, r0 = ng.cell_of(o.pos.x - rad, o.pos.y - rad)
                c1, r1 = ng.cell_of(o.pos.x + rad, o.pos.y + rad)
                for c in range(c0, c1 + 1):
                    for r in range(r0, r1 + 1):
                        p = ng.world_of(c, r)
                        if (p.x - o.pos.x) ** 2 + (p.y - o.pos.y) ** 2 <= rad * rad:
                            self.assertFalse(ng.passable(c, r, 1.0),
                                             f"seed {seed}: cell in {o.kind}")

    def test_passable_never_out_runs_is_walkable_at_enemy_radii(self):
        for seed in SEEDS:
            _w, gm, ng = _grid(seed)
            n = ng.cols * ng.rows
            for radius, max_permissive, max_conservative in ((14, 0.05, 0.0),
                                                             (24, 0.0, 0.05)):
                permissive = conservative = 0
                for i in range(n):
                    c, r = i % ng.cols, i // ng.cols
                    p = ng.world_of(c, r)
                    nav = ng.passable(c, r, radius)
                    real = gm.is_walkable(p, radius)
                    if nav and not real:
                        permissive += 1
                    elif real and not nav:
                        conservative += 1
                self.assertLessEqual(permissive / n, max_permissive,
                                     f"seed {seed} r{radius}: too permissive")
                self.assertLessEqual(conservative / n, max_conservative,
                                     f"seed {seed} r{radius}: too conservative")


class NavGridCorridorTests(unittest.TestCase):
    def test_corridor_cells_are_flagged_walkable_and_inside_a_corridor_rect(self):
        for seed in SEEDS:
            w, _gm, ng = _grid(seed)
            flagged = 0
            for i in range(ng.cols * ng.rows):
                if not ng.corridor[i]:
                    continue
                flagged += 1
                self.assertTrue(ng.walkable[i])
                p = ng.world_of(i % ng.cols, i // ng.cols)
                self.assertTrue(any(cr.rect.collidepoint(p.x, p.y)
                                    for cr in w.corridors))
            self.assertGreater(flagged, 0, f"seed {seed}: no corridor cells")

    def test_a_normal_enemy_can_route_start_to_boss(self):
        for seed in SEEDS:
            w, _gm, ng = _grid(seed)
            start = ng.cell_of(*w.room(w.start_id).center)
            goal = ng.cell_of(*w.room(w.boss_id).center)
            self.assertTrue(_bfs_reaches(ng, start, goal, 14),
                            f"seed {seed}: r14 cannot reach the boss room")

    def test_one_tile_corridors_need_leniency_for_the_big_enemies(self):
        # documents the M3 requirement: a 64 px corridor is 2 cells wide, so no
        # cell centre clears radius 24 -- routing the rare big enemies needs the
        # corridor flag, not just clearance.
        w, _gm, ng = _grid(3)
        start = ng.cell_of(*w.room(w.start_id).center)
        goal = ng.cell_of(*w.room(w.boss_id).center)
        self.assertFalse(_bfs_reaches(ng, start, goal, 24))
        self.assertTrue(_bfs_reaches(ng, start, goal, 24, corridor_lenient=True))


def _follow(ff, ng, start_world, max_steps=4000):
    """Walk the flow field from `start_world`, one ~cell hop per step. Returns
    the list of (point, cost) visited, ending at a zero-vector cell."""
    p = pygame.Vector2(start_world)
    out = [(pygame.Vector2(p), ff.cost_at(p))]
    for _ in range(max_steps):
        d = ff.direction_at(p)
        if d.length_squared() < 1e-9:
            break
        p = p + d * (ng.cell * 0.9)
        out.append((pygame.Vector2(p), ff.cost_at(p)))
    return out


class FlowFieldTests(unittest.TestCase):
    def _field(self, seed, target=None, min_clearance=14.0, lenient=True, cell=32):
        w = generate_world(seed)
        ng = NavGrid(w, w.obstacles, cell)
        ff = FlowField(ng)
        tgt = target if target is not None else w.room(w.start_id).center
        ff.rebuild((tgt.x, tgt.y), min_clearance, lenient)
        return w, ng, ff, pygame.Vector2(tgt.x, tgt.y)

    def test_every_cell_has_a_strictly_downhill_neighbour(self):
        # the field-level invariant M4 relies on: from any reachable non-target
        # cell at least one traversable neighbour has strictly lower cost.
        # LD-9 D4: the neighbour must also be one the terrain allows -- a cell
        # across a drop can be downhill and still be no way out, because the
        # fill reached it the long way round. `direction_at` gates on the same
        # mask, so an ungated invariant would no longer be the one M4 needs.
        for seed in SEEDS:
            _w, ng, ff, _t = self._field(seed)
            cols, rows = ng.cols, ng.rows
            for i in range(cols * rows):
                ci = ff.cost[i]
                if ci >= _INF or ci == 0:
                    continue
                col, row = i % cols, i // cols
                mask = ng.step_mask[i]
                best = min((ff.cost[ng.idx(col + dc, row + dr)]
                            for dc, dr, _w, bit in ff._NEI
                            if (mask & bit) and ng.in_bounds(col + dc, row + dr)),
                           default=_INF)
                self.assertLess(best, ci, f"seed {seed}: local min at {(col, row)}")

    def test_gradient_walk_trends_down_and_reaches_the_target(self):
        for seed in SEEDS:
            w, ng, ff, tgt = self._field(seed)
            cand = [w.room(w.boss_id).center] + [r.center for r in w.rooms[:6]]
            starts = [s for s in cand
                      if 0 < ff.cost_at(pygame.Vector2(s)) < _INF]
            self.assertGreater(len(starts), 1, f"seed {seed}: no walkable start")
            for s in starts:
                walk = _follow(ff, ng, s)
                costs = [c for _p, c in walk if c < _INF]
                self.assertGreater(len(costs), 1)
                # discrete-cell sampling of a smooth walk can nudge up by up to a
                # step when clipping a corner, but never more, and the trend is
                # firmly down.
                for a, b in zip(costs, costs[1:]):
                    self.assertLessEqual(b, a + ff._w_diag + 1,
                                         f"seed {seed}: cost jumped up")
                self.assertLess(costs[-1], costs[0] * 0.2 + ff._w_diag)
                self.assertLess(walk[-1][0].distance_to(tgt), ng.cell * 1.5,
                                f"seed {seed}: walk did not reach the target")

    def test_field_covers_the_whole_world_including_off_screen(self):
        for seed in SEEDS:
            w, ng, ff, _tgt = self._field(seed)  # target in the start room
            bc = ng.cell_of(*w.room(w.boss_id).center)
            self.assertLess(ff.cost[ng.idx(*bc)], _INF,
                            f"seed {seed}: boss room never reached")

    def test_respects_min_clearance(self):
        w = generate_world(3)
        ng = NavGrid(w, w.obstacles, 32)
        tgt = w.room(w.start_id).center
        strict = FlowField(ng)
        strict.rebuild((tgt.x, tgt.y), 22.0, corridor_lenient=False)
        for i in range(ng.cols * ng.rows):
            if strict.cost[i] < _INF:
                self.assertGreaterEqual(ng.clearance[i], 22.0)
        lenient = FlowField(ng)
        lenient.rebuild((tgt.x, tgt.y), 22.0, corridor_lenient=True)
        for i in range(ng.cols * ng.rows):
            if lenient.cost[i] < _INF:
                self.assertTrue(ng.clearance[i] >= 22.0 or ng.corridor[i])

    def test_zero_vector_before_rebuild_and_off_the_field(self):
        w = generate_world(1)
        ng = NavGrid(w, w.obstacles, 32)
        ff = FlowField(ng)
        self.assertEqual(ff.direction_at(w.room(w.start_id).center),
                         pygame.Vector2())
        ff.rebuild(tuple(w.room(w.start_id).center), 14.0)
        void = pygame.Vector2(ng.origin[0] + 2, ng.origin[1] + 2)  # bounds corner
        self.assertEqual(ff.direction_at(void), pygame.Vector2())

    def test_target_deep_in_the_void_reports_unreachable_or_snaps_to_floor(self):
        w = generate_world(7)
        ng = NavGrid(w, w.obstacles, 32)
        ff = FlowField(ng)
        ff.rebuild((ng.origin[0] + 4, ng.origin[1] + 4), 14.0)
        if ff.reachable:
            self.assertTrue(ng.is_floor(*ff.target_cell))
        else:
            self.assertEqual(ff.direction_at(w.room(w.start_id).center),
                             pygame.Vector2())

    def test_deterministic(self):
        w = generate_world(11)
        ng = NavGrid(w, w.obstacles, 32)
        tgt = tuple(w.room(w.start_id).center)
        a, b = FlowField(ng), FlowField(ng)
        a.rebuild(tgt, 14.0)
        b.rebuild(tgt, 14.0)
        self.assertEqual(a.cost.tobytes(), b.cost.tobytes())
        for r in w.rooms:
            va = a.direction_at(r.center)
            vb = b.direction_at(r.center)
            self.assertAlmostEqual(va.x, vb.x)
            self.assertAlmostEqual(va.y, vb.y)

    def test_relaxation_cap_is_not_hit_on_a_normal_world(self):
        for seed in SEEDS:
            _w, _ng, ff, _t = self._field(seed)
            self.assertTrue(ff.reachable)
            self.assertLess(ff.relaxations, ff.relax_cap)

    def test_followed_route_stays_on_navigable_ground(self):
        for seed in SEEDS:
            w, ng, ff, _t = self._field(seed)
            for pt, _c in _follow(ff, ng, w.room(w.boss_id).center):
                c, r = ng.cell_of(pt.x, pt.y)
                self.assertTrue(ng.passable(c, r, 14) or ng.is_corridor(c, r),
                                f"seed {seed}: route left the floor at {pt}")

    def test_big_enemy_needs_corridor_leniency_to_leave_a_room(self):
        w = generate_world(3)
        ng = NavGrid(w, w.obstacles, 32)
        tgt = tuple(w.room(w.start_id).center)
        bc = ng.idx(*ng.cell_of(*w.room(w.boss_id).center))
        strict = FlowField(ng)
        strict.rebuild(tgt, 24.0, corridor_lenient=False)
        self.assertEqual(strict.cost[bc], _INF)
        lenient = FlowField(ng)
        lenient.rebuild(tgt, 24.0, corridor_lenient=True)
        self.assertLess(lenient.cost[bc], _INF)


class FlowFieldEscapeTests(unittest.TestCase):
    """`steer_at` -- gradient on a reached cell, else a bearing to the nearest
    reached cell so an enemy on a too-tight pocket does not beeline blindly."""

    def _field(self, seed=3):
        w = generate_world(seed)
        ng = NavGrid(w, w.obstacles, 32)
        ff = FlowField(ng)
        ff.rebuild(tuple(w.room(w.start_id).center), 14.0)
        return w, ng, ff

    def _unreached_floor_cell_by_the_field(self, ng, ff):
        cols = ng.cols
        for i in range(cols * ng.rows):
            if not ng.walkable[i] or ff.cost[i] < _INF:
                continue
            c, r = i % cols, i // cols
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if dc == dr == 0:
                        continue
                    nc, nr = c + dc, r + dr
                    if (0 <= nc < cols and 0 <= nr < ng.rows
                            and ng.walkable[nr * cols + nc]
                            and ff.cost[nr * cols + nc] < _INF):
                        return (c, r)
        return None

    def test_steer_matches_the_gradient_on_reached_cells(self):
        for seed in SEEDS:
            _w, ng, ff = self._field(seed)
            checked = 0
            for i in range(0, ng.cols * ng.rows, 7):
                if ff.cost[i] >= _INF or ff.cost[i] == 0:
                    continue
                p = ng.world_of(i % ng.cols, i // ng.cols)
                self.assertEqual(ff.steer_at(p), ff.direction_at(p))
                checked += 1
            self.assertGreater(checked, 20)

    def test_steer_escapes_a_too_tight_cell_toward_the_field(self):
        w, ng, ff = self._field(3)
        cell = self._unreached_floor_cell_by_the_field(ng, ff)
        self.assertIsNotNone(cell, "no unreached floor cell to test")
        p = ng.world_of(*cell)
        self.assertEqual(ff.direction_at(p), pygame.Vector2())   # gradient has nothing
        d = ff.steer_at(p)
        self.assertGreater(d.length(), 0.5)                      # but steer does
        # it points at a genuinely reached neighbour
        cols = ng.cols
        best = min(((ff.cost[(cell[1] + dr) * cols + cell[0] + dc], (dc, dr))
                    for dc in (-1, 0, 1) for dr in (-1, 0, 1)
                    if not (dc == dr == 0)
                    and 0 <= cell[0] + dc < cols and 0 <= cell[1] + dr < ng.rows),
                   default=(_INF, (0, 0)))
        toward = pygame.Vector2(best[1])
        self.assertGreater(d.dot(toward.normalize()), 0.0)

    def test_steer_is_zero_on_the_target_and_deep_in_the_void(self):
        w, ng, ff = self._field(7)
        self.assertEqual(ff.steer_at(pygame.Vector2(w.room(w.start_id).center)),
                         pygame.Vector2())
        void = pygame.Vector2(ng.origin[0] + 2, ng.origin[1] + 2)
        self.assertEqual(ff.steer_at(void), pygame.Vector2())

    def test_steer_is_deterministic(self):
        w = generate_world(9)
        ng = NavGrid(w, w.obstacles, 32)
        a, b = FlowField(ng), FlowField(ng)
        t = tuple(w.room(w.start_id).center)
        a.rebuild(t, 14.0)
        b.rebuild(t, 14.0)
        cell = self._unreached_floor_cell_by_the_field(ng, a)
        if cell is not None:
            self.assertEqual(a.steer_at(ng.world_of(*cell)),
                             b.steer_at(ng.world_of(*cell)))


class NavGridBuildTests(unittest.TestCase):
    def test_deterministic(self):
        for seed in (2, 11, 30):
            w = generate_world(seed)
            a = NavGrid(w, w.obstacles, 32)
            b = NavGrid(w, w.obstacles, 32)
            self.assertEqual(bytes(a.walkable), bytes(b.walkable))
            self.assertEqual(bytes(a.corridor), bytes(b.corridor))
            self.assertEqual(a.clearance.tobytes(), b.clearance.tobytes())

    def test_build_is_fast_enough(self):
        for seed in (1, 7, 42):
            w = generate_world(seed)
            t = time.perf_counter()
            NavGrid(w, w.obstacles, 32)
            self.assertLess(time.perf_counter() - t, 1.5)

    def test_dual_grid_sizes_both_build(self):
        w = generate_world(5)
        small = NavGrid(w, w.obstacles, 32)
        big = NavGrid(w, w.obstacles, 48)
        self.assertLess(big.cols, small.cols)
        self.assertGreater(sum(big.walkable), 0)


if __name__ == "__main__":
    unittest.main()
