# The crowd bump at any frame rate: journal

**ID:** ENT-019 · **System:** entities (+ SYS) · **Type:** bug ·
**Status:** done (2026-09-30) · **Branch:** ComeGalletas/ent-019-bump-frame-rate-417b14b3
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
    display's refresh since BLD-003 (`web_frame_time_journal.md`, D4; on
    main since the BLD-003 landing), would separate faster on a 120 to
    165 Hz display.
- **Constraint:**
  - Measure first: the same packed crowd, or a hand-built overlapping
    pair, stepped for the same game time at dt 1/30, 1/62 and 1/144.
  - At 62 fps the behaviour stays **byte-identical** to today, pinned by a
    test.
  - At other rates the separation per game-second matches. (Narrowed by
    the owner in D5: faster frames only; slower ones stay as they were.)
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
  - On the tuned frame and any longer one the factor is returned as the
    literal 1.0 (D5, D6), and `x × 1.0 == x` in IEEE arithmetic, so every
    `_knock` there is the one it is today, bit for bit.
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
- **ENT-019.D4: below 62 Hz no per-frame factor is exact.** The bump is a
  stiff one-sided spring. For the bench's lopsided pair (troll, weight 80,
  against bumblebee, weight 3; the weight gap amplifies the shove 2.855×)
  the pair's natural frequency is 46 rad/s, so `ω × dt` is 0.74 at 62 Hz,
  1.54 at 30 Hz and 2.3 at 20 Hz, past the 2.0 where a step that size stops
  following a spring at all. A long frame hands the pair its whole share
  at the overlap it started with, while at 62 Hz the first frame already
  clears most of it. Measured with the factor applied at every rate: at
  45 Hz and above every measure is within 11 % of 62 Hz, but the bumblebee
  flies 37 % further at 30 Hz and twice as far at 20 Hz (1098 px/s peak
  against 532). A lag correction (subtracting the closing a longer frame
  skips) changed nothing for that pair, since its first shove starts from
  rest. Only sub-stepping long frames is exact.
- **ENT-019.D5 (owner, 2026-09-30): the factor only ever scales down.**
  Asked with the measured tables, the owner chose to fix only the fast side
  and leave slow frames exactly as they were. `bump_scale` is exactly 1.0 on
  any frame of 1/62 s or longer, so at 62 fps and below the pass is the
  tuned one bit for bit, and a heavy scene still separates a crowd more
  slowly a second, as before. The options put to the owner, at 30 fps as a
  share of the 62 fps value:

  | Measure | today | this (cap at 60, taken as "exactly today") | cap at 45 | uncapped |
  |---|---|---|---|---|
  | crowd t50 | 153 % | 153 % | 132 % | 115 % |
  | crowd t10 | 153 % | 153 % | 136 % | 162 % |
  | bear pair, distance | 81 % | 81 % | 91 % | 104 % |
  | bumblebee against troll, distance | 77 % | 77 % | 99 % | 137 % |

  - The option was worded "cap at 60 fps; below 60 fps the bump stays
    exactly as today". A cap at a 1/60 s frame would give a slower frame
    1.0315× today's shove, not today's, so the cap is put at the tuned
    rate, where "exactly as today" holds bit for bit. The two differ only
    on frames between 1/62 and 1/60 s, and by at most 3 %.
  - A fourth option, keeping the loop capped at 60 fps and no bump change,
    would have undone BLD-003's uncapped browser pacing.
  - Recorded in memory (`bump-frame-rate-decisions`).
- **ENT-019.D6 (critic finding): the tuned frame is 16 ms, not 1/62 s.**
  `Game._step` takes `clock.tick(FPS) / 1000`, whole milliseconds. The
  critic measured `clock.tick(62)` over 300 frames: 16 ms 133 times, 17 ms
  150 times, 18 ms 14 times. The loop never produces 1/62 s (16.13 ms), so
  a threshold at 1/62 scaled 45 % of real desktop frames at the cap by
  0.9924, and every pin, fed exactly 1/62, missed it. `physics.tuned_dt()`
  is `floor(1000 / BUMP_REFERENCE_FPS) / 1000` = 16 ms: the threshold and
  the fast-frame reference both. 16, 17 and 18 ms frames, and 1/62 s, all
  return exactly 1.0, and the share meets 1.0 continuously just under
  16 ms. A faster frame now matches the 16 ms frame a second, not the
  1/62 s one; the two differ by 0.76 %.

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
     compared at 62 fps before and after. The pinned digests step at 1/60,
     a slow frame after D5, so ENT-019 does not move them. (Seed 123's pin
     was already stale on `main`, see the Results.)
   - **Tests:**
     - `test_bump_exact.py` compares the new pass on the tuned 16 ms frame,
       and at 1/62 s, 17 and 18 ms, 1/60, 1/30 and 1/20, against the
       verbatim oracle (its own copy of the pre-ENT-019 `_bump`), `==` on
       every `_knock`: the byte-identity pin.
     - `bump_scale` is exactly 1.0 on the tuned frame and every longer one. A held overlap
       settles at the same knock at every faster rate. `resolve(dt)` shoves
       `bump_scale(dt)` times the 62 Hz amount.
     - The bench's crowd and pairs at 144 and 165 Hz agree with 62 Hz
       within stated bounds. With the factor forced to 1.0 (the bug) the
       same check fails, so it catches the bug.
4. A cold critic pass (an attacker on the repro); fixes; results; docs.

## ENT-019: Results

### ENT-019.2: the bench, and the pass before the fix

- `tools/benchmarks/bump_rate.py`. `--markdown` prints the tables below,
  each value beside its share of the 62 Hz one. The same arguments print
  the same numbers in any process (the crowd rows match the scratch probe
  in the confirmed reading to the digit).
- The crowd: seed 35, 60 bodies in 70 px, AI inert, hero out of reach.
  Time until the total overlap is down to half, a quarter, a tenth:

  | Rate | t50 | t25 | t10 |
  |---|---|---|---|
  | 20 Hz | 0.147 (188 %) | 0.243 (194 %) | 0.442 (197 %) |
  | 30 Hz | 0.120 (153 %) | 0.211 (169 %) | 0.342 (153 %) |
  | 45 Hz | 0.093 (119 %) | 0.178 (142 %) | 0.288 (129 %) |
  | 62 Hz | 0.078 (100 %) | 0.125 (100 %) | 0.224 (100 %) |
  | 144 Hz | 0.048 (61 %) | 0.081 (65 %) | 0.170 (76 %) |
  | 165 Hz | 0.045 (57 %) | 0.074 (59 %) | 0.171 (76 %) |

- The pairs, 12 px inside their push radius: "equal" is two bears (r 22,
  w 30); "lopsided" is the troll (r 26, w 80) against the bumblebee (r 9,
  w 3), the heaviest and lightest in the crowd. Distance after 1 s, and the
  peak knock (px/s):

  | Rate | equal: distance at 1 s | equal: peak knock | lopsided: distance at 1 s | lopsided: peak knock |
  |---|---|---|---|---|
  | 20 Hz | 55.2 (76 %) | 80 (55 %) | 84.3 (80 %) | 396 (75 %) |
  | 30 Hz | 59.1 (81 %) | 100 (70 %) | 80.6 (77 %) | 396 (75 %) |
  | 45 Hz | 66.7 (91 %) | 121 (84 %) | 93.5 (89 %) | 434 (82 %) |
  | 62 Hz | 73.0 (100 %) | 144 (100 %) | 105.0 (100 %) | 532 (100 %) |
  | 144 Hz | 96.9 (133 %) | 226 (157 %) | 143.0 (136 %) | 788 (148 %) |
  | 165 Hz | 102.2 (140 %) | 241 (167 %) | 148.9 (142 %) | 836 (157 %) |

- **Read:** on a 144 Hz display a light scene shoves a pair a third
  further than at 62 Hz, and half again as fast. A heavy scene at 30 Hz
  shoves it a fifth short, and a crowd takes half as long again to come
  apart.
- **Tests:** `tests/playing/test_bump_rate.py`, 14 (the bench class is
  `integration`; the series readers and the flags are `unit`), plus
  `tests/devtools/test_tier_audit.py`, green.

### ENT-019.3: the pass after the fix

- `physics.bump_scale(dt)` and `physics.tuned_dt()`; `resolve(dt)` computes
  the share once a frame and hands it to `_bump`;
  `PlayingState._phase_update` passes its `dt`; `config.BUMP_REFERENCE_FPS`
  62. `spawn_stress.bump_times` times the pass on the tuned frame, where its
  work is the old one. `run_digest --fps N` compares a whole run by hand at
  another step. The bench gained `--unscaled` (the pass before ENT-019).
- The bench after the fix (`--markdown --rates 20 30 60 62 62.5 75 120 144
  165`), as a share of the 62 Hz value:

  | Rate | t50 | t25 | t10 |
  |---|---|---|---|
  | 20 Hz | 0.147 (188 %) | 0.243 (194 %) | 0.442 (197 %) |
  | 30 Hz | 0.120 (153 %) | 0.211 (169 %) | 0.342 (153 %) |
  | 60 Hz | 0.079 (101 %) | 0.130 (104 %) | 0.232 (103 %) |
  | 62 Hz | 0.078 (100 %) | 0.125 (100 %) | 0.224 (100 %) |
  | 62.5 Hz | 0.078 (100 %) | 0.125 (99 %) | 0.231 (103 %) |
  | 75 Hz | 0.074 (95 %) | 0.127 (101 %) | 0.244 (109 %) |
  | 120 Hz | 0.071 (90 %) | 0.122 (98 %) | 0.223 (99 %) |
  | 144 Hz | 0.071 (91 %) | 0.122 (97 %) | 0.235 (105 %) |
  | 165 Hz | 0.069 (89 %) | 0.113 (90 %) | 0.223 (99 %) |

  | Rate | equal: distance at 1 s | equal: peak knock | lopsided: distance at 1 s | lopsided: peak knock |
  |---|---|---|---|---|
  | 20 Hz | 55.2 (76 %) | 80 (55 %) | 84.3 (80 %) | 396 (75 %) |
  | 30 Hz | 59.1 (81 %) | 100 (70 %) | 80.6 (77 %) | 396 (75 %) |
  | 60 Hz | 72.1 (99 %) | 142 (99 %) | 104.0 (99 %) | 523 (98 %) |
  | 62 Hz | 73.0 (100 %) | 144 (100 %) | 105.0 (100 %) | 532 (100 %) |
  | 62.5 Hz | 73.2 (100 %) | 144 (100 %) | 105.2 (100 %) | 534 (100 %) |
  | 75 Hz | 72.4 (99 %) | 144 (100 %) | 100.1 (95 %) | 509 (96 %) |
  | 120 Hz | 72.6 (99 %) | 142 (99 %) | 100.7 (96 %) | 501 (94 %) |
  | 144 Hz | 72.5 (99 %) | 141 (98 %) | 100.3 (96 %) | 494 (93 %) |
  | 165 Hz | 72.5 (99 %) | 141 (98 %) | 99.8 (95 %) | 498 (94 %) |

- **Read:** a fast display now shoves a pair within 7 % of 62 fps (was 33
  to 67 % over), and a crowd comes apart within 11 % (was 24 to 43 %
  faster). Every row at 62 Hz and below is the before table, digit for
  digit (D5). The 60 and 62 Hz rows differ from each other because the
  step differs, not the share: both are 1.0.
- **Whole run, by hand** (`run_digest`, seeds 7 and 123, 720 frames):
  - at 62 fps, before `{7: 43ab7e5ca69932513d83, 123: ec31b46cf3c89e3e40e7}`
    and after the same;
  - at 60 fps, seed 7 matches the pin. Seed 123 does not, and did not
    before this branch either: the merge of PR #46 (CMB-010, `cf5145b`)
    moved it without a re-pin (each first-parent merge since the pin was
    digested to find it). Left to its own task, not re-pinned here.
- **Tests:**
  - `test_bump_exact.py` (8): the pass on the tuned frame and on every
    slow frame the loop makes, against the pre-RND-008.5 `resolve` and the
    pre-ENT-019 `_bump`, `==` on every knock, 1403 subtests. A 2^-40
    change in `knock_split` fails 1281 of them; the 1/62 threshold of the
    first draft fails 603.
  - `test_bump_rate.py` (29): the factor's rules (exactly 1.0 on the
    tuned frame and slower, the same held-overlap speed at every faster
    frame to 1e-9, no shove for a zero, negative or NaN frame, not moved
    by `FPS`); `resolve(dt)` on stubs, hero included; the bench at 144 and
    165 Hz inside its bounds (crowd 0.85 to 1.15, pairs 0.90 to 1.10), the
    old pass failing the same bounds, and the crowd bit for bit the old
    one at 62.5, 62, 60 and 30 Hz through the real `Enemy.update`.
  - `test_bump.py`, `test_elements_base.py`, `test_spawn_stress.py`: moved
    to `resolve(tuned_dt())`, unchanged otherwise.
  - The lane, `tests/playing tests/entities tests/combat tests/devtools
    tests/flows tests/spawn`: **1798 passed, 0 skipped**, 2543 subtests,
    9 min 47 s. The full suite was not run: the change reaches only the
    bump pass, and every module that steps a run is in this lane.

### ENT-019.4: the cold critic

One critic sub-agent, given the diff, the requirement and D5, and none of
the reasoning. Verdict **FAIL**, seven findings, all taken:

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | blocker | The loop's frames are whole ms (16/17/18 ms at the cap); the 1/62 threshold scaled every 16 ms frame by 0.9924, and every pin fed exactly 1/62 | D6: `tuned_dt()` 16 ms is the threshold and the reference; 16, 17, 18 ms pinned |
| 2 | blocker | The oracle's `_old_resolve` called the *new* `_bump`, so a change to the shove itself passed (a 2^-40 `knock_split` mutation: all green) | The oracle keeps its own verbatim pre-ENT-019 `_bump`; the mutation now fails 1281 subtests |
| 3 | should-fix | `run_digest --check` already fails on `main` (seed 123) | Traced to `cf5145b` (CMB-010); left to its own task; not cited as proof here |
| 4 | should-fix | The test cited an ENT-019.3 results section that did not exist yet; D1 claimed 1.0 by division | This section; D1 reworded |
| 5 | should-fix | `physics.py` docstring named `resolve()` and claimed the crowd times match exactly | Signature fixed; "exact" kept for the held-overlap speed, "within the bounds" for the crowd |
| 6 | nit | A negative or NaN `dt` gave a negative or NaN share | Such a frame shoves nothing |
| 7 | nit | `run_digest --fps` with no value, or 0, crashed | Refused with a message |

- The critic confirmed as clean: every `resolve` caller passes a `dt`; the
  enemy tick-LOD gets the frame's bump each frame and integrates it over
  its own span, consistent per game-second; every other `apply_knockback`
  caller is a one-shot impulse; the bench is deterministic and its teeth
  test bites; the tier audit is green; the hot path adds one `pow` a frame
  and one multiply a pair.

## ENT-019: Tasks

- [x] ENT-019.1: This block, the index row
- [x] ENT-019.2: `tools/benchmarks/bump_rate.py`, its test, the before table
- [x] ENT-019.3: The dt-scaled bump (faster frames only, D5; the 16 ms tuned frame, D6); tests
- [x] ENT-019.4: Critic pass, results, docs; ENT-019 done
