"""The `unused` category: enemies benched from the run without being deleted.

Owner, 2026-09-17: "make an unused category for currently unused enemies. move
the current panda enemy there. dont delete the references in the code, just
'disable' it."

So the contract has two halves, and both are worth pinning. The director must
never roll a benched enemy; and everything else about it must survive -- its
block, its art, its band weights, the group that lists it, `spawn_at`, and
every test that builds one directly. A benched enemy is one string away from
coming back.

**The shipped list is empty as of G1** (owner, 2026-09-17): Stoutpaw was
unbenched to join the Wild beasts group, and nothing is benched today. That
would leave every assertion here vacuous, so the mechanism is exercised
against a *synthetic* table instead -- one that benches the panda exactly as
the shipped table used to -- and the shipped table is checked only for the
things that must hold whatever is or is not in the list. The feature stays
one string away from being needed again, and it stays tested.
"""
import copy
import json
import os
import random
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.content import get_content
from spawn.budget import SpawnDirector
from spawn.tables import SpawnTables, TableError

DATA = Path(__file__).resolve().parents[2] / "data" / "enemies"
BENCHED = "panda"          # the synthetic bench, not the shipped one
GROUP = "wild_beasts"      # the group Stoutpaw joined in G1


def _raw():
    return json.loads((DATA / "spawn_tables.json").read_text(encoding="utf-8"))


def _tables(**over):
    data = copy.deepcopy(_raw())
    data.update(over)
    return SpawnTables(data)


class ShippedTests(unittest.TestCase):
    """What must hold of the shipped table whatever its list contains. These
    pass trivially while it is empty and start biting the moment something is
    benched that a band or a group still needs."""

    @classmethod
    def setUpClass(cls):
        cls.content = get_content()
        cls.tables = cls.content.spawn_tables

    def test_nothing_is_benched_today(self):
        # G1: Stoutpaw came back and the list emptied. If this ever fails,
        # the rest of this module is the place to look for what it costs.
        self.assertEqual(set(self.tables.unused), set())

    def test_no_group_member_can_be_a_benched_enemy(self):
        for name in self.tables.groups:
            with self.subTest(group=name):
                g = self.tables.group(name)
                members = set(g.get("commons", {})) | set(g.get("elites", {}))
                self.assertFalse(members & self.tables.unused)

    def test_the_unbenched_stoutpaw_is_rollable_again(self):
        """The other side of G1: unbenching is one string, and this is what
        that string bought. Since G2 it is a Wild beasts common."""
        self.assertNotIn(BENCHED, self.tables.unused)
        self.assertIn(BENCHED, self.tables.group(GROUP)["commons"])


class MechanismTests(unittest.TestCase):
    """The filtering itself, against a table that benches the panda. This is
    what the shipped table used to prove and no longer can."""

    @classmethod
    def setUpClass(cls):
        cls.tables = _tables(unused=[BENCHED])
        cls.raw = _raw()

    def test_the_benched_enemy_is_listed(self):
        self.assertIn(BENCHED, self.tables.unused)

    def test_a_group_that_lists_it_survives_short(self):
        """Wild beasts lists the panda; the group keeps working without it."""
        g = self.tables.group(GROUP)
        self.assertNotIn(BENCHED, g["commons"])
        self.assertTrue(g["commons"], "the group emptied")
        self.assertTrue(g["elites"], "the elites were filtered too")

    def test_the_weights_are_filtered_not_rewritten(self):
        """Disabled, not deleted: the numbers stay on disk, so re-enabling is
        removing one string rather than re-deriving them."""
        self.assertIn(BENCHED, self.raw["groups"][GROUP]["commons"])
        self.assertGreater(self.raw["groups"][GROUP]["commons"][BENCHED], 0)

    def test_clearing_the_list_brings_it_straight_back(self):
        back = _tables(unused=[])
        self.assertIn(BENCHED, back.group(GROUP)["commons"])


class SurvivalTests(unittest.TestCase):
    """The "don't delete anything" half. Stoutpaw is live again, so these are
    no longer about a bench -- they are the plain requirement that a rostered
    enemy has a block and art that load."""

    @classmethod
    def setUpClass(cls):
        cls.content = get_content()

    def test_the_enemy_block_is_intact(self):
        self.assertIn(BENCHED, self.content.enemies)
        self.assertEqual(self.content.enemies[BENCHED]["name"], "Stoutpaw")

    def test_its_art_loads(self):
        from game.assets import get_assets
        import pygame
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        assets = get_assets()
        self.assertIn(BENCHED, self.content.sprites)
        for anim in ("idle", "walk", "attack"):
            self.assertGreater(assets.frame_count(BENCHED, anim), 0)


class ValidationTests(unittest.TestCase):
    """Benching is tuning, but it can express things that are table errors.
    Each is named rather than left to fail later as an empty draw."""

    def test_an_unknown_id_cannot_be_benched(self):
        problems = SpawnTables.validate(
            {**_raw(), "unused": ["no_such_enemy"]}, {"skull", BENCHED})
        self.assertTrue(any("unknown enemy" in p for p in problems), problems)

    def test_benching_a_whole_half_costs_the_group_not_the_run(self):
        """G2a (owner, 2026-09-17): benching that leaves a half with nothing
        used to be a load error. It now loads, and the roster drops what it
        cannot use -- the group when its commons are gone, only the elite
        half when its elites are."""
        from spawn.roster import resolve_groups
        enemies = get_content().enemies

        t = _tables(unused=["gnoll", "panda"])          # Wild beasts commons
        r = resolve_groups(t.groups, enemies)
        self.assertIsNone(r.get("wild_beasts"), "the group should be skipped")
        self.assertEqual(len(r.names()), 5, "the others are untouched")
        self.assertTrue(any("wild_beasts" in n for n in r.notes), r.notes)

        # G3 retired the top-level `elites` slot that used to make this
        # case unreachable through `unused`, so it can be asserted now.
        t = _tables(unused=["hex_shaman", "troll"])     # Goblin elites
        r = resolve_groups(t.groups, enemies)
        self.assertIsNotNone(r.get("goblin"), "the group survives")
        self.assertFalse(r.get("goblin").has_elites, "as common-only")
        self.assertEqual(r.names(elite=True), ["wild_beasts"])

    def test_the_list_must_be_strings(self):
        problems = SpawnTables.validate({**_raw(), "unused": [7]}, None)
        self.assertTrue(any("`unused`" in p for p in problems), problems)

    def test_tables_with_no_unused_key_are_still_valid(self):
        data = _raw()
        data.pop("unused", None)
        t = SpawnTables(data)
        self.assertEqual(t.unused, frozenset())
        self.assertIn(BENCHED, t.group(GROUP)["commons"])


class DirectorTests(unittest.TestCase):
    """End to end: a run on a table that benches an enemy never seats it,
    while the shipped table does. Driven through the master, because since
    G3 the director names a *group* and the master composes the bodies --
    there is no id sequence to inspect on the director alone."""

    def _bodies(self, tables, seed: int, seconds: float = 700.0) -> set:
        import pygame
        from spawn import SpawnMaster
        from tests.spawn.fakehost import FakeHost
        host = FakeHost(seed=seed)
        director = SpawnDirector(run_duration=600.0, rng=random.Random(seed),
                                 tables=tables)
        m = SpawnMaster(host, director, tables=tables)
        t, dt = 0.0, 1 / 30
        while t < seconds:
            m.update(dt)
            t += dt
            host.elapsed = t
        return {e.enemy_id for e in host.live}

    def test_a_long_run_never_seats_a_benched_enemy(self):
        seen = self._bodies(_tables(unused=[BENCHED]), 7)
        self.assertTrue(seen, "nothing spawned at all")
        self.assertNotIn(BENCHED, seen)

    def test_the_same_run_does_seat_it_once_it_is_unbenched(self):
        """Without this the test above could pass because the run never
        reaches the group the panda belongs to. Stoutpaw is a Wild beasts
        common, and Wild beasts is an elite group behind the one-minute
        unlock and the cap gate, so the window has to be long enough for
        one of its companies to actually land -- which is why both halves
        of this pair use the same 700 s."""
        seen = self._bodies(_tables(unused=[]), 7)
        self.assertIn(BENCHED, seen)


if __name__ == "__main__":
    unittest.main()
