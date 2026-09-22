"""The elemental colours, and the art agreeing with them (M12).

Two kinds of drift this pins, both of which happened while M12 was being
built and neither of which any other test would have caught.

**A second copy of a colour.** `overlays.py` kept its own table of all four
element colours for the dev aura inspector, justified in a comment as a
debug marker rather than the game's look. When Thunder went from yellow to
purple the inspector would have gone on labelling a purple aura in yellow.
The owner's rule is that discontinued references and appearances are not
acceptable, so the table is gone and this makes sure it cannot come back.

**Art that no longer matches its colour.** The aura and reaction strips are
*cut* assets with a colour baked into them. Changing a number in
`element_visuals.json` cannot reach them; only re-running
`tools/asset_pipeline/cut_element_effects.py` can. Nothing else in the
suite looks at a pixel, so a colour change that forgot the art would show
up only as somebody eventually noticing.

That second one is not hypothetical. Overload's first pair ramp was
authored as "purple shadow to orange core" and shipped with **no purple in
it at all**: fire and thunder are nearly opposite on the colour wheel, so a
straight RGB interpolation between them passes through muddy red rather
than showing either end, and the source's darkest pixels never reach the
dark end anyway. The picture looked plausible. The measurement did not.

Hue rather than RGB distance, because what is being asserted is "this is
still the same colour family", not "this is the same colour" -- the art is
a whole ramp and the declared value is one point on it. Measured deltas
today are 0 to 11 degrees against a 45 degree threshold, so there is four
times the headroom for a retune and still no room for a 150-degree mistake
like yellow for purple.
"""
import colorsys
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.config import REACTION_PAIRS
from combat.elements.ids import ELEMENTS, REACTIONS, ElementId, ReactionId
from game.content import get_content

C = get_content()

# How far an authored strip's hue may sit from the colour it is meant to be.
HUE_TOLERANCE = 45.0
# A pixel this unsaturated, this dark or this pale states no hue worth
# measuring -- the packs' art is outlined in near-black and cored in
# near-white, and both would drag a mean around.
_MIN_SAT, _MIN_LIGHT, _MAX_LIGHT = 0.25, 0.12, 0.93
# For a strip that is meant to hold *two* hues, how much of its coloured
# area each one has to claim.
_MIN_SHARE = 0.05


def _init():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def hue_of(rgb) -> float:
    return colorsys.rgb_to_hls(*[c / 255 for c in rgb])[0] * 360.0


def hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _coloured_pixels(path: str) -> list:
    surface = pygame.image.load(path).convert_alpha()
    out = []
    for y in range(surface.get_height()):
        for x in range(surface.get_width()):
            r, g, b, a = surface.get_at((x, y))
            if a < 200:
                continue
            h, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if sat < _MIN_SAT or light < _MIN_LIGHT or light > _MAX_LIGHT:
                continue
            out.append((h * 360.0, sat))
    return out


def mean_hue(path: str):
    """The strip's hue, averaged on the circle and weighted by saturation.

    A plain mean is wrong for hue: red at 350 and red at 10 average to
    cyan. Summing unit vectors and taking the angle back is the standard
    fix, and weighting by saturation lets the colours that actually state
    the hue outvote the washed-out ones.
    """
    x = y = 0.0
    for h, sat in _coloured_pixels(path):
        rad = math.radians(h)
        x += math.cos(rad) * sat
        y += math.sin(rad) * sat
    if not (x or y):
        return None
    return math.degrees(math.atan2(y, x)) % 360.0


def share_near(path: str, target: float) -> float:
    """What fraction of a strip's coloured pixels sit near `target`."""
    pixels = _coloured_pixels(path)
    if not pixels:
        return 0.0
    near = sum(1 for h, _s in pixels if hue_gap(h, target) <= HUE_TOLERANCE)
    return near / len(pixels)


def declared(element: ElementId):
    return tuple(C.element_visuals["elements"][element.key]["colour"])


# --- the second copy ----------------------------------------------------------------

class DevInspectorTests(unittest.TestCase):
    """The dev aura inspector reads the game's colours, it does not keep
    its own."""

    def setUp(self):
        _init()

    def test_every_element_matches_the_data(self):
        from game.states.playing.devtools.overlays import aura_colour

        for element in ELEMENTS:
            self.assertEqual(
                tuple(aura_colour(element.key)), declared(element),
                f"the inspector's {element.key} has drifted from the data")

    def test_there_is_no_hand_kept_table_left(self):
        """Named rather than implied: this is the shape the defect took the
        first time, and a future edit could reintroduce it while leaving
        the test above passing by keeping both in step *today*."""
        from game.states.playing.devtools import overlays

        self.assertFalse(hasattr(overlays, "_AURA_COLOURS"),
                         "the inspector is keeping its own colour table again")

    def test_an_override_is_possible_and_visible(self):
        """There is room for a contrast nudge, but it has to be written
        down in `_READABLE` rather than forked."""
        from game.states.playing.devtools import overlays

        self.assertEqual(overlays._READABLE, {},
                         "an override exists -- if that is deliberate, say "
                         "why here; if not, it is a fork")


# --- the art agreeing with the data --------------------------------------------------

class AuraArtColourTests(unittest.TestCase):
    def setUp(self):
        _init()

    def test_each_aura_strip_is_its_element_colour(self):
        for element in ELEMENTS:
            with self.subTest(element=element.key):
                want = hue_of(declared(element))
                got = mean_hue(f"assets/effects/elements/{element.key}.png")
                self.assertIsNotNone(got, "the strip has no coloured pixels")
                self.assertLessEqual(
                    hue_gap(want, got), HUE_TOLERANCE,
                    f"{element.key}: the data says hue {want:.0f} and the cut "
                    f"art is {got:.0f}. Re-run "
                    "tools/asset_pipeline/cut_element_effects.py")


class ReactionArtColourTests(unittest.TestCase):
    """The six reactions split into two families, and the split is a
    decision rather than an accident."""

    # One swirl in three colours: the same mechanic with different
    # payloads, which should read as siblings. Each takes its payload
    # element's colour, not a mix of its pair.
    WIND_TRIO = {ReactionId.FIREWIND: ElementId.FIRE,
                 ReactionId.ICEWIND: ElementId.ICE,
                 ReactionId.THUNDERWIND: ElementId.THUNDER}
    # Remapped across their own pair, because one authored row is one
    # colour and these two have to state both of their elements.
    PAIR_RAMPED = (ReactionId.OVERLOAD, ReactionId.SUPERCONDUCT)

    def setUp(self):
        _init()

    def test_each_wind_reaction_wears_its_payload(self):
        for reaction, element in self.WIND_TRIO.items():
            with self.subTest(reaction=reaction.key):
                want = hue_of(declared(element))
                got = mean_hue(f"assets/effects/reactions/{reaction.key}.png")
                self.assertIsNotNone(got)
                self.assertLessEqual(
                    hue_gap(want, got), HUE_TOLERANCE,
                    f"{reaction.key} should carry {element.key}'s colour")

    def test_a_pair_ramped_reaction_shows_both_of_its_elements(self):
        """The test that caught the real one.

        Overload's first ramp was authored purple-to-orange and contained
        no purple: fire and thunder are nearly opposite on the wheel, so
        interpolating between them in RGB goes through mud, and the
        source's darkest pixels never reached the dark end. It looked
        fine. Only counting pixels found it.
        """
        for reaction in self.PAIR_RAMPED:
            path = f"assets/effects/reactions/{reaction.key}.png"
            for element in REACTION_PAIRS[reaction]:
                with self.subTest(reaction=reaction.key, element=element.key):
                    share = share_near(path, hue_of(declared(element)))
                    self.assertGreaterEqual(
                        share, _MIN_SHARE,
                        f"{reaction.key} is only {share:.1%} {element.key}: "
                        "the ramp is not reaching that end of its pair")

    def test_every_reaction_strip_has_a_colour_at_all(self):
        for reaction in REACTIONS:
            with self.subTest(reaction=reaction.key):
                self.assertIsNotNone(
                    mean_hue(f"assets/effects/reactions/{reaction.key}.png"))


if __name__ == "__main__":
    unittest.main()
