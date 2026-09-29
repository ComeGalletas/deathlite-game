"""Runtime cross-check for `tier_audit.py`: which tests *actually* boot a
`Game` or generate a world, against the tier conftest gave them.

`tier_audit` reads the source, and cannot see a call made through an object it
cannot type. This watches the same primitives while the tests run -- the
`Game`, `PlayingState` and `LoadingState` constructors, `generate_world`,
`generate_world_steps`, and a `GameMap` handed a seed -- and at the end lists
every test that reached one from a lower tier. A pytest plugin, loaded by
name; it changes no result and fails nothing::

    python -m pytest -m unit -p tools.verification.tier_trace

What it cannot see is what a cache hides, or another process does: the first
test that asks `tests/worlds.py` for a seed pays the build and is listed, a
later one gets the cached map and is not; a `setUpClass` boot or a module-level
run cache (`test_buffs.py`) shows on the class's or module's first test only;
a run in a child interpreter (`test_run_determinism.py`) is not seen at all.
So a clean trace confirms the audit, it does not replace it. Work done at
import time is attributed to the module's collection.
"""
from __future__ import annotations

import functools

RANK = {"unit": 0, "world": 1, "integration": 2, "sweep": 3}

_current = ["(session)"]
_seen: dict = {}          # nodeid -> {tier needed: first primitive}
_given: dict = {}         # nodeid -> tier conftest gave it


def _note(tier: str, what: str) -> None:
    _seen.setdefault(_current[0], {}).setdefault(tier, what)


def _wrap_init(cls, tier, label, only_if=None):
    original = cls.__init__

    @functools.wraps(original)
    def __init__(self, *args, **kwargs):
        if only_if is None or only_if(args, kwargs):
            _note(tier, label)
        return original(self, *args, **kwargs)

    cls.__init__ = __init__


def _wrap_function(module, name, tier):
    import sys
    original = getattr(module, name)

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        _note(tier, f"{name}(")
        return original(*args, **kwargs)

    # Rebind every module that already imported it by name, then the source,
    # so a later `from world.gen import generate_world` gets the wrapper too.
    for mod in list(sys.modules.values()):
        if getattr(mod, name, None) is original:
            setattr(mod, name, wrapper)


def pytest_configure(config):
    from game.game import Game
    from game.states.loading_state import LoadingState
    from game.states.playing.core.state import PlayingState
    import world.gen
    from world.map import GameMap

    _wrap_init(Game, "integration", "Game(")
    _wrap_init(PlayingState, "integration", "PlayingState(")
    _wrap_init(LoadingState, "integration", "LoadingState(")

    def seeded(args, kwargs):
        seed = args[0] if args else kwargs.get("seed")
        return seed is not None

    _wrap_init(GameMap, "world", "GameMap(seed)", only_if=seeded)
    _wrap_function(world.gen, "generate_world", "world")
    _wrap_function(world.gen, "generate_world_steps", "world")


def pytest_collectstart(collector):
    _current[0] = f"{collector.nodeid} (import)"


def pytest_runtest_setup(item):
    _current[0] = item.nodeid
    tiers = [m.name for m in item.iter_markers() if m.name in RANK]
    _given[item.nodeid] = max(tiers, key=RANK.get) if tiers else "unit"


def pytest_terminal_summary(terminalreporter):
    tr = terminalreporter
    rows = []
    for nodeid, needs in _seen.items():
        need = max(needs, key=RANK.get)
        given = _given.get(nodeid, "unit")      # an import is judged as unit
        if RANK[given] < RANK[need]:
            rows.append((nodeid, given, need, needs[need]))
    tr.section("tier trace")
    tr.write_line(f"{len(_given)} tests traced; {len(rows)} reached a "
                  f"primitive above their tier")
    for nodeid, given, need, what in sorted(rows):
        tr.write_line(f"  {nodeid}: in `{given}`, reached {what} (`{need}`)")
