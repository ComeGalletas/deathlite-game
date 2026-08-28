"""Ranged / summoner movers. Ports `kite_shoot` and `summoner`."""
from __future__ import annotations

from entities.ai.components import FireProjectile, MaintainRange, SummonBrood
from entities.ai.machine import Behavior
from entities.ai.registry import behavior


@behavior("kite_shoot")
def build_kite_shoot(cfg: dict) -> Behavior:
    pref = cfg.get("prefer_distance", 240)
    return Behavior({"move": [
        MaintainRange(distance=pref, band=30, close_via="nav"),
        FireProjectile(interval=cfg.get("shoot_interval", 2.0),
                       damage=cfg.get("shoot_damage", 6),
                       speed=cfg.get("shot_speed", 220),
                       radius=6, max_range=pref * 1.8),
    ]})


@behavior("summoner")
def build_summoner(cfg: dict) -> Behavior:
    # old: flee at full speed inside 200 px, else drift in at 0.4x speed
    return Behavior({"move": [
        MaintainRange(distance=200, band=0, close_via="nav",
                      weight=1.0, close_weight=0.4),
        SummonBrood(interval=cfg.get("summon_interval", 4.0),
                    enemy_id=cfg.get("summon_id", "swarm"),
                    count=cfg.get("summon_count", 3)),
    ]})
