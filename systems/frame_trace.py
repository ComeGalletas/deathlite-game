"""A frame-time trace of real play (SYS-010, `frame_trace_journal.md`).

`python main.py --trace` (or `DEATHLITE_TRACE=1`, for the packaged exe)
writes one CSV per session with a row per frame:

    t            seconds from the trace's start to this frame's start
    frame_ms     this frame's own period: from the start of its work to the
                 start of the next frame's (so its update, draw, present and
                 the wait for the next tick), timed with `perf_counter`
    update_ms    the state machine's update
    draw_ms      drawing the frame, before it is presented
    present_ms   `display.flip()`: the upload and the vsync wait
    wait_ms      `clock.tick` after the frame, the cap's own wait (0 for
                 the last frame, which no tick follows). The period is the
                 update, the draw, the present, this wait, and the rest:
                 the input, the music, the trace's own sample and writes
    state        the class name of the deepest state the frame's update
                 reached (`StateMachine.updated`, SYS-010.D3): the run's own
                 `PlayingState` whenever the run was updated, under the end
                 banner's wait phase too; `PausedState`, `LevelUpState` and
                 the like over a frozen run; `LoadingState`, `MenuState`, ...
                 So a play frame that pushes the level-up cards is a
                 `PlayingState` row, and the frame that finishes the load is
                 a `LoadingState` row.
    shown        the top state's class name at the frame's end: what it
                 drew last
    opened       1 when the frame's update left a different state on top
                 than the one it began under, read after the input and
                 compared as objects, else 0. So a chained level-up counts
                 (the pick pops the cards in the input, the update opens
                 the next), and so does an update that swaps the top for a
                 new state of the same kind. A `PlayingState` row with
                 `opened` 1 drew that overlay's first frame (SYS-010.D6).
    live         bodies alive in the run at the frame's end (the run's
                 `targetables()`: the enemies, and the boss while it lives),
                 blank outside a run
    in_view      of those, how many the camera shows
    particles    live particles
    numbers      floating damage numbers
    run_time     the run's own clock, in seconds

A row is written once the next frame begins, because only then is its
period known; the last one when the trace closes.
`tools/benchmarks/trace_report.py` reads it.

The rows are buffered and written every `FLUSH_EVERY` rows or
`FLUSH_SECONDS`, whichever comes first, and when the trace closes, also when
the game loop dies of an exception (`Game.run`, `Game.run_async`). Then,
or when the stack drains, the frame that never finished gets no row; the
row before it ends where that frame began, with that frame's tick as its
wait. A killed process loses at most about a second. A trace that cannot open or write its file logs why
and stops recording, and so does a sample that fails; it never stops the
game. Nothing is recorded, and nothing is opened or imported beyond this
module, unless the trace is switched on.

The on cost (the journal): 12 to 21 µs a frame on average with 100 alive,
plus the batch write once a second: typically 0.1 to 0.3 ms, and an odd
write of 1 to 4 ms (the second of a session, in the journal's runs). That
lands in the frame's `other`.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

COLUMNS = ("t", "frame_ms", "update_ms", "draw_ms", "present_ms", "wait_ms", "state",
           "shown", "opened", "live", "in_view", "particles", "numbers", "run_time")
ENV = "DEATHLITE_TRACE"
# The frame budget: 60 frames a second, 16.67 ms (RND-008.D3). The game
# caps itself at `config.FPS` with `clock.tick`: 62, which pygame turns
# into a whole 16 ms (it truncates 1000 / 62; 16.008 ms a period
# measured with `tick_busy_loop`). It was set
# as one 60 Hz vsync period; SYS-011 found the owner's display runs at
# 174 Hz, where `flip` returns at once and the cap alone paces, so it reads
# as the frame-rate target rather than a refresh (owner, 2026-09-30: it
# stays the 60 fps target). The one copy: the stress harness and the
# trace report both read it from here.
BUDGET_MS = 1000.0 / 60.0
# A batch is written after this many rows or this much time, whichever
# comes first: a trace is most wanted when a session ends badly, and a
# killed process never reaches the last write (SYS-010.4).
FLUSH_EVERY = 60
FLUSH_SECONDS = 1.0


def trace_path(argv, environ, save_path, platform: str = sys.platform) -> Path | None:
    """The file to trace this session into, or None when tracing is off.

    On with `--trace` among the arguments, or with `DEATHLITE_TRACE` set to
    anything but empty or "0" (for the packaged exe, where a variable can
    be set once instead of passing the flag at each start). The file goes in a `traces/` folder beside the save, named
    by the session's start time and process, so a trace never lands in the
    repo's tracked files and two sessions never share one. Never on the
    browser build (`emscripten`), whatever its arguments or environment."""
    if platform == "emscripten":
        return None                        # the browser build has no disk to trace to
    flag = "--trace" in argv
    env = environ.get(ENV, "")
    if not flag and env in ("", "0"):
        return None
    folder = Path(save_path).parent / "traces"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return folder / f"frames-{stamp}-{os.getpid()}.csv"


def sample(game, state: str, opened: bool = False) -> tuple:
    """`(state, shown, opened, live, in_view, particles, numbers, run_time)`
    for the frame just drawn; `state` is the deepest one its update reached
    and `opened` whether that update changed the top state (`Game._step`
    reads both), `shown` the top of the stack now."""
    stack = game.state_machine.stack
    shown = type(stack[-1]).__name__ if stack else ""
    return (state, shown, 1 if opened else 0) + _crowd(game)


def _crowd(game) -> tuple:
    """`(live, in_view, particles, numbers, run_time)`. The run is the one
    `run_status_state.find_playing` finds, so a frame under the pause menu,
    the level-up cards or the run-status screen still carries its crowd.
    Outside a run the crowd fields are None (written blank)."""
    from game.states.run_status_state import find_playing

    run = getattr(find_playing(game.state_machine), "run", None)
    if run is None:
        return None, None, None, None, None
    bodies = run.targetables()
    view = run.camera.visible_rect()
    in_view = sum(1 for e in bodies if view.collidepoint(e.pos.x, e.pos.y))
    return (len(bodies), in_view, len(run.particles), len(run.damage_numbers),
            float(run.stats.get("time", 0.0)))


class FrameTrace:
    """One session's rows, written to `path` as CSV. Build it with `open`,
    which answers None (and logs why) when the file cannot be made."""

    def __init__(self, path) -> None:
        # `csv` here, not at the top: the web build never traces.
        import csv

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open for the session and closed by `close`, not by a `with` block.
        self._file = open(self.path, "w", newline="", encoding="utf-8")  # noqa: SIM115
        self._writer = csv.writer(self._file)
        self._writer.writerow(COLUMNS)
        self._file.flush()                 # a valid (empty) trace from the first frame
        self._rows: list[tuple] = []
        self._pending: tuple | None = None
        self._origin: float | None = None
        self._last_flush = time.perf_counter()
        self.frames = 0
        self.broken = False

    @classmethod
    def open(cls, path) -> FrameTrace | None:
        try:
            return cls(path)
        except OSError as exc:
            log.warning("frame trace off: cannot write %s (%s)", path, exc)
            return None

    def sample(self, game, state: str, opened: bool = False) -> tuple | None:
        """`sample(game, state, opened)`, or None when it fails; `record`
        then switches the trace off (logged) rather than stopping the game."""
        try:
            return sample(game, state, opened)
        except Exception:                  # a tracing bug must never end a run
            log.exception("frame trace off: sampling the frame failed")
            return None

    def record(self, start: float, waited_ms: float, update_ms: float, draw_ms: float,
               present_ms: float, sampled: tuple | None) -> None:
        """Frame at `start` (a `perf_counter` time, taken when its work
        began, after `waited_ms` in `clock.tick`) took these times and ended
        in this state. The frame before it is written now: its period is
        `start` minus its own start, and the tick that ended it was this
        frame's `waited_ms`."""
        if self.broken:
            return
        if self._origin is None:
            self._origin = start
        self._finish(start, waited_ms)
        if sampled is None:                # the sample failed: keep what came before, stop
            self.flush()
            self.broken = True
            return
        self._pending = (start, update_ms, draw_ms, present_ms, sampled)
        if len(self._rows) >= FLUSH_EVERY or start - self._last_flush >= FLUSH_SECONDS:
            self.flush()

    def _finish(self, until: float, waited_ms: float) -> None:
        if self._pending is None:
            return
        start, update_ms, draw_ms, present_ms, sampled = self._pending
        state, shown, opened, live, in_view, particles, numbers, run_time = sampled
        self._rows.append((
            f"{start - self._origin:.4f}", f"{(until - start) * 1000.0:.3f}",
            f"{update_ms:.3f}", f"{draw_ms:.3f}", f"{present_ms:.3f}", f"{waited_ms:.3f}", state, shown, opened,
            "" if live is None else live, "" if in_view is None else in_view,
            "" if particles is None else particles, "" if numbers is None else numbers,
            "" if run_time is None else f"{run_time:.3f}"))
        self._pending = None
        self.frames += 1

    def flush(self) -> None:
        if self._rows and not self.broken:
            try:
                self._writer.writerows(self._rows)
                self._file.flush()
            except OSError as exc:
                log.warning("frame trace off: writing %s failed (%s)", self.path, exc)
                self.broken = True
            self._rows.clear()
        self._last_flush = time.perf_counter()

    def close(self, until: float | None = None, waited_ms: float = 0.0) -> None:
        """Write the last row and close. `until` is where the last row's
        period ends: now by default, or the start of a frame that began and
        never finished (a crash, a drained stack), whose tick, `waited_ms`,
        ended the last row. Twice is harmless."""
        if self._file.closed:
            return
        self._finish(time.perf_counter() if until is None else until, waited_ms)
        self.flush()
        try:
            self._file.close()
        except OSError:
            pass

