# Frame-time trace of real play: journal

**ID:** SYS-010 · **System:** systems (+ tools) · **Type:** feature ·
**Status:** in progress · **Branch:** ComeGalletas/sys-010-frame-trace-9ec11fc6
(stacked on RND-009, the chain tip, so it measures the game as it will ship;
owner, 2026-09-29)

---

## SYS-010: Requirement (owner, 2026-09-29)

- **Objective:** Measure how often real play misses the frame budget, and
  why, before changing how the game looks or plays to save time.
- **Details:**
  - RND-008 and ENT-018 measured stress workloads, 100 or more enemies
    packed round the hero. RND-009 found the terrain bands at the
    blitter's floor.
  - Every lever left changes the picture, the pipeline or how crowds move
    (`ground_bands_journal.md`, `enemy_update_journal.md`).
  - The trace tells whether any of those trade-offs is needed at all: how
    many real frames miss 16.67 ms, at what crowd sizes, and whether it is
    the update or the draw.
- **Constraint:**
  - **Switched on by a command-line flag** (owner, SYS-010.D1):
    `python main.py --trace`, plus an environment variable for the
    packaged exe. Off by default.
  - When off, it costs next to nothing (measured: two clock reads, four
    checks and one stored reference per state updated, 0.15 µs a frame). When on, its
    per-frame cost is measured and stated.
  - It changes no gameplay. It never writes into the repo (the files go
    beside the save, in a gitignored `traces/`).

## SYS-010: Plan

- **SYS-010.2: The recorder:**
  - `systems/frame_trace.py`: `FrameTrace`, one CSV per session, buffered.
  - `sample(game, state)`: the name of the deepest state the frame's
    update reached (SYS-010.D3), the state shown at its end and whether
    that update opened it (D6), the bodies the run can target (`Run.targetables()`)
    and how many are in view, the particles, the damage numbers, the run
    clock. A menu frame is recorded too, with the crowd blank.
  - `trace_path(argv, environ, save_path)`: whether to trace, and to
    which file.
  - `Game` takes the trace and times the update, the draw and the present
    (`display.flip`, the vsync wait) apart, and the frame cap's wait in
    `clock.tick` after it (SYS-010.D4). Each row's period is the frame's
    own, from the start of its work to the start of the next frame's
    (SYS-010.D2).
  - `main.py` passes `trace_path(...)`. `.gitignore` gains `/traces/`, and
    the web build's `ignoreDirs` gains `/traces`.
- **SYS-010.3: The report,** `python -m tools.benchmarks.trace_report FILE`:
  - frames over the budget, in play and overall, as work (update + draw),
    update-bound against draw-bound;
  - long frames (over 1.5 x the budget), how many had work over budget,
    and what took most of each: update, draw, present, the tick's wait, or
    the rest of the period (SYS-010.D5);
  - play frames that opened an overlay, counted apart by its name (D6);
  - p50 / p90 / p99 / max of the period and each of those parts;
  - the same by crowd size, with the in-view and particle medians;
  - the worst seconds of each run.
  - Its budget is the harness's `BUDGET_MS`: one constant, not two.
- **SYS-010.4: Tests** (the recorder, the format, the flag, off by default,
  the `Game` wiring, and the report's numbers on a synthetic trace built
  so every figure is known) and a how-to in `README.md`. The recorder's
  own per-frame cost is measured.
- **SYS-010.5: Results;** the index to done.
- **Outcome:** the owner can play a normal run with `--trace` and get the
  answer from one command.

## SYS-010: Tasks

- [x] SYS-010.1: This journal; the index row
- [x] SYS-010.2: The recorder and its wiring (`--trace`, `DEATHLITE_TRACE`, `traces/` beside the save)
- [x] SYS-010.3: The report (`tools/benchmarks/trace_report.py`); `BUDGET_MS` moved to `systems/frame_trace.py`, the one copy
- [x] SYS-010.4: Tests, the recorder's measured cost, the how-to; five cold critics' findings fixed, the sixth passed it
- [ ] SYS-010.5: Results; index to done

## SYS-010: Decisions

- **SYS-010.D1 (owner):** a command-line flag switches the trace on,
  `python main.py --trace`, with `DEATHLITE_TRACE` for the packaged exe.
- **SYS-010.D2: each row carries its own period.** `clock.tick` returns the
  time since the previous tick, so a row that stored it described the frame
  before. A slow frame showed up one row late, under the next frame's state
  and crowd, and the frame that entered a run carried the menu's period.
  `Game._step` now takes `perf_counter` right after the tick, and the
  recorder finishes a row when the next one starts. The period is the
  frame's work, its present and the wait before the next frame's work.
- **SYS-010.D3: a row is the deepest state the frame's update reached.** At first
  a row took the state the frame ended in. The first `PlayingState` row of
  a run was then the frame that finished the load and ran
  `PlayingState.enter`, so those frames were counted apart and left out of
  every in-play figure. The second critic showed that rule hid real play: a
  `PlayingState.update` that pushes the level-up cards, a boss death's
  banner or a chest's reward ended in the overlay, so its hitch left every
  in-play figure without being counted. The unpause frame, whose update is
  ordinary play, was dropped for no reason. The second fix read the top
  state after the input; the third critic showed that still missed the end
  banner's first second, whose wait phase updates the run under it
  (`update_below` True: the death poof, the boss burst). Now
  `StateMachine.update` notes the deepest state its own walk reached
  (`StateMachine.updated`, one stored reference, the walk itself
  unchanged), and the row carries it: the rule lives once, in the loop that
  applies it. The frame that finishes the load is a `LoadingState` row, the
  level-up frame and the end banner's wait a `PlayingState` row, the frame
  that presses pause a `PausedState` row, the one that unpauses a
  `PlayingState` row. No exclusion is needed. The crowd is still sampled at
  the frame's end, so the last loading row carries the run it built.
- **SYS-010.D4: the tick's wait is a column of its own (`wait_ms`).** Found
  verifying SYS-010.4 end to end. A headless seed-35 session traced with
  the dummy drivers read a period p50 of 30.9 ms against 6.3 ms of work and
  0.6 ms of present, so 79 % of its frames read "long" with nothing in the
  row to say why. Timing each phase of `_step` put the missing 23 ms in
  `clock.tick(62)` itself, while `pygame.time.delay` stayed exact; minutes
  later the same probe held 16.3 to 16.8 ms. A trace must say which it is,
  so `_step` times the tick and the recorder puts it on the row of the
  frame it ended, like the period. The parts of a row now account for its
  period: update, draw, present and wait are disjoint spans inside it
  (pinned by `test_every_frame_is_recorded`), and what is left is the
  input, the music and the trace's own sample.
  - **The cause (SYS-011, `timer_resolution_journal.md` on its own branch,
    stacked on this one, holds the evidence):** Windows 11
    may ignore the 1 ms timer request of a process that owns windows but is
    neither visible nor audible. A headless pygame process owns hidden
    message-only windows, and with the dummy audio driver it has no audio
    stream, so it qualifies; Windows re-judges it on desktop window and
    focus events, which is why identical runs differ. SYS-011 reproduced it
    on demand and found real play unaffected: a visible window keeps the
    1 ms timer, and an open audio device keeps it even minimized. Headless
    traces like this journal's are what meet it.
  - **Corrected:** this entry first said that with vsync on, `flip` waits
    for the refresh and the tick after it has nothing left to wait. SYS-011
    found that false on the owner's machine: the display runs at 174 Hz, so
    `flip` returns in about 0.2 ms and `tick(62)` paces every real frame.
    The wait column is therefore most of every healthy play row's period
    (p50 11.2 ms in the second end-to-end run below), and the budget's own
    premise, one 60 Hz refresh (`BUDGET_MS`, RND-008.D3), is a question for
    the owner rather than for this trace. Until it is answered the budget
    reads as the 60 fps target, and the report no longer calls a long frame
    "a missed refresh".
- **SYS-010.D5: a long frame is put down to its largest part.** The report
  first split long frames into "the tick's own wait" and the rest. The
  second critic showed a frame long because of its present (work 12 ms,
  present 21 ms) read as a missed refresh with no cause. Each long frame
  is now put down to whichever of update, draw, present, wait and the rest
  of the period took most of it, the first in that order on a tie, and the
  report says how many long frames had work over budget. When the wait
  took any, the report adds that this is the frame cap's sleep overshooting,
  most often under a coarse OS timer, or on a busy machine, not the game's
  work.
- **SYS-010.D6: a play frame that opened an overlay is counted apart.** D3
  labels a row by its update, but its draw is whatever is on top at the
  frame's end. The fourth critic showed the frame that opens the level-up
  cards (a `PlayingState` update) draws the cards' first frame, about
  22 ms every level-up since the cards are a new state each time, so the
  report blamed the play scene's draw for it. The pause was not affected:
  its push frame is a `PausedState` row. A `shown` column now records the
  top state at the frame's end, and an `opened` column whether the
  frame's update changed the top: `Game._step` reads the top after the
  input and compares it, as an object, with the top after the update. A
  play row that opened something other than the run is left out of every
  in-play figure and counted apart by the overlay's name, with how many
  had work over budget. The end banner's wait phase keeps its steady
  frames in play; only the frame that opened it is apart.
  - **Amended after the fifth critic:** the first cut of D6 compared
    `shown` with the row before. A chained level-up defeats that: the pick
    pops the cards in the frame's input and the run's update opens the
    next, so the row shows `LevelUpState` as the one before it did, and
    the fresh cards' first draw (about 35 ms) counted as play again. Only
    the recorder can see it, hence `opened`.

## SYS-010.4: The cold critics' findings, and what changed

### First critic

A critic that had not built it read the diff and the plan cold. Verdict:
FAIL. Its findings, each with the fix and the test that now pins it:

| Finding | Fix | Pinned by |
|---|---|---|
| **Blocker:** a row's period was the previous frame's (`clock.tick`), so every slow frame was reported one row late, under the wrong state and crowd | D2: own-period rows | `test_a_slow_frame_carries_its_time_on_its_own_row` (a real `Game`, the third update sleeps 250 ms and pushes a state; that row, and no other, carries it; since D3 it is the row of the state whose update took the time) |
| A killed session lost every row: they were written only at close | Rows written every 60 or every second, the header at once; `run` and `run_async` close in `finally` | `test_rows_are_written_in_batches_by_count_and_by_time`, `test_a_crash_still_writes_what_was_traced` |
| A file that could not be opened or written raised into the game loop | `FrameTrace.open` answers None and logs; a failed write logs and stops recording | `test_a_file_that_cannot_be_opened_switches_it_off`, `test_a_failed_write_switches_it_off_without_raising` |
| The crowd was read from the top state only: every pause, level-up and run-status frame read as "no run" | `sample` uses `find_playing`, which walks the stack through the new `StateMachine.stack` | `test_the_crowd_is_read_under_a_pause_menu`, and the paused rows of `test_every_frame_is_recorded` |
| The boss was not counted | Counted while it lives, through `Run.targetables()` since the second critic | `test_the_crowd_is_what_the_run_can_target`, `test_the_real_run_counts_a_live_boss` |
| Two runs' seconds merged in the worst-seconds table | Seconds keyed by run; a run begins after frames outside any run or when the run clock goes back | `RunTests` (one test per rule) |
| A truncated or non-numeric row raised a traceback | `load` skips and counts it; the count is printed | `UnreadableRowTests` |
| The report's default missed the packaged game's traces | `newest` reads beside both saves | `test_newest_picks_across_both_saves`, `test_no_argument_reads_the_newest_beside_either_save` |
| The percentile was a third copy | The harness's `_percentile`, imported | the one definition |
| `traces/` would ride into the web build | `ignoreDirs` gains `/traces`; `.gitignore` anchors `/traces/` | by reading `dist/web/pygbag.ini` |
| The present was not shown apart from the draw | `_drawn_at` taken before `flip` | `test_the_present_is_timed_apart_from_the_draw` (flip made 20 ms slow) |

Found while fixing, not by the critic: run separation briefly lost the
only row whose clock had gone back to 0, and two runs merged again;
`RunTests` caught it, and runs are told apart on every row. And
`find_playing` reading the public `StateMachine.stack` broke
`test_run_status.py`'s fake machine, which held the private `_stack`; the
fake now carries `stack` like the real one.

### Second critic

A fresh critic re-judged the fixed work cold. Verdict: FAIL, 3 major and 9
minor. It confirmed the D2 attribution, the in-view count and the
`run_async` crash path by its own probes. Its findings:

| Finding | Fix | Pinned by |
|---|---|---|
| **Major:** a long frame long for its present, or the rest of the period, read as a missed refresh with no cause | D5: each long frame put down to its largest part; long frames crossed with work over budget; the rest of the period shown | `CauseTests` (one frame per part, and a tie) |
| **Major:** a play frame whose update pushed an overlay (a level-up, a boss death) left every in-play figure uncounted | D3: rows are the state whose update ran | `test_a_slow_frame_carries_its_time_on_its_own_row` (the frame that pushes is its updater's row) |
| **Major:** `run_async`, the loop `main.py` runs, had no test; the report's no-argument command was untested | Tests added | `test_a_crash_in_the_browser_loop_still_writes_what_was_traced`, `test_no_argument_reads_the_newest_beside_either_save`, `test_no_argument_and_no_trace_says_how_to_make_one` |
| A crash, or a drained stack, put the unfinished frame's time on the row before it | `Game` keeps the frame that began unrecorded; closing ends the row before it where it began, with its tick | `test_a_frame_that_never_finished_ends_the_row_before_it`, `test_a_drained_stack_ends_the_last_row_where_its_frame_began`, `test_a_normal_quit_finishes_the_last_row_after_its_work` |
| A row cut off inside the crowd columns was read, its missing fields as blanks | Too few or too many fields skip the row | `test_rows_that_cannot_be_read_are_skipped_and_counted` |
| The off cost was described as "one check a frame" | Measured and restated: two clock reads and four checks, 0.13 µs | below |
| The on cost, 14 to 18 µs, did not reproduce (it read 19.8 to 20.9 µs) | Restated as the range over every sitting, 12 to 21 µs | below |
| A missing file was a traceback; a trace from an older recorder read as every row unreadable | Both refused by name | `test_a_missing_file_is_named_not_a_traceback`, `test_a_trace_from_an_older_recorder_is_refused_by_name`; `MainTests` now removes every file its child made, and this session's three stale pre-D4 files were deleted |
| `in_view`, `particles` and `numbers` were recorded but never reported | The crowd table shows the in-view and particle medians | `test_the_crowd_buckets` |
| The real loading screen's frames were never traced in a test (`start_run` settles outside `_step`) | A test steps the real `LoadingState` through `_step` | `test_the_real_loading_screen_is_traced_frame_by_frame` |
| The unpause frame did not "carry the change" as the docs said; it was dropped | D3 | the unpause rows of `test_every_frame_is_recorded`, driven through the real input path |
| `sample` kept a second copy of `Run.targetables()` | It calls it | `test_the_crowd_is_what_the_run_can_target` |

### Third critic

A third fresh critic re-judged cold. Verdict: FAIL, 1 major and 7 minor. It
confirmed D2 to D4, the crash, kill and drained-stack paths, the variable,
run separation, the refusals and both cost figures by its own probes,
among them a 514-frame session through two runs, a level-up, a pause, a
quit, a death, the end banner and the game over. Its findings:

| Finding | Fix | Pinned by |
|---|---|---|
| **Major:** `test_the_present_is_timed_apart_from_the_draw` failed on its own (the first draw after `Game()` builds caches, about 43 ms) and passed only after another test had warmed them | One warm-up frame before `flip` is slowed; that row left out | every test in `test_frame_trace.py` run alone, one process each: all pass |
| A crowd half written (`live` set, `in_view` blank) was read and crashed the report; an empty file read as "an older recorder"; a BOM header was refused; negative numbers were read | Crowd fields all set or all blank, numbers not negative, else the row is skipped; an empty file refused as empty; the header read as `utf-8-sig` | `test_rows_that_cannot_be_read_are_skipped_and_counted`, `test_an_empty_file_is_refused_as_empty`, `test_a_header_an_editor_gave_a_bom_still_reads` |
| The on cost stated only the mean, hiding the batch write once a second | The tail measured and stated (below, the README, the module) | measured |
| The end banner's wait phase, which updates the run, was left out of play | D3: the deepest state the update reached | `test_an_overlay_that_updates_the_state_below_is_that_states_row` |
| Nothing told the owner that a wait-dominated long frame is the OS timer | The report says so when it sees one | `test_long_frames_the_wait_took_are_named_as_the_os_timer` |
| The game imported `csv` at start, web build included | Imported inside `FrameTrace` | `test_the_game_imports_no_csv_unless_it_traces` (a child process imports `game.game`) |
| This branch's index says SYS-011 is free; the D4 cause pointed at a journal not on this branch; the mutant count cannot be reproduced | The index's next free ID moves to SYS-012 with SYS-010.5; the D4 cause names where that journal lives. The mutants stay a throwaway script; each is named below | |
| A broken trace still sampled every frame, and a failing sample would stop the game | A broken trace samples nothing; a failing sample is logged, the rows before it are written, and the trace switches off | `test_a_failed_sample_switches_the_trace_off_not_the_game` |

### Fourth critic

A fourth fresh critic re-judged cold. Verdict: FAIL, 1 major and 4 minor.
Its own end-to-end probe drove a real game through `_step` alone: menu,
hero select, the real loading screen, play, level-ups, a death, every end
banner phase, the game over, a second run, a quit. It confirmed the D3
labels, the run split, a kill losing under a second, the on cost (14.0 to
15.1 µs) and that `StateMachine.updated` changes no gameplay. Its findings:

| Finding | Fix | Pinned by |
|---|---|---|
| **Major:** the frame that opens the level-up cards counted as play, its draw (the cards' first, about 22 ms) blamed on the scene | D6: a `shown` column; play frames that opened an overlay counted apart by name | `test_a_real_level_up_is_a_play_row_that_shows_the_cards` (seed 35, a real level-up), `OpenedOverlayTests` |
| A file that is not UTF-8, a UTF-16 file, a field over the CSV limit each a traceback; an unclosed quote swallowed every row after it | Such files refused by name; the reader takes no quotes (the recorder writes none), so a stray one spoils its own row only | `test_a_file_that_is_not_utf8_csv_is_refused_by_name`, the stray-quote rows of `test_rows_that_cannot_be_read_are_skipped_and_counted` |
| The budget's comment still said the owner's display is 60 Hz; the report called a long frame "a missed refresh"; the OS-timer note named one cause only | Comment and wording corrected (D4); the note names a busy machine too | `test_the_printout_carries_the_answer` |
| An unused import in `game/game.py` | Removed; the lint findings this branch added were meant to be fixed too, but the check missed a new file (see the fifth critic) | `ruff check` |
| The report imported the stress harness's private `_percentile`, and with it the harness's SDL settings | `tools/benchmarks/stats.py`, one `percentile` with no side effects, read by both | `tests/devtools/test_spawn_stress.py` |

### Fifth critic

A fifth fresh critic re-judged cold. Verdict: FAIL, 1 major and 5 minor.
It confirmed every test passing on its own, the tier audit, the refusals,
the crash, drained-stack and quit paths, D2 and D4, and the on cost (14.7
µs at 94 alive, 19.4 µs at 166). Its findings:

| Finding | Fix | Pinned by |
|---|---|---|
| **Major:** a chained level-up's second cards counted as play (the D6 rule compared names with the row before) | D6 amended: the recorder's `opened`, the top compared as an object after the input and after the update | `test_a_chained_level_up_opens_the_next_cards_on_the_pick_frame` (seed 35, a real double level-up picked through the input), `test_an_update_that_swaps_the_top_for_its_like_opened_it`, `test_a_chained_level_up_is_counted_apart_though_the_cards_were_up` |
| The branch added lint findings to `systems/frame_trace.py` (an import block, `open` outside a `with`, a quoted annotation) and an unused `noqa` in `spawn_stress.py`; the fourth round's "every lint finding fixed" was false, because the comparison script read a file absent from the base as clean | Fixed; the comparison now counts findings by rule for every changed or new file, 0 where the base lacks it, and was checked to see a planted finding: 0 added | `ruff check` |
| The stress harness and the report still called the budget "60 Hz" | "the 60 fps target" | `test_the_printout_carries_the_answer` |
| Rows the recorder cannot write were read: timed parts over the period, `in_view` over `live`, a count that is not whole | Skipped and counted | the added rows of `test_rows_that_cannot_be_read_are_skipped_and_counted` |
| A file of blank lines read as an older recorder's | Refused as empty; a blank first line before a header refused as "not a header" | `test_an_empty_file_is_refused_as_empty`, `test_a_file_whose_first_line_is_blank_is_not_a_trace` |
| The README said the packaged game cannot take the flag | It can (`DeathliteGame.exe --trace`); the variable sets it once instead | by reading `main.py` |

**Mutation checks** (a throwaway script, not kept: each mutant is a source
edit, both test modules run against it, the source restored): 63 mutants,
63 caught. The first run of this round missed two, each closed with a
test: `opened` compared by class rather than object (the chained level-up
reads the top after the input, so the class differs there too; an update
that swaps the top for its like now pins the object comparison), and the
half-written-crowd check dropped (the whole-count check caught most such
rows by accident; a row with `live` blank and the rest set did not). The
63 are: the flag ignored; the variable's "0" switching it on; `csv`
imported with the game; the crowd read from the top state only, or from
the enemies instead of the run's targetables; the shown state written as
the updated one; `opened` never recorded, or compared by class; a failed
sample raising into the game, leaving the trace on, or losing the rows
before it; a broken trace still sampling; the D3 label taken at the
frame's end, or from the top updated state rather than the deepest; the D2
blocker put back (each row given the previous frame's start); draw and
present swapped; the D4 wait put on the frame after its tick, timed after
the tick, or never recorded; an unfinished frame's start ignored at close,
or a recorded frame left as unfinished; no `finally` close in `run` or in
`run_async`; no header flush; no batch write by count, none by time; the
last row lost at close; open and write errors raised; a bucket's top edge
dropped; a tie counted draw-bound; paused or loading frames counted as
play; a frame that opened an overlay kept in play, told by its shown state
alone, or by the old name rule; an opening frame kept in the worst
seconds; the every-frame line counting play only; a cause tie settled the
other way; the wait left in the rest of the period; every long frame
counted as over budget; the in-view median read from the crowd; the
OS-timer note always printed, or never; each run-boundary rule dropped; a
non-finite, a negative or a half-written crowd let through; timed parts
over the period, a count that is not whole, more in view than alive, an
`opened` other than 0 or 1 let through; a cut or overlong row let through;
a stray quote swallowing the rows after it; an older header let through;
an empty file, a blank-lines file, a missing file, a file that is not
UTF-8 CSV each mishandled; a BOM header refused; `newest`, or the
command's default, reading one save only.

**The tier audit** (`python -m tools.verification.tier_audit`): 0
under-tiered (the count is in SYS-010.5). `MainTests` (it runs
`main.py --trace`, and imports the game, in child processes) sits with
`GameWiringTests` in the integration tier.

### Sixth critic

A sixth fresh critic re-judged cold. Verdict: **PASS**, no blocker, no
major. Its own probe drove 411 frames through the real `_step` and checked
every row against the stack: the menu, the hero select, the real loading
screen, a single and a chained level-up picked through the input, pause,
unpause and the run-status screen, a death with every end banner phase, the
game over, a second run; 411 written, 411 read, 0 skipped, 2 runs, 4
opening frames apart. It also killed `main.py --trace` mid-run (0.9 s
lost), loaded a synthetic hour-long trace (223,200 rows, 20 MB: 10 s to
load, 6 s to summarise) and found no lint the branch added. Its ten minor
findings, all fixed before the commit:

| Finding | Fix |
|---|---|
| The cap was stated as 16.13 ms; pygame truncates 1000 / 62 to a whole 16 ms (16.008 ms a period measured here with `tick_busy_loop`) | The budget comment, the stress harness's printout and the RND-008 journal's note of that printout say 16 ms; the RND-008 measurement tables keep the figure they were taken against |
| "1.5 x the budget" was called a frame late; it is 25 ms, half a frame | Reworded in the report and the README |
| Two stale journal lines (the critic count; the first critic's row still said "under the new state") | Corrected |
| `wait_ms` was described as all the period holds beyond the work and the present | The docstring names the rest: the input, the music, the trace |
| `percentile` was called nearest-rank; it takes the nearest index, rounding half to even | The docstring says what it does |
| Opening frames said how many were over budget, not whether the update or the draw did it | "update-bound n, draw-bound m" on the counted-apart line; `test_an_opening_frame_over_budget_by_its_update_says_so` |
| "One stored reference a frame" is one per state updated | Reworded in the README and `game.py` |
| `MainTests` found the child's file by process id, which a venv launcher would not share; it left an empty `traces/` | The file is told by being new since the launch; the folder is removed when the test made it |
| Nothing kept the browser build from tracing | `trace_path` answers None on `emscripten`; `test_never_on_the_browser_build` |
| `tools/benchmarks/stats.py` was untracked | Committed with SYS-010.4 |

A stopped run: the last mutation run was cut off by the session ending
after 29 of 65 mutants, with mutant 30 (a tie counted draw-bound) still
written into `trace_report.py`, since only a clean exit restores the file.
It was found by checking that every mutant's original text is in its file
exactly once, put back, the tests re-run green, and the remaining 36
mutants run from where it stopped.

## SYS-010.4: The recorder's cost

**Method:** a throwaway probe, not kept. It builds the stress harness's
seed-35 fight with 100 enemies packed round the hero
(`spawn_stress.build(35, 100, 0, 300.0, config.ENEMY_LOD_SKIP)`) and runs
30 frames. Then it times `sample(game, "PlayingState")`, and `sample` plus
`record`, with `timeit`: 6000 calls (a hundred batches), best of five, no
profiler or wrapper.

| Sitting | `sample` | `sample` + `record` |
|---|---|---|
| First, a test suite running beside it, before D4 | 9.8 to 14.4 µs | 11.8 to 17.1 µs |
| Second, nothing else running | 10.7 to 15.2 µs | 14.0 to 18.1 µs |
| The second critic's own probe, same method | | 19.8 to 20.9 µs |
| Third, after D3 (`targetables()`), nothing else running | 9.6 to 11.2 µs | 11.9 to 13.8 µs |

So 12 to 21 µs a frame on average with 100 alive, depending on the
sitting: about 0.1 % of the 16.67 ms budget, small enough that a trace
does not move what it measures.

**The tail (the third critic's finding, re-measured here):** the rows are
written once a second, and that write lands in one frame's "rest". Its
probe wrapped `flush`, `record` and `sample` in a real session (seed 35,
`start_run`, 1500 `_step` frames); two runs of it here gave writes of 53
to 281 µs, typically 100 to 200 µs, and one write per run far above: 3.6 ms
and 1.3 ms, the second write of the session both times. `record` median
6.9 to 7.5 µs, `sample` median 16.5 to 17.7 µs in that session.

**Off:** `_step` adds two `perf_counter` reads and three
`self.trace is not None` checks, `_render` one check, and
`StateMachine.update` one stored reference per state it updates (D3). That
code, timed with `timeit` (a million calls, best of five, three runs)
against an empty call, adds 0.147 µs a frame.

## SYS-010.4: End to end

A headless session with the trace on, seed 35: 5 menu frames, 5 on the hero
select, the real loading screen stepped frame by frame, 120 run frames, 10
paused, 10 back in play. Then the report on its file. Two runs:

**Before D3 and D5, the stretch on:**

- 181 rows written, 181 read, 0 skipped.
- Period p50 30.9 ms against 6.3 ms of work and 0.6 ms of present, wait
  p50 23.2 ms. The report of the day said "99 (76.7 %); 99 of them the
  tick's own wait". Without D4 the same file would have read as 99
  unexplained long frames.

**After D3 and D5, the stretch off:**

- 180 rows written, 180 read, 0 skipped: the recorder and the report agree
  on every row.
- The frame that finished the load is a `LoadingState` row: period
  92.7 ms, update 56.9 ms (the load's end and `PlayingState.enter`),
  carrying the run it built. The next row, the first `PlayingState` row,
  has an update of 1.5 ms.
- 130 frames in play, the unpause frame among them; 0 over budget, 0
  long. Period p50 16.73 ms: work 4.6 ms, present 0.6 ms, wait 11.2 ms.
- What a row's four timed parts do not cover (the input, the music, the
  sample) is 0.02 to 4.7 ms.
