"""The browser build's own crowd (BLD-003.2).

`config.apply_web_profile()` lowers the enemy live cap to
`ENEMY_COUNT_BASE` (100) and sets the three AI performance knobs of
`documentation/plans/web_plan.md` section 4 (BLD-003.D1, D2). The first
class pins the numbers on both sides; the second boots a run under the
profile and checks each value where the game reads it (the spawn master's
director, the flow field's fill, the refresh timer at boot, after a
round-robin tick and after a jump, the tick LOD), so a reader that captured
a value before the profile ran would fail here rather than silently keep
the desktop number.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
# Every module that reads one of the four values, imported here under the
# desktop config. The booted run below imports whatever it lacks only
# inside the web profile, where a value captured at import would already be
# the browser's and the test could not tell; imported first, a capture holds
# the desktop value and the run's checks fail on it.
import game.states.playing.core.navigation  # noqa: F401
import game.states.playing.core.state  # noqa: F401
import spawn.master  # noqa: F401
import world.nav.field  # noqa: F401
from tests.flows import test_lod as L
from tests.web_profile import web_profile

# Name -> (desktop, browser). A deliberate retune on either side changes
# this table and `documentation/journals/web_frame_time_journal.md` together.
CROWD = {
    "ENEMY_LIVE_CAP": (250, 100),
    "ENEMY_LOD_SKIP": (2, 3),
    "ENEMY_NAV_REBUILD_INTERVAL": (0.4, 0.6),
    "NAV_FILL_MAX_COST": (4500, 3500),
}


class WebCrowdValueTests(unittest.TestCase):
    def test_the_desktop_keeps_its_own_crowd(self):
        for name, (desktop, _web) in CROWD.items():
            self.assertEqual(getattr(config, name), desktop, name)

    def test_the_web_profile_sets_the_browser_crowd(self):
        with web_profile():
            for name, (_desktop, web) in CROWD.items():
                self.assertEqual(getattr(config, name), web, name)

    def test_the_web_cap_follows_the_directors_opening_crowd(self):
        """D1: the browser's cap *is* `ENEMY_COUNT_BASE`, so a run opens
        with the desktop's crowd and only the growth past it is cut."""
        with mock.patch.object(config, "ENEMY_COUNT_BASE", 80), web_profile():
            self.assertEqual(config.ENEMY_LIVE_CAP, 80)

    def test_leaving_the_profile_restores_the_desktop_crowd(self):
        with web_profile():
            pass
        for name, (desktop, _web) in CROWD.items():
            self.assertEqual(getattr(config, name), desktop, name)


class WebCrowdRunTests(unittest.TestCase):
    """One run booted under the web profile (seed 35, developer mode, the
    same boot as `test_lod`), shared by every test here. A test that moves
    the hero or re-aims the field puts them back; enemies a test spawns
    stay, and no other test here reads the crowd's size."""

    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(web_profile())
        cls.ps = L._run()
        cls.nav_t_at_boot = cls.ps._nav_t        # before anything updates

    def test_the_director_opens_at_the_base_and_stops_at_100(self):
        d = self.ps.spawn.master.director
        self.assertEqual(d.live_cap, 100)
        self.assertEqual(d.enemy_count_cap(0.0), config.ENEMY_COUNT_BASE)
        self.assertEqual(d.enemy_count_cap(10_000.0), 100)

    def test_a_flow_field_fill_stops_at_3500(self):
        nav = self.ps._nav
        nav.begin(self.ps.player.pos)
        for name, field in nav.fields.items():
            self.assertEqual(field._fill.limit, 3500, name)
        nav.step(None)                                    # land it

    def test_the_first_refresh_waits_0_6_s(self):
        """`PlayingState._init_nav` arms the timer from the profile."""
        self.assertAlmostEqual(self.nav_t_at_boot, 0.6)

    def test_the_periodic_refresh_waits_0_6_s_across_the_classes(self):
        ps = self.ps
        ps._nav.step(None)                                # nothing mid-fill
        ps._nav_t = 0.0
        ps.nav.update(1 / 60)
        self.assertAlmostEqual(ps._nav_t, 0.6 / len(ps._nav.classes))

    def test_the_refresh_after_a_jump_waits_0_6_s(self):
        ps = self.ps
        home = pygame.Vector2(ps.player.pos)
        ps._nav.step(None)
        ps._nav_t = 10.0                                  # the timer is not due
        ps.player.pos.update(L._far_spot(ps))             # many cells away
        try:
            ps.nav.update(1 / 60)
            self.assertAlmostEqual(ps._nav_t, 0.6)
        finally:
            ps.player.pos.update(home)
            ps._nav.rebuild(home)

    def test_a_far_idle_enemy_ticks_every_third_frame(self):
        ps = self.ps
        far = ps.spawn.spawn_enemy("skull", at=L._far_spot(ps))
        near = ps.spawn.spawn_enemy("skull",
                                    at=ps.player.pos + pygame.Vector2(200, 0))
        counts, dts = L.count_updates(ps, 30)
        self.assertEqual(counts[id(near)], 30)
        self.assertEqual(counts[id(far)], 10)
        self.assertEqual(dts[id(far)], {round(3 / 60, 6)})


if __name__ == "__main__":
    unittest.main()
