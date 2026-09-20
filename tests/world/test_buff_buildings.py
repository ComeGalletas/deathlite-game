"""Buff buildings (journal: buff_buildings_journal.md): two to five
interactive buildings per island, seated by `world/gen/buildings.py` right
after the houses, dressed by `world/terrain/decor/dressing.py` at bake time.

Reads the shared cached worlds; the placement rules hold for every seed, so
the pinned four are enough. Determinism is `test_digest.py`'s job.
"""
import unittest

from game import config
from game.content import get_content
from tests import worlds as W
from world.gen.tuning import VILLAGE_KIND
from world.layout import VSTAIR, EWSTAIR

PX = config.TILE_PX


def _data():
    return get_content().buildings


def _kinds():
    return tuple(_data()["buffs"])


def _room_of(w, o):
    for room in w.rooms:
        if room.rect.collidepoint(o.pos.x, o.pos.y):
            return room
    return None


def _eligible(w):
    place = _data()["placement"]
    return [r for r in w.rooms
            if r.id != w.boss_id and r.kind != VILLAGE_KIND
            and len(r.cells) >= place["min_room_cells"]
            and min(r.rect.width, r.rect.height) >= place["min_room_tiles"] * PX]


def _per_room(w):
    out = {}
    for o in w.buff_buildings(_kinds()):
        out.setdefault(_room_of(w, o).id, []).append(o)
    return out


class PlacementTests(unittest.TestCase):
    def test_every_eligible_island_seats_two_to_five(self):
        """The pass draws `lo..hi` per island. What it seats can fall short
        of `lo`: the cluster rule (rev. 6) spreads buildings 500 px apart
        in pairs at most, which a small island cannot always hold, and the
        unseal repair may take one back where it sealed a route (seed 42,
        island 6, loses its cave). Never none on an eligible island, never
        more than `hi`, and most islands reach `lo`."""
        lo, hi = _data()["placement"]["per_island"]
        for seed in W.SEEDS:
            w = W.layout(seed)
            per = _per_room(w)
            rooms = _eligible(w)
            short = 0
            for room in rooms:
                n = len(per.get(room.id, ()))
                self.assertTrue(1 <= n <= hi,
                                f"island {room.id} has {n} buildings (seed {seed})")
                short += n < lo
            self.assertLessEqual(short, max(1, len(rooms) // 2),
                                 f"seed {seed}: {short} islands under {lo}")

    def test_never_more_than_two_close_together(self):
        """Rev. 6: inside the cluster ring round any building at most one
        other building stands."""
        place = _data()["placement"]
        ring2 = place["cluster_ring_px"] ** 2
        max_nb = place["cluster_max_neighbours"]
        for seed in W.SEEDS:
            w = W.layout(seed)
            prim = w.buff_buildings(_kinds())
            for o in prim:
                near = [q for q in prim if q is not o
                        and (q.pos - o.pos).length_squared() < ring2]
                self.assertLessEqual(len(near), max_nb,
                                     f"{o.kind} has {len(near)} neighbours inside the "
                                     f"ring (seed {seed})")

    def test_the_mushroom_tower_has_its_hut(self):
        """Rev. 6: the Haste tower's company includes the gnome hut, a
        colliding, non-interactive obstacle on its ring."""
        ring_hi = _data()["placement"]["dressing_ring_tiles"][1] * PX + 1.0
        seen = 0
        for seed in W.SEEDS:
            w = W.layout(seed)
            for o in w.buff_buildings(_kinds()):
                if o.kind != "haste":
                    continue
                huts = [q for q in w.obstacles if q.kind == "gnome_hut"
                        and (q.pos - o.pos).length() <= ring_hi]
                seen += len(huts)
            self.assertFalse(any(it.kind == "gnome_hut" for it in ()))
        self.assertGreater(seen, 0, "no tower got its hut on the pinned seeds")

    def test_kinds_never_repeat_on_an_island(self):
        for seed in W.SEEDS:
            for rid, buildings in _per_room(W.layout(seed)).items():
                kinds = [o.kind for o in buildings]
                self.assertEqual(len(kinds), len(set(kinds)),
                                 f"island {rid} repeats a kind: {kinds} (seed {seed})")

    def test_never_on_the_village_or_the_boss_island(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for o in w.buff_buildings(_kinds()):
                room = _room_of(w, o)
                self.assertIsNotNone(room)
                self.assertNotEqual(room.kind, VILLAGE_KIND, f"seed {seed}")
                self.assertNotEqual(room.id, w.boss_id, f"seed {seed}")

    def test_buildings_stand_inland_and_off_the_flights(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for o in w.buff_buildings(_kinds()):
                room = _room_of(w, o)
                col = int((o.pos.x - room.rect.left) // PX)
                row = int((o.pos.y - room.rect.top) // PX)
                for dc in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        self.assertIn((col + dc, row + dr), room.cells,
                                      f"building at the island's edge (seed {seed})")
                cell = room.grid.get((col, row))
                self.assertNotIn(cell.kind, (VSTAIR, EWSTAIR), f"on a flight (seed {seed})")

    def test_buildings_keep_a_ring_from_each_other(self):
        gap = _data()["placement"]["building_gap_tiles"] * PX
        for seed in W.SEEDS:
            for rid, buildings in _per_room(W.layout(seed)).items():
                for i, a in enumerate(buildings):
                    for b in buildings[i + 1:]:
                        self.assertGreaterEqual(
                            (a.pos - b.pos).length(), gap - 1e-6,
                            f"two buildings crowd on island {rid} (seed {seed})")

    def test_the_layout_lists_them_by_kind(self):
        w = W.layout(W.SEEDS[0])
        listed = w.buff_buildings(_kinds())
        self.assertEqual(listed, [o for o in w.obstacles
                                  if o.kind in _kinds() and o.skin])
        self.assertGreater(len(listed), 0)

    def test_the_wide_buildings_stand_on_a_two_tile_base(self):
        """The dead tree, the two towers and the cave (owner, 2026-09-20)
        draw two tiles wide and their base is a compound: a primary plus a
        satellite either side, the satellites collide-only and never listed
        as buildings."""
        for seed in W.SEEDS:
            w = W.layout(seed)
            for b in w.buff_buildings(_kinds()):
                if b.kind not in ("vampire", "turbo", "haste", "pinball", "magnet"):
                    continue
                sats = [o for o in w.obstacles if o.kind == b.kind and not o.skin
                        and abs(o.pos.y - b.pos.y) < 8 and abs(o.pos.x - b.pos.x) < 40]
                self.assertEqual(len(sats), 2, f"{b.kind} without its base (seed {seed})")
                self.assertGreaterEqual(max(o.pos.x for o in sats) - min(o.pos.x for o in sats), 48)


class DressingTests(unittest.TestCase):
    def test_each_building_is_dressed(self):
        """The bake seats at least one prop on every building's ring."""
        ring_hi = _data()["placement"]["dressing_ring_tiles"][1] * PX + 1.0
        for seed in W.SEEDS:
            gm = W.baked(seed)
            for o in gm.layout.buff_buildings(_kinds()):
                room = _room_of(gm.layout, o)
                near = [inst for inst in gm._room_decor.get(room.id, ())
                        if (inst[4] - o.pos.x) ** 2 + (inst[5] - o.pos.y) ** 2 <= ring_hi ** 2]
                self.assertTrue(near, f"{o.kind} on island {room.id} is bare (seed {seed})")

    def test_every_building_is_skinned(self):
        for seed in W.SEEDS:
            gm = W.baked(seed)
            for i, o in enumerate(gm.obstacles):
                if o.kind in _kinds() and o.skin:      # a satellite collides only
                    self.assertIn(i, gm._decos, f"{o.kind} has no skin (seed {seed})")


if __name__ == "__main__":
    unittest.main()
