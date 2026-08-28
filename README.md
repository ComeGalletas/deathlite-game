# Death Lite Die

An original 2D action roguelite / bullet-heaven built with Python + Pygame.
Inspired by the genre (time-survival, auto-attacks, XP, level-up choices,
roguelite progression). All game *content* — design, code, data, and the
procedurally synthesised sound effects — is original. **All art** (heroes, every
enemy + the boss, terrain, props) is from the **"Tiny Swords" pack by Pixel
Frog**; the standalone title-screen illustration is separate — see
[`assets/CREDITS.md`](assets/CREDITS.md). Every sprite is an optional layer over
a primitive fallback, so the game runs with an empty `assets/`.

## Requirements

- Python 3.12+
- Pygame 2.x (installed into a local virtualenv, see below)

## Setup

```bash
cd deathlite-game
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install pygame
```

## Run

```bash
python main.py
```

(or without activating: `.venv\Scripts\python.exe main.py`)

## Run the tests

```bash
python -m unittest discover -s tests -v
```

391 tests: pure logic plus headless integration (SDL dummy video/audio driver)
covering boot, a full state walk, the death/dying lifecycles, sprite slicing,
terrain tiling / bridge corridors / the decoration scatter / obstacle skins,
depth-sorted rendering, the start menu + options + rankings screens, developer
mode, the difficulty knobs (spawn cadence / phase + boss pacing / HP ramp /
enemy-count growth) and per-difficulty records, the per-hit damage model, and
the interactables.

## Controls

| Key | Action |
|-----|--------|
| WASD / Arrow keys | Move; also navigate menus |
| ENTER or SPACE | Confirm / start / select a menu entry / buy / equip |
| ← → (hero select) | Choose the hero · ↑ ↓ choose the **difficulty** (Normal / Fast / Super Fast) |
| ← → (Options) | Adjust the master volume |
| E | Use a special location you're standing on (shrine, chest, fountain, altar, merchant) |
| ESC | Pause (in game) / back / quit (from the start menu) |
| S (run summary) | Open the **Sanctuary** (meta upgrades + item stash) — from the start menu it's under **Options** |
| TAB (Sanctuary) | Switch between Upgrades and Stash · U unequips |
| 1 / 2 / 3 or ← → + ENTER | Choose a level-up upgrade / blessing |
| M | Mute / unmute audio (persisted); also an **Options** toggle |
| F1 | Toggle debug overlay (FPS, per-system counts, run seed, hero, timings) |
| F2–F7 | Spawn enemy / grant XP / force level / spawn boss / invuln / collision vis |

Debug keys are never required for normal play.

Weapons attack automatically — you only move, pick upgrades/blessings, use
special locations, and choose a hero and difficulty. The world is a procedural
graph of rooms and corridors with obstacles; explore it, survive the escalating
waves, and the boss (**The First Hunger**) appears in its arena near the end of
the run and drops an item. Salvage and loot carry over between runs via the
Sanctuary.

### Display

The window is **1600×900** (`config.SCREEN_WIDTH/HEIGHT`). The in-game view is a
**draw-time camera zoom** (`config.CAMERA_ZOOM`, default 1.5): the world is drawn
straight to the screen with every sprite, tile and shape scaled by the zoom, so
the picture is "closer" but stays crisp — sprites scale *down* from their large
source frames, no upscale blur. The visible world extent is `SCREEN / CAMERA_ZOOM`.
The HUD and damage feedback are drawn afterwards at full resolution, unscaled.
`CAMERA_ZOOM = 1.0` disables the zoom entirely.

### Start screen

A keyboard-navigated menu: **Start new game** → hero + difficulty select → run;
**Start new developer mode game** → the same select screen → a non-persistent
sandbox run with the dev overlay (backtick / tilde); **Rankings**; **Options**;
**Exit**. Options holds the **master volume** (← → in 5% steps), a **mute**
toggle, and the entry point into the **Sanctuary** — all persisted to
`save.json` immediately. If `assets/ui/title.png` exists it fills the screen
as the backdrop (with a translucent panel behind the menu for legibility);
without it the screen is plain black with the title as white text. The game
instructions sit in their own smaller column to the left of the menu.

### Difficulty

Picked per run on the hero-select screen (**↑ ↓**), never persisted:

| | Enemy spawn rate | Harder types + boss | Enemy HP/speed ramp | Crowd growth |
|---|---|---|---|---|
| **Normal** | — | — | — | +5 enemies / 20 s |
| **Fast** | +25% | 25% sooner (run ends sooner) | +25% faster | +8 / 20 s |
| **Super Fast** | +50% | 50% sooner | +50% faster | +10 / 20 s |

The stat ramp accelerates in step with the shorter run, so a faster run still
reaches the full HP/speed curve by its (earlier) end. In a **developer** run the
dev overlay has a **Difficulty** row that switches this live. **Rankings** (on
the start menu) keeps a separate best run — time, level, kills, damage — for
each difficulty; they are never compared across difficulties.

Progress is stored in `save.json` next to `main.py` (human-readable; a missing
or corrupt file is handled gracefully — the game never crashes over it).

## Project layout

```
deathlite-game/
├── main.py             thin entry point
├── game/               loop, state machine, config, event bus, content,
│   │                   save, assets (sprite loader/cache)
│   └── states/         one module per game state (menu, options, rankings,
│                       char-select, playing, level-up, paused, game-over,
│                       victory, sanctuary, dev menu)
├── entities/           player, enemy (+ ai), boss, projectile, pickup,
│                       summon, hazard, obstacle, interactable
├── systems/            camera, spatial grid, object pool, particles,
│                       screen shake, audio, animation, debug overlay
├── combat/             weapons, damage, targeting, status
├── progression/        experience, stats, upgrades, blessings, items, meta
├── world/              map, spawning (director), procedural (world gen)
├── ui/                 hud, level-up panel, damage numbers
├── data/               JSON content (weapons, enemies, bosses, characters,
│                       blessings, items, meta_upgrades, sprites, terrain)
├── assets/             characters/<colour>/<unit>/, enemies/<mob>/,
│                       projectiles/, terrain/{tiles,bridge,props,resources}/,
│                       buildings/, effects/, ui/title.png, CREDITS.md
│                       (PNG sprites only — see assets/CREDITS.md)
└── tests/              391 tests: pure logic + headless integration
```

## Content

- **3 heroes**, each with a distinct trait (hold-ground damage reduction /
  momentum stacking / status-on-first-hit) and starting weapon
- **7 weapons**: single-target bolt, piercing fan, chain lightning, orbiting
  embers, reaping cone, summon totem, summon wolf
- **13 enemy variants** (incl. 3 FSM-driven: charger, teleporter, area-denial
  warlock) + **1 boss** with 3 telegraphed attack patterns and a health bar
- **32 blessings** across 4 sources, interacting through tags and status effects
- **5 status effects** (burn / poison / bleed / chill / shock) on a generic
  data-driven framework
- **17 item affixes**, 5 rarities, seeded deterministic item generation
- **6 meta-progression upgrades**, corruption-tolerant JSON save/load
- Seeded **procedural world**: room-graph + corridors + obstacles, with a boss
  arena; **6 special locations** (shrine, treasure, fountain, altar, merchant,
  elite arena)
- XP / leveling with a weighted 3-choice upgrade & blessing screen
- Phase-based spawn director; a per-run **difficulty** (Normal / Fast / Super
  Fast) drives four independent knobs — spawn rate, how fast the phase schedule
  and boss arrive, the enemy HP/speed ramp, and the enemy-count growth — with a
  separate best-run ranking per difficulty
- Procedurally synthesised sound effects (no audio files)
- Animated sprites for all 3 heroes, all 13 enemies + the boss, and enemy shots;
  a red hit-tint and a shared skull death-poof stand in for the missing
  hurt/death strips. A data-driven `if sprite: … else: shape` layer keeps the
  game fully playable with an empty `assets/`
- **Tiled terrain**: procedural rooms rendered as a grass tileset with autotile
  edges over a tiled water void; corridors are directional plank **bridges**;
  animated shoreline foam sits *behind* the terrain and shows through the
  transparent tile fringes and the bridge plank gaps. A seeded, data-driven
  **decoration scatter** adds non-colliding clutter on room interiors and water
  scenery (rocks, a duck) on the open water. Every circular obstacle draws as a
  decoration sprite (animated tree / bush / rock) scaled to its collider; trees
  also cast a soft round shade over the characters. Obstacles, clutter and the
  characters are painted back-to-front by ground-contact Y, so the hero walks
  *behind* a tree when above it. Each layer is a `config` flag and the whole
  thing falls back to flat coloured rects + drawn circles if the tileset is absent
- Object pooling, spatial-grid collision, a difficulty-scaled enemy-count cap
  that grows with in-game time, F1 debug overlay with per-system timings + the
  run seed

## Development status

**Phases 1–3 complete — feature-complete against the spec.** The full loop
runs: pick hero + difficulty → explore the procedural world → auto-combat → XP →
upgrade / blessing choices → special locations → escalating waves → boss (in its
arena, drops an item) → victory / defeat → Salvage & loot banked → Sanctuary
(spend, equip) → next run inherits it. Phase 4 adds the per-run difficulty
(Normal / Fast / Super Fast) and per-difficulty Rankings.

Not done: balance is a first tuning pass (needs human playtesting); one boss
(the spec's Phase-1 floor); a few polish items listed in `journals/journal.md`.

## Assets

Sprites are an optional cosmetic layer over the primitive renderer. Metadata
(sheet paths, frame size, per-animation fps/loop, a `content` crop, `scale`,
`anchor`) lives in `data/sprites.json`; `game/assets.py` loads and caches
frames (sliced, scaled, flipped, rotated — all memoised), and returns `None`
for a missing file so the caller falls back to a shape. A character opts in via
a `"sprite"` key in its data.

Currently sprited: all **3 heroes** (Aegis = blue Warrior, Kestrel = yellow
Archer, Nihil = purple Monk), **all 13 enemy variants + the boss**, and the
enemy-shot arrow. The pack ships no `hurt` / `death` strips, so on a hit the live
frame is **red-tinted** in place (no pop to a circle) and on death *any* entity
plays one shared one-shot **skull poof** (`characters/dead/dead.png`; enemy poof
at 55 %, hero at full size). Each hero's `color` in `data/characters.json` is its
primitive-fallback tint. Only XP gems and the HUD still draw as shapes.
**Obstacles** are skinned by the terrain decoration rigs (below), not
`sprites.json`. See `assets/CREDITS.md` for the pack layout.

The **world** is tiled from `data/terrain.json` — a slot table (which sheet
index is the interior / edge / corner tile), a `bridge` block (the corridor
plank autotile), a `decorations` array (the non-colliding scatter registry), an
`obstacle_decor` map (obstacle kind → decoration rigs + a size boost + the
tree-shade params), and the rigs themselves (each with a measured
`footprint`). `GameMap` pre-renders each static room to one **SRCALPHA** surface
(autotile edges baked in, transparent water side preserved) and each corridor to
a directional plank bridge, tiles the water void into a reusable buffer,
draws the 16-frame `Water_Foam` animation *behind* the terrain along shorelines
and bridge gaps, scatters seeded non-colliding clutter (`pebble_*` on interiors,
`water_rock_*` / `duck` on the open water), and skins each circular obstacle with
a decoration sprite scaled so its footprint covers the collider (`tree` →
animated `deco_tree_*`, `shrub` → bushes, `rock`/`pillar` → rocks; the
`Obstacle.variant` picks which of four). Trees additionally cast a soft round
shade that is drawn over the hero / enemies, so standing under one darkens you.
Every layer is a `config` flag (`TERRAIN_FOAM`, `TERRAIN_DECORATIONS`,
`TERRAIN_DECOR`, `TERRAIN_SHADOWS`) and the whole terrain degrades to the flat
renderer (drawn circles) if the tileset is missing.

The **start menu** is the one screen with its own palette (`config.MENU_*`):
black background, white text. `Assets.picture()` loads `assets/ui/title.png`
(if present) and it's scaled to fill the screen as a backdrop, with a
translucent scrim (`config.MENU_SCRIM`) behind the option list. No file → the
`config.TITLE` string is drawn as the fallback and the screen stays plain black.

Every third-party pack (character sprites, terrain, title art) and its licence
must be confirmed in `assets/CREDITS.md` before distribution.

Project logs live in `journals/`: `journal.md` (full milestone log),
`transcript.md` (the key decision behind each step), `assets_journal.md`
(sprite / terrain integration), `dev_mode_journal.md` (developer mode),
`combat_balance_journal.md` (combat-model / tuning changes) and `BUG_JOURNAL.md`
(confirmed defects). Design references are under `documentation/`
(`COMBAT_CALCS.md` — damage; `level_design.md` — world generation & the
asset-backed vs primitive renderers; `terrain_tile_slots_formula.md` — how a
tilemap cell is addressed, cut and placed).
