"""Simple movers -- one `move` state. Ports `chase` and `path_chase` from
`entities/enemy_ai.py`.

Every component param defaults to the value the old code hard-coded, and is
overridable from the enemy's `data/enemies.json` block (`cfg`), so a variant can
be re-tuned without a new behaviour.
"""
from __future__ import annotations

from entities.ai.components import AvoidObstacles, Separation, SeekTarget, Unstick
from entities.ai.machine import Behavior
from entities.ai.registry import behavior


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
