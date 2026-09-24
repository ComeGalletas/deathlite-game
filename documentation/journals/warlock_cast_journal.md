# Hexcaller cast wind-up — journal

**ID:** ENT-013 · **System:** entities (+ RND) · **Type:** feature ·
**Status:** in progress · **Branch:** claude/ent-013-warlock-cast-marker
(stacked on PR #30, in the current worktree — owner, 2026-09-24)

---

## ENT-013 — Requirement (owner, 2026-09-24)

- **Objective:** Show the Hexcaller's cast on the ground where it will land
  for the whole wind-up, so the player can step out before the hazard
  appears.
- **Details:** Use the hazard's own sprite for the marker, and find a
  suitable wind-up / cast animation in the art reserve to play at the
  landing spot before the hazard appears.
- **Constraint:** Stacked on #30. The wind-up exists to be read and dodged:
  it has to mark the real footprint, from the moment the target is chosen.

## ENT-013 — Confirmed reading

- The Hexcaller (`hex_shaman`, behaviour `fsm_warlock`,
  `entities/ai/behaviors/melee.py`) snapshots the hero's position into
  `bb.slot(ATTACK_SLOT)["cast_at"]` when its wind-up starts
  (`on_windup_start`), winds up for `cast_telegraph` 0.8 s, then drops its
  hazard there: `hazard_radius` 20, `hazard_dps` 6, `hazard_duration` 0.9,
  drawn with `hazard_sprite` `hex_shaman_explosion_spell` (10 frames at 14
  fps, one shot — a small pink ring that swells into a pink-and-white burst
  and scatters).
- Nothing marks `cast_at` during the wind-up. The only telegraph drawing is
  the red ring round an enemy with a `slam_radius`
  (`visual/rendering.py`), which the Hexcaller has not — noted as wanted in
  `designs/sprite_functionality.md` *Still open*, "the same rig drawn at the
  snapshotted `cast_at` during the `telegraph` state".
- **The asset.** Surveyed in the reserve (`assets/unused/`, the Super Pixel
  Effects Gigapack): the charge-up and absorb families are the ones that
  read as *something gathering here*. Contact sheet compared on a dark
  ground: `Sci-fi/scifi_charge_up_001` (pink; reads as a sci-fi reticle),
  `002` (violet; busy, green sparks), **`003` (violet; a pink-violet ring
  with orbs pulsing inside it)**, `Fantasy Spells/spell_absorb_001` (pink;
  gathers well but ends in sparkles that clash with the burst),
  `spell_debuff_001` and `spell_death_001` (the wrong subject: arrows, a
  skull).
- **ENT-013.D1 — `scifi_charge_up_003_small_violet`.** Its ring marks an
  area, its orbs gather, its pinks and violets are the hex burst's, and its
  16 frames at 64 px loop cleanly — at 20 fps they fill the 0.8 s wind-up.
- **ENT-013.D2 — Two layers, both authored.** Under it, the hazard sprite's
  own first frame (its small pink ring) at the hazard's footprint, fading in
  over the wind-up — the "use the hazard sprite" part, and the exact area
  that will burn. The charge-up plays over it. On landing both give way to
  the burst as today. No procedural ring (the standing rule: authored art
  replaces the procedural indicator).
- **ENT-013.D3 — Timing and numbers unchanged.** The 0.8 s wind-up, the
  snapshot at its start and the hazard's size and damage stay; what changes
  is that the player can see them. Tuning is the owner's.

## ENT-013 — Plan

- **Art:** the 16 source frames archived, tracked, in
  `assets/enemies/hex_shaman/unused/cast_charge/`, and
  `tools/asset_pipeline/cut_cast_charge.py` joining them into
  `assets/enemies/hex_shaman/hex_shaman_cast_charge.png` (1024 × 64), with
  a `--check` mode a test runs. A rig for it in `enemy_sprites.json`.
- **Data:** the Hexcaller names its wind-up rig and the marker's alpha
  ramp in `enemies.json`, beside `hazard_sprite`.
- **Draw:** a focused module under `game/states/playing/visual/` that,
  for an enemy telegraphing a cast, draws the two layers at `cast_at`,
  under the actors (a ground effect).
- **Tests:** the cut's `--check`; the marker drawn only while telegraphing
  and at `cast_at`, not at the enemy; the footprint layer sized to
  `hazard_radius`; data validation. Screenshot of a wind-up.

## ENT-013 — Tasks

- [x] ENT-013.1 — Open this journal; index row
- [x] ENT-013.2 — Archive the source frames, the cut script and its strip, the rig
- [x] ENT-013.3 — The wind-up draw at `cast_at`, data in `enemies.json`
- [x] ENT-013.4 — Tests and a screenshot
- [ ] ENT-013.5 — Results; `sprite_functionality.md`'s open note; index to done

## ENT-013 — Results

- **Art (ENT-013.2):** the 16 Gigapack frames archived and tracked in
  `assets/enemies/hex_shaman/unused/cast_charge/`;
  `tools/asset_pipeline/cut_cast_charge.py` joins them into
  `hex_shaman_cast_charge.png` (1024 × 64), `--check` exits 0; the rig plays
  all 16 at 20 fps; `CREDITS.md` usage line added.
- **Draw (ENT-013.3):** `game/states/playing/visual/cast_marker.py`, called
  from the flat-effects pass right after the hazard pools. Data:
  `hex_shaman.cast_marker` = `{"sprite": "hex_shaman_cast_charge",
  "footprint_alpha": [60, 200]}`.
- **ENT-013.D4 — Tuned on the screenshot:** the first build drew the
  charge-up at 52 px; the Hexcaller aims at the hero's feet, so with the
  hero standing in the spot the marker hid under the body. The charge-up is
  **76 px**, so it shows round a body standing in it; the footprint layer
  keeps the hazard's exact size, so the true area stays honest.
- **Screenshot:** seed 35, the hero steps 90 px aside once the wind-up
  starts — at 0.05 s a dashed violet ring and scattered orbs, at 0.42 s the
  orbs gathering, at 0.75 s a bright pink core over the pale footprint ring,
  then the hazard pool landing on exactly that spot with the hero clear.
- **Tests (ENT-013.4):** `tests/render/test_cast_charge.py` (3: the cut's
  `--check`, the 16 archived frames, the rig) and
  `tests/render/test_cast_marker.py` (8: drawn at `cast_at` and not at the
  caster; nothing outside the wind-up, without a snapshot, or on an enemy
  with no `cast_marker`; the footprint's progress ramp; the footprint is the
  hazard sprite at the hazard's size; the data; drawn after the hazard pools)
  — **11 passed**. The broader `tests/render` + `tests/playing` +
  `tests/entities` run on the new draw was still in progress when these
  were committed, at the owner's request to push; its count is recorded in
  the next commit.
