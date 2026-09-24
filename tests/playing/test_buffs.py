"""The buff buildings' timed buffs (journal: buff_buildings_journal.md),
driven through a real headless run so each buff hits the code the game runs:
the interact key, the stat modifiers, the bump weight, the gem pull, the
summon cadence, the pinball's bounces and the per-hit heal.
"""
import math
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import Weapon
from entities.summon import Summon
from game import config
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing.core import interactions
from game.states.playing.visual import key_marker
from tests import worlds as W
from tests.boot import start_run
from tests.combat.test_weapon_fire import BOLT

SEED = W.pinned(2)
_RUN = None


def playing():
    """One booted run for the module (a boot costs seconds). Every test
    leaves the buffs expired and the hero where it found them."""
    global _RUN
    if _RUN is None:
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        game.state_machine.change(MenuState(game))
        _RUN = (game, start_run(game, SEED))
    return _RUN[1]


def building(p, kind):
    return next(it for it in p.interactables if it.kind == kind and not it.used)


class _BuffCase(unittest.TestCase):
    def setUp(self):
        self.p = playing()
        self.p.buffs.update(60.0)               # nothing left over from the last test
        self.p.player.hp = self.p.player.max_hp
        # A building fires once per run; the tests share one run, so each
        # starts with every building fresh again.
        for it in self.p.interactables:
            if self.p.buffs.is_buff(it.kind):
                it.used = False

    def use(self, kind):
        p = self.p
        it = building(p, kind)
        p.player.pos.update(it.pos.x, it.pos.y + it.radius + 20)
        self.assertIs(interactions.nearest(p), it)
        interactions.activate(p, it)
        return it


class ActivationTests(_BuffCase):
    def test_every_building_has_an_interactable_that_fires_once(self):
        p = self.p
        for kind in p.buffs.kinds:
            it = self.use(kind)
            self.assertTrue(it.used)
            self.assertTrue(p.buffs.is_active(kind))
            self.assertAlmostEqual(p.buffs.active[kind], p.buffs.spec(kind)["duration"])
            self.assertFalse(interactions.usable(it))
            p.buffs.update(60.0)
            self.assertFalse(p.buffs.is_active(kind))

    def test_the_keycap_hangs_over_the_building_art(self):
        p = self.p
        it = building(p, "haste")
        p.camera.snap_to(it.pos)
        found = key_marker.art_box(p, it)
        self.assertIsNotNone(found, "a skinned building measures its painted box")
        box, peak = found
        self.assertGreater(box.height, 0)

    def test_feedback_fires_and_fades(self):
        p = self.p
        self.use("vampire")
        self.assertIsNotNone(p.buffs.tint)
        self.assertEqual(len(p.buffs.hero_fx), 1)
        self.assertEqual(p.buffs.hero_fx[0][2], p.buffs.spec("vampire").get("fx_scale", 1.0),
                         "the effect carries the buff's own draw scale")
        self.assertEqual([b.text for b in p.buffs.banners.items], ["Vampire"])
        self.assertEqual(p.buffs.banners.items[0].colour, tuple(p.buffs.palette("vampire")[0]))
        p.buffs.update(1.0)
        self.assertIsNone(p.buffs.tint, "the tint is brief")
        p.buffs.update(1.5)
        self.assertEqual(p.buffs.hero_fx, [], "the hero effect lasts a couple of seconds")
        self.assertTrue(p.buffs.banners.items, "the name is still fading")
        p.buffs.update(4.6)
        self.assertEqual(p.buffs.banners.items, [], "gone after seven seconds")

    def test_hud_rows_drain_and_empty(self):
        p = self.p
        self.use("magnet")
        rows = p.buffs.rows()
        self.assertEqual(len(rows), 1)
        kind, frac, rig, colour = rows[0]
        self.assertEqual((kind, rig), ("magnet", "hud_buff_magnet"))
        self.assertAlmostEqual(frac, 1.0)
        full = p.buffs.spec("magnet")["duration"]
        p.buffs.update(full / 2)
        self.assertAlmostEqual(p.buffs.rows()[0][1], 0.5)
        p.buffs.update(full / 2 + 0.1)
        self.assertEqual(p.buffs.rows(), [])

    def test_the_mine_goes_dark_once_used(self):
        from world.terrain.decor.obstacle_skins import reskin_obstacle
        p = self.p
        gm, assets = p.game_map, p.game.assets
        it = building(p, "magnet")
        i = next(i for i, o in enumerate(gm.obstacles)
                 if o.kind == "magnet" and (o.pos - it.pos).length_squared() <= 1.0)
        # Another test may have used this mine already: light its door again.
        self.assertTrue(reskin_obstacle(gm, assets, i, "building_magnet"))
        size = gm._decos[i][3][0].get_size()
        self.assertIs(gm._decos[i][3][0], assets.frames("building_magnet", "loop", size=size)[0])
        self.use("magnet")
        self.assertIs(gm._decos[i][3][0],
                      assets.frames("building_magnet_used", "loop", size=size)[0],
                      "the dark-door sheet, at the same drawn size")


class StatTests(_BuffCase):
    def test_turbo_adds_speed_armor_and_weight_then_gives_them_back(self):
        p = self.p
        speed, armor = p.player.move_speed, p.player.stats["armor"]
        spec = p.buffs.spec("turbo")
        self.use("turbo")
        self.assertEqual(p.player.move_speed, speed + spec["speed_add"])
        self.assertEqual(p.player.stats["armor"], armor + spec["armor_add"])
        self.assertTrue(math.isinf(p.player.weight))
        p.buffs.update(spec["duration"] + 0.01)
        self.assertEqual(p.player.move_speed, speed)
        self.assertEqual(p.player.stats["armor"], armor)
        self.assertEqual(p.player.weight, config.PLAYER_WEIGHT)

    def test_haste_doubles_attack_speed_and_the_floor_holds(self):
        p = self.p
        self.use("haste")
        self.assertEqual(p.player.stats["attack_speed_multiplier"], 2.0)
        w = Weapon("bolt", dict(BOLT))
        self.assertAlmostEqual(w._cooldown(2.0), w._cooldown(1.0) / 2.0)
        fast = dict(BOLT, cooldown=0.06)
        self.assertEqual(Weapon("bolt", fast)._cooldown(2.0), 0.05, "never below the floor")
        p.buffs.update(p.buffs.spec("haste")["duration"] + 0.1)
        self.assertEqual(p.player.stats["attack_speed_multiplier"], 1.0)

    def test_haste_paces_the_summons_too(self):
        p = self.p
        self.use("haste")
        self.assertEqual(p.buffs.attack_speed_mult(), 2.0)
        s = Summon()
        s.reset(kind="totem", pos=pygame.Vector2(), damage=1.0, lifetime=10.0,
                color=(255, 255, 255), tags=())
        s.attack_cd = 1.0
        ctx = SimpleNamespace(enemies=[], spawn_projectile=lambda **kw: None,
                              player_pos=pygame.Vector2(), attack_speed_mult=2.0)
        s.update(0.25, ctx)
        self.assertAlmostEqual(s.attack_cd, 0.5)

    def test_vampire_raises_damage_ten_percent(self):
        p = self.p
        base = p.player.stats["damage_multiplier"]
        self.use("vampire")
        self.assertAlmostEqual(p.player.stats["damage_multiplier"], base + 0.10)
        p.buffs.update(p.buffs.spec("vampire")["duration"] + 0.01)
        self.assertAlmostEqual(p.player.stats["damage_multiplier"], base)

    def test_a_refresh_does_not_stack(self):
        p = self.p
        speed = p.player.move_speed
        spec = p.buffs.spec("turbo")
        self.use("turbo")
        p.buffs.update(3.0)
        p.buffs.start("turbo")
        self.assertEqual(p.player.move_speed, speed + spec["speed_add"])
        self.assertAlmostEqual(p.buffs.active["turbo"], spec["duration"])


class MagnetTests(_BuffCase):
    def _gem(self, dx):
        p = self.p
        gem = p.gems.acquire()
        gem.reset(p.player.pos + pygame.Vector2(dx, 0), 3)
        return gem

    def test_stranded_and_fresh_gems_home_while_magnet_runs(self):
        p = self.p
        far = p.player.pickup_radius * 4
        stranded = self._gem(far)
        self.assertFalse(stranded.homing)
        self.use("magnet")
        self.assertTrue(stranded.homing, "every gem already on the field is pulled")
        fresh = self._gem(-far)
        p.buffs.on_gem(fresh)
        self.assertTrue(fresh.homing, "a gem dropped meanwhile is pulled too")
        p.buffs.update(p.buffs.spec("magnet")["duration"] + 0.1)
        later = self._gem(far)
        p.buffs.on_gem(later)
        self.assertFalse(later.homing, "once the buff is over gems wait again")
        for g in (stranded, fresh, later):
            g.active = False


class ContactAndHitTests(_BuffCase):
    def _enemy(self):
        p = self.p
        enemy_id = next(iter(p.content.enemies))
        e = p.spawn.spawn_enemy(enemy_id, at=pygame.Vector2(p.player.pos), owner="dev")
        self.assertIsNotNone(e)
        p.grid.rebuild(p.enemies)
        return e

    def tearDown(self):
        for e in self.p.enemies:
            e.alive = False
        self.p.combat.cull_dead_enemies()

    def test_turbo_bites_five_per_second_per_touching_enemy(self):
        p = self.p
        self.use("turbo")                       # moves the hero to the tower...
        e = self._enemy()                       # ...so the enemy spawns on it after
        e.hp = 1000.0
        p.buffs.update(0.016)
        self.assertAlmostEqual(e.hp, 997.5)
        p.buffs.update(0.016)
        self.assertAlmostEqual(e.hp, 997.5, "one bite per half second")
        p.buffs.update(0.5)
        self.assertAlmostEqual(e.hp, 995.0, "5 damage over the first second")

    def _hit(self, weapon_id):
        p = self.p
        e = self._enemy()
        e.hp = 1000.0
        proj = p._spawn_projectile(pos=pygame.Vector2(e.pos), vel=pygame.Vector2(),
                                   damage=1.0, radius=8.0, lifetime=1.0,
                                   weapon_id=weapon_id)
        p.combat.projectile_hits()
        proj.active = False
        return e

    def test_vampire_heals_one_per_hit_but_not_for_summons(self):
        p = self.p
        self.use("vampire")
        p.player.hp = p.player.max_hp - 10
        main = p.player.weapons[0].weapon_id
        self._hit(main)
        self.assertAlmostEqual(p.player.hp, p.player.max_hp - 9)
        summon_id = next(wid for wid, d in p.content.weapons.items()
                         if d.get("class") == "summon")
        p.player.weapons.append(Weapon(summon_id, dict(p.content.weapon(summon_id))))
        try:
            self._hit(summon_id)
            self.assertAlmostEqual(p.player.hp, p.player.max_hp - 9, "a summon's hit heals nothing")
        finally:
            p.player.weapons.pop()
        p.buffs.update(p.buffs.spec("vampire")["duration"] + 0.1)
        self._hit(main)
        self.assertAlmostEqual(p.player.hp, p.player.max_hp - 9, "no heal once expired")


class PinballTests(_BuffCase):
    def _balls(self):
        return [q for q in self.p.projectiles if q.active and q.style == "pinball"]

    def tearDown(self):
        for q in self._balls():
            q.active = False
        self.p.projectiles.sweep()

    def test_a_ball_every_two_seconds_while_attacking(self):
        p = self.p
        self.use("pinball")
        p.player._attack_t = 0.0
        p.buffs.update(0.016)
        self.assertEqual(self._balls(), [], "no swing, no ball")
        p.player._attack_t = 1.0
        p.buffs.update(0.016)
        balls = self._balls()
        self.assertEqual(len(balls), 1)
        spec = p.buffs.spec("pinball")["pinball"]
        self.assertEqual(balls[0].bounces_left, spec["bounces"])
        self.assertAlmostEqual(balls[0].lifetime, spec["lifetime"])
        self.assertEqual(balls[0].src_weight, spec["weight"])
        self.assertAlmostEqual(balls[0].vel.length(), spec["speed"], places=3)
        p.buffs.update(1.0)
        self.assertEqual(len(self._balls()), 1)
        p.buffs.update(1.1)
        self.assertEqual(len(self._balls()), 2, "the next ball two seconds on")

    def _ball(self, pos, vel, bounces=10):
        p = self.p
        q = p._spawn_projectile(pos=pygame.Vector2(pos), vel=pygame.Vector2(vel),
                                damage=1.0, radius=10.0, lifetime=10.0, pierce=999,
                                style="pinball", weapon_id="pinball", bounces=bounces)
        return q

    def test_a_ball_reflects_off_an_obstacle(self):
        p = self.p
        rock = next(o for o in p.game_map.obstacles if o.blocks_projectiles)
        before = pygame.Vector2(rock.pos.x - rock.radius - 30, rock.pos.y)
        q = self._ball(before, (200, 0))
        q.pos.update(rock.pos.x - rock.radius - 5, rock.pos.y)      # nosed into it
        p.fx.bounce(q, before)
        self.assertLess(q.vel.x, 0, "back the way it came")
        self.assertAlmostEqual(q.vel.y, 0.0)
        self.assertEqual(q.bounces_left, 9)
        self.assertIsNone(p.game_map.blocking_obstacle_hit(q.pos, q.radius),
                          "seated back outside the obstacle")

    def test_a_ball_reflects_off_the_edge_of_the_world(self):
        p = self.p
        start = pygame.Vector2(p.player.pos)
        self.assertTrue(p.game_map.is_walkable(start, 10.0))
        left = p.game_map.layout.bounds.left
        q = self._ball(start, (-200, 0))
        before = pygame.Vector2(left + 30, start.y)
        q.pos.update(left - 40, start.y)
        p.fx.bounce(q, before)
        self.assertGreater(q.vel.x, 0)
        self.assertEqual(q.bounces_left, 9)

    def test_the_last_bounce_spends_the_ball(self):
        p = self.p
        rock = next(o for o in p.game_map.obstacles if o.blocks_projectiles)
        before = pygame.Vector2(rock.pos.x - rock.radius - 30, rock.pos.y)
        q = self._ball(before, (200, 0), bounces=1)
        q.pos.update(rock.pos.x - rock.radius - 5, rock.pos.y)
        p.fx.bounce(q, before)
        self.assertFalse(q.active)

    def test_an_ordinary_shot_still_dies_on_an_obstacle(self):
        p = self.p
        rock = next(o for o in p.game_map.obstacles if o.blocks_projectiles)
        q = p._spawn_projectile(pos=pygame.Vector2(rock.pos), vel=pygame.Vector2(1, 0),
                                damage=1.0, radius=4.0, lifetime=1.0)
        p.fx.block_on_obstacle(q)
        self.assertFalse(q.active)


if __name__ == "__main__":
    unittest.main()
