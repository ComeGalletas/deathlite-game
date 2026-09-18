"""`data/enemies/spawn_tables.json` loads, is sound, and is checked (spawn master S2).

The shipped tables are read through the content loader exactly as the game
reads them; the malformed ones are built by hand from a copy of the shipped
data with one thing wrong, so each check is exercised on its own.
"""
import copy
import unittest

from game.content import get_content
from spawn.tables import SpawnTables, TableError


def _shipped() -> dict:
    return copy.deepcopy(get_content().spawn_tables._data)


class ShippedTablesTests(unittest.TestCase):
    def test_the_shipped_tables_load_through_content(self):
        t = get_content().spawn_tables
        self.assertIsInstance(t, SpawnTables)
        self.assertEqual(SpawnTables.validate(t._data, set(get_content().enemies)), [])

    def test_every_enemy_the_tables_name_exists(self):
        content = get_content()
        for eid in content.spawn_tables.enemy_ids():
            self.assertIn(eid, content.enemies)

    def test_the_phases_cover_the_whole_run_in_order(self):
        phases = get_content().spawn_tables.phases()
        untils = [p["until"] for p in phases]
        self.assertEqual(untils, sorted(untils))
        self.assertGreaterEqual(untils[-1], 1.0)
        self.assertEqual(phases[0]["types"], {"skull": 1.0})   # the calm opening

    def test_phase_lookup_by_run_fraction(self):
        t = get_content().spawn_tables
        self.assertIs(t.phase_at(0.0), t.phases()[0])
        self.assertIs(t.phase_at(0.199), t.phases()[0])
        self.assertIs(t.phase_at(0.20), t.phases()[1])
        self.assertIs(t.phase_at(1.0), t.phases()[-1])
        self.assertIs(t.phase_at(5.0), t.phases()[-1])          # a run that overstays

    def test_a_difficulty_without_its_own_phases_plays_the_shared_ones(self):
        t = get_content().spawn_tables
        for level in ("normal", "fast", "super_fast", "made_up"):
            self.assertIs(t.phases(level), t.phases())

    def test_a_difficulty_with_its_own_phases_replaces_them(self):
        data = _shipped()
        own = [{"until": 1.0, "interval": [0.5, 0.5], "pack": [1, 1], "elite": 0.0,
                "types": {"turtle": 1.0}}]
        data["difficulty"]["fast"] = {"phases": own}
        t = SpawnTables(data, enemy_ids=get_content().enemies)
        self.assertEqual(t.phases("fast"), own)
        self.assertIs(t.phases("normal"), t.phases())
        self.assertEqual(t.phase_at(0.5, "fast")["types"], {"turtle": 1.0})

    def test_groups_are_looked_up_by_name(self):
        t = get_content().spawn_tables
        self.assertEqual(t.group("dark")["common_range"], [5, 30])
        self.assertIn("skull", t.group("dark")["commons"])
        with self.assertRaises(TableError):
            t.group("nope")

    def test_the_declared_groups_are_all_present(self):
        """The table's own contents. Which of them are *usable*, and the two
        pools the draw reads, are the roster's business since G2a -- see
        `test_roster.py`."""
        t = get_content().spawn_tables
        self.assertEqual(set(t.groups),
                         {"dark", "swarm", "marine", "gnomes", "goblin",
                          "wild_beasts"})
        self.assertTrue(all(g.get("commons") for g in t.groups.values()))


class ValidationTests(unittest.TestCase):
    def _bad(self, mutate) -> list:
        data = _shipped()
        mutate(data)
        return SpawnTables.validate(data, set(get_content().enemies))

    def test_an_unknown_enemy_in_a_phase_fails(self):
        def m(d): d["phases"][2]["types"]["dragon"] = 1.0
        bad = self._bad(m)
        self.assertTrue(any("dragon" in b for b in bad), bad)

    def test_an_unknown_elite_slot_still_fails(self):
        """`elites` (the old default / rare slot) is still checked at load.
        The *groups* are not -- see the next test."""
        def m(d): d["elites"]["rare"] = "titan"
        self.assertTrue(any("titan" in b for b in self._bad(m)))

    def test_bad_group_members_do_not_refuse_to_load(self):
        """G2a (owner, 2026-09-17). A corrupt or inadequate group must cost
        the offending enemy or group, not the run, so none of these is a
        load error any more. `spawn/roster.py` skips or demotes them once
        per run and logs each decision; `test_roster.py` pins what each one
        costs.
        """
        cases = {
            "an enemy that does not exist":
                lambda d: d["groups"]["dark"]["commons"].__setitem__("ghost", 1.0),
            "a zero weight":
                lambda d: d["groups"]["dark"]["commons"].__setitem__("skull", 0),
            "an empty half":
                lambda d: d["groups"]["dark"].__setitem__("commons", {}),
            "a backwards span":
                lambda d: d["groups"]["dark"].__setitem__("common_range", [9, 4]),
            "a zero elite step":
                lambda d: d["groups"]["goblin"].__setitem__("elite_step", 0),
            "an elite among the commons":
                lambda d: d["groups"]["dark"]["commons"].__setitem__("bear", 1.0),
            "a non-elite among the elites":
                lambda d: d["groups"]["goblin"]["elites"].__setitem__("skull", 1.0),
        }
        for label, mutate in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self._bad(mutate), [], label)

    def test_a_missing_groups_section_is_still_fatal(self):
        """The one thing that stays a load error: there is no enemy to skip
        and no company could be built either way."""
        def gone(d): d.pop("groups")
        self.assertTrue(any("`groups`" in b for b in self._bad(gone)))

        def empty(d): d["groups"] = {}
        self.assertTrue(any("`groups`" in b for b in self._bad(empty)))

    def test_the_cooldown_ladder_is_checked(self):
        def missing(d): d["cooldowns"].pop("elite_decay")
        self.assertTrue(any("`elite_decay`" in b for b in self._bad(missing)))

        def negative(d): d["cooldowns"]["common"] = -1
        self.assertTrue(any("`common`" in b for b in self._bad(negative)))

        def floor_above(d): d["cooldowns"]["common_floor"] = 9.0
        self.assertTrue(any("above" in b for b in self._bad(floor_above)))

        def zero_step(d): d["cooldowns"]["step_seconds"] = 0
        self.assertTrue(any("`step_seconds`" in b for b in self._bad(zero_step)))

    def test_phases_must_increase_and_reach_the_end(self):
        def m(d): d["phases"][1]["until"] = 0.1
        self.assertTrue(any("increase" in b for b in self._bad(m)))

        def m2(d): d["phases"] = d["phases"][:2]
        self.assertTrue(any("before the run does" in b for b in self._bad(m2)))

    def test_pack_and_interval_shapes(self):
        def m(d):
            d["phases"][0]["pack"] = [3, 1]
            d["phases"][1]["interval"] = [1.0]
        bad = self._bad(m)
        self.assertTrue(any("`pack`" in b for b in bad), bad)
        self.assertTrue(any("`interval`" in b for b in bad), bad)

    def test_a_bad_pacing_base_is_refused(self):
        def m(d): d["pacing"]["base"] = 0
        self.assertTrue(any("`base`" in b for b in self._bad(m)))

        def m2(d): d["pacing"]["base"] = "five"
        self.assertTrue(any("`base`" in b for b in self._bad(m2)))

    def test_a_broken_table_refuses_to_construct(self):
        data = _shipped()
        data["phases"][0]["types"] = {"dragon": 1.0}
        with self.assertRaises(TableError):
            SpawnTables(data, enemy_ids=get_content().enemies)

    def test_without_an_enemy_list_only_the_shape_is_checked(self):
        data = _shipped()
        data["phases"][0]["types"] = {"dragon": 1.0}
        self.assertEqual(SpawnTables.validate(data), [])


if __name__ == "__main__":
    unittest.main()
