"""The `unused` category: enemies benched from the run without being deleted.

Owner, 2026-09-17: "make an unused category for currently unused enemies. move
the current panda enemy there. dont delete the references in the code, just
'disable' it."

So the contract has two halves, and both are worth pinning. The director must
never roll a benched enemy; and everything else about it must survive -- its
block, its art, its band weights, the group that lists it, `spawn_at`, and
every test that builds one directly. A benched enemy is one string away from
coming back.
"""
import copy
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.content import get_content
from spawn.tables import SpawnTables, TableError

DATA = Path(__file__).resolve().parents[2] / "data" / "enemies"


def _raw():
    return json.loads((DATA / "spawn_tables.json").read_text(encoding="utf-8"))


def _tables(**over):
    data = copy.deepcopy(_raw())
    data.update(over)
    return SpawnTables(data)


class ShippedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = get_content()
        cls.tables = cls.content.spawn_tables
        cls.raw = _raw()

    def test_the_panda_is_benched(self):
        self.assertIn("panda", self.tables.unused)

    def test_no_band_can_roll_a_benched_enemy(self):
        for i, phase in enumerate(self.tables.phases(), 1):
            with self.subTest(band=i):
                self.assertFalse(set(phase["types"]) & self.tables.unused)

    def test_no_difficulty_override_can_roll_one_either(self):
        for level in ("normal", "fast", "super_fast"):
            for i, phase in enumerate(self.tables.phases(level), 1):
                with self.subTest(level=level, band=i):
                    self.assertFalse(set(phase["types"]) & self.tables.unused)

    def test_no_group_follower_can_be_a_benched_enemy(self):
        """`artillery` lists the panda; the group survives, short."""
        for name in self.tables.groups:
            with self.subTest(group=name):
                followers = self.tables.group(name).get("followers", {})
                self.assertFalse(set(followers) & self.tables.unused)

    # --- the "don't delete anything" half ---------------------------------
    def test_the_enemy_block_is_untouched(self):
        self.assertIn("panda", self.content.enemies)
        self.assertEqual(self.content.enemies["panda"]["name"], "Stoutpaw")

    def test_its_art_is_untouched(self):
        from game.assets import get_assets
        import pygame
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        assets = get_assets()
        self.assertIn("panda", self.content.sprites)
        for anim in ("idle", "walk", "attack"):
            self.assertGreater(assets.frame_count("panda", anim), 0)

    def test_its_band_weights_are_still_written_down(self):
        """Disabled, not deleted: re-enabling is removing one string, not
        re-deriving the numbers."""
        weighted = [p["types"]["panda"] for p in self.raw["phases"]
                    if "panda" in p["types"]]
        self.assertTrue(weighted, "the panda's weights were deleted")

    def test_the_group_still_names_it(self):
        self.assertIn("panda", self.raw["groups"]["artillery"]["followers"])

    def test_clearing_the_list_brings_it_straight_back(self):
        back = _tables(unused=[])
        self.assertTrue(any("panda" in p["types"] for p in back.phases()))
        self.assertIn("panda", back.group("artillery")["followers"])


class IdentityTests(unittest.TestCase):
    """Filtering happens once, at construction. Callers compare phases by
    identity (`_phase(x) is _phase(y)`), so rebuilding them per lookup would
    break the director's tests in a way that is tedious to trace."""

    def test_a_phase_lookup_returns_the_same_object_every_time(self):
        t = get_content().spawn_tables
        self.assertIs(t.phase_at(0.5), t.phase_at(0.5))
        self.assertIs(t.phases()[-1], t.phase_at(1.0))


class ValidationTests(unittest.TestCase):
    """Benching is tuning, but it can express things that are table errors.
    Each is named rather than left to fail later as an empty draw."""

    def test_an_unknown_id_cannot_be_benched(self):
        problems = SpawnTables.validate(
            {**_raw(), "unused": ["no_such_enemy"]}, {"skull", "panda"})
        self.assertTrue(any("unknown enemy" in p for p in problems), problems)

    def test_benching_cannot_empty_a_band(self):
        with self.assertRaises(TableError) as caught:
            _tables(unused=["skull"])           # band 1 is skull-only
        self.assertIn("nothing left", str(caught.exception))

    def test_benching_cannot_orphan_a_group_leader(self):
        with self.assertRaises(TableError) as caught:
            _tables(unused=["hex_shaman"])      # leads `artillery`
        self.assertIn("leader", str(caught.exception))

    def test_benching_cannot_silence_the_elite_slot(self):
        for eid in ("bear", "troll"):
            with self.subTest(elite=eid):
                with self.assertRaises(TableError) as caught:
                    _tables(unused=[eid])
                self.assertIn("elites", str(caught.exception))

    def test_the_list_must_be_strings(self):
        problems = SpawnTables.validate({**_raw(), "unused": [7]}, None)
        self.assertTrue(any("`unused`" in p for p in problems), problems)

    def test_tables_with_no_unused_key_are_still_valid(self):
        data = _raw()
        data.pop("unused", None)
        t = SpawnTables(data)
        self.assertEqual(t.unused, frozenset())
        self.assertTrue(any("panda" in p["types"] for p in t.phases()))


class DirectorTests(unittest.TestCase):
    """End to end: a long scripted run never emits the benched enemy, but the
    master's direct entry points still seat one."""

    def test_a_long_run_never_rolls_the_panda(self):
        import random
        from spawn.budget import SpawnDirector
        d = SpawnDirector(run_duration=600.0, rng=random.Random(7))
        seen, t = set(), 0.0
        while t < 600.0:
            seen.update(d.update(1 / 30, t, 0))
            t += 1 / 30
        self.assertTrue(seen, "the director emitted nothing")
        self.assertNotIn("panda", seen)

    def test_roll_pack_never_produces_one_either(self):
        import random
        from spawn.budget import SpawnDirector
        d = SpawnDirector(run_duration=600.0, rng=random.Random(11))
        seen = set()
        for t in range(0, 600, 5):
            seen.update(d.roll_pack(float(t)))
        self.assertNotIn("panda", seen)
