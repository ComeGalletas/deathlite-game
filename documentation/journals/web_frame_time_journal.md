# Web frame time: the browser's own crowd and host-paced frames

**ID:** BLD-003 · **Systems:** BLD (+ SPN, SYS) · **Type:** performance ·
**Branch:** `ComeGalletas/web-frame-pacing-5be9212c` (its own worktree,
stacked on UI-016's `ComeGalletas/ui-016-web-ui-scale-b5bf589e` at
`586e8cc`, see D3) · **Started:** 2026-09-29

Follows the web frame-time review of 2026-09-29 (below) and implements its
items 2 and 3. The earlier assessment is `../plans/web_plan.md`; the web
build's own log is `pygbag.md` (BLD-001).

## Requirement (owner, 2026-09-29)

- **Objective:** make the browser build cheaper per frame: give it its own
  crowd numbers, and stop the frame from being paced twice (the review's
  wording; at 60 Hz the cap costs nothing in the model, see "The cap
  against the refresh").
- **Details:**
  - Item 2 of the review: `config.apply_web_profile()` sets the browser's
    enemy live cap and the three AI performance knobs of `web_plan.md` §4.
  - Item 3 of the review: in the browser, `Game._step` stops asking
    `clock.tick` for a frame cap and lets pygbag's `requestAnimationFrame`
    stepping pace the loop.
- **Constraint:**
  - The desktop build does not change. `main.py --web` (the web profile on
    the desktop, for testing) keeps its frame cap, because there nothing
    else paces the loop.
  - Resolution is not a performance lever (owner, 2026-09-28): nothing here
    lowers the render size.
  - No timing assertion goes into the suite; timings live in this journal.

## The review (2026-09-29)

Why a frame costs more in the browser, measured and sourced in the session
that opened this requirement:

- The game logic is Python run by CPython compiled to WebAssembly. WASM runs
  native code about 1.45-1.55x slower on average and up to 2.5x at worst
  (Jangda et al., USENIX ATC '19). The 2026-09-03 web check (`web_plan.md`
  §1) measured the update at 30-58 ms against the ~23 ms desktop spike it
  held: **x1.30-2.52**.
- The draw measured 14-20 ms against ~4 ms on desktop: **x3.5-5.0**. Two
  likely causes, not verified: pygame-ce's SIMD blitters are probably
  missing from the wasm wheel, and the 1280x720 software surface is copied
  to the page's canvas every frame.
- One thread. pygbag's CPython has no threads, and pygame surfaces are
  main-thread only anyway (`../plans/fluidity_plan.md` §4); slicing work
  across frames is the only mechanism.
- **Two pacers.** `Game._step` calls `clock.tick(config.FPS)`. pygame-ce
  implements that as `SDL_Delay` of the rest of the frame
  (`src_c/time.c`, `clock_tick_base`, no emscripten branch). SDL2's
  `SDL_Delay` only yields in the browser when the runtime was built with
  Asyncify (`emscripten_sleep`); otherwise it falls through to `nanosleep`,
  which on the page's main thread busy-waits. Whether pygbag's runtime has
  Asyncify is not confirmed. pygbag resumes the loop after
  `await asyncio.sleep(0)` from its `requestAnimationFrame` stepper, per
  a comment in pygbag 0.9.3's `aio.run` (`support/cross/aio/__init__.py`);
  the scheduler itself lives in the runtime, not the wheel, and this is not
  measured. *Corrected by the critic pass:* the review first said a frame
  that fits is "held twice". In the model, at exactly 60 Hz it is not: if
  pygbag steps once per refresh (not measured), the steps arrive ~16.7 ms
  apart and the tick waits 0 ms. The modelled cost is on faster displays;
  see "The cap against the refresh" below.
- **The crowd.** `ENEMY_LIVE_CAP` went 100 → 150 on 2026-09-03 and
  150 → 250 on 2026-09-16 (S12, `spawn_master_journal.md`), and the web
  profile never lowered it.

The desktop numbers under the web profile (1280x720, zoom 1.25, dummy
driver, seed 35, 600 frames, `tools/benchmarks/spawn_stress` with the
profile applied by a wrapper), scaled by the factors above:

| Crowd | Desktop p50 (update + draw) | Desktop p99 | Browser estimate p50 |
|---|---|---|---|
| 58 live | 5.5 ms (3.08 + 2.45) | 14.5 ms | 12.6-20.0 ms |
| ~166 live | 9.1 ms (5.11 + 3.99) | 21.4 ms | 20.6-32.8 ms |
| ~175 live (250 asked) | 9.35 ms (5.39 + 3.96) | 17.3 ms | 20.9-33.4 ms |

These are estimates. The browser pane of the desktop app cannot measure
frame rate (it never fires `requestAnimationFrame`); a real Chrome with the
F1 overlay settles them.

### The cap against the refresh

A model, not a measurement: `python -m tools.benchmarks.raf_pacing`
(tested in `tests/devtools/test_raf_pacing.py`; its docstring states the
assumptions). A loop stepped once per `requestAnimationFrame` with
`tick(60)` inside each step, as pygame-ce's `clock_tick_base` computes it on
SDL's integer ms clock (a 16 ms frame less the whole ms since the last
tick, then `SDL_Delay`), against the same loop with no cap. `Work` is the
step's own update + draw. 6,000 steps, steady state from the second half;
the spin is the range over 20 offsets of the refresh against SDL's ms
clock (the offset never moves the fps). The table is the tool's output,
and `test_raf_pacing` fails if it stops being.

| Display | Work | Capped fps (spin ms / frame) | Uncapped fps |
|---|---|---|---|
| 60 Hz | 5 ms | 60.0 (0.0) | 60.0 |
| 60 Hz | 12 ms | 60.0 (0.0) | 60.0 |
| 75 Hz | 5 ms | 62.5 (5.0-5.6) | 75.0 |
| 75 Hz | 12 ms | 50.0 (1.0-1.5) | 75.0 |
| 90 Hz | 5 ms | 62.5 (5.7-6.0) | 90.0 |
| 90 Hz | 12 ms | 45.0 (0.0) | 45.0 |
| 120 Hz | 5 ms | 62.5 (7.0) | 120.0 |
| 120 Hz | 12 ms | 60.0 (0.0) | 60.0 |
| 144 Hz | 5 ms | 62.5 (7.1) | 144.0 |
| 144 Hz | 12 ms | 57.6 (1.1) | 72.0 |
| 165 Hz | 5 ms | 62.5 (8.2-8.4) | 165.0 |
| 165 Hz | 12 ms | 61.9 (1.9) | 82.5 |

*Corrected by the critic passes:* the first version of this table came
from a scratch model that mixed a float clock with integer ticks and
printed 59.3-61.9 fps and 4.5-8.0 ms for the 5 ms rows; the second critic's
own simulation of `clock_tick_base` gave 62.5 fps, which the checked-in
model reproduces, and the third found that one clock phase had been
reported as the range, hence the sweep. The 12 ms rows' fps and the
conclusions did not change.

So in the model the cap is free at 60 Hz (a refresh that jitters early can
cost ~1 ms; the model has no jitter). On every faster display it would
spin the page's thread, if the runtime has no Asyncify, 5.0-8.4 ms a light
frame to hold 62.5 fps, and at 75 Hz it drops a 12 ms frame to 50 fps where
the refresh gives 75. The price of no cap, in the model: on a fast display
a light scene (a menu, an empty early run) draws at the display's rate, up
to 2.6x the frames at 165 Hz (165 against 62.5), which is CPU and battery
on a laptop.
A skip-a-step cap without the spin (skip a refresh while less than some
threshold has passed) was considered and not pursued: whatever threshold
holds ~60 on one display quantises differently on the next (at 144 Hz a
15.7 ms threshold steps every third refresh, 48 fps; a 13 ms one every
second, 72 fps), so it trades the spin for a per-display tuning problem.

## Decisions

- **BLD-003.D1 — the browser's live cap is 100** (owner, 2026-09-29).
  100 is `ENEMY_COUNT_BASE`, so a run opens with the desktop's crowd; only
  growth past 100 is cut (the desktop's director grows by
  `ceil(5 x enemy_count_step_scale)` every 20 s up to 250,
  `spawn/budget.py`; what else the cap stops is below). The cost,
  stated when the owner chose: the late-run difference between the
  difficulties flattens in the browser, and 100 live may still miss the
  16.7 ms budget (estimated p50 16-25 ms then, by interpolating the review
  table's 58-live and ~166-live rows at 100; 14.7-24.0 and 20.4-32.3 ms
  in BLD-003.4's two sessions) until measured. The web plan's 60
  was the alternative. D1 relaxes BLD-001's "zero gameplay divergence"
  goal for crowd size; D2 adds AI fidelity and D4 the per-step budgets on
  fast displays (the page's refresh does pace the loop, measured in
  BLD-003.6). What
  the cap gates: every spawn through the spawn master
  (the director's companies, residents, enemy summoners' broods;
  `spawn/master.py`, "every entry point checks both per body") except the
  `cap_exempt` owners (`dev`, `dummy`, `data/enemies/spawn_tables.json`).
  Waking dormant enemies does not consult it (`spawn/population.py`, owner
  2026-09-18), so the live count can pass 100 in the browser as it passes
  250 on the desktop.
- **BLD-003.D2 — all three AI knobs** (owner, 2026-09-29):
  `ENEMY_LOD_SKIP` 2 → 3, `ENEMY_NAV_REBUILD_INTERVAL` 0.4 → 0.6 s,
  `NAV_FILL_MAX_COST` 4500 → 3500, the values and reasons of
  `web_plan.md` §4. They change how enemies are simulated (an off-screen,
  non-chasing enemy updates every third frame; routing refreshes a little
  less often; a few far enemies keep the bearing fallback), not how many.
- **BLD-003.D3 — stacked on UI-016.** PR #47 (UI-016, open) rewrites
  `apply_web_profile()` and adds `tests/web_profile.py`, which applies the
  profile and restores every upper-case `config` value. This branch starts
  from its tip so the helper covers the new values and the two do not
  conflict in the same function. The PR targets UI-016's branch and is
  retargeted to `main` when #47 merges.
- **BLD-003.D4 — host pacing is keyed on the runtime, not the profile.**
  `config.HOST_PACES_FRAMES` is set by `apply_web_profile()` to
  `sys.platform == "emscripten"`. `main.py --web` applies the same profile
  on the desktop, where `asyncio.sleep(0)` paces nothing; dropping the cap
  there would spin the desktop as fast as its frames allow (hundreds of
  frames a second or more in a light scene; an estimate, not measured).

  In the browser the trade-off in "The cap against the refresh" was taken
  by the builder, not yet by the owner, who approved item 3 on the
  review's first wording ("held twice"): in the model, no spin and the
  display's cadence, against more frames on fast displays in light scenes.
  In the model, at 60 Hz it changes nothing (a refresh that jitters early
  could cost ~1 ms; not measured).

  One more consequence, beyond CPU and battery. Whatever the game does per
  step rather than per unit of game time runs more times a second when
  there are more steps a second. The desktop's cap keeps it at most 62.5
  steps a second (the 62 fps cap truncates to 16 ms frames; a little under
  in practice as `SDL_Delay` overshoots); the page's refresh paces the
  browser's loop (measured in BLD-003.6: the menu ran 72-74 steps a second
  on a 175 Hz display), so a fast display with a light frame goes past
  that. Known per-step work, found by reading
  the code and not an exhaustive audit:
  - the population's wakes (`wake_budget` a frame, `spawn/population.py`)
    and the flow field's `ENEMY_NAV_FILL_BUDGET` relaxations a frame: fills
    land and dormant enemies wake sooner in wall time;
  - the elemental reactions (`max_reactions_per_frame`,
    `combat/elements/resolve.py`): held-over reactions land sooner;
  - the bump pass (`game/states/playing/core/physics.py`): each step adds a
    `BUMP_GAIN x penetration` impulse while the knockback decays by `dt`,
    so crowded enemies separate faster at a higher step rate. This one is
    already frame-rate dependent on the desktop below 62 fps.

  Per-game-time work does not move: the watchdog, for one, samples each
  enemy once per `sample_interval` of game time (`spawn/watchdog.py`). In a
  heavy frame, where the per-step budgets matter most, the frame's own cost
  caps the rate first. Reported to the owner with the corrected reasoning.

## Plan

1. Journal and index (this file).
2. The browser crowd: `apply_web_profile()` sets the cap and the three
   knobs; tests pin that the profile sets them, that the desktop keeps its
   own, and that a director built under the profile stops at 100.
3. Host-paced frames: `HOST_PACES_FRAMES`, `Game._step` ticks without a cap
   when it is set; tests pin both branches and the emscripten keying.
4. The stress harness takes `--web`, so the measurement above is a flag,
   not a wrapper script; measure the new profile.
5. Docs (`dist/web/README.md`, `pygbag.md`, `web_plan.md` §4,
   `config.py`), cold critic pass, close.

## Critic rubric (frozen before building)

The cold critic pass judges the diff against these, and nothing the
builder writes later:

1. Under the web profile `ENEMY_LIVE_CAP` is 100, `ENEMY_LOD_SKIP` 3,
   `ENEMY_NAV_REBUILD_INTERVAL` 0.6, `NAV_FILL_MAX_COST` 3500; without it
   every one of them keeps its desktop value, and a test fails if either
   side changes.
2. Every reader of those four values reads them at call time after the
   profile runs (none captured at import or as a default argument), shown
   by a test through the real consumer, not only by reading the constant.
3. In the browser `Game._step` calls `clock.tick()` with no cap; on the
   desktop, and under `main.py --web` on the desktop, it keeps
   `clock.tick(config.FPS)`. Both branches are tested.
4. No test leaks a changed `config` value to the tests after it.
5. Every doc that states the web profile's contents or the pacing agrees
   with the code: no stale copy of an old value.
6. The desktop's gameplay and frame pacing are byte-for-byte unchanged.

The second critic round was given item 5 with one added clause, "and no
claim stated with more certainty than its evidence", after the first round
had failed the docs on exactly that. It tightens the bar and loosens
nothing. Later rounds added two scope notes and loosened nothing either:
dated history in older journals is out of scope, and a claim counts as
hedged when its own sentence or clause carries the qualifier.

## Tasks

- [x] BLD-003.1 — journal, index entry
- [x] BLD-003.2 — browser live cap and AI knobs in the web profile, tests
- [x] BLD-003.3 — host-paced frames in the browser, tests
- [x] BLD-003.4 — `spawn_stress --web`, test, measurement
- [x] BLD-003.5 — docs, the pacing model (`tools/benchmarks/raf_pacing.py`),
  the critic passes' fixes, close
- [x] BLD-003.6 — the real-Chrome measurement (review item 1, owner
  2026-09-30), and the docs it made stale

Out of scope, from the same review: remove the desktop draw spikes that
become browser hitches (4), fewer and larger terrain blits (5),
`gc.freeze()` after loading (6). Item 1 was done as BLD-003.6.

## Results

### BLD-003.2 and .3 — tests

- `tests/flows/test_web_crowd.py` (10): both sides' values pinned; the web
  cap follows `ENEMY_COUNT_BASE`; a run booted under the profile shows each
  value where the game reads it (the director's cap, a fill's `limit`, the
  refresh timer at boot, after a round-robin tick and after a jump, a far
  idle enemy ticking 10 times in 30 frames with a 3/60 `dt`). With the four
  assignments removed from `apply_web_profile` (first version of the
  file), the five web-side tests of the time failed (`250 != 100`,
  `4500 != 3500`, `0.2 != 0.3`, `15 != 10`).
- `tests/flows/test_frame_pacing.py` (6): the flag is False on the
  desktop, True only when `sys.platform` is `emscripten`, False under the
  web profile on `win32`; `_step` asks `tick` for `62` (pinned), `0` and `60` in
  those three cases. With the old `tick(config.FPS)` the browser case
  fails (`[60, 60, 60] != [0, 0, 0]`). `sys.platform` is patched only
  while the profile is applied; the `Game` is built as the desktop one.
- `tests/flows/test_lod.py`: its update counter moved to a module-level
  `count_updates`, shared with `test_web_crowd`.
- `tests/web_profile.py` gained `config_restored()` (the snapshot alone),
  which `web_profile()` now wraps, for a test whose code applies the
  profile itself.
- `tests/conftest.py`: `WebCrowdRunTests` and `StepTickTests` boot a
  `Game` and are `integration`; the tier audit named both.

### BLD-003.4 — the measurement

`python -m tools.benchmarks.spawn_stress --web --render --live 100
--frames 600` (seed 35, dummy driver, 89 bodies at the start of timing),
against a control that applies the profile and puts the four desktop
values back (`ENEMY_LIVE_CAP` 250 included), so only the crowd settings
differ. "Update + draw" is the harness's own p50 / p90 of each frame's sum,
as printed. In the four first-session runs the printed p50 happened to
equal update p50 + draw p50 to the hundredth (a critic pass suspected a
hand sum; the harness's output in the session, not kept in the repo,
printed 6.45, 6.62, 7.04 and 7.94);
in the second session it did not, as usual.

**First session, 600 frames, two runs a side, not interleaved:**

| | Update p50 / p90 | Draw p50 | Update + draw p50 / p90 | Live at end | Browser estimate p50 |
|---|---|---|---|---|---|
| BLD-003 settings, run 1 | 3.57 / 4.24 ms | 2.88 ms | 6.45 / 7.91 ms | 100 | 14.7-23.4 ms |
| BLD-003 settings, run 2 | 3.67 / 4.40 ms | 2.95 ms | 6.62 / 7.87 ms | 100 | 15.1-24.0 ms |
| desktop settings, run 1 | 3.98 / 5.31 ms | 3.06 ms | 7.04 / 8.90 ms | 107 | 15.9-25.3 ms |
| desktop settings, run 2 | 4.52 / 5.42 ms | 3.42 ms | 7.94 / 9.10 ms | 107 | 17.9-28.5 ms |

The first version of this section read a p50 cut of 8-17 % into these
four rows by pairing run 1 with run 1. *Corrected by the second critic
pass:* all four pairings give 6-19 %, and the critic's own interleaved
600-frame re-run gave 0.5-5 % at p50. At 600 frames the two crowds end
7 apart (100 against 107), so what is left to measure is the three AI
knobs alone, and their effect is inside run-to-run noise.

**Second session, 1,200 frames, three pairs, interleaved** (web, control,
web, control, ...):

| Pair | BLD-003: update p50 / p90, draw p50, both p50 / p90 | Desktop settings: same | Both p50 | Both p90 |
|---|---|---|---|---|
| 1 | 4.81 / 6.46, 4.19, 9.06 / 11.41 ms (100 live) | 5.64 / 7.64, 4.38, 10.08 / 12.76 ms (133 live) | -10.1 % | -10.6 % |
| 2 | 4.72 / 6.08, 4.08, 8.81 / 10.61 ms (100) | 5.53 / 7.55, 4.38, 10.05 / 12.76 ms (133) | -12.3 % | -16.8 % |
| 3 | 4.73 / 6.10, 4.08, 8.81 / 10.80 ms (100) | 5.77 / 8.35, 4.60, 10.39 / 14.09 ms (133) | -15.2 % | -23.3 % |

Over 1,200 frames the enemy summons grow the control's crowd to 133 while
the cap holds the browser's at 100, so this is the cap and the knobs
together, the comparison a longer run makes. Browser estimates from the
medians of the three pairs' update and draw p50s: 20.4-32.3 ms with the
BLD-003 settings, 22.7-36.1 ms without.

What the two sessions say together:

- **The cap is the lever; the knobs are small.** With equal crowds the
  difference is noise-level; once the desktop settings let the crowd grow,
  the BLD-003 frame is 10-15 % cheaper at p50 and 11-23 % at p90 (the
  desktop-settings frame is 11.3-17.9 % and 11.8-30.5 % dearer).
- **The absolute numbers moved between sessions by more than the effect**
  (BLD-003 draw p50 2.9 ms in the first, 4.1 ms in the second, same seed
  and crowd), and the browser estimate multiplies draw by 3.5-5.0, so it
  swings with them: 14.7-24.0 ms in the first session, 20.4-32.3 ms in the
  second. Both straddle or exceed the 16.7 ms budget. A third data point
  from the last critic pass (2026-09-30, same command, 600 frames): update
  + draw p50 10.30 ms, above both sessions, so the spread is wider still.
- **Draw, not update, is most of the browser frame.** The next lever is the
  draw (review items 4 and 5), and the next measurement is a real Chrome
  with the F1 overlay (item 1), which is also the only place the pacing of
  BLD-003.3 can be seen.
- The draw p99 ranged 8.1-14.3 ms across the first session's runs (14.25
  and 8.69 ms with the BLD-003 settings, 8.10 and 8.83 without):
  first-sight blit work that the harness does not pin (review item 4).

### BLD-003.5 — critic passes, docs, close

Twelve cold critic rounds, each a fresh sub-agent with the diff and the
rubric only. Rounds 1-11 failed, round 12 passed. Items 1, 3, 4 and 6 held
in every round; item 2 failed once (round 2: an import-order gap let a
module-level capture in `state.py` or `navigation.py` pass when
`test_web_crowd.py` ran alone, fixed by importing every consumer under the
desktop config first); item 5 carried the rest. What those rounds found in
the docs, all fixed: the "held twice" premise (false at 60 Hz); a scratch
pacing model that mixed float and integer clocks, replaced by the tested
`tools/benchmarks/raf_pacing.py` whose table this journal prints and
`test_raf_pacing` checks; the knobs' gain first overstated (8-17 %, noise at
equal crowds); what the live cap gates (every spawn-master entry point bar
`cap_exempt`, not wakes); which work scales with the step rate (the
watchdog does not; reactions and the bump impulse do); and claims about
the unmeasured `requestAnimationFrame` premise without their own hedge.
Every critic ran its own mutations; all were killed. The verdict log and
the raw measurements are kept outside the repo, in
`/tmp/bld-003/critique/` (`verdicts.md`, `interleaved_1200_frames.txt`,
`raf_pacing_table.md`).

Found on the way and left for its own requirement: the bump pass's
impulse is per frame while its decay is per `dt`, so crowd separation
already depends on the frame rate (on the desktop too, below 62 fps).

Self-rating: 8 / 10. The two points short are the outcome this
requirement exists to move, still estimated rather than measured (browser
frame time needs a real Chrome with the F1 overlay, review item 1), and the
pacing trade-off, which the owner approved on the review's first, wrong
wording and has not yet re-approved on the corrected one (D4).

**Status:** done, pending the owner's re-approval of D4. The real-Chrome
measurement followed as BLD-003.6.

### BLD-003.6 — measured in Chrome (2026-09-30)

- **Requirement (owner, 2026-09-30):** run the web build in Chrome and
  measure it (review item 1).
- **Setup:** this branch at `bd7a80d`, built with pygbag 0.9.3 plus
  `--disable-sound-format-error` (see below), the pygame-ce 2.5.7 wheel
  put in `out/cdn/cp312/`, served statically by `python -m http.server`.
  Chrome through Claude in Chrome, tab visible, on the owner's machine. Its
  display refreshes at ~175 Hz: every `requestAnimationFrame` interval is a
  whole multiple of 5.71 ms. One run, seed not pinned (the page's run),
  hero Aegis on Normal; for the steady readings the hero was made
  invulnerable and non-attacking from inside the page, and for the crowd
  reading 72 enemies were seated near the hero through
  `ps.spawn.spawn_enemy`. Python ran inside the page through
  `window.python.PyRun_SimpleString`; pygbag's stdlib has no `cProfile`,
  so stages were timed by wrapping the draw functions for 20 frames and
  restoring them. Raw results: `/tmp/bld-003/chrome/results.md` (kept
  outside the repo).

**The static host works.** The page boots from a plain `http.server` once
the wheel is beside it: the fix a Vercel or Pages deploy needs, now shown
end to end. The bundle is a 19.6 MB `.apk` (44.8 MB on 2026-09-03). The
menu was up about 10 s after navigating; the loading screen took about
3 s (the web plan feared 5-10 s).

**Frame rate, from the page's refresh intervals and the F1 overlay:**

| Scene | fps | Interval p50 | Update / render (overlay) |
|---|---|---|---|
| Menu (as shipped, uncapped) | 68-74 | 11.4-17.1 ms | about 14 ms a step in all |
| Level-up screen over the run | 19-20 | 51.5 ms | 0.00 / 47.2 ms |
| Run start, 21-25 enemies, hero still | 22-23 | 45.7 ms | 4.1-4.4 / 38.7-42.7 ms |
| 99 live enemies | 25.6 | 40.0 ms | 3.8 / 38.0 ms |

**The review's estimate was wrong in both directions.** Update is about
1.05-1.1x the desktop's (3.8 ms at 99 live against 3.6 ms for 100 on the
desktop harness), not 1.3-2.5x; draw is about 11-17x (32.6-42.7 ms
against the desktop harness's 2.45-2.95 ms at 58-100 live), not 3.5-5x. So the crowd is cheap in the browser, the cap
(D1) and knobs (D2) are not what holds it back, and the draw is the whole
budget. The cap held: seating stopped at exactly 100.

**Where the draw goes** (ms per frame, 20 frames, wrappers removed after):

| Stage | Gameplay, 24 enemies | Level-up open, 21 enemies |
|---|---|---|
| Scenery sprites (trees, decor; 165 in view) | 15.3 | 17.0 |
| Ground bands | 7.3 | 8.8 |
| Water | 4.6 | 5.3 |
| Actors (hero, enemies) | 1.7 | 2.9 |
| Flat effects | 1.5 | 1.9 |
| `feedback_overlays` | 0.03 | 8.9 (hurt flash active) |
| Level-up dim backdrop / cards | - | 9.9 / 3.3 |
| HUD, ghost pass | 0.4 | 0.8 |
| **State draw** | **32.6** | **60.3** |

`Game._render`'s other parts are small: fill 0.4, debug overlay 1.3,
`display.flip` (the copy to the canvas) 0.5 ms. The review's guess that
the canvas copy costs several ms is wrong.

**Why: per-pixel alpha.** One 1280x720 blit inside the page, median of 15:

| Blit | ms |
|---|---|
| Opaque surface | 0.1 |
| Constant alpha (`set_alpha` on an RGB surface) | 1.0 |
| Per-pixel alpha (`SRCALPHA`), prebuilt | 8.3 |
| `SRCALPHA` built, filled and blitted | 8.5 |
| `fill(..., BLEND_RGB_ADD)` | 7.5 |

Per-pixel alpha is ~8x constant alpha and ~80x opaque, about 9 ns a pixel,
which fits the review's guess that the wasm wheel lacks the SIMD blitters
(still not confirmed from the wheel itself). Every full-screen `SRCALPHA`
overlay (the hurt flash, the low-HP vignette, the level-up and pause dims)
costs ~8-10 ms on its own, and the scenery, ground and water are
per-pixel-alpha sprites and bands.

**Pacing (item 3, D4), A/B on the menu** (~14 ms of work a step), by
setting `config.HOST_PACES_FRAMES` inside the page:

| | Game clock fps | Page fps | Refreshes per step (2 / 3 / 4) |
|---|---|---|---|
| Uncapped (as shipped) | 74.1 | 74.0 | 236 / 133 / 1 |
| Capped `tick(60)` | 62.5 | 62.2 | 73 / 225 / 14 |
| Uncapped again | 71.9 | 69.5 | 171 / 174 / 3 |

The premise holds: steps land on whole refreshes, and the game clock's fps
equals the page's. The capped figure is exactly the 62.5 fps
`raf_pacing` predicts. On this 175 Hz display, removing the cap is worth
12-19 % on a light screen (game clock 15-19 %, page refreshes 12-19 %);
in gameplay (40 ms frames) the cap changes nothing. Whether the capped wait spins or yields (Asyncify) is still not
measured: the rates cannot tell them apart.

**Found on the way:**

- `dist/web/build.sh` and `serve.sh` fail: pygbag refuses the MP3 music
  ("Use OGG format instead"). They have failed since the music landed
  (2026-09-16). This build passed `--disable-sound-format-error`; whether
  the MP3s play in the browser was not checked. Converting to OGG would
  change the owner's MP3 decision, so it is the owner's call.
- The bundle still carries `unused/` folders below the top level
  (`assets/effects/status/unused/`, `assets/effects/weapons/grave_totem/unused/`
  and others): `pygbag.ini` ignores only `/assets/unused`.
- The level-up screen draws the whole run beneath it every frame, dim
  included: 19-20 fps while the player picks a card.

**What moves the browser's frame, in measured order:** the scenery
sprites (15-17 ms), the full-screen `SRCALPHA` overlays (8-10 ms each when
shown), the ground bands (7-9 ms), the water (5 ms). Constant alpha
instead of per-pixel alpha for the flat overlays, and a cached frozen
backdrop behind the level-up and pause screens, are the cheap ones; the
terrain and scenery need the renderer work of review item 5 (fewer, larger,
opaque-where-possible blits). Resolution stays out of it (owner,
2026-09-28). That is a new requirement, not BLD-003. The cheap ones were done as RND-010
(`web_draw_journal.md`): the level-up screen went from 19-20 to 172-175 fps
in Chrome.
