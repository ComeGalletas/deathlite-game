# Death Lite Die

An original 2D action roguelite / bullet-heaven built with Python + Pygame.
Inspired by the genre (time-survival, auto-attacks, XP, level-up choices,
roguelite progression). All content is original; no third-party names, art or
assets.

## Requirements

- Python 3.12+
- Pygame 2.x (installed into a local virtualenv, see below)

## Setup

```bash
cd death_lite_die
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

Tests cover pure logic only (no display needed) and a headless boot smoke test.

## Controls

| Key | Action |
|-----|--------|
| WASD / Arrow keys | Move; also navigate menus |
| ENTER or SPACE | Confirm / start / buy / equip |
| E | Use a special location you're standing on (shrine, chest, fountain, altar, merchant) |
| ESC | Pause (in game) / back |
| S (menu or summary) | Open the **Sanctuary** (meta upgrades + item stash) |
| TAB (Sanctuary) | Switch between Upgrades and Stash · U unequips |
| 1 / 2 / 3 or ← → + ENTER | Choose a level-up upgrade / blessing |
| M | Mute / unmute audio (persisted) |
| F1 | Toggle debug overlay (FPS, per-system counts, run seed, hero, timings) |
| F2–F7 | Spawn enemy / grant XP / force level / spawn boss / invuln / collision vis |

Debug keys are never required for normal play.

Weapons attack automatically — you only move, pick upgrades/blessings, use
special locations, and choose a hero. The world is a procedural graph of rooms
and corridors with obstacles; explore it, survive the escalating waves, and the
boss (**The First Hunger**) appears in its arena near the end of the run and
drops an item. Salvage and loot carry over between runs via the Sanctuary.

Progress is stored in `save.json` next to `main.py` (human-readable; a missing
or corrupt file is handled gracefully — the game never crashes over it).

## Project layout

```
death_lite_die/
├── main.py             thin entry point
├── game/               loop, state machine, config, event bus, content, save
│   └── states/         one module per game state (menu, char-select, playing,
│                       level-up, paused, game-over, victory, sanctuary)
├── entities/           player, enemy (+ ai), boss, projectile, pickup,
│                       summon, hazard, obstacle, interactable
├── systems/            camera, spatial grid, object pool, particles,
│                       screen shake, audio, debug overlay
├── combat/             weapons, damage, targeting, status
├── progression/        experience, stats, upgrades, blessings, items, meta
├── world/              map, spawning (director), procedural (world gen)
├── ui/                 hud, level-up panel, damage numbers
├── data/               JSON content (weapons, enemies, bosses, characters,
│                       blessings, items, meta_upgrades)
└── tests/              181 tests: pure logic + headless integration
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
- Phase-based spawn director with independent difficulty knobs
- Procedurally synthesised sound effects (no audio files)
- Object pooling, spatial-grid collision, configurable entity caps, F1 debug
  overlay with per-system timings + the run seed

## Development status

**Phases 1–3 complete — feature-complete against the spec.** The full loop
runs: pick hero → explore the procedural world → auto-combat → XP → upgrade /
blessing choices → special locations → escalating waves → boss (in its arena,
drops an item) → victory / defeat → Salvage & loot banked → Sanctuary (spend,
equip) → next run inherits it.

Not done: balance is a first tuning pass (needs human playtesting); one boss
(the spec's Phase-1 floor); a few polish items listed in `journal.md`.

See `journal.md` for the full milestone log and `transcript.md` for the key
decisions behind each step.
