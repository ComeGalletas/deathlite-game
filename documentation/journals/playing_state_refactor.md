# PlayingState refactor — dev log

Splitting `game/states/playing_state.py` (1404 lines, one class, ~88 methods)
into a `game/states/playing/` package so each concern is a small, separately
maintainable unit. Same as `enemy_ai.md` tracks the AI split and
`assets_journal.md` the art passes; the general `journal.md` gets a one-paragraph
pointer here once this lands.

Milestones are **P1–P7**. Each ends with the **full suite green**
(`python -m unittest discover -s tests -t .`) and, where the milestone touches
rendering, a windowed / headless-screenshot check. Nothing is committed unless
the user asks.

**Status:** complete (P0–P6, P8). P7 (`RunContext`) deliberately not done — see
its row. `state.py` **1386 → 735**; sub-systems: `rendering.py` 420, `combat.py`
184, `effects.py` 127, `locations.py` 125, `spawning.py` 73, `navigation.py` 70,
`perception.py` 36. Suite **578 green** throughout; determinism A/B checked at
P2/P3/P4/P5/P6.

---

## Goals

1. `PlayingState` becomes a **thin coordinator**: it owns the frame pipeline
   (`update()` 4-phase order), the `draw()` layer order, event routing, and the
   wiring between sub-systems — nothing else. Target ≤ ~320 lines.
2. Every other concern is a sub-system in its own module that owns its slice of
   state and exposes `update(dt)` and/or `draw(surface, camera)`.
3. **No behaviour change.** Byte-identical gameplay for a fixed seed; the test
   suite stays green at every milestone (delegators or one-line test edits, never
   a skipped assertion).
4. Import compatibility preserved: `from game.states.playing_state import
   PlayingState` keeps working.
5. The `entities.ai` boundary (`_enemy_context`) becomes a typed object instead
   of a bare `SimpleNamespace`.

## Non-goals

- No gameplay, balance, or content changes.
- No new abstraction the code doesn't already imply (a `RunContext` dataclass is
  **P7, optional** — the earlier steps just pass `self`).
- `update()`'s phase order and `draw()`'s layer list **stay in** `PlayingState`
  verbatim — the point of the coordinator is that those two read top-to-bottom
  on one screen.

---

## Current state (what's in the 1404 lines)

| Concern | Lines (approx) | Key methods |
|---|---|---|
| Lifecycle | `enter` 76–191, `exit` 193 | `enter` is **115 flat lines** of field wiring |
| Update pipeline | 232–398 | `update`, `_phase_input/update/combat/progression`, `_run_death_sequence`, `_apply_dev_unlimited_hp` |
| AI context + nav | 399–465 | `_enemy_context`, `_nav_dir`, `_nav_neighbors`, `_obstacles_near`, `_update_nav`, `_NAV_DRIFT_CELLS` |
| Spawning | 487–526 | `_spawn_enemy`, `_summon`, `_spawn_boss`, `_boss_arena_point`, `_targetables`, `_in_world_margin` |
| Special locations | 528–614 | `_build_interactables`, `_nearby_interactable`, `_activate_nearby_interactable`, `_use_shrine/treasure/fountain/altar/merchant`, `_update_elite_arenas`, `_grant_random_blessing` |
| Transient spawners | 615–686 | `_spawn_projectile`, `_fire_hostile`, `_block_on_obstacle`, `_spawn_summon`, `_update_summons`, `_spawn_hazard`, `_update_hazards`, `_explosion`, `_update_explosions` |
| Combat resolution | 687–820 | `_resolve_projectile_hits`, `_damage_multiplier`, `_apply_on_hit_effects`, `_in_cone`, `_chain_to_next`, `_resolve_hostile_hits`, `_resolve_enemy_contact`, `_cull_dead_enemies` |
| On-kill / status / death FX | 822–876, 824–839 | `_apply_on_kill_effects`, `_enemy_explosion`, `_spread_status`, `_sprite_drop`, `_spawn_death_fx`, `_update_death_fx` |
| Level-up + handlers + run-end + bonuses + debug | 878–999 | `_open_level_up`, `_on_level_up_chosen`, `_on_enemy_killed`, `_drop_item`, `_on_player_damaged`, `_on_boss_spawned`, `_on_boss_killed`, `_end_run`, `_restart_dev_run`, `_apply_persistent_bonuses`, `_report_debug` |
| **Rendering** | **1001–1405 (~430)** | `draw`, `_draw_feedback_overlays`, `_draw_interactables/_hazards/_one_summon/_gems/_explosions`, `_depth_items`, `_draw_depth_layer`, `_hit_tinted`, `_draw_one_enemy`, `_draw_death_fx`, `_draw_enemy_sprite`, `_draw_boss`, `_draw_player_projectiles`, `_draw_cone`, `_draw_hostile_projectiles`, `_draw_player`, `_draw_collider_overlay`, `_hero_sprite_frame` |

### Pain points the split targets

- Rendering is ~30 % of the file and the most-churned code (art passes), yet
  welded to gameplay state.
- `_phase_update` (313–352) is a 40-line grab-bag of ~15 unrelated update calls.
- Three near-duplicate sprite blitters: `_draw_enemy_sprite`, `_draw_boss`,
  `_draw_player` repeat `scale_for → frame → anchor → hurt-tint → drop → blit`.
- Positional-list state: `self._death_fx` entries are
  `[Animator, Vector2, int, float, float]` (`fx[0]`, `fx[1].y`); `self._explosions`
  is a list of ad-hoc dicts.
- Four hand-rolled transient systems (projectiles, summons, hazards, explosions),
  each a `_spawn_* / _update_* / _draw_*` triplet in a different section.
- `_enemy_context` is an untyped `SimpleNamespace` of 13 callbacks — the
  `entities.ai` seam is invisible from both sides.

### Test coupling (10 files reach into internals)

`tests/ai/test_boss.py`, `tests/ai/test_enemy_nav.py`,
`tests/characters/test_characters.py`, `tests/characters/test_movement.py`,
`tests/combat/test_incoming_damage.py`, `tests/combat/test_weapons_special.py`,
`tests/core/test_dev_mode.py`, `tests/core/test_smoke.py`,
`tests/core/test_state_machine.py`, `tests/progression/test_blessings.py`,
`tests/rendering/test_damage_numbers.py`, `tests/rendering/test_depth_sort.py`,
`tests/rendering/test_enemy_sprite.py`, `tests/rendering/test_menu.py`,
`tests/rendering/test_options.py`, `tests/rendering/test_terrain.py`,
`tests/world/test_interactables.py`, `tests/world/test_obstacles.py`,
`tests/world/test_spawning.py`.

Attributes/methods they depend on (must stay reachable, via delegator or a
one-line test edit): `p.enemies`, `p.projectiles`, `p.hostiles`, `p.gems`,
`p.summons`, `p.interactables`, `p.stats`, `p.player`, `p.game_map`,
`p.blessing_fx`, `p._blessing_library`, `p.draw`, `p._phase_combat`,
`p._spawn_enemy`, `p._use_shrine/treasure/fountain/altar/merchant`,
`p._update_elite_arenas`, `p._depth_items`, `p._draw_depth_layer`,
`p._draw_player_projectiles`, `p._draw_hostile_projectiles`.

---

## Target structure

```
game/states/playing/
├── __init__.py         from .state import PlayingState
├── state.py            PlayingState — enter/exit, update() pipeline,
│                       handle_event, handle_debug_key, draw() layer order,
│                       _report_debug, _run_death_sequence, dev-HP ratchet   (~300)
├── setup.py            enter() body split: _init_world / _init_player /
│                       _init_pools / _init_nav / _subscribe_events          (~140)
├── rendering.py        WorldRenderer — every _draw_*, _depth_items,
│                       _hit_tinted, _sprite_drop, _hero_sprite_frame,
│                       feedback + collider overlays. One `_blit_rig(...)`
│                       replaces the 3× sprite-blit duplication.             (~430)
├── combat.py           CombatResolver — _resolve_projectile_hits /
│                       _resolve_hostile_hits / _resolve_enemy_contact /
│                       _cull_dead_enemies + _damage_multiplier /
│                       _apply_on_hit_effects / _in_cone / _chain_to_next    (~150)
├── locations.py        SpecialLocations — _build/_nearby/_activate/
│                       _use_*×5/_update_elite_arenas/_grant_random_blessing (~110)
├── spawning.py         EnemyControl — _spawn_enemy / _summon / _spawn_boss /
│                       _boss_arena_point / director tick / _targetables /
│                       stat-multiplier scaling / _in_world_margin           (~90)
├── navigation.py       NavCoordinator — _update_nav / _nav_dir /
│                       _nav_neighbors / _obstacles_near + drift/RR state    (~70)
├── effects.py          TransientFx — explosions + death poofs + hazards
│                       behind one `TimedVisual` dataclass; unified
│                       spawn / update / draw                                (~120)
└── perception.py       PlayingPerception dataclass — typed replacement for
│                       the _enemy_context SimpleNamespace (entities.ai seam) (~50)
```

`game/states/playing_state.py` stays as a one-line shim:
`from game.states.playing.state import PlayingState`.

### How the pieces talk

- **P1–P6: pass `self`** (the `PlayingState`) into each sub-system's
  constructor. Every module's docstring **must** list the exact `PlayingState`
  attributes it reads and the ones it writes — that documents each seam without
  inventing an abstraction and makes P7 mechanical.
- Sub-systems are created in `enter()` after their dependencies exist and stored
  as `self.renderer`, `self.combat`, `self.locations`, `self.spawn`, `self.nav`,
  `self.fx`.
- For the handful of internals the tests call directly, keep a one-line
  delegator on `PlayingState` (`_use_shrine = lambda self, it:
  self.locations.use_shrine(it)`); don't add delegators for anything else.

---

## Milestones

| # | Scope | Ends when |
|---|-------|-----------|
| **P0 ✅** | **Scaffold.** `game/states/playing/` created — `__init__.py` re-exports `PlayingState`; the class moved **verbatim** via `git mv` to `game/states/playing/state.py`; `game/states/playing_state.py` is now a 3-line re-export shim. No logic moved. **Done 2026-08-28** — all three import paths (`game.states.playing_state`, `game.states.playing`, `game.states.playing.state`) resolve to one class; full suite **578 green** on both `unittest -t .` and `pytest`. |
| **P1 ✅** | **Rendering → `rendering.py`.** New `game/states/playing/rendering.py`: module fns `hit_tinted` / `draw_cone` (+ the lazy `_get_gfxdraw` and the `_ORB_RIGS` / `_STATUS_TINT` / `_HIT_TINT` / `_HOSTILE_ARROW_TINT` constants), and `WorldRenderer(ps)` holding every painter — `feedback_overlays`, `interactables`, `hazards`, `one_summon`, `gems`, `explosions`, `one_enemy`, `enemy_sprite`, `death_fx`, `boss`, `player_projectiles`, `hostile_projectiles`, `player`, `hero_sprite_frame`, `collider_overlay`, `sprite_drop`. Read-only w.r.t. `PlayingState` (bodies verbatim, `self.` → `ps.`). `state.py`: `self.renderer = WorldRenderer(self)` built at the end of `enter()`; `draw()` keeps its exact layer list, calling `self.renderer.<layer>` for the non-patched layers and thin delegators (`_draw_player_projectiles` / `_draw_depth_layer` / `_draw_hostile_projectiles`) for the three `test_render_pipeline_order` monkey-patches. `_depth_items` + `_draw_depth_layer` stay on `PlayingState` (scene composition). Delegators kept for everything a test reaches: `_draw_player` / `_draw_one_enemy` / `_draw_boss` / `_draw_one_summon` / `_draw_death_fx` / `_sprite_drop` (instance) + `_hit_tinted` / `_draw_cone` (`staticmethod(_rendering.*)`). **`_blit_rig` fold deferred** — the three sprite paths differ enough (per-entity rings / telegraphs / invuln) that a shared core is a follow-up, not P1. **Done 2026-08-28** — `state.py` **1386 → 1063**; suite **578 green** (`unittest -t .` + `pytest`); busy-scene screenshot (2 enemies + boss telegraph banner + low-HP + F7 colliders) renders identically. |
| **P2 ✅** | **`enter()` split.** The ~115-line body is now six methods called in order — `_init_run(seed, dev, difficulty)` → `_init_world` (map + interactables + `SpawnDirector`) → `_init_player` (hero + weapon + rig + persistent bonuses + blessing lib + camera) → `_init_scaffold` (pools, feedback systems, HUD/levels, transient-FX lists, `renderer`, `stats`) → `_init_nav` → `_subscribe_events`. Kept a package module (`setup.py`) unnecessary — the steps are private methods on `PlayingState`, which reads better and needs no `self`-passing. Only reorder: `SpawnDirector` and `Camera` are constructed a few lines earlier than before; neither draws from `self.rng` at construction, so the RNG stream is untouched. **Done 2026-08-28** — suite **578 green**; fixed-seed 700-frame A/B self-consistency check identical (`pos`, enemy count, kills, damage). `enter()` is now a 6-line sequence. |
| **P3 ✅** | **Combat resolution → `combat.py`.** New `game/states/playing/combat.py`: `CombatResolver(ps)` with `resolve()` running the four passes — `projectile_hits` / `hostile_hits` / `enemy_contact` / `cull_dead_enemies` — plus `damage_multiplier` / `apply_on_hit_effects` and static `in_cone` / `chain_to_next`. `_ENEMY_DEATH_FX_SCALE` moved here (its only caller). `_phase_combat` stays on `PlayingState` (builds `FireContext`, fires the weapons) and now ends with `self.combat.resolve()`. `self.combat` built in `_init_scaffold`. Run-scoped effects it doesn't own are called back on `ps`: `_on_boss_killed`, `_apply_on_kill_effects`, `_explosion`, `_spawn_death_fx`. One delegator kept: `_cull_dead_enemies` (`test_enemy_sprite._kill_one` calls it). `_targetables` stays on `PlayingState`. **Done 2026-08-28** — `state.py` **1082 → 949**; suite **578 green**; fixed-seed 900-frame A/B (fast difficulty) identical (pos, hp, kills, damage, level, pool sizes). |
| **P4 ✅** | **Special locations → `locations.py`.** New `game/states/playing/locations.py`: `SpecialLocations(ps)` — `build()` (fills `ps.interactables`), `nearby()`, `activate_nearby()` (dispatches `use_<kind>`), `grant_random_blessing()`, `use_shrine/treasure/fountain/altar/merchant()`, `update_elite_arenas()`. `MERCHANT_COST` / `ALTAR_HP_COST_FRACTION` moved here. `self.locations` built in `_init_world` (only needs `game_map`); `_init_world`'s `_build_interactables()` → `self.locations.build()`. Call sites updated: `handle_event` `E` key → `self.locations.activate_nearby()`, `_phase_update` → `self.locations.update_elite_arenas()`, `rendering.feedback_overlays` → `ps.locations.nearby()`. `ps.interactables` stays a `PlayingState` attribute (tests + renderer read it). Delegators kept: `_use_shrine/treasure/fountain/altar/merchant` + `_update_elite_arenas` (`test_interactables` calls them). Dead imports `Interactable` / `SPECIAL_KINDS` dropped from `state.py`. **Done 2026-08-28** — `state.py` **949 → 872**; suite **578 green**; determinism check (teleport onto every interactable, activate all, run elite arenas) A/B identical. |
| **P5 ✅** | **Transient FX → `effects.py`.** New `game/states/playing/effects.py`: `TransientFx(ps)` owns the spawn/update/cull logic for hostile projectiles (`fire_hostile`, `block_on_obstacle`, `update_projectiles` — both pools + off-margin cull, lifted out of `_phase_update`), ground hazards (`spawn_hazard`, `update_hazards`), blast visuals (`explosion`, `enemy_explosion`, `update_explosions`), and the death poof (`spawn_death_fx`, `update_death_fx`). `self.fx` built in `_init_scaffold`. Call sites rewired: `_phase_update` (4 calls collapse to `self.fx.*`), `_enemy_context` (`fire_projectile`/`explosion`/`spawn_hazard`), `_apply_on_kill_effects` (`enemy_explosion`), `update()` + `_on_boss_killed` (`spawn_death_fx`), `combat.py` (`ps.fx.explosion` / `ps.fx.spawn_death_fx`). Containers (`_explosions` dicts, `_death_fx` lists, `hazards`, the pools) **stay on `PlayingState`** — the renderer and tests read them. Delegators kept: `_spawn_hazard`, `_update_death_fx` (`test_incoming_damage` / `test_enemy_sprite`). **`TimedVisual` dataclass deferred** — `test_enemy_sprite` asserts the `_death_fx[i][0..4]` positional layout; folding it is a separate change now that the logic is isolated. **Done 2026-08-28** — `state.py` **872 → 802**; suite **578 green**; 1200-frame A/B (super_fast, warlock+bomb+ranged) identical across pos/hp/kills/damage/level and every transient count. |
| **P6 ✅** | **Spawning + nav + perception.** Three new modules: `spawning.py` `EnemyControl(ps)` — `tick_director(dt)` (the `should_spawn_boss` + `director.update` loop lifted from `_phase_update`), `spawn_enemy`, `summon`, `spawn_boss`, `boss_arena_point`. `navigation.py` `NavCoordinator(ps)` — `update(dt)` / `direction` / `neighbors` / `obstacles_near`, `_DRIFT_CELLS`; operates on the `ps._nav*` fields (still set by `_init_nav`, still read by `_report_debug` + `test_enemy_nav`). `perception.py` `@dataclass PlayingPerception` — the 15 `Perception`+`Combat` fields, replacing the `SimpleNamespace` in `_enemy_context` (kept plain, not `frozen`, to match the old mutability exactly). `self.spawn` built in `_init_world`, `self.nav` in `_init_scaffold`. `_phase_update` shrinks: `self._update_nav(dt)` + the 6-line director block → `self.nav.update(dt)` + `self.spawn.tick_director(dt)`. Rewired: F2/F5 debug keys, `locations.update_elite_arenas` (`ps.spawn.spawn_enemy`), `_enemy_context` (`self.nav.*` / `self.spawn.summon`). Delegators kept: `_spawn_enemy`, `_spawn_boss`, `_update_nav`, `_nav_dir` (all called by tests). `_targetables` / `_in_world_margin` / `_spawn_summon` / `_update_summons` stay on `PlayingState`. Dead `import time` dropped. **Done 2026-08-28** — `state.py` **802 → 735**; suite **578 green** (`test_enemy_nav` 48-case run clean); 1500-frame A/B (super_fast + boss) identical across pos/hp/enemies/kills/level/`_nav_rebuilds`/enemy positions. |
| **P7** *(optional)* — **not done, by decision.** | **`RunContext`.** The idea was a small dataclass to replace passing `self` into every sub-system. In practice the six sub-systems touch far more of `PlayingState` than the 15 fields the plan listed — `director`, `content`, `blessing_lib`, `game.assets` / `game.audio`, the feedback timers/fonts, `dev_mode`, `interactables`, `_explosions` / `_death_fx` / `hazards`, `_nav*`, and callbacks (`_on_boss_killed`, `_apply_on_kill_effects`, `_drop_item`, `_open_level_up`, `_report_dot`, `_in_world_margin`, `_targetables`, `_spawn_summon`). A context capturing all of that is just `PlayingState` renamed; a context that genuinely narrows would mean hand-writing a Protocol per sub-system. The payoff (constructing a sub-system in a test without a real `PlayingState`) is speculative — every current test drives the whole state through `enter()` and is happy. Each module's docstring already lists the exact attributes it reads/writes, which is the 80% of the value at 0% of the churn/regression risk. **Revisit only if a sub-system genuinely needs isolated unit tests.** |
| **P8 ✅** | **Docs.** This file finished (status + the "Where things live now" table below). One-paragraph "PlayingState refactor" pointers appended to `journals/journal.md` and `journals/transcript.md`. `README.md` project-layout — `states/` line now says `playing/` is a package (coordinator + 6 sub-systems). **Done 2026-08-28.** |

### Sequencing note

P0→P1→P2 alone drop the file to ~800 lines with near-zero behavioural risk (P1
is pure output, P2 is a pure move). P3–P4 are well-bounded. P5 carries the most
risk (it changes the shape of `_death_fx` / `_explosions` state) — do it after
the easy wins, with a fixed-seed A/B check. P6 touches the `entities.ai` seam.
P7 is only worth doing if the sub-systems need isolated tests.

## Verification per milestone

- `python -m unittest discover -s tests -t .` green before moving on.
- Fixed-seed determinism spot-check for P3/P5/P6: run ~900 frames headless on a
  pinned seed before and after, diff the aggregate (`stats`, enemy count/positions,
  pool sizes) — expect identical.
- Rendering milestones (P1, P5): windowed screenshots of menu→run, an enemy, the
  boss telegraph, the low-HP vignette, and the F7 collider overlay.

## Where things live now (post-P8)

`game/states/playing/state.py` — **735 lines** (was 1386). It holds only the
coordinator surface: `enter()` + the `_init_*` steps, `exit`, `handle_event` /
`handle_debug_key`, the `update()` 4-phase pipeline (`_phase_input/update/combat/
progression`), `draw()`'s layer order, `_depth_items` / `_draw_depth_layer`
(scene composition), `_run_death_sequence`, the dev toggles
(`_apply_dev_unlimited_hp` / `_set_difficulty`), level-up flow, the event
handlers (`_on_enemy_killed` / `_on_player_damaged` / `_on_boss_*`), `_end_run` /
`_restart_dev_run`, `_apply_persistent_bonuses`, `_report_debug`, and the small
shared helpers (`_targetables`, `_in_world_margin`, `_report_dot`,
`_spawn_projectile` / `_spawn_summon` / `_update_summons`, `_spread_status`,
`_apply_on_kill_effects`, `_drop_item`, `_hero_anim_name` / `_update_hero_anim`).
Plus the thin delegators tests reach through.

| Concern | Module | Type | Built in |
|---|---|---|---|
| world-layer painting (every `_draw_*`, overlays, depth painters, sprite drop) | `rendering.py` | `WorldRenderer(ps)` | `_init_scaffold` (`self.renderer`) |
| hit detection (projectiles ↔ enemies / player, body contact, cull) | `combat.py` | `CombatResolver(ps)` | `_init_scaffold` (`self.combat`) |
| hostile shots, hazards, blast visuals, death poofs | `effects.py` | `TransientFx(ps)` | `_init_scaffold` (`self.fx`) |
| special locations (shrine/altar/…/elite arenas) | `locations.py` | `SpecialLocations(ps)` | `_init_world` (`self.locations`) |
| enemy / boss spawning + the phase director tick | `spawning.py` | `EnemyControl(ps)` | `_init_world` (`self.spawn`) |
| flow-field nav rebuilds + steering queries | `navigation.py` | `NavCoordinator(ps)` | `_init_scaffold` (`self.nav`) |
| the per-frame `Perception`+`Combat` object for `entities.ai` | `perception.py` | `@dataclass PlayingPerception` | `_enemy_context()` per frame |

All sub-systems take `ps` (the `PlayingState`) and their module docstring lists
exactly which `ps` attributes they read and write. `game/states/playing_state.py`
is a 3-line re-export shim, so both `from game.states.playing_state import
PlayingState` and `from game.states.playing import PlayingState` work.

## Follow-ups (not blocking)

- **`_blit_rig`** — fold the enemy / boss / player sprite-blit cores in
  `rendering.py` into one helper (the per-entity extras — state rings, phase
  telegraphs, invuln ring — stay separate).
- **`TimedVisual` dataclass** — replace the positional `_death_fx`
  `[anim, pos, facing, scale, radius]` list and the `_explosions`
  `{pos, radius, t, dur}` dict; needs the ~8 `test_enemy_sprite` assertions on
  the list layout updated.
- `_report_debug` stays central (it reads every sub-system's counters); fine as
  is.
