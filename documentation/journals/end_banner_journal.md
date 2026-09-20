# End banners (GAME OVER / VICTORY intermission) — execution journal

## Requirement (owner, 2026-09-19)

Find art for the game-over and victory screens in the asset reserve, and add
it as an *animated intermediary screen* shown before the proper end state:

- **Loss** — when the hero loses all HP, wait 3 s, then play the "game over"
  sprite animation through one full loop, wait 2 s, then show the game-over
  summary screen.
- **Win** — the same behaviour with the victory sprite, then the victory
  summary screen.

Confirm and propose first; build on a go.

---

## What the reserve holds

Nothing in the tracked tree or in `assets/unused/ui/banners/` (parchment and
scroll panels) is end-screen art. The animations are in the untracked
**Super Pixel Effects Gigapack** (`assets/unused/Super Pixel Effects Gigapack/`,
main checkout only — this worktree does not have the folder), under
`PNG/Symbols/` as per-frame PNGs and under `spritesheet/Symbols/` as packed
2048 px sheets with a `.txt` atlas. Every symbol comes in six colourways
(red, orange, yellow, green, blue, violet) and two sizes, and the pack's guide
states 15 FPS (66.7 ms per frame).

| Symbol | Frames | Large frame | Small frame | One loop | Motion |
|---|---|---|---|---|---|
| `symbol_game_over_text_001` | 44 | 416×128 | 208×64 | 2.93 s | letters fly in one by one, hold, fly out |
| `symbol_game_over_text_002` | 60 | 352×96 | 176×48 | 4.00 s | slash-in, hold, slash out (italic face) |
| `symbol_you_lost_text_001` | 48 | 360×128 | 180×64 | 3.20 s | "You Lost..." bounce in, hold, drop out |
| `symbol_victory_text_001` | 52 | 256×96 | 128×48 | 3.47 s | letters slam in, hold, scatter out |
| `symbol_you_won_text_001` | 42 | 288×128 | 144×64 | 2.80 s | "You Won!" bounce in, hold, drop out |

Chosen pair: **`game_over_text_001` in red** (the end screen's title is
`(230, 90, 90)`) and **`you_won_text_001` in yellow** (the victory title is
gold `(255, 214, 112)`). Both are one-shot in/hold/out sequences, so "play
until the loop finishes" reads naturally as "play through the fly-out".

## Confirmed reading of the flow

Today (`game/states/playing/core/state.py`):

- Loss: the frame the hero stops being alive spawns the death poof and holds
  the run open 1.05 s (`_death_seq_t`), then `_end_run(victory=False)` builds
  the summary, publishes `RUN_ENDED` and `change()`s to `GameOverState`.
- Win: `_on_boss_killed` calls `_end_run(victory=True)` at once.
- Both end states declare `music = None`, so the run track fades the moment
  they arrive.

Proposed timeline (both outcomes, only the art differs):

```
t = 0.0   HP hits 0  /  boss dies
          run clock stops, summary snapshot taken, input and combat off,
          music fades (as today)
t = 0..3  WAIT  — the world keeps animating underneath (death poof, boss
          burst, particles finish naturally); nothing can hurt the hero
t = 3.0   BANNER — world frozen; the sprite plays one full loop, centred
          on the UI box, over a dimmed scene
t = 3.0 + loop (2.93 s loss / 3.47 s win)
          WAIT 2 s on the last frame (the banner has flown out; dim scene)
t = +2.0  hand-off: RUN_ENDED published, change() to GameOverState /
          VictoryState with the snapshot — the summary screens are untouched
```

The 1.05 s death hold is subsumed by the 3 s wait (the poof is ~1 s, so it
completes inside it). Dev-mode runs see the same intermission and then take
their usual instant reset instead of a summary screen.

## Proposed implementation

An overlay state, `game/states/end_banner_state.py` (`EndBannerState`), pushed
on top of the run rather than replacing it, so the scene stays visible: it
declares `draw_below = True`, `update_below` toggled per phase (True during the
wait, False once the banner starts), `music = None`. It owns a small phase
timer (`wait → banner → hold → handoff`) and drives the sprite with the
existing `systems.animation.Animator`, so frame count, fps and one-shot-ness
come from a rig entry instead of code.

## Todo

1. **Cut the art in** — `tools/asset_pipeline/cut_end_banners.py` reads the
   chosen colourway's large frames from the Gigapack and writes
   `assets/ui/end_banners/game_over.png` and `victory.png` (strip or grid,
   whichever the asset loader takes); the Gigapack stays where it is as the
   source. Extend `assets/CREDITS.md` with the pack entry / usage line.
2. **Register the rigs** — a rig entry per banner (frame size, 15 fps,
   `loop: false`) so `Animator` and `Assets.frame` drive it like the spawn
   burst does.
3. **Split `_end_run`** — `_snapshot_summary()` (runs at the trigger, stops the
   clock) and `_hand_off(summary)` (publishes `RUN_ENDED`, changes state).
   Dev mode runs the same intermission; its hand-off is the reset.
4. **`EndBannerState`** — the phase timer, the wait / banner / hold sequence,
   dim layer, banner centred on the UI box at an integer scale, input
   swallowed (no skip), `on_display_changed` rebuild.
5. **Wire the triggers** — hero death and `_on_boss_killed` push the overlay
   with `victory=`, replacing the `_death_seq_t` hold; the run refuses damage
   and input while the overlay is up.
6. **Tests** — `tests/screens/test_end_banner.py` with a stub assets object:
   hand-off happens at 3 s + one loop + 2 s and not a frame earlier for both
   outcomes; the world keeps updating during the wait and stops once the
   banner starts; the snapshot's `time` does not grow during the
   intermission; a dev run's hand-off is the reset, not a summary.
7. **Screenshot** of both banners mid-animation over a live scene, and the
   journal entry.

## Decisions (owner, 2026-09-19)

- Symbols: **`symbol_game_over_text_001`** for the loss, **`symbol_you_won_text_001`**
  for the win. Colourways follow the summary screens' titles: red for the
  loss, yellow for the win.
- During the 3 s wait the world **keeps animating** underneath; it freezes
  once the banner starts.
- **No skip**: no key or click shortens the intermission.
- **Dev-mode runs show the banner as well**, then reset as they do today
  (still no summary screen, nothing banked).

Loop lengths with the chosen symbols: loss 44 frames = 2.93 s, win
42 frames = 2.80 s, so the whole intermission is 7.93 s for a loss and
7.80 s for a win.

---

## Build (2026-09-19)

Everything in the todo, in order, on branch `claude/gameover-victory-sprites-96ff62`.

**Art.** `tools/asset_pipeline/cut_end_banners.py` reads the chosen
colourway's large frames from the Gigapack (`--source DIR` when the pack is
not beside the checkout; it is untracked and this worktree has no copy) and
writes `assets/ui/end_banners/game_over.png` (44 frames, 5 per row,
2080 x 1152) and `you_won.png` (42 frames, 7 per row, 2016 x 768).
`--check` re-cuts and compares, or with the pack absent only confirms the
sheets exist. `assets/CREDITS.md` gained a "where the additional packs are
used" note for the Gigapack.

**Loader.** `Assets._build_frames` learned `cols` -- an anim may wrap over
several rows, `cols` frames each -- because a single-row strip of these
would be 18 000 px wide; and it falls back to the rig-level `file` when the
anim names none, so a one-sheet rig is declared once. Neither changes any
existing rig (no `cols` means one row, as before).

**Rigs.** `end_banner_loss` / `end_banner_win` in `data/ui/ui_sprites.json`:
frame size, `show` anim with the frame count, 15 fps, `loop: false`, `cols`.

**Config.** `END_BANNER_WAIT = 3.0`, `END_BANNER_HOLD = 2.0`,
`END_BANNER_SCALE = 2` (416 x 128 drawn at 832 x 256 on the 1600-wide box,
through `scale.int_scale` under native rendering), `END_BANNER_DIM_ALPHA = 150`
(the pause overlay's dim) and `END_BANNER_DIM_FADE = 0.4`.

**`game/states/end_banner_state.py`.** `EndBannerState`, an overlay
(`draw_below = True`, `music = None`, input swallowed) with a phase clock:
`wait` (the run underneath keeps updating -- `update_below` is set per
instance and flips to False when the banner starts), `banner` (the
`Animator` plays `show` once; the dim fades in over 0.4 s), `hold`, then
`on_done`. `draw` puts the frame at 42 % of the box height. With no art the
same words are drawn in the heading face and the clock is the two waits.

**`PlayingState`.** The 1.05 s `_death_seq_t` hold is gone. `_ending` is set
the frame the outcome is decided; `update` then runs `_run_ending_sequence`
(hero anim, death / trail / spawn fx, camera, particles, damage numbers,
shake -- no input, no combat, no enemy motion, no clock). `_end_run` was
split into `_snapshot_summary` (the dict the screens read, taken at the
trigger) and `_hand_off` (publish `RUN_ENDED`, then the dev reset or the
summary state); `_begin_end` is what the death and `_on_boss_killed` call
-- snapshot, then push the banner with `on_done = _hand_off`. `_end_run`
survives as snapshot-plus-hand-off with no banner, for the tests that want
the summary at once. The dev "unlimited HP mid-death" cancel went with the
timer: the dev menu cannot be opened under the overlay.

**Tests.** `tests/screens/test_end_banner.py`: the hand-off instant to the
frame for both outcomes (7.93 s / 7.80 s), nothing a frame early, the phase
order, one hand-off only, the run underneath updated every wait frame and
not once after, input swallowed, nothing drawn during the wait, the sprite
at the integer scale during the banner, the dim kept and the sprite dropped
during the hold, the words drawn without art, the rigs naming the chosen
symbols, every frame present on the committed sheets, and `--check` clean.
Updated for the banner: `test_enemy_sprite` (death sets `_ending` and pushes
the banner), `test_smoke` (the boss kill and the death ride the banner to the
summary), `test_dev_mode` (a dev death rides it to the reset), `test_music`
(the banner is in the roster and fades to silence).

**Screenshots.** Both banners over a live booted run, delivered in the
session.

**Results.** `tests/screens/test_end_banner.py` 17 passed; the affected
screen / music / sprite suites 152 passed; the integration suites that boot
a run and end it (`test_smoke`, `test_dev_mode`, `test_hero_unlock`,
`test_potion_drops`, `test_ui_scale`, `test_ultrawide`): 124 passed, 2 failed
on the first run: two `test_hero_unlock` tests called `_on_boss_killed`
and read the victory screen on the next line, so they now ride the banner
out first (`_ride_out_banner`), and the module passes (12); the unit
tier 1493 passed with one pre-existing failure (`test_imp` asserts an
untracked file under `assets/unused/`, which this worktree does not carry).
