"""Enemy sprite rigs, the hit tint (no `hurt` strip -> red-tint the live frame),
and the shared one-shot `dead` death poof for every entity."""
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.enemy import Enemy
from entities.enemy_ai import EnemyContext
from game.content import get_content
from systems.animation import Animator


def _ctx(dt=1 / 30, player=(0, 0)):
    return EnemyContext(
        dt=dt, player_pos=pygame.Vector2(*player), player=object(),
        rng=random.Random(0), fire_projectile=lambda **k: None,
        summon=lambda *a: None, explosion=lambda *a: None)


def make(eid, x=200, y=0):
    return Enemy(eid, get_content().enemy(eid), x, y)


ALL_ENEMIES = tuple(get_content().enemies)          # every enemy is sprited now


class EnemyRigTests(unittest.TestCase):
    def test_every_enemy_has_an_animator(self):
        self.assertEqual(make("chaser").anim.rig, "skull")
        for eid in ALL_ENEMIES:
            self.assertIsInstance(make(eid).anim, Animator, eid)

    def test_fsm_telegraph_and_attack_states_play_the_attack_anim(self):
        e = make("charger")
        self.assertEqual(e._anim_name(), "idle")
        e.ai["fs"] = "telegraph"
        self.assertEqual(e._anim_name(), "attack")
        e.ai["fs"] = "attack"
        self.assertEqual(e._anim_name(), "attack")
        e.ai["fs"] = "recover"
        self.assertEqual(e._anim_name(), "idle")
        # brute uses ai["slam_state"] instead of ai["fs"]
        b = make("brute")
        b.ai["slam_state"] = "telegraph"
        self.assertEqual(b._anim_name(), "attack")

    def test_hit_sets_the_tint_timer_but_not_a_hurt_anim(self):
        e = make("chaser")               # skull rig -- no `hurt` strip
        self.assertFalse(e._has_hurt)
        e.anim.play("walk")
        e.take_damage(3.0)
        self.assertGreater(e._hurt_t, 0.0)     # drives the red tint
        self.assertNotEqual(e.anim.anim, "hurt")   # did NOT pop to a missing anim

    def test_anim_name_ignores_hurt_without_a_strip(self):
        e = make("chaser")
        e.vel.update(50, 0)
        self.assertEqual(e._anim_name(), "walk")
        e.vel.update(0, 0)
        e._hurt_t = 0.1
        self.assertEqual(e._anim_name(), "idle")    # not "hurt"
        e.alive = False
        self.assertEqual(e._anim_name(), "death")

    def test_facing_tracks_the_player(self):
        e = make("chaser", x=200)
        e.update(_ctx(player=(0, 0)))
        self.assertEqual(e._facing, -1)
        e.update(_ctx(player=(9999, 0)))
        self.assertEqual(e._facing, 1)

    def test_hurt_timer_decays_in_update(self):
        e = make("chaser")
        e.take_damage(3.0)
        for _ in range(20):
            e.update(_ctx())
        self.assertEqual(e._hurt_t, 0.0)

    def test_dot_does_not_trip_the_tint(self):
        e = make("chaser")
        e._status_damage(2.0, _ctx())        # burn tick path
        self.assertEqual(e._hurt_t, 0.0)


class HitTintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_tinted_copy_is_distinct_same_size_and_redder(self):
        from game.states.playing_state import PlayingState
        src = pygame.Surface((10, 10), pygame.SRCALPHA)
        src.fill((80, 80, 80, 255))
        out = PlayingState._hit_tinted(src)
        self.assertIsNot(out, src)
        self.assertEqual(out.get_size(), src.get_size())
        r, g, b, _ = out.get_at((5, 5))
        self.assertGreater(r, 80)
        self.assertGreater(r - g, 40)          # shifted toward red
        self.assertEqual((g, b), (80 + 30, 80 + 30))

    def test_transparent_pixels_stay_transparent(self):
        from game.states.playing_state import PlayingState
        src = pygame.Surface((6, 6), pygame.SRCALPHA)   # all (0,0,0,0)
        out = PlayingState._hit_tinted(src)
        self.assertEqual(out.get_at((3, 3))[3], 0)


class DeathPoofTests(unittest.TestCase):
    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        return g, g.state_machine.current

    def _kill_one(self, p, eid):
        p._spawn_enemy(eid, at=p.player.pos + pygame.Vector2(60, 0))
        e = p.enemies[-1]
        e.hp = 0.0
        e.alive = False
        p._cull_dead_enemies()
        return e

    def test_any_enemy_death_pushes_one_dead_poof(self):
        g, p = self._playing()
        for eid in ("chaser", "ranged"):        # sprited + primitive both poof
            p._death_fx.clear()
            kills0 = p.stats["kills"]
            e = self._kill_one(p, eid)
            self.assertNotIn(e, p.enemies)
            self.assertEqual(p.stats["kills"], kills0 + 1)
            self.assertEqual(len(p._death_fx), 1)
            self.assertEqual(p._death_fx[0][0].rig, "dead")
            self.assertAlmostEqual(p._death_fx[0][1].x, e.pos.x)
            self.assertAlmostEqual(p._death_fx[0][3], 0.55)   # enemy poof at 55%
        pygame.quit()

    def test_poof_clears_when_the_one_shot_finishes(self):
        g, p = self._playing()
        self._kill_one(p, "chaser")
        for _ in range(90):                     # 1.5 s
            p._update_death_fx(1 / 60)
        self.assertEqual(p._death_fx, [])
        pygame.quit()

    def test_hero_death_spawns_a_poof_and_holds_the_run(self):
        g, p = self._playing()
        p.player.hp = 0.0
        p.player.alive = False
        p.update(1 / 60)
        self.assertGreaterEqual(len(p._death_fx), 1)
        self.assertEqual(p._death_fx[-1][3], 1.0)          # hero poof at full size
        self.assertIsNotNone(p._death_seq_t)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
