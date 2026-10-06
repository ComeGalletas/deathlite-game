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


SIZES = {"a": 10, "b": 20, "c": 40}      # each key's copy, in bytes


def _events(*frames):
    """`_events("ab", "c")`: frame 0 asks a and b, frame 1 asks c."""
    return [(f, k, SIZES[k]) for f, keys in enumerate(frames) for k in keys]


def _figures(r: dict) -> tuple:
    return r["per"], r["avg"], r["worst"], r["clears"], r["peak"]


class ReplayTests(unittest.TestCase):
    """Misses a frame, the worst frame, and the most bytes held."""

    def test_emptied_when_full_against_lru(self):
        # Cap 2. Frame 0 asks a and b, frame 1 c, frame 2 b. The game's
        # cache is full at c and empties (then holds c, 40), so b misses
        # again (60); the LRU drops only a (20 + 40) and keeps b.
        events = _events("ab", "c", "b")
        self.assertEqual(_figures(SC.replay(events, 3, 2, lru=False)), ([2, 1, 1], 4 / 3, 2, 1, 60))
        self.assertEqual(_figures(SC.replay(events, 3, 2, lru=True)), ([2, 1, 0], 1.0, 2, 0, 60))
        self.assertEqual(_figures(SC.replay(events, 3, 2, lru=False, warm=1)), ([2, 1, 1], 1.0, 1, 1, 60))
        self.assertEqual(_figures(SC.replay(events, 3, 2, lru=True, warm=1)), ([2, 1, 0], 0.5, 1, 0, 60))
        self.assertEqual(SC.replay(events, 3, 2, lru=False, warm=2)["clears"], 0)   # it emptied in frame 1

    def test_a_hit_refreshes_the_lru(self):
        # a, b, a, c, a at cap 2: the hit on a makes b the oldest, so c
        # drops b (10 + 40 held) and the last a hits. Dropping by age of
        # entry would drop a (20 + 40) and miss it.
        events = _events("a", "b", "a", "c", "a")
        self.assertEqual(_figures(SC.replay(events, 5, 2, lru=True)), ([1, 1, 0, 1, 0], 3 / 5, 1, 0, 50))
        self.assertEqual(_figures(SC.replay(events, 5, 2, lru=False)), ([1, 1, 0, 1, 1], 4 / 5, 1, 1, 50))

    def test_the_game_checks_the_cap_before_it_adds(self):
        # Cap 1: a fills it, b empties it first, then a misses again.
        events = _events("a", "a", "b", "a")
        self.assertEqual(_figures(SC.replay(events, 4, 1, lru=False)), ([1, 0, 1, 1], 3 / 4, 1, 2, 20))

    def test_the_replay_counts_what_the_game_s_own_caches_copy(self):
        # The game's real `washed` and `hit_tinted`, on caches of their own
        # with a cap of 3, against the replay of the same requests. A miss
        # is read off the game's own cache before each call.
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx
        from game.states.playing.visual import rendering as R
        frames = [_surface(2 + i, 2) for i in range(5)]
        order = [0, 1, 2, 0, 3, 0, 1, 4, 4, 2, 0]    # the game copies 9, an LRU would 8
        for name, module, cache, cap in (("wash", fx, "_WASH_CACHE", "_WASH_CACHE_CAP"),
                                         ("tint", R, "_TINT_CACHE", "_TINT_CACHE_CAP")):
            with self.subTest(cache=name), mock.patch.object(module, cache, {}), \
                    mock.patch.object(module, cap, 3):
                misses, events = [], []
                for step, i in enumerate(order):
                    f = frames[i]
                    key = (id(f), int(ElementId.FIRE)) if name == "wash" else id(f)
                    held = getattr(module, cache).get(key)
                    misses.append(int(not (held is not None and held[0] is f)))
                    if name == "wash":
                        fx.washed(f, ElementId.FIRE)
                    else:
                        R.hit_tinted(f)
                    events.append((step, key, 1))
                self.assertEqual(SC.replay(events, len(order), 3, lru=False)["per"], misses)  # copy for copy
                self.assertEqual(sum(misses), 9)
                lru = SC.replay(events, len(order), 3, lru=True)["per"]
                self.assertEqual(sum(lru), 8)                      # the order tells them apart


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


class BytesTests(unittest.TestCase):
    def test_a_copy_holds_its_rows_times_its_height(self):
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx
        odd = pygame.Surface((5, 3), depth=24)               # rows of 15 bytes, padded
        for frame in (_surface(5, 4), odd):
            with self.subTest(size=frame.get_size(), depth=frame.get_bitsize()):
                copy = frame.copy()
                self.assertEqual(SC.nbytes(frame), copy.get_pitch() * copy.get_height())
        self.assertNotEqual(SC.nbytes(odd), 5 * 3 * 4)       # not four bytes a pixel
        self.assertGreaterEqual(SC.nbytes(odd), 5 * 3 * 3)
        frame = _surface(7, 3)
        with mock.patch.object(fx, "_WASH_CACHE", {}):
            out = fx.washed(frame, ElementId.ICE)
        self.assertEqual(SC.nbytes(frame), out.get_pitch() * out.get_height())


class ClearCostTests(unittest.TestCase):
    def test_a_full_cache_emptied_and_the_game_s_left_as_found(self):
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx
        frames = [_surface(3 + i, 3) for i in range(5)]
        sources = {("wash", id(f), int(ElementId.FIRE)): (f, ElementId.FIRE) for f in frames}
        game_cache, cap = fx._WASH_CACHE, fx._WASH_CACHE_CAP
        held = _surface(9, 9)
        game_cache[("held", 1)] = (held, held)                # must survive the emptying
        self.addCleanup(game_cache.pop, ("held", 1), None)
        contents = dict(game_cache)
        real, sizes = fx.washed, []

        def spy(frame, element, profiles=None):
            out = real(frame, element, profiles)
            sizes.append((len(fx._WASH_CACHE), fx._WASH_CACHE_CAP))
            return out

        with mock.patch.object(fx, "washed", spy):
            cost = SC.clear_cost("wash", sources, 3, passes=2)
        self.assertEqual(cost["entries"], 3)
        self.assertEqual(len(cost["ms"]), 2)
        self.assertEqual([n for n, _c in sizes], [1, 2, 3] * 2)    # filled afresh each pass
        self.assertTrue(all(c > 3 for _n, c in sizes))             # never emptied while filling
        self.assertIs(fx._WASH_CACHE, game_cache)
        self.assertEqual((fx._WASH_CACHE, fx._WASH_CACHE_CAP), (contents, cap))
        self.assertEqual(SC.clear_cost("wash", sources, 10, passes=1)["entries"], 5)
        self.assertIsNone(SC.clear_cost("tint", sources, 3))


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
                    cost = SC.miss_cost(name, sources, passes=2)
                    self.assertEqual([len(cost["miss"]), len(cost["hit"])], [2, 2])
                    self.assertTrue(all(us > 0.0 for us in cost["miss"] + cost["hit"]))
            for module, cache, cap, store, contents, cap_value in before:
                self.assertIs(getattr(module, cache), store)
                self.assertEqual(store, contents)
                self.assertEqual(getattr(module, cap), cap_value)
        finally:
            for _module, _cache, _cap, store, _contents, _value in before:
                store.pop(("held", 1), None)
        self.assertIsNone(SC.miss_cost("wash", {("tint", 1): (held, None)}))

    def test_each_pass_misses_then_hits_every_source_on_a_fresh_cache(self):
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
            cost = SC.miss_cost("wash", sources, passes=2)
        self.assertEqual(len(cost["miss"]), 2)
        self.assertEqual([h for h, _n, _c in seen], ([False] * 5 + [True] * 5) * 2)
        self.assertEqual([n for _h, n, _c in seen], ([1, 2, 3, 4, 5] + [5] * 5) * 2)
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
        # a 400 KB, b 200 KB, c 800 KB; the median distinct frame is a's,
        # whatever how often b is asked for. Cap 2: the game's cache holds
        # c and then b (1.0 MB) after emptying; the LRU drops a for c.
        events = [(0, "a", 400_000), (0, "b", 200_000), (1, "c", 800_000), (2, "b", 200_000)]
        cost = {"miss": [120.0, 90.0, 100.0], "hit": [0.9, 0.5, 0.4]}    # the first pass is slowest
        clear = {"ms": [3.0, 1.0, 2.0], "entries": 2}
        self.assertEqual(SC.report("wash", events, 3, 0, 2, [2], cost, clear), [
            ("  wash: 1.3 requests a frame, 3 distinct frames, the median one 400.0 KB; "
             "the game's cap 2, frames 0 to 3"),
            ("    cap     2: emptied when full   1.33 misses a frame, worst    2, emptied   1 times, "
             "held at most   1.0 MB  |  LRU   1.00, worst    2, held at most   1.0 MB"),
            "    a miss 100.0 us (90.0 to 120.0), a hit 0.50 us (0.40 to 0.90), over 3 passes",
            "    emptying a cache of 2: 2.00 ms (1.00 to 3.00), over 3 passes"])
        self.assertEqual(SC.report("tint", [], 3, 0, 2, [2], None), ["  tint: nothing asked of it"])
        warm = SC.report("wash", events, 3, 1, 2, [2, 4], None)
        self.assertEqual(len(warm), 3)
        self.assertTrue(warm[0].startswith("  wash: 1.0 requests a frame, "))   # c and b over 2
        self.assertIn("frames 1 to 3", warm[0])

    def test_the_command_line(self):
        a = SC.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.frames, a.warm, a.wash_caps, a.tint_caps, a.passes),
                         (SEED, 400, 900, 300, [512, 768, 1024, 1536, 2048], [128, 256, 512], 5))
        self.assertEqual(SC.parse(["--live", "1", "--elapsed", "0", "--wash-caps", "8,16"]).wash_caps,
                         [8, 16])
        for bad in (["--live", "1", "--elapsed", "0", "--wash-caps", "0"],
                    ["--live", "1", "--elapsed", "0", "--tint-caps", ","],
                    ["--live", "1", "--elapsed", "0", "--frames", "10", "--warm", "10"],
                    ["--live", "1", "--elapsed", "0", "--warm", "-1"],
                    ["--live", "1", "--elapsed", "0", "--passes", "0"]):
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
                    r = SC.replay(events, 6, distinct + 1, lru=lru)
                    self.assertEqual(sum(r["per"]), distinct)
                    self.assertEqual(r["peak"], sum({k: b for _f, k, b in events}.values()))


class RequestTests(unittest.TestCase):
    """The replay's premise: what the draw asks of the caches does not
    depend on what they hold."""

    def test_the_same_scene_asks_the_same_of_a_churning_and_a_full_cache(self):
        # Two builds of one scene, 8 frames each. The first runs on caches
        # small enough to empty themselves over and over; the second on
        # caches already holding every frame the first asked for, so it
        # never misses. Both ask for the same frames in the same order.
        from game.states.playing.visual import elements as fx
        from game.states.playing.visual import rendering as R
        frames, small = 8, (16, 4)
        streams, recs = [], []
        full = ({}, {})
        for churn in (True, False):
            with contextlib.redirect_stdout(io.StringIO()):
                _game, ps = LP.packed_scene(SEED, 40, 0, 300.0, TDL._fresh_save(), elements=True)
            wash, tint = ({}, {}) if churn else full
            caps = small if churn else (10 ** 6, 10 ** 6)
            with mock.patch.object(fx, "_WASH_CACHE", wash), \
                    mock.patch.object(fx, "_WASH_CACHE_CAP", caps[0]), \
                    mock.patch.object(R, "_TINT_CACHE", tint), \
                    mock.patch.object(R, "_TINT_CACHE_CAP", caps[1]):
                if not churn:
                    before = (len(wash), len(tint))
                rec = SC.record(ps, frames)
                if churn:                          # every frame it asked for, held
                    with mock.patch.object(fx, "_WASH_CACHE", full[0]), \
                            mock.patch.object(fx, "_WASH_CACHE_CAP", 10 ** 6), \
                            mock.patch.object(R, "_TINT_CACHE", full[1]), \
                            mock.patch.object(R, "_TINT_CACHE_CAP", 10 ** 6):
                        for key, (frame, element) in rec["sources"].items():
                            if key[0] == "wash":
                                fx.washed(frame, element)
                            else:
                                R.hit_tinted(frame)
            recs.append(rec)
            streams.append([(name, f, k) for name in ("wash", "tint") for f, k, _b in rec[name]])
        self.assertGreater(len(recs[0]["wash"]), 0)
        self.assertGreater(len(recs[0]["tint"]), 0)            # the hurt branch ran too
        self.assertGreater(SC.replay(recs[0]["wash"], frames, small[0], lru=False)["clears"], 0)
        self.assertEqual(streams[0], streams[1])
        self.assertEqual((len(full[0]), len(full[1])), before)    # the full caches served every request


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = SC.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                            "--frames", "4", "--warm", "1", "--wash-caps", "64",
                            "--tint-caps", "64", "--passes", "2"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  sprite caches, the hero fighting: ", text)
        self.assertRegex(text, r"\n  wash: [\d.]+ requests a frame")     # the hero fights
        self.assertIn("    cap    64: emptied when full ", text)
        self.assertRegex(text, r"a miss [\d.]+ us \([\d.]+ to [\d.]+\), a hit .* over 2 passes")
        self.assertTrue(text.rstrip().endswith("  boss at the end: held back"))


if __name__ == "__main__":
    unittest.main()
