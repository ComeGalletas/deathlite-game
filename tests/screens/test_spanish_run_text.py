"""The run's own text in the locale files (UI-014.8): hints, keycaps, the
Forge and its rail, infusion, damage labels, the end banner and the end
screens.

Two checks for every string:
- **English is byte-identical** to what the code built before the move. The
  old f-strings are kept here, verbatim, as the reference, and compared
  across every input they took (every rarity, element, pace, plural).
- **Spanish is drawn**, and differs from English, so a pass cannot be
  English leaking through.

Unit tier: fakes stand in for weapons and screens. The booted-run half is
`tests/playing/test_spanish_run_notices.py`.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements import tracking
from combat.elements.ids import ELEMENTS, ElementId
from combat.weapons.core import ATTACK_MODE, TIME_MODE
from game import config, fonts, locale
from game.states.playing.core import infusion
from game.states.playing.core.chests import Chests, _rarity_word
from ui import end_screen, keycap, text
from ui.text import wrap
from ui.end_screen import Button, EndScreen
from ui.forge_rail import ForgeRail, rows_for

NB = "\u00a0"                  # the no-break space before a unit


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()


def _both(fn):
    """`fn()` in English, then in Spanish."""
    locale.set_language("en")
    en = fn()
    locale.set_language("es")
    try:
        return en, fn()
    finally:
        locale.set_language(locale.DEFAULT)


class _Weapon:
    def __init__(self, wid, name, levels=0, forge=None, is_summon=False, element=None,
                 mode=ATTACK_MODE, window=1.0, interval=0):
        self.weapon_id, self.name, self.forge = wid, name, forge
        self.is_summon, self._levels = is_summon, levels
        self.element = element or ElementId.NONE
        self.element_mode, self.element_window, self.element_interval = mode, window, interval


def _levels(w):
    return w._levels


# --- the old f-strings, verbatim: English must still build these ----------------

def old_rail_note(w, need, have, name):
    if w.forge is not None:
        return f"already forged into {name}"
    if have >= need:
        return f"{have} / {need} blessings"
    short = need - have
    plural = "" if short == 1 else "s"
    return f"{have} / {need} - needs {short} more blessing{plural}"


def old_pace(weapon):
    if weapon.element_mode == TIME_MODE:
        return f"every {weapon.element_window:.2g}s"
    if weapon.element_interval:
        return f"on 1 attack in {weapon.element_interval + 1}"
    return "on every attack"


def old_describe(weapon, element):
    held = weapon.element
    if held == element:
        return f"Already carries {element.key}. Refreshes it ({old_pace(weapon)})."
    if held != ElementId.NONE:
        return f"Replaces {held.key} with {element.key} ({old_pace(weapon)})."
    return f"Carries {element.key} {old_pace(weapon)}."


OLD_LABELS = {
    "fire_hit": "Fire", "burn": "Burn", "wind_hit": "Wind", "wind_area": "Wind area",
    "thunder_chain": "Thunder chain", "frozen_contact": "Frozen contact",
    "frostburn": "Frostburn", "overload": "Overload",
    "overload_wave": "Overload shockwave", "superconduct": "Superconduct",
    "firewind": "FireWind", "icewind": "IceWind", "thunderwind": "ThunderWind",
    "thunder_strike": "Thunder strike",
}


# --- keycaps -------------------------------------------------------------------

class KeycapTests(unittest.TestCase):
    def test_words_translate_and_legends_do_not(self):
        cases = {pygame.K_SPACE: ("SPACE", "ESPACIO"),
                 pygame.K_LSHIFT: ("SHIFT", "MAYÚS"), pygame.K_RSHIFT: ("SHIFT", "MAYÚS"),
                 pygame.K_BACKSPACE: ("BKSP", "BORRAR"),
                 pygame.K_RETURN: ("ENTER", "ENTER"), pygame.K_TAB: ("TAB", "TAB"),
                 pygame.K_ESCAPE: ("ESC", "ESC"), pygame.K_LCTRL: ("CTRL", "CTRL"),
                 pygame.K_LALT: ("ALT", "ALT"), pygame.K_RALT: ("ALT", "ALT"),
                 pygame.K_UP: ("↑", "↑"),
                 pygame.K_e: ("E", "E"), pygame.K_q: ("Q", "Q")}
        for code, want in cases.items():
            with self.subTest(key=pygame.key.name(code)):
                self.assertEqual(_both(lambda: keycap.label_for(code)), want)

    def test_the_mouse_word_is_translated_when_the_cursor_art_is_missing(self):
        _display()
        seen = []

        class _Font:
            def render(self, label, *a):
                seen.append(label)
                return pygame.Surface((4, 4))

            def size(self, label):
                return (4, 4)
        surface = pygame.Surface((200, 200))
        with mock.patch.object(keycap, "mouse_glyph", return_value=None):
            _both(lambda: keycap.draw_keycap(surface, None, (60, 60), keycap.MOUSE,
                                             font=_Font()))
        self.assertEqual(seen, ["CLICK", "CLIC"])

    def _drawn(self, label):
        """The cap's rect, and every font `fit_font` handed the cap."""
        fitted = []

        def fit(*a, **k):
            fitted.append(keycap_fit(*a, **k))
            return fitted[-1]
        keycap_fit = keycap.fit_font
        with mock.patch.object(keycap, "fit_font", fit):
            rect = keycap.draw_keycap(pygame.Surface((400, 200)), None, (150, 60), label)
        return rect, fitted

    def test_a_word_that_fits_keeps_the_default_size(self):
        _display()
        for label in ("SPACE", "ESPACIO", "MAYÚS", "BORRAR", "TAB", "ESC", "CLICK"):
            with self.subTest(label=label):
                self.assertEqual(self._drawn(label)[1], [])

    def test_a_word_too_long_for_the_cap_steps_down_to_fit(self):
        _display()
        label = "BLOQ MAYUS"
        rect, fitted = self._drawn(label)
        self.assertEqual(len(fitted), 1)
        font = fitted[0]
        room = int(rect.width * keycap.WORD_ROOM)
        default = fonts.body(keycap.WORD_PX, bold=True)
        self.assertGreater(default.size(label)[0], room)       # it would not fit
        self.assertLessEqual(font.size(label)[0], room)          # and now it does
        self.assertEqual(room, int(96 * 0.75))                   # 3 caps of 32, 75 %
        # Wider than the 75 % room but not than the cap itself: still steps.
        mid = "CAPS LOCK"
        self.assertGreater(default.size(mid)[0], room)
        self.assertLess(default.size(mid)[0], rect.width)
        _rect, fitted_mid = self._drawn(mid)
        self.assertEqual(len(fitted_mid), 1)
        self.assertLessEqual(fitted_mid[0].size(mid)[0], room)
        # Longer than even the smallest step: the smallest step, not a crash.
        _rect, fitted = self._drawn("SUPRIMIR TODO")
        floor = round(keycap.WORD_PX * 0.7)
        self.assertEqual(fitted[0].get_height(), fonts.body(floor, bold=True).get_height())
        self.assertTrue(font.get_bold() and fitted[0].get_bold())   # bold, like the caps

    def test_a_callers_own_font_is_never_replaced(self):
        _display()
        big = fonts.body(40, bold=True)                   # far too big for the cap
        seen = []

        class _Font:
            def render(self, label, *a):
                seen.append(label)
                return big.render(label, *a)

            def size(self, label):
                return big.size(label)
        with mock.patch.object(keycap, "fit_font") as fit:
            keycap.draw_keycap(pygame.Surface((400, 200)), None, (150, 60),
                               "SUPRIMIR TODO", font=_Font())
        fit.assert_not_called()
        self.assertEqual(seen, ["SUPRIMIR TODO"])

    def test_the_default_cap_font_is_bold(self):
        _display()
        for label, px in (("E", keycap.LABEL_PX), ("TAB", keycap.WORD_PX)):
            with mock.patch.object(keycap.fonts, "body", wraps=keycap.fonts.body) as body:
                keycap.draw_keycap(pygame.Surface((400, 200)), None, (150, 60), label)
            body.assert_called_once_with(px, bold=True)

    def test_a_square_cap_is_never_fitted(self):
        _display()
        with mock.patch.object(keycap, "fit_font") as fit:
            keycap.draw_keycap(pygame.Surface((400, 200)), None, (150, 60),
                               "SUPRIMIR TODO", wide=False)
        fit.assert_not_called()

    def test_the_default_word_size_is_unchanged_for_english(self):
        """The fitted font is only ever asked for on overflow, so every English
        word renders in exactly the font it always did."""
        _display()
        default = fonts.body(keycap.WORD_PX, bold=True)
        for label in ("SPACE", "SHIFT", "BKSP", "ENTER", "CTRL", "CLICK", "TAB", "ESC"):
            self.assertLessEqual(default.size(label)[0], int(96 * keycap.WORD_ROOM), label)


# --- the fit cache survives pygame.quit ------------------------------------------

class FitCacheTests(unittest.TestCase):
    def test_a_quit_and_init_cycle_drops_the_cached_fonts(self):
        """Regression (UI-014.8): a Font cached before `pygame.quit()` and
        used after `pygame.init()` is an access violation. The keycaps made
        `fit_font` run from the pause menu's Controls block, and the suite
        crashed in `test_pause` the first time it did."""
        pygame.init()
        _display()
        text.fit_font(fonts.body, 20, "WWWWWWWWWWWWWWWWWWWW", 10)
        self.assertTrue(text._FIT_CACHE)
        pygame.quit()
        self.assertEqual(text._FIT_CACHE, {})
        pygame.init()
        _display()
        font = text.fit_font(fonts.body, 20, "WWWWWWWWWWWWWWWWWWWW", 10)
        self.assertGreater(font.size("W")[0], 0)                # usable, not stale
        self.assertTrue(text._FIT_CACHE)                         # and cached again
        pygame.quit()
        self.assertEqual(text._FIT_CACHE, {})                    # the hook was re-armed
        pygame.init()


    def test_the_quit_hook_is_registered_once_per_cycle(self):
        pygame.init()
        _display()
        text._forget_fonts()                      # a clean cycle
        try:
            with mock.patch.object(pygame, "register_quit") as hook:
                for px in (12, 13, 14, 12, 13):
                    text.cached_font(fonts.body, px)
            self.assertEqual(hook.call_count, 1)
        finally:
            text._forget_fonts()                  # the patched hook never ran: re-arm

    def test_the_cache_is_keyed_by_render_scale(self):
        from game import config
        pygame.init()
        _display()
        one = text.cached_font(fonts.body, 14)
        self.assertIs(text.cached_font(fonts.body, 14), one)
        with mock.patch.object(config, "RENDER_SCALE", config.RENDER_SCALE * 2):
            two = text.cached_font(fonts.body, 14)
        self.assertIsNot(two, one)
        self.assertGreater(two.get_height(), one.get_height())


# --- chests --------------------------------------------------------------------

class ChestTextTests(unittest.TestCase):
    def test_the_list_joins_like_the_old_code(self):
        def old(parts):
            if len(parts) == 1:
                return parts[0]
            return ", ".join(parts[:-1]) + " and " + parts[-1]
        for parts in (["a"], ["a", "b"], ["a", "b", "c"], ["1 gold", "x", "y", "z"]):
            en, es = _both(lambda: Chests._listed(parts))
            self.assertEqual(en, old(parts))
            self.assertEqual(es, old(parts).replace(" and ", " y "))

    def test_spanish_joins_an_i_sound_with_e(self):
        # "e" only when the /i/ opens the last item; a vowel after it (each
        # one the rule lists) makes a diphthong and keeps "y".
        cases = {"Imán II": "e", "Impacto pesado II": "e", "Hilo de oro": "e",
                 "ímpetu": "e", "Ira": "e",
                 "Hielo": "y", "Hierro": "y", "hiato": "y", "Hioides": "y",
                 "Iodo": "y", "hiárea": "y", "hiélago": "y", "hióptero": "y",
                 "Hiuro": "y", "iúrico": "y",
                 "Hoja pesada": "y", "Viento": "y",
                 "Hojas afiladas II": "y", "Espada ligera": "y"}   # an "i" later on
        for last, word in cases.items():
            with self.subTest(last=last):
                en, es = _both(lambda: Chests._listed(["40 de oro", "una poción", last]))
                self.assertEqual(en, f"40 de oro, una poción and {last}")
                self.assertEqual(es, f"40 de oro, una poción {word} {last}")

    def test_the_rarity_words_agree_with_their_noun(self):
        self.assertEqual(_both(lambda: _rarity_word("chest", "rare")), ("Rare", "raro"))
        self.assertEqual(_both(lambda: _rarity_word("potion", "rare")), ("rare", "rara"))
        for r in ("common", "uncommon", "rare", "epic"):
            self.assertEqual(_both(lambda: _rarity_word("chest", r))[0], r.capitalize())
        for r in ("common", "uncommon", "rare"):
            self.assertEqual(_both(lambda: _rarity_word("potion", r))[0], r)
        self.assertEqual([_both(lambda: _rarity_word("chest", r))[1]
                          for r in ("common", "uncommon", "rare", "epic")],
                         ["común", "poco común", "raro", "épico"])
        self.assertEqual([_both(lambda: _rarity_word("potion", r))[1]
                          for r in ("common", "uncommon", "rare")],
                         ["común", "poco común", "rara"])

    def test_every_rarity_in_the_data_has_a_word(self):
        from game.content import Content
        C = Content()
        for kind, table in (("chest", C.chests), ("potion", C.potions)):
            for r in table["rarities"]:
                with self.subTest(kind=kind, rarity=r):
                    self.assertTrue(locale.has(f"{kind}.rarity.{r}"))

    def test_an_unknown_rarity_shows_its_id(self):
        self.assertEqual(_both(lambda: _rarity_word("chest", "mythic")), ("Mythic", "Mythic"))
        self.assertEqual(_both(lambda: _rarity_word("potion", "mythic")), ("mythic", "mythic"))

    def test_the_notice_templates(self):
        def build():
            parts = [locale.t("chest.gold", n=12),
                     locale.t("chest.potion", rarity=_rarity_word("potion", "rare")),
                     "Heavy Blade"]
            return locale.t("chest.notice", contents=Chests._listed(parts),
                            rarity=_rarity_word("chest", "epic"))
        self.assertEqual(_both(build),
                         ("Epic chest: 12 gold, a rare potion and Heavy Blade.",
                          "Cofre épico: 12 de oro, una poción rara y Heavy Blade."))


# --- the Forge's rail ------------------------------------------------------------

class ForgeRailTests(unittest.TestCase):
    WEAPONS = [_Weapon("sword", "Sword", levels=4), _Weapon("bow", "Bow", levels=3),
               _Weapon("hammer", "Hammer", levels=1), _Weapon("daggers", "Daggers", levels=0),
               _Weapon("magic_rod", "Magic Rod", levels=9, forge="arcanist"),
               _Weapon("ember_ring", "Ember Ring", is_summon=True)]

    def test_english_notes_are_the_old_ones(self):
        for need in (1, 2, 4):
            rows = rows_for(self.WEAPONS, need, _levels, forged_name=lambda w: "Arcanist")
            want = [old_rail_note(w, need, w._levels, "Arcanist")
                    for w in self.WEAPONS if not w.is_summon]
            self.assertEqual([r[2] for r in rows], want)

    def test_spanish_notes(self):
        locale.set_language("es")
        rows = rows_for(self.WEAPONS, 4, _levels, forged_name=lambda w: "Arcanista")
        self.assertEqual([r[2] for r in rows], [
            "4 / 4 bendiciones",
            "3 / 4 - falta 1 bendición",
            "1 / 4 - faltan 3 bendiciones",
            "0 / 4 - faltan 4 bendiciones",
            "ya tiene forja: Arcanista"])

    def test_the_heading_is_read_when_drawn(self):
        _display()
        seen = []
        real = ForgeRail._fit

        def fit(font, role, px, s, room):
            chosen = real(font, role, px, s, room)
            seen.append(s)
            return chosen
        rail = ForgeRail()
        rows = rows_for(self.WEAPONS[:1], 4, _levels)
        with mock.patch.object(ForgeRail, "_fit", staticmethod(fit)):
            for lang in ("en", "es"):
                locale.set_language(lang)
                rail.draw(pygame.Surface((800, 600)), rows, 0, right=400, top=100)
                rail.draw(pygame.Surface((800, 600)), rows, 0, right=400, top=100,
                          heading=infusion.RAIL_HEADING)
        self.assertEqual([s for s in seen if s.isupper() or s.startswith("¿")],
                         ["REFORGE WHICH WEAPON", "INFUSE WITH WHICH ELEMENT",
                          "¿QUÉ ARMA REFORJAR?", "¿CON QUÉ ELEMENTO INFUNDIR?"])

    def drawn(self, rows, heading=None):
        """`{text: (font, drawn width)}` for everything the rail drew, and
        the rail's width and row room in native px."""
        from ui import scale
        from ui.forge_rail import WIDTH, _PAD_X
        chose, fonts_for = {}, {}
        real_fit, real_render = ForgeRail._fit, ForgeRail._render

        def fit(font, role, px, s, room):
            fonts_for[s] = real_fit(font, role, px, s, room)
            return fonts_for[s]

        def render(this, font, role, px, s, room, colour):
            out = real_render(this, font, role, px, s, room, colour)
            chose[s] = (fonts_for[s], out.get_width())
            return out
        rail = ForgeRail()
        kw = {} if heading is None else {"heading": heading}
        with (mock.patch.object(ForgeRail, "_fit", staticmethod(fit)),
              mock.patch.object(ForgeRail, "_render", render)):
            rail.draw(pygame.Surface((800, 600)), rows, 0, right=400, top=100, **kw)
        width = scale.px(WIDTH)
        return rail, chose, width, width - 2 * scale.px(_PAD_X)

    def test_a_row_too_long_for_the_rail_steps_down(self):
        _display()
        name = "Anillo de brasas del sepulcro"           # fits a few steps down
        note = "en Espada, Arco, Vara mágica, Martillo"   # the same
        rows = [(SimpleNamespace(name=name), True, note),
                (SimpleNamespace(name="Espada"), False, "sin portar")]
        rail, chose, _width, room = self.drawn(rows)
        for s, own in ((name, rail._name), (note, rail._note)):
            with self.subTest(text=s):
                font, drawn = chose[s]
                self.assertGreater(own.size(s)[0], room)          # it would not fit
                self.assertLess(font.get_height(), own.get_height())
                self.assertEqual(drawn, font.size(s)[0])          # whole, not trimmed
                self.assertLessEqual(drawn, room)
        self.assertIs(chose["sin portar"][0], rail._note)        # a short one keeps the font
        self.assertIs(chose["Espada"][0], rail._name)
        # Each stepped in its own face: the note in the body face, the name
        # in the heading face (a probe measures the same only in its role).
        probe = "Wim Espada, 0123"
        for s, role, px in ((note, fonts.body, 15), (name, fonts.heading, 20)):
            font = chose[s][0]
            self.assertTrue(any(role(k).size(probe) == font.size(probe)
                                for k in range(round(px * 0.7), px)), s)

    def test_the_rail_fonts_are_their_full_sizes(self):
        _display()
        rail = ForgeRail()
        probe = "Wim Espada, 0123"
        for font, want in ((rail._name, fonts.heading(20)), (rail._note, fonts.body(15)),
                           (rail._head, fonts.body(16))):
            self.assertEqual(font.size(probe), want.size(probe))

    def test_english_rows_draw_exactly_as_before(self):
        """A row and a heading that fit are the plain antialiased render of
        the rail's own font, in the row's colour."""
        from game import config
        _display()
        drawn = []
        real = ForgeRail._render

        def render(this, font, role, px, s, room, colour):
            out = real(this, font, role, px, s, room, colour)
            drawn.append((font, s, colour, out))
            return out
        rows = [(SimpleNamespace(name="Sword"), True, "2 / 2 blessings"),
                (SimpleNamespace(name="Bow"), False, "0 / 2 - needs 2 more blessings")]
        rail = ForgeRail()
        with mock.patch.object(ForgeRail, "_render", render):
            rail.draw(pygame.Surface((800, 600)), rows, 0, right=400, top=100)
        want = [(rail._head, "REFORGE WHICH WEAPON", config.COLOR_TEXT_DIM),
                (rail._name, "Sword", config.COLOR_ON_BUTTON),
                (rail._note, "2 / 2 blessings", config.COLOR_ON_BUTTON_DIM),
                (rail._name, "Bow", config.COLOR_TEXT_DIM),
                (rail._note, "0 / 2 - needs 2 more blessings", config.COLOR_TEXT_DIM)]
        self.assertEqual([d[:3] for d in drawn], want)
        for font, s, colour, out in drawn:
            plain = font.render(s, True, colour)
            self.assertEqual(pygame.image.tostring(out, "RGBA"),
                             pygame.image.tostring(plain, "RGBA"), s)

    def test_the_row_room_is_the_rail_less_its_padding(self):
        """Through `draw`: a note one pixel inside the room keeps the note
        font, one pixel over steps down."""
        from ui import scale
        from ui.forge_rail import WIDTH, _PAD_X
        _display()
        rail = ForgeRail()
        room = scale.px(WIDTH) - 2 * scale.px(_PAD_X)
        s = "m"
        while rail._note.size(s + "m")[0] <= room:
            s += "m"
        over = s + "m"
        self.assertLessEqual(rail._note.size(s)[0], room)
        self.assertGreater(rail._note.size(over)[0], room)
        rows = [(SimpleNamespace(name="A"), True, s), (SimpleNamespace(name="B"), True, over)]
        drawn_rail, chose, _width, _room = self.drawn(rows)
        self.assertIs(chose[s][0], drawn_rail._note)                    # the note font
        self.assertLess(chose[over][0].get_height(), drawn_rail._note.get_height())

    def test_draw_fits_and_trims_to_the_exact_room(self):
        """Through `draw`: a row's text is fitted and trimmed to the rail less
        its padding, the heading to the whole rail, to the pixel."""
        from ui import forge_rail, scale
        from ui.forge_rail import WIDTH, _PAD_X
        _display()
        width = scale.px(WIDTH)
        room = width - 2 * scale.px(_PAD_X)
        name = "Anillo de brasas del sepulcro"
        note = "en Espada, Arco, Vara mágica, Anillo de brasas, Tótem sepulcral"
        locale.set_language("es")
        heading = "¿CON QUÉ ELEMENTO INFUNDIR?"
        with (mock.patch.object(forge_rail, "fit_font", wraps=forge_rail.fit_font) as fit,
              mock.patch.object(forge_rail, "ellipsize", wraps=forge_rail.ellipsize) as trim):
            ForgeRail().draw(pygame.Surface((800, 600)),
                             [(SimpleNamespace(name=name), True, note)], 0,
                             right=400, top=100, heading=infusion.RAIL_HEADING)
        self.assertEqual({(c.args[2], c.args[3]) for c in fit.call_args_list},
                         {(heading, width), (name, room), (note, room)})
        self.assertEqual({(c.args[1], c.args[2]) for c in trim.call_args_list},
                         {(heading, width), (name, room), (note, room)})

    def test_a_text_exactly_the_room_keeps_the_font(self):
        _display()
        rail = ForgeRail()
        s = "sin portar"
        room = rail._note.size(s)[0]
        self.assertIs(ForgeRail._fit(rail._note, fonts.body, 15, s, room), rail._note)
        self.assertIsNot(ForgeRail._fit(rail._note, fonts.body, 15, s, room - 1), rail._note)

    def test_a_row_too_long_even_stepped_down_is_trimmed(self):
        _display()
        note = "en Espada, Arco, Vara mágica, Anillo de brasas, Tótem sepulcral"
        rail, chose, _width, room = self.drawn([(SimpleNamespace(name="Fuego"), True, note)])
        font, drawn = chose[note]
        self.assertGreater(font.size(note)[0], room)             # smallest step, still over
        self.assertLessEqual(drawn, room)                        # but drawn inside

    def test_the_heading_fits_the_rail_width_not_the_row_room(self):
        _display()
        rows = [(SimpleNamespace(name="Fuego"), True, "sin portar")]
        rail, chose, width, room = self.drawn(rows, heading=infusion.RAIL_HEADING)
        english = "INFUSE WITH WHICH ELEMENT"
        # Wider than a row's room, but it fits the rail: drawn at full size.
        self.assertGreater(rail._head.size(english)[0], room)
        self.assertIs(chose[english][0], rail._head)
        locale.set_language("es")
        rail, chose, width, _room = self.drawn(rows, heading=infusion.RAIL_HEADING)
        spanish = "¿CON QUÉ ELEMENTO INFUNDIR?"
        self.assertGreater(rail._head.size(spanish)[0], width)
        font, drawn = chose[spanish]
        self.assertLess(font.get_height(), rail._head.get_height())
        self.assertEqual(drawn, font.size(spanish)[0])
        self.assertLessEqual(drawn, width)


# --- the cards' descriptions ------------------------------------------------------

class CardDescriptionFitTests(unittest.TestCase):
    """Every blessing and forge description fits the card band, in both
    languages, on the level-up card and the Forge's narrower one. Before
    UI-014.8, 18 Spanish forge cards and two English ones (Whirlwind,
    Minefield) ran into the category line on the narrow card at render scale
    1. At the smallest windows (scale 0.65-0.75) Greatsword overflowed too;
    it steps down the same way. The step-down only ever changes a card that
    was drawing over its category line."""

    def setUp(self):
        _display()
        from ui import level_up as L
        from ui import scale
        self.L, self.panel = L, L.LevelUpPanel()
        self.band = (scale.px(L._CARD_H) - scale.px(L._TAG_UP)
                     - self.panel._hint.get_height() - scale.px(L._DESC_GAP)
                     - scale.px(L._DESC_TOP))
        self.inset = 2 * scale.px(L._CARD_TEXT_INSET)
        self.scale = scale

    def texts(self):
        from combat.weapons.forge import get_forges
        from game.content import Content
        from progression.blessings.catalog import get_catalog
        C = Content()
        out = [b.describe(lv) for b in get_catalog(C).by_id.values()
               for lv in range(1, b.max_level + 1)]
        out += [f"{f.display_description} ({f.display_identity}.)"
                for f in get_forges(C).by_id.values()]
        return out

    def test_every_description_fits_its_band(self):
        stepped = {}
        for lang in ("en", "es"):
            locale.set_language(lang)
            for card_w in (self.L.CARD_W, self.L.CARD_W_NARROW):
                width = self.scale.px(card_w) - self.inset
                for s in self.texts():
                    font, lines, line_h = self.panel.desc_block(s, width, self.band)
                    self.assertLessEqual(len(lines) * line_h, self.band, (lang, card_w, s))
                    if font is not self.panel._desc:
                        stepped[(lang, card_w)] = stepped.get((lang, card_w), 0) + 1
        # The level-up width needs no step in English, and the Forge's does.
        self.assertNotIn(("en", self.L.CARD_W), stepped)
        self.assertIn(("es", self.L.CARD_W_NARROW), stepped)

    def test_a_description_that_fits_keeps_the_panel_font(self):
        width = self.scale.px(self.L.CARD_W) - self.inset
        font, lines, line_h = self.panel.desc_block("Short.", width, self.band)
        self.assertIs(font, self.panel._desc)
        self.assertEqual((lines, line_h), (["Short."], self.scale.px(self.L._DESC_LINE_H)))

    def draw_card(self, description):
        """Draw one narrow card with no art, no tag and no rarity; returns
        what `desc_block` chose, the fonts each line was rendered in, the
        ink rows grouped into lines (scanned over the card's whole height
        below the title), and the band."""
        from game import config
        up = SimpleNamespace(title="X", description=description, tags=(), rarity="")
        chosen, rendered, antialias, widths = [], [], [], []
        real = self.L.LevelUpPanel.desc_block

        class _Spy:
            def __init__(self, font):
                self.font = font

            def render(self, s, *a):
                rendered.append(self.font)
                antialias.append(a[0])
                return self.font.render(s, *a)

        def spy(this, *a):
            widths.append(a[1])
            font, lines, line_h = real(this, *a)
            chosen.append((font, lines, line_h))
            return _Spy(font), lines, line_h
        surface = pygame.Surface((1600, 900))
        with mock.patch.object(self.L.LevelUpPanel, "desc_block", spy):
            self.panel.draw(surface, [up], 0, card_w=self.L.CARD_W_NARROW, assets=None)
        card = self.panel.hits.rect_of(0)
        below_title = card.top + self.scale.px(46) + self.panel._name.get_height()
        ink = tuple(config.COLOR_ON_BUTTON_DIM) + (255,)
        rows = [y for y in range(below_title, card.bottom)
                if any(tuple(surface.get_at((x, y))) == ink
                       for x in range(card.left + 8, card.right - 8))]
        groups = []
        for y in rows:
            if groups and y - groups[-1][-1] <= 2:
                groups[-1].append(y)
            else:
                groups.append([y])
        band_top = card.top + self.scale.px(self.L._DESC_TOP)
        self.assertEqual(widths, [self.scale.px(self.L.CARD_W_NARROW) - self.inset])
        self.assertEqual(set(antialias), {True})
        return chosen[0], rendered, groups, band_top, band_top + self.band

    def test_the_card_draws_a_stepped_description_spaced_and_centred(self):
        text = ("La Espada gira sin pausa: un barrido rápido en círculo completo que "
                "hace mucho menos daño por golpe. Fuerte cuando te rodean, débil "
                "contra un solo objetivo. (Área defensiva.)")
        (font, lines, line_h), rendered, groups, band_top, band_bottom = self.draw_card(text)
        self.assertLess(font.get_height(), self.panel._desc.get_height())
        self.assertEqual(rendered, [font] * len(lines))          # every line, that font
        self.assertEqual(len(groups), len(lines))                # one ink band per line
        tops = [g[0] for g in groups]
        for a, b in zip(tops, tops[1:]):
            self.assertAlmostEqual(b - a, line_h, delta=2)       # the stepped spacing
        self.assertGreaterEqual(groups[0][0], band_top)
        self.assertLessEqual(groups[-1][-1], band_bottom)
        # Centred in the band on the stepped line height: the ink block's
        # middle is within a few px of the band's (1 px, measured).
        self.assertAlmostEqual((tops[0] + groups[-1][-1]) / 2, (band_top + band_bottom) / 2,
                               delta=5)

    # (render scale, forge) -> (font size, lines, line height, band), measured.
    # One step at a time from 17, the line height `px(24 * size / 18)` rounded
    # (not floored), and a block exactly the band's height fits: Whirlwind at
    # scale 1.5 is 6 x 34 = 204.
    PINNED = {(1, "whirlwind"): (16, 5, 21, 136), (1, "minefield"): (17, 5, 23, 136),
              (1.5, "whirlwind"): (17, 6, 34, 204), (1.5, "minefield"): (17, 5, 34, 204),
              (2, "whirlwind"): (17, 6, 45, 273), (2, "minefield"): (17, 5, 45, 273)}

    def test_the_english_forge_cards_that_step_are_pinned(self):
        from combat.weapons.forge import get_forges
        from game import config
        from game.content import Content
        forges = get_forges(Content())
        for (rs, fid), want in self.PINNED.items():
            with self.subTest(scale=rs, forge=fid), \
                    mock.patch.object(config, "RENDER_SCALE", rs):
                L, scale = self.L, self.scale
                panel = L.LevelUpPanel()
                band = (scale.px(L._CARD_H) - scale.px(L._TAG_UP)
                        - panel._hint.get_height() - scale.px(L._DESC_GAP)
                        - scale.px(L._DESC_TOP))
                width = scale.px(L.CARD_W_NARROW) - 2 * scale.px(L._CARD_TEXT_INSET)
                f = forges.get(fid)
                s = f"{f.display_description} ({f.display_identity}.)"
                font, lines, line_h = panel.desc_block(s, width, band)
                size = next(k for k in range(13, 19) if fonts.body(k).size(s) == font.size(s))
                self.assertEqual((size, len(lines), line_h, band), want)
                self.assertEqual(line_h, scale.px(L._DESC_LINE_H * size / L._DESC_PX))

    def test_at_scale_1_english_steps_only_whirlwind_and_minefield(self):
        from combat.weapons.forge import get_forges
        from game.content import Content
        width = self.scale.px(self.L.CARD_W_NARROW) - self.inset
        stepped = {f.id for f in get_forges(Content()).by_id.values()
                   if self.panel.desc_block(f"{f.display_description} "
                                            f"({f.display_identity}.)",
                                            width, self.band)[0] is not self.panel._desc}
        self.assertEqual(stepped, {"whirlwind", "minefield"})

    def test_a_block_exactly_the_band_keeps_the_panel_font(self):
        width = self.scale.px(self.L.CARD_W) - self.inset
        text = "Una línea. " * 12
        lines = wrap(self.panel._desc, text, width)
        exact = len(lines) * self.scale.px(self.L._DESC_LINE_H)
        self.assertIs(self.panel.desc_block(text, width, exact)[0], self.panel._desc)
        self.assertIsNot(self.panel.desc_block(text, width, exact - 1)[0], self.panel._desc)

    def test_a_stepped_card_builds_its_fonts_once(self):
        """The step-down reads `cached_font`: a card drawn every frame builds
        its smaller fonts on the first frame only."""
        from game import fonts as font_roles
        from progression.upgrades import Upgrade
        up = Upgrade(id="x", title="X", description=" ".join(["palabra"] * 40), weight=1.0,
                     apply=lambda p: None, kind="stat", rarity="rare")
        surface = pygame.Surface((1600, 900))
        draw = lambda: self.panel.draw(surface, [up], 0, card_w=self.L.CARD_W_NARROW)
        text._forget_fonts()                            # nothing cached by earlier tests
        with mock.patch.object(font_roles, "_load", wraps=font_roles._load) as load:
            draw()
            first = load.call_count
            draw()
        self.assertGreater(first, 0)                    # it did step down
        self.assertEqual(load.call_count, first)        # and built nothing more

    def test_the_smallest_step_is_the_floor(self):
        width = self.scale.px(self.L.CARD_W_NARROW) - self.inset
        font, lines, line_h = self.panel.desc_block(" ".join(["palabra"] * 200),
                                                    width, self.band)
        floor = fonts.body(self.L._DESC_MIN_PX)
        probe = "Aa Bb palabra 0123"
        self.assertEqual(self.L._DESC_MIN_PX, 13)
        self.assertEqual(font.size(probe), floor.size(probe))
        self.assertEqual(line_h, self.scale.px(24 * 13 / 18))
        self.assertGreater(len(lines) * line_h, self.band)       # too long, even so


# --- infusion --------------------------------------------------------------------

class InfusionTextTests(unittest.TestCase):
    def weapons(self):
        out = []
        for held in (ElementId.NONE,) + tuple(ELEMENTS):
            out += [_Weapon("sword", "Sword", element=held, mode=TIME_MODE, window=w)
                    for w in (0.35, 1.25, 2.0, 12.0, 100.0, 123.4)]
            out += [_Weapon("bow", "Bow", element=held, interval=n) for n in (0, 1, 3)]
        return out

    def test_english_descriptions_are_the_old_ones(self):
        for w in self.weapons():
            for element in ELEMENTS:
                with self.subTest(held=w.element.key, element=element.key,
                                  mode=w.element_mode):
                    self.assertEqual(infusion._describe(w, element), old_describe(w, element))

    def test_spanish_descriptions(self):
        locale.set_language("es")
        fire, ice = ElementId.FIRE, ElementId.ICE
        timed = _Weapon("sword", "Espada", element=ice, mode=TIME_MODE, window=1.25)
        self.assertEqual(infusion._describe(timed, ice),
                         f"Ya porta hielo. Lo renueva (cada 1,2{NB}s).")
        self.assertEqual(infusion._describe(timed, fire),
                         f"Cambia hielo por fuego (cada 1,2{NB}s).")
        counted = _Weapon("bow", "Arco", interval=2)
        self.assertEqual(infusion._describe(counted, fire),
                         "Porta fuego en 1 de cada 3 ataques.")
        self.assertEqual(infusion._describe(_Weapon("bow", "Arco"), fire),
                         "Porta fuego en cada ataque.")

    def test_element_names(self):
        self.assertEqual([_both(lambda: infusion.element_name(e)) for e in ELEMENTS],
                         [("Fire", "Fuego"), ("Ice", "Hielo"), ("Thunder", "Trueno"),
                          ("Wind", "Viento")])
        for e in ELEMENTS:
            self.assertEqual(_both(lambda: infusion.ElementRow(e).name)[0], e.key.title())

    def test_every_weapon_name_lowered_is_its_spaced_id(self):
        """The reforged notice used to print the id, spaced; it now prints the
        base name, lowered, so English stays byte-identical only while the two
        agree. A weapon whose name is not its id would change the notice."""
        from game.content import Content
        for wid, entry in Content().weapons.items():
            if isinstance(entry, dict) and "name" in entry:
                with self.subTest(weapon=wid):
                    self.assertEqual(entry["name"].lower(), wid.replace("_", " "))

    def test_an_element_the_locale_lacks_is_its_id(self):
        tables = {lang: {k: v for k, v in locale._table(lang).items()
                         if k != "element.fire"} for lang in locale.LANGUAGES}
        try:
            locale.load(tables)
            self.assertEqual(_both(lambda: infusion.element_name(ElementId.FIRE)),
                             ("Fire", "Fire"))
        finally:
            locale.load(None)

    def test_the_reforged_weapon_is_named_from_its_base_definition(self):
        from game.states.playing.core.locations import SpecialLocations
        weapons = {"great_axe": {"name": "Great Axe", "name_es": "Gran hacha"},
                   "odd_thing": {}}
        fake = SimpleNamespace(run=SimpleNamespace(content=SimpleNamespace(weapons=weapons)),
                               ps=None)
        name = lambda wid: SpecialLocations._base_name(fake, wid)
        self.assertEqual(_both(lambda: name("great_axe")), ("great axe", "gran hacha"))
        self.assertEqual(_both(lambda: name("odd_thing")), ("odd thing", "odd thing"))
        self.assertEqual(_both(lambda: name("missing_one")), ("missing one", "missing one"))

    def test_the_rail_notes(self):
        player = SimpleNamespace(weapons=[_Weapon("sword", "Sword", element=ElementId.FIRE),
                                          _Weapon("bow", "Bow", element=ElementId.FIRE)])
        en, es = _both(lambda: [r[2] for r in infusion.element_rows(player)])
        self.assertEqual(en, ["on Sword, Bow" if e == ElementId.FIRE else "not carried"
                              for e in ELEMENTS])
        self.assertEqual(es, ["en Sword, Bow" if e == ElementId.FIRE else "sin portar"
                              for e in ELEMENTS])


# --- damage labels ----------------------------------------------------------------

class EffectLabelTests(unittest.TestCase):
    def test_english_is_the_old_table_and_spanish_differs(self):
        self.assertEqual(set(OLD_LABELS), set(tracking.EFFECTS))
        for effect in tracking.EFFECTS:
            en, es = _both(lambda: tracking.label(effect))
            self.assertEqual(en, OLD_LABELS[effect])
            self.assertNotEqual(es, en, effect)

    def test_the_spanish_table(self):
        locale.set_language("es")
        self.assertEqual({e: tracking.label(e) for e in tracking.EFFECTS}, {
            "fire_hit": "Fuego", "burn": "Quemadura", "wind_hit": "Viento",
            "wind_area": "Área de viento", "thunder_chain": "Cadena de trueno",
            "frozen_contact": "Contacto helado", "frostburn": "Quemadura gélida",
            "overload": "Sobretensión", "overload_wave": "Onda de sobretensión",
            "superconduct": "Superconducción", "firewind": "Viento ígneo",
            "icewind": "Viento helado", "thunderwind": "Viento tormentoso",
            "thunder_strike": "Rayo"})

    def test_spanish_labels_are_distinct(self):
        locale.set_language("es")
        labels = [tracking.label(e) for e in tracking.EFFECTS]
        # Fire and Wind are both the element and its hit, as in English.
        self.assertEqual(len(set(labels)), len(set(OLD_LABELS.values())))
        self.assertEqual(tracking.label("overload"), "Sobretensión")

    def test_an_unknown_effect_is_its_id(self):
        self.assertEqual(_both(lambda: tracking.label("acid_rain")), ("Acid Rain", "Acid Rain"))

    def test_a_floating_reaction_word_is_spanish(self):
        """The floating word is `tracking.label(reaction.key)`: every reaction
        key is an effect id with a label."""
        from combat.elements.ids import REACTIONS
        locale.set_language("es")
        for r in REACTIONS:
            self.assertTrue(locale.has(f"effect.{r.key}"), r.key)


# --- the end screens -----------------------------------------------------------------

class EndScreenTests(unittest.TestCase):
    STATS = {"character": "Aegis", "difficulty": "fast", "seed": 35}

    def test_the_buttons_and_the_hint(self):
        from game.states.game_over_state import BUTTONS
        _display()
        seen = {}

        def capture():
            labels, hints = [], []
            screen = EndScreen(dict(self.STATS), title="t", title_colour=(1, 1, 1),
                               backdrop=(0, 0, 0), buttons=BUTTONS, lock=0.0)
            screen._hint_font = _Rec(screen._hint_font, hints)
            real = end_screen.widgets.draw_button

            def button(surface, assets, rect, label, **k):
                labels.append(label)
                return real(surface, assets, rect, label, **k)
            with mock.patch.object(end_screen.widgets, "draw_button", button):
                screen.draw(pygame.Surface((1600, 900)), None)
            return labels, hints
        (en_b, en_h), (es_b, es_h) = _both(capture)
        self.assertEqual(en_b, ["New run", "Sanctuary", "Main menu"])
        self.assertEqual(es_b, ["Nueva partida", "Santuario", "Menú principal"])
        self.assertEqual(en_h, ["ENTER new run   -   S sanctuary   -   ESC main menu"
                                "   -   Left / Right select"])
        self.assertEqual(es_h, ["ENTER: nueva partida   -   S: santuario   -   "
                                "ESC: menú principal   -   Izquierda / Derecha: elegir"])

    def test_the_victory_buttons_match(self):
        from game.states import game_over_state, victory_state
        fields = lambda bs: [(b.bid, b.label, b.hint, b.key) for b in bs]
        self.assertEqual(fields(victory_state.BUTTONS), fields(game_over_state.BUTTONS))
        self.assertEqual(fields(victory_state.BUTTONS), [
            ("new_run", "end.new_run", "ENTER", None),
            ("sanctuary", "end.sanctuary", "S", pygame.K_s),
            ("menu", "end.menu", "ESC", pygame.K_ESCAPE)])
        self.assertEqual([b.variant for b in victory_state.BUTTONS], ["primary"] * 3)
        self.assertEqual([b.variant for b in game_over_state.BUTTONS],
                         ["primary", "primary", "danger"])
        for b in victory_state.BUTTONS:
            self.assertTrue(locale.has(b.label), b.label)

    def test_the_subtitle(self):
        self.assertEqual(_both(lambda: end_screen.run_subtitle(self.STATS)),
                         ("Aegis   -   Fast   -   seed 35",
                          "Aegis   -   Rápido   -   semilla 35"))

    def test_the_titles(self):
        from game.states.game_over_state import GameOverState
        from game.states.victory_state import VictoryState
        game = SimpleNamespace(assets=None)

        def titles():
            out = []
            for cls in (GameOverState, VictoryState):
                s = cls(game)
                s.enter(stats=dict(self.STATS))
                out.append(s._screen.title)
            return out
        self.assertEqual(_both(titles), (["Game Over", "Victory"],
                                         ["Fin de la partida", "Victoria"]))


class _Rec:
    def __init__(self, font, seen):
        self.font, self.seen = font, seen

    def render(self, s, *a, **k):
        self.seen.append(s)
        return self.font.render(s, *a, **k)

    def __getattr__(self, name):
        return getattr(self.font, name)


# --- the end banner (UI-014.D10) --------------------------------------------------------

class _Assets:
    def __init__(self, own=()):
        self.own = set(own)
        self.frames = []

    def rig(self, name):
        if name.endswith("_es") and name not in self.own:
            return None
        return {"frame": [416, 128]}

    def frame_count(self, rig, anim):
        return 30

    def fps(self, rig, anim):
        return 15.0

    def loops(self, rig, anim):
        return False

    def frame(self, rig, anim, index, *, size=None, flip=False, tint=None):
        self.frames.append(rig)
        return pygame.Surface(size or (416, 128), pygame.SRCALPHA)


class EndBannerTests(unittest.TestCase):
    def banner(self, assets, victory=False):
        from game.state import StateMachine
        from game.states.end_banner_state import BANNER, EndBannerState
        game = SimpleNamespace(assets=assets)
        game.state_machine = StateMachine(game)
        st = EndBannerState(game)
        st.enter(victory=victory)
        st.update(config.END_BANNER_WAIT + 0.5)     # past the wait, into the banner
        self.assertEqual(st.phase, BANNER)
        return st

    def words(self, st):
        from game.states import end_banner_state
        seen = []
        real = end_banner_state.shadowed

        def shadowed(font, s, colour, **k):
            seen.append(s)
            return real(font, s, colour, **k)
        with mock.patch.object(end_banner_state, "shadowed", shadowed):
            st.draw(pygame.Surface((1600, 900)))
        return seen

    def test_english_plays_the_art(self):
        _display()
        assets = _Assets()
        st = self.banner(assets)
        self.assertEqual(self.words(st), [])
        self.assertEqual(assets.frames, ["end_banner_loss"])

    def test_spanish_draws_the_words_on_the_english_clock(self):
        _display()
        for victory, want in ((False, "FIN DE LA PARTIDA"), (True, "¡VICTORIA!")):
            locale.set_language("es")
            assets = _Assets()
            st = self.banner(assets, victory)
            self.assertEqual(self.words(st), [want])
            self.assertEqual(assets.frames, [])                # no English letters
            self.assertEqual(st.banner_seconds, 2.0)           # 30 frames at 15 fps
            st.update(2.1)                                     # the play is over
            self.assertEqual(self.words(st), [])

    def test_the_words_shadow_is_in_design_px(self):
        """`shadowed` scales the offset itself: at render scale 2 the drop is
        8 native px, not 16."""
        from game import config
        from game.states import end_banner_state
        _display()
        locale.set_language("es")
        offsets = []
        real = end_banner_state.shadowed

        def shadowed(font, s, colour, **k):
            offsets.append(k.get("offset"))
            return real(font, s, colour, **k)
        with (mock.patch.object(config, "RENDER_SCALE", 2),
              mock.patch.object(end_banner_state, "shadowed", shadowed)):
            st = self.banner(_Assets())
            surf = st._words(shadow=True)
            plain = st._font.render("FIN DE LA PARTIDA", True, (0, 0, 0))
        self.assertEqual(offsets, [(4, 4)])
        self.assertEqual(surf.get_width() - plain.get_width(), 8)

    def test_a_spanish_rig_is_played_when_the_sheet_has_one(self):
        _display()
        locale.set_language("es")
        assets = _Assets(own={"end_banner_win_es"})
        st = self.banner(assets, victory=True)
        self.assertEqual(self.words(st), [])
        self.assertEqual(assets.frames, ["end_banner_win_es"])

    def test_without_art_the_fallback_words_follow_the_language(self):
        """Pixel for pixel what the banner drew before, in English: the
        heading face at 96, antialiased, in the outcome's colour, centred."""
        _display()
        from game.states import end_banner_state as E
        cases = (("en", False, "GAME OVER"), ("en", True, "YOU WON!"),
                 ("es", False, "FIN DE LA PARTIDA"), ("es", True, "¡VICTORIA!"))
        for lang, victory, words in cases:
            with self.subTest(lang=lang, victory=victory):
                locale.set_language(lang)
                st = E.EndBannerState(SimpleNamespace(assets=None))
                st.enter(victory=victory)
                st.phase = E.BANNER
                drawn = pygame.Surface((1600, 900))
                st.draw(drawn)
                want = pygame.Surface((1600, 900))
                frame = fonts.heading(96).render(words, True, E.FALLBACK_COLOUR[victory])
                want.blit(frame, frame.get_rect(center=(800, int(900 * E.CENTRE_Y))))
                self.assertEqual(pygame.image.tostring(drawn, "RGB"),
                                 pygame.image.tostring(want, "RGB"))


if __name__ == "__main__":
    unittest.main()
