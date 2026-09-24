# Frame warm-up — journal

**ID:** RND-005 · **System:** rendering (+ SYS) · **Type:** feature ·
**Status:** done (D1 open to the owner) · **Branch:** claude/sys-008-run-determinism (the
owner's choice, 2026-09-24: stay on the current branch)

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

### What a world holds, measured (2026-09-24)

Every surface the renderer passes through `_z_surf`, by kind, after the
loading screen's warm ring, at zoom 1.5 (`config.effective_zoom()`):

| kind | seed 35: unique · warmed · cold MB | seed 7 | seed 123 |
|---|---|---|---|
| water buffer | 1 · 1 · 0 | 1 · 1 · 0 | 1 · 1 · 0 |
| foam frames | 16 · 9 · 2.3 | 16 · 3 · 4.3 | 16 · 3 · 4.3 |
| **terrace bands** | 19 · 3 · **407.5** | 18 · 2 · **404.1** | 15 · 3 · **278.8** |
| bridge surfaces and shadows | 26 · 10 · 4.9 | 30 · 12 · 7.6 | 22 · 8 · 5.7 |
| decor frames (room and void scatter) | 210 · 56 · 6.7 | 229 · 53 · 7.1 | 228 · 51 · 7.5 |
| obstacle skin frames | 98 · 29 · 21.0 | 96 · 29 · 23.0 | 100 · 32 · 19.7 |
| tree shadows | 1 · 1 · 0 | 1 · 1 · 0 | 1 · 1 · 0 |

The ring leaves 95–105 MB in the cache. Warming **every surface but the
bands** is ~240 surfaces and ~35 MB, and takes **14 ms** in total on seed
35. A cold band takes **2–11 ms** to scale (six measured, 1728×576 to
3072×1792 source px) — a one-off hitch the first time a terrace comes on
screen.

- **RND-005.D1 — The bands are not warmed; the owner decides.** "All
  possible" at ~35 MB and 14 ms is the non-band set. The bands would add
  280–410 MB of scaled surfaces per world to save a 2–11 ms hitch once per
  band — measured, put to the owner, not assumed.

## RND-005 — Plan

A generator of warm steps over every animation the baked world holds —
foam, room decor, obstacle skins, tree shadows, anything with more than one
frame — calling `_z_surf` on each frame at `config.effective_zoom()`, sliced
into the loading screen's existing steps so the screen stays responsive.
Measure cache entries, memory and loading time before and after; the test
asserts the first draw at any phase adds no cache entry.

## RND-005 — Tasks

- [x] RND-005.1 — Measure what a world holds and what the ring leaves cold (above)
- [x] RND-005.2 — `world/terrain/warm.py`: every non-band scaled surface, warmed as one loading step
- [x] RND-005.3 — Tests: every non-band source is cached after loading, and a first draw at any clock phase adds nothing
- [x] RND-005.4 — Results; D1 to the owner

## RND-005 — Results

### RND-005.2 — The warm step

- `world/terrain/warm.py`: `scaled_sources(gm)` lists every surface the
  renderer scales except the bands — the water buffer, the foam frames,
  bridges and their shadows, every frame of the room and void decor, every
  frame of every obstacle skin, the tree shadows — once each by id;
  `warm(gm)` passes each through `_z_surf` at the current render zoom.
- `LoadingState._warm_steps` ends with it as one more step, "warming the
  animations", after the ring — so the zoom is already the run's.
- After loading (seeds 35 and 7): foam 16/16, bridges 26/26 and 30/30, decor
  210/210 and 229/229, obstacle frames 98/98 and 96/96 cached; the cache
  goes from ~105 MB to 140 MB (seed 35) and 126 MB (seed 7); the only cold
  surfaces left are the bands (D1). Load time unchanged within noise
  (2.7 s and 2.5 s against 3.0 s and 2.3 s before).
- `spawn_master_journal.md`'s warm-up paragraph gains a pointer to it.

### RND-005.3 — The tests

- `test_the_view_is_warmed_before_the_run_starts` no longer pins the
  renderer clock to a warmed phase: it draws the first frame at five phases
  (0, 0.13, 0.5, 2.9 and 7.77 s, most of them phases no ring pass drew) and
  asserts the cache does not grow **at all** (it allowed up to 3 before),
  and that the "warming the animations" step ran.
- `test_every_frame_but_the_bands_is_warm_before_the_run_starts`: every
  surface `scaled_sources` lists is cached after loading, and none of them
  is a band.
- **They catch its absence:** with the `warm.warm(gm)` call disabled, both
  fail — the first frame at phase 0.13 scaled 5 surfaces (118 against 113),
  and the cold list was not empty; with it restored, both pass.
- `test_suite_review.md`'s note on the old pinned test says it is unpinned.
- **Tests:** `tests/flows` + `tests/render` + `tests/world` — 893 passed,
  625 subtests, 0 skipped (9 min 52 s).

### RND-005.4 — Closed

A run's first frame now scales nothing at any animation phase: every foam,
bridge, decor, obstacle and shadow frame is warm before the run starts, for
~35 MB and ~14 ms of loading. No screenshot: nothing on screen changes, only
when the scaling happens. **Left to the owner (D1):** whether the terrace
bands should be warmed too — 280–410 MB more a world, against a 2–11 ms
hitch the first time each band comes on screen.
