"""RND-010.7: the shade walk's early return, timed in shapes against the walk
before, in one process on the packed scene's own drawn bodies (headless:
the unshaded path draws no pixels).

`before` is the walk (`tests/render/test_shade_skip.py`'s
`_walk_before`); `any_skip` is RND-010.7.2's skip as built; `one_cell` adds
a fast path for a frame inside one index cell; `bare` is only what every
shape must do anyway (the call, the zoom, the camera and the cell
arithmetic), the floor no skip can go under. Each round times each shape
over every drawn body, the order rotated, and the p50 per call is printed.
A measurement tool, not game code. From the repo root:
    python documentation/journals/data/rnd-010.7/walk_shapes.py 250 600
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())

from tests.render.test_shade_skip import _walk_before
from tools.benchmarks import draw_leads as DLe
from tools.benchmarks import layer_probes as LP
from tools.benchmarks.stats import percentile


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
    return self.shade_character_frame(frame, dest, camera, character_y)


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
                    return self.shade_character_frame(frame, dest, camera, character_y)
        return frame
    return self.shade_character_frame(frame, dest, camera, character_y)


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
z = cam.zoom
args = []
for e in DLe.drawn_enemies(ps):
    frame, flip = ren.rig_frame(e.anim, e._facing, z)
    ax, ay = ren.anchor_for(e.anim.rig, flip)
    sx, sy = cam.world_to_screen(e.pos)
    dest = (sx - ax * z, sy - ay * z + ren.sprite_drop(e.radius))
    if _walk_before(t, frame, dest, cam, e.pos.y) is frame:      # the unshaded bodies only
        args.append((frame, dest, e.pos.y))
shapes = {"before": lambda a: _walk_before(t, a[0], a[1], cam, a[2]),
          "any_skip": lambda a: any_skip(t, a[0], a[1], cam, a[2]),
          "one_cell": lambda a: one_cell(t, a[0], a[1], cam, a[2]),
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
print(f"{live}: {len(args)} unshaded bodies, 400 rounds")
for n in names:
    us = percentile(sorted(samples[n]), 0.5)
    print(f"    {n:9s} {us:5.2f} us a call, {us * len(args) / 1000:5.3f} ms a frame")
