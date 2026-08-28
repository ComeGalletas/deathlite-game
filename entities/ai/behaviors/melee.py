"""Melee / detonate / FSM movers. Ports `exploder`, `brute`, `fsm_charger`,
`fsm_teleporter`, `fsm_warlock`. Defaults copied from `entities/enemy_ai.py`.
"""
from __future__ import annotations

import pygame

from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.components import (Charge, Cooldown, Explode, SeekTarget, after,
                                    all_of, in_range)
from entities.ai.machine import ATTACK_SLOT, Behavior, Transition
from entities.ai.registry import behavior


@behavior("exploder")
def build_exploder(cfg: dict) -> Behavior:
    return Behavior({"move": [
        SeekTarget(via="nav", slew=0.0),
        Explode(fuse_range=cfg.get("fuse_range", 32)),
    ]})


@behavior("brute")
def build_brute(cfg: dict) -> Behavior:
    """chase -> telegraph (rooted) -> slam + reset -> chase."""
    interval = cfg.get("slam_interval", 3.5)
    radius = cfg.get("slam_radius", 120)
    damage = cfg.get("slam_damage", 28)
    reach = cfg.get("slam_range", 120)
    windup = cfg.get("slam_telegraph", 0.9)
    cd = Cooldown(seconds=interval, start_ready=False)

    def slam(actor, per, cmb):
        if (per.player_pos - actor.pos).length() <= radius:
            cmb.explosion(pygame.Vector2(actor.pos), radius, damage)
        cd.trigger(actor)

    return Behavior(
        always=[cd],
        states={"chase": [SeekTarget(via="nav", slew=0.0)], "telegraph": []},
        transitions=[
            Transition("chase", "telegraph",
                       when=all_of(in_range(reach), lambda a, p: cd.ready(a))),
            Transition("telegraph", "chase", when=after(windup), on=slam),
        ],
        initial="chase",
    )


@behavior("fsm_charger")
def build_charger(cfg: dict) -> Behavior:
    def lock_dir(actor, per, cmb):
        d = per.player_pos - actor.pos
        actor.bb.slot(ATTACK_SLOT)["dir"] = (
            d.normalize() if d.length_squared() > 1 else pygame.Vector2(1, 0))

    return telegraph_cycle(
        chase=[SeekTarget(via="nav", slew=0.0)],
        trigger_range=cfg.get("charge_range", 340),
        telegraph=cfg.get("charge_telegraph", 0.7),
        active=cfg.get("charge_duration", 0.5),
        recover=cfg.get("charge_recover", 1.1),
        cooldown=cfg.get("charge_interval", 3.0),
        on_windup_end=lock_dir,
        attack=[Charge(speed=cfg.get("charge_speed", 620),
                       damage=cfg.get("charge_damage", 26))],
    )


@behavior("fsm_teleporter")
def build_teleporter(cfg: dict) -> Behavior:
    lo, hi = 20.0, cfg.get("blink_range", 70)
    dmg = cfg.get("blink_damage", 16)

    def blink(actor, per, cmb):
        off = pygame.Vector2(per.rng.uniform(-1, 1), per.rng.uniform(-1, 1))
        if off.length_squared() > 0:
            off.scale_to_length(per.rng.uniform(lo, hi))
        actor.pos = per.resolve_movement(actor.pos, per.player_pos + off,
                                         actor.radius)
        actor.contact_damage = dmg

    return telegraph_cycle(
        chase=[SeekTarget(via="nav", slew=0.0)],
        trigger_range=cfg.get("blink_trigger", 460),
        telegraph=cfg.get("blink_telegraph", 0.55),
        active=cfg.get("blink_duration", 0.35),
        recover=cfg.get("blink_recover", 0.9),
        cooldown=cfg.get("blink_interval", 2.6),
        on_windup_end=blink,
    )


@behavior("fsm_warlock")
def build_warlock(cfg: dict) -> Behavior:
    haz = (cfg.get("hazard_radius", 90), cfg.get("hazard_dps", 20),
           cfg.get("hazard_duration", 3.5), cfg.get("hazard_tick"))

    def snapshot(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["cast_at"] = pygame.Vector2(per.player_pos)

    def cast(actor, per, cmb):
        at = actor.bb.slot(ATTACK_SLOT).get("cast_at", per.player_pos)
        cmb.spawn_hazard(pygame.Vector2(at), *haz)

    return telegraph_cycle(
        chase=[SeekTarget(via="nav", slew=0.0)],
        trigger_range=cfg.get("cast_range", 420),
        telegraph=cfg.get("cast_telegraph", 0.8),
        active=cfg.get("cast_duration", 0.2),
        recover=cfg.get("cast_recover", 1.8),
        cooldown=cfg.get("cast_interval", 3.4),
        on_windup_start=snapshot,
        on_windup_end=cast,
    )
