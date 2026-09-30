# Frame-cap timer resolution on Windows 11: journal

**ID:** SYS-011 · **System:** systems (display shims) · **Type:** bug ·
**Status:** done · **Branch:** ComeGalletas/sys-011-timer-resolution-26b3a82b
(stacked on SYS-010, whose trace found it: `0de00e4`; owner, 2026-09-29)

---

## SYS-011: Requirement (owner, 2026-09-29)

- **Objective:** Find why `clock.tick(62)` sometimes holds every frame at
  about 30.6 ms on the owner's Windows 11 machine, whether real play meets
  it, and fix it if it does, with the pacing left as it is.
- **Details:**
  - Found verifying SYS-010.4 (`frame_trace_journal.md`, SYS-010.D4): a
    headless traced run (dummy video and audio, seed 35) read a period p50
    of 30.9 ms against 6.3 ms of work, `wait_ms` p50 23.2 ms. In that
    process a bare `tick(62)` loop held 30.6 ms whatever the work, while
    `pygame.time.delay` stayed exact. Minutes later the same probe held
    16.3 to 16.8 ms.
  - The hypothesis to confirm or refute: the Windows timer falls back to
    its default 15.6 ms granularity, because Windows 11 may ignore
    `timeBeginPeriod` for processes it sees as neither visible nor
    audible, and pygame's tick sleeps through `SDL_Delay`.
- **Constraint:**
  - `config.FPS` and the resolution do not change (the native resolution
    is fixed by the owner).
  - Any change to gameplay pacing is the owner's call, asked with measured
    evidence before it is made.

## SYS-011: What was found

All measurements on the owner's machine: Windows 11 Pro 10.0.26200, RTX
5080 display at **174 Hz**, Balanced power plan, no battery, Python
3.12.0, pygame 2.5.2, SDL 2.28.3. The probes are throwaway scripts (not
kept); each number is the median of the stated sample.

### The mechanism

`Clock.tick` computes the time left in the frame and sleeps it with
`SDL_Delay`, which on Windows is `Sleep()`. SDL asks for a 1 ms timer when
it starts (`timeBeginPeriod(1)` in `SDL_TicksInit`) and gives it back in
`SDL_Quit`. `pygame.time.delay` is different: it busy-waits anything under
12 ms, which is why it "stayed exact" in D4.

With the 1 ms request out of effect (cancelled on purpose with
`timeEndPeriod(1)` after `pygame.init()`), the tick shows D4's exact
signature: two coarse timer periods a frame, whatever the work.

| work in the frame | `tick(62)` fine: p50 | coarse: p10 / p50 / p90 | `tick_busy_loop(62)` coarse |
|---|---|---|---|
| 0 ms | 16.66 | 16.21 / 30.79 / 31.55 | 16.00 |
| 3 ms | 16.72 | 16.27 / 30.89 / 31.53 | 16.00 |
| 6 ms | 16.67 | 16.25 / 30.75 / 31.52 | 16.00 |
| 10 ms | 16.70 | 16.29 / 30.91 / 31.63 | 16.00 |

`Sleep(1)` reads 1.51 ms fine and 15.29 ms coarse.

Two other readings ruled out on the way:

- **CPU load is a different signature.** 32 busy processes on the 16
  logical cores gave `tick(62)` p50 27 to 29 ms but max 322 ms, with
  `Sleep(1)` anywhere from 1.5 to 12.6 ms. D4's run 8 stretched with
  nothing running beside it.
- **`pygame.quit()` heals itself.** `SDL_Quit` does drop the process back
  to 15.3 ms `Sleep`, but the next `tick` finds SDL's timer subsystem down,
  starts it again, and the 1 ms request with it.

### The trigger: the documented Windows 11 rule

Microsoft documents it under `timeBeginPeriod` and `SetProcessInformation`:
from Windows 11, if a window-owning process becomes fully occluded,
minimized or otherwise non-visible to the end user, and non-audible,
Windows may ignore its timer resolution request. A process can opt out
with `SetProcessInformation(ProcessPowerThrottling)`, control mask
`PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION`, state 0 ("always
honor timer resolution requests").

A headless pygame process qualifies. It owns four hidden message-only
windows after `pygame.init()` and no visible one, and with
`SDL_AUDIODRIVER=dummy` it has no audio stream. Whether Windows applies
the rule to it is re-judged on desktop window and focus events elsewhere,
which is why identical runs differed (D4 run 4 flipped at `Game()`, run 7
of the same script did not). Here a headless dummy-audio process flipped
at 18:16:31 while other windows opened, minimized and closed; a
real-audio process sampled beside it stayed at 1.5 ms throughout (65
samples over 20 minutes).

**Reproduced on demand:** a real window (windows driver), dummy audio,
minimized. Within a second `Sleep(1)` reads 15.2 to 15.9 ms, for all of a
three-minute minimize, and 1.5 ms again the moment it is restored. The
same window with the real audio device open (playing nothing) kept 1.5 ms
through a 90-second minimize: an open device counts as audible even when
silent.

**Causal check, in one naturally stretched headless process** (the D4
case itself):

| step | `Sleep(1)` | `tick(62)` p50 |
|---|---|---|
| stretched | 15.51 | 30.86 |
| `timeBeginPeriod(1)` again | 16.15 | 30.89 |
| opt-out (`IGNORE_TIMER_RESOLUTION` off) | 1.51 | **16.43** |
| the same, 20 s later | 1.51 | 16.48 |
| back to system-managed | 15.32 | 30.78 |

So the hypothesis stands, with one correction to D4. SDL does ask for the
1 ms timer, and Windows sets that request aside.

### Real play

D4 expected vsync to hide it: "`flip` waits for the refresh and the tick
after it normally has nothing left to wait". That holds only while the
refresh is at or under 62 Hz. At 174 Hz, `flip` returns in about 0.2 ms at
62 fps (the swap chain never fills), so **`tick(62)` paces every real
frame**, vsync on or refused.

The real `Game`, windows driver, stepped by its own `_step` on the menu,
4 to 5 s a row:

| | vsync on | vsync refused |
|---|---|---|
| visible, real audio | 16.62 | 16.54 |
| visible, no audio device (dummy) | 16.66 | 16.52 |
| minimized, real audio | 33.37 (DWM holds `flip` at ~30 ms; `Sleep(1)` 1.50) | 16.67 |
| minimized, no audio device | 46.88 (`Sleep(1)` 15.28) | 30.80 (`Sleep(1)` 15.74) |

Real play is **not affected** while the window can be seen, and not while
the mixer holds a device. Muting does not change that: `AudioManager` and
`MusicPlayer` mute by volume and skip, and the device stays open. The
exposure is:

- every headless run that uses the dummy audio driver: `--trace` sessions
  driven headless, `tools/benchmarks/*` (they all `setdefault` both dummy
  drivers), and tests that time frames;
- a hidden window (minimized or fully covered) on a machine where the
  mixer could open no device.

`config.MAX_DT` is 50 ms, so a stretched frame keeps game time right; it
halves the frame rate, it does not slow the game down. (The minimized
vsync row at 46.9 ms sits close to that clamp.)

### The fixes, measured

6 ms of work a frame, 5 s each:

| pacer | fine: fps / p50 / CPU | coarse: fps / p50 / CPU |
|---|---|---|
| `Clock.tick(62)` (today) | 60.2 / 16.63 / 36 % of a core | 35.8 / 30.82 / 12 % |
| `Clock.tick_busy_loop(62)` | 62.5 / 16.00 / **99 %** | 62.5 / 16.00 / 99 % |
| high-resolution waitable timer pacer | 62.0 / 16.20 / 37 % | 62.0 / 16.20 / 38 % |
| `tick` + the opt-out | as fine | lifted to fine (table above) |

- `tick_busy_loop`: pygame spins any wait under 12 ms, and at 62 fps every
  wait is. A whole core for pacing. Rejected.
- `timeBeginPeriod(1)` again: no effect while Windows ignores the process
  (table above). Rejected.
- Pacing by vsync alone: 174 fps on this monitor. Rejected.
- A high-resolution waitable timer (`CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`)
  is immune in every regime, but paces at 62.0 fps instead of today's
  60.2: a pacing change.
- The opt-out: one call at startup, no CPU, today's pacing kept.

## SYS-011: Decisions

- **SYS-011.D1 (owner):** the opt-out at startup. `Game.__init__` asks
  Windows to always honor the process's timer resolution request, so
  `tick(62)` paces as it does today in every case above. Pacing is not
  otherwise changed; `config.FPS` stays.
- **SYS-011.D2: it lives in `game/display/native.py`,** the one module that
  touches `ctypes` ("nothing else should"). Like
  `system_cursor_ink_height` it is not about the window; its docstring
  says so. It never raises: off Windows, or on a Windows too old for the
  policy, it answers `False` and logs why.
- **SYS-011.D3: the gate test switches the policy on itself.** Windows
  applying the rule on its own and a process setting
  `IGNORE_TIMER_RESOLUTION` on read as one policy here. Microsoft does not
  say so: its `SetProcessInformation` remarks say only that Windows 11
  "may automatically ignore" the request for a hidden, silent process. The
  equivalence is measured. The flag set explicitly reproduces the stretch
  every time (`Sleep(1)` median 15.27 ms, three cycles of three, 240 ms a
  cycle), the same 15.3 ms the eval's control arms read when Windows
  applies the rule to the real minimized game, and the fix lifts both. So
  the test that pins the fix is deterministic and needs no minimized
  window; the eval is what ties it to Windows' own decision.

## SYS-011: Plan

- **SYS-011.2: The fix.** `native.honor_timer_resolution()`;
  `Game.__init__` calls it and keeps the answer (`Game.timer_honored`) and
  logs it once.
- **SYS-011.3: Tests.** In `tests/display/test_native.py`: the policy reads
  back as set; off Windows it is a no-op that touches no Win32 API; a
  failing call answers `False` and never raises; and the regression pin,
  the policy switched on reproduces the coarse sleep and the fix lifts it.
  In the `Game` wiring tests: `Game()` calls it and keeps the answer.
- **SYS-011.4: The eval,** `python -m tools.benchmarks.timer_regime`: the
  real `Game` in a real window with no audio device, minimized, stepped by
  `_step`, with the policy handed to Windows, honored, and handed back. It
  passes when the honored arm paces at the tick's own rate, and says
  whether Windows reproduced the rule in the control arms.
- **SYS-011.5: A cold critic pass** (CLAUDE.md, medium bug fix: an
  attacker on the repro), its findings fixed.
- **SYS-011.6: Results;** the index to done.
- **Outcome:** a headless `--trace` or benchmark run, and a hidden window
  with no audio device, pace at 60 fps, not 32. Measured by the eval, and
  in a trace by SYS-010's `wait_ms` column.

## SYS-011: Tasks

- [x] SYS-011.1: This journal; the index row
- [x] SYS-011.2: The fix (`native.honor_timer_resolution`, `Game.timer_honored`)
- [x] SYS-011.3: Tests
- [x] SYS-011.4: The eval (`tools/benchmarks/timer_regime.py`)
- [x] SYS-011.5: The cold critic's findings, fixed
- [x] SYS-011.6: Results; index to done

## SYS-011.3: What the tests catch

Mutation check (a throwaway script, not kept: each mutant is one source
edit, the three touched test modules run against it, the source restored
byte for byte): 12 mutants, 12 caught. The fix removed; the policy set to
ignore instead of honor; handed back to Windows instead; the wrong
information class; `Game` never calling it; a refusal not checked; either
platform gate dropped; exceptions escaping; the read's failure log
dropped; the eval ignoring the shipped call; the eval with no
inconclusive status. The critic's load run: the timer tests ten times
under 32 busy processes on the 16 logical cores, no failure. The tier
audit: 4036 tests read, 0 under-tiered.

## SYS-011.5: The cold critic's findings, and what changed

A critic that had not built it read the four commits, the repro and the
requirement cold, re-ran the eval and a mutation and load run of its own.
It could not break the fix (the eval, the ctypes layout against the
`SetProcessInformation` page, the web build, every pacing entry point, a
re-init, the load run). Verdict: FAIL, on these:

| Finding | Fix |
|---|---|
| The journal said the branch was stacked on SYS-010 while it sat on `main` | Rebased onto SYS-010's pushed tip before the PR; the line is now true |
| Tasks .2 to .4 unticked after they landed; no results; status in progress | Ticked; results below; the index row to done |
| The regression pin passed with the policy handed back to Windows, the pre-fix state, whenever Windows was not applying its rule to the test process at that moment | The pin asserts the policy reads `(IGNORE_TIMER_RESOLUTION, 0)` after the fix, not only the sleep |
| The eval's honored arm set the bits with the private setter, never the shipped call, and ignored `Game.timer_honored` | The arm calls `native.honor_timer_resolution()`; `judge` fails when it or `Game`'s call answered False |
| A pass with neither control arm reproducing exited 0, though it would pass with the fix deleted | Exit 3, "inconclusive"; 0 needs a control arm to have reproduced |
| The wiring test left the process policy changed | It restores what it found |
| `_throttling` failed without saying why, against the module's contract | It logs on each failure path |
| D3 said Microsoft documents the equivalence | Reworded: measured, not documented |
| The import test depended on the caller's `SDL_VIDEODRIVER` | It reloads the module and compares the drivers before and after |
| `Next free: SYS-012` with no SYS-010 row on the branch | Resolved by the rebase: SYS-010's row is there |

Not verified here: whether Windows 10 refuses the timer bit. The code
treats a refusal as `False` and a log line, and before Windows 11 the
request is never set aside, so either answer is safe. It would take a
Windows 10 machine running
`python -c "from game.display import native; print(native.honor_timer_resolution())"`.

## SYS-011.6: Results

`python -m tools.benchmarks.timer_regime`, the final code, 2026-09-29, on
the owner's machine (as above). The real `Game`, real window, no audio
device, minimized, 5 s an arm after a 3 s settle; ms:

| run | arm | `SDL_Delay(1)` before -> after | frame p50 / p90 | tick wait p50 |
|---|---|---|---|---|
| 1, vsync off | managed | 15.51 -> 15.30 | 30.66 / 31.79 | 29.11 |
| | **honored** | 1.51 -> 1.51 | **16.64** / 17.52 | 14.99 |
| | managed again | 15.27 -> 15.28 | 30.70 / 31.63 | 29.13 |
| 2, vsync off | managed | 15.33 -> 15.55 | 30.82 / 31.89 | 29.05 |
| | **honored** | 1.52 -> 1.53 | **16.62** / 17.85 | 15.01 |
| | managed again | 15.33 -> 15.42 | 30.74 / 31.78 | 28.96 |
| 3, vsync on | managed | 15.44 -> 15.76 | 46.86 / 47.96 | 0.00 |
| | **honored** | 1.51 -> 1.52 | **33.59** / 34.35 | 0.00 |
| | managed again | 15.51 -> 15.24 | 46.88 / 48.02 | 0.00 |

All three: the rule reproduced in both control arms, the fix PASS, exit 0.
With vsync off a hidden, silent game paces at the cap's 16.6 ms again
instead of 30.7 (32 fps to 60). With vsync on the minimized present is
DWM's (the tick never waits), and the coarse timer stretched that too:
46.9 ms down to 33.6. Real play, visible or with a device open, was never
exposed and keeps its 16.5 to 16.7 ms.

**In SYS-010's own trace.** The same outcome through the recorder and the
report on the final code, stacked on SYS-010 (`0de00e4`): a headless
session (dummy video and audio), 10 menu frames, `start_run(seed=35)`, 240
play frames, one process per arm; ms, p50 / p90 / p99 / max:

| policy | long frames in play | what took most of each | period | `wait_ms` |
|---|---|---|---|---|
| ignored (what Windows does to a hidden, silent process) | 181 of 240 (75.4 %) | the wait, all 181 | 30.80 / 31.60 / 32.33 / 32.64 | 24.73 / 27.21 / 28.15 / 28.51 |
| honored (the fix) | 0 of 240 | none | 16.65 / 17.27 / 17.97 / 18.17 | 12.20 / 13.33 / 14.14 / 14.33 |

Work over budget was 0 in play in both. The D4 run's picture (period p50
30.9 ms against 6.3 ms of work) is the first row; with the fix a headless
trace reads like real play.
