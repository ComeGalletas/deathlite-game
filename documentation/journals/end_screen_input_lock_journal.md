# End-screen input lock — journal

An input lock on the two run-end screens (GAME OVER and VICTORY), so the
summary cannot be dismissed by the keypress or click that was already on its
way when the run ended.

---

## Requirement (owner, 2026-09-16)

- **Objective:** Add an input lock that engages when the game-over or victory
  screen appears, after the player has died or won.
- **Details:** Lock the controls so that a click or a keypress already on its
  way cannot close the screen before the player has had time to react to it.
- **Constraint:** Confirm the reading before implementing.

## Confirmed reading

- **Both screens, one place.** GAME OVER and VICTORY are the same frame:
  `ui/end_screen.py` `EndScreen`, shared since 2026-09-12
  (`victory_screen_journal.md`). The lock belongs on the frame, so neither
  screen can be given it and the other forgotten — the exact way those two
  drifted apart before.
- **Keyboard *and* mouse.** The heading says "keyboard input lock" and the
  body says "accidentaly clicks or presses a key". Both are locked. A click
  is the likelier accident of the two: manual aim holds the left button
  through a fight, so a run that ends mid-click already has a press in flight.
- **What "locked" covers.** Everything that can fire a button or move the
  selection: ENTER / SPACE, the direct keys (S, ESC), the cursor keys, and
  mouse press / release. Mouse *motion* still updates the hover highlight, so
  the screen does not look frozen for the duration; motion can never activate
  anything.
- **A press made during the lock does not fire late.** The press is dropped
  rather than remembered, so `MouseNav` never records what it landed on and
  the release that follows matches nothing. The same holds for a key held
  down across the lock: pygame key repeat is off in this game (`set_repeat`
  is never called), so a held ENTER is one KEYDOWN, and that KEYDOWN is
  inside the lock.
- **Duration.** Not specified by the request. **1.5 s**, in
  `config.END_SCREEN_INPUT_LOCK` where the rest of the UI timings live
  (`MUSIC_FADE_MS`, the glow periods). Long enough to swallow a keypress in
  flight and register that the screen changed; short enough that a player who
  means to leave is not made to wait.
- **What this is not.** The existing "only KEYDOWN leaves" rule in
  `EndScreen.handle_event` already stopped the *release* of the key that
  ended the run from dismissing the summary. That covers one case. This
  covers the rest: a fresh press, and anything from the mouse.

### Left out deliberately

No visual "locked" state — the buttons and the hint line draw exactly as they
do now for the 1.5 s. The request is for the lock, and a hint line that pops
in after a second and a half is a change to the screen nobody asked for. Easy
to add later if it turns out a player needs to be told why their first press
did nothing.

## Proposal

- `game/config.py` — `END_SCREEN_INPUT_LOCK: float = 1.5`, with a comment
  saying what the lock is for.
- `ui/end_screen.py`
  - `EndScreen.__init__` takes `lock: float | None = None`, defaulting to the
    config value, and stores `self.lock_remaining`.
  - `tick(dt)` counts it down; `locked` is the read.
  - `handle_event` returns `None` immediately while locked, letting only
    `MOUSEMOTION` through to the hover bookkeeping.
- `game/states/game_over_state.py`, `game/states/victory_state.py` —
  `update(dt)` ticks the frame. Both states have only ever had `enter`,
  `handle_event` and `draw`; `State.update` is a no-op hook and
  `StateMachine.update` already calls the top state every frame.
- Tests
  - `tests/screens/test_end_screen.py` — its `_screen()` helper builds the
    frame unlocked (`lock=0`) so every existing contract test still measures
    what it was written to measure; a new class covers the lock itself.
  - `tests/screens/test_game_over.py`, `test_victory.py` — their `_state()`
    helpers tick past the lock, and each file gets a test that the screen it
    owns refuses input before that.

## Built

- `game/config.py` — `END_SCREEN_INPUT_LOCK: float = 1.5`, beside
  `RUN_DURATION_SECONDS`, with the reason in the comment. 0 disables it.
- `ui/end_screen.py` — `EndScreen` takes `lock` (default: the config value),
  keeps `lock_remaining`, and exposes `locked` and `tick(dt)`.
  `handle_event` returns `None` before anything else while locked, letting
  only `MOUSEMOTION` reach the hover bookkeeping.
- `game/states/game_over_state.py`, `game/states/victory_state.py` —
  `update(dt)` ticks the frame. It is each state's only `update`.

The gate sits *above* `self.mouse.event(event)` rather than below it, which is
what makes a press made during the lock harmless: `MouseNav` never sees it, so
`pressed_on` stays `None` and the release that arrives after the lock lifts
matches nothing. Deferring the event instead would have fired the button the
instant the lock ended, which is the bug this was asked to prevent.

## Tests

`tests/screens/test_end_screen.py` — `_screen()` now builds with `lock=0`, so
the twenty-odd tests of the frame's input contract still measure the contract
rather than the lock. A new `InputLockTests` covers the lock itself: the
shipped screen starts locked for the configured time; confirm, the direct keys
and the cursor keys all do nothing while it is on; the lock runs out on ticks
and never goes negative; a press made during the lock does not fire when the
lock lifts; a whole click during the lock fires nothing; hover still tracks;
and `lock=0` is open from the first frame.

`tests/screens/test_game_over.py` and `test_victory.py` — `_state()` ticks past
the lock by default, with `locked=True` for the new `InputLockTests` in each:
the state refuses ENTER, ESC and a click while locked, and `update` is what
lifts it. Both files carry the test because the two screens sharing a frame is
only a guarantee while both are checked.

Screens: 96 passed. Everything else that touches these screens
(`tests/flows/test_smoke.py`, `test_hero_unlock.py`, `test_ui_scale.py`,
`test_ultrawide.py`, `tests/systems/test_music.py`): 63 passed.

## Suite

2,430 passed, 8 sweep tests deselected, 487 subtests passed (16 min 21 s).

## Progress

- [x] `config.END_SCREEN_INPUT_LOCK`
- [x] `EndScreen` lock, tick and gate
- [x] Both states tick it
- [x] Tests
