# Asset Integration Journal — Death Lite Die

A focused checklist + phase log for wiring real sprites into the game, kept
separate from the main `journal.md`. Same format: **Goal → What changes → How
it's verified → Decisions → Risks**, with a tick-box workflow.

The engine already has the seam for this: every entity is drawn in a `_draw_*`
method with `pygame.draw.*`, and the plan from the start was
`if sprite: blit(sprite) else: draw_primitive`. Nothing in gameplay, state,
combat, or collision is affected — sprites are a cosmetic layer.

---

## Utility update — Sprite Sheet Lab split-window viewer — ✅ DONE (2026-08-27)

**What changed:** Added the external `utilities/sprite_sheet_lab.py` authoring
tool as a standalone sprite metadata/crop previewer, then revised it so the
large sprite sheet renders in its own SDL2 window instead of sharing space with
the control/metadata UI. The sheet viewer now has a clipped viewport below a
fixed header, independent vertical and horizontal scroll state, crop dragging
inside the sheet window, and fractional zoom from 50% to 600%.

**Expected next phase:** Use the utility interactively against a few raw PNGs
and existing metadata entries, then tune any requested authoring controls such
as editable frame dimensions, anchor editing, grid-sheet support, or direct
merge/export into `data/sprites.json`.

**Verified:**
- `python -m py_compile utilities\\sprite_sheet_lab.py`
- Dummy-display smoke draw: created the main control window plus the separate
  sheet-view window, loaded `enemies/bear/attack.png`, and built 9 frames.

## Scope of this pass (locked by the request)

| Sprite | Used for | Everything else |
|--------|----------|-----------------|
| **Soldier** (`assets/sprites/soldier/`) | **Aegis only** (the first hero) | Kestrel & Nihil stay primitive |
| **Orc** (`assets/sprites/orc/`) | **the basic enemy** (the `chaser` / "Husk") | the other 12 enemy types stay primitive |
| **Arrow** (`assets/projectiles/arrow.png`) | **enemy / boss shots only** (the hostile-projectile pool) | **all player projectiles keep their current glow-circle rendering, unchanged** |

Not touched this pass: the boss, **every player weapon's projectiles**, XP gems,
ground hazards, obstacles, the procedural floor/wall/void rendering, the HUD,
menus. They keep the shape renderer, which stays as the permanent fallback for
un-arted content.

---

## Asset inventory

All character strips are **horizontal, 100×100 px frames**. Rigs face **right**;
a left-facing entity needs a horizontal flip.

| Rig | Animation | File | Frames | Suggested fps / loop |
|-----|-----------|------|-------:|----------------------|
| Soldier | idle | `Soldier_Idle.png` | 6 | 8 · loop |
| Soldier | walk | `Soldier_Walk.png` | 8 | 12 · loop |
| Soldier | attack | `Soldier_Attack01.png` | 6 | 16 · once |
| Soldier | (alt attacks) | `Soldier_Attack02/03.png` | 6 / 9 | 16 · once |
| Soldier | hurt | `Soldier_Hurt.png` | 4 | 14 · once |
| Soldier | death | `Soldier_Death.png` | 4 | 10 · once |
| Orc | idle | `Orc_Idle.png` | 6 | 8 · loop |
| Orc | walk | `Orc_Walk.png` | 8 | 11 · loop |
| Orc | attack | `Orc_Attack01/02.png` | 6 / 6 | 16 · once |
| Orc | hurt | `Orc_Hurt.png` | 4 | 14 · once |
| Orc | death | `Orc_Death.png` | 4 | 10 · once |
| Arrow | — | `projectiles/arrow.png` | 1 | rotate to velocity |

`Soldier.png` / `Orc.png` are combined grid sheets — kept for reference, not
loaded (we use the per-animation strips).

---

## Decisions

### Locked
1. **Soldier → Aegis, Orc → chaser, Arrow → enemy shots only.** Per the request.
2. **Fallback stays.** Any entity without a sprite key keeps drawing its
   primitive. The game is fully playable at every step of this pass.
3. **Gameplay is authoritative, sprites are cosmetic.** `radius`, hitboxes,
   damage, movement are unchanged. Sprites are scaled to *read* at roughly
   `radius × 2.6`; the collision circle is unaffected.
4. **Sheet metadata lives in data** (`data/sprites.json`), not constants —
   frame size, count, fps, loop, and a per-rig `anchor` (feet position inside
   the 100 px box, since the art is bottom-heavy with transparent padding).
5. **Transforms are cached, never per-frame.** Sliced frames, scaled copies,
   flipped copies and rotation buckets are all memoised in the asset manager.
6. **Basic enemy = the `chaser` ("Husk") only.** `fast` / `swarm` / `tank` /
   `elite` / `shielded` keep their primitives this pass.
7. **Player attack anim = yes.** `Soldier_Attack01` plays as a one-shot burst
   each time a weapon fires; it interrupts idle/walk and returns to them when
   done (unless overridden by hurt/death).
8. **Enemy hit feedback = `Orc_Hurt` animation** (not the white flash) for the
   sprited chaser — a 4-frame one-shot that interrupts walk/idle.
9. **Arrows only for enemy / boss shots** — the hostile-projectile pool
   (`self.hostiles`). **Every player weapon is left exactly as it renders now:**
   arcane bolt, frost shards, thunder orb keep their glow dots; Ember Ring and
   Soul Scythe keep their glow circles. `_draw_projectiles` is not touched;
   only the hostile-projectile draw loop changes.

### Priority order for the player animator (highest wins)
`death` → `hurt` → `attack` → `walk` → `idle`. Enemy: `death` → `hurt` →
`walk` → `idle`.

### Still using defaults
- Facing source: player uses `_move_dir.x`, falling back to `_last_move_dir.x`
  when standing still; enemy faces `sign((player.pos − pos).x)`.
- Scale ≈ `radius × 2.6`, anchor ≈ `(50, 68)` — both tuned in `sprites.json`
  during Phases B/C.

---

## Workflow — 5 phases

Each phase ends green (tests + a windowed run) before the next begins.

### Phase A — Asset loader + metadata *(no visible change)* — ✅ DONE (2026-08-27)
- [x] `game/assets.py`: `Assets` + `get_assets()` / `reset_assets()`. Lazy
      `_load_image` (`convert_alpha`, missing → `None` warned once). `frames()`
      slices a strip into per-frame copies, memoised by `(rig, anim, size,
      flip)`; `frame(index)` wraps for loops / clamps for one-shots. `image()`
      + `rotated(deg)` (8° buckets) for the single-frame arrow. All transforms
      cached, none per-frame.
- [x] `data/sprites.json`: rigs `soldier` (idle/walk/attack/hurt/death),
      `orc` (idle/walk/hurt/death), `arrow`. Each carries `frame`, `anchor`,
      `face`, `scale`, and per-anim `{file, frames, fps, loop}`.
- [x] `game/content.py`: loads `sprites.json` → `Content.sprites` (+ log line).
- [x] `game/game.py`: `self.assets = get_assets()` after `get_content()`
      (display already exists from `set_mode`).
- [x] `tests/test_assets.py` — 14 tests: files exist; strip width ==
      `frame_w × frames` and height == `frame_h`; `frames()` yields the exact
      count; unscaled frame is native size, scaled matches request; loop wraps /
      one-shot clamps; flip is a distinct same-size surface and is cached;
      missing rig/anim/file all return `None` (warned once, not per call);
      arrow image + bucketed rotation; metadata helpers.
- [x] `assets/CREDITS.md`: template with `<FILL IN>` for pack name / author /
      source / licence — the sprites are third-party and their licence must be
      confirmed before distribution (spec §15).

**Verified:**
- `python -m unittest discover -s tests` → **195 pass** (181 + 14 new).
- Manual slice check: every frame of all 9 animations is a 100×100 surface with
  real (non-transparent) pixels; `arrow.png` loads 32×32.
- `python main.py` runs unchanged — content log now reads "3 sprite rigs";
  nothing blits a sprite yet.
- No gameplay/render code touched; the `if sprite: … else: primitive` seam is
  not wired until Phase B.

### Phase B — Aegis sprite (Soldier) — ✅ DONE (2026-08-27)
- [x] `systems/animation.py::Animator` — tracks time only; reads
      count/fps/loop from `Assets` for the current `(rig, anim)`; `index`
      wraps for loops / clamps for one-shots; `finished` flag; `frame(size,
      flip)` delegates. Owned by `PlayingState` (`self._hero_anim`), not
      `Player` — Player exposes the *state*, the state machine owns rendering.
- [x] `Player`: `_hurt_t` (set in `take_damage` only when `dealt > 0`),
      `_attack_t` + `trigger_attack_anim()`, `_facing` (±1, follows
      `_move_dir.x`, kept when still). All decay in `update`. No gameplay effect.
- [x] `data/characters.json`: `aegis` → `"sprite": "soldier"`. Kestrel / Nihil
      have no `sprite` key → `_hero_anim` is `None` → primitive circle.
- [x] `game/states/playing_state.py`: `_hero_anim` built in `enter`;
      `_update_hero_anim` in `_phase_update`; `_hero_anim_name()` priority
      `death > hurt > attack > walk > idle`; `trigger_attack_anim()` fired from
      `_spawn_projectile` (next to `audio.play_shoot`); `_draw_player` blits the
      frame at `pos − anchor`, flipped by `_facing`, else the circle; invuln
      draws a red ring around the sprite. **Death sequence:** if the hero has a
      rig, `update` holds `PlayingState` open for 0.6 s (`_death_seq_t`) to play
      the death animation before `_end_run` — camera / particles keep updating,
      input / combat stop. No rig → ends immediately as before.
- [x] `data/sprites.json`: added a `content` crop rect per rig (the packs ship
      an ~80% transparent margin — cropping fixes both visibility *and* blit
      cost). `scale` is the final sprite size; `anchor` is the pixel in the
      final sprite that sits on the world position.

**Verified:**
- `python -m unittest discover -s tests` → **205 pass**. New:
  `test_animation` (6 — advance / loop wrap / one-shot clamp+finished / play
  reset / delegation) and `test_movement::AnimStateTests` (4 — hurt timer set &
  decays, none when fully mitigated, attack timer, facing follows input and
  persists when still).
- Rendered screenshots (headless → PNG): Soldier reads clearly at ~50 px,
  stands on its position with the shadow around it, flips correctly for
  left/right, and the attack pose shows on the scythe's beat.
- Aegis death held `PlayingState` for exactly 36 frames (0.60 s) playing
  `death`, then `GameOverState`.
- Kestrel: `_hero_anim is None`, `_hero_sprite_frame() is None` → circle; run
  fine. Compressed full end-to-end still reaches VictoryState with persistence
  intact.
- Windowed `python main.py` runs clean.

Anchor/scale are a first tune (`content [30,27,46,40]` / `scale [69,60]` /
`anchor [34,40]` for soldier) — a couple of px of nudge room remains and it is
a pure `sprites.json` edit.

### Phase C — Basic enemy sprite (Orc) — ✅ DONE (2026-08-27)
- [x] `data/enemies.json`: `chaser` gets `"sprite": "orc"` (only that entry).
- [x] `entities/enemy.py`: `self.anim = Animator(get_assets(), rig)` when the
      def declares a rig, else `None`. `_hurt_t` + an `Orc_Hurt` restart in
      `take_damage` (direct hits only — DoT ticks use `_status_damage` and do
      not flinch). `_facing` tracks `player_pos.x`. `_anim_name()` priority
      `death > hurt > walk > idle`; `update` advances the animator. `hit_flash`
      is still set but not drawn for sprited enemies.
- [x] `game/states/playing_state.py`: `self._dying` list of `[enemy, secs]`.
      `_cull_dead_enemies` fires **all** death effects (kills++, explosion,
      on-kill blessings, `ENEMY_KILLED`) at the instant of death, then, if the
      enemy is sprited, moves it to `_dying` with a 0.42 s timer instead of
      dropping it. `_update_dying` (in `_phase_update`) advances the death anim
      and expires the entry. `_draw_enemies` → `_draw_one_enemy` (sprite for the
      chaser, circle for the other 12) + `_draw_enemy_sprite` for the `_dying`
      list; elite / shield / telegraph rings + collision-vis draw on top of
      either renderer; status shows as a coloured ring on sprited enemies.
- [x] Anchor/scale for `orc`: `content [31,34,42,32]` / `scale [63,48]` /
      `anchor [31,33]`.

**Verified:**
- `python -m unittest discover -s tests` → **213 pass**. New `test_enemy_sprite`
  (8): only the chaser gets an `Animator`; a hit sets `_hurt_t` and restarts
  the flinch; `_anim_name` priority; facing tracks the player; hurt decays; DoT
  does not flinch; **death lifecycle** — a sprited enemy leaves `enemies`,
  enters `_dying` (kills already ++, `death` playing) and expires after ~0.66 s;
  a plain enemy vanishes with no `_dying` entry.
- Screenshots: green Orc chasers ring the Soldier, each facing the player (flip
  correct), on their positions with shadows; primitive `fast` enemies still
  draw as circles alongside; on death the Orcs play a collapse for ~0.4 s while
  the XP gem / particles / damage number appear at the death spot immediately.
- Compressed full end-to-end still reaches VictoryState with persistence
  intact; windowed run clean.

### Phase D — Arrow projectile *(enemy / boss shots only)* — ✅ DONE (2026-08-27)
- [x] `data/sprites.json` arrow rig: `content [6,12,21,9]` (the art is a 19×7
      arrow in a 32 px frame, pointing **right**), `scale [30,13]`.
- [x] `game/assets.py`: `image()` now honours a `content` crop and an optional
      `tint` (brighten-toward via `BLEND_RGBA_ADD`, keeps the alpha silhouette);
      `rotated(rig, degrees, *, size, tint)` caches by `(rig, size, tint,
      bucket)` — 8° buckets, so **exactly 45** surfaces for the one tint.
- [x] `game/states/playing_state.py`: **only** the hostile loop in
      `_draw_projectiles` changed — blit `assets.rotated("arrow",
      degrees(atan2(vel.y, vel.x)), size=scale_for("arrow"), tint=(150,26,12))`
      centred on the projectile; falls back to the dot if the sprite is
      missing. The player-projectile loop above it is byte-for-byte unchanged.

**Verified:**
- `python -m unittest discover -s tests` → **215 pass**. New arrow tests:
  `content` crop applied when unsized; tinted arrow is a distinct, cached
  surface; 88°/90° share a rotation bucket.
- Screenshots: 15 hostile shots fired in a fan render as bright-red arrows each
  pointing along its own velocity; the Soldier and player projectiles are
  unchanged.
- Perf: 400 live hostile arrows → **1.06 ms/frame** render (0.43 ms baseline);
  rotation cache holds exactly 45 surfaces and does not grow.
- Compressed full end-to-end → VictoryState, persistence intact; windowed run
  clean.

**Noticed (pre-existing, out of scope):** the Soul Scythe *cone* renders as a
solid opaque purple disc (`radius == area == 74`) for its 0.14 s, which briefly
covers the hero. Not a Phase D change (cone was scoped out); worth a follow-up —
draw it as a translucent wedge / expanding ring instead of a filled circle.

### Phase E — Polish + documentation — ✅ DONE (2026-08-27)
- [x] Optional Orc-reuse hook — **skipped.** Out of the stated scope
      ("chaser only"). The path is trivial for later: give a variant
      `"sprite": "orc"` plus a `tint` override and teach `_draw_enemy_sprite`
      to pass a per-enemy tint — a few lines, no new system.
- [x] `README.md`: corrected the intro (no longer claims "no third-party
      assets" — links `assets/CREDITS.md`), fixed the stale folder name,
      updated the layout tree + content list + test count, added an **Assets**
      section.
- [x] `journal.md`: "Post-Phase-3 — Sprite integration" milestone entry (goal /
      5-phase table / verification / decisions / limitations).
- [x] `transcript.md`: "Asset integration" section — 5 steps with the reasoning.
- [x] `assets_journal.md`: every phase ticked with its verification notes; this
      section + the summary below.

**Verified (final):**
- `python -m unittest discover -s tests` → **215 pass**.
- Per-hero compressed headless playtest → aegis / kestrel / nihil all reach
  VictoryState; `_hero_anim` is set for Aegis only; peak render ≈ 4.6–5.2 ms/
  frame; rotation cache 22–28 (→ caps at 45).
- Windowed `python main.py` clean.

---

## Summary

A user-supplied Aseprite pack (Soldier, Orc, arrow) is now wired in as a
**cosmetic layer** with zero gameplay change:

| Sprited | How |
|---------|-----|
| **Aegis** (hero) | Soldier — idle / walk / attack (on weapon fire) / hurt / death; flips by facing; 0.6 s death-sequence before game-over |
| **chaser** (enemy) | Orc — walk / hurt (direct hits) / death; faces the player; ~0.42 s render-only "dying" phase |
| **enemy + boss shots** | one 32×32 arrow, rotated to velocity (8° buckets), tinted red |

Everything else — Kestrel, Nihil, 12 enemy types, the boss, XP gems, hazards,
obstacles, the world, the HUD, **all player projectiles** — still draws as a
primitive. The `if sprite: … else: shape` seam is at every draw site and the
loader returns `None` for missing files, so the game runs identically with an
empty `assets/`.

New modules: `game/assets.py` (loader + cache), `systems/animation.py`
(`Animator`), `data/sprites.json` (metadata). Test count 181 → **215**.

### Follow-ups (not blocking)
- Fill in `assets/CREDITS.md` and confirm the pack's licence before distributing.
- Anchor / scale for both rigs are a first eyeball tune — pure `sprites.json`.
- Soul Scythe cone draws as an opaque disc for 0.14 s (pre-existing) — redo as a
  translucent wedge / ring.
- Reuse the Orc rig (tinted) for `fast` / `swarm` / `tank` / `elite` if desired.
- More rigs for the rest of the roster + the boss.

---

## Risks / watch-items (post-implementation)

- **Anchor & scale are eyeball-tuned.** Current values are readable but not
  pixel-perfect; all in `data/sprites.json`, so re-tuning is a data edit.
- **Rotation cost** — resolved: 400 hostile arrows measured at ~0.6 ms of extra
  render, cache fixed at 45 surfaces.
- **Death lifecycle** — the one real `playing_state.py` change. Covered by
  `test_enemy_sprite`: death *events* (kills, XP, on-kill, `ENEMY_KILLED`) fire
  at the instant of death; only removal is deferred.
- **`.convert_alpha()` needs a display** — handled: `Assets` is created after
  `set_mode`, and loading is lazy so pure-logic tests never touch disk.
- **Only 2 humanoid rigs + 1 arrow** — most of the roster stays primitive. The
  fallback keeps everything shippable.
- **Facing pop** when `vel.x` / `_move_dir.x` crosses zero — minor; a dead-zone
  could be added if it reads badly.
- **`assets/CREDITS.md` is a template** — the pack's licence is unconfirmed; the
  README intro now reflects that third-party art is in use.

---

## Second asset pack added — Tiny Swords (Buildings + Terrain + FX)

**Date:** 2026-08-27

A second pack (filenames strongly indicate **"Tiny Swords" by Pixel Frog**,
itch.io, CC0) was dropped into `assets/`: `Buildings/`, `Terrain/`
(Tileset + Decorations + Resources) and `Particle FX/`.

### Reorganised into the game's convention (PNG-only game folders)

```
assets/
├── terrain/
│   ├── tileset/        Tilemap_color1..5.png (576x384, 64px tiles, 9x6),
│   │                   Shadow.png (192x192), Water_Background.png (64x64),
│   │                   Water_Foam.png (3072x192, 48x3 @ 64px)
│   ├── decorations/
│   │   ├── bushes/     Bushe1..4.png   (1024x128 → 8 @ 128px)
│   │   ├── rocks/      Rock1..4.png    (64x64 static)
│   │   ├── water_rocks/ Water_Rocks_01..04.png (1024x64 → 16 @ 64px, animated)
│   │   ├── clouds/     Clouds_01..08.png (576x256, single large sprites)
│   │   └── duck/       Rubber_Duck.png (96x32 → 3 @ 32px)
│   └── resources/      trees/ gold/ meat/ tools/ wood/   (filed, NOT in scope)
├── buildings/          black/ blue/ purple/ red/ yellow/  (8 PNGs each, filed)
├── fx/                 Dust/Fire/Explosion/Water_Splash strips (filed)
└── aseprite/           + Bushes, Clouds, Water_Rocks_01..04, Rubber_Duck,
                        Water_Foam, Trees, Sheep, Gold_Resource, Gold_Stones
```

`.DS_Store` deleted; every `.aseprite` source moved to `assets/aseprite/`
(spaces → underscores), matching the Orc/Soldier convention. Game folders now
contain **only** `*.png`.

> **Incident + fix:** a first reorg attempt was run on this case-insensitive
> filesystem with `mkdir buildings/ … ; mv … ; rm -rf Buildings` — `buildings/`
> resolved *into* the existing `Buildings/`, so the `rm` deleted the just-moved
> files. The user re-supplied the pack. The safe procedure now used: rename the
> top dir to a **unique** staging name first (`mv Buildings _stage_buildings`),
> build the clean tree, move files in, then `rm -rf` the uniquely-named stage.
> Never `rm` a name that case-collides with a directory being kept.

---

## To-do — implement **terrain + decorations only**

Scope: the `terrain/tileset/` floor/water and `terrain/decorations/`
(bushes, rocks, water-rocks, clouds, duck). **Not** in this plan: Buildings,
Particle FX, Resources (trees/gold/sheep/tools). Each phase ends green
(`unittest` + a windowed / headless-screenshot check) before the next; the
primitive renderer stays as the permanent fallback for a missing tileset.

### Investigated (2026-08-27) — actual sheet contents

`Tilemap_color1..5.png` — 576×384, **9×6 grid of 64 px tiles**, index = `row*9 +
col`. It is a grass-on-water autotile "blob" set:

| Use | tile `#` (col,row) |
|-----|--------------------|
| **interior floor** (only tile needed for T2) | `#10` (1,1) |
| edges N / S / W / E | `#1` / `#19` / `#9` / `#11` |
| corners NW / NE / SW / SE | `#0` / `#2` / `#18` / `#20` |
| 1-wide vertical strip top/mid/bot | `#3` / `#12` / `#21` |
| 1-wide horizontal strip L/mid/R | `#27` / `#28` / `#29` |
| 1×1 island | `#30` |
| col 4 | empty spacer |
| cols 5-8, rows 0-3 | 2nd grass tint ("plateau") — same layout, for special-room floors |
| rows 4-5, cols 5-8 | cliff faces — **unused** (our world is flat) |
| `#36 #39 #45 #48` | rounded-corner decorative tiles (T3 polish) |

Other tileset files: `Water_Background.png` 64×64 (plain void fill);
`Water_Foam.png` 3072×192 = **16-frame** 192×192 shoreline-foam animation (T3);
`Shadow.png` 192×192 nine-slice soft shadow decal (optional decoration polish).

Decorations:

| kind | file(s) | frame | frames | anim | use (after the T4 revision) |
|------|---------|-------|--------|------|-----------------------------|
| bush | `bushes/Bushe1..4.png` (1024×128) | 128×128 | 8 | sway loop @ ~6 fps | **skins `tree` / `shrub` obstacles** |
| rock | `rocks/Rock1..4.png` | 64×64 | 1 | static | **skins `rock` / `pillar` obstacles** |
| water rock | `water_rocks/Water_Rocks_01..04.png` (1024×64) | 64×64 | 16 | foam-ring loop @ ~10 fps | rig defined, **unused** (free-scatter removed) |
| duck | `duck/Rubber_Duck.png` (96×32) | 32×32 | 3 | bob loop @ ~5 fps | rig defined, **unused** |
| cloud | `clouds/Clouds_01..08.png` (~576×256) | — | 1 | static, big | sky overlay (default **off**, deferred) |

Measured `footprint` (non-transparent content width in source px, used to scale
each rig to an obstacle's collider): bush 1..4 = 67 / 46 / 79 / 46; rock 1..4 =
32 / 50 / 39 / 59.

### Phase T1 — asset plumbing *(no visible change)* — ✅ DONE (2026-08-27)
- [x] `data/terrain.json` — `tile_px: 64`, `floor_sheet`, `grid [9,6]`,
      `water_tile`, the `slots` table (interior/edges/corners/strips/single),
      `room_palettes` (kind → `Tilemap_colorN`), and a `rigs` block of **13**
      decoration rigs (`deco_bush_1..4` 8f, `deco_rock_1..4` 1f,
      `deco_water_rock_1..4` 16f, `deco_duck` 3f), each in the exact schema
      `Assets.frames()` consumes.
- [x] `game/content.py`: loads it → `Content.terrain` (+ log line).
- [x] `game/assets.py`:
      - `meta` is now `{**sprites, **terrain["rigs"]}` — decorations use the
        unchanged `frames()` / `frame()` path;
      - new `terrain` property (the `terrain.json` config);
      - new `tile(sheet_rel, index, *, size=None)` — slices cell
        `(index % grid_cols, index // grid_cols)` × `tile_px`, memoised by
        `(sheet_rel, index, size)`; `None` for a missing sheet or an
        out-of-range index.
- [x] `tests/test_terrain.py` — 12 tests: core fields; every slot index inside
      the 9×6 grid; referenced sheets exist; each `deco_*` file exists and its
      strip width == `frame_w × frames`; `tile()` returns a 64×64 cell, scales,
      caches, distinguishes indices, and returns `None` for a missing sheet /
      bad index; decoration rigs slice via `frames()` to the right count/size;
      the sprite + terrain rigs share one namespace.

**Verified:** `unittest` → **227 pass** (215 → 227). `python main.py` unchanged
(startup log now reads "13 terrain rigs"); nothing draws terrain yet.

### Phase T2 — tiled floor + water *(replaces the flat rects)* — ✅ DONE (2026-08-27)
- [x] `world/map.py`: `_build_tiles()` runs **once, lazily on the first
      `draw()`** (needs a display) — pre-renders every room and corridor to its
      own `Surface` (tiled with the `interior` grass tile; room kind → palette
      via `room_palettes`, so the boss floor is `Tilemap_color4` etc.), and
      tiles `Water_Background` into a `SCREEN + 1 tile` buffer for the void.
- [x] `draw()` → `_draw_tiled()`: blit the water buffer at
      `(-(ox % 64), -(oy % 64))` (one blit, no shimmer), then the cached
      room/corridor floor surfaces (view-culled), then
      `_draw_walls_and_obstacles()` (the 3-px wall borders + obstacles, on top
      of either renderer).
- [x] Fallback preserved: `_draw_flat_layout()` (the old `_FLOOR`/`_VOID`
      rects) runs when the tileset probe returns `None`. The no-layout branch
      (tests / menus) is unchanged.

**Verified:**
- `unittest` → **227 pass** (no regressions).
- Screenshots: grass-tiled room floors + corridors over a tiled teal water
  void, wall borders + obstacles + sprites + HUD unaffected. 16 room surfaces
  pre-rendered, water buffer 1344×784.
- Perf: tiled `draw()` = **0.40 ms/frame** (same as the old flat renderer —
  pre-rendered surfaces mean ~1 water blit + ~5 room blits, not per-tile).
- Compressed full end-to-end → VictoryState, persistence intact; windowed run
  clean.

Rooms are hard-edged grass rectangles against the water for now — shoreline /
edge tiles are Phase T3.

### Phase T3 — autotile edges + animated foam — ✅ DONE (2026-08-27)
- [x] `world/map.py` `_slot_for(row, col, rows, cols)` → picks
      `interior` / `edge_[nsew]` / `corner_*` from `slots` by the tile's
      position in the room grid (rooms are rects, so no neighbour mask needed
      yet). `_build_tiles` bakes those tiles into each pre-rendered room
      surface; a `(sheet, index)` cache keeps it fast. Corridors stay plain
      `interior`.
- [x] **Animated shoreline foam** — `Water_Foam.png` is 16 frames of 192×192
      (a breathing foam patch). Registered as rig `terrain_foam`
      (`frames: 16, fps: 12`). `_build_tiles` records every room's perimeter
      tile in `self._shore` (492 across the 16 rooms). `_draw_tiled` blits the
      current foam frame (`get_ticks`-clocked) centred on each shoreline tile
      **in view**, drawn *after* the room floors and *before* the corridors —
      so a corridor's plain grass covers the foam at every doorway.
- [x] Grey room wall-border dropped in the tiled path (the foam edge is the
      boundary now); kept in the flat fallback. `config.TERRAIN_FOAM` gates
      the foam pass (falls back to the baked edge tiles alone).
- [x] `tests/test_terrain.py`: updated for the `terrain_foam` rig (16 × 192).

**Verified:**
- `unittest` → **227 pass**.
- Screenshots: every room now has a foamy shoreline; corridors pass through
  cleanly at the doorways; autotile edge tiles + foam read as grassy islands in
  water. Player / enemies / obstacles / HUD unaffected.
- Perf: tiled + foam `draw()` ≈ **1.3 ms/frame** (0.4 ms without foam — the
  foam pass blits ~30–60 visible 192 px frames). Well under the 16.7 ms budget;
  a cheaper "bake a static foam ring + subtle animated overlay" is a possible
  later optimisation.
- Compressed end-to-end → VictoryState, persistence intact; windowed clean.

### Phase T4 — obstacle decoration skins — ✅ DONE (2026-08-27)

*First cut (superseded): `WorldLayout.decorations` — free-standing bushes / rocks
scattered on floors, water-rocks / a duck in the void, drawn as pure scenery.
The user then asked: "change the circular obstacles as decoration … don't place
decorations without an obstacle attached." Reworked as below.*

- [x] `entities/obstacle.py`: `Obstacle` gains a cosmetic `variant` (1–4).
- [x] `world/procedural.py`: `_scatter_decorations` and `WorldLayout.decorations`
      **removed**. `_scatter_obstacles` now assigns `o.variant = rng.randint(1,4)`
      in a post-placement pass, so obstacle **positions / kinds for a seed are
      byte-identical** to before.
- [x] `data/terrain.json`: `obstacle_decor` block — `size_boost` (1.25) + `rigs`
      mapping each obstacle kind to interchangeable rigs (`tree`/`shrub` →
      `deco_bush_1..4`, `rock`/`pillar` → `deco_rock_1..4`); each of those 8 rigs
      gains a measured `footprint` (content width in source px).
- [x] `world/map.py`: `_build_obstacle_decor()` (in `_build_tiles`) iterates
      `self.obstacles`, picks `rigs[kind][variant-1]`, scales the frame so
      `footprint` covers `2·radius·size_boost` and scales the anchor by the same
      factor, and stores `self._decos[obstacle_index] = (ax, ay, fps, frs)`.
      Cache of scaled frame-sets is bounded at 4 kinds × 4 variants = 16.
      `_draw_obstacles()` blits the `get_ticks`-clocked frame with its base on
      the collider centre; **falls back to the drawn circle** when no rig
      resolved (missing tileset / `config.TERRAIN_DECORATIONS` off). The separate
      `_draw_decorations` pass is gone.
- [x] `tests/test_terrain.py`: `ObstacleDecorTests` replaces the free-scatter
      tests — every obstacle skinned, `_decos` keys are valid obstacle indices,
      frame width matches the scaling formula (±1 px), tree skin wider than shrub
      skin per variant, deterministic per seed, variants ∈ 1..4, `obstacles` is
      the same list object and `is_walkable` unchanged, flag-off → circles,
      headless build. Plus a `TerrainMetadataTests` check that `obstacle_decor`
      covers every `Obstacle` kind and each rig has a positive `footprint`.

**Verified:**
- `unittest` → **237 pass** (233 → 237).
- A typical world (seed 1234): **62 obstacles**, all skinned — 12 tree + 25 shrub
  as bushes, 16 rock + 9 pillar as rocks; 4 variants seen; 13 distinct scaled
  frame sizes (70–181 px). Screenshots: trees render as large grass bushes,
  shrubs as smaller ones, rocks as variant-sized boulders — all on the tiled
  floor inside the foam shoreline; no free-standing scenery; no stray circles.
- Perf: full terrain `draw()` ≈ **1.2 ms/frame** — one small view-culled blit
  per obstacle (≤ 62), fewer than the old scatter.
- Compressed end-to-end → VictoryState, persistence intact; windowed clean.

**Deferred:** item 12, the `clouds/` parallax sky overlay — it belongs in
`PlayingState.draw` (on top of the world, before the HUD), not in `GameMap`.
A `config.TERRAIN_CLOUDS` flag is the intended switch; small follow-up.

### Phase T5 — docs — ✅ DONE (2026-08-27)
- [x] This file — phase notes T1–T5 + per-phase verification (above) and the
      closing summary (below).
- [x] `README.md` — layout tree (`data/` + `terrain`, `assets/terrain|buildings|fx`),
      test count 215 → 237, a "Tiled terrain" bullet in **Content**, and a
      "The **world** is tiled from `data/terrain.json`…" paragraph in **Assets**.
- [x] `assets/CREDITS.md` — "Pack 2 — terrain / buildings / FX" section (files
      strongly indicate *Tiny Swords* by Pixel Frog, itch.io; licence field is
      a `<FILL IN>` placeholder pending the user's confirmation).
- [x] `journal.md` — "Post-Phase-3 — Terrain integration (second asset pass)"
      milestone entry (goal / T1–T5 table / decisions / verification / limits).
- [x] `transcript.md` — "Terrain integration (post-Phase-3)" steps section.

### Draw order after T2/T4
water bg → room/corridor floors → animated foam → corridors → obstacle skins
(*or* fallback circles) → *(existing:* gems, hazards, enemies, boss, summons,
player, projectiles, particles, damage numbers *)* → optional cloud overlay →
HUD.

---

## Terrain pass — closing summary (T1–T5 complete, 2026-08-27)

**Outcome.** The procedural world now renders as grass-tiled islands — autotile
edges, an animated shoreline-foam ring, palette-per-room-kind floors — sitting
in a tiled water void. Every circular obstacle draws as a decoration sprite
(bush / rock) scaled to its collider; there is no scenery that isn't also a
collider. It is a second cosmetic layer: no tileset, or either `config` flag
off, and the original flat-rect renderer (with drawn circles) takes over
unchanged.

**Shape of the change.**
- `data/terrain.json` — the tile *vocabulary* (slot table, palettes, deco rigs +
  `terrain_foam`) and `obstacle_decor` (kind → rigs, `size_boost`, per-rig
  `footprint`); the *layout* stays in `world/procedural.py`.
- `game/assets.py` — `tile(sheet, index)` + `terrain` accessor; deco rigs share
  the sprite `frames()` path via a merged `meta` namespace.
- `world/procedural.py` — obstacles get a cosmetic `Obstacle.variant`; the old
  free-standing `decorations` list was removed on the user's follow-up.
- `world/map.py` — `_build_tiles()` pre-renders each static room/corridor to one
  `Surface` (edges baked) and `_build_obstacle_decor()` resolves one scaled
  rig per obstacle; per-frame cost = a few blits + one water blit + a handful of
  view-culled foam / obstacle blits.

**Tests.** `test_terrain.py` — 22 tests (metadata coherence incl. `obstacle_decor`
coverage, tile slicing + degrade-to-None, obstacle skinning: every obstacle
skinned, scaling formula, tree-vs-shrub size, determinism, walkability unchanged,
flag-off fallback, headless build). Suite: **215 → 237**.

**Perf.** Full terrain `draw()` ≈ 1.2 ms/frame (flat renderer was ~0.4 ms) —
foam is the bulk (~0.9 ms, 16×192px blits per in-view shoreline tile); obstacle
skins are ≤ 62 small view-culled blits.

**Deferred (need a fresh go-ahead).** Clouds parallax overlay (T4 item 12,
`PlayingState.draw` + `config.TERRAIN_CLOUDS`); a baked-foam-ring optimisation;
the now-unused `deco_water_rock_* / deco_duck` rigs (a future water-scenery
feature); wiring the Buildings / Particle-FX / Resources packs; filling the
`<FILL IN>` licence fields in `assets/CREDITS.md`. **Terrain layering — water
backdrop, foam behind the shore tiles, grid-aligned rooms, overlay tiles — is
now planned as T6–T10, below.**

---

## Terrain layering — T6–T10 (planned, no code)

**Date raised:** 2026-08-27. **Status:** ✅ **complete — T6–T10 all done**
(2026-08-27). Five phases, each ending green (`unittest` + a windowed /
headless-screenshot check) before the next. Scope is **terrain only** (backdrop /
floor / edge / overlay tiles, foam, shadow) — hero / enemy / building / FX
assets are out of scope for this pass.

### Asset inventory (checked 2026-08-27)

| file | size | notes |
|------|------|-------|
| `terrain/tileset/Water_Background.png` | **64 × 64**, opaque | flat teal water tile ≈ `(70,175,165)`. **The world backdrop** — tile it edge-to-edge under everything. |
| `terrain/tileset/Tilemap_color1..5.png` | 576 × 384 = **9 × 6 @ 64px**, 32-bit | grass-on-water **blob autotile** in cols 0–3 + row 3: `interior` #10 (opaque), `edge_*` #1/#9/#11/#19 and `corner_*` #0/#2/#18/#20 (**transparent on the water-facing side**), `strip_v` #3/#12/#21, `strip_h` #27/#28/#29, `single` #30. Rows 4–5 cols 0/3 (#36 #39 #45 #48) = **inner-corner** (concave grass). Cols 5–8 rows 0–2 = a 2nd grass variant; cols 5–8 rows 3–5 = a **grey stone / cliff** set (unused). `colorN` = per-room-kind tint, identical layout. |
| `terrain/tileset/Water_Foam.png` | 3072 × 192 = **16 frames @ 192 × 192**, ~86% transparent | soft **radial foam patch**, *not* directional — sits centred on a shore/bridge-edge cell and peeks out around the terrain. |
| `terrain/tileset/Shadow.png` | 192 × 192 nine-slice, ~87% transparent | soft drop-shadow decal (T9, under trees / large decorations). |
| **`Bridge/Bridge_All.png`** | 192 × 256 = **3 × 4 @ 64px**, ~47% transparent | **wood-plank bridge autotile.** Horizontal segment: left-end #0, mid #1, right-end #2. Vertical segment: top-end #3, mid #6, bot-end #9. Remaining cells = loose-plank debris decorations. Plank gaps + post edges are transparent → foam/water shows through. → **corridors render as bridges over water.** |
| **`Deco/01..18.png`** | mostly 64 × 64 (two 64 × 128, one 192 × 192), 50–94 % transparent | **no-collision ground clutter:** red mushrooms ×3, grey pebble piles ×3, grass tufts ×3, sprout, reeds, small pumpkin, pumpkin cluster, bones ×2, a skull signpost + a wooden signpost (64 × 128), a large brazier landmark (192 × 192). → the **room-interior decoration layer**. |
| **`Trees/Tree.png`** | 768 × 576 = **4 × 3 @ 192px** | a pine tree with a **4-frame sway animation** (#0–3), an alt pine (#4–5, 2f), a stump (#8). → the one **colliding** decoration: a `tree` obstacle, animated. |
| `terrain/decorations/water_rocks/*`, `duck/*` | 64 × 64 strips | water-side scenery (rocks 16f, duck 3f) — **in the void**, on the water backdrop, can't be stepped on. |
| `terrain/resources/trees/Tree1..4.png`, `Stump1..4.png` | | alt tree / stump variants for future variety. |

Still **out of scope**: `terrain/resources/{gold,meat,tools,wood}` (harvestable
nodes, later); `decorations/clouds/*` (deferred parallax); `buildings/`, `fx/`,
`Enemy Pack/` (not terrain).

### Target render model

Bottom → top, tiled renderer:

1. **Water backdrop** — `Water_Background.png` tiled across the screen
   (`self._water_buf` scroll buffer). Always fully covers.
2. **Void / water decorations** — `water_rocks` / `duck` instances placed in the
   void (outside all rooms + corridors), drawn on the backdrop, animated,
   view-culled. No walkability effect (the void is already unwalkable).
3. **Foam** — the current `Water_Foam` frame, centred on **every in-view
   room-perimeter *and* bridge-edge cell**, drawn **behind** the terrain
   surfaces. Shows through the transparent water-sides of the `edge_*` /
   `corner_*` grass tiles and the bridge plank gaps, plus on the open water just
   outside — "foam at the edges, just behind the terrain tile."
4. **Room floor surfaces** — one **SRCALPHA** baked surface per room, every cell
   a whole 64 px tile: perimeter row/col = `edge_*` / `corner_*` (transparent
   water side), interior = `interior` #10. Room dims snapped to a multiple of 64
   so the grid covers the room exactly (no clipped edge tile).
5. **Bridge (corridor) surfaces** — SRCALPHA baked from `Bridge_All.png`,
   directional: horizontal run → `bridge_h_left / mid / right` along its length,
   vertical run → `bridge_v_top / mid / bot`.
6. **Per-room decoration layer** — each room owns a decoration instance list
   (`Deco/*` clutter on interior cells), **drawn per frame** so animated
   decorations (brazier, animated plants) and the swaying trees update; static
   ones just blit. View-culled.
7. **Obstacle skins** (trees = animated `Tree.png`; rocks / pillars / shrubs =
   their current rig skins), then entities, then HUD (unchanged).

### Why it needs work today

- The baked surfaces are `pygame.Surface(size).convert()` — **no alpha, black
  ground.** The `edge_*` / `corner_*` transparent water sides bake to **black**;
  hidden only because foam is drawn *on top*. `TERRAIN_FOAM = False` shows the
  black ring. Nothing can layer on the surface without its transparent parts
  revealing that black.
- Room rects are `uniform(0.55, 0.86)` of a 720 chunk → not a 64-multiple, so
  `paint_room` blits a **clipped** edge tile on the right / bottom — the border
  doesn't complete.
- Foam is drawn *after* the terrain, not behind it.
- Corridors are plain grass strips — there is a purpose-built **bridge** set
  going unused.
- The free-standing decoration layer was removed in the obstacle-skin change;
  `Deco/*`, `Trees/*` and the water scenery now want a home.

### Phases

| # | Scope | Ends when |
|---|-------|-----------|
| **T6 ✅** | `world/map.py`: `paint_room` / `paint_plain` bake to `pygame.Surface(size, pygame.SRCALPHA)` (water buffer unchanged, opaque `.convert()`). `_draw_tiled` reordered to **water → foam → room surfaces → corridor surfaces** — foam now sits *behind* the terrain and shows through the transparent water-side of the autotile edge/corner tiles (and on the open water just outside a room). No new art, no `terrain.json` change; corridors still plain grass. **Done 2026-08-27** — `tests/test_terrain.py` `TerrainSurfaceAlphaTests` (4): every `_room_surfs` / `_corr_surfs` bake is `SRCALPHA` + 32-bit; the water buffer stays opaque; the top row of every baked room surface has `alpha<255` pixels (autotile edge transparency survived — `.convert()` would have baked it black); `_draw_tiled` blits a foam frame before any room surface. Suite **312 → 316**. Screenshots: **foam on** — pale foam scallops peeking from under every room's grass border + on the water outside; **`TERRAIN_FOAM=False`** — clean grass↔water autotile edge, **no black ring**. `_draw_tiled` ≈ 1.24 ms with foam (unchanged — foam was always the bulk), 0.48 ms without. |
| **T7 ✅** | `world/procedural.py`: `config.TILE_PX` (64) new; room rect W/H snapped `max(3*px, round(dim * uniform(0.55,0.86) / px) * px)` and re-centred (corridors still join centres; `bounds` recomputed); corridor `width = px` (was ~90) — one tile wide, rendered as a plank bridge. `data/terrain.json`: a `bridge` block — `sheet: "Bridge/Bridge_All.png"`, `grid: [3, 4]`, `slots: {h_left:0, h_mid:1, h_right:2, v_top:3, v_mid:6, v_bot:9}`. `game/assets.py`: `tile(sheet, idx, *, size=None, cols=None)` — `cols` defaults to `terrain.grid[0]`, overridable for sheets of a different width (the 3-wide bridge sheet); cache key now carries `cols`. `world/map.py`: `_bridge_slot(horizontal, row, col, rows, cols)` staticmethod (end-cap vs mid by position); `cell()` gained a `cols` arg + 3-tuple cache key; `paint_plain` → `paint_corridor` — directional bridge tiles, every corridor cell appended to `self._shore` so foam scallops sit behind the plank gaps over open water; degrades to the interior floor tile when the bridge sheet is absent. **Done 2026-08-27** — `tests/test_procedural.py` `GridAlignmentTests` (3): room dims `% 64 == 0` and `≥ 3·px` across seeds 1/7/99/1234; every corridor min-dim `== 64`; snapped layout still connected + non-overlapping. `tests/test_terrain.py` `BridgeCorridorTests` (4): `bridge` block coherent; `_bridge_slot` picks end-caps + mid; `tile(bridge_sheet, 3, cols=3)` slices while the default `cols=9` returns `None`; corridor bakes are `SRCALPHA` and seed `self._shore`. Suite **316 → 323**. Screenshots: rooms autotile cleanly to all four sides (no clipped edge tile, no black ring); horizontal + vertical corridors render as `Bridge_All.png` plank runs with pale foam wisps showing through the gaps over the teal water backdrop; the H/V bridge junction reads coherently. `_draw_tiled` unchanged in cost (~1.2 ms with foam). |
| **T8 ✅** | `data/terrain.json`: a `decorations` **registry** (array) — each entry `{id, rig, placement, scale, per_room\|chance, collision}`, `placement ∈ {room_interior, void, room_edge}`, `rig` names an existing entry in `rigs`. Shipped wired: `pebble_small` / `pebble_flat` (`deco_rock_1/3` at 0.45–0.5×, `room_interior`, `per_room` 0–4) + `water_rock_a..d` / `duck` (`deco_water_rock_1..4` / `deco_duck`, `void`, per-cell `chance`). `game/config.py`: `TERRAIN_DECOR` (new, default `True`) — gates the whole non-colliding layer; `TERRAIN_DECORATIONS` still gates the obstacle skins. `world/map.py`: `_build_decor_scatter(a)` — string-seeded (`f"{layout.seed}:{room.id}:decor"` / `f"{seed}:{gx}:{gy}:void"`, stable under any `PYTHONHASHSEED`); per-room clutter on **interior** cells only, kept clear of the room centre + 20 px off any obstacle + 40 px apart; void scenery on a 160 px grid over `bounds` (inset `CHUNK//3`), placed only where `_point_ok` fails at the point **and** ±36 px (never clipping a shore), capped at 240. Instances `(frames, anchor_x·scale, anchor_y·scale, fps, wx, wy)` resolved once at build. `_blit_decor()` shared draw — current `get_ticks` frame, base at `(wx, wy)`, view-culled. `_draw_tiled` order now **water → void decor → foam → rooms → corridors → room clutter** (entities/obstacles still on top). **Nothing here touches `self.obstacles` or `is_walkable`**; `collision: true` entries (trees) are deferred to **T9** (world-gen emits them). **Done 2026-08-27** — `tests/test_terrain.py`: `TerrainMetadataTests.test_decoration_registry_is_coherent` + `DecorationScatterTests` (8): deterministic per seed; something placed; clutter lands on interior cells clear of the centre; every void instance fails `_point_ok`; a 137×149 walkability grid is identical with the scatter on vs `TERRAIN_DECOR=False` and the obstacle list is the same length + identity; flag-off → `_room_decor=={}`, `_void_decor==[]`; every instance resolves to real `Surface` frames; void decor is blitted before the foam. Suite **323 → 332**. Screenshots (seed as spawned): pebbles scattered on room interiors clear of spawn, grey water-rocks + the odd duck bobbing on the open water between the bridge islands, foam still behind the plank gaps, no black gaps; flag-off world is bare. `_draw_tiled` ≈ 1.45 ms (was ~1.2 ms — +0.2 ms for ~53 void + in-view clutter blits). |
| **T9 ✅** | `data/terrain.json`: 4 new rigs `deco_tree_1..4` (`terrain/resources/trees/Tree1..4.png`, 8-frame sway @ 192 px, `fps 5`, measured `anchor` = trunk base, `footprint` = trunk width 32–63 px); `obstacle_decor.rigs.tree` remapped from the bush rigs to `[deco_tree_1..4]` (shrub/rock/pillar unchanged); `obstacle_decor.shadow` = `terrain/tileset/Shadow.png` + `shadow_blob: 70` (opaque-blob px within the 192 frame). `game/config.py`: `TERRAIN_SHADOWS` (new, default `True`, needs `TERRAIN_DECORATIONS`). `world/map.py`: `_build_obstacle_decor` also resolves one soft contact shadow per distinct collider radius — `smoothscale(Shadow.png, ·)` so the blob spans `2.2·r`, squashed to `0.55 h` for the oblique view — into `self._obst_shadow[i]`; `_draw_obstacles` blits it (base at `o.pos`, nudged `+0.15·r` down) **before** the skin. Doorway seam: after the shore list is built, drop every `self._shore` cell whose 64 px tile touches **both** a room rect and a corridor rect inflated by `px` — mid-bridge cells (corridor only) keep their plank-gap foam, open room edges (room only) keep their shoreline, only the junction is trimmed. **Done 2026-08-27** — `tests/test_terrain.py` `TreeSkinShadowSeamTests` (8): `tree` → `deco_tree_1..4` (sheets exist, 8 frames, int footprint) while shrub keeps `deco_bush_1`; every skinned `tree` has an 8-frame animated skin scaled to its collider; a tree obstacle still fails `is_walkable` at its centre; `_obst_shadow` keys == `_decos` keys and every shadow surf is wider than tall; `TERRAIN_SHADOWS=False` keeps the skins but empties `_obst_shadow`; the shadow is blitted before the skin; no `_shore` cell straddles a bridge+room; > 100 shore cells survive the trim. `ObstacleDecorTests.test_bigger_collider_…` retargeted tree/shrub → rock/pillar (both on the rock rigs). `BridgeCorridorTests.test_corridors_…seed_the_shore` now asserts a *mid-bridge* cell survives. Suite **332 → 340**. Screenshots: pine + deciduous trees with a soft shadow at the trunk, shrubs still small bushes, rocks grounded by a faint shadow; bridge/room junctions read as solid grass↔plank with no foam bite; mid-span plank gaps still foam; `_draw_tiled + _draw_obstacles` ≈ 1.0 ms. **Deferred:** the optional floor-tile overlay layer (2nd-grass / decorative slots baked into the room surface, `TERRAIN_OVERLAYS`) — pure polish, not started; `collision: true` registry → `Obstacle` is moot (trees are already colliders via `_scatter_obstacles`). |
| **T10 ✅** | `documentation/level_design.md` rewritten to the shipped model — §1.2 (room grid snap), §1.3 (1-wide bridge corridors), §3.3 (SRCALPHA bake, new bottom→top composite order, `paint_corridor` bridges, doorway seam), §3.4 (tree skins + contact shadow), §3.5 (degradation table: `bridge.sheet`, `Shadow.png`, `TERRAIN_DECOR`, `TERRAIN_SHADOWS`), **new §3.6** (the `decorations` registry + `_build_decor_scatter`), §4 (`bridge` / `decorations` / `obstacle_decor.shadow` keys, `Assets.tile(cols=)`), §5 (side-by-side rows), §6 ("Tile layering" note replaced with "shipped (T6–T9)"). `journals/journal.md` — new "Post-Phase-3 — Terrain layering (T6–T10)" section with the phase table + verification + deferred list. `README.md` — test count 269 → 340, the "Tiled terrain" content bullet, the "Assets" world paragraph (bridges, scatter registry, shadows, the four flags), and the "Obstacles are skinned by terrain rigs" note. **Done 2026-08-27** — full `unittest` **340 pass**; `python main.py` walk-through clean (rooms autotile all sides, bridges with gap-foam, trees sway with shadows, pebbles + water-rocks + a duck, no black gaps); flat renderer (empty `assets/`) byte-for-byte unchanged. **Deferred:** the optional floor-tile overlay layer (`TERRAIN_OVERLAYS`) — not started, pure polish. |

### Closing summary — T6–T10 (2026-08-27)

The tiled renderer went from "flat grass rects with a foam fringe" to a layered
scene, without touching generation, collision, or the flat fallback:

- **Bake** — rooms are SRCALPHA (transparent tile fringe preserved), snapped to
  the 64 px grid so the autotile ring always completes; corridors bake as
  directional plank bridges (`Bridge_All.png`, its own 3-wide grid); the
  bridge/room doorway seam is trimmed from the foam ring.
- **Composite** (bottom → top) — scrolling water buffer → void water scenery →
  foam (now *behind* the terrain) → room floors → bridges → interior clutter →
  obstacle shadow + skin.
- **Data-driven scatter** — `terrain.json` `decorations` is an open registry;
  `GameMap._build_decor_scatter` places string-seeded, non-colliding clutter
  (interiors) and water scenery (void). A new prop is a rig + a JSON line.
- **Obstacle polish** — `tree` obstacles use real 8-frame sway sprites
  (`deco_tree_*`); every skin gets a soft `Shadow.png` contact shadow.
- **Flags** — `TERRAIN_FOAM`, `TERRAIN_DECORATIONS`, `TERRAIN_DECOR`,
  `TERRAIN_SHADOWS`, each independent; any missing sheet degrades locally, a
  missing `floor_sheet` drops the whole level to the flat renderer.

Suite **312 → 340** (+28). Per-frame terrain cost ≈ 1.0–1.5 ms. Not done: the
optional floor-tile overlay layer; palette-blend surfaces (the SRCALPHA bake
makes them easy now); the `Deco/*` mushroom/signpost/brazier props (absent from
the pack — registry is ready for them).

### Decisions to confirm

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Room grid alignment (T7): **snap room dims in `procedural.py`** (render == collision == grid), or a whole-tile `paint_room` surface that overhangs the room rect into the void? | Snap in `procedural.py` — one source of truth |
| 2 | Snap rule — `round(dim / 64) * 64`, `ceil`, or `floor` (min 3 tiles)? | `round`, floor-clamped to 3×3 |
| 3 | SRCALPHA on corridor / bridge bakes too? | Yes |
| 4 | Water buffer stays opaque `.convert()`? | Yes |
| 5 | **Corridors — bridges + foam.** Corridors render as `Bridge_All.png` directional autotile (h `left/mid/right` #0/#1/#2, v `top/mid/bot` #3/#6/#9); foam drawn behind so it shows through the plank gaps and along the bridge's long edges. Bridge ends may need a short blend into the room's grass. | **Confirmed** by the user. Bridge blends into room floor at each end (a `bridge_end` tile or just overlap the grass edge). |
| 6 | **Decoration layer per room, animatable, not baked.** Each room owns a decoration **instance list**, drawn per frame (animated entries advance; static ones blit). An optional per-room baked overlay `Surface` for the static ones is a later optimisation. | **Confirmed** by the user. |
| 7 | **Open, data-driven decoration registry** in `terrain.json` (new decoration = new JSON entry, no code). Ship wired to `assets/Deco/*` (18 no-collision props) and `assets/Trees/Tree.png` (the one collider → a `tree` obstacle). `terrain/resources/trees/*` as alternates. | **Confirmed** by the user. |
| 8 | **Room decorations = interior cells only.** Plus a **`void` placement** for water scenery (`water_rocks`, `duck`) on the backdrop — un-steppable already, so no `is_walkable` change. | **Confirmed** by the user. |
| 9 | Flags — one `TERRAIN_DECOR` for the whole non-colliding layer, or split (clutter vs void vs floor-overlays)? Current `TERRAIN_DECORATIONS` gates the obstacle skins. | One `TERRAIN_DECOR` for the non-colliding scatter (rooms + void); keep `TERRAIN_DECORATIONS` for obstacle skins + trees; floor overlays under `TERRAIN_OVERLAYS` (T9), default `True` |

### Touch list (anticipated)

- `world/map.py` — SRCALPHA bakes + `_draw_tiled` reorder (T6); `paint_corridor`
  bridge autotile + foam-behind-bridge (T7); decoration scatter + per-frame
  `_draw_room_decor` / `_draw_void_decor` (T8); tree skin + floor overlays +
  `Shadow.png` + doorway seam (T9).
- `world/procedural.py` — snap room rects to `tile_px` multiples (T7); emit
  `collision: true` decorations (trees) as `Obstacle`s (T8).
- `data/terrain.json` — `bridge` block (T7); `decorations` registry +
  `overlay` slot-lists (T8/T9).
- `game/config.py` — `TERRAIN_DECOR`, `TERRAIN_OVERLAYS` (T8/T9).
- `game/assets.py` — no change expected (`tile()` / `frames()` already
  alpha-safe).
- `tests/test_terrain.py` — SRCALPHA + transparent-preserved + composite order
  (T6); bridge autotile (T7); decoration registry determinism / placement /
  walkability / flag-off (T8); tree collider + animation (T9).
- `tests/test_procedural.py` — room dims 64-multiples; re-pin deterministic
  rects; tree obstacle count (T7/T8).
- `documentation/level_design.md`, `journals/assets_journal.md`,
  `journals/journal.md`, `README.md` (T10).
- **No new dependencies. Nothing committed.**

---

## Bridge corridor rework — B1 (2026-08-27)

Follow-up after T6–T10: the T7 bridge ran its tiles across the corridor's
centre-to-centre collision rect, so `h_left` / `h_right` (and `v_top` / `v_bot`)
end-caps sat buried at the room centres and only middle planks ever showed over
the water. Checked `assets/Bridge/Bridge_All.png` (3 × 4 @ 64): row 0 =
`#0 h_left` (posts left) / `#1 h_mid` / `#2 h_right` (posts right); col 0 =
`#3 v_top` (posts top) / `#6 v_mid` / `#9 v_bot` (posts bottom); the other cells
are loose-plank debris. The slot indices were already right — the placement was
the bug.

- `world/procedural.py` — `Corridor` now carries `axis` (`"h"` west/east |
  `"v"` north/south), `end_low` / `end_high` (the named edge at the smaller /
  larger world coordinate), `room_low` / `room_high`.
- `world/map.py` — `_bridge_slot(axis, index, ncells)` (was
  `(horizontal, row, col, rows, cols)`); `paint_corridor(c)` bakes a surface
  spanning **one tile inside `room_low` → one tile inside `room_high`**
  (`edge ∓ tile_px`, centred) and returns its own `(blit_rect, surface)`, so the
  end-cap planks overlap each room's shoreline tile (no water sliver between the
  bridge and the grass). Collision `rect` untouched.
- `tests/test_terrain.py` `BridgeCorridorTests` +3 (edge properties; matching
  cap baked at each mouth; surface overlaps one tile into each room). Suite
  **340 → 343**.
- Screenshots: every bridge has a posted end-cap that meets the grass on both
  shores with middle planks between; doorway seams still clean; flat renderer
  unchanged.

---

## Depth-sorted scenery + characters — B2 (2026-08-27)

Follow-up: obstacle skins and interior clutter were part of the map draw and so
always sat *under* every entity — the hero could never stand behind a tree.

- `world/map.py` — `draw()` split into `draw_ground()` (terrain only) +
  `scenery_drawables(camera)` → `[(depth_y, fn), …]` for each in-view obstacle
  (`_draw_one_obstacle`) and clutter instance (`_blit_one_decor`). `_draw_tiled`
  no longer paints clutter; `draw()` kept (unsorted) for non-`PlayingState` use.
- `game/states/playing_state.py` — `_draw_depth_layer` merges `scenery_drawables`
  with `(entity.pos.y, fn)` for hero / enemies / boss / summons / dying, sorts by
  ground-contact Y, paints back-to-front. Lower-on-map (larger Y) draws on top;
  a character with a smaller Y than a tree is hidden by its canopy.
- `tests/test_depth_sort.py` (new, 6). Suite **343 → 349**. Screenshots: a 12 px
  Y move flips whether the hero is in front of or behind a tree. Flat renderer,
  `GameMap.draw`, and per-frame cost (`_depth_items` ≈ 0.006 ms) unaffected.

---

## Tree shade replaces obstacle contact shadows — B3 (2026-08-27)

The T9 per-obstacle contact shadow (`Shadow.png`, squashed, under every skinned
tree / rock / bush) is removed. Only **trees** now cast anything: a soft round
shade patch drawn *over* the characters so a hero / enemy under a tree is gently
darkened.

- `game/config.py` — `TERRAIN_SHADOWS` repurposed to gate the tree shade.
- `data/terrain.json` — `obstacle_decor.shadow` / `shadow_blob` → `tree_shadow`
  `{radius_scale: 1.9, color, alpha: 66}`.
- `world/map.py` — `_obst_shadow` + `Shadow.png` scaling gone; new
  `_build_tree_shadows` (one SRCALPHA disc per distinct `R = radius · 1.9`,
  concentric translucent fills) → `self._tree_shadows`; new `draw_tree_shadows`
  blits them after the depth layer (`PlayingState.draw` + `GameMap.draw`).
- `tests/test_terrain.py` shadow cases rewritten (+1 net), `test_depth_sort.py`
  +1 ordering check. Suite **349 → 351**. Screenshots: trees sit in a round
  shade; the hero under one is subtly darkened; rocks / bushes cast nothing.

---


## Asset library reorganization — A1 ✅

**Date:** 2026-08-27. **Status:** DONE. Plan + decisions below; results at the
end.

`assets/` has grown to **576 files** (493 png, 43 `.aseprite`, 39 `.DS_Store`,
1 `.md`). Folder names are inconsistent (`Bridge/`, `Deco/`, `Enemy Pack/`,
`Units/`, `Trees/` capitalised at the root beside `terrain/`, `fx/`,
`projectiles/`); `title screen.png` sits loose at the root with a space in the
name; and the character sprites the game loads were removed from disk (`git`
shows `D assets/sprites/soldier/*` and `D assets/sprites/orc/*`) — so the suite
is **currently red** (6 fails in `test_assets`) and the hero + chaser render as
primitives. A new `assets/Units/` pack (`{Black,Blue,Purple,Red,Yellow}
Units/{Archer,Lancer,Monk,Pawn,Warrior}/*.png`, 192×192 strips) was added to
replace them.

### Decisions (from the user, 2026-08-27)

1. **Heroes:** Aegis = **blue**, Kestrel = **yellow**, Nihil = **purple**.
2. **Unit type varies by hero** — Aegis = **Warrior**, Kestrel = **Archer**,
   Nihil = **Monk** (a caster silhouette for the status hero).
3. **Hurt / death:** omit — the `Animator` clamps a missing anim, so the hero
   holds `idle` when hit or during the death sequence. No fake art.
4. **Unused packs are NOT deleted.** Instead: normalise the *whole* library into
   one consistent, conventionally-named tree and rename/move every PNG so each
   pack is ready to wire up later. Only true metadata is removed — every
   `*.aseprite` (43) and every `.DS_Store` (39). `CREDITS.md` stays.

### Naming convention (every category)

- **lower-case**, `snake_case`; spaces → `_`; no capitals or spaces anywhere in
  a path.
- **Animated entity** → one folder, one file per animation strip:
  `<category>/<entity>/<anim>.png`. `<anim>` is the pack's own suffix,
  lower-cased (`idle`, `run`, `walk`, `move`, `attack`, `attack1`, `attack2`,
  `shoot`, `throw`, `heal`, `guard`, `windup`, `recovery`, `death`, `hurt`,
  `avatar`…). Anim names are **not** force-normalised across packs — a mob that
  ships `Move` keeps `move`; one that ships `Run` keeps `run`.
- **Single image** → `<category>/<group>/<name>.png`.
- **Colour variants** → colour is a folder level: `<category>/<colour>/…`.

### Target layout

```
assets/
├── characters/                      # 5 colours × the unit types (playable + reserve)
│   ├── blue/warrior/{idle,run,attack1,attack2,guard}.png    <- Aegis (wired)
│   ├── yellow/archer/{idle,run,shoot}.png  + arrow.png      <- Kestrel (wired)
│   ├── purple/monk/{idle,run,heal,heal_effect}.png          <- Nihil (wired)
│   ├── {blue,yellow,purple,red,black}/{archer,lancer,monk,pawn,warrior}/…   (reserve)
│   └── lancer keeps its directional strips:
│       {up,down,right,upright,downright}_{attack,defence}.png
├── enemies/
│   ├── orc/{idle,walk,hurt,death}.png                       <- chaser (wired; restore from git)
│   ├── bear/ bomb_fish/ bumblebee/ giant_bat/ gnoll/ gnome/ harpoon_shark/
│   │   hex_shaman/ lizard/ minotaur/ paddle_shark/ panda/ skull/ slingshot_gnome/
│   │   snake/ spider/ spear_goblin/ thief/ torch_goblin/ troll/ turtle/  (reserve)
│   │       each: {idle, run|walk|move, attack|throw|shoot, avatar, …}.png
│   └── extra/  boat/ cannon/ cave/ dead_tree/ fish_hut/ gnome_buildings/ goblin_hut/
│       minotaur_guard/ panda_guard/ pig/ pig_rider/ pirate_tower/ seahorse_boat/
│       skull_guard/ skull_decorations/ turtle_guard/ wooden_fence/  (reserve)
├── projectiles/
│   ├── arrow.png                                            (wired)
│   └── acorn.png harpoon.png cannon_ball.png gnoll_bone.png hex_bolt.png …  (reserve)
├── buildings/
│   └── {black,blue,purple,red,yellow}/{archery,barracks,castle,house_1,house_2,house_3,monastery,tower}.png
├── effects/
│   └── dust_1.png dust_2.png explosion_1.png explosion_2.png fire_1.png fire_2.png fire_3.png water_splash.png
├── terrain/
│   ├── tiles/     tilemap_1..5.png  water_background.png  water_foam.png  shadow.png
│   ├── bridge/    bridge_all.png
│   ├── props/     bush_1..4  rock_1..4  tree_1..4  stump_1..4  water_rock_1..4  duck
│   │              cloud_1..8  deco_1..18  dead_tree     (bush/rock/tree/water_rock/duck wired)
│   └── resources/ gold/  meat/  tools/  wood/            (lower-cased, otherwise as-is)
├── ui/
│   └── title.png                                          (was "title screen.png"; wired)
└── CREDITS.md
```

Every current PNG lands somewhere; nothing is dropped except `*.aseprite` /
`.DS_Store`.

### The 3 wired heroes — `data/sprites.json`

| hero | colour | unit | rig name | anims (source → key, frames) |
|------|--------|------|----------|------------------------------|
| **Aegis** | blue | Warrior | `hero_aegis` | `idle` (8), `run`→`walk` (6), `attack1`→`attack` (4) |
| **Kestrel** | yellow | Archer | `hero_kestrel` | `idle` (6), `run`→`walk` (6), `shoot`→`attack` (8) |
| **Nihil** | purple | Monk | `hero_nihil` | `idle` (6), `run`→`walk` (4), `heal`→`attack` (8) |

192×192 frames; `face: "right"`; `content` / `scale` / `anchor` measured from
each hero's art (as was done for `soldier`). No `hurt` / `death` keys.

`data/characters.json`: `aegis.sprite: "hero_aegis"`,
`kestrel.sprite: "hero_kestrel"`, `nihil.sprite: "hero_nihil"`; plus a
primitive-fallback / HUD accent `color` — `aegis (70,130,210)`,
`kestrel (230,200,90)`, `nihil (170,110,210)`.

### Touch list (code / data / tests / docs)

- `data/sprites.json` — drop `soldier`; add `hero_aegis` / `hero_kestrel` /
  `hero_nihil`; repoint `orc` (→ `enemies/orc/…`) and `arrow`
  (→ `projectiles/arrow.png`, path unchanged).
- `data/characters.json` — the 3 `sprite` keys + a `color` per hero.
- `data/terrain.json` — every `"file"`, `floor_sheet`, `water_tile`,
  `bridge.sheet` → new `terrain/tiles|bridge|props/` paths + renamed files
  (`Tilemap_color1.png` → `terrain/tiles/tilemap_1.png`, `Bushe1.png` →
  `terrain/props/bush_1.png`, `Tree1.png` → `terrain/props/tree_1.png`, …).
- `game/config.py` — `MENU_TITLE_IMAGE = "ui/title.png"`.
- `game/states/playing_state.py` / `entities/player.py` — use the hero's
  `color` for the `_draw_player` primitive fallback + HUD accent instead of the
  single `config.COLOR_PLAYER`.
- `.gitignore` — add `*.aseprite` and `.DS_Store`.
- Tests — `test_assets.py` (`test_expected_rigs_present` → `hero_aegis`,
  `hero_kestrel`, `hero_nihil`, `orc`, `arrow`; `test_files_exist` picks up new
  paths), `test_terrain.py` (`test_rig_files_and_strip_widths`,
  `test_referenced_sheets_exist`, decoration-rig names),
  `test_characters.py` (all 3 now carry a `sprite`),
  `test_enemy_sprite.py` (orc path), `test_animation.py`,
  `test_menu.py` (title path).
- Docs — `README.md` (Assets section + the `assets/` tree),
  `documentation/level_design.md` §3.3 / §3.4 / §4 (paths + rig names),
  `documentation/terrain_tile_slots_formula.md`
  (`Tilemap_color1.png` → `terrain/tiles/tilemap_1.png`),
  `assets/CREDITS.md` (rewrite the file lists; add `Units/` as "Pack 3"; note
  the enemy / buildings / fx packs are filed for future use),
  `journals/journal.md` pointer, this section → a completion note.

### Execution

`git mv` for every move (keeps history), `git rm` for the `*.aseprite` /
`.DS_Store` deletes. A short script generates the move list from the tables
above; run it, then `python -m unittest discover -s tests` back to green
(6 currently red from the missing `soldier`), a windowed `python main.py`
(each hero renders as its coloured unit, chaser as the orc, title loads,
terrain unchanged), and a headless screenshot per hero.

### Results (done 2026-08-27)

- **591 → 509 files.** 82 deletes (43 `.aseprite` + 39 `.DS_Store`), 507
  moves/renames into the tree above. `git` detects ~238 as renames; the untracked
  `Units/` pack lands as adds. `.gitignore` now blocks `*.aseprite` / `.DS_Store`.
- Confirmed conventions: wired heroes keep the game's `idle/walk/attack`
  vocabulary — `sprites.json` maps `walk`→`run.png`, `attack`→`attack1.png` /
  `shoot.png` / `heal.png` (source files renamed to `run` / `shoot` / `heal`,
  not to `walk`/`attack`). Reserve enemy packs keep their `avatar.png` portraits.
- `data/sprites.json`: `soldier` dropped as a hero but re-declared as a **reserve
  rig** pointing at `characters/soldier/` (keeps `test_assets` honest and the set
  usable later); new `hero_aegis` (blue Warrior, idle 8 / walk←run 6 / attack←attack1 4),
  `hero_kestrel` (yellow Archer, 6 / 4 / shoot 8), `hero_nihil` (purple Monk,
  6 / 4 / heal 11) — all 192×192, measured `content`/`scale`/`anchor`, no
  hurt/death; `orc` repointed to `enemies/orc/`; `arrow` unchanged.
- `data/characters.json`: `sprite` + `color` on all three
  (`aegis (70,130,210)` / `kestrel (230,200,90)` / `nihil (170,110,210)`).
- `data/terrain.json`: every path → `terrain/tiles|bridge|props/` + renamed
  files. `game/config.py`: `MENU_TITLE_IMAGE = "ui/title.png"`.
- `game/states/playing_state.py`: `self._hero_color` from `cdef["color"]` feeds
  the `_draw_player` primitive fallback (was the single `config.COLOR_PLAYER`).
- Tests: `test_assets.py` — `test_expected_rigs_present` now covers the 3 hero
  rigs + `soldier` + `orc` + `arrow`; `test_strip_width_…` iterates every
  animated rig generically. Suite back to **351 green** (was 6 red).
- Docs: `assets/CREDITS.md` rewritten (Pack 1 orc / Pack 2 terrain / Pack 3
  units + a reserve-enemy note); `README.md` Assets section + project tree +
  "currently sprited" (3 heroes now); `documentation/level_design.md` +
  `terrain_tile_slots_formula.md` paths (`Tilemap_color1.png` →
  `terrain/tiles/tilemap_1.png`).
- Screenshots: each hero renders as its distinct coloured unit
  (blue Warrior / yellow Archer / purple Monk), HUD trait + HP correct per hero;
  chaser renders the orc; menu title loads from the new path; terrain unchanged.

**Fix (2026-08-27):** the first `content` crops were measured from the **idle
strip only**, so the wider walk / attack frames (the warrior's sword swing, the
archer's bow draw, the monk's heal aura) were clipped. Recomputed each hero's
`content` as the **union bounding box over every anim** and re-derived
`scale` / `anchor` from that, targeting a ~58 px on-screen idle-body height:
`hero_aegis` content `[43,44,120,112]` scale `[78,73]` anchor `[38,61]`;
`hero_kestrel` `[53,46,87,90]` / `[57,59]` / `[25,59]`;
`hero_nihil` `[35,63,121,71]` / `[102,60]` / `[51,60]` (the heal frame is wide).
Screenshots re-verified — full sprite, no clipping, size in line with the
terrain. Suite still 351 green.

**Downscale (2026-08-27):** the heroes still read as much larger than the
`PLAYER_RADIUS = 16` collider. Re-scaled so ≤ ~10 % of the sprite's opaque
pixels (measured across idle + walk + attack) fall outside an `R = 16` circle on
the body centre — the standing body is now ~32–37 px, close to the 32 px collider
diameter: `hero_aegis` scale `[46,43]` anchor `[22,35]`; `hero_kestrel`
`[37,38]` / `[16,38]`; `hero_nihil` `[56,33]` / `[28,33]` (`content` unchanged —
still the full union bbox, so the swing / bow / heal aura never clip). Verified
with the collider ring drawn: the body hugs the circle, only the head + the
transient attack reach sit outside. Suite 351 green.

---

## Enemy sprite pass — E1–E6 ✅ (2026-08-27)

**Date raised:** 2026-08-27.

`assets/enemies/orc/` was removed from disk; `chaser` (its only user) now draws
a primitive, and the other 12 enemies + the boss have never had a sprite. The
reorganised `assets/enemies/` holds **21 full mob sets** (each `idle` +
`run`/`walk`/`move` + usually `attack`/`shoot`/`throw` + `avatar`) — enough to
cover every current enemy and the boss with 7 to spare. All from the same
Tiny Swords enemy pack, so after this pass the whole `assets/` tree is one
source and `CREDITS.md` collapses to a single entry.

`assets/characters/dead/dead.png` — a **14-frame 64 × 256 one-shot** skull-poof
(flash → skull + light ring → bounce → sink) — is the **shared death animation**
for every entity, hero or enemy (the packs ship no per-creature death strip).
See E2.

### Sprite → enemy

| sprite (`assets/enemies/…`) | enemy (`data/enemies.json`) | move anim | attack anim |
|---|---|---|---|
| `skull`           | `chaser`     | run  | attack (7f) |
| `spider`          | `fast`       | run  | attack (8f) |
| `turtle`          | `tank`       | walk | attack (10f) |
| `bumblebee`       | `swarm`      | move | attack (11f) |
| `slingshot_gnome` | `ranged`     | run  | shoot (9f) + `acorn_projectile` |
| `bomb_fish`       | `exploder`   | run  | `bomb_fuse_lit` / `bomb_spinning` |
| `panda`           | `shielded`   | run  | attack (13f) |
| `bear`            | `elite`      | run  | attack (9f) |
| `gnome`           | `summoner`   | run  | attack (7f) |
| `troll`           | `brute`      | walk | `windup` (5f) → `attack` (6f) → `recovery` (10f) |
| `minotaur`        | `charger`    | walk | attack (12f) |
| `thief`           | `teleporter` | run  | attack (6f) |
| `hex_shaman`      | `warlock`    | run  | attack (10f) + `projectile` + `explosion` |
| `giant_bat`       | `the_first_hunger` (boss) | move | attack (7f) |

### Reserve (unused mob sets)

`gnoll`, `harpoon_shark`, `lizard`, `paddle_shark`, `snake`, `spear_goblin`,
`torch_goblin`, plus everything under `assets/enemies/extra/`.

### Milestones

- **E1 — rig infra. ✅ (2026-08-27)** The dead `orc` rig (files removed with the
  folder) was replaced in `data/sprites.json` by **14 rigs** — one per set in
  the table — each `idle` + `walk` (←the set's `run` / `walk` / `move` strip) +
  `attack` (←`attack` / `shoot`). `frame` = the strip's native cell (192 / 256 /
  320 / 384 px); `content` / `scale` / `anchor` computed from the union bbox
  across those anims, scaled so the idle body ≈ `2.4 × radius` on screen (same
  method as the hero fix). No `hurt` / `death` strips ship — the flinch / death
  anim names still resolve (`Animator.play` sets the name; `frame()` returns the
  held pose), exactly as for the heroes. `chaser.sprite` re-pointed `orc` →
  `skull` here too (its rig is what broke); the other 5 of the chase family stay
  primitive until E2. `test_assets.py` / `test_enemy_sprite.py` moved their
  representative-rig refs `orc` → `skull`. **Verified:** all 14 rigs slice to
  the declared frame counts with `content` inside `frame`, no clipping (montage
  + in-game — the chaser renders as skeleton warriors again). Suite **353 green**
  (was 5 red from the missing `orc` files).
- **E2 — shared hit tint + `dead` death animation, then the chase family. ✅
  (2026-08-27)**
  Two pieces of render infra that every sprited entity (heroes included) needs
  because the Tiny Swords packs ship no `hurt` / `death` strips, followed by the
  first batch of enemy wiring.

  **Shipped:** `entities/enemy.py` — `_has_hurt` (rig has a real `hurt` strip?),
  `take_damage` sets `_hurt_t` always but only `anim.play("hurt")` when
  `_has_hurt`, `_anim_name` guards `"hurt"` likewise, `_hurt_t` decays even for
  animless enemies. `game/states/playing_state.py` — `_HIT_TINT (150,30,30)` +
  `_hit_tinted(frame)` (`BLEND_RGBA_ADD` copy); `_draw_enemy_sprite` /
  `_draw_player` blit the tinted frame while `_hurt_t > 0` (no more circle pop);
  `_hero_has_hurt` + `_hero_anim_name` guard. Death: `_dying` / `_update_dying`
  replaced by `_death_fx` (`[Animator("dead", start="loop"), pos, facing]`) +
  `_spawn_death_fx` / `_update_death_fx` (drop on `Animator.finished`) /
  `_draw_death_fx`; `_cull_dead_enemies` poofs **every** dead enemy (sprited or
  not); `update()` on hero death spawns a poof and holds `_death_seq_t = 1.05`;
  `_run_death_sequence` advances `_update_death_fx`; `_draw_player` early-returns
  while `not alive` so the poof stands in; `_depth_items` carries the poofs.
  `data/sprites.json` — new `dead` rig. **`dead.png` shipped as a 7 × 2 grid of
  128 px frames**, but the loader (`_build_frames`) only does a single
  horizontal row — the first cut declared `frame [64,256]` and sliced 14
  half-column strips straddling both rows ("cut in half"). Fixed by **repacking
  `dead.png` to a 1792 × 128 14 × 1 strip**; rig is `frame [128,128]`, one-shot
  `loop` anim `fps 15`, `content [35,32,60,67]`, `scale [39,44]`,
  `anchor [19,41]`. `_spawn_death_fx(pos, facing, scale=1.0)` carries a scale
  factor on the fx entry; `_draw_death_fx` scales `size` **and** `anchor` by it.
  `_ENEMY_DEATH_FX_SCALE = 0.55` — **enemy** death poofs render at 55 %, the
  **hero** poof stays full size. `data/enemies.json` — `sprite` on
  `fast` → `spider`, `tank` → `turtle`, `swarm` → `bumblebee`,
  `shielded` → `panda`, `elite` → `bear`. `tests/test_enemy_sprite.py` rewritten
  (`HitTintTests`, `DeathPoofTests` incl. the 0.55 / 1.0 scale checks,
  chase-family / no-hurt-anim assertions). Suite **353 → 356**. Screenshots:
  chase-family crowd renders; a hit spider flashes red (no disc); enemy poof is
  visibly smaller than the hero poof.

  1. **Hit tint (replaces the circle flicker).** Today `take_damage` sets
     `_hurt_t` and calls `anim.play("hurt")`; the rig has no `hurt` strip, so
     `Animator.frame()` returns `None` and `_draw_enemy_sprite` /
     `_draw_player` fall back to a `pygame.draw.circle` for ~0.26 s after every
     hit — the sprite visibly pops to a coloured disc. Change: **do not switch
     to `"hurt"`** when the rig lacks it (`assets.frame_count(rig, "hurt") == 0`);
     keep the current idle / walk / attack frame and, while `_hurt_t > 0`, blit
     a **red-tinted copy** of that frame — `frame.copy()` +
     `fill((150, 30, 30, 0), special_flags=BLEND_RGBA_ADD)` (brightens toward
     red, keeps the silhouette + detail). Shared helper (or a `tint=` arg on
     `Assets.frame()` / `frames()`, memoised, alongside the existing
     `image(tint=)` path). Rigs that *do* have a `hurt` strip keep using it.
  2. **`dead` death animation.** New shared rig `dead` from
     `assets/characters/dead/dead.png` — **14 frames, 64 × 256, one-shot**
     (white flash → skull poof + light ring → bounce → sink into the ground),
     `fps ≈ 15`, `content` = union bbox, `anchor` = feet. On death of **any**
     entity (hero or enemy), the creature sprite stops and a one-shot `dead`
     animation plays at the death position (feet-anchored, `_facing`-flipped),
     then is removed — replacing the enemy "linger on the held last frame"
     (`_dying`) and the hero "freeze on `idle`" (`_run_death_sequence`). Enemy:
     push `[Animator("dead"), pos]` to a `_death_fx` list drawn in the depth
     layer, drop the `e.anim.play("death")` hold. Hero: play `dead` for its full
     length (~0.9 s) inside `_death_seq_t` before `_end_run`. Non-sprited enemies
     also get the poof now (uniform feedback).

  3. **Chase family wiring.** `sprite` on `fast` / `tank` / `swarm` / `shielded`
     / `elite` (chaser done in E1). The E1 rigs carry first-pass
     `content` / `scale` / `anchor` (idle body ≈ 2.4 · `radius` = 10 / 24 / 7 /
     16 / 22); re-tune from a mixed-crowd screenshot.

  Green + screenshots: a hit enemy flashes red (no disc), a dying enemy + a
  dying hero both play the skull poof.
- **E3 — ranged / special. ✅ (2026-08-27)** `data/enemies.json` — `sprite` on
  `ranged` → `slingshot_gnome`, `exploder` → `bomb_fish`, `summoner` → `gnome`,
  `brute` → `troll` (the E1 rigs' first-pass `content`/`scale`/`anchor` at
  2.4 · `radius` = 13 / 16 / 20 / 30 read fine in-game — small gnome skirmisher,
  puffer, wizard, club-raising troll with the elite ring). `test_enemy_sprite.py`
  `SPRITED` / `PRIMITIVE` updated (only `charger` / `teleporter` / `warlock` stay
  primitive, for E4). Suite **356**. **Deferred:** the `bomb_fish` bomb strips
  on the exploder blast telegraph and `slingshot_gnome` `acorn_projectile` as
  the ranged shot — both touch the projectile / explosion renderers, out of
  scope for the sprite wiring; revisit as polish.
- **E4 — FSM enemies. ✅ (2026-08-27)** `data/enemies.json` — `sprite` on
  `charger` → `minotaur`, `teleporter` → `thief`, `warlock` → `hex_shaman`.
  **All 13 enemies are now sprited.** `entities/enemy.py` — `_anim_name` gained
  an `"attack"` branch driven by a new `_attacking` property
  (`telegraphing or ai["fs"] == "attack" or ai["slam_state"] == "attack"`), so
  the FSM wind-up + strike (and the brute's slam) play the rig's one-shot
  `attack` strip; the shared `if e.telegraphing:` red ring still draws over the
  sprite. `tests/test_enemy_sprite.py` — `test_every_enemy_has_an_animator`
  (drives off `get_content().enemies`), `test_fsm_telegraph_and_attack_states_play_the_attack_anim`
  (charger `ai["fs"]`, brute `ai["slam_state"]`). Suite **356 → 357**.
  Screenshots: minotaur / thief / hex_shaman each render mid-telegraph in their
  attack pose inside the telegraph ring.
- **E5 — boss. ✅ (2026-08-27)** `entities/boss.py` — `Animator` + `_facing` +
  `_hurt_t` / `_has_hurt`; `_anim_name` maps `intro`/`recover` → `idle`,
  `telegraph`/`active` → `attack`, else `walk`/`idle`, `not alive` → `death`;
  `update` advances the anim + tracks facing + decays `_hurt_t`; `take_damage`
  sets `_hurt_t`. `data/bosses.json` — `the_first_hunger.sprite = "giant_bat"`.
  `game/states/playing_state.py` — `_draw_boss` blits the frame (feet-anchored,
  facing-flipped, hit-tinted while `_hurt_t > 0`) and keeps the three telegraph
  overlays; primitive circle stays as the fallback; the HUD health bar is
  untouched. `_on_boss_killed` spawns a `dead` poof at 1.4× (mostly unseen — the
  victory transition follows). `tests/test_boss.py` `BossSpriteTests` (+2).
  Suite **357 → 359**. Screenshot: the boss renders as a large winged bat in its
  attack pose under each of the radial-barrage / charge / summon-brood
  telegraphs.
- **E6 — docs / credits + single source. ✅ (2026-08-27)** Made `assets/`
  genuinely one-source: `projectiles/arrow.png` swapped to the Tiny Swords
  archer arrow (64 px; `arrow` rig `content [10,26,43,12]` / `scale [26,7]` /
  `anchor [13,3]`); the unused `characters/soldier/` reserve rig **and folder
  removed** (its ~8 `test_assets.py` refs repointed to `hero_aegis` — the
  one-shot `attack` covers the death-clamp / no-loop cases). `assets/CREDITS.md`
  rewritten as a single **"Tiny Swords" by Pixel Frog** entry (wired list +
  reserve list); the standalone `assets/ui/title.png` illustration is the only
  noted non-pack asset. `README.md` — top blurb, "currently sprited" (all 3
  heroes + all 13 enemies + boss + the hit-tint / death-poof note), the Content
  bullet. `journals/journal.md` — "Enemy + boss sprite pass (E1–E6)" pointer.
  Suite **359**.

---

## Sprite anchor drop — seat the sprite in the collider (2026-08-28)

Every rig is blitted so its `anchor` pixel lands on `entity.pos` (the collider
centre), and the character anchors sit at the **feet** — so the body rendered
entirely *above* the collision circle and the circle hugged the ground at the
character's ankles. Verified with the F7 collision overlay: the green rings sat
below the sprites.

Added one knob, **`config.SPRITE_ANCHOR_DROP = 0.7`** — a downward render offset
of `SPRITE_ANCHOR_DROP * collider_radius * camera.zoom` screen px, so `entity.pos`
effectively rises into the lower torso and far more of the sprite falls inside
the circle. At the shipped `PLAYER_RADIUS = 16` / `CAMERA_ZOOM = 1.5` that is
16.8 px; for enemies it scales with each `enemy.radius`, so it tracks size
(small `swarm` barely shifts, `tank` / boss shift more).

- `game/states/playing_state.py` — new `_sprite_drop(radius)` helper; the offset
  is added to the blit `y` in `_draw_enemy_sprite`, `_draw_player`, `_draw_boss`
  and `_draw_death_fx`. `_spawn_death_fx` gained a `radius` arg (5th tuple slot,
  default `PLAYER_RADIUS`) threaded from the enemy / hero / boss it replaces, so
  the poof drops by the same amount and doesn't jump.
- `world/map.py` — `_draw_one_obstacle` applies the same drop
  (`SPRITE_ANCHOR_DROP * o.radius * _render_zoom`) to the obstacle **skin**, so
  trees / rocks / bushes seat into their colliders too (added in a follow-up on
  the same day). The fallback circle branch stays on `o.pos` (it *is* the
  collider), and the **tree canopy shade** (`draw_tree_shadows`) stays on the
  world anchor — it's a ground-plane pool, not the billboard sprite.
- **Render-only.** `entity.pos`, `resolve_movement` / `is_walkable`, projectile
  and cone hit tests, off-screen spawn, world-gen placement and the depth sort
  (`_depth_items` / `scenery_drawables` key on the *unshifted* `.pos.y`) are all
  untouched.
- The primitive fallbacks, status / elite / shield rings and the F7
  collision-vis circle stay on the collider centre — the rings now read around
  the torso, the debug circle still shows the true collider.
- `tests/test_enemy_sprite.py` — new `SpriteAnchorDropTests` (4): the offset is
  `fraction * radius * zoom`; the hero blit `y` is exactly `collider_y - ay*z +
  drop`; `SPRITE_ANCHOR_DROP = 0.0` puts the anchor back on the collider
  (byte-identical); the depth-sort key is still the unshifted entity `y`. Plus
  `DeathPoofTests` — the poof tuple carries the entity radius (hero + enemy).
  `tests/test_terrain.py` — `test_obstacle_skin_is_seated_below_the_collider_by
  _the_drop` (the skin blit `y` shifts by `0.7 * o.radius` between drop 0.0 and
  0.7). Suite **397 → 403**.

Screenshots: F7 overlay before (rings at the feet / trunk base) vs after (rings
around the lower torso / trunk, sprites sitting inside the circle). Tune via the
single constant; `0.0` disables it everywhere.

---

## Wired the leftover `terrain/props` decorations (2026-08-28)

`assets/terrain/props/` had unused PNGs. Added them as **non-colliding**
decorations, data-only in `data/terrain.json` (no code):

- **`deco_ground_1..18`** rigs -> `deco_1..18.png` (`deco_1..15` are 64x64,
  `deco_16/17` 64x128, `deco_18` 192x192 -- all single static frames, anchored
  at the art's base). 9 wired as `room_interior` entries (`sprout_a/b`, `twig`,
  `flower_a/b`, `mushroom`, `reed_a/b`, `flower_patch`) at `per_room [0,1]` /
  `[0,2]`, scale 0.35-0.6; the rest stay available.
- **`deco_stump_1..4`** rigs -> `stump_1..4.png` (192x256, static). Two wired
  (`stump_a`, `stump_b`) as `room_interior`, scale 0.5-0.55.
- **`deco_cloud_1..8`** rigs -> `cloud_1..8.png` (576x256, static). Four wired
  as `void` decorations, `chance` 0.005-0.006, scale 0.26-0.32 -- sparse cloud
  puffs on the open water between islands. They sit on the void layer (behind
  the islands), like the water rocks; an overhead/parallax pass could move them
  later.

All go through the existing `_build_decor_scatter` path: room clutter is
spacing-capped (>= 40 px apart, fully-interior cells only, clear of the centre
disc and obstacles) so the extra entries do not crowd a room; nothing here
touches `obstacles` / `is_walkable`. `tests/test_terrain.py` (registry coherence
+ strip-width checks) validates every new rig/entry. Suite unchanged at 438.

---

## Houses — plan (2026-08-28)

Place a house (large circular `Obstacle`) in sufficiently large rooms, reusing
the whole obstacle pipeline; colour + type randomised from the run seed.
Assets: `assets/buildings/<5 colours>/house_1..3.png` (128x192).

- [x] `game/config.py` -- `TERRAIN_BUILDINGS: bool = True`.
- [x] `entities/obstacle.py` -- `KINDS["house"] = (48, True, (150, 120, 90))`.
- [x] `data/terrain.json` -- 15 `house_<colour>_<n>` rigs (`frame [128,192]`,
  per-type `footprint` 112/128/122, feet anchors [64,173]/[64,178]/[64,172]) +
  `obstacle_decor.rigs["house"]` list (blue, red, yellow, purple, black x 1..3).
- [x] `world/procedural.py` `_scatter_houses(rooms, all_doors, rng, boss_id, out)`
  -- runs **before** the small-obstacle loop, gated on `TERRAIN_BUILDINGS` (off
  => pass skipped, draws no RNG):
  - eligible: any room kind **except `boss`** (so `combat`, `start`, special).
  - size gate: `min(w,h) >= 6*TILE_PX` **and** `len(cells) >= 60`; ~35% roll
    (`_HOUSE_ROOM_CHANCE`); one house per room before the village step; global cap
    `_HOUSE_GLOBAL_CAP = 7`.
  - centre keep-clear disc, measured from **both** the shaped-room centroid and
    the bbox centre: `combat` `max(min(w,h)*0.30, R+2t)`, special
    `max(min(w,h)*0.22, R+2t)`, `start` `max(min(w,h)*0.25, R+2t)` (`R=_HOUSE_RADIUS`,
    `t=TILE_PX`).
  - house cell + its 8 neighbours all in `room.cells` (inland); `>= 2R` from
    doorway slabs inflated by `2R`; `>= 2R` from every other house.
  - `o.variant` for a house encodes `colour_band*3 + type` -> 1..15; small
    obstacles keep their 1..4 in the later cosmetic pass, which now skips houses.
- [x] **Village clusters.** If the room is roomy (`len(cells) >=
  _VILLAGE_MIN_ROOM_CELLS = 100`), after the first house add `rng.randint(1, 3)`
  (`_VILLAGE_EXTRA`) more:
  - one colour band rolled per room, so a village is colour-cohesive; each extra
    house takes the next unused `house_*` type (1,2,3) then falls back to a random
    type once all three are used.
  - each extra house is within `_VILLAGE_RADIUS[1] * TILE_PX` (5 tiles = 320 px)
    of the **first** house, `>= 2R` from all others, and still passes every rule
    above.
  - `_spot()` retries 16 times per house; the cluster stops early if it runs out
    of room. Total still bounded by `_HOUSE_GLOBAL_CAP`.
- [x] Tests -- `tests/test_houses.py` (13): eligible-room / never-boss / off-centre
  / doorway-clear / deterministic / variant range; collider blocks standing +
  projectiles; village = one colour band, varied types, `>= 2R` apart, all within
  the cluster radius of the anchor; flag-off = no houses + stable stream + special
  centres clear both ways. `tests/test_terrain.py` updated: `test_obstacle_
  variants_in_range` allows 1..15 for houses; `test_sprite_width_matches_the_
  scaling_formula` indexes the rig list by `% len(choices)` not `% 4`.
- [x] No changes to `world/map.py` render, `is_walkable`, `resolve_movement`,
  depth sort -- houses ride the existing obstacle path.

### Implemented — 2026-08-28

Suite: **451 green** (was 438; +13 in `test_houses.py`).

Notes / deviations from the plan:
- **Both-centres keep-clear.** The small-obstacle special-room disc in
  `_scatter_obstacles` was widened from `0.22` about the centroid to `0.24` about
  *both* the centroid and the bbox centre. Adding the house pass shifts the shared
  RNG stream, which on seed 5 nudged a `pillar` to ~103 px from an `altar` bbox
  centre (`test_special_room_centres_kept_clear` checks a `0.2` disc there). For an
  L / T room the centroid and bbox centre sit a cell or two apart, so clearing
  only one left a shot-blocker readable as "mid-room". Houses got the same
  both-centres treatment.
- **Concurrent rename fallout.** Several `deco_ground_*` rigs were renamed on disk
  during this pass (`_12/_13` -> `_pumpkin_1/2`, `_16/_17/_18` ->
  `_cross_sign/_left_arrow_sign/_scarecrow`); the matching `decorations` entries
  still pointed at the old rig names and were repointed here so
  `test_decoration_registry_is_coherent` passes.
- **House sprite scale.** `_build_obstacle_decor` scales a rig so its `footprint`
  covers `2*R*size_boost`. The sprite tracks the collider, so house size is tuned
  purely through `_HOUSE_RADIUS` / `KINDS["house"]` -- initially `48`, then pulled
  to **31** (~35% smaller) so a house reads as roughly one tile wide instead of
  dominating the room. The frame stays taller than the collider (a house rises
  well above its footprint) and the anchor drop seats the door sill on the
  collider centre.
- Over 40 seeds every seed places at least one house; villages (>= 2 in a room)
  show up on roughly one seed in six.

---

## Obstacle split — minerals vs. trees, shrubs demoted to decor (2026-08-28)

Goal from the request: two obstacle families instead of a flat weighted pick.
**Minerals** (`rock`, `pillar`) keep everything as-is. **Trees** get a smaller
*collision* ring (the art stays full size) and ~25% more of them for a lusher
canopy. **Shrubs stop being obstacles** and come back as sparse, non-colliding
decoration; other low flora (mushrooms, flowers) may now cluster into patches.

### Design decisions (locked with the user)
- Shrub is removed from `KINDS` entirely; bushes return purely as `decorations`
  data, no collision of any kind.
- Rock / pillar placement is left byte-identical: the per-room loop keeps its
  4-way `rng.choices(("tree","rock","pillar","shrub"), (4,3,2,3))` draw and still
  materialises a throw-away `Obstacle("shrub")` so the `(radius + gap)` spacing
  maths is unchanged, then a final pass strips every `shrub` from the list.
- Tree collider radius **15 -> 11**; the sprite and the canopy shade keep the
  size they have today via a new `obstacle_decor.render_radius` map
  (`{"tree": 15}`) that `_build_obstacle_decor` / `_build_tree_shadows` read in
  place of `o.radius`. `is_walkable` / `resolve_movement` keep using the real
  (smaller) `o.radius`. The render-only `SPRITE_ANCHOR_DROP` stays keyed to the
  collider (sub-pixel effect).
- Tree count boost is **global, +25%** (`_TREE_DENSITY_BOOST = 0.25`), applied as
  a top-up pass after the main loop: `round(0.25 * total_trees)` extra trees,
  each seeded near a randomly chosen existing tree (drawn across the whole world)
  and placed inside that tree's room, clear of doorway slabs + special-room
  centre discs. New trees land in existing groves -> denser forest, no new maze
  walls.
- Tree spacing is tightened but only tree-to-tree: separation `radius + 22`
  (centre distance ~44 px) for a tree against another tree, `radius + 46`
  everywhere else. The kind is picked before the spacing test so the gap can be
  chosen per pair.
- Bushes stay **sparse**: four entries `bush_a..d` -> `deco_bush_1..4`,
  `placement:"room_interior"`, `collision:false`, `scale ~0.8`, `per_room:[0,1]`
  each, and **no `min_gap`** so they keep the full 40 px separation and never
  bunch.
- New optional `decorations` field **`min_gap`**: `_build_decor_scatter` uses
  `max(gap_a, gap_b)` between a candidate and each already-placed prop (the gap
  is stored in the placed tuple), default 40. Small flora gets a small gap so a
  handful fills roughly one tile:
  - `mushroom` (`deco_ground_pumpkin_2`) `min_gap 14`, `per_room [0,4]`
  - `mushroom_b` (new, `deco_ground_pumpkin_1`, previously unused) `min_gap 14`,
    `per_room [0,3]`
  - `flower_a` / `flower_b` `min_gap 16`, `per_room [0,4]`
  - `sprout_a` / `sprout_b` / `twig` `min_gap 18`
  - `pebble_small` / `pebble_flat` `min_gap 20`
- `obstacle_decor.rigs["shrub"]` is deleted (unused once shrub is not an
  obstacle). `deco_bush_*` rigs stay -- now consumed by the `decorations` list.

### Implementation steps
- [x] **S1** Retire the `shrub` obstacle. `entities/obstacle.py` -- drop
  `KINDS["shrub"]`, rewrote the module docstring. `world/procedural.py`
  `_scatter_obstacles` -- keeps the 4-way weighted pick, still materialises the
  `shrub` slot (and its `variant` draw), then returns
  `[o for o in out if o.kind != "shrub"]`. `test_obstacles` -- the shrub test
  became `test_every_obstacle_kind_blocks_projectiles`.
- [x] **S2** Bushes as sparse decor. `data/terrain.json` -- `bush_a..d` ->
  `deco_bush_1..4`, `scale 0.75`, `per_room:[0,1]` each, no `min_gap`;
  `obstacle_decor.rigs["shrub"]` removed. `test_tree_kind_maps_to_tree_rigs`
  now asserts `"shrub" not in rigs`; `test_obstacle_decor_covers_every_obstacle_
  kind` already enforces the mapping matches `KINDS`.
- [x] **S3** `min_gap` in `_build_decor_scatter`: a `gaps` list runs parallel to
  `placed` (kept out of the instance tuple -- `_blit_one_decor` unpacks 6), and
  separation between a candidate and each placed prop is `max(my_gap, that_gap)`,
  default 40. Wired: `mushroom`/`mushroom_b` (new, `deco_ground_pumpkin_1`) 14,
  `flower_a/b` 16, `sprout_a/b`/`twig` 18, `pebble_*` 20.
- [x] **S4** `KINDS["tree"]` radius `15 -> 11`; `obstacle_decor.render_radius =
  {"tree": 15}`; `_build_obstacle_decor` + `_build_tree_shadows` take
  `draw_r = render_radius.get(kind, o.radius)` for the sprite scale, anchor, and
  shade radius. Tree skin widths (114/122/167/225) and shade radius (28) are
  unchanged from radius 15.
- [x] **S5** `_TREE_DENSITY_BOOST = 0.25` + `_topup_trees(...)` in
  `world/procedural.py`, called after the variant pass: `round(0.25 * tree_count)`
  extra trees, each offset `_TREE_THICKET_MIN..MAX` (36-96 px) from a uniformly
  chosen existing tree, kept on that tree's room cells and clear of doorways /
  special-room centre discs. Measured 1.248x over 30 seeds; minerals unchanged.
- [x] **S6** Kind-aware placement gap: `_TREE_TREE_GAP = 22` between two trees,
  `_OBSTACLE_GAP = 46` for every other pairing, in both the main loop (kind is
  now drawn first) and `_topup_trees`. Tree-tree nearest-neighbour min drops to
  ~36 px (was 76). Trading byte-identical mineral *positions* held S1-S5; S6's
  hoisted kind draw shifts the main-loop stream, so rock/pillar coordinates move
  for a seed (their count, size, and behaviour are unchanged).
- [x] **S7** `tests/test_obstacle_families.py` (11) + `test_terrain`
  `test_min_gap_lets_small_flora_cluster_but_not_bushes`. **Suite 451 -> 462.**

### Implemented -- 2026-08-28

Verified on seed 48 room 5: eight trees, the top-up packed into a tight grove
with overlapping canopies while the trunk rings stay small; bushes / mushrooms /
pumpkins scatter as non-colliding decor with mushrooms visibly bunching; rocks
untouched; every obstacle base sits on a walkable floor cell.


## Projectile FX — animated sprites, modular per-family draw (2026-08-28)

**Goal.** Replace the flat-circle draw of the Ember Ring's orbiters with an
animated, travel-facing flame sprite (`assets/effects/flame-loop/Spritesheet.png`,
16 frames of 47x75, the flame points *south*). Do it inside a **modular
projectile-rendering structure** so the next animated projectile (bolts, chain
lightning, ...) is a new small file, not another branch piled into
`rendering.py` — consistent with the `game/states/playing/` sub-system split
(`journals/playing_state_refactor.md`).

### Structure

New `game/states/playing/projectiles/` package:

| file | holds |
|---|---|
| `__init__.py` | `@style(name)` registry, `draw_projectile(surface, cam, proj, ctx, *, default)` dispatch, `classify(proj, default)` |
| `simple.py` | `style("bolt")` — plain circle; `style("arrow")` — rotated hostile sprite. The current defaults, moved verbatim. |
| `cone.py` | `style("cone")` — the reaping sector. `draw_cone` moves here; `rendering.py` re-imports it so `PlayingState._draw_cone` (a `test_depth_sort` entry point) still resolves. |
| `orbit.py` | `style("orbit")` — the animated flame (this change). |

`WorldRenderer.player_projectiles` / `hostile_projectiles` stay as the two
ordered, test-patchable entry points, but their bodies collapse to
`for p in pool: draw_projectile(surface, self.ps.camera, p, self._projctx,
default="bolt" | "arrow")`. Each style fn is `draw(surface, cam, proj, ctx) ->
None`; `ctx` is a tiny holder of `assets` + `now` (`ps.stats["time"]`).

**Dispatch by the signals that already exist** — `classify` reads
`cone_half_angle > 0` -> `"cone"`, `orbit_speed != 0 and anchor is not None` ->
`"orbit"`, else `default`. No `entities/projectile.py` or `combat/weapons.py`
change yet; an explicit `Projectile.style` field is parked for when a weapon
needs a look unrelated to its mechanics.

### Assets

* **`Assets.frame_rotated(rig, anim, index, degrees, *, size=None, tint=None)`** —
  animated sibling of `rotated()`: slice the strip frame, then bucket-rotate at
  the existing 8-deg `ROTATION_BUCKET_DEG` with a new cache dict keyed
  `(rig, anim, index, size, tint, bucket)`; `None` when the sheet is missing.
* **`ember` rig in `data/sprites.json`** —
  `{"frame":[47,75], "content":[4,2,34,73], "scale":[16,34], "anchor":[8,17],
    "anims":{"loop":{"file":"effects/flame-loop/Spritesheet.png","frames":16,
    "fps":18,"loop":true}}}`. `content` is the union of every frame's
  non-transparent bbox (measured: x 5-37, y 3-74) — trims the wide side margins
  so the rotation pivot sits near the flame. `scale`/`anchor`/`fps` are starting
  values, tune by screenshot.

### Rotation math

Sprite default heading = south = screen 90 deg. An orbiter's travel (tangent)
heading is `degrees(orbit_angle) + 90` for `orbit_speed > 0`. `rotated()`-style
calls take a screen-CW heading, so the value passed to `frame_rotated` is
`degrees(orbit_angle)` (`+ 180` if a blessing ever makes `orbit_speed < 0`).
Frame index from the run clock: `int(now * 18) % 16` — a phase-locked ring reads
as intentional; add `+ orbit_angle * k` later for per-ember shimmer (still no
per-projectile state). Blit centred on `p.pos`; circle fallback preserved when
`frame_rotated` returns `None` (sprites are an optional layer).

### TODO (EP = ember / projectiles)

- [x] **EP1 — modular scaffold.** `game/states/playing/projectiles/` package:
  `__init__.py` (`@style` registry, `ProjCtx(assets, now, zoom)`,
  `classify(proj, default)`, `draw_projectile()` — unknown style falls back to
  `default`), `simple.py` (`bolt` disc / `arrow` rotated sprite, verbatim),
  `cone.py` (`draw_cone` + the lazy `_get_gfxdraw`, moved verbatim; `rendering.py`
  re-imports `draw_cone` so `PlayingState._draw_cone` still resolves).
  `WorldRenderer.player_projectiles` / `hostile_projectiles` are now thin loops
  over `draw_projectile(..., default="bolt"|"arrow")`. `classify` already routes
  orbiters to `"orbit"`, which falls back to `bolt` until EP3. **Done 2026-08-28**
  — suite **578 green** (`ConeWeaponVisualTests` + `test_render_pipeline_order`
  pass); classify spy confirms Kestrel→`bolt`, Aegis→`cone`+`arrow`; fixed-seed
  A/B identical. `rendering.py` 420→367.
- [x] **EP2 — `assets.frame_rotated()`.** `Assets.frame_rotated(rig, anim,
  index, degrees, *, size=None, tint=None)` — `rotated()` for a strip rig:
  snaps `degrees` to `ROTATION_BUCKET_DEG` (8), optionally BLEND_RGBA_ADD-tints,
  `pygame.transform.rotate(base, -bucket)`, caches in the shared `self._rot`
  under a `("<frot>", rig, anim, index, size, tint, bucket)` key (no clash with
  `rotated()`'s 4-tuple). `None` when the rig / anim / sheet is absent. `index`
  is the caller's responsibility to normalise. **Done 2026-08-28** — `test_assets`
  +4 (surface + bucket-share + per-frame distinct + tint distinct/cached +
  missing rig/anim None + 0-bucket keeps size, oblique grows it). Suite **582
  green**; pure addition — nothing calls it until EP3.
- [x] **EP3 — the flame.** `ember` rig in `data/sprites.json`
  (`effects/flame-loop/Spritesheet.png`, 16x47x75, `content [4,2,34,73]`,
  `scale [16,34]`, `anims.loop fps 18`). New `game/states/playing/projectiles/
  orbit.py` `@style("orbit")`: `size = scale_for*zoom`, `idx = int(now *
  fps) % frames` (shared run clock -> phase-locked ring), `heading =
  degrees(orbit_angle) + (0 if orbit_speed>0 else 180)`, then
  `frame_rotated("ember","loop", idx, heading, size)` blitted centred on
  `p.pos`; circle fallback when the rig is absent. Registered in
  `projectiles/__init__` (`classify` already routed orbiters here).
  **Done 2026-08-28** — suite **582 green**; cardinal-angle render (embers at
  0/90/180/270 deg) confirms each flame's axis follows the travel tangent;
  `scale`/`fps` looked right first try, no JSON tuning needed. Tip currently
  *leads* travel (wisps forward); a `+180` flip makes the bright base lead if
  wanted.
- [x] **EP4 — tests + housekeeping.** New `tests/rendering/test_projectiles.py`
  (5): the registry has `bolt`/`arrow`/`cone`/`orbit`; `classify` routes
  cone-angle/orbit-speed/plain; the `orbit` style calls
  `frame_rotated("ember","loop",...)`, falls back to `pygame.draw.circle`
  when it returns `None`, and its frame index tracks `ctx.now * fps % frames`.
  **Renamed the effect packs to the repo convention** (lowercase,
  underscores): `assets/effects/flame-loop/` -> `flame_loop/`, and in all
  four new dirs (`fire`, `fire_aura`, `flame`, `flame_loop`)
  `Spritesheet.png` -> `spritesheet.png`, `Sprites/` -> `sprites/`,
  `Preview.gif` -> `preview.gif`, `.DS_Store` deleted. `data/sprites.json`
  `ember` file path updated. `.gitignore` — `assets/effects/*/preview.gif`
  and `assets/effects/*/sprites/` (only the `spritesheet.png`s ship).
  **Done 2026-08-28** — suite **587 green**; `git add -n` under `effects/`
  lists only the four `spritesheet.png` files.

**Parked:** ~~explicit `Projectile.style` field~~ (done at WA4 -- see below);
animated `bolt` / `chain` styles; `explosion_*.png` for `TransientFx.explosion`;
`fire_aura` sheet for the burn-status ring.


## Weapon / summon animations -- Spirit Wolf, modular per-kind draw (2026-08-28)

**Goal.** Animate the Spirit Wolf summon with the `spectral/wolf-spectral.png`
sheet, and do it inside a modular summon-draw package (the `projectiles/`
pattern), so the next animated summon / weapon effect is a new small file. Only
the anims the wolf actually needs -- **run**, **bite**, plus **idle** in the rig
now for a later "benched wolf" milestone.

### The sheet (analysed, no split needed)

`assets/characters/summons/spectral/wolf-spectral.png` -- **240 x 912**, a
**5-col x 19-row grid of 48 x 48 frames** (not a strip). `wolf-guide.png` is the
legend; rows are directional anims:

| row | anim | f | row | anim | f |
|--|--|--|--|--|--|
| 0-3  | WALK d/l/r/u | 4 | 12-15 | BITE d/l/r/u | 5 |
| 4-7  | RUN  d/l/r/u | 4 | 16-17 | HOWL l/r     | 5 |
| 8-11 | EAT  d/l/r/u | 5 | 18    | SLEEP down   | 4 |

The wolf blob sits ~x[11,38] y[11,36] inside each 48 cell. There is **no idle
row** -- use SLEEP (row 18) as the resting/benched idle. 17 `wolf-colorways/`
and 17 `wolfshadow-colorways/` recolours exist (same layout) -- parked.

The loader is horizontal-strip only (`_build_frames` slices `rect = (i*fw, 0,
fw, fh)`). Rather than split 240x912 into ~10 strips per colourway, add a
one-line **`row`** offset -- see WA2. Splitting stays the fallback if that turns
messy.

### Structure

New `game/states/playing/summons/` (mirrors `projectiles/`):

| file | holds |
|--|--|
| `__init__.py` | `@summon_style(kind)` registry, `draw_summon(surface, sx, sy, s, ctx, *, default)` |
| `totem.py` | `@summon_style("totem")` -- the current rounded rect, verbatim |
| `wolf.py` | `@summon_style("wolf")` -- the wolf rig; circle+dot fallback (today's draw) |

`WorldRenderer.one_summon` becomes a thin `draw_summon(...)` call.
`ProjCtx(assets, now, zoom)` is hoisted to `game/states/playing/drawctx.py`
`DrawCtx` and shared by both packages.

### Wolf rig (`data/sprites.json`)

```jsonc
"spirit_wolf": {
  "frame": [48, 48], "content": [10, 10, 28, 27],   // content measured, tune
  "scale": [22, 20], "anchor": [11, 16], "grid": [5, 19],
  "anims": {
    "run_left":   {"file": "characters/summons/spectral/wolf-spectral.png", "frames": 4, "fps": 10, "loop": true,  "row": 5},
    "run_right":  {"file": "...same...", "frames": 4, "fps": 10, "loop": true,  "row": 6},
    "bite_left":  {"file": "...", "frames": 5, "fps": 16, "loop": false, "row": 13},
    "bite_right": {"file": "...", "frames": 5, "fps": 16, "loop": false, "row": 14},
    "idle":       {"file": "...", "frames": 4, "fps": 4,  "loop": true,  "row": 18}
  }
}
```

**Left/right only** -- matches every other entity in the game; the sheet's
down/up rows (4-directional) are a parked upgrade. No `flip` -- the L/R rows are
used directly.

### Wolf animation state

`entities/summon.py`: `__slots__` += `anim`, `_bite_t`, `_side`.
* At spawn, if `kind == "wolf"`, build `Animator("spirit_wolf")` (assets reach it
  via the summon ctx -- `_update_summons` gains `assets=self.game.assets`).
* `update()` sets `self._bite_t = 0.25` on each bite and ticks it down; tracks
  `_side` from `vel.x` (keeps the last non-zero).
* `_anim_name()`: `bite_{side}` while `_bite_t > 0`, else `run_{side}` (moving or
  poised in range), `idle` reserved for the future benched state.
* `_update_summons` calls `s.anim.play(s._anim_name()); s.anim.update(dt)`.
* `summons/wolf.py` blits `s.anim.frame(size=scale*zoom)` centred (+ the
  `SPRITE_ANCHOR_DROP` seat), circle+dot fallback when the rig/sheet is absent.

### TODO (WA = weapon / summon animation)

- [x] **WA1 -- modular summon draw.** New `game/states/playing/summons/`
  package: `__init__.py` (`@summon_style(kind)` registry, `draw_summon(
  surface, sx, sy, s, ctx, *, default="disc")`, a `disc` fallback style),
  `totem.py` (rounded rect + core, verbatim), `wolf.py` (colour disc + core --
  today's `else` branch; WA4 swaps in the rig). `WorldRenderer.one_summon` is
  now `draw_summon(surface, sx, sy, s, self._draw_ctx(), default="disc")`.
  `ProjCtx` hoisted to `game/states/playing/drawctx.py` `DrawCtx(assets, now,
  zoom)`; `projectiles/__init__` re-exports it (`ProjCtx = DrawCtx` alias kept)
  and `rendering._proj_ctx` -> `_draw_ctx`, shared by both packages.
  **Done 2026-08-28** -- suite **592 green**; `one_summon` over a totem + wolf
  makes the same 1 rect / 3 circle calls as before; fixed-seed A/B identical.
- [x] **WA2 -- grid rows in the loader.** `_build_frames` computes
  `row_y = int(spec.get("row", 0)) * fh` and slices `rect = (i*fw, row_y, fw,
  fh)` -- omit `row` -> row 0, the plain horizontal strip, byte-identical to
  before. `test_assets`: `test_row_offset_slices_the_named_grid_strip` (a
  synthetic 3x2 sheet seeded straight into `_sheets`, red row / green row --
  `row: 1` picks the green strip, default picks red);
  `test_strip_width_matches_declared_frame_count` gained a `grid: [cols, rows]`
  branch (grid sheet is `cols*fw x rows*fh`, every anim's `frames <= cols` and
  `row < rows`) so WA3's wolf rig won't trip it. **Done 2026-08-28** -- suite
  **593 green**; every existing strip rig slices unchanged.
- [x] **WA3 -- the wolf rig.** `spirit_wolf` in `data/sprites.json`:
  `frame [48,48]`, `grid [5,19]`, `content [7,10,35,23]` (measured union of
  every used frame's non-transparent bbox -- x[8,40] y[11,32]), `scale
  [32,21]`, `anchor [16,16]` (placeholders, WA4 tunes). Anims: `run_left`
  r5, `run_right` r6 (4f, fps 10, loop), `bite_left` r13, `bite_right` r14
  (5f, fps 16, one-shot), `idle` r18 (SLEEP, 4f, fps 4 -- reserved for the
  future benched state). All point at `characters/summons/spectral/
  wolf-spectral.png` unchanged. **Done 2026-08-28** -- suite **593 green**
  (`test_files_exist` + the WA2 grid branch of
  `test_strip_width_matches_declared_frame_count` cover it); contact-sheet
  render confirms all 5 anims slice with no clipping (run trot+leap, bite
  lunge+snap, idle curl), L vs R rows distinct.
- [x] **WA4 -- wolf animation state.** `entities/summon.py`: `__slots__` +=
  `anim` / `_bite_t` / `_side`; `reset(kind="wolf")` builds
  `Animator(get_assets(), "spirit_wolf", start="run_right")` (same
  `get_assets()` singleton `Enemy` uses -- no ctx plumbing). `update()`
  restructured so the movement (`_chase`) and attack (`_maybe_attack`) run,
  then the animator always ticks (`play(self._anim_name()); update(dt)`).
  `_anim_name()` -> `bite_{side}` while `_bite_t > 0` (set to `_BITE_ANIM_S =
  0.32` on each bite), else `run_{side}`; `_side` tracks `vel.x` while
  chasing and the bite direction at the snap. `idle` reserved. Chase math is
  byte-identical to before (targetless wolf still holds position).
  `summons/wolf.py` blits `s.anim.frame(size = scale_for*zoom)` at
  `(sx - ax*z, sy - ay*z)`, circle+dot fallback when the rig is absent -- no
  `_update_summons` change needed.
  **Bite hitbox no longer renders as a big disc.** Retired the parked
  "explicit `Projectile.style`" item: `Projectile` `__slots__` += `style`
  (`reset(style="")`), `projectiles.classify` returns `proj.style` when set,
  new `projectiles/melee.py` `@style("melee")` draws nothing; the wolf bite
  `spawn_projectile(..., style="melee")`. **Done 2026-08-28** -- suite **593
  green** (`test_projectiles` registry set += `melee`); controlled renders
  confirm the wolf faces its target both ways, bites on contact, and the
  bite-disc is gone. `scale [32,21]` / `anchor [16,16]` kept -- read fine,
  nudge to ~`[36,24]` later if it wants more presence next to big enemies.
- [ ] **WA5 -- tests + housekeeping.** `tests/rendering/test_summons.py`
  (registry + classify + wolf sprite-vs-fallback + `bite_*` shows for ~0.25 s
  after a bite + run direction follows `vel.x`). `.gitignore` `wolf-guide.png`
  and the unused `*-colorways/` dirs (or keep -- decide at WA5). `README` Assets
  note if warranted. Journal tick.

**Parked:** 4-directional wolf (rows 4/7/12/15); EAT / HOWL anims; the 34
colourway recolours (blessing-tinted / per-hero wolves); `wolfshadow` as a
ground shadow; a totem sprite rig; other weapon FX (chain-lightning arc).


## Soul Scythe -- reaping slash sprite over the (dimmed) cone (2026-08-28)

**Goal.** Layer an animated purple slash on the Soul Scythe's reaping arc, **on
top of** the existing translucent damage cone (kept, not replaced), with the
cone ~35% more transparent so the sprite carries the read.

### The sheet

`assets/effects/weapons/circle_cuts.png` -- **640 x 576, a 10-col x 9-row grid
of 64 x 64 frames**. Each **row is a colour** (row 0 gold, **row 1 purple**,
2 cyan, 3 green, ...); each row is one left-to-right slash: cols 0-5 the crescent
forms + swings, cols 6-9 it dissipates. Soul Scythe uses **row 1** (purple,
matches its `color [200,120,255]`). Row-1 content union: x[6,57] y[10,56] ->
`content [5, 9, 53, 48]`. The crescent is a "C" opening **right** -> default
heading = +x, rotate to `atan2(cone_dir.y, cone_dir.x)`.

### TODO (SS = Soul Scythe)

- [x] **SS1 -- `soul_slash` rig.** `data/sprites.json`: `frame [64,64]`,
  `grid [10,9]`, `content [5,9,53,48]` (row-1 union), `scale [72,64]`,
  `anchor [36,32]` (placeholders -- SS2's cone fn blits by centre + a forward
  offset, doesn't read anchor), one anim `loop` -> `{file:
  "effects/weapons/circle_cuts.png", frames: 6, fps: 40, loop: true, row: 1}`
  (cols 0-5, the forming crescent; ~0.15 s/cycle ~= `projectile_lifetime
  0.14`). **Done 2026-08-28** -- suite **593 green** (`test_files_exist` + the
  WA2 grid branch cover it); slices to 6 frames of `(53,48)`, avg opaque
  colour `(215,110,235)` confirms row 1 is purple, crescent opens right.
- [x] **SS2 -- draw both in `projectiles/cone.py`.** Cone alphas named
  `_FILL_A = 46` / `_EDGE_A = 137` (was 70 / 210 -- x0.65, 35% more
  transparent) and used in `draw_cone` (gfxdraw + the pygbag polygon
  fallback). The `@style("cone")` fn now: `draw_cone(...)` for the dimmed
  damage sector, then -- when the `soul_slash` rig is present --
  `frame_rotated("soul_slash", "loop", int(now*fps)%frames,
  degrees(atan2(cone_dir.y, cone_dir.x)), size=scale_for*zoom)` blitted
  centred at `apex + heading_unit * (radius * _SLASH_FWD 0.40 * zoom)`;
  rig absent -> sector only. Tuned by screenshot: `scale [72,64] -> [84,74]`,
  `_SLASH_FWD 0.45 -> 0.40`. **Done 2026-08-28** -- suite **593 green**
  (`ConeWeaponVisualTests` still fills inside the arc at the lower alpha);
  Aegis render shows the purple crescent carving through the cone toward the
  target, sector a faint footprint behind it.
- [x] **SS3 -- tests + journal.** `tests/rendering/test_projectiles.py`
  `ConeSlashTests` (4): `_FILL_A` / `_EDGE_A` == `round(70|210 * 0.65)` (46 /
  136 -- pinned the 35%); `cone` calls `draw_cone` **and** requests
  `frame_rotated("soul_slash", "loop", ...)` with a heading that follows
  `cone_dir`; with `scale_for("soul_slash")` stubbed to `None` it draws the
  sector only and never touches `frame_rotated`; the slash frame index tracks
  `int(now*fps) % frames`. `ConeWeaponVisualTests` (in `test_depth_sort`)
  still green at the lower alpha. `_EDGE_A` 137 -> 136 so it matches the
  formula exactly. **Done 2026-08-28** -- suite **597 green**.

**Parked:** the other 8 colour rows (per-hero / blessing-tinted slashes); a
per-projectile animator so the slash always plays 0->5 in lifetime order rather
than off the shared clock.

---

## Cliff foot sits on grass, not sea — LD-7a (2026-08-30)

Cross-ref: `level_design_journal.md` LD-7 (cliffs = lowest terrain layer).

**Goal.** Where a raised room's south cliff drops onto a lower room, the bottom
row of cliff-face tiles must read as sitting *on the ground*: no sea / foam
showing through the cliff foot's transparent scallops, and the lower room's own
north-edge tile directly under the cliff must not autotile as a white foam
shoreline ("the directly south tile looks like a north shore tile"). A cliff
genuinely over open water is unchanged — scalloped foot + lapping `terrain_foam`.

**Water foam is not touched.** The animated shoreline system (`_shore` +
`_cliff_foam` anchor lists, `foam_routines`, the `terrain_foam` sheet, the foam
draw pass) is unchanged. What changes is which cliff *feet* are classified as
"over sea": a foot with lower-room floor directly beneath it stops drawing the
scalloped `bottom` tile and stops seeding a `_cliff_foam` point — it draws the
plain `body` tile like any grounded foot. Feet over actual open water keep
everything.

### What changed — `world/map.py`, render + bake only

1. **`_cliff_underlay`** — a new list of `(rect, tile)`, one lower-room
   `interior` grass tile at each cliff-face **foot cell** that has a room floor
   **directly south of it** (`south_room()` centre-probes the cell one row
   below the drawn foot). "Below" here means *same x/y, painted first*: the
   underlay is drawn before the cliff faces, so the cliff sits on top of it and
   its transparent foot shows grass. It never fills a cell that has nothing
   else drawn on it — no gap filling (a real void gap between the cliff and the
   room keeps its shoreline).

2. **`_cliff_capped`** — a set of `(room_id, col, row)` ground-room edge cells
   with a cliff band **flush overhead** (a `px`-tall strip at the cell's north
   edge intersects the raised room's `face_h`-tall band rect for that column).
   `paint_room` paints those cells with the north side forced closed
   (`_mask_slot(shape | {(col, row-1)}, ...)` → `interior`, not an `edge_n` /
   `corner` shoreline tile) and seeds **no** `_shore` anchor for them. Together
   with the underlay this reads as the lower room extending one tile up under
   the cliff.

3. **`paint_cliff`** — the `near_ground_k` / `_cliff_fill` gap-fill from the
   first LD-7 pass (which poured grass into a 1–2 tile void gap) is **removed**.
   The per-column branch now computes `lower = south_room(col, row + draw_h)`;
   `landed = grounded or lower is not None`. `landed` → plain `body` foot, no
   `_cliff_foam`. `lower is not None` → append the `_cliff_underlay` tile and a
   `_cliff_shadow` anchor at the foot cell (LD-6's shadow anchor moved up one
   row, from the room tile to the cliff-foot cell).

4. **Draw order (`_draw_tiled`)** — the LD-7a exception to "cliffs first":
   `water → foam → void decor → _cliff_underlay → _cliff_shadow → _cliff_surfs
   → room floors (bottom floor up) → _stair_surfs → _ramp_surfs → corridors`.
   The underlay and the shadow are the only terrain drawn before the cliff
   faces; the shadow, sitting between the underlay and the cliffs, reads as a
   tight contact shadow at the cliff base rather than a blob on the open field.

### Verified

- `tests/world/test_verticality.py`: `test_cliff_foot_underlay_sits_at_the_cliff_cell_over_lower_ground`
  (underlay tile is opaque grass, a lower room is directly south of it, the
  cell carries a shadow anchor); `test_cliff_foot_foams_over_void_and_grounds_over_a_tile`
  reworked around the `lower` / `grounded` split; `test_cliff_foot_shadow_does_not_suppress_ground_shoreline_foam`
  skips `_cliff_capped` cells; `test_shadow_only_where_a_cliff_foot_lands_on_a_lower_room`
  probes one tile south of the anchor; `test_cliff_faces_paint_below_rooms_and_ramp_units_above`
  now also asserts the underlay blits before the first cliff face.
- Full suite **714 green**. Generation / `WorldLayout` untouched (pure render +
  bake); flat-world baseline unaffected (`_cliff_underlay` / `_cliff_capped`
  stay empty with no raised rooms).
- Screenshots: seeds 2 / 10 (flush cliff-on-room) show the cliff foot on a thin
  grass strip with the lower room's grass continuous under it, no foam band;
  the water-facing columns of the same wall keep their scalloped foot + foam.

### Known gap

Where the cliff band ends a full tile *above* the lower room (a real void gap,
e.g. seed 5), the gap is left as open water per the "do not fill empty spaces"
rule — only a flush cliff is capped.

---

## Thunder Orb -- layered lightning FX on the orb projectile -- ✅ DONE (2026-08-30)

**Goal.** Give the Thunder Orb projectile a real look: two stacked, looping
animations centred on the orb -- an amber energy **aura** ring behind and a grey
**lightning ball** in front -- over (not replacing) the existing orb disc.
User request: "for the first sheet [`thunder_ball`] use row 5 (0-indexed), for
the aura sheet [`thunder_aura`] use row 4; align both on top of the orb entity
for now."

### The sheets (measured)

`assets/effects/weapons/` -- both **576 px tall, a 64 x 64 grid**, row = colour
variant, column = animation frame (bolt strikes in -> ring forms + crackles ->
breaks apart + fades):

| sheet | size | grid | row used | frames in that row |
|---|---|---|---|---|
| `thunder_ball.png` | 1472 x 576 | **23 col x 9 row** | **row 5** (grey/white) | 23 -- a full strike->ball->dissipate cycle, ends near-empty |
| `thunder_aura.png` | 768 x 576 | **12 col x 9 row** | **row 4** (amber) | 12 -- a spiky ring swells from a dot then expands + fades |

Frames are roughly centred in their 64 px cells, so "align on top of the orb" =
blit the scaled frame `get_rect(center=(sx, sy))`, no `content` crop and no
rotation (unlike `ember` / `soul_slash`, these don't face travel).

### What the engine already gives us (no new `assets.py` code)

* Grid-row slicing: `_build_frames` already reads `frame:[fw,fh]` from the rig
  and `row` from the anim spec (`assets.py:113-118`), same path `soul_slash`
  uses.
* `Assets.frame() / frame_count() / fps() / scale_for()` -- the `orbit` style's
  toolkit.
* `Projectile.style` field + `classify()` honours an explicit `proj.style`
  (`projectiles/__init__.py`); `_spawn_projectile(**kw)` forwards everything to
  `proj.reset()`.
* `DrawCtx(assets, now, zoom)` passed to every style fn.

### Changes

1. **`data/sprites.json`** -- two rigs:

   ```json
   "thunder_ball": {
     "frame": [64, 64], "grid": [23, 9], "anchor": [32, 32], "scale": [40, 40],
     "anims": { "loop": { "file": "effects/weapons/thunder_ball.png",
                          "row": 5, "frames": 23, "fps": 24, "loop": true } }
   },
   "thunder_aura": {
     "frame": [64, 64], "grid": [12, 9], "anchor": [32, 32], "scale": [48, 48],
     "anims": { "loop": { "file": "effects/weapons/thunder_aura.png",
                          "row": 4, "frames": 12, "fps": 14, "loop": true } }
   }
   ```
   `scale` (world px) and `fps` are starting values -- tune by screenshot. The
   orb's `area` is 9 (~9 px disc), so `40` / `48` make the ball a chunky halo
   around a small bright core. `anchor` unused by the draw (blits by centre);
   kept for consistency.

2. **`game/states/playing/projectiles/thunder.py`** (new) -- `@style("thunder")`:

   ```python
   _ANIM = "loop"
   @style("thunder")
   def thunder(surface, sx, sy, p, ctx) -> None:
       z, a = ctx.zoom, ctx.assets
       pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                          max(2, round(p.radius * z)))          # orb still shows
       for rig in ("thunder_aura", "thunder_ball"):             # aura under, ball over
           n = max(1, a.frame_count(rig, _ANIM))
           idx = int(ctx.now * a.fps(rig, _ANIM)) % n
           sc = a.scale_for(rig) or (48, 48)
           size = (max(1, round(sc[0] * z)), max(1, round(sc[1] * z)))
           spr = a.frame(rig, _ANIM, idx, size=size)
           if spr is not None:
               surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
   ```
   Both anims run off the shared run clock (`ctx.now`), exactly like `orbit` --
   phase-locked, no per-projectile state. `frame()` -> `None` on a missing
   sheet, so the style degrades to just the disc (sprites stay optional).
   Register with `from ... import thunder as _thunder` in
   `projectiles/__init__.py`.

3. **`combat/weapons.py`** `_fire` -- plumb a def-declared render family into the
   straight/chain spawn (general hook, not thunder-specific):

   ```python
   style = str(self.definition.get("style", ""))
   ...
   ctx.spawn_projectile(..., chain_left=chain_left, chain_range=chain_range,
                        style=style)
   ```

4. **`data/weapons.json`** -- `thunder_orb` gains `"style": "thunder"`.

### How it's verified

* `tests/rendering/test_projectiles.py`: `registered()` contains `"thunder"`;
  `classify(FakeProj(style="thunder"), "bolt") == "thunder"`; the style blits
  `frame("thunder_aura","loop",...)` then `frame("thunder_ball","loop",...)`,
  each index `int(now*fps)%frames`, and with both stubbed to `None` it draws
  only `pygame.draw.circle`.
* `tests/rendering/test_terrain.py`-style asset check (or `test_assets`): the
  two rigs slice a non-empty frame 0 and a non-empty last frame at their
  declared `row`; sheet files exist.
* `tests/combat/test_weapons_special.py`: a `thunder_orb` fire sets
  `proj.style == "thunder"` on every spawned projectile; other weapons stay
  `style == ""`.
* Full suite green; A/B fixed-seed identical (render-only + one inert data key).
* Screenshot: Thunder Orb in flight -- amber ring pulsing behind a grey
  crackling ball, small yellow core visible through it.

> **Superseded 2026-08-30 (see `journal.md` "Weapon logic / presentation
> split"):** `color` + `style` moved from `data/weapons.json` to
> `data/weapon_visuals.json`; `_fire` now passes `weapon_id` and the spawn shim
> resolves `color` / `style` / `fx`. The Thunder Orb's per-weapon effect
> tuning (`aura_scale` / `ball_scale`) lives in `weapon_visuals.json` `fx` and
> overrides the rig `scale` below.

### TODO (TO = Thunder Orb)

- [x] **TO1 -- rigs.** `thunder_ball` (`row 5`, 23 frames, `grid [23,9]`,
  `scale [40,40]`, `fps 24`) and `thunder_aura` (`row 4`, 12 frames,
  `grid [12,9]`, `scale [48,48]`, `fps 14`) in `data/sprites.json`, both
  `frame [64,64]`. No `content` crop -- frames are already centred and there is
  no rotation. Covered by `test_assets.test_strip_width_matches_declared_frame_count`
  (the grid branch: sheet == `fw*gcols x fh*grows`, `frames <= gcols`,
  `row < grows`) and `test_files_exist`. **Done** -- API slice check: both rigs
  return all frames from the right row, scaled.
- [x] **TO2 -- `style` hook.** `_fire` reads `style =
  str(self.definition.get("style", ""))` once and passes it to every
  straight/chain `spawn_projectile`; `thunder_orb` def gets
  `"style": "thunder"`. `Projectile.style` / `_spawn_projectile(**kw)` /
  `classify()` already carry it. `tests/combat/test_weapons_special.py`
  `ChainTests`: `+test_thunder_orb_requests_the_thunder_render_style`,
  `+test_a_def_without_a_style_leaves_the_projectile_unstyled`. **Done.**
- [x] **TO3 -- `projectiles/thunder.py`.** `@style("thunder")`: orb disc
  (`pygame.draw.circle`, still reads through), then `thunder_aura` frame, then
  `thunder_ball` frame, each `frame(rig, "loop", int(now*fps)%n, size=scale*zoom)`
  blitted `get_rect(center=(sx,sy))`. Shared run clock, no per-projectile
  state. Missing sheet -> that layer skipped, disc still drawn. Registered in
  `projectiles/__init__`. `tests/rendering/test_projectiles.py`:
  `RegistryTests` gains `"thunder"` + `test_an_explicit_style_wins_over_field_inference`;
  new `ThunderOrbTests` (3): asks for both layers aura-before-ball; both frame
  indices follow `now*fps`; disc still drawn when both sheets are `None`.
  **Done.**
- [x] **TO4 -- tune + screenshot.** `scale` / `fps` / order / keep-the-disc all
  looked right on the first in-game shot (same as `ember` / `soul_slash`) -- no
  JSON tuning. In-game filmstrip (Thunder Orb fired at a dummy across its
  flight): spark -> forming ring -> amber aura burst + grey crackling ball ->
  scatter -> fade, reads clearly against grass. Kept the disc (near-invisible
  under the ball, and it is the fallback). Full suite **714 -> 720** green.

**Parked:** per-projectile spawn-time phase offset (needs a `Projectile` field
so each orb's loop starts at 0); the other 8 colour rows; a travel-facing
variant; tinting the disc out entirely once the ball reads on its own; the same
`style` hook for the `cone` / `orbit` / `summon` spawn paths when something
needs it.

---

## Arcane Bolt -- blue dust trail + spinning arcane ring (2026-08-30)

**Goal.** Two looping effects centred on the `arcane_bolt` projectile, over its
disc: `arcane_circle.png` **row 2** (blue, 10 frames) as a spinning ring, and
`dust_2.png` (white, 10 frames) recoloured blue as a trailing puff. Same
mechanism as the Thunder Orb -- `@style` module + rigs + per-weapon `fx`
tuning; **no `combat/weapons.py` change** (`classify()` + `_resolve_visual()`
route `style` / `fx` from `data/weapon_visuals.json`).

### The sheets (measured, 64x64 grid)

| sheet | size | grid | use |
|---|---|---|---|
| `effects/weapons/arcane_circle.png` | 640x576 | 10 col x 9 row | **row 2** (blue) -- spark -> 6-point star -> spinning atom-ring -> fragments -> fade |
| `effects/dust_2.png` | 640x64 | 10 col x 1 row | white puff blooms + scatters + fades; tinted blue per weapon |

### TODO (AB = Arcane Bolt)

- [x] **AB1 -- `tint` on animated frames (`game/assets.py`).** `frames()` /
  `frame()` / `_build_frames()` take `tint=(r,g,b)|None`; applied per frame
  after the `content` crop with `BLEND_RGBA_MULT` (a white pack takes the
  colour -- `frame_rotated`'s additive tint can't). Frame cache key
  `(rig, anim, size, flip)` -> `+ tint`. `test_assets`: a white frame x
  `tint=(0,0,255)` comes back blue, cached, `None` unchanged.
- [x] **AB2 -- rigs in `data/weapon_sprites.json`.** `arcane_circle`
  (`grid [10,9]`, `scale [40,40]`, `anims.loop {row:2, frames:10, fps:18}`) and
  `dust_puff` (`grid [10,1]`, `scale [44,44]`, `anims.loop {frames:10, fps:22}`,
  white). Both `frame [64,64]`, `anchor [32,32]`, no `content`. Covered by the
  `test_assets` grid check + `test_files_exist`.
- [x] **AB3 -- `data/weapon_visuals.json` `arcane_bolt`.** `+ "style": "arcane"`
  and `fx: { circle_scale:[40,40], circle_spin_dps:90, dust_scale:[44,44],
  dust_tint:[90,140,255] }`. `test_weapons_special`:
  `weapon_visual("arcane_bolt").style == "arcane"`.
- [x] **AB4 -- `game/states/playing/projectiles/arcane.py` (new).**
  `@style("arcane")`, pattern of `thunder.py`: base disc; `dust_puff` frame
  centred, `size` from `fx.dust_scale`, `tint=fx.dust_tint`; `arcane_circle`
  frame centred, spun via `frame_rotated(..., now*fx.circle_spin_dps, ...)`
  when set else plain `frame(...)`. Shared `ctx.now` clock; each layer skipped
  if its sheet is missing (disc still drawn). Register in
  `projectiles/__init__`. `test_projectiles`: registry has `"arcane"`;
  `classify(style="arcane")`; both layers requested (dust with `tint`); indices
  track `now*fps`; disc-only fallback.
- [x] **AB5 -- verify + screenshot.** Full suite green; fixed-seed A/B
  identical (render-only + inert data). In-game filmstrip of `arcane_bolt` at a
  dummy. If the burst sheets pop on loop-wrap, fall back to a one-shot muzzle
  puff via the transient-FX system (same data, adds a fire hook, still no
  `weapons.py` change) -- decide from the shot.

**As built (2026-08-30):** all five landed first pass, full suite **720 -> 726** green. `Assets.frames/frame` `tint` = per-frame `BLEND_RGBA_MULT` (cache key `+tint`, JSON list coerced to a tuple). Rigs in `data/weapon_sprites.json`; `arcane_bolt` visual =
`{style:"arcane", fx:{circle_scale:[40,40], circle_spin_dps:90, dust_scale:[44,44], dust_tint:[90,140,255]}}`. `projectiles/arcane.py` = disc + tinted `dust_puff` + spun `arcane_circle` (row 2), shared clock, per-layer missing-sheet fallback. In-game shot: purple dart in a blue dust puff + spinning blue rune ring, no tuning needed. No `combat/weapons.py` change.

### AB6 -- dust trail (transient puffs) -- ✅ DONE (2026-08-30)

The on-bolt dust rides with the projectile; a *trail* means puffs left **at past
positions** that finish their own bloom -> scatter -> fade while the bolt flies
on. A draw-only `@style` can't spawn persistent things, so this is an emitter
driven from `TransientFx.update_projectiles`, mirroring `_death_fx`.

**Structure**
- `data/weapon_sprites.json` -- `dust_puff` gains a `burst` anim (same sheet,
  `loop: false`) so a trail Animator can `finished`.
- `data/weapon_visuals.json` -- `arcane_bolt.fx.trail =
  { rig, tint, scale, spacing, fade }`; on-bolt `dust_scale` dropped 44 -> 30
  (the trail carries the volume now). Rides onto `p.fx` via the existing spawn
  shim -- no new plumbing.
- `entities/projectile.py` -- `trail_shed: float` slot (px since the last puff).
- `game/states/playing/effects.py` -- `update_projectiles` measures per-frame
  travel; `_shed_trail(p, moved)` drops
  `[Animator("burst"), Vector2(pos), size, tint, fade]` into `ps._trail_fx`
  every `spacing` px (soft cap 400); `update_trail_fx(dt)` ticks + culls on
  `Animator.finished`.
- `game/states/playing/state.py` -- `_trail_fx` list (init + cleared with
  `_death_fx`); `update_trail_fx` in both per-frame passes; drawn by
  `renderer.trail_fx` **before** the player projectiles so the bolt sits over
  its own trail.
- `game/states/playing/rendering.py` -- `trail_fx(surface)`: blit each puff's
  `assets.frame(rig, "burst", anim.index, size=size*zoom, tint=tint)`; when
  `fade`, a `.copy()` + `set_alpha(255*(1 - t/total))` (never touches the
  shared frame cache).

**Verified.** `tests/rendering/test_enemy_sprite.py::ProjectileTrailTests` (3):
a `fx.trail` projectile sheds `("dust_puff","burst")` puffs and a plain one
sheds none; puffs cull once the burst finishes; `spacing` sets the count. Full
suite **726 -> 729** green. In-game: a blue dust ribbon lingers behind the bolt
across the field, denser at the head, dissipating toward the hero. No
`combat/weapons.py` change. Tune via `fx.trail` (`spacing` up / `scale` down for
wispier).

---

## Terrain: a cliff face always stands behind a sideways stair

**Rule.** An east/west grass flight (`slots.ramp` `w` / `e`, the wedge tiles) is
a notch cut **into** a cliff, not a hole through it. The stone therefore has to
be drawn behind the flight, and that stone is an ordinary cliff face in every
respect: it takes its `left` / `mid` / `right` / `single` variant from its
neighbours exactly as any other cliff cell does, so a rim reads as one
continuous run straight past the flight instead of stopping either side of it.
This holds whichever way the flight faces.

The wedge art's own corners are transparent -- that is by design, and it is how
the stone behind shows through. Before this, `grid_paint.paint_room_grid` laid
plain grass under the wedge, so those corners showed grass floating in the
middle of a rock wall and the wall appeared to break at every crossing.

**Where it lives.** `world/terrain/grid_paint.py`, the `EWSTAIR` branch: the
terrace the flight drops onto, then `cliff_idx("body", var)` with `var` from
`_run_var`, then the wedge on top.

**The neighbour rule that goes with it.** Which variant a face takes is
decided by the rule below, and a flight counts as *closing* the side it sits
against -- it is a gap cut through the wall, not the end of it -- which is what
lets the run carry through.

---

## Terrain: when a cliff face is `mid`, capped, or a pillar

**Rule.** A cliff face is square-shouldered (`mid`) by default. It only takes a
rounded, part-transparent cap on a side where that side is genuinely **open**,
and it is only the free-standing `single` pillar when it is open on three
sides at once.

A side counts as open when the space beside the face holds nothing at the
wall's own height: the sea, a lake, or a *lower* terrace looking up at it.
Everything at the wall's own level closes the side -- more cliff, a flight cut
through the wall, and (this is the part that used to be missing) **the terrace
grass itself**, where the rim jogs a row so the face's neighbour is plateau top
rather than stone.

    open  -> lower ground, lake, void
    closed -> cliff, flight, ground at this wall's level or above

    both sides closed          -> mid
    open to the west           -> left
    open to the east           -> right
    west + east + the foot     -> single

`single` is tested against the **foot of the wall**, not the face's own south
neighbour: a wall is one to `drop` cells deep, so for a two-deep wall that
neighbour is the wall's own second row and the test would never pass on the
upper cell -- rendering a one-wide two-tall pillar as a cap stacked on a
pillar. `_wall_foot` walks the stack down first, so the whole column reads as
one pillar.

**The tile above a pillar.** A `single` carries exactly one ground cell, and
the way terraces are grown that cell always continues north into the plateau.
Its cap is therefore the three-sided `raised["swe"]` piece (slot 26), never the
fully islanded `nswe` one. Measured across twelve worlds this was already what
the corner rules produced on their own for every pillar that had ground above
it, so forcing it changes nothing today and pins the invariant for later.

**Why it matters.** The previous rule asked only "is the neighbour part of this
same wall", which made same-level grass alongside a face read as the end of the
run. Across twelve worlds that inverted the whole distribution: 613 pillars
against 328 `mid`. Under this rule it is 25 pillars against 774 `mid`, with the
remaining 1,145 caps sitting where a lower terrace really is visible past the
stone.

**Where it lives.** `world/terrain/grid_paint.py` -- `_open_side`,
`_wall_foot`, `_run_var`, and the `_is_pillar` short-circuit at the top of
`_open_sides`.

---

## Terrain: the shadow under a cliff

**Rule.** Every cliff cell casts the `terrain_shadow` blob (`shadow.png`, one
192x192 sprite: a ~1-tile core with a feathered bleed into the ring of cells
around it) centred on itself, drawn **after the ground / lower-floor tile and
before the cliff face** -- ground, shadow, stone. Only the feather shows past
the face, which is what makes the wall read as standing above the terrace it
fronts instead of being painted onto it.

An east/west flight casts one too, because a cliff face stands behind it. A
vertical flight does not -- it is a channel cut through the wall that you walk
down, not stone.

**Compositing.** The blobs are three cells wide but sit one cell apart, so six
of them overlap on every tile of a continuous run. Blitted straight down with
normal alpha they stack into lumpy over-darkened patches; accumulate them on a
scratch `SRCALPHA` surface with `pygame.BLEND_RGBA_MAX` instead and the run
merges into one even strip.

**Where it lives.** `data/terrain.json` `rigs.terrain_shadow`;
`TileSheets.cliff_shadow`; `grid_paint._shade`, called between pass 1 (ground)
and pass 3 (stone) of `paint_room_grid`. The LD-8 band renderer does the same
thing in `world/terrain/render.py` from `GameMap._cliff_shadow`.

---

## Terrain: the two ground fringe blocks, and when each applies

**The sheet has two complete autotile blocks**, same sixteen combinations in
both, different art:

* the **shoreline** block -- white surf. `slots.interior` / `edge_*` /
  `corner_*` (the eight rectangle slots) plus `strip_v` `[3, 12, 21]`,
  `strip_h` `[27, 28, 29]` and `single` `30` for the opposite pairs and the
  3- and 4-sided nubs. All sixteen are authored; earlier code used only the
  eight and fell back to `interior` for the rest, which is why a one-wide spine
  of ground, or a cell pinched between a lake and a cliff, painted as a flat
  square with no fringe.
* the **raised** block -- `slots.raised`, keyed directly by the open sides
  (`""`, `"n"`, ... `"nswe"`). A dark navy rim, no surf.

**Rule.** Which *sides* get a fringe is decided by the tile's own floor alone:
own-floor ground continues, or it does not. Which *block* draws it is decided
by what lies beyond the edge -- **shoreline when any side fronts open sea or a
lake, raised otherwise**. They are not interchangeable: drawing every sea-level
tile from the shoreline block traces white surf along the inland foot of every
cliff, which reads as a beach in the middle of the island.

This holds at every level, so an inland lake on a plateau gets surf and the
plateau's own rim against stone does not.

**Where it lives.** `world/terrain/autotile.py` (`_GROUND_SLOT`, `mask_slot`),
`world/terrain/grid_paint.py` (`_floor_sides`, `_at_water`, the `GROUND` branch
of `paint_room_grid`).

---

## Terrain: `tilemap_7`, merged from `tilemap_flat` + `tilemap_6`

**What it is.** A standard 9x6 / 576x384 sheet assembled from two supplied
sheets that were not in the standard layout: `tilemap_flat` (10x4 -- two 4x4
autotile blocks, green and sand, each with a trailing spacer column) and
`tilemap_6` (4x8 -- stone surfaces, cliff faces and strata).

| standard block | source |
|---|---|
| shoreline, cols 0-3 rows 0-3 | `tilemap_flat` sand block |
| raised, cols 5-8 rows 0-3 | `tilemap_flat` green block |
| cliff body, row 4 | `tilemap_6` row 3 |
| cliff bottom, row 5 | `tilemap_6` row 7 (strata) |

**Why the merge is clean, which had to be checked rather than assumed:** the
shoreline block is *the same 4x4 autotile ordering* as the raised block.
`(3,0)` is `strip_v` top = `nwe`; `(0,3)` is `strip_h`'s west cap = `nsw`;
`(3,3)` is `single` = `nswe`. So any well-formed 4x4 block drops into either
half. Verified slot by slot by measuring which edges of each tile carry a
fringe -- `tilemap_flat`'s green block detects *more* cleanly than
`tilemap_1`'s own raised block.

**The one real gap, and the rule that answers it.** Neither supplied block is a
shoreline block. Transparency in the top band: `tilemap_1` shoreline **55.2%**,
its raised 25.3%, flat green 18.2%, flat sand **15.4%**. The animated foam is
drawn *beneath* the tiles and shows through that gap, so the sand bank would
read as a hard edge with almost no foam.

Rather than fake it, a sheet may now declare `"shoreline": false` in
`terrain.json` `sheet_flags`. `TileSheets.has_shoreline` reads it and
`grid_paint._ground_tile` takes the **raised block for every fringe** on such a
sheet -- the same thing it already does where a tile borders stone. The biome
simply has no beaches, which is the honest reading for a rocky highland and
needs no new art.

Cheap in practice: measured over 16 worlds the shoreline block covers 22% of
sea-level ground but only **1.1% of level 1 and 3.3% of level 2** -- 364 tiles
in ~23,500. Every world has at least one, so it would have been seen, just
rarely.

**Wiring.** `terrain.json` gains `heightmap_floor_sheets`, consulted by
`sheet_for` only when `config.HEIGHTMAP_ROOMS` is on. Editing `floor_sheets`
directly was not an option: it is shared with the LD-8 path, where
`test_verticality` pins an expected grass tone per floor. `tilemap_7` is
assigned to **floor 2 only** -- giving it to both 1 and 2 made adjacent floors
share a tileset, against the standing rule that no two adjacent floors may. The
map is an interim stand-in for the per-island biome palette.

**`rocky_shadow.png`** is a drop-in alternative to `shadow.png`: identical tint
and alpha `(22, 28, 46, 80)`, same 3x3 layout, but a crisper and wider blob --
core exactly 4096 px (a full tile) against 4028, arms 338/235 against 200/184.
Diagonals are 0 in both, so it needs the same corner fill as C24. Unused so
far; a candidate for a per-biome shadow, harder-edged for rock.

**Left over for another sheet:** `tilemap_6` slots 16-19 (a 4x2 short block)
and 20-23 (a second cliff-face row) are unused, and the sand block currently
only fills `tilemap_7`'s dead shoreline slots. A sand-ground sheet with the
alternate rock face is assemblable from what is already in the folder.

---

## Terrain: three ground sheets from the same two sources

`tilemap_6.png` was **renamed to `tilemap_rocky.png`** between the last entry
and this one; `tilemap_7` had been built from it under the old name.

The supplied art carries three distinct *grounds* -- rocky (`tilemap_rocky`
rows 0-3), green and sand (`tilemap_flat`'s two 4x4 blocks). Each is now its
own standard 9x6 sheet, all three sharing `tilemap_rocky`'s faces for the cliff
rows:

| sheet | ground | cliff body / bottom |
|---|---|---|
| `tilemap_6` | rocky | rocky rows 5 / 7 |
| `tilemap_7` | green | rocky rows 3 / 7 |
| `tilemap_8` | sand | rocky rows 3 / 7 |

`tilemap_7` was rebuilt: it previously carried the sand block in its shoreline
slots, which `shoreline: false` then made unreachable -- dead art. Both halves
are green now and the sand has its own sheet.

**The rocky block needed one synthesised row.** A standard raised block is
sixteen combinations; `tilemap_rocky` supplies twelve -- `nw n ne nwe` /
`w '' e we` (twice, an interchangeable middle) / `sw s se swe`, with no row for
the thin `nsw ns nse nswe`. Those are built by compositing: a tile open north
*and* south is the top half of the `n` tile over the bottom half of the `s`
tile, same column. The two share a base texture, so the join at mid-tile does
not show. `tilemap_flat`'s blocks needed none of this -- both are complete
sixteens already.

**Verification, and where it disagreed.** Each assembled raised block was
re-measured against the standard ordering. `tilemap_7` matches on all sixteen.
`tilemap_6` and `tilemap_8` each disagree on two -- sand's right-edge fringe at
`(7,0)` / `(8,0)`, rocky's south fringe at `(6,2)` and the row synthesised from
it. In every case **the same disagreement appears on the raw source art**, so
it is the edge detector's threshold on a subtle fringe rather than a fault in
the merge; confirmed by eye against the rendered sheets.

**Wiring.** `heightmap_floor_sheets` now reads `1 -> tilemap_8` (sand),
`2 -> tilemap_6` (rocky); floor 0 keeps the room-kind palette, which is the only
one with a real surf block. All three floors are on different sheets, satisfying
the rule that no two adjacent floors share a tileset. All three new sheets carry
`shoreline: false`.

`tilemap_7` (green) is now unused by the wiring but stays in the library -- it
is a third distinct ground for the per-island biome pool, which is what will
replace this fixed floor map.

---

## `tilemap_6` rebuilt: rocky top only, borrowed faces, and its own stairs

The first cut of `tilemap_6` took its whole look from `tilemap_rocky` --- the
pale rubble for the ground rows and the same sheet's stratified rock for the
cliffs. Only the rubble was right. `tilemap_rocky` has **no south-fringed
ground row at all**: in that art a rocky surface's south edge is always drawn as
a *face*, chunky columns seen from the side, so the previous build had put a
wall texture flat on the ground for every `sw s se swe` tile, and the cliff rows
never matched the faces every other tileset renders.

The rebuild (`utilities/build_ground_tilemaps.py`, the first of these assembly
scripts to be kept rather than thrown away) uses only the top-down rubble and
borrows everything vertical:

| slots | source |
|---|---|
| `nw n ne nwe` | `tilemap_rocky` r0 |
| `w '' e we` | `tilemap_rocky` r1 |
| `sw s se swe` | r0 **flipped vertically** --- the north rim becomes a south rim |
| `nsw ns nse nswe` | top half of the north row over the bottom half of the south |
| `cliff.body`, `cliff.bottom` | `tilemap_1` |
| ramp wedges | `rocky_temp_stairs.png` |

The vertical flip works because the rubble has no up/down reading of its own;
only the rim is directional, and flipping is exactly what turns it into the
opposite rim. `vflip(nw)` is fringed south and west, which *is* `sw`.

Note that `cliff.top` (32--35) is the **same four slots** as the raised block's
thin row, so it stays rubble rather than coming from `tilemap_1` with the other
cliff slots. That sharing is deliberate in the original sheets: a cliff top is
the ground lip seen from above, so it has to match the ground, not the face.

Re-measured against the standard ordering with a luminance rim test (a raised
block's fringe is a dark rim drawn *in colour*, not cut alpha --- an
alpha-based edge test reads every one of these tiles as unfringed and is
useless here), `tilemap_6` and `tilemap_8` now match all sixteen. `tilemap_1`,
the hand-authored reference, itself misses two on the same test, which is the
threshold on a weak south rim rather than a fault in either sheet.

### The supplied stair art

`rocky_temp_stairs.png` arrives as a 2892x1440 render on a flat white backdrop
with **no alpha channel at all**. It works: the two wedges' silhouettes match
the ones already in `tilemap_1` to within about 2px of a 64px tile (mean error
0.034 and 0.011 of a tile width across sixteen sampled rows), and the aspect is
715x1440, within half a percent of the 1:2 a two-tile-tall wedge needs. It is
plainly a recolour of the existing wedge, rubble where `tilemap_1` has grass,
down to the stone foot at the bottom.

Keying it needed two passes, not one. Eroding the backdrop inward along each
**row** is the obvious move and is wrong on its own twice over: the two wedges
sit side by side, so a row scan run before the shapes are separated bridges the
gap and reads them as one; and the wedge's foot is a row of rock lobes with
backdrop in the notches between them, enclosed left-to-right, which survives a
row scan and comes through the downscale as white specks along the bottom edge.
Splitting on column occupancy first and then eroding from **both** the rows and
the columns clears both. A final guard drops any downscaled cell that averages
to a neutral near-white, since nothing in this rock is one.

The downscale averages **only the opaque source pixels** in each output cell's
footprint, so the white backdrop never bleeds into the silhouette edge; coverage
below 45% leaves the cell clear.

Which wedge is which is asserted, not assumed --- the westward wedge is the one
whose mass leans right across its top quarter --- so a re-render that swaps them
fails loudly instead of silently mirroring every staircase in the game.

**The one open point** is palette: the wedges are a neutral grey (mean RGB
96, 99, 107) against teal-grey cliff faces (92, 136, 137) and pale blue-green
rubble (135, 186, 184). In place they read as loose scree rather than as the
same stone, which makes a climbable ramp instantly distinguishable from a cliff
face --- arguably a readability gain, so they are left as supplied.

### Fixed in passing: the sibling sheets had no ramp wedges

`tilemap_7` and `tilemap_8` were assembled without slots 36/45 and 39/48.
Nothing complained, because a missing ramp is not an error: `grid_paint` blits
those slots unconditionally and an empty slot simply draws nothing. Every
east/west staircase on floors 1 and 2 was therefore rendering as bare cliff with
a walkable but **invisible** flight over it. The green sheet now takes
`tilemap_1`'s grass wedges, the sand sheet the rocky ones --- a bare outcrop of
steps reads better on sand than a tuft of grass.

---

## Importing a hand re-rendered sheet: `utilities/key_sheet.py`

`new_tilemap_6.png` came back as the assembled sheet re-rendered with the stair
wedges recoloured into the teal family --- 2528x1686, flat on white, **no alpha
channel at all**. Restoring the transparency is not a threshold; it took three
distinct passes, each fixing a failure the previous one left behind.

**1. Connectivity, not colour.** A tilesheet is full of enclosed light pixels
--- the cream highlights in the rock, the pale crack fills --- so "near-white is
transparent" punches holes through the middle of tiles. The near-white mask is
flood filled instead, so only ground reachable from outside the art is cleared.
The fill walks row *runs* rather than pixels: a few thousand nodes against four
million, which is what makes a pure-Python fill fast enough that scipy (not
installed here) is not needed.

**2. Seed from every tile seam, not the image border.** A sheet is not one
picture. Its tiles butt against each other, so the notches between the rock
lobes along a tile's south fringe are enclosed by the *neighbouring* tile's art.
Keying from the border alone left **891** opaque white pixels wedged into
exactly those fringes --- slots 19, 24, 28, 33 and the cliff bodies --- against
**zero** in the hand-authored `tilemap_1`. Each tile is its own drawing, so each
tile's own edge counts as an outside. That took it to 3.

**3. Erode the blend ring.** These renders are upscales, so art meets ground
across a few pixels of blend rather than a hard edge: sampled across the
boundary the run reads 243,253,254 -> 232,246,246 -> 227,239,239 -> 203,217,220
-> rock. Those pixels are too dim for the near-white test and too tinted for the
neutrality test, but they are mostly backdrop by weight, and counting them as
art pulled boundary luminance to a maximum of 250 against `tilemap_1`'s 225.
They are taken by growing the *known* backdrop into anything still above 205 ---
which cannot run away into the rock's own cream highlights, because those do not
touch the backdrop --- capped near the upscale factor.

A final guard drops any downscaled cell that averages to a neutral near-white,
for a notch genuinely sealed on all four sides. One pixel of 160,000 survives
everything.

**The downscale averages only the opaque source pixels** under each output cell.
Box filtering the raw image would drag white into every silhouette edge; a cell
under 45% covered stays clear, which reproduces the hard alpha edge the
hand-authored sheets have.

**Verification.** Alpha IoU against the sheet this one re-renders is 0.9916, and
the only slots whose *colour* moved are 36/39/45/48 --- the four ramp wedges,
exactly as described. The raised block matches all sixteen combinations on the
luminance rim test. The wedges now read 121,154,157 and 109,145,148, sitting
between the cliff faces at 94,134,136 and the ground at 137,185,186 instead of
the neutral grey 96,99,107 they were.

`utilities/build_ground_tilemaps.py` now defaults to this import path, so
running it reproduces what is on disk rather than overwriting the re-render with
the older derivation; `--derive` still rebuilds from the source art. It also
hands the keyed wedges to `tilemap_8`, which had been given the grey ones ---
two floors of the same island were rendering staircases in different colours.

---

## `tilemap_8`: same import, plus a face transplant

`new_tilemap_8.png` arrived the same way as the rocky one --- 2528x1686 flat on
white, no alpha --- with the ramp wedges recoloured to sand. It goes through the
same `key_sheet` pipeline, and the pipeline needed one more turn of the screw
for it.

**The neutral guard now cuts at 225, not 238.** Sand is a light colour, so the
blend where art meets backdrop runs through pale yellows rather than dropping
straight to a dark outline, and a downscaled cell straddling a tile seam can
catch a sliver of that blend from *both* neighbours and average out to a light
neutral grey. Five such pixels survived at the old threshold. The right
discriminator was never brightness: this art is teal rock and yellow sand, both
strongly tinted, and `tilemap_1` contains no light neutral pixel at all, so a
cell that averages to one is backdrop however it got there. That took the rocky
sheet to zero and the sand sheet to five pixels of 167,000, at the outermost
ring of the silhouette where they are invisible against any ground.

**The cliff faces are swapped for `tilemap_1`'s.** The render carried
`tilemap_rocky`'s stratified rock in its cliff rows, which is the one part of
that source that never matched the rest of the game --- the same problem that
prompted the `tilemap_6` rebuild. `cliff.body` and `cliff.bottom` now come from
`tilemap_1` verbatim (byte-identical, asserted).

`cliff.top` (32--35) deliberately does **not**: it is the same four slots as the
raised block's thin row, so taking it from `tilemap_1` would put green grass on
the rim of a sand terrace *and* break every thin sand strip at the same time. It
keeps the sheet's own sand, which is what a ground lip seen from above should
be.

**Each floor's staircase now matches its own ground** --- teal rubble wedges on
the rocky summit, sand wedges on the sand terrace. The stopgap that gave
`tilemap_8` the rocky wedges is gone, so `_fill_ramps_on_green` is down to the
green sheet, the only one without a hand re-render.

---

## All three sheets on one stone; and a tidy-up that moved a live asset

`tilemap_7`, the one sheet with no hand re-render, gets the same face transplant
as `tilemap_8`: `cliff.body` and `cliff.bottom` from `tilemap_1`, byte-identical,
with `cliff.top` left on the sheet's own ground for the reason it always is ---
those four slots are also the raised block's thin row.

`tilemap_6`'s faces were taken verbatim too. They already *came* from
`tilemap_1`, but they made the round trip through the re-render's upscale and
back down, which left them about 4/255 off and carrying the same blend
artefacts at their edges that the keying fights everywhere else. Taking them
straight cost nothing and is measurable: the sheet's maximum boundary luminance
dropped from 233.5 to exactly `tilemap_1`'s 225.0. All three sheets now render
literally the same stone.

**Sources moved to `assets/terrain/tiles/extras/`.** The large renders and raw
source sheets are inputs, not shipped art, so the tiles directory now holds only
what the game loads. `build_ground_tilemaps` reads `new_tilemap_6`,
`new_tilemap_8`, `rocky_temp_stairs`, `tilemap_rocky` and `tilemap_flat` from
there.

**`vstairs.png` went with them, and it is not an extra.** It is still live:
`data/terrain.json` names it as `vstair.sheet`, and `world/terrain/cliffs.py`
loads it through `Sheets.vstair_overlay` for the LD-8a rock staircase. That path
fails *soft* --- a missing sheet returns `None` and the caller quietly renders
the biome grass ramp instead --- so nothing crashed and nothing logged; the two
tests that noticed (`test_vstair_overlay_sprite_is_a_real_srcalpha_file` and
`RampTests::test_ramp_units_render_by_style`) were the only signal. It has been
moved back beside the other live tiles.

`vertical_stairs.png` really is unused --- nothing in the codebase or the data
names it --- so it stays in `extras/`.
