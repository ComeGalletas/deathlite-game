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
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import actions, build_behavior, templates
from entities.melee_hitbox import MeleeHitbox
from game import config
from game.content import get_content
from tests import worlds as W
from world.gen import repair, spawnpoints
from world.nav.field import _INF

MELEE = ("skull", "panda", "bear", "turtle")
WINDUP_BONUS = 1.15

# Every behaviour that carries its own damage, so an enemy may hand its
# contact bite over to one.
ATTACKING = frozenset({"path_chase_attack", "brute", "fsm_charger",
                       "fsm_teleporter", "fsm_warlock", "exploder",
                       "summoner", "kite_shoot", "path_chase_summon",
                       "path_chase_sweep", "path_chase_breath"})


def _sprites() -> dict:
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    return json.loads((root / "data" / "enemies" / "enemy_sprites.json").read_text(encoding="utf-8"))


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
            if "dummy" in cfg.get("tags", ()):
                continue        # the training dummy is harmless by design
            with self.subTest(eid):
                self.assertIn(cfg["behavior"], ATTACKING,
                              f"{eid} deals no contact damage and never attacks")

    def test_the_shielded_one_keeps_the_chasers_timing_exactly(self):
        """Asked for by name: the bulwark swings on the chaser's beat, not
        the elite's and the tank's longer wind-up."""
        chaser, shielded = self.enemies["skull"], self.enemies["panda"]
        self.assertEqual(shielded["attack_telegraph"], chaser["attack_telegraph"])
        self.assertEqual(shielded["attack_active"], chaser["attack_active"])

    def test_the_new_windup_is_15_percent_over_the_chaser(self):
        chaser = self.enemies["skull"]["attack_telegraph"]
        for eid in ("bear", "turtle"):
            with self.subTest(eid):
                self.assertAlmostEqual(self.enemies[eid]["attack_telegraph"],
                                       chaser * WINDUP_BONUS, places=3)

    def test_the_swing_lasts_as_long_as_the_attack_animation(self):
        """Wind-up plus swing covers the rig's attack strip, so the art
        plays out instead of being cut back to `walk` mid-swing."""
        rigs = _sprites()
        for eid in ("bear", "turtle"):
            with self.subTest(eid):
                cfg = self.enemies[eid]
                strip = rigs[cfg["sprite"]]["anims"]["attack"]
                beat = cfg["attack_telegraph"] + cfg["attack_active"]
                self.assertAlmostEqual(beat, strip["frames"] / strip["fps"], places=2)

    def test_the_husk_attack_animation_covers_its_swing(self):
        """ENT-014: the skull's strip plays through within one frame of its
        swing -- never cut back to `walk`, never held still for long."""
        cfg = self.enemies["skull"]
        strip = _sprites()[cfg["sprite"]]["anims"]["attack"]
        beat = cfg["attack_telegraph"] + cfg["attack_active"]
        length = strip["frames"] / strip["fps"]
        self.assertLessEqual(length, beat)
        self.assertLess(beat - length, 1 / strip["fps"])

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


class _Hits:
    """The `poke` action's only call into the combat context."""
    def __init__(self):
        self.boxes = []

    def melee_hit(self, pos, radius, damage, duration):
        self.boxes.append(MeleeHitbox(pos.x, pos.y, radius, damage, duration))


class ColliderShrinkTests(unittest.TestCase):
    """ENT-020 / ENT-021: the Ravager's and Grudge's colliders are a fixed
    20 px so they fit tighter ground, and the large nav class routes them
    through every gap that size fits. The sprites keep their size, and the
    Ravager's swing keeps its reach through `attack_radius`."""

    OLD = {"bear": 22.0, "troll": 26.0}
    RADIUS = 20.0

    def setUp(self):
        self.enemies = get_content().enemies

    def _cfg(self, eid: str) -> dict:
        return templates.merged(templates.template(self.enemies[eid]["behavior"]),
                                self.enemies[eid])

    def _swing_at(self, eid: str, distance: float):
        """Fire `eid`'s poke at a hero `distance` px away; the hitbox."""
        cfg = self._cfg(eid)
        actor = SimpleNamespace(pos=pygame.Vector2(0, 0), radius=float(cfg["radius"]),
                                _base_contact=1.0)
        per = SimpleNamespace(player_pos=pygame.Vector2(distance, 0))
        hits = _Hits()
        actions.ACTIONS["poke"](cfg)(actor, per, hits)
        return hits.boxes[0]

    def test_the_colliders_are_a_fixed_20(self):
        for eid in self.OLD:
            with self.subTest(eid):
                self.assertEqual(self.enemies[eid]["radius"], self.RADIUS)

    def test_the_world_is_still_certified_for_the_wider_walkers(self):
        """ENT-021: lowering the large class's clearance to route these two
        does not lower the body world generation certifies ground for. The
        unseal repair and the large spawn points stay at 22, so the turtle
        (24) keeps the reach it had. `tests/world/test_digest.py` pins the
        world itself byte for byte."""
        self.assertEqual(repair._widest_class(), (48, 22.0))
        self.assertEqual(spawnpoints.body_radii(), (16.0, 22.0))

    def test_the_sprites_keep_their_size(self):
        rigs = _sprites()
        self.assertEqual(rigs["bear"]["scale"], [113, 96])
        self.assertEqual(rigs["troll"]["scale"], [99, 77])

    def test_the_ravager_swings_from_where_it_did(self):
        """22 + PLAYER_RADIUS + 5, the trigger before the body shrank."""
        reach = actions.TRIGGERS["melee_reach"](self._cfg("bear"))
        self.assertAlmostEqual(reach, self.OLD["bear"] + config.PLAYER_RADIUS + 5.0)

    def test_the_ravager_hitbox_is_the_one_it_had(self):
        box = self._swing_at("bear", 100.0)
        self.assertAlmostEqual(box.radius, self.OLD["bear"] / 2.0)
        self.assertAlmostEqual(box.pos.x, self.OLD["bear"])

    def test_the_grudge_slam_does_not_read_the_body(self):
        cfg = self.enemies["troll"]
        self.assertEqual((cfg["slam_range"], cfg["slam_radius"]), (60, 60))

    def test_every_poke_lands_on_a_hero_at_its_trigger_range(self):
        """The general rule the Ravager's shrink could have broken: a swing
        that starts at the trigger range reaches a hero standing there.
        Pinning only the trigger (an `attack_range`) while the hitbox still
        followed the smaller body would whiff: 37 px out against a hitbox
        edge at 1.5 x 15.4 + 10 = 33.1."""
        pokers = [eid for eid, e in self.enemies.items()
                  if e.get("behavior") == "path_chase_attack"]
        self.assertIn("bear", pokers)
        for eid in pokers:
            with self.subTest(eid):
                reach = actions.TRIGGERS["melee_reach"](self._cfg(eid))
                box = self._swing_at(eid, reach)
                self.assertTrue(box.contains(pygame.Vector2(reach, 0),
                                             config.PLAYER_RADIUS))


class ColliderRoutingTests(unittest.TestCase):
    """ENT-021: the large nav class routes the 20 px Ravager and Grudge
    through every gap they fit. World tier: reads the shared nav field of a
    pinned world (`tests/conftest.py: WORLD`)."""

    def setUp(self):
        self.enemies = get_content().enemies

    def test_the_nav_class_clearance_matches_them(self):
        """The class a body paths in asks for exactly its radius. Above it,
        the pathfinder refuses gaps the body fits (ENT-020.Q1: Grudge at
        18.2 in a 22 px class); below it, the pathfinder sends the body into
        gaps it cannot pass."""
        field = W.nav(W.SEEDS[0])
        for eid in ("bear", "troll"):
            with self.subTest(eid):
                r = float(self.enemies[eid]["radius"])
                self.assertEqual(field._min_clear[field._class_for(r)], r)

    def test_the_field_routes_them_through_a_20_px_gap(self):
        """Behaviour, not the config: on a pinned world, every open (non
        corridor) large-lattice cell with 20-22 px of clearance -- ground
        a 20 px body fits and the old 22 px class refused -- is reached
        by the large field, rebuilt toward a roomier neighbour."""
        field = W.nav(W.SEEDS[0])
        ng = field.grids["large"]
        r = float(self.enemies["bear"]["radius"])
        checked = 0
        for row in range(1, ng.rows - 1):
            for col in range(1, ng.cols - 1):
                i = row * ng.cols + col
                if not ng.walkable[i] or ng.corridor[i] or not r <= ng.clearance[i] < 22.0:
                    continue
                roomy = [(col + dc, row + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if ng.walkable[(row + dr) * ng.cols + col + dc]
                         and ng.clearance[(row + dr) * ng.cols + col + dc] >= 22.0]
                if not roomy:
                    continue
                field.rebuild(ng.world_of(*roomy[0]), only="large")
                self.assertLess(field.cost(ng.world_of(col, row), r), _INF,
                                f"cell {(col, row)} clearance {ng.clearance[i]:.1f}")
                checked += 1
                if checked >= 12:
                    return
        self.assertGreater(checked, 0, "no 20-22 px gap on the pinned world")


if __name__ == "__main__":
    unittest.main()
