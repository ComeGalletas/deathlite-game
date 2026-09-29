"""A frame-time trace of real play (SYS-010, `frame_trace_journal.md`).

`python main.py --trace` (or `DEATHLITE_TRACE=1`, for the packaged exe)
writes one CSV per session with a row per frame:

    t            seconds since the trace began
    frame_ms     the frame's period, `clock.tick`'s raw value (the vsync
                 cadence included)
    update_ms    the state machine's update
    draw_ms      drawing the frame, before it is presented
    present_ms   `display.flip()`: the upload and the vsync wait
    state        the top state's class name (`PlayingState`,
                 `PausedState`, `MenuState`, ...)
    live         enemies alive in the run, or blank outside a run
    in_view      of those, how many the camera shows
    particles    live particles
    numbers      floating damage numbers
    run_time     the run's own clock, in seconds

`tools/benchmarks/trace_report.py` reads it. The rows are buffered and
written every `FLUSH_EVERY` frames and at the end, so a trace costs a
list append per frame, plus the sample (measured in the journal).
Nothing is recorded, and nothing is opened, unless the trace is switched
on.
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path

COLUMNS = ("t", "frame_ms", "update_ms", "draw_ms", "present_ms", "state",
           "live", "in_view", "particles", "numbers", "run_time")
ENV = "DEATHLITE_TRACE"
FLUSH_EVERY = 600          # frames between writes: ten seconds at 60 fps


def trace_path(argv, environ, save_path) -> Path | None:
    """The file to trace this session into, or None when tracing is off.

    On with `--trace` among the arguments, or with `DEATHLITE_TRACE` set to
    anything but empty or "0" (the packaged exe has no terminal to pass a
    flag from). The file goes in a `traces/` folder beside the save, named
    by the session's start time, so a trace never lands in the repo's
    tracked files and two sessions never share one."""
    flag = "--trace" in argv
    env = environ.get(ENV, "")
    if not flag and env in ("", "0"):
        return None
    folder = Path(save_path).parent / "traces"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return folder / f"frames-{stamp}-{os.getpid()}.csv"


def sample(game) -> tuple:
    """`(state, live, in_view, particles, numbers, run_time)` for the frame
    just drawn. The run is found anywhere on the stack, so a frame under
    the pause menu or the level-up cards still carries its crowd. Outside
    a run the crowd fields are None (written blank)."""
    stack = game.state_machine.stack
    top = type(stack[-1]).__name__ if stack else ""
    run = next((getattr(s, "run", None) for s in reversed(stack)
                if getattr(s, "run", None) is not None), None)
    if run is None:
        return top, None, None, None, None, None
    enemies = run.enemies
    view = run.camera.visible_rect()
    in_view = sum(1 for e in enemies if view.collidepoint(e.pos.x, e.pos.y))
    return (top, len(enemies), in_view, len(run.particles), len(run.damage_numbers),
            float(run.stats.get("time", 0.0)))


class FrameTrace:
    """One session's rows, written to `path` as CSV."""

    def __init__(self, path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(COLUMNS)
        self._file.flush()                 # a valid (empty) trace from the first frame
        self._rows: list[tuple] = []
        self._start = time.perf_counter()
        self.frames = 0

    def record(self, frame_ms: float, update_ms: float, draw_ms: float,
               present_ms: float, sampled: tuple) -> None:
        state, live, in_view, particles, numbers, run_time = sampled
        self._rows.append((
            f"{time.perf_counter() - self._start:.4f}", f"{frame_ms:.3f}",
            f"{update_ms:.3f}", f"{draw_ms:.3f}", f"{present_ms:.3f}", state,
            "" if live is None else live, "" if in_view is None else in_view,
            "" if particles is None else particles, "" if numbers is None else numbers,
            "" if run_time is None else f"{run_time:.3f}"))
        self.frames += 1
        if len(self._rows) >= FLUSH_EVERY:
            self.flush()

    def flush(self) -> None:
        if self._rows:
            self._writer.writerows(self._rows)
            self._rows.clear()
            self._file.flush()

    def close(self) -> None:
        if self._file.closed:
            return
        self.flush()
        self._file.close()
