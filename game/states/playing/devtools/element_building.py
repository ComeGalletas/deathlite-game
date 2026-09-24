"""Seat an elemental buff building beside the hero (CMB-009.5, §10.3).

The dev menu's "Spawn elemental building..." row, for testing a building
of a chosen element without hunting a seed that rolled one. The building is
built the way the world builds one: `world.gen.buildings._seat` makes the
compound (the primary circle carries the art, the satellites only collide),
`GameMap.obstacles` takes it through its setter so the obstacle index is
rebuilt, `reskin_obstacle` gives it the kind's first rig at the size the
bake would draw it, and an `Interactable` carrying the element goes on the
run's list -- so using it runs the ordinary buff and infusion code.

The spot is the first free one on rings round the hero: every circle of the
compound on walkable ground and clear of every obstacle already standing.

What it does not do (CMB-009.D4): the navigation field is baked at run
start and is not rebuilt, so enemies do not route round a spawned building
-- they collide with it and slide, as they would round any obstacle the
field did not know. A dev tool; a run that needs a real one takes a seed.
"""
from __future__ import annotations

import math

import pygame

from entities.interactable import Interactable
from entities.obstacle import KINDS, satellites_of
from game import config
from world.gen.buildings import _seat
from world.terrain.decor.obstacle_skins import reskin_obstacle

# Rings round the hero, in tiles, and how many spots are tried on each.
_RINGS = (3.0, 4.5, 6.0, 8.0)
_SPOTS_PER_RING = 12


def spawn_elemental_building(ps, element, kind: str | None = None) -> tuple[bool, str]:
    """Seat a buff building of `kind` (the next buff kind in turn when left
    out) carrying `element` beside the hero. Returns `(ok, message)`."""
    run = ps.run
    gm = run.game_map
    kinds = list(ps.buffs.kinds)
    if not kinds:
        return False, "No buff buildings in the data"
    if kind is None:
        dev = ps.dev
        kind = kinds[dev.building_turn % len(kinds)]
        dev.building_turn += 1
    spot = _free_spot(gm, run.player.pos, kind)
    if spot is None:
        return False, f"No room for a {kind} building here"
    new: list = []
    primary = _seat(kind, spot.x, spot.y, new)
    index = len(gm.obstacles)
    gm.obstacles = list(gm.obstacles) + new
    rigs = _rigs(ps, kind)
    if rigs:
        reskin_obstacle(gm, ps.game.assets, index, rigs[0])
    run.interactables.append(Interactable(kind, primary.pos.x, primary.pos.y,
                                          element=element))
    return True, f"{element.key.title()} {kind} building seated"


def _rigs(ps, kind: str) -> list:
    conf = ps.game.assets.terrain.get("obstacle_decor", {})
    return list(conf.get("rigs", {}).get(kind, ()))


def _free_spot(gm, centre, kind: str):
    """The first spot on the rings where every circle of a `kind` compound
    stands on walkable ground clear of the obstacles already placed."""
    radius = float(KINDS[kind][0])
    circles = [(0.0, 0.0, radius)] + [(dx, dy, r) for dx, dy, r in satellites_of(kind)]
    px = config.TILE_PX
    for ring in _RINGS:
        for k in range(_SPOTS_PER_RING):
            a = math.tau * k / _SPOTS_PER_RING
            x = centre.x + math.cos(a) * ring * px
            y = centre.y + math.sin(a) * ring * px
            if all(_clear(gm, x + dx, y + dy, r) for dx, dy, r in circles):
                return pygame.Vector2(x, y)
    return None


def _clear(gm, x: float, y: float, r: float) -> bool:
    if not gm.is_walkable(pygame.Vector2(x, y), r):
        return False
    for o in gm._obstacle_index.near(x, y, r):
        if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (r + o.radius) ** 2:
            return False
    return True
