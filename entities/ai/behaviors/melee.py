"""Code-built melee shapes: the brute's slam and the Whirlspear's sweep.

Every other melee behaviour is a template in `data/enemies/behaviors.json`
(ENT-017) built from the generic shapes in `entities/ai/templates.py`. These
two stay code because their machines are not a plain telegraph cycle -- the
brute has no attack state, and the sweep's wind-up depends on which swing it
picked. Their numbers come from the merged block, with no fallbacks.
"""
from __future__ import annotations

import pygame

from entities.ai.actions import pursuit_stack
from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.components import Cooldown, SeekTarget, after, all_of, in_range
from entities.ai.machine import ATTACK_SLOT, Behavior, Transition
from entities.ai.registry import behavior


@behavior("brute")
def build_brute(cfg: dict) -> Behavior:
    """chase -> telegraph (rooted) -> slam + reset -> chase."""
    radius, damage = cfg["slam_radius"], cfg["slam_damage"]
    cd = Cooldown(seconds=cfg["slam_interval"], start_ready=False)

    def slam(actor, per, cmb):
        if (per.player_pos - actor.pos).length() <= radius:
            cmb.explosion(pygame.Vector2(actor.pos), radius, damage)
        cd.trigger(actor)

    return Behavior(
        always=[cd],
        states={"chase": [SeekTarget(via="nav", slew=0.0)], "telegraph": []},
        transitions=[
            Transition("chase", "telegraph",
                       when=all_of(in_range(cfg["slam_range"]),
                                   lambda a, p: cd.ready(a))),
            Transition("telegraph", "chase", when=after(cfg["slam_telegraph"]), on=slam),
        ],
        initial="chase",
    )


@behavior("path_chase_sweep")
def build_path_chase_sweep(cfg: dict) -> Behavior:
    """chase -> telegraph (rooted) -> a hitbox centred on the body -> recover.

    The Whirlspear (`journals/spear_goblin_journal.md`). Every other melee
    enemy pokes: the `poke` action drops its hitbox at
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
        trigger_range=(cfg["attack_range"] if "attack_range" in cfg
                       else cfg["radius"] + reach),
        telegraph=windup_for,
        active=active,
        recover=float(cfg["attack_recover"]),
        cooldown=float(cfg["attack_cooldown"]),
        recover_weight=cfg["recover_weight"],
        on_windup_start=pick,
        on_windup_end=sweep,
    )
