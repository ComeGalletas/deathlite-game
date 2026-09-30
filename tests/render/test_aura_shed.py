"""RND-011: the aura's shed runs in the update, not the draw
(`aura_shed_journal.md`).

Before RND-011 every drawn aura rolled `run.rng` and could add a mote, so
drawing a frame changed the run: the shed was as dense as the draw was
fast (about 3x in the browser at 175 Hz against the desktop's 62 fps cap),
and gameplay's random numbers depended on how many frames had been drawn.
Pinned here, each against the defect it closes:

* **the draw changes nothing**: `run.rng`, the shed's own stream and the
  particle pool are the same after any number of draws, headless and in a
  booted run;
* **a rate per second**: the motes born per second match `rate` per aura
  at dt 1/30, 1/62 and 1/175, and each other (the old roll of `rate / 60`
  a frame would read 1.9x, 1.0x and 0.34x of it; the control shows it);
* **the budget still bounds it**, by the same amount per second at every
  step length;
* **its own stream**: the update-time shed leaves `run.rng` alone, and the
  same seed sheds the same motes.

Statistical where it has to be, on fixed seeds, so every number here is
the same on every run; the tolerances are what the seed's sample needs,
stated where they are set.
"""
import os
import random
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS, ElementId
from game.states.playing.visual import elements as fx
from game.states.playing.visual.elements import ElementVisuals, shed
from tests import worlds as W
from tests.render.test_element_visuals import C, _init, fake_run

SEED = W.pinned(3)
STEPS = (1 / 30, 1 / 62, 1 / 175)
SECONDS = 20.0


def _primed(n: int, element=ElementId.FIRE, spacing: float = 4.0):
    from tests.combat.fakes import FakeEnemy

    bodies = [FakeEnemy(i * spacing - 500.0, 0.0) for i in range(n)]
    for body in bodies:
        body.elemental.set_aura(element, 0.0, 1e6)
    return bodies


def _born(bursts) -> int:
    return sum(kw["count"] for _, _, kw in bursts)


def _budget_state(budget) -> tuple:
    """Everything the budget holds, so a draw that refills it (which also
    zeroes `spent`) or takes from it is seen."""
    return (budget._left, dict(budget._by_element), budget._frame_carry,
            dict(budget._element_carry), budget.granted, budget.spent,
            budget.refused)


def _per_second(run, dt: float, seconds: float = SECONDS) -> float:
    """Motes born per second over `seconds` of play in steps of `dt`."""
    run.particles.bursts.clear()
    steps = round(seconds / dt)
    for _ in range(steps):
        shed.update(run, dt)
    return _born(run.particles.bursts) / (steps * dt)


class DrawIsPureTests(unittest.TestCase):
    """The draw paints; it rolls nothing and adds nothing."""

    def setUp(self):
        _init()
        self.surface = pygame.Surface((320, 240))

    def test_drawing_a_primed_crowd_leaves_the_run_alone(self):
        crowd = [b for element in ELEMENTS for b in _primed(10, element)]
        run = fake_run(crowd)
        # One step first, so the budget holds something a draw could take,
        # carries a draw could reset, and a `spent` a refill would zero.
        shed.update(run, 1 / 62)
        run.particles.bursts.clear()
        budget = _budget_state(run.element_visuals.budget)
        self.assertGreater(budget[0], 0, "nothing left for a draw to take")
        self.assertGreater(budget[5], 0, "no `spent` for a refill to zero")
        rng, own = run.rng.getstate(), run.element_visuals.rng.getstate()
        for _ in range(200):
            fx.draw(self.surface, run)
        self.assertEqual(run.element_visuals.auras_drawn, len(crowd),
                         "the auras were drawn")
        self.assertEqual(run.rng.getstate(), rng, "the draw rolled run.rng")
        self.assertEqual(run.element_visuals.rng.getstate(), own,
                         "the draw rolled the shed's stream")
        self.assertEqual(run.particles.bursts, [], "the draw added motes")
        self.assertEqual(_budget_state(run.element_visuals.budget), budget,
                         "the draw took from or refilled the budget")

    def test_the_same_crowd_does_shed_in_the_update(self):
        # The control for the test above: the crowd is one that sheds.
        run = fake_run(_primed(10))
        for _ in range(60):
            shed.update(run, 1 / 60)
        self.assertGreater(_born(run.particles.bursts), 0)


class RatePerSecondTests(unittest.TestCase):
    """50 bodies of each element for 20 s: rate 5 to 7 a second is 5,000
    to 7,000 motes a sample, so one standard deviation is under 1.2 % of
    the mean and 4 % is over three of them."""

    TOLERANCE = 0.04

    def test_every_element_sheds_its_rate_at_every_step_length(self):
        for element in ELEMENTS:
            want = 50 * C.element_visuals["elements"][element.key]["particles"]["rate"]
            got = {}
            for dt in STEPS:
                run = fake_run(_primed(50, element))
                got[dt] = _per_second(run, dt)
                with self.subTest(element=element.key, dt=round(1 / dt)):
                    self.assertAlmostEqual(got[dt] / want, 1.0,
                                           delta=self.TOLERANCE)
            with self.subTest(element=element.key, what="agree"):
                self.assertLess(max(got.values()) / min(got.values()),
                                1.0 + 2 * self.TOLERANCE)

    def test_the_old_roll_a_frame_is_as_dense_as_the_frame_rate(self):
        """What the tests above would catch coming back: a chance of
        `rate / 60` per step (the draw-time roll) sheds in proportion to the
        step rate, 175 / 62 = 2.8x more at 175 Hz than at 62 fps."""
        def old_roll(run, dt):
            visuals = run.element_visuals
            for body in run.enemies:
                rate = visuals.profiles[ElementId.FIRE].particles.rate
                if visuals.rng.random() <= rate / 60.0:
                    run.particles.burst(body.pos, (0, 0, 0), count=1)

        rates = {}
        for dt in (1 / 62, 1 / 175):
            run = fake_run(_primed(50))
            with mock.patch.object(shed, "update", old_roll):
                rates[dt] = _per_second(run, dt)
        self.assertAlmostEqual(rates[1 / 175] / rates[1 / 62], 175 / 62,
                               delta=0.15)

    def test_a_step_that_owes_more_than_one_mote_pays_the_whole_part(self):
        # `MAX_DT` keeps rate * dt under 1 in play (at most 7 * 1/20); a
        # longer step still owes rate * dt on average, never at most one.
        run = fake_run(_primed(50))
        rate = run.element_visuals.profiles[ElementId.FIRE].particles.rate
        got = _per_second(run, 0.5, seconds=100.0)
        self.assertAlmostEqual(got / (50 * rate), 1.0, delta=self.TOLERANCE)
        counts = {kw["count"] for _, _, kw in run.particles.bursts}
        self.assertEqual(counts, {3, 4}, "7/s over 0.5 s is 3 or 4 motes")

    def test_a_body_out_of_view_sheds_nothing(self):
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(5000.0, 0.0)             # the fake view ends at 1000
        body.elemental.set_aura(ElementId.FIRE, 0.0, 1e6)
        run = fake_run([body])
        self.assertEqual(_per_second(run, 1 / 60), 0.0)

    def test_a_body_without_an_aura_sheds_nothing(self):
        from tests.combat.fakes import FakeEnemy

        run = fake_run([FakeEnemy(0.0, 0.0)])
        self.assertEqual(_per_second(run, 1 / 60), 0.0)

    def test_no_step_sheds_nothing(self):
        run = fake_run(_primed(10))
        rng = run.element_visuals.rng.getstate()
        self.assertEqual(shed.update(run, 0.0), 0)
        self.assertEqual(run.element_visuals.rng.getstate(), rng)


class BudgetBoundsTests(unittest.TestCase):
    """The budget is `per_frame` 90 and `per_element` 40 per 1/60 s of play:
    5,400 and 2,400 motes a second. Each cap must bite when a crowd owes
    more, by the same amount a second at every step length, and never let
    one step past its share. Four seconds a sample: these crowds are big."""

    SECONDS = 4.0

    def _capped(self, crowd, cap_per_step, dt):
        """Motes a second over `SECONDS`, asserting the step cap as it goes."""
        run = fake_run(crowd)
        budget = run.element_visuals.budget
        steps = round(self.SECONDS / dt)
        for _ in range(steps):
            before = _born(run.particles.bursts)
            shed.update(run, dt)
            # The carried fraction can lift one step by less than a mote.
            self.assertLess(budget.spent, cap_per_step(budget) * dt + 1)
            # What is born is what was granted, not what was owed.
            self.assertEqual(_born(run.particles.bursts) - before, budget.spent)
        return budget, _born(run.particles.bursts) / (steps * dt)

    def test_one_elements_share_bites(self):
        # 400 Fire auras owe 2,800 a second, past Fire's 2,400.
        crowd = _primed(400, spacing=2.0)
        for dt in STEPS:
            with self.subTest(dt=round(1 / dt)):
                budget, per_second = self._capped(
                    crowd, lambda b: b.per_element * b.RATE_HZ, dt)
                allowed = budget.per_element * budget.RATE_HZ
                self.assertLessEqual(per_second, allowed + 1 / self.SECONDS)
                self.assertGreater(per_second, 0.95 * allowed, "the cap never bit")

    def test_a_body_owed_several_motes_is_given_only_what_is_granted(self):
        # Half-second steps owe each Fire aura 3 or 4 motes; a budget of 1
        # per 1/60 s grants 30 a step, so some body is granted part of its
        # share. Every step's births must equal the grant, never the debt.
        from game.states.playing.visual.elements.budget import ParticleBudget

        run = fake_run(_primed(50))
        run.element_visuals.budget = budget = ParticleBudget(1, 1)
        for _ in range(20):
            before = _born(run.particles.bursts)
            shed.update(run, 0.5)
            self.assertEqual(budget.spent, 30)
            self.assertEqual(_born(run.particles.bursts) - before, 30)

    def test_the_frame_cap_bites_across_the_elements(self):
        # 300 of each element owe 2,100 + 1,500 + 1,800 + 1,800 = 7,200 a
        # second: every element under its own 2,400, the sum past 5,400.
        crowd = [b for element in ELEMENTS
                 for b in _primed(300, element, spacing=0.8)]
        for dt in STEPS:
            with self.subTest(dt=round(1 / dt)):
                budget, per_second = self._capped(
                    crowd, lambda b: b.per_frame * b.RATE_HZ, dt)
                allowed = budget.per_frame * budget.RATE_HZ
                self.assertLessEqual(per_second, allowed + 1 / self.SECONDS)
                self.assertGreater(per_second, 0.95 * allowed, "the cap never bit")


class OwnStreamTests(unittest.TestCase):
    def test_the_update_time_shed_never_rolls_run_rng(self):
        run = fake_run(_primed(50))
        rng = run.rng.getstate()
        _per_second(run, 1 / 62, seconds=2.0)
        self.assertGreater(_born(run.particles.bursts), 0)
        self.assertEqual(run.rng.getstate(), rng)

    def test_the_same_seed_sheds_the_same_motes(self):
        def bursts(seed):
            run = fake_run(_primed(20))
            run.element_visuals = ElementVisuals(C, seed=seed)
            _per_second(run, 1 / 62, seconds=2.0)
            return [(tuple(pos), kw["count"]) for pos, _, kw in run.particles.bursts]

        self.assertEqual(bursts(7), bursts(7))
        self.assertNotEqual(bursts(7), bursts(8))

    def test_the_stream_is_seeded_from_the_run_seed(self):
        a = ElementVisuals(C, seed=123).rng
        self.assertEqual(a.getstate(), random.Random("123:aura_shed").getstate())


class BootedRunTests(unittest.TestCase):
    """The same contract in a real run: the state calls the shed once per
    update step with that step's `dt`, seeded from the run, and
    `PlayingState.draw` leaves the run as it found it."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        from game.game import Game
        from game.states.menu_state import MenuState
        from tests.boot import start_run

        cls.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        cls.game.state_machine.change(MenuState(cls.game))
        cls.ps = start_run(cls.game, SEED)
        cls.fresh_stream = cls.ps.run.element_visuals.rng.getstate()
        cls._prime_the_view(cls.ps)

    @classmethod
    def _prime_the_view(cls, ps):
        from tests.nearby import spots_near

        run = ps.run
        now = run.stats["time"]
        for spot in spots_near(ps, 8, radius=14.0):
            body = ps.spawn.master.spawn_at("skull", spot, owner="test")
            if body is not None:
                body.elemental.set_aura(ElementId.FIRE, now, 1e6)

    def test_the_stream_is_the_run_seeds(self):
        self.assertEqual(self.fresh_stream,
                         random.Random(f"{self.ps.run.seed}:aura_shed").getstate())

    def test_the_draw_leaves_the_run_as_it_found_it(self):
        ps, run = self.ps, self.ps.run
        surface = pygame.Surface((640, 360))
        ps.update(1 / 62)                        # a budget with a step behind it
        ps.draw(surface)
        self.assertGreater(run.element_visuals.auras_drawn, 0, "no aura in view")
        rng, own, motes = (run.rng.getstate(), run.element_visuals.rng.getstate(),
                           len(run.particles))
        budget = _budget_state(run.element_visuals.budget)
        self.assertGreater(budget[4], 0, "the step granted nothing")
        for _ in range(60):
            ps.draw(surface)
        self.assertEqual(run.rng.getstate(), rng)
        self.assertEqual(run.element_visuals.rng.getstate(), own)
        self.assertEqual(len(run.particles), motes)
        self.assertEqual(_budget_state(run.element_visuals.budget), budget)

    def test_a_mote_is_drawn_whole_on_the_step_it_is_born(self):
        """The shed runs after the particles age (`state.py`), so a mote
        born this step has its whole life when the frame is drawn; shed
        before the ageing and every one would already be a step old."""
        ps, run = self.ps, self.ps.run
        for _ in range(30):
            before = {id(p) for p in run.particles.layer(True)}
            ps.update(1 / 62)
            born = [p for p in run.particles.layer(True) if id(p) not in before]
            if born:
                break
        self.assertTrue(born, "no mote was born in 30 steps")
        self.assertTrue(all(p.life == p.max_life for p in born))

    def test_nothing_sheds_under_the_end_banner(self):
        """RND-011.D5: `run_end.ending_sequence` stands in for the update
        while the end banner waits, and births nothing: the particles age,
        the shed's stream holds still."""
        ps, run = self.ps, self.ps.run
        ps.draw(pygame.Surface((640, 360)))
        self.assertGreater(run.element_visuals.auras_drawn, 0, "no aura in view")
        own, motes = run.element_visuals.rng.getstate(), len(run.particles)
        with mock.patch.object(ps.run_end, "ending", True):
            with mock.patch.object(fx.shed, "update", wraps=fx.shed.update) as m:
                for _ in range(60):
                    ps.update(1 / 62)
        self.assertEqual(m.call_count, 0)
        self.assertEqual(run.element_visuals.rng.getstate(), own)
        self.assertLessEqual(len(run.particles), motes, "a mote was born")

    def test_the_update_sheds_once_a_step_with_its_dt(self):
        ps = self.ps
        with mock.patch.object(fx.shed, "update", wraps=fx.shed.update) as m:
            for dt in STEPS:
                ps.update(dt)
        self.assertEqual([c.args[1] for c in m.call_args_list], list(STEPS))
        self.assertTrue(all(c.args[0] is ps.run for c in m.call_args_list))

    def test_the_shed_in_a_real_run_adds_motes_under_the_bodies(self):
        run = self.ps.run
        before = len(run.particles.layer(True))
        rng = run.rng.getstate()
        for _ in range(30):
            shed.update(run, 1 / 62)
        self.assertGreater(len(run.particles.layer(True)), before)
        self.assertEqual(run.rng.getstate(), rng)


if __name__ == "__main__":
    unittest.main()
