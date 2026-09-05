"""CB-5 manual aim: the input side (group B).

Pure tests for `game.states.playing.aim.read_aim` -- the priority ladder
(click > held aim key > nothing), the layout swap, the tap flag, the cursor-on-
hero fallback -- and for the hero's facing override. The state-level wiring
(`Q` toggle, the tap queue, the frame's `AimInput`) is in
`ManualAimStateTests` further down, driven through a real headless
PlayingState. The weapon side (group C) -- the assist cone, the forced-fire
path that ignores the reach ring, the auto-attack hold, orbiters on a held
click, the tap spent on fire -- is `ConeTests` / `WeaponAimTests` /
`TapConsumptionTests`.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import math

from combat import targeting
from combat.weapons import FireContext, Weapon
from entities.player import Player
from game import config
from game.content import get_content
from game.states.playing.aim import AimInput, mouse_direction, read_aim
from systems.camera import Camera

WASD = config.KEY_LAYOUTS["wasd_move"]
ARROWS_MOVE = config.KEY_LAYOUTS["arrows_move"]
_ALL_KEYS = (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
             pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)


def keys(*pressed):
    return {k: (k in pressed) for k in _ALL_KEYS}


def mouse(left=False):
    return (left, False, False)


class _Cam:
    """A camera whose screen space *is* world space (zoom 1, at the origin)."""
    @staticmethod
    def screen_to_world(pos):
        return pygame.Vector2(pos)


ORIGIN = pygame.Vector2(500, 500)
RIGHT = pygame.Vector2(1, 0)


def aim(pressed=None, left=False, mouse_pos=(900, 500), layout=WASD,
        fallback=RIGHT, tap=False, camera=_Cam()):
    return read_aim(pressed or keys(), mouse(left), mouse_pos, camera, ORIGIN,
                    layout["aim"], fallback, tap_pending=tap)


class ReadAimTests(unittest.TestCase):
    def test_nothing_pressed_is_no_aim(self):
        a = aim()
        self.assertFalse(a.active)
        self.assertIsNone(a.source)
        self.assertFalse(a.wants_fire)
        self.assertEqual(a, AimInput.none())

    def test_held_aim_key_aims_and_keeps_firing(self):
        a = aim(keys(pygame.K_UP))
        self.assertEqual(a.source, "keys")
        self.assertTrue(a.held)
        self.assertFalse(a.tap)
        self.assertTrue(a.wants_fire)
        self.assertAlmostEqual(a.direction.y, -1.0)

    def test_diagonal_aim_keys_are_normalised(self):
        a = aim(keys(pygame.K_RIGHT, pygame.K_DOWN))
        self.assertAlmostEqual(a.direction.length(), 1.0, places=6)

    def test_movement_keys_never_aim(self):
        # Under the default layout WASD walks; it must not register as aim.
        self.assertFalse(aim(keys(pygame.K_d)).active)

    def test_layout_swap_moves_the_aim_keys(self):
        self.assertFalse(aim(keys(pygame.K_LEFT), layout=ARROWS_MOVE).active)
        a = aim(keys(pygame.K_a), layout=ARROWS_MOVE)
        self.assertEqual(a.source, "keys")
        self.assertAlmostEqual(a.direction.x, -1.0)

    def test_held_click_aims_at_the_cursor(self):
        a = aim(left=True, mouse_pos=(500, 100))       # straight up from the hero
        self.assertEqual(a.source, "mouse")
        self.assertTrue(a.held)
        self.assertTrue(a.wants_fire)
        self.assertAlmostEqual(a.direction.x, 0.0)
        self.assertAlmostEqual(a.direction.y, -1.0)

    def test_click_beats_a_held_aim_key(self):
        a = aim(keys(pygame.K_LEFT), left=True, mouse_pos=(900, 500))
        self.assertEqual(a.source, "mouse")
        self.assertAlmostEqual(a.direction.x, 1.0)     # cursor, not the key

    def test_queued_tap_aims_at_the_cursor_without_a_held_button(self):
        a = aim(tap=True, mouse_pos=(100, 500))
        self.assertEqual(a.source, "mouse")
        self.assertTrue(a.tap)
        self.assertFalse(a.held)
        self.assertTrue(a.wants_fire)
        self.assertAlmostEqual(a.direction.x, -1.0)

    def test_tap_beats_a_held_aim_key_too(self):
        a = aim(keys(pygame.K_UP), tap=True, mouse_pos=(900, 500))
        self.assertEqual(a.source, "mouse")

    def test_cursor_on_the_hero_falls_back_to_the_last_move_direction(self):
        a = aim(left=True, mouse_pos=(500, 500), fallback=pygame.Vector2(0, 1))
        self.assertAlmostEqual(a.direction.y, 1.0)
        # ...and to +x when there is no movement history either.
        a = aim(left=True, mouse_pos=(500, 500), fallback=pygame.Vector2())
        self.assertEqual(a.direction, RIGHT)

    def test_mouse_direction_goes_through_the_camera(self):
        cam = Camera(4000, 4000, 800, 600, zoom=2.0)
        cam.pos.update(400, 400)                       # top-left of the view
        # Screen (200, 300) at zoom 2 -> world (500, 550): straight down.
        d = mouse_direction((200, 300), cam, ORIGIN, RIGHT)
        self.assertAlmostEqual(d.x, 0.0)
        self.assertAlmostEqual(d.y, 1.0)

    def test_mouse_position_alone_does_nothing(self):
        # The cursor is inert unless clicked: no aim, whatever it hovers.
        self.assertFalse(aim(mouse_pos=(0, 0)).active)


class FacingOverrideTests(unittest.TestCase):
    class _World:
        @staticmethod
        def resolve_movement(prev, new, radius, flying=False):
            return pygame.Vector2(new)

    def test_face_sets_facing_and_update_keeps_it_for_that_frame(self):
        p = Player(100, 100)
        p.handle_input(keys(pygame.K_d), WASD["move"])   # walking right...
        p.face(pygame.Vector2(-1, 0))                     # ...aiming left
        self.assertEqual(p._facing, -1)
        p.update(1 / 60, self._World())
        self.assertEqual(p._facing, -1)                   # override held this frame
        p.update(1 / 60, self._World())
        self.assertEqual(p._facing, 1)                    # next frame: movement rule

    def test_vertical_aim_keeps_the_current_facing(self):
        p = Player(100, 100)
        p._facing = -1
        p.face(pygame.Vector2(0, -1))
        self.assertEqual(p._facing, -1)


# --- state wiring ----------------------------------------------------------
def _fresh_playing():
    from game.game import Game
    from game.states.menu_state import MenuState
    from game.states.playing_state import PlayingState
    from tests.boot import settle
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    for _ in range(2):                       # menu -> hero select -> loading
        game.state_machine.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    ps = settle(game)
    assert isinstance(ps, PlayingState)
    return game, ps


class ManualAimStateTests(unittest.TestCase):
    """One shared run for the class: the world build is the expensive part
    and nothing here mutates it."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _fresh_playing()

    def setUp(self):
        self.ps.auto_attack = config.AUTO_ATTACK_DEFAULT
        self.ps._tap_pending = False
        self.game.set_key_layout(config.DEFAULT_KEY_LAYOUT)

    def _event(self, **kw):
        self.ps.handle_event(pygame.event.Event(kw.pop("type"), **kw))

    def _frame_input(self, pressed=None, left=False, mouse_pos=(0, 0)):
        from unittest import mock
        with mock.patch.object(pygame.key, "get_pressed", return_value=pressed or keys()), \
             mock.patch.object(pygame.mouse, "get_pressed", return_value=mouse(left)), \
             mock.patch.object(pygame.mouse, "get_pos", return_value=mouse_pos):
            self.ps._phase_input()
        return self.ps._aim

    def test_auto_attack_defaults_on_and_q_toggles_it(self):
        self.assertTrue(self.ps.auto_attack)
        self._event(type=pygame.KEYDOWN, key=pygame.K_q)
        self.assertFalse(self.ps.auto_attack)
        self._event(type=pygame.KEYDOWN, key=pygame.K_q)
        self.assertTrue(self.ps.auto_attack)

    def test_left_click_queues_one_tap_until_consumed(self):
        self._event(type=pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0))
        self.assertFalse(self.ps._tap_pending)          # right button: nothing
        self._event(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))
        self.assertTrue(self.ps._tap_pending)
        a = self._frame_input()                          # button already released
        self.assertEqual(a.source, "mouse")
        self.assertTrue(a.tap)
        self.assertFalse(a.held)
        self.assertTrue(self._frame_input().tap)         # still queued next frame
        self.ps.consume_tap()
        self.assertFalse(self._frame_input().active)

    def test_no_input_is_no_aim(self):
        self.assertEqual(self._frame_input(), AimInput.none())

    def test_held_aim_key_faces_the_hero(self):
        self.ps.player._facing = 1
        a = self._frame_input(keys(pygame.K_LEFT))
        self.assertEqual(a.source, "keys")
        self.assertEqual(self.ps.player._facing, -1)
        self.assertTrue(self.ps.player._face_override)

    def test_held_click_aims_through_the_run_camera(self):
        cam = self.ps.camera
        target = self.ps.player.pos + pygame.Vector2(0, 200)      # below the hero
        a = self._frame_input(left=True, mouse_pos=cam.world_to_screen(target))
        self.assertEqual(a.source, "mouse")
        self.assertTrue(a.held)
        self.assertAlmostEqual(a.direction.y, 1.0, places=5)

    def test_movement_follows_the_active_layout(self):
        self._frame_input(keys(pygame.K_LEFT))
        self.assertEqual(self.ps.player._move_dir.length_squared(), 0.0)  # arrows aim
        self.game.set_key_layout("arrows_move")
        a = self._frame_input(keys(pygame.K_LEFT))
        self.assertAlmostEqual(self.ps.player._move_dir.x, -1.0)         # ...now walk
        self.assertFalse(a.active)                                        # and don't aim
        a = self._frame_input(keys(pygame.K_a))
        self.assertEqual(a.source, "keys")                                # WASD aims


# --- weapons -----------------------------------------------------------------
class FakeEnemy:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


class FakeProj:
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def weapon(wid):
    w = Weapon(wid, get_content().weapon(wid))
    w._cd = 0.0
    return w


def fire_ctx(enemies, sink, *, aim=None, auto_attack=True, origin=(0, 0)):
    o = pygame.Vector2(*origin)
    return FireContext(
        origin=o, enemies=list(enemies),
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=1.0,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: (sink.append(FakeProj(**kw)), sink[-1])[1],
        anchor=o, aim=aim, auto_attack=auto_attack)


def held_keys(direction):
    return AimInput(pygame.Vector2(direction).normalize(), "keys", held=True)


def held_click(direction):
    return AimInput(pygame.Vector2(direction).normalize(), "mouse", held=True)


def tap(direction):
    return AimInput(pygame.Vector2(direction).normalize(), "mouse", tap=True)


def bearing(v) -> float:
    return math.degrees(math.atan2(v.y, v.x))


class ConeTests(unittest.TestCase):
    O = pygame.Vector2(0, 0)
    RIGHT = pygame.Vector2(1, 0)

    def cone(self, enemies, half_deg=25.0, reach=400.0):
        return targeting.enemies_in_cone(self.O, self.RIGHT, enemies,
                                         math.radians(half_deg), reach)

    def test_angle_filter(self):
        inside = FakeEnemy(100, 30)        # ~17 deg off the aim
        outside = FakeEnemy(100, 70)       # ~35 deg
        behind = FakeEnemy(-100, 0)
        self.assertEqual(self.cone([inside, outside, behind]), [inside])

    def test_reach_filter(self):
        near, far = FakeEnemy(100, 0), FakeEnemy(500, 0)
        self.assertEqual(self.cone([near, far], reach=400), [near])
        self.assertEqual(self.cone([near, far], reach=float("inf")), [near, far])

    def test_enemy_on_the_origin_counts_as_inside(self):
        on_top = FakeEnemy(0, 0)
        self.assertEqual(self.cone([on_top]), [on_top])


class WeaponAimTests(unittest.TestCase):
    def test_forced_fire_ignores_the_empty_reach_ring(self):
        sink = []
        w = weapon("arcane_bolt")
        self.assertFalse(w.update(1 / 60, fire_ctx([], sink)))          # auto: ring empty
        self.assertEqual(sink, [])
        w._cd = 0.0
        self.assertTrue(w.update(1 / 60, fire_ctx([], sink, aim=held_keys((0, -1)))))
        self.assertEqual(len(sink), 1)
        self.assertAlmostEqual(bearing(sink[0].vel), -90.0)             # straight up
        self.assertGreater(w._cd, 0.0)                                  # cooldown restarted

    def test_manual_shot_homes_on_the_closest_enemy_in_the_cone(self):
        sink = []
        w = weapon("arcane_bolt")                                        # reach 400
        near_in = FakeEnemy(200, 40)                                     # ~11 deg, d=204
        far_in = FakeEnemy(300, -20)                                     # ~4 deg,  d=301
        off_axis = FakeEnemy(100, 150)                                   # ~56 deg, nearer
        w.update(1 / 60, fire_ctx([off_axis, far_in, near_in], sink, aim=held_keys((1, 0))))
        self.assertAlmostEqual(bearing(sink[0].vel), bearing(near_in.pos), places=4)

    def test_manual_shot_goes_straight_when_the_cone_is_empty(self):
        sink = []
        w = weapon("arcane_bolt")
        w.update(1 / 60, fire_ctx([FakeEnemy(100, 150)], sink, aim=held_keys((1, 0))))
        self.assertAlmostEqual(bearing(sink[0].vel), 0.0)

    def test_enemy_in_reach_but_outside_the_cone_is_ignored_even_when_nearest(self):
        sink = []
        w = weapon("arcane_bolt")
        w.update(1 / 60, fire_ctx([FakeEnemy(0, 60)], sink, aim=held_click((1, 0))))
        self.assertAlmostEqual(bearing(sink[0].vel), 0.0)

    def test_per_weapon_aim_assist_override(self):
        d = dict(get_content().weapon("arcane_bolt"))
        d["aim_assist_deg"] = 70
        w = Weapon("arcane_bolt", d); w._cd = 0.0
        sink = []
        e = FakeEnemy(30, 52)                                            # ~60 deg off the aim
        w.update(1 / 60, fire_ctx([e], sink, aim=held_click((1, 0))))
        self.assertAlmostEqual(bearing(sink[0].vel), bearing(e.pos), places=4)  # now inside

    def test_melee_cone_points_at_the_raw_aim(self):
        sink = []
        w = weapon("soul_scythe")
        # An enemy inside the assist cone but off-axis must not bend the swing.
        w.update(1 / 60, fire_ctx([FakeEnemy(40, 15)], sink, aim=held_keys((1, 0))))
        self.assertEqual(len(sink), 1)
        self.assertAlmostEqual(bearing(sink[0].cone_dir), 0.0)
        self.assertGreater(sink[0].cone_half_angle, 0.0)

    def test_melee_whiffs_into_empty_space(self):
        sink = []
        w = weapon("soul_scythe")
        self.assertTrue(w.update(1 / 60, fire_ctx([], sink, aim=held_click((-1, 0)))))
        self.assertAlmostEqual(bearing(sink[0].cone_dir), 180.0)

    def test_auto_attack_off_holds_but_keeps_the_weapon_ready(self):
        sink = []
        w = weapon("frost_shards")
        enemies = [FakeEnemy(100, 0)]
        for _ in range(30):
            self.assertFalse(w.update(1 / 60, fire_ctx(enemies, sink, auto_attack=False)))
        self.assertEqual(sink, [])
        self.assertEqual(w._cd, 0.0)
        # The first manual attack is instant.
        self.assertTrue(w.update(1 / 60, fire_ctx(enemies, sink, aim=tap((1, 0)),
                                                  auto_attack=False)))
        self.assertEqual(len(sink), w._projectile_count())              # one volley

    def test_auto_attack_off_still_fires_on_a_held_aim_key(self):
        sink = []
        w = weapon("frost_shards")
        self.assertTrue(w.update(1 / 60, fire_ctx([], sink, aim=held_keys((0, 1)),
                                                  auto_attack=False)))

    def test_multishot_fans_around_the_manual_aim(self):
        sink = []
        w = weapon("frost_shards")
        w.bonus["projectile_count"] += 2
        w.update(1 / 60, fire_ctx([], sink, aim=held_keys((0, -1))))
        angles = sorted(bearing(p.vel) for p in sink)
        n = w._projectile_count()                                       # data count + 2
        self.assertEqual(len(angles), n)
        self.assertAlmostEqual(sum(angles) / n, -90.0, places=4)        # centred on the aim
        self.assertGreater(angles[-1] - angles[0], 0.0)

    def test_chain_lightning_opens_along_the_aim(self):
        sink = []
        w = weapon("thunder_orb")
        w.update(1 / 60, fire_ctx([], sink, aim=held_keys((-1, 0))))
        self.assertAlmostEqual(bearing(sink[0].vel), 180.0)
        self.assertGreater(sink[0].chain_left, 0)                       # still chains after the hit

    def test_summons_ignore_the_aim(self):
        sink = []
        spawned = []
        w = weapon("spirit_wolf")
        ctx = fire_ctx([], sink, aim=held_click((1, 0)), auto_attack=False)
        ctx.spawn_summon = lambda **kw: (spawned.append(kw), FakeProj())[1]
        self.assertFalse(w.update(1 / 60, ctx))                         # never an "attack"
        self.assertEqual(len(spawned), 1)                               # ...but it still works
        self.assertEqual(sink, [])


class OrbitOnClickTests(unittest.TestCase):
    def orbiters(self, aim, enemies=()):
        sink = []
        w = weapon("ember_ring")
        w.update(1 / 60, fire_ctx(enemies, sink, aim=aim))
        return [o for o in sink if o.active], w

    def test_ring_forms_on_a_held_click_with_nothing_in_reach(self):
        live, w = self.orbiters(held_click((1, 0)))
        self.assertEqual(len(live), w._projectile_count())

    def test_ring_drops_when_the_click_is_released(self):
        sink = []
        w = weapon("ember_ring")
        w.update(1 / 60, fire_ctx([], sink, aim=held_click((1, 0))))
        w.update(1 / 60, fire_ctx([], sink, aim=AimInput.none()))
        self.assertFalse(any(o.active for o in sink))

    def test_a_held_aim_key_alone_does_not_raise_the_ring(self):
        live, _ = self.orbiters(held_keys((1, 0)))
        self.assertEqual(live, [])

    def test_a_tap_alone_does_not_raise_the_ring(self):
        live, _ = self.orbiters(tap((1, 0)))
        self.assertEqual(live, [])

    def test_an_enemy_in_reach_still_raises_it_without_any_aim(self):
        live, w = self.orbiters(None, enemies=[FakeEnemy(50, 0)])
        self.assertEqual(len(live), w._projectile_count())

    def test_auto_attack_off_does_not_lower_the_ring(self):
        # Orbit is not a "swing": the `Q` toggle leaves it alone.
        sink = []
        w = weapon("ember_ring")
        w.update(1 / 60, fire_ctx([FakeEnemy(50, 0)], sink, auto_attack=False))
        self.assertEqual(sum(o.active for o in sink), w._projectile_count())


class HoldKeepsFiringTests(unittest.TestCase):
    def _volleys(self, aim, seconds=2.0, auto_attack=True):
        sink = []
        w = weapon("arcane_bolt")
        fires = 0
        for _ in range(int(seconds * 60)):
            fires += w.update(1 / 60, fire_ctx([], sink, aim=aim, auto_attack=auto_attack))
        return fires, w

    def test_held_key_fires_once_per_cooldown(self):
        fires, w = self._volleys(held_keys((1, 0)))
        expected = int(2.0 / w._cooldown(1.0)) + 1          # first shot is instant
        self.assertEqual(fires, expected)

    def test_held_click_fires_at_the_same_cadence_with_auto_off(self):
        a, _ = self._volleys(held_click((0, 1)), auto_attack=False)
        b, _ = self._volleys(held_keys((0, 1)), auto_attack=True)
        self.assertEqual(a, b)
        self.assertGreater(a, 1)

    def test_a_tap_that_is_never_consumed_keeps_firing_until_it_is(self):
        # The weapon fires on every ready frame while the tap is pending; it is
        # the run (`_phase_combat`) that spends the tap after the first volley.
        # So a stale tap must be consumed -- pinned here so the contract stays
        # visible if the consumption ever moves.
        fires, _ = self._volleys(tap((1, 0)))
        self.assertGreater(fires, 1)


class TapConsumptionTests(unittest.TestCase):
    """Through the run: a queued click is one attack, spent on the frame a
    directional weapon fires from it, and it plays the attack animation even
    into empty space."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _fresh_playing()

    def setUp(self):
        ps = self.ps
        ps.auto_attack = False                      # isolate the tap
        ps.enemies.clear(); ps.boss = None          # nothing to auto-target
        ps._dev_no_attack = False
        for w in ps.player.weapons:
            w._cd = 0.0
        ps.player._attack_t = 0.0
        ps.consume_tap()

    def _combat_frame(self):
        before = len(self.ps.projectiles)
        self.ps._phase_combat(1 / 60)
        return len(self.ps.projectiles) - before

    def test_tap_fires_exactly_once_and_animates_the_whiff(self):
        ps = self.ps
        ps._tap_pending = True
        ps._aim = tap((0, -1))
        self.assertGreaterEqual(self._combat_frame(), 1)
        self.assertFalse(ps._tap_pending)                              # spent
        self.assertGreater(ps.player._attack_t, 0.0)                   # whiff animates
        ps._aim = AimInput.none()                                      # next frame, released
        for w in ps.player.weapons:
            w._cd = 0.0
        self.assertEqual(self._combat_frame(), 0)

    def test_tap_waits_out_the_cooldown_then_fires_once(self):
        ps = self.ps
        for w in ps.player.weapons:
            w._cd = 0.05
        ps._tap_pending = True
        ps._aim = tap((1, 0))
        self.assertEqual(self._combat_frame(), 0)                      # 1/60 < 0.05
        self.assertTrue(ps._tap_pending)                               # still queued
        for _ in range(4):
            self._combat_frame()
        self.assertFalse(ps._tap_pending)

    def test_no_aim_and_auto_off_never_fires(self):
        self.ps._aim = AimInput.none()
        for _ in range(10):
            self.assertEqual(self._combat_frame(), 0)
        self.assertEqual(self.ps.player._attack_t, 0.0)


class FullFrameTests(unittest.TestCase):
    """The whole pipeline: real pygame snapshots (mocked) into
    `PlayingState.update`, out the other end as projectiles -- the wiring
    from `_phase_input` through `_phase_combat` in one frame."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _fresh_playing()

    def setUp(self):
        ps = self.ps
        ps.auto_attack = True
        ps._dev_no_attack = False
        ps.consume_tap()
        ps.enemies.clear(); ps.boss = None
        ps.spawn.master.frozen = True             # no director spawns mid-test
        for w in ps.player.weapons:
            w._cd = 0.0
        self.game.set_key_layout(config.DEFAULT_KEY_LAYOUT)

    def _frame(self, pressed=None, left=False, mouse_pos=(0, 0), n=1):
        from unittest import mock
        before = len(self.ps.projectiles)
        with mock.patch.object(pygame.key, "get_pressed", return_value=pressed or keys()), \
             mock.patch.object(pygame.mouse, "get_pressed", return_value=mouse(left)), \
             mock.patch.object(pygame.mouse, "get_pos", return_value=mouse_pos):
            for _ in range(n):
                self.ps.update(1 / 60)
        return [p for p in self.ps.projectiles][before:]

    def _main_dir(self, shots):
        # A pooled `Projectile` carries no weapon id; the main weapon's tag
        # tuple identifies its shots. A cone (melee) shot aims by `cone_dir`.
        main = self.ps.player.weapons[0]
        mine = [p for p in shots if tuple(p.source_tags) == main.tags]
        self.assertTrue(mine, "the main weapon did not fire")
        p = mine[0]
        return p.cone_dir if p.cone_half_angle > 0.0 else p.vel

    def test_held_arrow_with_auto_off_attacks_that_way(self):
        self.ps.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
        self.assertFalse(self.ps.auto_attack)
        shots = self._frame(keys(pygame.K_UP))
        self.assertAlmostEqual(bearing(self._main_dir(shots)), -90.0, places=3)

    def test_auto_off_with_an_enemy_in_reach_stays_silent(self):
        self.ps.auto_attack = False
        e = self.ps.spawn.spawn_enemy("chaser", at=self.ps.player.pos + pygame.Vector2(60, 0),
                                      owner="dev")
        self.assertIsNotNone(e)
        shots = self._frame(n=30)
        self.assertEqual(shots, [])
        self.ps.enemies.clear()

    def test_held_arrow_beats_auto_aim_on_an_enemy(self):
        e = self.ps.spawn.spawn_enemy("chaser", at=self.ps.player.pos + pygame.Vector2(80, 0),
                                      owner="dev")
        self.assertIsNotNone(e)
        shots = self._frame(keys(pygame.K_LEFT))                # enemy right, aim left
        self.assertAlmostEqual(bearing(self._main_dir(shots)), 180.0, places=3)
        self.assertEqual(self.ps.player._facing, -1)
        self.ps.enemies.clear()

    def test_click_tap_fires_once_at_the_cursor(self):
        cam = self.ps.camera
        target = self.ps.player.pos + pygame.Vector2(-100, 0)
        self.ps.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                                pos=cam.world_to_screen(target)))
        shots = self._frame(mouse_pos=cam.world_to_screen(target))
        self.assertAlmostEqual(bearing(self._main_dir(shots)), 180.0, places=3)
        self.assertFalse(self.ps._tap_pending)
        for w in self.ps.player.weapons:
            w._cd = 0.0
        self.assertEqual(self._frame(mouse_pos=cam.world_to_screen(target)), [])

    def test_swapped_layout_aims_with_wasd(self):
        self.game.set_key_layout("arrows_move")
        self.ps.auto_attack = False
        shots = self._frame(keys(pygame.K_s))                   # S aims down now
        self.assertAlmostEqual(bearing(self._main_dir(shots)), 90.0, places=3)
        self.assertEqual(self.ps.player._move_dir.length_squared(), 0.0)
