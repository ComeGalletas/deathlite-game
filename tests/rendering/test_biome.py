"""LD-9/LD-10: the per-island biome.

The height-map worlds used to read a fixed `floor -> sheet` map, so every island
on every seed wore the same tileset at the same height. Which tilesets an island
may wear is a property of its **topography** now
(`config.HEIGHTMAP_TOPOGRAPHIES`), not of its room kind: kind says what happens
on an island and topography says what shape it is, so choosing the ground by
kind was reading the wrong axis. The brief's rule -- *at least three tilemaps
per island, no two adjacent floors share one* -- runs from level 0 up.

Level 0 is still special, but for a reason that is now *derived* rather than
declared: it is the only terrace that meets the sea, so a sheet flagged
`shoreline: false` has no surf block for it. The filter is the flag, and a
topography may opt out -- `boss` does, deliberately, to see what a beachless
coastline reads like.

Adjacency compares the **biome** rather than the filename, over the six biomes
grouped on measured ground colour in `data/terrain.json`. LD-10 step 3 gives
each of those a scatter mix as well, so a rock terrace is boulders where a
forest one is trunks -- which is why the palette is decided at generation
(`world/gen/biomes.py`) and merely read at bake.
"""
import collections
import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import ASSETS_DIR, get_assets
from tests import worlds as W
from world.map import GameMap
from world.layout import GROUND
from world.gen import biomes
from world.terrain import decor
from world.gen.biomes import floor_palette, scatter_mix
from world.terrain.sheets import TileSheets

POOL = ["a.png", "b.png", "c.png"]
SHORE = {"a.png", "b.png", "c.png", "base.png"}
# `b` shares a material with the ground the islands rise from, the way
# `tilemap_7`'s grass shares one with the level-0 kind palettes.
FAMILY = {"base.png": "grass", "a.png": "rock", "b.png": "grass",
          "c.png": "sand"}.get


class PoolDataTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join("data", "terrain.json"), encoding="utf-8") as fh:
            self.t = json.load(fh)

    def test_every_topography_declares_sheets_it_can_wear(self):
        flags = self.t.get("sheet_flags", {})
        for name, spec in config.HEIGHTMAP_TOPOGRAPHIES.items():
            owned = spec.get("sheets")
            self.assertTrue(owned, f"{name} declares no sheets")
            self.assertEqual(len(set(owned)), len(owned), f"{name} repeats one")
            if not spec.get("allow_beachless_shore"):
                self.assertTrue(
                    any(flags.get(x, {}).get("shoreline", True) for x in owned),
                    f"{name} has no sheet that can meet the sea")

    def test_every_sheet_names_a_declared_biome(self):
        """An unlisted sheet falls back to being its own biome, which quietly
        exempts it from the adjacency rule -- so the mapping has to be complete
        for anything a topography can wear."""
        biomes = self.t["biomes"]
        owned = {x for spec in config.HEIGHTMAP_TOPOGRAPHIES.values()
                 for x in spec["sheets"]}
        for rel in owned:
            self.assertIn(rel, self.t["sheet_biomes"], rel)
            self.assertIn(self.t["sheet_biomes"][rel], biomes, rel)

    def test_every_topography_owns_at_least_two_biomes(self):
        """The precondition for the adjacency rule to be satisfiable at all.
        `small` failed this under the old three-material split, which is what
        made every terrace boundary on a small island green-on-green."""
        fams = self.t["sheet_biomes"]
        for name, spec in config.HEIGHTMAP_TOPOGRAPHIES.items():
            got = {fams[x] for x in spec["sheets"]}
            self.assertGreaterEqual(len(got), 2,
                                    f"{name} owns only {got}")

    def test_every_biome_declares_its_scatter_mix(self):
        """The fallback in `_biome_batches` is a floor, not a per-biome
        default: a biome that declared nothing would quietly scatter like an
        LD-8 room and the difference would only show up by eye."""
        for name, spec in self.t["biomes"].items():
            mix = spec.get("scatter")
            self.assertTrue(mix, f"{name} declares no scatter block")
            self.assertGreater(float(mix["per_1000"]), 0, name)
            weights = mix["weights"]
            # The four core kinds are mandatory; a biome may additionally name
            # a post kind (`sign` / `scarecrow`), which only some of them do --
            # a scarecrow belongs on farmland, not on a rock shelf.
            self.assertTrue({"tree", "rock", "pillar", "shrub"} <= set(weights),
                            f"{name} is missing a core kind")
            self.assertTrue(set(weights) <= {"tree", "rock", "pillar", "shrub",
                                             "sign", "scarecrow"},
                            f"{name} weights an unknown kind")
            self.assertGreater(sum(weights.values()), 0, name)

    def test_every_sheet_a_topography_names_is_a_real_file(self):
        for name, spec in config.HEIGHTMAP_TOPOGRAPHIES.items():
            for rel in spec["sheets"]:
                self.assertTrue(os.path.exists(os.path.join(ASSETS_DIR, rel)),
                                f"{name}: {rel}")

    def test_the_old_fixed_floor_map_is_gone(self):
        """It is superseded; leaving it would be two sources for one answer."""
        self.assertNotIn("heightmap_floor_sheets", self.t)

    def test_every_sheet_that_can_touch_a_terrace_declares_its_material(self):
        """An undeclared sheet is its own family, so it would be allowed to sit
        on top of a sheet it is indistinguishable from."""
        fams = self.t.get("sheet_biomes", {})
        for rel in {x for spec in config.HEIGHTMAP_TOPOGRAPHIES.values()
                    for x in spec["sheets"]}:
            self.assertIn(rel, fams, f"{rel} has no declared biome")


class PaletteRuleTests(unittest.TestCase):
    def test_adjacent_levels_never_share_a_sheet(self):
        for seed in range(40):
            for rid in range(6):
                pal = floor_palette(seed, rid, (0, 1, 2), POOL)
                got = [pal[k] for k in sorted(pal)]
                for a, b in zip(got, got[1:]):
                    self.assertNotEqual(a, b, f"seed {seed} room {rid}: {got}")

    def test_adjacent_levels_never_share_a_material(self):
        """The rule that matters. Two different files of the same material read
        as one continuous surface with a cliff line drawn through it."""
        for seed in range(40):
            for rid in range(6):
                pal = floor_palette(seed, rid, (0, 1, 2), POOL, family=FAMILY)
                got = [FAMILY(pal[k]) for k in sorted(pal)]
                for a, b in zip(got, got[1:]):
                    self.assertNotEqual(a, b, f"seed {seed} room {rid}: {got}")

    def test_level_zero_only_takes_a_sheet_that_can_meet_the_sea(self):
        """The one rule that is per-level rather than per-neighbour."""
        allowed = lambda level, sheet: level > 0 or sheet != "c.png"
        for seed in range(40):
            pal = floor_palette(seed, 0, (0, 1, 2), POOL, allowed=allowed)
            self.assertNotEqual(pal[0], "c.png", f"seed {seed}: {pal}")

    def test_a_topography_may_opt_out_of_that(self):
        """`boss` does, on purpose. Without the opt-out the check above would
        be the only behaviour and the experiment could not be run."""
        seen = {floor_palette(s, 0, (0,), POOL)[0] for s in range(40)}
        self.assertIn("c.png", seen)

    def test_it_is_stable_for_the_same_seed_and_room(self):
        a = floor_palette(7, 3, (0, 1, 2), POOL)
        b = floor_palette(7, 3, (0, 1, 2), POOL)
        self.assertEqual(a, b)

    def test_rooms_of_one_world_do_not_all_look_alike(self):
        seen = {tuple(sorted(floor_palette(11, rid, (0, 1, 2), POOL).items()))
                for rid in range(12)}
        self.assertGreater(len(seen), 1, "every island drew the same palette")

    def test_a_pool_of_one_degrades_instead_of_failing(self):
        """Nothing else is available, so the repeat is the only answer; it must
        not raise or loop."""
        pal = floor_palette(0, 0, (0, 1), ["only.png"])
        self.assertEqual(pal, {0: "only.png", 1: "only.png"})

    def test_an_empty_pool_yields_no_palette(self):
        self.assertEqual(floor_palette(0, 0, (0, 1), []), {})

    def test_it_does_not_touch_the_shared_rng(self):
        """The world's own stream must not shift because something asked for a
        palette, or the same seed would generate two different worlds."""
        import random
        random.seed(99)
        before = [random.random() for _ in range(5)]
        random.seed(99)
        floor_palette(1, 1, (0, 1, 2), POOL)
        self.assertEqual(before, [random.random() for _ in range(5)])


class BakedWorldTests(unittest.TestCase):
    """The painters have to agree with the palette, not just the module."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))


    def _sheets(self, seed):
        layout = W.layout(seed)
        return layout, TileSheets(get_assets(), layout.seed)

    def test_every_raised_level_of_every_island_gets_a_pool_sheet(self):
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        raised = 0
        for room in layout.rooms:
            if not room.grid:
                continue
            for level in {c.level for c in room.grid.values()
                          if c.kind == GROUND and c.level > 0}:
                self.assertIn(sheets.sheet_for(level, room.kind, room),
                              sheets.biome_pool)
                raised += 1
        self.assertGreater(raised, 0, "no raised terrace in this world to check")

    def test_level_zero_comes_from_the_topography_not_the_kind(self):
        """The change this rule made. `room_palettes` chose level 0 by what
        happens on an island; the topography chooses it by what shape the island
        is, and the two are orthogonal."""
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        for room in layout.rooms:
            if not room.grid:
                continue
            allowed = config.HEIGHTMAP_TOPOGRAPHIES[room.topography]["sheets"]
            self.assertIn(sheets.sheet_for(0, room.kind, room), allowed,
                          f"room {room.id} ({room.topography}) is wearing a "
                          f"sheet its topography does not own")

    def test_only_a_sheet_with_surf_may_meet_the_sea(self):
        """Unless the topography opts out, which `boss` does on purpose."""
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        for room in layout.rooms:
            if not room.grid:
                continue
            spec = config.HEIGHTMAP_TOPOGRAPHIES[room.topography]
            if spec.get("allow_beachless_shore"):
                continue
            self.assertTrue(
                sheets.has_shoreline(sheets.sheet_for(0, room.kind, room)),
                f"room {room.id} ({room.topography}) has a beachless shore "
                f"and did not ask for one")

    def test_two_islands_of_one_world_differ(self):
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        pals = {tuple(sorted(sheets.biome_palette(r).items()))
                for r in layout.rooms if r.grid and r.floor >= 0}
        self.assertGreater(len(pals), 1)

    def test_no_terrace_wears_the_biome_of_the_one_below_it(self):
        """Unconditional now, and it was not before.

        The split used to be three coarse materials -- grass / rock / sand --
        and a `small` island owns tilemaps 1-5, all five of which were "grass".
        Every terrace boundary on one was therefore green-on-green with a cliff
        line between, and the rule had nothing to reach for. Six biomes grouped
        on measured ground colour give it something: over twelve worlds, 108
        boundaries and **zero** with the same biome on both sides.
        """
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        checked = 0
        for room in layout.rooms:
            if not room.grid:
                continue
            below = None
            for level in sorted({c.level for c in room.grid.values()
                                 if c.kind == GROUND}):
                fam = sheets.biome_of(sheets.sheet_for(level, room.kind, room))
                if below is not None:
                    self.assertNotEqual(
                        fam, below,
                        f"room {room.id} ({room.topography}) level {level} is "
                        f"{fam} on top of {fam}")
                    checked += 1
                below = fam
        self.assertGreater(checked, 0)

    def test_a_call_with_no_room_falls_back_rather_than_guessing(self):
        """`sheet_for` with no room cannot know which island was meant, so it
        must not reach into a topography's sheets at all."""
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        self.assertEqual(sheets.sheet_for(0, "default"),
                         sheets.palettes.get("default", sheets.floor_sheet))
    def test_the_bake_reads_the_palette_rather_than_re_deriving_it(self):
        """The whole reason the palette moved into generation. Two modules
        working the same answer out from the same seed is how they come to
        disagree -- which this feature has already had happen once, when the
        adjacency rule compared filenames and the eye compared colours."""
        layout, sheets = self._sheets(21)
        for room in layout.rooms:
            if room.topography:
                self.assertIs(sheets.biome_palette(room), room.palette)


class ScatterMixTests(unittest.TestCase):
    """LD-10 step 3: obstacles are mixed and counted per biome.

    "A rocky layout for tilemap_6 needs a lot more rocks than trees." The mix
    belongs to the biome rather than to the island, because one volcanic island
    can wear wetland at the waterline, forest above it and rock on top, and the
    three should not scatter alike -- so the floor is split by terrace and each
    terrace scattered on its own terms.

    Asserted as proportions over a few seeds rather than exact counts: the
    weights are a draw, and placement rejects whatever will not fit, so the
    only claim worth pinning is that the biomes come out clearly different.
    """

    # Twelve seeds, not three. These are proportions over a weighted draw, and
    # the per-seed spread is wide: measured over thirty worlds the forest tree
    # share has a standard deviation of 0.060 and a range of 0.54 to 0.79.
    # Three worlds could not tell the design intent from that noise; twelve
    # pool to 0.673 against a thirty-seed 0.697, which is close enough to judge.
    SEEDS = tuple(range(21, 33))

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.tally = {}
        px = config.TILE_PX
        for seed in cls.SEEDS:
            layout = W.layout(seed)
            for o in layout.obstacles:
                for room in layout.rooms:
                    if not room.rect.collidepoint(o.pos.x, o.pos.y):
                        continue
                    cell = room.grid.get(
                        (int((o.pos.x - room.rect.left) // px),
                         int((o.pos.y - room.rect.top) // px)))
                    if cell is None:
                        break
                    fam = biomes.biome_of(room.palette.get(cell.level, ""))
                    cls.tally.setdefault(fam, collections.Counter())[o.kind] += 1
                    break


    def _share(self, fam, kinds):
        got = self.tally.get(fam)
        self.assertTrue(got, f"no {fam} terrace carried an obstacle")
        total = sum(got.values())
        self.assertGreater(total, 30, f"{fam} sample too small to judge")
        return sum(got[k] for k in kinds) / total

    def test_a_rock_terrace_is_mostly_stone(self):
        self.assertGreater(self._share("rock", ("rock", "pillar")), 0.7)

    def test_a_forest_terrace_is_mostly_trees(self):
        """Back at 0.7 -- and now with margin it did not have before.

        This briefly had to be lowered. The uphill keep-back rejects trees far
        more often than anything else (a canopy reaches four tiles north where
        a boulder reaches half of one), and the scatter used to re-draw the
        kind on *every* retry, so a slot that opened as a tree and failed came
        back as a boulder. That quietly re-weighted every biome toward whatever
        was easiest to place: measured over thirty worlds the forest share sat
        at 0.697 pooled with a 0.060 standard deviation, and sixteen of those
        thirty seeds fell below 0.7 individually.

        Drawing the kind once per slot instead (`world/gen/scatter.py`) fixed
        the mix rather than the threshold: 0.772 pooled, standard deviation
        0.040, three of thirty below 0.7. The remaining gap to the raw weights
        is the +25% tree top-up, which is not in them.
        """
        self.assertGreater(self._share("forest", ("tree",)), 0.7)

    def test_the_two_are_not_the_same_scatter_with_a_different_tileset(self):
        self.assertGreater(self._share("forest", ("tree",))
                           - self._share("rock", ("tree",)), 0.5)

    def test_an_unknown_sheet_asks_for_no_mix(self):
        """`None` is what makes the caller keep its own default rather than
        inventing weights for a tileset nobody has classified."""
        self.assertIsNone(scatter_mix("terrain/tiles/not_a_sheet.png"))
        self.assertIsNone(scatter_mix(""))

    def test_the_declared_mix_is_what_the_scatter_draws_from(self):
        sheet = next(k for k, v in get_assets().terrain["sheet_biomes"].items()
                     if v == "rock")
        kinds, weights, per_1000 = scatter_mix(sheet)
        want = get_assets().terrain["biomes"]["rock"]["scatter"]
        self.assertEqual(dict(zip(kinds, weights)),
                         {k: float(v) for k, v in want["weights"].items()})
        self.assertEqual(per_1000, float(want["per_1000"]))


class DecorBiomeTests(unittest.TestCase):
    """LD-10 step 4: a decoration may name the biomes it belongs to.

    Untagged means universal -- the default a new prop gets, and what keeps a
    terrace from being able to come out with nothing on it at all. The filter
    is per **terrace**: a volcanic island can be wetland at the waterline and
    rock at the summit, so "which props suit this island" is not a question
    with an answer.
    """

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.layout = W.layout(21)
        with open(os.path.join("data", "terrain.json"), encoding="utf-8") as fh:
            cls.t = json.load(fh)
        cls.props = [e for e in cls.t["decorations"]
                     if e.get("placement") == "room_interior"
                     and not e.get("collision")]


    def _mixed_room(self):
        """An island wearing more than one biome -- the only kind where the
        split can be observed to do anything."""
        for room in self.layout.rooms:
            if len({biomes.biome_of(s) for s in room.palette.values()}) > 1:
                return room, sorted(room.cells)
        self.fail("no island in this world wears two biomes")

    def test_an_island_is_split_into_its_terraces(self):
        room, floor = self._mixed_room()
        groups = decor._terraces(room, floor)
        self.assertGreater(len(groups), 1, "the island came back as one group")
        seen = set()
        for fam, cells in groups:
            self.assertTrue(cells)
            seen.update(cells)
            fam_of = decor._cell_biomes(room, cells)
            for cell in cells:
                self.assertEqual(fam_of.get(cell), fam)
        self.assertEqual(seen, set(floor), "a cell fell out of every terrace")

    def test_a_room_with_no_height_map_stays_one_group(self):
        """The legacy world has no palette, so it keeps the single unfiltered
        pass it has always had rather than being split against biomes it
        cannot have."""
        room = self.layout.rooms[0]
        bare = type(room)(99, (0, 0), room.rect.copy(), "combat",
                          cells=room.cells)
        floor = sorted(bare.cells)
        self.assertEqual(decor._cell_biomes(bare, floor), {})
        self.assertEqual(decor._terraces(bare, floor), [(None, floor)])

    def test_a_terrace_that_declares_no_rate_keeps_the_authored_counts(self):
        """No rates means no scaling: an unrated biome -- and every legacy
        room, which has no biome at all -- uses `per_room` exactly as written.
        The caller reads a missing tier out of this as 1.0."""
        legal = [{"per_room": [0, 2], "tier": decor.FEATURE}] * 4
        self.assertEqual(decor._tier_scales({}, None, 500, legal), {})
        self.assertEqual(
            decor._tier_scales({"biomes": {"x": {}}}, "x", 500, legal), {})

    def test_the_rate_sets_the_terrace_budget(self):
        """`per_room` was authored for 60-cell LD-8 rooms; the rate is what
        stretches it over a 500-cell terrace, with the authored counts as the
        weights that share that tier's budget out."""
        legal = [{"per_room": [0, 2], "tier": decor.FEATURE}] * 5
        terrain = {"biomes": {"x": {"decor": {"per_1000": {"feature": 60}}}}}
        # 500 cells at 60 per thousand = a budget of 30, over an expectation
        # of 5 -> every count in that tier multiplied by 6.
        got = decor._tier_scales(terrain, "x", 500, legal)
        self.assertAlmostEqual(got[decor.FEATURE], 6.0)

    def test_each_tier_is_priced_independently(self):
        """The reason tiers exist: with one budget the authored counts were
        shares of a single number, so making grass common could only take
        props away from the boulders."""
        legal = [{"per_room": [0, 2], "tier": decor.GROUND_COVER},
                 {"per_room": [0, 2], "tier": decor.FEATURE}]
        terrain = {"biomes": {"x": {"decor": {"per_1000": {
            "ground_cover": 250, "feature": 50}}}}}
        got = decor._tier_scales(terrain, "x", 1000, legal)
        self.assertAlmostEqual(got[decor.GROUND_COVER], 250.0)
        self.assertAlmostEqual(got[decor.FEATURE], 50.0)
        # ...and raising one leaves the other exactly where it was.
        terrain["biomes"]["x"]["decor"]["per_1000"]["ground_cover"] = 500
        again = decor._tier_scales(terrain, "x", 1000, legal)
        self.assertAlmostEqual(again[decor.GROUND_COVER], 500.0)
        self.assertAlmostEqual(again[decor.FEATURE], got[decor.FEATURE])

    def test_a_tier_a_biome_does_not_price_places_nothing(self):
        legal = [{"per_room": [0, 2], "tier": decor.LANDMARK}]
        terrain = {"biomes": {"x": {"decor": {"per_1000": {"feature": 50}}}}}
        self.assertEqual(
            decor._tier_scales(terrain, "x", 1000, legal)[decor.LANDMARK], 0.0)

    def test_every_tag_names_a_declared_biome(self):
        declared = set(self.t["biomes"])
        for e in self.props:
            for fam in e.get("biomes", ()):
                self.assertIn(fam, declared, f"{e['id']} tags {fam!r}")

    def test_every_biome_has_enough_props_to_look_furnished(self):
        """A biome nothing is tagged for would render as bare ground. Five is
        not a magic number -- it is roughly what one terrace draws before the
        `min_gap` spacing starts refusing places anyway."""
        for fam in self.t["biomes"]:
            legal = [e for e in self.props
                     if not e.get("biomes") or fam in e["biomes"]]
            self.assertGreaterEqual(len(legal), 5,
                                    f"{fam} has only {len(legal)} props")

    def test_the_stony_biomes_are_not_furnished_with_flora(self):
        """The point of the pass, stated as the thing that would have been
        wrong before it: fungi and pumpkins on a bare rock summit."""
        for prop in ("mushroom_small", "mushroom_big", "pumpkin_a", "bush_a"):
            e = next(x for x in self.props if x["id"] == prop)
            self.assertNotIn("rock", e.get("biomes", ()), prop)
            self.assertNotIn("sand", e.get("biomes", ()), prop)


class TreeGroupTests(unittest.TestCase):
    """LD-10: five tree rigs, two groups, one group per biome.

    The art falls into pines (`deco_tree_1/2/5`) and autumn crowns
    (`deco_tree_3/4`), and mixing them across a terrace was the last thing
    keeping an island from reading as one place. A biome names its group in the
    `biomes` table -- no new file, no new metadata layer -- and the obstacle
    carries the biome the scatter stamped on it, so the bake looks nothing up
    twice.
    """

    PINE = ["deco_tree_1", "deco_tree_2", "deco_tree_5"]
    AUTUMN = ["deco_tree_3", "deco_tree_4"]

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        with open(os.path.join("data", "terrain.json"), encoding="utf-8") as fh:
            cls.t = json.load(fh)


    def test_every_biome_picks_one_of_the_two_groups(self):
        for fam, spec in self.t["biomes"].items():
            self.assertIn(spec.get("trees"), (self.PINE, self.AUTUMN), fam)

    def test_the_groups_between_them_use_every_tree_rig(self):
        """`deco_tree_5` was unreachable before this: the global list holds
        five rigs and the variant is a `randint(1, 4)`, so `(variant - 1) % 5`
        never reached the last one. Groups of three and two are both shorter
        than the draw, so every rig can come up."""
        rigs = self.t["obstacle_decor"]["rigs"]["tree"]
        self.assertEqual(sorted(self.PINE + self.AUTUMN), sorted(rigs))

    def test_both_groups_are_in_use(self):
        got = {tuple(spec["trees"]) for spec in self.t["biomes"].values()}
        self.assertEqual(len(got), 2, "every biome picked the same group")

    def test_a_tree_is_skinned_from_its_own_terrace_group(self):
        layout = W.layout(41)
        gm = W.baked(41)
        if not gm._tiles_ok:
            self.skipTest("tileset missing")
        checked = 0
        for i, o in enumerate(gm.obstacles):
            if o.kind != "tree" or not o.biome:
                continue
            want = self.t["biomes"][o.biome]["trees"]
            rig = want[(o.variant - 1) % len(want)]
            meta = get_assets().rig(rig)
            self.assertEqual(gm._decos[i][3][0].get_size()[0],
                             self._skin_width(meta, o))
            checked += 1
        self.assertGreater(checked, 0, "no tree carried a biome")

    def _skin_width(self, meta, o):
        conf = self.t["obstacle_decor"]
        fw = meta["frame"][0]
        footprint = float(meta.get("footprint") or fw)
        draw_r = float(conf.get("render_radius", {}).get(o.kind, o.radius))
        scale = (2.0 * draw_r * float(conf.get("size_boost", 1.25))) / footprint
        return max(1, round(fw * scale))

    def test_the_stony_biomes_grow_stumps_where_the_trees_were(self):
        """Trees are reduced rather than banned -- a lone pine on a boulder
        field is fine -- and the dead ones stand in for them."""
        trees = {fam: spec["scatter"]["weights"]["tree"]
                 for fam, spec in self.t["biomes"].items()}
        for stony in ("rock", "sand"):
            for other in ("meadow", "forest", "drab", "wetland"):
                self.assertLess(trees[stony], trees[other],
                                f"{stony} grows as many trees as {other}")
            self.assertGreater(trees[stony], 0, f"{stony} banned trees outright")
        stumps = [e for e in self.t["decorations"] if e["id"].startswith("stump")]
        self.assertTrue(stumps)
        for e in stumps:
            self.assertIn("rock", e["biomes"], e["id"])
            self.assertIn("sand", e["biomes"], e["id"])


if __name__ == "__main__":
    unittest.main()
