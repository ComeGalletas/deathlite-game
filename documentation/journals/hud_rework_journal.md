# HUD rework — execution journal

## Requirement (owner, 2026-09-12)

New HUD sprite sheets were added under `assets/ui/` (`00.png`–`07.png` plus the
combined `All.png`). The first piece of the rework: draw the in-run **HP bar**
and **experience bar** from those sheets instead of the primitive rectangles
`ui/hud.py` draws today. The owner named `04.png` and `01.png` as the sheets to
analyse and asked for a proposal before any code.

---

## What the sheets contain

### `04.png` — 336×240, a uniform 48×16 grid (7 columns × 15 rows)

Three horizontal bar *families* of four rows each, then a vertical section:

| family | rows | y | column 0 (frames) | columns 1–6 (fills) |
|---|---|---|---|---|
| **A** slab / parallelogram | 0–3 | 0–64 | silver, grey, copper | red, yellow, blue, green |
| **B** hexagon | 4–7 | 64–128 | silver, grey, copper | red, yellow, blue, green |
| **C** capsule | 8–11 | 128–192 | silver, grey, copper | red, blue, yellow, green |
| **D** vertical | 12–14 | 192–240 | 3 frames, 10 px wide | 18 bars = 3 colours × 6 steps |

Fill colours are exact and shared by all three families: red `#D90F1E`, yellow
`#FFC825`, blue `#0098DC`, green `#21AA41`. Frame colours are silver
`#92A1B9`/`#C7CFDD`, grey `#858585`, copper `#BF6F4A`.

### `01.png` — 272×144

* **x 0–80**: four banner / ribbon plates, 80×18 of art on a 32 px pitch at
  y 8, 40, 72, 104 — silver, blue, green, orange.
* **x 80–272, row 0 (y 0–48)**: four empty gem sockets, 48×48 cells, art 44×40
  at cell-relative (2, 4) — red, green, blue, grey. The interior is transparent.
* **row 1 (y 48–96)**: the matching gem bodies, art 36×32 at (6, 8) — orange,
  green, blue, silver. Socket and gem are **concentric within their cells**, so
  gem-then-socket at the same origin nests them with no offset table.
* **row 2 (y 96–144)**: two winged badges, 80×40 of art in 96-wide cells at
  x 80 and x 176 — red/orange and blue.

---

## Three findings that decide the implementation

**1. Frame and fill register at offset (0, 0).** The column-0 sprite is a
*housing with a transparent trough*, and the fill sprite is a self-contained bar
carrying its own black rails. The housing's inner rails and the fill's rails
land on the same scanlines — y6/y10 for families A and B, y5/y9 for C. Blitting
the housing at (0, 0) and the fill at (0, 0) lines them up exactly; no
per-family offset is needed.

**2. Every bar sprite is a clean horizontal 3-slice.** Scanning for the longest
run of pixel-identical columns inside each sprite's art box:

```
A frame  art  0-48   caps L6 R6    uniform middle 36 px
A fill   art  3-45   caps L3 R4    uniform middle 35 px
B frame  art  3-45   caps L6 R6    uniform middle 30 px
B fill   art  7-41   caps L2 R2    uniform middle 30 px
C fill   art  9-41   caps L1 R1    uniform middle 30 px
C frame  art  6-44   caps L4 R25   uniform middle  9 px   <-- broken
```

So a 48 px cell rebuilds at any length under the same rule `ui/panels.py`
already applies to the Tiny Swords buttons — caps kept, middle stretched — but
one-dimensional and on a 48 px grid instead of 64. **Family C is the exception**:
its housing carries a diagonal gloss highlight that is not column-uniform, so
stretching it smears the sheen into a long gradient. C is usable at its native
48 px, not as a 300 px HUD bar.

**3. The six authored fill steps are not the runtime granularity.** Columns 1–6
are 100 / 82 / 61 / 40 / 18 / 0 %. Six steps is far too coarse for HP. They
exist so the artist could author a proper *right terminus* at each length — the
hex point on family B, the diagonal cut on A, the round cap on C. That terminus
is simply the fill sprite's own right cap. So the correct use is to take the
100 % sprite, 3-slice it, and cut it to the exact pixel length: the authored
terminus travels along as the slice's right cap. The bar then moves
continuously while every edge on screen is still authored art, with no
procedurally drawn edges — the standing preference recorded in
`authored-tiles-over-procedural-edges`.

Family A has no true 0 % sprite (its column 6 is still 22.5 % filled), so its
empty trough has to be sliced out of the dark tail of a partial fill. Families B
and C do ship a real 0 %, which is why B costs nothing here.

---

## Confirmed design (owner, 2026-09-12)

Four treatments were mocked at the real 1600×900 and the owner chose:

| | decision |
|---|---|
| Bar family | **B, the hexagon family** — rows 4–7 |
| HP bar | **framed**: silver housing (row 4, col 0) + red fill (row 4, col 1) |
| XP bar | **blue** fill (row 6, col 1), **frameless**, tucked under the HP bar |
| Frame colour | **silver** (not copper, not grey) |
| Medallion | **plain gem socket over gem**, ~64 px, level number centred inside |
| Scale | **×3** nearest-neighbour |

The framed-over-frameless pairing is what gives the two bars their size
hierarchy: at ×3 the HP housing is 33 px tall and the bare XP fill 15 px, so one
art family covers both without introducing a second style. The winged badge from
`01.png` row 2 was turned down as too dominant in the corner; the plain socket
at ~64 px is about a third smaller than the ×2 mock it was compared against.

---

## Plan

Per the project's sub-package convention, the bar drawing goes in a new
`ui/bars/` package rather than growing `ui/hud.py`:

* `ui/bars/geometry.py` — the measured art boxes and 3-slice caps, read from
  the rig data, plus the family / colour taxonomy. No per-sprite numbers
  hard-coded in Python beyond the taxonomy itself.
* `ui/bars/build.py` — the 1-D 3-slice, the fill-cut, and the surface cache.
* `ui/bars/hud_bars.py` — the HP bar, XP bar and level medallion widgets.

The cell rects live in `data/ui_sprites.json` alongside the existing button and
ribbon rigs, so the sheet layout is data and not code. `ui/hud.py` calls the new
widgets and keeps its current primitive drawing as the missing-asset fallback,
matching the degrade contract in `game/assets.py`.

---

## Progress

* **2026-09-12** — Sheets analysed, four treatments mocked, design confirmed by
  the owner (above).
* **2026-09-12** — HP and XP bars shipped. What landed:
  * `data/ui_sprites.json` gains ten rigs: the three hex housings, the four hex
    fills, the shared empty trough, and the blue gem socket / core. Bar rigs
    carry `caps` (the 3-slice end widths) and the housings carry `well` — the
    `(x, y, w, h)` of the fill's resting place inside the housing's art box —
    so no sheet coordinate is written in Python.
  * `ui/bars/slices.py` — the 1-D 3-slice, cached per `(rig, width)`.
  * `ui/bars/meters.py` — `bar()`: trough, fill cut to the exact pixel length,
    housing over the top, then the nearest-neighbour upscale.
  * `ui/bars/medallion.py` — `medallion()`: gem first, socket ring over it.
  * `ui/hud.py` — `_draw_meters` draws the cluster and returns False when the
    art is missing, in which case `_draw_flat_meters` draws the old rectangles.
  * `game/config.py` — a HUD bar block: the four rig names, `HUD_BAR_WIDTH`
    (104 native, 312 on screen), `HUD_BAR_SCALE` (3), and `HUD_GEM_PX` (64).
  * `tests/rendering/test_hud_bars.py` — 24 tests. The ones that carry weight:
    the caps of every bar rig are copied pixel-for-pixel out of the sheet, the
    stretched middle can never introduce a colour of its own, the bar seats the
    authored fill slice (hex point included) in the well at any fraction, a
    sliver too short for its own caps draws nothing rather than showing health
    an almost-dead hero lacks, and the frameless XP bar ends on the same pixel
    as the framed HP bar at the same fraction.

  Two decisions worth recording, made while building and open to being
  overruled: the gem's 64 px is 1.33x its native 48, a non-integer scale that
  leaves its outline very slightly uneven (48 or 96 would be exact); and the
  HUD still prints `LV n` at the top right, which the gem now duplicates.

  Verified in a booted run (seed 35, headless) as well as in unit tests. The
  two suite failures at this commit — `test_projectiles.py` (an unregistered
  `totem_bolt` family) and `test_totem_sprite.py` (a missing source sheet) —
  predate this work and belong to the totem branch in the tree.

* **2026-09-12** — Layout pass, on the owner's call:
  * Both HUD corners dropped 25 px from the top edge. The left cluster hangs
    off `config.HUD_LEFT_TOP` (39, was 14), which the primitive fallback reads
    too so the HUD does not jump when the sheets are missing.
  * **The HUD was cut down to four things**: the level gem, the HP bar, the XP
    bar and the run timer. The `LV` / `Kills` / `Gold` rows, the trait line,
    the blessing list and the bottom-left weapon list are gone, because the run
    status screen (TAB) shows all of it on demand and in more detail. The
    short-lived `HUD_RIGHT_TOP` constant went with them.
  * The boss bar was kept. It shows only during a boss fight, so it is combat
    readability rather than a standing readout.
* **2026-09-12** — The boss bar reworked into the same hex family, on the
  owner's call: silver housing, red fill, framed, at `HUD_BAR_SCALE` like the
  hero's bars, half the screen wide with the name shadowed above it. Its native
  width is derived from the screen (`int(w * HUD_BOSS_WIDTH) // HUD_BAR_SCALE`)
  so it stays half the frame at any resolution while still landing on whole
  source pixels, and `HUD_BOSS_BOTTOM` is the gap under it — shared by the
  primitive fallback, which is otherwise unchanged and still lands on the same
  pixel row it always did.

  New `tests/rendering/test_hud.py` (10 tests) covers the HUD itself rather
  than the bar builders: that the cluster and timer draw, that **nothing** is
  drawn in the other three corners (a regression test for the cut above), that
  no boss or a dead boss means no bar, that the boss bar is the hex bar centred
  and clear of the bottom edge, and that both fallbacks fire and sit where the
  art sat.

## Still to come

The rest of `assets/ui/` is unused so far and worth knowing about: `06.png` has
segmented pip bars that would suit XP-to-next-level, `05.png` a wedge meter,
`03.png` radial dial rings for cooldowns, `00.png` hearts, stars and small
chevrons, and `04.png`'s own vertical section a boss bar down the screen edge.
The boss bar in `ui/hud.py` is still a primitive rectangle.

## The pieces were cut out of the pack sheets (owner, 2026-09-12)

- **Objective:** Cut the UI elements that have sprites out of the shared
  sprite sheets into per-element sheets.
- **Details:** Review which elements have sprites first; once cut, move the
  big pack sheets into a separate "base" folder.

Ten rigs were reaching into `assets/ui/04.png` and `01.png` with offsets — the
only assets in the whole of `assets/ui/` doing so, since the buttons, ribbons
and pointer have always been one file per rig.

### What was proposed, and what was chosen

The obvious reading — one sheet per element, `health_bar.png` / `xp_bar.png` /
`boss_bar.png` — does not survive contact with the art: **the three bars share
pieces.** The empty trough is in all three and the red fill is in both the HP
and boss bars, so element sheets would duplicate them and a later edit to the
trough would have to remember three files. There is also a non-obvious
dependency: the XP bar is frameless but reads `bar_hex_frame_silver`'s `well`
for its inset, which is the only reason the HP and XP fills line up to the
pixel.

The owner chose **one file per piece**, named exactly after the rig that draws
it, in `assets/ui/hud/`. `bar_hex_frame_silver.png` is rig
`bar_hex_frame_silver` — no indirection, and duplication is impossible. The
three spare colours (grey housing, yellow and green fills) were cut too, so
nobody has to reopen the pack sheet to use them.

### How

`utilities/cut_ui_bars.py`, in the shape the chest and totem cutters already
take: the rects in one table with the measured geometry in the docstring, and
a `--check` mode a test runs so a re-cut can never drift from what is
committed. The rigs lost their `content` crops entirely — the file *is* the
crop now — while `caps` and `well` stayed, because those describe how the art
is rebuilt, not where it lives. `well` needed no adjustment: it was always
relative to the housing's art box, which is exactly what the cut file is.

The gem pieces keep their whole 48x48 cell rather than being cropped to their
ink. Cropping each to its own ink would have thrown away precisely the offset
that seats the gem inside the ring.

`00`–`07.png` and `All.png` moved to `assets/ui/base/`, unread. **`icon.png`
and `icon.ico` stayed put** — they sit in `assets/ui/` beside the sheets but
`config.WINDOW_ICON` points at `ui/icon.png`, so sweeping them into `base/`
would have dropped the window icon.

### Proof it changed nothing

The HUD (HP, XP and boss bar), the victory screen and the game-over screen were
rendered before and after and compared byte for byte: **all three identical**.
`tests/rendering/test_ui_bar_sprites.py` (10) pins the rest — the committed
files against the cutter, that no rig still reads a pack sheet, that each
filename matches its rig, that no `content` crop survives, that every housing's
`well` matches the fill it holds, and that the window icon is still where
`config` says it is.
