"""Melee / detonate / FSM movers. Ports `exploder`, `brute`, `fsm_charger`,
`fsm_teleporter`, `fsm_warlock`. Defaults copied from `entities/enemy_ai.py`.
"""
from __future__ import annotations

import pygame

from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.behaviors.simple import pursuit_stack
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
           cfg.get("hazard_duration", 3.5), cfg.get("hazard_tick"),
           cfg.get("hazard_sprite"))

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


@behavior("path_chase_sweep")
def build_path_chase_sweep(cfg: dict) -> Behavior:
    """chase -> telegraph (rooted) -> a hitbox centred on the body -> recover.

    The Whirlspear (`journals/spear_goblin_journal.md`). Every other melee
    enemy pokes: `path_chase_attack` drops its hitbox at
    `pos + facing * radius` with radius `radius / 2`, a small disc in front.
    This art is a full 360 degree sweep of the spear, so the damage is a disc
    centred on the actor instead -- there is no safe side, only a safe
    distance. That is also why the wind-up is longer than a poke's: a ring
    cannot be side-stepped, it has to be backed out of.

    Two swings, alternating. Every `strong_every`-th one is the heavy whirl:
    a wider ring, more damage, and a longer wind-up, playing the rig's
    `attack_strong` strip. The choice is made when the wind-up *starts*, so
    the telegraph the player reads is the one that lands.
    """
    reach = float(cfg["sweep_reach"])
    strong_reach = float(cfg["strong_reach"])
    strong_mult = float(cfg["strong_damage_mult"])
    fast_windup = float(cfg["attack_telegraph"])
    strong_windup = float(cfg["strong_telegraph"])
    strong_every = max(1, int(cfg["strong_every"]))
    active = float(cfg["attack_active"])

    def pick(actor, per, cmb):
        slot = actor.bb.slot(ATTACK_SLOT)
        n = slot.get("swings", 0) + 1
        slot["swings"] = n
        strong = n % strong_every == 0
        slot["strong"] = strong
        slot["anim"] = "attack_strong" if strong else "attack"

    def windup_for(actor) -> float:
        return strong_windup if actor.bb.slot(ATTACK_SLOT).get("strong") else fast_windup

    def sweep(actor, per, cmb):
        strong = actor.bb.slot(ATTACK_SLOT).get("strong")
        radius = actor.radius + (strong_reach if strong else reach)
        damage = actor._base_contact * (strong_mult if strong else 1.0)
        cmb.melee_hit(pygame.Vector2(actor.pos), radius, damage, active)

    return telegraph_cycle(
        chase=pursuit_stack(cfg),
        trigger_range=cfg.get("attack_range", cfg["radius"] + reach),
        telegraph=windup_for,
        active=active,
        recover=float(cfg["attack_recover"]),
        cooldown=float(cfg["attack_cooldown"]),
        on_windup_start=pick,
        on_windup_end=sweep,
    )


@behavior("path_chase_breath")
def build_path_chase_breath(cfg: dict) -> Behavior:
    """chase -> wind up -> spit a pool of fire -> watch it burn out.

    The Imp (`journals/imp_journal.md`). Its art is the only three-part attack
    in the game -- `attack_start` rears it back, `attack_loop` holds the
    stream while the flame pools on the ground, `attack_end` breaks the pool
    into embers -- so the three strips map onto the three states the cycle
    already has: telegraph, attack, recover.

    The damage is a `Hazard`, not a hitbox: the flame lands in front, sits
    there and bites over time, which is what the animation shows. It carries
    **no sprite**, because the imp's own frames already draw it -- a hazard
    sprite on top would double the flame.

    The hazard outlives the `attack` state on purpose: `hazard_duration`
    covers the loop *and* the embers, so the burning stops exactly when the
    last ember fades rather than while flame is still drawn.
    """
    reach = float(cfg["breath_offset"])

    def rear_back(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_start"

    def spit(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_loop"
        d = per.player_pos - actor.pos
        facing = d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2(1, 0)
        at = actor.pos + facing * (actor.radius + reach)
        cmb.spawn_hazard(pygame.Vector2(at), float(cfg["hazard_radius"]),
                         float(cfg["hazard_dps"]), float(cfg["hazard_duration"]),
                         float(cfg["hazard_tick"]), None)

    def embers(actor, per, cmb):
        actor.bb.slot(ATTACK_SLOT)["anim"] = "attack_end"

    return telegraph_cycle(
        chase=pursuit_stack(cfg),
        trigger_range=cfg.get("attack_range",
                              cfg["radius"] + reach + cfg["hazard_radius"]),
        telegraph=float(cfg["attack_telegraph"]),
        active=float(cfg["attack_active"]),
        recover=float(cfg["attack_recover"]),
        cooldown=float(cfg["attack_cooldown"]),
        on_windup_start=rear_back,
        on_windup_end=spit,
        on_recover_start=embers,
    )
