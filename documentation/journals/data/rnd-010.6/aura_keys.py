"""Throwaway: how many distinct aura frames a packed fight asks for, and
how many auras are drawn per frame as it runs (the variant's cap is 256)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())

from game.states.playing.visual.elements.profiles import (
    ElementVisualProfile,
)
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S

live, elapsed = int(sys.argv[1]), float(sys.argv[2])
_game, ps = LP.packed_scene(35, live, 400, elapsed, None, elements=True)
real = ElementVisualProfile.aura_frame
seen, per_frame, calls = set(), [], [0]


def aura_frame(self, size=None):
    f = real(self, size=size)
    if f is not None:
        seen.add(id(f))
        calls[0] += 1
    return f


ElementVisualProfile.aura_frame = aura_frame
for block in range(16):
    before = calls[0]
    S.run(ps, 40, render=True)
    per_frame.append((calls[0] - before) / 40)
print(f"{live}: distinct aura frames {len(seen)}; auras drawn a frame by block of 40: "
      + " ".join(f"{x:.0f}" for x in per_frame))
