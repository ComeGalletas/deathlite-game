"""RND-008.5: the faster bump pass gives exactly the old one's result
(`frame_time_journal.md`).

`BumpResolver.resolve` now drops a pair that does not touch before any
tuple, set or vector, and pads its broad phase by the largest collider
present (never more than the old 72 px). It must still shove every pair the
old pass shoved, in the same order and the same way round: the knockbacks
are summed as floats, and a float sum depends on its order, so "close" would
be another game.

The oracle is the old pass, copied here verbatim from before RND-008.5.
Pinned, bit for bit (every `_knock` compared with `==`, and every
frozen-contact exchange in order):

* random crowds, many of them, with radii from 9 to 26, a 46 px boss, a
  collider bigger than the old pad, bodies stacked exactly on top of each
  other and pairs exactly touching, with and without bodies killed by a
  frozen contact in the middle of the pass;
* the pad's edge cases, built on purpose: a giant across a cell edge, and a
  pair on the one-cell to two-cell boundary; and a pair just past `_bump`'s
  coincident limit;
* seed 35's harness fight, packed and primed round the hero with the boss
  in it, frame after frame as it plays.

ENT-019 made the pass take the frame's `dt` and size each shove by
`physics.bump_scale(dt)`, which is exactly 1.0 on the tuned 16 ms frame (the
loop's frame at the 62 fps cap) or any longer one. The oracle keeps its own
copy of the pre-ENT-019 `_bump`, and the new pass runs here on the tuned
frame, and the random crowds on every slow frame the loop makes, so these
same comparisons are ENT-019's pin: at the 62 fps cap and below, the pass is
the one CB-3/H tuned, bit for bit (`journals/bump_frame_rate_journal.md`).
Faster frames are `test_bump_rate.py`'s.
"""
import os
import random
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements import ice as ice_rules
from combat.knockback import knock_split
from game import config
from game.states.playing.core import physics
from game.states.playing.core.physics import BumpResolver


def _old_bump(self, a, b, contact: bool = False, reach: float = 1.0) -> None:
    """`BumpResolver._bump` as it was before ENT-019, verbatim: no `dt`,
    every frame's shove the tuned one whatever the frame's length. Kept
    here, not borrowed from the resolver, so the comparison pins the shove
    itself and not only the factor that ENT-019 put in front of it."""
    delta = a.pos - b.pos
    d2 = delta.length_squared()
    touch = a.radius + b.radius
    if d2 >= touch * touch or d2 < 1e-9:
        return                                   # not overlapping / coincident
    rr = touch * reach
    if d2 < rr * rr:
        pen = min(rr - d2 ** 0.5, rr * physics._PEN_CAP_FRAC)
        push_a, push_b = knock_split(a.weight, b.weight, config.BUMP_GAIN * pen)
        a.apply_knockback(delta, push_a)         # a shoved away from b
        b.apply_knockback(-delta, push_b)        # b shoved away from a
    if contact:
        self._frozen_contact(a, b)


def _old_resolve(self) -> None:
    """`BumpResolver.resolve` as it was before RND-008.5, verbatim, calling
    the pre-ENT-019 `_bump` above."""
    ps = self.ps
    run = getattr(self, "run", ps)
    enemies = run.enemies
    boss = run.boss if (run.boss is not None and run.boss.alive) else None

    population = enemies + [boss] if boss is not None else enemies
    if not population:
        return
    self._grid.rebuild(population)

    seen: set[tuple[int, int]] = set()
    for a in enemies:
        if not a.alive:
            continue
        for b in self._grid.query_circle(a.pos.x, a.pos.y,
                                         a.radius + physics._QUERY_PAD):
            if b is a or not getattr(b, "alive", True):
                continue
            key = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
            if key in seen:
                continue
            seen.add(key)
            frac = (1.0 if b is boss else config.CROWD_PUSH_RADIUS_FRAC)
            _old_bump(self, a, b, contact=True, reach=frac)

    p = run.player
    if p.alive:
        for e in self._grid.query_circle(p.pos.x, p.pos.y,
                                         p.radius + physics._QUERY_PAD):
            if getattr(e, "alive", True):
                _old_bump(self, p, e)


# The tuned frame: 16 ms, what the loop's millisecond clock gives at the
# 62 fps cap (`physics.tuned_dt`).
TUNED_DT = physics.tuned_dt()
# The frames ENT-019 leaves as they were: exactly 1/62 s, the loop's 17 and
# 18 ms frames at the cap, 60 Hz vsync, a heavy scene, and the longest frame
# the loop allows.
SLOW_DTS = (1 / 62, 0.017, 0.018, 1 / 60, 1 / 30, config.MAX_DT)


class _Body:
    """What the pass reads and writes on a body."""

    def __init__(self, x, y, radius, weight=1.0, alive=True):
        self.pos = pygame.Vector2(x, y)
        self.radius = float(radius)
        self.weight = weight
        self.alive = alive
        self._knock = pygame.Vector2()
        self.invulnerable = False

    def apply_knockback(self, direction, strength):
        if direction.length_squared() > 1e-6:
            self._knock += direction.normalize() * strength


def _both(run, resolver, kill=None, dt=TUNED_DT):
    """Knocks, frozen-contact exchanges and deaths from the old pass and the
    new, each from the same starting state.

    `kill=(every, side)` makes every `every`-th exchange kill its `a` or its
    `b`, as frozen-contact damage can: the one state that changes inside a
    pass, and what the new pass's order of checks must not trip over.
    `dt` is the new pass's frame (the old one has none, ENT-019)."""
    # The real boss is immovable (`apply_knockback` ignores it) and keeps no
    # knock; every other body does.
    everyone = [b for b in [*run.enemies, run.player, run.boss] if b is not None]
    bodies = [b for b in everyone if hasattr(b, "_knock")]
    start = [b._knock.copy() for b in bodies]
    living = [b.alive for b in everyone]
    out = []

    def new_resolve(r):
        BumpResolver.resolve(r, dt)

    for resolve in (_old_resolve, new_resolve):
        for b, k in zip(bodies, start):
            b._knock.update(k)
        for b, alive in zip(everyone, living):
            b.alive = alive
        exchanges = []

        def exchange(_r, a, b, _now):
            exchanges.append((id(a), id(b)))
            if kill and len(exchanges) % kill[0] == 0:
                (a if kill[1] == "a" else b).alive = False

        with mock.patch.object(ice_rules, "exchange_contact", exchange):
            resolve(resolver)
        out.append(([tuple(b._knock) for b in bodies], exchanges,
                    [b.alive for b in everyone]))
    for b, k in zip(bodies, start):
        b._knock.update(k)
    for b, alive in zip(everyone, living):
        b.alive = alive
    return out


def _assert_same(case, new, old) -> None:
    """`new == old`, reported by its first difference: a failure here can
    differ in hundreds of floats, and printing the whole diff of every
    subtest takes minutes."""
    if new == old:
        return
    for what, n, o in zip(("knock", "exchange", "alive"), new, old):
        if n != o:
            i = next((i for i, (x, y) in enumerate(zip(n, o)) if x != y), min(len(n), len(o)))
            case.fail(f"{what} #{i} differs: new {n[i] if i < len(n) else 'missing'}, "
                      f"old {o[i] if i < len(o) else 'missing'} (lengths {len(n)} / {len(o)})")
    case.fail("differs")


class RandomCrowdTests(unittest.TestCase):
    def _run(self, rng, n, *, boss=False, giant=False, stacked=False, touching=False):
        cx, cy = 500.0, 500.0
        spread = rng.choice((40.0, 120.0, 400.0))
        enemies = [_Body(cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread),
                         rng.choice((9, 10, 13, 14, 15, 16, 22, 24, 26)),
                         weight=rng.choice((0.5, 1.0, 2.0, 4.0)),
                         alive=rng.random() > 0.05)
                   for _ in range(n)]
        if giant:
            enemies.append(_Body(cx, cy, 90))                # bigger than the old pad
        if stacked and len(enemies) > 1:
            enemies[1].pos.update(enemies[0].pos)             # coincident
        if touching and len(enemies) > 2:
            a = enemies[2]
            b = enemies[3] if len(enemies) > 3 else enemies[0]
            b.pos.update(a.pos.x + a.radius + b.radius, a.pos.y)   # exactly touching
        run = SimpleNamespace(
            enemies=enemies,
            boss=_Body(cx + 30, cy - 20, 46, weight=50.0) if boss else None,
            player=_Body(cx + rng.uniform(-30, 30), cy + rng.uniform(-30, 30), 14),
            elements=object(), stats={"time": 1.0})
        resolver = BumpResolver.__new__(BumpResolver)
        resolver.ps = run
        resolver.run = run
        resolver._grid = physics.SpatialGrid()
        return run, resolver

    def test_many_random_crowds_are_shoved_exactly_as_before(self):
        rng = random.Random(8005)
        cases = 0
        for i in range(400):
            run, resolver = self._run(
                rng, rng.randrange(2, 90), boss=i % 3 == 0, giant=i % 7 == 0,
                stacked=i % 5 == 0, touching=i % 4 == 0)
            old, new = _both(run, resolver)
            with self.subTest(case=i):
                _assert_same(self, new, old)
            cases += 1
        self.assertEqual(cases, 400)

    def test_a_slow_frame_is_shoved_exactly_as_before(self):
        # ENT-019.D5: only a frame shorter than the tuned 16 ms one is
        # scaled; every longer one is the tuned pass, bit for bit.
        rng = random.Random(8007)
        for i in range(120):
            run, resolver = self._run(
                rng, rng.randrange(2, 90), boss=i % 3 == 0, giant=i % 7 == 0,
                stacked=i % 5 == 0, touching=i % 4 == 0)
            for dt in SLOW_DTS:
                old, new = _both(run, resolver, dt=dt)
                with self.subTest(case=i, fps=round(1 / dt, 2)):
                    _assert_same(self, new, old)

    def test_a_fast_frame_is_not(self):
        # The comparison above means something: at 144 Hz the pass does
        # shove differently.
        rng = random.Random(8007)
        run, resolver = self._run(rng, 60)
        old, new = _both(run, resolver, dt=1 / 144)
        self.assertNotEqual(new[0], old[0])

    def test_bodies_killed_by_a_frozen_contact_mid_pass(self):
        # Frozen-contact damage can kill a body in the middle of a pass; the
        # rest of the pass must skip it exactly as the old one did.
        rng = random.Random(8006)
        died = 0
        for i in range(240):
            kill = ((2, "a"), (2, "b"), (3, "a"), (3, "b"))[i % 4]
            run, resolver = self._run(
                rng, rng.randrange(2, 90), boss=i % 3 == 0, giant=i % 7 == 0,
                stacked=i % 5 == 0, touching=i % 4 == 0)
            old, new = _both(run, resolver, kill)
            with self.subTest(case=i, kill=kill):
                _assert_same(self, new, old)
            died += old[2].count(False)
        self.assertGreater(died, 500, "the kills barely happened")

    def test_a_giant_across_a_cell_edge_is_met_from_the_same_side(self):
        # With 96 px cells and every real collider 46 px or less, a
        # one-cell search finds every pair that touches, so the pad cannot
        # matter there, and random crowds rarely say otherwise. It matters
        # when a collider bigger than the old 72 px pad touches a smaller
        # body two cells away. Which body's search finds the pair decides
        # which way round it is shoved, and so the order of the frozen
        # exchanges:
        #  * r 9 at x 95.9 (cell 0), giant r 90 at x 192.1 (cell 2), 96.2
        #    apart and touching. The old pad (72) finds it only from the
        #    giant; an uncapped pad (90) would find it from the small body.
        #  * r 26 at x 95.9 against the same giant, 97 apart. The old pad
        #    finds it from the small body; a pad well short of the largest
        #    collider would not.
        #  * two r 48.25 at x 95.99 and 192.39, 96.4 apart. The right pad
        #    (48.25) makes the search 96.5 px, two cells, and finds the pair;
        #    a pad even one px short makes it one cell on both sides, and
        #    the pair is never met (the cell-count boundary).
        for (ra, xa), (rb, xb) in (((9, 95.9), (90, 192.1)), ((26, 95.9), (90, 192.9)),
                                   ((48.25, 95.99), (48.25, 192.39))):
            with self.subTest(a=ra, b=rb):
                run = SimpleNamespace(
                    enemies=[_Body(xa, 50.0, ra), _Body(xb, 50.0, rb)],
                    boss=None, player=_Body(5000.0, 5000.0, 14),
                    elements=object(), stats={"time": 1.0})
                resolver = BumpResolver.__new__(BumpResolver)
                resolver.ps = resolver.run = run
                resolver._grid = physics.SpatialGrid()
                old, new = _both(run, resolver)
                self.assertEqual(len(old[1]), 1, "the pair should touch once")
                _assert_same(self, new, old)

    def test_a_pair_just_past_the_coincident_limit_is_met(self):
        # `_bump` treats a pair closer than 1e-9 (squared) as coincident and
        # leaves it; one just past that is met. The early drop keeps its
        # own limit a billionth under `_bump`'s, so this pair reaches
        # `_bump` and is met as before.
        # At the origin, so the separation keeps its precision (at x 300 a
        # float's step is larger than the window this needs).
        dx = (1e-9 * (1.0 + 5e-10)) ** 0.5
        a, b = _Body(0.0, 0.0, 14), _Body(dx, 0.0, 14)
        d2 = (a.pos - b.pos).length_squared()
        self.assertTrue(1e-9 <= d2 < 1e-9 * (1.0 + 1e-9), d2)
        run = SimpleNamespace(
            enemies=[a, b],
            boss=None, player=_Body(5000.0, 5000.0, 14),
            elements=object(), stats={"time": 1.0})
        resolver = BumpResolver.__new__(BumpResolver)
        resolver.ps = resolver.run = run
        resolver._grid = physics.SpatialGrid()
        old, new = _both(run, resolver)
        # Met: the frozen contact is exchanged. (Too close to be shoved:
        # `apply_knockback` ignores a direction under 1e-3 px.)
        self.assertEqual(len(old[1]), 1, "the pair should be met")
        _assert_same(self, new, old)

    def test_the_crowds_are_not_trivial(self):
        # The comparison above means something only if pairs are shoved and
        # frozen contacts exchanged.
        rng = random.Random(8005)
        shoved = exchanged = 0
        for i in range(400):
            run, resolver = self._run(
                rng, rng.randrange(2, 90), boss=i % 3 == 0, giant=i % 7 == 0,
                stacked=i % 5 == 0, touching=i % 4 == 0)
            (knocks, exchanges, _alive), _new = _both(run, resolver)
            shoved += sum(1 for k in knocks if k != (0.0, 0.0))
            exchanged += len(exchanges)
        self.assertGreater(shoved, 1000)
        self.assertGreater(exchanged, 1000)


class HarnessFightTests(unittest.TestCase):
    """Seed 35's packed, primed fight, with the boss in it, as it plays."""

    @classmethod
    def setUpClass(cls):
        from tools.benchmarks import spawn_stress as S

        cls.game, cls.ps = S.build(35, 100, 0, 300.0, config.ENEMY_LOD_SKIP)
        S.infuse(cls.ps, 35)
        S.run(cls.ps, 20)
        S.cascade_setup(cls.ps)
        cls.ps.spawn.spawn_boss()
        cls.ps.run.boss.pos.update(cls.ps.player.pos.x + 20, cls.ps.player.pos.y)

    def test_every_frame_is_shoved_exactly_as_before(self):
        ps = self.ps
        compared = shoved = 0
        for frame in range(40):
            old, new = _both(ps.run, ps.bump)
            with self.subTest(frame=frame):
                _assert_same(self, new, old)
            shoved += len(old[1])
            compared += 1
            ps.update(1 / 60)                         # the fight moves on
        self.assertEqual(compared, 40)
        self.assertGreater(shoved, 200, "the crowd barely touched")


if __name__ == "__main__":
    unittest.main()
