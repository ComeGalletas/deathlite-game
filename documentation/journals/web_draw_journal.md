# Web draw: the cheap wins

**ID:** RND-010 · **Systems:** RND (+ UI, BLD) · **Type:** performance ·
**Branch:** `ComeGalletas/web-draw-cheap-5be9212c` (this session's worktree,
stacked on BLD-003's `ComeGalletas/web-frame-pacing-5be9212c`, PR #48, which
sits on UI-016, PR #47) · **Started:** 2026-09-30

Follows the Chrome measurement of BLD-003.6 (`web_frame_time_journal.md`):
in the browser the draw, not the crowd, is the cost, and per-pixel alpha is
why (a full-screen `SRCALPHA` blit is 8.3 ms against 1.0 ms with constant
alpha and 0.1 ms opaque).

## Requirement (owner, 2026-09-30)

- **Objective:** make the browser's draw cheaper, starting with the cheap
  wins: the full-screen translucent overlays and the world redrawn under
  frozen overlays.
- **Details:**
  - The overlays: the hurt flash and the low-HP vignette
    (`game/states/playing/visual/rendering.py`), the buff tint (same
    file), the level-up dim (`ui/level_up.py`), the pause dim
    (`game/states/paused_state.py`), the TAB screen's dim
    (`ui/run_status/common.py`) and the end banner's dim
    (`game/states/end_banner_state.py`). Each builds or blits a
    full-screen per-pixel-alpha surface.
  - The backdrop: the level-up, pause and TAB screens freeze the run but
    redraw the whole world under themselves every frame (level-up measured
    at 19-20 fps in Chrome, 47 ms of render).
  - The terrain and scenery (review item 5) are the next step, not this one.
- **Constraint:**
  - Resolution is not a lever (owner, 2026-09-28).
  - The desktop and browser draw the same; nothing here is browser-only.
  - The overlay stays live (cards, menus, timers, the end banner's fade).

## Decisions

- **RND-010.D1 — freeze the world under frozen overlays** (owner,
  2026-09-30). Water foam and animated scenery run on a wall clock
  (`world/terrain/render.py` `seconds()`) and today keep moving under the
  pause and level-up dim. Caching the frame beneath the overlay stops that
  motion while the overlay is open. Chosen over keeping them animated.
- **RND-010.D2 — ±1 rounding is accepted for overlay alpha** (owner,
  2026-09-30). Constant alpha (`set_alpha` on an RGB surface) differs from
  today's per-pixel alpha by at most 1 in one colour channel on some pixels
  (measured on desktop pygame 2.5.2: (8,6,16) at 200 moved 1,805 of 57,600
  pixels by 1; (200,30,30) at 120 moved most pixels by 1; black at 150 is
  exact). Tests pin the new output and the ±1 bound.
- **RND-010.D3 — a new branch in this session's worktree, stacked on #48**
  (owner chose "new worktree, stacked on #48"; CLAUDE.md allows one
  worktree per session and a new branch per task, so the branch is new and
  the worktree is this session's).
- **RND-010.D4 — the frozen backdrop is opt-in per overlay.** Level-up,
  pause and TAB opt in. The dev menu does not (its actions change the run
  while it is open), nor the end banner (it toggles `update_below` between
  phases). The cache holds only the states *below* the overlay; the
  overlay's own `draw_backdrop` (the dim) is drawn every frame, cheaply,
  so an animated dim would still animate.
- **RND-010.D5 — no cache on a per-pixel-alpha target.** A cached frame is
  blitted, not redrawn; onto an `SRCALPHA` surface (offscreen tests and
  tools) that could blend differently from drawing directly, so the state
  machine draws those uncached. The screen is never `SRCALPHA`.

- **RND-010.D6 — no held input under an overlay** (builder, after the
  critic pass; within D1's "the world is frozen"). **Approved by the owner
  2026-09-30, pending proper testing** (in play: hold E into the Forge or a
  building, hold a move key into the pause, and check the caps under the
  dim are raised and show pressed again on return). The interact keycap
  (`key_marker.py`) and the opening hints (`hints.py`) draw a held key
  pressed, read live as they are drawn. Opening the Forge or a building
  with E pushes the overlay while E is still down, so the kept frame
  carried a pressed E cap until the overlay closed (the critic reproduced
  it: 3,192 bytes off a full redraw). Held input is now read only while no
  state covers the run (`playing/visual/live_input.py`, on
  `StateMachine.is_covered`); under any overlay the caps draw raised. A run
  drawn on its own, off the stack as tests draw it, still shows held keys.
  Before RND-010 a cap held under an overlay showed pressed, dimmed; that
  detail is gone.
- **RND-010.D7 — the aura shed stops under a frozen overlay** (builder,
  after critic pass 2; within D1's "the world is frozen"). The run's draw
  is not free of side effects: each draw of a body wearing an elemental
  aura rolls `run.rng` and may add a particle (`elements/layers.py`
  `_shed`). Under the old per-frame redraw, pausing piled up aura
  particles (critic probe: 3 to 142 in 120 paused frames) and used up the
  run's random stream for as long as the game stayed paused. The kept
  frame draws the run once, so neither happens any more; while auras are
  on screen a full redraw is not reproducible anyway (two in a row
  differ). The proper fix, moving the shed out of the draw into the update
  at a rate per second, would also end its frame-rate dependence (about 3x
  denser at the browser's 175 Hz) and the draw's use of the run's random
  stream; it changes elemental behaviour and the run's random sequence, so
  it is the owner's call and a requirement of its own, not RND-010.
  **Status (2026-09-30): interim, to be superseded by RND-011**
  (`aura_shed_journal.md`, another session, branched off `main`): the shed moves into the update
  on its own random stream (`"{seed}:aura_shed"`), a chance of `rate *
  dt` per body per step, the budget scaled to the step. That stops the
  shed under every frozen overlay by construction (the dev menu and the
  end banner's wait too, which D7 does not cover) and fixes gameplay's
  frame-rate dependence and `run.rng` use, which D7 does not touch. When
  both have merged, `AuraShedTests`' control (the per-frame redraw piles
  particles up) turns false; RND-011's journal says how to rewrite it,
  whichever lands second.

Found on the way: the cone draw's fallback for "pygbag / no gfxdraw"
(`game/states/playing/visual/projectiles/cone.py`) builds a full-screen
`SRCALPHA` surface per cone, but `pygame.gfxdraw` is available in the
browser (checked in Chrome, 2026-09-30), so the fallback does not run
there. Its comment is corrected, nothing else.

## Plan

1. Journal and index (this file).
2. One cached constant-alpha veil for full-screen fills (`ui/veil.py`);
   the level-up, pause, TAB and end-banner dims, the hurt flash and the buff
   tint use it or its technique; the vignette becomes four border strips.
   Tests: each against the old per-pixel-alpha result (max difference 1),
   none of the surfaces carries per-pixel alpha, the vignette's geometry.
3. The frozen backdrop in `StateMachine.draw`, opt-in by a
   `freeze_backdrop` flag on the overlay. Tests: a cached frame is
   pixel-identical to a full redraw (renderer clock pinned), the states
   below are drawn once over many frames, and the cache is dropped on
   push, pop, change, a new surface or size, a display change, and never
   kept for an `SRCALPHA` target or a non-opted overlay.
4. Measure in Chrome (the BLD-003.6 method) and on the desktop harness;
   docs; cold critic pass; close.

## Critic rubric and performance budget (frozen before building)

1. Each of the seven overlays draws within 1 per channel of the old
   per-pixel-alpha result on the same input, pinned by a test; none of the
   surfaces it blits over the whole frame carries `SRCALPHA`.
2. Under the level-up, pause and TAB screens the world is drawn once, not
   per frame; the cached frame is pixel-identical to a full redraw at the
   same instant; any stack change, surface change, size change or display
   change redraws it; the dev menu and end banner are unaffected.
3. The overlay itself stays live: selection, hover, the Forge rail, the
   end banner's fade all still change frame to frame (a test shows a
   changed selection reaches the screen under a cached backdrop).
4. Budget, measured in Chrome on the owner's machine (175 Hz display), the
   same method as BLD-003.6: the level-up screen's render at or under
   10 ms and its frame rate at or above 60 fps (was 47 ms, 19-20 fps); a
   frame with the hurt flash spends at or under 1.5 ms in
   `feedback_overlays` (was 8.9 ms).
5. No behaviour change on the desktop beyond D1's frozen background and
   D2's rounding; the touched suites pass. (D6 and D7 were recorded after
   the critic passes, as builder decisions within D1, pending the owner's
   sign-off.)
6. Every doc that states these overlays' or the backdrop's behaviour agrees
   with the code, and says what was measured versus expected.

## Tasks

- [x] RND-010.1 — journal, index entry
- [x] RND-010.2 — constant-alpha overlays and the vignette strips, tests
- [x] RND-010.3 — the frozen backdrop, tests
- [x] RND-010.4 — measure (Chrome and desktop), docs, critic, close

## Results

### RND-010.2 and .3 — tests

- `tests/render/test_overlay_veil.py` (15, unit): each converted overlay
  against the old per-pixel-alpha path on a noisy frame (the pause, TAB
  and end-banner dims exact; the level-up dim, hurt flash, vignette and buff
  tint within 1 per channel, D2), each drawn through `veil.veil` (the buff
  tint by its own opaque gradient, alpha mask 0), the vignette strips
  covering exactly `draw.rect(width=24)`'s pixels, the veil cache bounded.
- `tests/flows/test_frozen_backdrop.py` (16, integration, seed 35): the run
  drawn once over six frames under each of level-up, pause and TAB; a kept
  frame byte-identical to a full redraw; redrawn after a push, a pop, a
  display change, another target, the key-layout toggle, an explicit
  invalidation; never kept for an `SRCALPHA` target; the dev menu and end
  banner drawing the run every frame; the pause and level-up selection
  still reaching the screen. Two mutations fail it: the pause opted out (6
  failures) and the target surface left out of the key (1).
- `tests/screens/test_end_banner.py`: the hold's dim is now checked on an
  opaque white frame against the old blend. It read the dim's alpha off a
  transparent `SRCALPHA` target, where a constant-alpha blit no longer
  writes its alpha into the destination; the screen has no alpha channel.
- Suites run before the critic pass: `tests/render`, `tests/screens`,
  `tests/flows`, `tests/systems` with the tier audit (1,664 passed), and
  `tests/playing` with `tests/flows` (541 passed). The runs after the
  critic passes are under "Critic pass" below.

### RND-010.4 — measured

**Desktop** (browser profile, 1280x720, dummy driver, median of 120;
`/tmp/rnd-010/critique/desktop_overlay_bench.txt`): a level-up frame
3.17 ms redrawn against 0.83 ms kept, pause 3.10 against 0.76, the hurt
flash 0.89 ms per-pixel against 0.41 ms veiled. (A first run, not kept,
gave 3.24 / 0.83, 3.11 / 0.77 and 0.85 / 0.41; the critic's rerun gave
3.67 / 0.90, 3.63 / 0.89 and 0.96 / 0.42.)

**Chrome** (the owner's machine, 175 Hz display, the BLD-003.6 method;
`/tmp/rnd-010/critique/chrome_measurement.md`), median of 20 inside the page:

| | Before | After |
|---|---|---|
| Level-up screen `StateMachine.draw` (the rubric's render is this plus fill, debug overlay and flip, ~2.2 ms in BLD-003.6, so ~5.6 ms, within the 5-6 ms step) | 35.2 ms (world redrawn: the new overlays with `invalidate_backdrop()` before each frame; BLD-003.6's 47 ms was the old code) | 3.4 ms (kept) |
| Pause screen draw | 34.3 ms | 2.7 ms |
| Hurt flash | 7.3 ms | 1.0 ms |
| Low-HP vignette | 7.1 ms | 0.1 ms |
| `feedback_overlays` with the flash on | 8.9 ms (BLD-003.6) | 1.0 ms |
| Level-up screen, game clock | 19-20 fps | 172-175 fps (the display's rate) |

Budget, frozen before building: level-up render at or under 10 ms (3.4,
met); level-up at or above 60 fps (172-175, met); `feedback_overlays` with
the flash at or under 1.5 ms (1.0, met). Gameplay itself (29-31 fps with 5
enemies in this run) was not the target here: its draw is the terrain and
scenery, review item 5, the next requirement.

### Critic pass (RND-010.4)

One cold critic, rubric frozen above. **FAIL** on items 2 and 5 (and 6,
minor): held input in the kept frame, D6 above, reproduced through the real
E handler. Everything else held, including 12 of its own mutations; its
full run of `tests/render tests/screens tests/flows tests/systems
tests/playing` passed (2,024, 0 failures). Fixed after it:

- D6: `playing/visual/live_input.py`; `key_marker.py` and `hints.py` read
  held input only while no state covers the run. Two regression tests in
  `test_frozen_backdrop.py` (the hints on the shared run; the E cap on its
  own run, opened through the real E handler); both fail with the gate
  removed. The first version asked "is the run the top state?", which is
  false for a run drawn off the stack: `test_key_marker` and
  `test_run_hints` caught it (a held key no longer showed pressed there),
  and `StateMachine.is_covered` replaced it
  (`tests/systems/test_live_input.py` pins the four cases).
- The overlay tests now pin each veil call's colour and alpha exactly
  (the +-1 pixel bound let a drift of 1 through: the critic's alpha 199 and
  colour 201 mutations survived before).
- The desktop figures above now quote the kept evidence file.
- `ui/veil.py` `clear()`, called from `StateMachine.on_display_changed`:
  old full-frame fills are not kept across resolution changes.
- Two more full-frame-ish translucent panels moved to the veil: the TAB
  screen's panel (`ui/run_status/common.py` `draw_panel`, ~71 % of the
  frame, every frame) and the run summary's column backdrops
  (`ui/run_summary.py` `draw_column_fill`), both with parity tests. The dev
  menu's card is left as it is: its rounded, transparent corners are not a
  rectangle a veil can fill, and it is a developer screen.
- Stale docs: `buff_buildings_journal.md` (the tint is an opaque gradient
  now) and `pygbag.md` (the cone fallback does not run in the browser).

Second critic pass (fresh, same rubric): **FAIL** on items 2, 5 and 6: the
aura shed (D7 above) and stale docs. D6 held, including its mutations.
Fixed after it: D7 recorded, `AuraShedTests` (FIRE auras on 8 enemies in
view, 60 paused frames: no particles added, `run.rng` untouched, the frame
still; its control, the old per-frame redraw, piles them up), the
`key_marker.py` / `hints.py` docstrings and `key_icons_journal.md` note the
D6 exception, the test counts above.

Suite runs after the fixes: after critic pass 1, `tests/render tests/screens
tests/flows tests/playing tests/systems` with the tier audit and
`test_raf_pacing`: 2,071 passed (a first run of it caught D6's "top state"
wording breaking `test_key_marker` and `test_run_hints`, fixed by
`is_covered`). The critic's own run in pass 2: 2,161 passed across render,
screens, flows, systems, playing and devtools.

Third critic pass (fresh, same rubric): **PASS**. All six items hold; 11
of its own mutations killed; its run of `tests/render tests/screens
tests/flows tests/systems tests/playing tests/devtools`: 2,162 passed, 0
failed. Its nits applied: the rubric's item 5 notes D6/D7 pending the
owner, the Results table says how the level-up draw relates to the
rubric's render, two line wraps. Verdict log:
`/tmp/rnd-010/critique/verdicts.md`.

Self-rating: 9 / 10. The point short: D6 and D7 are builder decisions
within D1 that the owner has not yet confirmed, and D2's +-1 bound is
checked on desktop pygame 2.5.2, not on the browser's pygame-ce 2.5.7.

**Status:** done (PR open). D6 approved by the owner (2026-09-30), pending
proper testing in play; D7 interim until RND-011 lands.
