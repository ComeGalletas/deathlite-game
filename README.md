# Deathlite Game

An original 2D action roguelite / bullet-heaven built with Python + Pygame.
Inspired by the genre (time-survival, auto-attacks, XP, level-up choices,
roguelite progression). All game *content* — design, code, data, and the
procedurally synthesised sound effects — is original. **All art** (heroes, every
enemy + the boss, terrain, props) is from the **"Tiny Swords" pack by Pixel
Frog**; the standalone title-screen illustration is separate — see
[`assets/CREDITS.md`](assets/CREDITS.md). Every sprite is an optional layer over
a primitive fallback, so the game runs with an empty `assets/`.

This file is the player's overview. How the game is built, tested, packaged
and wired is in [`FUNCTIONAL_README.md`](FUNCTIONAL_README.md); the packaged
builds (Windows `.exe`, browser) are documented under
[`dist/README.md`](dist/README.md).

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

Progress is stored in `save.json` next to `main.py` (human-readable; a missing
or corrupt file is handled gracefully — the game never crashes over it).

## Controls

| Key | Action |
|-----|--------|
| WASD | Move (menus: navigate). **Key layout** in Options / pause swaps this with the arrows |
| Arrow keys | **Aim** while held: the hero attacks that way, auto attack on or off (menus: navigate) |
| Left click | In a run: attack toward the cursor — tap for one attack, hold to keep attacking; beats auto-aim and a held aim key |
| Mouse (menus) | Hover to highlight, click to pick, on every menu — start, hero select, pause, level-up, Options, Sanctuary, Rankings, the build screen, dev menu (the dev menu alone takes the wheel and the right button). On the hero select the first click on a card selects it and a second click begins; or click **Begin**. In Options the three volume bars **drag** |
| Q | Toggle **auto attack** (on by default). No indicator: read it from the hero |
| ENTER or SPACE | Confirm / start / select a menu entry / buy / equip |
| ← → (hero select) | Choose the hero · ↑ ↓ choose the **difficulty** (Normal / Fast / Super Fast), or click the difficulty ribbon to step it |
| ← → (Options) | Adjust the selected volume — master, music or sound effects (or drag the bar with the mouse) |
| E | Use what you're standing on — a treasure chest, the village forge or fountain, a buff building |
| ESC | Pause (in game) / back / quit (from the start menu) · the pause menu has Resume / Run status / Options / Key layout / Quit to menu |
| TAB (in a run) | The **build screen**: the run line, your stats, weapons, Forging and blessings — the run freezes while it is open |
| S (run summary) | Open the **Sanctuary** (meta upgrades + item stash) — from the start menu it's under **Options** |
| TAB (Sanctuary) | Switch between Upgrades and Stash · U unequips |
| 1 / 2 / 3 or ← → + ENTER | Choose a level-up upgrade / blessing (or click the card) |
| M | Mute / unmute audio (persisted); also an **Options** toggle |

Weapons attack automatically by default — you move, pick upgrades/blessings,
use special locations, and choose a hero and difficulty. Hold an aim key or
click to attack where you point instead (the shot homes on the closest enemy
inside a cone around your aim, else flies straight; melee swings that way);
`Q` turns auto attack off so the hero only attacks on your input. Orbit and
summon weapons take no aim. The world is a chain of islands joined by
bridges, each a stack of terraces with cliffs, stairs, lakes and obstacles;
explore it, survive the escalating waves, and the boss (**The First Hunger**)
appears in its arena near the end of the run and drops an item. Salvage and
loot carry over between runs via the Sanctuary.

The developer-mode keys (F1–F8, the dev menu) are listed in
[`FUNCTIONAL_README.md`](FUNCTIONAL_README.md); none of them is needed to play.

### Display

The window is **1600×900** and can be windowed or borderless fullscreen, with
a Resolution row in Options; the picture is scaled to fit, the gameplay is the
same at every size. The in-game view is zoomed in (1.5×) so the picture is
"closer" but stays crisp. The interface always sits in a centred 16:9 box, so
on an ultrawide window the world fills the width and the HUD stays where it
is.

### Start screen

A keyboard-navigated menu: **Start new game** → hero + difficulty select → run;
**Start new developer mode game** → the same select screen → a non-persistent
sandbox run with the dev overlay (backtick / tilde: HP / attack / overlay
toggles, spawn any enemy, grant any blessing, item or weapon, apply any
Forging, remove owned weapons, reset the run); **Rankings**; **Options**;
**Exit**. Options holds the three-level **mixer** — a **master volume** over a
**music** and a **sound effects** level, each ← → in 5% steps or dragged with
the mouse — a **mute** toggle, the **key layout**, a **Tutorials** toggle
(the opening Move / Attack hints), the **window** rows, and the entry point
into the **Sanctuary** — all persisted to `save.json` immediately.
The sound-effects level covers every cue the game plays, the synthesised ones
and the recorded clips (footsteps, the monster growl) alike. If `assets/ui/title.png` exists it fills the screen
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

## Content

- **3 heroes**, each with a distinct trait (hold-ground damage reduction and
  block / a double-shot Bow / a quick-cast Rod) and starting weapon; the first
  boss kill with a hero unlocks that hero's choice of main weapon
- **6 weapons** (Sword, Hammer, Daggers, Bow, Magic Rod, Bomb; three per
  run) plus **3 summons** (Ember Ring, Grave Totem, Spirit Wolf; one per run)
  -- see `documentation/designs/six_weapon_system_design.md`
- **Blessings**: every weapon owns six, always on offer while you hold it,
  covering damage, speed, area and a special effect; plus the hero's stat
  blessings — offered on level-up
- **Forging** at the village forge: a per-weapon upgrade that rewrites its
  numbers
- **13 enemy variants** (incl. 3 FSM-driven: charger, teleporter, area-denial
  warlock) + **1 boss** with 3 telegraphed attack patterns and a health bar
- **5 status effects** (burn / poison / bleed / chill / shock) on a generic
  data-driven framework
- **4 elemental infusions** (fire / ice / thunder / wind) attached to a
  weapon for the run, leaving an aura on what they hit, with **6 reactions**
  when one element lands on another's aura
- **17 item affixes**, 5 rarities, seeded deterministic item generation
- **6 meta-progression upgrades**, corruption-tolerant JSON save/load
- Seeded **procedural world** of islands and bridges: terraces, cliffs and
  staircases, inland lakes, a village island with its forge, fountain and
  villagers, buff buildings (2–5 per island), treasure chests with potions,
  fish huts with seahorse boats, and a boss arena; the **interactables** are
  the village forge (Forging) and fountain (heal), the buff buildings and the
  chests
- XP / leveling with a weighted 3-choice upgrade & blessing screen
- Phase-based spawn director; a per-run **difficulty** (Normal / Fast / Super
  Fast) drives four independent knobs — spawn rate, how fast the phase schedule
  and boss arrive, the enemy HP/speed ramp, and the enemy-count growth — with a
  separate best-run ranking per difficulty
- Procedurally synthesised sound effects alongside a few recorded cues, and
  two streamed music tracks; a three-level mixer (master over music and sound
  effects) in Options
- Animated sprites for all 3 heroes, all 13 enemies + the boss, and enemy shots;
  a red hit-tint and a shared skull death-poof stand in for the missing
  hurt/death strips. The game stays fully playable with an empty `assets/`
- **Tiled terrain**: each island baked from its height map as a grass tileset
  with autotile edges, cliff faces and stairs, over a tiled water void;
  corridors are directional plank **bridges**; animated shoreline foam sits
  *behind* the terrain and shows through the transparent tile fringes. A
  seeded **decoration scatter** adds non-colliding clutter on the islands and
  water scenery (rocks, a duck) on the open water. Every obstacle draws as a
  decoration sprite (animated tree / bush / rock) scaled to its collider;
  trees cast a soft round shade over the characters. The world is painted one
  terrace at a time with the characters slotted between, so a higher terrace
  hides what stands below it and the hero walks *behind* a tree when above it
- **Game over** shows the run's résumé: time, level, kills, gold and Salvage,
  the items acquired, kills per enemy type, the blessings with their levels,
  and the damage done per weapon with its DPS

## Assets

All heroes, enemies, the boss, terrain, props, buildings and the UI art come
from the **Tiny Swords** pack by Pixel Frog; the title-screen illustration is
separate. Music is two Pixabay tracks; the sound effects are synthesised at
startup, with a few recorded cues. Every pack, track and its licence is listed
in [`assets/CREDITS.md`](assets/CREDITS.md).

Sprites are an optional cosmetic layer over a primitive renderer — a missing
file falls back to a shape, so the game runs with an empty `assets/`.
Currently sprited: all **3 heroes** (Aegis = blue Warrior, Kestrel = yellow
Archer, Nihil = purple Monk), **all 13 enemy variants + the boss**, the
villagers, the enemy-shot arrow, the terrain, the obstacles and the props.
How the sprites, the terrain sheets and the decoration rigs are wired is in
[`FUNCTIONAL_README.md`](FUNCTIONAL_README.md#assets--how-they-are-wired).

## Tools

`tools/` holds the scripts around the game rather than in it — the asset
pipeline that cuts delivered art and audio into what the game reads, the
DPS and spawn benchmarks, and the world-digest check the tests pin. They are
described in [`FUNCTIONAL_README.md`](FUNCTIONAL_README.md#developer-keys-and-tools).

## Documentation

Everything written about the project lives under `documentation/`:
`designs/` (the spec and the design references), `plans/` (what is to be
done) and `journals/` (what was done, with the numbers). The map is in
[`FUNCTIONAL_README.md`](FUNCTIONAL_README.md#documentation-map).
