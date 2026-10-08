"""Throwaway: what the RLE copies hold after a packed fight (decoded size)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())

from game.states.playing.visual.elements import rle
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S

live, elapsed = int(sys.argv[1]), float(sys.argv[2])
_game, ps = LP.packed_scene(35, live, 400, elapsed, None, elements=True)
S.run(ps, 640, render=True)
copies = [c for f, c in rle._COPIES.values() if c is not f]
size = sum(c.get_width() * c.get_height() * 4 for c in copies)
big = max((c.get_width() * c.get_height() * 4 for c in copies), default=0)
print(f"{live}: {len(rle._COPIES)} entries, {len(copies)} RLE copies, {size / 1e6:.1f} MB as pixels "
      f"(largest {big / 1e3:.0f} kB); cap {rle._CAP} x largest = {rle._CAP * big / 1e6:.1f} MB")
