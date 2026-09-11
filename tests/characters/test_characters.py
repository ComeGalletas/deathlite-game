"""Heroes (spec 4.1; six-weapon system P1, design §20): three distinct
identities, the re-pointed traits, and the defensive stats."""
import random
import unittest


from combat.weapons import Weapon
from entities.player import Player
from game import config
from game.content import get_content


def hero(cid, rng=None):
    c = get_content().character(cid)
    return Player(0, 0, base_stats=c["base_stats"], trait=c["trait"],
                  trait_params=c.get("trait_params"), character_id=cid, rng=rng)


def weapon(wid):
    return Weapon(wid, get_content().weapon(wid))


class _FixedRng:
    """`random()` returns the queued values in order (then 1.0: never rolls)."""
    def __init__(self, *values):
        self._v = list(values)

    def random(self):
        return self._v.pop(0) if self._v else 1.0


class CharacterDataTests(unittest.TestCase):
    def test_three_characters_each_distinct(self):
        chars = get_content().characters
        self.assertEqual(len(chars), 3)
        weapons, traits = set(), set()
        for c in chars.values():
            self.assertIn("base_stats", c)
            self.assertTrue(c.get("trait"))
            self.assertIn("trait_params", c)
            weapons.add(c["starting_weapon"])
            traits.add(c["trait"])
        self.assertEqual(len(weapons), 3, "each hero starts with a different weapon")
        self.assertEqual(len(traits), 3, "each hero has a different trait")

    def test_starting_weapons_are_sword_bow_and_rod(self):
        c = get_content()
        self.assertEqual(c.character("aegis")["starting_weapon"], "sword")
        self.assertEqual(c.character("kestrel")["starting_weapon"], "bow")
        self.assertEqual(c.character("nihil")["starting_weapon"], "magic_rod")
        for cid in c.characters:
            self.assertIn(c.character(cid)["starting_weapon"], c.weapons)


class CharacterBuildTests(unittest.TestCase):
    def test_base_stats_override_defaults(self):
        aegis, kestrel = hero("aegis"), hero("kestrel")
        self.assertEqual(aegis.stats["max_hp"], 160)
        self.assertGreater(kestrel.move_speed, aegis.move_speed)
        self.assertLess(kestrel.stats["max_hp"], aegis.stats["max_hp"])

    def test_bulwark_reduces_damage_only_after_standing_still(self):
        p = hero("aegis")
        p.still_time = 0.0
        self.assertFalse(p.bulwark_active)
        self.assertEqual(p.incoming_damage_multiplier(), 1.0)
        p.still_time = 0.5
        self.assertTrue(p.bulwark_active)
        self.assertAlmostEqual(p.incoming_damage_multiplier(), 0.7)

    def test_bulwark_numbers_come_from_the_data(self):
        c = get_content().character("aegis")["trait_params"]
        p = hero("aegis")
        p.still_time = c["still_after"] - 0.01
        self.assertFalse(p.bulwark_active)
        p.still_time = c["still_after"]
        self.assertAlmostEqual(p.incoming_damage_multiplier(), c["damage_taken_mult"])

    def test_no_hero_has_a_passive_outgoing_multiplier(self):
        for cid in get_content().characters:
            self.assertEqual(hero(cid).outgoing_damage_multiplier(), 1.0, cid)


class TraitWeaponModTests(unittest.TestCase):
    def test_double_shot_adds_an_arrow_to_the_bow_only(self):
        k = hero("kestrel")
        tp = get_content().character("kestrel")["trait_params"]
        bow = k.weapon_mods(weapon("bow"))
        self.assertEqual(bow.extra_projectiles, tp["extra_projectiles"])
        self.assertAlmostEqual(bow.damage_mult, tp["damage_mult"])
        self.assertLess(bow.damage_mult, 1.0)                 # the split: not "+100 %"
        self.assertEqual(k.weapon_mods(weapon("sword")).extra_projectiles, 0)
        self.assertEqual(k.weapon_mods(weapon("magic_rod")).damage_mult, 1.0)

    def test_quick_cast_speeds_the_rod_only(self):
        n = hero("nihil")
        tp = get_content().character("nihil")["trait_params"]
        rod = n.weapon_mods(weapon("magic_rod"))
        self.assertAlmostEqual(rod.cooldown_mult, tp["cooldown_mult"])
        self.assertLess(rod.cooldown_mult, 1.0)
        self.assertGreaterEqual(rod.cooldown_mult, 0.8, "the bonus is meant to be small")
        self.assertEqual(n.weapon_mods(weapon("bow")).cooldown_mult, 1.0)

    def test_bulwark_has_no_weapon_mods(self):
        a = hero("aegis")
        for wid in ("sword", "bow", "magic_rod"):
            self.assertEqual(a.weapon_mods(weapon(wid)).extra_projectiles, 0)
            self.assertEqual(a.weapon_mods(weapon(wid)).cooldown_mult, 1.0)


class DefensiveStatTests(unittest.TestCase):
    """Design §20: base evasion 5 % (Kestrel 10 %); block only on Aegis at
    30 %; a block removes 50 %; both roll before the trait and armour."""

    def test_hero_bases(self):
        self.assertAlmostEqual(config.PLAYER_DEFAULTS["evasion_chance"], 0.05)
        self.assertAlmostEqual(config.PLAYER_DEFAULTS["block_chance"], 0.0)
        self.assertAlmostEqual(config.PLAYER_DEFAULTS["block_strength"], 0.5)
        self.assertAlmostEqual(hero("aegis").stats["evasion_chance"], 0.05)
        self.assertAlmostEqual(hero("nihil").stats["evasion_chance"], 0.05)
        self.assertAlmostEqual(hero("kestrel").stats["evasion_chance"], 0.10)
        self.assertAlmostEqual(hero("aegis").stats["block_chance"], 0.30)
        self.assertAlmostEqual(hero("kestrel").stats["block_chance"], 0.0)
        self.assertAlmostEqual(hero("nihil").stats["block_chance"], 0.0)

    def test_evasion_negates_the_hit(self):
        p = hero("kestrel", rng=_FixedRng(0.01))            # under 10 %: evaded
        hp = p.hp
        self.assertEqual(p.take_damage(40), 0.0)
        self.assertEqual(p.hp, hp)
        self.assertEqual(p.last_defense, "evaded")

    def test_block_halves_the_hit_before_armour(self):
        # Aegis: armour 4. Evasion roll misses (0.9), block roll lands (0.1).
        p = hero("aegis", rng=_FixedRng(0.9, 0.1))
        p.still_time = 0.0
        self.assertAlmostEqual(p.take_damage(40), 40 * 0.5 - 4)
        self.assertEqual(p.last_defense, "blocked")

    def test_block_then_bulwark_then_armour(self):
        p = hero("aegis", rng=_FixedRng(0.9, 0.1))
        p.still_time = 1.0                                    # guard up: x0.7
        self.assertAlmostEqual(p.take_damage(40), 40 * 0.5 * 0.7 - 4)

    def test_no_roll_lands_plain_damage(self):
        p = hero("kestrel", rng=_FixedRng(0.5, 0.5))
        self.assertAlmostEqual(p.take_damage(40), 40.0)
        self.assertEqual(p.last_defense, "")

    def test_block_strength_is_a_stat_so_a_blessing_can_raise_it(self):
        from progression.stats import FLAT, Modifier
        p = hero("aegis", rng=_FixedRng(0.9, 0.1))
        p.add_modifiers(Modifier("block_strength", FLAT, 0.25, "test"))
        self.assertAlmostEqual(p.take_damage(40), 40 * 0.25 - 4)

    def test_a_bare_player_rolls_with_its_own_rng(self):
        p = Player(0, 0)
        self.assertIsInstance(p.rng, random.Random)
        p.take_damage(1)                                      # no crash


class _FreeWorld:
    """No walls -- movement is unconstrained (for trait tests)."""
    def resolve_movement(self, prev, new, radius, flying=False):
        return new


class StillTimeTests(unittest.TestCase):
    def test_still_time_resets_on_movement(self):
        p = hero("aegis")
        world = _FreeWorld()
        for _ in range(60):
            p.update(1 / 60, world)
        self.assertGreater(p.still_time, 0.9)
        p._move_dir.update(1, 0)
        p.update(1 / 60, world)
        self.assertEqual(p.still_time, 0.0)


if __name__ == "__main__":
    unittest.main()
