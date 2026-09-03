"""The world is byte-identical to the one that was pinned.

Three fingerprints per shipping seed -- the generated layout, the baked
terrain, one drawn frame -- against `digests.json`. A refactor that claims to
be a pure move has to leave all three alone; one that changes the world says
so and regenerates the file:

    python -m world.digest --write

The determinism test covers what `test_procedural`, `test_obstacles`,
`test_houses`, `test_repair` and `test_water_decor` each asserted separately
(two builds of one seed agree), in one place and over the whole model.
"""
import json
import unittest
from pathlib import Path

from tests import worlds as W
from world import digest

_PINNED = Path(__file__).with_name("digests.json")


def _pinned() -> dict:
    return json.loads(_PINNED.read_text())


class DigestTests(unittest.TestCase):
    def _check(self, stage, compute):
        pinned = _pinned()
        for seed in W.SEEDS:
            with self.subTest(seed=seed):
                self.assertEqual(
                    compute(seed), pinned[str(seed)][stage],
                    f"{stage} digest moved for seed {seed}; if the change is "
                    f"intended, run `python -m world.digest --write`")

    def test_the_layout_is_pinned(self):
        self._check("layout", lambda s: digest.layout_digest(W.layout(s)))

    def test_the_bake_is_pinned(self):
        self._check("bake", lambda s: digest.bake_digest(W.baked(s)))

    def test_the_frame_is_pinned(self):
        self._check("draw", lambda s: digest.draw_digest(W.baked(s)))

    def test_generation_is_deterministic(self):
        """Two builds of one seed are the same world, field for field."""
        seed = W.SEEDS[0]
        self.assertEqual(digest.layout_digest(W.layout(seed)),
                         digest.layout_digest(W.fresh(seed).layout))

    def test_the_digest_sees_a_change(self):
        """A moved obstacle changes the fingerprint -- otherwise the pins
        above would prove nothing."""
        gm = W.fresh(W.SEEDS[0])
        before = digest.layout_digest(gm.layout)
        gm.layout.obstacles[0].pos.x += 1
        self.assertNotEqual(before, digest.layout_digest(gm.layout))


if __name__ == "__main__":
    unittest.main()
