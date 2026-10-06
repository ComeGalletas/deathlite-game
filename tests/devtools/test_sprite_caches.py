"""RND-010.3: the two sprite caches a fight leans on, replayed on the
fight's own requests (`tools/benchmarks/sprite_caches.py`,
`crowd_draw_journal.md`).

What is pinned:
* **the replay:** the game's policy (empty whole when full, then add) and
  the LRU (drop the entry used longest ago, a hit refreshing it), miss by
  miss, frame by frame, and the averages from `warm` on;
* **the recording:** every request with its frame, key and bytes, the
  sources kept, the caches called through and put back;
* **the costs:** taken on an emptied cache with room for every source,
  the game's cache left exactly as found;
* **the printout and the command line;**
* **the scene:** a fight asks the wash cache for frames, and a cap that
  holds every distinct frame misses each one once.
"""
import contextlib
import io
import unittest
from unittest import mock

import pygame

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import sprite_caches as SC

SEED = 35


def _surface(w=4, h=3, colour=(200, 120, 40, 255)):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(colour)
    return s


class ReplayTests(unittest.TestCase):
    def test_emptied_when_full_against_lru(self):
        # Cap 2. Frame 0 asks a and b, frame 1 c, frame 2 b. The game's
        # cache is full at c and empties, so b misses again; the LRU drops
        # only a and keeps b.
        events = [(0, "a", 1), (0, "b", 1), (1, "c", 1), (2, "b", 1)]
        self.assertEqual(SC.replay(events, 3, 2, lru=False), (4 / 3, 2))
        self.assertEqual(SC.replay(events, 3, 2, lru=True), (1.0, 2))
        self.assertEqual(SC.replay(events, 3, 2, lru=False, warm=1), (1.0, 1))
        self.assertEqual(SC.replay(events, 3, 2, lru=True, warm=1), (0.5, 1))

    def test_a_hit_refreshes_the_lru(self):
        # a, b, a, c, a at cap 2: the hit on a makes b the oldest, so c
        # drops b and the last a hits. Dropping by age of entry would miss it.
        events = [(i, k, 1) for i, k in enumerate("abaca")]
        self.assertEqual(SC.replay(events, 5, 2, lru=True), (3 / 5, 1))
        self.assertEqual(SC.replay(events, 5, 2, lru=False), (4 / 5, 1))

    def test_the_game_checks_the_cap_before_it_adds(self):
        # Cap 1: a fills it, b empties it first, then a misses again.
        events = [(0, "a", 1), (1, "a", 1), (2, "b", 1), (3, "a", 1)]
        self.assertEqual(SC.replay(events, 4, 1, lru=False), (3 / 4, 1))


class RecordTests(unittest.TestCase):
    def test_every_request_with_its_frame_called_through_and_put_back(self):
        from game.states.playing.visual import elements as fx
        from game.states.playing.visual import rendering as R
        a, b = _surface(4, 3), _surface(2, 5)
        seen = []
        fake_wash = lambda f, el, profiles=None: seen.append(("wash", f, el)) or "washed"
        fake_tint = lambda f: seen.append(("tint", f)) or "tinted"
        returned = []

        def run(ps, frames, render, after_draw):
            self.assertTrue(render)
            for _ in range(frames):
                returned.append(fx.washed(a, 2))
                returned.append(fx.washed(a, None))         # unprimed: not a request
                returned.append(R.hit_tinted(b))
                after_draw()
            return [], [], []

        with mock.patch.object(fx, "washed", fake_wash), \
                mock.patch.object(R, "hit_tinted", fake_tint), \
                mock.patch.object(SC.S, "run", run):
            rec = SC.record(mock.Mock(), 2)
            self.assertIs(fx.washed, fake_wash)
            self.assertIs(R.hit_tinted, fake_tint)
        wkey, tkey = ("wash", id(a), 2), ("tint", id(b))
        self.assertEqual(rec["wash"], [(0, wkey, 48), (1, wkey, 48)])
        self.assertEqual(rec["tint"], [(0, tkey, 40), (1, tkey, 40)])
        self.assertEqual(rec["sources"], {wkey: (a, 2), tkey: (b, None)})
        self.assertEqual(returned, ["washed", "washed", "tinted"] * 2)
        self.assertEqual(len(seen), 6)


class MissCostTests(unittest.TestCase):
    def test_the_game_cache_is_left_exactly_as_found(self):
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx
        from game.states.playing.visual import rendering as R
        frames = [_surface(3 + i, 3) for i in range(3)]
        sources = {("wash", id(f), int(ElementId.FIRE)): (f, ElementId.FIRE) for f in frames}
        sources.update({("tint", id(f)): (f, None) for f in frames})
        held = _surface(9, 9)
        before = []
        for module, cache, cap in ((fx, "_WASH_CACHE", "_WASH_CACHE_CAP"),
                                   (R, "_TINT_CACHE", "_TINT_CACHE_CAP")):
            store = getattr(module, cache)
            store[("held", 1)] = (held, held)
            before.append((module, cache, cap, store, dict(store), getattr(module, cap)))
        try:
            for name in ("wash", "tint"):
                with self.subTest(cache=name):
                    miss, hit = SC.miss_cost(name, sources)
                    self.assertGreater(miss, 0.0)
                    self.assertGreater(hit, 0.0)
            for module, cache, cap, store, contents, cap_value in before:
                self.assertIs(getattr(module, cache), store)
                self.assertEqual(store, contents)
                self.assertEqual(getattr(module, cap), cap_value)
        finally:
            for _module, _cache, _cap, store, _contents, _value in before:
                store.pop(("held", 1), None)
        self.assertIsNone(SC.miss_cost("wash", {("tint", 1): (held, None)}))

    def test_the_first_pass_misses_and_the_second_hits_every_source(self):
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx
        frames = [_surface(3 + i, 3) for i in range(5)]
        sources = {("wash", id(f), int(ElementId.WIND)): (f, ElementId.WIND) for f in frames}
        real, seen = fx.washed, []

        def spy(frame, element, profiles=None):
            held = (id(frame), int(element)) in fx._WASH_CACHE
            out = real(frame, element, profiles)
            seen.append((held, len(fx._WASH_CACHE), fx._WASH_CACHE_CAP))
            return out

        with mock.patch.object(fx, "washed", spy):
            SC.miss_cost("wash", sources)
        self.assertEqual([h for h, _n, _c in seen], [False] * 5 + [True] * 5)
        self.assertEqual([n for _h, n, _c in seen], [1, 2, 3, 4, 5] + [5] * 5)
        self.assertTrue(all(c >= 5 for _h, _n, c in seen))

    def test_the_swap_holds_room_for_every_source_and_is_undone_on_error(self):
        module = mock.Mock(cache={"x": 1}, cap=5)
        game_cache = module.cache
        with self.assertRaises(ZeroDivisionError), SC._empty(module, "cache", "cap", 7):
            self.assertEqual((module.cache, module.cap), ({}, 7))
            raise ZeroDivisionError
        self.assertIs(module.cache, game_cache)
        self.assertEqual(module.cap, 5)


class ReportTests(unittest.TestCase):
    def test_every_figure(self):
        events = [(0, "a", 4000), (0, "b", 4000), (1, "c", 8000), (2, "b", 4000)]
        self.assertEqual(SC.report("wash", events, 3, 0, 2, [2], (100.0, 0.5)), [
            ("  wash: 1.3 requests a frame, 3 distinct frames, the median 4.0 KB; "
             "the game's cap 2, frames 0 to 3"),
            ("    cap     2 (  0.0 MB): emptied when full   1.33 misses a frame, worst    2  |  "
             "LRU   1.00, worst    2"),
            "    a miss 100.0 us, a hit 0.50 us"])
        self.assertEqual(SC.report("tint", [], 3, 0, 2, [2], None), ["  tint: nothing asked of it"])
        self.assertEqual(len(SC.report("wash", events, 3, 1, 2, [2, 4], None)), 3)

    def test_the_command_line(self):
        a = SC.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.frames, a.warm, a.wash_caps, a.tint_caps),
                         (SEED, 400, 900, 300, [512, 768, 1024, 1536, 2048], [128, 256, 512]))
        self.assertEqual(SC.parse(["--live", "1", "--elapsed", "0", "--wash-caps", "8,16"]).wash_caps,
                         [8, 16])
        for bad in (["--live", "1", "--elapsed", "0", "--wash-caps", "0"],
                    ["--live", "1", "--elapsed", "0", "--tint-caps", ","],
                    ["--live", "1", "--elapsed", "0", "--frames", "10", "--warm", "10"],
                    ["--live", "1", "--elapsed", "0", "--warm", "-1"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                SC.parse(bad)


class SceneTests(unittest.TestCase):
    """One packed scene with the hero fighting, seed 35, 40 alive."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.game, cls.ps = LP.packed_scene(SEED, 40, 0, 300.0, TDL._fresh_save(),
                                               elements=True)

    def test_a_fight_washes_and_a_roomy_cap_misses_each_frame_once(self):
        from game.states.playing.visual import elements as fx
        from game.states.playing.visual import rendering as R
        real = fx.washed, R.hit_tinted
        rec = SC.record(self.ps, 6)
        self.assertEqual((fx.washed, R.hit_tinted), real)
        self.assertGreater(len(rec["wash"]), 0)
        for name in ("wash", "tint"):
            events = rec[name]
            with self.subTest(cache=name):
                self.assertTrue(all(0 <= f < 6 for f, _k, _b in events))
                self.assertTrue(all(k in rec["sources"] for _f, k, _b in events))
                distinct = len({k for _f, k, _b in events})
                for lru in (False, True):
                    avg, _worst = SC.replay(events, 6, distinct + 1, lru=lru)
                    self.assertAlmostEqual(avg * 6, distinct)


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = SC.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                            "--frames", "4", "--warm", "1", "--wash-caps", "64",
                            "--tint-caps", "64"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  sprite caches, the hero fighting: ", text)
        self.assertRegex(text, r"\n  wash: [\d.]+ requests a frame")     # the hero fights
        self.assertIn("    cap    64 (", text)
        self.assertTrue(text.rstrip().endswith("  boss at the end: held back"))


if __name__ == "__main__":
    unittest.main()
