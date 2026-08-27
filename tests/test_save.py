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


if __name__ == "__main__":
    unittest.main()
