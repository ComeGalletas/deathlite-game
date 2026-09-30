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
   D2's rounding; the touched suites pass.
6. Every doc that states these overlays' or the backdrop's behaviour agrees
   with the code, and says what was measured versus expected.

## Tasks

- [x] RND-010.1 — journal, index entry
- [x] RND-010.2 — constant-alpha overlays and the vignette strips, tests
- [ ] RND-010.3 — the frozen backdrop, tests
- [ ] RND-010.4 — measure (Chrome and desktop), docs, critic, close
