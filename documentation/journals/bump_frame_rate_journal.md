# The crowd bump at any frame rate: journal

**ID:** ENT-019 · **System:** entities (+ SYS) · **Type:** bug ·
**Status:** in progress · **Branch:** ComeGalletas/ent-019-bump-frame-rate-417b14b3
(the app's session worktree `.claude/worktrees/busy-shtern-6bb78d`, based on
`origin/main` d61d9f2)

---

## ENT-019: Requirement (owner, 2026-09-30)

- **Objective:** The crowd bump (CB-3's separation pass) separates bodies by
  the same amount per game-second at any frame rate.
- **Details:**
  - `BumpResolver._bump` (`game/states/playing/core/physics.py`) runs once
    a frame and hands each overlapping pair `BUMP_GAIN × penetration`
    through `apply_knockback`, with no `dt` in it.
  - `Enemy.update` (and `Player.update`) move by `(vel + _knock) × dt`,
    then decay `_knock *= BUMP_DECAY ** dt`.
  - So the push a second grows with the number of frames a second. At the
    desktop's 62 fps cap it is today's tuning. Below it (heavy frames) a
    crowd separates more slowly. The browser build, uncapped at the
    display's refresh since BLD-003 (`web_frame_time_journal.md`, D4, on
    its own branch), would separate faster on a 120 to 165 Hz display.
- **Constraint:**
  - Measure first: the same packed crowd, or a hand-built overlapping
    pair, stepped for the same game time at dt 1/30, 1/62 and 1/144.
  - At 62 fps the behaviour stays **byte-identical** to today, pinned by a
    test.
  - At other rates the separation per game-second matches.
  - Read the tuning history (CB-3/H, ENT-016, RND-008.5, ENT-018) before
    changing anything. Ask the owner before changing the feel at 62 fps.

## ENT-019: Confirmed reading (2026-09-30)

- **The tuning history.**
  - CB-3/H (`combat_balance_journal.md`) set `BUMP_GAIN 12`,
    `BUMP_DIFF_GAIN 2.0`, `BUMP_DECAY 0.001` and `_PEN_CAP_FRAC 0.6` by
    playtest on the desktop loop. Its own note already reads the bump as
    "applied *every frame the pair overlaps*".
  - ENT-016 (`enemy_ai_journal.md`) set the crowd push radius 0.75 from
    the bridge-crowd bench, which steps at 1/60.
  - RND-008.5 (`frame_time_journal.md`) and ENT-018
    (`enemy_update_journal.md`) made the pass and the update cheaper bit
    for bit. `tests/playing/test_bump_exact.py` keeps the pre-RND-008.5
    pass verbatim as an oracle and compares every `_knock` with `==`.
- **The only per-frame impulse.** Every other `apply_knockback` caller
  (weapon hits, the elemental shockwaves, Crowd Cleaner's pull, the
  villagers' lance) fires once per event, so it is an impulse and correct
  at any rate. The bump is the one that repeats every frame an overlap
  lasts, which makes it a rate that was written as a per-frame amount.
- **The hero shares the pass.** Hero against enemy and hero against boss
  go through the same `_bump`, so the fix covers the hero's shove too.
- **The desktop's real step is not exactly 1/62.** `clock.tick(62)` works
  in whole milliseconds, so a frame is 16 ms (62.5 Hz) against the cap, or
  16 and 17 ms alternating on a 60 Hz vsync display.
- **Measured before any change** (scratch probe; the tool in ENT-019.2
  reproduces it): seed 35, 60 enemies packed into 70 px round the hero,
  their AI made inert so only the bump moves them, the real
  `Enemy.update` and `BumpResolver.resolve` stepped in the game's order.
  Time until the crowd's total overlap is down to half, a quarter and a
  tenth:

  | Rate | t50 | t25 | t10 |
  |---|---|---|---|
  | 20 Hz | 0.147 s | 0.243 s | 0.442 s |
  | 30 Hz | 0.120 s | 0.211 s | 0.342 s |
  | 62 Hz | 0.078 s | 0.125 s | 0.224 s |
  | 144 Hz | 0.048 s | 0.081 s | 0.170 s |
  | 165 Hz | 0.045 s | 0.074 s | 0.171 s |

  At 144 Hz the crowd halves its overlap in 62 % of the 62 Hz time; at
  30 Hz it takes 154 %. The dependence is real and large.

## ENT-019: Decisions

- **ENT-019.D1: the per-frame impulse is scaled by
  `(1 − BUMP_DECAY^dt) / (1 − BUMP_DECAY^(1/62))`.**
  - Why this form and not `dt × 62`. A pair held at the same overlap gets
    `J` a frame. Its knock settles where the frame's decay takes away what
    the frame adds, at `J / (1 − D^dt)`, and that is the speed it is shoved
    at. Scaling `J` by `1 − D^dt` makes that speed, and the distance it
    covers a game-second, the same at every rate, exactly, not only as dt
    goes to zero. `dt × 62` gets that only in the limit: 6 % too strong at
    30 Hz, 3 % too weak at 144 Hz.
  - At dt = 1/62 the factor is the same float divided by itself, exactly
    1.0, and `x × 1.0 == x` in IEEE arithmetic, so every `_knock` is the
    one it is today, bit for bit.
  - The scratch probe compared both forms on the crowd and on two pairs:
    the exponential form is as close as the linear one at high rates and
    closer below 62 Hz on every measure.
- **ENT-019.D2: the reference is a constant 62, not `config.FPS`.** The
  web profile sets `FPS = 60`, and a later change to the cap must not
  retune the bump. `config.BUMP_REFERENCE_FPS = 62` is the rate CB-3/H was
  tuned at. It has the same value as `FPS` today, but it is a different
  quantity, so it is not a duplicate of it.
- **ENT-019.D3: the pass takes the frame's `dt`.** `resolve(dt)` computes
  the factor once a frame and hands it to `_bump`, whose default of 1.0
  keeps the RND-008.5 oracle in `test_bump_exact.py` runnable as it is.
  `dt` is required on `resolve`, so a caller cannot silently get the
  62 Hz amount.
- **ENT-019.D4: what the factor cannot fix is stated, not hidden.** The
  bump is a stiff one-sided spring: for a light enemy against a heavy one
  (weights 8 and 30) the pair's natural frequency is 40 rad/s, so `ω × dt`
  is 0.65 at 62 Hz and 2.0 at 20 Hz, the edge past which a step that size
  no longer follows a spring at all. No per-frame factor makes a step
  that coarse follow the overlap as it closes. The numbers below 62 Hz are measured and
  written down in the Results.

## ENT-019: Plan

1. This block and the index row.
2. **The measuring tool**, `tools/benchmarks/bump_rate.py`:
   - The packed crowd (the spawn-stress harness's `build` and
     `cascade_setup` with `prime=False`), AI made inert, the hero parked
     out of reach, stepped for the same game time at each rate. Reported:
     time to 50 / 25 / 10 % of the starting overlap, and the overlap left
     at fixed times.
   - Two hand-built pairs, one equal and one lopsided (weights 30 and 8),
     12 px inside the push radius. Reported: distance at fixed times and
     the peak knock.
   - `--unscaled` runs the pass as it was before ENT-019, so the before
     table can be reproduced after the fix.
   - The before table from the tool, in this journal.
3. **The fix:**
   - `physics.bump_scale(dt)`, `resolve(dt)`, the call in
     `PlayingState._phase_update`, `config.BUMP_REFERENCE_FPS`.
   - Callers of `resolve()` updated: `spawn_stress.bump_times` and the
     tests.
   - `run_digest` gets `--fps`, so the whole-run fingerprint can be
     compared at 62 fps before and after. The pinned digests step at 1/60
     and move; they are re-pinned.
   - **Tests:**
     - `test_bump_exact.py` compares the new pass at `dt = 1/62` against
       the verbatim oracle, `==` on every `_knock`: the byte-identity pin.
     - `bump_scale(1/62) == 1.0` exactly. A held overlap settles at the
       same knock at every rate. `resolve(dt)` shoves `bump_scale(dt)`
       times the 62 Hz amount.
     - The tool's crowd and pairs at 30, 62 and 144 Hz agree within stated
       bounds. With the factor forced to 1.0 (the bug) the same test
       fails, so it catches the bug.
4. A cold critic pass (an attacker on the repro); fixes; results; docs.

## ENT-019: Tasks

- [x] ENT-019.1: This block, the index row
- [ ] ENT-019.2: `tools/benchmarks/bump_rate.py`, its test, the before table
- [ ] ENT-019.3: The dt-scaled bump; tests; digests re-pinned
- [ ] ENT-019.4: Critic pass, results, docs; ENT-019 done
