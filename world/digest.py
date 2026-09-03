"""Fingerprints of a world at each of its three stages: the generated
layout, the baked terrain, and one drawn frame.

A refactor of the generator, the bake or the renderer is "pure" only if the
world it produces is byte-identical, and that is a measurement, not a claim.
`tests/world/test_digest.py` pins these for the shipping seeds; before and
after a move, the pinned values either match or the change has to be
explained. The W7 fingerprint that verified the last split lived in a scratch
script and was lost with it -- this is that script, kept.

From the command line::

    python -m world.digest              # print the digests for SEEDS
    python -m world.digest --write      # rewrite tests/world/digests.json

The hash walks the data model generically -- dataclasses, slotted objects,
`pygame.Rect`, `Vector2`, `array`, `Surface` -- so a new field on `Room` is
fingerprinted the day it is added rather than when someone remembers to list
it. Floats are rounded to six places, which is well under any placement
difference that matters and above the noise a different `math` build could
introduce.
"""
from __future__ import annotations

import hashlib
import json
import sys
from array import array
from pathlib import Path

import pygame

from game import config

SEEDS = (35, 7, 1234, 42)
PINNED = Path(__file__).resolve().parent.parent / "tests" / "world" / "digests.json"

# The containers the bake fills on a `GameMap`. Empty ones are skipped, so a
# container that is deleted once nothing fills it leaves the digest unchanged.
_BAKE_FIELDS = (
    "_tiles_ok", "_water_tile", "_water_buf", "_shadow", "_foam",
    "_foam_routines", "_grid_surfs", "_corr_surfs", "_shore", "_decos",
    "_sprite_drop", "_tree_shadows", "_room_decor", "_void_decor",
)


def _feed(h, obj) -> None:
    """Walk `obj` into the hash, deterministically."""
    if obj is None or isinstance(obj, (bool, int, str, bytes)):
        h.update(repr(obj).encode())
    elif isinstance(obj, float):
        h.update(repr(round(obj, 6)).encode())
    elif isinstance(obj, pygame.Surface):
        h.update(b"S")
        h.update(repr(obj.get_size()).encode())
        h.update(pygame.image.tobytes(obj, "RGBA"))
    elif isinstance(obj, pygame.Rect):
        h.update(repr(tuple(obj)).encode())
    elif isinstance(obj, pygame.Vector2):
        _feed(h, (obj.x, obj.y))
    elif isinstance(obj, array):
        h.update(obj.typecode.encode())
        h.update(obj.tobytes())
    elif isinstance(obj, (bytearray, memoryview)):
        h.update(bytes(obj))
    elif isinstance(obj, dict):
        h.update(b"{")
        for k in sorted(obj, key=repr):
            _feed(h, k)
            _feed(h, obj[k])
        h.update(b"}")
    elif isinstance(obj, (frozenset, set)):
        h.update(b"#")
        for k in sorted(obj, key=repr):
            _feed(h, k)
    elif isinstance(obj, (tuple, list)):
        h.update(b"[")
        for v in obj:
            _feed(h, v)
        h.update(b"]")
    elif callable(obj):
        h.update(getattr(obj, "__qualname__", repr(type(obj))).encode())
    else:
        # A dataclass, a NamedTuple already handled above as a tuple, or a
        # slotted object such as `Obstacle` / `InsetField`.
        h.update(type(obj).__name__.encode())
        names = getattr(obj, "__slots__", None)
        if names is None:
            names = sorted(vars(obj))
        for name in names:
            if name.startswith("__"):
                continue
            _feed(h, name)
            _feed(h, getattr(obj, name, None))


def _hex(h) -> str:
    return h.hexdigest()[:16]


def layout_digest(layout) -> str:
    """Rooms (rects, cells, grids, tile meta, palettes, inset fields),
    corridors, stairs, obstacles, bounds, roles -- everything
    `generate_world` decides."""
    h = hashlib.sha256()
    _feed(h, layout)
    return _hex(h)


def bake_digest(gm) -> str:
    """Every baked surface's pixels and every anchor list. Bakes first if
    the map has not been (needs a display)."""
    if not gm._tiles_ready:
        gm._build_tiles()
    h = hashlib.sha256()
    for name in _BAKE_FIELDS:
        value = getattr(gm, name, None)
        if not value:
            continue
        _feed(h, name)
        _feed(h, value)
    return _hex(h)


def draw_digest(gm, seconds: float = 0.0) -> str:
    """One composited frame at the start room, at the configured zoom, at
    animation time `seconds`. Pixels only."""
    from systems.camera import Camera
    if not gm._tiles_ready:
        gm._build_tiles()
    surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    surface.fill((0, 0, 0))
    camera = Camera(gm.width, gm.height)
    camera.snap_to(gm.center)
    renderer = gm.renderer
    clock = renderer.clock
    renderer.clock = lambda: seconds          # foam and decor animate on this
    try:
        renderer.draw(surface, camera)
    finally:
        renderer.clock = clock
    h = hashlib.sha256()
    _feed(h, surface)
    return _hex(h)


def world_digests(seed: int) -> dict:
    """All three digests for one seed, from a fresh build."""
    from world.map import GameMap
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    gm = GameMap(seed=seed)
    return {"layout": layout_digest(gm.layout),
            "bake": bake_digest(gm),
            "draw": draw_digest(gm)}


def main(argv) -> int:
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    out = {str(seed): world_digests(seed) for seed in SEEDS}
    text = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        PINNED.write_text(text, newline="\n")
        print(f"wrote {PINNED}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
