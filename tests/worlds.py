"""Shared worlds for the test suite: one build per seed per process.

A height-map world costs one to two seconds to generate, and the suite used
to pay that inside every test: `test_repair.py` regenerated the same eight
seeds in each of its twenty-five tests (456 s of a 952 s run), and
`test_obstacle_families.py` built thirty seeds twice inside one test (98 s).
Six modules had each grown a private module-level cache. This is the one they
all share.

Everything is keyed by *what was built*: the seed, plus any `game.config`
values and module attributes that were patched while it was built. A world
generated under one setting is never handed to a test that asked for
another -- the "generated under one mode, read under another" hazard that
module-scope flag flipping used to create.

Worlds are shared, so **tests must not mutate them**. A test that needs to
change a layout's obstacles or a map's state takes `fresh()` (an uncached
build) or a `copy.deepcopy` of the layout, which costs well under a tenth of
a second.

Plain functions rather than pytest fixtures, so
`python -m unittest discover -s tests -t .` keeps working unchanged.
"""
from __future__ import annotations

import contextlib
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from world.map import GameMap
from world.pathfinding import NavField

# The seeds the digest pins. Modules should prefer these so the shared set
# stays small; a statistical sweep that needs more says so with a marker.
SEEDS = (35, 7, 1234, 42)

_MAPS: dict = {}
_NAV: dict = {}


def display() -> None:
    """A 1x1 dummy display -- the bake needs one to `convert()` surfaces."""
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def _key(seed, overrides: dict, patches) -> tuple:
    return (int(seed),
            tuple(sorted(overrides.items())),
            tuple((m.__name__, a, v) for m, a, v in patches))


@contextlib.contextmanager
def settings(overrides: dict, patches=()):
    """Apply `config` overrides and `(module, attr, value)` patches for the
    duration of a build, restoring every one afterwards -- including on an
    exception, which is what the hand-written try/finally blocks in the old
    modules sometimes forgot."""
    saved = [(config, k, getattr(config, k)) for k in overrides]
    saved += [(m, a, getattr(m, a)) for m, a, _v in patches]
    try:
        for k, v in overrides.items():
            setattr(config, k, v)
        for m, a, v in patches:
            setattr(m, a, v)
        yield
    finally:
        for obj, a, v in saved:
            setattr(obj, a, v)


def fresh(seed: int, patches=(), **overrides) -> GameMap:
    """An uncached `GameMap` built under the given settings. For tests that
    mutate what they build, or that assert two builds agree."""
    with settings(overrides, patches):
        return GameMap(seed=seed)


def game_map(seed: int, patches=(), **overrides) -> GameMap:
    """The shared `GameMap` for `seed`: layout, obstacles, `LevelIndex`. Not
    baked. Do not mutate."""
    k = _key(seed, overrides, patches)
    gm = _MAPS.get(k)
    if gm is None:
        gm = _MAPS[k] = fresh(seed, patches, **overrides)
    return gm


def layout(seed: int, patches=(), **overrides):
    """The shared `WorldLayout` for `seed`. Do not mutate."""
    return game_map(seed, patches, **overrides).layout


def levels(seed: int, patches=(), **overrides):
    """The shared `LevelIndex` for `seed`."""
    return game_map(seed, patches, **overrides)._levels


def baked(seed: int, patches=(), **overrides) -> GameMap:
    """The shared map with its terrain baked. Baked once, on the dummy
    display; later calls return the same object."""
    gm = game_map(seed, patches, **overrides)
    if not gm._tiles_ready:
        display()
        with settings(overrides, patches):
            gm._build_tiles()
    return gm


def nav(seed: int, patches=(), **overrides) -> NavField:
    """The shared `NavField` for `seed`. Its grids are immutable; its flow
    fields are rebuilt toward whatever target a test asks for, so a test that
    reads a field must `rebuild` it first rather than trust the last caller."""
    k = _key(seed, overrides, patches)
    nf = _NAV.get(k)
    if nf is None:
        lay = layout(seed, patches, **overrides)
        with settings(overrides, patches):
            nf = _NAV[k] = NavField(lay, lay.obstacles)
    return nf
