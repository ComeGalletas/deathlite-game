"""Which enemies swing, and how long the wind-up runs.

The elite and the tank used to carry `contact_damage_enabled: false` -- the
flag that hands the damage to a melee hitbox -- while their behaviour was
plain `path_chase`, which has no attack. They dealt no damage at all.
Both run the chaser's `path_chase_attack` beat now, with a wind-up 15 %
longer than the chaser's so the ring is easier to read coming.
"""
import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from entities.ai import build_behavior
from game.content import get_content

MELEE = ("chaser", "shielded", "elite", "tank")
WINDUP_BONUS = 1.15

# Every behaviour that carries its own damage, so an enemy may hand its
# contact bite over to one.
ATTACKING = frozenset({"path_chase_attack", "brute", "fsm_charger",
                       "fsm_teleporter", "fsm_warlock", "exploder",
                       "summoner", "kite_shoot"})


def _sprites() -> dict:
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "data" / "enemy_sprites.json").read_text(encoding="utf-8"))


class MeleeRosterTests(unittest.TestCase):
    def setUp(self):
        self.enemies = get_content().enemies

    def test_the_melee_enemies_run_the_attack_beat(self):
        for eid in MELEE:
            with self.subTest(eid):
                self.assertEqual(self.enemies[eid]["behavior"], "path_chase_attack")

    def test_nothing_that_disables_contact_damage_is_left_harmless(self):
        """`contact_damage_enabled: false` says "a hitbox deals my damage".
        An enemy that says that and has no attack does nothing at all --
        which is exactly what the elite and the tank did."""
        for eid, cfg in self.enemies.items():
            if cfg.get("contact_damage_enabled", True):
                continue
            with self.subTest(eid):
                self.assertIn(cfg["behavior"], ATTACKING,
                              f"{eid} deals no contact damage and never attacks")

    def test_the_shielded_one_keeps_the_chasers_timing_exactly(self):
        """Asked for by name: the bulwark swings on the chaser's beat, not
        the elite's and the tank's longer wind-up."""
        chaser, shielded = self.enemies["chaser"], self.enemies["shielded"]
        self.assertEqual(shielded["attack_telegraph"], chaser["attack_telegraph"])
        self.assertEqual(shielded["attack_active"], chaser["attack_active"])

    def test_the_new_windup_is_15_percent_over_the_chaser(self):
        chaser = self.enemies["chaser"]["attack_telegraph"]
        for eid in ("elite", "tank"):
            with self.subTest(eid):
                self.assertAlmostEqual(self.enemies[eid]["attack_telegraph"],
                                       chaser * WINDUP_BONUS, places=3)

    def test_the_swing_lasts_as_long_as_the_attack_animation(self):
        """Wind-up plus swing covers the rig's attack strip, so the art
        plays out instead of being cut back to `walk` mid-swing."""
        rigs = _sprites()
        for eid in ("elite", "tank"):
            with self.subTest(eid):
                cfg = self.enemies[eid]
                strip = rigs[cfg["sprite"]]["anims"]["attack"]
                beat = cfg["attack_telegraph"] + cfg["attack_active"]
                self.assertAlmostEqual(beat, strip["frames"] / strip["fps"], places=2)

    def test_every_melee_enemy_has_the_art_to_show_it(self):
        rigs = _sprites()
        for eid in MELEE:
            with self.subTest(eid):
                self.assertIn("attack", rigs[self.enemies[eid]["sprite"]]["anims"])

    def test_the_beat_builds_with_the_four_states(self):
        for eid in MELEE:
            with self.subTest(eid):
                b = build_behavior("path_chase_attack", self.enemies[eid])
                # `aggro_idle` is the pursuit-timer wrapper every enemy
                # with an `aggro_range` gets (LD-9 D7).
                self.assertEqual(sorted(b.states),
                                 ["aggro_idle", "attack", "chase", "recover",
                                  "telegraph"])


if __name__ == "__main__":
    unittest.main()
