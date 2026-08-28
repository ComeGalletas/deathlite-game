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
from game.content import get_content
from systems.animation import Animator
from tests.aictx import ai_ctx


def _ctx(dt=1 / 30, player=(0, 0)):
    return ai_ctx(dt=dt, player=player)


def make(eid, x=200, y=0):
    return Enemy(eid, get_content().enemy(eid), x, y)


ALL_ENEMIES = tuple(get_content().enemies)          # every enemy is sprited now


class EnemyRigTests(unittest.TestCase):
    def test_every_enemy_has_an_animator(self):
        self.assertEqual(make("chaser").anim.rig, "skull")
        for eid in ALL_ENEMIES:
            self.assertIsInstance(make(eid).anim, Animator, eid)

    def test_fsm_telegraph_and_attack_states_play_the_attack_anim(self):
        def phase(enemy, name):
            enemy.bb.slot("__machine__")["state"] = name

        e = make("charger")
        self.assertEqual(e._anim_name(), "idle")
        phase(e, "telegraph")
        self.assertEqual(e._anim_name(), "attack")
        phase(e, "attack")
        self.assertEqual(e._anim_name(), "attack")
        phase(e, "recover")
        self.assertEqual(e._anim_name(), "idle")
        b = make("brute")
        phase(b, "telegraph")
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
        self.assertEqual(p._death_fx[-1][4], p.player.radius)   # carries the radius
        self.assertIsNotNone(p._death_seq_t)
        pygame.quit()

    def test_enemy_poof_carries_the_enemy_radius(self):
        g, p = self._playing()
        e = self._kill_one(p, "tank")
        self.assertEqual(p._death_fx[-1][4], e.radius)
        pygame.quit()


class _BlitRecorder:
    """A stand-in surface that logs (src, x, y) for every blit."""
    def __init__(self, size=(1600, 900)):
        self._size = size
        self.calls = []

    def blit(self, src, dest, *a, **k):
        x, y = dest[0], dest[1]
        self.calls.append((src, x, y))

    def get_size(self):
        return self._size

    def fill(self, *a, **k):
        pass


class SpriteAnchorDropTests(unittest.TestCase):
    """The character sprite is drawn `SPRITE_ANCHOR_DROP * radius` below the
    collider centre so more of it sits inside the collision circle. Render-only."""

    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        return g, g.state_machine.current

    def test_sprite_drop_is_fraction_of_radius_times_zoom(self):
        from game import config
        g, p = self._playing()
        exp = config.SPRITE_ANCHOR_DROP * 20.0 * p.camera.zoom
        self.assertAlmostEqual(p._sprite_drop(20.0), exp)
        pygame.quit()

    def test_hero_blit_sits_below_the_collider_by_the_drop(self):
        g, p = self._playing()
        _, collider_y = p.camera.world_to_screen(p.player.pos)
        ax, ay = p.game.assets.anchor(p._hero_anim.rig)
        z = p.camera.zoom
        rec = _BlitRecorder()
        p._draw_player(rec)
        hero_blits = [c for c in rec.calls if c[0] is not None]
        self.assertTrue(hero_blits)
        _, _, blit_y = hero_blits[0]
        # blit_y == collider_y - ay*z + drop   (drop > 0 -> lower on screen)
        self.assertAlmostEqual(blit_y, collider_y - ay * z + p._sprite_drop(p.player.radius))
        self.assertGreater(p._sprite_drop(p.player.radius), 0.0)
        pygame.quit()

    def test_zero_drop_puts_the_anchor_back_on_the_collider(self):
        from game import config
        g, p = self._playing()
        old = config.SPRITE_ANCHOR_DROP
        config.SPRITE_ANCHOR_DROP = 0.0
        try:
            self.assertEqual(p._sprite_drop(999.0), 0.0)
            _, collider_y = p.camera.world_to_screen(p.player.pos)
            ax, ay = p.game.assets.anchor(p._hero_anim.rig)
            rec = _BlitRecorder()
            p._draw_player(rec)
            _, _, blit_y = next(c for c in rec.calls if c[0] is not None)
            self.assertAlmostEqual(blit_y, collider_y - ay * p.camera.zoom)
        finally:
            config.SPRITE_ANCHOR_DROP = old
        pygame.quit()

    def test_depth_sort_key_is_still_the_unshifted_entity_y(self):
        g, p = self._playing()
        p._spawn_enemy("chaser", at=pygame.Vector2(p.player.pos.x, p.player.pos.y + 40))
        e = p.enemies[-1]
        keys = {round(y, 3) for y, _ in p._depth_items()}
        self.assertIn(round(e.pos.y, 3), keys)
        self.assertIn(round(p.player.pos.y, 3), keys)
        pygame.quit()


class EnemyStateRingsTests(unittest.TestCase):
    """The elite / shield / status rings at the collider edge read like a
    collision circle. config.SHOW_ENEMY_STATE_RINGS gates them for sprited
    enemies (default off); a primitive-fallback enemy always keeps them."""

    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        return g, g.state_machine.current

    def _circles(self, p, e):
        """Count pygame.draw.circle calls made by _draw_one_enemy(e)."""
        n = [0]
        real = pygame.draw.circle
        pygame.draw.circle = lambda *a, **k: (n.__setitem__(0, n[0] + 1),
                                              real(*a, **k))[1]
        try:
            p._draw_one_enemy(pygame.Surface((1600, 900)), e)
        finally:
            pygame.draw.circle = real
        return n[0]

    def test_sprited_elite_draws_no_ring_by_default_but_does_when_flag_on(self):
        from game import config
        g, p = self._playing()
        p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(80, 0))
        e = p.enemies[-1]
        e.is_elite = True
        self.assertIsNotNone(e.anim)                       # sprited
        old = config.SHOW_ENEMY_STATE_RINGS
        try:
            config.SHOW_ENEMY_STATE_RINGS = False
            self.assertEqual(self._circles(p, e), 0)       # sprite only, no ring
            config.SHOW_ENEMY_STATE_RINGS = True
            self.assertGreaterEqual(self._circles(p, e), 1)  # elite ring back
        finally:
            config.SHOW_ENEMY_STATE_RINGS = old
        pygame.quit()

    def test_primitive_enemy_always_shows_its_state_rings(self):
        from game import config
        g, p = self._playing()
        p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(80, 0))
        e = p.enemies[-1]
        e.anim = None                                     # force the primitive path
        e.is_elite = True
        old = config.SHOW_ENEMY_STATE_RINGS
        try:
            config.SHOW_ENEMY_STATE_RINGS = False
            # body disc + elite ring at least
            self.assertGreaterEqual(self._circles(p, e), 2)
        finally:
            config.SHOW_ENEMY_STATE_RINGS = old
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
