"""The terrace inset field: how far inside its own floor a point stands.

Phase 1 of the frontier margin. Nothing consumes the field yet -- props,
movement and the flow field come after -- so what is pinned here is the field
itself: that it exists where it should, that it measures what it claims to,
that it is *conservative* rather than merely close, and that an 8 px inset
takes no floor away from anyone.

Three things this suite exists to stop coming back.

`world/inset.py` originally stored an absolute origin taken from `room.rect`.
Island rects are still being packed when the field is built, so every query
landed in a different room by the time anything read it. The field is
room-relative now, and `test_the_field_is_room_relative` is the regression.

The chamfer measures centre to centre, so the nearest possible sample scored a
whole step and an 8 px margin forbade nothing at all. The boundary sits half a
step short of the neighbouring centre, which is what the field stores.

And `at()` reads the minimum of the four samples bracketing a point rather than
the one it lands in. Reading it raw over-reported by up to 9 px near a
boundary -- more than the margin itself -- so a body could stand flush against
the edge the rule exists to hold it off.
"""
import math
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from world import inset as I
from world.layout import CLIFF, VSTAIR, EWSTAIR, WALKABLE_KINDS
from world.map import GameMap

SEEDS = (35, 7)
MARGIN = 8.0
_SAVED = None
_MAPS: dict = {}


def setUpModule():
    global _SAVED
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    _SAVED = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = True


def tearDownModule():
    config.HEIGHTMAP_ROOMS = _SAVED
    _MAPS.clear()


def _map(seed: int) -> GameMap:
    if seed not in _MAPS:
        gm = GameMap(seed=seed)
        gm._build_tiles()
        _MAPS[seed] = gm
    return _MAPS[seed]


def _rooms(seed):
    return [r for r in _map(seed).layout.rooms if r.inset is not None]


def _near_flight(room, c) -> bool:
    return any((room.grid.get((c[0] + dc, c[1] + dr)) or room.grid[c]).kind
               in (VSTAIR, EWSTAIR)
               for dc in (-1, 0, 1) for dr in (-1, 0, 1))


def _true_distance(room, c, x, y, level, px, reach=6):
    """Brute force: distance from a world point to the nearest tile of another
    level, measured to that tile's rectangle rather than to a sample."""
    best = float("inf")
    for dc in range(-reach, reach + 1):
        for dr in range(-reach, reach + 1):
            o = room.grid.get((c[0] + dc, c[1] + dr))
            if o is None:
                continue
            if not (o.kind == CLIFF
                    or (o.kind in WALKABLE_KINDS and o.level != level)):
                continue
            ox = room.rect.x + (c[0] + dc) * px
            oy = room.rect.y + (c[1] + dr) * px
            dx = max(ox - x, 0.0, x - (ox + px))
            dy = max(oy - y, 0.0, y - (oy + px))
            best = min(best, math.hypot(dx, dy))
    return best


class PresenceTests(unittest.TestCase):
    def test_islands_with_terraces_get_a_field(self):
        for seed in SEEDS:
            with_levels = [r for r in _map(seed).layout.rooms
                           if r.grid and len({c.level for c in r.grid.values()
                                              if c.kind in WALKABLE_KINDS}) > 1]
            self.assertTrue(with_levels, f"seed {seed}: no multi-level island")
            for room in with_levels:
                self.assertIsNotNone(room.inset,
                                     f"seed {seed} room {room.id}: no field")

    def test_a_room_without_a_grid_answers_clear(self):
        """The flat LD-8 world has no levels, so it has no boundaries and the
        rule has nothing to say about it."""
        room = _rooms(SEEDS[0])[0]
        bare = type(room)(id=99, cell=(0, 0), rect=room.rect, kind="normal")
        self.assertIsNone(bare.inset)
        self.assertTrue(I.world_clear(bare, room.rect.centerx,
                                      room.rect.centery, MARGIN))

    def test_the_field_stays_small(self):
        """One byte a sample at a quarter-tile pitch. The cap is what keeps a
        big island under 100 KB."""
        for seed in SEEDS:
            for room in _rooms(seed):
                self.assertEqual(len(room.inset.data),
                                 room.inset.cols * room.inset.rows)
                self.assertLess(len(room.inset.data), 200 * 1024)


class GeometryTests(unittest.TestCase):
    def test_the_field_is_room_relative(self):
        """The regression for the stale origin. Island rects are packed after
        the grids are built, so a field holding absolute coordinates reads out
        of a different room entirely -- which is exactly what happened, and it
        showed up as the margin forbidding nothing anywhere."""
        px = config.TILE_PX
        for seed in SEEDS:
            for room in _rooms(seed)[:3]:
                for c in sorted(room.cells)[:40]:
                    cell = room.grid.get(c)
                    if cell is None or cell.kind not in WALKABLE_KINDS:
                        continue
                    if c in room.inset.exempt:
                        continue        # a crossing answers clear regardless
                    x = room.rect.x + c[0] * px + px / 2
                    y = room.rect.y + c[1] * px + px / 2
                    rel = room.inset.at(x - room.rect.x, y - room.rect.y)
                    # the conversion `world_clear` does, and the only one
                    self.assertEqual(I.world_clear(room, x, y, rel), True)
                    self.assertEqual(I.world_clear(room, x, y, rel + 1), False)
                    # ...and feeding it world coordinates raw -- the bug --
                    # lands outside the field, which answers CAP and would
                    # have made every point on every island "clear".
                    if room.rect.x > room.rect.width:
                        self.assertEqual(room.inset.at(x, y), I.CAP)

    def test_the_query_is_conservative_near_a_boundary(self):
        """It may hold a body further inside than asked; it may not let one
        stand closer. Half a step of slack is the sampling pitch."""
        px = config.TILE_PX
        rng = random.Random(3)
        checked = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                cells = sorted(room.cells)
                for _ in range(250):
                    c = rng.choice(cells)
                    cell = room.grid.get(c)
                    if cell is None or cell.kind not in WALKABLE_KINDS:
                        continue
                    if _near_flight(room, c):
                        continue            # exempt by design, tested below
                    x = room.rect.x + c[0] * px + rng.uniform(1, px - 1)
                    y = room.rect.y + c[1] * px + rng.uniform(1, px - 1)
                    ref = _true_distance(room, c, x, y, cell.level, px)
                    if ref > 40:
                        continue            # far field: both say "clear"
                    got = room.inset.at(x - room.rect.x, y - room.rect.y)
                    checked += 1
                    self.assertLessEqual(
                        got - ref, I.STEP / 2 + 0.5,
                        f"seed {seed}: field says {got}px at {(x, y)} but the "
                        f"boundary is {ref:.1f}px away")
        self.assertGreater(checked, 200, "not enough near-boundary samples")

    def test_a_point_hard_against_a_level_change_is_not_clear(self):
        px = config.TILE_PX
        found = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    if _near_flight(room, c):
                        continue
                    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        o = room.grid.get((c[0] + dc, c[1] + dr))
                        if o is None:
                            continue
                        if not (o.kind == CLIFF
                                or (o.kind in WALKABLE_KINDS
                                    and o.level != cell.level)):
                            continue
                        # a point one pixel inside the shared edge
                        x = room.rect.x + c[0] * px + px / 2 + dc * (px / 2 - 1)
                        y = room.rect.y + c[1] * px + px / 2 + dr * (px / 2 - 1)
                        found += 1
                        self.assertFalse(
                            I.world_clear(room, x, y, MARGIN),
                            f"seed {seed}: {(x, y)} sits against a level "
                            f"change and the field calls it clear")
                        break
        self.assertGreater(found, 100, "no level changes sampled")


class WaterTests(unittest.TestCase):
    """Explicitly not a frontier -- the user's call. A shore is not a floor
    boundary, and insetting every coastline would take a slice off every island
    for nothing anyone would see."""

    def test_a_coastline_is_not_a_frontier(self):
        px = config.TILE_PX
        checked = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    if _near_flight(room, c):
                        continue
                    # sea on one side, and nothing else within two tiles that
                    # could be the boundary being measured
                    if not any(room.grid.get((c[0] + dc, c[1] + dr)) is None
                               for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        continue
                    if any((o := room.grid.get((c[0] + dc, c[1] + dr))) is not None
                           and (o.kind == CLIFF
                                or (o.kind in WALKABLE_KINDS
                                    and o.level != cell.level))
                           for dc in (-2, -1, 0, 1, 2)
                           for dr in (-2, -1, 0, 1, 2)):
                        continue
                    x = room.rect.x + c[0] * px + px / 2
                    y = room.rect.y + c[1] * px + px / 2
                    checked += 1
                    self.assertTrue(
                        I.world_clear(room, x, y, MARGIN),
                        f"seed {seed}: shore tile {c} was inset")
        self.assertGreater(checked, 20, "no clean coastline tiles found")


class FlightTests(unittest.TestCase):
    def test_every_flight_cell_is_exempt(self):
        """A crossing exists to straddle a frontier. A margin on it would seal
        the staircase, and it would not look like a bug -- only like an island
        whose stairs are never used."""
        px = config.TILE_PX
        total = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c, cell in room.grid.items():
                    if cell.kind not in (VSTAIR, EWSTAIR):
                        continue
                    total += 1
                    x = room.rect.x + c[0] * px + px / 2
                    y = room.rect.y + c[1] * px + px / 2
                    self.assertTrue(I.world_clear(room, x, y, MARGIN),
                                    f"seed {seed}: flight cell {c} is inset")
        self.assertGreater(total, 50, "no flights in the sample")

    def test_the_landings_are_exempt_too(self):
        """A body has to stand next to the unit to line up with it, and the
        widest one in the game is 46 px of radius against a 64 px tile."""
        px = config.TILE_PX
        total = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    if cell.kind in (VSTAIR, EWSTAIR) or not _near_flight(room, c):
                        continue
                    total += 1
                    x = room.rect.x + c[0] * px + px / 2
                    y = room.rect.y + c[1] * px + px / 2
                    self.assertTrue(I.world_clear(room, x, y, MARGIN),
                                    f"seed {seed}: landing {c} is inset")
        self.assertGreater(total, 50, "no landings in the sample")


class CostTests(unittest.TestCase):
    def test_an_eight_pixel_inset_strands_nothing(self):
        """The question the whole phase exists to answer. Flood the samples a
        body may stand on and check every walkable tile keeps at least one of
        them in the main component -- no pocket cut off, no staircase sealed.
        """
        px = config.TILE_PX
        for seed in SEEDS:
            for room in _rooms(seed):
                f = room.inset
                step = f.step
                allowed = bytearray(f.cols * f.rows)
                for row in range(f.rows):
                    ry = row * step + step / 2
                    for col in range(f.cols):
                        rx = col * step + step / 2
                        cell = room.grid.get((int(rx // px), int(ry // px)))
                        if cell is None or cell.kind not in WALKABLE_KINDS:
                            continue
                        if f.clear(rx, ry, MARGIN):
                            allowed[row * f.cols + col] = 1
                main = self._largest_component(allowed, f.cols, f.rows)
                per = px // step
                reached = {(i % f.cols // per, i // f.cols // per) for i in main}
                for c, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS:
                        continue
                    self.assertIn(c, reached,
                                  f"seed {seed} room {room.id}: tile {c} "
                                  f"({cell.kind}) is cut off by the inset")

    @staticmethod
    def _largest_component(allowed, cols, rows):
        seen = bytearray(len(allowed))
        best: list = []
        for start in range(len(allowed)):
            if not allowed[start] or seen[start]:
                continue
            comp, stack = [], [start]
            seen[start] = 1
            while stack:
                i = stack.pop()
                comp.append(i)
                r0, c0 = divmod(i, cols)
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    r1, c1 = r0 + dr, c0 + dc
                    if 0 <= r1 < rows and 0 <= c1 < cols:
                        j = r1 * cols + c1
                        if allowed[j] and not seen[j]:
                            seen[j] = 1
                            stack.append(j)
            if len(comp) > len(best):
                best = comp
        return set(best)


class PropChannelTests(unittest.TestCase):
    """Phase 2: the props read the field, and they read a different channel.

    `world/frontier.py`'s rules have always counted the water's edge as a
    frontier -- a pebble at the shoreline reads as floating -- while the
    movement rule deliberately does not, because walking to the water's edge
    reads as standing on a beach. One field, two questions.
    """

    def test_the_two_channels_differ_at_the_shore(self):
        px = config.TILE_PX
        differ = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c, cell in room.grid.items():
                    if cell.kind not in WALKABLE_KINDS or c in room.inset.exempt:
                        continue
                    side = next(((dc, dr) for dc, dr in
                                 ((1, 0), (-1, 0), (0, 1), (0, -1))
                                 if room.grid.get((c[0] + dc, c[1] + dr)) is None),
                                None)
                    if side is None:
                        continue
                    # Two pixels in from the water-facing edge. The tile centre
                    # is 32 px from every edge, so an 8 px margin never bites
                    # there and the two channels agree by accident.
                    dc, dr = side
                    x = room.rect.x + c[0] * px + px / 2 + dc * (px / 2 - 2)
                    y = room.rect.y + c[1] * px + px / 2 + dr * (px / 2 - 2)
                    if (I.world_clear(room, x, y, MARGIN)
                            and not I.world_prop_clear(room, x, y, MARGIN)):
                        differ += 1
        self.assertGreater(differ, 20,
                           "no shoreline where a body may stand and a prop "
                           "may not -- the channels are not doing their job")

    def test_the_field_is_never_more_permissive_than_the_rim_test(self):
        """The swap may only tighten. The eight-point rim test it replaces has
        gaps between its samples; a distance field has none, so every
        disagreement should be the field refusing something the rim test let
        through, and never the other way round."""
        from world import frontier as FR
        px = config.TILE_PX
        rng = random.Random(17)
        looser = checked = 0
        for seed in SEEDS:
            for room in _rooms(seed):
                for c in sorted(room.cells)[::5]:
                    cell = room.grid.get(c)
                    if cell is None or cell.kind not in WALKABLE_KINDS:
                        continue
                    for _ in range(3):
                        x = room.rect.x + c[0] * px + rng.uniform(2, px - 2)
                        y = room.rect.y + c[1] * px + rng.uniform(2, px - 2)
                        rim = all(FR.tile_level(room, x + dx * MARGIN,
                                                y + dy * MARGIN, px) == cell.level
                                  for dx, dy in FR.AROUND)
                        got = FR.frontier_clear(room, x, y, cell.level,
                                                MARGIN, px)
                        checked += 1
                        if got and not rim:
                            looser += 1
        self.assertGreater(checked, 500)
        self.assertEqual(looser, 0,
                         f"the field allowed {looser} placements the rim test "
                         f"refused")


class MovementTests(unittest.TestCase):
    """Phase 3: the collider keeps a body's centre inside its own terrace."""

    def test_the_margin_is_read_from_the_data(self):
        """No per-value default in code -- the standing rule for this project.
        Setting it to 0 has to switch the whole thing off."""
        from game.content import get_content
        self.assertEqual(
            _map(SEEDS[0])._body_inset,
            float(get_content().terrain["frontier"]["body_inset"]))

    def test_a_body_cannot_stand_against_a_level_change(self):
        px = config.TILE_PX
        gm = _map(SEEDS[0])
        found = 0
        for room in _rooms(SEEDS[0]):
            for c, cell in room.grid.items():
                if cell.kind not in WALKABLE_KINDS or c in room.inset.exempt:
                    continue
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    o = room.grid.get((c[0] + dc, c[1] + dr))
                    if o is None:
                        continue
                    if not (o.kind == CLIFF
                            or (o.kind in WALKABLE_KINDS
                                and o.level != cell.level)):
                        continue
                    x = room.rect.x + c[0] * px + px / 2 + dc * (px / 2 - 1)
                    y = room.rect.y + c[1] * px + px / 2 + dr * (px / 2 - 1)
                    if not gm._point_ok(x, y):
                        continue
                    found += 1
                    self.assertFalse(
                        gm.is_walkable(pygame.Vector2(x, y)),
                        f"a body may stand at {(x, y)}, hard against a "
                        f"{o.kind}@{o.level} from a {cell.kind}@{cell.level}")
                    break
        self.assertGreater(found, 50, "no level changes sampled")

    def test_a_body_already_inside_the_margin_may_leave_but_not_go_deeper(self):
        """The escape hatch. Without it, anything that put a body inside the
        margin -- a spawn from before the rule, a knockback, the end of a
        crossing's exemption -- would freeze it there permanently.

        Stated on the margin rule alone. Walking a body to a neighbouring point
        drags in the elevation rule and the obstacle test as well, and both of
        them legitimately refuse moves near a rim, so a test phrased that way
        measures three things and blames this one.
        """
        px = config.TILE_PX
        gm = _map(SEEDS[0])
        tested = 0
        for room in _rooms(SEEDS[0]):
            for c, cell in room.grid.items():
                if cell.kind not in WALKABLE_KINDS or c in room.inset.exempt:
                    continue
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    o = room.grid.get((c[0] + dc, c[1] + dr))
                    if o is None or not (
                            o.kind == CLIFF
                            or (o.kind in WALKABLE_KINDS
                                and o.level != cell.level)):
                        continue
                    x = room.rect.x + c[0] * px + px / 2 + dc * (px / 2 - 1)
                    y = room.rect.y + c[1] * px + px / 2 + dr * (px / 2 - 1)
                    inside = pygame.Vector2(x, y)
                    if not gm._point_ok(x, y) or gm.inset_ok(x, y):
                        continue
                    if any((x - ob.pos.x) ** 2 + (y - ob.pos.y) ** 2
                           < ob.radius ** 2 for ob in gm.obstacles):
                        continue        # an obstacle would refuse it anyway
                    tested += 1
                    # arriving from outside: refused
                    self.assertFalse(gm.is_walkable(inside),
                                     f"{inside} is inside the margin and the "
                                     f"collider allows standing there")
                    # already there, not going deeper: allowed
                    self.assertTrue(
                        gm.is_walkable(inside, frm=inside),
                        f"a body already at {inside} is frozen by the margin")
                    break
                if tested > 40:
                    break
            if tested > 40:
                break
        self.assertGreater(tested, 5, "no points inside the margin found")

    def test_every_crossing_stays_walkable(self):
        """The exemption, from the collider's side. A margin on a staircase
        would seal it, and the failure would look like an island whose stairs
        are simply never used."""
        px = config.TILE_PX
        gm = _map(SEEDS[0])
        total = 0
        for room in _rooms(SEEDS[0]):
            for c, cell in room.grid.items():
                if cell.kind not in (VSTAIR, EWSTAIR):
                    continue
                total += 1
                x = room.rect.x + c[0] * px + px / 2
                y = room.rect.y + c[1] * px + px / 2
                self.assertTrue(gm.inset_ok(x, y),
                                f"the margin seals the crossing at {c}")
        self.assertGreater(total, 20)

    def test_a_corridor_carries_no_margin(self):
        """Bridges are flat and have no grid, so there is no floor boundary on
        one to keep away from -- and a margin keyed on rooms would otherwise
        wall every bridge shut."""
        gm = _map(SEEDS[0])
        self.assertTrue(gm.layout.corridors)
        checked = 0
        for corr in gm.layout.corridors[:20]:
            x, y = corr.rect.centerx, corr.rect.centery
            if not gm._point_ok(x, y):
                continue
            checked += 1
            self.assertTrue(gm.inset_ok(x, y))
        self.assertGreater(checked, 3, "no corridor centres on floor")


class NavTests(unittest.TestCase):
    """Phase 4: the flow field and the collider answer the same question.

    They are two authorities over the same geometry, and this milestone has
    already watched that go wrong twice -- `walk_links` against
    `_flight_opens`, then the baked step mask against `can_step`. A field that
    routed through ground the collider refuses would send an enemy at a
    boundary it can never cross and leave it grinding on the corner for ever,
    which reads as broken AI rather than as a rule.
    """

    def _nav(self, seed):
        from world.pathfinding import NavField
        gm = _map(seed)
        if not hasattr(gm, "_test_nav"):
            gm._test_nav = NavField(gm.layout, gm.obstacles)
        return gm, gm._test_nav

    def test_the_field_never_routes_where_the_collider_refuses(self):
        for seed in SEEDS:
            gm, nav = self._nav(seed)
            for name, g in nav.grids.items():
                ox, oy = g.origin
                half = g.cell * 0.5
                bad = 0
                for row in range(g.rows):
                    cy = oy + row * g.cell + half
                    base = row * g.cols
                    for col in range(g.cols):
                        if not g.walkable[base + col]:
                            continue
                        cx = ox + col * g.cell + half
                        if not gm.inset_ok(cx, cy):
                            bad += 1
                self.assertEqual(bad, 0,
                                 f"seed {seed} {name}: {bad} walkable nav "
                                 f"cells sit inside the margin")

    def test_the_margin_is_not_treated_as_a_wall(self):
        """A margin cell is not walkable, and it is not stone either.

        `blocked` seeds the wall chamfer that produces `clearance`, and calling
        a margin stone would shrink the clearance of every cell near a rim --
        which is precisely what would stop the 48 px class threading a one-tile
        neck, the risk this phase carried. Checked where it shows: the
        clearance transform must come out byte for byte identical with the
        margin on and off.
        """
        import world.pathfinding as P
        real = P.terrain_inset.body_inset
        try:
            for seed in SEEDS:
                gm = _map(seed)
                P.terrain_inset.body_inset = lambda: 0.0
                off = P.NavField(gm.layout, gm.obstacles)
                P.terrain_inset.body_inset = real
                on = P.NavField(gm.layout, gm.obstacles)
                for name in off.grids:
                    self.assertEqual(
                        list(off.grids[name].clearance),
                        list(on.grids[name].clearance),
                        f"seed {seed} {name}: the margin changed the wall "
                        f"clearance, so it is being treated as stone")
                    self.assertLess(sum(on.grids[name].walkable),
                                    sum(off.grids[name].walkable) + 1)
        finally:
            P.terrain_inset.body_inset = real

    def test_every_crossing_stays_on_both_nav_grids(self):
        """The margin may not take a staircase away from either body size."""
        px = config.TILE_PX
        for seed in SEEDS:
            gm, nav = self._nav(seed)
            for name, g in nav.grids.items():
                ox, oy = g.origin
                missing = 0
                total = 0
                for room in gm.layout.rooms:
                    if not room.grid:
                        continue
                    for c, cell in room.grid.items():
                        if cell.kind not in (VSTAIR, EWSTAIR):
                            continue
                        total += 1
                        x = room.rect.x + c[0] * px + px / 2
                        y = room.rect.y + c[1] * px + px / 2
                        col = int((x - ox) // g.cell)
                        row = int((y - oy) // g.cell)
                        if not (0 <= col < g.cols and 0 <= row < g.rows):
                            continue
                        if not g.walkable[row * g.cols + col]:
                            missing += 1
                self.assertGreater(total, 20)
                self.assertEqual(missing, 0,
                                 f"seed {seed} {name}: {missing} flight cells "
                                 f"dropped off the nav grid")


class PhaseTests(unittest.TestCase):
    def test_only_the_landed_phases_read_the_field(self):
        """A gate, not a style rule. Each phase lands on its own so that if one
        of them changes how the world plays it does so alone and visibly:
        phase 1 built the field, phase 2 moved the props onto it, phase 3 gave
        it to the collider, and phase 4 baked it into the flow field. All four
        have landed, so this is now a fence rather than a gate: a fifth reader
        is a decision, not an accident.
        """
        import pathlib
        readers = set()
        for q in pathlib.Path(".").rglob("*.py"):
            sp = str(q)
            if "test" in sp or "worktrees" in sp or "scratchpad" in sp:
                continue
            text = q.read_text(encoding="utf-8", errors="ignore")
            # Both ways in: importing the module, and reading the field the
            # generation stage hangs on every room.
            if ("world.inset" in text or "from world import inset" in text
                    or "room.inset" in text or ".inset is not None" in text):
                readers.add(q.name)
        readers.discard("inset.py")
        self.assertEqual(
            readers,
            {"islands.py", "frontier.py", "map.py", "pathfinding.py"},
                         f"unexpected readers of the inset field: {readers}")


if __name__ == "__main__":
    unittest.main()
