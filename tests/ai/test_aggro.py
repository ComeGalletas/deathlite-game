"""LD-9 phase D7: aggro range and the pursuit timer.

Before this, every enemy chased from anywhere on the map for ever. On the
height-map worlds that is untenable -- movement between terraces is by
staircase only, so the flow field will route an enemy the length of an island
to reach a player one tile away across a drop.

The gate is applied once, in `registry.build_behavior`, so it covers all twelve
enemy types and the boss without any builder knowing about it. `aggro_range`
and `pursuit_seconds` live in `data/enemies.json`; a type carrying neither is
returned untouched, which is how the boss keeps chasing unconditionally.
"""
import unittest

import pygame

from entities.ai.components.aggro import is_aggroed
from entities.ai.registry import build_behavior
from entities.enemy import Enemy
from game.content import get_content
from tests.aictx import ai_ctx

DT = 1 / 60


def _enemy(eid, x, y=0.0):
    return Enemy(eid, get_content().enemy(eid), x, y)


def _run(e, player_x, seconds, now=0.0):
    """Tick for `seconds`, returning distance travelled and the final clock."""
    travel = 0.0
    for _ in range(int(seconds / DT)):
        px = player_x(now) if callable(player_x) else player_x
        c = ai_ctx(dt=DT, player=(px, 0.0), now=now)
        before = pygame.Vector2(e.pos)
        e.update(c)
        travel += (e.pos - before).length()
        now += DT
    return travel, now


class AggroDataTests(unittest.TestCase):
    def test_every_enemy_type_declares_both_values(self):
        """A new type that forgets them silently reverts to chasing for ever,
        which is the behaviour this phase exists to remove."""
        for eid, cfg in get_content().enemies.items():
            self.assertIn("aggro_range", cfg, eid)
            self.assertIn("pursuit_seconds", cfg, eid)
            self.assertGreater(cfg["aggro_range"], 0, eid)
            self.assertGreater(cfg["pursuit_seconds"], 0, eid)

    def test_a_type_with_no_values_is_left_alone(self):
        base = build_behavior("path_chase", {})
        self.assertNotIn("aggro_idle", base.states)


class AggroBehaviourTests(unittest.TestCase):
    def test_a_distant_enemy_does_not_pursue(self):
        e = _enemy("chaser", 2000.0)
        travel, _ = _run(e, 0.0, 4.0)
        speed = get_content().enemy("chaser")["speed"]
        # it drifts (the idle wander) but nothing like a chase
        self.assertLess(travel, speed * 4.0 * 0.5)
        self.assertGreater(e.pos.x, 1800.0, "it closed on the player anyway")

    def test_an_enemy_inside_the_ring_pursues(self):
        cfg = get_content().enemy("chaser")
        start = cfg["aggro_range"] * 0.7
        e = _enemy("chaser", start)
        travel, _ = _run(e, 0.0, 4.0)
        # It closes the gap and then stops to attack, so the distance travelled
        # is the gap itself -- not four seconds of running.
        self.assertGreater(travel, start * 0.9)
        self.assertLess(e.pos.x, 40.0, "it never reached the player")

    def test_being_attacked_provokes_from_out_of_range(self):
        e = _enemy("chaser", 2000.0)
        e.take_damage(1.0)
        travel, _ = _run(e, 0.0, 3.0)
        self.assertGreater(travel, get_content().enemy("chaser")["speed"] * 3.0 * 0.8)

    def test_the_timer_refreshes_in_range_then_counts_down_on_leaving(self):
        cfg = get_content().enemy("chaser")
        secs = cfg["pursuit_seconds"]
        e = _enemy("chaser", cfg["aggro_range"] * 0.7)
        left_at = 2.0
        now = 0.0
        dropped = None
        for _ in range(int((left_at + secs + 3.0) / DT)):
            px = 0.0 if now < left_at else 50000.0
            c = ai_ctx(dt=DT, player=(px, 0.0), now=now)
            e.update(c)
            if dropped is None and now > left_at and not is_aggroed(e, c):
                dropped = now
            now += DT
        self.assertIsNotNone(dropped, "aggro never expired")
        # held for `pursuit_seconds` after the player left, not after arrival --
        # the deadline is refreshed every frame the player is in range
        self.assertAlmostEqual(dropped - left_at, secs, delta=3 * DT)

    def test_giving_up_leaves_it_wandering_not_frozen(self):
        cfg = get_content().enemy("chaser")
        e = _enemy("chaser", 50000.0)
        travel, _ = _run(e, 0.0, 6.0)
        self.assertGreater(travel, 0.0, "an idle enemy is a statue")
        self.assertLess(travel, cfg["speed"] * 6.0 * 0.5)


if __name__ == "__main__":
    unittest.main()
