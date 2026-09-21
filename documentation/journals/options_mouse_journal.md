# Options mouse journal — the last keyboard-only menu

## Requirement (owner, 2026-09-16)

- **Objective:** Enable mouse control for the options menu.
- **Constraint:** Review and confirm only — no code yet.

## Confirmed reading

The Options screen (`game/states/options_state.py`) is the only menu the
player meets in normal play that still answers the keyboard alone. Its
`handle_event` opens with `if event.type != pygame.KEYDOWN: return`, so every
mouse event is dropped. The request is to give it the same hover-selects /
click-activates behaviour every other menu already has, plus whatever the two
volume bars need, without changing what the keyboard does.

This was left out on purpose, not by oversight. The 2026-09-04 mouse entry in
`journal.md` closed with *"Options, Rankings, the Sanctuary, the run-summary
screens and the loading screen are keyboard-only after this ... The volume bar
in Options would be the one screen that wants **drag** (set volume from the
click x), which the helper above does not need for anything in scope, so it is
left out on purpose."* This entry is that deferred work, for Options only.
Rankings, the Sanctuary and the loading screen stay keyboard-only unless the
owner asks.

### What the screen is made of

Eight rows (seven in-run — the Sanctuary row is hidden when Options is pushed
from the pause menu), laid out in `draw` at `y0 = px(240)`, `step = px(74)`,
label column `x0 = cx - px(250)`, value column `vx = x0 + px(250)`:

| row | keyboard today | what a mouse should do |
|-----|----------------|------------------------|
| Master volume | Left / Right ±`VOLUME_STEP`, `xp` blip, persist | click / drag the bar sets the level |
| Music volume | Left / Right ±`VOLUME_STEP`, no blip, persist | click / drag the bar sets the level |
| Mute | ENTER toggles | click toggles |
| Key layout | ENTER / Left / Right cycle (two layouts) | click cycles |
| Display mode | ENTER / Left / Right toggle Windowed ↔ Borderless | click toggles |
| Resolution | ENTER / Right step +1, Left −1 | click steps +1 |
| Sanctuary | ENTER opens `MetaState` | click opens it |
| Back | ENTER / ESC returns | click returns |

Two rows are *skipped* by `_move` when `_skipped(rid)` is true — Display and
Resolution with no scaled window, Resolution in borderless. They are drawn
`COLOR_TEXT_DIM` and the keyboard cursor passes over them.

### What already works in our favour

- `ui/mouse.py` gives `HitMap` (rects registered during `draw`, asked in
  `handle_event`) and `MouseNav` (motion → `("hover", key)`, a left press and
  release on the same key → `("click", key)`). Five screens use it; the
  idiom is three lines in `enter`, two in `draw`, five in `handle_event`.
- Coordinates need no conversion. `StateMachine.handle_event` runs
  `uibox.translate_event` for every `ui_box` state, and Options is one, so
  `event.pos` arrives in the same box coordinates the row rects are built in —
  ultrawide margins and native-resolution scaling included, because the rects
  are themselves built through `ui.scale.px` during the same `draw`.
- The arrow cursor is already installed globally at boot.
- Hover feedback needs no new art. Selection on this screen *is*
  `COLOR_ACCENT` plus the `>` marker, so pointing at a row and arrowing to it
  look identical. Per the 2026-09-04 art decision, **Options keeps its text
  rows** — no buttons, no ribbons, no new sheets.

### The one thing that is genuinely new: the sliders

Every mouse screen so far activates on *release*, never on press, because
`PlayingState` polls the held mouse button for manual aim and a pick on press
would fire an attack the instant an overlay closed. A slider drag has to act
on the press — that is what a slider is — but it is safe here, and the rule
is not weakened: dragging a bar never pops a state, so the run is never
resumed with the button still down. Every row that *does* leave the screen
(Back, Sanctuary) keeps activating on release, through `MouseNav` unchanged.

## Proposal

No new module. `ui/mouse.py` stays as it is; the drag lives in
`options_state.py`, which is the only screen with a bar.

**`enter`** gains `self._mouse = MouseNav()`, `self._bars: dict[str,
pygame.Rect] = {}` and `self._drag: str | None = None`.

**`draw`** clears the hit map and, per row, registers a full-width band —
`px(74)` tall (the step, so bands touch and never overlap), spanning label
column through the percentage text — keyed by the row index, **except** for
rows `_skipped(rid)` is true for, which register nothing. A dim row is then
inert to the mouse exactly as it is to Up / Down. `_draw_slider` returns its
bar rect, which `draw` stores in `self._bars[rid]`.

**`handle_event`**, in order, before the existing KEYDOWN body:

1. `MOUSEMOTION` while `self._drag` — set that row's level from `event.pos[0]`
   and return.
2. `MOUSEBUTTONDOWN` left inside a bar rect — select that row, start the drag,
   set the level, return. `MouseNav` never sees the press, so the matching
   release cannot also read as a click on the row.
3. `MOUSEBUTTONUP` left while dragging — end the drag, `game.persist()`,
   return.
4. Otherwise the standard three lines: `act = self._mouse.event(event)`;
   hover sets `self.sel`; click sets it and calls `self._activate()`.

**Setting a level from x** reuses the existing rounding so the mouse and the
keyboard land on the same grid: `level = (x - bar.left) / bar.width`, clamped
to 0–1, snapped to `config.VOLUME_STEP`. The value is applied live while
dragging (you hear it move), the master row plays its `xp` blip only when the
snapped step actually changes (a per-pixel blip would be a buzz saw), the
music row stays silent as it is today, and `game.persist()` runs once on
release rather than on every motion event.

**Activation on click** is exactly `_activate()` as it stands — click on Mute
toggles, on Key layout / Display cycles, on Resolution steps +1 (the same as
ENTER), on Sanctuary opens it, on Back returns. Nothing in `_activate`,
`_nudge`, `_move` or `_back` changes, so the pause-menu (`in_run=True`) path
inherits all of it for free.

**Hint line.** The bottom hint stays as written; no other menu advertises the
mouse either.

### Decisions (owner, 2026-09-16)

All three questions were answered as proposed:

1. **Drag on the bars.** Press, slide, release — not click-only. This is the
   one press-time action in any menu, for the reason argued above.
2. **No right-click.** Left-click steps a value row forward, the same as
   ENTER; there is no backwards step by mouse. The dev menu already uses
   right-click as ESC's twin, and one button meaning two different things
   across screens is worse than clicking round again.
3. **No mouse wheel.** The wheel is ignored on this screen, so a stray tick
   over the Resolution row can never resize the window.

## Todo

- [x] `options_state.py`: `MouseNav`, row bands in `draw`, bar rects from
      `_draw_slider`, the four-branch mouse path in `handle_event`, the
      level-from-x helper. Skipped rows register no band.
- [x] Docstring: the mouse paragraph, and why the slider is the one press-time
      action in the menus.
- [x] `tests/screens/test_options.py — OptionsMouseTests` (+22, the file
      30 → 52): bands and their non-overlap; a skipped row registers none;
      the in-run row set; hover selects and hovering off leaves the selection;
      click on Mute / Key layout / Display / Resolution does what ENTER does;
      click on Back returns and on Sanctuary opens; press on one row and
      release on another is inert; a click off every band is inert; the wheel
      and the right button never touch a value; a click in a bar sets the
      level on the step grid and does *not* also activate the row; a drag
      tracks, clamps at both ends and survives leaving the bar vertically;
      the drag writes the save once, on release; the two bars stay
      independent; the master bar blips once per step crossed and the music
      bar never blips.
- [x] `README.md`: the Mouse (menus) row lists Options and the dragging bars;
      the ← → (Options) row notes the drag.
- [x] Full suite green and a screenshot delivered.

## Verification (2026-09-16)

- `tests/screens/test_options.py`: 30 → **52 passed**.
- `tests/screens`: **438 passed**, 22 subtests.
- Full default suite: **2387 passed, 8 deselected, 487 subtests**, exit 0
  (13:47).
- Screenshot: the screen at 1600x900 with the pointer mid-drag on the master
  bar — the row gold and marked, the level snapped to 65 %.
- Not verifiable headless: the feel of the drag itself (the dummy driver has
  no pointer). The grid snap and the clamp are pinned by tests instead.
