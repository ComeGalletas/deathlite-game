"""The run summary, the TAB screen and the Sanctuary in the locale files
(UI-014.9), with name tables for every id they print.

For each screen:
- **English is the text drawn before the move.** The strings pinned here are
  the old literals; the ids a screen showed as text are the English names.
  (A pixel comparison of every screen state against the previous commit was
  run by hand for UI-014.9 and is recorded in the journal.)
- **Spanish is drawn**, checked where it is drawn, and none of the English
  words below survives in it.

Text is captured by standing a recorder in for each font the screen draws
with, since pygame's `Font.render` cannot be patched. Unit tier: a
hand-built run from `test_run_status`, no world.
"""
import itertools
import os
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ElementId
from combat.weapons.core import ATTACK_MODE, TIME_MODE
from combat.weapons.forge import TEXT_OVERRIDE_KEYS
from game import config, fonts, locale
from game.content import get_content
from game.states.run_status_state import PANES
from progression.blessings.catalog import get_catalog
from progression.items import generate_item
from tests.screens.test_run_status import _run, _state
from ui import run_summary
from ui.run_status import build, common
from ui.run_summary import COLUMNS, VICTORY_COLUMNS, RunSummaryPanel

NB = " "

# The labels the code carried before UI-014.9, verbatim.
OLD_STAT_LABELS = {
    "max_hp": "Max HP", "hp_regen": "HP regen", "move_speed": "Move speed",
    "armor": "Armor", "damage_multiplier": "Damage", "melee_damage": "Melee damage",
    "ranged_damage": "Ranged damage", "attack_speed_multiplier": "Attack speed",
    "projectile_speed_multiplier": "Projectile speed", "area_multiplier": "Area",
    "crit_chance": "Crit chance", "crit_damage": "Crit damage", "evasion_chance": "Evasion",
    "block_chance": "Block chance", "block_strength": "Block strength",
    "pickup_radius": "Pickup radius", "luck": "Luck", "xp_gain": "XP gain",
    "gold_gain": "Gold gain"}
OLD_WEAPON_STATS = {
    "damage": "Damage", "cooldown": "Cooldown", "projectile_count": "Projectiles",
    "area": "Area", "reach": "Reach", "pierce": "Pierce", "blast_radius": "Blast radius",
    "cone_half_angle": "Cone", "chain_count": "Chains", "weight": "Weight"}


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()


class _Rec:
    """Stands in for a font: records every text it renders."""

    def __init__(self, font, seen):
        self.font, self.seen = font, seen

    def render(self, text, *a, **k):
        self.seen.append(str(text))
        return self.font.render(text, *a, **k)

    def __getattr__(self, name):
        return getattr(self.font, name)


def _both(fn):
    locale.set_language("en")
    en = fn()
    locale.set_language("es")
    try:
        return en, fn()
    finally:
        locale.set_language(locale.DEFAULT)


# --- the name tables -------------------------------------------------------------

class NameTableTests(unittest.TestCase):
    def setUp(self):
        self.C = get_content()
        self.weapons = [v for v in self.C.weapons.values() if isinstance(v, dict)]
        self.forges = [v for v in self.C.forges.values() if isinstance(v, dict)]
        self.sources = self.weapons + [f.get("overrides", {}) for f in self.forges]

    def values(self, key):
        out = set()
        for src in self.sources:
            v = src.get(key)
            out.update(map(str, v) if isinstance(v, list) else ([str(v)] if v else []))
        return out

    def test_every_id_the_screens_print_has_a_name_in_both_languages(self):
        tables = get_content().locale
        need = {"class": self.values("class"),
                "weapon_category": self.values("category"),
                "special": self.values("special_effect"),
                "targeting": self.values("targeting_mode"),
                "tag": self.values("tags") | {a["tag"] for a in self.C.items["affixes"].values()
                                              if a.get("kind") == "tag_damage"},
                "slot": set(self.C.items["bases"]),
                "stat": {s for s, _k in common.STAT_ROWS},
                "weapon_stat": {k for k, _b, _kind in build._NUMBERS},
                "forge_field": {k for f in self.forges for k in f.get("overrides", {})
                                if k not in TEXT_OVERRIDE_KEYS}
                               | {k for f in self.forges for k in (f.get("effects") or {})},
                "element": {e.key for e in ElementId if e is not ElementId.NONE}}
        for table, ids in need.items():
            self.assertTrue(ids, table)
            for i in ids:
                for lang in ("en", "es"):
                    with self.subTest(table=table, id=i, lang=lang):
                        self.assertIn(f"{table}.{i}", tables[lang])

    def test_english_names_are_what_the_screens_drew(self):
        tables = get_content().locale["en"]
        for key, text in tables.items():
            table, _, i = key.partition(".")
            if table == "forge_field":
                self.assertEqual(text, i.replace("_", " "), key)
            elif table in ("class", "weapon_category", "special", "tag", "targeting", "slot"):
                self.assertEqual(text, i, key)
        self.assertEqual({s: tables[f"stat.{s}"] for s in OLD_STAT_LABELS}, OLD_STAT_LABELS)
        self.assertEqual({s: tables[f"weapon_stat.{s}"] for s in OLD_WEAPON_STATS},
                         OLD_WEAPON_STATS)

    def test_name_falls_back_for_an_unlisted_id(self):
        self.assertEqual(_both(lambda: locale.name("slot", "armor")), ("armor", "armadura"))
        self.assertEqual(_both(lambda: locale.name("slot", "trinket")), ("trinket", "trinket"))
        self.assertEqual(_both(lambda: locale.name("slot", "trinket", "Trinket!")),
                         ("Trinket!", "Trinket!"))
        self.assertEqual(_both(lambda: common.stat_label("thorn_power")),
                         ("Thorn power", "Thorn power"))


# --- the TAB screen ------------------------------------------------------------------

def _tab_text(ps, sel=0):
    """Every string the TAB screen draws, pane by pane: `{pane: [text]}`."""
    s = _state(ps)
    seen = []
    for name in ("ribbon", "title", "sub", "row", "small"):
        setattr(s._fonts, name, _Rec(getattr(s._fonts, name), seen))
    s._hint = _Rec(s._hint, seen)
    out = {}
    for i, pane in enumerate(PANES):
        s.tab = i
        if hasattr(s.pane, "sel"):
            s.pane.sel = sel
        seen.clear()
        s.draw(pygame.Surface((1600, 900)))
        out[pane] = list(seen)
    return out


class TabScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.ps = _run(full=True)
        cls.ps.player.weapons[2].element = ElementId.FIRE        # an infused bow
        cls.ps.stats.update(potions=3, potion_healing=41.6)
        cls.en, cls.es = _both(lambda: _tab_text(cls.ps))

    def test_the_tabs_and_the_hint(self):
        for pane in PANES:
            with self.subTest(pane=pane):
                self.assertIn("TAB / ESC close   -   Left / Right or 1 2 3 switch pane   -   "
                              "Up / Down or wheel select", self.en[pane])
                self.assertIn("TAB / ESC: cerrar   -   Izquierda / Derecha o 1 2 3: cambiar "
                              "panel   -   Arriba / Abajo o rueda: elegir", self.es[pane])
                for en, es in (("Overview", "Resumen"), ("Build", "Arsenal"),
                               ("Blessings", "Bendiciones")):
                    self.assertIn(en, self.en[pane])
                    self.assertIn(es, self.es[pane])

    def test_the_overview(self):
        en, es = self.en["overview"], self.es["overview"]
        for old in ("Hero", "Difficulty", "Survived", "HP", "Level", "Kills", "Gold",
                    "Salvage", "Potions", "Equipped items  (1)", "Hero stats", "Normal",
                    *OLD_STAT_LABELS.values()):
            self.assertIn(old, en)
        self.assertIn("3   (42 HP)", en)
        for new in ("Héroe", "Dificultad", "Tiempo", "PV", "Nivel", "Bajas", "Oro",
                    "Chatarra", "Pociones", "Objetos equipados  (1)",
                    "Estadísticas del héroe", "3   (42 PV)", "PV máximos", "Prob. crítico"):
            self.assertIn(new, es)
        item = self.ps.player.equipment[0]
        slot_es = {"weapon": "arma", "armor": "armadura", "accessory": "accesorio"}[item.slot]
        self.assertIn(f"{item.slot}  Lv {item.level}", en)
        self.assertIn(f"{slot_es}  Nv. {item.level}", es)
        for word in ("Hero stats", "Difficulty", "Salvage", "Equipped items", "Max HP"):
            self.assertFalse([t for t in es if word in t], word)

    def test_the_build_pane(self):
        en, es = self.en["build"], self.es["build"]
        sword, bow, wolf = (self.ps.player.weapons[i] for i in (0, 2, 3))
        self.assertIn(f"{sword.name}  Lv {sword.level}", en)
        self.assertIn(f"{_both(lambda: bow.name)[1]}  Nv. {bow.level}", es)
        self.assertIn("melee  ·  cone", en)
        self.assertIn("cuerpo a cuerpo  ·  cono", es)
        self.assertIn("summon", en)
        self.assertIn("invocación", es)
        self.assertIn("fire  ·  every attack", en)
        self.assertIn("fuego  ·  cada ataque", es)
        for old in ("Blessing levels", "cannot be forged", "Synergies  (1)", "Cooldown",
                    "Damage", "cooldown", "projectile lifetime"):
            self.assertIn(old, en)
        for new in ("Niveles de bendición", "no se puede forjar", "Sinergias  (1)",
                    "Recarga", "Daño", "recarga", "duración del proyectil"):
            self.assertIn(new, es)
        self.assertTrue([t for t in en if t.startswith("Forging: ")])
        self.assertTrue([t for t in es if t.startswith("Forja: ")])
        self.assertTrue([t for t in en if t.startswith("forged  -  ")])
        self.assertTrue([t for t in es if t.startswith("con forja  -  ")])
        for word in ("Blessing levels", "cannot be forged", "every attack", "Forging:",
                     "Synergies", "Cooldown", "projectile lifetime"):
            self.assertFalse([t for t in es if word in t], word)

    def test_the_blessings_pane(self):
        en, es = self.en["blessings"], self.es["blessings"]
        self.assertIn("Blessings  (4)", en)
        self.assertIn("Bendiciones  (4)", es)
        self.assertIn("Level", en)
        self.assertIn("Nivel", es)
        self.assertTrue([t for t in en if re.fullmatch(r"[IVX]+ of [IVX]+", t)])
        self.assertTrue([t for t in es if re.fullmatch(r"[IVX]+ de [IVX]+", t)])
        self.assertFalse([t for t in es if re.fullmatch(r"[IVX]+ of [IVX]+", t)])
        detail = [t for t in en if "  ·  " in t]
        self.assertTrue(detail)
        rarity, category, owner = detail[0].split("  ·  ")
        self.assertEqual((rarity, category), (rarity.lower(), category.lower()))
        self.assertIn(owner, ("Hero", *(w.name for w in self.ps.player.weapons)))
        es_detail = [t for t in es if "  ·  " in t][0].split("  ·  ")
        self.assertIn(es_detail[0], ("común", "poco común", "raro"))
        self.assertIn(es_detail[1], ("poder", "cobertura", "comportamiento", "sinergia"))

    def test_an_empty_run(self):
        en, es = _both(lambda: _tab_text(_run(full=False)))
        self.assertIn("none", en["overview"])
        self.assertIn("ninguno", es["overview"])
        self.assertIn("no weapons", en["build"])
        self.assertIn("sin armas", es["build"])
        self.assertIn("none yet  -  a synergy blessing links two weapons", en["build"])
        self.assertIn("ninguna aún  -  una sinergia une dos armas", es["build"])
        self.assertIn("none yet", en["blessings"])
        self.assertIn("ninguna aún", es["blessings"])
        self.assertIn("Blessings come from level-ups and the village.", en["blessings"])
        self.assertIn("Las bendiciones llegan al subir de nivel y en la aldea.", es["blessings"])

    def test_no_run(self):
        def text():
            s = _state(self.ps)
            s.playing = None
            seen = []
            s._fonts.row = _Rec(s._fonts.row, seen)
            s.draw(pygame.Surface((1600, 900)))
            return seen
        self.assertEqual(_both(text), (["no run"], ["sin partida"]))


class BuildHelperTests(unittest.TestCase):
    def weapon(self, **k):
        d = dict(element=ElementId.WIND, element_mode=ATTACK_MODE, element_window=1.25,
                 element_interval=0)
        d.update(k)
        return SimpleNamespace(**d)

    def test_infusion_text(self):
        cases = ((dict(element_mode=TIME_MODE), ("wind  ·  every 1.2s",
                                                 f"viento  ·  cada 1,2{NB}s")),
                 (dict(element_interval=2), ("wind  ·  1 attack in 3",
                                             "viento  ·  1 de cada 3 ataques")),
                 ({}, ("wind  ·  every attack", "viento  ·  cada ataque")))
        for kw, want in cases:
            self.assertEqual(_both(lambda: build.infusion_text(self.weapon(**kw))), want)

    def test_gate_text(self):
        from combat.weapons.forge import get_forges
        forges = get_forges(get_content())
        ok = lambda **k: SimpleNamespace(**{"is_summon": False, "forge": None, "level": 1, **k})
        self.assertEqual(_both(lambda: build.gate_text(ok(is_summon=True), 2, forges)),
                         ("cannot be forged", "no se puede forjar"))
        self.assertEqual(_both(lambda: build.gate_text(ok(level=3), 2, forges)),
                         ("ready for the Forge (2)", "puede ir a la Forja (2)"))
        self.assertEqual(_both(lambda: build.gate_text(ok(level=2), 3, forges)),
                         ("Forge at 3  -  has 1", "Forja con 3  -  tiene 1"))

    def test_a_forging_value_reads_through_its_table(self):
        fmt = build._fmt
        self.assertEqual(_both(lambda: fmt(["melee", "area"], "n", "tag")),
                         ("melee, area", "cuerpo a cuerpo, área"))
        self.assertEqual(_both(lambda: fmt("orbit", "n", "weapon_category")),
                         ("orbit", "órbita"))
        self.assertEqual(_both(lambda: fmt("nearest", "n", "targeting")),
                         ("nearest", "el más cercano"))
        self.assertEqual(_both(lambda: fmt(True, "n")), ("yes", "sí"))
        self.assertEqual(_both(lambda: fmt(False, "n")), ("no", "no"))
        self.assertEqual(_both(lambda: fmt(2.5, "s")), ("2.5s", f"2,5{NB}s"))   # D7 style (UI-014.10)
        self.assertEqual(build._VALUE_TABLES, {"category": "weapon_category",
                                               "special_effect": "special",
                                               "targeting_mode": "targeting", "tags": "tag"})


# --- the run summary ------------------------------------------------------------------

def _summary_text(stats, columns, stepped=None, pairs=None):
    """Every string the panel draws; a value drawn in a stepped-down font
    (`_kv`) is recorded too, and listed in `stepped` when given. `pairs`
    collects each `_kv` row as `(label, value)`."""
    seen = []
    panel = RunSummaryPanel(stats)
    if pairs is not None:
        real_kv = RunSummaryPanel._kv

        def kv(surface, area, y, label, value, **k):
            pairs.append((str(label), str(value)))
            return real_kv(panel, surface, area, y, label, value, **k)
        panel._kv = kv
    for name in ("_ribbon", "_sub", "_row", "_small"):
        setattr(panel, name, _Rec(getattr(panel, name), seen))
    real = run_summary.uitext.fit_font

    def fit(role, px, text, room, **k):
        if stepped is not None:
            stepped.append(text)
        return _Rec(real(role, px, text, room, **k), seen)
    with mock.patch.object(run_summary.uitext, "fit_font", fit):
        panel.draw(pygame.Surface((1600, 900)), None, 178, 762, columns=columns)
    return seen


def _summary_stats():
    """A won run's summary with every row kind: the fixture the summary
    tests share (built fresh, so no test depends on another's order)."""
    C = get_content()
    items = [generate_item(C, seed=s, item_level=5).to_dict() for s in range(3)]
    return {
        "time": 412.0, "level": 9, "kills": 57, "gold_earned": 120, "potions": 2,
        "potion_healing": 30.4, "chests": 1, "unlocked_elements": ["fire", "wind"],
        "dropped_items": items, "new_records": ["time", "damage_dealt"],
        "kill_rows": [("Skitter", 50), ("Imp", 7)],
        "weapon_rows": [{"name": "Sword", "level": 5, "damage": 900.0, "share": 0.98,
                         "dps": 2.2}],
        "other_rows": [{"name": "Burn", "damage": 20.0, "share": 0.02, "dps": 0.1}],
        "damage_dealt": 920.0, "blessing_rows": [("Vitality", 2)],
        "character": "Aegis", "trait_name": "Bulwark",
        "hero_stats": {"max_hp": 160.0, "crit_chance": 0.1}, "equipment": items[:1],
        "first_clear": True, "victory": True}


class RunSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.stats = _summary_stats()
        cls.en, cls.es = _both(lambda: _summary_text(cls.stats, VICTORY_COLUMNS))

    def test_english_is_what_it_was(self):
        for old in ("Run", "Enemies slain", "Weapons", "Hero", "Cleared in", "best", "Level",
                    "Kills", "57   (8/min)", "Gold earned", "Potions", "2   (30 HP)", "Chests",
                    "Elements", "fire, wind", "Items acquired  (3)", "Total",
                    "Blessings  (1)", "Lv 2", "Lv 5", "Lv", "Damage", "Share", "DPS",
                    "Weapon", "Blessing procs & other", "Main weapon unlocked", "Trait",
                    "Stats", "Max HP", "Crit chance", "Equipped  (1)"):
            self.assertIn(old, self.en, old)
        self.assertTrue([t for t in self.en if t.startswith("[C] ") or t.startswith("[U] ")])

    def test_spanish_is_drawn(self):
        self.assertIn("57   (8/min)", self.es)
        self.assertEqual(self.es.count("Héroe"), 2)            # the ribbon and the row
        self.assertIn("DPS", self.es)
        for new in ("Partida", "Enemigos abatidos", "Armas", "Héroe", "Tiempo", "récord",
                    "Nivel", "Bajas", "Oro ganado", "Pociones", "2   (30 PV)", "Cofres",
                    "Elementos", "fuego, viento", "Objetos obtenidos  (3)", "Total",
                    "Bendiciones  (1)", "Nv. 2", "Nv. 5", "Nv.", "Daño", "Parte", "Arma",
                    "Efectos de bendiciones y otros", "Arma principal liberada", "Rasgo",
                    "Estadísticas", "PV máximos", "Prob. crítico", "Equipado  (1)"):
            self.assertIn(new, self.es, new)
        for word in ("Enemies slain", "Cleared in", "best", "Gold earned", "Items acquired",
                     "Blessing procs", "Main weapon", "Equipped", "Weapon", "Lv "):
            self.assertFalse([t for t in self.es if word in t], word)

    def test_a_value_too_wide_for_its_row_steps_down_before_the_label_trims(self):
        """"fuego, viento" beside "Elementos" does not fit the Victory Run
        column at full size: the value steps down and the label is whole.
        English's "fire, wind" fits, and nothing steps."""
        en_stepped, es_stepped = [], []
        locale.set_language("en")
        en = _summary_text(self.stats, VICTORY_COLUMNS, en_stepped)
        locale.set_language("es")
        es = _summary_text(self.stats, VICTORY_COLUMNS, es_stepped)
        self.assertEqual(en_stepped, [])
        self.assertIn("fuego, viento", es_stepped)
        self.assertIn("Elementos", es)                      # whole, not "Eleme..."
        self.assertIn("Elements", en)

    def test_the_damage_record_marks_the_weapons_total(self):
        def markers(records):
            stats = dict(self.stats, new_records=records)
            return _both(lambda: _summary_text(stats, VICTORY_COLUMNS))
        (en, es) = markers(["damage_dealt"])
        self.assertEqual(en.count("best"), 1)
        self.assertEqual(es.count("récord"), 1)
        # Drawn with the damage table's Total row: the marker comes just
        # before the row's name is rendered.
        self.assertEqual(en[en.index("best") + 1], "Total")
        self.assertEqual(es[es.index("récord") + 1], "Total")
        (en, es) = markers([])
        self.assertNotIn("best", en)
        self.assertNotIn("récord", es)

    def test_the_empty_item_lists(self):
        stats = dict(self.stats, equipment=[], dropped_items=[])
        en, es = _both(lambda: _summary_text(stats, VICTORY_COLUMNS))
        for lang, text, heads, word in (("en", en, ("Items acquired  (0)", "Equipped  (0)"), "none"),
                                        ("es", es, ("Objetos obtenidos  (0)", "Equipado  (0)"),
                                         "ninguno")):
            for head in heads:
                with self.subTest(lang=lang, head=head):
                    self.assertEqual(text[text.index(head) + 1], word)

    def test_the_kill_rate(self):
        stats = dict(self.stats, kills=600, time=60.0)
        en, es = _both(lambda: _summary_text(stats, VICTORY_COLUMNS))
        self.assertIn("600   (600/min)", en)
        self.assertIn("600   (600/min)", es)

    def test_a_loss_and_the_empty_lists(self):
        empty = {"time": 30.0}
        en, es = _both(lambda: _summary_text(dict(empty, victory=False), COLUMNS))
        for old, new in (("Survived", "Tiempo"), ("none", "ninguno"),
                         ("nothing slain", "sin bajas"), ("no weapons", "sin armas"),
                         ("Blessings  (0)", "Bendiciones  (0)")):
            self.assertIn(old, en)
            self.assertIn(new, es)
        # Under "Bendiciones (0)" the Spanish agrees: ninguna.
        i = es.index("Bendiciones  (0)")
        self.assertEqual(es[i + 1], "ninguna")
        self.assertEqual(en[en.index("Blessings  (0)") + 1], "none")

    def test_the_more_lines(self):
        C = get_content()
        many = dict(self.stats,
                    dropped_items=[generate_item(C, seed=s).to_dict() for s in range(14)],
                    kill_rows=[(f"E{i}", 1) for i in range(16)],
                    other_rows=[{"name": f"P{i}", "damage": 1.0, "share": 0.0, "dps": 0.0}
                                for i in range(5)],
                    blessing_rows=[(f"B{i}", 1) for i in range(20)],
                    hero_stats={s: 0.1 for s, _k in common.STAT_ROWS})
        en, es = _both(lambda: _summary_text(many, VICTORY_COLUMNS))
        for what, word in (("items", "objetos"), ("types", "tipos"), ("sources", "fuentes"),
                           ("blessings", "bendiciones"), ("stats", "estadísticas")):
            with self.subTest(what=what):
                self.assertTrue([t for t in en if t.startswith("+") and t.endswith(f"more {what}")])
                self.assertTrue([t for t in es if t.startswith("+") and t.endswith(f"{word} más")])

    def test_an_older_summary_names_blessings_through_the_catalog(self):
        cat = get_catalog(get_content())
        old = {"time": 30.0, "blessings": {"vitality": 2, "no_such_blessing": 1}}
        en, es = _both(lambda: _summary_text(old, COLUMNS))
        self.assertIn(_both(lambda: cat.get("vitality").display_name)[0], en)
        self.assertIn(_both(lambda: cat.get("vitality").display_name)[1], es)
        self.assertIn("No Such Blessing", en)                  # unknown: the id, titled
        self.assertIn("No Such Blessing", es)

    def test_the_rarity_initial_and_the_element_words(self):
        item = {"rarity": "uncommon", "name": "x"}
        self.assertEqual(_both(lambda: run_summary._item_name(item)[0][:4]), ("[U] ", "[P] "))
        self.assertEqual(_both(lambda: run_summary._element_word("ice")), ("ice", "hielo"))
        self.assertEqual(_both(lambda: run_summary._element_word("acid")), ("acid", "acid"))

    def test_the_level_cell_is_measured_in_the_language(self):
        font = fonts.body(22)
        en, es = _both(lambda: run_summary._widest(font, run_summary._widest_level()))
        self.assertEqual(en, run_summary._widest(font, "Lv ##"))
        self.assertEqual(es, run_summary._widest(font, "Nv. ##"))


class SummaryFitTests(unittest.TestCase):
    """The Victory screen's four columns are the tightest the summary gets."""

    def setUp(self):
        _display()
        locale.set_language("es")
        f = fonts.body(22)
        space = 1600 - 2 * 60 - 3 * 20
        self.widths = run_summary.column_widths(
            space, run_summary.column_minimums(VICTORY_COLUMNS, f))
        self.f, self.small = f, fonts.body(17)

    def test_spanish_stat_labels_fit_the_hero_column(self):
        area = self.widths[3] - 56
        value = {"num": "999", "regen": "1 / 5s", "mult": "x1.25", "pct": "30%",
                 "pctplus": "+30%"}
        for stat, kind in common.STAT_ROWS:
            label = common.stat_label(stat)
            room = area - self.f.size(value[kind])[0] - 12
            with self.subTest(stat=stat, label=label):
                self.assertLessEqual(self.f.size(label)[0], room)

    def test_spanish_single_lines_fit(self):
        for text, col, font in (("summary.nothing_slain", 1, self.f),
                                ("summary.main_weapon", 3, self.small)):
            with self.subTest(key=text):
                self.assertLessEqual(font.size(locale.t(text))[0], self.widths[col] - 56)

    def test_the_spanish_time_row_fits_beside_its_record_marker(self):
        need = (self.f.size(locale.t("summary.cleared"))[0]
                + self.small.size(locale.t(run_summary.BEST_FLAG))[0] + 8 + 12
                + self.f.size("59:59")[0])
        self.assertLessEqual(need, self.widths[0] - 56)


# --- the Sanctuary ------------------------------------------------------------------------

class SanctuaryTests(unittest.TestCase):
    def setUp(self):
        _display()
        from game.game import Game
        from game.states.meta_state import MetaState
        self.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        C = self.game.content
        self.game.save.stash = [generate_item(C, seed=s, item_level=3).to_dict() for s in range(4)]
        for d in self.game.save.stash:
            if self.game.save.equipped.get(d["slot"]) is None:
                self.game.save.equipped[d["slot"]] = d["item_id"]
        self.game.save.currency = 55
        self.game.save.meta = {"constitution": 10}
        self.m = MetaState(self.game)
        self.m.enter()

    def text(self, stash=True):
        if not stash:
            self.game.save.stash = []
        seen = []
        for name in ("_title", "_h", "_f", "_small"):
            setattr(self.m, name, _Rec(getattr(self.m, name), seen))
        self.m.draw(pygame.Surface((1600, 900)))
        for name in ("_title", "_h", "_f", "_small"):
            setattr(self.m, name, getattr(self.m, name).font)
        return seen

    def test_english_and_spanish(self):
        en, es = _both(self.text)
        for old, new in (("Sanctuary", "Santuario"), ("Salvage: 55", "Chatarra: 55"),
                         ("Upgrades <", "Mejoras <"), ("Stash", "Inventario"),
                         ("TAB switch panel   -   Up/Down select   -   ENTER buy/equip   -   "
                          "U unequip   -   ESC back",
                          "TAB: cambiar panel   -   Arriba/Abajo: elegir   -   ENTER: "
                          "comprar/equipar   -   U: desequipar   -   ESC: volver"),
                         ("weapon", "arma"), ("armor", "armadura"), ("accessory", "accesorio")):
            self.assertIn(old, en)
            self.assertIn(new, es)
        self.assertIn("Constitution   10/10    MAX", en)            # the old padded line
        self.assertIn("Fortune        0/5     50", en)
        self.assertIn("Constitución   10/10    MÁX", es)
        empty = _both(lambda: self.text(stash=False))
        self.assertIn("(no items yet - beat elites / the boss)", empty[0])
        self.assertIn("(aún no hay objetos: vence a élites o al jefe)", empty[1])

    def test_an_upgrade_row_is_the_padded_line_in_any_face(self):
        """Each row is the one `f"{name:<14} {lvl}/{mx}   {cost:>4}"` string
        it always was, at the same place: pixel for pixel the old row in the
        web build's default face as much as in a monospaced one."""
        from ui import scale
        for face in (None, pygame.font.Font(None, 18)):
            if face is not None:
                self.m._f = face
            where = self.placed()
            with self.subTest(face=face):
                self.assertEqual(where["Constitution   10/10    MAX"][0],
                                 where["Fortune        0/5     50"][0])
                self.assertEqual(where["Constitution   10/10    MAX"][0], scale.px(70))

    def test_the_active_stash_panel_is_marked(self):
        self.m.panel = 1
        en, es = _both(self.text)
        self.assertIn("Stash <", en)
        self.assertIn("Upgrades", en)
        self.assertIn("Inventario <", es)
        self.assertIn("Mejoras", es)

    def test_the_description_line_is_drawn_under_its_row(self):
        from ui import scale
        where = self.placed()
        desc = locale.text(self.game.content.meta_upgrades["constitution"], "desc")
        self.assertEqual(where[desc], [scale.px(70) + scale.px(16)])
        (x, y), = self.xy["Constitution   10/10    MAX"]
        self.assertEqual(self.xy[desc], [(x + scale.px(16), y + scale.px(20))])
        band = next(r for r, k in self.m._mouse.hits._items if k == (0, 0))
        self.assertEqual(band.topleft, (x - scale.px(8), y - scale.px(4)))
        self.assertEqual(band.height, scale.px(46))

    def test_the_slot_lines_colour(self):
        self.placed()
        for t in ("weapon", "armor", "accessory", "Plain Battle Sigil"):
            self.assertEqual(self.colours[t], (150, 200, 255), t)

    def test_a_long_name_widens_the_hit_band(self):
        from ui import scale
        entry = self.game.content.meta_upgrades["constitution"]
        old = entry.get("name_es")
        entry["name_es"] = "Constitución extraordinaria y descomunal de los antiguos"
        try:
            locale.set_language("es")
            self.m.draw(pygame.Surface((1600, 900)))
            row = self.m._f.size(f"{entry['name_es']:<14} 10/10    MÁX")[0]
        finally:
            entry["name_es"] = old
        band = next(r for r, k in self.m._mouse.hits._items if k == (0, 0))
        self.assertGreater(row + scale.px(16), scale.px(440))
        self.assertEqual(band.width, row + scale.px(16))

    def test_a_long_description_widens_the_hit_band(self):
        from ui import scale
        entry = self.game.content.meta_upgrades["constitution"]
        old = entry.get("desc_es")
        entry["desc_es"] = "una descripción muy larga " * 6
        try:
            locale.set_language("es")
            self.m.draw(pygame.Surface((1600, 900)))
        finally:
            entry["desc_es"] = old
        band = next(r for r, k in self.m._mouse.hits._items if k == (0, 0))
        desc_w = self.m._small.size("una descripción muy larga " * 6)[0]
        self.assertEqual(band.width, scale.px(32) + desc_w)
        self.assertGreater(band.width, scale.px(440))
        locale.set_language("en")
        self.m.draw(pygame.Surface((1600, 900)))
        band = next(r for r, k in self.m._mouse.hits._items if k == (0, 0))
        self.assertEqual(band.width, scale.px(440))              # as it always was

    def placed(self):
        """`{text: [x, ...]}`: where each rendered text was blitted."""
        texts, keep = {}, []

        class _Tagging(_Rec):
            def render(self, text, *a, **k):
                out = self.font.render(text, *a, **k)
                texts[id(out)] = str(text)
                keep.append(out)            # alive, so no later surface reuses its id
                self_.colours[str(text)] = tuple(a[1]) if len(a) > 1 else None
                return out

        class _Surface(pygame.Surface):
            def blit(self, src, dest, *a, **k):
                if id(src) in texts:
                    where.setdefault(texts[id(src)], []).append(int(dest[0]))
                    self_.xy.setdefault(texts[id(src)], []).append((int(dest[0]), int(dest[1])))
                return super().blit(src, dest, *a, **k)

        self_ = self
        self.xy, self.colours = {}, {}
        where = {}
        for name in ("_h", "_f", "_small"):
            setattr(self.m, name, _Tagging(getattr(self.m, name), []))
        try:
            self.m.draw(_Surface((1600, 900)))
        finally:
            for name in ("_h", "_f", "_small"):
                setattr(self.m, name, getattr(self.m, name).font)
        return where

    def test_a_long_name_pushes_the_level_column(self):
        uid = "constitution"
        entry = self.game.content.meta_upgrades[uid]
        old = entry.get("name_es")
        long_name = "Constitución extraordinaria"
        entry["name_es"] = long_name
        try:
            locale.set_language("es")
            where = self.placed()
        finally:
            entry["name_es"] = old
        # Longer than the pad: its level follows it, one space on.
        self.assertIn(f"{long_name} 10/10    MÁX", where)
        self.assertEqual(where[f"{long_name} 10/10    MÁX"], where["Presteza       0/10     35"])

    def test_the_slot_column_aligns_the_item_names(self):
        from ui import scale
        for lang in ("en", "es"):
            locale.set_language(lang)
            where = self.placed()
            labels = [locale.name("slot", s) for s in ("weapon", "armor", "accessory")]
            left = {where[t][0] for t in labels}
            self.assertEqual(len(left), 1)
            item_x = left.pop() + max(self.m._small.size(t)[0] for t in labels) + scale.px(12)
            names = [t for t, xs in where.items() if item_x in xs]
            with self.subTest(lang=lang):
                self.assertEqual(sum(where[t].count(item_x) for t in names), 3)



# --- UI-014.9 critic round 1: the Spanish values, and every template drawn -----------

ES_NAMES = {
    "stat": {"max_hp": "PV máximos", "hp_regen": "Regen. PV",
             "move_speed": "Vel. movimiento", "armor": "Armadura",
             "damage_multiplier": "Daño", "melee_damage": "Daño c. a c.",
             "ranged_damage": "Daño a dist.", "attack_speed_multiplier": "Vel. ataque",
             "projectile_speed_multiplier": "Vel. proyectil", "area_multiplier": "Área",
             "crit_chance": "Prob. crítico", "crit_damage": "Daño crítico",
             "evasion_chance": "Evasión", "block_chance": "Prob. bloqueo",
             "block_strength": "Fuerza bloqueo", "pickup_radius": "Radio recogida",
             "luck": "Suerte", "xp_gain": "EXP obtenida", "gold_gain": "Oro obtenido"},
    "weapon_stat": {"damage": "Daño", "cooldown": "Recarga", "projectile_count": "Proyectiles",
                    "area": "Área", "reach": "Alcance", "pierce": "Perforación",
                    "blast_radius": "Radio de explosión", "cone_half_angle": "Cono",
                    "chain_count": "Cadenas", "weight": "Peso"},
    "forge_field": {
        "area": "área", "blast_radius": "radio de explosión", "category": "categoría",
        "cluster_count": "bombas de racimo", "cluster_damage_mult": "daño del racimo",
        "cluster_fuse": "mecha del racimo", "cluster_radius_mult": "radio del racimo",
        "cluster_speed": "velocidad del racimo", "cone_half_angle": "semiángulo del cono",
        "cooldown": "recarga", "damage": "daño",
        "hazard_dps_mult": "daño por segundo de la zona",
        "hazard_duration": "duración de la zona", "hazard_radius": "radio de la zona",
        "mine": "mina", "mine_arm_delay": "armado de la mina",
        "mine_lifetime": "duración de la mina", "orbit_radius": "radio de órbita",
        "orbit_speed": "velocidad de órbita", "pierce": "perforación",
        "projectile_count": "proyectiles", "projectile_lifetime": "duración del proyectil",
        "projectile_speed": "velocidad del proyectil", "reach": "alcance",
        "rehit_interval": "intervalo entre golpes",
        "shockwave_damage_mult": "daño de la onda", "shockwave_radius": "radio de la onda",
        "special_effect": "efecto especial", "spread_deg": "dispersión",
        "tags": "etiquetas", "targeting_mode": "apuntado",
        "twin_offset_deg": "desfase gemelo", "weight": "peso"},
    "class": {"melee": "cuerpo a cuerpo", "ranged": "a distancia", "summon": "invocación"},
    "weapon_category": {"melee": "cuerpo a cuerpo", "orbit": "órbita",
                        "projectile": "proyectil", "summon": "invocación"},
    "special": {"bomb": "bomba", "cone": "cono", "orbit": "órbita", "slam": "golpe",
                "summon": "invocación"},
    "tag": {"arcane": "arcano", "area": "área", "explosive": "explosivo",
            "melee": "cuerpo a cuerpo", "orbit": "órbita", "projectile": "proyectil",
            "ranged": "a distancia", "summon": "invocación", "elite": "élite"},
    "targeting": {"nearest": "el más cercano", "none": "ninguno"},
    "slot": {"weapon": "arma", "armor": "armadura", "accessory": "accesorio"},
}


class SpanishValueTests(unittest.TestCase):
    def test_every_spanish_name_is_pinned(self):
        es = get_content().locale["es"]
        for table, names in ES_NAMES.items():
            for i, text in names.items():
                with self.subTest(key=f"{table}.{i}"):
                    self.assertEqual(es[f"{table}.{i}"], text)
        listed = {k for k in es if k.partition(".")[0] in ES_NAMES}
        pinned = {f"{t}.{i}" for t, names in ES_NAMES.items() for i in names}
        self.assertEqual(listed, pinned)


class _Placed:
    """Records where each rendered text was blitted: `{text: [Rect]}`."""

    def __init__(self):
        self.where, self._texts, self._keep = {}, {}, []
        outer = self

        class _Surface(pygame.Surface):
            def blit(self, src, dest, *a, **k):
                if id(src) in outer._texts:
                    rect = (pygame.Rect(dest) if isinstance(dest, pygame.Rect)
                            else pygame.Rect(dest, src.get_size()))
                    outer.where.setdefault(outer._texts[id(src)], []).append(rect)
                return super().blit(src, dest, *a, **k)
        self.Surface = _Surface

    def font(self, font):
        outer = self

        class _Tag(_Rec):
            def render(self, text, *a, **k):
                out = self.font.render(text, *a, **k)
                outer._texts[id(out)] = str(text)
                outer._keep.append(out)     # alive, so no later surface reuses its id
                return out
        return _Tag(font, [])


class BuildPaneDetailTests(unittest.TestCase):
    """The Forging block, an unforged weapon, the card's "+n more", the
    synergies' "+n more", and a card whose category is not its class."""

    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        from combat.weapons import Weapon
        from combat.weapons.forge import apply_forge, get_forges
        from progression.blessings import apply_blessing
        self.C = get_content()
        self.ps = _run(full=False)
        p = self.ps.player
        # The forged three first, then the bow; the sword and hammer so the
        # hero owns every synergy's weapon.
        for wid in ("daggers", "magic_rod", "bomb", "bow", "sword", "hammer"):
            p.weapons.append(Weapon(wid, dict(self.C.weapon(wid))))
        forges = get_forges(self.C)
        apply_forge(p.weapons[0], forges.get("fan_of_blades"))
        apply_forge(p.weapons[1], forges.get("arcane_storm"))
        apply_forge(p.weapons[2], forges.get("cluster_bomb"))
        cat = get_catalog(self.C)
        for b in cat.by_id.values():
            if b.category == "synergy":
                apply_blessing(p, b)
        p.recompute()

    def pairs(self, sel):
        """`[(label, value)]` of every `kv` row, and every line, for the Build
        pane with weapon `sel` selected."""
        rows, lines = [], []
        real_kv, real_line, real_sub = common.kv, common.line, common.subheader

        def kv(surface, font, area, y, label, value, **k):
            rows.append((str(label), str(value)))
            return real_kv(surface, font, area, y, label, value, **k)

        def line(surface, font, area, y, text, **k):
            lines.append(str(text))
            return real_line(surface, font, area, y, text, **k)

        def sub(surface, font, area, y, text, *a, **k):
            lines.append(str(text))
            return real_sub(surface, font, area, y, text, *a, **k)
        s = _state(self.ps)
        s.tab = PANES.index("build")
        s.pane.sel = sel
        with (mock.patch.object(common, "kv", kv), mock.patch.object(common, "line", line),
              mock.patch.object(common, "subheader", sub)):
            s.draw(pygame.Surface((1600, 900)))
        return rows, lines

    def both(self, sel):
        return _both(lambda: self.pairs(sel))

    def test_a_forging_prints_its_changes_through_the_tables(self):
        from combat.weapons.forge import forge_changes
        for sel in (0, 1, 2):
            w = self.ps.player.weapons[sel]
            changes = forge_changes(self.C, w)
            (en_rows, _en), (es_rows, _es) = self.both(sel)
            for key, before, after in changes:
                table = build._VALUE_TABLES.get(key)

                def show(v, lang):
                    if v is None:
                        return "none" if lang == "en" else "ninguno"
                    if isinstance(v, list):
                        return ", ".join(show(x, lang) for x in v)
                    if table and isinstance(v, str):
                        return ES_NAMES[table].get(v, v) if lang == "es" else v
                    return f"{float(v):g}".replace(".", "," if lang == "es" else ".")
                with self.subTest(forge=w.forge, key=key):
                    for lang, rows in (("en", en_rows), ("es", es_rows)):
                        want = (f"+ {show(after, lang)}" if before is None
                                else f"{show(before, lang)}  ->  {show(after, lang)}")
                        label = (key.replace("_", " ") if lang == "en"
                                 else ES_NAMES["forge_field"][key])
                        self.assertIn((label, want), rows)
        # Both shapes occur: an override (before -> after) and an effect (+ x).
        self.assertTrue(any(b is None for _k, b, _a in forge_changes(self.C, self.ps.player.weapons[2])))
        self.assertTrue(any(b is not None for _k, b, _a in forge_changes(self.C, self.ps.player.weapons[0])))

    def test_the_forging_header_and_an_unforged_weapon(self):
        from combat.weapons.forge import get_forges
        f = get_forges(self.C).get("fan_of_blades")
        (_r, en), (_r2, es) = self.both(0)
        self.assertIn(f"Forging: {_both(lambda: f.display_name)[0]}  -  "
                      f"{_both(lambda: f.display_identity)[0]}", en)
        self.assertIn(f"Forja: {_both(lambda: f.display_name)[1]}  -  "
                      f"{_both(lambda: f.display_identity)[1]}", es)
        self.assertIn(f"forged  -  {_both(lambda: f.display_identity)[0]}", en)
        self.assertIn(f"con forja  -  {_both(lambda: f.display_identity)[1]}", es)
        (_r, en), (_r2, es) = self.both(3)                 # the bow: not forged
        self.assertIn("Bow  -  not forged", en)
        self.assertIn("Arco  -  sin forja", es)
        self.assertIn("Forge at 2  -  has 0", en)           # the gate, capitalised
        self.assertIn("Forja con 2  -  tiene 0", es)

    def test_a_category_that_is_not_the_class(self):
        (_r, en), (_r2, es) = self.both(0)
        self.assertIn("ranged  ·  projectile", en)          # the bow
        self.assertIn("a distancia  ·  proyectil", es)

    def test_more_synergies_than_the_list_shows(self):
        n = sum(1 for b in self.ps.player.blessings
                if get_catalog(self.C).by_id[b].category == "synergy")
        self.assertGreater(n, build.MAX_SYNERGIES)
        (_r, en), (_r2, es) = self.both(0)
        self.assertIn(f"Synergies  ({n})", en)
        self.assertIn(f"+{n - build.MAX_SYNERGIES} more synergies", en)
        self.assertIn(f"+{n - build.MAX_SYNERGIES} sinergias más", es)

    def test_a_card_with_more_numbers_than_room(self):
        from combat.weapons.forge import get_forges
        pane = build.BuildPane(common.Fonts())
        w = self.ps.player.weapons[2]                       # the bomb: many numbers
        rows = build.weapon_numbers(w)

        def draw():
            drawn, lines = [], []
            real_kv, real_line = common.kv, common.line

            def kv(surface, font, area, y, label, value, **k):
                drawn.append(str(label))
                return real_kv(surface, font, area, y, label, value, **k)

            def line(surface, font, area, y, text, **k):
                lines.append(str(text))
                return real_line(surface, font, area, y, text, **k)
            card = pygame.Rect(0, 0, 300, common.S(220))
            with mock.patch.object(common, "kv", kv), mock.patch.object(common, "line", line):
                pane._draw_card(pygame.Surface((400, 400)), card, w, 2, get_forges(self.C),
                                selected=False)
            return drawn, lines
        (en_drawn, en_lines), (es_drawn, es_lines) = _both(draw)
        shown = len([l for l in en_drawn if l != "Blessing levels"])
        self.assertLess(shown, len(rows))
        self.assertIn(f"+{len(rows) - shown} more", en_lines)
        self.assertIn(f"+{len(rows) - shown} más", es_lines)

    def test_a_weapons_crit_line(self):
        sword = _run(full=True).player.weapons[0]
        sword.bonus["crit_chance"] = 0.8                 # 1 % off prints another number
        en, es = _both(lambda: build.weapon_numbers(sword))
        self.assertIn(("Crit chance", "+80%", None), en)
        self.assertIn(("Prob. crítico", f"+80{NB}%", None), es)

    def test_the_number_rows_units_and_bonus_keys(self):
        from combat.weapons import Weapon
        sword = Weapon("sword", dict(self.C.weapon("sword")))
        bow = Weapon("bow", dict(self.C.weapon("bow")))
        bow.bonus["projectile_count"] = 2.0
        rows = {label: (base, now) for label, base, now in build.weapon_numbers(sword)}
        self.assertEqual(rows["Cooldown"][0], f"{float(sword.definition['cooldown']):g}s")
        self.assertEqual(rows["Cone"][0], f"{float(sword.definition['cone_half_angle']):g}°")
        base = float(bow.definition["projectile_count"])
        rows = {label: (b, now) for label, b, now in build.weapon_numbers(bow)}
        self.assertEqual(rows["Projectiles"], (f"{base:g}", f"{base + 2:g}"))

    def test_every_bonus_key_adds_to_its_number(self):
        """A definition carrying every number (no weapon carries all of
        them; none carries chains): each bonus key adds to its own row."""
        # The bonus keys the fire path writes, spelled out (not read back
        # from `_NUMBERS`, which is what is under test). The blast radius has
        # the Bomb's own rule, tested above.
        keys = {k: k for k in ("damage", "projectile_count", "area", "pierce",
                               "cone_half_angle", "chain_count", "weight")}
        w = SimpleNamespace(definition={k: 10.0 for k, _b, _kind in build._NUMBERS},
                            bonus={b: 3.0 for b in keys.values()})
        rows = {label: now for label, _base, now in build.weapon_numbers(w)}
        for k in keys:
            with self.subTest(key=k):
                self.assertEqual(rows[OLD_WEAPON_STATS[k]], "13°" if k == "cone_half_angle" else "13")
        self.assertIsNone(rows["Reach"])                   # no bonus key: never changes
        self.assertEqual(rows["Cooldown"], None)

    def test_a_title_that_exactly_fits_is_not_stepped(self):
        from combat.weapons.forge import get_forges
        pane = build.BuildPane(common.Fonts())
        w = self.ps.player.weapons[3]
        title = f"{w.name}  Lv {w.level}"
        card = pygame.Rect(0, 0, pane.f.title.size(title)[0] + common.S(32), common.S(300))
        with mock.patch.object(build, "fit_font", wraps=build.fit_font) as fit:
            pane._draw_card(pygame.Surface((600, 400)), card, w, 2, get_forges(self.C),
                            selected=False)
        fit.assert_not_called()
        card.width -= 1
        with mock.patch.object(build, "fit_font", wraps=build.fit_font) as fit:
            pane._draw_card(pygame.Surface((600, 400)), card, w, 2, get_forges(self.C),
                            selected=False)
        fit.assert_called_once()

    def test_a_hero_synergy_in_spanish(self):
        bdef = SimpleNamespace(category="synergy", weapon=None, requires_weapons=("bow",),
                               title=lambda lvl: "Pacto", describe=lambda lvl: "texto")
        player = SimpleNamespace(blessings={"pact": 1})
        catalog = SimpleNamespace(by_id={"pact": bdef})
        rows = _both(lambda: build.synergy_rows(player, catalog, {"bow": "Arco"}))
        self.assertEqual(rows, ([("Hero + Arco  -  Pacto", "texto")],
                                [("Héroe + Arco  -  Pacto", "texto")]))

    def test_the_card_title_size(self):
        """28 px heading at 1600; on a 1280x720 surface at scale 1 (the old
        web profile, before UI-016: the narrowest cards the pane has had) a
        title too wide for its card steps down in the same heading face.
        The web profile now draws the pane at 0.8, where the titles fit
        (`WebProfileFitTests`)."""
        from ui.run_status import common as cm
        self.assertEqual(cm.TITLE_PX, 28)
        probe = "Wim  Lv 10"
        self.assertEqual(cm.Fonts().title.size(probe), fonts.heading(28).size(probe))
        chose = []
        real = build.fit_font

        def fit(role, px, text, room, **k):
            font = real(role, px, text, room, **k)
            chose.append((role, px, font))
            return font
        ps = _run(full=True)
        for w in ps.player.weapons:
            w.level = 10
        locale.set_language("es")
        s = _state(ps)
        s.tab = PANES.index("build")
        with mock.patch.object(build, "fit_font", fit):
            s.draw(pygame.Surface((1280, 720)))
        steps = [fonts.heading(k).size(probe) for k in range(20, 28)]
        self.assertTrue(chose)
        for role, px, font in chose:
            self.assertIs(role, fonts.heading)
            self.assertEqual(px, 28)
            self.assertIn(font.size(probe), steps)

    def test_ids_a_table_does_not_list(self):
        w = self.ps.player.weapons[3]
        w.definition["special_effect"] = "arc_nova"
        (_r, en), (_r2, es) = self.both(3)
        self.assertTrue([t for t in en if t.endswith("  ·  arc nova")], en)
        self.assertTrue([t for t in es if t.endswith("  ·  arc nova")], es)
        with mock.patch.object(build, "forge_changes", lambda c, w: [("odd_key", 1, 2)]):
            (rows, _l), (es_rows, _l2) = self.both(0)
        self.assertIn(("odd key", "1  ->  2"), rows)
        self.assertIn(("odd key", "1  ->  2"), es_rows)


class BlessingsPaneListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def text(self, ps, sel=0):
        s = _state(ps)
        s.tab = PANES.index("blessings")
        seen = []
        for name in ("row", "small", "sub", "title"):
            setattr(s._fonts, name, _Rec(getattr(s._fonts, name), seen))
        s.pane.sel = sel
        s.draw(pygame.Surface((1600, 900)))
        rows = [k for _r, k in s._mouse.hits._items if isinstance(k, tuple) and k[0] == "row"]
        return seen, s.pane, len(rows)

    def test_the_owner_of_a_hero_blessing(self):
        ps = _run(full=True)
        en, es = _both(lambda: self.text(ps)[0])
        self.assertIn("Hero", en)                              # vitality has no weapon
        self.assertIn("Héroe", es)

    def test_an_unknown_blessing_is_its_id_and_the_hero_owns_it(self):
        ps = _run(full=False)
        ps.player.blessings["storm_crown"] = 1
        en, es = _both(lambda: self.text(ps)[0])
        self.assertIn("Storm Crown I", en)
        self.assertIn("Hero", en)
        self.assertIn("Héroe", es)

    def test_a_scrolled_list(self):
        ps = _run(full=False)
        for b in get_catalog(get_content()).by_id.values():
            ps.player.blessings[b.id] = 1                 # far more than the list shows
        total = len(ps.player.blessings)

        def draw():
            seen, pane, shown = self.text(ps, sel=total // 2)
            return seen, pane.scroll, shown
        (en, scroll, shown), (es, scroll_es, shown_es) = _both(draw)
        self.assertGreater(scroll, 0)
        self.assertLess(scroll + shown, total)
        self.assertIn("^ more", en)
        self.assertIn("^ más", es)
        self.assertIn(f"+{total - scroll - shown} more  (scroll)", en)
        self.assertIn(f"+{total - scroll_es - shown_es} más  (desplaza)", es)


class ItemLineTests(unittest.TestCase):
    def test_a_tag_damage_affix(self):
        from ui.run_status.overview import item_lines
        item = SimpleNamespace(base_stat="armor", base_op="flat", base_value=2.0,
                               affixes=[SimpleNamespace(kind="tag_damage", value=0.8,
                                                        tag="elite")],
                               unique_effect=None)
        en, es = _both(lambda: item_lines(item))
        self.assertEqual(en, ["+2 Armor", "+80% damage vs elite"])
        self.assertEqual(es, ["+2 Armadura", f"+80{NB}% de daño contra élite"])


class SummaryRowTests(unittest.TestCase):
    """`_kv`'s geometry: a value steps down, then both step, then the
    row takes two lines; a label is never trimmed (UI-014.11)."""

    def setUp(self):
        _display()
        self.panel = RunSummaryPanel({})
        from ui import scale
        self.S = scale.px

    def row(self, label, value, width, flag=""):
        placed = _Placed()
        self.panel._row = placed.font(self.panel._row)
        self.panel._small = placed.font(self.panel._small)
        stepped = []
        real = run_summary.uitext.fit_font

        def fit(role, px, text, room, **k):
            font = real(role, px, text, room, **k)
            stepped.append((text, font, room))
            return placed.font(font)
        real_cached = run_summary.uitext.cached_font

        def cached(role, px, **k):
            return placed.font(real_cached(role, px, **k))
        area = pygame.Rect(0, 0, width, 400)
        with mock.patch.object(run_summary.uitext, "fit_font", fit), \
                mock.patch.object(run_summary.uitext, "cached_font", cached):
            self.last_y = self.panel._kv(placed.Surface((width, 400)), area, 20, label, value,
                                         flag=flag)
        self.panel._row = self.panel._row.font
        self.panel._small = self.panel._small.font
        return placed.where, stepped

    def test_the_row_font_is_22(self):
        probe = "Kills 845 (83/min)"
        self.assertEqual(run_summary._ROW_PX, 22)
        self.assertEqual(self.panel._row.size(probe), fonts.body(22).size(probe))

    def test_a_value_that_fits_is_not_stepped(self):
        where, stepped = self.row("Elements", "fire, wind", 226)
        self.assertEqual(stepped, [])
        self.assertIn("Elements", where)

    def test_a_value_steps_down_to_leave_the_label_whole(self):
        label, value, width = "Elementos", "fuego, viento", 226
        where, stepped = self.row(label, value, width)
        self.assertEqual(len(stepped), 1)
        text, font, room = stepped[0]
        label_w = self.panel._row.size(label)[0]
        self.assertEqual(room, width - label_w - self.S(12))
        self.assertLessEqual(font.size(value)[0], room)
        self.assertLess(font.get_height(), self.panel._row.get_height())
        self.assertIn(label, where)                                  # whole
        self.assertLessEqual(where[label][0].right + self.S(12), where[value][0].left)

    def test_a_label_too_long_for_the_row_takes_its_own_line(self):
        """UI-014.11: a label is never trimmed. Its marker stays beside it,
        the value goes to the next line, right-aligned as ever."""
        label, value, width = "A very long label indeed", "845   (83/min)", 226
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertFalse([t for t in where if t.endswith("...")])
        self.assertIn(label, where)
        (lab,), (best,), (val,) = where[label], where["best"], where[value]
        self.assertLessEqual(lab.right, best.left)
        self.assertLessEqual(best.right, width)
        self.assertGreater(val.top, lab.bottom)
        self.assertEqual(val.right, width)
        self.assertEqual(self.last_y, 20 + 2 * self.S(run_summary.ROW_STEP))

    def test_the_label_and_the_value_both_step_before_two_lines(self):
        """"Bajas récord 3877 (129/min)", the Victory Run column at 1600: the
        value alone cannot step far enough to leave "Bajas" whole at the row
        size, but both stepped share the line (UI-014.11)."""
        label, value, width = "Bajas", "3877   (129/min)", 228
        locale.set_language("es")
        self.addCleanup(locale.set_language, locale.DEFAULT)
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertEqual(set(where), {label, "récord", value})
        (lab,), (best,), (val,) = where[label], where["récord"], where[value]
        self.assertLess(abs(lab.centery - val.centery), self.S(6))    # one line
        self.assertLessEqual(best.right + self.S(12), val.left)
        self.assertEqual(self.last_y, 20 + self.S(run_summary.ROW_STEP))

    def test_four_elements_go_under_their_label(self):
        """No step leaves "Elementos" whole beside the four Spanish elements:
        the value takes the next line, stepped to the column. English's four
        share their line, both stepped."""
        value, width = "fuego, hielo, trueno, viento", 226
        self.assertGreater(self.panel._row.size(value)[0], width)
        where, _stepped = self.row("Elementos", value, width)
        (lab,), (val,) = where["Elementos"], where[value]
        self.assertGreater(val.top, lab.bottom)
        self.assertGreaterEqual(val.left, 0)
        self.assertLessEqual(val.right, width)
        where, _stepped = self.row("Elements", "fire, ice, thunder, wind", width)
        (lab,), (val,) = where["Elements"], where["fire, ice, thunder, wind"]
        self.assertLess(abs(lab.centery - val.centery), self.S(6))
        self.assertLessEqual(lab.right + self.S(12), val.left)

    def test_a_value_that_exactly_fits_is_not_stepped(self):
        label, value = "Elements", "fire, wind"
        width = self.panel._row.size(label)[0] + self.S(12) + self.panel._row.size(value)[0]
        where, stepped = self.row(label, value, width)
        self.assertEqual(stepped, [])

    def test_a_step_that_exactly_fits_is_taken(self):
        label, value = "Elementos", "fuego, viento"
        target = fonts.body(20)
        width = self.panel._row.size(label)[0] + self.S(12) + target.size(value)[0]
        where, stepped = self.row(label, value, width)
        self.assertEqual(len(stepped), 1)
        self.assertEqual(where[value][0].width, target.size(value)[0])
        self.assertIn(label, where)

    def test_a_marker_row_with_no_room_for_its_label_takes_two_lines(self):
        """Room for the marker and the value at 17 px, none for "Enemigos"
        beside them: the marker stays with its label, the value goes to the
        next line at the size that fits the column."""
        label, value = "Enemigos", "99999   (1666/min)"
        marker = self.panel._small.size("best")[0]
        extra = self.S(12) + marker + self.S(8)
        width = extra + fonts.body(17).size(value)[0]
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertIn("best", where)
        self.assertIn(label, where)
        fitted = run_summary.uitext.fit_font(fonts.body, 22, value, width)
        self.assertEqual(where[value][0].width, fitted.size(value)[0])
        self.assertGreater(where[value][0].top, where["best"][0].bottom)

    def test_a_marker_that_leaves_no_room_goes_before_the_label(self):
        """So narrow that even the smallest label and the marker do not share
        a line: the marker gives way, the label keeps its words, the value
        its size on the line below."""
        label, value = "Enemigos", "999"
        smallest = run_summary.uitext.fit_font(fonts.body, 22, label, 0)
        width = smallest.size(label)[0] + 2
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertNotIn("best", where)
        self.assertIn(label, where)
        self.assertGreater(where[value][0].top, where[label][0].bottom)

    def test_a_two_line_value_sits_one_row_below_at_the_right_edge(self):
        label, value = "Impuestos", "999"
        width = self.panel._row.size(label)[0] + 4
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertEqual(where[value][0].right, width)
        self.assertEqual(self.last_y, 20 + 2 * self.S(run_summary.ROW_STEP))

    def test_a_word_wider_than_the_column_is_trimmed_on_its_own_line(self):
        """60 px: the value wraps under its label, "99999" whole; "(1666/min)"
        is wider than the column even at the smallest step, so it alone
        trims. Nothing leaves the column."""
        label, value, width = "Enemigos", "99999   (1666/min)", 60
        self.assertGreater(fonts.body(15).size(value)[0], width)      # the premise
        where, _stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        self.assertIn("99999", where)
        self.assertTrue([t for t in where if t.startswith("(") and t.endswith("...")])
        for rects in where.values():
            for r in rects:
                self.assertGreaterEqual(r.left, 0)
                self.assertLessEqual(r.right, width)

    def test_the_marker_counts_against_the_room(self):
        label, value, width = "Kills", "845   (83/min)", 226
        where, stepped = self.row(label, value, width, flag=run_summary.BEST_FLAG)
        marker_w = self.panel._small.size("best")[0]
        self.assertEqual(stepped[0][2], width - self.panel._row.size(label)[0]
                         - self.S(12) - marker_w - self.S(8))
        self.assertIn("Kills", where)
        self.assertLessEqual(where["best"][0].right, where[value][0].left)


class SummaryPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def pairs(self, stats, columns=VICTORY_COLUMNS):
        def go():
            pairs = []
            text = _summary_text(stats, columns, pairs=pairs)
            return pairs, text
        return _both(go)

    def test_the_hero_rows_and_both_totals(self):
        stats = dict(_summary_stats(), unlocked_elements=[])
        (en, en_text), (es, es_text) = self.pairs(stats)
        self.assertIn(("Hero", "Aegis"), en)
        self.assertIn(("Héroe", "Aegis"), es)
        self.assertIn(("Elements", "none"), en)
        self.assertIn(("Elementos", "ninguno"), es)
        self.assertIn(("Total", "57"), en)                       # the kills' total
        self.assertIn(("Total", "57"), es)
        self.assertEqual(en_text.count("Total"), 2)              # and the damage total
        self.assertEqual(es_text.count("Total"), 2)
        self.assertEqual(en_text.count("100%"), 1)               # the total's share only
        self.assertEqual(es_text.count(f"100{NB}%"), 1)

    def test_a_long_weapon_name_stops_short_of_its_level(self):
        stats = dict(_summary_stats(), weapon_rows=[
            {"name": "An extraordinarily long forged weapon name", "level": 12,
             "damage": 1234567.0, "share": 1.0, "dps": 99.9}])
        for lang, level in (("en", "Lv 12"), ("es", "Nv. 12")):
            locale.set_language(lang)
            placed = _Placed()
            panel = RunSummaryPanel(stats)
            panel._row = placed.font(panel._row)
            panel._small = placed.font(panel._small)
            panel.draw(placed.Surface((1600, 900)), None, 178, 762, columns=VICTORY_COLUMNS)
            names = [t for t in placed.where if t.startswith("An extra")]
            with self.subTest(lang=lang):
                self.assertEqual(len(names), 1)
                self.assertTrue(names[0].endswith("..."))
                # The name's room ends a level cell (measured in this
                # language, "Nv. ##") and a gap short of the level's edge.
                from ui import scale
                x_lv = placed.where[level][0].right
                cell = run_summary._widest(panel._row, locale.t("summary.level_value", n="##"))
                self.assertLessEqual(placed.where[names[0]][0].right,
                                     x_lv - cell - scale.px(run_summary._CELL_GAP))
        locale.set_language(locale.DEFAULT)


class ShareCellTests(unittest.TestCase):
    """The weapons table's share cell ("100%", "100 %" in Spanish): a
    translation keeps English's gap before it -- on every row, the total
    included -- and English stays at `_DAMAGE_X` at every render scale
    (UI-014.10)."""

    SCALES = (0.6, 0.7, 0.75, 0.8, 720 / 900, 0.9, 1.0, 1.2, 1.25, 1.5, 1.6, 1.8, 2.0, 2.4, 2.7)

    def setUp(self):
        _display()
        self.addCleanup(locale.set_language, locale.DEFAULT)

    def gaps(self, lang, scale_, stats):
        """`[(damage text, gap to its share)]` per row, as drawn."""
        from game import config
        from ui import scale
        with mock.patch.object(config, "RENDER_SCALE", scale_):
            locale.set_language(lang)
            placed = _Placed()
            panel = RunSummaryPanel(stats)
            panel._row = placed.font(panel._row)
            w, h = round(1600 * scale_), round(900 * scale_)
            panel.draw(placed.Surface((w, h)), None, scale.px(178), scale.px(762),
                       columns=VICTORY_COLUMNS)
        pct = "%" if lang == "en" else "\u00a0%"
        shares = [(r, t) for t, rs in placed.where.items() if t.endswith(pct) for r in rs]
        grouped = r"\d{1,3}(,\d{3})+" if lang == "en" else r"\d{1,3}(\.\d{3})+"
        damages = sorted(((r, t) for t, rs in placed.where.items() if re.fullmatch(grouped, t)
                          for r in rs), key=lambda x: x[0].centery)
        out = []
        for d, _dt in damages:
            # The share on the damage figure's own row, right of it.
            (sr, st), = [(r, t) for r, t in shares if r.centery == d.centery and r.left > d.left]
            out.append((st, sr.left - d.right))
        return out

    def test_a_translation_keeps_englishs_gap_on_every_row(self):
        """Two weapons at half each: the rows draw "50 %", the total "100 %"."""
        stats = dict(_summary_stats(), weapon_rows=[
            {"name": "Sword", "level": 5, "damage": 617283.0, "share": 0.5, "dps": 9.9},
            {"name": "Bow", "level": 3, "damage": 617284.0, "share": 0.5, "dps": 9.9}],
            other_rows=[], damage_dealt=1234567.0)
        for scale_ in (1.0, 0.8, 1.5):
            en, es = self.gaps("en", scale_, stats), self.gaps("es", scale_, stats)
            with self.subTest(scale=scale_):
                self.assertEqual([t for t, _g in es], ["50\u00a0%", "50\u00a0%", "100\u00a0%"])
                self.assertEqual([g for _t, g in en], [g for _t, g in es])
        # At the design scale the gap is the design's.
        from ui import scale
        self.assertGreaterEqual(min(g for _t, g in self.gaps("es", 1.0, stats)),
                                scale.px(run_summary._CELL_GAP))

    def test_english_keeps_the_design_offset_at_every_scale(self):
        from game import config
        from ui import scale
        for scale_ in self.SCALES:
            with self.subTest(scale=scale_), mock.patch.object(config, "RENDER_SCALE", scale_):
                font = fonts.body(22)
                self.assertEqual(run_summary._damage_offset(font, [1.0, 0.5, 0.98]),
                                 scale.px(run_summary._DAMAGE_X))

    def test_spanish_widens_by_its_share_alone(self):
        from ui import scale
        font = fonts.body(22)
        locale.set_language("es")
        extra = font.size("100\u00a0%")[0] - font.size("100%")[0]
        self.assertGreater(extra, 0)
        self.assertEqual(run_summary._damage_offset(font, [1.0, 0.5]),
                         scale.px(run_summary._DAMAGE_X) + extra)
        es_min = run_summary.weapons_min_width(font)
        locale.set_language("en")
        en_min = run_summary.weapons_min_width(font)
        # The Spanish floor: English's, the wider share, and the wider
        # level cell ("Nv. ##") -- nothing else.
        level = (run_summary._widest(font, "Nv. ##") - run_summary._widest(font, "Lv ##"))
        self.assertEqual(es_min, en_min + extra + level)


class VictoryAt1280Tests(unittest.TestCase):
    """The web profile draws the summary's columns at 1280x720 (the
    interface at 0.8, between the end screen's own panel rows):
    every text stays inside the area it is laid out in -- a row inside its
    column's content area, a title inside its ribbon -- and none sits on
    another, in either language, three columns or four: ribbon titles,
    subheaders with two-digit counts, and a kill record whose value takes
    the whole row."""

    def setUp(self):
        _display()
        self.addCleanup(locale.set_language, locale.DEFAULT)

    def texts(self, stats, columns=VICTORY_COLUMNS, *, narrow=False):
        """`[(text, rect)]` drawn, and the `(ribbon, area)` of each column,
        as `_column` laid them out: under the web profile, between the end
        screen's panel rows; or, `narrow`, on a 1280x720 surface at scale 1
        -- the old web profile, before UI-016, and no shipped configuration
        now: the tightest columns the panel has had to hold, kept so its
        step-down and trim paths stay exercised."""
        from tests.web_profile import web_profile
        from ui import scale
        from ui.end_screen import PANEL_BOTTOM, PANEL_TOP
        if narrow:
            return self._texts(stats, columns, 142, 610)     # the panel rows at 0.8
        with web_profile():
            return self._texts(stats, columns, scale.px(PANEL_TOP), scale.px(PANEL_BOTTOM))

    def _texts(self, stats, columns, top, bottom):
        placed = _Placed()
        panel = RunSummaryPanel(stats)
        for name in ("_ribbon", "_sub", "_row", "_small"):
            setattr(panel, name, placed.font(getattr(panel, name)))
        real_fit, real_column = run_summary.uitext.fit_font, RunSummaryPanel._column
        real_ribbon = run_summary.widgets.draw_ribbon
        ribbons, areas = [], []

        def ribbon(surface, assets, rect, *a, **k):
            ribbons.append(pygame.Rect(rect))
            return real_ribbon(surface, assets, rect, *a, **k)

        def column(this, *a, **k):
            areas.append(real_column(this, *a, **k))
            return areas[-1]
        with (mock.patch.object(run_summary.uitext, "fit_font",
                                lambda *a, **k: placed.font(real_fit(*a, **k))),
              mock.patch.object(run_summary.widgets, "draw_ribbon", ribbon),
              mock.patch.object(RunSummaryPanel, "_column", column)):
            panel.draw(placed.Surface((1280, 720)), None, top, bottom, columns=columns)
        texts = [(t, r) for t, rects in placed.where.items() for r in rects]
        return texts, list(zip(ribbons, areas, strict=True))

    def stats(self):
        C = get_content()
        return dict(_summary_stats(), kills=999, time=3599.0,
                    new_records=["kills", "time", "damage_dealt"],
                    unlocked_elements=["fire", "ice", "thunder", "wind"],
                    dropped_items=[generate_item(C, seed=s).to_dict() for s in range(14)],
                    blessing_rows=[(f"B{i}", 1) for i in range(12)])

    def test_every_text_stays_in_its_area_and_alone(self):
        stats = self.stats()
        for (lang, columns), narrow in itertools.product(
                (("en", VICTORY_COLUMNS), ("es", VICTORY_COLUMNS), ("en", COLUMNS),
                 ("es", COLUMNS)), (False, True)):
            locale.set_language(lang)
            texts, boxes = self.texts(stats, columns, narrow=narrow)
            with self.subTest(lang=lang, columns=len(columns), narrow=narrow):
                for t, r in texts:
                    ribbon, area = next((b, a) for b, a in boxes
                                        if b.left - 20 <= r.centerx <= b.right + 20)
                    box = ribbon if r.bottom <= area.top else area
                    self.assertGreaterEqual(r.left, box.left, t)
                    self.assertLessEqual(r.right, box.right, t)
                for i, (t, r) in enumerate(texts):
                    for u, q in texts[i + 1:]:
                        self.assertFalse(r.colliderect(q) and r.clip(q).width > 1
                                         and r.clip(q).height > 4, (t, u))

    def test_a_subheader_steps_then_trims_words_but_keeps_its_count(self):
        """On the narrow surface; under the web profile the subheader fits
        whole in both languages (the next test)."""
        stats = self.stats()
        locale.set_language("en")
        texts, _boxes = self.texts(stats, narrow=True)
        drawn = [t for t, _r in texts]
        # English steps down and stays whole.
        self.assertIn("Items acquired  (14)", drawn)
        locale.set_language("es")
        texts, _boxes = self.texts(stats, narrow=True)
        heads = [t for t, _r in texts if t.startswith("Objetos")]
        self.assertEqual(len(heads), 1)
        self.assertTrue(heads[0].endswith("...  (14)"), heads[0])   # words gave way, the count did not

    def test_under_the_web_profile_the_subheader_is_whole(self):
        stats = self.stats()
        for lang, head in (("en", "Items acquired  (14)"), ("es", "Objetos obtenidos  (14)")):
            locale.set_language(lang)
            with self.subTest(lang=lang):
                self.assertIn(head, [t for t, _r in self.texts(stats)[0]])


class WebProfileFitTests(unittest.TestCase):
    """The 1280x720 web profile (the interface at 0.8), four weapons:
    nothing on the Build pane trims in Spanish (UI-014.9)."""

    def drawn_and_trimmed(self, ps):
        """(everything the Build pane drew, what it trimmed) at 1280x720, in
        Spanish, with `ellipsize` watched."""
        drawn, trimmed = [], []
        real = common.uitext.ellipsize

        def ellipsize(font, text, room):
            out = real(font, text, room)
            drawn.append(text)
            if out != text:
                trimmed.append(text)
            return out
        from tests.web_profile import web_profile
        locale.set_language("es")
        with web_profile():
            s = _state(ps)
            s.tab = PANES.index("build")
            with mock.patch.object(common.uitext, "ellipsize", ellipsize):
                s.draw(pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))
        return drawn, trimmed

    def test_four_cards_at_level_10_keep_their_titles(self):
        _display()
        ps = _run(full=True)
        for w in ps.player.weapons:
            w.level = 10
        drawn, trimmed = self.drawn_and_trimmed(ps)
        titles = [t for t in drawn if "  Nv. 10" in t]
        self.assertEqual(len(titles), 4)
        self.assertEqual([t for t in trimmed if t in titles], [])

    def test_the_empty_synergy_line_fits(self):
        _display()
        from combat.weapons import Weapon
        ps = _run(full=False)
        for wid in ("sword", "daggers", "bow", "spirit_wolf"):
            ps.player.weapons.append(Weapon(wid, dict(get_content().weapon(wid))))
        drawn, trimmed = self.drawn_and_trimmed(ps)
        line = "ninguna aún  -  una sinergia une dos armas"
        self.assertIn(line, drawn)
        self.assertNotIn(line, trimmed)


if __name__ == "__main__":
    unittest.main()
