# Asset Credits

All game **content** (design, code, data, the procedurally synthesised audio in
`systems/audio.py`) is original to this project.

All art under `assets/` (sprites, projectiles, terrain, decorations, buildings,
fx) and the `.aseprite` sources under `assets/aseprite/` were supplied by the
project owner from third-party packs. **Before this project is distributed,
confirm each pack's licence permits the intended use and fill in the details
below.**

## Pack 1 — character sprites

| Field | Value |
|-------|-------|
| Pack name | _<FILL IN>_ |
| Author | _<FILL IN>_ |
| Source URL | _<FILL IN>_ |
| Licence | _<FILL IN — e.g. CC0, CC-BY 4.0, "free for commercial use">_ |
| Attribution required? | _<FILL IN>_ |
| Date obtained | _<FILL IN>_ |

Files covered:

- `assets/sprites/soldier/` — Soldier: `Idle` (6f), `Walk` (8f),
  `Attack01/02/03` (6/6/9f), `Hurt` (4f), `Death` (4f); 100×100 frames.
  Used in-game for the hero **Aegis**.
- `assets/sprites/orc/` — Orc: `Idle` (6f), `Walk` (8f), `Attack01/02` (6/6f),
  `Hurt` (4f), `Death` (4f); 100×100 frames. Used for the basic enemy
  (**chaser** / "Husk").
- `assets/projectiles/arrow.png` — 32×32 single frame. Used for enemy / boss
  projectiles.
- `assets/aseprite/Orc.aseprite`, `assets/aseprite/Soldier.aseprite` — editable
  sources, not loaded at runtime.

`assets/sprites/*/Orc.png` and `Soldier.png` are combined reference sheets and
are not loaded by the game (the per-animation strips are used instead).

## Pack 2 — terrain / buildings / FX

Filenames strongly indicate **"Tiny Swords" by Pixel Frog** (itch.io). Confirm
before distributing.

| Field | Value |
|-------|-------|
| Pack name | _<FILL IN — likely "Tiny Swords">_ |
| Author | _<FILL IN — likely Pixel Frog>_ |
| Source URL | _<FILL IN — likely https://pixelfrog-assets.itch.io/tiny-swords>_ |
| Licence | _<FILL IN — Tiny Swords is CC0, verify the version you downloaded>_ |
| Attribution required? | _<FILL IN>_ |
| Date obtained | _<FILL IN>_ |

Covers `assets/terrain/` (tileset + decorations + resources), `assets/buildings/`
(5 colour variants), `assets/fx/` (dust / fire / explosion / splash strips), and
the matching `.aseprite` sources in `assets/aseprite/`.

In-game so far (see the terrain pass in `../journals/assets_journal.md` /
`../journals/journal.md`):

- `assets/terrain/tileset/` — `Tilemap_color1..5.png` (grass floors, autotile
  edges baked per room by palette), `Water_Background.png` (void fill),
  `Water_Foam.png` (16-frame animated shoreline overlay).
- `assets/terrain/decorations/bushes/` and `rocks/` — each circular map obstacle
  is skinned with one of these, scaled to its collider (`tree`/`shrub` → bushes,
  `rock`/`pillar` → rocks). `water_rocks/`, `duck/`, `clouds/` and `Shadow.png`
  are present but not currently used.
- `assets/buildings/`, `assets/fx/`, `assets/terrain/resources/` — filed, not
  wired in yet.
