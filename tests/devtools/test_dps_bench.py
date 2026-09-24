"""The level-N build the DPS bench measures (`training_dummy_journal.md`,
2026-09-19).

What is pinned here: a level-N hero holds the starter weapon plus N-1 picks
taken through the real offering; the picks are all combat picks because the
non-combat stat blessings are filtered out of the pool before the roll; the
same seed gives the same build; and the summary statistics are what they say.
The classification of every stat blessing is pinned explicitly, so a new
blessing has to be sorted into one side or the other on purpose.
"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.content import get_content
from progression.blessings.catalog import get_catalog
from tools.benchmarks import dps_bench

# Every stat blessing that changes nothing about the damage landing on the
# dummy. Magnet was the owner's example; the rest follow the same rule.
NON_COMBAT = {"vitality", "mending", "fleet_foot", "scholar", "gold_rush",
              "iron_skin", "magnet", "shield_arm", "shield_wall", "nimble"}


class ClassificationTests(unittest.TestCase):
    def test_the_excluded_blessings_are_exactly_these(self):
        catalog = get_catalog(get_content())
        self.assertEqual(dps_bench.excluded_blessings(catalog), NON_COMBAT)

    def test_every_weapon_blessing_is_combat_relevant(self):
        catalog = get_catalog(get_content())
        for bid, b in catalog.by_id.items():
            if b.kind != "stat":
                self.assertTrue(dps_bench.combat_relevant(b), bid)

    def test_the_damage_stat_blessings_pass(self):
        catalog = get_catalog(get_content())
        for bid in ("iron_arm", "keen_eye", "haste", "lucky_strike", "fortune"):
            self.assertTrue(dps_bench.combat_relevant(catalog.by_id[bid]), bid)


class BuildTests(unittest.TestCase):
    def test_level_one_is_the_starter_weapon_alone(self):
        _game, ps = dps_bench._start_dev_run()
        taken = dps_bench.build_at_level(ps, 1, random.Random(0))
        self.assertEqual(taken, [])
        self.assertEqual([w.weapon_id for w in ps.player.weapons], ["sword"])
        self.assertEqual(ps.player.blessings, {})

    def test_level_n_takes_n_minus_one_combat_picks(self):
        _game, ps = dps_bench._start_dev_run()
        taken = dps_bench.build_at_level(ps, 12, random.Random(7))
        self.assertEqual(len(taken), 11)
        self.assertEqual(ps.levels.level, 12)
        # Every pick is accounted for: a blessing level, a grant or a Forge.
        grants = sum(1 for u in taken if u.kind == "grant")
        forges = sum(1 for u in taken if u.kind == "forge")
        self.assertEqual(sum(ps.player.blessings.values()) + grants + forges, 11)
        self.assertEqual(len(ps.player.weapons), 1 + grants)
        self.assertEqual(set(ps.player.blessings) & NON_COMBAT, set())
        self.assertIn("sword", [w.weapon_id for w in ps.player.weapons])

    def test_the_offering_never_shows_a_non_combat_card(self):
        _game, ps = dps_bench._start_dev_run()
        rng = random.Random(3)
        for _ in range(40):
            cards = dps_bench.offer_cards(ps, rng)
            self.assertEqual(len(cards), 3)
            self.assertEqual({u.id for u in cards} & NON_COMBAT, set())

    def test_the_same_seed_gives_the_same_build(self):
        builds = []
        for _ in range(2):
            _game, ps = dps_bench._start_dev_run()
            taken = dps_bench.build_at_level(ps, 8, random.Random(99))
            builds.append([u.id for u in taken])
        self.assertEqual(builds[0], builds[1])

    def test_summons_can_be_taken(self):
        """The owner let summons in (2026-09-19): over enough builds one is
        granted, and it sits in its own slot beside the three weapons."""
        seen = False
        for seed in range(6):
            _game, ps = dps_bench._start_dev_run()
            dps_bench.build_at_level(ps, 15, random.Random(seed))
            if any(w.is_summon for w in ps.player.weapons):
                seen = True
                self.assertLessEqual(
                    sum(1 for w in ps.player.weapons if not w.is_summon), 3)
                break
        self.assertTrue(seen, "no summon granted in six level-15 builds")


class StatisticsTests(unittest.TestCase):
    def test_summary_on_a_known_list(self):
        s = dps_bench.summarise([10, 20, 30, 40, 100])
        self.assertEqual(s["n"], 5)
        self.assertAlmostEqual(s["mean"], 40.0)
        self.assertAlmostEqual(s["median"], 30.0)
        self.assertAlmostEqual(s["p25"], 20.0)
        self.assertAlmostEqual(s["p75"], 40.0)
        self.assertEqual((s["min"], s["max"]), (10.0, 100.0))
        self.assertAlmostEqual(s["stdev"], 31.6227766, places=5)

    def test_summary_of_one_and_none(self):
        one = dps_bench.summarise([7.0])
        self.assertEqual((one["mean"], one["median"], one["p25"], one["p75"]),
                         (7.0, 7.0, 7.0, 7.0))
        self.assertEqual(one["stdev"], 0.0)
        self.assertEqual(dps_bench.summarise([])["n"], 0)

    def test_per_weapon_averages_over_appearances(self):
        rows = [{"split": [("bow", 300.0, 1.0)], "elapsed": 30.0},
                {"split": [("bow", 600.0, 0.5), ("sword", 600.0, 0.5)], "elapsed": 30.0}]
        self.assertEqual(dps_bench.per_weapon(rows),
                         [("sword", 1, 20.0), ("bow", 2, 15.0)])


class DamageScaleTests(unittest.TestCase):
    """`--damage-scale` (owner, 2026-09-19: "weapons only"): every weapon's
    base damage and every Forge damage override, nothing else, and the
    singleton is put back afterwards."""

    def test_scales_every_weapon_and_forge_damage_and_nothing_else(self):
        import copy
        from combat.weapons.forge import get_forges
        content = get_content()
        before_w = copy.deepcopy(content.weapons)
        before_f = {fid: dict(f.overrides) for fid, f in get_forges(content).by_id.items()}
        restore = dps_bench.scale_weapon_damage(1.2)
        try:
            for wid, w in content.weapons.items():
                self.assertAlmostEqual(w["damage"], before_w[wid]["damage"] * 1.2, msg=wid)
                for k, v in before_w[wid].items():
                    if k != "damage":
                        self.assertEqual(w[k], v, f"{wid}.{k} moved")
            forges = get_forges(content).by_id
            touched = 0
            for fid, ov in before_f.items():
                now = forges[fid].overrides
                if "damage" in ov:
                    touched += 1
                    self.assertAlmostEqual(now["damage"], ov["damage"] * 1.2, msg=fid)
                for k, v in ov.items():
                    if k != "damage":
                        self.assertEqual(now[k], v, f"{fid}.{k} moved")
            self.assertGreater(touched, 0)
        finally:
            restore()
        self.assertEqual(content.weapons, before_w)
        self.assertEqual({fid: dict(f.overrides) for fid, f in get_forges(content).by_id.items()},
                         before_f)

    def test_scale_one_is_a_no_op(self):
        import copy
        content = get_content()
        before = copy.deepcopy(content.weapons)
        restore = dps_bench.scale_weapon_damage(1.0)
        try:
            self.assertEqual(content.weapons, before)
        finally:
            restore()

    def test_the_sword_alone_measures_one_point_two_times_the_baseline(self):
        base = dps_bench.run_one(1, random.Random(0), seconds=6.0)
        restore = dps_bench.scale_weapon_damage(1.2)
        try:
            up = dps_bench.run_one(1, random.Random(0), seconds=6.0)
        finally:
            restore()
        self.assertAlmostEqual(up["total"] / base["total"], 1.2, places=6)


# The seventeen blessings whose number is damage. Broadhead and Arcane Focus
# joined the fifteen when the six-blessings pass gave the Bow and the Rod a
# damage card of their own (2026-09-19).
DAMAGE_BLESSINGS = {
    "iron_arm", "keen_eye",
    "sword_sharpened_edge", "sword_heavy_blade", "hammer_crushing_blow",
    "daggers_sharpened_blades", "bow_broadhead", "bow_heavy_draw",
    "magic_rod_arcane_focus", "bomb_explosive_force",
    "ember_ring_ember_heat", "grave_totem_spectral_bolts", "spirit_wolf_savage_bite",
    "twin_daggers_dual_wield", "greatsword_cleaver", "ballista_siege_bolt",
    "arcane_lance_impale",
}


class BlessingDamageScaleTests(unittest.TestCase):
    """`--blessing-damage-scale`: exactly the damage effects of exactly
    these blessings, nothing else on the same card, and the catalog is put
    back afterwards."""

    def test_the_set_is_exactly_these_seventeen(self):
        catalog = get_catalog(get_content())
        self.assertEqual(dps_bench.damage_blessings(catalog), DAMAGE_BLESSINGS)

    def test_scales_only_the_damage_effect_of_each(self):
        catalog = get_catalog(get_content())
        before = dict(catalog.by_id)
        restore = dps_bench.scale_blessing_damage(1.25)
        try:
            for bid, old in before.items():
                now = catalog.by_id[bid]
                if bid not in DAMAGE_BLESSINGS:
                    self.assertIs(now, old, bid)
                    continue
                self.assertEqual(len(now.effects), len(old.effects))
                for e_old, e_new in zip(old.effects, now.effects):
                    if dps_bench.is_damage_effect(e_old):
                        for a, b in zip(e_old.levels, e_new.levels):
                            self.assertAlmostEqual(b, a * 1.25, msg=bid)
                    else:
                        self.assertEqual(e_new, e_old, f"{bid}: a non-damage effect moved")
            # Heavy Blade: damage up, its weight and slower swing untouched.
            hb = catalog.by_id["sword_heavy_blade"]
            self.assertAlmostEqual(hb.effects[0].levels[-1],
                                   before["sword_heavy_blade"].effects[0].levels[-1] * 1.25)
            self.assertEqual(hb.effects[1].levels, before["sword_heavy_blade"].effects[1].levels)
            self.assertEqual(hb.effects[2].levels, before["sword_heavy_blade"].effects[2].levels)
        finally:
            restore()
        self.assertEqual(dict(catalog.by_id), before)

    def test_scale_one_is_a_no_op_in_effect(self):
        catalog = get_catalog(get_content())
        before = {bid: b.effects for bid, b in catalog.by_id.items()}
        restore = dps_bench.scale_blessing_damage(1.0)
        try:
            self.assertEqual({bid: b.effects for bid, b in catalog.by_id.items()}, before)
        finally:
            restore()

    def test_sharpened_edge_adds_one_and_a_quarter_times_as_much(self):
        """Sword alone vs Sword + Sharpened Edge V, with and without the
        scale: the *added* damage is 1.25x, the base is not."""
        from progression.blessings import apply_blessing

        def sword_plus_edge(scale):
            restore = dps_bench.scale_blessing_damage(scale)
            try:
                _game, ps = dps_bench._start_dev_run()
                bdef = ps.catalog.by_id["sword_sharpened_edge"]
                for _ in range(bdef.max_level):
                    apply_blessing(ps.player, bdef)
                return ps.player.weapons[0].bonus["damage"]
            finally:
                restore()

        top = get_catalog(get_content()).by_id["sword_sharpened_edge"].effects[0].levels[-1]
        self.assertAlmostEqual(sword_plus_edge(1.0), top)            # tuned in blessings.json
        self.assertAlmostEqual(sword_plus_edge(1.25), top * 1.25)


class MeasurementTests(unittest.TestCase):
    def test_one_short_measurement_at_level_five(self):
        row = dps_bench.run_one(5, random.Random(1), seconds=5.0)
        self.assertEqual(row["level"], 5)
        self.assertEqual(row["n_picks"], 4)
        self.assertGreater(row["dps"], 0.0)
        self.assertAlmostEqual(row["elapsed"], 5.0, delta=0.05)
        self.assertEqual(row["silent"], [])


if __name__ == "__main__":
    unittest.main()
