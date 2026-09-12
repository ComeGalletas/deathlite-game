"""`game/states/playing/run_ledger.py`: the run-wide damage and kill ledger
the game-over screen reads.

Hand-built objects, no world: the ledger only needs things with a
`weapon_id` / `name` / `level` (a weapon) and an `enemy_id` / `boss_id` /
`name` (something that died). What is pinned:

* attribution follows the source string, the villager is dropped and an
  unnamed path lands in the `other` bucket -- the same rules as the meter;
* a weapon's DPS is over the time it was *held*, a proc's over the time
  since its first hit, and a source with no span reads zero, not infinity;
* kills are counted per type with the display name kept, the boss under its
  own id;
* the rows the screen draws: weapons in slot order, the rest biggest first.
"""
import unittest
from types import SimpleNamespace

from game.states.playing.dps_meter import UNATTRIBUTED, VILLAGER
from game.states.playing.run_ledger import RunLedger


def _weapon(wid, name, level=1):
    return SimpleNamespace(weapon_id=wid, name=name, level=level)


class RecordTests(unittest.TestCase):
    def test_damage_is_summed_per_source(self):
        led = RunLedger()
        led.record(10.0, "sword")
        led.record(5.0, "sword")
        led.record(3.0, "bow")
        self.assertEqual(led.damage, {"sword": 15.0, "bow": 3.0})
        self.assertEqual(led.total, 18.0)

    def test_the_villager_is_not_the_hero(self):
        led = RunLedger()
        led.record(40.0, VILLAGER)
        self.assertEqual(led.damage, {})

    def test_an_unnamed_path_lands_in_other(self):
        led = RunLedger()
        led.record(7.0, None)
        self.assertEqual(led.damage, {UNATTRIBUTED: 7.0})

    def test_an_empty_source_is_unnamed_too(self):
        """A projectile whose `weapon_id` was never set arrives as `""`; it
        must file under `other`, not under a blank name."""
        led = RunLedger()
        led.record(7.0, "")
        self.assertEqual(led.damage, {UNATTRIBUTED: 7.0})

    def test_zero_and_negative_are_ignored(self):
        led = RunLedger()
        led.record(0.0, "sword")
        led.record(-2.0, "sword")
        self.assertEqual(led.damage, {})

    def test_first_hit_is_stamped_with_the_clock(self):
        led = RunLedger()
        led.now = 12.5
        led.record(1.0, "bow")
        led.now = 20.0
        led.record(1.0, "bow")
        self.assertEqual(led.first_hit["bow"], 12.5)


class SpanTests(unittest.TestCase):
    def test_a_weapon_is_measured_over_the_time_it_was_held(self):
        """Picked up at t=100, hitting from t=130, run ends at t=200: the DPS
        is over the 100 s held, not the 200 s run or the 70 s since the first
        hit."""
        led = RunLedger()
        led.now = 100.0
        led.track_held(["bow"])
        led.now = 130.0
        led.record(500.0, "bow")
        self.assertEqual(led.span_of("bow", 200.0), 100.0)
        self.assertAlmostEqual(led.dps_of("bow", 200.0), 5.0)

    def test_track_held_keeps_the_first_sighting(self):
        led = RunLedger()
        led.now = 10.0
        led.track_held(["sword"])
        led.now = 50.0
        led.track_held(["sword", "bow"])
        self.assertEqual(led.held_since, {"sword": 10.0, "bow": 50.0})

    def test_a_proc_is_measured_from_its_first_hit(self):
        led = RunLedger()
        led.now = 40.0
        led.record(60.0, "fire_nova")
        self.assertAlmostEqual(led.dps_of("fire_nova", 100.0), 1.0)

    def test_no_span_reads_zero_not_infinity(self):
        led = RunLedger()
        led.record(60.0, "sword")             # at t=0, end at t=0
        self.assertEqual(led.dps_of("sword", 0.0), 0.0)
        self.assertEqual(led.dps_of("never_hit", 10.0), 0.0)

    def test_the_end_defaults_to_now(self):
        led = RunLedger()
        led.track_held(["sword"])
        led.now = 10.0
        led.record(30.0, "sword")
        self.assertAlmostEqual(led.dps_of("sword"), 3.0)


class KillTests(unittest.TestCase):
    def test_kills_are_counted_per_type_with_the_name_kept(self):
        led = RunLedger()
        for _ in range(3):
            led.kill(SimpleNamespace(enemy_id="chaser", name="Husk"))
        led.kill(SimpleNamespace(enemy_id="tank", name="Brute"))
        self.assertEqual(led.kills, {"chaser": 3, "tank": 1})
        self.assertEqual(led.kill_names, {"chaser": "Husk", "tank": "Brute"})
        self.assertEqual(led.total_kills, 4)

    def test_the_boss_counts_under_its_own_id(self):
        led = RunLedger()
        led.kill(SimpleNamespace(boss_id="warden", name="The Warden"))
        self.assertEqual(led.kill_rows(), [("The Warden", 1)])

    def test_kill_rows_are_biggest_first_then_by_id(self):
        led = RunLedger()
        led.kill(SimpleNamespace(enemy_id="tank", name="Brute"))
        for _ in range(2):
            led.kill(SimpleNamespace(enemy_id="fast", name="Skitter"))
        led.kill(SimpleNamespace(enemy_id="chaser", name="Husk"))
        self.assertEqual(led.kill_rows(),
                         [("Skitter", 2), ("Husk", 1), ("Brute", 1)])


class RowTests(unittest.TestCase):
    def _ledger(self):
        led = RunLedger()
        led.track_held(["sword", "bow"])
        led.now = 100.0
        led.record(300.0, "sword")
        led.record(100.0, "bow")
        led.record(80.0, "fire_nova")
        led.record(20.0, None)
        return led

    def test_weapon_rows_follow_slot_order_and_carry_share_and_dps(self):
        led = self._ledger()
        rows = led.weapon_rows([_weapon("bow", "Bow", 2), _weapon("sword", "Sword", 4)], 100.0)
        self.assertEqual([r["id"] for r in rows], ["bow", "sword"])
        self.assertEqual(rows[1]["name"], "Sword")
        self.assertEqual(rows[1]["level"], 4)
        self.assertEqual(rows[1]["damage"], 300.0)
        self.assertAlmostEqual(rows[1]["share"], 0.6)
        self.assertAlmostEqual(rows[1]["dps"], 3.0)

    def test_a_held_weapon_that_never_hit_still_gets_a_row(self):
        led = self._ledger()
        rows = led.weapon_rows([_weapon("hammer", "Hammer")], 100.0)
        self.assertEqual(rows[0]["damage"], 0.0)
        self.assertEqual(rows[0]["dps"], 0.0)
        self.assertEqual(rows[0]["share"], 0.0)

    def test_other_rows_are_the_non_weapon_sources_biggest_first(self):
        led = self._ledger()
        rows = led.other_rows(["sword", "bow"], {"fire_nova": "Fire Nova"}, 100.0)
        self.assertEqual([r["id"] for r in rows], ["fire_nova", UNATTRIBUTED])
        self.assertEqual(rows[0]["name"], "Fire Nova")
        self.assertIsNone(rows[0]["level"])
        self.assertAlmostEqual(rows[0]["share"], 0.16)

    def test_an_unnamed_source_is_titled_from_its_id(self):
        led = self._ledger()
        rows = led.other_rows(["sword", "bow"], None, 100.0)
        self.assertEqual(rows[0]["name"], "Fire Nova")

    def test_a_weapon_the_run_let_go_of_moves_to_the_other_rows(self):
        """A weapon in the ledger but no longer held: its damage is not
        lost, it just is not a weapon row any more."""
        led = self._ledger()
        rows = led.other_rows(["sword"], {"bow": "Bow"}, 100.0)
        self.assertIn("bow", [r["id"] for r in rows])

    def test_shares_are_zero_with_no_damage(self):
        led = RunLedger()
        rows = led.weapon_rows([_weapon("sword", "Sword")], 10.0)
        self.assertEqual(rows[0]["share"], 0.0)
        self.assertEqual(led.other_rows(["sword"]), [])


if __name__ == "__main__":
    unittest.main()
