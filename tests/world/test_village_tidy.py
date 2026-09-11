"""LD-Z: the village tidy pass (`world/gen/village_tidy.py`).

What the layout pass leaves, made clean: nothing paints over the forge,
the heal zone or the town hall; no building paints over another; the heal
has company; the roads bend onto the street rather than cutting the
square. Painted boxes are read the way the pass reads them -- the rigs'
measured `paint` boxes through `frontier.paint_reach` -- so the test and
the generator agree by construction, and a separate test pins the boxes
to the sheets so neither can drift from the art.

Reads the shared cached worlds.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game import config
from game.content import get_content
from tests import worlds as W
from world.gen.tuning import (
    _V_ART_TOL, _V_CLUSTER_MAX, _V_HEAL_COMPANY, _V_HEAL_NEAR, _V_HEAL_RADIUS,
    _V_PEN_SCALE, _V_STREET_REACH,
)
from world.gen.village_tidy import BUILDINGS, KEY, clips
from world.rules import frontier as F

VILLAGE_RIGS = ("forge", "fx_heal", "monastery_", "house_", "barracks_", "tower_",
                "archery_", "fence_")


def _reach():
    return F.paint_reach(get_content().terrain, config.SPRITE_ANCHOR_DROP)


def _box(reach, kind, x, y):
    n, s, w, e = reach[kind]
    return pygame.Rect(round(x - w), round(y - n), round(w + e), round(n + s))


def _heal_box(x, y):
    n, s, w, e = F.paint_box(get_content().terrain["rigs"]["fx_heal"], 1.0)
    box = pygame.Rect(round(x - w), round(y - n), round(w + e), round(n + s))
    r = _V_HEAL_RADIUS
    return box.union(pygame.Rect(round(x - r), round(y - r), round(2 * r), round(2 * r)))


def _on(w, v):
    room = w.room(v.room_id)
    return [o for o in w.obstacles
            if room.rect.collidepoint(o.pos.x, o.pos.y) and getattr(o, "skin", True)]


class PaintBoxTests(unittest.TestCase):
    """The data the pass reads is true to the sheets."""

    def test_every_village_rig_declares_a_paint_box_inside_its_frame(self):
        rigs = get_content().terrain["rigs"]
        seen = 0
        for name, meta in rigs.items():
            if not name.startswith(VILLAGE_RIGS):
                continue
            seen += 1
            self.assertIn("paint", meta, name)
            x, y, w, h = meta["paint"]
            fw, fh = meta["frame"]
            self.assertTrue(0 <= x and 0 <= y and x + w <= fw and y + h <= fh, name)
            self.assertTrue(w > 0 and h > 0, name)
        self.assertGreaterEqual(seen, 40)

    def test_the_paint_box_is_the_opaque_bounding_box_of_the_sheet(self):
        """Measured, not typed: the box declared for a rig is what its
        frames actually paint, so the pass and the art cannot drift."""
        W.display()
        rigs = get_content().terrain["rigs"]
        for name in ("forge", "fx_heal", "house_blue_1", "monastery_red", "tower_blue",
                     "barracks_black", "archery_yellow", "fence_n1"):
            meta = rigs[name]
            anim = meta["anims"]["loop"]
            sheet = pygame.image.load(os.path.join("assets", anim["file"])).convert_alpha()
            fw, fh = meta["frame"]
            union = None
            for i in range(int(anim.get("frames", 1))):
                x, y = (i * fw, 0) if sheet.get_width() >= (i + 1) * fw else (0, i * fh)
                r = sheet.subsurface((x, y, fw, fh)).get_bounding_rect(min_alpha=8)
                union = r if union is None else union.union(r)
            self.assertEqual(tuple(union), tuple(meta["paint"]), name)

    def test_paint_reach_is_the_frame_reach_or_less(self):
        """The painted box sits inside the frame, so the painted reach
        north is never more than the frame reach the terrace rules use."""
        terrain = get_content().terrain
        frame = F.obstacle_reach(terrain)
        paint = _reach()
        for kind in BUILDINGS + ("fence",):
            n, s, w, e = paint[kind]
            fn, fw_, fe = frame[kind]
            # `paint_reach` includes the sprite drop (art shifted down), so
            # north can only be smaller; west and east are unaffected by it
            self.assertLessEqual(n, fn + 1e-6, kind)
            self.assertLessEqual(w, fw_ + 1e-6, kind)
            self.assertLessEqual(e, fe + 1e-6, kind)


class TidyTests(unittest.TestCase):
    """The three promises, over the pinned seeds."""

    def _villages(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                yield seed, w, v

    def test_nothing_paints_over_the_forge_the_heal_or_the_hall(self):
        reach = _reach()
        halls = 0
        for seed, w, v in self._villages():
            on = _on(w, v)
            protected = [_heal_box(v.heal.x, v.heal.y)]
            for o in on:
                if o.kind in KEY:
                    protected.append(_box(reach, o.kind, o.pos.x, o.pos.y))
                    halls += o.kind == "monastery"
            self.assertEqual(len(protected), 3, f"seed {seed}: forge, heal and hall expected")
            for o in on:
                if o.kind in KEY or o.kind not in reach:
                    continue
                box = _box(reach, o.kind, o.pos.x, o.pos.y)
                for p in protected:
                    self.assertFalse(clips(box, p, _V_ART_TOL),
                                     f"seed {seed}: {o.kind} at {o.pos} paints over the square")
        self.assertGreater(halls, 0)

    def test_no_building_paints_over_another(self):
        reach = _reach()
        pairs = 0
        for seed, w, v in self._villages():
            blds = [(o, _box(reach, o.kind, o.pos.x, o.pos.y))
                    for o in _on(w, v) if o.kind in BUILDINGS]
            self.assertGreaterEqual(len(blds), 4, f"seed {seed}: a bare village")
            for i, (a, ra) in enumerate(blds):
                for b, rb in blds[i + 1:]:
                    pairs += 1
                    self.assertFalse(clips(ra, rb, _V_ART_TOL),
                                     f"seed {seed}: {a.kind} paints over {b.kind}")
        self.assertGreater(pairs, 0)

    def test_the_heal_has_company(self):
        """Two buildings besides the forge and the hall within reach of the
        heal, and the record says how many."""
        px = config.TILE_PX
        for seed, w, v in self._villages():
            near = [o for o in _on(w, v)
                    if o.kind in BUILDINGS and o.kind not in KEY
                    and o.pos.distance_to(v.heal) <= _V_HEAL_NEAR * px]
            self.assertEqual(len(near), v.company, f"seed {seed}: the record disagrees")
            self.assertGreaterEqual(v.company, _V_HEAL_COMPANY,
                                    f"seed {seed}: the heal stands alone")
            # on both sides of the axis, not two on one flank
            self.assertTrue(any(o.pos.x < v.heal.x for o in near), f"seed {seed}: west flank empty")
            self.assertTrue(any(o.pos.x > v.heal.x for o in near), f"seed {seed}: east flank empty")

    def test_the_village_is_one_piece_round_its_square(self):
        px = config.TILE_PX
        for seed, w, v in self._villages():
            blds = [pygame.Vector2(x, y) for _k, x, y in v.buildings]
            for kind, x, y in v.buildings:
                if kind != "house":
                    continue
                h = pygame.Vector2(x, y)
                self.assertLessEqual(min(h.distance_to(b) for b in blds if b is not h),
                                     _V_CLUSTER_MAX * px, f"seed {seed}: a house stands alone")

    def test_the_roads_bend_onto_the_street(self):
        """A road reaches the forge along its own row: the last leg is
        horizontal, and the knee stands `_V_STREET_REACH` tiles or more
        from the axis -- so no road cuts the square north of the street."""
        from world.gen.village import _road
        px = config.TILE_PX
        for seed, w, v in self._villages():
            for m in v.mouths:
                legs = _road(pygame.Vector2(m), v.forge, px)
                a, b = legs[-1]
                self.assertEqual(b, v.forge)
                self.assertEqual(a.y, v.forge.y, f"seed {seed}: the last leg is not the street")
                if len(legs) == 2:
                    self.assertGreaterEqual(abs(a.x - v.forge.x), _V_STREET_REACH * px - 1e-6)

    def test_the_forge_heal_and_hall_never_move_or_go(self):
        """The protected three stand where the record says, whatever the
        pass did to the rest."""
        for seed, w, v in self._villages():
            on = _on(w, v)
            self.assertEqual([o.pos for o in on if o.kind == "forge"], [v.forge], f"seed {seed}")
            halls = [(k, x, y) for k, x, y in v.buildings if k == "monastery"]
            self.assertEqual(len(halls), 1, f"seed {seed}: no hall")
            self.assertEqual(halls[0][1], v.heal.x)


class CorralTests(unittest.TestCase):
    """The corral at 0.45: smaller fence, same sheep."""

    def test_the_fence_pitch_and_art_are_at_the_same_scale(self):
        self.assertEqual(_V_PEN_SCALE, 0.45)
        self.assertEqual(get_content().terrain["obstacle_decor"]["render_scale"]["fence"], 0.45)

    def test_the_interior_still_seats_the_sheep(self):
        """The pen's interior holds the sheep the placement wants -- their
        radius plus the placement's pad, and the rig is not scaled with
        the fence."""
        npcs = get_content().npcs
        sheep = npcs["kinds"]["sheep"]
        lo, hi = npcs["placement"]["sheep"]
        pad = sheep["radius"] + 4
        rig = get_content().sprites["npc_sheep"]
        self.assertEqual(list(rig["scale"]), [24, 21])
        pens = 0
        for seed in W.SEEDS:
            for v in W.layout(seed).villages:
                self.assertIsNotNone(v.pen, f"seed {seed}: no pen")
                pens += 1
                self.assertGreater(v.pen.width, 2 * pad)
                self.assertGreater(v.pen.height, 2 * pad)
                # room for `hi` sheep standing apart
                self.assertGreaterEqual(v.pen.width * v.pen.height,
                                        hi * (2 * sheep["radius"]) ** 2, f"seed {seed}")
        self.assertGreater(pens, 0)
