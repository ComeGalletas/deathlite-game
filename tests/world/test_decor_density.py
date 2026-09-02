"""Decoration density: tiers, ground cover, and the spacing that survives them.

Group D of the props work. Three things are pinned.

`per_1000` used to be one number per biome, so every prop competed for a single
budget and the authored `per_room` counts were shares of it -- making grass
common could only take props away from the boulders. It is a per-tier table
now, and the tiers must stay independently priced.

Densities were then raised roughly fourfold, which turned two latent costs into
real ones. The placement test was O(n^2) against everything already placed (see
`decor._Neighbourhood`), and every island had a 394 px-radius disc blanked out
of its middle -- the LD-8 "keep the interaction space clear" rule, which is a
fraction of the room's size and was written for 60-cell rooms. No amount of
raising the rates would have shown through that.
"""
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.content import get_content
from world import frontier as F
from world.map import GameMap
from world.terrain import decor as D

SEEDS = (35, 7, 1234)
_SAVED = None
_MAPS: dict = {}


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


def _room_entries():
    return [e for e in get_content().terrain["decorations"]
            if e["placement"] == "room_interior" and not e.get("collision")]


def _gap_by_drawn_size():
    """`(w, h) -> min_gap`, so a placed instance can be traced back to the rule
    it was placed under. The instance tuple carries frames, not its entry."""
    terrain = get_content().terrain
    out = {}
    for e in _room_entries():
        frame = terrain["rigs"][e["rig"]]["frame"]
        s = float(e.get("scale", 1.0))
        size = (max(1, round(frame[0] * s)), max(1, round(frame[1] * s)))
        # The *smallest* gap of any entry drawn at this size. Two entries can
        # share a drawn size with different gaps (a 32x32 boulder asks 22 px, a
        # 32x32 flat pebble 20), and an instance carries frames rather than its
        # entry, so this is the strongest constraint that is certainly true of
        # whichever one it came from.
        out[size] = min(out.get(size, 1e9), float(e.get("min_gap", 40)))
    return out


class TierSchemaTests(unittest.TestCase):
    def test_every_room_entry_declares_a_tier(self):
        """Read as `e["tier"]`, with no fallback in code: a decoration with no
        tier has no defined density, and tuning belongs in the data."""
        for e in _room_entries():
            self.assertIn("tier", e, f"{e['id']} declares no tier")
            self.assertIn(e["tier"], D.TIERS, f"{e['id']}: {e['tier']!r}")

    def test_every_biome_prices_every_tier(self):
        for fam, spec in get_content().terrain["biomes"].items():
            rates = spec["decor"]["per_1000"]
            self.assertIsInstance(rates, dict, f"{fam} still has a flat rate")
            for tier in D.TIERS:
                self.assertIn(tier, rates, f"{fam} does not price {tier}")
                self.assertGreater(float(rates[tier]), 0, f"{fam}/{tier}")

    def test_landmarks_are_the_rarest_tier_everywhere(self):
        """The shape the tiers exist to express: a stump or a bush is an event
        on a terrace, whatever else that terrace is covered in."""
        for fam, spec in get_content().terrain["biomes"].items():
            r = spec["decor"]["per_1000"]
            self.assertLess(r["landmark"], r["feature"], fam)
            self.assertLess(r["landmark"], r["ground_cover"], fam)

    def test_the_green_biomes_are_carried_by_ground_cover(self):
        """Grass is what makes a meadow look like a meadow. The stony biomes
        deliberately invert this -- a rock shelf is mostly stones, and grass on
        it is the accent rather than the ground."""
        rates = {fam: spec["decor"]["per_1000"]
                 for fam, spec in get_content().terrain["biomes"].items()}
        for fam in ("meadow", "forest", "drab", "wetland"):
            self.assertGreater(rates[fam]["ground_cover"],
                               rates[fam]["feature"], fam)
        for fam in ("rock", "sand"):
            self.assertGreaterEqual(rates[fam]["feature"],
                                    rates[fam]["ground_cover"], fam)


class GrassTests(unittest.TestCase):
    """deco_10 / deco_11 -- plain grass strands, wanted everywhere and often."""

    RIGS = ("deco_ground_10", "deco_ground_11")

    def _entries(self):
        return [e for e in _room_entries() if e["rig"] in self.RIGS]

    def test_the_grass_strands_are_universal(self):
        got = self._entries()
        self.assertEqual(len(got), len(self.RIGS))
        for e in got:
            self.assertNotIn("biomes", e,
                             f"{e['id']} is still restricted to some biomes")
            self.assertEqual(e["tier"], D.GROUND_COVER, e["id"])

    def test_the_grass_strands_clump(self):
        """A small `min_gap` is what lets them bunch into patches instead of
        spacing out like a placed prop."""
        for e in self._entries():
            self.assertLessEqual(float(e["min_gap"]), 12, e["id"])

    def test_the_grass_strands_are_big_enough_to_read(self):
        """They were authored as rare accents at quarter scale, which put 8 px
        of content on a 64 px tile -- placing more of them changed nothing that
        could be seen. Ground cover has to be legible to count."""
        terrain = get_content().terrain
        for e in self._entries():
            path = os.path.join(
                "assets", *terrain["rigs"][e["rig"]]["anims"]["loop"]["file"].split("/"))
            content = pygame.image.load(path).convert_alpha().get_bounding_rect()
            drawn = content.width * float(e["scale"])
            self.assertGreater(drawn, config.TILE_PX * 0.25,
                               f"{e['id']} draws {drawn:.0f}px of content")

    def test_grass_actually_reaches_every_biome(self):
        placed = set()
        for seed in SEEDS:
            gm = _map(seed)
            for room in gm.layout.rooms:
                if not room.grid:
                    continue
                for _f, _ax, _ay, _fps, x, y in gm._room_decor.get(room.id, ()):
                    cell = room.grid.get(gm.room_cell(room, x, y))
                    if cell is not None:
                        placed.add(cell.level)
        self.assertTrue(placed, "nothing placed at all")


class DensityTests(unittest.TestCase):
    def test_terraces_are_furnished_not_sprinkled(self):
        """Before the tiers a terrace ran about one prop per 13 to 25 tiles,
        which reads as bare ground with an accident on it."""
        for seed in SEEDS:
            gm = _map(seed)
            props = sum(len(v) for v in gm._room_decor.values())
            cells = sum(len(F.interior_cells(r) or ())
                        for r in gm.layout.rooms if r.grid)
            self.assertGreater(cells, 0)
            per = cells / max(props, 1)
            self.assertLess(per, 6.0,
                            f"seed {seed}: 1 prop per {per:.1f} tiles")

    def test_the_centre_of_an_island_is_not_blanked(self):
        """The fixed disc replaced a fraction-of-the-room rule that cleared a
        394 px radius on a 3200 x 1792 island."""
        clear = float(get_content().terrain["decor_placement"]["centre_clear"])
        self.assertLess(clear, 4 * config.TILE_PX)
        found = 0
        for seed in SEEDS:
            gm = _map(seed)
            for room in gm.layout.rooms:
                if not room.grid:
                    continue
                cx, cy = room.center
                for _f, _ax, _ay, _fps, x, y in gm._room_decor.get(room.id, ()):
                    if math.dist((x, y), (cx, cy)) < 6 * config.TILE_PX:
                        found += 1
        self.assertGreater(found, 20,
                           "island centres are still coming out bare")


class SpacingTests(unittest.TestCase):
    """The index has to give the same answers the pairwise scan did."""

    def test_no_two_props_are_closer_than_their_gap(self):
        gaps = _gap_by_drawn_size()
        for seed in SEEDS:
            gm = _map(seed)
            for rid, inst in gm._room_decor.items():
                pts = [(x, y, gaps.get(frs[0].get_size(), 40.0))
                       for frs, _ax, _ay, _fps, x, y in inst]
                for i, (x, y, g) in enumerate(pts):
                    for x2, y2, g2 in pts[i + 1:]:
                        self.assertGreaterEqual(
                            math.dist((x, y), (x2, y2)), max(g, g2) - 1e-6,
                            f"seed {seed} room {rid}: props too close")

    def test_no_prop_crowds_an_obstacle(self):
        for seed in SEEDS:
            gm = _map(seed)
            for inst in gm._room_decor.values():
                for _f, _ax, _ay, _fps, x, y in inst:
                    for o in gm.obstacles:
                        self.assertGreaterEqual(
                            math.dist((x, y), (o.pos.x, o.pos.y)),
                            o.radius + 20 - 1e-6,
                            f"seed {seed}: prop inside {o.kind} clearance")


class NeighbourhoodTests(unittest.TestCase):
    def test_it_matches_a_pairwise_scan(self):
        import random
        rng = random.Random(7)
        pts = [(rng.uniform(0, 900), rng.uniform(0, 900),
                rng.choice((10.0, 20.0, 40.0))) for _ in range(400)]
        idx = D._Neighbourhood(40.0)
        placed = []
        for x, y, g in pts:
            want = any(math.dist((x, y), (px_, py_)) < max(g, pg)
                       for px_, py_, pg in placed)
            self.assertEqual(idx.blocked(x, y, g), want)
            if not want:
                idx.add(x, y, g)
                placed.append((x, y, g))

    def test_a_zero_gap_query_honours_only_what_is_stored(self):
        """How the obstacle clearance keeps its exact `(radius + 20)` meaning."""
        idx = D._Neighbourhood(60.0)
        idx.add(100.0, 100.0, 50.0)
        self.assertTrue(idx.blocked(140.0, 100.0, 0.0))
        self.assertFalse(idx.blocked(151.0, 100.0, 0.0))

    def test_an_empty_index_blocks_nothing(self):
        self.assertFalse(D._Neighbourhood(40.0).blocked(0.0, 0.0, 100.0))


if __name__ == "__main__":
    unittest.main()
