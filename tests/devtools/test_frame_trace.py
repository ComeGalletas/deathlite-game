"""SYS-010: the frame-time trace of real play (`frame_trace_journal.md`).

What is pinned:
* **the switch:** off by default; on with `--trace` or with `DEATHLITE_TRACE`
  set (not empty, not "0"); the file lands in `traces/` beside the save;
  `main.py` itself, launched with `--trace`, logs and writes one;
* **the recorder:** one header, one row per frame, each row's period its own
  (from its start to the next frame's) and the tick wait that ended it on
  that same row, the last finished at close; rows
  written in batches by count and by time; blanks outside a run; a file
  that cannot be opened or written switches the trace off, never raises;
* **the sample:** the updating state's name, the state shown at the
  frame's end, whether the update opened it (by object, so a chained
  level-up counts), the crowd found under a pause menu, the bodies the run can target (the boss included while it lives);
* **the wiring:** a real `Game` records every frame through menu, run,
  pause and unpause, each row under the deepest state its update reached
  (the frame that pushes the pause is a pause row, the one that pops it a
  play row, the frame that finishes the real loading screen a loading row,
  a frame under an overlay that updates the state below that state's row);
  a sample that fails switches the trace off, never the game, and a trace
  that is off samples nothing more; the game never imports `csv` unless it
  traces; a
  frame made slow carries the time on its own row, and so does a slow tick;
  the parts never add up to more than the period; the present is timed
  apart from the draw; a crash, in `run` and in `run_async`, still writes
  what was traced, and a frame that never finished (a crash, a drained
  stack) ends the row before it where it began; no trace, no file.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pygame

from game.state import State
from systems import frame_trace as FT

ROOT = Path(__file__).resolve().parents[2]
FRAME, DRAW, PRESENT, WAIT, STATE, SHOWN, OPENED, LIVE = (
    FT.COLUMNS.index(c) for c in ("frame_ms", "draw_ms", "present_ms", "wait_ms", "state", "shown",
                                  "opened", "live"))


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def _tmp(case) -> str:
    d = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, d, True)
    return d


class TracePathTests(unittest.TestCase):
    def setUp(self):
        self.save = os.path.join(_tmp(self), "save.json")

    def test_off_by_default(self):
        self.assertIsNone(FT.trace_path(["main.py"], {}, self.save))
        for off in ("", "0"):
            with self.subTest(env=off):
                self.assertIsNone(FT.trace_path(["main.py"], {FT.ENV: off}, self.save))

    def test_never_on_the_browser_build(self):
        for argv, env in ((["main.py", "--trace"], {}), (["main.py"], {FT.ENV: "1"})):
            with self.subTest(argv=argv, env=env):
                self.assertIsNone(FT.trace_path(argv, env, self.save, platform="emscripten"))
                self.assertIsNotNone(FT.trace_path(argv, env, self.save, platform="win32"))

    def test_the_flag_or_the_variable_switches_it_on(self):
        for argv, env in ((["main.py", "--trace"], {}), (["main.py"], {FT.ENV: "1"}),
                          (["DeathliteGame.exe"], {FT.ENV: "yes"})):
            with self.subTest(argv=argv, env=env):
                p = FT.trace_path(argv, env, self.save)
                self.assertEqual(p.parent, Path(self.save).parent / "traces")
                self.assertEqual(p.suffix, ".csv")
                self.assertTrue(p.name.startswith("frames-"))


ONE = ("MenuState", "MenuState", 0, None, None, None, None, None)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(_tmp(self)) / "traces" / "t.csv"

    def test_each_row_has_its_own_period(self):
        tr = FT.FrameTrace(self.path)
        # Each frame is handed the tick it waited through before it; that
        # wait ended the frame before, so it lands on the row before.
        tr.record(100.0, 7.0, 5.25, 9.5, 1.125,
                  ("PlayingState", "LevelUpState", 1, 113, 95, 40, 7, 12.5))
        tr.record(100.016, 0.5, 0.5, 2.0, 0.25, ONE)        # 16 ms after the first began
        tr.record(100.066, 30.0, 0.5, 2.0, 0.25, ONE)       # 50 ms after the second
        tr.close()
        rows = _rows(self.path)
        self.assertEqual(rows[0], list(FT.COLUMNS))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1], ["0.0000", "16.000", "5.250", "9.500", "1.125", "0.500",
                                   "PlayingState", "LevelUpState", "1", "113", "95", "40",
                                   "7", "12.500"])
        self.assertEqual(rows[2][:2], ["0.0160", "50.000"])
        self.assertEqual(rows[2][5], "30.000")
        self.assertEqual(rows[2][6:], ["MenuState", "MenuState", "0", "", "", "", "", ""])
        self.assertGreaterEqual(float(rows[3][1]), 0.0)     # the last: finished at close
        self.assertEqual(rows[3][5], "0.000")               # and no tick followed it
        self.assertEqual(tr.frames, 3)

    def test_rows_are_written_in_batches_by_count_and_by_time(self):
        with mock.patch.object(FT, "FLUSH_EVERY", 3), mock.patch.object(FT, "FLUSH_SECONDS", 1e9):
            tr = FT.FrameTrace(self.path)
            for i in range(3):
                tr.record(float(i), 0.0, 1.0, 1.0, 1.0, ONE)
            self.assertEqual(len(_rows(self.path)), 1)            # two finished, one pending
            tr.record(3.0, 0.0, 1.0, 1.0, 1.0, ONE)
            self.assertEqual(len(_rows(self.path)), 4)            # three finished: a batch
            tr.close()
            tr.close()                                            # twice is harmless
        self.assertEqual(len(_rows(self.path)), 5)
        with mock.patch.object(FT, "FLUSH_SECONDS", 0.0):
            path = self.path.with_name("u.csv")
            tr = FT.FrameTrace(path)
            now = time.perf_counter()                             # the game's clock
            tr.record(now, 0.0, 1.0, 1.0, 1.0, ONE)
            tr.record(now + 0.016, 0.0, 1.0, 1.0, 1.0, ONE)
            self.assertEqual(len(_rows(path)), 2)                 # written at once: time's up
            tr.close()

    def test_a_file_that_cannot_be_opened_switches_it_off(self):
        blocker = Path(_tmp(self)) / "a-file"
        blocker.write_text("x")
        with self.assertLogs("systems.frame_trace", "WARNING"):
            self.assertIsNone(FT.FrameTrace.open(blocker / "traces" / "t.csv"))

    def test_a_failed_write_switches_it_off_without_raising(self):
        tr = FT.FrameTrace(self.path)
        tr.record(0.0, 0.0, 1.0, 1.0, 1.0, ONE)
        tr.record(1.0, 0.0, 1.0, 1.0, 1.0, ONE)
        with mock.patch.object(tr, "_writer", SimpleNamespace(writerows=mock.Mock(side_effect=OSError("disk full")))), \
                self.assertLogs("systems.frame_trace", "WARNING"):
            tr.flush()
        self.assertTrue(tr.broken)
        tr.record(2.0, 0.0, 1.0, 1.0, 1.0, ONE)                        # ignored, no error
        tr.close()


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.b = (x0, y0, x1, y1)

    def collidepoint(self, x, y):
        x0, y0, x1, y1 = self.b
        return x0 <= x < x1 and y0 <= y < y1


class _PausedState:
    pass


class SampleTests(unittest.TestCase):
    def _playing(self, extra=()):
        body = lambda x, y: SimpleNamespace(pos=pygame.Vector2(x, y))
        enemies = [body(10, 10), body(50, 50), body(500, 500)]
        run = SimpleNamespace(
            enemies=enemies, targetables=lambda: enemies + [body(*p) for p in extra],
            camera=SimpleNamespace(visible_rect=lambda: _Rect(0, 0, 100, 100)),
            particles=[1, 2, 3, 4], damage_numbers=[1, 2], stats={"time": 42.5})
        return SimpleNamespace(player=object(), stats=run.stats, run=run)

    def _game(self, *states):
        return SimpleNamespace(state_machine=SimpleNamespace(stack=tuple(states)))

    def test_a_menu_frame_has_no_crowd(self):
        self.assertEqual(FT.sample(self._game(SimpleNamespace()), "MenuState"),
                         ("MenuState", "SimpleNamespace", 0, None, None, None, None, None))

    def test_a_run_frame_counts_its_crowd(self):
        self.assertEqual(FT.sample(self._game(self._playing()), "PlayingState"),
                         ("PlayingState", "SimpleNamespace", 0, 3, 2, 4, 2, 42.5))

    def test_the_crowd_is_read_under_a_pause_menu(self):
        got = FT.sample(self._game(self._playing(), _PausedState()), "PausedState", opened=True)
        self.assertEqual(got, ("PausedState", "_PausedState", 1, 3, 2, 4, 2, 42.5))

    def test_the_crowd_is_what_the_run_can_target(self):
        # `Run.targetables()`: the enemies, and the boss while it lives;
        # one rule, read from the run, not a second copy of it.
        got = FT.sample(self._game(self._playing(extra=[(20, 20)])), "PlayingState")
        self.assertEqual(got[3:5], (4, 3))

    def test_the_real_run_counts_a_live_boss(self):
        from game.states.playing.core.run import Run

        boss = SimpleNamespace(alive=True)
        run = SimpleNamespace(enemies=[1, 2], boss=boss)
        self.assertEqual(len(Run.targetables(run)), 3)
        boss.alive = False
        self.assertEqual(len(Run.targetables(run)), 2)


class _Overlay(State):
    """A do-nothing overlay pushed by a test."""
    draw_below = True


class GameWiringTests(unittest.TestCase):
    """A real `Game`, headless, seed 35."""

    def _game(self):
        from game.game import Game

        d = _tmp(self)
        path = FT.trace_path(["main.py", "--trace"], {}, os.path.join(d, "save.json"))
        return Game(save_path=os.path.join(d, "save.json"), trace_path=path), path

    def test_every_frame_is_recorded(self):
        # The pause is pushed and popped through the real input path, inside
        # the frame: the frame that pushes it runs the pause's update, the
        # one that pops it runs the run's.
        from tests.boot import start_run

        def escape():
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

        g, path = self._game()
        g._start()
        for _ in range(4):
            g._step()
        start_run(g, 35)
        for _ in range(6):
            g._step()
        escape()
        for _ in range(3):
            g._step()
        escape()
        for _ in range(2):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        self.assertEqual(len(rows), 15)
        self.assertEqual([r[STATE] for r in rows], ["MenuState"] * 4 + ["PlayingState"] * 6
                         + ["PausedState"] * 3 + ["PlayingState"] * 2)
        self.assertTrue(all(r[LIVE] == "" for r in rows[:4]))                  # no crowd in the menu
        self.assertTrue(all(r[LIVE] != "" for r in rows[4:]))                  # the run's, under the pause too
        for r in rows:
            frame, update, draw, present, wait = map(float, r[FRAME:WAIT + 1])
            self.assertTrue(frame >= 0 and update >= 0 and draw > 0 and present >= 0
                            and wait >= 0, r)
            # The parts are disjoint spans inside the period.
            self.assertLessEqual(update + draw + present + wait, frame + 0.01, r)

    def test_a_slow_frame_carries_its_time_on_its_own_row(self):
        # The third frame's update takes 250 ms and pushes a new state, as a
        # level-up does: that row, and no other, carries the time, under the
        # state whose update took it; the rows after are the new state's.
        g, path = self._game()
        g._start()
        real, n = g.state_machine.update, [0]

        def update(dt):
            real(dt)
            n[0] += 1
            if n[0] == 3:
                time.sleep(0.25)
                g.state_machine.push(_Overlay(g))

        g.state_machine.update = update
        for _ in range(6):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        periods = [float(r[FRAME]) for r in rows]
        self.assertGreaterEqual(periods[2], 250.0, periods)
        self.assertTrue(all(p < 250.0 for i, p in enumerate(periods) if i != 2), periods)
        self.assertEqual([r[STATE] for r in rows], ["MenuState"] * 3 + ["_Overlay"] * 3)
        self.assertEqual([r[SHOWN] for r in rows], ["MenuState"] * 2 + ["_Overlay"] * 4)
        self.assertEqual([r[OPENED] for r in rows], ["0", "0", "1", "0", "0", "0"])

    def test_a_slow_tick_lands_on_the_row_it_ended(self):
        # The third tick sleeps 80 ms. It is the wait after the second
        # frame, so the second row carries it, as wait and as period.
        g, path = self._game()
        g._start()
        real, n = g.clock, [0]

        class Clock:
            def tick(self, fps=0):
                n[0] += 1
                if n[0] == 3:
                    time.sleep(0.08)
                return real.tick(fps)

            def __getattr__(self, name):
                return getattr(real, name)

        g.clock = Clock()
        for _ in range(5):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        waits = [float(r[WAIT]) for r in rows]
        self.assertGreaterEqual(waits[1], 80.0, waits)
        self.assertGreaterEqual(float(rows[1][FRAME]), waits[1], rows[1])
        self.assertTrue(all(w < 80.0 for i, w in enumerate(waits) if i != 1), waits)

    def test_the_present_is_timed_apart_from_the_draw(self):
        # One frame first: the first draw after `Game()` builds its caches
        # (about 40 ms), which would read as a slow draw on its own.
        g, path = self._game()
        g._start()
        g._step()
        real_flip = pygame.display.flip
        with mock.patch.object(pygame.display, "flip", lambda: (time.sleep(0.02), real_flip())):
            for _ in range(3):
                g._step()
        g.trace.close()
        for r in _rows(path)[2:]:
            self.assertGreaterEqual(float(r[PRESENT]), 20.0, r)
            self.assertLess(float(r[DRAW]), 20.0, r)

    def test_an_overlay_that_updates_the_state_below_is_that_states_row(self):
        # The end banner's wait phase runs the run under it; its frames are
        # the run's. Once it freezes what is below, they are its own.
        g, path = self._game()
        g._start()
        g._step()
        overlay = _Overlay(g)
        overlay.update_below = True
        g.state_machine.push(overlay)
        for _ in range(2):
            g._step()
        overlay.update_below = False
        for _ in range(2):
            g._step()
        g.trace.close()
        self.assertEqual([r[STATE] for r in _rows(path)[1:]],
                         ["MenuState"] * 3 + ["_Overlay"] * 2)

    def test_a_failed_sample_switches_the_trace_off_not_the_game(self):
        g, path = self._game()
        g._start()
        g._step()
        calls = [0]

        def broken(game, state, opened=False):
            calls[0] += 1
            raise AttributeError("a state the sample did not expect")

        with mock.patch.object(FT, "sample", broken), \
                self.assertLogs("systems.frame_trace", "ERROR"):
            for _ in range(3):
                g._step()                            # the game goes on
        self.assertTrue(g.trace.broken)
        self.assertEqual(calls[0], 1)                # and samples nothing more
        g._close_trace()
        self.assertEqual(len(_rows(path)) - 1, 1)    # what came before is kept

    def test_a_real_level_up_is_a_play_row_that_shows_the_cards(self):
        # Seed 35. The frame whose update levels the hero up runs the run's
        # update and draws the cards' first frame: a `PlayingState` row
        # shown as `LevelUpState`; the frames on the cards are theirs.
        from progression.experience import xp_for_level
        from tests.boot import start_run

        g, path = self._game()
        g._start()
        ps = start_run(g, 35)
        for _ in range(3):
            g._step()
        lv = ps.run.levels
        lv.add_xp(xp_for_level(lv.level) - lv.xp_into_level)
        steps = 0
        while type(g.state_machine.current).__name__ != "LevelUpState":
            g._step()
            steps += 1
            self.assertLess(steps, 30, "the level-up never opened")
        for _ in range(2):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        push = rows[3 + steps - 1]
        self.assertEqual((push[STATE], push[SHOWN], push[OPENED]),
                         ("PlayingState", "LevelUpState", "1"))
        self.assertEqual([(r[STATE], r[SHOWN]) for r in rows[3 + steps:]],
                         [("LevelUpState", "LevelUpState")] * 2)

    def test_an_update_that_swaps_the_top_for_its_like_opened_it(self):
        # Compared as objects: an update that replaces the top state with a
        # new one of the same kind (fresh cards for the old) opened it,
        # though the name shown is the same before and after.
        g, path = self._game()
        g._start()
        swaps = [0]

        class Swapping(_Overlay):
            def update(self, dt):
                if swaps[0] == 0:
                    swaps[0] += 1
                    self.game.state_machine.pop()
                    self.game.state_machine.push(Swapping(self.game))

        g.state_machine.push(Swapping(g))
        swaps[0] = 1                                 # no swap on this first frame
        g._step()
        swaps[0] = 0                                 # the next update swaps
        for _ in range(2):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        self.assertEqual([(r[SHOWN], r[OPENED]) for r in rows],
                         [("Swapping", "0"), ("Swapping", "1"), ("Swapping", "0")])

    def test_a_chained_level_up_opens_the_next_cards_on_the_pick_frame(self):
        # Seed 35, two levels pending. The pick pops the cards in the
        # frame's input and the run's update opens the next ones: the row
        # still shows `LevelUpState`, as the one before it did, and is
        # marked opened, because the cards on top are new.
        from progression.experience import xp_for_level
        from tests.boot import start_run

        g, path = self._game()
        g._start()
        ps = start_run(g, 35)
        for _ in range(3):
            g._step()
        lv = ps.run.levels
        lv.add_xp(xp_for_level(lv.level) - lv.xp_into_level + xp_for_level(lv.level + 1) + 1)
        steps = 0
        while type(g.state_machine.current).__name__ != "LevelUpState":
            g._step()
            steps += 1
            self.assertLess(steps, 30, "the level-up never opened")
        for _ in range(3):
            g._step()
        first = g.state_machine.current
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1",
                                             mod=0, scancode=0))
        g._step()
        self.assertIsNot(g.state_machine.current, first, "the second cards did not open")
        g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        pick, after = rows[-2], rows[-1]
        self.assertEqual((pick[STATE], pick[SHOWN], pick[OPENED]),
                         ("PlayingState", "LevelUpState", "1"))
        self.assertEqual((rows[-3][SHOWN], rows[-3][OPENED]), ("LevelUpState", "0"))
        self.assertEqual((after[STATE], after[OPENED]), ("LevelUpState", "0"))

    def test_the_real_loading_screen_is_traced_frame_by_frame(self):
        # Menu, hero select, then the real `LoadingState` stepped through
        # `_step` until the run is up. The frame that finishes the load is a
        # loading row (its update was the loading screen's) and the first to
        # carry the run's crowd, which it built.
        from game.states.loading_state import LoadingState
        from game.states.playing.core.state import PlayingState

        g, path = self._game()
        g._start()
        for _ in range(2):
            g._step()
        g.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        for _ in range(2):
            g._step()
        cs = g.state_machine.current
        g.state_machine.change(LoadingState(g), seed=35, character_id=cs.hero_id,
                               difficulty=cs.difficulty, main_weapon=cs.main_weapon(cs.hero_id))
        loading = 0
        while not isinstance(g.state_machine.current, PlayingState):
            g._step()
            loading += 1
            self.assertLess(loading, 600, "the load never finished")
        for _ in range(3):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        states = [r[STATE] for r in rows]
        self.assertEqual(states, ["MenuState"] * 2 + ["CharacterSelectState"] * 2
                         + ["LoadingState"] * loading + ["PlayingState"] * 3)
        loads = rows[4:4 + loading]
        self.assertTrue(all(r[LIVE] == "" for r in loads[:-1]))
        self.assertNotEqual(loads[-1][LIVE], "")

    def test_a_frame_that_never_finished_ends_the_row_before_it(self):
        # The fourth update sleeps 200 ms and raises. That frame gets no
        # row; the row before it ends where it began, not at the crash.
        g, path = self._game()
        real, n = g.state_machine.update, [0]

        def update(dt):
            n[0] += 1
            if n[0] == 4:
                time.sleep(0.2)
                raise RuntimeError("the game fell over")
            real(dt)

        g.state_machine.update = update
        with self.assertRaises(RuntimeError):
            g.run()
        rows = _rows(path)[1:]
        self.assertEqual(len(rows), 3)
        last = rows[-1]
        self.assertLess(float(last[FRAME]), 150.0, last)
        self.assertGreaterEqual(float(last[FRAME]), float(last[WAIT]), last)

    def test_a_normal_quit_finishes_the_last_row_after_its_work(self):
        g, path = self._game()
        real, n = g.state_machine.update, [0]

        def update(dt):
            real(dt)
            n[0] += 1
            if n[0] == 3:
                g.running = False

        g.state_machine.update = update
        g.run()
        rows = _rows(path)[1:]
        self.assertEqual(len(rows), 3)
        frame, update_ms, draw, present = map(float, rows[-1][FRAME:PRESENT + 1])
        self.assertGreaterEqual(frame, update_ms + draw + present, rows[-1])

    def test_a_drained_stack_ends_the_last_row_where_its_frame_began(self):
        g, path = self._game()
        g._start()
        for _ in range(3):
            g._step()
        while not g.state_machine.is_empty():
            g.state_machine.pop()
        g._step()                                    # begins, finds nothing to run
        self.assertFalse(g.running)
        time.sleep(0.2)
        g._close_trace()
        rows = _rows(path)[1:]
        self.assertEqual(len(rows), 3)
        self.assertLess(float(rows[-1][FRAME]), 150.0, rows[-1])

    def test_a_crash_in_the_browser_loop_still_writes_what_was_traced(self):
        # `run_async` is the loop `main.py` runs.
        import asyncio

        g, path = self._game()
        real, n = g._step, [0]

        def step():
            real()
            n[0] += 1
            if n[0] == 5:
                raise RuntimeError("the game fell over")

        g._step = step
        with mock.patch.object(FT, "FLUSH_SECONDS", 1e9), self.assertRaises(RuntimeError):
            asyncio.run(g.run_async())
        self.assertEqual(len(_rows(path)) - 1, 5)

    def test_a_crash_still_writes_what_was_traced(self):
        # Five frames are fewer than one batch, so only the loop's `finally`
        # can have written them.
        g, path = self._game()
        real, n = g._step, [0]

        def step():
            real()
            n[0] += 1
            if n[0] == 5:
                raise RuntimeError("the game fell over")

        g._step = step
        with mock.patch.object(FT, "FLUSH_SECONDS", 1e9), self.assertRaises(RuntimeError):
            g.run()
        self.assertEqual(len(_rows(path)) - 1, 5)

    def test_without_a_trace_nothing_is_recorded(self):
        from game.game import Game

        d = _tmp(self)
        g = Game(save_path=os.path.join(d, "save.json"))
        g._start()
        g._step()
        self.assertIsNone(g.trace)
        self.assertFalse((Path(d) / "traces").exists())


class MainTests(unittest.TestCase):
    """`python main.py --trace`, as the owner runs it, headless: it logs the
    trace's path and writes rows. The child's file is told by being new
    since the launch (not by process id, which a venv's launcher would not
    share), and every such file is removed afterwards, rows or none, with
    `traces/` itself if the test made it (it lies beside the source tree's
    save, gitignored)."""

    def test_main_with_the_flag_writes_a_trace(self):
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        env.pop(FT.ENV, None)
        folder = ROOT / "traces"
        had_folder = folder.exists()
        before = set(folder.glob("frames-*.csv"))
        if not had_folder:
            self.addCleanup(lambda: folder.exists() and not any(folder.iterdir()) and folder.rmdir())
        proc = subprocess.Popen([sys.executable, "main.py", "--trace"], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        found = None
        try:
            deadline = time.time() + 60
            while time.time() < deadline and found is None:
                for f in set(folder.glob("frames-*.csv")) - before:
                    if len(_rows(f)) > 1:
                        found = f
                time.sleep(0.25)
        finally:
            proc.kill()
            out = proc.communicate()[0]
            for f in set(folder.glob("frames-*.csv")) - before:
                self.addCleanup(f.unlink, missing_ok=True)
        self.assertIsNotNone(found, out[-2000:])
        self.assertIn(f"frame trace: {found}", out)
        self.assertEqual(_rows(found)[0], list(FT.COLUMNS))

    def test_the_game_imports_no_csv_unless_it_traces(self):
        # The web build imports the game, never traces, and should not load
        # a module only the trace needs.
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys, game.game; print('_csv' in sys.modules or 'csv' in sys.modules)"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL, check=False)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "False", out.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
