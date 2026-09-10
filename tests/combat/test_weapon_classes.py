"""Six-weapon system P1: the weapon roster and its taxonomy (design §3, §3.7,
§19). Six weapons -- three melee, three ranged -- plus three summons, every
one declaring a `class`; the fields each fire path reads are present in the
data, not defaulted in code."""
import unittest

from combat.weapons import CLASSES, SPECIAL_EFFECTS, Weapon
from game import config
from game.content import get_content

SIX = {"sword", "hammer", "daggers", "bow", "magic_rod", "bomb"}
SUMMONS = {"ember_ring", "grave_totem", "spirit_wolf"}
RETIRED = {"arcane_bolt", "frost_shards", "thunder_orb", "soul_scythe"}


def w(wid):
    return Weapon(wid, get_content().weapon(wid))


class RosterTests(unittest.TestCase):
    def test_exactly_the_six_weapons_and_the_three_summons(self):
        self.assertEqual(set(get_content().weapons), SIX | SUMMONS)

    def test_retired_weapons_are_gone(self):
        self.assertFalse(RETIRED & set(get_content().weapons))

    def test_three_melee_three_ranged_three_summons(self):
        by_class = {c: set() for c in CLASSES}
        for wid in get_content().weapons:
            by_class[w(wid).weapon_class].add(wid)
        self.assertEqual(by_class["melee"], {"sword", "hammer", "daggers"})
        self.assertEqual(by_class["ranged"], {"bow", "magic_rod", "bomb"})
        self.assertEqual(by_class["summon"], SUMMONS)

    def test_is_summon_follows_the_class(self):
        for wid in SUMMONS:
            self.assertTrue(w(wid).is_summon, wid)
        for wid in SIX:
            self.assertFalse(w(wid).is_summon, wid)


class TaxonomyTests(unittest.TestCase):
    def test_class_is_required(self):
        d = dict(get_content().weapon("sword"))
        d.pop("class")
        with self.assertRaises(ValueError):
            Weapon("sword", d)

    def test_unknown_class_is_rejected(self):
        d = dict(get_content().weapon("sword"))
        d["class"] = "spell"
        with self.assertRaises(ValueError):
            Weapon("sword", d)

    def test_unknown_special_effect_is_rejected(self):
        d = dict(get_content().weapon("bow"))
        d["special_effect"] = "homing"
        with self.assertRaises(ValueError):
            Weapon("bow", d)

    def test_bomb_is_a_known_special(self):
        self.assertIn("bomb", SPECIAL_EFFECTS)
        self.assertEqual(w("bomb").special, "bomb")


class RequiredFieldTests(unittest.TestCase):
    """Every field a fire path subscripts is in the data."""

    def test_melee_weapons_carry_their_cone_or_slam(self):
        for wid in ("sword", "daggers"):
            d = get_content().weapon(wid)
            self.assertEqual(d["special_effect"], "cone", wid)
            self.assertIn("cone_half_angle", d, wid)
            self.assertGreater(d["projectile_lifetime"], 0.0, wid)
        # CR1: the Hammer is a slam -- a swing, then a circle ahead.
        h = get_content().weapon("hammer")
        self.assertEqual(h["special_effect"], "slam")
        for key in ("swing_time", "impact_offset", "impact_rig"):
            self.assertIn(key, h, key)
        self.assertGreater(h["projectile_lifetime"], 0.0)

    def test_ranged_weapons_carry_reach_and_spread(self):
        for wid in ("bow", "magic_rod", "bomb"):
            d = get_content().weapon(wid)
            self.assertIn("reach", d, wid)
            self.assertIn("spread_deg", d, wid)

    def test_bomb_fields(self):
        d = get_content().weapon("bomb")
        for key in ("fuse", "throw_time", "blast_radius", "blast_lifetime"):
            self.assertIn(key, d, key)
        self.assertGreater(d["fuse"], d["throw_time"], "the bomb lands before it goes off")

    def test_hammer_stuns_and_nothing_else_does(self):
        self.assertGreater(get_content().weapon("hammer")["stun_chance"], 0.0)
        self.assertGreater(get_content().weapon("hammer")["stun_duration"], 0.0)
        for wid in SIX - {"hammer"}:
            self.assertEqual(get_content().weapon(wid).get("stun_chance", 0.0), 0.0, wid)

    def test_the_rod_has_a_wider_assist_cone_than_the_default(self):
        # Design §3.5 / decision 6: a manual aim gives the Rod a *rough area*.
        rod = get_content().weapon("magic_rod")
        self.assertGreater(rod["aim_assist_deg"], config.MANUAL_AIM_ASSIST_DEG)
        for wid in SIX - {"magic_rod"}:
            self.assertNotIn("aim_assist_deg", get_content().weapon(wid), wid)


class IdentityTests(unittest.TestCase):
    """Design §3: the six answer different questions -- pinned as numbers."""

    def d(self, wid):
        return get_content().weapon(wid)

    def test_daggers_are_the_fastest_and_the_hammer_the_slowest_melee(self):
        cds = {wid: self.d(wid)["cooldown"] for wid in ("sword", "hammer", "daggers")}
        self.assertLess(cds["daggers"], cds["sword"])
        self.assertLess(cds["sword"], cds["hammer"])

    def test_the_hammer_hits_hardest_and_heaviest(self):
        self.assertEqual(self.d("hammer")["damage"], 25)                 # CR1: fixed
        self.assertGreater(self.d("hammer")["weight"], self.d("sword")["weight"])
        # CR1: a circle 40 px ahead with radius 52 reaches past the Sword's arc.
        self.assertGreater(self.d("hammer")["impact_offset"] + self.d("hammer")["area"],
                           self.d("sword")["area"])

    def test_the_sword_sweeps_wider_than_the_daggers(self):
        self.assertGreater(self.d("sword")["cone_half_angle"], self.d("daggers")["cone_half_angle"])
        self.assertGreater(self.d("sword")["area"], self.d("daggers")["area"])

    def test_the_bow_pierces_and_reaches_furthest(self):
        self.assertGreater(self.d("bow")["pierce"], 0)
        self.assertEqual(self.d("magic_rod")["pierce"], 0)
        self.assertGreater(self.d("bow")["reach"], self.d("magic_rod")["reach"])
        self.assertGreater(self.d("bow")["reach"], self.d("bomb")["reach"])

    def test_the_bomb_is_slow_and_wide(self):
        self.assertGreater(self.d("bomb")["cooldown"], self.d("bow")["cooldown"])
        self.assertGreater(self.d("bomb")["blast_radius"], self.d("sword")["area"] * 0.9)


if __name__ == "__main__":
    unittest.main()
