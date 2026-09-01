"""LD-9: obstacles must not seal part of the world off, and lakes must read as
lakes.

Two generation-stage guarantees that were both being broken quietly.

`world/gen/repair.py` answers the first: after the scatter, can the *widest*
navigating body still reach everywhere bare terrain allows? Before it, four of
ten sample seeds lost between 1,300 and 6,300 reachable cells on the large
navigation class, one of them 69% of the world -- and nothing complained,
because an enemy that cannot route simply stands there.

`heightmap._trim_lake_stubs` answers the second. The brief: a lake is at least
three contiguous tiles on one terrace, line or L, no single-tile ponds. The size
floor alone did not get what it was aimed at, because the offender was a
one-tile arm hanging off a bigger blob.
"""
import unittest

from game import config
from world.gen import generate_world
from world.gen.rooms import _cell_rect
from world.gen.repair import _killers, _reachable, _start_cell, _widest_class
from world.gen.heightmap import _trim_lake_stubs, _walk, check_grid
from world.layout import GROUND, LAKE
from world.pathfinding import NavGrid

_SEEDS = range(8)
_NB = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _sealed(layout, obstacles=None) -> int:
    """Cells the widest body could stand on but cannot walk to from the start.

    Deliberately built from the same pieces `unseal` uses, so a change to the
    navigation model moves the check and the fix together rather than letting
    them drift apart.

    Pass `[]` for the bare-terrain baseline. That baseline is **not zero**, and
    assuming it was is what these tests originally did: LD-10's ragged coast
    leaves narrow spits and nooks a 22 px body cannot stand on at all, 300-570
    nav cells of about 9,000 per world. Measured, they are fringe rather than
    region -- on a sample seed, 30 single cells, 20 pairs and 19 triples, with
    the largest anything at 29 cells, about four tiles. A wide enemy not fitting
    onto a one-tile spit is the terrain being honest, not a seal.
    """
    cell, radius = _widest_class()
    grid = NavGrid(layout, [], cell)
    n = grid.cols * grid.rows
    open_ = bytearray(1 if (grid.walkable[i] and grid.clearance[i] >= radius)
                      else 0 for i in range(n))
    start = _start_cell(grid, layout, open_)
    if start is None:
        return 0
    obs = layout.obstacles if obstacles is None else obstacles
    killers = _killers(grid, obs, radius)
    seen = _reachable(grid, open_, killers, start)
    return sum(1 for i in range(n)
               if open_[i] and not killers[i] and not seen[i])


class _Heightmap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved = config.HEIGHTMAP_ROOMS
        config.HEIGHTMAP_ROOMS = True

    @classmethod
    def tearDownClass(cls):
        config.HEIGHTMAP_ROOMS = cls._saved


class SealTests(_Heightmap):
    def test_obstacles_never_cut_off_more_than_bare_terrain_does(self):
        """What the repair actually promises. Terrain has its own unreachable
        fringe (see `_sealed`); the guarantee is that obstacles add nothing to
        it."""
        for seed in _SEEDS:
            layout = generate_world(seed)
            self.assertLessEqual(_sealed(layout), _sealed(layout, []),
                                 f"seed {seed}: obstacles cut off more than the "
                                 f"terrain alone")

    def test_the_repair_has_teeth(self):
        """Without it the seals are there. If this ever passes trivially the
        test above is proving nothing.

        It needs a **wide** seed range, wider than the rest of this module.
        Since LD-10 reshaped the islands, a bad seal is rare but severe rather
        than common and small: over twenty seeds the deltas run
        0, 0, 1, 2, ... 10, 14, 80, 567, **2319**. The first eight seeds top out
        at 14, so the range used elsewhere would let this pass while proving
        nothing at all.
        """
        saved = config.HEIGHTMAP_UNSEAL
        try:
            config.HEIGHTMAP_UNSEAL = False
            worst = max(_sealed(w) - _sealed(w, [])
                        for w in (generate_world(s) for s in range(20)))
        finally:
            config.HEIGHTMAP_UNSEAL = saved
        self.assertGreater(worst, 100,
                           "no seed seals without the repair -- the test above "
                           "is proving nothing")

    def test_it_takes_back_only_a_handful(self):
        """A repair that clears the map would also pass the test above."""
        saved = config.HEIGHTMAP_UNSEAL
        try:
            config.HEIGHTMAP_UNSEAL = False
            before = [len(generate_world(s).obstacles) for s in _SEEDS]
        finally:
            config.HEIGHTMAP_UNSEAL = saved
        after = [len(generate_world(s).obstacles) for s in _SEEDS]
        for s, (b, a) in zip(_SEEDS, zip(before, after)):
            self.assertLessEqual(b - a, max(4, b // 20),
                                 f"seed {s}: removed {b - a} of {b}")

    def test_it_is_deterministic(self):
        a = [(o.kind, tuple(o.pos)) for o in generate_world(5).obstacles]
        b = [(o.kind, tuple(o.pos)) for o in generate_world(5).obstacles]
        self.assertEqual(a, b)


class LegacyWorldTests(unittest.TestCase):
    def test_the_ld8_world_is_left_alone(self):
        """The seals were measured on the height-map worlds; the legacy
        generator is pinned seed by seed in the tests that describe it, so
        neither the repair nor the widened mouth test may touch it."""
        saved = config.HEIGHTMAP_ROOMS
        try:
            config.HEIGHTMAP_ROOMS = False
            with_repair = [(o.kind, tuple(o.pos))
                           for o in generate_world(3).obstacles]
            saved_u = config.HEIGHTMAP_UNSEAL
            try:
                config.HEIGHTMAP_UNSEAL = False
                without = [(o.kind, tuple(o.pos))
                           for o in generate_world(3).obstacles]
            finally:
                config.HEIGHTMAP_UNSEAL = saved_u
        finally:
            config.HEIGHTMAP_ROOMS = saved
        self.assertEqual(with_repair, without)


def _components(cells):
    seen, out = set(), []
    for p in cells:
        if p in seen:
            continue
        stack, comp = [p], set()
        seen.add(p)
        while stack:
            q = stack.pop()
            comp.add(q)
            for dx, dy in _NB:
                n = (q[0] + dx, q[1] + dy)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(comp)
    return out


class InlandHoleTests(_Heightmap):
    """LD-10: the three-tile minimum covers *any* inland water, not just lakes.

    The offenders were never lakes. Measured over ten worlds before the fix: 43
    one-tile and 156 two-tile near-enclosed holes, and 199 of 205 were cells
    absent from the grid altogether -- open sea bitten in by the coast walk, or
    left behind when the prune took the ground around them away. The lake
    minimum itself was already clean over thirty seeds.
    """

    def _holes(self, room):
        """Water blobs inside the island's own bounding box, with how much land
        surrounds them."""
        land = {p for p, c in room.grid.items() if c.kind != LAKE}
        if not land:
            return
        cs = [p[0] for p in land]
        rs = [p[1] for p in land]
        box = {(c, r) for c in range(min(cs), max(cs) + 1)
               for r in range(min(rs), max(rs) + 1)}
        holes = box - land
        seen = set()
        for p in holes:
            if p in seen:
                continue
            stack, comp = [p], set()
            seen.add(p)
            while stack:
                q = stack.pop()
                comp.add(q)
                for dx, dy in _NB:
                    n = (q[0] + dx, q[1] + dy)
                    if n in holes and n not in seen:
                        seen.add(n)
                        stack.append(n)
            touching = sum(1 for q in comp for dx, dy in _NB
                           if (q[0] + dx, q[1] + dy) in land)
            yield comp, touching

    def test_no_inland_hole_is_smaller_than_three_tiles(self):
        for seed in _SEEDS:
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                for comp, touching in self._holes(room):
                    if touching < 3:
                        continue          # still open to the sea: a bay
                    self.assertGreaterEqual(
                        len(comp), 3,
                        f"seed {seed} room {room.id}: {sorted(comp)}")

    def test_filling_never_leaves_ground_hanging_over_the_sea(self):
        """Nearly half the holes have their south side open, so a fill puts new
        ground where there was water and something has to stand under it."""
        for seed in _SEEDS:
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                for (col, row), cell in room.grid.items():
                    if cell.kind != GROUND or cell.level <= 0:
                        continue
                    self.assertIn((col, row + 1), room.grid,
                                  f"seed {seed} room {room.id}: level "
                                  f"{cell.level} ground at ({col},{row}) with "
                                  f"open sea below it")

    def test_it_does_not_strand_anything(self):
        """Both fill branches only ever replace water, so the walkable set can
        grow but never split."""
        for seed in _SEEDS:
            for room in generate_world(seed).rooms:
                if room.grid:
                    check_grid(room.grid)


class CoastPresetTests(_Heightmap):
    """LD-10: the coastline is a named preset, and `classic` is the way back.

    The old shore was straight because the walk had **no room to wander**, not
    because it held each value too long: with a margin of 4 and steps of one or
    two, the walk hits 0 or the margin constantly and the clamp pins it there.
    Measured, forcing a step at the old amplitude moved 37.9% of runs-of-5 only
    to 29.9% and made *more* perfect rectangles; raising the amplitude took it
    to 13.1%, and the two together to 10.6%.
    """

    def _shores(self, seeds=range(1, 6)):
        """Run lengths along the west and north shores of every island."""
        runs = []
        for seed in seeds:
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                land = {p for p, c in room.grid.items() if c.kind != LAKE}
                if not land:
                    continue
                west, north = {}, {}
                for c, r in land:
                    west[r] = min(west.get(r, 1 << 30), c)
                    north[c] = min(north.get(c, 1 << 30), r)
                for d in (west, north):
                    keys = sorted(d)
                    n = 1
                    for a, b in zip(keys, keys[1:]):
                        if b == a + 1 and d[b] == d[a]:
                            n += 1
                        else:
                            runs.append(n)
                            n = 1
                    runs.append(n)
        return runs

    def test_the_shore_is_not_ruled_straight(self):
        runs = self._shores()
        long_ = sum(1 for n in runs if n >= 5) / len(runs)
        self.assertLess(long_, 0.20,
                        f"{long_ * 100:.0f}% of shore runs are 5+ tiles")

    def test_no_island_is_a_rectangle(self):
        for seed in range(1, 6):
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                land = {p for p, c in room.grid.items() if c.kind != LAKE}
                if not land:
                    continue
                cs = [p[0] for p in land]
                rs = [p[1] for p in land]
                box = (max(cs) - min(cs) + 1) * (max(rs) - min(rs) + 1)
                self.assertLess(len(land) / box, 0.95,
                                f"seed {seed} room {room.id} is a rectangle")

    def test_a_capped_run_is_really_capped(self):
        """The clamp can hand back the same value and silently defeat the cap,
        which is why `_walk` forces a move when it does."""
        import random
        cap = config.HEIGHTMAP_COAST_PRESETS["rugged"]["run_cap"]
        for seed in range(30):
            got = _walk(60, random.Random(seed), 6, (2, 3), cap)
            n = 1
            for a, b in zip(got, got[1:]):
                n = n + 1 if a == b else 1
                self.assertLessEqual(n, cap, f"seed {seed}: {got}")


class TopographyTests(_Heightmap):
    """LD-10: an island's *shape* type, declared as a table.

    Orthogonal to room kind -- kind says what happens on an island, topography
    says what shape it is, so a shrine can stand on a small one. Declared in
    `config.HEIGHTMAP_TOPOGRAPHIES` in the spirit of `SPECIAL_KINDS`: adding a
    "castle" is a table entry naming a squarer coast preset, not new code.
    """

    def _rooms(self, seeds=range(1, 9)):
        for seed in seeds:
            for room in generate_world(seed).rooms:
                if room.grid:
                    yield seed, room

    def test_every_island_gets_one(self):
        for seed, room in self._rooms():
            self.assertIn(room.topography, config.HEIGHTMAP_TOPOGRAPHIES,
                          f"seed {seed} room {room.id}")

    def test_the_boss_island_is_flat(self):
        """Flat is the half of "big and relatively flat" that can be delivered
        today. **Big cannot**: `size` may not take a room past the chunk plus
        two tiles without breaking the packing guarantee, so the boss is capped
        at 1.0 like everything else and comes out around its neighbours' size.
        A genuinely larger boss island needs either a bigger lattice cell or a
        per-topography `HEIGHTMAP_COAST_KEEP`, and boss islands are a deferred
        conversation -- so this asserts only what is actually true."""
        for seed in range(1, 9):
            layout = generate_world(seed)
            boss = layout.room(layout.boss_id)
            if not boss.grid:
                continue
            self.assertEqual(boss.topography, config.HEIGHTMAP_BOSS_TOPOGRAPHY)
            levels = {c.level for c in boss.grid.values() if c.kind == GROUND}
            self.assertEqual(levels, {0}, f"seed {seed}: boss island is terraced")

    def test_a_volcanic_island_can_be_two_floors_as_well_as_three(self):
        """The case the old generator had no way to express: it was a coin flip
        between all three floors and one, with nothing in between."""
        tops = set()
        for _seed, room in self._rooms():
            if room.topography == "volcanic":
                tops.add(max(c.level for c in room.grid.values()
                             if c.kind == GROUND))
        self.assertIn(1, tops, "no two-floor volcanic island in eight worlds")
        self.assertIn(2, tops, "no three-floor volcanic island in eight worlds")

    def test_a_small_island_never_exceeds_two_floors(self):
        for seed, room in self._rooms():
            if room.topography != "small":
                continue
            top = max(c.level for c in room.grid.values() if c.kind == GROUND)
            self.assertLessEqual(top, 1, f"seed {seed} room {room.id}")

    def test_a_small_island_is_about_half_a_volcanic_one(self):
        """`size` is a linear scale on the rect, not an area ratio -- the coast
        margin is an absolute number of tiles, so it eats proportionally more of
        a smaller island. 0.76 linear measures out at about half the walkable
        area; 0.7 gave 0.38."""
        by = {}
        for _seed, room in self._rooms():
            by.setdefault(room.topography, []).append(
                sum(1 for c in room.grid.values() if c.kind == GROUND))
        small = sum(by["small"]) / len(by["small"])
        volcanic = sum(by["volcanic"]) / len(by["volcanic"])
        self.assertGreater(small / volcanic, 0.40)
        self.assertLess(small / volcanic, 0.60)

    def test_topography_and_kind_are_independent(self):
        """If they were not, this table would just be `SPECIAL_KINDS` again."""
        seen = {(r.topography, r.kind) for _s, r in self._rooms()}
        shapes = {t for t, _k in seen}
        self.assertGreater(len(shapes), 1)
        for shape in shapes - {config.HEIGHTMAP_BOSS_TOPOGRAPHY}:
            kinds = {k for t, k in seen if t == shape}
            self.assertGreater(len(kinds), 1,
                               f"every {shape} island has the same room kind")

    def test_elite_arenas_are_gone_from_the_height_map_worlds(self):
        for seed, room in self._rooms():
            self.assertNotEqual(room.kind, "elite_arena", f"seed {seed}")

    def test_but_the_legacy_generator_still_has_them(self):
        """Dropping a kind there re-labels its rooms, and a re-labelled room is
        shaped and scattered differently -- which moved four pinned-seed LD-8
        tests that have nothing to do with elite arenas."""
        saved = config.HEIGHTMAP_ROOMS
        try:
            config.HEIGHTMAP_ROOMS = False
            kinds = {r.kind for s in range(12) for r in generate_world(s).rooms}
        finally:
            config.HEIGHTMAP_ROOMS = saved
        self.assertIn("elite_arena", kinds)


class PlacementTests(_Heightmap):
    """LD-10 D: more islands, off-centre in their cells, with a per-topography
    bridge allowance."""

    def _sides(self, layout):
        """`(room id, side) -> bridges landing there`."""
        out = {}
        for c in layout.corridors:
            a, b = layout.room(c.a), layout.room(c.b)
            for room, other in ((a, b), (b, a)):
                if c.axis == "h":
                    side = "e" if other.rect.centerx > room.rect.centerx else "w"
                else:
                    side = "s" if other.rect.centery > room.rect.centery else "n"
                out[(room.id, side)] = out.get((room.id, side), 0) + 1
        return out

    def test_no_two_islands_share_a_land_cell(self):
        """The packing guarantee, and the reason the offset is bounded against
        the *chunk* rather than against a slack derived from the nominal sizes.
        Deriving it let an odd-width room stack an offset on top of the
        half-tile the snap had already moved it, and two islands met."""
        px = config.TILE_PX
        for seed in range(1, 13):
            cells = {}
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                for (c, r), cell in room.grid.items():
                    if cell.kind == LAKE:
                        continue
                    key = ((int(room.rect.left) // px) + c,
                           (int(room.rect.top) // px) + r)
                    self.assertNotIn(key, cells,
                                     f"seed {seed}: rooms {cells.get(key)} and "
                                     f"{room.id} share land at {key}")
                    cells[key] = room.id

    def test_no_two_rects_overlap_by_more_than_two_tiles(self):
        """The invariant the packing rests on, stated between the rooms rather
        than against their cells -- the world is shifted to the origin at the
        end of generation, so a room's rect no longer sits where
        `_cell_rect(room.cell)` says. Two tiles is what a full-size room's
        one-tile overhang gives on each side, and `HEIGHTMAP_COAST_KEEP` holds
        each island's land that far inside its own rect."""
        px = config.TILE_PX
        for seed in range(1, 9):
            rooms = generate_world(seed).rooms
            for i, a in enumerate(rooms):
                for b in rooms[i + 1:]:
                    hit = a.rect.clip(b.rect)
                    if hit.width and hit.height:
                        self.assertLessEqual(min(hit.width, hit.height), 2 * px,
                                             f"seed {seed}: rooms {a.id} and "
                                             f"{b.id} overlap by "
                                             f"{min(hit.width, hit.height) / px:.0f}"
                                             f" tiles")

    def test_no_topography_can_outgrow_its_cell(self):
        """A guard on the table itself. The boss island was declared at 1.15,
        which put it five tiles outside its chunk and made it share land cells
        with its neighbour -- caught only because the offsets made it reliable
        rather than a matter of luck."""
        for name, spec in config.HEIGHTMAP_TOPOGRAPHIES.items():
            for room_max, chunk in ((config.HEIGHTMAP_ROOM_COLS[1],
                                     config.HEIGHTMAP_CHUNK_COLS),
                                    (config.HEIGHTMAP_ROOM_ROWS[1],
                                     config.HEIGHTMAP_CHUNK_ROWS)):
                self.assertLessEqual(room_max * spec["size"], chunk + 2,
                                     f"{name} can grow past its cell")

    def test_islands_are_not_all_centred_in_their_cells(self):
        """Otherwise the world reads as a grid however ragged the coasts get."""
        px = config.TILE_PX
        chunk = (config.HEIGHTMAP_CHUNK_COLS * px, config.HEIGHTMAP_CHUNK_ROWS * px)
        moved = 0
        for seed in range(1, 5):
            for room in generate_world(seed).rooms:
                if _cell_rect(room.cell, chunk).center != room.rect.center:
                    moved += 1
        self.assertGreater(moved, 0, "every island sits dead centre")

    def test_every_room_stays_on_the_world_tile_grid(self):
        px = config.TILE_PX
        for seed in range(1, 9):
            for room in generate_world(seed).rooms:
                self.assertEqual((int(room.rect.left) % px,
                                  int(room.rect.top) % px), (0, 0),
                                 f"seed {seed} room {room.id}")

    def test_a_side_never_carries_more_bridges_than_its_topography_allows(self):
        for seed in range(1, 13):
            layout = generate_world(seed)
            for (rid, side), n in self._sides(layout).items():
                cap = config.HEIGHTMAP_TOPOGRAPHIES[
                    layout.room(rid).topography]["bridges"]
                self.assertLessEqual(n, cap,
                                     f"seed {seed}: room {rid} side {side} has "
                                     f"{n} bridges")

    def test_a_small_island_never_takes_two_on_one_side(self):
        """Stated separately from the table check because it is the brief's own
        wording, and because it is the case the `min` of the two ends is doing
        the work: a small island linked to a volcanic one still gets one."""
        for seed in range(1, 13):
            layout = generate_world(seed)
            for (rid, _side), n in self._sides(layout).items():
                if layout.room(rid).topography == "small":
                    self.assertEqual(n, 1, f"seed {seed}: small room {rid}")

    def test_volcanic_islands_really_do_get_the_extra_one(self):
        """A cap nobody reaches is not a rule."""
        doubled = 0
        for seed in range(1, 13):
            layout = generate_world(seed)
            for (rid, _s), n in self._sides(layout).items():
                if n > 1 and layout.room(rid).topography == "volcanic":
                    doubled += 1
        self.assertGreater(doubled, 0, "no link ever carried two bridges")

    def test_the_world_is_still_one_piece(self):
        """Bridges are cloned and dropped here; the tree must survive it."""
        for seed in range(1, 13):
            layout = generate_world(seed)
            adj = {r.id: set() for r in layout.rooms}
            for c in layout.corridors:
                adj[c.a].add(c.b)
                adj[c.b].add(c.a)
            seen, stack = {layout.rooms[0].id}, [layout.rooms[0].id]
            while stack:
                for nb in adj[stack.pop()]:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            self.assertEqual(len(seen), len(layout.rooms), f"seed {seed}")


class LakeShapeTests(_Heightmap):
    def _lakes(self):
        for seed in _SEEDS:
            for room in generate_world(seed).rooms:
                if not room.grid:
                    continue
                cells = {p for p, c in room.grid.items() if c.kind == LAKE}
                for comp in _components(cells):
                    yield seed, room, comp

    def test_there_is_something_to_check(self):
        self.assertGreater(sum(1 for _ in self._lakes()), 0, "no lakes at all")

    def test_every_lake_is_at_least_three_contiguous_tiles(self):
        for seed, room, comp in self._lakes():
            self.assertGreaterEqual(len(comp), 3,
                                    f"seed {seed} room {room.id}: {sorted(comp)}")

    def test_every_lake_sits_on_one_terrace(self):
        for seed, room, comp in self._lakes():
            levels = {room.grid[p].level for p in comp}
            self.assertEqual(len(levels), 1,
                             f"seed {seed} room {room.id}: levels {levels}")

    def test_no_lake_has_a_trimmable_single_tile_arm(self):
        """The one-tile pond the rule is aimed at usually arrives as a spur off
        a larger blob, not as a lake of its own.

        The invariant is that every shipped lake is a **fixed point** of the
        trim, not that no lake has a leaf -- some shapes are all leaves and
        cannot be trimmed at all. A line or an L of three is the obvious case;
        so is a four-cell T, whose three outer cells are every one of them an
        end. Asserting "no leaves" instead fails on exactly those, which is the
        rule forbidding the shapes the brief allows.
        """
        for seed, room, comp in self._lakes():
            self.assertEqual(_trim_lake_stubs(set(comp)), comp,
                             f"seed {seed} room {room.id}: {sorted(comp)} still "
                             f"has an arm the trim would take")


if __name__ == "__main__":
    unittest.main()
