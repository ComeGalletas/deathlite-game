# Dynamic window scaling — execution journal

## Requirement (owner, 2026-09-15)

> Review and propose a way to implement dynamic window scaling, using
> arbitrary screen resolutions and sizes to fit many screens, from fullscreen
> (needs to be only borderless windowed) and windowed. Consider a min and max
> resolution and make sure the integrity of the gameplay remains the same. Do
> not alter the zoom. Confirm, don't touch code.

Status: **proposal only**. No code was changed; the owner asked for
confirmation first. Everything below was checked against the code and
against pygame 2.6.1 / SDL 2.28.4 on the owner's machine with throwaway
probe scripts (kept out of the repo).

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
| `KEY_TOGGLE_FULLSCREEN` | `K_F11` | Plus Alt+Enter. F1–F8 are the debug keys; F11 is free. |

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
  `handle_event(event)` (size-changed → remember the windowed size when not
  fullscreen, re-apply the integer-scale flag, rescale the cursor),
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
window events to the manager and handles F11 / Alt+Enter globally, next to
the `M` mute key.

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

### 4. Fullscreen and the controls

- `toggle_fullscreen()`; on the way back to windowed, re-apply the
  integer-scale flag, re-assert the remembered windowed size, rescale the
  cursor, persist the mode.
- Hotkeys F11 and Alt+Enter anywhere (global, consumed before states).
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
- Pause menu: one more wide-button row, **Display mode**, showing Windowed /
  Borderless on the right like the Key layout row (five rows still end at
  y ≈ 650 of 900). Resolution changes stay in Options.

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
5. F11 and Alt+Enter; Display mode and Resolution rows in Options, Display
   mode alone in the pause menu — **confirmed by the owner 2026-09-15**.
6. First launch opens windowed and fitted (not fullscreen).

---

## Progress

- [ ] Config constants and the `SCREEN_*` comment
- [ ] `game/display/` — `fit.py`, `native.py`, `window.py`
- [ ] `Game` wiring: prepare before init, open, events, hotkeys
- [ ] Save coercion of `settings["display"]`
- [ ] Display mode and Resolution rows in Options; Display mode row in the pause menu
- [ ] Cursor rescale
- [ ] Web profile flag
- [ ] Tests listed in §8
- [ ] Manual checklist and the screenshots (windowed 1.2x, fullscreen ultrawide)

---

## Ultrawide render extent (owner, 2026-09-15) — under consideration

> Expand the game window display — not these resolutions, the size the game
> is actually rendered — to allow for ultrawide screen resolutions. 21:9
> resolutions can be selected in windowed mode too. The game should only
> change visually: extend the game display to cover the sides for the
> ultrawide size. The camera should naturally cover this extended space, and
> because the spawn master can spawn enemies anywhere it should affect the
> gameplay. HUD elements must remain static as a 16:9 resolution.

Status: **considered only**, not confirmed and not built. It relaxes the
"identical gameplay at every size" rule above for ultrawide players.

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
  wider edges. **Open:** whether menus and overlays (pause, level-up, run
  status, title) also stay in that box — assumed yes, with the world or the
  background showing in the side margins.

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
   Changing the logical size at run time needs its own probe. Proposed: two
   logical widths only, 16:9 (1600) and 21:9 (2100), chosen by the
   resolution pick or the desktop aspect; a dragged window keeps the current
   aspect behind bars. A continuously variable width would mean a display
   re-open on every resize event, which is too fragile.
5. **Mid-run changes.** A Display mode toggle on an ultrawide desktop changes
   the aspect while a run is live, so `PlayingState.camera.view_width`, the
   bake span and the loading prewarm must accept a change at any time, not
   only at run start.
6. **Tests** that pin layouts to `config.SCREEN_WIDTH` (`tests/screens/`,
   `tests/render/test_render_cull.py`, `tests/entities/ai/test_boss.py`)
   would need the UI box vs the render width told apart.

### To probe before confirming

- A second `set_mode` that changes the logical width (windowed) keeps
  vsync, the renderer and the integer-scale fix.
- Whether the same works through the borderless toggle, or whether the
  logical width must be chosen before the toggle.
