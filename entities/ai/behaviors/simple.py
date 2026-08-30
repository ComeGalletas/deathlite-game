"""Simple movers -- one `move` state. Ports `chase` and `path_chase` from
`entities/enemy_ai.py`.

Every component param defaults to the value the old code hard-coded, and is
overridable from the enemy's `data/enemies.json` block (`cfg`), so a variant can
be re-tuned without a new behaviour.
"""
from __future__ import annotations

import pygame

from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.components import AvoidObstacles, Separation, SeekTarget, Unstick
from entities.ai.machine import Behavior
from entities.ai.registry import behavior
from game import config

# --- path_chase_attack melee tuning ------------------------------------------
# Default timing for the chaser's chase -> telegraph -> attack -> recover beat.
# Kept here (module globals, not game/config) so the whole swing can be tuned in
# one place; an enemy's data/enemies.json block overrides any of these per-key
# (attack_telegraph / attack_active / attack_recover / attack_cooldown), and a
# missing key falls back to the constant.
#
# CB (journals/combat_balance_journal.md): the wind-up and the swing were
# stretched by MELEE_REACT_SCALE so the player can read the telegraph and step
# out before the MeleeHitbox lands. `attack_recover` / `attack_cooldown` are
# left alone, so attack *cadence* barely shifts -- only the readable window and
# the hitbox lifetime grow.
MELEE_REACT_SCALE = 1.25
MELEE_ATTACK_TELEGRAPH = 0.15 * MELEE_REACT_SCALE   # 0.1875 s wind-up (reaction window)
MELEE_ATTACK_ACTIVE = 0.35 * MELEE_REACT_SCALE      # 0.4375 s swing + hitbox lifetime
MELEE_ATTACK_RECOVER = 0.15
MELEE_ATTACK_COOLDOWN = 0.6


def _pursuit_stack(cfg: dict) -> list:
    """Flow-field seek + the local-avoidance stack (separation, obstacle push,
    unstick), ordered so `Unstick` reads the accumulated heading last."""
    return [
        SeekTarget(via="nav",
                   slew=cfg.get("nav_slew", 9.0),
                   weight=cfg.get("seek_weight", 1.0)),
        Separation(radius_mult=cfg.get("separation_mult", 1.6),
                   cap=cfg.get("separation_cap", 0.6)),
        AvoidObstacles(margin=cfg.get("obstacle_margin", 14.0),
                       cap=cfg.get("obstacle_cap", 0.7)),
        Unstick(seconds=cfg.get("stuck_seconds", 0.4),
                nudge_strength=cfg.get("nudge_strength", 1.5)),
    ]


@behavior("chaser")
@behavior("chase")
def build_chase(cfg: dict) -> Behavior:
    """Straight-line pursuit -- no field, no avoidance (the old `chase`)."""
    return Behavior({"move": [SeekTarget(via="straight", slew=0.0)]})


@behavior("path_chase")
def build_path_chase(cfg: dict) -> Behavior:
    return Behavior({"move": _pursuit_stack(cfg)})


@behavior("swarm")
def build_swarm(cfg: dict) -> Behavior:
    """Identical to `path_chase` today; kept separate as the tuning hook for the
    planned tighter crowd behaviour."""
    return Behavior({"move": _pursuit_stack(cfg)})


@behavior("path_chase_attack")
def build_path_chase_attack(cfg: dict) -> Behavior:
    """`path_chase`, but rooted into a `telegraph -> attack` beat (drives the
    sprite's "attack" animation) whenever it's touching the player. On the
    `telegraph -> attack` transition it drops a small `MeleeHitbox` on its
    front-facing side (`radius / 2`, `contact_damage`-worth) that lasts for the
    swing -- the actual damage path now, since the passive body-overlap bite
    in `combat.py` is disabled for melee-attack enemies (see `enemies.json`).
    """
    reach = cfg.get(
        "attack_range", cfg.get("radius", 14.0) + config.PLAYER_RADIUS + 5.0)
    # Per-enemy overrides (data/enemies.json) win; a missing key falls back to
    # the module default above.
    active = cfg.get("attack_active", MELEE_ATTACK_ACTIVE)

    def spawn_hit(actor, per, cmb):
        d = per.player_pos - actor.pos
        facing = d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2(1, 0)
        pos = actor.pos + facing * actor.radius
        cmb.melee_hit(pos, actor.radius / 2.0, actor._base_contact, active)

    return telegraph_cycle(
        chase=_pursuit_stack(cfg),
        trigger_range=reach,
        telegraph=cfg.get("attack_telegraph", MELEE_ATTACK_TELEGRAPH),
        active=active,
        recover=cfg.get("attack_recover", MELEE_ATTACK_RECOVER),
        cooldown=cfg.get("attack_cooldown", MELEE_ATTACK_COOLDOWN),
        on_windup_end=spawn_hit,
    )
