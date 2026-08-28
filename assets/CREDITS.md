# Asset Credits

All game **content** — design, code, data, and the procedurally synthesised
audio in `systems/audio.py` — is original to this project.

## Art — "Tiny Swords" by Pixel Frog

**Every PNG under `assets/` is from the "Tiny Swords" asset pack by Pixel Frog**
(itch.io). `.aseprite` editor sources and `.DS_Store` files were removed; only
sprites the game loads (plus a set of reserve packs kept for future use) remain.

| Field | Value |
|-------|-------|
| Pack name | Tiny Swords |
| Author | Pixel Frog |
| Source URL | _<FILL IN — https://pixelfrog-assets.itch.io/tiny-swords>_ |
| Licence | _<FILL IN — Tiny Swords is CC0; verify the version downloaded>_ |
| Attribution required? | _<FILL IN>_ |
| Date obtained | _<FILL IN>_ |

### Wired into the game

- `assets/characters/<colour>/<unit>/` — the three heroes:
  **Aegis** = blue Warrior (`hero_aegis`), **Kestrel** = yellow Archer
  (`hero_kestrel`), **Nihil** = purple Monk (`hero_nihil`). `idle` + `walk` +
  `attack`, 192 px frames, no hurt/death strip (the renderer red-tints on hit
  and plays the shared `dead` poof).
- `assets/characters/dead/dead.png` — the shared one-shot **death poof** (14 f,
  repacked to a 14×1 128 px strip) used for every entity, hero and enemy.
- `assets/enemies/<mob>/` — all 13 enemy variants + the boss:
  `chaser`→skull, `fast`→spider, `tank`→turtle, `swarm`→bumblebee,
  `ranged`→slingshot_gnome, `exploder`→bomb_fish, `shielded`→panda,
  `elite`→bear, `summoner`→gnome, `brute`→troll, `charger`→minotaur,
  `teleporter`→thief, `warlock`→hex_shaman, and `the_first_hunger` (boss)→giant_bat.
- `assets/projectiles/arrow.png` — the archer arrow, used for enemy / boss shots.
- `assets/terrain/tiles/` — `tilemap_1..5` (grass autotile per room palette),
  `water_background`, `water_foam` (16 f shoreline); `shadow.png` present, unused.
- `assets/terrain/bridge/bridge_all.png` — the plank-bridge autotile (corridors).
- `assets/terrain/props/` — `bush_*` / `rock_*` / `tree_*` skin the obstacles;
  `water_rock_*` / `duck` are the void scatter.

### Reserve (in the tree, not wired)

`assets/enemies/<mob>/` for the ~7 unused mobs + `assets/enemies/extra/`;
`assets/characters/{black,red}/…` and the `lancer` / `pawn` unit types;
`assets/buildings/`, `assets/effects/`, `assets/terrain/props/{cloud_*,deco_*,
stump_*}`, `assets/terrain/resources/`. All Tiny Swords, kept and renamed to the
project's `lower_snake_case` convention so a future skin pass is drop-in.

## Not part of the Tiny Swords pack

- `assets/ui/title.png` — a standalone title-screen illustration.
  **Confirm its source and licence separately before distribution.** Optional at
  runtime (the menu falls back to drawn text if it is missing).
