"""The weapon roster and its data (six-weapon design §3, §3.7, §19): six
weapons -- three melee, three ranged -- plus three summons, every one
declaring a `class` and a `category`; the fields each fire path reads are
present in the data, not defaulted in code.

Regrouped by subject in TST-004.5: this module was `test_weapon_classes.py`
(six-weapon P1) and took in the category checks from `test_weapons_reach.py`
and the spread-data checks from `test_weapons.py`.
"""
import unittest

from combat.weapons import CATEGORIES, CLASSES, SPECIAL_EFFECTS, Weapon
from game import config
from game.content import get_content

SIX = {"sword", "hammer", "daggers", "bow", "magic_rod", "bomb"}
SUMMONS = {"ember_ring", "grave_totem", "spirit_wolf"}
RETIRED = {"arcane_bolt", "frost_shards", "thunder_orb", "soul_scythe"}
_ALLOWED = set(CATEGORIES)


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
        # "Hardest" is the claim, so assert it against the other melee weapons
        # rather than against a number the owner tunes (25 agreed, 27 since).
        for other in ("sword", "daggers"):
            self.assertGreater(self.d("hammer")["damage"], self.d(other)["damage"])
        self.assertGreater(self.d("hammer")["weight"], self.d("sword")["weight"])
        # CR1: a circle 40 px ahead with radius 52 reaches past the Sword's arc.
        self.assertGreater(self.d("hammer")["impact_offset"] + self.d("hammer")["area"],
                           self.d("sword")["area"])

    def test_the_sword_sweeps_wider_than_the_daggers(self):
        # Wider in angle; the owner tuned the Sword's reach down to a short
        # swing (area 32), so the arc is the identity, not the reach.
        self.assertGreater(self.d("sword")["cone_half_angle"], self.d("daggers")["cone_half_angle"])

    def test_the_bow_pierces_and_reaches_furthest(self):
        self.assertGreater(self.d("bow")["pierce"], 0)
        self.assertEqual(self.d("magic_rod")["pierce"], 0)
        self.assertGreater(self.d("bow")["reach"], self.d("magic_rod")["reach"])
        self.assertGreater(self.d("bow")["reach"], self.d("bomb")["reach"])

    def test_the_bomb_is_slow_and_wide(self):
        self.assertGreater(self.d("bomb")["cooldown"], self.d("bow")["cooldown"])
        self.assertGreater(self.d("bomb")["blast_radius"], self.d("sword")["area"] * 0.9)


class CategoryTests(unittest.TestCase):
    def test_every_def_declares_an_allowed_category(self):
        for wid in get_content().weapons:
            self.assertIn(w(wid).category, _ALLOWED, wid)

    def test_expected_category_per_weapon(self):
        want = {
            "sword": "melee", "hammer": "melee", "daggers": "melee",
            "bow": "projectile", "magic_rod": "projectile", "bomb": "projectile",
            "ember_ring": "orbit", "grave_totem": "summon",
            "spirit_wolf": "summon",
        }
        for wid, cat in want.items():
            self.assertEqual(w(wid).category, cat, wid)

    def test_category_is_required_metadata(self):
        # weapons.json carries every field now -- a def with no `category`
        # (validated against the CATEGORIES constant) is bad data, not a
        # fall-through.
        d = dict(get_content().weapon("magic_rod"))
        d.pop("category", None)
        with self.assertRaises(ValueError):
            Weapon("magic_rod", d)


class ProjectileSpreadDataTests(unittest.TestCase):
    """Every weapon that fans its shots must say how wide the fan is.

    A `<weapon>:projectiles` upgrade is generated for *every* owned weapon
    (`progression/upgrades._weapon_upgrades`), so any projectile weapon can be
    pushed past one shot in a real run. `Weapon._fire_projectiles` reads
    `spread_deg` with a hard subscript at that point -- deliberately, since a
    default in code would be per-weapon tuning living outside the data -- so a
    weapon missing the field crashes the run the moment the player takes its
    projectile upgrade. Two of the retired weapons once shipped without it.
    """

    def test_every_projectile_weapon_declares_a_spread(self):
        for wid, cfg in get_content().weapons.items():
            if cfg.get("category") != "projectile":
                continue
            self.assertIn("spread_deg", cfg, wid)
            self.assertGreater(float(cfg["spread_deg"]), 0.0, wid)

    def test_one_multishot_upgrade_does_not_crash_any_weapon(self):
        """The failure this guards is a KeyError deep in a firing path, so it is
        exercised rather than only asserted on the data: every weapon takes
        one `projectiles` upgrade and fires through `Weapon.update` at a
        target in reach. A projectile weapon then lays out one shot per count,
        fanned `spread_deg` apart (read from the data) edge to edge."""
        import pygame

        from tests.combat.fakes import FakeTarget
        from tests.combat.test_weapon_fire import make_context

        fanned = 0
        for wid, cfg in get_content().weapons.items():
            with self.subTest(weapon=wid):
                w = Weapon(wid, cfg)
                w.bonus["projectile_count"] += 1
                count = w._projectile_count()
                shots = []
                w.update(0.016, make_context([FakeTarget(60, 0)], shots,
                                             spawn_summon=lambda **kw: None))
                if count > 1 and cfg.get("category") == "projectile":
                    self.assertEqual(len(shots), count)
                    first = pygame.Vector2(shots[0]["vel"])
                    last = pygame.Vector2(shots[-1]["vel"])
                    self.assertAlmostEqual(
                        abs(first.angle_to(last)),
                        float(cfg["spread_deg"]) * (count - 1), places=3)
                    fanned += 1
        self.assertGreater(fanned, 0, "no projectile weapon fanned its shots")


if __name__ == "__main__":
    unittest.main()
