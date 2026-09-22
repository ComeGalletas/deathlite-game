"""Where the elemental visuals sit in the paint order (M10 rule 3).

The rule is by *meaning*: a persistent elemental state -- an aura, a
tornado, a status mark, a jump arc -- belongs **under** the bodies it is
attached to, so a crowd of primed enemies never becomes a wall of effect
art with the enemies lost inside it. A reaction is a momentary event and
goes **over** everything, briefly, because it is the one elemental visual
the player must not miss.

Both used to be a single pass immediately after `_draw_world`, which put
all of it above every character. These pin the split, because it is the
kind of thing a later refactor moves back by accident: the two passes look
interchangeable from inside the module that owns them.

The run boots on a pinned seed -- an unpinned world is a coin flip about
where the hero stands and therefore about which terrace bands exist at
all.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS, REACTIONS
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing.visual import elements as element_fx
from game.states.playing.visual import elements as fx
from game.states.playing.visual import scene
from game.states.playing.visual.elements import transient
from tests import worlds as W
# The headless fake run and its stub camera, shared with the sibling
# module rather than written twice.
from tests.render.test_element_visuals import _Camera, _init, fake_run

SEED = W.pinned(0)


class DrawOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        from tests.boot import start_run
        cls.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        cls.game.state_machine.change(MenuState(cls.game))
        cls.ps = start_run(cls.game, SEED)

    def setUp(self):
        self.ps = type(self).ps
        self.surface = pygame.Surface((640, 360))
        self.run = self.ps.run
        self.run.element_fx.clear()

    def _primed_enemy(self):
        """An enemy beside the hero, holding an aura.

        Seated here rather than picked out of whatever the spawn master
        left in view: what the master happened to seat is not this test's
        subject, and on two of the seeds tried the run simply had nothing
        near the hero, which turned both order tests into skips.
        """
        from tests.nearby import spots_near

        view = self.run.camera.visible_rect()
        for enemy in self.run.enemies:
            if view.collidepoint(enemy.pos.x, enemy.pos.y):
                enemy.elemental.set_aura(ELEMENTS[0], self.run.stats["time"],
                                         600.0)
                return enemy
        spots = spots_near(self.ps, 1, radius=14.0)
        self.assertTrue(spots, "the hero has nowhere an enemy can stand")
        enemy = self.ps.spawn.master.spawn_at("skull", spots[0], owner="test")
        self.assertIsNotNone(enemy, "the spawn master refused a placed body")
        enemy.elemental.set_aura(ELEMENTS[0], self.run.stats["time"], 600.0)
        return enemy

    def _trace(self):
        """`ps.draw` with the elemental passes and the enemy painter logged
        in call order."""
        events = []
        real_under = element_fx.draw_under
        real_reactions = element_fx.draw_reactions
        real_begin = element_fx.begin_frame
        real_enemy = self.ps._draw_one_enemy

        def under(surface, run, level=None):
            events.append("under")
            return real_under(surface, run, level)

        def reactions(surface, run):
            events.append("reaction")
            return real_reactions(surface, run)

        def begin(run):
            events.append("begin")
            return real_begin(run)

        def enemy(surface, e):
            events.append("enemy")
            return real_enemy(surface, e)

        with mock.patch.object(scene.element_fx, "draw_under", under), \
                mock.patch.object(element_fx, "draw_reactions", reactions), \
                mock.patch.object(element_fx, "begin_frame", begin), \
                mock.patch.object(self.ps, "_draw_one_enemy", enemy):
            # `state.py` holds its own reference to the module, so patching
            # the module's attribute is what reaches both call sites.
            self.ps.draw(self.surface)
        return events

    def test_an_aura_pass_runs_before_any_enemy_is_painted(self):
        self._primed_enemy()
        events = self._trace()
        self.assertIn("under", events)
        self.assertIn("enemy", events)
        self.assertLess(events.index("under"), events.index("enemy"),
                        "the elemental state paints under the bodies")

    def test_a_reaction_paints_after_every_character(self):
        self._primed_enemy()            # so there is a body to go over
        self.run.element_fx.append(
            transient.Flash(self.run.player.pos, REACTIONS[0], 40.0,
                            self.run.stats["time"]))
        events = self._trace()
        self.assertIn("reaction", events)
        self.assertIn("enemy", events)
        last_enemy = len(events) - 1 - events[::-1].index("enemy")
        self.assertGreater(events.index("reaction"), last_enemy,
                           "a reaction goes over every body")

    def test_the_frame_begins_once_however_many_bands_there_are(self):
        """The particle budget and the aura counter are per frame. The
        under-pass runs once per terrace, so resetting them there would
        hand each band the whole budget and leave the counter showing only
        the last band's auras."""
        events = self._trace()
        self.assertEqual(events.count("begin"), 1)
        self.assertGreaterEqual(events.count("under"), 1)
        self.assertLess(events.index("begin"), events.index("under"))

    def test_auras_drawn_counts_every_band_not_just_the_last(self):
        self._primed_enemy()
        self.ps.draw(self.surface)
        self.assertGreaterEqual(self.run.element_visuals.auras_drawn, 1)


class BandingTests(unittest.TestCase):
    """`off_band` is the same rule the other flat effects use, including
    its `level is None` escape -- the headless tests draw fake runs that
    have no map at all."""

    def test_no_level_draws_everything(self):
        import types
        run = types.SimpleNamespace()
        self.assertFalse(transient.off_band(run, None, (0.0, 0.0)))

    def test_a_run_without_a_map_draws_everything(self):
        import types
        run = types.SimpleNamespace(game_map=None)
        self.assertFalse(transient.off_band(run, 2, (0.0, 0.0)))

    def test_a_position_on_another_terrace_is_skipped(self):
        import types
        renderer = types.SimpleNamespace(level_at=lambda x, y: 3)
        run = types.SimpleNamespace(
            game_map=types.SimpleNamespace(renderer=renderer))
        self.assertTrue(transient.off_band(run, 2, (0.0, 0.0)))
        self.assertFalse(transient.off_band(run, 3, (0.0, 0.0)))


class TransientSplitTests(unittest.TestCase):
    """The split cuts across the pooled list: arcs band, bursts do not."""

    def test_an_arc_bands_and_a_flash_does_not(self):
        self.assertFalse(transient.Arc.OVER)
        self.assertTrue(transient.Flash.OVER)


class ShedParticleLayerTests(unittest.TestCase):
    """The aura's shed goes under the bodies too (M11 A).

    It was the one piece of rule 3 that did not land in M10, and it did not
    land because the particles are not drawn by the elements package at
    all -- the pool is painted from `PlayingState.draw`, after the whole
    world. One flag on the particle splits it without a second pool.
    """

    def setUp(self):
        from systems.particles import ParticleSystem
        _init()
        self.surface = pygame.Surface((320, 240))
        self.particles = ParticleSystem(max_particles=64)

    def _drawn(self, **kwargs):
        """How many particles a `draw` call actually paints."""
        seen = []
        real = pygame.draw.circle

        def circle(surface, colour, centre, radius, *a, **kw):
            seen.append(colour)
            return real(surface, colour, centre, radius, *a, **kw)

        with mock.patch.object(pygame.draw, "circle", circle):
            self.particles.draw(self.surface, _Camera(), **kwargs)
        return len(seen)

    def test_the_default_burst_is_an_event_and_draws_late(self):
        self.particles.burst(pygame.Vector2(0, 0), (255, 0, 0), count=5)
        self.assertEqual(self._drawn(under=False), 5)
        self.assertEqual(self._drawn(under=True), 0)

    def test_an_under_burst_draws_in_the_banded_pass_only(self):
        self.particles.burst(pygame.Vector2(0, 0), (0, 255, 0), count=5,
                             under=True)
        self.assertEqual(self._drawn(under=True), 5)
        self.assertEqual(self._drawn(under=False), 0)

    def test_no_filter_draws_both(self):
        self.particles.burst(pygame.Vector2(0, 0), (255, 0, 0), count=3)
        self.particles.burst(pygame.Vector2(0, 0), (0, 255, 0), count=4,
                             under=True)
        self.assertEqual(self._drawn(), 7)

    def test_the_flag_is_reset_when_a_particle_is_recycled(self):
        """A pooled object outlives its last use, so a stale `under` would
        strand an event particle in the wrong layer."""
        self.particles.burst(pygame.Vector2(0, 0), (0, 255, 0), count=64,
                             under=True)
        for p in self.particles._pool:
            p.life = -1.0
            p.active = False
        self.particles._pool.sweep()
        self.particles.burst(pygame.Vector2(0, 0), (255, 0, 0), count=5)
        self.assertEqual(self._drawn(under=False), 5,
                         "a recycled particle kept the old layer")

    def test_the_shed_asks_for_the_lower_layer(self):
        """The one caller that wants it. Checked through `fx.draw` rather
        than by reading `_shed`, so a refactor that stops passing the flag
        is caught."""
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(0.0, 0.0)
        body.elemental.set_aura(ELEMENTS[0], 0.0, 10.0)
        run = fake_run([body])
        run.particles = self.particles
        # The shed is a once-a-frame chance per aura, so drive enough
        # frames that it cannot plausibly have been skipped every time.
        for _ in range(400):
            fx.draw(self.surface, run)
        under = [p for p in self.particles._pool if p.under]
        self.assertTrue(under, "the aura shed nothing in 400 frames")
        self.assertEqual(len(under), len(list(self.particles._pool)),
                         "the aura shed an event-layer particle")


if __name__ == "__main__":
    unittest.main()
