"""Milestone 7: save/load round-trip + corruption tolerance
(spec 4.7 / 8: "Save/load")."""
import json
import logging
import tempfile
import unittest
from pathlib import Path

from game.save import SaveData, load, save


class SaveLoadTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "save.json"

    def test_missing_file_returns_default_never_raises(self):
        data = load(self.path)  # file does not exist
        self.assertIsInstance(data, SaveData)
        self.assertEqual(data.currency, 0)
        self.assertEqual(set(data.equipped), {"weapon", "armor", "accessory"})

    def test_round_trip_preserves_fields(self):
        d = SaveData(currency=250, meta={"constitution": 3},
                     discovered_items=["weapon-1-rare"])
        d.equipped["weapon"] = "weapon-1-rare"
        d.stash.append({"item_id": "weapon-1-rare", "slot": "weapon"})
        d.record_best({"time": 640.0, "kills": 900})
        save(d, self.path)

        back = load(self.path)
        self.assertEqual(back.currency, 250)
        self.assertEqual(back.meta["constitution"], 3)
        self.assertEqual(back.equipped["weapon"], "weapon-1-rare")
        self.assertEqual(back.best["time"], 640.0)
        self.assertEqual(len(back.stash), 1)

    def test_file_is_human_readable_json(self):
        save(SaveData(currency=7), self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("\n", text)                 # pretty-printed
        self.assertEqual(json.loads(text)["currency"], 7)

    def test_corrupt_file_is_backed_up_and_replaced_with_default(self):
        self.path.write_text("{ this is not json ", encoding="utf-8")
        logging.disable(logging.CRITICAL)  # the warning here is expected
        try:
            data = load(self.path)
        finally:
            logging.disable(logging.NOTSET)
        self.assertIsInstance(data, SaveData)
        self.assertEqual(data.currency, 0)
        self.assertTrue((self.dir / "save.json.corrupt").exists())

    def test_default_key_layout_and_round_trip(self):
        # CB-5: the controls layout lives in settings and survives a save.
        self.assertEqual(SaveData().settings["key_layout"], "wasd_move")
        d = SaveData()
        d.settings["key_layout"] = "arrows_move"
        save(d, self.path)
        self.assertEqual(load(self.path).settings["key_layout"], "arrows_move")

    def test_unknown_key_layout_falls_back_to_default(self):
        for junk in ("dvorak", 7, None):
            self.path.write_text(json.dumps({"settings": {"key_layout": junk}}),
                                 encoding="utf-8")
            self.assertEqual(load(self.path).settings["key_layout"], "wasd_move")
        # A settings dict with no layout key at all also gets the default.
        self.path.write_text(json.dumps({"settings": {"muted": True}}),
                             encoding="utf-8")
        back = load(self.path)
        self.assertTrue(back.settings["muted"])
        self.assertEqual(back.settings["key_layout"], "wasd_move")

    def test_partial_dict_fills_defaults(self):
        self.path.write_text(json.dumps({"currency": 99}), encoding="utf-8")
        data = load(self.path)
        self.assertEqual(data.currency, 99)
        self.assertEqual(data.unlocked_characters, ["aegis", "kestrel", "nihil"])
        self.assertEqual(data.meta, {})

    def test_junk_types_are_ignored(self):
        self.path.write_text(json.dumps({
            "currency": "not a number", "meta": "nope", "equipped": 5,
        }), encoding="utf-8")
        data = load(self.path)
        self.assertEqual(data.currency, 0)
        self.assertEqual(data.meta, {})

    def test_record_best_only_improves(self):
        d = SaveData()
        d.record_best({"time": 100})
        d.record_best({"time": 50})
        self.assertEqual(d.best["time"], 100)


class DifficultyRecordsTests(unittest.TestCase):
    """Phase 4 D5: best runs are bucketed per difficulty and never compared
    across buckets."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "save.json"

    def test_default_has_a_bucket_per_difficulty(self):
        self.assertEqual(set(SaveData().records), {"normal", "fast", "super_fast"})
        self.assertEqual(SaveData().records["fast"], {})

    def test_records_are_independent_per_bucket(self):
        d = SaveData()
        d.record_best({"time": 300, "kills": 40}, difficulty="normal")
        d.record_best({"time": 120, "kills": 90}, difficulty="fast")
        self.assertEqual(d.records["normal"]["time"], 300)
        self.assertEqual(d.records["fast"]["time"], 120)      # not clobbered by 300
        self.assertEqual(d.records["fast"]["kills"], 90)
        self.assertEqual(d.records["super_fast"], {})

    def test_bucket_record_only_improves(self):
        d = SaveData()
        d.record_best({"level": 12}, difficulty="fast")
        d.record_best({"level": 5}, difficulty="fast")
        self.assertEqual(d.records["fast"]["level"], 12)

    def test_unknown_difficulty_falls_into_normal(self):
        d = SaveData()
        d.record_best({"time": 77}, difficulty="nightmare")
        self.assertEqual(d.records["normal"]["time"], 77)

    def test_legacy_best_still_tracks_the_all_difficulty_max(self):
        d = SaveData()
        d.record_best({"time": 100}, difficulty="normal")
        d.record_best({"time": 250}, difficulty="super_fast")
        self.assertEqual(d.best["time"], 250)

    def test_records_round_trip_and_tolerate_junk(self):
        d = SaveData()
        d.record_best({"time": 200, "damage_dealt": 5000}, difficulty="fast")
        save(d, self.path)
        back = load(self.path)
        self.assertEqual(back.records["fast"]["time"], 200)
        self.assertEqual(back.records["fast"]["damage_dealt"], 5000)

        import json
        self.path.write_text(json.dumps({"records": {
            "fast": {"time": "nope", "kills": 12}, "bogus": {"time": 5}}}),
            encoding="utf-8")
        back = load(self.path)
        self.assertEqual(back.records["fast"], {"kills": 12.0})
        self.assertNotIn("bogus", back.records)


if __name__ == "__main__":
    unittest.main()
