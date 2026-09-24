# Mark overlay — journal

**ID:** RND-007 · **System:** rendering (+ CMB) · **Type:** feature ·
**Status:** in progress · **Branch:** claude/rnd-007-mark-overlay (the current
worktree, cut from `main` after #36 — owner, 2026-09-24)

---

## RND-007 — Requirement (owner, 2026-09-24)

- **Objective:** Show the `mark` status on a marked enemy with authored art
  from the reserve.
- **Details:**
  - The art is the lock-on brackets found in the unused assets.
  - The colour is raspberry (hue 340). It must read as red but stay clearly
    apart from the fire element's orange.
  - The mark shows only while the hero holds a blessing that reads it.
- **Constraint:**
  - It must not be mistaken for fire.
  - The art stays regenerable from archived sources.
  - What the mark does in combat does not change.

## RND-007 — Confirmed reading

- **The status.** The Magic Rod and its forges (`mark_on_hit`) leave `mark`
  (`combat/status.py`, family `mark`, refresh, one stack) on what they hit,
  for `config.SYNERGY_WINDOW_S` (1.5 s). `combat/synergy.py` reads it:
  `syn_vs_marked` adds damage against a marked target. Two blessings give
  that effect: Marked Prey (Daggers, +30–100 %) and Crossfire (Bow,
  +20–70 %).
- **What shows today:** nothing, with sprites on. The only sign is the
  lilac `(210, 170, 255)` status ring in `_STATUS_TINT`
  (`visual/rendering.py`), drawn for the primitive fallback or under
  `SHOW_ENEMY_STATE_RINGS`.
- **The survey** covered the Gigapack's red colourways of nine candidates
  over a real enemy (`scifi_analyze_001`, `scifi_charge_up_001`/`002`,
  `spell_debuff`/`death`/`dispel`/`absorb`, `symbol_alert`/`warning`), and
  `unordered-effects` at thumbnail size.
  - **Chosen: `scifi_analyze_001` (RND-007.D1).** Four corner brackets frame
    the body, reading as "targeted" without covering it.
  - The reticle is rejected: its white core hides the enemy.
  - Arrows, the skull, the "!" and the warning sign are the wrong subjects,
    and the bursts read as hits.
- **The colour (RND-007.D2).** The pack's "red" is a salmon orange-red
  (median hue 14°), next to fire's 22°. The free band is 330–355°, between
  the HP bar's pure red (about 0°) and thunder's violet (265°). **Raspberry,
  hue 340**, the owner's pick.
- **The frames (RND-007.D3).** Of the 144 px `large_red` source's 120
  frames, 4–108 add scanner panels. The run 109 → 119 → 0 → 2 is brackets
  only, and breathes: the box tightens from 62 px wide to 50 and opens
  again. That is a clean 14-frame lock-on loop.
  - A leader line from the retracting panel trails off the **top-right**
    bracket in those frames; the left brackets never carry it.
  - The cut script erases anything on the right half above the left
    brackets' top row, frame by frame, so no hand edit is needed.
- **When it shows (RND-007.D4, owner).** Only while any weapon the hero
  holds has `syn_vs_marked` above 0. It is data: the visual's
  `shown_with_effects` lists the effect keys that make the mark worth
  seeing.
- **Draw (RND-007.D5).**
  - It is drawn right after the enemy's own sprite, so it depth-sorts with
    the body and an enemy standing in front still covers it.
  - It is sized so the bracket box frames the body's drawn size, and fades
    over the mark's last `fade` seconds.
  - The authored brackets replace the ring. The ring stays as the no-art
    fallback, recoloured to raspberry, from the data.

## RND-007 — Plan

- **Art:**
  - `assets/effects/status/unused/mark/`: the 14 source frames, archived and
    tracked.
  - `tools/asset_pipeline/cut_mark_brackets.py`: erase the leader, recolour
    to the data's hue, join into `assets/effects/status/mark.png`, with a
    `--check` mode.
  - A rig `status_mark` in `weapon_sprites.json`, and a `CREDITS.md` line.
- **Data:** `data/weapons/status_visuals.json` `mark`:
  - `sprite`, `hue`, `colour` (the fallback ring);
  - `box` (the bracket box in source px) and `over_body`;
  - `fade`, `shown_with_effects`.
- **Code:**
  - `game/states/playing/visual/status_marks.py`, drawn from `one_enemy`
    after the sprite.
  - `_STATUS_TINT["mark"]` reads the data's colour.
- **Tests:**
  - the cut's `--check`;
  - drawn only when marked and a `syn_vs_marked` weapon is held;
  - the fade;
  - sized to the body;
  - the colour is apart from fire's.
- **Screenshot:** a Rod plus Marked Prey build marking a pack.

## RND-007 — Tasks

- [x] RND-007.1 — This journal; the index row
- [x] RND-007.2 — Archive the frames; the cut script with its recolour and leader erase; the strip; the rig; credits
- [ ] RND-007.3 — `status_visuals.json`; the overlay module; the fallback ring's colour
- [ ] RND-007.4 — Tests and a screenshot
- [ ] RND-007.5 — Results; index to done
