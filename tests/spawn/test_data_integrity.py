"""Every slot that names an enemy id, and every slot that names a difficulty,
checked against the real vocabularies.

Written after R8 (`documentation/journals/enemy_roster_expansion_journal.md`)
put a rename in the wrong slot. The enemy ids and the difficulty levels used to
share the word `fast`, so the pass that re-keyed `"<id>": <number>` inside the
phase bands also hit `residents.difficulty_scale`, turning the `fast` entry
into `spider`. Nothing failed: the lookup is a `.get(level, 1.0)` and the value
it lost happened to be 1.0, so the bug was invisible to the suite and to the
game, and only showed up when the table was read out by eye.

`SpawnTables.validate` checks the ids it knows about, but it is handed
`enemy_ids` only when content loads, it never sees `bosses.json`, and it has no
opinion about difficulty keys at all. These tests close that gap from the
outside: they compare the shipped files against `enemies.json` and
`config.DIFFICULTY_ORDER` and name the offending slot when they fail.
"""
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config

DATA = Path(__file__).resolve().parents[2] / "data" / "enemies"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class EnemyIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enemies = _load("enemies.json")
        cls.tables = _load("spawn_tables.json")
        cls.bosses = _load("bosses.json")
        cls.ids = set(cls.enemies)

    def test_every_band_names_enemies_that_exist(self):
        for i, phase in enumerate(self.tables["phases"], 1):
            for eid in phase["types"]:
                with self.subTest(band=i, enemy=eid):
                    self.assertIn(eid, self.ids)

    def test_every_difficulty_override_names_enemies_that_exist(self):
        for level, over in self.tables.get("difficulty", {}).items():
            for i, phase in enumerate(over.get("phases", []), 1):
                for eid in phase["types"]:
                    with self.subTest(level=level, band=i, enemy=eid):
                        self.assertIn(eid, self.ids)

    def test_every_group_names_enemies_that_exist(self):
        """G2: a group is two weight tables, `commons` and (sometimes)
        `elites`, rather than a leader and followers."""
        for name, g in self.tables["groups"].items():
            if name.startswith("_"):            # a comment, not a group
                continue
            with self.subTest(group=name):
                self.assertTrue(g.get("commons"), f"{name} has no commons")
                for half in ("commons", "elites"):
                    for eid in g.get(half, {}):
                        self.assertIn(eid, self.ids, f"{name} {half} {eid}")

    def test_the_elite_slots_name_enemies_that_exist(self):
        for key in ("default", "rare"):
            with self.subTest(slot=key):
                self.assertIn(self.tables["elites"][key], self.ids)

    def test_every_summon_names_an_enemy_that_exists(self):
        """Both the enemy blocks and `bosses.json`, which the tables'
        own validation never looks at."""
        for eid, cfg in self.enemies.items():
            if "summon_id" in cfg:
                with self.subTest(enemy=eid):
                    self.assertIn(cfg["summon_id"], self.ids)
        for name, boss in self.bosses.items():
            for pattern in boss.get("patterns", []):
                if "summon_id" in pattern:
                    with self.subTest(boss=name, pattern=pattern.get("id")):
                        self.assertIn(pattern["summon_id"], self.ids)

    def test_every_enemy_id_is_its_own_sprite(self):
        """The rule the owner set in R8. `training_dummy` is the one
        exception: it is not a creature and has no art of its own."""
        for eid, cfg in self.enemies.items():
            if eid == "training_dummy":
                continue
            with self.subTest(enemy=eid):
                self.assertEqual(cfg["sprite"], eid)


class DifficultyKeyTests(unittest.TestCase):
    """The slots keyed by difficulty level rather than by enemy. This is the
    pair the R8 rename actually broke."""

    @classmethod
    def setUpClass(cls):
        cls.tables = _load("spawn_tables.json")
        cls.levels = set(config.DIFFICULTY_ORDER)

    def test_the_difficulty_section_lists_exactly_the_shipped_levels(self):
        self.assertEqual(set(self.tables["difficulty"]), self.levels)

    def test_resident_scaling_lists_exactly_the_shipped_levels(self):
        self.assertEqual(set(self.tables["residents"]["difficulty_scale"]),
                         self.levels)

    def test_no_difficulty_slot_has_picked_up_an_enemy_id(self):
        """The failure mode by name: a difficulty key replaced by a creature."""
        enemy_ids = set(_load("enemies.json"))
        for slot in (self.tables["difficulty"],
                     self.tables["residents"]["difficulty_scale"]):
            stray = set(slot) & enemy_ids
            self.assertFalse(stray, f"enemy id in a difficulty slot: {stray}")


class ShippedArtTests(unittest.TestCase):
    """`assets/enemies/` ships only what the game loads.

    Added after the imp was delivered (2026-09-17) with an `.aseprite` source
    and a portrait `avatar.png` that nothing reads, and four folders moved in
    earlier the same day carried the same stray portrait. Source art and
    unread art belong under `assets/unused/`, which the desktop build prunes;
    anything left here is shipped to every player.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        rigs = json.loads((DATA / "enemy_sprites.json").read_text(encoding="utf-8"))
        cls.referenced = set()
        for rig in rigs.values():
            for anim in rig.get("anims", {}).values():
                cls.referenced.add(anim["file"])
            if "file" in rig:
                cls.referenced.add(rig["file"])

    def test_every_shipped_enemy_file_is_referenced_by_a_rig(self):
        art = self.root / "assets" / "enemies"
        stray = [f"enemies/{d.name}/{f.name}"
                 for d in sorted(art.iterdir()) if d.is_dir()
                 for f in sorted(d.iterdir()) if f.is_file()]
        stray = [rel for rel in stray if rel not in self.referenced]
        self.assertEqual(stray, [], f"unreferenced art is being shipped: {stray}")

    def test_no_editor_sources_are_shipped(self):
        art = self.root / "assets" / "enemies"
        self.assertEqual(sorted(p.name for p in art.rglob("*.aseprite")), [])

    def test_enemy_art_paths_are_lowercase(self):
        """A rig names `enemies/imp/idle.png`; the imp arrived in a folder
        called `Imp`, which Windows resolves and Linux does not. Case is a
        silent, platform-specific break, so it is pinned."""
        art = self.root / "assets" / "enemies"
        wrong = [p.relative_to(art).as_posix() for p in art.rglob("*")
                 if p.name != p.name.lower()]
        self.assertEqual(wrong, [], f"not lowercase: {wrong}")
