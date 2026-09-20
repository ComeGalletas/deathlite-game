"""Six blessings per weapon (2026-09-19, `journals/six_blessings_journal.md`):
every weapon owns six always-available blessings that cover damage, speed /
frequency, coverage and special effects, and the numbers follow one yardstick
-- about x1.15 output per level, so level V doubles the weapon."""
import unittest

from combat.status import REGISTRY
from game.content import get_content
from progression.blessings import get_catalog

C = get_content()
CAT = get_catalog(C)

SPEED = (0.87, 0.76, 0.66, 0.57, 0.5)              # x1 / 1.15^n
SPEED_FIELDS = ("cooldown_mult", "attack_interval_mult", "rehit_mult")


def own(wid):
    """The weapon's own blessings: no second weapon, no Forge required."""
    return [b for b in CAT.for_weapon(wid)
            if not b.requires_weapons and b.requires_forge is None]


def is_damage(b):
    return (len(b.effects) == 1 and b.effects[0].type == "weapon_bonus"
            and b.effects[0].field == "damage")


def speed_effects(b):
    return [e for e in b.effects if e.type == "weapon_bonus" and e.mode == "mult"
            and ((e.field in SPEED_FIELDS and e.levels[-1] < 1.0)
                 or (e.field == "orbit_speed_mult" and e.levels[-1] > 1.0))]


class SixPerWeaponTests(unittest.TestCase):
    def test_every_weapon_owns_exactly_six(self):
        for wid in C.weapons:
            self.assertEqual(len(own(wid)), 6, f"{wid}: {[b.id for b in own(wid)]}")

    def test_the_six_cover_the_four_axes(self):
        for wid in C.weapons:
            six = own(wid)
            self.assertEqual(sum(1 for b in six if is_damage(b)), 1, wid)
            self.assertGreaterEqual(sum(1 for b in six if speed_effects(b)), 1, wid)
            self.assertGreaterEqual(sum(1 for b in six if b.category == "coverage"), 1, wid)
            self.assertGreaterEqual(sum(1 for b in six if b.category == "behavior"), 1, wid)

    def test_only_cross_weapon_cards_are_synergies(self):
        # Weak Point and Demolitionist need no second weapon: behaviour, not synergy.
        for b in CAT.by_id.values():
            self.assertEqual(b.category == "synergy", bool(b.requires_weapons), b.id)
        self.assertEqual(sum(1 for b in CAT.by_id.values() if b.category == "synergy"), 6)

    def test_the_bomb_has_one_coverage_card(self):
        self.assertNotIn("bomb_blast_amplifier", CAT.by_id)
        cov = [b.id for b in own("bomb") if b.category == "coverage"]
        self.assertEqual(cov, ["bomb_bigger_explosion"])

    def test_every_card_formats_at_every_level(self):
        for b in CAT.by_id.values():
            for lv in range(1, 6):
                text = b.describe(lv)
                self.assertTrue(text, b.id)
                self.assertNotIn("{", text, b.id)

    def test_on_hit_status_cards_name_registered_statuses(self):
        for b in CAT.by_id.values():
            for e in b.effects:
                if e.type != "weapon_effect":
                    continue
                for suffix in ("_on_hit_frac", "_on_hit_potency", "_on_hit_duration"):
                    if e.key.endswith(suffix):
                        self.assertIn(e.key[:-len(suffix)], REGISTRY, b.id)


class YardstickTests(unittest.TestCase):
    def test_damage_blessings_follow_base_times_fifteen_percent_compounded(self):
        for wid, d in C.weapons.items():
            base = float(d["damage"])
            for b in own(wid):
                if not is_damage(b):
                    continue
                for n, total in enumerate(b.effects[0].levels, start=1):
                    want = base * (1.15 ** n - 1.0)
                    self.assertLessEqual(abs(total - want), 1.0,
                                         f"{b.id} level {n}: +{total:g} vs +{want:.2f}")
                # Level V doubles the weapon.
                self.assertLessEqual(abs(base + b.effects[0].levels[-1] - 2.0 * base), 1.0, b.id)

    def test_every_damage_step_is_ten_to_twenty_percent(self):
        for wid, d in C.weapons.items():
            base = float(d["damage"])
            for b in own(wid):
                if not is_damage(b):
                    continue
                prev = base
                for n, total in enumerate(b.effects[0].levels, start=1):
                    now = base + total
                    step = now / prev - 1.0
                    self.assertTrue(0.10 - 1e-9 <= step <= 0.20 + 1e-9,
                                    f"{b.id} level {n}: +{step:.1%}")
                    prev = now

    def test_speed_blessings_share_one_curve(self):
        seen = 0
        for wid in C.weapons:
            for b in own(wid):
                for e in speed_effects(b):
                    if e.field == "orbit_speed_mult":
                        for n, v in enumerate(e.levels, start=1):
                            self.assertAlmostEqual(v, 1.15 ** n, delta=0.02, msg=b.id)
                    elif wid == "hammer":
                        continue                   # its own curve, below
                    else:
                        self.assertEqual(e.levels, SPEED, b.id)
                    seen += 1
        # One per weapon at least; the totem and the wolf have a speed and a
        # frequency card each.
        self.assertGreaterEqual(seen, len(C.weapons) + 1)

    def test_the_hammers_speed_card_is_sized_on_its_whole_cycle(self):
        """CR1: the blow is a swing plus a rest and a cooldown blessing only
        shortens the rest, so Quick Swing's curve is deeper -- the swing +
        rest cycle is what follows x1 / 1.15^n."""
        d = C.weapon("hammer")
        swing, rest = float(d["swing_time"]), float(d["cooldown"])
        e = next(e for b in own("hammer") for e in speed_effects(b))
        for n, m in enumerate(e.levels, start=1):
            cycle = swing + rest * m
            self.assertAlmostEqual(cycle, (swing + rest) / 1.15 ** n, delta=0.02, msg=f"level {n}")

    def test_trade_cards_net_out_on_the_yardstick(self):
        """Heavy Blade / Heavy Draw: x1.15 slower, damage sized so the net
        output still climbs about x1.15 a level."""
        for bid in ("sword_heavy_blade", "bow_heavy_draw"):
            b = CAT.get(bid)
            base = float(C.weapon(b.weapon)["damage"])
            dmg = next(e for e in b.effects if e.field == "damage")
            cd = next(e for e in b.effects if e.field == "cooldown_mult")
            for n in range(1, 6):
                net = (base + dmg.levels[n - 1]) / base / cd.levels[n - 1]
                self.assertAlmostEqual(net, 1.15 ** n, delta=0.06, msg=f"{bid} level {n}")

    def test_post_forge_damage_cards_double_the_forged_weapon(self):
        for bid, forge in (("greatsword_cleaver", "greatsword"), ("ballista_siege_bolt", "ballista"),
                           ("arcane_lance_impale", "arcane_lance"), ("twin_daggers_dual_wield", "twin_daggers")):
            b = CAT.get(bid)
            base = float(C.forges[forge]["overrides"]["damage"])
            dmg = next(e for e in b.effects if e.field == "damage")
            self.assertLessEqual(abs(dmg.levels[-1] - base), max(1.0, base * 0.02), bid)


class PostForgeGateTests(unittest.TestCase):
    """A post-Forge card is never offered as an ordinary blessing: not by the
    level-up roll, not by a chest or shrine (they share `valid_offers`), and
    only for the Forge the weapon actually took."""

    def _hero(self, *wids):
        import random
        from combat.weapons import Weapon
        from entities.player import Player
        from progression.blessings import valid_offers
        p = Player(0, 0)
        p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
        return p, lambda **kw: {u.id for u in valid_offers(p, C, random.Random(0), **kw)}

    def test_unforged_weapons_see_no_post_forge_card(self):
        for wid in C.weapons:
            p, ids = self._hero(wid)
            offered = ids()
            for b in CAT.for_weapon(wid):
                if b.requires_forge is not None:
                    self.assertNotIn(b.id, offered, b.id)

    def test_the_forge_taken_unlocks_its_cards_and_no_others(self):
        from combat.weapons.forge import apply_forge, get_forges
        p, ids = self._hero("sword")
        whirlwind = next(f for f in get_forges(C).for_weapon("sword") if f.id == "whirlwind")
        apply_forge(p.weapons[0], whirlwind)
        offered = ids()
        self.assertIn("whirlwind_cyclone", offered)
        self.assertNotIn("greatsword_cleaver", offered)
        # The chest / shrine paths pass `kinds`; the gate holds there too.
        self.assertIn("whirlwind_cyclone", ids(kinds=("stat", "weapon")))
        self.assertNotIn("greatsword_cleaver", ids(kinds=("stat", "weapon")))


if __name__ == "__main__":
    unittest.main()
