"""Six-weapon system P2: the weapon blessings that need code beyond a bonus
field -- Executioner, Weak Point, Demolitionist (conditional damage in the
resolver), Split Arrow (children on hit), Bloodletting (heal on the killing
weapon), Overcharge (every Nth attack), Chain / Seeking / Staggering /
Bigger Explosion (bonus fields read by the fire path)."""
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from game.content import get_content
from game.states.playing.combat import CombatResolver
from tests.combat.fakes import FakeEnemy, fake_ps

C = get_content()


def owned(ps, wid, **effects):
    w = Weapon(wid, C.weapon(wid))
    w.effects.update(effects)
    ps.player.weapons.append(w)
    return w


def hit(ps, enemy, wid, damage=10.0, vel=(0, 0)):
    ps.projectiles.clear()                 # one live shot per hit
    p = ps._spawn_projectile(pos=enemy.pos, vel=vel, damage=damage, radius=20,
                             lifetime=0.2, pierce=999, weapon_id=wid,
                             source_tags=("ranged",))
    CombatResolver(ps).projectile_hits()
    return p


def ctx(enemies, sink, **over):
    base = dict(origin=pygame.Vector2(), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: sink.append(kw))
    base.update(over)
    return FireContext(**base)


class ConditionalDamageTests(unittest.TestCase):
    def test_executioner_only_below_the_threshold(self):
        healthy, weak = FakeEnemy(0, 0), FakeEnemy(0, 0)
        weak.hp = 30.0                                       # 30 % of 100
        ps = fake_ps([healthy])
        owned(ps, "hammer", executioner_mult=0.5, executioner_threshold=0.35)
        hit(ps, healthy, "hammer")
        self.assertAlmostEqual(healthy.hp, 90.0)
        ps.enemies = [weak]
        hit(ps, weak, "hammer")
        self.assertAlmostEqual(weak.hp, 15.0)                # 10 x 1.5

    def test_weak_point_only_against_the_wounded(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "daggers", weak_point_mult=0.5)
        hit(ps, e, "daggers")
        self.assertAlmostEqual(e.hp, 90.0)                   # first hit: full health
        hit(ps, e, "daggers")
        self.assertAlmostEqual(e.hp, 75.0)                   # wounded: x1.5

    def test_demolitionist_against_stunned_or_shoved(self):
        calm, stunned, shoved = FakeEnemy(0, 0), FakeEnemy(0, 0), FakeEnemy(0, 0)
        stunned.status.apply("stun", 1.0, 1.0)
        shoved._knock.update(200, 0)
        ps = fake_ps([calm])
        owned(ps, "bomb", demolition_mult=1.0)
        hit(ps, calm, "bomb"); self.assertAlmostEqual(calm.hp, 90.0)
        ps.enemies = [stunned]
        hit(ps, stunned, "bomb"); self.assertAlmostEqual(stunned.hp, 80.0)
        ps.enemies = [shoved]
        hit(ps, shoved, "bomb"); self.assertAlmostEqual(shoved.hp, 80.0)

    def test_effects_of_another_weapon_do_not_leak(self):
        e = FakeEnemy(0, 0)
        e.hp = 10.0
        ps = fake_ps([e])
        owned(ps, "hammer", executioner_mult=1.0, executioner_threshold=0.5)
        owned(ps, "sword")
        hit(ps, e, "sword")
        self.assertAlmostEqual(e.hp, 0.0)                    # 10 flat, not 20

    def test_a_shot_from_no_owned_weapon_is_plain(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        hit(ps, e, "")
        self.assertAlmostEqual(e.hp, 90.0)


class SplitArrowTests(unittest.TestCase):
    def _children(self, ps):
        return [p for p in ps.projectiles if p.active and "split" in p.source_tags]

    def test_a_moving_hit_splits_into_children_that_skip_the_target(self):
        e = FakeEnemy(100, 0)
        ps = fake_ps([e])
        owned(ps, "bow", split_count=2, split_damage_mult=0.5)
        hit(ps, e, "bow", damage=10, vel=(400, 0))
        kids = self._children(ps)
        self.assertEqual(len(kids), 2)
        for k in kids:
            self.assertAlmostEqual(k.damage, 5.0)
            self.assertIn(id(e), k.hit_ids)
            self.assertEqual(k.weapon_id, "bow")
            self.assertAlmostEqual(k.vel.length(), 400.0, places=3)
        headings = sorted(math.degrees(math.atan2(k.vel.y, k.vel.x)) for k in kids)
        self.assertAlmostEqual(headings[0], -12.5, places=3)
        self.assertAlmostEqual(headings[1], 12.5, places=3)

    def test_children_never_split_again(self):
        e, e2 = FakeEnemy(100, 0), FakeEnemy(140, 10)
        ps = fake_ps([e])
        owned(ps, "bow", split_count=1, split_damage_mult=0.5)
        hit(ps, e, "bow", damage=10, vel=(400, 0))
        self.assertEqual(len(self._children(ps)), 1)
        ps.enemies = [e2]
        for k in self._children(ps):
            k.pos.update(e2.pos)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(len([p for p in ps.projectiles if p.active and "split" in p.source_tags]),
                         0, "the child hit and died without spawning more")

    def test_a_stationary_hit_does_not_split(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "sword", split_count=2)
        hit(ps, e, "sword", vel=(0, 0))
        self.assertEqual(self._children(ps), [])


class KillAttributionTests(unittest.TestCase):
    def test_the_killing_projectile_names_its_weapon(self):
        e = FakeEnemy(0, 0, hp=5.0)
        ps = fake_ps([e])
        owned(ps, "sword")
        hit(ps, e, "sword", damage=10)
        self.assertFalse(e.alive)
        self.assertEqual(e.killed_by, "sword")

    def test_a_surviving_enemy_is_not_marked(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        hit(ps, e, "sword", damage=10)
        self.assertEqual(e.killed_by, "")


class FirePathBonusTests(unittest.TestCase):
    def _fire(self, w, enemies=(FakeEnemy(25, 0),)):
        sink = []
        w._cd = 0.0
        w.update(1 / 60, ctx(enemies, sink))
        return sink

    def test_chain_blessing_turns_the_rod_into_a_chain_shot(self):
        w = Weapon("magic_rod", C.weapon("magic_rod"))
        self.assertEqual(self._fire(w)[0]["chain_left"], 0)
        w.bonus["chain_count"] += 2
        w.bonus["chain_range"] += 200
        shot = self._fire(w)[0]
        self.assertEqual(shot["chain_left"], 2)
        self.assertEqual(shot["chain_range"], 200)

    def test_seeking_widens_the_assist_cone(self):
        w = Weapon("magic_rod", C.weapon("magic_rod"))
        base = w._assist_half_angle()
        w.bonus["aim_assist_deg"] += 20
        self.assertAlmostEqual(w._assist_half_angle(), base + math.radians(20))

    def test_staggering_strike_and_titans_grip_reach_the_blow(self):
        # CR1: the Hammer swings first; tick it until the blow lands.
        w = Weapon("hammer", C.weapon("hammer"))
        d = C.weapon("hammer")
        w.bonus["stun_chance"] += 0.1
        w.bonus["stun_duration"] += 0.2
        w.bonus["weight"] += 15
        sink = []
        w._cd = 0.0
        for _ in range(90):
            w.update(1 / 60, ctx([FakeEnemy(25, 0)], sink))
            if sink:
                break
        s = sink[0]
        self.assertAlmostEqual(s["stun_chance"], d["stun_chance"] + 0.1)
        self.assertAlmostEqual(s["stun_duration"], d["stun_duration"] + 0.2)
        self.assertAlmostEqual(s["src_weight"], d["weight"] + 15)

    def test_wide_cleave_widens_the_sword_cone(self):
        w = Weapon("sword", C.weapon("sword"))
        d = C.weapon("sword")
        w.bonus["cone_half_angle"] += 10
        s = self._fire(w)[0]
        self.assertAlmostEqual(s["cone_half_angle"], math.radians(d["cone_half_angle"] + 10))

    def test_bigger_explosion_reaches_the_bomb(self):
        w = Weapon("bomb", C.weapon("bomb"))
        w.bonus["blast_radius"] += 24
        s = self._fire(w, [FakeEnemy(150, 0)])[0]
        self.assertAlmostEqual(s["blast_radius"], C.weapon("bomb")["blast_radius"] + 24)

    def test_per_weapon_crit_chance_adds_to_the_heros(self):
        w = Weapon("sword", C.weapon("sword"))
        w.bonus["crit_chance"] = 0.2
        self.assertAlmostEqual(w._crit_chance(ctx([], [], crit_chance=0.1)), 0.3)

    def test_overcharge_every_fifth_attack(self):
        w = Weapon("magic_rod", C.weapon("magic_rod"))
        w.effects.update(overcharge_every=5, overcharge_mult=2.0)
        base = C.weapon("magic_rod")["damage"]
        dmgs = []
        for _ in range(10):
            dmgs.append(self._fire(w)[0]["damage"])
        self.assertEqual([d / base for d in dmgs], [1, 1, 1, 1, 2, 1, 1, 1, 1, 2])

    def test_class_damage_multipliers_skip_summons(self):
        sword = Weapon("sword", C.weapon("sword"))
        bow = Weapon("bow", C.weapon("bow"))
        wolf = Weapon("spirit_wolf", C.weapon("spirit_wolf"))
        c = ctx([], [], melee_damage_mult=1.5, ranged_damage_mult=2.0)
        self.assertAlmostEqual(sword._damage(c), C.weapon("sword")["damage"] * 1.5)
        self.assertAlmostEqual(bow._damage(c), C.weapon("bow")["damage"] * 2.0)
        self.assertAlmostEqual(wolf._damage(c), C.weapon("spirit_wolf")["damage"])

    def test_totem_lifetime_bonus(self):
        w = Weapon("grave_totem", C.weapon("grave_totem"))
        w.bonus["summon_lifetime"] += 4
        made = []
        c = ctx([FakeEnemy(100, 0)], [], spawn_summon=lambda **kw: made.append(kw) or None)
        w.update(1 / 60, c)
        self.assertAlmostEqual(made[0]["lifetime"], C.weapon("grave_totem")["summon_lifetime"] + 4)


class BloodlettingTests(unittest.TestCase):
    def test_a_kill_by_the_blessed_weapon_heals(self):
        from game.states.playing.state import PlayingState
        healed = []
        ps = fake_ps([])
        ps.player.heal = lambda amt: healed.append(amt)
        owned(ps, "sword", on_kill_heal=3.0)
        owned(ps, "bow")
        e = FakeEnemy(0, 0, hp=1.0)
        e.killed_by = "sword"
        PlayingState._apply_on_kill_effects(ps, e)
        self.assertEqual(healed, [3.0])
        e2 = FakeEnemy(0, 0, hp=1.0)
        e2.killed_by = "bow"
        PlayingState._apply_on_kill_effects(ps, e2)
        self.assertEqual(healed, [3.0])


if __name__ == "__main__":
    unittest.main()
