"""Obstacle families: minerals (rock / pillar) unchanged, shrubs retired to
decoration, trees given a small collision ring and a global +25% density
boost clumped into groves. See `world/gen/scatter.py` (`_scatter_obstacles`,
`_topup_trees`) and the assets journal, "Obstacle split -- minerals vs.
trees".

Reads the shared worlds in `tests/worlds.py`. Every property test here holds
for any seed, so they check the four pinned seeds; the density boost is a
statistical claim and keeps its thirty-seed sweep, marked as such.
"""
import unittest

import pygame

import world.gen.scatter as P
from entities.obstacle import KINDS
from tests import worlds as W


def _boosted(seed, boost):
    """The layout for `seed` scattered with `_TREE_DENSITY_BOOST = boost`.
    The default boost is the shared world, so nothing is rebuilt for it."""
    if boost == P._TREE_DENSITY_BOOST:
        return W.layout(seed)
    return W.layout(seed, patches=((P, "_TREE_DENSITY_BOOST", boost),))


class ShrubRetiredTests(unittest.TestCase):
    def test_shrub_is_not_an_obstacle_kind(self):
        self.assertNotIn("shrub", KINDS)

    def test_no_world_generates_a_shrub_obstacle(self):
        for seed in W.SEEDS:
            self.assertFalse(any(o.kind == "shrub"
                                 for o in W.layout(seed).obstacles))

    def test_obstacle_kinds_are_only_the_declared_families(self):
        """`sign` and `scarecrow` joined the list when the three post props
        (deco_16..deco_18) stopped being unreachable decoration entries and
        became real obstacles with small colliders."""
        seen = set()
        for seed in W.SEEDS:
            seen.update(o.kind for o in W.layout(seed).obstacles)
        self.assertTrue(seen.issubset(
            {"tree", "rock", "pillar", "house", "sign", "scarecrow"}), seen)


class TreeColliderTests(unittest.TestCase):
    def test_tree_ring_is_smaller_than_a_rock(self):
        self.assertLess(KINDS["tree"][0], KINDS["rock"][0])

    def test_tree_still_blocks_movement_and_shots(self):
        for seed in W.SEEDS:
            gm = W.game_map(seed)
            t = next((o for o in gm.obstacles if o.kind == "tree"), None)
            if t is None:
                continue
            self.assertFalse(gm.is_walkable(pygame.Vector2(t.pos), 0))
            self.assertIsNotNone(gm.blocking_obstacle_hit(pygame.Vector2(t.pos), 4))
            return
        self.fail(f"no tree obstacle in seeds {W.SEEDS}")


class TreeDensityBoostTests(unittest.TestCase):
    def _count(self, boost, seeds):
        return sum(sum(o.kind == "tree" for o in _boosted(s, boost).obstacles)
                   for s in seeds)

    def test_boost_adds_about_25_percent_more_trees_globally(self):
        """A ratio over thirty seeds; fewer and the +/-6 % band is noise.
        Tier `sweep`."""
        seeds = range(30)
        base, boosted = self._count(0.0, seeds), self._count(0.25, seeds)
        self.assertGreater(base, 0)
        self.assertAlmostEqual(boosted / base, 1.25, delta=0.06)

    def test_boost_leaves_minerals_byte_identical(self):
        """The top-up runs after the main scatter and only adds trees, so no
        mineral may move when it is switched on.

        The connectivity repair is switched off for the comparison, and has to
        be: it is a decision about the *whole* obstacle set, so an added tree
        can legitimately change which obstacle is cheapest to take back --
        including a rock. That is the repair working, not the top-up leaking
        into the placement RNG, which is what this test is about."""
        def minerals(boost):
            lay = W.layout(7, patches=((P, "_TREE_DENSITY_BOOST", boost),),
                           HEIGHTMAP_UNSEAL=False)
            return [(o.kind, round(o.pos.x, 3), round(o.pos.y, 3))
                    for o in lay.obstacles if o.kind in ("rock", "pillar")]
        self.assertEqual(minerals(0.0), minerals(0.25))


class TreeSpacingTests(unittest.TestCase):
    def test_a_tree_pair_is_tighter_than_the_old_floor(self):
        """Trees group; minerals do not. Before the tree gap existed the closest
        two obstacles of any kind could sit was 2*15 + 46 = 76 px, and the point
        of the tree-to-tree gap is that a pair can stand closer than that.

        The bound is 76, not the 70 it was, because the height-map world
        spaces *canopies* rather than trunks (`tuning._TREE_TREE_GAP_GRID`): a
        tree's collider is a 15 px trunk ring but its art is 93-138 px wide, so
        the old 37 px floor let a third of all trees overlap a neighbour by
        most of a canopy. The floor is 70 px there now -- still inside the
        mineral spacing this test is really about, which is what makes a grove
        a grove."""
        tightest = 1e9
        for seed in W.SEEDS:
            trees = [o.pos for o in W.layout(seed).obstacles
                     if o.kind == "tree"]
            for i in range(len(trees)):
                for j in range(i + 1, len(trees)):
                    tightest = min(tightest, trees[i].distance_to(trees[j]))
            if tightest < 76:
                return
        self.fail("tree spacing never tightened into a grove")

    def test_trees_never_collide_with_a_mineral(self):
        rt = KINDS["tree"][0]
        for seed in W.SEEDS:
            obs = W.layout(seed).obstacles
            trees = [o for o in obs if o.kind == "tree"]
            rocks = [o for o in obs if o.kind in ("rock", "pillar")]
            for t in trees:
                for r in rocks:
                    self.assertGreater(t.pos.distance_to(r.pos), rt + r.radius,
                                       f"tree overlaps {r.kind} (seed {seed})")


if __name__ == "__main__":
    unittest.main()
