"""`tools/verification/tier_audit.py` and the tiers in `tests/conftest.py`.

The tiers are assigned by path, so a new module that boots a `Game` lands in
`unit` -- the tier run on every save -- unless someone remembers to list it.
TST-006 found fourteen such modules (`test_run_hints.py` and
`test_key_marker.py` among them, each generating seed 1234 inside `unit`) and
five `world` modules that boot a `Game`. `SuiteTests` is the check that would
have caught every one; the rest pin what the audit reads, on source trees
small enough to see whole.
"""
from __future__ import annotations

import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import conftest
from tools.verification import tier_audit as A

# The primitives, where the audit expects them to be defined.
_REPO = {
    "game/__init__.py": "",
    "game/game.py": "class Game:\n    def __init__(self, save_path=None): pass\n",
    "game/states/__init__.py": "",
    "game/states/loading_state.py": "class LoadingState:\n    def __init__(self, game): pass\n",
    "game/states/playing/__init__.py": "",
    "game/states/playing/core/__init__.py": "",
    "game/states/playing/core/state.py": (
        "class PlayingState:\n"
        "    def __init__(self, game): pass\n"
        "    def enter(self, seed=None): pass\n"),
    "world/__init__.py": "",
    "world/gen/__init__.py": (
        "def generate_world(seed): pass\n"
        "def generate_world_steps(seed): pass\n"),
    "world/map.py": (
        "from world.gen import generate_world\n"
        "class GameMap:\n"
        "    def __init__(self, seed=None, *, layout=None): pass\n"),
    "tests/__init__.py": "",
    "tests/boot.py": (
        "def start_run(game, seed=None):\n"
        "    from game.states.loading_state import LoadingState\n"
        "    LoadingState(game)\n"),
    "tests/worlds.py": (
        "from world.map import GameMap\n"
        "SEEDS = (35, 7)\n"
        "def pinned(i): return SEEDS[i]\n"
        "def display(): pass\n"
        "def fresh(seed): return GameMap(seed=seed)\n"
        "def layout(seed): return fresh(seed)\n"),
    "tests/x/__init__.py": "",
}


class _Tree(unittest.TestCase):
    """A throwaway repo: the primitives above plus the modules a test adds."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        for rel, text in _REPO.items():
            self._write(rel, text)

    def _write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    def needs(self, source, tier_of=lambda nodeid: "unit"):
        """{Class::test: tier needed} for one module holding `source`."""
        self._write("tests/x/test_m.py", source)
        results = list(A.tests(A.Index(self.root), tier_of))
        return {t.nodeid.split("::", 1)[1]: t.need.tier for t in results}


class BootTests(_Tree):

    def test_constructing_a_game_in_set_up_class_is_integration(self):
        got = self.needs("""
            import unittest
            class T(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    from game.game import Game
                    cls.game = Game(save_path="s.json")
                def test_a(self): pass
        """)
        self.assertEqual(got, {"T::test_a": "integration"})

    def test_the_run_hints_shape_is_integration(self):
        """What `test_run_hints.py` and `test_key_marker.py` do: a module
        helper builds a Game and enters a PlayingState on a seed."""
        got = self.needs("""
            import unittest
            def _run(seed=1234):
                from game.game import Game
                from game.states.playing.core.state import PlayingState
                g = Game(save_path="s.json")
                p = PlayingState(g)
                p.enter(seed=seed)
                return p
            class StageTests(unittest.TestCase):
                def test_a(self):
                    _run()
        """)
        self.assertEqual(got, {"StageTests::test_a": "integration"})

    def test_a_helper_module_is_followed(self):
        got = self.needs("""
            import unittest
            from tests.boot import start_run
            class T(unittest.TestCase):
                def test_a(self):
                    start_run(object())
        """)
        self.assertEqual(got, {"T::test_a": "integration"})

    def test_self_methods_and_inherited_set_up_are_followed(self):
        got = self.needs("""
            import unittest
            import game.game as gg
            class _Base(unittest.TestCase):
                def setUp(self):
                    self.game = self._boot()
                def _boot(self):
                    return gg.Game()
            class A(_Base):
                def test_a(self): pass
            class B(_Base):
                def setUp(self):
                    super().setUp()
                def test_b(self): pass
        """)
        self.assertEqual(got, {"A::test_a": "integration",
                               "B::test_b": "integration"})

    def test_a_subclass_of_playing_state_boots(self):
        got = self.needs("""
            import unittest
            from game.states.playing.core.state import PlayingState
            class _Quiet(PlayingState):
                pass
            class T(unittest.TestCase):
                def test_a(self):
                    _Quiet(None)
        """)
        self.assertEqual(got, {"T::test_a": "integration"})

    def test_a_game_built_at_import_boots_every_class(self):
        got = self.needs("""
            import unittest
            from game.game import Game
            GAME = Game()
            class A(unittest.TestCase):
                def test_a(self): pass
            class B(unittest.TestCase):
                def test_b(self): pass
        """)
        self.assertEqual(got, {"A::test_a": "integration",
                               "B::test_b": "integration"})

    def test_a_fake_game_and_a_menu_enter_are_unit(self):
        got = self.needs("""
            import unittest
            class _Game:
                pass
            class _Menu:
                def enter(self, **kw): pass
            class T(unittest.TestCase):
                def test_a(self):
                    _Menu().enter(stats={}, game=_Game())
        """)
        self.assertEqual(got, {"T::test_a": "unit"})


class WorldTests(_Tree):

    def test_the_shared_worlds_are_world(self):
        got = self.needs("""
            import unittest
            from tests import worlds as W
            class T(unittest.TestCase):
                def test_a(self):
                    W.layout(W.pinned(0))
        """)
        self.assertEqual(got, {"T::test_a": "world"})

    def test_generate_world_under_an_alias_is_world(self):
        got = self.needs("""
            import unittest
            from world.gen import generate_world as gw
            class T(unittest.TestCase):
                def test_a(self):
                    gw(7)
        """)
        self.assertEqual(got, {"T::test_a": "world"})

    def test_a_game_map_without_a_seed_is_unit(self):
        got = self.needs("""
            import unittest
            from tests import worlds as W
            from world.map import GameMap
            class T(unittest.TestCase):
                def setUp(self):
                    W.display()
                def test_none(self):
                    GameMap(); GameMap(seed=None); GameMap(None)
                def test_layout(self):
                    GameMap(layout=object())
                def test_seeded(self):
                    GameMap(35)
        """)
        self.assertEqual(got, {"T::test_none": "unit", "T::test_layout": "unit",
                               "T::test_seeded": "world"})


class CollectionTests(_Tree):

    def test_only_testcases_are_collected_and_inherited_tests_count(self):
        got = self.needs("""
            import unittest
            from unittest import TestCase
            class Mixin:
                def test_mixin(self): pass
            class _Base(unittest.TestCase):
                def test_base(self): pass
            class Child(Mixin, _Base):
                def test_child(self): pass
            class Plain(TestCase):
                def test_plain(self): pass
        """)
        self.assertEqual(set(got), {
            "_Base::test_base", "Child::test_mixin", "Child::test_base",
            "Child::test_child", "Plain::test_plain"})


class GroupingTests(_Tree):
    """Register a module whole when every test in it agrees, class by class
    when it mixes pure and booting classes (as `test_fish_huts.py` does)."""

    SOURCE = """
        import unittest
        from game.game import Game
        class Pure(unittest.TestCase):
            def test_p(self): pass
        class Boots(unittest.TestCase):
            def test_b(self): Game()
            def test_c(self): Game()
    """

    def _grouped(self, source):
        self._write("tests/x/test_m.py", source)
        results = list(A.tests(A.Index(self.root), lambda nodeid: "unit"))
        return A.grouped(A.under(results), results)

    def test_a_mixed_module_is_named_by_class(self):
        self.assertEqual(self._grouped(self.SOURCE), {
            ("unit", "integration"): {
                "tests/x/test_m.py::Boots": ("Boots.test_b", "game.game.Game",
                                             "Game(")}})

    def test_a_uniform_module_is_named_whole(self):
        grouped = self._grouped(self.SOURCE.replace("def test_p(self): pass",
                                                    "def test_p(self): Game()"))
        self.assertEqual(list(grouped[("unit", "integration")]),
                         ["tests/x/test_m.py"])


class ConftestTierTests(unittest.TestCase):
    """`tier()` is what the collection hook marks with."""

    def test_an_unlisted_module_is_unit(self):
        self.assertEqual(conftest.tier("tests/playing/test_gold.py::T::test_a"), "unit")

    def test_a_class_prefix_claims_only_that_class(self):
        self.assertEqual(conftest.tier(
            "tests/render/test_biome.py::ScatterMixTests::test_x"), "sweep")
        self.assertEqual(conftest.tier(
            "tests/render/test_biome.py::PaletteRuleTests::test_x"), "world")

    def test_hand_built_grids_stay_unit_under_the_world_prefix(self):
        self.assertEqual(conftest.tier("tests/world/grids/test_x.py::T::test_a"), "unit")
        self.assertEqual(conftest.tier("tests/world/test_repair.py::T::test_a"), "world")

    def test_windows_separators_are_read_as_slashes(self):
        self.assertEqual(conftest.tier("tests\\flows\\test_smoke.py::T::t"),
                         "integration")


class SuiteTests(unittest.TestCase):
    """The real suite: nothing runs below the tier it needs."""

    @classmethod
    def setUpClass(cls):
        cls.results = list(A.tests(A.Index(A.ROOT), conftest.tier))

    def test_no_test_is_under_tiered(self):
        bad = A.grouped(A.under(self.results), self.results)
        lines = [f"{prefix}: in `{given}`, needs `{needs}` via {' -> '.join(chain)}"
                 for (given, needs), prefixes in sorted(bad.items())
                 for prefix, chain in sorted(prefixes.items())]
        self.assertEqual(lines, [], "\nregister these in tests/conftest.py:\n"
                         + "\n".join(lines))

    def test_the_run_hints_and_key_marker_modules_are_integration(self):
        for path in ("tests/playing/test_run_hints.py",
                     "tests/playing/test_key_marker.py"):
            mine = [t for t in self.results if t.nodeid.startswith(path)]
            self.assertTrue(mine, path)
            self.assertEqual({(t.tier, t.need.tier) for t in mine},
                             {("integration", "integration")}, path)

    def test_this_module_is_unit(self):
        mine = [t for t in self.results
                if t.nodeid.startswith("tests/devtools/test_tier_audit.py")]
        self.assertTrue(mine)
        self.assertEqual({(t.tier, t.need.tier) for t in mine}, {("unit", "unit")})


if __name__ == "__main__":
    unittest.main()
