"""Elemental system M3: what the four base elements actually do
(design §4, journal `elemental_system_journal.md`).

Unit tier: hand-built enemies and a recording world, no run and no Game.
Every element is driven through the real resolver, so what is pinned here is
the behaviour a weapon hit would produce, not a shortcut into the element.

The shipped numbers are read from the content rather than repeated, so a
balance pass in `elements.json` retunes the game without rewriting these.
"""
import unittest

import pygame

from combat.elements import ice as ice_rules
from combat.elements import tracking
from combat.elements.area import WindArea
from combat.elements.ids import ElementId
from combat.elements.registry import ElementRegistry
from combat.elements.resolve import ElementalResolver, Outcome
from combat.elements.thunder import Thunder
from combat.elements.tracking import ElementTracking
from combat.elements.world import NullWorld
from game.content import get_content
from systems.collision import SpatialGrid
from tests.combat.fakes import FakeEnemy

C = get_content()
FIRE, ICE, THUNDER, WIND = (ElementId.FIRE, ElementId.ICE,
                            ElementId.THUNDER, ElementId.WIND)

FIRE_CFG = C.elements["elements"]["fire"]
ICE_CFG = C.elements["elements"]["ice"]
THUNDER_CFG = C.elements["elements"]["thunder"]
WIND_CFG = C.elements["elements"]["wind"]


def build(enemies=(), *, elements=None, reactions=None, runner=None):
    """A resolver over the real four elements and a recording world."""
    data = {"global": C.elements["global"],
            "elements": elements or C.elements["elements"]}
    registry = ElementRegistry(data, reactions or C.reactions)
    tracked = ElementTracking()
    world = NullWorld(enemies, tracking=tracked)
    resolver = ElementalResolver(registry, tracking=tracked, world=world,
                                 reaction_runner=runner)
    return resolver, world, tracked


def tweak(**paths):
    """A copy of the shipped element data with dotted paths overridden:
    `tweak(**{"thunder.chain.jumps": 0})`."""
    import copy
    data = copy.deepcopy(C.elements["elements"])
    for path, value in paths.items():
        node = data
        parts = path.split(".")
        for key in parts[:-1]:
            node = node[key]
        node[parts[-1]] = value
    return data


def row(x=0.0, y=0.0, n=1, gap=40.0):
    """`n` enemies in a line, `gap` apart, starting at (x, y)."""
    return [FakeEnemy(x + i * gap, y) for i in range(n)]


# --- Fire ---------------------------------------------------------------------

class FireTests(unittest.TestCase):
    def setUp(self):
        self.enemy = FakeEnemy(0.0, 0.0)
        self.r, self.world, self.tracked = build([self.enemy])

    def hit(self, damage=100.0, now=0.0):
        return self.r.apply(self.enemy, FIRE, weapon_id="sword",
                            hit_damage=damage, now=now)

    def test_a_hit_deals_its_fraction_of_the_weapon_damage(self):
        self.hit(damage=100.0)
        frac = FIRE_CFG["hit"]["damage"]["frac"]
        self.assertAlmostEqual(self.world.dealt[0][1], 100.0 * frac)
        self.assertEqual(self.world.dealt[0][3], tracking.FIRE_HIT)

    def test_the_burn_is_bound_to_the_aura_and_uses_the_datas_interval(self):
        self.hit()
        self.assertIn("burn", self.enemy.status)
        self.assertTrue(self.enemy.status.is_bound("burn"))
        entry = self.enemy.status._active["burn"]
        self.assertEqual(entry.interval, FIRE_CFG["burn"]["tick_interval"])
        self.assertEqual(entry.effect, tracking.BURN)
        self.assertEqual(entry.source, "sword")

    def test_the_burn_lasts_exactly_as_long_as_the_aura(self):
        self.hit(now=1.0)
        self.assertAlmostEqual(self.enemy.status.remaining("burn"),
                               FIRE_CFG["aura"]["duration"])
        self.assertAlmostEqual(self.enemy.elemental.remaining(1.0),
                               FIRE_CFG["aura"]["duration"])

    def test_fire_refreshes_its_burn_and_never_stacks_it(self):
        self.hit(now=0.0)
        self.hit(now=1.0)
        self.hit(now=2.0)
        self.assertEqual(self.enemy.status.stacks("burn"), 1)
        self.assertAlmostEqual(self.enemy.status.remaining("burn"),
                               FIRE_CFG["aura"]["duration"])

    def test_a_blessing_can_still_stack_the_same_burn_row(self):
        self.enemy.status.apply("burn", 2.0, 1.0)
        self.enemy.status.apply("burn", 2.0, 1.0)
        self.assertEqual(self.enemy.status.stacks("burn"), 2,
                         "Scorch is untouched by Fire's no-stack rule")

    def test_the_burn_ticks_are_credited_to_the_burn_effect(self):
        self.hit()
        ticks = []
        self.enemy.status.update(
            FIRE_CFG["burn"]["tick_interval"],
            lambda amount, source, effect=None: ticks.append((amount, source, effect)))
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0][1:], ("sword", tracking.BURN))
        self.assertAlmostEqual(ticks[0][0], 100.0 * FIRE_CFG["burn"]["tick"]["frac"])

    def test_on_a_locked_slot_the_burn_is_standalone(self):
        self.enemy.elemental.lock(0.0, 5.0)
        self.assertEqual(self.hit(), Outcome.LOCKED)
        self.assertIn("burn", self.enemy.status)
        self.assertFalse(self.enemy.status.is_bound("burn"))

    def test_a_profile_can_switch_the_burn_off_without_stopping_the_damage(self):
        from combat.elements import profiles as prof
        profiles, _ = prof.resolve({"skull": {"elementProfile": {"burn": {"enabled": False}}}})
        self.r.profiles = profiles
        self.hit()
        self.assertNotIn("burn", self.enemy.status)
        self.assertTrue(self.world.dealt, "the hit still lands")


# --- Ice ------------------------------------------------------------------------

class IceTests(unittest.TestCase):
    def setUp(self):
        self.enemy = FakeEnemy(0.0, 0.0)
        self.r, self.world, self.tracked = build([self.enemy])
        self.required = ICE_CFG["freeze"]["stacks_required"]

    def hit(self, now=0.0, target=None):
        return self.r.apply(target or self.enemy, ICE, weapon_id="rod",
                            hit_damage=100.0, now=now)

    def test_ice_deals_no_direct_damage(self):
        self.hit()
        self.assertEqual(self.world.dealt, [], "Ice's effect is the slow")

    def test_each_hit_adds_a_stack_and_deepens_the_slow(self):
        per = ICE_CFG["slow"]["percent_per_stack"]
        for i in range(1, 3):
            self.hit(now=i * 0.1)
            self.assertEqual(self.enemy.elemental.ice_stacks, i)
            self.assertAlmostEqual(self.enemy.status.potency("chill"), per * i)

    def test_the_slow_is_capped(self):
        data = tweak(**{"ice.slow.max_percent": 0.2,
                        "ice.freeze.stacks_required": 99})
        self.r, self.world, _ = build([self.enemy], elements=data)
        for i in range(10):
            self.hit(now=i * 0.1)
        self.assertAlmostEqual(self.enemy.status.potency("chill"), 0.2)

    def test_it_freezes_at_exactly_the_threshold_and_spends_the_stacks(self):
        for i in range(self.required - 1):
            self.hit(now=i * 0.1)
            self.assertNotIn("freeze", self.enemy.status)
        self.hit(now=1.0)
        self.assertIn("freeze", self.enemy.status)
        self.assertEqual(self.enemy.elemental.ice_stacks, 0)
        self.assertAlmostEqual(self.enemy.status.remaining("freeze"),
                               ICE_CFG["freeze"]["duration"])

    def test_a_freeze_stops_the_enemy_the_way_a_stun_does(self):
        for i in range(self.required):
            self.hit(now=i * 0.1)
        self.assertTrue(self.enemy.status.is_stunned())
        self.assertEqual(self.enemy.status.speed_multiplier(), 0.0)

    def test_the_ice_aura_survives_the_freeze_that_it_triggered(self):
        for i in range(self.required):
            self.hit(now=i * 0.1)
        self.assertEqual(self.enemy.elemental.element(1.0), ICE,
                         "open item 9: the aura stays until it expires or reacts")

    def test_immunity_holds_the_stacks_instead_of_spending_them(self):
        for i in range(self.required):
            self.hit(now=i * 0.01)
        self.enemy.status.end("freeze")
        for i in range(self.required):
            self.hit(now=0.2 + i * 0.01)
        self.assertNotIn("freeze", self.enemy.status, "still inside the window")
        self.assertEqual(self.enemy.elemental.ice_stacks, self.required,
                         "clamped, so the slow does not sawtooth")

    def test_it_freezes_again_once_the_immunity_lapses(self):
        for i in range(self.required):
            self.hit(now=i * 0.01)
        self.enemy.status.end("freeze")
        after = (ICE_CFG["freeze"]["duration"]
                 + ICE_CFG["freeze"]["immunity_duration"] + 0.1)
        self.assertFalse(self.enemy.elemental.freeze_immune(after))
        # The threshold has to be reached again: the first freeze spent the
        # stacks, so this is a fresh build-up, not a single hit.
        for i in range(self.required):
            self.hit(now=after + i * 0.01)
        self.assertIn("freeze", self.enemy.status)

    def test_a_freeze_outlives_its_aura_being_consumed(self):
        runner = lambda *a: None
        self.r, self.world, _ = build([self.enemy], runner=runner)
        for i in range(self.required):
            self.hit(now=i * 0.01)
        self.assertIn("freeze", self.enemy.status)
        self.r.apply(self.enemy, FIRE, weapon_id="sword", hit_damage=10.0, now=0.2)
        self.assertNotIn("chill", self.enemy.status, "the slow was bound")
        self.assertIn("freeze", self.enemy.status,
                      "open item 8: only the slow ends with the aura")

    def test_stacks_reset_when_the_slow_has_lapsed(self):
        self.hit(now=0.0)
        self.assertEqual(self.enemy.elemental.ice_stacks, 1)
        self.enemy.status.end("chill")
        self.hit(now=0.1)
        self.assertEqual(self.enemy.elemental.ice_stacks, 1,
                         "the stacks were part of the slow")

    def test_a_profile_can_disable_freezing_but_not_the_slow(self):
        from combat.elements import profiles as prof
        profiles, _ = prof.resolve({"skull": {"elementProfile": {"freeze": {"enabled": False}}}})
        self.r.profiles = profiles
        for i in range(self.required + 2):
            self.hit(now=i * 0.1)
        self.assertNotIn("freeze", self.enemy.status)
        self.assertIn("chill", self.enemy.status)


# --- frozen contact ---------------------------------------------------------------

class FrozenContactTests(unittest.TestCase):
    def setUp(self):
        self.slider = FakeEnemy(0.0, 0.0)
        self.victim = FakeEnemy(10.0, 0.0)
        self.r, self.world, self.tracked = build([self.slider, self.victim])

    def freeze_and_shove(self, body=None, speed=200.0):
        body = body or self.slider
        body.status.apply("freeze", 2.0, 1.0, source="rod")
        body._knock.update(speed, 0.0)

    def test_a_frozen_body_being_shoved_damages_what_it_clips(self):
        self.freeze_and_shove()
        dealt = ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        self.assertGreater(dealt, 0.0)
        self.assertEqual(self.victim.damage_effects[-1], tracking.FROZEN_CONTACT)

    def test_the_damage_is_the_sliders_own_bite(self):
        self.freeze_and_shove()
        ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        expected = (self.slider.contact_damage * self.slider.contact_interval
                    * ICE_CFG["freeze"]["contact"]["damage"]["frac"])
        self.assertAlmostEqual(self.world.dealt[0][1], expected)

    def test_a_frozen_body_standing_still_clips_nothing(self):
        self.slider.status.apply("freeze", 2.0, 1.0)
        self.assertEqual(
            ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0), 0.0)

    def test_a_sliding_body_that_is_not_frozen_clips_nothing(self):
        self.slider._knock.update(200.0, 0.0)
        self.assertEqual(
            ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0), 0.0)

    def test_each_body_is_clipped_once_per_slide(self):
        self.freeze_and_shove()
        first = ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        again = ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.1)
        self.assertGreater(first, 0.0)
        self.assertEqual(again, 0.0)
        self.slider.elemental.end_slide()
        self.assertGreater(
            ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.2), 0.0)

    def test_a_contact_leaves_no_aura_so_it_cannot_chain(self):
        self.freeze_and_shove()
        ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        self.assertFalse(self.victim.elemental.has_aura(0.0))
        self.assertEqual(self.victim.knocks, [], "no knockback transfer (R30)")

    def test_it_is_credited_to_whoever_shoved_it(self):
        self.freeze_and_shove()
        self.slider.elemental.knock_source = "hammer"
        ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        self.assertEqual(self.victim.damage_sources[-1], "hammer")

    def test_it_falls_back_to_whoever_froze_it(self):
        self.freeze_and_shove()
        ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0)
        self.assertEqual(self.victim.damage_sources[-1], "rod")

    def test_a_slide_into_the_hero_is_not_an_elemental_contact(self):
        """The bump pass shoves the hero as well as the enemies, but a
        frozen enemy sliding into the hero must not take the elemental
        damage path: `Player.take_damage` has its own signature and the
        hero's mitigation (evasion, block, armor) is its own."""
        from types import SimpleNamespace

        from game.states.playing.core.physics import BumpResolver

        class Hero:
            def __init__(self):
                self.pos = pygame.Vector2(0.0, 0.0)
                self.radius = 10.0
                self.weight = 40.0
                self.alive = True
                self._knock = pygame.Vector2()
                self.hits = []

            def take_damage(self, amount):       # no source, no effect
                self.hits.append(amount)
                return amount

            def apply_knockback(self, direction, strength):
                pass

        hero = Hero()
        ps = SimpleNamespace(enemies=[self.slider], boss=None, player=hero,
                             stats={"time": 0.0}, elements=self.r)
        bump = BumpResolver(ps)
        self.freeze_and_shove()
        self.slider.pos.update(hero.pos)
        bump.resolve()
        self.assertEqual(hero.hits, [])

    def test_the_toggle_in_the_data_switches_it_off(self):
        data = tweak(**{"ice.freeze.contact": {"enabled": False,
                                               "damage": {"frac": 0.5}}})
        self.r, self.world, _ = build([self.slider, self.victim], elements=data)
        self.freeze_and_shove()
        self.assertEqual(
            ice_rules.exchange_contact(self.r, self.slider, self.victim, 0.0), 0.0)


# --- Thunder --------------------------------------------------------------------

class ThunderTests(unittest.TestCase):
    def chain(self, *, jumps, per_jump, max_targets=99, max_range=200.0,
              count=8, gap=40.0, falloff=1.0, runner=None):
        data = tweak(**{"thunder.chain.jumps": jumps,
                        "thunder.chain.targets_per_jump": per_jump,
                        "thunder.chain.max_targets": max_targets,
                        "thunder.chain.max_range": max_range,
                        "thunder.chain.falloff": falloff})
        enemies = row(n=count, gap=gap)
        r, world, tracked = build(enemies, elements=data, runner=runner)
        return r, world, tracked, enemies

    def test_no_jumps_hits_only_the_target(self):
        r, world, _t, enemies = self.chain(jumps=0, per_jump=3)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual([d[0] for d in world.dealt], [enemies[0]])

    def test_one_jump_of_three_reaches_at_most_four(self):
        r, world, _t, enemies = self.chain(jumps=1, per_jump=3)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual(len({id(d[0]) for d in world.dealt}), 4)

    def test_no_enemy_is_taken_twice_by_one_chain(self):
        r, world, _t, enemies = self.chain(jumps=3, per_jump=2, count=10)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        hit = [id(d[0]) for d in world.dealt]
        self.assertEqual(len(hit), len(set(hit)))

    def test_max_targets_bounds_the_tree(self):
        r, world, _t, enemies = self.chain(jumps=4, per_jump=3, max_targets=5,
                                           count=30, gap=20.0)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual(len(world.dealt), 6, "the hit enemy plus five jumps")

    def test_max_range_bounds_the_reach(self):
        r, world, _t, enemies = self.chain(jumps=1, per_jump=5, max_range=50.0,
                                           count=6, gap=40.0)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual(len(world.dealt), 2, "only the neighbour is in range")

    def test_every_node_receives_a_thunder_aura(self):
        r, _w, _t, enemies = self.chain(jumps=1, per_jump=3)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        with_aura = [e for e in enemies if e.elemental.element(0.0) == THUNDER]
        self.assertEqual(len(with_aura), 4, "wide aura spread is intended (R13)")

    def test_falloff_weakens_each_level(self):
        r, world, _t, enemies = self.chain(jumps=2, per_jump=1, falloff=0.5,
                                           count=4)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        amounts = [d[1] for d in world.dealt]
        self.assertAlmostEqual(amounts[1], amounts[0] * 0.5)
        self.assertAlmostEqual(amounts[2], amounts[0] * 0.25)

    def test_a_jump_into_another_aura_reacts_instead_of_dealing_damage(self):
        reacted = []
        r, world, _t, enemies = self.chain(
            jumps=1, per_jump=1, count=3,
            runner=lambda t, v, c, ctx: reacted.append((t, v.reaction)))
        # The neighbour already burns: the jump must consume it, not damage it.
        r.apply(enemies[1], FIRE, weapon_id="sword", hit_damage=10.0, now=0.0)
        world.dealt.clear()
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.1)
        struck = [d[0] for d in world.dealt]
        self.assertIn(enemies[0], struck)
        self.assertNotIn(enemies[1], struck, "R17: no jump damage on a reaction")
        self.assertEqual([t for t, _r in reacted], [enemies[1]])

    def test_a_reacting_node_stops_that_branch(self):
        r, world, _t, enemies = self.chain(
            jumps=3, per_jump=1, count=5, runner=lambda *a: None)
        r.apply(enemies[1], FIRE, weapon_id="sword", hit_damage=10.0, now=0.0)
        world.dealt.clear()
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.1)
        struck = {id(d[0]) for d in world.dealt}
        self.assertNotIn(id(enemies[2]), struck,
                         "the branch ended at the enemy that reacted")

    def test_a_locked_node_takes_damage_and_keeps_spreading(self):
        r, world, _t, enemies = self.chain(jumps=2, per_jump=1, count=4)
        enemies[1].elemental.lock(0.0, 10.0)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        struck = {id(d[0]) for d in world.dealt}
        self.assertIn(id(enemies[1]), struck, "open item 1: damage lands")
        self.assertFalse(enemies[1].elemental.has_aura(0.0))
        self.assertIn(id(enemies[2]), struck, "...and it keeps spreading")

    def test_a_node_the_jump_killed_still_arcs_onward(self):
        r, world, _t, enemies = self.chain(jumps=2, per_jump=1, count=4)
        enemies[1].hp = 0.1                      # the jump kills it
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertFalse(enemies[1].alive)
        struck = {id(d[0]) for d in world.dealt}
        self.assertIn(id(enemies[2]), struck,
                      "the chain needs only where the node was standing")
        self.assertFalse(enemies[1].elemental.has_aura(0.0),
                         "but nothing is written to the body")

    def test_a_jump_leaves_an_arc_for_the_placeholder_visual(self):
        r, world, _t, enemies = self.chain(jumps=1, per_jump=2)
        r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual(len(world.arcs), 2)

    def test_the_chain_flag_is_what_stops_a_node_branching_again(self):
        r, _w, _t, enemies = self.chain(jumps=1, per_jump=1, count=3)
        thunder = r.registry.element(THUNDER)
        self.assertIsInstance(thunder, Thunder)
        seen = []
        original = thunder.spread
        thunder.spread = lambda *a, **k: seen.append(1) or original(*a, **k)
        try:
            r.apply(enemies[0], THUNDER, weapon_id="rod", hit_damage=100.0, now=0.0)
        finally:
            thunder.spread = original
        self.assertEqual(len(seen), 1, "one tree per root hit")


# --- Wind ------------------------------------------------------------------------

class WindTests(unittest.TestCase):
    def setUp(self):
        self.enemies = row(n=4, gap=30.0)
        self.r, self.world, self.tracked = build(self.enemies)

    def blow(self, now=0.0):
        return self.r.apply(self.enemies[0], WIND, weapon_id="bow",
                            hit_damage=100.0, now=now)

    def test_the_hit_deals_its_damage_and_seats_an_area(self):
        self.blow()
        self.assertEqual(self.world.dealt[0][3], tracking.WIND_HIT)
        self.assertEqual(len(self.world.areas), 1)

    def test_the_area_lasts_its_configured_duration(self):
        self.blow(now=5.0)
        area = self.world.areas[0]
        self.assertAlmostEqual(area.expires_at, 5.0 + WIND_CFG["area"]["duration"])
        self.assertTrue(area.update(5.0 + WIND_CFG["area"]["duration"] - 0.01, self.world))
        self.assertFalse(area.update(5.0 + WIND_CFG["area"]["duration"], self.world))

    def test_the_enemy_it_formed_on_is_not_in_its_own_area(self):
        self.blow()
        area = self.world.areas[0]
        area.update(0.0, self.world)
        hit = [d[0] for d in self.world.dealt if d[3] == tracking.WIND_AREA]
        self.assertNotIn(self.enemies[0], hit)

    def test_each_enemy_is_contacted_at_most_once(self):
        self.blow()
        area = self.world.areas[0]
        for step in range(10):
            area.update(step * 0.05, self.world)
        hit = [d[0] for d in self.world.dealt if d[3] == tracking.WIND_AREA]
        self.assertEqual(len(hit), len(set(map(id, hit))))

    def test_contact_knocks_radially_away_from_the_centre(self):
        self.blow()
        area = self.world.areas[0]
        area.update(0.0, self.world)
        pushed = self.enemies[1]
        self.assertGreater(pushed._knock.x, 0.0, "shoved away from the origin")

    def test_it_follows_the_enemy_it_formed_on(self):
        self.blow()
        area = self.world.areas[0]
        self.enemies[0].pos.update(500.0, 500.0)
        area.update(0.01, self.world)
        self.assertEqual(tuple(area.pos), (500.0, 500.0))

    def test_a_dead_anchor_leaves_the_area_where_it_was(self):
        self.blow()
        area = self.world.areas[0]
        here = pygame.Vector2(area.pos)
        self.enemies[0].alive = False
        self.enemies[0].pos.update(900.0, 900.0)
        area.update(0.01, self.world)
        self.assertEqual(area.pos, here)

    def test_contact_is_checked_at_the_low_rate_not_every_frame(self):
        """A tornado that swept every frame would be the expensive part of
        the whole system, so the rate is pinned rather than assumed."""
        from combat.elements.area import CHECK_HZ

        data = tweak(**{"wind.area.duration": 1.0, "wind.area.radius": 500.0,
                        "wind.area.max_targets": 99})
        self.r, self.world, _ = build(self.enemies, elements=data)
        self.blow(now=0.0)
        area = self.world.areas[0]
        checks = 0
        previous = area.next_check_at
        for frame in range(60):                 # one second of 60 Hz frames
            area.update(frame / 60.0, self.world)
            if area.next_check_at != previous:
                checks += 1
                previous = area.next_check_at
        self.assertLessEqual(checks, int(CHECK_HZ) + 1)
        self.assertGreaterEqual(checks, int(CHECK_HZ) - 1)

    def test_max_targets_bounds_one_area(self):
        data = tweak(**{"wind.area.max_targets": 1, "wind.area.radius": 500.0})
        self.r, self.world, _ = build(self.enemies, elements=data)
        self.blow()
        area = self.world.areas[0]
        for step in range(6):
            area.update(step * 0.2, self.world)
        hit = [d for d in self.world.dealt if d[3] == tracking.WIND_AREA]
        self.assertEqual(len(hit), 1)

    def test_the_run_cap_refuses_an_area_rather_than_queueing_it(self):
        self.world.area_cap = 1
        self.blow(now=0.0)
        self.r.apply(self.enemies[1], WIND, weapon_id="bow", hit_damage=100.0,
                     now=0.1)
        self.assertEqual(len(self.world.areas), 1)
        self.assertTrue(self.enemies[1].elemental.has_aura(0.1),
                        "the hit and its aura still happened")

    def test_a_payload_runs_on_every_contact(self):
        """A payload is handed the live clock and the area's own figure as
        well as the body: since the rework a Wind reaction's payload spreads
        an aura, which has to be timed against the run clock rather than
        against the reaction that seated the area."""
        paid = []
        area = WindArea(pos=pygame.Vector2(0, 0), radius=200.0, expires_at=10.0,
                        damage=1.0, knockback=0.0, weapon_id="bow",
                        effect=tracking.WIND_AREA, max_targets=9,
                        payload=lambda t, a, w, now, dmg: paid.append((t, now, dmg)))
        area.update(2.5, self.world)
        self.assertEqual(len(paid), len(self.enemies))
        for _body, now, dmg in paid:
            self.assertEqual(now, 2.5, "the live clock, not the reaction's")
            self.assertEqual(dmg, 1.0)


# --- the spatial query --------------------------------------------------------------

class NearestTests(unittest.TestCase):
    def setUp(self):
        self.grid = SpatialGrid()
        self.enemies = row(n=6, gap=30.0)
        self.grid.rebuild(self.enemies)

    def test_it_returns_the_closest_first(self):
        got = self.grid.nearest(0.0, 0.0, 3, 200.0)
        self.assertEqual(got, self.enemies[:3])

    def test_the_radius_bounds_it(self):
        self.assertEqual(self.grid.nearest(0.0, 0.0, 6, 35.0), self.enemies[:2])

    def test_excluded_ids_are_skipped(self):
        got = self.grid.nearest(0.0, 0.0, 2, 200.0,
                                exclude={id(self.enemies[0]), id(self.enemies[1])})
        self.assertEqual(got, self.enemies[2:4])

    def test_the_dead_are_skipped(self):
        self.enemies[1].alive = False
        self.assertEqual(self.grid.nearest(0.0, 0.0, 2, 200.0),
                         [self.enemies[0], self.enemies[2]])

    def test_asking_for_none_or_no_reach_returns_nothing(self):
        self.assertEqual(self.grid.nearest(0.0, 0.0, 0, 200.0), [])
        self.assertEqual(self.grid.nearest(0.0, 0.0, 3, 0.0), [])

    def test_it_never_returns_more_than_asked(self):
        self.assertEqual(len(self.grid.nearest(0.0, 0.0, 2, 1000.0)), 2)


if __name__ == "__main__":
    unittest.main()
