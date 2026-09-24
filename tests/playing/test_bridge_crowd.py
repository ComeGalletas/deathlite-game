"""ENT-016: a pack files across a bridge at the shipped crowd push radius.

One small case of `tools/benchmarks/bridge_crowd.py`, pinned as a rate rather
than an outcome: a mixed pack of 12 on seed 35's first bridge, 20 s, with
the hero still on the far island. The bench's full table (six bridges, three
seeds, four fractions) is in `journals/enemy_ai_journal.md`.
"""
import unittest

from game import config
from tools.benchmarks import bridge_crowd as B

SEED = 35
PACK = 12


class BridgeCrowdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = B.boot(SEED)

    def test_the_shipped_push_radius_is_the_benched_one(self):
        self.assertEqual(config.CROWD_PUSH_RADIUS_FRAC, 0.75)

    def test_a_pack_crosses_a_bridge_and_none_is_stuck(self):
        c = self.ps.game_map.layout.corridors[0]
        r = B.trial(self.game, self.ps, c, PACK, 20.0, SEED, config.CROWD_PUSH_RADIUS_FRAC)
        self.assertIsNotNone(r, "the bridge had no room for the pack")
        self.assertEqual(r["pack"], PACK)
        self.assertGreaterEqual(r["crossed"], 0.9 * PACK, r)
        self.assertEqual(r["stuck"], 0, r)
        self.assertIsNotNone(r["t_half"], r)


if __name__ == "__main__":
    unittest.main()
