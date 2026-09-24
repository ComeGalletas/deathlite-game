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


def _coloured_pixels(path: str, step: int = 1) -> list:
    """The pixels of `path` that state a hue, as (hue, saturation).

    `step` samples every nth pixel in each axis. The melee strips are small
    enough to read whole; the recoloured sheets are up to 1920 x 192 and
    there are twenty-four of them, and this is a `get_at` per pixel. A hue
    mean over a ninth of a sheet is the same hue.
    """
    surface = pygame.image.load(path).convert_alpha()
    out = []
    for y in range(0, surface.get_height(), step):
        for x in range(0, surface.get_width(), step):
            r, g, b, a = surface.get_at((x, y))
            if a < 200:
                continue
            h, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if sat < _MIN_SAT or light < _MIN_LIGHT or light > _MAX_LIGHT:
                continue
            out.append((h * 360.0, sat))
    return out


def mean_hue(path: str, step: int = 1):
    """The strip's hue, averaged on the circle and weighted by saturation.

    A plain mean is wrong for hue: red at 350 and red at 10 average to
    cyan. Summing unit vectors and taking the angle back is the standard
    fix, and weighting by saturation lets the colours that actually state
    the hue outvote the washed-out ones.
    """
    x = y = 0.0
    for h, sat in _coloured_pixels(path, step):
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


# --- M13: an infused weapon looks infused -------------------------------------

class MeleeVariantTests(unittest.TestCase):
    """The melee attacks are authored once per element, not tinted."""

    MELEE = ("sword_slash", "daggers_slash", "daggers_stab", "hammer_impact")
    VARIANTS = ("plain", "fire", "ice", "thunder", "wind")

    def setUp(self):
        _init()

    def test_every_attack_has_every_variant_and_they_all_load(self):
        from game.assets import get_assets

        assets = get_assets()
        for base in self.MELEE:
            for variant in self.VARIANTS:
                with self.subTest(rig=f"{base}_{variant}"):
                    self.assertGreater(
                        assets.frame_count(f"{base}_{variant}", "loop"), 0)

    def test_each_variant_wears_its_own_element(self):
        """The point of cutting five instead of tinting one: the colour is
        authored, so it has to actually be the element's."""
        from combat.elements.ids import element_from_key

        for base in self.MELEE:
            for key in ("fire", "ice", "thunder", "wind"):
                with self.subTest(rig=f"{base}_{key}"):
                    want = hue_of(declared(element_from_key(key)))
                    got = mean_hue(_melee_path(base, key))
                    self.assertIsNotNone(got)
                    self.assertLessEqual(hue_gap(want, got), HUE_TOLERANCE)

    def test_the_plain_variant_is_not_any_element(self):
        """It has to read as steel. A neutral strip has no hue to speak of,
        so this checks saturation rather than distance from four hues."""
        import colorsys

        for base in self.MELEE:
            with self.subTest(base=base):
                pixels = _coloured_pixels(_melee_path(base, "plain"))
                surface = pygame.image.load(
                    _melee_path(base, "plain")).convert_alpha()
                total = sum(1 for x in range(surface.get_width())
                            for y in range(surface.get_height())
                            if surface.get_at((x, y))[3] > 200)
                self.assertGreater(total, 0)
                self.assertLess(len(pixels) / total, 0.25,
                                "the plain variant is coloured, not steel")


class RecolouredVariantTests(unittest.TestCase):
    """The effects that keep their own art and are recoloured for it.

    The other half of M13 C, and the half that was rebuilt. These were
    first drawn with the enemy `wash` over them, which is a multiply, and a
    multiply cannot turn an orange flame blue -- it can only darken toward
    where two hues overlap. Measured at four strengths, stronger only meant
    muddier. So the sprites are hue-rotated once, offline, by
    `tools/asset_pipeline/recolour_element_variants.py`.

    The guard that matters most here is the last one. The melee variants
    are cut from a pack that is not even in the repo, so they are as fixed
    as any authored art; these are derived from sheets that ship and can be
    replaced any day, and nothing about replacing one would say that four
    more files went stale.
    """

    KEYS = ("fire", "ice", "thunder", "wind")
    # Frame counts and timings must match or an infused summon would play
    # at a different speed from a plain one; the geometry must match or the
    # sprite would jump the moment the weapon was infused.
    SHARED = ("frame", "scale", "anchor", "grid", "content", "fireball")

    def setUp(self):
        _init()

    def infusable(self):
        return {rig: spec for rig, spec in C.sprites.items()
                if spec.get("infused") is not None}

    def test_there_are_infusable_rigs_to_check(self):
        self.assertGreaterEqual(len(self.infusable()), 6)

    def test_every_one_has_four_variants_with_the_base_geometry(self):
        for rig, base in sorted(self.infusable().items()):
            for key in self.KEYS:
                spec = C.sprites.get(f"{rig}_{key}")
                with self.subTest(rig=f"{rig}_{key}"):
                    self.assertIsNotNone(spec)
                    for field in self.SHARED:
                        self.assertEqual(spec.get(field), base.get(field),
                                         f"{field} drifted from {rig}")
                    self.assertEqual(sorted(spec.get("anims", {})),
                                     sorted(base.get("anims", {})))
                    for name, anim in base.get("anims", {}).items():
                        got = spec["anims"][name]
                        self.assertEqual(
                            [got.get(k) for k in ("frames", "fps", "loop", "row")],
                            [anim.get(k) for k in ("frames", "fps", "loop", "row")],
                            f"{rig}.{name} timing drifted")

    def test_every_variant_sheet_loads_and_keeps_the_silhouette(self):
        """A recolour must not touch alpha. If it did, an infused summon
        would have a different outline from a plain one."""
        for rig, base in sorted(self.infusable().items()):
            for name, anim in base.get("anims", {}).items():
                src = pygame.image.load(f"assets/{anim['file']}").convert_alpha()
                for key in self.KEYS:
                    path = f"assets/{C.sprites[f'{rig}_{key}']['anims'][name]['file']}"
                    with self.subTest(sheet=path):
                        got = pygame.image.load(path).convert_alpha()
                        self.assertEqual(got.get_size(), src.get_size())
                        self.assertEqual(
                            [got.get_at((x, y))[3]
                             for x in range(0, got.get_width(), 7)
                             for y in range(0, got.get_height(), 7)],
                            [src.get_at((x, y))[3]
                             for x in range(0, src.get_width(), 7)
                             for y in range(0, src.get_height(), 7)])

    def test_each_variant_wears_its_own_element(self):
        """The same measurement the melee variants get. It is worth more
        here: those colours were drawn by a human and these come out of a
        hue rotation, which has exactly one way to be wrong and no way to
        look wrong in a thumbnail."""
        from combat.elements.ids import element_from_key

        for rig in sorted(self.infusable()):
            for key in self.KEYS:
                spec = C.sprites[f"{rig}_{key}"]
                sheet = next(iter(spec["anims"].values()))["file"]
                with self.subTest(rig=f"{rig}_{key}"):
                    want = hue_of(declared(element_from_key(key)))
                    got = mean_hue(f"assets/{sheet}", step=3)
                    self.assertIsNotNone(got)
                    self.assertLessEqual(hue_gap(want, got), HUE_TOLERANCE)

    def test_the_art_on_disk_is_what_the_tool_would_write_today(self):
        """The one that survives the source art being replaced.

        Every one of these sheets is derived from a sheet that ships and
        can be redrawn, repointed or retuned at any time, and none of that
        would announce that four generated copies had gone stale. The tool
        rebuilds the whole tree in memory and compares, so a changed
        source, a changed `infused` block and a hand-edited variant all
        come out as the same failure: re-run the tool.

        The tool reads the sheets through `pygame.surfarray`, which needs
        numpy. The game does not; the suite does, because derived art keeps
        a `--check` a test runs. A missing numpy is therefore a failure that
        says what to install, not a skip (TST-004.3.9).
        """
        try:
            import numpy                                   # noqa: F401
        except ImportError:
            self.fail("numpy is not installed -- the recolour tool's --check "
                      "needs it (pygame.surfarray): pip install numpy")
        from tools.asset_pipeline import recolour_element_variants as tool

        self.assertEqual(tool.main(["--check"]), 0,
                         "assets/infused is stale -- re-run "
                         "python -m tools.asset_pipeline."
                         "recolour_element_variants")


class VariantResolutionTests(unittest.TestCase):
    """`variant_rig` picks the colour, and refuses to guess."""

    def setUp(self):
        _init()

    def test_it_resolves_a_cut_family(self):
        from combat.elements.ids import ELEMENTS
        from game.assets import get_assets
        from game.states.playing.visual import elements as fx

        assets = get_assets()
        self.assertEqual(fx.variant_rig(assets, "sword_slash", None),
                         "sword_slash_plain")
        for element in ELEMENTS:
            with self.subTest(element=element.key):
                self.assertEqual(fx.variant_rig(assets, "sword_slash", element),
                                 f"sword_slash_{element.key}")

    def test_it_resolves_a_recoloured_family_back_to_the_base(self):
        """A recoloured family has no `_plain`, on purpose: it would be a
        second copy of the sheets the base already owns, and a copy is a
        thing that goes stale. So an uninfused Ember Ring burns the base
        rig itself."""
        from combat.elements.ids import ELEMENTS
        from game.assets import get_assets
        from game.states.playing.visual import elements as fx

        assets = get_assets()
        for base in ("ember", "grave_totem", "spirit_wolf", "explosion", "bomb"):
            with self.subTest(base=base):
                self.assertIsNone(assets.rig(f"{base}_plain"),
                                  "a recoloured family must not grow a copy "
                                  "of its own art")
                self.assertEqual(fx.variant_rig(assets, base, None), base)
                for element in ELEMENTS:
                    self.assertEqual(fx.variant_rig(assets, base, element),
                                     f"{base}_{element.key}")

    def test_it_leaves_a_rig_that_was_never_cut_alone(self):
        """The guard that matters. Guessing `base_<element>` by name
        resolved `totem_bolt` + fire to `totem_bolt_fire`, which is a real
        rig and is the Grave Totem bolt's flame tail -- nothing to do with
        an infusion. A family has to say so in the data -- a `_plain`
        sibling for a replaced family, an `infused` block for a recoloured
        one -- and `totem_bolt` says neither."""
        from combat.elements.ids import ElementId
        from game.assets import get_assets
        from game.states.playing.visual import elements as fx

        assets = get_assets()
        self.assertGreater(assets.frame_count("totem_bolt_fire", "loop"), 0,
                           "the decoy rig this guards against still exists")
        for base in ("totem_bolt", "soul_slash", "arrow", "dust_puff"):
            with self.subTest(base=base):
                self.assertEqual(
                    fx.variant_rig(assets, base, ElementId.FIRE), base)
                self.assertEqual(fx.variant_rig(assets, base, None), base)


class WashTests(unittest.TestCase):
    """The tint a primed enemy wears.

    Its only surface now. M13 briefly put it on the attacks too and the
    measurement sent it back: see `RecolouredVariantTests`.
    """

    def setUp(self):
        _init()
        from game.assets import get_assets
        self.assets = get_assets()
        self.frame = self.assets.frame("thunder_ball", "loop", 3, size=(40, 40))

    def test_no_element_passes_the_frame_straight_through(self):
        from game.states.playing.visual import elements as fx

        self.assertIs(fx.washed(self.frame, None), self.frame)
        self.assertIsNone(fx.washed(None, None))

    def test_an_element_changes_the_frame_and_keeps_its_silhouette(self):
        from combat.elements.ids import ELEMENTS
        from game.states.playing.visual import elements as fx

        def alpha_map(s):
            return [s.get_at((x, y))[3]
                    for x in range(s.get_width()) for y in range(s.get_height())]

        base = alpha_map(self.frame)
        for element in ELEMENTS:
            with self.subTest(element=element.key):
                out = fx.washed(self.frame, element)
                self.assertNotEqual(pygame.image.tobytes(out, "RGBA"),
                                    pygame.image.tobytes(self.frame, "RGBA"))
                self.assertEqual(alpha_map(out), base,
                                 "the wash must not eat the silhouette")

    def test_it_is_cached_per_frame_and_element(self):
        """These are the asset cache's own surfaces: a copy per draw would
        be an allocation per sprite per frame."""
        from combat.elements.ids import ElementId
        from game.states.playing.visual import elements as fx

        first = fx.washed(self.frame, ElementId.FIRE)
        self.assertIs(fx.washed(self.frame, ElementId.FIRE), first)
        self.assertIsNot(fx.washed(self.frame, ElementId.ICE), first)

    def test_its_strength_comes_from_the_data(self):
        """No third copy of an element's colour, and no constant buried in
        a renderer -- the same rule M12 enforced on the dev inspector."""
        from game.states.playing.visual.elements.profiles import get_visuals

        wash = get_visuals(C).wash
        self.assertEqual(wash.lift, C.element_visuals["wash"]["lift"])
        self.assertEqual(wash.alpha, C.element_visuals["wash"]["alpha"])
        self.assertGreater(wash.alpha, 0)
        self.assertLessEqual(wash.alpha, 255)


def _melee_path(base: str, variant: str) -> str:
    weapon, action = base.split("_", 1)
    return f"assets/effects/weapons/{weapon}/{action}_{variant}.png"
