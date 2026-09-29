"""The menu screens in Spanish (UI-014.7).

Two properties are checked:
- English is unchanged. The strings built from parts (the level-up category
  line, the menu's save line) are compared with the old formula, byte for
  byte, for every input the data allows.
- Each screen draws Spanish once the language is switched, including
  Options, where the switch itself is made.

Drawn text is captured at the font, since pygame's `Font.render` cannot be
patched.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, locale
from game.content import get_content
from game.game import Game
from progression.blessings.catalog import CATEGORIES
from ui.level_up import category_line

C = get_content()
CLASSES = sorted({d["class"] for d in C.weapons.values()})


class _Recorder:
    def __init__(self, font, seen):
        self.font, self.seen = font, seen

    def render(self, text, *a, **k):
        self.seen.append(str(text))
        return self.font.render(text, *a, **k)

    def __getattr__(self, name):
        return getattr(self.font, name)


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _old_line(tags):
    """The category line before UI-014.7: each tag capitalised, joined."""
    return " ".join(t[:1].upper() + t[1:] for t in tags)


class CategoryLineTests(unittest.TestCase):
    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    def cards(self):
        """Every card shape the offers build, for every value the data has."""
        weapons = [d["name"] for d in C.weapons.values()]
        for cat in CATEGORIES:
            yield SimpleNamespace(kind="stat", tags=("hero", cat))
            for w in weapons:
                yield SimpleNamespace(kind="weapon", tags=(w, cat))
        for cls in CLASSES:
            yield SimpleNamespace(kind="grant", tags=(cls, "weapon", "grant"))
        for w in weapons:
            yield SimpleNamespace(kind="forge", tags=(w, "forge"))

    def test_english_is_unchanged_for_every_card(self):
        for card in self.cards():
            self.assertEqual(category_line(card), _old_line(card.tags), card)

    def test_spanish_phrases(self):
        locale.set_language("es")
        cases = {
            ("stat", ("hero", "power")): "Poder del héroe",
            ("weapon", ("Espada", "coverage")): "Espada · Cobertura",
            ("grant", ("melee", "weapon", "grant")): "Arma cuerpo a cuerpo",
            ("grant", ("summon", "weapon", "grant")): "Arma de invocación",
            ("forge", ("Espada", "forge")): "Forja · Espada",
        }
        for (kind, tags), want in cases.items():
            self.assertEqual(category_line(SimpleNamespace(kind=kind, tags=tags)), want)
        for card in self.cards():                   # no key leaks through
            self.assertNotIn(".", category_line(card).replace("·", ""), card)

    def test_other_shapes_join_as_before(self):
        locale.set_language("es")
        odd = SimpleNamespace(kind="weapon", tags=("a", "b", "c"))
        self.assertEqual(category_line(odd), "A B C")
        self.assertEqual(category_line(SimpleNamespace(tags=("x",))), "X")

    def test_every_rarity_category_and_class_is_named(self):
        for lang in locale.LANGUAGES:
            locale.set_language(lang)
            for key in ([f"rarity.{r}" for r in ("common", "uncommon", "rare", "epic",
                                                 "legendary", "forge")]
                        + [f"category.{c}" for c in CATEGORIES]
                        + [f"weapon_class.{c}" for c in CLASSES]
                        + [f"difficulty.{d}" for d in config.DIFFICULTY_ORDER]
                        + [f"key_layout.{k}" for k in config.KEY_LAYOUTS]):
                self.assertNotEqual(locale.t(key), key, (lang, key))


class MenuEnglishTests(unittest.TestCase):
    def test_the_save_line_is_unchanged(self):
        from game.states.menu_state import MenuState
        game = _game()
        game.save.currency, game.save.best = 120, {"time": 311.6, "level": 7, "kills": 480}
        game.save.discovered_items = ["a", "b"]
        menu = MenuState(game)
        game.state_machine.change(menu)
        seen = []
        menu._small = _Recorder(menu._small, seen)
        menu.draw(game.screen)
        self.assertIn("Salvage 120    Best: 312s / Lv 7 / 480 kills    Items found 2", seen)


class SpanishScreenTests(unittest.TestCase):
    """Each screen, switched to Spanish, draws its Spanish text."""

    def setUp(self):
        pygame.init()
        self.game = _game()
        self.game.set_language("es")

    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    def drawn(self, state, fonts, **enter):
        self.game.state_machine.change(state, **enter)
        seen = []
        for name in fonts:
            setattr(state, name, _Recorder(getattr(state, name), seen))
        state.draw(self.game.screen)
        return seen

    def test_main_menu(self):
        from game.states.menu_state import MenuState
        menu = MenuState(self.game)
        self.game.state_machine.change(menu)
        self.assertEqual([label for label, _ in menu._options],
                         ["Nueva partida", "Nueva partida en modo desarrollador",
                          "Clasificación", "Opciones", "Salir"])
        seen = self.drawn(menu, ["_small"])
        self.assertTrue(any(t.startswith("Chatarra 0    Mejor: 0 s / Nv. 1") for t in seen))

    def test_hero_select(self):
        from game.states.character_select_state import CharacterSelectState
        cs = CharacterSelectState(self.game)
        seen = self.drawn(cs, ["_title", "_name", "_diff_type", "_hint", "_instr"])
        for want in ("Elige a tu héroe", "Dificultad:  ", "Normal", "<  Volver",
                     "Las armas disparan solas; mantén una dirección o haz clic para apuntarlas."):
            self.assertIn(want, seen)
        keys = next(t for t in seen if t.startswith("Mover"))
        self.assertIn("Apuntar  Flechas / Clic", keys)
        self.assertTrue(any(t.startswith("Izquierda / Derecha: héroe") for t in seen))

    def test_hero_select_lines_difficulty_button_and_hint(self):
        from game.states.character_select_state import CharacterSelectState
        cs = CharacterSelectState(self.game)
        self.game.state_machine.change(cs)
        cs.diff_index = config.DIFFICULTY_ORDER.index("fast")    # "Normal" is the same in both
        seen = []
        for name in ("_title", "_name", "_diff_type", "_hint", "_body"):
            setattr(cs, name, _Recorder(getattr(cs, name), seen))
        cs.draw(self.game.screen)
        for want in ("Empieza con: Espada", "Rápido", "Comenzar"):
            self.assertIn(want, seen)
        self.assertIn("Izquierda / Derecha: héroe    -    Arriba / Abajo o clic: dificultad"
                      "    -    ENTER / Comenzar    -    ESC: volver", seen)
        # A hero who has cleared the boss picks a main weapon.
        self.game.save.mark_cleared("aegis")
        seen = self.drawn(CharacterSelectState(self.game), ["_hint", "_body"])
        self.assertIn("Arma principal:", seen)
        self.assertTrue(any("    -    Q / E: arma principal" in t for t in seen))

    def test_level_up_panel_draws_spanish(self):
        from ui import level_up
        from progression.blessings.offer import grant_offers
        from entities.player import Player
        from combat.weapons import Weapon
        import random
        from unittest import mock
        p = Player(0, 0)
        p.weapons = [Weapon("sword", C.weapon("sword"))]
        card = {u.id: u for u in grant_offers(p, C, random.Random(1))}["grant:grave_totem"]
        panel = level_up.LevelUpPanel()
        seen, titles = [], []
        for name in ("_title", "_hint", "_desc"):
            setattr(panel, name, _Recorder(getattr(panel, name), seen))
        real = level_up.shadowed

        def shadowed(font, text, *a, **k):
            surf = real(font, text, *a, **k)
            titles.append((text, surf.get_width()))
            return surf

        with mock.patch.object(level_up, "shadowed", shadowed):
            panel.draw(self.game.screen, [card], 0, assets=self.game.assets)
        self.assertIn("Subes de nivel  -  elige una", seen)
        self.assertIn("COMÚN", seen)
        self.assertIn("Arma de invocación", seen)
        self.assertIn("1 o Izquierda/Derecha + Enter para elegir    -    "     # one card
                      "o haz clic en una carta", seen)
        # The long Spanish title is drawn smaller, inside the card.
        from ui import scale
        room = scale.px(level_up.CARD_W) - 2 * scale.px(level_up._CARD_TEXT_INSET)
        title, width = titles[0]
        self.assertEqual(title, "Nueva arma: Tótem sepulcral")
        self.assertGreater(panel._name.size(title)[0], room)     # would overflow
        self.assertLessEqual(width, room + 4)                    # +shadow offset

    def test_level_up_state_default_hints(self):
        from game.states.level_up_state import LevelUpState
        rows = SimpleNamespace(weapon_rows=[1], cancelable=True, _hint_arg=None,
                               _hint_key=None, choices=[1, 2, 3],
                               _default_hint=lambda: LevelUpState._default_hint(rows))
        self.assertEqual(LevelUpState.hint.fget(rows).split("    -    ")[0],
                         "Arriba/Abajo: elegir fila")
        leave = SimpleNamespace(weapon_rows=[], cancelable=True, _hint_arg=None,
                                _hint_key=None, choices=[1, 2, 3],
                                _default_hint=lambda: LevelUpState._default_hint(leave))
        self.assertTrue(LevelUpState.hint.fget(leave).endswith("ESC para salir"))
        own = SimpleNamespace(_hint_arg="custom", _hint_key=None, _default_hint=lambda: "x")
        self.assertEqual(LevelUpState.hint.fget(own), "custom")

    def test_the_loading_label_follows_the_language(self):
        from game.states.loading_state import LoadingState
        locale.set_language("en")
        state = LoadingState(self.game)
        self.game.state_machine.change(state, seed=35)
        self.game.set_language("es")                             # after it was built
        seen = []
        state._font = _Recorder(state._font, seen)
        state.draw(self.game.screen)
        self.assertIn("Cargando...", seen)

    def test_options_and_pause_hints(self):
        from game.states.options_state import OptionsState
        from game.states.paused_state import PausedState
        seen = self.drawn(OptionsState(self.game), ["_hint"])
        self.assertIn(locale.t("options.hint"), seen)
        self.assertTrue(seen[-1].startswith("Arriba / Abajo: elegir"))
        seen = self.drawn(PausedState(self.game), ["_hint"])
        self.assertIn("Arriba / Abajo: elegir    -    ENTER: aceptar    -    ESC / P: continuar",
                      seen)

    def test_an_options_label_that_does_not_fit_is_drawn_smaller(self):
        from game.states import options_state as o
        from ui import scale
        opt = o.OptionsState(self.game)
        self.game.state_machine.change(opt)
        text = locale.t("options.music")                          # Volumen de la música
        room = scale.px(o._VALUE_DX) - scale.px(o._LABEL_GAP)
        self.assertGreater(opt._row.size(text)[0], room)          # would overflow
        seen = []
        opt._row = _Recorder(opt._row, seen)
        opt.draw(self.game.screen)
        self.assertNotIn(text, seen)                              # not the default font
        self.assertIn(locale.t("options.master"), seen)           # which still draws the rest

    def test_options_switches_in_place(self):
        # Switching back to English from the Spanish Options screen redraws
        # it in English on the next frame.
        from game.states.options_state import OptionsState
        opt = OptionsState(self.game)
        seen = self.drawn(opt, ["_title", "_row", "_hint"])
        for want in ("Opciones", "Volumen general", "Idioma", "Español", "Sí",
                     "WASD: mover / Flechas: apuntar"):
            self.assertIn(want, seen)
        self.assertTrue(any(t.endswith(" %") for t in seen))
        opt.sel = opt._rows.index("language")
        opt._activate()                                         # -> English
        seen.clear()
        opt.draw(self.game.screen)
        self.assertIn("Options", seen)
        self.assertIn("Master volume", seen)

    def test_pause(self):
        from game.states.paused_state import PausedState
        from unittest import mock
        from game.states import paused_state
        pause = PausedState(self.game)
        self.game.state_machine.change(pause)
        title, rows, controls, fitted = [], [], [], []
        pause._title_font = _Recorder(pause._title_font, title)
        pause._font = _Recorder(pause._font, rows)
        pause._controls_head = _Recorder(pause._controls_head, controls)
        from ui import controls_block
        real_fit = paused_state.fit_font
        real_cached = controls_block.uitext.cached_font
        with mock.patch.object(paused_state, "fit_font",
                               lambda *a, **k: _Recorder(real_fit(*a, **k), fitted)), \
                mock.patch.object(controls_block.uitext, "cached_font",
                                  lambda *a, **k: _Recorder(real_cached(*a, **k), controls)):
            pause.draw(self.game.screen)
        self.assertEqual(title, ["Pausa"])
        for want in ("Continuar", "Estado de la partida", "Opciones", "Teclas",
                     "Salir al menú"):
            self.assertIn(want, rows)
        # The key-layout value is too long for its default size; it is drawn
        # fitted, in Spanish.
        self.assertEqual(fitted, ["WASD: mover / Flechas: apuntar"])
        for want in ("Controles", "Mover", "Apuntar (mantener)", "Atacar", "Interactuar",
                     "Ataque automático", "Equipo", "Pausa"):
            self.assertIn(want, controls)

    def test_rankings(self):
        from game.states.rankings_state import RankingsState
        self.game.save.records["fast"] = {"time": 95.0, "level": 5, "kills": 12,
                                          "damage_dealt": 900.0}
        seen = self.drawn(RankingsState(self.game), ["_title", "_hint", "_head", "_row"])
        for want in ("Clasificación", "Rápido", "Superrápido", "aún no hay partidas",
                     "Tiempo", "95 s", "ENTER / ESC  -  volver al menú",
                     "Mejor partida por dificultad  -  nunca se comparan entre dificultades"):
            self.assertIn(want, seen)

    def test_level_up_title_rarity_and_new_weapon(self):
        from progression.blessings.offer import grant_offers
        from entities.player import Player
        from combat.weapons import Weapon
        import random
        p = Player(0, 0)
        p.weapons = [Weapon("sword", C.weapon("sword"))]
        card = {u.id: u for u in grant_offers(p, C, random.Random(1))}["grant:bow"]
        self.assertEqual(card.title, "Nueva arma: Arco")
        self.assertEqual(locale.t(f"rarity.{card.rarity}").upper(), "COMÚN")
        self.assertEqual(locale.t("level_up.title"), "Subes de nivel  -  elige una")

    def test_options_on_and_off_follow_the_setting(self):
        from game.states.options_state import OptionsState
        opt = OptionsState(self.game)
        self.game.state_machine.change(opt)
        self.game.audio.muted = False
        self.game.set_tutorials(True)
        seen = []
        opt._row = _Recorder(opt._row, seen)
        opt.draw(self.game.screen)
        # Each value is drawn right after its label.
        self.assertEqual(seen[seen.index("Silenciar") + 1], "No")
        self.assertEqual(seen[seen.index("Tutoriales") + 1], "Sí")
        self.game.audio.muted = True
        self.game.set_tutorials(False)
        seen.clear()
        opt.draw(self.game.screen)
        self.assertEqual(seen[seen.index("Silenciar") + 1], "Sí")
        self.assertEqual(seen[seen.index("Tutoriales") + 1], "No")

    def test_an_unknown_difficulty_shows_its_id(self):
        from ui import end_screen
        sub = end_screen.run_subtitle({"character": "Aegis", "difficulty": "nightmare",
                                       "seed": 1})
        self.assertIn("nightmare", sub)
        self.assertNotIn("difficulty.", sub)
        self.assertIn("Rápido", end_screen.run_subtitle({"character": "Aegis",
                                                           "difficulty": "fast", "seed": 1}))

    def test_the_display_rows(self):
        from unittest import mock
        d = self.game.display
        with mock.patch.object(d, "available", False):
            self.assertEqual(d.mode_label(), "No disponible")
            self.assertEqual(d.resolution_label(), "No disponible")
        with mock.patch.object(d, "available", True), \
                mock.patch.object(d, "mode", "windowed"), \
                mock.patch.object(d, "windowed_size", (1234, 567)), \
                mock.patch.object(d, "resolution_index", lambda: -1):
            self.assertEqual(d.mode_label(), "En ventana")
            self.assertEqual(d.resolution_label(), "Personalizada 1234x567")
        with mock.patch.object(d, "available", True), \
                mock.patch.object(d, "mode", "borderless"):
            self.assertEqual(d.mode_label(), "Sin bordes")


class FitTests(unittest.TestCase):
    """A translation longer than its slot steps down in size (UI-014.7)."""

    def setUp(self):
        pygame.init()

    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    def test_fit_font_picks_the_largest_size_that_fits(self):
        from game import fonts
        from ui.text import fit_font
        text = "Volumen de la música"
        full = fonts.body(26).size(text)[0]
        room = full - 20
        font = fit_font(fonts.body, 26, text, room)
        # The largest design size that fits, worked out independently.
        expected = next(s for s in range(26, 17, -1)
                        if fonts.body(s).size(text)[0] <= room)
        self.assertLess(expected, 26)
        self.assertEqual(font.size(text), fonts.body(expected).size(text))
        self.assertGreater(fonts.body(expected + 1).size(text)[0], room)
        self.assertIs(fit_font(fonts.body, 26, text, room), font)   # cached
        # Enough room: the design size itself.
        self.assertEqual(fit_font(fonts.body, 26, text, full).size(text)[0], full)
        # No room at all: the floor, never smaller.
        tiny = fit_font(fonts.body, 26, text, 1)
        self.assertEqual(tiny.get_height(), fonts.body(int(round(26 * 0.7))).get_height())

    def test_every_options_label_fits_before_its_value(self):
        from game import fonts
        from game.states import options_state as o
        from ui import scale
        from ui.text import fit_font
        room = scale.px(o._VALUE_DX) - scale.px(o._LABEL_GAP)
        for lang in locale.LANGUAGES:
            locale.set_language(lang)
            for rid in ("master", "music", "sfx", "mute", "key_layout", "tutorials",
                        "language", "display", "resolution", "sanctuary", "back"):
                text = locale.t(f"options.{rid}")
                width = fit_font(fonts.body, o._ROW_PX, text, room).size(text)[0]
                self.assertLessEqual(width, room, (lang, text))

    def test_the_pause_key_layout_row_fits_in_spanish(self):
        from game.states.paused_state import PausedState, _ROWS
        game = _game()
        game.set_language("es")
        pause = PausedState(game)
        game.state_machine.change(pause)
        rects = []

        class Spy(pygame.Surface):
            def blit(self, src, dest, *a, **k):
                rects.append(pygame.Rect(dest, src.get_size()) if not
                             isinstance(dest, pygame.Rect) else pygame.Rect(dest))
                return super().blit(src, dest, *a, **k)

        screen = Spy(game.screen.get_size())
        pause.draw(screen)
        row = pause._mouse.hits.rect_of(_ROWS.index("key_layout"))
        texts = sorted((r for r in rects if row.contains(r) and r.width < row.width),
                       key=lambda r: r.left)
        label, value = texts[0], texts[-1]
        self.assertLess(label.right, value.left)               # no overlap
        self.assertLessEqual(value.right, row.right)

    def test_the_fitted_options_label_keeps_its_gap_before_the_value(self):
        # Measured on what is drawn, against the design's 16 px, so the gap
        # constant cannot vouch for itself.
        from game.states import options_state as o
        from ui import scale
        game = _game()
        game.set_language("es")
        opt = o.OptionsState(game)
        game.state_machine.change(opt)
        opt.draw(game.screen)                          # registers the bars
        rects = []

        class Spy(pygame.Surface):
            def blit(self, src, dest, *a, **k):
                rects.append(pygame.Rect(dest, src.get_size()) if not
                             isinstance(dest, pygame.Rect) else pygame.Rect(dest))
                return super().blit(src, dest, *a, **k)

        screen = Spy(game.screen.get_size())
        opt.draw(screen)
        bar = opt._bars["music"]                       # the value: the slider
        row = [r for r in rects if r.right <= bar.left and r.top < bar.centery < r.bottom]
        label = max(row, key=lambda r: r.width)        # "Volumen de la música"
        self.assertGreaterEqual(bar.left - label.right, scale.px(16))

    def test_the_fit_cache_follows_the_render_scale(self):
        # After a window rescale the same design size is a different native
        # size; a cache keyed without the scale would hand back the old font.
        from unittest import mock
        from game import fonts
        from ui.text import fit_font
        text = "Volumen de la música"
        small = fit_font(fonts.body, 26, text, 10_000)
        with mock.patch.object(config, "RENDER_SCALE", config.RENDER_SCALE * 2):
            big = fit_font(fonts.body, 26, text, 10_000)
        self.assertGreater(big.size(text)[0], small.size(text)[0])

    def test_the_options_mouse_band_covers_every_value(self):
        # A click anywhere on a row's value lands on that row, in any language.
        from game.states import options_state as o
        from ui import scale
        for lang in locale.LANGUAGES:
            game = _game()
            game.set_language(lang)
            opt = o.OptionsState(game)
            game.state_machine.change(opt)
            opt.draw(game.screen)
            x0 = game.screen.get_width() // 2 + scale.px(o._LABEL_DX)
            vx = x0 + scale.px(o._VALUE_DX)
            for layout in config.KEY_LAYOUTS:
                band = opt._mouse.hits.rect_of(opt._rows.index("key_layout"))
                right = vx + opt._row.size(locale.t(f"key_layout.{layout}"))[0]
                self.assertLessEqual(right, band.right, (lang, layout))
        locale.set_language(locale.DEFAULT)

    def test_every_grant_title_fits_its_card(self):
        from game import fonts
        from ui.level_up import CARD_W, _CARD_TEXT_INSET, _NAME_PX
        from ui import scale
        from ui.text import fit_font
        room = scale.px(CARD_W) - 2 * scale.px(_CARD_TEXT_INSET)
        for lang in locale.LANGUAGES:
            locale.set_language(lang)
            for d in C.weapons.values():
                title = locale.t("level_up.new", name=locale.text(d, "name"))
                font = fit_font(fonts.heading, _NAME_PX, title, room)
                self.assertLessEqual(font.size(title)[0], room, (lang, title))


if __name__ == "__main__":
    unittest.main()
