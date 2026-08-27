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

### Phase A — Asset loader + metadata *(no visible change)*
- [ ] `game/assets.py`: `Assets` singleton via `get_assets()`. `sheet(key)`
      loads a PNG once with `.convert_alpha()`, slices it into frame surfaces
      with `subsurface`, caches. `scaled(key, size)`, `flipped(surf)`,
      `rotated(surf, deg_bucket)` all memoised. Missing file → `None`, logged
      once (never raises — matches `save.py`'s degrade contract).
- [ ] `data/sprites.json`: per-rig `{frame, anchor, face, anims:{name:{file,
      frames, fps, loop}}}`.
- [ ] `game/content.py` or a sibling: load `sprites.json` into `Content`.
- [ ] `game/game.py`: `self.assets = get_assets()` right after
      `set_mode(...)` (so `.convert_alpha()` has a display; headless tests use
      the SDL dummy driver, which still allows it).
- [ ] `tests/test_assets.py`: every strip slices to exactly its declared frame
      count (`frame_w × frames == sheet_w`); `image(None)` and a missing key
      return `None`, no exception; runs under the dummy video driver.
- [ ] `assets/CREDITS.md`: pack name, author, license (confirm CC0 / free-for-
      commercial — spec §15).

**Verify:** `unittest` green; `python main.py` looks byte-identical (nothing
blits a sprite yet).

### Phase B — Aegis sprite (Soldier)
- [ ] `Animator` helper (frames + fps + loop + elapsed → current frame, with a
      one-shot "finished" flag). Owned by `Player`; **reads** state, never
      drives it.
- [ ] `Player`: add `_hurt_t` (set in `take_damage`) and `_attack_t` (set when
      a weapon fires — a hook the state calls). `walk`/`idle` from `_move_dir`,
      `death` from `alive`. Priority `death > hurt > attack > walk > idle`.
- [ ] `game/states/playing_state.py`: fire the `_attack_t` hook from the
      weapon-fire path (`_spawn_projectile`, same spot as `audio.play_shoot`);
      `_draw_player` picks the anim for `character_id == "aegis"`, blits at
      `pos − anchor` flipped by facing, else the current circle.
- [ ] Tune `scale` and `anchor` in `sprites.json` against a windowed run.

**Verify:** windowed — Aegis idles, walks, flips with movement direction, plays
an attack burst when the scythe fires, flashes `hurt` on a hit, plays `death`
on game-over. Kestrel/Nihil unchanged. Invuln tint / low-HP vignette still read.

### Phase C — Basic enemy sprite (Orc)
- [ ] `SpriteState` on `Enemy`, only instantiated for kinds that declare a
      `sprite` rig (chaser). `walk`/`idle` from `vel`, faces the player.
      `Orc_Hurt` (4-frame one-shot) plays on each hit — set a `_hurt_t` in
      `Enemy.take_damage`; priority `death > hurt > walk > idle`. The existing
      white `hit_flash` tint stays off for sprited enemies (the anim replaces it).
- [ ] **Death lifecycle change** (`playing_state.py`): dead sprited enemies
      move to a render-only `self._dying` list for their death-anim duration
      (~0.4 s), then are dropped. XP gem, loot, and `ENEMY_KILLED` still fire
      at the instant of death, exactly as now.
- [ ] `_draw_enemies`: blit the Orc frame for the chaser, primitive for the
      other 12; keep the elite gold ring / shield ring / telegraph ring overlays
      on top of whichever renderer.

**Verify:** windowed — chasers walk, flinch on hit, and play a death animation;
every other enemy type looks exactly as before; kill count, XP drops, on-kill
blessings still work; the headless compressed full-run still reaches
VictoryState.

### Phase D — Arrow projectile *(enemy / boss shots only)*
- [ ] `Assets.rotated(...)`: cache the arrow pre-rotated in ~8° buckets (up to
      ~45 cached surfaces) — rotating per projectile per frame is the perf risk.
- [ ] **Only** the hostile-projectile draw loop in `_draw_projectiles` changes:
      blit the arrow rotated to `atan2(vel.y, vel.x)`, scaled to `radius`,
      tinted with the hostile colour (cached `BLEND_MULT` copy). The player
      projectile loop above it is left untouched.

**Verify:** windowed — enemy / boss shots are arrows pointing along their path;
**every player weapon renders exactly as before** (arcane / frost / thunder
dots, Ember Ring, Soul Scythe glows all unchanged); F1 overlay shows FPS holding
at 60 with a few hundred projectiles live; headless full run still green.

### Phase E — Polish + documentation
- [ ] Optional: tint/scale hook so future work can reuse the Orc sheet for
      `fast`/`swarm`/`tank`/`elite` by colour.
- [ ] `README.md` asset section; a milestone-style entry in `journal.md`; a
      "Asset integration" section in `transcript.md` (key steps + why).
- [ ] `assets_journal.md` (this file): fill in the "How it was verified" and
      final decisions.

**Verify:** full headless playtest per hero + a windowed run; 60 fps under load;
`unittest` green.

---

## Risks / watch-items

- **Anchor & scale are eyeball-tuned.** The 100 px frames have large transparent
  margins; expect a few iterations to get feet-on-ground and size right. Kept in
  JSON so it's a data tweak, not a code change.
- **Rotation cost** for the arrow at high projectile counts — mitigated by the
  angle-bucket cache; will confirm with the F1 timing readout in Phase D.
- **Death lifecycle** is the one real code change to `playing_state.py`; it must
  not delay or drop the death *events* (XP, loot, `ENEMY_KILLED`) — only the
  visual removal is deferred.
- **`.convert_alpha()` needs a display** — the asset manager must be created
  after `set_mode`, and pure-logic tests must not import a module that eagerly
  loads images. Lazy loading handles both.
- **Only 2 humanoid rigs** — most of the roster stays primitive after this
  pass. That is intended; the fallback keeps everything shippable.
- **Facing pop** when an entity's `vel.x` crosses zero — acceptable; can add a
  small dead-zone later if it reads badly.
