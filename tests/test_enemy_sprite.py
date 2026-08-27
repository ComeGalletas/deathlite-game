"""Asset Phase C: the basic enemy (chaser) uses the Orc rig; death animation
lifecycle; plain enemies are untouched."""
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


class EnemyRigTests(unittest.TestCase):
    def test_only_the_chaser_gets_an_animator(self):
        c = make("chaser")
        self.assertIsInstance(c.anim, Animator)
        self.assertEqual(c.anim.rig, "orc")
        for eid in ("fast", "tank", "ranged", "warlock", "elite", "shielded"):
            self.assertIsNone(make(eid).anim, f"{eid} should stay primitive")

    def test_hit_sets_hurt_timer_and_restarts_the_flinch(self):
        e = make("chaser")
        e.anim.play("walk")
        e.take_damage(3.0)
        self.assertGreater(e._hurt_t, 0.0)
        self.assertEqual(e.anim.anim, "hurt")

    def test_anim_name_priority(self):
        e = make("chaser")
        e.vel.update(50, 0)
        self.assertEqual(e._anim_name(), "walk")
        e.vel.update(0, 0)
        self.assertEqual(e._anim_name(), "idle")
        e._hurt_t = 0.1
        self.assertEqual(e._anim_name(), "hurt")
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

    def test_dot_does_not_trip_the_flinch(self):
        e = make("chaser")
        e._status_damage(2.0, _ctx())        # burn tick path
        self.assertEqual(e._hurt_t, 0.0)


class DeathLifecycleTests(unittest.TestCase):
    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        return g, g.state_machine.current

    def test_sprited_enemy_lingers_render_only_then_drops(self):
        g, p = self._playing()
        p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(60, 0))
        e = p.enemies[-1]
        kills0 = p.stats["kills"]
        e.hp = 0.0
        e.alive = False
        p._cull_dead_enemies()

        self.assertEqual(p.stats["kills"], kills0 + 1)   # death effects fired now
        self.assertNotIn(e, p.enemies)                   # out of the live list
        self.assertEqual([d[0] for d in p._dying], [e])  # ...into the dying list
        self.assertEqual(e.anim.anim, "death")

        for _ in range(40):                              # ~0.66 s
            p._update_dying(1 / 60)
        self.assertEqual(p._dying, [])                   # expired and dropped
        pygame.quit()

    def test_plain_enemy_vanishes_immediately(self):
        g, p = self._playing()
        p._spawn_enemy("fast", at=p.player.pos + pygame.Vector2(60, 0))
        e = p.enemies[-1]
        e.hp = 0.0
        e.alive = False
        p._cull_dead_enemies()
        self.assertNotIn(e, p.enemies)
        self.assertEqual(p._dying, [])
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
