"""Tiering for pytest -- see `pytest.ini`.

Markers are assigned here, by path, rather than with `@pytest.mark` in the
modules, so that no test module imports pytest and the plain unittest runner
stays a first-class way to run everything.

Anything unlisted is `unit`. `tools/verification/tier_audit.py` reads what
each test calls and `tests/devtools/test_tier_audit.py` fails when one needs
more than it gets here (TST-006).
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
    # Forty generated worlds for the buff-building counts: ~30 s, the `world`
    # tier's slowest by a factor of three. The guarantee and the ceiling stay
    # in `world` on the pinned seeds (`PinnedSeedBuffBuildingTests`, TST-005.3).
    "tests/world/test_repair.py::BuffBuildingCountTests",
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
    # Generated worlds that moved out of tests/world/ in the folder
    # reorganisation and keep their tier. The classes of these modules that
    # boot a Game are in `INTEGRATION` (TST-006.3), and the pure ones fall to
    # `unit`; `WORLD` is matched first, so it names only its own classes.
    "tests/entities/ai/test_boss_pig_rider.py",
    "tests/world/test_pathfinding.py",
    "tests/playing/test_enemy_nav.py::NavFieldTests",
    "tests/entities/ai/test_aggro.py",
    "tests/entities/ai/test_flying.py",
    "tests/render/test_terrain.py",
    "tests/render/test_biome.py",
    "tests/render/test_depth_sort.py::SceneryDrawablesTests",
    "tests/render/test_hazard_sprite.py",
    "tests/playing/test_projectile_elevation.py",
    # TST-006.2: reads the shared worlds; the module's boats boot a run.
    "tests/entities/test_fish_huts.py::PlacementTests",
    # ENT-021: the 20 px gap routing, on a pinned world's shared nav field.
    "tests/entities/ai/test_melee_enemies.py::ColliderRoutingTests",
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
    "tests/playing/test_spanish_run.py",
    "tests/playing/test_spanish_run_notices.py",
    "tests/screens/test_hero_select_preview.py",
    "tests/playing/test_manual_aim.py",
    "tests/combat/test_weapon_specials.py",
    "tests/flows/test_controls.py",
    "tests/flows/test_dev_mode.py",
    "tests/flows/test_hero_unlock.py",
    "tests/flows/test_loading.py",
    "tests/flows/test_lod.py",
    "tests/flows/test_smoke.py",
    "tests/render/test_damage_numbers.py",
    "tests/render/test_enemy_sprite.py",
    "tests/render/test_enemy_shapes.py",
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
    "tests/playing/test_bridge_crowd.py",
    # TST-006.2: booted a Game inside `unit`. Whole modules where every class
    # boots; class by class where the rest of the module is pure, and a class
    # that mixes goes whole (TST-006.D1). `tools/verification/tier_audit.py`
    # names the call that boots each one.
    "tests/playing/test_run_hints.py",
    "tests/playing/test_key_marker.py",
    "tests/playing/test_buffs.py",
    "tests/flows/test_display_change_in_run.py",
    "tests/screens/test_ui_scale.py",
    "tests/combat/test_forge.py::ArcaneStormOnTheDummyTests",
    "tests/combat/test_forge.py::ForgeWeaponPickerTests",
    "tests/devtools/test_dps_bench.py::BuildTests",
    "tests/devtools/test_dps_bench.py::DamageScaleTests",
    "tests/devtools/test_dps_bench.py::BlessingDamageScaleTests",
    "tests/devtools/test_dps_bench.py::MeasurementTests",
    "tests/devtools/test_dps_meter.py::BenchArenaTests",
    "tests/entities/ai/test_ranged_windup.py::FiringTests",
    "tests/entities/test_fish_huts.py::BoatTests",
    "tests/render/test_element_layers.py::DrawOrderTests",
    "tests/render/test_enemy_hp_bar.py::BossExclusionTests",
    "tests/render/test_spawn_fx.py::RunTests",
    "tests/screens/test_ultrawide.py::DimCoversTheMarginsTests",
    "tests/screens/test_ultrawide.py::ScreenBackdropTests",
    "tests/screens/test_ultrawide.py::PanelsStayInTheBoxTests",
    # TST-006.3: booted a Game inside `world`, where they had been carried
    # whole. `PenSpotTests`, `DataTests` and `ConeWeaponVisualTests` build
    # nothing and are `unit`.
    "tests/playing/test_interactables.py",
    "tests/entities/test_npcs.py::VillagerTests",
    "tests/playing/test_infusion_sources.py::PlacementTests",
    "tests/playing/test_infusion_sources.py::MonasteryTests",
    "tests/playing/test_infusion_sources.py::CardTests",
    "tests/playing/test_infusion_sources.py::BuffBuildingTests",
    "tests/playing/test_enemy_nav.py::PlayingStateNavWiringTests",
    "tests/playing/test_enemy_nav.py::NavRebuildStaggerTests",
    "tests/render/test_depth_sort.py::DepthOrderTests",
    # RND-008.2: the stress harness boots a run; its flag and budget checks
    # boot nothing and stay unit.
    "tests/devtools/test_spawn_stress.py::HarnessDefaultsTests",
    "tests/devtools/test_spawn_stress.py::LiveDirectorTests",
    "tests/devtools/test_spawn_stress.py::CommandLineTests",
    # RND-010.2: the draw timed by layer on a packed seed-35 fight.
    "tests/devtools/test_draw_layers.py::WiringTests",
    "tests/devtools/test_draw_layers.py::MainTests",
    "tests/devtools/test_draw_layers.py::VillagersAndHutsTests",
    "tests/devtools/test_draw_layers.py::BossTests",
    "tests/devtools/test_draw_layers.py::ElementPathTests",
    "tests/devtools/test_layer_probes.py::PackedSceneTests",
    "tests/devtools/test_layer_probes.py::SceneTests",
    "tests/devtools/test_layer_probes.py::MainTests",
    # RND-010.3: the leads, the variants and the sprite caches each boot a
    # packed seed-35 scene; the data test runs derived.py in a child process.
    "tests/devtools/test_bench_probes.py::GcRunTests",
    "tests/devtools/test_draw_leads.py::SceneTests",
    "tests/devtools/test_draw_leads.py::MainTests",
    "tests/devtools/test_draw_variants.py::SceneTests",
    "tests/devtools/test_draw_variants.py::MainTests",
    "tests/devtools/test_sprite_caches.py::SceneTests",
    "tests/devtools/test_sprite_caches.py::RequestTests",
    "tests/devtools/test_rnd_010_3_data.py::DerivedTests",
    "tests/devtools/test_rnd_010_4_data.py::DerivedTests",
    "tests/devtools/test_sprite_caches.py::MainTests",
    # RND-010.5: a booted run, the probe's own packed scene, and two runs
    # in child processes (the overlay hidden and shown).
    "tests/playing/test_debug_lines.py::DebugLinesTests",
    "tests/devtools/test_debug_lines_probe.py::MainTests",
    "tests/flows/test_debug_lines_exact.py::DebugLinesExactTests",
    # RND-010.6: the under-layer's leads probe on a packed seed-35 fight.
    "tests/devtools/test_under_leads.py::SceneTests",
    "tests/devtools/test_under_leads.py::MainTests",
    "tests/devtools/test_rnd_010_6_data.py::DerivedTests",
    # SYS-011: the timer eval's command line reads as far as the Game it
    # builds on Windows; its judgment tests stay unit.
    "tests/devtools/test_timer_regime.py::CommandLineTests",
    # RND-008.3: a whole run's draw, three booted runs.
    "tests/playing/test_frame_fonts.py",
    # RND-008.4: the harness's packed, primed fight; the cache checks stay unit.
    "tests/render/test_elemental_draw_cost.py::TerraceSortTests",
    # RND-011: the draw and the update-time shed in a booted run; the fake
    # crowds' rate and budget checks stay unit.
    "tests/render/test_aura_shed.py::BootedRunTests",
    # RND-008.5: seed 35's fight as it plays; the random crowds stay unit.
    "tests/playing/test_bump_exact.py::HarnessFightTests",
    # ENT-018: seed 35's fight as it plays; the random crowds stay unit.
    "tests/entities/test_enemy_update_exact.py::SeparationFightTests",
    # ENT-019: the bump-rate bench boots seed 35's packed crowd; the series
    # readers and the flag checks stay unit.
    "tests/playing/test_bump_rate.py::BenchTests",
    # UI-014: screens drawn from a booted `Game`; the fit test boots a run.
    "tests/locale/test_numbers.py::LocaleNumberTests",
    "tests/screens/test_english_layout.py",
    "tests/screens/test_fit.py",
    "tests/screens/test_fit_rules.py::ControlsWordTests",
    "tests/screens/test_fit_rules.py::HeroCardTests",
    "tests/screens/test_fit_rules.py::SummaryPanelTests",
    "tests/screens/test_spanish_menus.py::FitTests",
    "tests/screens/test_spanish_menus.py::MenuEnglishTests",
    "tests/screens/test_spanish_menus.py::SpanishScreenTests",
    "tests/screens/test_spanish_status.py::SanctuaryTests",
    # SYS-010: a real Game stepped with and without a trace, and main.py run.
    "tests/devtools/test_frame_trace.py::GameWiringTests",
    "tests/devtools/test_frame_trace.py::MainTests",
    # BLD-003: a run booted under the web profile, and the main loop's tick;
    # the profile's values and the pacing flag boot nothing and stay unit.
    "tests/flows/test_web_crowd.py::WebCrowdRunTests",
    "tests/flows/test_frame_pacing.py::StepTickTests",
    # RND-012: overlays over a booted run.
    "tests/flows/test_frozen_backdrop.py",
    # BLD-004: a Game booted silent under the web profile; the switch, the
    # managers and the bundle check boot nothing and stay unit.
    "tests/systems/test_web_audio.py::SilentGameTests",
)


def tier(nodeid: str) -> str:
    """The tier a test gets, by the first tuple one of whose prefixes starts
    its nodeid; `unit` when none does. `tools/verification/tier_audit.py`
    reads the same answer to check it against what each test reaches."""
    path = nodeid.replace("\\", "/")
    for name, prefixes in (("sweep", SWEEP), ("unit", UNIT), ("world", WORLD),
                           ("integration", INTEGRATION)):
        if any(path.startswith(p) for p in prefixes):
            return name
    return "unit"


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(getattr(pytest.mark, tier(item.nodeid)))


@pytest.fixture(autouse=True)
def _english_ui():
    """Every test starts and ends in English (UI-014.3). The UI language is
    process-global in `game.locale`, and `Game()` sets it from the save it
    loads -- a test that boots a `Game` without a temp `save_path` reads the
    developer's own `save.json`, which may say Spanish. A test that wants
    another language sets it itself; this puts English back after it."""
    from game import locale
    locale.set_language(locale.DEFAULT)
    yield
    locale.set_language(locale.DEFAULT)
