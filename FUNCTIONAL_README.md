# Deathlite Game — functional reference

How the game is built, tested, packaged and wired. The player-facing
overview — what the game is, how to run it, the controls, the content — is
[`README.md`](README.md); packaging details per target are under
[`dist/README.md`](dist/README.md); world generation and terrain rendering
have their own walkthrough in [`world/README.md`](world/README.md).

## Play in the browser

The game also builds to WebAssembly with [pygbag](https://pygame-web.github.io/).
The loop is `asyncio`-driven (`Game.run_async`), so one code path serves the
desktop and web builds. `main.py` is the only entry point; under the emscripten
runtime (or with `--web` on the desktop) it calls `config.apply_web_profile()` —
**session-only save** (never reads or writes `save.json`), **60 fps** to match
the browser compositor, and a **1280×720** render target that keeps the desktop
field of view while cutting per-frame work ~35%.

Everything else pygbag needs lives in `dist/web/` (`pygbag.ini`, `build.sh`,
`serve.sh`, and `dist/web/README.md` with the details):

```bash
bash dist/web/serve.sh   # rebuild + serve at http://localhost:8000
bash dist/web/build.sh   # build only -> dist/web/out/  (gitignored)
```

First run downloads a CPython-WASM runtime (cached after). Mixer bring-up is
platform-specific behind `systems/mixer_backend.py` (desktop re-inits at
44100 Hz stereo and resamples the 22050 Hz synth cues up to it; the browser
keeps the WebAudio context it was given and resamples to that instead).
Fonts are the bundled **Fredoka** face (`assets/fonts/`, via `game/fonts.py`).
See `documentation/journals/pygbag.md` for the full plan and the GitHub Pages deploy steps.

## Build for distribution

All packaging lives under `dist/`, one folder per target, with `dist/README.md`
as the index. The Windows desktop build is a PyInstaller `onedir` bundle:

```powershell
powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Zip
```

That produces `dist/desktop/out/DeathliteGame-<version>.zip` (gitignored); the
recipient unzips it anywhere and runs `DeathliteGame.exe`. Details and the
diagnostic `-Console` build are in `dist/desktop/README.md`. A packaged build
keeps its save in `%LOCALAPPDATA%\DeathliteGame\` (`main.py` checks
`sys.frozen`); running from source uses the repo-root `save.json`.

## Run the tests

```bash
python -m pytest
```

That is the `unit`, `world` and `integration` tiers (see `pytest.ini`). While
you work, the `unit` tier is the one to keep under a keystroke — hand-built
grids and fakes, nothing generated and no window opened:

```bash
python -m pytest -m unit
```

| tier | what it does | tests | time |
|------|--------------|------:|-----:|
| `unit` | hand-built grids and fakes | 1,133 | 50 s |
| `world` | the four cached worlds in `tests/worlds.py` | 525 | 2 min 57 s |
| `integration` | boots a real `Game` and drives its states | 503 | 6 min 29 s |
| `sweep` | many seeds, statistical | 8 | 2 min 18 s |

The default `python -m pytest` is the first three together: 1,643 tests in
8 min 40 s.

The `sweep` tier makes statistical claims over many seeds and runs before a
commit:

```bash
python -m pytest -m sweep
```

Everything, under the standard library runner (no tiers):

```bash
python -m unittest discover -s tests -t .
```

`tests/` is split by subject into `__init__.py` sub-packages (the tree is in
*Project layout* below), so only the shared helpers sit at the root:
`worlds.py` (the world cache), `boot.py` (drives the loading screen to a run
inside a test), `nearby.py` (a spot beside the hero an enemy can stand on),
`aictx.py` (the fake AI context) and `conftest.py` (tier markers, assigned by
path so no test module imports pytest). `-t .` makes the modules import as
`tests.<area>.<name>` so the `combat` / `world` / `systems` / `progression`
/ `spawn` folders don't shadow the same-named source packages.

A world is generated once per seed per process. A test that needs to mutate
one takes `worlds.fresh(seed)`; one that changes generation settings passes
them as keywords (`worlds.layout(seed, HEIGHTMAP_UNSEAL=False)`) and gets a
separately cached build. `tests/world/test_digest.py` pins a fingerprint of
the layout, the bake and one drawn frame for each cached seed; a change that
moves the world says so and runs `python -m tools.verification.world_digest --write`.
A test that boots a run pins its seed: an unpinned world is a coin flip.

1,650 tests: pure logic plus headless integration (SDL dummy video/audio driver)
covering boot, a full state walk, the death/dying lifecycles, sprite slicing,
terrain tiling / bridge corridors / the decoration scatter / obstacle skins,
depth-sorted rendering, the start menu + options + rankings screens, developer
mode, the difficulty knobs (spawn cadence / phase + boss pacing / HP ramp /
enemy-count growth) and per-difficulty records, the per-hit damage model, and
the interactables.

There is no CI and none is planned: the suite is run locally, for stability.

## Developer keys and tools

| Key | Action |
|-----|--------|
| F1 | Toggle debug overlay (FPS, per-system counts, run seed, hero, timings) |
| F2–F6 | Spawn enemy / grant XP / force level / spawn boss / toggle invuln |
| F7 | Toggle the **collision-shape overlay** — *developer runs only*; also a dev-menu row |
| F8 | Toggle the generated **spawn points** overlay — developer runs only |
| ` / ~ | The **dev menu** in a developer run: HP / attack / overlay toggles, spawn any enemy, grant any blessing, item or weapon, apply any Forging, remove owned weapons, switch difficulty live, freeze spawns, activate every room, place the training dummy, reset the run |

Debug keys are never required for normal play. To see the real circular
colliders, start a developer run and press **F7**: hero / enemy / boss /
obstacle bodies in green, pickup radius and projectile hitboxes dimmer.

`tools/` holds the scripts that are not part of the game:

- `tools/asset_pipeline/` — cutting delivered art and audio into the strips
  the game reads (`cut_*`, `slice_tree_sheet`, `build_ground_tilemaps`,
  `sprite_sheet_lab`, `key_sheet`, `make_icon`, `cut_sound_effects`).
- `tools/benchmarks/` — `dps_bench` (the training-dummy DPS bench, composed by
  hero level through the real offering) and `spawn_stress`.
- `tools/verification/world_digest.py` — the pinned layout / bake / frame
  fingerprints the `world` tier checks.
- `tools/verification/run_digest.py` — a fingerprint of a headless run (two
  pinned seeds, 720 frames, debug spawns thrown in): `--check` after a
  change to the run's wiring says whether the same seed still plays the
  same frames. Pins Python's hash seed itself; not a test.
- `tools/gen_weapon_tables.py` — generates the weapon / blessing / forge
  reference tables from the data JSON (Markdown for `documentation/designs/`,
  plus an HTML body); run from the repo root with the output paths as
  arguments.

## Display internals

The window is **1600×900** (`config.SCREEN_WIDTH/HEIGHT`) in design pixels;
`game/display/` scales that frame into whatever window the player picked
(windowed / borderless, the Resolution row, drag resizes) and `ui/scale.py`
is the one seam between design pixels and native pixels. The in-game view is
a **draw-time camera zoom** (`config.CAMERA_ZOOM`, default 1.5): the world is
drawn straight to the screen with every sprite, tile and shape scaled by the
zoom, so the picture is "closer" but stays crisp — sprites scale *down* from
their large source frames, no upscale blur. The visible world extent is
`SCREEN / CAMERA_ZOOM`. The HUD and damage feedback are drawn afterwards at
full resolution, unscaled, into the centred 16:9 **UI box**
(`game/display/uibox.py`; on a 21:9 render the world fills the width and the
interface stays where a 16:9 player sees it). `CAMERA_ZOOM = 1.0` disables the
zoom entirely. Keep `TILE_PX * CAMERA_ZOOM` a whole number of pixels — steps of
0.25 at the 64 px tile — or the tile grid lands on fractional boundaries and
the seams shimmer.

A **sprited** enemy is just its sprite — the thin elite / shield / status rings
that used to sit at the collider edge are off by default
(`config.SHOW_ENEMY_STATE_RINGS`); primitive-fallback enemies (no tileset)
always keep them. Attack telegraphs (the red slam ring) are always shown.

Object pooling (`systems/object_pool.py`), spatial-grid collision
(`systems/collision.py`), a difficulty-scaled enemy-count cap that grows with
in-game time, and the F1 overlay with per-system timings and the run seed are
the performance scaffolding the run sits on.

## Project layout

```
deathlite-game/
├── main.py             entry point (async loop); `--web` / emscripten applies
│                       the browser profile
├── dist/               packaging, one folder per target: desktop/ (PyInstaller
│                       spec + build.ps1), web/ (pygbag.ini, build.sh, serve.sh);
│                       each target's output lands in its own out/ (gitignored)
├── game/               loop, state machine, config, event bus, content,
│   │                   save, assets (sprite loader/cache), fonts
│   ├── display/        the window the fixed frame is scaled into: fit maths,
│   │                   ctypes SDL calls, DisplayWindow, the UI box
│   └── states/         one module per game state (menu, options, rankings,
│                       char-select, loading, level-up, paused, run-status,
│                       game-over, victory, end-banner, sanctuary, dev menu);
│                       `playing/` is a package — core/ (the PlayingState
│                       coordinator over a `Run` context, plus combat /
│                       effects / spawning / rewards / run end / hero /
│                       locations / buffs / chests / npcs / fish huts /
│                       navigation / physics / hints / run ledger),
│                       visual/ (the scene composition, the world renderer,
│                       projectile and summon painters, slash / slam fx,
│                       glow, key marker) and devtools/ (the dev flags and
│                       overlays, the DPS meter)
├── entities/           player, enemy (+ ai/: the component FSM, behaviours,
│                       registry), boss, npc, projectile, pickup, potion,
│                       chest, summon, hazard, obstacle, interactable
├── spawn/              the spawn master: points, tables, budget (director),
│                       roster, placement, locality, population, watchdog,
│                       the Host protocol and the SpawnMaster facade
├── systems/            camera, spatial grid, object pool, particles, screen
│                       shake, audio (+ mixer backend), music, animation,
│                       debug overlay
├── combat/             weapons/ (core, bomb, slam, forge), damage,
│   │                   targeting, status, knockback, synergy, weapon visuals
│   └── elements/    the four elements and their six reactions: ids,
│                       schema/config (the JSON tuning), registry,
│                       modifiers, aura state, the resolver, fire / ice /
│                       thunder / wind, reactions/, spread, tracking
├── progression/        experience, stats, upgrades, blessings/ (catalog,
│                       offer, apply, effects), items, potions, chests, meta
├── world/              layout (the WorldLayout data model); gen/ (seeded
│                       generation: one module per stage, height/ for the
│                       island height maps, village/ for the human island,
│                       settings + validate); rules/
│                       (floor, steps, inset, frontier, biome, spacing —
│                       shared by generation, bake and runtime); elevation
│                       (LevelIndex); map (GameMap: the collider, holding the
│                       BakedTerrain); terrain/ (sheets, autotile, grid_paint,
│                       decor/, bake -> BakedTerrain, render); nav/ (NavGrid,
│                       clearance, flow field); spawning (the no-layout ring
│                       rule)
├── ui/                 hud, bars/ (meters, medallion), level-up panel, forge
│                       rail, damage numbers, keycap hints, buff banner and
│                       marks, run summary (the game-over résumé), end screen,
│                       run_status/ (the TAB build screen's panes), mouse
│                       (HitMap, MouseNav), menu_nav (the menus' shared
│                       cursor + hover rules), widgets (buttons, ribbons),
│                       panels, text, scale
├── tools/              asset_pipeline/ (cutting delivered art and audio),
│                       benchmarks/ (dps_bench, spawn_stress), verification/
│                       (world_digest), gen_weapon_tables
├── data/               JSON content, split by domain: heroes/ (characters,
│                       meta upgrades, rigs), enemies/ (enemies, bosses, spawn
│                       tables, rigs), weapons/ (weapons, blessings, offering,
│                       forges, items, rigs, visuals), loot/ (chests, potions,
│                       prop rigs), village/ (npcs), world/ (terrain,
│                       buildings), ui/ (ui rigs)
├── assets/             characters/<colour>/<unit>/, enemies/<mob>/,
│                       projectiles/, terrain/{tiles,bridge,props,resources}/,
│                       buildings/, effects/, items/, ui/, fonts/, music/,
│                       sound_effects/, CREDITS.md; unused/ is gitignored
│                       reserve art
├── documentation/      designs/ (the spec and the design references),
│                       plans/ (what is to be done), journals/ (what was done),
│                       dps_calcs/
└── tests/              1,650 tests: pure logic + headless integration
    ├── combat/         weapons, damage, status, forges, synergies, summons,
    │                   elements (config, auras, hits, the six reactions)
    ├── entities/       ai/ (behaviours, FSM enemies, boss), characters,
    │                   movement, hero animation, npcs, fish huts, pickups
    ├── playing/        the run's sub-systems: buffs, bump, chests, gold,
    │                   hints, manual aim, nav, potions, projectiles, ledger
    ├── progression/    xp, stats, upgrades, blessings, items, meta, potions
    ├── render/         depth sort, terrain, biomes, sprites, projectiles,
    │                   glows, ghosts, culling
    ├── screens/        every menu and overlay, the HUD, the widgets
    ├── spawn/          the spawn master phase by phase
    ├── world/          generation, height maps, repair, spawn points, digests,
    │                   layering, elevation, villages, decor
    ├── systems/        object pool, audio, music, sound effects, collision,
    │                   camera, animation, assets, fonts, save, events, the
    │                   state machine
    ├── display/        window fit, native calls, the UI box
    ├── devtools/       the DPS meter and bench
    ├── flows/          smoke boot, controls, dev mode, loading, hero unlock,
    │                   display changes mid-run
    └── worlds.py, boot.py, nearby.py, aictx.py, conftest.py (helpers)
```

## Assets — how they are wired

Sprites are an optional cosmetic layer over the primitive renderer. Metadata
(sheet paths, frame size, per-animation fps/loop, a `content` crop, `scale`,
`anchor`) lives in the domain-split rig files — `data/heroes/character_sprites.json`,
`data/enemies/enemy_sprites.json`, `data/weapons/weapon_sprites.json`,
`data/loot/prop_sprites.json` — merged into one namespace by
`game/content.py` (`data/ui/ui_sprites.json` is loaded beside them as its
own); `game/assets.py` loads and caches frames (sliced, scaled,
flipped, rotated — all memoised), and returns `None` for a missing file so the
caller falls back to a shape. A character opts in via a `"sprite"` key in its
data.

The pack ships no `hurt` / `death` strips, so on a hit the live frame is
**red-tinted** in place (no pop to a circle) and on death *any* entity plays
one shared one-shot **skull poof** (`characters/dead/dead.png`; enemy poof at
55 %, hero at full size). Each hero's `color` in `data/heroes/characters.json`
is its primitive-fallback tint. Only XP gems and the HUD still draw as shapes.
**Obstacles** are skinned by the terrain decoration rigs (below), not the
`*_sprites.json` files. See `assets/CREDITS.md` for the pack layout.

The **world** is tiled from `data/world/terrain.json` — a slot table (which sheet
index is the interior / edge / corner tile), a `bridge` block (the corridor
plank autotile), a `decorations` array (the non-colliding scatter registry), an
`obstacle_decor` map (obstacle kind → decoration rigs + a size boost + the
tree-shade params), and the rigs themselves (each with a measured
`footprint`). The bake (`world/terrain/bake.py`) pre-renders each island to one
**SRCALPHA** surface per terrace (autotile edges baked in, transparent water
side preserved) and each corridor to a directional plank bridge, tiles the
water void into a reusable buffer, draws the 16-frame `Water_Foam` animation
*behind* the terrain along shorelines and bridge gaps, scatters seeded
non-colliding clutter (`pebble_*` on interiors, `water_rock_*` / `duck` on the
open water), and skins each circular obstacle with a decoration sprite scaled
so its footprint covers the collider (`tree` → animated `deco_tree_*`, `shrub`
→ bushes, `rock`/`pillar` → rocks; the `Obstacle.variant` picks which of four).
Trees additionally cast a soft round shade that is drawn over the hero /
enemies, so standing under one darkens you. Every layer is a `config` flag
(`TERRAIN_FOAM`, `TERRAIN_DECORATIONS`, `TERRAIN_DECOR`, `TERRAIN_SHADOWS`) and
the whole terrain degrades to the flat renderer (drawn circles) if the tileset
is missing. The full walk from `generate_world` to a drawn frame is
[`world/README.md`](world/README.md).

The **start menu** is the one screen with its own palette (`config.MENU_*`):
black background, white text. The backdrop is
`assets/ui/start_screen/menu_background.png` (`config.MENU_BACKGROUND_IMAGE`),
or the 21:9 `menu_background_long.png` on an ultrawide render; it falls back to
`config.MENU_TITLE_IMAGE`, then to the flat `MENU_BG` fill. The logo above the
option list is `config.MENU_LOGO_IMAGE`; without it the title is drawn as text.

Every third-party pack (character sprites, terrain, title art) and its licence
must be confirmed in `assets/CREDITS.md` before distribution. Delivered audio
is reviewed and cut to the usable part, renamed by purpose, its source
archived and credited by author; a source art grid, once cut into the strip the
game reads, goes to an `unused/` folder beside the strip.

## Development status

**Phases 1–3 complete — feature-complete against the spec.** The full loop
runs: pick hero + difficulty → explore the procedural world → auto-combat → XP →
upgrade / blessing choices → the village forge and fountain, the buff
buildings and the chests → escalating waves → boss (in its
arena, drops an item) → victory / defeat → Salvage & loot banked → Sanctuary
(spend, equip) → next run inherits it. Phase 4 adds the per-run difficulty
(Normal / Fast / Super Fast) and per-difficulty Rankings.

**Game over** shows the run's résumé (`ui/run_summary.py`): time, level,
kills, gold and Salvage, the items acquired; kills per enemy type and the
blessings with their levels; and the damage done per weapon with its DPS over
the time the weapon was held, fed by a run-wide ledger every enemy reports
to (`game/states/playing/core/run_ledger.py`). Three buttons — New run, Sanctuary,
Main menu — take the mouse or ENTER / S / ESC. See
`documentation/journals/game_over_journal.md`.

**TAB during a run** opens the build screen (`game/states/run_status_state.py`,
panes in `ui/run_status/`), an overlay that freezes the run: Overview (the
run line, the hero's resolved stats, the equipped items with what each one
gives), Build (a card per weapon with its live numbers and Forge gate, the
selected weapon's Forging with every number it changed, the synergies) and
Blessings (the owned blessings and the selected one's card text at its
current level). Also reachable from the pause menu's "Run status" row. See
`documentation/journals/run_status_journal.md`.

**Elemental infusions.** Four elements — Fire, Ice, Thunder, Wind — can be
attached to a weapon slot for the run, from the village Monastery or a buff
building. An infused weapon's hits land normally and then apply their element
(`core/combat.py:apply_element`, the system's one entry point, which every
hero damage path already funnels through: shots, melee cones, chains,
orbiters, blasts, summon bites, crater ticks). Each element does something of
its own — Fire burns, Ice stacks toward a freeze, Thunder chains to
neighbours, Wind knocks back and leaves a tornado — and each one leaves an
**aura** on what it hit.

An aura is what makes the system more than four damage types: land a
*different* element on a body that already carries one and the pair produces
a **reaction** — Frostburn, Overload, Superconduct, FireWind, IceWind,
ThunderWind — which consumes the aura and locks the slot briefly. A weapon
inflicts its element on a cadence of its own (`element_application` in
`data/weapons/weapons.json`): every Nth attack, or once per time window for
the summons and the orbiters, which never fire an "attack" to count.

A reaction is paid from **both** hits that met on that body — the one that
placed the aura and the one that triggered it — as `high × the larger +
low × the smaller`, so a heavy primer still pays when a feeble hit sets it
off. The same figure lands on the enemy it fired on and on everything it
reaches, raised to a floor (`reaction_min_damage`) on the carrier alone. The
three Wind reactions and Superconduct also **prime what they reach with
their own element**, so a reaction can set off another one; the brakes on
that cascade are the per-enemy aura lock and the per-frame reaction budget,
and it is documented at `ElementalResolver.spread_aura`. Overload and
Frostburn spread nothing and stay terminal. See
`documentation/journals/reaction_damage_rework_journal.md`.

Elements are code and JSON only tunes them: the behaviours are
`combat/elements/`, the numbers are `data/weapons/elements.json` and
`reactions.json`, and how they look is `element_visuals.json`, split off the
same way `weapons.json` and `weapon_visuals.json` already are. A killing blow
still fires the element's *outward* effects — the chain, the tornado, the
reaction — but writes nothing to the body it killed. See
`documentation/journals/elemental_system_journal.md`.

Not done: balance is a first tuning pass (needs human playtesting); one boss
(the spec's Phase-1 floor); a few polish items listed in `documentation/journals/journal.md`.
`documentation/plans/pending_plans.md` is the standing list of everything
designed or built but not yet wired up.

## Documentation map

Everything written about the project lives under `documentation/`, in three
kinds of file:

- **`documentation/journals/`** — what was *done*, in order, with the numbers:
  `journal.md` (full milestone log), `transcript.md` (the key decision behind
  each step), `assets_journal.md` (sprite / terrain integration),
  `dev_mode_journal.md` (developer mode), `combat_balance_journal.md`
  (combat-model / tuning changes), `bug_journal.md` (confirmed defects) and one
  journal per workstream (`weapon_system_journal.md`, `spawn_master_journal.md`,
  `level_design_journal.md`, `human_island_journal.md`,
  `structure_review_journal.md`, ...). A feature request gets its own journal
  before and while it is built.
- **`documentation/plans/`** — what is *to be done*, and in what order:
  `weapon_system_plan.md`, `worldgen_refactor_plan.md`, `spawn_master_todo.md`,
  `boss_free_roam_todo.md`, `fluidity_plan.md`, `web_plan.md` and
  `test_suite_review.md`. `pending_plans.md` is the standing list of everything
  designed or built but not yet wired up.
- **`documentation/designs/`** — design references that describe how the game
  *works*: `death_must_die_lite_game_spec.md` (the spec),
  `combat_calculations.md` (damage), `level_design.md` (world generation and
  the asset-backed vs primitive renderers), `spawn_master_design.md`,
  `six_weapon_system_design.md`, `weapon_blessing_forge_tables.md`,
  `sprite_functionality.md` and `terrain_tile_slots_formula.md` (how a tilemap
  cell is addressed, cut and placed).
