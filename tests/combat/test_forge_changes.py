"""`combat/weapons/forge.py::forge_changes`: what a Forging changed, as the
run status screen prints it.

Real content (`data/forges.json`, `data/weapons.json`), no display: the
readout is a comparison of the Forging's overrides against the base weapon
definition, plus the effects it added, so the test pins that shape against
the data every Forging is validated from.
"""
import unittest

from combat.weapons import Weapon
from combat.weapons.forge import apply_forge, forge_changes, get_forges
from game.content import get_content


class ForgeChangesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = get_content()
        cls.forges = get_forges(cls.content)

    def _forged(self, fid):
        fdef = self.forges.get(fid)
        w = Weapon(fdef.weapon, dict(self.content.weapon(fdef.weapon)))
        apply_forge(w, fdef)
        return w, fdef

    def test_an_unforged_weapon_has_no_changes(self):
        w = Weapon("sword", dict(self.content.weapon("sword")))
        self.assertEqual(forge_changes(self.content, w), [])

    def test_every_numeric_override_is_reported_against_the_base(self):
        """Each override that is not the name or description comes back as
        (key, base value, forged value); the base is the *unforged*
        definition even though the weapon's own definition is now merged."""
        for fid in self.forges.by_id:
            with self.subTest(forge=fid):
                w, fdef = self._forged(fid)
                base = self.content.weapon(fdef.weapon)
                changes = forge_changes(self.content, w)
                keys = [k for k, _b, _a in changes]
                for k, v in fdef.overrides.items():
                    if k in ("name", "description"):
                        self.assertNotIn(k, keys)
                        continue
                    self.assertIn(k, keys)
                    before, after = next((b, a) for kk, b, a in changes if kk == k)
                    self.assertEqual(before, base.get(k))
                    self.assertEqual(after, v)

    def test_added_effects_come_back_with_no_before(self):
        for fid in self.forges.by_id:
            w, fdef = self._forged(fid)
            changes = forge_changes(self.content, w)
            for k, v in fdef.effects.items():
                with self.subTest(forge=fid, effect=k):
                    self.assertIn((k, None, v), changes)

    def test_whirlwind_reads_as_the_data_says(self):
        w, _fdef = self._forged("whirlwind")
        changes = dict((k, (b, a)) for k, b, a in forge_changes(self.content, w))
        self.assertEqual(changes["cooldown"][1], 0.24)
        self.assertEqual(changes["damage"][1], 6)
        self.assertEqual(changes["cone_half_angle"][1], 180)
        self.assertNotEqual(changes["damage"][0], 6, "the base damage must be the unforged one")


if __name__ == "__main__":
    unittest.main()
