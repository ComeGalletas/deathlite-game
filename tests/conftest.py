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
    "tests/ai/test_aggro.py",
    "tests/ai/test_flying.py",
    "tests/rendering/test_terrain.py",
    "tests/rendering/test_biome.py",
    "tests/rendering/test_depth_sort.py",
    "tests/rendering/test_hazard_sprite.py",
    "tests/combat/test_projectile_elevation.py",
)

# Modules that boot a real `Game` and drive its states -- the menu into a run,
# the loading screen, a headless PlayingState. Each pays a window, an asset load
# and usually a world build, so they are the slow half of the suite and cannot
# be what `unit` means. Split out of `unit` so there is a tier fast enough to
# run on every save.
INTEGRATION = (
    "tests/combat/test_incoming_damage.py",
    "tests/combat/test_manual_aim.py",
    "tests/combat/test_weapons_special.py",
    "tests/core/test_controls.py",
    "tests/core/test_dev_mode.py",
    "tests/core/test_hero_unlock.py",
    "tests/core/test_loading.py",
    "tests/core/test_lod.py",
    "tests/core/test_smoke.py",
    "tests/rendering/test_damage_numbers.py",
    "tests/rendering/test_enemy_sprite.py",
    "tests/rendering/test_gem_glow.py",
    "tests/rendering/test_ghost.py",
    "tests/rendering/test_hostile_glow.py",
    "tests/rendering/test_level_up.py",
    "tests/rendering/test_menu.py",
    "tests/rendering/test_mouse.py",
    "tests/rendering/test_options.py",
    "tests/rendering/test_pause.py",
    "tests/rendering/test_rankings.py",
    "tests/rendering/test_render_cull.py",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = item.nodeid.replace("\\", "/")
        if any(path.startswith(p) for p in SWEEP):
            item.add_marker(pytest.mark.sweep)
        elif any(path.startswith(p) for p in WORLD):
            item.add_marker(pytest.mark.world)
        elif any(path.startswith(p) for p in INTEGRATION):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
