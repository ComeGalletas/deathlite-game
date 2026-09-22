# Cluster Bomb bomblet FX — journal

**Legacy ID:** RND-002 · **Systems:** RND, CMB · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## 1. The requirement (owner, 2026-09-12)

- **Objective:** Find explosion effects for the bomblets, different from the
  bomb's current explosion sprite.
- **Details:** Survey the assets folder — the unused folder and the mega pack
  on the root included — then confirm and propose which ones could be used
  and how.
- **Constraint:** Survey and proposal only; no code this pass.

A survey and a proposal. No code this pass.

## 2. Confirmed reading

### What the bomblets look like today

Cluster Bomb's bomblets already play **the same sprite as the main blast**.
`TransientFx.scatter_bomblets` spawns each bomblet as an ordinary fused,
inert projectile; when its `cluster_fuse` ends, `update_projectiles` sends it
through the same `detonate()` as the parent, and `detonate` calls
`burst_visual(pos, bomb.blast_radius)`, which hard-codes
`_BURST_RIG = "explosion"` — the `effects/explosion_2.png` strip. The only
difference is scale: a bomblet's `blast_radius` is the parent's times
`cluster_radius_mult` (0.6), and `_blit_burst` sizes the art to the blast
diameter, so a bomblet is literally a 60%-scale copy of the big explosion.

All three bomblets share one `cluster_fuse` (0.55 s) and one `stop_after`
(`fuse * 0.5`), so they go off **on the same frame**. Three simultaneous
60% copies of the main blast is exactly the readability problem a separate
sprite would solve.

Two adjacent facts found while reading, neither asked for:

* **in flight a bomblet already draws the `bomb` rig, at the parent's size.**
  (An earlier note in this journal said it fell back to the plain `bolt`
  disc, on the grounds that `scatter_bomblets` passes no `visual`. That was
  wrong: `PlayingState._resolve_visual` falls back to
  `weapon_visual(weapon_id)`, and the bomblet carries `weapon_id="bomb"`, so
  it resolves `style: "bomb"` with an empty `fx` — which means the rig's own
  `scale` `[24, 36]`, identical to the parent. Verified by spawning a real
  cluster through `PlayingState`: all three bomblets come out
  `style="bomb"`, `fx={}`.) `anim_for` then returns `spin` while they fly,
  because they have velocity.
* `assets/unused/` is tracked in git (645 files). The Gigapack is **not**
  tracked (0 files) and is not ignored either — it has simply never been
  added.

### What the current sprite is

`effects/explosion_2.png`, a 1920x192 strip: ten 192 px frames, rig
`explosion` in `data/weapon_sprites.json` — content `[40, 18, 112, 142]`,
scale `[112, 140]`, anchor `[56, 75]`, `fireball` 108, one one-shot `burst`
anim at 20 fps (0.5 s). A spark, the fireball swelling over frames 1-6, then
three frames thinning out. Long spikes and a smoke ring; it reads big.

## 3. The survey

### 3a. `assets/unused/effects/` — two siblings of the current sheet

Both are the same pack and the same 192 px grid as `explosion_2.png`, which
means no repacking and no style risk.

| file | frames | union opaque bbox | widest fireball | reads as |
|---|---|---|---|---|
| `explosion_1.png` | **8** | `[63, 60, 64, 64]` | ~64 px | the same star-burst, tighter and rounder, four short spikes, quick fade |
| `explosion_2.png` *(current)* | 10 | `[43, 20, 108, 138]` | 108 px | big star-burst, long spikes, smoke ring |
| `explosion_3.png` | 9 | `[44, 36, 105, 113]` | ~105 px | **ring first** — a white shockwave ring on frame 0, then a darker brown core inside it |

`explosion_1.png` is visibly the small sibling of the current sheet: same
palette, same spike language, a 64 px fireball against 108, and two frames
shorter. `explosion_3.png` is the same *size* class as the current one but a
different read (concussive ring rather than fireball).

### 3b. `assets/Super Pixel Effects Gigapack/` — the mega pack

61,783 files, 112 MB (71% of `assets/` by size, 98% by file count),
untracked. Organised as loose frames:
`PNG/<Category>/<effect>/<effect>_<size>_<colour>/frameNNNN.png`.
Categories: Explosions, Fantasy Spells, Fire, Impacts, Lightning, Magic
Bursts, Sci-fi, Smoke Bursts (plus Splatters / Symbols listed in the Guide).
Thirteen explosion families, each in `small` and `large` and 6-8 colour
themes:

| family | small | large | frames | verdict for a bomblet |
|---|---|---|---|---|
| `symmetrical_explosion_004` | 48x48 | 96x96 | 10 | **best of the pack** — white core into a ring of orange/yellow blobs flying outward, fading to red speckles. Symmetric, warm, unmistakably a small shrapnel pop |
| `symmetrical_explosion_001` | 32x32 | 64x64 | 8 | fastest and smallest — core, expanding ring, thin red crescent. Clean, but the white/red is more arcade than the game's ochre |
| `symmetrical_explosion_002` | 32x32 | 64x64 | 11 | star flash into a chunky grey cloud; the grey smoke reads dirty next to Tiny Swords |
| `stylized_explosion_001` | 48x48 | 96x96 | 9 | fades to **violet** — clashes with the warm palette |
| `stylized_explosion_002` | 48x48 | 96x96 | 10 | a striped sphere; reads as a ball, not a blast |
| `stylized_explosion_006` | 48x48 | 96x96 | 12 | mushroom cloud with **green** speckles — off-palette |
| `stylized_explosion_003/004/005` | 48-64 | 96-128 | 14 / 23 / 26 | far too many frames for a secondary pop |
| `epic_explosion_001/002/003` | 64-96 | 128-192 | 13 / 15 / 13 | the grand ones, violet smoke, too big and too long |
| `symmetrical_explosion_003` | 48x48 | 96x96 | 12 / 14 | usable, but 004 is the better ring |

Adjacent categories worth knowing about: **Smoke Bursts** (three
`directional_smoke_burst` families) for a puff after the pop, and **Impacts**
(`symmetrical_impact_001..006`, `toon_impact_001`) if a bomblet should read
as a hit rather than an explosion.

## 4. The proposal

### Recommendation: `explosion_1.png`, with `symmetrical_explosion_004` as the stylistic alternative

**Primary — `assets/unused/effects/explosion_1.png`.** It is the same art
family as the blast it is a fragment of, which is the whole point: a bomblet
should read as *a lesser version of that bomb*, not as a different weapon.
It is already tracked, already a 192 px strip the loader reads as-is, two
frames shorter than the parent (0.4 s at 20 fps, or 0.33 s at 24), and its
fireball is 64 px against the parent's 108 — so even at equal blast radii
the art itself is smaller. No repacking, no new attribution, no style risk.

Move it to `assets/effects/explosion_1.png` (beside the sheet it is a
sibling of) and declare a second rig. Measured starting numbers, derived the
same way `explosion`'s were — union opaque bbox plus a 2 px margin for
`content`, `scale` 1:1 with the crop, `anchor` = the burst centre minus the
content origin, `fireball` = the union bbox width:

```json
"explosion_small": {
  "frame": [192, 192], "content": [61, 58, 68, 68],
  "scale": [68, 68], "anchor": [34, 36], "fireball": 64,
  "anims": {"burst": {"file": "effects/explosion_1.png",
                      "frames": 8, "fps": 20, "loop": false}}
}
```

(The burst centre is the mean of the per-frame opaque bbox centres,
`(95, 94)`, so the anchor is `[34, 36]` — these are the numbers that
shipped.)

Those want the same eyeball pass `explosion` got before they ship — the
numbers are measured, not art-directed.

**Alternative — `symmetrical_explosion_004`, `small`, `orange`** (48x48,
10 f). Pick this if the bomblets should be *distinguishable at a glance*
rather than consistent: its outward ring of blobs says "shrapnel" in a way
the star-burst does not, and orange/yellow keeps it in the bomb's palette.
Cost: it is a different art pack, so it needs a cut step and a credits
entry. Follow `utilities/cut_totem_bolt_sheets.py` — a small
`utilities/pack_gigapack_effect.py` that concatenates the 10 frames into a
480x48 strip at `assets/effects/bomblet_burst.png` and supports `--check`,
with the Gigapack left untracked as the authoring source, exactly as the
totem's big source sheets were archived rather than shipped.

### The one code hook it needs

`TransientFx.burst_visual` takes the rig from the module constant
`_BURST_RIG`. The change is to choose it per detonation — a bomblet is
already identifiable by `"cluster" in bomb.source_tags`, the same test
`scatter_bomblets` uses to stop a bomblet scattering again. So `detonate()`
passes the rig, `burst_visual(pos, radius, rig=...)` uses it, and the
missing-sheet path still falls back to the expanding ring. Nothing in
`rendering.py` changes: `_blit_burst` already reads `anim.rig`, so it scales
whatever rig the entry carries by that rig's own `fireball`.

Tests would extend `BurstVisualTests` in `tests/combat/test_bomb.py`: a
bomblet's `_explosions` entry names the bomblet rig and the parent's names
`explosion`, each for its own strip's length, and the ring fallback survives
for both.

### Decisions (owner, 2026-09-12)

**Settled.**

* **The bomblet in flight keeps the parent's bomb sprite, with no rolling
  animation** — "so it looks like it just spreads out the explosion". The
  sprite is already right and already the parent's size; the only thing to
  change is the strip. `game/states/playing/projectiles/bomb.py -- anim_for`
  returns `"spin" if (p.vel.x or p.vel.y) else "fuse"`, and a scattering
  bomblet has velocity, so today it rolls. It must resolve to `fuse` from the
  moment it scatters, regardless of velocity — identifiable by the `cluster`
  tag the bomblet already carries, the same test `scatter_bomblets` and the
  burst-rig hook use.
* **The three bomblets stay simultaneous.** No `cluster_fuse` jitter: the
  stated intent is one explosion spreading outward, and staggering the pops
  would work against exactly that. The earlier "worth a decision" note is
  closed as "leave it".
* **Web packaging is out of scope** — "for now the web packaging is on the
  side so it doesn't matter". The `web/pygbag.ini` finding in §5 stands as a
  note for whenever the web build is picked back up; nothing to do now.

**Settled in the follow-up (same day).**

1. **The burst sheet is `explosion_1.png`** — the recommended option. Same
   pack, same 192 px grid, 8 frames against 10, fireball 64 against 108. No
   Gigapack art ships, so the `CREDITS.md` entry in §5 is **not** needed for
   this feature (the file is still wrong about the pack being the only one
   in the tree, which stands as its own note).
2. **The bomblet ball shrinks**, "consider metadata but if not don't add".
   It rides `cluster_radius_mult` — the knob that already sizes the bomblet's
   blast — instead of a second hand-tuned number: `TransientFx.bomblet_scale`
   multiplies the `bomb` rig's own `scale` by it and passes the result as the
   projectile's `fx.scale`, which `projectiles/bomb.py` already honours. No
   new data key, and the ball can never drift out of step with the blast.
   (The alternative was a `cluster_bomblet` entry in
   `data/weapon_visuals.json` with a literal `scale`; rejected as a second
   number to keep in sync.)
3. **The fuse animates** — the 4-frame lit-fuse loop plays. "No rolling"
   means no `spin`; a lit fuse should still spark.

## 5. Two findings this survey turned up

* **`assets/CREDITS.md` is stale.** It states "**Every PNG under `assets/` is
  from the 'Tiny Swords' asset pack by Pixel Frog**". The Gigapack is a
  second pack and needs its own entry with author, source and licence —
  before anything from it ships, and regardless of which option is chosen.
  Its Guide (`Guide/index.html`) names the pack but gives no author or
  licence.
* **The web build would pack the whole Gigapack.** `web/pygbag.ini`
  `ignoreDirs` excludes `/tests`, `/documentation`, `/utilities`, `/build`
  and friends, but nothing under `assets/`. pygbag walks the filesystem, not
  git, so being untracked does not save the browser bundle from 61,783 files
  and 112 MB — and `assets/unused/` (38 MB) rides along too. Both want an
  `ignoreDirs` entry.

## 6. What was built

| file | change |
|---|---|
| `assets/effects/explosion_1.png` | moved out of `assets/unused/effects/` |
| `data/weapon_sprites.json` | new rig `explosion_small` — frame `[192,192]`, content `[61,58,68,68]`, scale `[68,68]`, anchor `[34,36]`, `fireball` 64, one one-shot `burst` of 8 f at 20 fps (0.40 s) |
| `game/states/playing/effects.py` | `burst_rig(bomb)` picks the sheet off the `cluster` tag; `burst_visual(pos, radius, rig=None)` takes it; `bomblet_scale(mult)` derives the smaller sprite size; `scatter_bomblets` passes `fx={"scale": ...}` and reuses its `radius_mult` local |
| `game/states/playing/projectiles/bomb.py` | `anim_for` returns `fuse` for a `cluster`-tagged projectile whatever its velocity |
| `tests/combat/test_bomb.py` | `BombletFxTests` (rig choice, the small rig's shape, the bomblet bursts, the ring fallback, fuse-not-spin, the derived scale) and `BombletSpriteTests` (the real `PlayingState` spawn path: a bomblet resolves the parent's `bomb` visual and colour) |
| `tests/rendering/test_projectiles.py` | the `BombTests` stand-in gained `source_tags`; two new tests — a bomblet holds `fuse` in flight, and is blitted at the smaller `fx.scale` |

`rendering.py` needed nothing: `_blit_burst` already reads `anim.rig` and
scales by that rig's own `fireball`.

### Measured, through the real fire path

`cluster_radius_mult` 0.6, parent blast 42 (the data's current value):

| | parent | bomblet |
|---|---|---|
| ball sprite | 24 x 36 (rig scale) | **14.4 x 21.6** (60%) |
| in-flight strip | `spin` moving, `fuse` landed | **`fuse` always** |
| blast radius | 42 | **25.2** (60%) |
| burst sheet | `explosion`, 10 f, 0.50 s, fireball 108 | **`explosion_small`, 8 f, 0.40 s, fireball 64** |

Full suite: **2022 passed, 1 skipped, 7 failed** (`python -m pytest -q`,
14m31s). The arithmetic against the run before this feature (2014 passed,
3 failed) closes exactly: +12 new tests, -6 bomb tests the owner's `reach`
change broke, +2 world tests (`test_repair`, `test_village_tidy`) that the
owner's own in-flight edits fixed in the meantime. The 7 remaining failures
are the 6 `reach` ones listed below plus the hero-select off-by-one from
`bomb_blast_journal.md` §5 — none of them this feature's.

Screenshot delivered: three frames of one Cluster Bomb — the throw landing
full-size with a lit fuse, the scatter with three visibly smaller bombs
flown clear of the parent's fading burst, and the three `explosion_small`
pops.

### A data change landed mid-feature (not this work)

`data/weapons.json` changed on disk during the session, by the owner: the
Bomb's `blast_radius` 72 -> 42 and its `reach` 320 -> 100 (and the Bow's
`weight` 8 -> 20). Consequences worth knowing:

* The new tests are written against the data, never against a literal, so
  they survived it — `BlastAreaTests` now derives its target distance from
  `DATA["reach"]` rather than standing at a fixed 150 px.
* **Six pre-existing tests now fail** for one reason: their targets sit at
  150-300 px, outside the new 100 px reach ring, so the Bomb never fires.
  `ThrowTests::{test_a_throw_is_one_inert_fused_projectile,
  test_it_stops_on_a_near_target_rather_than_flying_past,
  test_a_far_target_gets_the_full_throw, test_extra_bombs_fan_out}`,
  `test_forge.py::BombForgeTests::test_minefield_throws_armed_mines`, and
  `test_weapon_effects.py::FirePathBonusTests::test_bigger_explosion_reaches_the_bomb`.
  Proven by restoring `reach` to 320 in the working tree: 61/61 pass, then
  the owner's 100 was put straight back.
* `reach` 100 is well under the other ranged weapons (Bow 460, Rod 400) and
  under the throw's own travel of `projectile_speed * throw_time` = 165 px,
  so a thrown bomb can no longer be thrown to the edge of its own arc. The
  owner kept the value and asked for the tests to be retuned instead.

**The retune (owner, 2026-09-12).** Every distance in `test_bomb.py` now
comes off the data — module-level `NEAR = DATA["reach"] * 0.4` and
`FULL_THROW_AT = projectile_speed * throw_time` — and the two other modules
derive theirs the same way, so the next tuning pass cannot strand a target
outside the ring. One test needed more than a number:
`test_a_far_target_gets_the_full_throw` could not survive as written,
because the full `throw_time` needs a target at least `FULL_THROW_AT` away
and the ring no longer reaches that far. It became
`test_the_far_end_of_the_throw_is_whichever_of_the_two_caps_first`, which
asserts whichever of the two caps the current data puts the Bomb under —
the full throw when `reach >= FULL_THROW_AT`, otherwise the ring capping it
short, with the `< throw_time` assertion that makes the second branch mean
something. Both regimes were exercised by flipping `reach` between 100 and
320 in the working tree: 91 passed either way, and the owner's 100 was put
straight back.

## 7. Progress

- [x] surveyed `assets/effects`, `assets/unused/effects`, and all 13 Gigapack
      explosion families (frame sizes, counts, colour themes)
- [x] contact sheets rendered and delivered for the Tiny Swords trio and the
      seven Gigapack candidates
- [x] proposal, rig numbers, the one code hook, and the open decisions
- [x] owner settled the in-flight look, the simultaneous pop, and web scope
- [x] owner picked the burst sprite, the shrink and the animated fuse
- [x] built, tested and screenshotted
