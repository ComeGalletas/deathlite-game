# Frame warm-up — journal

**ID:** RND-005 · **System:** rendering (+ SYS) · **Type:** feature ·
**Status:** proposed (next) · **Branch:** —

---

## RND-005 — Requirement (owner, 2026-09-24)

- **Objective:** Warm every animation frame the world can show before a run
  starts, so the first frame of a run scales nothing.
- **Details:** The loading screen warms the view at the start position and
  the eight views round it, at three foam phases. A real run's first frame
  lands on an arbitrary animation phase and still scales a handful of
  small foam and decor frames. The owner's call on the question
  `test_suite_review.md` left open: warm all of them.
- **Constraint:** Taken up as its own requirement because it is more than
  a documentation note (DOC-005); it is the session's next goal. The
  review that raised it thought the extra memory "likely wrong for the
  pygbag web build"; the web build is not yet considered finished, so the
  desktop build is the target.

## RND-005 — Confirmed reading

- `LoadingState._warm_steps` (`game/states/loading_state.py`) renders nine
  views into a scratch surface — the centre at the three
  `_WARM_FOAM_PHASES`, the ring at phase 0 — one view per step, inside the
  loading screen's per-frame time budget.
- Scaling is `TerrainRenderer._z_surf` (`world/terrain/render.py`): a frame
  is scaled once per render zoom and cached by its id in
  `gm._blit_cache`, cleared when the zoom changes. Warming therefore means
  calling `_z_surf` on every frame at the run's zoom — no drawing needed.
- The earlier measurement (`test_suite_review.md`, the loading-screen warm
  test): warming every animation frame is about **+190 cache entries and
  ~28 MB** on top of the ~142 MB the ring holds at zoom 1.75; the first
  draw today adds 0–5 entries, all foam or decor frames.
- `tests/flows/test_loading.py::test_the_view_is_warmed_before_the_run_starts`
  pins the renderer clock to a warmed phase today; with every frame warm it
  can take any phase.

## RND-005 — Plan

A generator of warm steps over every animation the baked world holds —
foam, room decor, obstacle skins, tree shadows, anything with more than one
frame — calling `_z_surf` on each frame at `config.effective_zoom()`, sliced
into the loading screen's existing steps so the screen stays responsive.
Measure cache entries, memory and loading time before and after; the test
asserts the first draw at any phase adds no cache entry.

## RND-005 — Tasks

*(numbered when taken up)*

## RND-005 — Results

*(filled in as the tasks land)*
