"""`spawn/roster.py`: what a company may be drawn from, resolved per run.

Owner, 2026-09-17: "do a simple check before the spawn decides. simple
function to read the list of enemies in a certain group. if one of them
contains elite metadata then check a flag instead of requiring at load ...
in case the data is corrupted or simply inadequate skip whichever enemy or
group contains it".

So the contract is a failure mode, and these tests are mostly about what a
given corruption *costs*. Two rules sit underneath:

* **nothing spawnable is thrown away** -- "if the available data is enough
  to spawn it as a common enemy do it", so a mis-filed body is demoted
  rather than dropped;
* **`is_elite` is the authority** -- the `"elite"` string some enemies carry
  in `tags` is never consulted.

The shipped data is expected to resolve cleanly with no notes at all; every
other case here is deliberately broken input.
"""
import copy
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.content import get_content
from spawn.roster import ResolvedGroup, Roster, resolve_groups


def _enemies() -> dict:
    return get_content().enemies


def _groups() -> dict:
    return copy.deepcopy(get_content().spawn_tables.groups)


def _resolve(mutate=None) -> Roster:
    groups = _groups()
    if mutate is not None:
        mutate(groups)
    return resolve_groups(groups, _enemies())


class ShippedTests(unittest.TestCase):
    def test_the_shipped_groups_resolve_cleanly(self):
        r = _resolve()
        self.assertEqual(r.notes, [], "the shipped data should need no fixing")
        self.assertEqual(set(r.names()),
                         {"dark", "swarm", "marine", "gnomes", "goblin",
                          "wild_beasts"})

    def test_the_two_pools_are_separate_and_cover_everything(self):
        r = _resolve()
        common, elite = r.names(elite=False), r.names(elite=True)
        self.assertEqual(set(common) | set(elite), set(r.names()))
        self.assertEqual(set(common) & set(elite), set())
        self.assertEqual(elite, ["goblin", "wild_beasts"])

    def test_every_resolved_member_is_a_real_enemy_on_the_right_side(self):
        r, elites = _resolve(), {e for e, d in _enemies().items() if d.get("is_elite")}
        for name in r.names():
            g = r.get(name)
            with self.subTest(group=name):
                self.assertTrue(g.commons)
                for eid, w in g.commons.items():
                    self.assertIn(eid, _enemies())
                    self.assertGreater(w, 0)
                for eid in g.elites:
                    self.assertIn(eid, elites, f"{eid} is not is_elite")

    def test_the_ladder_climbs_by_its_step_and_stops_at_the_ceiling(self):
        r = _resolve()
        for name in r.names(elite=True):
            g = r.get(name)
            lo, hi = g.elite_range
            with self.subTest(group=name):
                self.assertEqual(g.elite_count(0), lo)
                self.assertEqual(g.elite_count(1), lo + g.elite_step)
                self.assertEqual(g.elite_count(999), hi)
                seen = [g.elite_count(s) for s in range(12)]
                self.assertEqual(seen, sorted(seen), "the ladder went backwards")
        for name in r.names(elite=False):
            self.assertEqual(r.get(name).elite_count(999), 0, name)

    def test_a_negative_step_is_treated_as_the_start_of_the_ladder(self):
        g = _resolve().get("goblin")
        self.assertEqual(g.elite_count(-5), g.elite_count(0))


class RankTests(unittest.TestCase):
    """The pair the owner asked about, and they resolve differently."""

    def test_a_non_elite_among_the_elites_is_demoted_not_dropped(self):
        r = _resolve(lambda g: g["goblin"]["elites"].__setitem__("skull", 1.0))
        goblin = r.get("goblin")
        self.assertIn("skull", goblin.commons, "it should still spawn")
        self.assertNotIn("skull", goblin.elites, "but never as an elite")
        self.assertTrue(any("moved" in n and "skull" in n for n in r.notes), r.notes)

    def test_the_elite_count_still_means_real_elites(self):
        """The reason a demotion beats keeping it in place: an elite company
        is *guaranteed* elites, so a plain body must not fill a slot."""
        r = _resolve(lambda g: g["goblin"]["elites"].__setitem__("skull", 99.0))
        elites = {e for e, d in _enemies().items() if d.get("is_elite")}
        self.assertTrue(set(r.get("goblin").elites) <= elites)

    def test_an_elite_among_the_commons_stays_and_spawns_as_one(self):
        r = _resolve(lambda g: g["dark"]["commons"].__setitem__("bear", 1.0))
        dark = r.get("dark")
        self.assertIn("bear", dark.commons, "it is a spawnable body")
        self.assertFalse(dark.has_elites, "but dark is still a common group")
        self.assertTrue(any("bear" in n for n in r.notes), r.notes)

    def test_the_elite_tag_is_not_consulted_only_the_flag(self):
        """An enemy carrying the `"elite"` string in `tags` but no
        `is_elite` flag is still a common. One source of truth."""
        enemies = copy.deepcopy(_enemies())
        enemies["skull"] = {**enemies["skull"], "tags": ["basic", "elite"]}
        groups = _groups()
        groups["goblin"]["elites"]["skull"] = 1.0
        r = resolve_groups(groups, enemies)
        self.assertNotIn("skull", r.get("goblin").elites)
        self.assertIn("skull", r.get("goblin").commons)

    def test_a_member_listed_in_both_halves_is_not_duplicated(self):
        def m(g):
            g["goblin"]["commons"]["skull"] = 2.0
            g["goblin"]["elites"]["skull"] = 9.0
        r = _resolve(m)
        goblin = r.get("goblin")
        self.assertEqual(goblin.commons["skull"], 2.0, "the common weight wins")
        self.assertNotIn("skull", goblin.elites)


class SkipTests(unittest.TestCase):
    """What each corruption costs. Nothing here may raise."""

    def test_an_unknown_enemy_costs_only_itself(self):
        r = _resolve(lambda g: g["dark"]["commons"].__setitem__("dragon", 1.0))
        self.assertNotIn("dragon", r.get("dark").commons)
        self.assertIn("skull", r.get("dark").commons)
        self.assertEqual(len(r.names()), 6)

    def test_a_weight_that_is_not_positive_costs_only_itself(self):
        for weight in (0, -3, "heavy", None, True):
            with self.subTest(weight=weight):
                r = _resolve(lambda g, w=weight:
                             g["dark"]["commons"].__setitem__("skull", w))
                self.assertNotIn("skull", r.get("dark").commons)
                self.assertIsNotNone(r.get("dark"), "the group survives")

    def test_a_malformed_common_range_costs_the_group(self):
        for span in ([9, 4], [0, 5], "5-30", [5], None, [1.5, 3.0]):
            with self.subTest(span=span):
                r = _resolve(lambda g, s=span: g["dark"].__setitem__("common_range", s))
                self.assertIsNone(r.get("dark"))
                self.assertEqual(len(r.names()), 5, "only dark is lost")

    def test_an_empty_commons_half_costs_the_group(self):
        r = _resolve(lambda g: g["marine"].__setitem__("commons", {}))
        self.assertIsNone(r.get("marine"))
        self.assertEqual(len(r.names()), 5)

    def test_a_broken_elite_ladder_leaves_a_common_only_group(self):
        for mutate in (lambda g: g["goblin"].__setitem__("elite_step", 0),
                       lambda g: g["goblin"].__setitem__("elite_range", [9, 2]),
                       lambda g: g["goblin"].__setitem__("elite_range", None),
                       lambda g: g["goblin"].__setitem__("elites", {"ghost": 1.0})):
            with self.subTest(mutate=mutate):
                r = _resolve(mutate)
                self.assertIsNotNone(r.get("goblin"), "the group must survive")
                self.assertFalse(r.get("goblin").has_elites)
                self.assertEqual(r.names(elite=True), ["wild_beasts"])
                self.assertIn("goblin", r.names(elite=False))

    def test_a_group_that_is_not_an_object_is_skipped(self):
        r = _resolve(lambda g: g.__setitem__("dark", "nonsense"))
        self.assertIsNone(r.get("dark"))
        self.assertEqual(len(r.names()), 5)

    def test_comment_keys_are_not_groups(self):
        r = _resolve(lambda g: g.__setitem__("_note", "a comment"))
        self.assertNotIn("_note", r.names())
        self.assertEqual(len(r.names()), 6)

    def test_losing_every_group_is_reported_and_still_does_not_raise(self):
        r = _resolve(lambda g: [g[k].__setitem__("commons", {}) for k in list(g)])
        self.assertEqual(r.names(), [])
        self.assertFalse(r)
        self.assertTrue(any("no enemies will spawn" in n for n in r.notes), r.notes)

    def test_no_groups_at_all_is_reported_and_still_does_not_raise(self):
        for groups in ({}, None, "nonsense", []):
            with self.subTest(groups=groups):
                r = resolve_groups(groups, _enemies())
                self.assertEqual(r.names(), [])
                self.assertTrue(r.notes)


class NoteTests(unittest.TestCase):
    def test_every_decision_leaves_a_note_naming_the_group(self):
        """The owner asked for skips to be logged, so nothing may be
        silent. The master emits these as warnings once, at run start."""
        r = _resolve(lambda g: g["dark"]["commons"].__setitem__("dragon", 1.0))
        self.assertEqual(len(r.notes), 1)
        self.assertIn("dark", r.notes[0])
        self.assertIn("dragon", r.notes[0])

    def test_the_master_logs_the_notes_when_it_is_built(self):
        """Through the real path: a master built on tables with a bad group
        warns as it resolves, rather than the caller having to ask."""
        import random
        from spawn import SpawnMaster
        from spawn.budget import SpawnDirector
        from spawn.tables import SpawnTables
        from tests.spawn.fakehost import FakeHost

        data = copy.deepcopy(get_content().spawn_tables._data)
        data["groups"]["dark"]["commons"]["dragon"] = 1.0     # no such enemy
        data["groups"]["marine"]["common_range"] = [30, 5]    # backwards
        tables = SpawnTables(data, enemy_ids=_enemies())      # must not raise
        director = SpawnDirector(run_duration=600.0, rng=random.Random(1),
                                 tables=tables)
        with self.assertLogs("spawn.master", level="WARNING") as caught:
            m = SpawnMaster(FakeHost(), director, tables=tables)
        joined = "\n".join(caught.output)
        self.assertIn("dragon", joined)
        self.assertIn("marine", joined)
        # and the run goes on with what was left
        self.assertIsNone(m.roster.get("marine"))
        self.assertIn("dark", m.roster.names())
        self.assertNotIn("dragon", m.roster.get("dark").commons)


class ResolvedGroupTests(unittest.TestCase):
    def test_a_group_with_no_elites_never_reports_any(self):
        g = ResolvedGroup("plain", {"skull": 1.0}, (2, 4))
        self.assertFalse(g.has_elites)
        self.assertEqual(g.elite_count(99), 0)

    def test_the_master_composes_nothing_for_an_unusable_group(self):
        import random
        from spawn import SpawnMaster
        from spawn.budget import SpawnDirector
        from tests.spawn.fakehost import FakeHost
        host = FakeHost()
        m = SpawnMaster(host, SpawnDirector(run_duration=600.0, rng=random.Random(1)))
        m.roster = resolve_groups({"dark": "nonsense"}, _enemies())
        self.assertEqual(m.compose("dark"), [])
        self.assertEqual(m.spawn_group("dark"), [])
        self.assertEqual(len(host.live), 0)


if __name__ == "__main__":
    unittest.main()
