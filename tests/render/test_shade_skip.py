"""RND-010.7: the shade walk returns early where no shade can fall
(`world/terrain/render.py`, `shade_character_frame`; `crowd_draw_journal.md`).

The walk now works out the index cells a frame spans first and hands the
frame back at once when none holds a shadow. Pinned against the walk as it
was before (`_walk_before`, kept here word for word), on seed 35's packed
fight scene:
* every drawn body gets back the very object it did;
* over a sweep of camera positions across the island, frames of three sizes
  laid on a grid over the view, standing in front of and behind the trees,
  get back the very object where the old walk returned the frame, and the
  same bytes where it shaded it; the sweep must meet both cases, and the
  early return, many times;
* the skip is what returns them: the walk's own loop never runs for a
  frame whose cells hold no shadow.
"""
import contextlib
import io
import unittest
from unittest import mock

import pygame

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import draw_leads as DLe
from tools.benchmarks import layer_probes as LP

SEED = 35


def _walk_before(self, frame, dest, camera, character_y):
    """`TerrainRenderer.shade_character_frame` before RND-010.7."""
    shadows = self.gm._tree_shadows
    if not shadows:
        return frame
    frame_rect = frame.get_rect(topleft=(int(dest[0]), int(dest[1])))
    z = self.gm._render_zoom
    ox, oy = camera.pos.x, camera.pos.y
    c = self._SHADE_CELL
    wx0, wy0 = ox + frame_rect.left / z, oy + frame_rect.top / z
    wx1, wy1 = ox + frame_rect.right / z, oy + frame_rect.bottom / z
    index = self._shadow_index()
    overlay = shaded = None
    seen: set = set()
    for gx in range(int(wx0 // c), int(wx1 // c) + 1):
        for gy in range(int(wy0 // c), int(wy1 // c) + 1):
            for shadow in index.get((gx, gy), ()):
                key = id(shadow)
                if key in seen:
                    continue
                seen.add(key)
                wx, wy, r, shade = shadow
                if character_y < wy - 0.01:
                    continue
                scaled = self._z_surf(shade)
                shade_rect = scaled.get_rect(topleft=(
                    round((wx - ox) * z - r * z),
                    round((wy - oy) * z - r * z),
                ))
                if not frame_rect.colliderect(shade_rect):
                    continue
                if overlay is None:
                    overlay, shaded = self._scratch(frame.get_size())
                overlay.blit(scaled, (shade_rect.x - frame_rect.x,
                                      shade_rect.y - frame_rect.y))
    if overlay is None:
        return frame
    overlay.blit(frame, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    shaded.blit(frame, (0, 0))
    shaded.blit(overlay, (0, 0))
    return shaded


class ShadeSkipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.game, cls.ps = LP.packed_scene(SEED, 60, 0, 300.0, TDL._fresh_save())
        cls.terrain = cls.ps.run.game_map.renderer
        cls.cam = cls.ps.run.camera

    def _both(self, frame, dest, character_y):
        """(the walk now, the walk before) on the same arguments; the
        before's shaded result copied, since both share the scratch."""
        t = self.terrain
        now = t.shade_character_frame(frame, dest, self.cam, character_y)
        now = now if now is frame else now.copy()
        before = _walk_before(t, frame, dest, self.cam, character_y)
        return now, before

    def _same(self, frame, now, before):
        if before is frame:
            self.assertIs(now, frame)
            return "plain"
        self.assertIsNot(now, frame)
        self.assertEqual(pygame.image.tobytes(now, "RGBA"), pygame.image.tobytes(before, "RGBA"))
        return "shaded"

    def test_every_drawn_body_gets_back_what_it_did(self):
        ren, cam = self.ps.renderer, self.cam
        z = cam.zoom
        bodies = DLe.drawn_enemies(self.ps)
        self.assertGreater(len(bodies), 20)
        for e in bodies:
            frame, flip = ren.rig_frame(e.anim, e._facing, z)
            ax, ay = ren.anchor_for(e.anim.rig, flip)
            sx, sy = cam.world_to_screen(e.pos)
            dest = (sx - ax * z, sy - ay * z + ren.sprite_drop(e.radius))
            with self.subTest(enemy=e.enemy_id, at=(round(e.pos.x), round(e.pos.y))):
                self._same(frame, *self._both(frame, dest, e.pos.y))

    def test_a_sweep_over_the_island_meets_every_case_and_agrees(self):
        cam, t = self.cam, self.terrain
        shadows = list(t.gm._tree_shadows.values())
        self.assertGreater(len(shadows), 10)
        frames = []
        for size in ((24, 30), (70, 64), (160, 150)):
            f = pygame.Surface(size, pygame.SRCALPHA)
            f.fill((180, 90, 40, 255))
            pygame.draw.circle(f, (0, 0, 0, 0), (size[0] // 3, size[1] // 3), size[0] // 5)
            frames.append(f)
        # Cameras centred on a spread of the trees, and on open ground
        # between them, so whole views fall where no shade is.
        xs = sorted(s[0] for s in shadows)
        ys = sorted(s[1] for s in shadows)
        centres = [(s[0], s[1]) for s in shadows[::max(1, len(shadows) // 12)]]
        centres += [(xs[0] - 900, ys[0] - 900), ((xs[0] + xs[-1]) / 2, ys[-1] + 700)]
        home = cam.pos.copy()
        tally = {"plain": 0, "shaded": 0}
        try:
            for cx, cy in centres:
                cam.pos.update(cx - 640 / cam.zoom, cy - 360 / cam.zoom)
                for f in frames:
                    for dx in range(-150, 1300, 97):
                        for dy in range(-150, 800, 89):
                            wy = cam.pos.y + (dy + f.get_height()) / cam.zoom
                            for character_y in (wy - 300, wy, wy + 300):
                                kind = self._same(f, *self._both(f, (dx + 0.6, dy + 0.3), character_y))
                                tally[kind] += 1
        finally:
            cam.pos.update(home)
        self.assertGreater(tally["shaded"], 100, tally)
        self.assertGreater(tally["plain"], 1000, tally)

    def test_the_skip_is_what_returns_a_frame_with_no_shade_in_its_cells(self):
        # Under no tree: the index is asked for no shadow list at all.
        cam, t = self.cam, self.terrain
        shadows = list(t.gm._tree_shadows.values())
        far = (min(s[0] for s in shadows) - 5000, min(s[1] for s in shadows) - 5000)
        home = cam.pos.copy()
        frame = pygame.Surface((60, 60), pygame.SRCALPHA)
        index = t._shadow_index()
        try:
            cam.pos.update(far)
            with mock.patch.object(t, "_shadow_index", return_value=mock.MagicMock(wraps=index)) as m:
                spy = m.return_value
                spy.__contains__.side_effect = index.__contains__
                self.assertIs(t.shade_character_frame(frame, (100, 100), cam, far[1] + 10), frame)
            spy.get.assert_not_called()                      # the walk's loop never ran
            self.assertGreater(spy.__contains__.call_count, 0)
        finally:
            cam.pos.update(home)


if __name__ == "__main__":
    unittest.main()
