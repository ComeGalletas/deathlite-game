# Web UI scale — the 900-row screens on the 720-row web canvas

**ID:** UI-016 · **Systems:** UI, BLD · **Type:** bug · **Branch:**
`ComeGalletas/ui-016-web-ui-scale-b5bf589e` · **Started:** 2026-09-29

Closes UI-014.D20 (`localization_journal.md`).

## Requirement (owner, 2026-09-29)

- **Objective:** make every text of the title menu, hero select, Options,
  Game Over and Victory land on the web build's 1280x720 surface, with
  nothing overlapping.
- **Details:** the web profile (`config.apply_web_profile`) draws at
  1280x720 with `RENDER_SCALE 1.0`, but those screens are laid out in
  design pixels for 900 rows, so their lower buttons, hints and the menu's
  summary land below 720 or onto each other. The fit harness from UI-014.11
  (`tests/screens/fit_harness.py`, `fit_scenes.py`, `test_fit.py`) measures
  it and lists the screens in `WEB_UNFIT`; each fixed screen leaves that
  list.
- **Constraint:** check first that pygbag's canvas really is 1280x720. The
  1600x900 layout stays byte-identical (`test_english_layout.py` and the
  per-screen tests pin it). The web world view does not change.

## Confirmed reading

- **The canvas is 1280x720.** pygbag 0.9.3 (`.venv`) defaults the
  framebuffer to `DEFAULT_WIDTH = 1280`, `DEFAULT_HEIGHT = 720`
  (`pygbag/app.py:90`); `dist/web/build.sh` passes no `--width` /
  `--height`; the cached template fills `fb_width` / `fb_height` from them
  and the last build's `build/web/index.html` reads `Screen : 1280x720`,
  `fb_width "1280"`, `fb_height "720"`. `apply_web_profile` sets
  `SCREEN_* = 1280, 720`, and `DisplayWindow.open` (not scalable in the
  browser) forced `RENDER_SCALE = 1.0`.
- **The scale path already exists.** Native-resolution rendering sets
  `RENDER_SCALE = h / UI_HEIGHT` (1.6 at 1440 rows) and every screen lays
  out through `ui/scale.py` and `game/fonts.py` at that factor. The web
  surface is the same case at `720 / 900 = 0.8`: the 1600x900 layout at 80%,
  which fits by construction.

## Decisions

- **UI-016.D1 — scale the web interface by 0.8, not re-lay five screens**
  (owner, 2026-09-29). The web profile sets `RENDER_SCALE = SCREEN_HEIGHT /
  UI_HEIGHT`. Every screen, the in-run HUD included, becomes the design
  layout at 80%; text and the 64 px button art are resampled 20% smaller.
  A per-screen re-layout was the alternative: sizes kept at 1.0, but five
  screens of their own layout math and the same problem waiting for the
  next screen drawn for 900 rows.
- **UI-016.D2 — the web `CAMERA_ZOOM` is compensated so the effective zoom
  stays 1.25** (owner, 2026-09-29, relayed by the UI-014 session). The
  world draws at `config.effective_zoom() = CAMERA_ZOOM x RENDER_SCALE`
  snapped to 1/TILE_PX, so a 0.8 scale alone would shrink the web world
  view to zoom 1.0. The owner allows the web profile's `CAMERA_ZOOM`
  constant to change so the effective zoom does not: `1.25 / 0.8 = 1.5625`,
  `64 x 1.5625 x 0.8 = 80` px per tile, whole, as today (the seam rule in
  `apply_web_profile`'s docstring). Pinned by a test that
  `effective_zoom()` under the web profile is exactly 1.25.
- **UI-016.D3 — the browser window derives its scale, it does not force
  1.0.** `DisplayWindow.open`'s not-scalable branch set `RENDER_SCALE =
  1.0`, which would undo D1 after the profile ran. It now derives the scale
  the same way native rendering does, `SCREEN_HEIGHT / UI_HEIGHT`: 0.8 in
  the browser, 1.0 for every desktop design size (all 900 rows).
- **UI-016.D4 — the fit test draws its 1280 scenes under the real web
  profile.** Until now the 1280 scenes were a 1280x720 surface at scale
  1.0, which after D1 is no configuration the game runs in. They are drawn
  inside `apply_web_profile()` (restored after), with the in-run scenes on
  a run booted under it, so the fonts the run keeps are the web profile's.
  The other tests that described themselves as "the 1280 web profile" are
  moved onto it the same way (`tests/web_profile.py: web_profile()`), with
  one kind of exception: two tests existed to drive the Build pane's
  title step-down and the run summary's subheader trim, which only the
  old 1280-at-1.0 surface was narrow enough to reach. At 0.8 the fonts
  shrink with the layout and both fit whole. Those two keep the narrow
  surface, now named as a stress case and no shipped configuration, and a
  new test pins that the web profile shows the subheader whole in both
  languages.
- **UI-016.D5 — the web exemption goes, not just its entries.** With all
  13 `WEB_UNFIT` screens fitting at 0.8, the exemption (`WEB_UNFIT`,
  `web_held`, `web_exempt`, `spanish_adds_below` and their self-tests)
  would be machinery with nothing to exempt. It is removed; both sizes are
  held to one rule in `test_every_screen_fits_at_both_sizes`. A screen that
  one day misfits at 1280 fails like one that misfits at 1600.

## Plan

1. Journal and index (this file).
2. The web profile scales the interface by 0.8 and compensates the camera
   zoom; the window derives its scale; a test helper applies the web
   profile and restores every config value it touched, so tests stop
   hand-listing (and missing) the values; the effective-zoom pin.
3. The fit harness draws the 1280 scenes under the web profile; the fixed
   screens leave `WEB_UNFIT`; the tests that claim the web profile use it.
4. Screenshots of the web screens; docs (`pygbag.md`, `ui/scale.py`,
   `config.py` docstrings); close D20.

## Tasks

- [x] UI-016.1 — journal, index entry
- [x] UI-016.2 — web profile at scale 0.8, compensated zoom, window scale, test helper, zoom pin
- [x] UI-016.3 — fit harness under the web profile, `WEB_UNFIT` emptied, web-profile tests moved on
- [ ] UI-016.4 — screenshots, docs, D20 closed
