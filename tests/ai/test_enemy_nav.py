"""M3/M6 -- the dual-resolution `NavField` coordinator, its PlayingState wiring,
the staggered per-grid rebuild, and the debug-overlay counter.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game
from game.states.playing_state import PlayingState
from world.pathfinding import NavField, _INF
from world.procedural import generate_world


class NavFieldTests(unittest.TestCase):
    def _nf(self, seed=3):
        w = generate_world(seed)
        return w, NavField(w, w.obstacles)

    def test_builds_one_grid_and_field_per_class(self):
        _w, nf = self._nf()
        self.assertEqual(set(nf.grids), {"small", "large"})
        self.assertEqual(set(nf.fields), {"small", "large"})
        self.assertEqual(nf.grids["small"].cell, 32)
        self.assertEqual(nf.grids["large"].cell, 48)

    def test_class_selection_is_by_radius_ceiling(self):
        _w, nf = self._nf()
        self.assertEqual(nf._class_for(7), "small")
        self.assertEqual(nf._class_for(16), "small")
        self.assertEqual(nf._class_for(16.1), "large")
        self.assertEqual(nf._class_for(30), "large")

    def test_rebuild_reaches_across_the_world_for_both_classes(self):
        w, nf = self._nf()
        nf.rebuild(w.room(w.start_id).center)
        self.assertTrue(nf.reachable)
        far = pygame.Vector2(w.room(w.boss_id).center)
        for radius in (12, 24):
            self.assertLess(nf.cost(far, radius), _INF)
            self.assertGreater(nf.direction(far, radius).length(), 0.5)

    def test_target_cell_change_detection(self):
        w, nf = self._nf()
        p = pygame.Vector2(w.room(w.start_id).center)
        nf.rebuild(p)
        self.assertFalse(nf.target_cell_changed(p + pygame.Vector2(2, 0)))
        self.assertTrue(nf.target_cell_changed(p + pygame.Vector2(96, 96)))

    def test_deterministic(self):
        w = generate_world(9)
        a, b = NavField(w, w.obstacles), NavField(w, w.obstacles)
        t = w.room(w.start_id).center
        a.rebuild(t)
        b.rebuild(t)
        for name in a.fields:
            self.assertEqual(a.fields[name].cost.tobytes(),
                             b.fields[name].cost.tobytes())


def _playing(seed, flag):
    old = config.ENEMY_PATHFINDING
    config.ENEMY_PATHFINDING = flag
    try:
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        p = PlayingState(g)
        p.enter(seed=seed)
    finally:
        config.ENEMY_PATHFINDING = old
    return g, p


class PlayingStateNavWiringTests(unittest.TestCase):
    def test_flag_off_has_no_nav_object_and_zero_steering(self):
        _g, p = _playing(1234, False)
        self.assertIsNone(p._nav)
        self.assertEqual(p._nav_dir(p.player.pos + pygame.Vector2(300, 0), 14),
                         pygame.Vector2())
        self.assertEqual(p._enemy_context(0.1).nav_dir(p.player.pos, 14),
                         pygame.Vector2())

    def test_flag_on_builds_a_ready_navfield(self):
        _g, p = _playing(1234, True)
        self.assertIsInstance(p._nav, NavField)
        self.assertTrue(p._nav.reachable)
        self.assertGreater(p._nav_t, 0.0)

    def test_steering_from_elsewhere_points_toward_the_player(self):
        _g, p = _playing(1234, True)
        for off in (pygame.Vector2(0, 220), pygame.Vector2(200, 0),
                    pygame.Vector2(-180, 120)):
            probe = p.player.pos + off
            d = p._nav_dir(probe, 14)
            if d.length_squared() < 1e-6:
                continue
            self.assertGreater(d.dot((p.player.pos - probe).normalize()), 0.0)
            return
        self.skipTest("no probe landed on the field for this seed")

    def test_update_nav_repaths_when_the_player_leaves_the_cell(self):
        _g, p = _playing(1234, True)
        before = p._nav._target_cell
        p.player.pos = p.player.pos + pygame.Vector2(600, 0)
        p._nav_t = 5.0                       # interval not due -> the cell trigger fires
        p._update_nav(1 / 120)
        self.assertNotEqual(p._nav._target_cell, before)

    def test_path_chase_is_wired_and_moves_a_chaser_toward_the_player(self):
        _g, p = _playing(1234, True)
        spot = next(
            (p.player.pos + pygame.Vector2(dx, dy)
             for dist in (160, 220, 300)
             for dx, dy in ((dist, 0), (-dist, 0), (0, dist), (0, -dist))
             if p.game_map.is_walkable(p.player.pos + pygame.Vector2(dx, dy), 14)),
            None)
        self.assertIsNotNone(spot, "no walkable spawn near the player")
        p._spawn_enemy("chaser", at=spot)
        e = p.enemies[-1]
        self.assertEqual(e.behavior, "path_chase_attack")
        ctx = p._enemy_context(1 / 60)
        start = e.pos.distance_to(p.player.pos)
        for _ in range(90):
            e.update(ctx)
        self.assertLess(e.pos.distance_to(p.player.pos), start - 30)


class NavRebuildStaggerTests(unittest.TestCase):
    """M6: the periodic refresh rebuilds one grid per tick (round-robin) so the
    ~8 ms both-grids cost never lands whole on one frame; a player jump still
    repaths everything at once."""

    def _spy(self, nf):
        calls = []
        real = nf.rebuild
        nf.rebuild = lambda tgt, only=None: (calls.append(only), real(tgt, only))[-1]
        return calls

    def test_periodic_refresh_hits_one_grid_per_tick_cycling(self):
        _g, p = _playing(1234, True)
        calls = self._spy(p._nav)
        for _ in range(6):
            p._nav_t = 0.0                    # force the interval due, player still
            p._update_nav(1 / 120)
        self.assertTrue(calls and all(c is not None for c in calls))
        self.assertEqual(set(calls), set(p._nav.classes))
        self.assertGreater(p._nav_rebuilds, 0)

    def test_player_jump_rebuilds_every_grid_at_once(self):
        _g, p = _playing(1234, True)
        calls = self._spy(p._nav)
        p.player.pos = p.player.pos + pygame.Vector2(700, 0)
        p._nav_t = 9.0                        # interval nowhere near due
        p._update_nav(1 / 120)
        self.assertEqual(calls, [None])       # None -> all classes

    def test_navfield_rebuild_only_touches_the_named_field(self):
        w = generate_world(3)
        nf = NavField(w, w.obstacles)
        nf.rebuild(w.room(w.start_id).center)
        snap_small = nf.fields["small"].cost.tobytes()
        snap_large = nf.fields["large"].cost.tobytes()
        nf.rebuild(w.room(w.boss_id).center, only="small")
        self.assertNotEqual(nf.fields["small"].cost.tobytes(), snap_small)
        self.assertEqual(nf.fields["large"].cost.tobytes(), snap_large)

    def test_debug_overlay_reports_the_nav_counter(self):
        _g, p = _playing(1234, True)
        p._nav_t = 0.0
        p._update_nav(1 / 120)
        p._report_debug()
        self.assertIn("nav", p.game.debug._metrics)
        self.assertTrue(p.game.debug._metrics["nav"].startswith("on "))

    def test_pathfinding_is_enabled_by_default(self):
        # M6 signed this off; if it is turned back off, update the journal.
        self.assertTrue(config.ENEMY_PATHFINDING)

    def test_direction_escapes_a_field_pocket_instead_of_returning_zero(self):
        # follow-up 1: a walkable cell the fill never reached (clearance below the
        # class radius) next to a reached one -> `direction` now steers toward the
        # field instead of handing back zero (which forced a blind straight line).
        _g, p = _playing(1234, True)
        from world.pathfinding import _INF
        ng = p._nav.grids["small"]
        ff = p._nav.fields["small"]
        cols = ng.cols
        spot = None
        for i in range(cols * ng.rows):
            if not ng.walkable[i] or ff.cost[i] < _INF:
                continue
            c, r = i % cols, i // cols
            if any(0 <= c + dc < cols and 0 <= r + dr < ng.rows
                   and ng.walkable[(r + dr) * cols + c + dc]
                   and ff.cost[(r + dr) * cols + c + dc] < _INF
                   for dc in (-1, 0, 1) for dr in (-1, 0, 1) if dc or dr):
                spot = ng.world_of(c, r)
                break
        if spot is None:
            self.skipTest("no field pocket for this seed")
        self.assertGreater(p._nav.direction(spot, 14).length(), 0.5)


if __name__ == "__main__":
    unittest.main()
