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

    def test_groups_are_looked_up_by_name(self):
        """The lookup, not the tuning. The spans are balance numbers and
        have already moved once (dark went [5, 30] -> [10, 30] on
        2026-09-19), so what is pinned here is that a name resolves to a
        group with the right shape and an unknown name raises."""
        t = get_content().spawn_tables
        dark = t.group("dark")
        lo, hi = dark["common_range"]
        self.assertTrue(1 <= lo <= hi)
        self.assertIn("skull", dark["commons"])
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
    """G3 left almost nothing fatal here. The phase, elite-slot and pacing
    checks went with their sections, and the group members are resolved per
    run instead (`test_roster.py`), so what remains is the shape of the two
    sections a run cannot start without."""

    def _bad(self, mutate) -> list:
        data = _shipped()
        mutate(data)
        return SpawnTables.validate(data, set(get_content().enemies))

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


if __name__ == "__main__":
    unittest.main()
