"""Every screen, in English and Spanish, at 1600x900 and at the web
profile's 1280x720: no text leaves the screen or the panel it was drawn
on, no text sits on another, none is rendered and lost, and Spanish trims
no more than English (UI-014.11).

`fit_scenes.SCENES` draws each screen with the wordiest data a run can
show; `fit_harness.record` follows every text through the surfaces it was
composed on to where its ink lands.

* **1600x900** is the design size: every scene, both languages, nothing
  cut, nothing overlapping another text, nothing running over the edge of
  a button, card or ribbon.
* **1280x720** is the web profile, held to the same rule, with one
  exemption: `WEB_UNFIT` names the screens whose layout was drawn for 900
  rows and runs off a 720 surface in English too, and the row their
  900-row part starts at (the end screens' buttons, the menu's lower
  buttons). A problem at or below that row, in either language, is the
  web build's layout -- a task of its own (UI-014.D20) -- and is exempt
  as long as Spanish has no more of them there than English; everything
  above it is held to the 1600 rule.
* **Lost:** a string rendered while a screen drew and never placed on it
  -- composed through something the harness cannot follow -- fails, so a
  screen cannot pass by losing its text.
* **Trims:** a text ending in "..." is a trim. Generated item names
  ("[C] Cota de malla serena") are trimmed at the row size in both
  languages by design (`RunSummaryPanel._line`), and their lengths are
  the affixes', so they are not counted; Spanish may make no more of
  the other trims than English does on the same screen (a count, not a
  pairing: "Recar..." and "Cooldo..." on one screen are even).

`WEB_UNFIT` cannot go stale: a listed screen that fits in English fails.
"""
import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import locale
from tests.screens import fit_harness as H
from tests.screens import fit_scenes
from tests.screens.fit_scenes import SCENES, SIZES

DESIGN, WEB = SIZES
ITEM = re.compile(r"^\[[A-Z]\] ")
# scene -> (the y a 900-row layout's part below 720 starts at, why).
WEB_UNFIT = {
    "menu": (620, "the lower buttons (from y 629) and the summary pinned under them meet"),
    **{f"hero_select{v}_{i}": (740, "Begin and the instructions sit below 720")
       for i in range(3) for v in ("", "_unlocked")},
    **{name: (660, "the lower rows sit below 720 and meet the hint line")
       for name in ("options", "options_in_run", "options_borderless", "options_custom")},
    "game_over": (780, "the end screen's buttons and hint sit below 720"),
    "victory": (780, "the end screen's buttons and hint sit below 720"),
}

_RECORDS = {}
_TRACKING = H.tracking()


def setUpModule():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()
    _TRACKING.__enter__()
    fit_scenes.booted()             # boot outside any record: its own text is not a scene's


def tearDownModule():
    _TRACKING.__exit__(None, None, None)


def recorded(name, size, lang):
    """`(placed, rendered)` of a scene, once per module."""
    key = (name, size, lang)
    if key not in _RECORDS:
        was = locale.language()
        locale.set_language(lang)
        try:
            _RECORDS[key] = H.record(SCENES[name], size)
        finally:
            locale.set_language(was)
    return _RECORDS[key]


def problems(placed, size):
    """`[(y, description)]` for one drawn screen: texts cut or off it, on
    another text, or over the edge of a button, card or ribbon."""
    screen = pygame.Rect((0, 0), size)
    out = [(p.rect.y, f"cut {p.text!r} at {tuple(p.rect)}") for p in placed
           if p.cut or not screen.contains(p.rect)]
    out += [(max(a.rect.y, b.rect.y), f"overlap {a.text!r} on {b.text!r} at "
             f"{tuple(a.rect.clip(b.rect))}") for a, b in H.overlaps(placed)]
    out += [(p.rect.y, f"crossing {p.text!r} at {tuple(p.rect)} over the art at "
             f"{tuple(f.rect)}" + (f" labelled {f.label!r}" if f.label else ""))
            for p, f in H.crossing(placed)]
    return out


def web_held(name, found):
    """The problems at 1280 that count: all of them, but for a `WEB_UNFIT`
    screen those at or below its 900-row part's first row."""
    if name not in WEB_UNFIT:
        return found
    below = WEB_UNFIT[name][0]
    return [(y, d) for y, d in found if y < below]


def web_exempt(name, found):
    """The problems `web_held` lets go: at or below the listed row."""
    held = web_held(name, found)
    return [f for f in found if f not in held]


def spanish_adds_below(name, en_found, es_found):
    """Spanish's problems below a `WEB_UNFIT` row when it has more there than
    English, or [] -- the D20 rule, as the test and its self-test read it."""
    en, es = web_exempt(name, en_found), web_exempt(name, es_found)
    return [d for _y, d in es] if len(es) > len(en) else []


def spanish_trims_more(en_placed, es_placed):
    """Spanish's trims past English's on one screen (item names aside), or
    [] -- the trim rule, as the test and its self-test both read it."""
    en, es = trims(en_placed), trims(es_placed)
    return es if len(es) > len(en) else []


def trims(placed):
    return [t for t in H.trimmed(placed) if not ITEM.match(t)]


class FitTests(unittest.TestCase):
    def test_every_screen_fits_at_the_design_size(self):
        bad = []
        for name in SCENES:
            for lang in ("en", "es"):
                bad += [f"{name} {lang}: {d}"
                        for _y, d in problems(recorded(name, DESIGN, lang)[0], DESIGN)]
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_every_screen_fits_the_web_profile_above_its_900_row_part(self):
        bad = []
        for name in SCENES:
            found = {lang: problems(recorded(name, WEB, lang)[0], WEB) for lang in ("en", "es")}
            for lang in ("en", "es"):
                bad += [f"{name} {lang}: {d}" for _y, d in web_held(name, found[lang])]
            added = spanish_adds_below(name, found["en"], found["es"])
            if added:
                bad.append(f"{name}: Spanish adds problems below its row: {added}")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_every_listed_web_misfit_is_still_one_in_english(self):
        """Each `WEB_UNFIT` screen still has an English problem below its
        row: once the web layout is fixed, the exemption goes."""
        fits = [name for name in WEB_UNFIT
                if not web_exempt(name, problems(recorded(name, WEB, "en")[0], WEB))]
        self.assertEqual(fits, [], "fits at 1280 now: drop it from WEB_UNFIT")

    def test_no_text_is_rendered_and_lost(self):
        bad = []
        for name in SCENES:
            for size in SIZES:
                for lang in ("en", "es"):
                    lost = H.lost(*recorded(name, size, lang))
                    bad += [f"{name} {size[0]} {lang}: {t!r}" for t in lost]
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_spanish_trims_no_more_than_english(self):
        bad = []
        for name in SCENES:
            for size in SIZES:
                more = spanish_trims_more(recorded(name, size, "en")[0],
                                          recorded(name, size, "es")[0])
                if more:
                    bad.append(f"{name} {size[0]}: Spanish trims {more}")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_every_scene_draws_text_and_its_spanish(self):
        """Not vacuous: each screen puts text down, and a screen with words
        in English shows different ones in Spanish -- the scene is drawn in
        the language asked for."""
        for name in SCENES:
            en = {p.text for p in recorded(name, DESIGN, "en")[0]}
            es = {p.text for p in recorded(name, DESIGN, "es")[0]}
            with self.subTest(name):
                self.assertTrue(es)
                self.assertTrue(en)
                if any(re.search(r"[A-Za-z]{3,}", t) for t in en):
                    self.assertNotEqual(en, es)

    def test_the_boss_bar_names_the_boss(self):
        for lang in ("en", "es"):
            locale.set_language(lang)
            try:
                name = fit_scenes.boss_name()
            finally:
                locale.set_language(locale.DEFAULT)
            for size in SIZES:
                with self.subTest(lang=lang, size=size):
                    self.assertIn(name, {p.text for p in recorded("hud_boss", size, lang)[0]})


class HarnessTests(unittest.TestCase):
    """The checks see what they claim to."""

    def setUp(self):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def test_a_text_off_the_screen_and_one_on_another_are_caught(self):
        from game import fonts

        def draw(surface):
            f = fonts.body(20)
            surface.blit(f.render("Pausa", True, (255, 255, 255)), (1590, 10))
            surface.blit(f.render("Opciones", True, (255, 255, 255)), (100, 100))
            surface.blit(f.render("Volver", True, (255, 255, 255)), (110, 102))
        placed, _ = H.record(draw, DESIGN)
        found = [d for _y, d in problems(placed, DESIGN)]
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].startswith("cut 'Pausa'"))
        self.assertIn("overlap 'Opciones' on 'Volver'", found[1])

    def test_text_is_followed_through_a_panel_and_its_copy_and_cut_by_it(self):
        """A card composed on its own surface, and a copy of it: the text
        lands where the card does, and a text wider than the card is marked
        cut though the screen has room."""
        from game import fonts

        def draw(surface):
            f = fonts.body(20)
            card = pygame.Surface((80, 40), pygame.SRCALPHA)
            card.blit(f.render("Hi", True, (255, 255, 255)), (5, 5))
            card.blit(f.render("Ataque automático", True, (255, 255, 255)), (5, 20))
            surface.blit(card.copy(), (300, 200))
        placed, rendered = H.record(draw, DESIGN)
        by = {p.text: p for p in placed}
        self.assertEqual(set(by), {"Hi", "Ataque automático"})
        self.assertGreaterEqual(by["Hi"].rect.x, 305)
        self.assertFalse(by["Hi"].cut)
        self.assertTrue(by["Ataque automático"].cut)
        self.assertEqual(H.lost(placed, rendered), [])

    def test_a_shadow_is_one_text_but_two_rows_of_it_overlap(self):
        from game import fonts
        from ui.text import shadowed

        def draw(surface):
            f = fonts.body(20)
            surface.blit(shadowed(f, "Victoria", (255, 200, 0)), (10, 10))
            surface.blit(f.render("Nv. 3", True, (255, 255, 255)), (10, 100))
            surface.blit(f.render("Nv. 3", True, (255, 255, 255)), (10, 110))
        placed, _ = H.record(draw, DESIGN)
        over = H.overlaps(placed)
        self.assertEqual([(a.text, b.text) for a, b in over], [("Nv. 3", "Nv. 3")])

    def test_a_font_kept_from_before_reports_to_the_record_running_now(self):
        """The run keeps its fonts for its whole life; each window sees what
        they draw then, not the first window only."""
        from game import fonts
        with H.tracking():
            kept = fonts.body(20)
            for word in ("uno", "dos"):
                placed, _ = H.record(lambda s: s.blit(kept.render(word, True, (1, 1, 1)),
                                                      (10, 10)), DESIGN)
                self.assertEqual([p.text for p in placed], [word])

    def test_a_scaled_text_is_followed_and_a_converted_one_is_lost(self):
        from game import fonts

        def draw(surface):
            f = fonts.body(20)
            surface.blit(pygame.transform.smoothscale_by(f.render("Grande", True, (1, 1, 1)), 2),
                         (10, 10))
            surface.blit(f.render("Perdido", True, (1, 1, 1)).convert_alpha(), (10, 100))
        placed, rendered = H.record(draw, DESIGN)
        self.assertEqual([p.text for p in placed], ["Grande"])
        self.assertEqual(H.lost(placed, rendered), ["Perdido"])

    def test_a_blit_of_part_of_a_panel_shifts_and_cuts_its_text(self):
        """`blit(src, dest, area)`: a text inside the area lands at `dest`
        less the area's corner; one past the area's edge is cut."""
        from game import fonts

        def draw(surface):
            f = fonts.body(20)
            panel = pygame.Surface((300, 100), pygame.SRCALPHA)
            panel.blit(f.render("Dentro", True, (1, 1, 1)), (60, 10))
            panel.blit(f.render("Fuera", True, (1, 1, 1)), (180, 10))
            surface.blit(panel, (500, 400), pygame.Rect(50, 0, 150, 100))
        placed, _ = H.record(draw, DESIGN)
        by = {p.text: p for p in placed}
        self.assertLess(abs(by["Dentro"].rect.x - 510), 4)      # 500 + 60 - 50, less the side bearing
        self.assertFalse(by["Dentro"].cut)
        self.assertTrue(by["Fuera"].cut)

    def test_the_web_exemption_is_only_below_its_row(self):
        found = [(100, "cut 'Total'"), (779, "overlap"), (780, "cut 'Nuevo'"), (868, "cut")]
        self.assertEqual(web_held("victory", found), [(100, "cut 'Total'"), (779, "overlap")])
        self.assertEqual(web_held("paused", found), found)

    def test_text_over_the_edge_of_a_button_is_caught(self):
        from game import fonts
        from ui import widgets

        def draw(surface):
            f = fonts.body(20)
            card = pygame.Rect(100, 100, 200, 60)
            widgets.draw_button(surface, None, card, None, shape="panel")
            surface.blit(f.render("Dentro", True, (1, 1, 1)), (120, 110))
            surface.blit(f.render("Arma principal", True, (1, 1, 1)), (150, 150))
        placed, _ = H.record(draw, DESIGN)
        self.assertEqual([p.text for p, _f in H.crossing(placed)], ["Arma principal"])

    def test_spanish_may_trim_as_often_as_english_and_no_more(self):
        def at(*texts):
            return [H.Placed(t, pygame.Rect(0, 0, 1, 1), False) for t in texts]
        self.assertEqual(spanish_trims_more(at("Gold ea..."), at("Oro ga...")), [])
        self.assertEqual(spanish_trims_more(at("Gold"), at("Oro ga...")), ["Oro ga..."])
        self.assertEqual(spanish_trims_more(at(), at("[C] Cota de...")), [])

    def test_a_frame_drawn_on_a_panel_is_carried_with_it(self):
        """A card drawn on a panel, then the panel on the screen: a text
        running over the card's edge is caught at the panel's offset."""
        from game import fonts
        from ui import widgets

        def draw(surface):
            f = fonts.body(20)
            panel = pygame.Surface((400, 200), pygame.SRCALPHA)
            widgets.draw_button(panel, None, pygame.Rect(10, 10, 150, 60), None, shape="panel")
            panel.blit(f.render("Ataque automático", True, (1, 1, 1)), (60, 20))
            surface.blit(panel, (300, 300))
        placed, _ = H.record(draw, DESIGN)
        ((p, frame),) = H.crossing(placed)
        self.assertEqual(p.text, "Ataque automático")
        self.assertEqual(tuple(frame.rect), (310, 310, 150, 60))

    def test_problems_reports_text_over_the_art(self):
        """`problems`, which every fit test reads, includes the crossing
        check, not only the harness."""
        from game import fonts
        from ui import widgets

        def draw(surface):
            widgets.draw_button(surface, None, pygame.Rect(100, 100, 120, 40), None,
                                shape="panel")
            surface.blit(fonts.body(20).render("Ataque automático", True, (1, 1, 1)),
                         (110, 110))
        placed, _ = H.record(draw, DESIGN)
        self.assertEqual([d.split(" at ")[0] for _y, d in problems(placed, DESIGN)],
                         ["crossing 'Ataque automático'"])

    def test_a_text_on_a_labelled_button_is_caught_even_inside_it(self):
        from game import fonts
        from ui import widgets

        def draw(surface):
            f = fonts.body(20)
            widgets.draw_button(surface, None, pygame.Rect(100, 100, 400, 60), "Opciones",
                                font=f)
            surface.blit(f.render("Chatarra 5", True, (1, 1, 1)), (120, 130))
        placed, _ = H.record(draw, DESIGN)
        self.assertEqual([p.text for p, _f in H.crossing(placed)], ["Chatarra 5"])

    def test_below_the_row_spanish_may_not_add_problems(self):
        en = [(800, "cut 'New run'")]
        es = [(800, "cut 'Nueva partida'"), (805, "overlap")]
        self.assertEqual(web_exempt("victory", en), en)
        self.assertEqual(len(web_exempt("victory", es)), 2)
        self.assertEqual(web_exempt("paused", es), [])
        self.assertEqual(spanish_adds_below("victory", en, en), [])
        self.assertEqual(spanish_adds_below("victory", en, es), ["cut 'Nueva partida'", "overlap"])
        self.assertEqual(spanish_adds_below("victory", es, en), [])
        self.assertEqual(spanish_adds_below("victory", en, [(100, "above")]), [])   # held apart

    def test_item_names_are_the_one_trim_left_out(self):
        self.assertEqual(trims([H.Placed("[C] Cota de...", pygame.Rect(0, 0, 1, 1), False),
                                H.Placed("Vel. mov...", pygame.Rect(0, 0, 1, 1), False)]),
                         ["Vel. mov..."])


if __name__ == "__main__":
    unittest.main()
