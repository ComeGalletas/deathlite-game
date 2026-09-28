"""The game reads its data text through `game.locale` (UI-014.5).

Two properties are checked for every reader: in Spanish it shows the `_es`
text, and it follows a language switch at once. The language can change mid
run from the pause menu, so a name copied once at load, spawn or first kill
would stay in the old language; each reader here is switched after its
object exists and must follow.

The last class is a sweep: no game code outside a short, reasoned allowlist
reads a data text field (`d["name"]`, `d.get("desc")`, ...) without going
through `locale.text`. The allowlist counts occurrences, so a second
identical read in an allowlisted file is caught.

The sweep cannot see a read through a helper or a variable key
(`need("name")`, `d[key]`, `itemgetter("name")`). The game has two:
- `progression/blessings/catalog.py` `need("name")` / `need("description")`:
  the def's English identity. The player reads `display_name` and `describe`.
- `ui/run_summary.py` `widest_weapon_name` reads `v[k]` over every
  language's name, to measure the column, never to show.
(`combat/weapons/forge.py` loops over the required keys, and
`game/content.py` checks `BUFF_FIELDS`, but only to check that they exist.) Nor can it see an attribute read of an English
identity (`BlessingDef.name`, `ForgeDef.name` / `.identity` /
`.description`) where `display_*` belongs; the Spanish-run tests
(`tests/playing/test_spanish_run.py`) draw each such surface instead. A
reviewer, not this test, guards those forms.
"""
import ast
import os
import unittest
from collections import Counter
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import Weapon
from combat.weapons.forge import apply_forge, get_forges
from entities.boss import Boss
from entities.enemy import Enemy
from entities.player import Player
from game import locale
from game.content import get_content
from game.states.playing.core.run_ledger import RunLedger
from progression.blessings.catalog import get_catalog
from progression.blessings.offer import (blessing_offers, forge_offers_for,
                                         grant_offers)

C = get_content()
ROOT = Path(__file__).resolve().parents[2]


def hero(*wids):
    p = Player(0, 0)
    p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
    return p


class Spanish(unittest.TestCase):
    """Each test starts in English and may switch; English is restored."""

    def setUp(self):
        pygame.init()
        locale.set_language("en")

    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    def switch_shows(self, read, english, spanish):
        """`read()` gives `english`, then `spanish` after a switch, then
        `english` again: nothing was copied at construction."""
        self.assertEqual(read(), english)
        locale.set_language("es")
        self.assertEqual(read(), spanish)
        locale.set_language("en")
        self.assertEqual(read(), english)


class WeaponTests(Spanish):
    def test_a_weapon_name_follows_the_language(self):
        w = Weapon("sword", C.weapon("sword"))
        self.switch_shows(lambda: w.name, "Sword", "Espada")

    def test_a_forged_weapon_shows_the_forge(self):
        w = Weapon("sword", dict(C.weapon("sword")))
        apply_forge(w, get_forges(C).get("whirlwind"))
        self.switch_shows(lambda: w.name, "Whirlwind", "Torbellino")

    def test_a_definition_without_a_name_shows_its_id(self):
        w = Weapon("sword", {k: v for k, v in C.weapon("sword").items()
                             if not k.startswith("name")})
        locale.set_language("es")
        self.assertEqual(w.name, "sword")


class CreatureTests(Spanish):
    def test_an_enemy_name_follows_the_language(self):
        e = Enemy("spider", C.enemy("spider"), 0.0, 0.0)
        self.switch_shows(lambda: e.name, "Skitter", "Escurridiza")

    def test_a_boss_name_follows_the_language(self):
        b = Boss("the_first_hunger", C.boss("the_first_hunger"), 0.0, 0.0)
        self.switch_shows(lambda: b.name, "The First Hunger", "El Hambre Primigenia")

    def test_a_creature_without_a_name_shows_its_id(self):
        # Content does not require `name` on enemies or bosses.
        cfg = {k: v for k, v in C.enemy("spider").items() if not k.startswith("name")}
        bcfg = {k: v for k, v in C.boss("the_first_hunger").items()
                if not k.startswith("name")}
        locale.set_language("es")
        self.assertEqual(Enemy("spider", cfg, 0.0, 0.0).name, "spider")
        self.assertEqual(Boss("the_first_hunger", bcfg, 0.0, 0.0).name, "the_first_hunger")

    def test_the_kill_list_reads_names_when_shown(self):
        # A first kill in English, the list read after a switch to Spanish.
        led = RunLedger()
        led.kill(Enemy("spider", C.enemy("spider"), 0.0, 0.0))
        led.kill(Boss("the_first_hunger", C.boss("the_first_hunger"), 0.0, 0.0))
        self.switch_shows(lambda: dict(led.kill_rows()),
                          {"Skitter": 1, "The First Hunger": 1},
                          {"Escurridiza": 1, "El Hambre Primigenia": 1})


class BlessingTests(Spanish):
    def setUp(self):
        super().setUp()
        self.b = get_catalog(C).get("sword_heavy_blade")

    def test_title_and_card_text_follow_the_language(self):
        self.switch_shows(lambda: self.b.title(2), "Heavy Blade II", "Hoja pesada II")
        self.switch_shows(
            lambda: self.b.describe(1),
            "Swings 15% slower, hits for +5 more and shoves +10 harder.",
            "Golpea un 15 % más despacio, hace +5 más de daño y empuja +10 más fuerte.")

    def test_the_english_name_stays_the_identity(self):
        # `name` is what the dev menu sorts on and the logs print.
        locale.set_language("es")
        self.assertEqual(self.b.name, "Heavy Blade")
        self.assertEqual(self.b.display_name, "Hoja pesada")

    def test_a_hand_built_def_falls_back_to_its_english(self):
        from dataclasses import replace
        bare = replace(self.b, texts={})
        locale.set_language("es")
        self.assertEqual(bare.title(1), "Heavy Blade I")
        self.assertTrue(bare.describe(1).startswith("Swings 15% slower"))

    def test_a_hand_built_forge_def_falls_back_to_its_english(self):
        from dataclasses import replace
        bare = replace(get_forges(C).get("greatsword"), texts={})
        locale.set_language("es")
        self.assertEqual((bare.display_name, bare.display_identity),
                         ("Greatsword", "Crowd breaker"))
        self.assertTrue(bare.display_description.startswith("A slow"))


class ForgeDefTests(Spanish):
    def test_the_forge_card_text_follows_the_language(self):
        f = get_forges(C).get("greatsword")
        self.switch_shows(lambda: (f.display_name, f.display_identity),
                          ("Greatsword", "Crowd breaker"), ("Mandoble", "Rompehordas"))
        locale.set_language("es")
        self.assertTrue(f.display_description.startswith("Una hoja lenta"))
        self.assertEqual(f.name, "Greatsword")               # the identity


class OfferTests(Spanish):
    """The level-up cards are built in the language in use when they are
    rolled; the overlays that show them cannot open the pause menu, so a
    card never outlives a language switch."""

    def test_blessing_cards_in_spanish(self):
        locale.set_language("es")
        cards = {u.id: u for u in blessing_offers(hero("sword"), C)}
        card = cards["sword_heavy_blade"]
        self.assertEqual(card.title, "Hoja pesada I")
        self.assertIn("más despacio", card.description)
        self.assertIn("Espada", card.tags)

    def test_forge_cards_in_spanish(self):
        locale.set_language("es")
        p = hero("sword")
        cards = {u.id: u for u in forge_offers_for(p, C, p.weapons[0])}
        card = cards["forge:greatsword"]
        self.assertEqual(card.title, "Mandoble")
        self.assertTrue(card.description.startswith("Una hoja lenta"), card.description)
        self.assertTrue(card.description.endswith("(Rompehordas.)"))
        self.assertIn("Espada", card.tags)

    def test_grant_cards_carry_the_spanish_name_and_text(self):
        import random
        locale.set_language("es")
        cards = {u.id: u for u in grant_offers(hero("sword"), C, random.Random(1))}
        card = cards["grant:bow"]
        self.assertIn("Arco", card.title)
        self.assertEqual(card.description, C.weapon("bow")["description_es"])


class ScreenHelperTests(Spanish):
    def test_the_build_pane_forge_line(self):
        from ui.run_status.build import gate_text
        w = Weapon("sword", dict(C.weapon("sword")))
        apply_forge(w, get_forges(C).get("whirlwind"))
        locale.set_language("es")
        self.assertEqual(gate_text(w, 2, get_forges(C)), "forged  -  Área defensiva")

    def test_the_hero_select_weapon_name(self):
        from game.states.character_select_state import CharacterSelectState
        # `_weapon_name` reads only `self.content`; no screen is built.
        stub = type("S", (), {"content": C})()
        locale.set_language("es")
        self.assertEqual(CharacterSelectState._weapon_name(stub, "magic_rod"), "Vara mágica")
        self.assertEqual(CharacterSelectState._weapon_name(stub, "nope"), "nope")

    def test_the_dev_menu_stays_english_in_spanish(self):
        # UI-014.D6: the developer tools do not follow the player's language.
        from game.states.dev_menu_state import _english_name
        locale.set_language("es")
        w = Weapon("sword", dict(C.weapon("sword")))
        apply_forge(w, get_forges(C).get("whirlwind"))
        self.assertEqual(w.name, "Torbellino")
        self.assertEqual(_english_name(w), "Whirlwind")
        self.assertEqual(_english_name(Enemy("spider", C.enemy("spider"), 0.0, 0.0)),
                         "Skitter")
        self.assertEqual(_english_name(object(), "fire"), "fire")

    def test_the_weapons_column_fits_every_languages_names(self):
        # The name term alone: the whole column width is dominated by the
        # level and damage cells, so testing it would pass on English only.
        from game import fonts
        from ui.run_summary import widest_weapon_name
        font = fonts.body(18)
        tables = (C.weapons, C.forges)
        widest_en = max(font.size(v["name"])[0] for t in tables for v in t.values())
        widest_es = max(font.size(v["name_es"])[0] for t in tables for v in t.values())
        self.assertGreater(widest_es, widest_en)        # else this proves nothing
        self.assertEqual(widest_weapon_name(font), widest_es)


# (file, source of the read) -> how many times it may appear, each for a
# reason. A read beyond its count, or not listed, fails the sweep.
ALLOWED_RAW_READS = Counter({
    # The forge parser keeps the English as the def's identity; the player
    # reads `display_*` (UI-014.5).
    ("combat/weapons/forge.py", "d['name']"): 1,
    ("combat/weapons/forge.py", "d['identity']"): 1,
    ("combat/weapons/forge.py", "d['description']"): 1,
    # A log line names the boss in English.
    ("entities/ai/behaviors/boss.py", "cfg.get('name', '?')"): 1,
    # An item's English name is its identity: built at generation and
    # saved (`to_dict` / `from_dict` read `d['name']` for the item and each
    # affix). The player reads `item_name`, built from the parts in the
    # current language (UI-014.6).
    ("progression/items.py", "d['name']"): 2,
    ("progression/items.py", "base['name']"): 1,
    ("progression/items.py", "a['name']"): 1,
    # The summary's fallback for a dict that is not a whole item (a
    # summary written before items carried their parts).
    ("ui/run_summary.py", "d.get('name', '?')"): 1,
    # Keys of the run summary's own dict (already resolved), not data.
    ("game/states/playing/core/run_end.py", "summary['trait_name']"): 1,
    ("ui/run_summary.py", "s.get('trait_name')"): 1,
    ("ui/run_summary.py", "r['name']"): 2,
})
# The developer tools stay English (UI-014.D6).
ALLOWED_FILES = {"game/states/dev_menu_state.py"}
TEXT_FIELDS = {"name", "description", "desc", "identity", "trait_name", "trait_desc"}
SKIP_DIRS = {"tests", "tools", "documentation", ".claude", "build", "dist", "assets",
             "__pycache__"}


def text_field_reads(tree):
    """`x["field"]` and `x.get("field", ...)` for a data text field."""
    for node in ast.walk(tree):
        key = None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            key = node.slice.value
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("get", "pop", "setdefault") and node.args
              and isinstance(node.args[0], ast.Constant)):
            key = node.args[0].value
        if key in TEXT_FIELDS:
            yield ast.unparse(node)


def raw_text_reads():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts) or rel.as_posix() in ALLOWED_FILES:
            continue
        for src in text_field_reads(ast.parse(path.read_text(encoding="utf-8"))):
            yield rel.as_posix(), src


class RawReadSweepTests(unittest.TestCase):
    def test_no_data_text_bypasses_the_locale(self):
        found = Counter(raw_text_reads())
        extra = sorted((found - ALLOWED_RAW_READS).elements())
        self.assertEqual(extra, [], "raw data-text reads beyond the allowlist")

    def test_the_allowlist_is_not_stale(self):
        found = Counter(raw_text_reads())
        self.assertEqual(sorted((ALLOWED_RAW_READS - found).elements()), [])

    def test_a_second_identical_read_is_caught(self):
        # The hole the UI-014.5 critic found: a set allowlist let a second
        # `d['name']` in an allowlisted file through.
        found = Counter(raw_text_reads())
        found[("combat/weapons/forge.py", "d['name']")] += 1
        self.assertEqual(sorted((found - ALLOWED_RAW_READS).elements()),
                         [("combat/weapons/forge.py", "d['name']")])

    def test_the_sweep_sees_both_forms(self):
        tree = ast.parse('x = d["name"]\ny = d.get("desc", "")\nz = d["hp"]\n'
                         'w = locale.text(d, "name")\nv = d.pop("identity")\n'
                         'u = d.setdefault("trait_desc", "")\n')
        self.assertEqual(sorted(text_field_reads(tree)),
                         ["d.get('desc', '')", "d.pop('identity')",
                          "d.setdefault('trait_desc', '')", "d['name']"])


if __name__ == "__main__":
    unittest.main()
