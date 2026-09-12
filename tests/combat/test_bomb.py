"""Six-weapon system P1: the Bomb (design §3.6). A fused, inert throw that
lands on its target, sits, and detonates into a blast that scores through
the normal hit resolver."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from combat.weapons.bomb import landing_time
from game.states.playing.projectiles.bomb import anim_for
from entities.projectile import Projectile
from game.content import get_content
from game.states.playing.combat import CombatResolver
from game.states.playing.effects import TransientFx
from tests.combat.fakes import FakeEnemy, fake_ps


class _Target:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


class _Shot:
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def bomb():
    w = Weapon("bomb", get_content().weapon("bomb"))
    w._cd = 0.0
    return w


def ctx(enemies, sink, **over):
    base = dict(origin=pygame.Vector2(0, 0), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: (sink.append(_Shot(**kw)), sink[-1])[1])
    base.update(over)
    return FireContext(**base)


DATA = get_content().weapon("bomb")
# Every distance in this module is derived from the data, never written down.
# The Bomb's `reach` and `blast_radius` are live balance knobs and have
# already been retuned mid-flight (reach 320 -> 100, blast 72 -> 42); a
# target outside the reach ring means the weapon simply never fires, which
# reads as a dozen unrelated failures.
NEAR = float(DATA["reach"]) * 0.4          # comfortably inside the ring
# The full `throw_time` is only spent on a target at least this far away.
FULL_THROW_AT = float(DATA["projectile_speed"]) * float(DATA["throw_time"])


class ThrowTests(unittest.TestCase):
    def test_a_throw_is_one_inert_fused_projectile(self):
        sink = []
        self.assertTrue(bomb().update(1 / 60, ctx([_Target(NEAR, 0)], sink)))
        self.assertEqual(len(sink), 1)
        s = sink[0]
        self.assertTrue(s.inert)
        self.assertAlmostEqual(s.lifetime, DATA["fuse"])
        self.assertAlmostEqual(s.blast_radius, DATA["blast_radius"])
        self.assertAlmostEqual(s.blast_lifetime, DATA["blast_lifetime"])
        self.assertEqual(s.weapon_id, "bomb")
        self.assertAlmostEqual(s.vel.length(), DATA["projectile_speed"])

    def test_it_stops_on_a_near_target_rather_than_flying_past(self):
        sink = []
        bomb().update(1 / 60, ctx([_Target(NEAR, 0)], sink))
        self.assertAlmostEqual(sink[0].stop_after, NEAR / DATA["projectile_speed"])

    def test_the_far_end_of_the_throw_is_whichever_of_the_two_caps_first(self):
        """`landing_time`'s two halves through the fire path.

        The full `throw_time` is only spent on a target at least
        `projectile_speed * throw_time` away, and the reach ring decides
        whether an auto-throw can ever have one. Both regimes are real
        balance states, so the test asserts whichever one the current data
        puts the Bomb in rather than pinning a number that a tuning pass
        invalidates. Today `reach` (100) is under that distance (165), so
        every auto-throw lands on its target and the full throw is reachable
        only on a manual whiff -- covered by
        `test_manual_throw_whiffs_into_empty_space_with_the_full_throw`.
        """
        speed = float(DATA["projectile_speed"])
        reach = float(DATA["reach"])
        sink = []
        if reach >= FULL_THROW_AT:
            bomb().update(1 / 60, ctx([_Target(FULL_THROW_AT + 10, 0)], sink))
            self.assertAlmostEqual(sink[0].stop_after, DATA["throw_time"])
        else:
            bomb().update(1 / 60, ctx([_Target(reach, 0)], sink))
            self.assertAlmostEqual(sink[0].stop_after, reach / speed)
            self.assertLess(
                sink[0].stop_after, float(DATA["throw_time"]),
                "the reach ring caps the throw short of its full arc")

    def test_landing_time_helper(self):
        o = pygame.Vector2()
        self.assertAlmostEqual(landing_time(o, [], 300, 0.55), 0.55)
        self.assertAlmostEqual(landing_time(o, [_Target(60, 0)], 300, 0.55), 0.2)
        self.assertEqual(landing_time(o, [_Target(60, 0)], 0, 0.55), 0.0)

    def test_extra_bombs_fan_out(self):
        sink = []
        w = bomb()
        w.bonus["projectile_count"] += 2
        w.update(1 / 60, ctx([_Target(NEAR, 0)], sink))
        self.assertEqual(len(sink), 3)
        self.assertEqual(len({round(s.vel.y) for s in sink}), 3)

    def test_manual_throw_whiffs_into_empty_space_with_the_full_throw(self):
        from game.states.playing.aim import AimInput
        sink = []
        held = AimInput(pygame.Vector2(0, -1), "keys", held=True)
        self.assertTrue(bomb().update(1 / 60, ctx([], sink, aim=held)))
        self.assertAlmostEqual(sink[0].vel.normalize().y, -1.0)
        self.assertAlmostEqual(sink[0].stop_after, DATA["throw_time"])


class ProjectileFlightTests(unittest.TestCase):
    def _thrown(self):
        p = Projectile()
        p.active = True
        p.reset(pos=(0, 0), vel=(300, 0), damage=10, radius=8, lifetime=1.1,
                inert=True, stop_after=0.5, blast_radius=72, blast_lifetime=0.12)
        return p

    def test_it_halts_after_stop_after_and_keeps_its_fuse_running(self):
        p = self._thrown()
        for _ in range(31):                     # just past 0.5 s
            p.update(1 / 60)
        self.assertAlmostEqual(p.pos.x, 150, delta=6)
        self.assertEqual(p.vel, pygame.Vector2())
        self.assertTrue(p.active)
        for _ in range(36):                     # to ~1.12 s
            p.update(1 / 60)
        self.assertFalse(p.active)
        self.assertAlmostEqual(p.pos.x, 150, delta=6)

    def test_reset_clears_the_bomb_fields_for_the_next_shot(self):
        p = self._thrown()
        p.detonated = True
        p.reset(pos=(0, 0), vel=(1, 0), damage=1, radius=1, lifetime=1)
        self.assertFalse(p.inert)
        self.assertEqual(p.blast_radius, 0.0)
        self.assertEqual(p.stop_after, 0.0)
        self.assertFalse(p.detonated)
        self.assertEqual(p.age, 0.0)


class DetonationTests(unittest.TestCase):
    """Through `TransientFx.update_projectiles` and `CombatResolver`."""

    def _throw(self, ps):
        fx = TransientFx(ps)
        p = ps._spawn_projectile(pos=(0, 0), vel=(300, 0), damage=30, radius=8,
                                 lifetime=1.1, inert=True, stop_after=0.5,
                                 blast_radius=72, blast_lifetime=0.12,
                                 src_weight=22, weapon_id="bomb",
                                 source_tags=("ranged", "area"))
        return fx, p

    def test_a_flying_bomb_scores_no_direct_hit(self):
        e = FakeEnemy(20, 0)
        ps = fake_ps([e])
        self._throw(ps)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(e.hp, 100.0)

    def test_the_fuse_spawns_a_blast_that_damages_everything_in_radius(self):
        near, far = FakeEnemy(150, 40), FakeEnemy(150, 300)
        ps = fake_ps([near, far])
        fx, bomb_p = self._throw(ps)
        for _ in range(67):                         # 1.12 s: the fuse runs out
            fx.update_projectiles(1 / 60)
        self.assertTrue(bomb_p.detonated)
        live = [p for p in ps.projectiles if p.active]
        self.assertEqual(len(live), 1)
        blast = live[0]
        self.assertEqual(blast.style, "blast")
        self.assertAlmostEqual(blast.radius, 72)
        self.assertEqual(blast.pierce_left, 999)
        self.assertAlmostEqual(blast.pos.x, 150, delta=6)
        self.assertEqual(len(ps._explosions), 1)     # the ring visual
        CombatResolver(ps).projectile_hits()
        self.assertEqual(near.hp, 70.0)
        self.assertEqual(far.hp, 100.0)
        self.assertTrue(near.knocks, "a blast shoves like any weighted hit")

    def test_the_blast_expires_after_its_lifetime(self):
        ps = fake_ps([])
        fx, _ = self._throw(ps)
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        for _ in range(9):                          # 0.15 s > blast_lifetime
            fx.update_projectiles(1 / 60)
        self.assertEqual([p for p in ps.projectiles if p.active], [])

    def test_a_bomb_detonates_once(self):
        ps = fake_ps([])
        fx, bomb_p = self._throw(ps)
        for _ in range(80):
            fx.update_projectiles(1 / 60)
        self.assertEqual(len(ps._explosions), 1)

    def test_a_blocked_bomb_detonates_where_it_stopped(self):
        e = FakeEnemy(10, 0)
        ps = fake_ps([e], blocked=True)              # every step hits an obstacle
        fx, bomb_p = self._throw(ps)
        fx.update_projectiles(1 / 60)
        self.assertTrue(bomb_p.detonated)
        blast = [p for p in ps.projectiles if p.active and p.style == "blast"]
        self.assertEqual(len(blast), 1)
        self.assertLess(blast[0].pos.x, 10)



class BlastAreaTests(unittest.TestCase):
    """2026-09-12: the blast is part of the weapon **area** system
    (`Weapon._blast_radius`), not a stand-alone number -- the hero's
    `area_multiplier`, the weapon's `bonus["area"]` and the Blast Amplifier
    multiplier all reach it. The thrown ball's own collider does not grow
    with them beyond the ordinary `_area` scaling."""

    BASE = DATA["blast_radius"]

    def _blast(self, **over):
        w = bomb()
        for key, value in over.pop("bonus", {}).items():
            w.bonus[key] = value
        sink = []
        w.update(1 / 60, ctx([_Target(NEAR, 0)], sink, **over))
        return sink[0]

    def test_unmodified_it_is_the_data_field(self):
        self.assertAlmostEqual(self._blast().blast_radius, self.BASE)

    def test_the_hero_area_multiplier_widens_the_explosion(self):
        # `of Expanse` items used to widen every area and reach ring in the
        # game while leaving the Bomb's blast alone.
        s = self._blast(area_multiplier=1.25)
        self.assertAlmostEqual(s.blast_radius, self.BASE * 1.25)

    def test_an_area_bonus_widens_the_explosion(self):
        s = self._blast(bonus={"area": 10.0})
        self.assertAlmostEqual(s.blast_radius, self.BASE + 10)

    def test_the_blast_radius_multiplier_scales_the_total(self):
        s = self._blast(bonus={"blast_radius_mult": 1.75})
        self.assertAlmostEqual(s.blast_radius, self.BASE * 1.75)

    def test_flat_adds_land_inside_the_multiplier(self):
        s = self._blast(bonus={"blast_radius": 60.0, "blast_radius_mult": 1.75})
        self.assertAlmostEqual(s.blast_radius, (self.BASE + 60) * 1.75)

    def test_every_area_source_composes(self):
        s = self._blast(area_multiplier=1.25,
                        bonus={"area": 10.0, "blast_radius": 24.0,
                               "blast_radius_mult": 1.3})
        self.assertAlmostEqual(s.blast_radius,
                               (self.BASE + 24 + 10) * 1.25 * 1.3)

    def test_the_thrown_ball_keeps_its_own_small_collider(self):
        # It stops the throw on obstacles and trips a Minefield mine, so it
        # must stay far smaller than the explosion it carries.
        s = self._blast(bonus={"blast_radius_mult": 1.75})
        self.assertAlmostEqual(s.radius, DATA["area"])
        self.assertLess(s.radius, s.blast_radius / 4)

    def _detonate(self, enemies, **bonus):
        """Throw at the nearest of `enemies` through the real `TransientFx`
        and run the fuse out; returns `(ps, the blast projectile)`."""
        ps = fake_ps(enemies)
        fx = TransientFx(ps)
        w = bomb()
        for key, value in bonus.items():
            w.bonus[key] = value
        w.update(1 / 60, FireContext(
            origin=pygame.Vector2(0, 0), enemies=list(enemies),
            damage_multiplier=1.0, attack_speed_multiplier=1.0,
            projectile_speed_multiplier=1.0, area_multiplier=1.0,
            fallback_dir=pygame.Vector2(1, 0),
            spawn_projectile=ps._spawn_projectile))
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        blast = [p for p in ps.projectiles if p.active and p.style == "blast"][0]
        return ps, blast

    def test_the_detonation_uses_the_widened_radius(self):
        """End to end: the damage circle and the burst visual are both the
        grown radius, and an enemy just outside the base blast is only
        caught once it is widened."""
        target = FakeEnemy(NEAR, 0)
        # Just beyond the base blast's bite (radius + body), so the base
        # misses it and 1.75x -- far more than the 2 px of slack -- catches it.
        gap = self.BASE + target.radius + 2.0
        self.assertGreater(self.BASE * 1.75 + target.radius, gap,
                           "the multiplier must clear the gap for this to mean anything")
        far = FakeEnemy(NEAR + gap, 0)

        ps, blast = self._detonate([target, far])            # unmodified
        self.assertAlmostEqual(blast.radius, self.BASE)
        self.assertAlmostEqual(ps._explosions[0]["radius"], self.BASE)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(far.hp, 100.0, "the base blast does not reach it")

        far.hp = 100.0
        ps, blast = self._detonate([FakeEnemy(NEAR, 0), far],
                                   blast_radius_mult=1.75)
        self.assertAlmostEqual(blast.radius, self.BASE * 1.75)
        self.assertAlmostEqual(ps._explosions[0]["radius"], self.BASE * 1.75)
        CombatResolver(ps).projectile_hits()
        self.assertLess(far.hp, 100.0, "the widened blast does")

    def test_cluster_bomblets_inherit_the_widened_radius(self):
        """Cluster Bomb sizes a bomblet off its parent blast, so the area
        binding reaches them too."""
        ps = fake_ps([])
        fx = TransientFx(ps)
        w = bomb()
        w.forge = "cluster_bomb"
        w.effects.update(cluster_count=3, cluster_radius_mult=0.6,
                         cluster_fuse=0.55, cluster_speed=180,
                         cluster_damage_mult=0.4)
        w.bonus["blast_radius_mult"] = 1.5
        ps.player.weapons.append(w)       # `weapon_by_id` closes over the list
        w.update(1 / 60, FireContext(
            origin=pygame.Vector2(0, 0), enemies=[_Target(NEAR, 0)],
            damage_multiplier=1.0, attack_speed_multiplier=1.0,
            projectile_speed_multiplier=1.0, area_multiplier=1.0,
            fallback_dir=pygame.Vector2(1, 0),
            spawn_projectile=ps._spawn_projectile))
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        bomblets = [p for p in ps.projectiles
                    if p.active and "cluster" in p.source_tags]
        self.assertEqual(len(bomblets), 3)
        for b in bomblets:
            self.assertAlmostEqual(b.blast_radius, self.BASE * 1.5 * 0.6)


class BombletFxTests(unittest.TestCase):
    """Cluster Bomb bomblets are the parent bomb, smaller and not rolling
    (owner, 2026-09-12): the same `bomb` rig at `cluster_radius_mult` of its
    scale, holding the lit fuse instead of the `spin` strip, and detonating
    into the `explosion_small` sheet rather than a shrunken copy of the
    parent's `explosion`."""

    FORGE = "cluster_bomb"

    def _cluster(self):
        ps = fake_ps([])
        fx = TransientFx(ps)
        w = bomb()
        w.forge = self.FORGE
        w.effects.update(get_content().forges[self.FORGE]["effects"])
        ps.player.weapons.append(w)       # `weapon_by_id` closes over the list
        w.update(1 / 60, FireContext(
            origin=pygame.Vector2(0, 0), enemies=[_Target(NEAR, 0)],
            damage_multiplier=1.0, attack_speed_multiplier=1.0,
            projectile_speed_multiplier=1.0, area_multiplier=1.0,
            fallback_dir=pygame.Vector2(1, 0),
            spawn_projectile=ps._spawn_projectile))
        parent = ps.projectiles[0] if hasattr(ps.projectiles, "__getitem__") else None
        for _ in range(67):
            fx.update_projectiles(1 / 60)          # parent fuse -> scatter
        bomblets = [p for p in ps.projectiles
                    if p.active and "cluster" in p.source_tags]
        return ps, fx, w, bomblets

    # --- the rig each detonation plays -----------------------
    def test_burst_rig_is_the_small_sheet_only_for_a_bomblet(self):
        fx = TransientFx(fake_ps([]))
        plain = _Shot(source_tags=("ranged", "area", "explosive"))
        clustered = _Shot(source_tags=("ranged", "area", "explosive", "cluster"))
        self.assertEqual(fx.burst_rig(plain), "explosion")
        self.assertEqual(fx.burst_rig(clustered), "explosion_small")

    def test_the_small_sheet_is_a_real_one_shot_rig(self):
        from game.assets import get_assets
        a = get_assets()
        self.assertEqual(a.frame_count("explosion_small", "burst"), 8)
        self.assertFalse(a.loops("explosion_small", "burst"))
        self.assertLess(a.frame_count("explosion_small", "burst"),
                        a.frame_count("explosion", "burst"),
                        "a bomblet's burst is shorter than the parent's")
        self.assertLess(float(a.rig("explosion_small")["fireball"]),
                        float(a.rig("explosion")["fireball"]),
                        "and its fireball is drawn smaller at the same radius")

    def test_a_bomblet_detonation_carries_the_small_burst(self):
        from game.assets import get_assets
        ps, fx, _w, bomblets = self._cluster()
        self.assertEqual(len(ps._explosions), 1)                  # the parent's
        self.assertEqual(ps._explosions[0]["anim"].rig, "explosion")
        for _ in range(40):                                       # bomblet fuses
            fx.update_projectiles(1 / 60)
        small = [e for e in ps._explosions if e["anim"].rig == "explosion_small"]
        self.assertEqual(len(small), len(bomblets))
        a = get_assets()
        for e in small:
            self.assertEqual(e["anim"].anim, "burst")
            self.assertAlmostEqual(
                e["dur"], a.frame_count("explosion_small", "burst")
                / a.fps("explosion_small", "burst"))

    def test_burst_visual_still_falls_back_to_the_ring_for_a_missing_rig(self):
        fx = TransientFx(fake_ps([]))
        entry = fx.burst_visual(pygame.Vector2(), 40.0, rig="no_such_rig")
        self.assertNotIn("anim", entry)
        self.assertAlmostEqual(entry["dur"], 0.35)

    # --- the ball in flight ----------------------------------
    def test_a_bomblet_holds_the_fuse_and_never_rolls(self):
        _ps, _fx, _w, bomblets = self._cluster()
        self.assertTrue(bomblets)
        for b in bomblets:
            self.assertGreater(b.vel.length(), 0.0, "it is still flying outward")
            self.assertEqual(anim_for(b), "fuse")

    def test_the_parent_still_rolls_while_it_flies(self):
        sink = []
        bomb().update(1 / 60, ctx([_Target(NEAR, 0)], sink))
        self.assertEqual(anim_for(sink[0]), "spin")

    # --- the ball's size -------------------------------------
    def test_bomblet_scale_is_the_rig_scale_times_the_radius_mult(self):
        from game.assets import get_assets
        fx = TransientFx(fake_ps([]))
        bw, bh = get_assets().scale_for("bomb")
        self.assertEqual(fx.bomblet_scale(0.6), (bw * 0.6, bh * 0.6))

    def test_a_bomblet_is_drawn_smaller_than_its_parent(self):
        from game.assets import get_assets
        ps, _fx, w, bomblets = self._cluster()
        parent_scale = get_assets().scale_for("bomb")        # the parent's `fx` is empty
        mult = float(w.effects["cluster_radius_mult"])
        for b in bomblets:
            self.assertEqual(tuple(b.fx["scale"]),
                             (parent_scale[0] * mult, parent_scale[1] * mult))
            self.assertLess(b.fx["scale"][0], parent_scale[0])
            self.assertLess(b.fx["scale"][1], parent_scale[1])
        # `fake_ps` spawns without `_resolve_visual`, so the sprite *identity*
        # cannot be shown here -- `BombletSpriteTests` does it on the real
        # spawn path.


class BombletSpriteTests(unittest.TestCase):
    """That a bomblet wears the *parent's* sprite needs the real spawn path:
    `PlayingState._resolve_visual` falls back to `weapon_visual(weapon_id)`,
    and `scatter_bomblets` passes `weapon_id="bomb"` with no `style` of its
    own, so a bomblet resolves the Bomb's own entry. `fake_ps` skips that
    resolution, hence one booted run here -- built once for the class."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from game.game import Game
        from game.states.playing.state import PlayingState
        cls.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        cls.ps = PlayingState(cls.game)
        cls.ps.enter(seed=7)
        cls.ps.enemies.clear()

    def _scatter(self):
        ps = self.ps
        for p in list(ps.projectiles):             # reuse the booted run's pool
            p.active = False
        ps.projectiles.sweep()
        ps._explosions.clear()
        w = bomb()
        w.forge = "cluster_bomb"
        w.effects.update(get_content().forges["cluster_bomb"]["effects"])
        ps.player.weapons.clear()
        ps.player.weapons.append(w)
        parent = ps._spawn_projectile(
            pos=pygame.Vector2(ps.player.pos), vel=pygame.Vector2(),
            damage=20, radius=float(w.definition["area"]), lifetime=0.01,
            pierce=0, src_weight=w._weight(), weapon_id="bomb",
            visual=w.visual_id, source_tags=w.tags, inert=True, stop_after=0.0,
            blast_radius=w._blast_radius(1.0),
            blast_lifetime=float(w.definition["blast_lifetime"]))
        ps.fx.update_projectiles(0.02)             # parent fuse ends -> scatter
        bomblets = [q for q in ps.projectiles
                    if q.active and "cluster" in q.source_tags]
        return parent, bomblets, w

    def test_a_bomblet_resolves_the_parents_bomb_sprite(self):
        parent, bomblets, _w = self._scatter()
        self.assertEqual(parent.style, "bomb")
        self.assertTrue(bomblets)
        for b in bomblets:
            self.assertEqual(b.style, "bomb", "same sprite as the parent")
            self.assertEqual(b.color, parent.color)

    def test_it_is_smaller_and_holds_the_fuse_on_the_real_path(self):
        from game.assets import get_assets
        parent, bomblets, w = self._scatter()
        base = get_assets().scale_for("bomb")
        mult = float(w.effects["cluster_radius_mult"])
        self.assertEqual(parent.fx, {}, "the parent draws at the rig's own scale")
        for b in bomblets:
            self.assertEqual(tuple(b.fx["scale"]), (base[0] * mult, base[1] * mult))
            self.assertEqual(anim_for(b), "fuse")
            self.assertAlmostEqual(b.blast_radius, parent.blast_radius * mult)


class BurstVisualTests(unittest.TestCase):
    """The detonation plays `effects/explosion_2.png` (the `explosion` rig's
    one-shot `burst`) for exactly the strip's length, scaled to the blast."""

    def _detonated(self):
        ps = fake_ps([])
        fx = TransientFx(ps)
        p = ps._spawn_projectile(pos=(0, 0), vel=(300, 0), damage=30, radius=8,
                                 lifetime=1.1, inert=True, stop_after=0.5,
                                 blast_radius=72, blast_lifetime=0.12,
                                 src_weight=22, weapon_id="bomb",
                                 source_tags=("ranged", "area"))
        for _ in range(67):
            fx.update_projectiles(1 / 60)
        self.assertTrue(p.detonated)
        return ps, fx, ps._explosions[0]

    def test_the_bomb_burst_carries_the_explosion_animation(self):
        from game.assets import get_assets
        ps, fx, ex = self._detonated()
        self.assertEqual(ex["anim"].rig, "explosion")
        self.assertEqual(ex["anim"].anim, "burst")
        self.assertAlmostEqual(ex["radius"], 72)      # the blast_radius above
        a = get_assets()
        # Frame count read off the rig, not pinned at 10: re-cutting the
        # explosion strip is an art change, and the claim here is that the
        # burst lasts exactly the strip, whatever length that is.
        frames = a.frame_count("explosion", "burst")
        self.assertGreater(frames, 0)
        self.assertFalse(a.loops("explosion", "burst"))
        self.assertAlmostEqual(ex["dur"], frames / a.fps("explosion", "burst"))

    def test_the_burst_advances_and_is_culled_when_the_strip_ends(self):
        ps, fx, ex = self._detonated()
        fx.update_explosions(ex["dur"] / 2)
        self.assertEqual(ex["anim"].t, ex["dur"] / 2)
        self.assertFalse(ex["anim"].finished)
        self.assertIn(ex, ps._explosions)
        fx.update_explosions(ex["dur"] / 2 + 0.001)
        self.assertTrue(ex["anim"].finished)
        self.assertNotIn(ex, ps._explosions)

    def test_the_renderer_scales_the_burst_to_the_blast_diameter(self):
        from types import SimpleNamespace
        from game.assets import get_assets
        from game.states.playing.rendering import WorldRenderer
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        ps, fx, ex = self._detonated()
        fx.update_explosions(0.2)                     # mid-burst: the widest frames
        a = get_assets()
        camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda p: (p.x + 200, p.y + 200))
        r_ps = SimpleNamespace(game=SimpleNamespace(assets=a), camera=camera,
                               _explosions=[ex])
        surf = pygame.Surface((800, 800), pygame.SRCALPHA)
        WorldRenderer(r_ps).explosions(surf)
        bb = surf.get_bounding_rect(min_alpha=1)
        cx, cy = ex["pos"].x + 200, ex["pos"].y + 200
        self.assertTrue(bb.collidepoint(cx, cy))
        self.assertAlmostEqual(bb.centerx, cx, delta=8)   # centred on the blast
        self.assertAlmostEqual(bb.width, 2 * 72, delta=10)   # fireball spans the diameter
        # sheet gone -> the ring is drawn instead, never a crash
        a.frame = lambda *args, **kw: None
        try:
            surf.fill((0, 0, 0, 0))
            WorldRenderer(r_ps).explosions(surf)
            self.assertGreater(surf.get_bounding_rect(min_alpha=1).width, 0)
        finally:
            del a.frame


if __name__ == "__main__":
    unittest.main()
