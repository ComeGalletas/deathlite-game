"""CB-7: the hero's HP regeneration stat and the Mending blessing.

Every hero drips `stats["hp_regen"]` HP once per `config.HP_REGEN_INTERVAL`
seconds. The cadence is a fixed global; only the amount is a stat, and the
Mending blessing is what raises it.
"""
import unittest

import pygame

from entities.player import Player
from game import config
from game.content import get_content
from progression.blessings import apply_blessing, get_catalog, rebuild
from progression.stats import Modifier
from ui.run_status import common as rc

C = get_content()
CAT = get_catalog(C)
TICK = config.HP_REGEN_INTERVAL


class _RectWorld:
    """Minimal world stand-in for `Player.update` (see test_movement.py)."""
    def resolve_movement(self, prev, new, radius, flying=False):
        return pygame.Vector2(new)


def hero(cid=None):
    if cid is None:
        p = Player(0, 0)
    else:
        c = C.character(cid)
        p = Player(0, 0, base_stats=c["base_stats"], trait=c["trait"],
                   trait_params=c.get("trait_params"), character_id=cid)
    rebuild(p)
    return p


class BaselineTests(unittest.TestCase):
    def test_every_hero_regenerates_one_hp_per_tick(self):
        # "1 hp for all characters": the baseline lives in PLAYER_DEFAULTS, so
        # no hero has to declare it and none of them differ.
        for cid in ("aegis", "kestrel", "nihil"):
            self.assertEqual(hero(cid).hp_regen, 1.0, cid)

    def test_the_cadence_is_five_seconds(self):
        self.assertEqual(config.HP_REGEN_INTERVAL, 5.0)

    def test_the_stat_is_exposed_on_the_player(self):
        p = hero()
        self.assertEqual(p.hp_regen, p.stats["hp_regen"])


class TickTests(unittest.TestCase):
    def test_one_interval_restores_the_regen_amount(self):
        p = hero()
        p.hp = 50.0
        p.tick_regen(TICK)
        self.assertAlmostEqual(p.hp, 51.0)

    def test_nothing_before_the_interval_elapses(self):
        p = hero()
        p.hp = 50.0
        p.tick_regen(TICK - 0.01)
        self.assertAlmostEqual(p.hp, 50.0)

    def test_partial_frames_accumulate_across_calls(self):
        p = hero()
        p.hp = 50.0
        for _ in range(int(TICK / 0.5)):
            p.tick_regen(0.5)
        self.assertAlmostEqual(p.hp, 51.0)

    def test_the_remainder_carries_into_the_next_tick(self):
        p = hero()
        p.hp = 50.0
        p.tick_regen(TICK + TICK / 2.0)       # one tick paid, half banked
        self.assertAlmostEqual(p.hp, 51.0)
        p.tick_regen(TICK / 2.0)              # the bank completes the second
        self.assertAlmostEqual(p.hp, 52.0)

    def test_a_long_frame_pays_every_interval_it_spanned(self):
        # A lag spike or a loading hitch must not cost the player ticks.
        p = hero()
        p.hp = 50.0
        p.tick_regen(TICK * 3.0)
        self.assertAlmostEqual(p.hp, 53.0)

    def test_regen_never_overshoots_max_hp(self):
        p = hero()
        p.hp = p.max_hp - 0.4
        p.tick_regen(TICK)
        self.assertAlmostEqual(p.hp, p.max_hp)

    def test_regen_never_cuts_an_over_full_hero_down(self):
        # The dev HP tools and several combat tests bank HP above `max_hp` for
        # headroom. A regen tick must leave that surplus alone, not clamp it:
        # `heal` used to be a bare `min(max_hp, hp + amount)`.
        p = hero()
        p.hp = p.max_hp * 10.0
        p.tick_regen(TICK * 4.0)
        self.assertAlmostEqual(p.hp, p.max_hp * 10.0)

    def test_healing_an_over_full_hero_is_a_no_op(self):
        p = hero()
        p.hp = 1000.0
        p.heal(1.0)
        self.assertAlmostEqual(p.hp, 1000.0)

    def test_a_dead_hero_does_not_regenerate(self):
        p = hero()
        p.hp, p.alive = 0.0, False
        p.tick_regen(TICK * 5.0)
        self.assertEqual(p.hp, 0.0)
        self.assertFalse(p.alive)

    def test_zero_regen_banks_time_but_heals_nothing(self):
        p = hero()
        p.statset.set_base("hp_regen", 0.0)
        p.recompute()
        p.hp = 50.0
        p.tick_regen(TICK * 4.0)
        self.assertAlmostEqual(p.hp, 50.0)

    def test_the_phase_follows_run_time_not_the_last_hit(self):
        # The timer keeps running at full HP (the payout is clamped away), so a
        # hit landing late in an interval is topped up at the next boundary
        # instead of restarting a fresh countdown.
        p = hero()
        p.tick_regen(TICK * 0.9)              # banked while at full HP
        p.hp = 50.0
        p.tick_regen(TICK * 0.1)              # the boundary arrives
        self.assertAlmostEqual(p.hp, 51.0)

    def test_update_drives_the_tick(self):
        p = hero()
        p.hp = 50.0
        world = _RectWorld()
        for _ in range(int(TICK / 0.25)):
            p.update(0.25, world)
        self.assertAlmostEqual(p.hp, 51.0)


class MendingTests(unittest.TestCase):
    def test_the_blessing_is_a_five_level_stat_card(self):
        b = CAT.get("mending")
        self.assertEqual((b.kind, b.rarity, b.max_level), ("stat", "uncommon", 5))
        self.assertEqual(b.effects[0].stat, "hp_regen")
        self.assertEqual(b.effects[0].op, "flat")

    def test_each_level_adds_one_hp_to_the_tick(self):
        p = hero()
        b = CAT.get("mending")
        for level in range(1, b.max_level + 1):
            apply_blessing(p, b)
            self.assertAlmostEqual(p.hp_regen, 1.0 + level)

    def test_the_blessing_raises_the_payout_not_the_cadence(self):
        p = hero()
        apply_blessing(p, CAT.get("mending"))     # Mending I -> 2 HP a tick
        p.hp = 50.0
        p.tick_regen(TICK - 0.01)
        self.assertAlmostEqual(p.hp, 50.0)        # still nothing early
        p.tick_regen(0.01)
        self.assertAlmostEqual(p.hp, 52.0)

    def test_at_max_level_the_hero_regenerates_six_hp_a_tick(self):
        p = hero()
        b = CAT.get("mending")
        for _ in range(b.max_level):
            apply_blessing(p, b)
        p.hp = 50.0
        p.tick_regen(TICK)
        self.assertAlmostEqual(p.hp, 56.0)

    def test_the_card_text_states_the_real_cadence(self):
        # The description hardcodes the interval; pin it to the constant so
        # retuning `HP_REGEN_INTERVAL` cannot leave the card lying.
        text = CAT.get("mending").describe(1)
        self.assertIn(f"every {config.HP_REGEN_INTERVAL:g}s", text)
        self.assertIn("+1", text)

    def test_regen_cannot_be_driven_negative(self):
        p = hero()
        p.add_modifiers(Modifier("hp_regen", "flat", -50.0, "test"))
        self.assertEqual(p.hp_regen, 0.0)


class BuildScreenTests(unittest.TestCase):
    def test_the_build_screen_lists_hp_regen_under_max_hp(self):
        stats = [s for s, _l, _k in rc.STAT_ROWS]
        self.assertIn("hp_regen", stats)
        self.assertEqual(stats.index("hp_regen"), stats.index("max_hp") + 1)

    def test_the_row_prints_the_amount_with_its_cadence(self):
        self.assertEqual(rc.fmt_stat("hp_regen", 1.0), "1 / 5s")
        self.assertEqual(rc.fmt_stat("hp_regen", 6.0), "6 / 5s")

    def test_a_blessing_modifier_reads_as_a_flat_hp_amount(self):
        self.assertEqual(rc.fmt_mod("hp_regen", "flat", 2.0), "+2 HP regen")


if __name__ == "__main__":
    unittest.main()
