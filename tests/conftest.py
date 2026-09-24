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
    "tests/render/test_biome.py::ScatterMixTests",
    # Forty generated worlds for one mean; the per-seed caps and floors in the
    # same class stay in `world`.
    "tests/world/test_chests.py::CountingRuleTests::"
    "test_the_average_island_carries_two_to_three",
)

# Hand-built grids under a `world` prefix: rules checked on drawings small
# enough to read, nothing generated (worldgen R4). Listed before `WORLD` so
# the `tests/world/` prefix does not claim them.
UNIT = (
    "tests/world/grids/",
)

# Modules that read generated worlds (through tests/worlds.py or directly).
WORLD = (
    "tests/world/",
    # Booted or generated worlds that moved out of tests/world/ in the
    # folder reorganisation and keep their tier.
    "tests/entities/test_npcs.py",
    "tests/playing/test_interactables.py",
    "tests/playing/test_infusion_sources.py",
    "tests/entities/ai/test_boss_pig_rider.py",
    "tests/world/test_pathfinding.py",
    "tests/playing/test_enemy_nav.py",
    "tests/entities/ai/test_aggro.py",
    "tests/entities/ai/test_flying.py",
    "tests/render/test_terrain.py",
    "tests/render/test_biome.py",
    "tests/render/test_depth_sort.py",
    "tests/render/test_hazard_sprite.py",
    "tests/playing/test_projectile_elevation.py",
)

# Modules that boot a real `Game` and drive its states -- the menu into a run,
# the loading screen, a headless PlayingState. Each pays a window, an asset load
# and usually a world build, so they are the slow half of the suite and cannot
# be what `unit` means. Split out of `unit` so there is a tier fast enough to
# run on every save.
INTEGRATION = (
    "tests/combat/test_incoming_damage.py",
    "tests/flows/test_window.py",
    "tests/playing/test_bomb.py",
    "tests/playing/test_chest_open.py",
    "tests/playing/test_potion_drops.py",
    "tests/screens/test_hero_select_preview.py",
    "tests/playing/test_manual_aim.py",
    "tests/combat/test_weapons_special.py",
    "tests/flows/test_controls.py",
    "tests/flows/test_dev_mode.py",
    "tests/flows/test_hero_unlock.py",
    "tests/flows/test_loading.py",
    "tests/flows/test_lod.py",
    "tests/flows/test_smoke.py",
    "tests/render/test_damage_numbers.py",
    "tests/render/test_enemy_sprite.py",
    "tests/render/test_gem_glow.py",
    "tests/render/test_ghost.py",
    "tests/render/test_hostile_glow.py",
    "tests/screens/test_level_up.py",
    "tests/screens/test_menu.py",
    "tests/screens/test_character_select.py",
    "tests/screens/test_mouse.py",
    "tests/screens/test_options.py",
    "tests/screens/test_pause.py",
    "tests/screens/test_rankings.py",
    "tests/screens/test_sanctuary_mouse.py",
    "tests/render/test_render_cull.py",
    "tests/flows/test_run_determinism.py",
    "tests/devtools/test_element_building.py",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = item.nodeid.replace("\\", "/")
        if any(path.startswith(p) for p in SWEEP):
            item.add_marker(pytest.mark.sweep)
        elif any(path.startswith(p) for p in UNIT):
            item.add_marker(pytest.mark.unit)
        elif any(path.startswith(p) for p in WORLD):
            item.add_marker(pytest.mark.world)
        elif any(path.startswith(p) for p in INTEGRATION):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
