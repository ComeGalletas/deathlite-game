"""Floating damage numbers: the common (outgoing) style vs the incoming style
(red, 25% larger) shown when the hero takes damage."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from tests import worlds as W

SEED = W.pinned(1)

from game import config
from ui.damage_numbers import DamageNumbers, _BASE_PT, _IN_PT


class StyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_incoming_font_is_25_percent_bigger_than_common(self):
        self.assertEqual(_IN_PT, round(_BASE_PT * 1.25))
        dn = DamageNumbers()
        common, _crit, incoming = dn._fonts()
        self.assertGreater(incoming.get_height(), common.get_height())

    def test_add_flags_incoming(self):
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 12, incoming=True)
        dn.add(pygame.Vector2(0, 0), 7)
        flags = sorted(n.incoming for n in dn._pool)
        self.assertEqual(flags, [False, True])

    def test_incoming_renders_in_the_red_damage_colour(self):
        from systems.camera import Camera
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 9, incoming=True)
        surf = pygame.Surface((120, 60), pygame.SRCALPHA)
        dn.draw(surf, Camera(2000, 2000))
        r, g, b = config.COLOR_DAMAGE_IN
        hit = any(surf.get_at((x, y))[:3] == (r, g, b)
                  for x in range(0, 120, 2) for y in range(0, 60, 2))
        self.assertTrue(hit, "no pixel in COLOR_DAMAGE_IN was drawn")


class HeroDamageTests(unittest.TestCase):
    def test_player_damaged_pushes_an_incoming_number(self):
        from game.game import Game
        from game.states.menu_state import MenuState

        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        from tests.boot import start_run
        p = start_run(g, SEED)         # through the loading screen

        before = len(p.damage_numbers)
        p._on_player_damaged(amount=8.0)
        self.assertEqual(len(p.damage_numbers), before + 1)
        self.assertTrue(list(p.damage_numbers._pool)[-1].incoming)

        p._on_player_damaged(amount=0.0)      # fully absorbed -> no number
        self.assertEqual(len(p.damage_numbers), before + 1)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()


class CallerOwnedStyleTests(unittest.TestCase):
    """M11: a caller may own a number's colour, lifetime and priority.

    All three are generic on purpose. `ui/damage_numbers.py` does not know
    what an element is, the same way it does not know what a weapon is --
    it is handed a colour and draws it legibly.
    """

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_a_plain_number_owns_no_colour_and_lives_the_default(self):
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 12)
        n = next(iter(dn._pool))
        self.assertIsNone(n.colour)
        self.assertAlmostEqual(n.max_life, 0.6)

    def test_a_caller_colour_and_life_are_kept(self):
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 12, colour=(108, 74, 163), life=0.9)
        n = next(iter(dn._pool))
        self.assertEqual(n.colour, (108, 74, 163))
        self.assertAlmostEqual(n.max_life, 0.9)

    def test_the_colour_is_cleared_when_a_number_is_recycled(self):
        """A pooled object outlives its last use, so a stale colour would
        paint a weapon's number in the last element's hue."""
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 12, colour=(108, 74, 163), life=0.9)
        for n in dn._pool:
            n.life = -1.0
            n.active = False
        dn._pool.sweep()
        dn.add(pygame.Vector2(0, 0), 7)
        n = next(iter(dn._pool))
        self.assertIsNone(n.colour, "a recycled number kept the old colour")
        self.assertAlmostEqual(n.max_life, 0.6)

    def test_a_coloured_number_is_lifted_and_outlined(self):
        """Thunder is a dark violet and Wind a pale green over a green
        meadow: one is too dark to read against the world and the other
        too pale. Lifting fixes the first, the outline the second."""
        from ui.damage_numbers import _OWN_LIFT, _lifted, _outlined

        self.assertGreater(_lifted((108, 74, 163))[0], 108)
        self.assertGreater(_OWN_LIFT, 0.0)
        dn = DamageNumbers()
        font = dn._fonts()[0]
        plain = font.render("12", True, (255, 255, 255))
        outlined = _outlined(font, "12", (255, 255, 255))
        self.assertGreater(outlined.get_width(), plain.get_width(),
                           "the outline should grow the glyph")
        self.assertIs(_outlined(font, "12", (255, 255, 255)), outlined,
                      "and be cached -- five renders a number a frame is not")


class PoolPriorityTests(unittest.TestCase):
    """The last slice of the pool is reserved (M11).

    Measured, not assumed: elemental numbers live 0.9 s against a weapon's
    0.6 and arrive as a stream of burn ticks, so a large Fire fight fills
    the pool on its own -- the stress harness saturated all 200 slots. A
    full pool drops whatever asks next, and that might be the weapon's own
    number, which is the one being read.
    """

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_a_low_priority_number_yields_the_top_of_the_pool(self):
        from ui.damage_numbers import _LOW_PRIORITY_FULL

        dn = DamageNumbers(max_numbers=20)
        reserve_starts = int(20 * _LOW_PRIORITY_FULL)
        for _ in range(reserve_starts):
            dn.add(pygame.Vector2(0, 0), 1, low_priority=True)
        self.assertEqual(len(dn._pool), reserve_starts)
        dn.add(pygame.Vector2(0, 0), 1, low_priority=True)
        self.assertEqual(len(dn._pool), reserve_starts, "it should be refused")

    def test_an_ordinary_number_still_gets_the_reserve(self):
        dn = DamageNumbers(max_numbers=20)
        for _ in range(40):
            dn.add(pygame.Vector2(0, 0), 1, low_priority=True)
        held = len(dn._pool)
        self.assertLess(held, 20, "the reserve was spent on low-priority")
        for _ in range(20 - held):
            dn.add(pygame.Vector2(0, 0), 99)
        self.assertEqual(len(dn._pool), 20,
                         "an ordinary number should reach the full cap")


class ElementalNumberTests(unittest.TestCase):
    """What the elemental damage path asks for."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _world(self):
        import types

        from combat.elements.world import RunWorld
        from game.content import get_content
        from game.states.playing.visual.elements import ElementVisuals

        run = types.SimpleNamespace(
            ledger=types.SimpleNamespace(elements=None),
            element_visuals=ElementVisuals(get_content()))
        return RunWorld(run)

    def test_an_element_effect_takes_its_element_colour(self):
        from combat.elements.ids import ElementId
        from game.states.playing.visual.elements import tint

        world = self._world()
        for effect, element in (("fire_hit", ElementId.FIRE),
                                ("burn", ElementId.FIRE),
                                ("thunder_chain", ElementId.THUNDER),
                                ("frozen_contact", ElementId.ICE),
                                ("wind_area", ElementId.WIND)):
            with self.subTest(effect=effect):
                self.assertEqual(world.effect_colour(effect), tint(element))

    def test_a_reaction_effect_takes_the_mix_of_its_pair(self):
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import ReactionId
        from game.states.playing.visual.elements import tint
        from game.states.playing.visual.elements.transient import mix

        world = self._world()
        for effect, reaction in (("overload", ReactionId.OVERLOAD),
                                 ("overload_wave", ReactionId.OVERLOAD),
                                 ("frostburn", ReactionId.FROSTBURN)):
            with self.subTest(effect=effect):
                first, second = (tint(e) for e in REACTION_PAIRS[reaction])
                self.assertEqual(world.effect_colour(effect),
                                 mix(first, second, 0.5))

    def test_a_weapons_own_damage_has_no_element_colour(self):
        self.assertIsNone(self._world().effect_colour("sword"))
        self.assertIsNone(self._world().effect_colour(""))

    def test_every_effect_id_is_accounted_for(self):
        """A new effect with no entry would silently draw in the plain
        colour, which reads as the weapon's own damage."""
        from combat.elements import tracking

        missing = [e for e in tracking.EFFECTS if tracking.source_of(e) is None]
        self.assertEqual(missing, [])


class ReactionLabelTests(unittest.TestCase):
    """A reaction pops its name out of the enemy it fired on (M11 C)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_a_label_is_a_number_whose_text_is_a_word(self):
        """Same pool, same cap, same sweep: it shares every one of those
        with the damage numbers on purpose."""
        dn = DamageNumbers()
        dn.add_label(pygame.Vector2(0, 0), "Overload", (255, 130, 60),
                     (108, 74, 163))
        n = next(iter(dn._pool))
        self.assertEqual(n.text, "Overload")
        self.assertEqual(n.colour, (255, 130, 60))
        self.assertEqual(n.outline, (108, 74, 163))

    def test_a_label_rises_more_slowly_and_starts_higher(self):
        """A word has to be read, and the same body is usually taking the
        reaction's damage in the same frame."""
        from ui.damage_numbers import _LABEL_RISE

        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 100), 5)
        number = next(iter(dn._pool))
        dn.add_label(pygame.Vector2(0, 100), "Overload", (1, 1, 1), (2, 2, 2),
                     lift=16.0)
        label = list(dn._pool)[-1]
        self.assertLess(label.pos.y, number.pos.y, "the label sits higher")
        self.assertEqual(label.rise, _LABEL_RISE)
        self.assertLess(label.rise, number.rise)

    def test_the_outline_is_cleared_when_a_number_is_recycled(self):
        """Otherwise a plain damage number inherits a label's second
        colour and is drawn as a two-tone word."""
        dn = DamageNumbers()
        dn.add_label(pygame.Vector2(0, 0), "Overload", (1, 1, 1), (2, 2, 2))
        for n in dn._pool:
            n.life = -1.0
            n.active = False
        dn._pool.sweep()
        dn.add(pygame.Vector2(0, 0), 7)
        n = next(iter(dn._pool))
        self.assertIsNone(n.outline)
        self.assertEqual(n.rise, 38.0)

    def test_a_full_pool_drops_labels_rather_than_growing(self):
        dn = DamageNumbers(max_numbers=8)
        for _ in range(30):
            dn.add_label(pygame.Vector2(0, 0), "Overload", (1, 1, 1), (2, 2, 2))
        self.assertEqual(len(dn._pool), 8)

    def test_every_reaction_draws_its_name_in_both_of_its_colours(self):
        from combat.elements import tracking
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import REACTIONS
        from game.content import get_content
        from game.states.playing.visual.elements.profiles import get_visuals
        from ui.damage_numbers import _LABEL_LIFT, _labelled, _lift

        visuals = get_visuals(get_content())
        font = DamageNumbers()._label_font(1.0)
        for reaction in REACTIONS:
            with self.subTest(reaction=reaction.key):
                first, second = (visuals.tint(e)
                                 for e in REACTION_PAIRS[reaction])
                glyph = _labelled(font, tracking.label(reaction.key),
                                  first, second)
                pixels = {tuple(glyph.get_at((x, y)))[:3]
                          for x in range(glyph.get_width())
                          for y in range(glyph.get_height())
                          if glyph.get_at((x, y))[3] > 200}
                self.assertIn(_lift(first, _LABEL_LIFT), pixels,
                              "the fill colour is missing")
                self.assertIn(_lift(second, _LABEL_LIFT), pixels,
                              "the pair's second colour is missing")

    def test_the_text_is_the_one_the_run_summary_uses(self):
        """Taken from `tracking.label` rather than spelled again here, so
        the label and the summary cannot disagree about a name."""
        from combat.elements import tracking
        from combat.elements.ids import ReactionId

        self.assertEqual(tracking.label(ReactionId.OVERLOAD.key), "Overload")
        self.assertEqual(tracking.label(ReactionId.THUNDERWIND.key),
                         "ThunderWind")


class LabelColourOrderTests(unittest.TestCase):
    """Which of a reaction's two elements is the fill and which the ring.

    `REACTION_PAIRS` order is taxonomy -- it decides the blend, the art and
    the tests -- so which colour reads better *inside* a word is a separate
    question with its own answer in `element_visuals.json`.
    """

    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _visuals(self):
        from game.content import get_content
        from game.states.playing.visual.elements.profiles import get_visuals

        return get_visuals(get_content())

    def test_frostburn_reads_ice_inside_and_fire_outside(self):
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import ElementId, ReactionId

        burst = self._visuals().reaction(ReactionId.FROSTBURN.key)
        pair = REACTION_PAIRS[ReactionId.FROSTBURN]
        self.assertEqual(burst.label_pair(pair),
                         (ElementId.ICE, ElementId.FIRE))
        self.assertNotEqual(burst.label_pair(pair), pair,
                            "this is the reversal, so it must differ")

    def test_a_reaction_without_an_override_follows_the_pair(self):
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import ReactionId

        visuals = self._visuals()
        for reaction in ReactionId:
            if reaction is ReactionId.FROSTBURN:
                continue
            with self.subTest(reaction=reaction.key):
                pair = REACTION_PAIRS[reaction]
                self.assertEqual(
                    visuals.reaction(reaction.key).label_pair(pair), pair)

    def test_every_label_pair_is_two_elements_of_that_reaction(self):
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import ReactionId

        visuals = self._visuals()
        for reaction in ReactionId:
            with self.subTest(reaction=reaction.key):
                pair = REACTION_PAIRS[reaction]
                fill, ring = visuals.reaction(reaction.key).label_pair(pair)
                self.assertEqual({fill, ring}, set(pair))
                self.assertNotEqual(fill, ring)

    def test_a_bad_label_order_is_refused_at_boot(self):
        from game.content import ContentError, _check_reaction_label

        _check_reaction_label("frostburn", {"fill": "ice", "ring": "fire"})
        _check_reaction_label("frostburn", None)          # optional
        for bad, why in (({"fill": "ice"}, "only one named"),
                         ({"fill": "ice", "ring": "wind"}, "not in the pair"),
                         ({"fill": "ice", "ring": "ice"}, "the ring vanishes"),
                         ("ice/fire", "not an object")):
            with self.subTest(why=why):
                with self.assertRaises(ContentError):
                    _check_reaction_label("frostburn", bad)
