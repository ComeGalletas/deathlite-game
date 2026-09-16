# Dynamic window scaling — execution journal

## Requirement (owner, 2026-09-15)

> Review and propose a way to implement dynamic window scaling, using
> arbitrary screen resolutions and sizes to fit many screens, from fullscreen
> (needs to be only borderless windowed) and windowed. Consider a min and max
> resolution and make sure the integrity of the gameplay remains the same. Do
> not alter the zoom. Confirm, don't touch code.

Status: **built** (2026-09-15, "start with the window scaling changes"):
the scaled window, windowed / borderless, the Resolution row, the fit rule,
the saved settings and the cursor scale -- see "Built" at the end of the
proposal. The ultrawide render extent (its own section below) is confirmed
but not built. Everything here was checked against the code and against
pygame 2.6.1 / SDL 2.28.4 on the owner's machine with throwaway probe
scripts (kept out of the repo).

---

## Confirmed reading

| Requirement | What exists today | What the proposal does |
|---|---|---|
| Arbitrary window sizes, many screens | The window is a fixed 1600x900 (`config.SCREEN_WIDTH/HEIGHT`) opened once in `Game._open_window` (game/game.py:149) with `SCALED \| DOUBLEBUF`, `vsync=1`. It is not resizable and there is no fullscreen. On a desktop smaller than 1600x900 pygame opens the window *larger than the screen*, off-centre (a probe with a logical size bigger than the desktop opened at position (-224, -324)) — a 1366x768 laptop cannot play windowed today. | The window becomes any size the player wants. The game keeps drawing to a fixed 1600x900 **logical** surface that SDL scales into the window, aspect ratio preserved with black bars. First launch fits the window to the desktop; later launches restore the saved size. |
| Fullscreen = borderless windowed only | Nothing. | pygame's `display.toggle_fullscreen()` on a `SCALED` window sets `SDL_WINDOW_FULLSCREEN_DESKTOP` (probe: window flags 0x1001) — a borderless window at the desktop resolution, no display-mode switch. The exclusive `pygame.FULLSCREEN` mode is never requested on its own. |
| Windowed | Fixed size. | Resizable by dragging, plus an Options **Display mode** row (Windowed / Borderless) and a **Resolution** row that is live in Windowed and greyed out at the desktop size in Borderless. |
| Min and max resolution | None. | `WINDOW_MIN = (800, 450)` (half the logical size; below that the 16 px hint text is unreadable, and the floor exists only so a dragged window stays grabbable). The maximum is the desktop: a saved size larger than the usable desktop is clamped, and fullscreen is the true ceiling. Supported screen range for the fit rule and the manual checklist: 1280x720 up to 3840x2160. |
| Gameplay integrity | The visible world span is `SCREEN / CAMERA_ZOOM` = 1066.7 x 600 world px. That figure feeds the terrain bake span (world/terrain/bake.py:70), the spawn ring and cull pad, the boss AI's half-diagonal (config.py:727), the HUD layout, the menu hit rects and every screen test. | All of it reads the logical size, which never changes, so nothing about what the player sees, where enemies spawn, or where clicks land moves by a single world pixel. |
| Do not alter the zoom | `CAMERA_ZOOM = 1.5`, tile step 96 px. | Untouched. Scaling happens after the frame is finished, on the GPU texture, outside the camera. |

Two things the request leaves open, decided here (the owner can overturn
either):

- **The render target stays 1600x900 and the window gets bars.** The
  alternative — render at the window's native size with the same zoom — would
  show a 2560x1440 player 1.6x more world than a 1600x900 player and a laptop
  player less. That is exactly the integrity break the request rules out, so
  it is not proposed. On 16:10 or ultrawide screens the bars are the price;
  on the owner's 3440x1440 they are 440 px pillars each side in fullscreen.
- **The feature is desktop-only.** The browser build's canvas belongs to
  pygbag (`apply_web_profile`); the window manager is dormant there.

---

## What the probes established

pygame 2.6.1 (SDL 2.28.4) on Windows 11, the owner's 3440x1440 monitor at
125% display scaling. Each line is something the design depends on.

| # | Finding | Consequence |
|---|---|---|
| 1 | `set_mode((1600, 900), SCALED \| DOUBLEBUF \| RESIZABLE, vsync=1)` opens. The display surface stays 1600x900 and is the **same object** through every resize and fullscreen toggle. | States keep drawing to `game.screen`; no re-fetch after a mode change. |
| 2 | pygame pins the window's minimum size to the logical size (1600x900), so the window cannot be made smaller by dragging or by code. `SDL_SetWindowMinimumSize` lifts it. | One SDL call at open, or small screens stay unplayable. |
| 3 | In windowed mode pygame turns on SDL's **integer scale** flag. A 1920x1080 window then shows the 1600x900 image centred and **unscaled**, and the mouse maps offset-only (a click at 25% across reported x=320 instead of 400). Fullscreen has the flag off and scales freely. `SDL_RenderSetIntegerScale(renderer, 0)` fixes windowed mode: 1.2x, 0.75x and a 4:3-shaped 1400x1000 window all scale exactly, letterboxed, and the mouse lands within 1 px of the expected logical point. pygame re-asserts the flag when toggling back from fullscreen. | This one call is the heart of the feature. Re-apply it after every toggle and size change (idempotent). |
| 4 | `toggle_fullscreen()` gives `FULLSCREEN_DESKTOP`; the viewport pillarboxes (274 logical px each side at 1.6x on 3440x1440). Booting straight into `SCALED \| FULLSCREEN` also gives desktop fullscreen, and toggling out returns a 1600x900 window. | Saved mode can be applied at boot; no second window. |
| 5 | A **second** `set_mode` that adds `FULLSCREEN` fails with `failed to create renderer`. | One `set_mode` per process. All switching goes through `toggle_fullscreen()` and the window size. |
| 6 | pygame forces the scale filter to `nearest`. Setting `SDL_RENDER_SCALE_QUALITY=linear` in the environment before `set_mode` wins. | At 1.2x nearest duplicates every fifth pixel row (uneven tiles, scroll shimmer); linear is proposed. |
| 7 | Without DPI awareness SDL reports this desktop as **2752x1152** (3440x1440 / 1.25) and Windows re-stretches the whole output afterwards. `SDL_WINDOWS_DPI_AWARENESS=permonitorv2` before `pygame.init()` makes SDL see 3440x1440 and fullscreen present at native pixels. | Proposed on, behind a config flag. Desktop sizes are then physical pixels, so the fit rule accounts for the DPI factor. |
| 8 | With the flag from #3 off, mouse events and `mouse.get_pos()` are already in logical coordinates in every window shape and in fullscreen; a cursor in the pillar clamps to the edge. | `event.pos` in `ui/mouse.py` and the manual aim's `mouse.get_pos()` (game/states/playing/core/state.py:475) need no translation. |
| 9 | A resize posts `VIDEORESIZE`, `WINDOWRESIZED` and `WINDOWSIZECHANGED`. | One handler remembers the windowed size. |
| 10 | `ctypes.CDLL("SDL2.dll")` after `pygame.init()` binds the SDL already loaded by pygame (Windows returns the loaded module by name), so it works from the PyInstaller onedir without a path. | The shims need no packaging change. |
| 11 | The hardware cursor (`ui/mouse.install_cursor`) is in screen pixels and does not follow the scale. | Re-install it at `UI_CURSOR_SCALE * window_scale` on each size change. |
| 12 | (found while building) On the way **out** of fullscreen pygame re-pins the window minimum to the logical size: right after the toggle a 1280x720 request came back as 1600x900 while 1920x1080 went through. | The floor is lifted again before every programmatic size (`DisplayWindow._apply_windowed_size`), not only at open. |
| 13 | (owner's crash report, 2026-09-15: "game crashes when trying to change resolutions") An access violation in pygame's event pump one frame after a Resolution step, on a fresh save and not on a saved one -- with the cursor reinstall, the save write, the render, garbage collection and each SDL shim ruled out in turn. The trigger was every shim creating a throwaway `pygame._sdl2.video.Window.from_display_module()` wrapper: pygame stores a pointer to the wrapper in the SDL window's data and resolves window events through it, so a dropped wrapper leaves that pointer dangling and the next resize event reads freed memory; whether that faulted depended on heap layout, which is why a dict entry more or less in the save decided it. | `native._window()` makes the wrapper **once** and keeps it for the process, remaking it only if its window is gone. Pinned by `tests/display/test_native.py`. |

---

## Proposal

### 1. Config (`game/config.py`, Display section)

`SCREEN_WIDTH` / `SCREEN_HEIGHT` keep their names (43 references, tests
included) and gain a comment: they are the **logical** render size, not the
window. New constants, all read at call time:

| Constant | Value | Role |
|---|---|---|
| `WINDOW_MODE_DEFAULT` | `"windowed"` | `"windowed"` or `"borderless"` (desktop fullscreen). |
| `WINDOW_MIN` | `(800, 450)` | Floor for a dragged or saved window. |
| `WINDOW_FIT_FRACTION` | `0.90` | First-launch window: no taller than this share of the usable desktop. |
| `WINDOW_RESOLUTIONS` | `((1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (3200, 1800), (3840, 2160))` | Candidates for the Options "Resolution" row, filtered at run time to those that fit the usable desktop and clear `WINDOW_MIN`. |
| `WINDOW_RESIZABLE` | `True` | `apply_web_profile()` sets it `False`. |
| `WINDOW_DPI_AWARE` | `True` | Sets `SDL_WINDOWS_DPI_AWARENESS=permonitorv2` before init. |
| `WINDOW_SCALE_FILTER` | `"linear"` | Sets `SDL_RENDER_SCALE_QUALITY`. |

### 2. New package `game/display/` (one module per concern)

- `window.py` — `DisplayWindow`, owned by `Game`. `prepare()` sets the
  environment hints (with `setdefault`, so a player's own env wins) and must
  run before `pygame.init()`. `open()` does the single `set_mode` with
  `SCALED | DOUBLEBUF | RESIZABLE` (+ `FULLSCREEN` when the saved mode says
  so), vsync first and the plain fixed window as the fallback exactly as
  today; then lifts the minimum size, turns integer scaling off, applies the
  saved or fitted size, installs the cursor at the right scale. Also:
  `toggle_fullscreen()`, `set_windowed_size(w, h)`, `resolution_entries()` /
  `apply_resolution(i)`,
  `handle_event(event)` (a drag resize → remember the windowed size when
  not borderless, re-apply the integer-scale flag, rescale the cursor),
  `scale` (window over logical), `settings()` / `restore(settings)`, and
  `available` — `False` when `SCALED` was refused (dummy driver, some remote
  desktops) or on emscripten, in which case every method is a no-op and the
  Options rows read "unavailable".
- `native.py` — the only module that touches SDL directly: `ctypes` shims
  `set_minimum_size`, `set_integer_scale`, `usable_bounds`, `display_dpi`,
  plus `pygame._sdl2.video.Window.from_display_module()` for size and
  position. Every function returns `bool` and swallows failure; a missing
  symbol degrades that one capability, never the window.
- `fit.py` — pure arithmetic, no pygame: `fit_window(desktop, usable,
  dpi_scale, saved, minimum, fraction) -> (w, h)` and
  `letterbox(window, logical) -> (scale, offset)`. Fully unit-testable.

`Game.__init__` calls `prepare()` before `pygame.init()` and `open()` where
`_open_window` is called now; `_open_window` becomes a thin delegate so
`tests/flows/test_window.py` keeps its shape. `Game._process_input` routes
window events to the manager. There is no hotkey: the owner ruled
(2026-09-15) that the Options screen is the only place display settings
change.

### 3. Fit rule (first launch)

1. `desktop` = `pygame.display.get_desktop_sizes()[display]`; `usable` = the
   SDL usable bounds (taskbar excluded) or `desktop x 0.95` if the shim
   fails.
2. `preferred` = logical size x DPI factor, so a 1600x900 window looks the
   same physical size as today's DPI-unaware window.
3. Shrink `preferred` to fit `usable x WINDOW_FIT_FRACTION` keeping 16:9.
4. Never below `WINDOW_MIN`.

| Desktop (scaling) | Window on first launch | Scale |
|---|---|---|
| 1366x768 (100%) | 1152x648 | 0.72 |
| 1920x1080 (100%) | 1600x900 | 1.00 |
| 2560x1440 (100%) | 1600x900 | 1.00 |
| 3440x1440 (125%, the owner's) | 2000x1125 | 1.25 |
| 3840x2160 (150%) | 2400x1350 | 1.50 |

A saved size is clamped to `[WINDOW_MIN, usable]` when applied, not when
loaded, because the desktop can change between sessions.

### 4. Borderless and the controls

- `toggle_fullscreen()`; on the way back to windowed, re-apply the
  integer-scale flag, re-assert the remembered windowed size, rescale the
  cursor, persist the mode.
- **No hotkey and no pause-menu row** (owner, 2026-09-15): the Options
  screen, reached from the main menu, is the only place these settings
  change. A consequence worth its own line: a display change can never
  happen during a run, so the render width is fixed for the length of a run
  and nothing in the run has to survive an aspect change.
- Options screen: two rows above "Sanctuary" (owner's layout, 2026-09-15,
  after a first draft with a single Resolution row).
  - **Display mode** — Windowed / Borderless. Left/Right or ENTER switches.
    Borderless toggles desktop fullscreen and remembers the windowed size;
    Windowed restores it.
  - **Resolution** — in Windowed, Left/Right cycle the entries of
    `WINDOW_RESOLUTIONS` that fit this desktop and set the window to the
    pick; a drag-resized window shows as "Custom 1734x975" until a listed
    entry is picked. In Borderless the row reads the desktop resolution
    (e.g. "3440x1440"), is drawn in `COLOR_TEXT_DIM`, and the cursor skips
    it. The two modes are told apart at a glance by which row is live.
  - Same immediate-persist contract as volume and the key layout.
- Pause menu: unchanged. (A Display mode row was proposed and withdrawn the
  same day: Options only.)

### 5. Cursor

`install_cursor(assets, scale=config.UI_CURSOR_SCALE * window.scale)` is
re-run on every size change and toggle: one `smoothscale` of a 22x30 image.
Without it the arrow is a third of its intended size at 3440x1440.

### 6. Persistence

`settings["display"] = {"mode": "windowed" | "borderless", "window": [w, h]}`,
normalised in `save._coerce` the way `key_layout` is (unknown mode → default,
non-integer size → dropped). The windowed size is kept while in Borderless, so F11 or the Display mode
row from a 1920x1080 window returns to 1920x1080 and not to a default. Written on toggle
and resolution change; a drag resize is written once at quit, not per event.

### 7. Untouched

`CAMERA_ZOOM`, `Camera`, the loading-state prewarm, `bake.py`, the HUD and
every state's layout, `apply_web_profile` (it only gains
`WINDOW_RESIZABLE = False`), the packaging spec.

### 8. Tests (all `unit`, dummy driver)

- `tests/display/test_fit.py` — the table above, the DPI factor, the saved
  size clamped both ways, the floor, the letterbox offset for a 4:3 window
  and for the owner's ultrawide.
- `tests/display/test_settings.py` — coercion of the display block.
- `tests/display/test_window.py` — `DisplayWindow` with `pygame.display` and
  `native` mocked: toggle persists the mode and re-applies the flag; a
  size-changed event updates the windowed size only when windowed; the cursor
  is reinstalled at the new scale; the fallback path sets `available=False`
  and never calls a shim.
- `tests/flows/test_window.py` extended: the first `set_mode` asks for
  `RESIZABLE`; the fallback still returns the logical size.
- Manual checklist with a real window (no automated driver scales): a
  1366x768 laptop windowed, 1080p at 1.0x, ultrawide fullscreen bars, a drag
  resize, Alt+Enter twice, one Options button clicked at 1.2x and in
  fullscreen, one manual-aim shot at each.

### 9. Risks and notes

- `pygame._sdl2.video` and the `ctypes` shims are outside pygame's public
  API. They are isolated in `native.py`, each with a fallback that leaves a
  working fixed window, and pygame stays pinned at 2.6.1 in the packaging.
  pygame-ce would expose the minimum size natively, but the integer-scale
  call would still be needed, so switching flavour buys nothing here.
- Bars are black (SDL's clear colour); `COLOR_BG` fills only the logical
  surface. Acceptable; a matching bar colour is one `SDL_SetRenderDrawColor`
  if ever wanted.
- Linear filtering softens exact 2x very slightly. Switching to nearest at
  whole-number scales would need the texture's scale mode, which pygame does
  not expose; deferred.
- The DPI hint is Windows-only and harmless elsewhere.
- Performance: `SCALED` already uploads the frame as a texture every frame;
  scaling it to any window size is GPU work and free at these sizes.

---

## Decisions the owner is asked to confirm

1. Render target fixed at 1600x900 with bars, never native-size rendering.
2. `WINDOW_MIN = 800x450`; the desktop is the maximum; 1280x720 → 3840x2160
   is the supported screen range.
3. Linear scale filter.
4. DPI awareness on by default.
5. Display mode and Resolution rows in Options and nowhere else: no hotkey,
   no pause-menu row — **confirmed by the owner 2026-09-15**.
6. First launch opens windowed and fitted (not fullscreen).

---

## Built (2026-09-15)

- `game/config.py`: the `SCREEN_*` comment now says "logical size"; the
  `WINDOW_*` constants as in §1 minus the hotkey; `apply_web_profile` turns
  `WINDOW_RESIZABLE` off.
- `game/display/fit.py` (pure arithmetic), `native.py` (the four SDL
  shims through `ctypes`, each with a fallback), `window.py`
  (`DisplayWindow`), `__init__.py`.
- `game/game.py`: `DisplayWindow.prepare()` before `pygame.init()`; the
  save is read *before* the window opens (its mode and size shape it);
  `self.display.open()` replaces the old `_open_window` (kept as a delegate
  for the tests); a drag resize is routed to the manager from
  `_process_input` and written once at quit (`_close`); `persist` writes
  `settings["display"]`; the cursor is reinstalled at
  `UI_CURSOR_SCALE x window scale` whenever the scale changes.
- `game/save.py`: `_coerce` keeps a known mode and a plausible size, drops
  the rest.
- `ui/mouse.py`: `install_cursor(assets, scale=None)`.
- `game/states/options_state.py`: the Display mode and Resolution rows;
  the cursor skips the Resolution row in Borderless and both rows when the
  scaled window was refused; the skipped row is drawn in `COLOR_TEXT_DIM`.

### Verified on the real window (3440x1440 at 125 %)

Booted the actual `Game` with a saved 1920x1080 windowed setting and drove
the manager as the Options rows do, grabbing the OS window with GDI so the
pictures show the scaled window, not the logical surface:

| Step | Window | Scale | Resolution row |
|---|---|---|---|
| saved 1920x1080, windowed | 1920x1080 | 1.200 | `1920x1080` |
| Display mode -> Borderless | 3440x1440, fullscreen-desktop | 1.600 | `3440x1440`, dim |
| back to Windowed | 1920x1080 | 1.200 | `1920x1080` |
| Resolution row -> 1280x720 | 1280x720 | 0.800 | `1280x720` |
| dragged to 1734x975 | 1734x975 | 1.083 | `Custom 1734x975` |
| quit | -- | -- | save holds `[1734, 975]` |

The Resolution list on this desktop: 1280x720, 1600x900, 1920x1080,
2560x1440. Screenshots delivered: the Options screen at 1920x1080 (1.2x),
in Borderless on the ultrawide (440 px pillars), and at 1280x720.

### Tests

`tests/display/test_fit.py` (the fit table, clamps, the letterbox, the
Resolution list), `tests/display/test_window.py` (`DisplayWindow` with the
shims and pygame's display calls mocked: open, refused, saved borderless,
mode switches, the Resolution steps from a listed and a custom size, drag
events, the floor lifted before every size, the settings round trip
through `save._coerce`), `tests/flows/test_window.py` (+2: the dormant
manager under the dummy driver; the scaled window asks for `RESIZABLE`),
`tests/screens/test_options.py` (+5: the rows skipped without a scaled
window, mode switch and resolution step persisting, the row skipped and
reading the desktop in Borderless, the save carrying the block).

## Progress

- [x] Config constants and the `SCREEN_*` comment
- [x] `game/display/` — `fit.py`, `native.py`, `window.py`
- [x] `Game` wiring: prepare before init, open, events (no hotkeys: Options only)
- [x] Save coercion of `settings["display"]`
- [x] Display mode and Resolution rows in Options
- [x] Cursor rescale
- [x] Web profile flag
- [x] Tests listed in §8
- [x] Manual checklist and the screenshots (windowed 1.2x, borderless ultrawide, 1280x720)

---

## Ultrawide render extent (owner, 2026-09-15) — under consideration

> Expand the game window display — not these resolutions, the size the game
> is actually rendered — to allow for ultrawide screen resolutions. 21:9
> resolutions can be selected in windowed mode too. The game should only
> change visually: extend the game display to cover the sides for the
> ultrawide size. The camera should naturally cover this extended space, and
> because the spawn master can spawn enemies anywhere it should affect the
> gameplay. HUD elements must remain static as a 16:9 resolution.

Status: **built** (2026-09-15, "start with the ultrawide changes"); see
"Built" at the end of this section. It relaxes the "identical gameplay at
every size" rule above for ultrawide players. The owner's rulings on the
open points are folded in below.

### Reading

- The logical render surface is no longer fixed at 1600x900. Its height
  stays 900 and its width follows the aspect ratio: 16:9 → 1600, 21:9 →
  ~2100 (the owner's 3440x1440 is 2.39:1 → 2150). `CAMERA_ZOOM` stays 1.5,
  so the visible world grows from 1067x600 to ~1400x600 world px. Nothing is
  stretched; the extra width is more world.
- The Windowed resolution list gains 21:9 entries (2560x1080, 3440x1440,
  5120x2160), filtered by the desktop as before. Borderless on an ultrawide
  desktop renders at the desktop's aspect.
- The camera covers the wider span on its own (`Camera(view_width=...)`).
- Gameplay may change on ultrawide: `spawn/placement.py` places enemies
  outside `host.visible_rect()` (the OFFSCREEN tier), so a wider view pushes
  horizontal spawns further out and the player sees more. Accepted by the
  owner as the natural consequence.
- The HUD is laid out in a centred 1600x900 box and never drifts to the
  wider edges. Every other element stays as it is today: menus and the
  overlay panels keep their layout, centred in the same box (owner,
  2026-09-15).
- **The dim layer covers the whole wide surface.** The in-run overlays --
  pause (`game/states/paused_state.py:90`), run status
  (`ui/run_status/common.py:114`), level-up (`ui/level_up.py:65`) -- each
  size their black translucent layer from the surface they are handed. With
  the UI box a subsurface, the dim must be painted on the **full** surface
  first and only the panel on the box, or the world would stay bright in the
  side margins. The owner asked for this to be verified; it is a test (below)
  and a manual check in the screenshot at 21:9.

### What it touches

1. **Spawning** — resolved by the owner the same day: placement becomes a
   distance band around the hero regardless of the camera
   (`spawn_master_journal.md` S11), so a wider view no longer moves where
   enemies appear; some arrivals are simply visible at the edges on 21:9.
   The boss ring (`config.BOSS_SPAWN_DISTANCE = 680`) is already
   player-relative and may likewise be visible at 21:9.
2. **Terrain bake** (`world/terrain/bake.py:70`) spans the view width from
   config; it must span the widest supported aspect (cheapest) or re-bake
   when the aspect changes.
3. **HUD and menus** centre on `surface.get_width()` in ~16 files
   (`ui/hud.py`, `ui/level_up.py`, `ui/run_status/`, every state's `draw`).
   Proposed: hand those layers a centred 1600x900 **subsurface**
   (`surface.subsurface(ui_rect)`) so their code is untouched, and offset
   mouse events by the same margin for UI hit-testing (`ui/mouse.HitMap`).
   Manual aim works in full-surface coordinates and needs nothing.
4. **The logical size is fixed by `set_mode`.** Probe #5 above: a second
   `set_mode` with the same flags works, one that adds `FULLSCREEN` fails.
   Confirmed: two logical widths only, 16:9 (1600) and 21:9 (2100), chosen
   by the resolution pick or the desktop aspect; a dragged window keeps the
   current aspect behind bars. A continuously variable width would mean a
   display re-open on every resize event, which is too fragile.
5. **No mid-run changes.** Display settings change only in Options, from
   the main menu (the owner's ruling above), so the render width is chosen
   before a run starts and `PlayingState`, the camera, the bake span and the
   loading prewarm read it once at run start. The remaining work is the
   change *at the main menu*: a logical-width change there re-opens the
   display (windowed: a second `set_mode`; borderless: toggle out, re-open,
   toggle in) and refreshes `game.screen`.
6. **Tests** that pin layouts to `config.SCREEN_WIDTH` (`tests/screens/`,
   `tests/render/test_render_cull.py`, `tests/entities/ai/test_boss.py`)
   need the UI box vs the render width told apart. New: at a 2100x900 render
   the HUD's bars and the boss bar land inside the centred 1600x900 box; the
   pause, run-status and level-up dim layers darken a pixel in the side
   margin as much as one in the box; the camera's world span is 1400x600;
   the menus' hit rects stay where the 16:9 tests pin them, offset by the
   margin.

### Probed while building

| # | Finding | Consequence |
|---|---|---|
| 14 | A second `set_mode` at a **different** logical size fails with `failed to create renderer` in every path: windowed, while fullscreen with the flag, and after toggling out. A `pygame.display.quit()` + `display.init()` + `set_mode` works in every path, and converted surfaces and fonts survive it. | The render width changes by re-initialising the display module and opening afresh (`DisplayWindow.reopen`); the caption, the icon and the cursor are set again through hooks. Only ever from Options, so never during a run. |
| 15 | Opening a 2100x900 render **with the `FULLSCREEN` flag** made pygame's scaled path pick a 2560x1440 display mode on the 3440x1440 desktop -- a real mode switch. The toggle from a windowed window is desktop fullscreen at 3440x1440 every time. | Borderless always opens windowed and toggles; the flag is never passed. |

### Built

- `game/config.py`: `RENDER_WIDTHS = {"16:9": 1600, "21:9": 2100}`,
  `UI_WIDTH x UI_HEIGHT = 1600x900` (the box), the 21:9 sizes 2560x1080,
  3440x1440 and 5120x2160 in `WINDOW_RESOLUTIONS`; `SCREEN_WIDTH` is set
  from the render aspect when the display opens.
- `game/display/fit.py`: `aspect_class` -- wider than the midpoint of 16:9
  and 21:9 renders 21:9; 16:10 and 4:3 get the 16:9 render behind bars.
- `game/display/uibox.py`: the box rect, the subsurface, the offset, and
  `translate_event` for mouse events.
- `game/display/window.py`: `render_aspect` (saved as
  `display["render"]`, else derived: the desktop's class in Borderless,
  the picked size's class in Windowed); `wanted_aspect` / `_settle_aspect`
  after a mode switch or a Resolution pick (a drag never re-opens);
  `reopen(aspect)` per probe #14; Borderless opens windowed then toggles
  per probe #15.
- `game/state.py`: `State.ui_box` (default True; `PlayingState` False)
  and `State.draw_backdrop(surface)`. `StateMachine.draw` calls the
  backdrop with the whole surface and `draw` with the box for box states;
  `handle_event` hands a box state its mouse events in box coordinates.
- `game/states/playing/core/state.py`: the world on the surface, the HUD
  and the interface half of `feedback_overlays` on the box (the vignette
  and the hit flash stay full width).
- Overlays: the pause, level-up (`LevelUpPanel.draw_dim`, `draw(dim=False)`)
  and run-status dims moved to `draw_backdrop`; the menu paints its black
  behind the margins the same way.
- `game/save.py`: `display["render"]` coerced. `game/game.py`: the
  before-open and reopened hooks.
- **The ultrawide main menu** (owner, 2026-09-16): on a 21:9 render the
  menu paints `menu_background_long.png` (2496x800) across the whole
  surface in `draw_backdrop`, scaled to cover the height and centred, and
  skips the 16:9 art in the box; `config.MENU_BACKGROUND_LONG_IMAGE`.
  Pinned in `tests/screens/test_ultrawide.py`; verified at 3440x1440.
  The strip itself was then cut (owner, 2026-09-16, "1920, go"): the
  delivered 2496x800 art had a 1095 px band of plain sea in its middle,
  and an ultrawide needs 800 x aspect -- 1867 (21:9), 1911 (3440x1440),
  1920 (3840x1600). 576 px are removed from the centre by
  `tools/asset_pipeline/cut_menu_background_long.py`, leaving 359 px of
  sea either side of the seam; the source moved to
  `assets/ui/start_screen/unused/` as the project's art rule asks. The
  cover scaling now shows the whole strip on 3840x1600 and crops 4 px a
  side on 3440x1440.

### Verified on the real window (3440x1440)

| Step | Render | Window | Camera span |
|---|---|---|---|
| boot Borderless (saved) | 2100x900, 21:9 | 3440x1440 desktop fullscreen, 1.6x | 1400x600 |
| Display mode -> Windowed (saved 1920x1080) | 1600x900, 16:9 (re-opened) | 1920x1080, 1.2x | -- |
| Resolution -> 2560x1080 | 2100x900, 21:9 (re-opened) | 2560x1080, 1.2x | 1400x600 |
| quit | -- | save holds `render: 21:9`, `[2560, 1080]` | -- |

The Resolution list on this desktop: 1280x720, 1600x900, 1920x1080,
2560x1080, 2560x1440, 3440x1440. Screenshots of the 2100x900 render
delivered: the run with the pause overlay (the dim covers the margins, the
buttons and the HUD sit in the box), the run itself, and the Options
screen in the 2560x1080 window.

### Tests

`tests/display/test_uibox.py` (the box geometry, drawing through it,
event translation, the state machine handing the box to a box state and
the surface to the run, the camera span at 2100, the aspect class),
`tests/display/test_window.py` (+8: the aspect from the save, from the
mode and from the pick; a pick re-opens and a drag does not; the mode
switch settles both ways; the fallback always 16:9; `reopen` re-inits the
display and calls the hooks in order; the saved render coerced),
`tests/screens/test_ultrawide.py` (the pause, level-up and run-status
dims darken a margin pixel exactly like a box pixel; the menu's black
behind the margins; the pause buttons centred in the box; a level-up draw
without the dim leaves the margins alone).

### Progress

- [x] Logical width from the resolution pick / desktop aspect (16:9 or 21:9)
- [x] The UI box: HUD, menus and overlay panels on a centred 1600x900
      subsurface; mouse events offset for UI hit-testing
- [x] Dim layers painted on the full surface before the box
- [x] Terrain bake and loading prewarm span the render width (they read
      `config.SCREEN_WIDTH` at run start; nothing to change)
- [x] Tests listed in item 6
- [x] Screenshot at 21:9 with the pause overlay open
