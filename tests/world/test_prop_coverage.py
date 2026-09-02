"""Every prop asset is reachable, and the post props are real obstacles.

Two things are being pinned here.

The first is coverage: a rig can be declared in `data/terrain.json` and still be
reached by nothing, which is how `deco_16`..`deco_18` and four of the eight
cloud rigs sat unused. Declaring art is not using it, and nothing failed when
they did not appear -- so this suite walks the props directory and insists on a
route from each file to something that places it.

The second is the post family. `deco_16`..`deco_18` are signposts and a
scarecrow: they need a *small* collider (they are thin) while keeping the size
they were painted at (fitting a signpost to an 8 px post would shrink it to
nothing). Those two requirements pull against the normal skinning rule, which
scales a rig's footprint to cover its collider, and `render_scale` is what
separates them.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.obstacle import KINDS
from game import config
from game.assets import ASSETS_DIR
from game.content import get_content
from world import frontier as F
from world.map import GameMap

SEEDS = (35, 7, 1234)
_SAVED = None
_MAPS: dict = {}

POST_KINDS = ("sign", "scarecrow")


def setUpModule():
    global _SAVED
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    _SAVED = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = True


def tearDownModule():
    config.HEIGHTMAP_ROOMS = _SAVED


def _map(seed: int) -> GameMap:
    if seed not in _MAPS:
        gm = GameMap(seed=seed)
        gm._build_tiles()
        _MAPS[seed] = gm
    return _MAPS[seed]


def _reachable_rigs(terrain) -> set:
    """Every rig something can actually place: the decoration registry, the
    obstacle skins, and the per-biome tree lists that override them."""
    # A `collision: true` entry is filtered out of the room scatter and placed
    # by nothing else, so it does not count as a route to its art -- that is
    # precisely the hole deco_16..deco_18 sat in.
    out = {e["rig"] for e in terrain["decorations"] if not e.get("collision")}
    for names in terrain["obstacle_decor"]["rigs"].values():
        out.update(names)
    for spec in terrain["biomes"].values():
        out.update(spec.get("trees", []))
    return out


class AssetCoverageTests(unittest.TestCase):
    def test_every_prop_file_is_reachable(self):
        terrain = get_content().terrain
        reachable = _reachable_rigs(terrain)
        placed_files = {terrain["rigs"][r]["anims"]["loop"]["file"]
                        for r in reachable if r in terrain["rigs"]}
        props = os.path.join(ASSETS_DIR, "terrain", "props")
        missing = []
        for name in sorted(os.listdir(props)):
            if not name.endswith(".png"):
                continue
            rel = "terrain/props/" + name
            if rel not in placed_files:
                missing.append(name)
        self.assertEqual(missing, [], f"prop art nothing can place: {missing}")

    def test_no_declared_rig_is_orphaned(self):
        """The other direction: a rig declared but wired to nothing."""
        terrain = get_content().terrain
        declared = {r for r, m in terrain["rigs"].items()
                    if m["anims"]["loop"]["file"].startswith("terrain/props/")}
        self.assertEqual(declared - _reachable_rigs(terrain), set())

    def test_no_decoration_entry_is_gated_behind_collision(self):
        """`collision: true` entries were filtered out of the room scatter and
        placed by nothing else -- a silent hole, not a feature. The post props
        are obstacles now, so nothing should be sitting in it again."""
        terrain = get_content().terrain
        stuck = [e["id"] for e in terrain["decorations"] if e.get("collision")]
        self.assertEqual(stuck, [])


class PostObstacleTests(unittest.TestCase):
    def test_posts_are_declared_obstacle_kinds(self):
        for kind in POST_KINDS:
            self.assertIn(kind, KINDS)

    def test_posts_carry_a_small_collider(self):
        """Smaller than every other family -- these are thin things."""
        for kind in POST_KINDS:
            self.assertLess(KINDS[kind][0], KINDS["tree"][0],
                            f"{kind} collider is not small")

    def test_posts_do_not_block_projectiles(self):
        """An 8 px post swallowing a shot reads as a bug, not as cover."""
        for kind in POST_KINDS:
            self.assertFalse(KINDS[kind][1], f"{kind} blocks projectiles")

    def test_posts_are_drawn_at_their_authored_size(self):
        """The point of `render_scale`: the art keeps the size it was painted
        at instead of being fitted to the collider."""
        terrain = get_content().terrain
        seen = set()
        for seed in SEEDS:
            gm = _map(seed)
            for i, o in enumerate(gm.obstacles):
                if o.kind not in POST_KINDS or i not in gm._decos:
                    continue
                seen.add(o.kind)
                _ax, _ay, _fps, frs, _phase = gm._decos[i]
                rigs = terrain["obstacle_decor"]["rigs"][o.kind]
                authored = {tuple(terrain["rigs"][r]["frame"]) for r in rigs}
                self.assertIn(frs[0].get_size(), authored,
                              f"{o.kind} drawn at {frs[0].get_size()}, "
                              f"authored {sorted(authored)}")
        self.assertEqual(seen, set(POST_KINDS), "a post kind never placed")

    def test_render_scale_overrides_the_collider_fit(self):
        terrain = get_content().terrain
        conf = terrain["obstacle_decor"]
        for kind in POST_KINDS:
            self.assertEqual(conf["render_scale"][kind], 1.0)
            meta = terrain["rigs"][conf["rigs"][kind][0]]
            radius = float(terrain["obstacles"][kind]["radius"])
            boost = float(conf["size_boost"])
            self.assertEqual(F.rig_scale(meta, radius, boost, 1.0), 1.0)
            # ...and without the override it would have been shrunk badly.
            self.assertLess(F.rig_scale(meta, radius, boost), 0.5)

    def test_posts_appear_only_on_the_biomes_that_declare_them(self):
        terrain = get_content().terrain
        allowed = {kind: {fam for fam, spec in terrain["biomes"].items()
                          if kind in spec["scatter"]["weights"]}
                   for kind in POST_KINDS}
        for seed in SEEDS:
            for o in _map(seed).obstacles:
                if o.kind in POST_KINDS and o.biome:
                    self.assertIn(o.biome, allowed[o.kind],
                                  f"{o.kind} on {o.biome}")

    def test_posts_stay_landmarks_not_clutter(self):
        """Weighted at landmark scale on purpose: a handful per world, not a
        field of them."""
        for seed in SEEDS:
            obs = _map(seed).obstacles
            posts = sum(1 for o in obs if o.kind in POST_KINDS)
            self.assertGreater(posts, 0, f"seed {seed}: no posts at all")
            self.assertLess(posts / len(obs), 0.12,
                            f"seed {seed}: posts are {posts}/{len(obs)}")


if __name__ == "__main__":
    unittest.main()
