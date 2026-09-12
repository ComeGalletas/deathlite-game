"""The training dummy and the DPS meter (`training_dummy_journal.md`).

What is pinned here: the meter measures **one** enemy, so a hit on anything
else can never inflate it; villagers are dropped; the window rolls; and the
dummy absorbs damage without losing HP or moving.

The arithmetic tests drive `DpsMeter` directly with an explicit clock rather
than a real run, so they are exact -- a measured DPS is only worth anything if
the thing measuring it is known to be right.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.content import get_content
from game.states.playing.dps_meter import UNATTRIBUTED, VILLAGER, DpsMeter


class _Target:
    """The one attribute the meter hooks."""

    def __init__(self):
        self.damage_sink = None


class ArmingTests(unittest.TestCase):
    def test_arming_hooks_the_target_and_disarming_unhooks_it(self):
        m, t = DpsMeter(), _Target()
        self.assertFalse(m.armed)
        m.arm(t)
        self.assertTrue(m.armed)
        self.assertEqual(t.damage_sink, m.record)
        m.disarm()
        self.assertFalse(m.armed)
        self.assertIsNone(t.damage_sink)

    def test_arming_a_second_target_releases_the_first(self):
        """Otherwise a stale dummy keeps feeding the meter after it is gone."""
        m, a, b = DpsMeter(), _Target(), _Target()
        m.arm(a)
        m.arm(b)
        self.assertIsNone(a.damage_sink)
        self.assertEqual(b.damage_sink, m.record)

    def test_arming_clears_the_previous_reading(self):
        m, t = DpsMeter(), _Target()
        m.arm(t)
        m.record(100.0, "sword")
        m.update(1.0)
        m.arm(_Target())
        self.assertEqual(m.total, 0.0)
        self.assertEqual(m.elapsed, 0.0)
        self.assertEqual(m.breakdown(), [])

    def test_the_clock_only_runs_while_armed(self):
        m = DpsMeter()
        m.update(5.0)
        self.assertEqual(m.elapsed, 0.0)


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.m = DpsMeter(window_s=10.0)
        self.m.arm(_Target())

    def test_total_dps_is_damage_over_elapsed(self):
        for _ in range(4):
            self.m.record(50.0, "sword")
            self.m.update(1.0)
        self.assertEqual(self.m.total, 200.0)
        self.assertAlmostEqual(self.m.elapsed, 4.0)
        self.assertAlmostEqual(self.m.total_dps, 50.0)

    def test_the_window_divides_by_the_time_so_far_not_its_full_span(self):
        """Two seconds in, 100 damage is 50 dps -- not 10, which is what
        dividing by the whole 10 s window would report."""
        self.m.record(100.0, "sword")
        self.m.update(2.0)
        self.assertAlmostEqual(self.m.window_dps, 50.0)

    def test_damage_rolls_out_of_the_window(self):
        self.m.record(100.0, "sword")
        self.m.update(11.0)                      # past the 10 s window
        self.assertEqual(self.m.total, 100.0)    # the total never forgets
        self.assertAlmostEqual(self.m.window_dps, 0.0)

    def test_the_window_holds_what_is_still_inside_it(self):
        self.m.record(100.0, "sword")            # at t=0
        self.m.update(6.0)
        self.m.record(100.0, "sword")            # at t=6
        self.m.update(5.0)                       # t=11: the first has rolled off
        self.assertAlmostEqual(self.m._window_total, 100.0)

    def test_zero_and_negative_damage_are_ignored(self):
        self.m.record(0.0, "sword")
        self.m.record(-5.0, "sword")
        self.assertEqual(self.m.total, 0.0)

    def test_reset_clears_everything_but_stays_armed(self):
        self.m.record(100.0, "sword")
        self.m.update(1.0)
        self.m.reset()
        self.assertTrue(self.m.armed)
        self.assertEqual((self.m.total, self.m.elapsed), (0.0, 0.0))
        self.assertAlmostEqual(self.m.window_dps, 0.0)

    def test_dps_is_zero_before_any_time_passes(self):
        self.m.record(100.0, "sword")
        self.assertEqual(self.m.total_dps, 0.0)
        self.assertEqual(self.m.window_dps, 0.0)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.m = DpsMeter()
        self.m.arm(_Target())

    def test_damage_splits_by_source_biggest_first(self):
        self.m.record(75.0, "sword")
        self.m.record(25.0, "bow")
        rows = self.m.breakdown()
        self.assertEqual([r[0] for r in rows], ["sword", "bow"])
        self.assertAlmostEqual(rows[0][2], 0.75)
        self.assertAlmostEqual(rows[1][2], 0.25)

    def test_an_unnamed_source_is_visible_not_folded_away(self):
        """A hole in the attribution should read as a hole, not be quietly
        credited to a weapon that did not do it."""
        self.m.record(10.0, None)
        self.assertEqual(self.m.by_source, {UNATTRIBUTED: 10.0})

    def test_villager_damage_is_dropped_entirely(self):
        """A lancer that wanders over and stabs the dummy is not the hero."""
        self.m.record(50.0, "sword")
        self.m.record(999.0, VILLAGER)
        self.assertEqual(self.m.total, 50.0)
        self.assertNotIn(VILLAGER, self.m.by_source)

    def test_the_summary_reads_off_when_disarmed(self):
        self.assertEqual(DpsMeter().summary(), "off")


class DummyDataTests(unittest.TestCase):
    """The dummy is data, not a class."""

    def setUp(self):
        self.cfg = get_content().enemies["training_dummy"]

    def test_it_is_invulnerable_still_and_harmless(self):
        self.assertTrue(self.cfg["invulnerable"])
        self.assertEqual(self.cfg["speed"], 0)
        self.assertEqual(self.cfg["contact_damage"], 0)
        self.assertFalse(self.cfg["contact_damage_enabled"])
        self.assertEqual(self.cfg["experience_reward"], 0)
        self.assertEqual(self.cfg["behavior"], "dummy")
        self.assertIn("dummy", self.cfg["tags"])

    def test_no_other_enemy_is_invulnerable(self):
        """The flag is the dummy's alone -- a real enemy carrying it would be
        unkillable and the run unwinnable."""
        for eid, cfg in get_content().enemies.items():
            if eid == "training_dummy":
                continue
            self.assertFalse(cfg.get("invulnerable", False), eid)


class InvulnerableEnemyTests(unittest.TestCase):
    """`Enemy` honours the flag, and the meter sees the damage anyway."""

    def _dummy(self):
        from entities.enemy import Enemy
        return Enemy("training_dummy", get_content().enemies["training_dummy"],
                     0.0, 0.0)

    def test_damage_is_returned_but_no_hp_comes_off(self):
        e = self._dummy()
        hp = e.hp
        dealt = e.take_damage(50.0)
        self.assertEqual(dealt, 50.0)      # what the meter counts
        self.assertEqual(e.hp, hp)
        self.assertTrue(e.alive)

    def test_it_survives_far_more_than_its_hp(self):
        e = self._dummy()
        for _ in range(100):
            e.take_damage(1000.0)
        self.assertTrue(e.alive)

    def test_armor_still_applies(self):
        """The measurement is only useful if a hit behaves like a real hit."""
        e = self._dummy()
        self.assertLess(e.take_damage(50.0, armor=10.0), 50.0)

    def test_a_damage_over_time_tick_cannot_kill_it(self):
        """`_status_damage` used to subtract HP itself, which would have burned
        the dummy down straight through its invulnerability."""
        from tests.aictx import ai_ctx
        e = self._dummy()
        e.status.apply("burn", duration=5.0, potency=50.0, source="bow")
        ctx = ai_ctx(dt=0.5)
        for _ in range(20):
            e.status.update(0.5, lambda a, s: e._status_damage(a, ctx, s))
        self.assertTrue(e.alive)
        self.assertEqual(e.hp, e.max_hp)

    def test_the_meter_sees_every_path(self):
        e = self._dummy()
        m = DpsMeter()
        m.arm(e)
        e.take_damage(10.0, source="sword")            # a hit
        from tests.aictx import ai_ctx
        e.status.apply("burn", duration=5.0, potency=4.0, source="bow")
        e.status.update(1.0, lambda a, s: e._status_damage(a, ai_ctx(), s))
        self.assertGreater(m.by_source["sword"], 0.0)
        self.assertGreater(m.by_source["bow"], 0.0)

    def test_knockback_does_not_move_it(self):
        e = self._dummy()
        e.apply_knockback(pygame.Vector2(1, 0), 500.0)
        self.assertEqual(e._knock, pygame.Vector2())

    def test_a_normal_enemy_is_unaffected_by_all_of_this(self):
        from entities.enemy import Enemy
        e = Enemy("chaser", get_content().enemies["chaser"], 0.0, 0.0)
        hp = e.hp
        e.take_damage(5.0, source="sword")
        self.assertLess(e.hp, hp)
        e.apply_knockback(pygame.Vector2(1, 0), 50.0)
        self.assertGreater(e._knock.length(), 0.0)


class DummyBehaviourTests(unittest.TestCase):
    def test_the_dummy_behaviour_runs_no_components(self):
        """No steering, no attack, no aggro -- `speed: 0` alone is not enough,
        because every other behaviour still runs an attack beat."""
        from entities.ai import build_behavior
        b = build_behavior("dummy", {})
        self.assertEqual(sum(len(c) for c in b.states.values()), 0)
        self.assertEqual(b.transitions, [])
        self.assertEqual(b.always, [])

    def test_it_is_registered(self):
        from entities.ai import registered
        self.assertIn("dummy", registered())


if __name__ == "__main__":
    unittest.main()


class GroundTruthTests(unittest.TestCase):
    """The check that proves the meter rather than the meter proving itself.

    A weapon with a known `damage` and `cooldown` from the data, fired at the
    dummy with no blessings, no items and no crit, must measure at
    `damage / cooldown`. If this drifts, the meter is lying and every number it
    has ever shown is suspect.
    """

    def _fire_for(self, wid: str, seconds: float, dt: float = 1.0 / 60.0):
        """Tick one weapon at the dummy for `seconds`, landing every shot, and
        return `(meter, definition)`."""
        from combat.weapons import FireContext, Weapon
        from entities.enemy import Enemy

        cfg = get_content().weapon(wid)
        dummy = Enemy("training_dummy", get_content().enemies["training_dummy"],
                      60.0, 0.0)
        meter = DpsMeter()
        meter.arm(dummy)
        w = Weapon(wid, cfg)

        def land(**kw):
            # Every shot hits the dummy the instant it is fired: this measures
            # the weapon's output, not its travel time.
            meter.record(kw["damage"], wid)

        steps = int(round(seconds / dt))
        for _ in range(steps):
            w.update(dt, FireContext(
                origin=pygame.Vector2(0, 0), enemies=[dummy],
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0), spawn_projectile=land))
            meter.update(dt)
        return meter, cfg

    def test_a_projectile_weapon_measures_at_damage_over_cooldown(self):
        for wid in ("bow", "magic_rod"):
            with self.subTest(wid):
                meter, cfg = self._fire_for(wid, 30.0)
                shots = cfg["damage"] * cfg["projectile_count"]
                expected = shots / cfg["cooldown"]
                # Within 6%: the run is a whole number of shots, so the last
                # cooldown is always partly unspent.
                self.assertAlmostEqual(meter.total_dps / expected, 1.0, delta=0.06)

    def test_the_whole_measurement_is_attributed_to_the_weapon(self):
        meter, _cfg = self._fire_for("bow", 10.0)
        self.assertEqual(list(meter.by_source), ["bow"])
        self.assertNotIn(UNATTRIBUTED, meter.by_source)

    def test_the_window_agrees_with_the_average_once_it_is_full(self):
        """A steady weapon read over a full window is the same number either
        way; if they disagree the window is dropping or double-counting."""
        meter, _cfg = self._fire_for("bow", 30.0)
        self.assertAlmostEqual(meter.window_dps / meter.total_dps, 1.0, delta=0.10)


class BenchArenaTests(unittest.TestCase):
    """`game/dps_bench.py` measures on an empty arena, not a generated world.

    A generated world differs per run, so a loadout was measured on its own
    ground with its own obstacles between the hero and the dummy -- variance
    between the *rows of a table*, not just between passes. The arena removes
    the world as a variable instead of pinning it, and these pin that it stays
    removed: a future change that quietly puts a world back under the bench
    would make every published number incomparable again.
    """

    def test_the_arena_has_no_world_and_nothing_in_it(self):
        from game import dps_bench
        game, ps = dps_bench._start_dev_run()
        self.assertIsNone(ps.game_map.layout)
        self.assertEqual(list(ps.game_map.obstacles), [])
        self.assertEqual(ps.enemies, [])

    def test_the_dummy_lands_at_a_fixed_offset(self):
        """Not the dev menu's random bearing: two arenas put it in the same
        place, which is what makes a bench reproducible."""
        from game import dps_bench
        seen = []
        for _ in range(2):
            game, ps = dps_bench._start_dev_run()
            dummy = dps_bench._arm_dummy(game, ps)
            seen.append((dummy.pos.x - ps.player.pos.x, dummy.pos.y - ps.player.pos.y))
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(seen[0][1], 0.0)          # due east of the hero

    def test_the_standoff_is_inside_the_shortest_melee_reach(self):
        """The Daggers reach 22 px. A standoff outside that measures them at
        zero and the table reads as though they did nothing -- which is exactly
        what a 40 px standoff did."""
        from game import dps_bench
        reaches = [float(c["area"]) for c in get_content().weapons.values()
                   if c.get("category") == "melee"]
        self.assertLess(dps_bench.STANDOFF, min(reaches))

    def test_spawns_are_frozen_and_the_dummy_is_metered(self):
        from game import dps_bench
        game, ps = dps_bench._start_dev_run()
        dummy = dps_bench._arm_dummy(game, ps)
        self.assertTrue(ps.spawn.master.frozen)
        self.assertTrue(ps.dps.armed)
        self.assertIs(ps.dps.target, dummy)
        self.assertTrue(ps._dev_unlimited_hp)

    def test_isolate_clears_everything_but_the_dummy(self):
        from game import dps_bench
        game, ps = dps_bench._start_dev_run()
        dummy = dps_bench._arm_dummy(game, ps)
        other = ps.spawn.spawn_enemy("chaser", at=dummy.pos, owner="dev")
        self.assertIsNotNone(other)
        dps_bench._isolate(ps, dummy)
        self.assertFalse(other.alive)
        self.assertTrue(dummy.alive)
