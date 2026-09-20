"""The fish huts and their seahorse boats (`world/gen/fish_huts.py`,
`entities/npc.py` `WaterNpc`, `game/states/playing/core/fish_huts.py`;
journals/fish_hut_journal.md).

The placement half reads the shared pinned layouts; the run half boots one
run on a pinned seed, like the villagers' tests, and reads what it built.
"""
import math
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.npc import IDLE, WALK, WaterNpc
from game import config
from game.content import get_content
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing.core.fish_huts import BOAT, FishHutProp
from world.gen.fish_huts import bridge_ends, clear_water
from world.gen.tuning import _FH_APART, _FH_CLEAR, _FH_OUT
from tests import worlds as W


class PlacementTests(unittest.TestCase):
    """Every pinned seed: the huts moor beside their island's bridges on
    open water, one to three per island, apart from each other."""

    def _each(self):
        for seed in W.SEEDS:
            lay = W.layout(seed)
            with self.subTest(seed=seed):
                yield seed, lay

    def test_there_are_huts_and_never_more_than_three_per_island(self):
        lo, hi = get_content().npcs["placement"]["fish_huts"]
        for _seed, lay in self._each():
            self.assertTrue(lay.fish_huts)
            per = {}
            for h in lay.fish_huts:
                per[h.room_id] = per.get(h.room_id, 0) + 1
            for rid, n in per.items():
                self.assertLessEqual(n, hi, f"island {rid} has {n} huts")
                self.assertGreaterEqual(n, lo)

    def test_every_hut_stands_in_clear_water(self):
        px = config.TILE_PX
        for _seed, lay in self._each():
            for h in lay.fish_huts:
                self.assertTrue(clear_water(lay, h.x, h.y, _FH_CLEAR * px),
                                f"hut of island {h.room_id} at {h.x:.0f},{h.y:.0f} "
                                f"is not on clear water")

    def test_every_hut_is_beside_one_of_its_islands_bridges(self):
        """`_FH_OUT` tiles off the centre line of a bridge that touches its
        island -- perpendicular to the span, as asked."""
        px = config.TILE_PX
        for _seed, lay in self._each():
            for h in lay.fish_huts:
                c = lay.corridors[h.corridor]
                self.assertIn(h.room_id, (c.a, c.b))
                off = abs(h.y - c.rect.centery) if c.axis == "h" else abs(h.x - c.rect.centerx)
                self.assertAlmostEqual(off, _FH_OUT * px, delta=1.0)

    def test_the_hut_is_off_the_mouth_not_over_the_island(self):
        """Along the span, the hut sits past where the planks leave the
        island's cells: out to sea, not over the beach."""
        for _seed, lay in self._each():
            ends = {(e[0], e[1]): e for e in bridge_ends(lay)}
            for h in lay.fish_huts:
                _rid, _ci, mx, my, ax, ay, _sx, _sy = ends[(h.room_id, h.corridor)]
                along = (h.x - mx) * ax + (h.y - my) * ay
                self.assertGreater(along, 0.0)

    def test_huts_keep_their_distance(self):
        px = config.TILE_PX
        for _seed, lay in self._each():
            hs = lay.fish_huts
            for i in range(len(hs)):
                for j in range(i + 1, len(hs)):
                    d = math.hypot(hs[i].x - hs[j].x, hs[i].y - hs[j].y)
                    self.assertGreaterEqual(d, _FH_APART * px - 1e-6)

    def test_the_huts_are_seeded_by_the_world(self):
        seed = W.pinned(0)
        self.assertEqual(W.fresh(seed).layout.fish_huts, W.layout(seed).fish_huts)


SEED = W.pinned(2)


def fresh_playing(seed=SEED):
    from tests.boot import start_run
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    return game, start_run(game, seed)


class BoatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.p = fresh_playing()
        cls.lay = cls.p.game_map.layout

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _nearest_hut(self, pos):
        return min(self.p.fish_huts, key=lambda h: h.pos.distance_to(pos))

    def test_every_hut_is_built_with_two_to_four_boats(self):
        p = self.p
        self.assertEqual(len(p.fish_huts), len(self.lay.fish_huts))
        lo, hi = get_content().npcs["placement"]["boats"]
        ring = get_content().npcs["placement"]["boat_ring"][1] * config.TILE_PX
        crews = {id(h): 0 for h in p.fish_huts}
        for b in p.boats:
            self.assertIsInstance(b, WaterNpc)
            self.assertEqual(b.kind, BOAT)
            h = self._nearest_hut(b.home)
            self.assertLessEqual(h.pos.distance_to(b.home), ring + 1e-6)
            crews[id(h)] += 1
        for h in p.fish_huts:
            self.assertTrue(lo <= crews[id(h)] <= hi,
                            f"hut at {h.pos} has {crews[id(h)]} boats")

    def test_boats_are_on_the_water_and_never_fight(self):
        gm = self.p.game_map
        for b in self.p.boats:
            self.assertTrue(gm.is_open_water(b.pos.x, b.pos.y))
            self.assertEqual(b.aggro, 0.0)

    def test_the_riders_are_dealt_from_every_sheet(self):
        rigs = set(get_content().npcs["kinds"][BOAT]["rigs"])
        self.assertTrue({b.rig for b in self.p.boats} <= rigs)

    def test_a_boat_drifts_within_its_leash_and_stays_on_the_water(self):
        p = self.p
        b = p.boats[0]
        idle = get_content().npcs["kinds"][BOAT]["idle"]
        rng = random.Random(3)
        walked = False
        b.timer = 0.0
        for _ in range(60 * 30):
            b.update(1 / 60, rng, p.game_map, idle)
            if b.state == WALK:
                walked = True
            self.assertLessEqual(b.pos.distance_to(b.home), b.leash + 4.0 + 1e-6)
            self.assertTrue(p.game_map.is_open_water(b.pos.x, b.pos.y))
        self.assertTrue(walked, "the boat never drifted")
        self.assertIn(b.state, (IDLE, WALK))

    def test_a_hut_is_a_bobbing_prop_with_the_hut_rig(self):
        for h in self.p.fish_huts:
            self.assertIsInstance(h, FishHutProp)
            self.assertEqual(h.rig, "npc_fish_hut")
            self.assertIsNotNone(h.anim, "the hut rig did not load")

    def test_huts_and_boats_are_drawn_with_the_characters(self):
        p = self.p
        h = p.fish_huts[0]
        p.camera.snap_to(h.pos)
        depths = [d for _lvl, d, _fn in p._actor_items()]
        self.assertIn(h.pos.y, depths)
        crew = [b for b in p.boats if self._nearest_hut(b.home) is h]
        for b in crew:
            self.assertIn(b.pos.y, depths)
        p.fish_hut_manager.update(1 / 60)
        surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        p.draw(surface)                   # draws without raising

    def test_boats_are_seeded_by_the_world(self):
        p = self.p
        before = [(b.rig, round(b.home.x), round(b.home.y)) for b in p.boats]
        p.fish_hut_manager.build()
        after = [(b.rig, round(b.home.x), round(b.home.y)) for b in p.boats]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
