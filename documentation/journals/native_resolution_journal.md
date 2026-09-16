# Native-resolution rendering — execution journal

Branch: `native-resolution` (off `main` at `cf50aba`, 2026-09-16).

## Requirement (owner, 2026-09-16)

> Is there a way to scale the rendering resolution to keep the same
> sharpness as if the game was rendered at 1600x900, almost as if making it
> pixel perfect? Make a new branch for this, journal it in a new file,
> prepare a todo list for option 2.

Status: **review and todo only**. No code on this branch yet. The two
stage-0 decisions were taken by the owner on 2026-09-16 (see "Decisions").

---

## Why the picture is soft today

Since the window scaling work (`window_scaling_journal.md`) every frame is
drawn at the logical size -- 1600x900, or 2100x900 on a 21:9 render -- and
pygame's `SCALED` window stretches that finished image into the window on
the GPU. At any factor that is not a whole number (1.2x for a 1920x1080
window, 1.6x for borderless on the owner's 3440x1440) every output pixel is
an interpolation of source pixels. The filter cannot fix that:

| Filter | At 1.6x |
|---|---|
| linear (what ships) | every edge softened by up to one source pixel |
| nearest | every third or fourth pixel row duplicated; the duplication pattern crawls as the camera scrolls |

Only whole multiples are pixel perfect with nearest, and 3440x1440 is not a
multiple of 1600x900.

## The two real options

**Option 1 — integer scaling with bars.** Present the frame at the largest
whole multiple that fits, nearest filtered, black bars for the rest. Truly
pixel perfect and cheap (SDL's integer-scale flag back on, the nearest hint,
an Options row). On a 3440x1440 desktop the largest multiple is 1x, so the
game sits in a 1600x900 island inside the screen; it only pays on 4K, where
2x = 3200x1800. Rejected for this branch: not the picture the owner wants
on their monitor.

**Option 2 — render at the window's native resolution.** The logical
surface becomes the window size and the camera's draw-time zoom is
multiplied by the window scale: 1.5 becomes 2.4 in borderless on the
owner's monitor. The visible world extent stays exactly what it is now
(1067x600 world px on 16:9, 1400x600 on 21:9), so spawning, aiming and
every gameplay distance are untouched; but every sprite and tile is drawn
straight onto the real pixels, scaled down from its large source frame --
which is exactly why 1600x900 looks crisp today. This is what the branch is
for.

---

## Confirmed reading, and one thing to confirm

- "Sharpness as if rendered at 1600x900" = every output pixel drawn by the
  game, none interpolated by the presenter. Option 2 gives that at any
  window size; option 1 only at whole multiples.
- Gameplay integrity holds: the camera's world span is unchanged because
  the zoom scales with the window exactly as the frame used to.
- **To confirm with the owner:** the standing rule "do not alter the zoom"
  (2026-09-15). Option 2 keeps `config.CAMERA_ZOOM = 1.5` as the *design*
  zoom and the view extent it implies, but the *effective* zoom the
  renderers draw with becomes `1.5 x window scale`. The reading taken here
  is that the rule protects the view extent, not the number; the owner
  should say so before code starts.

## Decisions (owner, 2026-09-16)

1. **The zoom scales with the resolution but covers the same area.**
   `config.CAMERA_ZOOM` stays the design zoom; the effective zoom is
   computed, deterministically, from the native size:

       s    = native_height / 900                 # the UI box height is fixed;
                                                  # the width follows the aspect
       zoom = round(CAMERA_ZOOM * s * TILE_PX) / TILE_PX

   The rounding keeps `TILE_PX x zoom` whole (the tile-seam rule), so it is
   exact at 1x and 2x and within 0.3 % elsewhere: 2.40625 for 2.4 on the
   owner's 3440x1440, a view 598.4 world px tall for 600. Follow-up if the
   area must be exact at every size: drop the snap and remove the seams at
   their source by compositing each island's terrain into one surface at
   the zoom, so nothing rounds apart.
2. **The native size follows the last Options change, never a drag** --
   and **Options becomes reachable from the pause menu**, so a display
   change can happen mid-run. This reverses the 2026-09-15 rule (Options
   from the main menu only) and means every change rebuilds the live run in
   place: the display re-opens under the frozen run; the camera is rebuilt
   with the new view and zoom at the same world position; the terrain zoom
   cache and the sprite caches refill lazily, with the loading prewarm
   re-run synchronously behind a brief "Applying" frame to hide the hitch;
   the UI box and the HUD rescale. Gameplay is untouched (distance-band
   spawning, hero-relative boss ring, the same covered area); a 16:9 <->
   21:9 switch mid-run widens the view as the ultrawide decision allows.
   Options needs a way back to the pause menu and hides the Sanctuary row
   while a run is live.

## What the code already gives us

- The terrain renderer keeps a **zoom cache**: every baked island surface
  is scaled by `gm._render_zoom` on first use and cached by source id
  (`world/terrain/render.py:61`); the zoom is re-synced from the camera each
  draw (`:103`). Any zoom is already drawable.
- Sprites come through `Assets.frame / image / picture / tile(size=...)`,
  cached per size (`game/assets.py:150-238`); the renderers ask for
  `radius x zoom` sizes already.
- The sea buffer (`world/terrain/bake.py:70`) is sized from
  `SCREEN / CAMERA_ZOOM` in world px; unchanged by option 2 as long as it is
  expressed in world px and scaled at draw time like the islands.
- `Camera(view_width, view_height, zoom)` takes the view in pixels and the
  zoom separately; `world_span = view / zoom`. Passing the native size and
  the effective zoom is all it needs.
- The window manager (`game/display/window.py`) already knows the window
  size, the scale and the render aspect, and re-opens the display from
  Options. The re-open path is where the native logical size would be set.

## What has to change

1. **The logical surface = the window size.** `DisplayWindow.open` passes
   the window size to `set_mode` instead of 1600x900 / 2100x900, and the
   `SCALED` flag becomes unnecessary in windowed mode (the frame is 1:1).
   Borderless: the desktop size. A drag resize changes the native size, so
   a drag must re-open the display or, cheaper, keep `SCALED` on a fixed
   logical size *chosen at the last Options change* and accept softness
   only during a drag. Decision needed; the cheap path is proposed.
2. **Effective zoom.** `config.CAMERA_ZOOM` stays the design zoom; a
   `display.render_scale` (window px per design px) multiplies it where the
   camera is built (`PlayingState`, the loading prewarm). The tile-seam
   rule needs `64 x zoom` whole, so the effective zoom snaps to the nearest
   1/64 (2.4 -> 2.40625 on the owner's monitor): the view extent moves by
   a fraction of a percent, and the bars, if any, are a pixel wide.
3. **The UI scale.** Every screen lays itself out in absolute pixels (row
   steps of 74, 560-wide buttons, 26 px fonts, the HUD at fixed offsets;
   `ui/run_summary.py` alone has fifteen such numbers). At native resolution
   the UI box becomes `1600s x 900s`. Two ways:
   - **(a) composite**: draw the UI on a 1600x900 surface as now and
     `smoothscale` it onto the native frame each frame -- simple, but ~8-12
     ms per frame at 3440x1440 and the UI stays soft. Only for the
     measurement stage.
   - **(b) a UI scale factor** `s` threaded through the widgets: fonts
     built at `round(px x s)`, the button art scaled once per size, layouts
     multiplied by `s` at one seam (a `ui.scale` helper with `px(n)` and
     `rect(...)`), the HUD, the run-status panels, the level-up cards, the
     menus. This is the bulk of the work and the only way the UI is sharp.
4. **Bake memory and fill cost.** Island surfaces scale with the effective
   zoom squared: 2.56x at 1.6x, 5.8x at 4K. Output pixels likewise. The
   62 fps budget has to be measured before the UI work starts.
5. **Mouse.** `event.pos` and `mouse.get_pos()` arrive in native pixels; the
   UI box offset becomes `(W - 1600s) / 2` and hit rects are in scaled
   pixels -- consistent once (3b) is done. Manual aim reads the camera, so
   it is unchanged.
6. **The web profile** keeps the fixed 1280x720 canvas: `render_scale = 1`.
7. **Backdrops are the whole surface, never the box** (owner, 2026-09-16:
   the Loading screen shows as a black square on a 21:9 render). Today
   `Game._render` fills the surface with `COLOR_BG` and each box state
   fills its box with its own colour; the two match by luck for Options,
   the hero select, the rankings and the Sanctuary, and not for Loading
   (`_BG`), the end screens (`ui/end_screen.py:118`) or the menu, which
   already overrides `draw_backdrop`. The rule: a state declares its
   background (`State.backdrop`, default `COLOR_BG`) and the base
   `draw_backdrop` paints it on the **whole** surface it is handed; `draw`
   then paints only content on the box. Under native resolution the hook
   still receives the whole native surface, whatever its size, and the
   box is derived from it, so the rule carries over unchanged. Small, and
   independent of this branch: it belongs on `main`.

---

## Todo (option 2)

### Stage 0 — decide and measure (no player-visible change)

- [x] Owner confirms the reading of "do not alter the zoom": the zoom
      follows the resolution, the covered area does not (2026-09-16).
- [x] Owner picks the drag behaviour: the native size from the last
      Options change; drags stay soft until then (2026-09-16).
- [x] Owner adds: Options reachable from the pause menu, so a change
      rebuilds the live run (2026-09-16).
- [ ] A throwaway probe on the owner's machine: a run at 3440x1440 with the
      camera at zoom 2.40625 through the existing zoom cache; record
      update / render ms from `DebugOverlay.record_timing`, the bake memory,
      and a screenshot next to the 1.6x-scaled one for the sharpness
      difference. This decides whether the branch continues.

### Stage 1 — the world at native resolution (UI composited)

- [ ] `config.py`: `RENDER_NATIVE: bool` (branch default True), the
      effective-zoom snap (`ZOOM_SNAP = 1 / TILE_PX`), the design size
      renamed in comments as the *design* size (`SCREEN_*` stays the
      surface size).
- [ ] `game/display/window.py`: `render_scale` (window px per design px,
      from the window size and the design size); the logical size passed to
      `set_mode` becomes the native size; borderless uses the desktop size;
      `reopen` on an Options change only. `uibox` gets the scaled box.
- [ ] `Camera` built with the native view and `CAMERA_ZOOM x render_scale`
      snapped; the loading prewarm the same; `bake.py` sea span unchanged
      (world px).
- [ ] The UI composited: the screens keep drawing on a 1600x900 surface
      that is `smoothscale`d into the box each frame (temporary, measured).
- [ ] Tests: the camera's world span equals the design span within the
      snap tolerance at 1.0x, 1.2x, 1.6x, 2.4x; the effective zoom keeps
      `64 x zoom` whole; the window manager reports the scale; the
      fallback (dummy driver) renders 1.0x exactly as today.
- [ ] Screenshot at 1.6x borderless: world sharp, UI soft (the composite).
- [ ] The effective zoom in one place (`display.effective_zoom()`), pinned
      by a test: `64 x zoom` whole at every scale, exact at 1x and 2x,
      within 0.3 % of `CAMERA_ZOOM x s` otherwise.

### Stage 1b — Options from the pause menu (a change mid-run)

- [ ] Pause menu: an "Options" row; `OptionsState` pushed over the frozen
      run with a `return_to` so ESC / Back pop to the pause menu; the
      Sanctuary row hidden while a run is live.
- [ ] `PlayingState.on_display_changed(display)`: rebuild the camera at
      the same world position with the new view and zoom; re-sync the
      terrain zoom cache; re-run the loading prewarm synchronously behind
      an "Applying" frame; re-fetch the UI box.
- [ ] The state machine tells the run when the display re-opened (the
      hook already exists on `DisplayWindow.on_reopened`).
- [ ] Tests: a mode, resolution and aspect change with a run live keeps
      the player at the same screen fraction, the camera span at the design
      span, the enemies where they were; the Options screen returns to the
      pause menu and never to the main menu from a run.

### Stage 2 — the UI at native resolution

- [ ] `ui/scale.py`: the one seam -- `factor()`, `px(n)`, `rect(x, y, w, h)`,
      `font(role, px)` building fonts at `round(px x s)` with a per-size
      cache (fonts today are built per call: `game/fonts.py:17`).
- [ ] Widgets: `ui/widgets.py` button art scaled once per size; `ui/bars`
      meters and the medallion at `HUD_GEM_PX x s`; `ui/text.py`.
- [ ] Screens, one at a time, each with its screenshot at 1.6x: HUD,
      pause, level-up (cards and the Forge rail), run status (all panes),
      menu, character select, options, meta, rankings, game over, victory,
      loading, dev menu.
- [ ] `uibox` in scaled pixels; `translate_event` unchanged in form.
- [ ] The composite from stage 1 removed.
- [ ] Tests: each screen's layout test parameterised by `s` in {1.0, 1.6};
      hit rects scale with the layout; fonts at `s` are the requested size.

### Stage 3 — polish and the decision

- [ ] Performance at 3440x1440 and 3840x2160 against the 62 fps budget;
      the sprite and terrain caches' memory at 2.4x.
- [ ] Options: nothing new if the native size follows the existing rows;
      otherwise a "Render: native / scaled" row.
- [ ] Journal the measurements and screenshots; decide merge to `main`.

---

## Risks

- The UI refactor is wide (every screen) and is where the time goes; stage
  1 exists so the world gain is seen and measured before committing to it.
- Fill cost at 4K may not fit the budget; option 1 (integer scaling) stays
  the fallback for such screens and costs a day.
- Fonts at fractional scales hint differently from the 1600x900 ones; the
  text rules (NunitoSans titles, Fredoka body) hold, but sizes should be
  checked by eye at 1.2x and 1.6x.
- A drag resize with the proposed cheap path is briefly soft (the frame is
  presented through `SCALED` until the next Options change); acceptable,
  and stated in the Options screen if the owner wants it visible.
