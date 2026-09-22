# Requirement index

Every requirement ID, where its journal is, and its state. Rules are in
`CLAUDE.md` §1 (DOC-001). Search by ID: `git log --grep CMB-007`,
or grep the ID across `documentation/`.

Journals that existed before 2026-09-22 were given retroactive IDs in
creation order within their system; their status reads `legacy` until
someone confirms it. Each carries a `**Legacy ID:**` line under its title
(DOC-001.3) — grep `Legacy ID:` to list them. Their sections predate the
standard and are not rewritten to it.

**Next free:** CMB-008 · ENT-013 · SPN-004 · WLD-012 · RND-005 · UI-012 ·
PRG-003 · AUD-004 · SYS-008 · TST-003 · BLD-003 · DOC-003

## Requirements

| ID | title | systems | type | status | journal | branch | date |
|---|---|---|---|---|---|---|---|
| CMB-001 | Combat balance | CMB | balance | legacy | [combat_balance_journal.md](combat_balance_journal.md) | — | 2026-08-27 |
| CMB-002 | Six-weapon system | CMB, PRG | feature | legacy | [weapon_system_journal.md](weapon_system_journal.md) | — | 2026-09-10 |
| CMB-003 | Training dummy and DPS meter | CMB, UI | feature | legacy | [training_dummy_journal.md](training_dummy_journal.md) | — | 2026-09-11 |
| CMB-004 | Bomb blast radius | CMB | balance | legacy | [bomb_blast_journal.md](bomb_blast_journal.md) | — | 2026-09-12 |
| CMB-005 | Elemental system | CMB, RND | feature | legacy | [elemental_system_journal.md](elemental_system_journal.md) | — | 2026-09-21 |
| CMB-006 | Reaction damage rework | CMB | feature | done (balance confirmed in play) | [reaction_damage_rework_journal.md](reaction_damage_rework_journal.md) | claude/reaction-damage-rework | 2026-09-22 |
| CMB-007 | Elemental design doc brought to the shipped behaviour (open questions closed bar one) | CMB, DOC | process | done | [reaction_damage_rework_journal.md](reaction_damage_rework_journal.md) | claude/reaction-damage-rework | 2026-09-22 |
| ENT-001 | Enemy AI architecture | ENT | refactor | legacy | [enemy_ai_journal.md](enemy_ai_journal.md) | — | 2026-08-28 |
| ENT-002 | Pig rider boss | ENT | feature | legacy | [pig_rider_boss_journal.md](pig_rider_boss_journal.md) | — | 2026-09-12 |
| ENT-003 | Chaser collider | ENT | bug | legacy | [chaser_collider_journal.md](chaser_collider_journal.md) | — | 2026-09-15 |
| ENT-004 | The Bloat throws its bomb | ENT | feature | legacy | [bomb_fish_journal.md](bomb_fish_journal.md) | — | 2026-09-17 |
| ENT-005 | Enemy roster expansion | ENT, SPN | feature | legacy | [enemy_roster_expansion_journal.md](enemy_roster_expansion_journal.md) | — | 2026-09-17 |
| ENT-006 | Gnome split (Hammer Gnome, Beekeeper) | ENT | feature | legacy | [gnome_split_journal.md](gnome_split_journal.md) | — | 2026-09-17 |
| ENT-007 | The Imp ("Cinder") | ENT | feature | legacy | [imp_journal.md](imp_journal.md) | — | 2026-09-17 |
| ENT-008 | Pig NPC (village corral) | ENT, WLD | feature | legacy | [pig_npc_journal.md](pig_npc_journal.md) | — | 2026-09-17 |
| ENT-009 | The Whirlspear (spear goblin) | ENT | feature | legacy | [spear_goblin_journal.md](spear_goblin_journal.md) | — | 2026-09-17 |
| ENT-010 | Ranged range, wind-up and animation | ENT | feature | legacy | [ranged_windup_journal.md](ranged_windup_journal.md) | — | 2026-09-19 |
| ENT-011 | Fish huts and seahorse boats | ENT, WLD | feature | legacy | [fish_hut_journal.md](fish_hut_journal.md) | — | 2026-09-20 |
| ENT-012 | Enemy tuning (Stoutpaw shield, Tusked Lance radius) | ENT | balance | done | [enemy_tuning_journal.md](enemy_tuning_journal.md) | claude/reaction-damage-rework | 2026-09-22 |
| SPN-001 | Spawn master | SPN | feature | legacy | [spawn_master_journal.md](spawn_master_journal.md) | — | 2026-09-03 |
| SPN-002 | Spawn groups and ranks | SPN | feature | legacy | [spawn_groups_journal.md](spawn_groups_journal.md) | — | 2026-09-17 |
| SPN-003 | Enemy despawn by distance | SPN | feature | legacy | [enemy_despawn_journal.md](enemy_despawn_journal.md) | — | 2026-09-19 |
| WLD-001 | Level design | WLD | feature | legacy | [level_design_journal.md](level_design_journal.md) | — | 2026-08-30 |
| WLD-002 | World refactor | WLD | refactor | legacy | [world_refactor.md](world_refactor.md) | — | 2026-08-30 |
| WLD-003 | World generation refactor (execution) | WLD, TST | refactor | legacy | [world_refactor_plan_journal.md](world_refactor_plan_journal.md) | — | 2026-09-02 |
| WLD-004 | Worldgen modularity & test rework | WLD, TST | refactor | legacy | [worldgen_modularity_todo.md](worldgen_modularity_todo.md) | — | 2026-09-02 |
| WLD-005 | Human island | WLD, ENT | feature | legacy | [human_island_journal.md](human_island_journal.md) | — | 2026-09-10 |
| WLD-006 | Placement review | WLD | refactor | legacy | [placement_review_journal.md](placement_review_journal.md) | — | 2026-09-12 |
| WLD-007 | North stairs | WLD, RND | feature | legacy | [north_stairs_journal.md](north_stairs_journal.md) | — | 2026-09-14 |
| WLD-008 | Rock collider | WLD | bug | legacy | [rock_collider_journal.md](rock_collider_journal.md) | — | 2026-09-16 |
| WLD-009 | Buff buildings | WLD, PRG | feature | legacy | [buff_buildings_journal.md](buff_buildings_journal.md) | — | 2026-09-20 |
| WLD-010 | Special island facilities | WLD | feature | parked | [special_facilities_journal.md](special_facilities_journal.md) | — | 2026-09-20 |
| WLD-011 | Bridge clearance for large bodies | WLD, ENT | bug | done | [bridge_clearance_journal.md](bridge_clearance_journal.md) | claude/reaction-damage-rework | 2026-09-22 |
| RND-001 | Asset integration | RND | feature | legacy | [assets_journal.md](assets_journal.md) | — | 2026-08-27 |
| RND-002 | Cluster Bomb bomblet FX | RND, CMB | feature | legacy | [bomblet_fx_journal.md](bomblet_fx_journal.md) | — | 2026-09-12 |
| RND-003 | Dynamic window scaling | RND, UI | feature | legacy | [window_scaling_journal.md](window_scaling_journal.md) | — | 2026-09-15 |
| RND-004 | Native-resolution rendering | RND | feature | legacy | [native_resolution_journal.md](native_resolution_journal.md) | — | 2026-09-16 |
| UI-001 | Game over screen | UI | feature | legacy | [game_over_journal.md](game_over_journal.md) | — | 2026-09-12 |
| UI-002 | Hero-select sprite preview | UI | feature | legacy | [hero_select_preview_journal.md](hero_select_preview_journal.md) | — | 2026-09-12 |
| UI-003 | HUD rework | UI | feature | legacy | [hud_rework_journal.md](hud_rework_journal.md) | — | 2026-09-12 |
| UI-004 | Run status screen | UI, PRG | feature | legacy | [run_status_journal.md](run_status_journal.md) | — | 2026-09-12 |
| UI-005 | Victory screen | UI | feature | legacy | [victory_screen_journal.md](victory_screen_journal.md) | — | 2026-09-12 |
| UI-006 | Cursor size | UI | feature | legacy | [cursor_size_journal.md](cursor_size_journal.md) | — | 2026-09-16 |
| UI-007 | End-screen input lock | UI | bug | legacy | [end_screen_input_lock_journal.md](end_screen_input_lock_journal.md) | — | 2026-09-16 |
| UI-008 | Options menu mouse support | UI | feature | legacy | [options_mouse_journal.md](options_mouse_journal.md) | — | 2026-09-16 |
| UI-009 | End banners | UI | feature | legacy | [end_banner_journal.md](end_banner_journal.md) | — | 2026-09-19 |
| UI-010 | Key icons (keycaps) | UI, RND | feature | legacy | [key_icons_journal.md](key_icons_journal.md) | — | 2026-09-19 |
| UI-011 | Enemy health bar | UI, ENT | feature | legacy | [enemy_health_bar_journal.md](enemy_health_bar_journal.md) | — | 2026-09-22 |
| PRG-001 | Six blessings per weapon | PRG, CMB | feature | legacy | [six_blessings_journal.md](six_blessings_journal.md) | — | 2026-09-20 |
| PRG-002 | XP curve | PRG | balance | legacy | [xp_curve_journal.md](xp_curve_journal.md) | — | 2026-09-22 |
| AUD-001 | Music | AUD | feature | legacy | [music_journal.md](music_journal.md) | — | 2026-09-15 |
| AUD-002 | Audio mixer (SFX level) | AUD, UI | feature | legacy | [audio_mixer_journal.md](audio_mixer_journal.md) | — | 2026-09-16 |
| AUD-003 | Sound effects | AUD | feature | legacy | [sound_effects_journal.md](sound_effects_journal.md) | — | 2026-09-16 |
| SYS-001 | Bug journal (cross-system log) | all | bug | legacy | [bug_journal.md](bug_journal.md) | — | 2026-08-27 |
| SYS-002 | Developer mode | SYS | feature | legacy | [dev_mode_journal.md](dev_mode_journal.md) | — | 2026-08-27 |
| SYS-003 | Development journal (milestones) | all | process | legacy | [journal.md](journal.md) | — | 2026-08-27 |
| SYS-004 | Build transcript | all | process | legacy | [transcript.md](transcript.md) | — | 2026-08-27 |
| SYS-005 | PlayingState refactor | SYS | refactor | legacy | [playing_state_refactor.md](playing_state_refactor.md) | — | 2026-08-29 |
| SYS-006 | Data layout | SYS | refactor | legacy | [data_layout_journal.md](data_layout_journal.md) | — | 2026-09-12 |
| SYS-007 | Structure review | SYS | refactor | legacy | [structure_review_journal.md](structure_review_journal.md) | — | 2026-09-20 |
| TST-001 | Test seed stability | TST | refactor | legacy | [test_seed_stability_journal.md](test_seed_stability_journal.md) | — | 2026-09-17 |
| TST-002 | Remove the exit-2 skip from the cut-script tests | TST, RND | bug | done | [cut_script_skips_journal.md](cut_script_skips_journal.md) | claude/optimistic-poincare-e34af9 | 2026-09-22 |
| BLD-001 | Web build (pygbag) | BLD | feature | legacy | [pygbag.md](pygbag.md) | — | 2026-08-28 |
| BLD-002 | Desktop packaging (.exe) | BLD | feature | legacy | [desktop_packaging_journal.md](desktop_packaging_journal.md) | — | 2026-09-12 |
| DOC-001 | Process standard: IDs, journals, index, commits | DOC | process | done | [process_standards_journal.md](process_standards_journal.md) | claude/reaction-damage-rework | 2026-09-22 |
| DOC-002 | Flag and ask about balance tweaks in `data/` | DOC | process | done | [process_standards_journal.md](process_standards_journal.md) | claude/reaction-damage-rework | 2026-09-22 |

## Plans and designs

Only links whose owner is clear from the document are filled in; the rest
are `unassigned` until someone confirms which requirement they serve.

| document | serves |
|---|---|
| [plans/ELEMENTAL_SYSTEM_DESIGN.md](../plans/ELEMENTAL_SYSTEM_DESIGN.md) | CMB-005, CMB-006 |
| [plans/weapon_system_plan.md](../plans/weapon_system_plan.md) | CMB-002 |
| [designs/six_weapon_system_design.md](../designs/six_weapon_system_design.md) | CMB-002 |
| [designs/combat_calculations.md](../designs/combat_calculations.md) | CMB-001 |
| [plans/worldgen_refactor_plan.md](../plans/worldgen_refactor_plan.md) | WLD-003 |
| [designs/level_design.md](../designs/level_design.md) | WLD-001 |
| [designs/terrain_tile_slots_formula.md](../designs/terrain_tile_slots_formula.md) | WLD-001 |
| [designs/spawn_master_design.md](../designs/spawn_master_design.md) | SPN-001 |
| [plans/spawn_master_todo.md](../plans/spawn_master_todo.md) | SPN-001 |
| [plans/web_plan.md](../plans/web_plan.md) | BLD-001 |
| [designs/death_must_die_lite_game_spec.md](../designs/death_must_die_lite_game_spec.md) | SYS-003 |
| [designs/sprite_functionality.md](../designs/sprite_functionality.md) | unassigned |
| [designs/weapon_blessing_forge_tables.md](../designs/weapon_blessing_forge_tables.md) | unassigned |
| [plans/boss_free_roam_todo.md](../plans/boss_free_roam_todo.md) | unassigned |
| [plans/fluidity_plan.md](../plans/fluidity_plan.md) | unassigned |
| [plans/pending_plans.md](../plans/pending_plans.md) | unassigned |
| [plans/test_suite_review.md](../plans/test_suite_review.md) | unassigned |
