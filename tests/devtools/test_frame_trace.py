"""SYS-010: the frame-time trace of real play (`frame_trace_journal.md`).

What is pinned:
* **the switch:** off by default; on with `--trace` or with `DEATHLITE_TRACE`
  set (not empty, not "0"); the file lands in `traces/` beside the save;
* **the recorder:** one header, one row per frame, blanks outside a run,
  buffered and written every `FLUSH_EVERY` rows and at the end, closing
  twice is harmless;
* **the sample:** the top state's name, and the run's crowd found under a
  pause menu;
* **the wiring:** a `Game` with a trace records every frame it steps through
  menu, run and pause, update / draw / present apart; a `Game` without one
  records nothing and opens no file.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pygame

from systems import frame_trace as FT


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class TracePathTests(unittest.TestCase):
    def setUp(self):
        self.save = os.path.join(tempfile.mkdtemp(), "save.json")

    def test_off_by_default(self):
        self.assertIsNone(FT.trace_path(["main.py"], {}, self.save))
        for off in ("", "0"):
            with self.subTest(env=off):
                self.assertIsNone(FT.trace_path(["main.py"], {FT.ENV: off}, self.save))

    def test_the_flag_or_the_variable_switches_it_on(self):
        for argv, env in ((["main.py", "--trace"], {}), (["main.py"], {FT.ENV: "1"}),
                          (["DeathliteGame.exe"], {FT.ENV: "yes"})):
            with self.subTest(argv=argv, env=env):
                p = FT.trace_path(argv, env, self.save)
                self.assertEqual(p.parent, Path(self.save).parent / "traces")
                self.assertEqual(p.suffix, ".csv")
                self.assertTrue(p.name.startswith("frames-"))


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "traces" / "t.csv"

    def test_rows_round_trip_and_blanks_outside_a_run(self):
        tr = FT.FrameTrace(self.path)
        tr.record(16.0, 5.25, 9.5, 1.125, ("PlayingState", 113, 95, 40, 7, 12.5))
        tr.record(33.0, 0.5, 2.0, 0.25, ("MenuState", None, None, None, None, None))
        tr.close()
        rows = _rows(self.path)
        self.assertEqual(rows[0], list(FT.COLUMNS))
        self.assertEqual(rows[1][1:], ["16.000", "5.250", "9.500", "1.125", "PlayingState",
                                       "113", "95", "40", "7", "12.500"])
        self.assertEqual(rows[2][1:], ["33.000", "0.500", "2.000", "0.250", "MenuState",
                                       "", "", "", "", ""])
        self.assertEqual(tr.frames, 2)

    def test_rows_are_written_in_batches_and_at_the_end(self):
        with mock.patch.object(FT, "FLUSH_EVERY", 3):
            tr = FT.FrameTrace(self.path)
            one = ("MenuState", None, None, None, None, None)
            for _ in range(2):
                tr.record(16.0, 1.0, 1.0, 1.0, one)
            self.assertEqual(len(_rows(self.path)), 1)            # the header only
            tr.record(16.0, 1.0, 1.0, 1.0, one)
            self.assertEqual(len(_rows(self.path)), 4)            # a batch of three
            tr.record(16.0, 1.0, 1.0, 1.0, one)
            tr.close()
            tr.close()                                            # twice is harmless
        self.assertEqual(len(_rows(self.path)), 5)


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.b = (x0, y0, x1, y1)

    def collidepoint(self, x, y):
        x0, y0, x1, y1 = self.b
        return x0 <= x < x1 and y0 <= y < y1


class _PausedState:
    pass


class SampleTests(unittest.TestCase):
    def _run(self):
        body = lambda x, y: SimpleNamespace(pos=pygame.Vector2(x, y))      # noqa: E731
        return SimpleNamespace(
            enemies=[body(10, 10), body(50, 50), body(500, 500)],
            camera=SimpleNamespace(visible_rect=lambda: _Rect(0, 0, 100, 100)),
            particles=[1, 2, 3, 4], damage_numbers=[1, 2], stats={"time": 42.5})

    def _game(self, *states):
        return SimpleNamespace(state_machine=SimpleNamespace(stack=tuple(states)))

    def test_a_menu_frame_has_no_crowd(self):
        self.assertEqual(FT.sample(self._game(SimpleNamespace())),
                         ("SimpleNamespace", None, None, None, None, None))

    def test_a_run_frame_counts_its_crowd(self):
        playing = SimpleNamespace(run=self._run())
        self.assertEqual(FT.sample(self._game(playing))[1:], (3, 2, 4, 2, 42.5))

    def test_the_crowd_is_read_under_a_pause_menu(self):
        playing = SimpleNamespace(run=self._run())
        got = FT.sample(self._game(playing, _PausedState()))
        self.assertEqual(got, ("_PausedState", 3, 2, 4, 2, 42.5))


class GameWiringTests(unittest.TestCase):
    """A real `Game`, headless, seed 35."""

    def test_every_frame_is_recorded_apart(self):
        from game.game import Game
        from tests.boot import start_run

        d = tempfile.mkdtemp()
        path = FT.trace_path(["main.py", "--trace"], {}, os.path.join(d, "save.json"))
        g = Game(save_path=os.path.join(d, "save.json"), trace_path=path)
        g._start()
        for _ in range(4):
            g._step()
        start_run(g, 35)
        for _ in range(6):
            g._step()
        g.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        for _ in range(3):
            g._step()
        g.trace.close()
        rows = _rows(path)[1:]
        self.assertEqual(len(rows), 13)
        self.assertEqual([r[5] for r in rows],
                         ["MenuState"] * 4 + ["PlayingState"] * 6 + ["PausedState"] * 3)
        self.assertTrue(all(r[6] == "" for r in rows[:4]))                  # no crowd in the menu
        self.assertTrue(all(r[6] != "" for r in rows[4:]))                  # the run's, under the pause too
        for r in rows:
            frame, update, draw, present = map(float, r[1:5])
            self.assertTrue(frame >= 0 and update >= 0 and draw > 0 and present >= 0, r)

    def test_without_a_trace_nothing_is_recorded(self):
        from game.game import Game

        d = tempfile.mkdtemp()
        g = Game(save_path=os.path.join(d, "save.json"))
        g._start()
        g._step()
        self.assertIsNone(g.trace)
        self.assertFalse((Path(d) / "traces").exists())


if __name__ == "__main__":
    unittest.main()
