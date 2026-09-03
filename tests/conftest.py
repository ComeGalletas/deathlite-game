"""Tiering for pytest -- see `pytest.ini`.

Markers are assigned here, by path, rather than with `@pytest.mark` in the
modules, so that no test module imports pytest and the plain unittest runner
stays a first-class way to run everything.
"""
from __future__ import annotations

import pytest

# Individual tests (or whole classes / modules, by nodeid prefix) that build
# many seeds to make a statistical claim. Each says in its docstring why the
# range has to be wide.
SWEEP = (
    "tests/world/test_repair.py::SealTests::test_the_repair_has_teeth",
    "tests/world/test_obstacle_families.py::TreeDensityBoostTests::"
    "test_boost_adds_about_25_percent_more_trees_globally",
    # Twelve seeds pooled to judge each biome's scatter mix against intent.
    "tests/rendering/test_biome.py::ScatterMixTests",
)

# Modules that read generated worlds (through tests/worlds.py or directly).
WORLD = (
    "tests/world/",
    "tests/ai/test_pathfinding.py",
    "tests/ai/test_enemy_nav.py",
    "tests/rendering/test_terrain.py",
    "tests/rendering/test_biome.py",
    "tests/rendering/test_depth_sort.py",
    "tests/combat/test_projectile_elevation.py",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = item.nodeid.replace("\\", "/")
        if any(path.startswith(p) for p in SWEEP):
            item.add_marker(pytest.mark.sweep)
        elif any(path.startswith(p) for p in WORLD):
            item.add_marker(pytest.mark.world)
        else:
            item.add_marker(pytest.mark.unit)
