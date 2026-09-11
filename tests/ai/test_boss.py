"""Milestone 4: boss FSM -- pattern cycling, telegraph-before-damage,
distinct pattern effects, health fraction, death (spec 3.7)."""
import unittest


from entities.boss import Boss
from tests.aictx import ai_ctx
from game.content import get_content


def boss():
    bid = next(iter(get_content().bosses))
    return Boss(bid, get_content().boss(bid), 0, 0)


def ctx(dt, sink):
    return ai_ctx(
        dt=dt, player=(300, 0),
        fire_projectile=lambda **kw: sink["fired"].append(kw),
        summon=lambda eid, pos, n: sink["summoned"].append((eid, n)))


class BossTests(unittest.TestCase):
    def test_hp_fraction_and_death(self):
        b = boss()
        self.assertEqual(b.hp_fraction, 1.0)
        b.take_damage(b.max_hp / 2)
        self.assertAlmostEqual(b.hp_fraction, 0.5, places=3)
        b.take_damage(b.max_hp)
        self.assertFalse(b.alive)
        self.assertEqual(b.hp_fraction, 0.0)

    def test_cycles_through_all_three_patterns(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        seen = set()
        for _ in range(4000):
            b.update(ctx(1 / 30, sink))
            if b.pattern:
                seen.add(b.pattern["id"])
        self.assertEqual(seen, {"radial_barrage", "charge", "summon_brood"})

    def test_no_damage_output_during_telegraph(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        # step until the first telegraph of the radial pattern
        while not (b.phase == "telegraph" and b.pattern.get("id") == "radial_barrage"):
            b.update(ctx(1 / 60, sink))
        self.assertEqual(sink["fired"], [], "bullets fired before telegraph ended")
        # run the telegraph out
        guard = 0
        while b.phase == "telegraph" and guard < 1000:
            b.update(ctx(1 / 60, sink))
            guard += 1
        self.assertTrue(sink["fired"], "radial barrage never fired after telegraph")

    def test_radial_barrage_fires_ring_of_bullets(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        pat = next(p for p in b.cfg["patterns"] if p["id"] == "radial_barrage")
        for _ in range(6000):
            b.update(ctx(1 / 30, sink))
            if len(sink["fired"]) >= pat["bullets"]:
                break
        self.assertGreaterEqual(len(sink["fired"]), pat["bullets"])

    def test_summon_pattern_calls_summon(self):
        b = boss()
        sink = {"fired": [], "summoned": []}
        for _ in range(9000):
            b.update(ctx(1 / 30, sink))
            if sink["summoned"]:
                break
        self.assertTrue(sink["summoned"])
        self.assertEqual(sink["summoned"][0][0], "swarm")


class BossVisionTests(unittest.TestCase):
    """Beyond `vision_range` the boss only closes in on the player at full
    speed with its pattern clock held; inside it the cycle resumes where it
    left off. A committed charge is never interrupted."""

    def _sink(self):
        return {"fired": [], "summoned": []}

    def _ctx(self, dt, sink, player):
        return ai_ctx(dt=dt, player=player,
                      fire_projectile=lambda **kw: sink["fired"].append(kw),
                      summon=lambda eid, pos, n: sink["summoned"].append((eid, n)))

    def test_the_vision_range_covers_the_whole_view(self):
        import math
        from game import config
        b = boss()
        half_w = config.SCREEN_WIDTH / config.CAMERA_ZOOM / 2
        half_h = config.SCREEN_HEIGHT / config.CAMERA_ZOOM / 2
        self.assertGreaterEqual(b.vision_range, math.hypot(half_w, half_h))

    def test_out_of_sight_the_boss_only_closes_in(self):
        b = boss()
        sink = self._sink()
        t0 = b.phase_t
        for _ in range(600):                          # 20 s -- several cycles' worth
            far = (b.pos.x + b.vision_range + 800, 0)   # always out of sight, due east
            b.update(self._ctx(1 / 30, sink, far))
        self.assertTrue(b.closing)
        self.assertEqual(sink["fired"], [])
        self.assertEqual(sink["summoned"], [])
        self.assertEqual(b.phase, "intro")           # the clock never moved
        self.assertEqual(b.phase_t, t0)
        self.assertAlmostEqual(b.vel.length(), b.speed, places=3)   # full speed
        self.assertGreater(b.pos.x, 0.0)             # straight at the player
        self.assertEqual(b._anim_name(), "walk")

    def test_back_in_range_the_cycle_resumes_where_it_left(self):
        b = boss()
        sink = self._sink()
        near = (300, 0)
        while not (b.phase == "telegraph" and b.pattern.get("id") == "radial_barrage"):
            b.update(self._ctx(1 / 60, sink, near))
        held = b.phase_t
        b.pos.update(0, 0)
        for _ in range(120):
            b.update(self._ctx(1 / 60, sink, (b.pos.x + b.vision_range + 500, 0)))
        self.assertTrue(b.closing)
        self.assertEqual(b.phase, "telegraph")
        self.assertEqual(b.phase_t, held)
        self.assertEqual(b.telegraph_fraction, 1.0 - held / b.phase_len)
        self.assertEqual(sink["fired"], [])
        b.update(self._ctx(1 / 60, sink, (b.pos.x + 200, 0)))
        self.assertFalse(b.closing)
        self.assertLess(b.phase_t, held)
        self.assertEqual(b._anim_name(), "attack")

    def test_a_committed_charge_is_not_interrupted(self):
        b = boss()
        sink = self._sink()
        while not (b.phase == "active" and b.pattern.get("id") == "charge"):
            b.update(self._ctx(1 / 60, sink, (300, 0)))
        far = (b.pos.x + b.vision_range + 500, 0)
        b.update(self._ctx(1 / 60, sink, far))
        self.assertFalse(b.closing)
        self.assertEqual(b.phase, "active")
        self.assertAlmostEqual(b.vel.length(), float(b.pattern["charge_speed"]), places=3)


class BossSpriteTests(unittest.TestCase):
    def test_boss_has_an_animator_and_phase_anim_map(self):
        from systems.animation import Animator
        b = boss()
        self.assertIsInstance(b.anim, Animator)
        self.assertEqual(b.anim.rig, "giant_bat")
        b.phase = "intro"
        self.assertEqual(b._anim_name(), "idle")
        b.phase = "telegraph"
        self.assertEqual(b._anim_name(), "attack")
        b.phase = "active"
        self.assertEqual(b._anim_name(), "attack")
        b.phase = "recover"
        self.assertIn(b._anim_name(), ("idle", "walk"))
        b.alive = False
        self.assertEqual(b._anim_name(), "death")

    def test_hit_sets_the_tint_timer(self):
        b = boss()
        b.take_damage(50.0)
        self.assertGreater(b._hurt_t, 0.0)


if __name__ == "__main__":
    unittest.main()
