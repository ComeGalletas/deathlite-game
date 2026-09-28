"""The run's notices and overlays in Spanish, on a booted run (UI-014.8).

What a player reads in the middle of a run: the opening hints, a chest's
payout, the Forge (its title, keys, rail and both notices), the Monastery
and an elemental buff building. Each is driven through the real handler, in
English and then in Spanish, and each English line is checked against the
exact text the code printed before the move.

Integration tier: one pinned run for the module (`tests/boot.py`), put back
the way it was after each test. The unit half is
`tests/screens/test_spanish_run_text.py`.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ElementId
from entities.chest import Chest
from entities.interactable import Interactable
from game import locale
from game.states.level_up_state import LevelUpState
from game.states.playing.core import infusion
from tests.playing.test_interactables import fresh_playing
from ui import forge_rail

_RUN = None


def playing():
    global _RUN
    if _RUN is None:
        locale.set_language("en")
        _RUN = fresh_playing()
    return _RUN


def _esc():
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)


class RunNoticeTests(unittest.TestCase):
    def setUp(self):
        self.game, self.p = playing()
        self.sword = self.p.player.weapons[0]
        self.assertEqual(self.sword.weapon_id, "sword")
        self.level = self.sword.level
        self.need = self.game.content.offering["forge_requires_levels"]

    def tearDown(self):
        self.sword.level = self.level
        top = self.game.state_machine.current
        if isinstance(top, LevelUpState):
            top.handle_event(_esc())
        self.assertIs(self.game.state_machine.current, self.p)
        locale.set_language(locale.DEFAULT)

    def in_both(self, fn):
        out = []
        for lang in ("en", "es"):
            locale.set_language(lang)
            out.append(fn())
        return tuple(out)

    def forge(self):
        return next(it for it in self.p.interactables if it.kind == "forge")

    # --- the opening hints -----------------------------------------------------
    def test_the_hint_words(self):
        hints = self.p.hints
        words = lambda: ([w for w, _ in hints.clusters("move")],
                         [w for w, _ in hints.clusters("attack")])
        self.assertEqual(self.in_both(words), ((["Move"], ["Attack", "Aim"]),
                                               (["Mover"], ["Atacar", "Apuntar"])))

    # --- a chest ----------------------------------------------------------------------
    def test_a_chest_pays_out_in_the_current_language(self):
        """The blessing is stubbed out (no build change reaches the other
        tests), and the gold, the stats and the spilled potions are put back."""
        from game.states.playing.core import chests
        at, run = self.p.player.pos, self.p.run
        stats = dict(run.stats)
        before = list(run.potions)

        def open_one():
            self.p.chest_manager.open(Chest(at.x, at.y, "epic"))
            return run.notice_text
        try:
            with mock.patch.object(chests, "roll_offering", return_value=[]):
                en, es = self.in_both(open_one)
        finally:
            for potion in run.potions:
                if potion not in before:
                    potion.active = False
            run.potions.sweep()
            run.stats.clear()
            run.stats.update(stats)
        self.assertRegex(en, r"^Epic chest: \d+ gold and a (common|uncommon|rare) potion\.$")
        self.assertRegex(es, r"^Cofre épico: \d+ de oro y una poción "
                             r"(común|poco común|rara)\.$")
        self.assertEqual(list(run.potions), before)

    # --- the Forge ------------------------------------------------------------------------
    def test_a_forge_with_nothing_ready_says_what_is_missing(self):
        self.sword.level = 1                                   # no blessings yet
        say = lambda: self.p.locations.forge_requirements(self.need)
        self.assertEqual(self.in_both(say), (
            f"The Forge needs a weapon with {self.need} blessings: "
            f"the Sword needs {self.need} more.",
            f"La Forja necesita un arma con {self.need} bendiciones. "
            f"Espada: faltan {self.need}."))
        self.sword.level = self.need                           # one short
        self.assertEqual(self.in_both(say), (
            f"The Forge needs a weapon with {self.need} blessings: "
            "the Sword needs 1 more.",
            f"La Forja necesita un arma con {self.need} bendiciones. "
            "Espada: falta 1."))

    def test_every_weapon_forged(self):
        self.sword.forge = "whirlwind"
        try:
            self.assertEqual(
                self.in_both(lambda: self.p.locations.forge_requirements(self.need)),
                ("Every weapon is already forged.", "Todas las armas ya están forjadas."))
        finally:
            self.sword.forge = None

    def test_the_forge_overlay_and_its_notice(self):
        self.sword.level = self.need + 1                       # eligible

        def open_forge():
            self.p._use_forge(self.forge())
            top = self.game.state_machine.current
            self.assertIsInstance(top, LevelUpState)
            top.on_done(SimpleNamespace(weapon="sword", title="Forged"))
            seen = (top.title, top.hint, [r[2] for r in top.weapon_rows],
                    locale.t(top.rail_heading), self.p.run.notice_text)
            top.handle_event(_esc())
            return seen
        en, es = self.in_both(open_forge)
        self.assertEqual(en, (
            "The Forge  -  choose a weapon to reforge",
            "Up/Down pick the weapon    -    1/2/3 or Left/Right + Enter to forge"
            "    -    ESC to leave",
            [f"{self.need} / {self.need} blessings"],
            "REFORGE WHICH WEAPON",
            "The sword is reforged: Forged."))
        self.assertEqual(es, (
            "La Forja  -  elige un arma para reforjar",
            "Arriba/Abajo: elegir arma    -    1/2/3 o Izquierda/Derecha + Enter para forjar"
            "    -    ESC para salir",
            [f"{self.need} / {self.need} bendiciones"],
            "¿QUÉ ARMA REFORJAR?",
            "Reforja de espada: Forged."))
        self.assertEqual(forge_rail.DEFAULT_HEADING, "forge.rail.heading")

    # --- the Monastery and a buff building -------------------------------------------------
    def test_the_monastery_overlay(self):
        it = next(i for i in self.p.interactables if i.kind == "monastery")

        def open_monastery():
            self.p.locations.use(it)
            top = self.game.state_machine.current
            self.assertIsInstance(top, LevelUpState)
            seen = (top.title, top.hint, [r[0].name for r in top.weapon_rows],
                    [r[2] for r in top.weapon_rows], locale.t(top.rail_heading),
                    top.choices[0].description)
            top.handle_event(_esc())
            return seen
        en, es = self.in_both(open_monastery)
        self.assertFalse(it.used)
        self.assertEqual(en[:5], (
            "The Monastery  -  choose an element, then a weapon",
            "Up/Down pick the element    -    1/2/3 or Left/Right + Enter to infuse"
            "    -    ESC to leave",
            ["Fire", "Ice", "Thunder", "Wind"], ["not carried"] * 4,
            "INFUSE WITH WHICH ELEMENT"))
        self.assertTrue(en[5].startswith("Carries fire "), en[5])
        self.assertEqual(es[:5], (
            "El Monasterio  -  elige un elemento y luego un arma",
            "Arriba/Abajo: elegir elemento    -    1/2/3 o Izquierda/Derecha + Enter "
            "para infundir    -    ESC para salir",
            ["Fuego", "Hielo", "Trueno", "Viento"], ["sin portar"] * 4,
            "¿CON QUÉ ELEMENTO INFUNDIR?"))
        self.assertTrue(es[5].startswith("Porta fuego "), es[5])

    def test_the_infusion_notice(self):
        self.sword.element = ElementId.WIND
        try:
            said = self.in_both(lambda: (infusion._noticed(self.p, SimpleNamespace(
                weapon="sword")), self.p.run.notice_text)[1])
        finally:
            self.sword.element = ElementId.NONE
            self.p.run.unlocked_elements.discard(ElementId.WIND)
        self.assertEqual(said, ("The sword carries wind.", "Infusión de viento en espada."))

    def test_a_buff_building_names_its_element(self):
        kind = next(iter(self.p.buffs.defs))
        at = self.p.player.pos

        def activate():
            it = Interactable(kind, at.x, at.y)
            it.element = ElementId.ICE
            self.p.buffs.activate(it)
            top = self.game.state_machine.current
            self.assertIsInstance(top, LevelUpState)
            seen = (top.title, top.hint)
            top.handle_event(_esc())
            return seen
        try:
            en, es = self.in_both(activate)
        finally:
            self.p.buffs.update(600.0)                     # every buff runs out
        self.assertEqual(en, ("Ice - choose a weapon to infuse",
                              "1/2/3 or Left/Right + Enter to infuse    -    ESC to leave"))
        self.assertEqual(es, ("Hielo - elige un arma para infundir",
                              "1/2/3 o Izquierda/Derecha + Enter para infundir    -    ESC para salir"))

    def test_the_picker_titles_itself_when_no_title_is_given(self):
        def open_picker():
            infusion.offer(self.p)
            top = self.game.state_machine.current
            self.assertIsInstance(top, LevelUpState)
            title = top.title
            top.handle_event(_esc())
            return title
        self.assertEqual(self.in_both(open_picker), ("Choose an element, then a weapon",
                                                     "Elige un elemento y luego un arma"))

    def test_no_weapon_to_infuse(self):
        weapons = self.p.player.weapons[:]
        self.p.player.weapons.clear()
        try:
            said = self.in_both(lambda: (infusion.offer(self.p, element=ElementId.FIRE),
                                         self.p.run.notice_text)[1])
        finally:
            self.p.player.weapons.extend(weapons)
        self.assertEqual(said, ("No weapon to infuse.", "No hay armas que infundir."))


if __name__ == "__main__":
    unittest.main()
