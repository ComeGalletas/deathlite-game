# Asset Integration Journal — Death Lite Die

A focused checklist + phase log for wiring real sprites into the game, kept
separate from the main `journal.md`. Same format: **Goal → What changes → How
it's verified → Decisions → Risks**, with a tick-box workflow.

The engine already has the seam for this: every entity is drawn in a `_draw_*`
method with `pygame.draw.*`, and the plan from the start was
`if sprite: blit(sprite) else: draw_primitive`. Nothing in gameplay, state,
combat, or collision is affected — sprites are a cosmetic layer.

---

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
