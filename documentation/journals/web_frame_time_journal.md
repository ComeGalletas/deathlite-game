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
  crowd numbers, and stop the frame from being paced twice.
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
- **Double pacing.** `Game._step` calls `clock.tick(config.FPS)`. pygame-ce
  implements that as `SDL_Delay` of the rest of the frame
  (`src_c/time.c`, `clock_tick_base`, no emscripten branch). SDL2's
  `SDL_Delay` only yields in the browser when the runtime was built with
  Asyncify (`emscripten_sleep`); otherwise it falls through to `nanosleep`,
  which on the page's main thread busy-waits. pygbag then steps the loop on
  the next `requestAnimationFrame` after `await asyncio.sleep(0)`. So a
  frame that fits can be held twice: once spinning in `tick`, once waiting
  for the refresh.
- **The crowd.** `ENEMY_LIVE_CAP` went from 100 to 250 on 2026-09-16 (S12)
  and the web profile never lowered it.

The desktop numbers under the web profile (1280x720, zoom 1.25, dummy
driver, seed 35, 600 frames, `tools/benchmarks/spawn_stress` with the
profile applied by a wrapper), scaled by the factors above:

| Crowd | Desktop p50 (update + draw) | Desktop p99 | Browser estimate p50 |
|---|---|---|---|
| 58 live | 5.5 ms (3.08 + 2.45) | 14.5 ms | 12.6-20.0 ms |
| ~166 live | 9.1 ms (5.11 + 3.99) | 21.4 ms | 20.6-32.8 ms |
| ~175 live (250 asked) | 9.3 ms (5.39 + 3.96) | 17.3 ms | 20.9-33.4 ms |

These are estimates. The browser pane of the desktop app cannot measure
frame rate (it never fires `requestAnimationFrame`); a real Chrome with the
F1 overlay settles them.

## Decisions

- **BLD-003.D1 — the browser's live cap is 100** (owner, 2026-09-29).
  100 is `ENEMY_COUNT_BASE`, so a run opens with the desktop's crowd; only
  the director's growth past 100 is cut (desktop grows +5 x the
  difficulty's `enemy_count_step_scale` every 20 s up to 250). The cost,
  stated when the owner chose: the late-run difference between the
  difficulties flattens in the browser, and 100 live may still miss the
  16.7 ms budget (estimated p50 16-25 ms) until measured. The web plan's 60
  was the alternative. This relaxes BLD-001's "zero gameplay divergence"
  goal for crowd size only.
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
  there would spin the desktop at thousands of frames a second.

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

## Tasks

- [x] BLD-003.1 — journal, index entry
- [ ] BLD-003.2 — browser live cap and AI knobs in the web profile, tests
- [ ] BLD-003.3 — host-paced frames in the browser, tests
- [ ] BLD-003.4 — `spawn_stress --web`, test, measurement
- [ ] BLD-003.5 — docs, critic pass, close

Out of scope, from the same review: measure in a real Chrome (item 1),
remove the desktop draw spikes that become browser hitches (4), fewer and
larger terrain blits (5), `gc.freeze()` after loading (6).
