"""RND-010.6: what the RLE copies of a fight's aura frames hold, measured
as the process's memory (headless).

The fight's own aura frames (those `rle.ready` was asked for in 640 fight
frames) are copied afresh: the process's resident memory is read before the
copies, after them (each still a plain pixel buffer) and after one blit of
each onto a 32-bit scratch surface (which encodes it; SDL then frees the
pixel buffer and keeps the runs). A measurement tool, not game code.
"""
import gc
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())

import psutil
import pygame

from game.states.playing.visual.elements import rle
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S

live, elapsed = int(sys.argv[1]), float(sys.argv[2])
_game, ps = LP.packed_scene(35, live, 400, elapsed, None, elements=True)
S.run(ps, 640, render=True)
frames = [entry[0] for entry in rle._COPIES.values()]
pixels = sum(f.get_width() * f.get_height() * 4 for f in frames)
proc = psutil.Process()
gc.collect()
before = proc.memory_info().rss
copies = []
for f in frames:
    c = f.copy()
    c.set_alpha(255, pygame.RLEACCEL)
    copies.append(c)
gc.collect()
plain = proc.memory_info().rss
scratch = pygame.Surface((400, 400))
for c in copies:
    scratch.blit(c, (0, 0))
gc.collect()
encoded = proc.memory_info().rss
print(f"{live}: {len(frames)} copies, {pixels / 1e6:.1f} MB of pixels; resident memory "
      f"+{(plain - before) / 1e6:.1f} MB as plain copies, +{(encoded - before) / 1e6:.1f} MB once encoded")
