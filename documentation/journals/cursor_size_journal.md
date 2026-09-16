# Cursor size — matching the in-game arrow to the desktop cursor

**Owner request, 2026-09-16:** "review the current cursor rendering. currently
the cursor is rendering at around 20-40% bigger than the system cursor. change
it so the size of the windows cursor corresponds to the size of the ingame
cursor."

Confirmed with the owner before any change: **match Windows exactly**, by
measuring the system cursor at run time rather than tuning a constant.

## What was wrong

`ui/mouse.install_cursor` crops `assets/ui/pointers/arrow.png` to its ink —
**22x30 px** inside a 64x64 file — and scaled it by

```
config.UI_CURSOR_SCALE (1.0) x config.RENDER_SCALE x display.scale
```

(`Game._cursor_scale`). `RENDER_SCALE` is the *interface's* size: the window
height over the 900 px design height. On the owner's 3440x1440 desktop that is
1.6, so the arrow was drawn **35x48 screen px**.

The render scale has nothing to do with how large the operating system draws a
cursor, so the two only ever agreed by accident.

## What Windows actually draws (probed 2026-09-16)

| probe | result |
| --- | --- |
| `LoadImageW(IDC_ARROW)` bitmap | 32x32, hotspot (6, 3) on the tip |
| its colour bitmap's ink | 13x18 px — the arrow fills **18/32** of the rows |
| `GetSystemMetrics(SM_CXCURSOR/SM_CYCURSOR)` | 32 — **does not** follow the settings |
| `GetSystemMetricsForDpi(SM_CYCURSOR, 120)` | 32 (it only steps at 144) |
| `HKCU\Control Panel\Cursors\CursorBaseSize` | **48** (the owner's accessibility slider) |
| display DPI | 120, i.e. a scale of 1.25 |

So the drawn bitmap is `48 x 1.25 = 60 px` and the **visible** arrow inside it
is `60 x 18/32 = 33.75 px` tall. Against our 48 px that is ~40 % too big, which
is the range the owner reported.

The system-metrics calls are the obvious API and are the wrong one: they ignore
both the cursor-size slider and the DPI. `CursorBaseSize` (a 96-DPI base size)
times the display's DPI scale is what actually governs the drawn size.

## The rule now

`game/display/native.system_cursor_ink_height()` returns the height in screen
pixels of the arrow the desktop draws:

```
CursorBaseSize (registry, 32 when unreadable) x dpi_scale() x arrow ink fraction
```

The ink fraction is read from the live cursor's own colour bitmap
(`LoadImageW` + `GetIconInfo`, scanning for rows with any opaque pixel) and
cached, so a custom cursor scheme is honoured; it falls back to the stock
arrow's measured `18/32`. The two GDI bitmaps `GetIconInfo` hands out are
copies and are deleted.

`ui/mouse.system_match_scale(assets)` divides that by our own ink height and
multiplies by `config.UI_CURSOR_SCALE`. `Game._cursor_scale` prefers it and
keeps the old formula only where the platform will not say (anything but
Windows, or an unreadable setting) — the same degrade contract the cursor
already had for a missing image or a refusing driver.

On the owner's machine that is `33.75 / 30 = 1.125`, drawing the arrow at
**25x34 px** against the system's ~24x34.

## Consequences, stated to the owner before the change

The match is **absolute**, in screen pixels. The arrow no longer grows with the
render width or the window scale: it is the same physical size windowed,
borderless and at either render aspect. It is visibly smaller than before.

`config.UI_CURSOR_SCALE` changes meaning: 1.0 is now "the same size as the
system cursor" rather than "1x the asset", and it is only for making the game's
arrow deliberately larger than the player's own.

## Tests

`tests/screens/test_mouse.py`, in `CursorTests`:

* the arrow's drawn ink height equals the system ink height it was given
  (checked at three sizes);
* `_cursor_scale` is unchanged by `RENDER_SCALE` or `display.scale`;
* a platform that will not say falls back to the render-scale rule.

`tests/display/test_native.py`, in `SystemCursorTests`:

* `system_cursor_ink_height()` is a plausible pixel height on Windows and
  None elsewhere;
* the arrow's ink fraction is a fraction and is read once, then cached;
* an unreadable bitmap handle degrades to None rather than raising.
