"""The Tusked Lance (pig rider): its `sweep` pattern, its charge cycle, and
the rule that picks which boss a run faces.

The boss pool only means something if a pattern id that nothing handles is
caught -- `_fire_pattern` falls through silently on an unknown id, so a typo in
`bosses.json` would ship a boss that telegraphs and then does nothing at all.
`EveryPatternBitesTests` is the guard for that, over every boss in the data.
"""
import random
import unittest
from types import SimpleNamespace

import pygame

from entities.boss import Boss
from game.content import get_content
from game import config
from game.states.playing.core.spawning import EnemyControl, boss_spawn_point
from tests import worlds as W
from tests.aictx import ai_ctx

LANCE = "the_tusked_lance"


def lance(x=0, y=0):
    return Boss(LANCE, get_content().boss(LANCE), x, y)


def sink_ctx(dt, sink, player=(300, 0)):
    return ai_ctx(
        dt=dt, player=player,
        fire_projectile=lambda **kw: sink["fired"].append(kw),
        summon=lambda eid, pos, n: sink["summoned"].append((eid, n)),
        explosion=lambda pos, r, d: sink["blasts"].append((r, d)),
        spawn_hazard=lambda pos, r, dps, dur, tick_interval=None, sprite=None:
            sink["hazards"].append((r, dps, dur)),
        melee_hit=lambda pos, r, dmg, dur:
            sink["melee"].append((pygame.Vector2(pos), r, dmg, dur)))


def new_sink():
    return {"fired": [], "summoned": [], "blasts": [], "hazards": [], "melee": []}


def run_to(b, sink, pid, phase, limit=6000):
    """Step until the boss is in `phase` of pattern `pid`."""
    for _ in range(limit):
        if b.pattern and b.pattern.get("id") == pid and b.phase == phase:
            return True
        b.update(sink_ctx(1 / 60, sink))
    return False


class SweepTests(unittest.TestCase):
    """`sweep`: a ring of melee centred on the boss."""

    def test_the_sweep_lands_a_melee_hitbox_on_the_boss(self):
        b, sink = lance(140, -60), new_sink()
        self.assertTrue(run_to(b, sink, "sweep", "telegraph"))
        self.assertEqual(sink["melee"], [], "the sweep hit during its telegraph")
        while b.phase == "telegraph":
            b.update(sink_ctx(1 / 60, sink))
        self.assertEqual(len(sink["melee"]), 1)
        pos, radius, damage, duration = sink["melee"][0]
        pat = next(p for p in b.cfg["patterns"] if p["id"] == "sweep")
        self.assertEqual(radius, pat["sweep_radius"])
        self.assertEqual(damage, pat["sweep_damage"])
        self.assertEqual(duration, pat["duration"])
        # Centred on the boss, which is what makes a static hitbox correct:
        # every pattern but `charge` holds the boss still while it is active.
        self.assertLess((pos - b.pos).length(), 1.0)

    def test_the_boss_holds_still_through_its_own_sweep(self):
        b, sink = lance(140, -60), new_sink()
        self.assertTrue(run_to(b, sink, "sweep", "active"))
        start = pygame.Vector2(b.pos)
        while b.phase == "active":
            b.update(sink_ctx(1 / 60, sink))
        self.assertLess((b.pos - start).length(), 1.0,
                        "the boss drifted away from the hitbox it just left")

    def test_the_sweep_fires_no_projectile(self):
        # It reads as a spear arc, not a bullet ring -- an earlier design note
        # had this pattern wrong and the data must not drift back.
        b, sink = lance(140, -60), new_sink()
        self.assertTrue(run_to(b, sink, "sweep", "recover"))
        self.assertEqual(sink["fired"], [])


class ChargeCycleTests(unittest.TestCase):
    """charge + sweep + a three-dash flurry, all from the data."""

    def test_it_cycles_every_pattern_it_is_given(self):
        """Every authored entry comes round, and the cycle is built from the
        two ids this boss has code for.

        Deliberately not an assertion on the exact sequence: the entry list is
        tuning, and pinning it would fail a wiring test every time the flurry
        is rebalanced.
        """
        b, sink = lance(), new_sink()
        seen = set()
        for _ in range(9000):
            b.update(sink_ctx(1 / 30, sink))
            if b.pattern:
                seen.add(id(b.pattern))
        self.assertEqual({p["id"] for p in b.cfg["patterns"]}, {"charge", "sweep"})
        self.assertEqual(len(seen), len(b.cfg["patterns"]),
                         "some authored pattern never came round")

    def test_the_flurry_is_three_short_charges_in_a_row(self):
        # The triple-charge is data, not code: three `charge` entries with a
        # shorter telegraph than the opening one.
        pats = lance().cfg["patterns"]
        opener, flurry = pats[0], pats[2:]
        self.assertEqual([p["id"] for p in flurry], ["charge"] * 3)
        for p in flurry:
            self.assertLess(p["telegraph"], opener["telegraph"])
            self.assertGreater(p["charge_speed"], opener["charge_speed"])

    def test_a_charge_dash_plays_the_locomotion_animation(self):
        # A held spear pose sliding across the ground reads as a bug; the
        # gallop reads as a charge. The telegraph still plays the wind-up.
        b, sink = lance(), new_sink()
        self.assertTrue(run_to(b, sink, "charge", "telegraph"))
        self.assertEqual(b._anim_name(), "attack")
        while b.phase == "telegraph":
            b.update(sink_ctx(1 / 60, sink))
        self.assertEqual(b.phase, "active")
        self.assertEqual(b._anim_name(), "walk")

    def test_the_sweep_still_plays_the_attack_animation_while_active(self):
        b, sink = lance(140, -60), new_sink()
        self.assertTrue(run_to(b, sink, "sweep", "active"))
        self.assertEqual(b._anim_name(), "attack")

    def test_it_walks_the_ground_rather_than_flying(self):
        b = lance()
        self.assertNotIn("flying", b.tags)
        self.assertFalse(b.flying)


class GroundSpawnTests(unittest.TestCase):
    """A boss that walks has to be *put* on ground it can walk on.

    The ring the flyer uses is blind to what is under it -- water and the void
    between islands included -- so The Tusked Lance used to land in the sea and
    stand there for the rest of the run. The search is the fix; these are its
    two halves: the flyer still gets one blind point, the walker gets ground.
    """

    def test_a_walking_boss_is_never_placed_off_walkable_ground(self):
        gm = W.game_map(W.SEEDS[0])
        content = get_content()
        definition = content.boss(LANCE)
        radius = float(definition["radius"])
        start = gm.layout.room(gm.layout.start_id).center
        for seed in range(24):
            ps = SimpleNamespace(player=SimpleNamespace(pos=pygame.Vector2(start)),
                                 rng=random.Random(seed), game_map=gm)
            p = EnemyControl.boss_spawn_point(SimpleNamespace(ps=ps), definition)
            self.assertTrue(gm.is_walkable(p, radius),
                            f"seed {seed}: the lance spawned at {p} on nothing")

    def test_the_flyer_keeps_the_blind_point_at_the_configured_distance(self):
        gm = W.game_map(W.SEEDS[0])
        definition = get_content().boss("the_first_hunger")
        self.assertIn("flying", definition["tags"])
        start = gm.layout.room(gm.layout.start_id).center
        for seed in range(8):
            ps = SimpleNamespace(player=SimpleNamespace(pos=pygame.Vector2(start)),
                                 rng=random.Random(seed), game_map=gm)
            p = EnemyControl.boss_spawn_point(SimpleNamespace(ps=ps), definition)
            self.assertAlmostEqual((p - pygame.Vector2(start)).length(),
                                   config.BOSS_SPAWN_DISTANCE, places=3)

    def test_the_search_stays_on_the_ring_when_the_first_spot_is_good(self):
        # Everything walkable: the search must not drift off the intended
        # distance just because it is now a search.
        hero = pygame.Vector2(3000, 3000)
        for seed in range(8):
            p = boss_spawn_point(hero, random.Random(seed), 6000, 6000,
                                 walkable=lambda spot: True)
            self.assertAlmostEqual((p - hero).length(),
                                   config.BOSS_SPAWN_DISTANCE, places=5)

    def test_it_falls_back_to_a_point_rather_than_failing_to_spawn(self):
        # A world with no walkable spot anywhere still has to produce a boss.
        hero = pygame.Vector2(3000, 3000)
        p = boss_spawn_point(hero, random.Random(3), 6000, 6000,
                             walkable=lambda spot: False)
        self.assertAlmostEqual((p - hero).length(),
                               config.BOSS_SPAWN_DISTANCE, places=5)

    def test_the_side_is_still_drawn_from_the_rng(self):
        hero = pygame.Vector2(3000, 3000)
        seen = {tuple(boss_spawn_point(hero, random.Random(seed), 6000, 6000,
                                       walkable=lambda spot: True))
                for seed in range(12)}
        self.assertGreater(len(seen), 6, "the ring search collapsed the side")


class ClosingSprintTests(unittest.TestCase):
    """Out of `vision_range` a boss only closes, so it closes fast (owner,
    2026-09-12): a ground spawn can now be a long way out and a patrol-speed
    approach is dead time. The sprint ends the moment the hero is in sight."""

    def _step(self, b, sink, player):
        before = pygame.Vector2(b.pos)
        b.update(sink_ctx(1 / 60, sink, player=player))
        return (b.pos - before).length() * 60.0

    def test_it_closes_at_the_configured_multiple_of_its_speed(self):
        b, sink = lance(), new_sink()
        far = (b.vision_range * 3, 0)
        speed = self._step(b, sink, far)
        self.assertTrue(b.closing)
        self.assertAlmostEqual(speed, b.speed * config.BOSS_CLOSING_SPEED_MULT,
                               delta=1.0)

    def test_the_sprint_is_three_times_the_walk(self):
        self.assertAlmostEqual(config.BOSS_CLOSING_SPEED_MULT, 3.0)
        self.assertAlmostEqual(lance().closing_speed, 3.0)

    def test_it_drops_back_to_walking_speed_once_the_hero_is_in_sight(self):
        b, sink = lance(), new_sink()
        near = (b.vision_range * 0.5, 0)
        for _ in range(4):                      # past the intro phase
            b.update(sink_ctx(1 / 60, sink, player=near))
        self.assertFalse(b.closing)
        self.assertLessEqual(self._step(b, sink, near), b.speed + 1.0)

    def test_the_flyer_sprints_too(self):
        # The rule is the boss FSM's, not the pig rider's: nothing about it
        # depends on walking, and the bat can be pushed out of sight as well.
        content = get_content()
        b = Boss("the_first_hunger", content.boss("the_first_hunger"), 0, 0)
        sink = new_sink()
        speed = self._step(b, sink, (b.vision_range * 3, 0))
        self.assertTrue(b.closing)
        self.assertAlmostEqual(speed, b.speed * config.BOSS_CLOSING_SPEED_MULT,
                               delta=1.0)

    def test_a_definition_may_override_the_multiplier(self):
        cfg = dict(get_content().boss(LANCE))
        cfg["closing_speed_mult"] = 1.0
        self.assertAlmostEqual(Boss(LANCE, cfg, 0, 0).closing_speed, 1.0)

class EveryPatternBitesTests(unittest.TestCase):
    """Every authored pattern, on every boss, must actually do something."""

    def test_no_boss_ships_a_pattern_id_nothing_handles(self):
        content = get_content()
        for boss_id in content.bosses:
            b = Boss(boss_id, content.boss(boss_id), 0, 0)
            for pattern in b.cfg["patterns"]:
                sink = new_sink()
                b.pattern = pattern
                b._charge_dir = pygame.Vector2()
                b._fire_pattern(sink_ctx(1 / 60, sink))
                did = (any(sink[k] for k in
                           ("fired", "summoned", "blasts", "hazards", "melee"))
                       or b._charge_dir.length_squared() > 0)
                self.assertTrue(did, f"{boss_id}: pattern "
                                     f"{pattern['id']!r} did nothing")


class RigTests(unittest.TestCase):
    """The sprite the definition names has to exist and be animatable."""

    def test_the_named_rig_exists_with_the_states_the_fsm_plays(self):
        content = get_content()
        for boss_id in content.bosses:
            rig_name = content.boss(boss_id)["sprite"]
            rig = content.sprites.get(rig_name)
            self.assertIsNotNone(rig, f"{boss_id}: no rig {rig_name!r}")
            for state in ("idle", "walk", "attack"):
                self.assertIn(state, rig["anims"],
                              f"{rig_name}: the boss FSM plays {state!r}")

    def test_the_pig_riders_anchor_sits_inside_its_scaled_sprite(self):
        rig = get_content().sprites["pig_rider"]
        (ax, ay), (sw, sh) = rig["anchor"], rig["scale"]
        self.assertTrue(0 <= ax <= sw and 0 <= ay <= sh)
        # The anchor is the pig's feet, so it belongs at the bottom of the art.
        self.assertGreater(ay, sh * 0.9)


class BossSelectionTests(unittest.TestCase):
    """`EnemyControl.pick_boss`: which boss a run faces."""

    def picked(self, seed):
        """The shipped rule, not a copy of it: `pick_boss` reads only
        `ps.content` and `ps.run_seed`, so a stand-in `ps` exercises the real
        method."""
        ps = SimpleNamespace(content=get_content(), run_seed=seed)
        return EnemyControl.pick_boss(SimpleNamespace(ps=ps))

    def test_the_same_seed_always_gives_the_same_boss(self):
        for seed in (0, 7, 35, 1234, 99999):
            self.assertEqual(self.picked(seed), self.picked(seed))

    def test_it_only_ever_picks_a_boss_that_exists(self):
        ids = set(get_content().bosses)
        for seed in range(60):
            self.assertIn(self.picked(seed), ids)

    def test_both_bosses_are_reachable(self):
        picks = {self.picked(seed) for seed in range(60)}
        self.assertEqual(picks, set(get_content().bosses))

    def test_the_choice_does_not_ride_on_json_ordering(self):
        # pick_boss sorts the ids, so re-ordering bosses.json must not silently
        # change which boss every existing seed faces.
        ids = sorted(get_content().bosses)
        shuffled = list(reversed(ids))
        for seed in range(30):
            self.assertEqual(random.Random(f"{seed}:boss").choice(ids),
                             random.Random(f"{seed}:boss").choice(sorted(shuffled)))
