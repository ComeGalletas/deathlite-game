"""The `flying` tag: over the world rather than on it.

`The First Hunger` is a giant bat, so it crosses a boulder, a cliff and
its own island's lake in a straight line instead of rounding one, taking
the stairs to the second and stopping dead at the third. What it may
*not* do is leave the island -- a boss out over the sea is a boss the
player cannot fight.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.boss import Boss
from game.content import get_content
from tests import worlds as W

SEED = W.SEEDS[0]


def _boss(flying=True):
    c = get_content()
    bid = next(iter(c.bosses))
    cfg = dict(c.boss(bid))
    if not flying:
        cfg["tags"] = tuple(t for t in cfg.get("tags", ()) if t != "flying")
    return Boss(bid, cfg, 0.0, 0.0)


class TagTests(unittest.TestCase):
    def test_the_shipped_boss_flies(self):
        c = get_content()
        cfg = c.boss(next(iter(c.bosses)))
        self.assertIn("flying", cfg["tags"])
        self.assertEqual(cfg["sprite"], "giant_bat")     # the reason it flies
        self.assertTrue(_boss().flying)

    def test_the_tag_is_what_decides_it(self):
        self.assertFalse(_boss(flying=False).flying)


class ColliderTests(unittest.TestCase):
    """`GameMap.is_walkable(flying=True)` keeps the floor test and drops the
    rest."""

    def setUp(self):
        self.gm = W.game_map(SEED)

    def test_a_flyer_passes_over_an_obstacle_that_blocks_a_walker(self):
        blocked = 0
        for o in self.gm.obstacles:
            if self.gm.is_walkable(o.pos, 10.0):
                continue                      # not blocking there anyway
            blocked += 1
            self.assertTrue(self.gm.is_walkable(o.pos, 10.0, flying=True),
                            f"a flyer was stopped by a {o.kind}")
        self.assertGreater(blocked, 50, "no obstacle blocked a walker at all")

    def test_a_flyer_crosses_a_cliff_a_walker_may_not(self):
        """Pairs of neighbouring cells on different terraces: the elevation
        rule refuses the step, flying takes it."""
        px = 64
        refused = crossed = 0
        for room in self.gm.layout.rooms:
            for (col, row), cell in room.grid.items():
                if cell.kind != "ground":
                    continue
                here = pygame.Vector2(room.rect.left + (col + .5) * px,
                                      room.rect.top + (row + .5) * px)
                for dc, dr in ((1, 0), (0, 1)):
                    nb = room.grid.get((col + dc, row + dr))
                    if nb is None or nb.kind != "ground" or nb.level == cell.level:
                        continue
                    there = pygame.Vector2(here.x + dc * px, here.y + dr * px)
                    if self.gm.is_walkable(there, 0.0, frm=here):
                        continue
                    refused += 1
                    self.assertTrue(self.gm.is_walkable(there, 0.0, frm=here, flying=True))
                    crossed += 1
        self.assertGreater(refused, 5, "no terrace step was refused on this seed")
        self.assertEqual(refused, crossed)

    def test_a_flyer_crosses_its_own_islands_lake(self):
        """A lake is a cell of the island's height map. A body that walks is
        refused it; a bat that stops dead at a pond looks broken."""
        from world.layout import LAKE
        px = 64
        lakes = [(r, cell) for r in self.gm.layout.rooms
                 for cell, c in r.grid.items() if c.kind == LAKE]
        self.assertTrue(lakes, "no inland lake on this seed")
        for r, (col, row) in lakes:
            p = pygame.Vector2(r.rect.left + (col + .5) * px,
                               r.rect.top + (row + .5) * px)
            self.assertFalse(self.gm.is_walkable(p, 0.0))
            self.assertTrue(self.gm.is_walkable(p, 0.0, flying=True))

    def test_a_flyer_still_may_not_leave_the_island(self):
        """The sea is not a cell of anything: over it, flying buys nothing."""
        b = self.gm.layout.bounds
        for spot in (pygame.Vector2(b.left + 2, b.top + 2),
                     pygame.Vector2(b.centerx, b.top + 2),
                     pygame.Vector2(-500, -500)):
            self.assertFalse(self.gm.is_walkable(spot, 0.0, flying=True),
                             f"a flyer left the island at {spot}")

    def test_the_flying_floor_is_the_grid_plus_the_bridges(self):
        """Every cell an island's height map holds -- ground, cliff, flight,
        lake -- is flyable; the void between islands is not."""
        import random
        px, rng = 64, random.Random(7)
        lay = self.gm.layout
        checked = 0
        for _ in range(400):
            r = rng.choice(lay.rooms)
            col = rng.randrange(r.rect.width // px)
            row = rng.randrange(r.rect.height // px)
            p = pygame.Vector2(r.rect.left + (col + .5) * px,
                               r.rect.top + (row + .5) * px)
            inside = (col, row) in r.grid
            if not inside and self.gm._over_island(p.x, p.y):
                continue                      # another island's rect overlaps here
            self.assertEqual(self.gm.is_walkable(p, 0.0, flying=True), inside)
            checked += 1
        self.assertGreater(checked, 100)

    def test_resolve_movement_carries_the_flag_through_its_slides(self):
        """A step into a tree: refused for a walker (it slides or stays),
        taken whole for a flyer."""
        tree = next(o for o in self.gm.obstacles
                    if o.kind == "tree" and not self.gm.is_walkable(o.pos, 10.0))
        frm = pygame.Vector2(tree.pos.x - 40, tree.pos.y)
        if not self.gm.is_walkable(frm, 10.0):
            self.skipTest("no clear approach to that tree on this seed")
        walked = self.gm.resolve_movement(frm, pygame.Vector2(tree.pos), 10.0)
        flown = self.gm.resolve_movement(frm, pygame.Vector2(tree.pos), 10.0, flying=True)
        self.assertNotEqual(tuple(walked), tuple(tree.pos))
        self.assertEqual(tuple(flown), tuple(tree.pos))


class SeekTests(unittest.TestCase):
    def test_a_flyer_ignores_the_flow_field_and_beelines(self):
        """The field routes for a body that walks -- round the wall, up the
        stairs. A flyer takes the straight line."""
        from types import SimpleNamespace
        player = pygame.Vector2(300, 0)
        field = pygame.Vector2(0, 1)                    # the field says "go south"
        ctx = SimpleNamespace(player_pos=player, nav_dir=lambda p, r: pygame.Vector2(field))
        flyer, walker = _boss(), _boss(flying=False)
        self.assertAlmostEqual(flyer._seek(ctx).x, 1.0, places=3)   # straight at the player
        self.assertAlmostEqual(walker._seek(ctx).y, 1.0, places=3)  # follows the field


if __name__ == "__main__":
    unittest.main()
