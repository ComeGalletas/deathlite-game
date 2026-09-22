"""Elemental system M8: the visual system (design §8, journal
`elemental_system_journal.md`).

Drawing cannot be asserted pixel by pixel without pinning art that is still
being chosen, so what is pinned here is the contract the drawing keeps:
every element is distinguishable without colour, the particle budget is
honoured, the transient list cannot grow without bound, and the two layers
stay separate.

Each drawing pass is also run against a real surface, because a layer that
raises is a black screen in a run and no unit test of its numbers would
catch it.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS, REACTIONS, ElementId
from game.content import get_content
from game.states.playing.visual import elements as fx
from game.states.playing.visual.elements import layers, markers, transient
from game.states.playing.visual.elements.budget import ParticleBudget
from game.states.playing.visual.elements.profiles import get_visuals

C = get_content()


def _init():
    pygame.init()
    pygame.display.set_mode((320, 240))


class _Camera:
    zoom = 1.0

    @staticmethod
    def world_to_screen(pos):
        return (float(pos[0]) + 160.0, float(pos[1]) + 120.0)

    @staticmethod
    def visible_rect():
        return pygame.Rect(-1000, -1000, 2000, 2000)


def fake_run(enemies=()):
    """A `Run`-shaped namespace with only what the drawing reads."""
    import random
    from types import SimpleNamespace

    from game.states.playing.visual.elements import ElementVisuals

    class _Particles:
        """Records bursts instead of pooling them.

        `draw` is a no-op rather than absent: since M11 the elemental
        under-pass paints the aura's shed itself, so a stub without it
        turns every drawing test in this module into an AttributeError.
        """

        def __init__(self):
            self.bursts = []

        def burst(self, pos, colour, **kw):
            self.bursts.append((pos, colour, kw))

        def draw(self, surface, camera, under=None, keep=None):
            pass

    run = SimpleNamespace(
        enemies=list(enemies), boss=None, camera=_Camera(),
        stats={"time": 0.0}, wind_areas=[], element_fx=[],
        particles=_Particles(), rng=random.Random(5))
    run.element_visuals = ElementVisuals(C)
    return run


# --- the profiles -----------------------------------------------------------------

class ProfileTests(unittest.TestCase):
    def setUp(self):
        _init()
        self.visuals = get_visuals(C)

    def test_every_element_has_a_profile(self):
        for element in ELEMENTS:
            with self.subTest(element=element.key):
                self.assertIsNotNone(self.visuals.get(element))

    def test_no_two_elements_share_a_colour_or_a_shape(self):
        colours = {self.visuals[e].colour for e in ELEMENTS}
        shapes = {self.visuals[e].marker for e in ELEMENTS}
        self.assertEqual(len(colours), len(ELEMENTS))
        self.assertEqual(len(shapes), len(ELEMENTS),
                         "shape carries the element without colour (§8)")

    def test_every_marker_is_a_shape_the_renderer_knows(self):
        for element in ELEMENTS:
            self.assertIn(self.visuals[element].marker, markers.SHAPES)

    def test_every_element_now_has_authored_art(self):
        """M10: all four auras are cut art. The procedural ring stays wired
        as the empty-`assets/` fallback and for the locked slot, but no
        element reaches it any more."""
        for element in ELEMENTS:
            self.assertIsNotNone(self.visuals[element].aura_frame(),
                                 f"{element.key} has no aura frame")

    def test_status_art_is_keyed_by_status_not_by_element(self):
        """`burn` is shared with the weapon blessings, which have no element
        behind them; `chill` has no art and falls back to its chevron."""
        self.assertIsNotNone(self.visuals.status_frame("burn"))
        self.assertIsNotNone(self.visuals.status_frame("freeze"))
        self.assertIsNone(self.visuals.status_frame("chill"))

    def test_every_reaction_has_a_burst(self):
        for reaction in REACTIONS:
            burst = self.visuals.reaction(reaction.key)
            self.assertIsNotNone(burst, f"{reaction.key} has no burst")
            self.assertGreater(burst.frames, 0)
            self.assertGreater(burst.seconds, 0.0)

    def test_a_reaction_burst_is_indexed_not_clocked(self):
        """Two Overloads half a second apart are two events: each starts at
        its own first frame, so the burst is taken by progress rather than
        off the shared clock an aura rides."""
        burst = self.visuals.reaction("overload")
        first = burst.frame_at(0.0)
        self.assertIsNot(burst.frame_at(0.5), first)
        self.assertIs(burst.frame_at(0.0), first, "and 0 is always frame 0")
        # Clamped, not wrapped: overshooting holds the last frame.
        self.assertIs(burst.frame_at(1.5), burst.frame_at(0.999))

    def test_one_clock_per_element_not_one_per_aura(self):
        """A hundred burning enemies must not be a hundred animators."""
        thunder = self.visuals[ElementId.THUNDER]
        first = thunder.aura_frame()
        self.assertIs(thunder.aura_frame(), first, "same frame, same clock")
        # A third of a second, not a whole one: Thunder's loop is 16 frames
        # at 16 fps, so advancing by exactly 1 s would land back on frame 0
        # and this would assert that a working clock is broken.
        for _ in range(10):
            self.visuals.update(1 / 30)
        self.assertIsNot(thunder.aura_frame(), first, "and it does advance")

    def test_the_set_is_cached_per_content(self):
        self.assertIs(get_visuals(C), self.visuals)


# --- the budget --------------------------------------------------------------------

class BudgetTests(unittest.TestCase):
    def test_it_grants_up_to_the_frame_cap_and_then_refuses(self):
        b = ParticleBudget(per_frame=10, per_element=10)
        b.begin_frame()
        self.assertEqual(sum(b.take(ELEMENTS[0]) for _ in range(12)), 10)
        self.assertEqual(b.spent, 10)
        self.assertEqual(b.refused, 2)

    def test_one_element_cannot_take_the_whole_frame(self):
        b = ParticleBudget(per_frame=100, per_element=3)
        b.begin_frame()
        self.assertEqual(sum(b.take(ELEMENTS[0]) for _ in range(9)), 3)
        self.assertEqual(sum(b.take(ELEMENTS[1]) for _ in range(9)), 3,
                         "its neighbour still has its own share")

    def test_it_refills_each_frame(self):
        b = ParticleBudget(per_frame=4, per_element=4)
        b.begin_frame()
        self.assertEqual(sum(b.take(ELEMENTS[0]) for _ in range(9)), 4)
        b.begin_frame()
        self.assertEqual(sum(b.take(ELEMENTS[0]) for _ in range(9)), 4)

    def test_a_crowd_of_auras_cannot_outspend_it(self):
        """The point of the budget: the shared particle pool keeps room for
        the hit bursts and death poofs however many auras are alive."""
        _init()
        from tests.combat.fakes import FakeEnemy

        crowd = [FakeEnemy(i * 4.0, 0.0) for i in range(120)]
        run = fake_run(crowd)
        for enemy in crowd:
            enemy.elemental.set_aura(ElementId.FIRE, 0.0, 10.0)
        surface = pygame.Surface((320, 240))
        for _ in range(8):
            fx.draw(surface, run)
            self.assertLessEqual(run.element_visuals.budget.spent,
                                 run.element_visuals.budget.per_frame)


# --- the transient pool ---------------------------------------------------------------

class TransientTests(unittest.TestCase):
    def setUp(self):
        _init()
        self.run = fake_run()

    def test_arcs_and_flashes_share_one_capped_list(self):
        for i in range(transient.MAX_EFFECTS + 40):
            transient.add(self.run, transient.Arc((0, 0), (i, i),
                                                  ElementId.THUNDER, 1.0))
        self.assertEqual(len(self.run.element_fx), transient.MAX_EFFECTS)

    def test_add_reports_whether_it_took(self):
        self.assertTrue(transient.add(
            self.run, transient.Arc((0, 0), (1, 1), ElementId.THUNDER, 1.0)))
        self.run.element_fx = [None] * transient.MAX_EFFECTS
        self.assertFalse(transient.add(
            self.run, transient.Arc((0, 0), (1, 1), ElementId.THUNDER, 1.0)))

    def test_the_sweep_drops_what_has_expired(self):
        transient.add(self.run, transient.Arc((0, 0), (1, 1),
                                              ElementId.THUNDER, 0.5))
        transient.add(self.run, transient.Arc((0, 0), (1, 1),
                                              ElementId.THUNDER, 2.0))
        transient.sweep(self.run, 1.0)
        self.assertEqual(len(self.run.element_fx), 1)

    def test_a_reaction_flash_blends_both_of_its_elements(self):
        from combat.elements import config as element_config

        visuals = get_visuals(C)
        for reaction in REACTIONS:
            with self.subTest(reaction=reaction.key):
                colours = transient.blend_colours(visuals, reaction)
                a, b = element_config.REACTION_PAIRS[reaction]
                self.assertEqual(colours[0], visuals.tint(a))
                self.assertEqual(colours[-1], visuals.tint(b))
                self.assertNotIn(colours[1], (colours[0], colours[-1]))

    def test_every_reaction_has_a_palette_of_its_own(self):
        visuals = get_visuals(C)
        palettes = {tuple(transient.blend_colours(visuals, r)) for r in REACTIONS}
        self.assertEqual(len(palettes), len(REACTIONS))


# --- the layers draw ------------------------------------------------------------------

class DrawTests(unittest.TestCase):
    def setUp(self):
        _init()
        self.surface = pygame.Surface((320, 240))

    def crowd(self):
        from tests.combat.fakes import FakeEnemy

        bodies = [FakeEnemy(i * 26.0 - 60.0, 0.0) for i in range(4)]
        for body, element in zip(bodies, ELEMENTS):
            body.elemental.set_aura(element, 0.0, 10.0)
        return bodies

    def test_an_aura_of_every_element_draws(self):
        run = fake_run(self.crowd())
        fx.draw(self.surface, run)
        self.assertEqual(run.element_visuals.auras_drawn, 4)

    def test_a_locked_slot_draws_without_an_aura(self):
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(0.0, 0.0)
        body.elemental.lock(0.0, 5.0)
        run = fake_run([body])
        fx.draw(self.surface, run)
        self.assertEqual(run.element_visuals.auras_drawn, 0,
                         "locked is not an aura, and is drawn differently")

    def test_every_status_mark_draws(self):
        from tests.combat.fakes import FakeEnemy

        bodies = []
        for sid in ("burn", "chill", "freeze"):
            body = FakeEnemy(len(bodies) * 30.0, 0.0)
            body.status.apply(sid, 5.0, 1.0)
            bodies.append(body)
        fx.draw(self.surface, fake_run(bodies))

    def test_the_aura_and_status_layers_are_independent(self):
        """A body can be primed without burning and burning without being
        primed; both have to be legible either way (§8.3)."""
        from tests.combat.fakes import FakeEnemy

        primed, burning = FakeEnemy(-30.0, 0.0), FakeEnemy(30.0, 0.0)
        primed.elemental.set_aura(ElementId.FIRE, 0.0, 10.0)
        burning.status.apply("burn", 5.0, 1.0)
        run = fake_run([primed, burning])
        fx.draw(self.surface, run)
        self.assertEqual(run.element_visuals.auras_drawn, 1)

    def test_transient_effects_draw(self):
        run = fake_run()
        transient.add(run, transient.Arc((-40, -20), (40, 20),
                                         ElementId.THUNDER, 1.0))
        for reaction in REACTIONS:
            transient.add(run, transient.Flash((0, 0), reaction, 60.0, 1.0))
        fx.draw(self.surface, run)

    def test_a_wind_area_draws_tinted_toward_its_pair(self):
        from combat.elements import tracking
        from combat.elements.area import WindArea

        run = fake_run()
        for effect in (tracking.WIND_AREA, tracking.FIREWIND,
                       tracking.ICEWIND, tracking.THUNDERWIND):
            run.wind_areas.append(WindArea(
                pos=pygame.Vector2(0, 0), radius=50.0, expires_at=5.0,
                damage=0.0, knockback=0.0, weapon_id="bow", effect=effect,
                max_targets=4))
        fx.draw(self.surface, run)
        visuals = run.element_visuals.profiles
        plain = transient._area_colour(visuals, run.wind_areas[0])
        fiery = transient._area_colour(visuals, run.wind_areas[1])
        self.assertNotEqual(plain, fiery)

    def test_nothing_draws_for_a_run_with_no_visuals(self):
        run = fake_run()
        run.element_visuals = None
        fx.draw(self.surface, run)


# --- M10 rule 1 and rule 2: the sprite is the indicator -----------------------------

class SpriteIsTheIndicatorTests(unittest.TestCase):
    """Where art is wired it draws alone. The procedural ring and marker
    stay for the cases that have none: an empty `assets/`, and the locked
    slot, whose circle is what makes "primed" and "cannot be primed" one
    glance apart."""

    def setUp(self):
        _init()
        self.surface = pygame.Surface((320, 240))

    def _counted(self):
        """`fx.draw` with the procedural calls counted."""
        calls = {"ring": 0, "marker": 0}
        real_ring, real_marker = layers._ring, markers.draw

        def ring(*a, **k):
            calls["ring"] += 1
            return real_ring(*a, **k)

        def marker(*a, **k):
            calls["marker"] += 1
            return real_marker(*a, **k)

        return calls, ring, marker

    def test_an_element_with_a_rig_draws_no_ring_and_no_marker(self):
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(0.0, 0.0)
        body.elemental.set_aura(ElementId.FIRE, 0.0, 10.0)
        run = fake_run([body])
        calls, ring, marker = self._counted()
        with mock.patch.object(layers, "_ring", ring), \
                mock.patch.object(markers, "draw", marker):
            fx.draw(self.surface, run)
        self.assertEqual(run.element_visuals.auras_drawn, 1)
        self.assertEqual(calls["ring"], 0, "the sprite is the whole indicator")
        self.assertEqual(calls["marker"], 0)

    def test_an_element_without_a_rig_falls_back_to_both(self):
        """What a run with an empty `assets/` gets."""
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(0.0, 0.0)
        body.elemental.set_aura(ElementId.ICE, 0.0, 10.0)
        run = fake_run([body])
        profile = run.element_visuals.profiles[ElementId.ICE]
        calls, ring, marker = self._counted()
        # The profile is slotted, so its methods cannot be patched. Dropping
        # the animator is the same thing and is exactly what an empty
        # `assets/` produces.
        animator, profile._aura_anim = profile._aura_anim, None
        try:
            with mock.patch.object(layers, "_ring", ring), \
                    mock.patch.object(markers, "draw", marker):
                fx.draw(self.surface, run)
        finally:
            profile._aura_anim = animator
        self.assertEqual(calls["ring"], 1)
        self.assertEqual(calls["marker"], 1)

    def test_a_locked_slot_still_rings(self):
        """Rule 1 is about elements. "Cannot be primed" has no sprite, so by
        the same rule it keeps its circle."""
        from tests.combat.fakes import FakeEnemy

        body = FakeEnemy(0.0, 0.0)
        body.elemental.lock(0.0, 5.0)
        run = fake_run([body])
        calls, ring, marker = self._counted()
        with mock.patch.object(layers, "_ring", ring), \
                mock.patch.object(markers, "draw", marker):
            fx.draw(self.surface, run)
        self.assertEqual(calls["ring"], 1)

    def test_an_aura_sprite_keeps_the_art_aspect(self):
        """These frames were trimmed to their own content and are not
        square; squeezing one into a square box turns a ring into an
        ellipse."""
        profiles = get_visuals(C)
        for element in ELEMENTS:
            natural = profiles[element].aura_frame().get_size()
            got = profiles[element].aura_size(80.0)
            self.assertEqual(got[0], 80)
            self.assertAlmostEqual(got[1] / got[0], natural[1] / natural[0],
                                   places=1, msg=f"{element.key} is squeezed")

    def test_a_reaction_with_a_burst_draws_the_sprite_not_the_rings(self):
        run = fake_run()
        transient.add(run, transient.Flash((0, 0), REACTIONS[0], 60.0, 0.0))
        calls, ring, _marker = self._counted()
        with mock.patch.object(transient, "_ring", ring):
            fx.draw(self.surface, run)
        self.assertEqual(calls["ring"], 0)

    def test_a_reaction_without_a_burst_falls_back_to_the_blend(self):
        run = fake_run()
        transient.add(run, transient.Flash((0, 0), REACTIONS[0], 60.0, 0.0))
        calls, ring, _marker = self._counted()
        visuals = run.element_visuals.profiles
        with mock.patch.object(visuals, "reaction", lambda key: None), \
                mock.patch.object(transient, "_ring", ring):
            fx.draw(self.surface, run)
        self.assertGreater(calls["ring"], 0, "three rings in the blend")

    def test_a_burst_sets_the_flash_lifetime_from_the_data(self):
        """The combat layer hands over `now`; how long the thing stays on
        screen is presentation tuning and belongs to the renderer."""
        import types

        from combat.elements.world import RunWorld

        run = fake_run()
        run.ledger = types.SimpleNamespace(elements=None)
        world = RunWorld(run)
        world.add_flash((0, 0), REACTIONS[0], 40.0, 5.0)
        flash = run.element_fx[-1]
        burst = run.element_visuals.profiles.reaction(REACTIONS[0].key)
        self.assertEqual(flash.started, 5.0)
        self.assertAlmostEqual(flash.until, 5.0 + burst.seconds)


# --- the data ----------------------------------------------------------------------

class DataTests(unittest.TestCase):
    def test_a_bad_marker_or_a_missing_element_is_refused(self):
        import copy

        from game.content import ContentError, _check_element_visuals

        base = C.element_visuals
        broken = copy.deepcopy(base)
        broken["elements"]["fire"]["marker"] = "squiggle"
        with self.assertRaises(ContentError):
            _check_element_visuals(broken)

        broken = copy.deepcopy(base)
        del broken["elements"]["wind"]
        with self.assertRaises(ContentError):
            _check_element_visuals(broken)

        broken = copy.deepcopy(base)
        broken["elements"]["ice"]["particles"]["rate"] = 0
        with self.assertRaises(ContentError):
            _check_element_visuals(broken)

    def test_a_reaction_without_a_burst_is_refused(self):
        """Every reaction draws over the whole scene, so every reaction
        needs one. A missing entry would quietly fall back to the
        procedural flash for that pair alone, which is the sort of gap
        nobody notices until they wonder why one reaction looks
        different."""
        import copy

        from game.content import ContentError, _check_element_visuals

        for mangle in (lambda d: d["reactions"].pop("overload"),
                       lambda d: d["reactions"]["overload"].pop("rig"),
                       lambda d: d["reactions"]["overload"].update(seconds=0),
                       lambda d: d["reactions"]["overload"].update(size=-1),
                       lambda d: d.pop("reactions"),
                       lambda d: d.pop("statuses")):
            broken = copy.deepcopy(C.element_visuals)
            mangle(broken)
            with self.assertRaises(ContentError):
                _check_element_visuals(broken)

    def test_a_rig_name_that_resolves_to_nothing_is_refused(self):
        """Checked separately from the shape, because the sprite files
        merge *after* this one loads. It matters more since M10: with the
        sprite as the whole indicator, a typo leaves a primed enemy with
        nothing drawn on it rather than falling back to a ring."""
        import copy

        from game.content import ContentError, _check_element_rigs

        _check_element_rigs(C.element_visuals, C.sprites)      # the real one

        for where, mangle in (
                ("an element", lambda d: d["elements"]["fire"].update(
                    aura_rig="no_such_rig")),
                ("a reaction", lambda d: d["reactions"]["overload"].update(
                    rig="no_such_rig")),
                ("a status", lambda d: d["statuses"].update(
                    burn="no_such_rig"))):
            broken = copy.deepcopy(C.element_visuals)
            mangle(broken)
            with self.assertRaises(ContentError, msg=where):
                _check_element_rigs(broken, C.sprites)

    def test_a_rig_without_a_loop_animation_is_refused(self):
        import copy

        from game.content import ContentError, _check_element_rigs

        sprites = dict(C.sprites)
        sprites["element_fire"] = {"frame": [64, 64]}          # no `anims`
        with self.assertRaises(ContentError):
            _check_element_rigs(copy.deepcopy(C.element_visuals), sprites)


if __name__ == "__main__":
    unittest.main()
