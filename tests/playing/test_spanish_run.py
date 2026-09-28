"""A booted run in Spanish (UI-014.5): every screen that shows data text
draws its Spanish, after a switch made mid-run.

One run is booted and built up entirely in English, the way a player would
reach the pause menu:
- the Sword takes Heavy Blade, then is forged into the Greatsword;
- a Skitter and the boss are killed;
- the blessing's proc damage is booked.

Only then does the language change. So everything cached on the way, from
names at spawn and at first kill to the boss the rewards remember, is
checked for the old language. Each assertion picks a text that differs
between the two languages, so a pass cannot be English leaking through.

Drawn text is captured by wrapping the helpers each screen draws through,
since pygame's `Font.render` cannot be patched.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons.forge import apply_forge, get_forges
from entities.boss import Boss
from entities.enemy import Enemy
from game import locale
from game.game import Game
from game.states.menu_state import MenuState
from progression.blessings.apply import apply_blessing
from progression.blessings.catalog import get_catalog
from tests import worlds as W
from tests.boot import start_run

SEED = W.pinned(2)
BOSS = "the_first_hunger"
_RUN = None


def playing():
    """The module's run, built up in English (see the module docstring)."""
    global _RUN
    if _RUN is None:
        locale.set_language("en")
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        game.state_machine.change(MenuState(game))
        ps = start_run(game, SEED)
        C, p = ps.content, ps.player
        apply_blessing(p, get_catalog(C).get("sword_heavy_blade"))
        apply_forge(p.weapons[0], get_forges(C).get("greatsword"))
        ps.run.ledger.kill(Enemy("spider", C.enemy("spider"), 0.0, 0.0))
        boss = Boss(BOSS, C.boss(BOSS), 0.0, 0.0)
        ps.run.ledger.kill(boss)
        ps.rewards.boss_defeated = (boss.boss_id, boss.name)     # English, at the kill
        ps.run.ledger.damage["sword_heavy_blade"] = 10.0         # a proc row
        _RUN = (game, ps, boss)
    return _RUN


class _Recorder:
    """Stands in for a font: records what is rendered, renders it."""

    def __init__(self, font, seen):
        self.font, self.seen = font, seen

    def render(self, text, *a, **k):
        self.seen.append(str(text))
        return self.font.render(text, *a, **k)

    def __getattr__(self, name):
        return getattr(self.font, name)


class SpanishRunTests(unittest.TestCase):
    def setUp(self):
        self.game, self.ps, self.boss = playing()
        self.C = self.ps.content
        locale.set_language("es")              # switched mid-run

    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    # --- the end-of-run summary ------------------------------------------
    def test_the_run_summary_is_resolved_in_spanish(self):
        s = self.ps._snapshot_summary(True)
        self.assertEqual(s["trait_name"], "Baluarte")
        self.assertEqual(s["trait"], "bulwark")                 # the id stays
        self.assertEqual(s["character_id"], "aegis")
        self.assertIn(("Mandoble", 2), s["weapons"])
        self.assertEqual([r["name"] for r in s["weapon_rows"]], ["Mandoble"])
        self.assertIn(("Hoja pesada", 1), s["blessing_rows"])
        self.assertEqual(dict(s["kill_rows"]),
                         {"Escurridiza": 1, "El Hambre Primigenia": 1})
        self.assertEqual(s["boss"], "El Hambre Primigenia")
        self.assertEqual(s["boss_id"], BOSS)
        self.assertIn("Hoja pesada", [r["name"] for r in s["other_rows"]])

    def test_the_summary_screen_shows_the_trait_name(self):
        from ui.run_summary import VICTORY_COLUMNS, RunSummaryPanel
        s = self.ps._snapshot_summary(True)
        seen = []
        real = RunSummaryPanel._kv

        def kv(this, surface, area, y, label, value, *a, **k):
            seen.append(str(value))
            return real(this, surface, area, y, label, value, *a, **k)

        with mock.patch.object(RunSummaryPanel, "_kv", kv):
            RunSummaryPanel(s).draw(pygame.Surface((1600, 900)), self.game.assets,
                                    100, 850, columns=VICTORY_COLUMNS)
        self.assertIn("Baluarte", seen)
        # A two-word trait is shown as written, not re-cased ("Disparo Doble").
        from game.states.playing.core.run_end import trait_name
        s["trait_name"] = trait_name(self.C.character("kestrel"), "double_shot")
        seen.clear()
        with mock.patch.object(RunSummaryPanel, "_kv", kv):
            RunSummaryPanel(s).draw(pygame.Surface((1600, 900)), self.game.assets,
                                    100, 850, columns=VICTORY_COLUMNS)
        self.assertIn("Disparo doble", seen)

    # --- a buff, the boss ------------------------------------------------
    def test_a_buff_banner_reads_in_spanish(self):
        buffs = self.ps.buffs
        before = len(buffs.banners.items)
        buffs.start("vampire")
        self.assertEqual(buffs.banners.items[before].text, "Vampiro")
        buffs.update(60.0)

    def test_the_boss_warning_names_the_boss_in_spanish(self):
        from game.states.playing.visual import rendering
        run = self.ps.run
        seen = []
        self.ps._banner_font = _Recorder(self.ps._banner_font, seen)
        try:
            # A warning time on the banner's visible phase of its blink.
            run.boss, run.boss_name, run.boss_warning_t = self.boss, "The First Hunger", 1.0
            self.ps.draw(pygame.Surface((1600, 900)))
            self.assertTrue(any(t.startswith("El Hambre Primigenia") for t in seen), seen)
            # With no live boss, the name the spawn event carried is shown.
            seen.clear()
            run.boss = None
            self.ps.draw(pygame.Surface((1600, 900)))
            self.assertTrue(any(t.startswith("The First Hunger") for t in seen), seen)
        finally:
            run.boss, run.boss_warning_t = None, 0.0
            self.ps._banner_font = self.ps._banner_font.font

    # --- the TAB screen ----------------------------------------------------
    def tab_text(self):
        from game.states.run_status_state import PANES, RunStatusState
        from ui.run_status import common
        seen = []
        real_kv, real_line, real_sub = common.kv, common.line, common.subheader

        def kv(surface, font, area, y, label, value, **k):
            seen.append(str(value))
            return real_kv(surface, font, area, y, label, value, **k)

        def line(surface, font, area, y, text, **k):
            seen.append(str(text))
            return real_line(surface, font, area, y, text, **k)

        def sub(surface, font, area, y, text, *a, **k):
            seen.append(str(text))
            return real_sub(surface, font, area, y, text, *a, **k)

        s = RunStatusState(self.game)
        s.enter(playing=self.ps)
        surface = pygame.Surface((1600, 900))
        with (mock.patch.object(common, "kv", kv), mock.patch.object(common, "line", line),
              mock.patch.object(common, "subheader", sub)):
            for i in range(len(PANES)):
                s.tab = i
                s.draw(surface)
        return seen

    def test_the_tab_overview_names_the_hero_and_trait(self):
        self.assertIn("Aegis  (Baluarte)", self.tab_text())

    def test_the_tab_build_pane_shows_the_forged_weapon(self):
        seen = self.tab_text()
        self.assertTrue(any(t.startswith("Mandoble  Lv") for t in seen), seen[:30])
        self.assertIn("forged  -  Rompehordas", seen)
        self.assertIn("Forging: Mandoble  -  Rompehordas", seen)
        desc = get_forges(self.C).get("greatsword").display_description
        self.assertTrue(any(desc.startswith(t) for t in seen if len(t) > 12), desc)

    def test_the_tab_blessings_pane_shows_the_blessing(self):
        seen = self.tab_text()
        self.assertIn("Hoja pesada I", seen)
        text = get_catalog(self.C).get("sword_heavy_blade").describe(1)
        self.assertTrue(text.startswith("Golpea"))
        self.assertTrue(any(text.startswith(t) for t in seen if t.startswith("Golpea")), seen)

    def test_the_blessings_list_row_and_owner_are_spanish(self):
        # The list rows are drawn straight with the pane's row font, not
        # through `common`, so they are recorded at the font (a revert of
        # the row to `bdef.name` passed every other test).
        from game.states.run_status_state import PANES, RunStatusState
        s = RunStatusState(self.game)
        s.enter(playing=self.ps)
        seen = []
        s._fonts.row = _Recorder(s._fonts.row, seen)
        s._fonts.small = _Recorder(s._fonts.small, seen)
        s.tab = PANES.index("blessings")
        s.draw(pygame.Surface((1600, 900)))
        self.assertIn("Hoja pesada I", seen)
        self.assertIn("Espada", seen)                       # the owner

    def test_a_missing_name_or_trait_name_falls_back_not_crashes(self):
        # A boss or hero entry without the field: the summary and the TAB
        # overview keep the stored name / the titled id, as before UI-014.5.
        # `patch.dict` restores each shared content dict exactly, key order
        # included, where a pop-and-put-back would move the key to the end.
        from game.states.playing.core.run_end import trait_name
        bdef, cdef = self.C.bosses[BOSS], self.C.character("aegis")
        no_name = {k: v for k, v in bdef.items() if k != "name"}
        no_trait = {k: v for k, v in cdef.items() if k != "trait_name"}
        with mock.patch.dict(bdef, no_name, clear=True), \
                mock.patch.dict(cdef, no_trait, clear=True):
            s = self.ps._snapshot_summary(True)
            self.assertEqual(s["boss"], "The First Hunger")      # stored at the kill
            self.assertEqual(s["trait_name"], "Bulwark")
            self.assertEqual(trait_name(cdef, "double_shot"), "Double Shot")
            self.tab_text()                                      # draws, no KeyError
        self.assertEqual(trait_name(cdef, ""), "")
        self.assertEqual(list(bdef)[0], "name")                  # order restored

    def test_a_nameless_weapon_or_hero_falls_back_to_the_id(self):
        # Nothing requires a weapon's `name` or `description`, or a hero's
        # `name`: each reader shows the id (or nothing) instead of raising.
        import random
        from game.states.character_select_state import CharacterSelectState
        from progression.blessings.offer import grant_offers
        from entities.player import Player
        from combat.weapons import Weapon
        bow = self.C.weapons["bow"]
        stripped = {k: v for k, v in bow.items()
                    if not k.startswith(("name", "description"))}
        ledger = self.ps.run.ledger
        with mock.patch.dict(bow, stripped, clear=True), \
                mock.patch.dict(ledger.damage, {"bow": 1.0}):   # a proc row, unheld
            stub = type("S", (), {"content": self.C})()
            self.assertEqual(CharacterSelectState._weapon_name(stub, "bow"), "bow")
            rows = self.ps._snapshot_summary(True)["other_rows"]
            self.assertIn("bow", [r["name"] for r in rows])
            p = Player(0, 0)
            p.weapons = [Weapon("sword", self.C.weapon("sword"))]
            with mock.patch.dict(bow, {"name": "Bow"}):          # a name, no text
                card = {u.id: u for u in grant_offers(p, self.C, random.Random(1))}["grant:bow"]
                self.assertEqual(card.description, "")
        aegis = self.C.character("aegis")
        with mock.patch.dict(aegis, {k: v for k, v in aegis.items()
                                     if not k.startswith("name")}, clear=True):
            self.assertIn("aegis  (Baluarte)", self.tab_text())

    def test_the_dev_menu_stays_english_where_it_draws(self):
        # UI-014.D6, at every call site, not only in the helper: each
        # method is called unbound on a stub around the run, in Spanish.
        from types import SimpleNamespace
        from game.states.dev_menu_state import DevMenuState
        enemy = Enemy("spider", self.C.enemy("spider"), 0.0, 0.0)
        stub = SimpleNamespace(_playing=self.ps, _status="", page="weapons", sel=0,
                               _nearest_enemy=lambda: enemy,
                               _retire_weapon=lambda w: None,
                               _weapon_rows=lambda: [0])
        row = ("weapon", 0)                                   # the forged Greatsword
        self.assertTrue(DevMenuState._infusion_label(stub, row).startswith("Greatsword"))
        self.assertTrue(DevMenuState._row_label(stub, row).endswith("[Greatsword]"))
        saved = self.ps.player.weapons[0].element
        try:
            DevMenuState._cycle_infusion(stub, row)
            self.assertTrue(stub._status.startswith("Greatsword carries"), stub._status)
        finally:
            self.ps.player.weapons[0].element = saved
        from combat.elements.ids import ELEMENTS
        DevMenuState._force_aura(stub, ELEMENTS[0])
        self.assertIn(" on Skitter:", stub._status)
        DevMenuState._remove_weapon(stub, row)
        self.assertEqual(stub._status, "removed Greatsword")
        DevMenuState._forge(stub, "greatsword")                 # already forged
        self.assertTrue(stub._status.endswith("already forged into Greatsword"),
                        stub._status)

    def test_a_unique_effect_reads_in_spanish(self):
        from ui.run_status.overview import _unique_text
        self.assertEqual(_unique_text("overflow", self.C),
                         "Desbordamiento: +1 proyectil en tu primera arma.")

    def test_a_synergy_row_reads_in_spanish(self):
        from types import SimpleNamespace
        from ui.run_status.build import synergy_rows
        cat = get_catalog(self.C)
        bid = next(b for b, d in cat.by_id.items() if d.category == "synergy")
        bdef = cat.get(bid)
        names = {wid: locale.text(d, "name") for wid, d in self.C.weapons.items()}
        rows = synergy_rows(SimpleNamespace(blessings={bid: 1}), cat, names)
        self.assertEqual(rows, [(rows[0][0], bdef.describe(1))])
        self.assertIn(bdef.title(1), rows[0][0])
        self.assertNotEqual(bdef.title(1), f"{bdef.name} I")      # really Spanish

    # --- hero select, the Sanctuary ------------------------------------------
    def test_the_hero_select_draws_spanish_hero_text(self):
        from game.states import character_select_state as cs
        seen = []
        real_wrap, real_shadowed = cs.wrap, cs.shadowed

        def wrap(font, text, width):
            seen.append(text)
            return real_wrap(font, text, width)

        def shadowed(font, text, *a, **k):
            seen.append(text)
            return real_shadowed(font, text, *a, **k)

        state = cs.CharacterSelectState(self.game)
        state.enter()
        with mock.patch.object(cs, "wrap", wrap), mock.patch.object(cs, "shadowed", shadowed):
            state.draw(pygame.Surface((1600, 900)))
        aegis = self.C.character("aegis")
        self.assertIn(aegis["identity_es"], seen)
        self.assertIn(aegis["trait_desc_es"], seen)
        self.assertIn("Trait - Baluarte", seen)
        self.assertIn("Kestrel", seen)                      # a name that stays

    def test_the_sanctuary_draws_spanish_upgrades(self):
        from game.states.meta_state import MetaState
        meta = MetaState(self.game)
        meta.enter()
        seen = []
        meta._f = _Recorder(meta._f, seen)
        meta._small = _Recorder(meta._small, seen)
        meta.draw(pygame.Surface((1600, 900)))
        self.assertTrue(any(t.startswith("Constitución") for t in seen), seen[:10])
        self.assertIn(self.C.meta_upgrades["fortune"]["desc_es"], seen)


if __name__ == "__main__":
    unittest.main()
