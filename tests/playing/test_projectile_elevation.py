"""Shots respect elevation (LD-9 D10, reworked by CMB-010).

A plain shot keeps a floor that only rises. It travels over its own floor and
over anything lower, so firing *down* off a terrace works; terrain *above* it
stops it -- unless the shot got there the way a body walks, through a
staircase, which raises its floor. A bouncing shot moves like a walking body:
anything a body could not cross is a wall to it, up or down.

The interesting half of the plain rule is *where* an upward shot dies. A cliff
face has no walkable level, so a test against `LevelIndex.level_at_point`
would let the shot through the wall and only stop it on the plateau beyond,
reading as if it had passed through solid rock. `top_at_point` reports the
terrace a face holds up, which is what puts the impact on the face.

The climbing and bouncing sweeps run over every qualifying spot of one pinned
world rather than one hand-picked cell: each is structural, so a single
counter-example anywhere is a bug.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.projectile import Projectile
from game import config
from world.elevation import NONE
from world.layout import CLIFF, GROUND
from world.rules.steps import can_step
from tests import worlds as W

SEED = 21


class _Particles:
    def __init__(self):
        self.bursts = 0

    def burst(self, *a, **kw):
        self.bursts += 1


class _Map:
    """Just the two attributes `TransientFx` touches for this rule."""

    def __init__(self, levels):
        self._levels = levels


class _PS:
    def __init__(self, levels):
        self.game_map = _Map(levels)
        self.particles = _Particles()


def _fx(levels):
    from game.states.playing.core.effects import TransientFx
    return TransientFx(_PS(levels))


class _World(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.gm = W.game_map(SEED)
        cls.levels = cls.gm._levels


    def _world_of(self, col, row):
        ox, oy = self.levels.origin
        px = config.TILE_PX
        return pygame.Vector2(ox + col * px + px / 2, oy + row * px + px / 2)

    def _step(self, col, row, dr):
        """A column where the terrain height changes going `dr` rows: returns
        `(from_cell, to_cell)` tile coords, or None."""
        a = self.levels.top_at(col, row)
        b = self.levels.top_at(col, row + dr)
        if a == NONE or b == NONE or a == b:
            return None
        return (col, row), (col, row + dr)

    def _find(self, rising: bool):
        """A pair of adjacent tiles where the terrain rises (or falls) going
        north, both real terrain."""
        for row in range(1, self.levels.rows - 1):
            for col in range(self.levels.cols):
                pair = self._step(col, row, -1)
                if pair is None:
                    continue
                lo = self.levels.top_at(*pair[0])
                hi = self.levels.top_at(*pair[1])
                if (hi > lo) is rising:
                    return pair
        return None


class TerrainTopTests(_World):
    def test_a_cliff_face_reports_the_terrace_it_holds_up(self):
        """`level_at_point` cannot answer this -- a face is not walkable -- and
        it is the whole reason `top_at` exists."""
        px = config.TILE_PX
        checked = 0
        for room in self.gm.layout.rooms:
            if not room.grid:
                continue
            c0 = (int(room.rect.left) - self.levels.origin[0]) // px
            r0 = (int(room.rect.top) - self.levels.origin[1]) // px
            for (col, row), cell in room.grid.items():
                if cell.kind != CLIFF:
                    continue
                self.assertEqual(self.levels.top_at(c0 + col, r0 + row),
                                 cell.level)
                self.assertEqual(self.levels.level_at(c0 + col, r0 + row), NONE)
                checked += 1
        self.assertGreater(checked, 0, "no cliff in this world to check")

    def test_the_void_has_no_top(self):
        """Otherwise a shot could not cross the sea between two islands."""
        self.assertEqual(self.levels.top_at(-5, -5), NONE)


class BlockTests(_World):
    def _shoot(self, at, floor):
        p = Projectile()
        p.reset(pos=at, vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.active = True
        p.floor = floor
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        return p, fx.ps.particles.bursts

    def test_a_shot_dies_on_terrain_above_the_floor_it_left(self):
        pair = self._find(rising=True)
        self.assertIsNotNone(pair, "no rising step in this world")
        lo_t, hi_t = pair
        p, bursts = self._shoot(self._world_of(*hi_t),
                                self.levels.top_at(*lo_t))
        self.assertFalse(p.active, "the shot went through the cliff")
        self.assertEqual(bursts, 1, "no impact effect")

    def test_a_shot_crosses_terrain_at_or_below_its_own_floor(self):
        pair = self._find(rising=True)
        lo_t, hi_t = pair
        # fired from the high side, travelling down: the low tile must not stop it
        p, bursts = self._shoot(self._world_of(*lo_t),
                                self.levels.top_at(*hi_t))
        self.assertTrue(p.active, "firing down off a terrace was blocked")
        self.assertEqual(bursts, 0)

    def test_same_floor_is_never_blocked(self):
        pair = self._find(rising=True)
        lo_t, _hi = pair
        level = self.levels.top_at(*lo_t)
        p, _ = self._shoot(self._world_of(*lo_t), level)
        self.assertTrue(p.active)

    def test_open_sea_does_not_stop_anything(self):
        p, _ = self._shoot(pygame.Vector2(-9999, -9999), 0)
        self.assertTrue(p.active, "a shot died over open water")


class ExemptionTests(_World):
    def test_a_projectile_with_no_recorded_floor_is_left_alone(self):
        """`NONE` is what every unit test that builds a projectile by hand
        gets, so the rule has to be inert for them."""
        p = Projectile()
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.active = True
        self.assertEqual(p.floor, NONE)
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        self.assertTrue(p.active)

    def test_an_orbiter_is_exempt(self):
        """Ember Ring circles the player and is not travelling anywhere -- the
        same reason it skips the obstacle test."""
        pair = self._find(rising=True)
        lo_t, hi_t = pair
        p = Projectile()
        p.reset(pos=self._world_of(*hi_t), vel=(0, 0), damage=1, radius=4,
                lifetime=1, orbit_speed=2.0, anchor=pygame.Vector2())
        p.active = True
        p.floor = self.levels.top_at(*lo_t)
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        self.assertTrue(p.active)

    def test_reset_clears_the_recorded_floor(self):
        """The pool recycles projectiles; a stale level would judge the next
        shot against the last one's ground."""
        p = Projectile()
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.floor = 2
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        self.assertEqual(p.floor, NONE)


# --- CMB-010: climbing through stairs, bouncing like a body ----------------

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class _Terrain(_World):
    """Finders over the whole pinned world, and a `TransientFx` on the real
    map (the bouncing rule asks `GameMap.is_walkable`, which the bare
    `_Map` above does not have)."""

    def _real_fx(self):
        from game.states.playing.core.effects import TransientFx
        return TransientFx(SimpleNamespace(game_map=self.gm,
                                           particles=_Particles()))

    def _climbs(self):
        """Every straight line of tiles a body walks from low ground, onto a
        flight, and off it onto the terrace above: `(tiles, dir, low, upper)`.
        Built from `can_step`, so it is the walking graph's own answer."""
        ix = self.levels
        out = []
        for f, cell in ix._flight.items():
            upper = cell.level
            for d in _DIRS:
                g = (f[0] - d[0], f[1] - d[1])
                if (ix.kind_at(*g) != GROUND or ix.level_at(*g) >= upper
                        or not can_step(ix, g, f)):
                    continue
                path, cur = [g, f], f
                for _ in range(6):
                    nxt = (cur[0] + d[0], cur[1] + d[1])
                    if not can_step(ix, cur, nxt):
                        break
                    path.append(nxt)
                    cur = nxt
                    if ix.kind_at(*nxt) == GROUND and ix.level_at(*nxt) == upper:
                        out.append((path, d, ix.level_at(*g), upper))
                        break
        return out

    def _side_entries(self):
        """Low ground beside a flight, where a body may not step onto it: the
        flight's side, a wall even though both tiles are floor."""
        ix = self.levels
        out = []
        for f in ix._flight:
            for d in _DIRS:
                g = (f[0] - d[0], f[1] - d[1])
                if (ix.kind_at(*g) == GROUND and ix.top_at(*f) > ix.level_at(*g)
                        and not can_step(ix, g, f)):
                    out.append((g, f))
        return out

    def _flanks(self):
        """`(high, low)` ground tiles side by side at different levels: a
        plateau's flank or back edge, a level change with no stone in it."""
        ix = self.levels
        out = []
        for row in range(ix.rows):
            for col in range(ix.cols):
                if ix.kind_at(col, row) != GROUND:
                    continue
                for d in _DIRS:
                    n = (col + d[0], row + d[1])
                    if (ix.kind_at(*n) == GROUND
                            and ix.level_at(*n) < ix.level_at(col, row)):
                        out.append(((col, row), n))
        return out

    def _ball(self, at, vel, floor, bounces=5, radius=10.0, **kw):
        p = Projectile()
        p.reset(pos=at, vel=vel, damage=1, radius=radius, lifetime=9,
                bounces=bounces, **kw)
        p.active = True
        p.floor = floor
        return p

    def _plain(self, at, floor):
        p = Projectile()
        p.reset(pos=at, vel=(0, 0), damage=1, radius=4, lifetime=9)
        p.active = True
        p.floor = floor
        return p

    def _move(self, p, to, fx=None):
        """One frame's move to `to`, judged by the plain rule. Returns the
        burst count."""
        fx = fx or _fx(self.levels)
        before = pygame.Vector2(p.pos)
        p.pos.update(to)
        fx.block_on_terrain(p, before)
        return fx.ps.particles.bursts


class ClimbTests(_Terrain):
    """A plain shot reaches high ground through a staircase and nowhere
    else. Before CMB-010 every one of these died on the flight's first
    cell: a flight reports its *upper* surface, which stood above the floor
    the shot was fired from."""

    def test_the_world_has_staircases_to_climb(self):
        self.assertGreater(len(self._climbs()), 10)

    def test_a_shot_climbs_every_staircase_frame_by_frame(self):
        fx = _fx(self.levels)
        for path, d, low, upper in self._climbs():
            p = self._plain(self._world_of(*path[0]), low)
            end = self._world_of(*path[-1])
            step = pygame.Vector2(d) * 7.0              # ~420 px/s at 60 fps
            while p.active and (end - p.pos).dot(pygame.Vector2(d)) > 0:
                self._move(p, p.pos + step, fx)
            self.assertTrue(p.active, f"blocked climbing {path}")
            self.assertEqual(p.floor, upper, f"floor not raised on {path}")

    def test_a_fast_shot_climbs_a_whole_staircase_in_one_frame(self):
        """The move is walked every half tile, so a shot that covers the
        whole flight in one frame still takes every step of it."""
        for path, _d, low, upper in self._climbs():
            p = self._plain(self._world_of(*path[0]), low)
            self._move(p, self._world_of(*path[-1]))
            self.assertTrue(p.active, f"blocked climbing {path}")
            self.assertEqual(p.floor, upper)

    def test_the_side_of_a_flight_is_a_wall(self):
        entries = self._side_entries()
        self.assertGreater(len(entries), 0, "no flight side in this world")
        for g, f in entries:
            p = self._plain(self._world_of(*g), self.levels.level_at(*g))
            self._move(p, self._world_of(*f))
            self.assertFalse(p.active, f"went up the side of the flight at {f}")
            self.assertEqual(self.levels.tile_of(*p.pos), g,
                             "not stopped against the flight it hit")

    def test_a_plateau_flank_stops_a_shot_from_below(self):
        """A level change with no stone in it is still a wall going up: no
        staircase led the shot there."""
        flanks = self._flanks()
        self.assertGreater(len(flanks), 0)
        for hi, lo in flanks:
            p = self._plain(self._world_of(*lo), self.levels.level_at(*lo))
            self._move(p, self._world_of(*hi))
            self.assertFalse(p.active, f"climbed the flank {lo} -> {hi}")

    def test_a_fast_shot_cannot_tunnel_through_a_face(self):
        """Fired north at a cliff with a move long enough to reach the plateau
        beyond it in one frame. The shot must die *against the face*, the
        first tile standing above its floor, not wherever the frame ended."""
        ix = self.levels
        checked = 0
        for row in range(4, ix.rows):
            for col in range(ix.cols):
                lo, face = (col, row), (col, row - 1)
                if (ix.kind_at(*lo) != GROUND or ix.kind_at(*face)
                        or ix.top_at(*face) <= ix.level_at(*lo)):
                    continue
                p = self._plain(self._world_of(*lo), ix.level_at(*lo))
                bursts = self._move(p, self._world_of(col, row - 3))
                self.assertFalse(p.active)
                self.assertEqual(ix.tile_of(*p.pos), lo)
                face_edge = ix.origin[1] + row * ix.px     # the face's south edge
                self.assertLessEqual(p.pos.y - face_edge, 1.0, "not against the face")
                self.assertEqual(bursts, 1)
                checked += 1
        self.assertGreater(checked, 0, "no cliff face above low ground")

    def test_the_floor_never_drops(self):
        """Fired down off a terrace, the shot keeps its height over the low
        ground, so it still reaches another terrace of that height."""
        for hi, lo in self._flanks():
            level = self.levels.level_at(*hi)
            p = self._plain(self._world_of(*hi), level)
            self._move(p, self._world_of(*lo))
            self.assertTrue(p.active)
            self.assertEqual(p.floor, level)
            self._move(p, self._world_of(*hi))          # and back up, unstopped
            self.assertTrue(p.active, f"lost its floor over {lo}")

    def test_a_climbed_shot_is_judged_from_its_new_floor(self):
        """After a staircase the shot is on the upper floor for good: a flank
        up to that height, which stops a shot fired from below, no longer
        stops this one."""
        by_level = {}
        for hi, lo in self._flanks():
            by_level.setdefault((self.levels.level_at(*lo),
                                 self.levels.level_at(*hi)), (hi, lo))
        checked = 0
        for path, _d, low, upper in self._climbs():
            flank = by_level.get((low, upper))
            if flank is None:
                continue
            hi, lo = flank
            p = self._plain(self._world_of(*path[0]), low)
            self._move(p, self._world_of(*path[-1]))
            self.assertEqual(p.floor, upper)
            p.pos.update(self._world_of(*lo))           # out over the low ground
            self._move(p, self._world_of(*hi))
            self.assertTrue(p.active, "a climbed shot was stopped by its own floor")
            checked += 1
        self.assertGreater(checked, 0)


class BounceTests(_Terrain):
    """A bouncing shot moves like a walking body (CMB-010.D2)."""

    def test_a_ball_rolls_up_and_down_every_staircase(self):
        fx = self._real_fx()
        for path, _d, low, upper in self._climbs():
            for tiles, start_floor, end_floor in ((path, low, upper),
                                                  (path[::-1], upper, low)):
                a, b = self._world_of(*tiles[0]), self._world_of(*tiles[-1])
                heading = (b - a).normalize()
                p = self._ball(a, heading * 300, start_floor)
                for _ in range(int((b - a).length() / 6)):
                    before = pygame.Vector2(p.pos)
                    p.pos += heading * 6
                    fx.bounce(p, before)
                self.assertEqual(p.bounces_left, 5, f"bounced on the stairs {tiles}")
                self.assertEqual(p.floor, end_floor)

    def test_a_ball_bounces_off_a_drop_as_well_as_a_rise(self):
        """Regardless of height: a flank with no stone in it is a wall both
        ways. Before CMB-010 a pinball rolled straight off it downhill."""
        fx = self._real_fx()
        checked = 0
        for hi, lo in self._flanks():
            for frm, to in ((hi, lo), (lo, hi)):
                a, b = self._world_of(*frm), self._world_of(*to)
                if self.gm.blocking_obstacle_hit(b, 10.0) is not None:
                    continue        # an obstacle's own bounce; test_buffs covers it
                checked += 1
                v = (b - a).normalize() * 300
                p = self._ball(a, v, self.levels.level_at(*frm))
                p.pos.update(b)
                fx.bounce(p, a)
                self.assertEqual(p.bounces_left, 4, f"rolled {frm} -> {to}")
                self.assertEqual(p.pos, a, "not put back where it came from")
                # Back, or out sideways when a whole-tile move makes the way
                # back a wall too (the pocket rule); never on over the drop.
                self.assertLessEqual(p.vel.dot(v), 0, "still heading over the drop")
        self.assertGreater(checked, 100)

    def test_bouncing_is_the_shots_property_not_the_pinballs(self):
        """Any projectile given `bounces` gets the same rule: a sword shot,
        not styled or sourced as a pinball, bounces off the flank a pinball
        does."""
        fx = self._real_fx()
        hi, lo = next(f for f in self._flanks()
                      if self.gm.blocking_obstacle_hit(self._world_of(*f[1]), 4.0) is None)
        a, b = self._world_of(*hi), self._world_of(*lo)
        p = self._ball(a, (b - a).normalize() * 300, self.levels.level_at(*hi),
                       bounces=3, radius=4.0, weapon_id="sword")
        p.pos.update(b)
        fx.bounce(p, a)
        self.assertTrue(p.active)
        self.assertEqual(p.bounces_left, 2)
        self.assertEqual(p.style, "")

    def test_a_plain_shot_does_not_bounce(self):
        """Without `bounces` the same shot flies off the terrace, as every
        weapon's shot does by default."""
        hi, lo = self._flanks()[0]
        p = self._plain(self._world_of(*hi), self.levels.level_at(*hi))
        self.assertEqual(p.bounces_left, 0)
        self._move(p, self._world_of(*lo))
        self.assertTrue(p.active)
        self.assertEqual(p.pos, self._world_of(*lo))


class CriticTests(_Terrain):
    """The cases the CMB-010 critic pass broke the first version with."""

    def _reference(self, floor, start, end):
        """An independent walk of the same rule: sample the move every fifth
        of a pixel and judge each tile change on its own. Returns `(floor,
        tile the shot is stopped on)` -- the last tile before the wall -- or
        None when a sample changed row and column at once: a true corner,
        which only the traversal can resolve."""
        ix = self.levels
        cur = ix.tile_of(start.x, start.y)
        d = end - start
        n = max(1, int(d.length() * 5))
        for i in range(1, n + 1):
            p = start + d * (i / n)
            nxt = ix.tile_of(p.x, p.y)
            if nxt == cur:
                continue
            if nxt[0] != cur[0] and nxt[1] != cur[1]:
                return None
            top = ix.top_at(*nxt)
            if top != NONE and top > floor:
                if not can_step(ix, cur, nxt):
                    return floor, cur
                if ix.kind_at(*nxt) == GROUND:
                    floor = top
            cur = nxt
        return floor, None

    def test_the_walk_matches_an_exact_reference_near_every_staircase(self):
        """Short moves in every direction around the flights, where tile
        corners meet faces. A shot sampled every half tile used to clip
        through a face at a corner -- 99 in 20,000 at 7 px a frame."""
        import random
        from game.states.playing.core import shot_terrain
        rng = random.Random(10)
        ix = self.levels
        flights = sorted(ix._flight)
        compared = 0
        for _ in range(6000):
            c, r = rng.choice(flights)
            start = pygame.Vector2(
                ix.origin[0] + (c + rng.uniform(-1.5, 2.5)) * ix.px,
                ix.origin[1] + (r + rng.uniform(-1.5, 2.5)) * ix.px)
            floor = shot_terrain.muzzle_floor(ix, start)
            if floor == NONE:
                continue
            end = start + pygame.Vector2(rng.uniform(4, 60), 0).rotate(rng.uniform(0, 360))
            want = self._reference(floor, start, end)
            if want is None:
                continue
            got_floor, wall = shot_terrain.travel(ix, floor, start, end)
            got = (got_floor, None if wall is None else ix.tile_of(wall.x, wall.y))
            self.assertEqual(got, want, f"{tuple(start)} -> {tuple(end)} on {floor}")
            compared += 1
        self.assertGreater(compared, 4000)

    def test_a_shot_cannot_leave_a_flight_through_its_side(self):
        """A flight reports its upper terrace as its height, but a shot on it
        is still climbing: turning off the stairs into the face beside them is
        a wall, as it is for a body."""
        ix = self.levels
        checked = 0
        for path, d, low, _upper in self._climbs():
            f = path[1]
            for side in ((d[1], d[0]), (-d[1], -d[0])):
                s = (f[0] + side[0], f[1] + side[1])
                if ix.top_at(*s) <= low or can_step(ix, f, s):
                    continue
                p = self._plain(self._world_of(*path[0]), low)
                self._move(p, self._world_of(*f))
                self.assertTrue(p.active)
                self._move(p, self._world_of(*s))
                self.assertFalse(p.active, f"left the flight {f} into {s}")
                checked += 1
        self.assertGreater(checked, 10)

    def test_a_shot_fired_from_a_flight_leaves_from_its_low_end(self):
        from game.states.playing.core import shot_terrain
        ix = self.levels
        checked = 0
        for f, cell in ix._flight.items():
            low = cell.level - cell.drop
            self.assertEqual(shot_terrain.muzzle_floor(ix, self._world_of(*f)), low)
            for d in _DIRS:
                s = (f[0] + d[0], f[1] + d[1])
                if ix.top_at(*s) <= low or can_step(ix, f, s):
                    continue
                p = self._plain(self._world_of(*f),
                                shot_terrain.muzzle_floor(ix, self._world_of(*f)))
                self._move(p, self._world_of(*s))
                self.assertFalse(p.active, f"fired from {f} through {s}")
                checked += 1
        self.assertGreater(checked, 10)

    def test_an_obstacle_never_seats_a_ball_where_a_body_could_not_go(self):
        """Reflected off a rock, a ball is seated just outside it; a rock on
        a terrace rim used to seat it a level up or down."""
        from game.states.playing.core import shot_terrain
        fx = self._real_fx()
        gm = self.gm
        checked = 0
        for rock in gm.obstacles:
            if not rock.blocks_projectiles:
                continue
            for k in range(16):
                out = pygame.Vector2(1, 0).rotate(22.5 * k)
                before = rock.pos + out * (rock.radius + 10 + 6)
                if not gm.is_walkable(before, 10.0):
                    continue
                p = self._ball(pygame.Vector2(before), -out * 300,
                               self.levels.top_at_point(before.x, before.y))
                p.pos.update(rock.pos + out * (rock.radius + 10 - 3))
                fx.bounce(p, before)
                self.assertTrue(p.pos == before
                                or not shot_terrain.body_blocks(gm, p.pos, 10.0, before),
                                f"seated off {tuple(rock.pos)} at {tuple(p.pos)}")
                checked += 1
        self.assertGreater(checked, 100)

    def test_orbiters_and_no_block_shots_never_bounce(self):
        """Exempt from every wall, bouncing or not."""
        fx = self._real_fx()
        hi, lo = next(f for f in self._flanks()
                      if self.gm.blocking_obstacle_hit(self._world_of(*f[1]), 4.0) is None)
        a, b = self._world_of(*hi), self._world_of(*lo)
        for kw in ({"no_block": True},
                   {"orbit_speed": 2.0, "anchor": pygame.Vector2()}):
            p = self._ball(a, (b - a) * 5, self.levels.level_at(*hi), bounces=3,
                           radius=4.0, **kw)
            p.pos.update(b)
            fx.bounce(p, a)
            self.assertEqual(p.bounces_left, 3, kw)
            self.assertEqual(p.pos, b, kw)


def _exact_crossings(px, origin, sx, sy, ex, ey):
    """The reference grid walk, in exact rational arithmetic: every boundary
    event, simultaneous ones merged into one (diagonal) step. Tiles follow
    `LevelIndex.tile_of` -- floor division -- so a move ending exactly on a
    boundary going the negative way does not enter the next tile."""
    import math
    from fractions import Fraction as F
    ox, oy = origin
    x0, y0 = (F(sx) - ox) / px, (F(sy) - oy) / px
    x1, y1 = (F(ex) - ox) / px, (F(ey) - oy) / px
    col, row = math.floor(x0), math.floor(y0)
    col1, row1 = math.floor(x1), math.floor(y1)
    events = []
    if x1 > x0:
        events += [((k - x0) / (x1 - x0), 1, 0) for k in range(col + 1, col1 + 1)]
    elif x1 < x0:
        events += [((x0 - k) / (x0 - x1), -1, 0) for k in range(col, col1, -1)]
    if y1 > y0:
        events += [((k - y0) / (y1 - y0), 0, 1) for k in range(row + 1, row1 + 1)]
    elif y1 < y0:
        events += [((y0 - k) / (y0 - y1), 0, -1) for k in range(row, row1, -1)]
    events.sort()
    out, i = [], 0
    while i < len(events):
        t = events[i][0]
        while i < len(events) and events[i][0] == t:
            col += events[i][1]
            row += events[i][2]
            i += 1
        out.append((col, row))
    return out


class TraversalTests(_Terrain):
    """The grid walk both rules stand on, against an exact reference."""

    def test_it_matches_exact_arithmetic_on_and_off_the_grid_lines(self):
        """Grid lines, tile corners, eighth-pixel positions, negative
        coordinates and exact diagonals -- the cases float error and a
        negative-direction end on a boundary used to get wrong (the walk ran
        on up to seven tiles past its end)."""
        import random
        from game.states.playing.core import shot_terrain
        ix = self.levels
        rng = random.Random(1)

        def coord():
            m = rng.random()
            if m < 0.3:
                return float(rng.randint(-5, 40) * ix.px)
            if m < 0.5:
                return rng.randint(-5 * 512, 40 * 512) / 8.0
            return rng.uniform(-300, 2600)

        compared = 0
        for _ in range(20000):
            sx, sy = coord(), coord()
            if rng.random() < 0.3:                  # exactly along a diagonal
                k = rng.choice((0.5, 1, 1.25, 3))
                sgx, sgy = rng.choice((1, -1)), rng.choice((1, -1))
                ex, ey = sx + sgx * ix.px * k, sy + sgy * ix.px * k
            else:
                ex, ey = sx + rng.uniform(-700, 700), sy + rng.uniform(-700, 700)
            start, end = pygame.Vector2(sx, sy), pygame.Vector2(ex, ey)
            got = [tile for tile, _t in shot_terrain._crossings(ix, start, end)]
            want = _exact_crossings(ix.px, ix.origin, sx, sy, ex, ey)
            self.assertEqual(got, want, f"{(sx, sy)} -> {(ex, ey)}")
            if want:
                self.assertEqual(got[-1], ix.tile_of(ex, ey))
            compared += 1
        self.assertEqual(compared, 20000)

    def test_a_blocked_shot_is_seated_against_the_wall_that_stopped_it(self):
        """On the last tile it was legally on, touching the tile that refused
        it. Never across a corner: the seat is what a bomb's blast and its
        bomblets are thrown from, and a seat on the plateau beside the face
        let them climb it (6 in 5620 blocks, uniformly aimed). Never inside
        the wall either: bomblets thrown from there all died on their first
        frame, even the ones thrown back onto the low ground."""
        import random
        from game.states.playing.core import shot_terrain
        ix = self.levels
        rng = random.Random(3)
        flights = sorted(ix._flight)
        blocked = 0
        for _ in range(8000):
            c, r = rng.choice(flights)
            start = pygame.Vector2(
                ix.origin[0] + (c + rng.uniform(-3, 4)) * ix.px,
                ix.origin[1] + (r + rng.uniform(-3, 4)) * ix.px)
            floor = shot_terrain.muzzle_floor(ix, start)
            if floor == NONE:
                continue
            end = start + pygame.Vector2(rng.uniform(2, 90), 0).rotate(rng.uniform(0, 360))
            _floor, wall = shot_terrain.travel(ix, floor, start, end)
            if wall is None:
                continue
            # the tile the walk refused: the first step up with no stone in it
            cur, level, refused = ix.tile_of(start.x, start.y), floor, None
            for t in _exact_crossings(ix.px, ix.origin, start.x, start.y, end.x, end.y):
                top = ix.top_at(*t)
                if top != NONE and top > level:
                    if not can_step(ix, cur, t):
                        refused = t
                        break
                    if ix.kind_at(*t) == GROUND:
                        level = top
                cur = t
            self.assertEqual(ix.tile_of(wall.x, wall.y), cur)
            left = ix.origin[0] + refused[0] * ix.px
            top = ix.origin[1] + refused[1] * ix.px
            gap_x = max(left - wall.x, wall.x - (left + ix.px), 0.0)
            gap_y = max(top - wall.y, wall.y - (top + ix.px), 0.0)
            self.assertLessEqual(max(gap_x, gap_y), 0.5 + 1e-6, "not against the wall")
            blocked += 1
        self.assertGreater(blocked, 300)

    def test_a_shot_standing_above_its_floor_stops_even_as_it_moves_on(self):
        """The start tile is judged on every move, not only when the shot
        stays inside it: something put there without climbing (a spawn, a
        sticky bomb carried across a flank) must not walk on up the plateau."""
        from game.states.playing.core import shot_terrain
        hi, lo = self._flanks()[0]
        level = self.levels.level_at(*lo)
        start = self._world_of(*hi)
        for to in (start, start + pygame.Vector2(5, 0), self._world_of(*lo)):
            _floor, wall = shot_terrain.travel(self.levels, level, start, to)
            self.assertIsNotNone(wall, f"moved on from {hi} to {tuple(to)}")


class BounceRuleTests(_Terrain):
    """Round-two critic cases for bouncing shots."""

    def test_a_ball_never_clips_a_corner_at_any_frame_rate(self):
        """Every tile boundary a ball crosses is a step a body may take, at
        60 fps and at the 20 fps floor alike (`path_ok`'s half-tile samples
        let 11 to 18 in 17,500 moves through at 20 fps)."""
        import math
        import random
        ix = self.levels
        fx = self._real_fx()
        rng = random.Random(4)
        tiles = [(c + dc, r + dr) for (c, r) in ix._flight
                 for dc in range(-3, 4) for dr in range(-3, 4) if ix.kind_at(c + dc, r + dr)]
        moves = 0
        for dt in (1 / 60, 1 / 20):
            for _ in range(150):
                c, r = rng.choice(tiles)
                s = pygame.Vector2(ix.origin[0] + (c + rng.random()) * ix.px,
                                   ix.origin[1] + (r + rng.random()) * ix.px)
                if not self.gm.is_walkable(s, 10.0):
                    continue
                a = rng.uniform(0, math.tau)
                p = self._ball(s, pygame.Vector2(math.cos(a), math.sin(a)) * 260,
                               ix.top_at_point(s.x, s.y), bounces=10)
                for _ in range(int(2.0 / dt)):
                    if not p.active:
                        break
                    before = pygame.Vector2(p.pos)
                    p.update(dt)
                    fx.bounce(p, before)
                    cur = ix.tile_of(before.x, before.y)
                    for nxt in _exact_crossings(ix.px, ix.origin, before.x, before.y,
                                                p.pos.x, p.pos.y):
                        self.assertTrue(can_step(ix, cur, nxt),
                                        f"clipped {cur} -> {nxt} at dt {dt}")
                        cur = nxt
                        moves += 1
        self.assertGreater(moves, 1000)

    def test_a_ball_fired_over_the_sea_does_not_spend_its_bounces(self):
        """No ground under it, so no terrain to reflect off: it flies on (the
        bouncing counterpart of `floor == NONE`)."""
        from tests.entities.ai.test_flying import _open_sea
        fx = self._real_fx()
        sea = pygame.Vector2(_open_sea(self.gm))
        p = self._ball(sea, (300, 0), NONE)
        for _ in range(8):
            before = pygame.Vector2(p.pos)
            p.update(1 / 60)
            fx.roll(p, before)
        self.assertTrue(p.active)
        self.assertEqual(p.bounces_left, 5)
        self.assertGreater(p.pos.x, sea.x + 30)


class _PocketMap:
    """A wall along x = 0 and one rock: a pocket narrower than a frame's
    move once the ball is between them."""

    _levels = None

    def __init__(self):
        self.rock = SimpleNamespace(pos=pygame.Vector2(30, 50), radius=10.0,
                                    blocks_projectiles=True)

    def is_open_water(self, x, y):
        return False

    def on_floor(self, pos, radius=0.0, frm=None):
        return pos.x - radius >= 0

    def blocking_obstacle_hit(self, pos, radius):
        rr = self.rock.radius + radius
        return self.rock if (pos - self.rock.pos).length_squared() < rr * rr else None

    def is_walkable(self, pos, radius=0.0, frm=None, flying=False, path=True,
                    obstacles=True):
        if flying:
            return True
        return pos.x - radius >= 0 and (
            not obstacles or self.blocking_obstacle_hit(pos, radius) is None)


class PocketTests(unittest.TestCase):
    def _run(self, fps, vel):
        from game.states.playing.core.effects import TransientFx
        fx = TransientFx(SimpleNamespace(game_map=_PocketMap(), particles=_Particles()))
        p = Projectile()
        p.reset(pos=(12, 50), vel=vel, damage=1, radius=5, lifetime=9, bounces=10)
        p.active = True
        for _ in range(int(1.0 * fps)):
            before = pygame.Vector2(p.pos)
            p.update(1 / fps)
            fx.roll(p, before)
        return p

    def test_a_ball_between_a_rock_and_a_wall_bounces_its_way_out(self):
        """Stepping a whole frame put a blocked ball back where the frame
        began; between a rock and a wall closer than that it reflected off
        each in turn from the same spot until every bounce was spent. In
        sub-steps it meets each wall where it touches it, and a slanting
        throw works its way out of the gap."""
        for fps in (20, 30, 62, 144):
            p = self._run(fps, (600, 150))
            self.assertTrue(p.active, f"spent in the pocket at {fps} fps")
            self.assertGreater(abs(p.pos.y - 50), 60, f"still in the pocket at {fps} fps")

    def test_the_same_throw_bounces_the_same_at_any_frame_rate(self):
        """Sub-steps of at most `_SUBSTEP_PX` take the outcome out of the
        frame rate's hands: at 20 and at 144 fps the ball gets out of the
        pocket having spent the same bounces, give or take the one a
        sub-step's placement decides at a corner. Stepping whole frames, the
        20 fps ball spent every bounce on the spot."""
        a, b = self._run(20, (600, 150)), self._run(144, (600, 150))
        self.assertLessEqual(abs(a.bounces_left - b.bounces_left), 1)
        for p in (a, b):
            self.assertGreater(abs(p.pos.y - 50), 60)


class OffFloorTests(_Terrain):
    """Round-three critic cases: a bouncing shot that starts off the floor,
    and what a blocked shot leaves behind."""

    def _shores(self):
        """`(ground, sea)` tiles side by side: where a ball comes ashore."""
        ix = self.levels
        out = []
        for row in range(ix.rows):
            for col in range(ix.cols):
                if ix.kind_at(col, row) != GROUND:
                    continue
                for d in _DIRS:
                    n = (col + d[0], row + d[1])
                    if ix.top_at(*n) == NONE:
                        out.append(((col, row), n))
        return out

    def _fly(self, p, fx, dt, seconds):
        """Run the ball; return the most bounces it spent within 3 px."""
        worst, spot, spent = 0, None, 0
        for _ in range(int(seconds / dt)):
            if not p.active:
                break
            before = pygame.Vector2(p.pos)
            left = p.bounces_left
            p.update(dt)
            fx.roll(p, before)
            if p.bounces_left < left:
                if spot is not None and (p.pos - spot).length() < 3.0:
                    spent += 1
                else:
                    spot, spent = pygame.Vector2(p.pos), 1
                worst = max(worst, spent)
        return worst

    def test_a_ball_coming_ashore_is_never_pinned_at_the_waterline(self):
        """Its centre reached floor with its radius still over the water:
        every way on failed the probes and every way back the floor, and it
        spent all ten bounces on one spot (about 250 in 300 at 60 fps)."""
        import random
        rng = random.Random(8)
        fx = self._real_fx()
        shores = self._shores()
        self.assertGreater(len(shores), 50)
        for dt in (1 / 60, 1 / 20):
            for _ in range(120):
                ground, sea = rng.choice(shores)
                a, b = self._world_of(*sea), self._world_of(*ground)
                heading = (b - a).normalize().rotate(rng.uniform(-35, 35))
                p = self._ball(a - heading * 20, heading * 260, NONE, bounces=10)
                # A tight corner costs a real ball two or three quick
                # bounces; pinned is five or more on one spot.
                self.assertLess(self._fly(p, fx, dt, 2.0), 5,
                                f"pinned coming ashore at {ground}, dt {dt}")

    def test_a_ball_launched_from_a_face_comes_down_only_on_its_own_floor(self):
        """A flyer over a cliff face or a lake fires with that terrace's
        floor. It flies until it is over ground, and lands only on ground of
        that level: before, it dropped off the face onto the low ground below
        (134 of 295 launches on this world)."""
        from game.states.playing.core import shot_terrain
        ix = self.levels
        fx = self._real_fx()
        launches = landed = 0
        for row in range(ix.rows):
            for col in range(ix.cols):
                if ix.kind_at(col, row) or ix.top_at(col, row) == NONE:
                    continue                    # a face or a lake: terrain, not floor
                at = self._world_of(col, row)
                floor = shot_terrain.muzzle_floor(ix, at)
                for d in _DIRS:
                    p = self._ball(at, pygame.Vector2(d) * 300, floor, bounces=10)
                    launches += 1
                    for _ in range(40):
                        before = pygame.Vector2(p.pos)
                        p.update(1 / 60)
                        fx.roll(p, before)
                        if shot_terrain.on_ground(self.gm, p.pos, p.radius):
                            here = shot_terrain.standing_level(
                                ix, *ix.tile_of(p.pos.x, p.pos.y))
                            self.assertEqual(here, floor,
                                             f"came down off its floor from {(col, row)}")
                            landed += 1
                            break
        self.assertGreater(launches, 200)
        self.assertGreater(landed, 50)

    def test_a_shot_thrown_back_from_a_blocked_seat_flies(self):
        """A cluster bomb stopped on a face scatters its bomblets from the
        seat on its own floor. The ones thrown back over the low ground fly;
        the ones thrown at the face are stopped by it."""
        from game.states.playing.core import shot_terrain
        ix = self.levels
        checked = 0
        for row in range(4, ix.rows):
            for col in range(ix.cols):
                lo, face = (col, row), (col, row - 1)
                if (ix.kind_at(*lo) != GROUND or ix.kind_at(*face)
                        or ix.top_at(*face) <= ix.level_at(*lo)
                        or ix.kind_at(col, row + 1) != GROUND
                        or ix.level_at(col, row + 1) != ix.level_at(*lo)):
                    continue
                floor = ix.level_at(*lo)
                start = self._world_of(*lo)
                _f, seat = shot_terrain.travel(ix, floor, start, start + pygame.Vector2(0, -100))
                self.assertIsNotNone(seat)
                _f, back = shot_terrain.travel(ix, floor, seat, seat + pygame.Vector2(0, 40))
                self.assertIsNone(back, f"a bomblet thrown back from {lo} died")
                _f, on = shot_terrain.travel(ix, floor, seat, seat + pygame.Vector2(0, -40))
                self.assertIsNotNone(on, f"a bomblet went through the face at {face}")
                checked += 1
        self.assertGreater(checked, 50)


class GroundAndFlightTests(_Terrain):
    """Round-four critic cases: staying on the ground, and flying true."""

    def _bridge_points(self, rng, n):
        gm = self.gm
        out = []
        for c in gm.layout.corridors:
            r = c.rect
            for _ in range(n):
                p = pygame.Vector2(rng.uniform(r.left, r.right), rng.uniform(r.top, r.bottom))
                if gm.on_bridge(p.x, p.y) and gm.is_walkable(p, 10.0):
                    out.append(p)
        return out

    def test_a_ball_on_a_bridge_never_leaves_it_over_the_water(self):
        """The bridge leniency lets a body stand at a mouth with its radius
        over the water. A ball there used to lose its ground, switch to the
        flight rules and sail off over the sea (71 of 2160). Once on the
        ground it stays on it."""
        import math
        import random
        rng = random.Random(12)
        fx = self._real_fx()
        points = self._bridge_points(rng, 6)
        self.assertGreater(len(points), 20)
        for at in points:
            for _ in range(3):
                a = rng.uniform(0, math.tau)
                p = self._ball(pygame.Vector2(at), pygame.Vector2(math.cos(a), math.sin(a)) * 260,
                               self.levels.top_at_point(at.x, at.y), bounces=10)
                for _ in range(180):
                    if not p.active:
                        break
                    before = pygame.Vector2(p.pos)
                    p.update(1 / 60)
                    fx.roll(p, before)
                    self.assertTrue(p.landed)
                    self.assertFalse(self.gm.is_open_water(p.pos.x, p.pos.y),
                                     f"out over the water from {tuple(at)}")

    def test_a_ball_thrown_from_where_a_body_stands_is_on_the_ground(self):
        """Wherever the hero may stand -- a bridge mouth included, radius over
        the water -- the ball starts on the ground, not in flight."""
        fx = self._real_fx()
        for c in self.gm.layout.corridors:
            r = c.rect
            for mouth in (pygame.Vector2(r.left - 6, r.centery),
                          pygame.Vector2(r.right + 6, r.centery),
                          pygame.Vector2(r.centerx, r.top - 6),
                          pygame.Vector2(r.centerx, r.bottom + 6)):
                if self.gm.is_open_water(mouth.x, mouth.y):
                    continue
                p = self._ball(mouth, (0, 1), self.levels.top_at_point(mouth.x, mouth.y))
                before = pygame.Vector2(p.pos)
                p.update(1 / 60)
                fx.bounce(p, before)
                self.assertTrue(p.landed, f"in flight at a mouth {tuple(mouth)}")

    def test_a_move_in_flight_is_judged_along_its_path(self):
        """Every point of a move that `lands_off_floor` clears is clear on its
        own: a move cutting the corner of other-level ground is walled even
        when both its ends are over a face (64 in 54,511 13 px moves slipped
        through when only the end was judged)."""
        import random
        from game.states.playing.core import shot_terrain
        ix = self.levels
        rng = random.Random(6)
        off = [(c, r) for r in range(ix.rows) for c in range(ix.cols)
               if not ix.kind_at(c, r) and ix.top_at(c, r) != NONE]
        cleared = 0
        for _ in range(6000):
            c, r = rng.choice(off)
            a = self._world_of(c, r) + pygame.Vector2(rng.uniform(-32, 32), rng.uniform(-32, 32))
            floor = shot_terrain.muzzle_floor(ix, a)
            b = a + pygame.Vector2(rng.choice((13.0, 45.0)), 0).rotate(rng.uniform(0, 360))
            if shot_terrain.lands_off_floor(self.gm, a, b, floor):
                continue
            cleared += 1
            for k in range(1, 33):
                q = a + (b - a) * (k / 32)
                self.assertFalse(shot_terrain.lands_off_floor(self.gm, q, q, floor),
                                 f"{tuple(a)} -> {tuple(b)} passes {tuple(q)}")
        self.assertGreater(cleared, 1000)

    def test_a_rock_never_seats_a_ball_in_flight_on_another_floor(self):
        """Reflected off a rock while in flight, the ball is seated by the
        same wall test as its moves (1 in 364 came down a level lower)."""
        from game.states.playing.core import shot_terrain
        ix = self.levels
        gm = self.gm
        fx = self._real_fx()
        checked = 0
        for rock in gm.obstacles:
            if not rock.blocks_projectiles:
                continue
            for k in range(48):
                out = pygame.Vector2(1, 0).rotate(7.5 * k)
                for dist in (2.0, 6.0, 14.0, 24.0):
                    before = rock.pos + out * (rock.radius + 10 + dist)
                    if not gm.is_open_water(before.x, before.y):
                        continue                    # a ball in flight starts off the floor
                    floor = shot_terrain.muzzle_floor(ix, before)
                    if floor == NONE:
                        continue
                    for turn in (-50, -25, 0, 25, 50):
                        heading = (-out).rotate(turn)
                        p = self._ball(pygame.Vector2(before), heading * 300, floor)
                        p.landed = False
                        p.pos.update(before + heading * (dist + 3))
                        if gm.blocking_obstacle_hit(p.pos, 10.0) is None:
                            continue
                        fx.bounce(p, before)
                        self.assertFalse(
                            shot_terrain.lands_off_floor(gm, p.pos, p.pos, floor),
                            f"seated on another floor off {tuple(rock.pos)}")
                        checked += 1
        self.assertGreater(checked, 500)


class _CorridorMap(_PocketMap):
    """Walls at x = 0 and x = 50: a corridor running north-south, wider than
    the pocket distance but narrower than a fast ball's move at the 20 fps
    floor."""

    def __init__(self):
        super().__init__()
        self.rock = SimpleNamespace(pos=pygame.Vector2(-999, -999), radius=1.0,
                                    blocks_projectiles=True)

    def on_floor(self, pos, radius=0.0, frm=None):
        return pos.x - radius >= 0 and pos.x + radius <= 50

    def is_walkable(self, pos, radius=0.0, frm=None, flying=False, path=True,
                    obstacles=True):
        return flying or self.on_floor(pos, radius)


class FastPocketTests(unittest.TestCase):
    def test_a_fast_ball_runs_down_a_corridor_narrower_than_its_move(self):
        """At 900 px/s and 20 fps a ball moves 45 px a frame. Across a 50 px
        corridor it used to hit a wall every frame, be put back where the
        frame began and cross again, never getting anywhere. In sub-steps it
        crosses and re-crosses the corridor like a real ball, and makes its
        way down it at its own speed along it."""
        from game.states.playing.core.effects import TransientFx
        fx = TransientFx(SimpleNamespace(game_map=_CorridorMap(), particles=_Particles()))
        p = Projectile()
        p.reset(pos=(25, 0), vel=pygame.Vector2(880, 190), damage=1, radius=5,
                lifetime=9, bounces=50)
        p.active = True
        t = 0.0
        while p.active and t < 1.0:
            before = pygame.Vector2(p.pos)
            p.update(1 / 20)
            fx.roll(p, before)
            t += 1 / 20
        self.assertGreater(abs(p.pos.y), 0.8 * 190 * t, "held on the spot")
        self.assertGreater(p.bounces_left, 20, "more bounces than walls met")


class FrameLoopTests(_Terrain):
    """Round-five critic cases, through `update_projectiles` itself."""

    def _loop_fx(self):
        from game.states.playing.core.effects import TransientFx
        from systems.object_pool import Pool
        run = SimpleNamespace(game_map=self.gm, particles=_Particles(),
                              projectiles=Pool(Projectile, 64),
                              hostiles=Pool(Projectile, 64),
                              _in_world_margin=lambda pos, m: True,
                              _trail_fx=[])
        return TransientFx(run), run

    def test_a_shot_stops_against_a_face_before_a_rock_beyond_it(self):
        """A move that crosses a cliff face and ends inside a rock on the
        plateau beyond was killed by the rock, on the plateau, before the
        terrain walk ran (186 in 47,372 stopped shots at 62 fps). Terrain is
        judged first, so it stops against the face on its own floor."""
        from game.states.playing.core import shot_terrain
        ix = self.levels
        fx, run = self._loop_fx()
        checked = 0
        for rock in self.gm.obstacles:
            if not rock.blocks_projectiles:
                continue
            rt = ix.tile_of(rock.pos.x, rock.pos.y)
            for d in _DIRS:
                face = (rt[0] - d[0], rt[1] - d[1])
                lo = (rt[0] - 2 * d[0], rt[1] - 2 * d[1])
                if (ix.kind_at(*lo) != GROUND or ix.kind_at(*face)
                        or ix.top_at(*face) <= ix.level_at(*lo)):
                    continue
                for pool, hostile in ((run.projectiles, False), (run.hostiles, True)):
                    p = pool.acquire()
                    start = self._world_of(*lo)
                    p.reset(pos=start, vel=(rock.pos - start) * 60, damage=1,
                            radius=4, lifetime=1, hostile=hostile)
                    p.floor = ix.level_at(*lo)
                    fx.update_projectiles(1 / 60)   # one frame lands it in the rock
                    self.assertFalse(p.active)
                    self.assertNotEqual(ix.tile_of(p.pos.x, p.pos.y), rt,
                                        "died in the rock past the face")
                    level = shot_terrain.standing_level(ix, *ix.tile_of(p.pos.x, p.pos.y))
                    self.assertLessEqual(level, ix.level_at(*lo), "died on the plateau")
                    pool.sweep()
                    checked += 1
        self.assertGreater(checked, 5)

    def test_a_ball_ignores_props_that_do_not_block_shots(self):
        """A plain shot flies through a bush or a scarecrow; so does a
        bouncing one. A ball that came down on one used to find every move
        refused by the body's obstacle test and spend all its bounces there
        (78 of 114 landings on a prop)."""
        from game.states.playing.core import shot_terrain
        props = [o for o in self.gm.obstacles if not o.blocks_projectiles]
        self.assertGreater(len(props), 10)
        checked = 0
        for o in props:
            for k in range(8):
                frm = o.pos + pygame.Vector2(o.radius + 12, 0).rotate(45 * k)
                if not self.gm.is_walkable(frm, 10.0, obstacles=False):
                    continue
                to = frm + (o.pos - frm).normalize() * 4
                self.assertFalse(shot_terrain.body_blocks(self.gm, to, 10.0, frm),
                                 f"a prop at {tuple(o.pos)} walled the ball")
                checked += 1
        self.assertGreater(checked, 20)

    def test_a_ball_overhanging_the_water_may_roll_away_from_it(self):
        """Centre on floor, radius over the water -- a shooter smaller than
        its shot at a shoreline. Every move used to be refused by the radius
        probes and the ball spent its bounces there (489 of 491 shore spots).
        It may now roll on its centre until it is clear of the edge.

        Measured as a rate: a few spots squeeze the ball between a rock and
        the waterline, a gap its body cannot pass, and there it still spends
        its bounces (3 to 6 in 200 to 250 spots per world, every one beside a
        rock). No shooter stands there today: the hero is wider than the
        pinball, and no enemy fires a bouncing shot."""
        import random
        from game.states.playing.core import shot_terrain
        ix = self.levels
        gm = self.gm
        rng = random.Random(14)
        fx = self._real_fx()
        spots = spent = 0
        for _ in range(20000):
            c, r = rng.randrange(ix.cols), rng.randrange(ix.rows)
            at = self._world_of(c, r) + pygame.Vector2(rng.uniform(-32, 32), rng.uniform(-32, 32))
            if gm.is_open_water(at.x, at.y) or gm.on_floor(at, 10.0):
                continue
            spots += 1
            p = self._ball(at, pygame.Vector2(260, 0).rotate(rng.uniform(0, 360)),
                           shot_terrain.muzzle_floor(ix, at), bounces=10)
            for _ in range(62):
                if not p.active:
                    break
                before = pygame.Vector2(p.pos)
                p.update(1 / 62)
                fx.roll(p, before)
            spent += not p.active
            if spots >= 150:
                break
        self.assertGreater(spots, 50)
        self.assertLessEqual(spent / spots, 0.05,
                             f"{spent} of {spots} overhanging balls spent every bounce")


if __name__ == "__main__":
    unittest.main()
