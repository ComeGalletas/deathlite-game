"""RND-010.7: where the shade walk's time goes on the bodies no shade falls
on, and shapes of an early return timed against the walk, in one process
on the packed scene's own drawn bodies (headless: the unshaded path draws
no pixels).

The unshaded bodies are split by the walk's own 256 px index cells: those
whose cells are all empty (the walk's loop finds no shadow list at all)
and those touching an occupied cell (the walk tests the shadows there and
finds none that falls on them). The shapes, each over the unshaded bodies:
* `before`: the walk (`tests/render/test_shade_walk_pin.py`'s `_walk_before`);
* `any_skip`: RND-010.7.2's skip as built (`0450ac9`), then the walk;
* `one_cell`: a fast path for a frame inside one index cell, then the walk;
* `fine`: an exact early return on a finer occupancy grid (`FINE` world px
  cells, every cell a shade disc's box touches, padded a cell), then the
  walk; checked against the walk on every drawn body before it is timed;
* `bare`: the call, the zoom, the camera and the cell arithmetic and
  nothing else, an approximate floor: a correct skip also pays the index's
  validity check, which this leaves out, and a skip at the caller would
  save part of the call, which this keeps.
Each round times each shape over every unshaded body, the order rotated;
the p50 per call is printed. A measurement tool, not game code. From the
repo root:
    python documentation/journals/data/rnd-010.7/walk_shapes.py 250 600
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())

from tests.render.test_shade_walk_pin import _walk_before
from tools.benchmarks import draw_leads as DLe
from tools.benchmarks import layer_probes as LP
from tools.benchmarks.stats import percentile

FINE = 64          # world px


def any_skip(self, frame, dest, camera, character_y):
    """RND-010.7.2's skip as it was built (`0450ac9`), up to its early
    return; past it, the walk itself."""
    shadows = self.gm._tree_shadows
    if not shadows:
        return frame
    z = self.gm._render_zoom
    ox, oy = camera.pos.x, camera.pos.y
    left, top = int(dest[0]), int(dest[1])
    w, h = frame.get_size()
    c = self._SHADE_CELL
    gx0, gx1 = int((ox + left / z) // c), int((ox + (left + w) / z) // c)
    gy0, gy1 = int((oy + top / z) // c), int((oy + (top + h) / z) // c)
    index = self._shadow_index()
    for gx in range(gx0, gx1 + 1):
        if any((gx, gy) in index for gy in range(gy0, gy1 + 1)):
            break
    else:
        return frame
    return _walk_before(self, frame, dest, camera, character_y)


def one_cell(self, frame, dest, camera, character_y):
    shadows = self.gm._tree_shadows
    if not shadows:
        return frame
    z = self.gm._render_zoom
    pos = camera.pos
    left, top = int(dest[0]), int(dest[1])
    w, h = frame.get_size()
    c = self._SHADE_CELL
    gx0, gx1 = int((pos.x + left / z) // c), int((pos.x + (left + w) / z) // c)
    gy0, gy1 = int((pos.y + top / z) // c), int((pos.y + (top + h) / z) // c)
    index = self._shadow_index()
    if gx0 == gx1 and gy0 == gy1:
        if (gx0, gy0) not in index:
            return frame
    else:
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                if (gx, gy) in index:
                    return _walk_before(self, frame, dest, camera, character_y)
        return frame
    return _walk_before(self, frame, dest, camera, character_y)


def fine_cells(self) -> set:
    """Every `FINE` cell a shade disc's box touches, padded one cell."""
    cells = set()
    for wx, wy, r, _s in self.gm._tree_shadows.values():
        for gx in range(int((wx - r) // FINE) - 1, int((wx + r) // FINE) + 2):
            for gy in range(int((wy - r) // FINE) - 1, int((wy + r) // FINE) + 2):
                cells.add((gx, gy))
    return cells


def fine(self, frame, dest, camera, character_y, cells):
    if not cells:
        return frame
    z = self.gm._render_zoom
    pos = camera.pos
    left, top = int(dest[0]), int(dest[1])
    w, h = frame.get_size()
    gx0, gx1 = int((pos.x + left / z) // FINE), int((pos.x + (left + w) / z) // FINE)
    gy0, gy1 = int((pos.y + top / z) // FINE), int((pos.y + (top + h) / z) // FINE)
    for gx in range(gx0, gx1 + 1):
        for gy in range(gy0, gy1 + 1):
            if (gx, gy) in cells:
                return _walk_before(self, frame, dest, camera, character_y)
    return frame


def bare(self, frame, dest, camera, character_y):
    shadows = self.gm._tree_shadows
    if not shadows:
        return frame
    z = self.gm._render_zoom
    pos = camera.pos
    left, top = int(dest[0]), int(dest[1])
    w, h = frame.get_size()
    c = self._SHADE_CELL
    int((pos.x + left / z) // c), int((pos.x + (left + w) / z) // c)
    int((pos.y + top / z) // c), int((pos.y + (top + h) / z) // c)
    return frame


live, elapsed = int(sys.argv[1]), float(sys.argv[2])
_game, ps = LP.packed_scene(35, live, 400, elapsed, None)
t, ren, cam = ps.run.game_map.renderer, ps.renderer, ps.run.camera
z, zz, c = cam.zoom, t.gm._render_zoom, t._SHADE_CELL
index, cells = t._shadow_index(), fine_cells(t)
drawn, empty, occupied = [], [], []
for e in DLe.drawn_enemies(ps):
    frame, flip = ren.rig_frame(e.anim, e._facing, z)
    ax, ay = ren.anchor_for(e.anim.rig, flip)
    sx, sy = cam.world_to_screen(e.pos)
    dest = (sx - ax * z, sy - ay * z + ren.sprite_drop(e.radius))
    a = (frame, dest, e.pos.y)
    drawn.append(a)
    if _walk_before(t, frame, dest, cam, e.pos.y) is not frame:
        continue                                     # shaded: no skip applies
    w, h = frame.get_size()
    xs = range(int((cam.pos.x + int(dest[0]) / zz) // c), int((cam.pos.x + (int(dest[0]) + w) / zz) // c) + 1)
    ys = range(int((cam.pos.y + int(dest[1]) / zz) // c), int((cam.pos.y + (int(dest[1]) + h) / zz) // c) + 1)
    (occupied if any((gx, gy) in index for gx in xs for gy in ys) else empty).append(a)
args = empty + occupied
for f, d, y in drawn:                                # every shape exact before it is timed
    want = _walk_before(t, f, d, cam, y) is f
    for shape in (any_skip, one_cell):
        assert (shape(t, f, d, cam, y) is f) == want, shape.__name__
    assert (fine(t, f, d, cam, y, cells) is f) == want, "fine"
early = sum(1 for f, d, y in args
            if all((gx, gy) not in cells
                   for gx in range(int((cam.pos.x + int(d[0]) / zz) // FINE),
                                   int((cam.pos.x + (int(d[0]) + f.get_width()) / zz) // FINE) + 1)
                   for gy in range(int((cam.pos.y + int(d[1]) / zz) // FINE),
                                   int((cam.pos.y + (int(d[1]) + f.get_height()) / zz) // FINE) + 1)))
shapes = {"before": lambda a: _walk_before(t, a[0], a[1], cam, a[2]),
          "any_skip": lambda a: any_skip(t, a[0], a[1], cam, a[2]),
          "one_cell": lambda a: one_cell(t, a[0], a[1], cam, a[2]),
          "fine": lambda a: fine(t, a[0], a[1], cam, a[2], cells),
          "bare": lambda a: bare(t, a[0], a[1], cam, a[2])}
names = list(shapes)
samples = {n: [] for n in names}
for r in range(400):
    for n in names[r % len(names):] + names[:r % len(names)]:
        fn = shapes[n]
        t0 = time.perf_counter()
        for a in args:
            fn(a)
        samples[n].append((time.perf_counter() - t0) * 1e6 / len(args))
print(f"{live}: {len(args)} unshaded bodies of {len(drawn)} drawn: {len(empty)} with every index cell "
      f"empty, {len(occupied)} touching an occupied one; the {FINE} px grid returns early for {early}; "
      f"400 rounds")
for n in names:
    us = percentile(sorted(samples[n]), 0.5)
    print(f"    {n:9s} {us:5.2f} us a call, {us * len(args) / 1000:5.3f} ms a frame")
