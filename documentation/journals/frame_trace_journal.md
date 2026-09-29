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
  - When off, it costs one check a frame. When on, its per-frame cost is
    measured and stated.
  - It changes no gameplay. It never writes into the repo (the files go
    beside the save, in a gitignored `traces/`).

## SYS-010: Plan

- **SYS-010.2: The recorder:**
  - `systems/frame_trace.py`: `FrameTrace`, one CSV per session, buffered.
  - `sample(game)`: the state's name, the enemies live and in view, the
    particles, the damage numbers, the run clock. Read defensively, so a
    menu frame is recorded too.
  - `trace_path(argv, environ, save_path)`: whether to trace, and to
    which file.
  - `Game` takes the trace and times the update, the draw and the present
    (`display.flip`, the vsync wait) apart. It records the raw frame
    period from `clock.tick`.
  - `main.py` passes `trace_path(...)`. `.gitignore` gains `traces/`.
- **SYS-010.3: The report,** `python -m tools.benchmarks.trace_report FILE`:
  - frames over the budget, in play and overall, as work (update + draw)
    and as long frames (a skipped refresh);
  - p50 / p90 / p99 of the frame, the update, the draw and the present;
  - the same by crowd size;
  - update-bound against draw-bound among the misses;
  - the worst seconds.
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
- [ ] SYS-010.2: The recorder and its wiring (`--trace`, `DEATHLITE_TRACE`, `traces/` beside the save)
- [ ] SYS-010.3: The report
- [ ] SYS-010.4: Tests, the recorder's measured cost, the how-to
- [ ] SYS-010.5: Results; index to done
