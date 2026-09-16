# Native-resolution rendering — execution journal

Branch: `native-resolution` (off `main` at `cf50aba`, 2026-09-16).

## Requirement (owner, 2026-09-16)

> Is there a way to scale the rendering resolution to keep the same
> sharpness as if the game was rendered at 1600x900, almost as if making it
> pixel perfect? Make a new branch for this, journal it in a new file,
> prepare a todo list for option 2.

Status: **all stages built** (2026-09-16): the world renders at the
window's native size at the effective zoom, the interface draws at the
same scale inside its box, a display change from the pause menu rebuilds
the live run in place, and screens past the frame budget render at a
capped height. The merge to `main` is the owner's decision (stage 3).

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
- [x] A throwaway probe on the owner's machine (2026-09-16): the shipped
      run (2100x900 scaled 1.6x) against a run rendered at 3440x1440 with
      the camera at 2.40625 through the existing zoom cache -- no branch
      code, only the config knobs -- 500 frames of the hero walking on
      seed 35 in a dev run, timed around `update` and `_render`; the
      process working set before and after the run; a crop around the
      hero, the scaled one put through the presenter's linear filter.

      | | scaled 2100x900 @1.6x | native 3440x1440 @2.40625 |
      |---|---|---|
      | render ms, median / p95 | 4.9 / 5.5 | 11.9 / 12.9 |
      | update ms, median | 2.4 | 2.5 |
      | world load | 2.6 s | 2.7 s |
      | working set, menu -> run | 116 -> 574 MB | 142 -> 896 MB |
      | camera span, world px | 1400 x 600 | 1429.6 x 598.4 |
      | `64 x zoom` | 96 | 154 (whole: no seams) |

      Verdict: **the branch continues.** The native frame is crisp where
      the scaled one is soft on every edge (screenshot delivered), and it
      fits the 62 fps budget on the owner's monitor with ~1 ms to spare at
      the 95th percentile (12.9 + 2.5 of 16.1 ms). The costs are real and
      recorded: 2.4x the render time, +320 MB of caches at 2.4x, and by
      pixel count a 4K screen would land near 20 ms, over budget -- option
      1's integer scaling (or a native-size cap) stays the answer there and
      is a stage-3 item. The span differs from the design by 0.27 % from
      the seam snap, as decided.

### Stage 1 — the world at native resolution (UI unscaled in its box)

- [x] `config.py`: `RENDER_NATIVE` (True on the branch), `RENDER_SCALE`
      (native height over `UI_HEIGHT`, set by the window manager) and
      `effective_zoom()` = `round(CAMERA_ZOOM x RENDER_SCALE x TILE_PX) /
      TILE_PX`, the one place the run's zoom comes from. `CAMERA_ZOOM` is
      the design zoom and never changes.
- [x] `game/display/window.py`: `native_size()` (the desktop in
      Borderless, the clamped pick in Windowed) and `_apply_render_size()`
      set `SCREEN_*` and `RENDER_SCALE` before `set_mode`; a mode switch or
      a Resolution pick re-opens whenever the native size differs; a drag
      never does (the frame is presented scaled until the next Options
      change). The plain fallback resets to 1600x900 at scale 1. Fixed on
      the way: the ultrawide code was setting the render width even for a
      non-scalable window, which would have overridden the browser
      profile's 1280x720.
- [x] The three camera sites (`PlayingState`, the loading prewarm, the
      loading hero preview) and the sea-buffer span (`bake.py`) read
      `effective_zoom()`.
- [x] The interface: **not** composited. Drawing it unscaled in the centred
      1600x900 box costs nothing and is sharp; it is simply small on a
      large native surface until stage 2 scales it. (Chosen over the
      `smoothscale` composite from the first draft of this list.)
- [x] Tests (`tests/display/test_window.py::NativeRenderTests`, 7): the
      windowed pick and the desktop are the logical size with the right
      scale and zoom; the covered height is within 0.3 % of 600 world px
      at 1280x720, 1920x1080, 2560x1440, 3440x1440 and 3840x2160 with
      `64 x zoom` whole, and exact at 2x; a pick re-opens and a drag does
      not; a mode switch re-opens at the new size; the fallback is
      1600x900 at scale 1; the web profile keeps 1280x720. The older
      scaled-frame tests run with native rendering off.
- [x] Verified on the real window (3440x1440):

      | Step | Logical surface | `RENDER_SCALE` | zoom | camera span |
      |---|---|---|---|---|
      | boot Borderless | 3440x1440 (presented 1:1) | 1.6 | 2.40625 | 1429.6 x 598.4 |
      | Display mode -> Windowed 1920x1080 | 1920x1080 (re-opened) | 1.2 | 1.796875 | -- |
      | Resolution -> 1280x720 | 1280x720 (re-opened) | 0.8 | 1.203125 | 1063.9 x 598.4 |
      | dragged to 1500x844 | still 1280x720, presented at 1.17x | 0.8 | 1.203125 | -- |

      Update + render in the borderless run: median 14.4 ms, p95 18.2 ms
      (the probe's 11.9 / 12.9 were render alone at a quieter spot); the
      p95 is over the 16.1 ms budget on this monitor and is stage 3's
      first item.
- [x] Screenshot at 1.6x borderless delivered: world native and sharp,
      the pause dim across the whole surface, the interface small in its
      box.

### Stage 1b — Options from the pause menu (a change mid-run)

- [x] Pause menu: an **Options** row between Run status and Key layout;
      `OptionsState` is pushed over the frozen run with `in_run=True`: the
      Sanctuary row is hidden and Back / ESC pop to the pause menu.
- [x] `State.on_display_changed()` (a no-op by default) fanned out by
      `StateMachine.on_display_changed()` bottom-first from
      `Game._on_display_reopened`, which also drops the debug overlay's
      font. `PlayingState` rebuilds its camera for the new surface and
      `effective_zoom()` at the **same world centre**, rebuilds the HUD and
      its banner / prompt fonts, re-tiles the sea buffer for the new world
      span (`bake.water_buffer`, shared with the bake), and draws one frame
      of the world off screen so the terrain and sprite caches refill before
      the player sees the next one. The pause and Options screens rebuild
      their fonts. No "Applying" frame turned out to be needed: the whole
      change is ~245 ms on the owner's machine (below).
- [x] Tests (`tests/flows/test_display_change_in_run.py`, 6): the Options
      row pushes the screen over the run without the Sanctuary; Back pops
      to the pause menu and the run is still underneath; from the main menu
      the Sanctuary is there; a change to 3440x1440 rebuilds the camera at
      the same centre with the view, the zoom 2.40625 and the design
      height; fonts, the HUD and the sea follow; a change with no run is
      harmless.
- [x] Verified on the real window: a run in borderless (3440x1440, zoom
      2.40625) -> pause -> Options -> Windowed 1920x1080 (247 ms; zoom
      1.796875) -> Resolution 1280x720 (zoom 1.203125) -> ESC to the pause
      menu -> resume -> pause -> Options -> Borderless (241 ms). The world
      centre stayed at the same coordinates and the hero at exactly
      (0.500, 0.500) of the screen through every switch; the covered height
      598-601 world px each time.

### Stage 2 — the UI at native resolution

- [x] `ui/scale.py`: the one seam -- `factor()` (= `config.RENDER_SCALE`),
      `px(n)`, `size`, `rect`, `box_size()`, `int_scale(n)` for pixel-art
      scales (a x3 bar becomes x5 at 1.6x, never x4.8). Fonts go through
      `game/fonts.py`: `heading / body / mono(px)` take the *design* size
      and build the native one (`native_px`); `scaled=False` is for text
      that already follows the camera zoom (the floating damage numbers).
- [x] Widgets and helpers: the button label lifts, the fallback radii and
      edges, the ribbon fallback; the HUD's bar scale, gem size, offsets,
      timer, boss bar and the level-number nudge; `ui/text.shadowed`'s drop
      offset; `uibox` is the 1600x900 design at the factor (2560x1440 on
      the owner's desktop, 440 px margins); the cursor follows
      `RENDER_SCALE` (times what the presenter adds during a drag).
- [x] Screens, every pixel number wrapped at the point of use: pause,
      options, menu, loading, level-up (cards and the Forge rail), run
      status (the shared primitives take design px for `indent` / `step`;
      the three panes; the state's panel), the end screens and the run
      summary, the hero select (cards, ribbon, Begin, the preview zoom and
      band), the Sanctuary, the rankings, the dev menu, and the run's
      banner / notice / prompts. Module constants stay design numbers.
- [x] No composite was ever needed: the stage-1 interim drew the interface
      unscaled in the box, and stage 2 scales it in place.
- [x] Tests: `tests/screens/test_ui_scale.py` (10) at `RENDER_SCALE = 1.6`
      on a 3440x1440 surface -- the helpers, the box, fonts scaled and
      world text not, the pause buttons at 896 px centred in the box on a
      115 px step, the Options rows, the HUD cluster at its scaled corner
      and nowhere else, the level-up cards at 544x472, the menu rows, the
      end-screen buttons, and every other screen drawing without error.
      The existing screen tests run at scale 1, where every helper is the
      identity; the two level-up source pins moved to the scaled
      expressions. Found on the way: the headless dummy driver gives a
      fresh process a software-rendered scaled window, so `available`
      depended on process history once `SCREEN_*` followed the window;
      `_headless()` keeps the feature dormant under that driver, always.
- [x] Verified on the real window (3440x1440 borderless, `RENDER_SCALE`
      1.6, zoom 2.40625, box 2560x1440 at x 440): menu, options, hero
      select, the run with its HUD, pause, run status and game over
      captured from the render surface; the pause and run-status frames
      delivered.

### Stage 3 — polish and the decision

- [x] Performance at 3440x1440 with the finished build (stages 1, 1b and
      2), 150 timed frames of the hero walking on seed 35, then 60 frames
      under cProfile:

      | | median | p95 |
      |---|---|---|
      | update | 0.6 ms | -- |
      | render | 11.9 ms | 12.9 ms |

      The render is ~150 blits per frame (8 ms: the island surfaces at
      2.4x are large), the texture upload in `flip` (2.3 ms for 3440x1440),
      and the sea band's one full-screen blit (2 ms). It fits the 16.1 ms
      budget on the owner's machine with ~2.5 ms to spare at the 95th
      percentile. Memory at 2.4x was measured in stage 0 (+320 MB).
- [x] 3840x2160 would be 1.7x the pixels, ~20 ms of render: over budget.
      `config.RENDER_MAX_HEIGHT = 1440` caps the native render height at
      the window's aspect -- a 4K screen renders 2560x1440 (`RENDER_SCALE`
      1.6, zoom 2.40625) and the presenter scales it 1.5x, soft but
      playable; 0 disables the cap for a machine that can afford it.
      Pinned in `tests/display/test_window.py`.
- [x] Options: nothing new. The native size follows the existing Display
      mode and Resolution rows, and the cap is a config knob.
- [x] Journal and screenshots: this file; the stage-2 frames (pause, run
      status, menu at 3440x1440) and the stage-1b pause menu at 1280x720
      were delivered. **Merge to `main`: the owner's call.** What the
      branch changes for a player: sharp at every size (stage 0's
      comparison), Options in the pause menu, ~245 ms per display change
      mid-run, 2.4x the render time and +320 MB at 1.6x, the 4K cap.

### Loose ends noticed, not changed

- A dragged window is presented scaled (soft) until the next Options
  change, by the owner's choice. The Options screen could say so on the
  Resolution row ("Custom WxH, scaled") if it ever confuses.
- The seam snap keeps the covered height within 0.3 % of 600 world px;
  the exact-area alternative (composite each island's terrain into one
  surface at the zoom, drop the snap) stays a follow-up.
- The render's 150 blits per frame are the island and decor surfaces at
  the zoom; a per-frame cull of off-screen decor blits, or batching the
  island layers, would be where to look if a slower machine needs it.

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
