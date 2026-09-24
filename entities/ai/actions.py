"""The names a behaviour template (`data/enemies/behaviors.json`) may use
(ENT-017).

A template is data; what its names *do* is here. Four registries, each
`name -> factory(cfg)`, where `cfg` is the enemy's merged block (shared
defaults, then the template's, then the enemy's own):

* **stacks** -- a list of steering / behaviour components for a state: the
  chase of a `telegraph_cycle`, or the whole of a `move` shape.
* **actions** -- a transition side-effect `fn(actor, per, cmb)`: lock a dash,
  blink, drop a hazard, land a hitbox.
* **attacks** -- the components that run *during* the attack state (a dash).
* **triggers** -- a rule for a cycle's `trigger_range` that is a formula
  rather than one key (`melee_reach`); a template trigger that is not a rule
  here names a key in `cfg`.

A new variant of an enemy is data. A new kind of action is one function
here, the way a new boss attack is one `@boss_pattern` (ENT-015).
"""
from __future__ import annotations

from typing import Callable

import pygame

from entities.ai.components import (AvoidObstacles, Charge, Explode, MaintainRange,
                                    SeekTarget, Separation, SummonBrood, Unstick)
from entities.ai.machine import ATTACK_SLOT
from game import config

STACKS: dict[str, Callable[[dict], list]] = {}
ACTIONS: dict[str, Callable[[dict], Callable]] = {}
ATTACKS: dict[str, Callable[[dict], list]] = {}
TRIGGERS: dict[str, Callable[[dict], float]] = {}


def _reg(table: dict, name: str):
    def deco(fn):
        if name in table:
            raise ValueError(f"{name!r} already registered")
        table[name] = fn
        return fn
    return deco


def stack(name: str):
    return _reg(STACKS, name)


def action(name: str):
    return _reg(ACTIONS, name)


def attack(name: str):
    return _reg(ATTACKS, name)


def trigger(name: str):
    return _reg(TRIGGERS, name)


def _facing(actor, per) -> pygame.Vector2:
    d = per.player_pos - actor.pos
    return d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2(1, 0)


# --- stacks --------------------------------------------------------------------

@stack("pursuit")
def pursuit_stack(cfg: dict) -> list:
    """Flow-field seek + the local-avoidance stack (separation, obstacle push,
    unstick), ordered so `Unstick` reads the accumulated heading last.

    A `flying` enemy (the tag, as on the boss) seeks in a straight line and
    keeps only the separation: the field routes round walls and up stairs
    for a body that has to walk, there is no obstacle to push off, and a
    body that passes through everything is never stuck."""
    seek_sep = [
        SeekTarget(via="straight" if "flying" in cfg.get("tags", ()) else "nav",
                   slew=cfg["nav_slew"], weight=cfg["seek_weight"]),
        Separation(radius_mult=cfg["separation_mult"], cap=cfg["separation_cap"]),
    ]
    if "flying" in cfg.get("tags", ()):
        return seek_sep
    return seek_sep + [
        AvoidObstacles(margin=cfg["obstacle_margin"], cap=cfg["obstacle_cap"]),
        Unstick(seconds=cfg["stuck_seconds"], nudge_strength=cfg["nudge_strength"]),
    ]


@stack("seek_nav")
def _seek_nav(cfg: dict) -> list:
    return [SeekTarget(via="nav", slew=0.0)]


@stack("seek_straight")
def _seek_straight(cfg: dict) -> list:
    """Straight-line pursuit -- no field, no avoidance (the old `chase`)."""
    return [SeekTarget(via="straight", slew=0.0)]


@stack("keep_away")
def _keep_away(cfg: dict) -> list:
    """Flee at full speed inside `keep_away`, else drift in at
    `keep_away_close_weight` of speed (the summoner)."""
    return [MaintainRange(distance=cfg["keep_away"], band=0, close_via="nav",
                          weight=1.0, close_weight=cfg["keep_away_close_weight"])]


@stack("explode")
def _explode(cfg: dict) -> list:
    return [Explode(fuse_range=cfg["fuse_range"])]


@stack("summon_brood")
def _summon_brood(cfg: dict) -> list:
    return [SummonBrood(interval=cfg["summon_interval"], enemy_id=cfg["summon_id"],
                        count=cfg["summon_count"])]


# --- attacks -------------------------------------------------------------------

@attack("charge")
def _charge(cfg: dict) -> list:
    return [Charge(speed=cfg["charge_speed"], damage=cfg["charge_damage"])]


# --- triggers ------------------------------------------------------------------

@trigger("melee_reach")
def _melee_reach(cfg: dict) -> float:
    """Touching distance: the enemy's collider, the hero's and a small pad."""
    if "attack_range" in cfg:
        return cfg["attack_range"]
    return cfg["radius"] + config.PLAYER_RADIUS + cfg["attack_reach_pad"]


@trigger("breath_reach")
def _breath_reach(cfg: dict) -> float:
    """Where the flame lands, plus the pool's own radius."""
    if "attack_range" in cfg:
        return cfg["attack_range"]
    return cfg["radius"] + float(cfg["breath_offset"]) + cfg["hazard_radius"]


# --- actions -------------------------------------------------------------------

@action("lock_dash")
def _lock_dash(cfg: dict):
    """Aim the dash at the hero as the wind-up ends; `charge` runs it."""
    def fn(actor, per, cmb):
        d = per.player_pos - actor.pos
        actor.bb.slot(ATTACK_SLOT)["dir"] = (
            d.normalize() if d.length_squared() > 1 else pygame.Vector2(1, 0))
    return fn


@action("blink")
def _blink(cfg: dict):
    """Teleport to a random point `blink_min`..`blink_range` from the hero,
    resolved against walls, and bite for `blink_damage`."""
    lo, hi, dmg = cfg["blink_min"], cfg["blink_range"], cfg["blink_damage"]

    def fn(actor, per, cmb):
        off = pygame.Vector2(per.rng.uniform(-1, 1), per.rng.uniform(-1, 1))
        if off.length_squared() > 0:
            off.scale_to_length(per.rng.uniform(lo, hi))
        actor.pos = per.resolve_movement(actor.pos, per.player_pos + off,
                                         actor.radius)
        actor.contact_damage = dmg
    return fn


@action("cast_snapshot")
def _cast_snapshot(cfg: dict):
    """Where the cast will land: the hero's feet as the wind-up starts."""
    def fn(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["cast_at"] = pygame.Vector2(per.player_pos)
    return fn


@action("cast_hazard")
def _cast_hazard(cfg: dict):
    haz = (cfg["hazard_radius"], cfg["hazard_dps"], cfg["hazard_duration"],
           cfg["hazard_tick"], cfg["hazard_sprite"])

    def fn(actor, per, cmb):
        at = actor.bb.slot(ATTACK_SLOT).get("cast_at", per.player_pos)
        cmb.spawn_hazard(pygame.Vector2(at), *haz)
    return fn


@action("poke")
def _poke(cfg: dict):
    """A small hitbox on the facing side (`radius / 2`, `contact_damage`-worth)
    that lasts the swing -- the melee enemies' damage path, since their
    passive body bite is off (see `enemies.json`)."""
    active = cfg["attack_active"]

    def fn(actor, per, cmb):
        pos = actor.pos + _facing(actor, per) * actor.radius
        cmb.melee_hit(pos, actor.radius / 2.0, actor._base_contact, active)
    return fn


@action("summon_swing")
def _summon_swing(cfg: dict):
    """The Beekeeper's swing: the summon and the hitbox on one transition."""
    active = cfg["attack_active"]
    enemy_id, count = cfg["summon_id"], int(cfg["summon_count"])

    def fn(actor, per, cmb):
        cmb.summon(enemy_id, actor.pos, count)
        cmb.melee_hit(actor.pos + _facing(actor, per) * actor.radius,
                      actor.radius / 2.0, actor._base_contact, active)
    return fn


@action("rear_back")
def _rear_back(cfg: dict):
    def fn(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_start"
    return fn


@action("breath_spit")
def _breath_spit(cfg: dict):
    """The flame lands in front and burns there: a `Hazard` with no sprite,
    because the imp's own frames draw it."""
    reach = float(cfg["breath_offset"])
    haz = (float(cfg["hazard_radius"]), float(cfg["hazard_dps"]),
           float(cfg["hazard_duration"]), float(cfg["hazard_tick"]), None)

    def fn(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_loop"
        at = actor.pos + _facing(actor, per) * (actor.radius + reach)
        cmb.spawn_hazard(pygame.Vector2(at), *haz)
    return fn


@action("embers")
def _embers(cfg: dict):
    def fn(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_end"
    return fn
