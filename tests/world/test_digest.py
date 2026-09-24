"""The world is byte-identical to the one that was pinned.

Three fingerprints per shipping seed -- the generated layout, the baked
terrain, one drawn frame -- against `digests.json`. A refactor that claims to
be a pure move has to leave all three alone; one that changes the world says
so and regenerates the file:

    python -m tools.verification.world_digest --write

The determinism test covers what `test_obstacles`, `test_houses`, `test_repair`
and `test_water_decor` each asserted separately (two builds of one seed agree),
in one place and over the whole model.

The pins are checked through `world_digest.world_digests(seed)` -- the entry
point `--write` uses -- on a fresh `GameMap`, not on the shared cached worlds
in `tests/worlds.py`. A cached world is baked under whatever config its first
caller had; going through the writer's own path means the pinned file and the
assertion measure the same build and cannot drift apart (TST-004.2).
"""
import json
import unittest
from pathlib import Path

from tests import worlds as W
from tools.verification import world_digest as digest

_PINNED = Path(__file__).with_name("digests.json")


def _pinned() -> dict:
    return json.loads(_PINNED.read_text())


_COMPUTED: dict = {}


def _computed(seed: int) -> dict:
    """The writer's three digests for `seed`, built once per process and
    shared by the three pin tests."""
    if seed not in _COMPUTED:
        _COMPUTED[seed] = digest.world_digests(seed)
    return _COMPUTED[seed]


class DigestTests(unittest.TestCase):
    def _check(self, stage):
        pinned = _pinned()
        self.assertEqual(sorted(int(s) for s in pinned), sorted(digest.SEEDS),
                         "digests.json pins a different seed set from the writer")
        for seed in digest.SEEDS:
            with self.subTest(seed=seed):
                self.assertEqual(
                    _computed(seed)[stage], pinned[str(seed)][stage],
                    f"{stage} digest moved for seed {seed}; if the change is "
                    f"intended, run `python -m tools.verification.world_digest --write`")

    def test_the_layout_is_pinned(self):
        self._check("layout")

    def test_the_bake_is_pinned(self):
        self._check("bake")

    def test_the_frame_is_pinned(self):
        self._check("draw")

    def test_the_suite_and_the_writer_pin_the_same_seeds(self):
        self.assertEqual(W.SEEDS, digest.SEEDS)

    def test_generation_is_deterministic(self):
        """Two builds of one seed are the same world, field for field -- and
        the shared cached world the rest of the suite reads is that world."""
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
