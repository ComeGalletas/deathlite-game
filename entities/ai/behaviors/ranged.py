"""Ranged / summoner movers. Ports `kite_shoot` and `summoner`, plus the
swing-summoner `path_chase_summon`.
"""
from __future__ import annotations

import pygame

from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.behaviors.simple import pursuit_stack
from entities.ai.components import FireProjectile, MaintainRange, SummonBrood
from entities.ai.machine import Behavior
from entities.ai.registry import behavior


@behavior("kite_shoot")
def build_kite_shoot(cfg: dict) -> Behavior:
    """Hold a distance and shoot, with a wind-up the player can read.

    **The shot is telegraphed** (owner, 2026-09-19). This used to be a
    single `move` state -- `MaintainRange` plus `FireProjectile` on a timer
    -- and that is exactly why none of the four kiters ever played the
    attack strip they all ship: `Enemy._anim_name()` returns "attack" only
    while the machine sits in `telegraph`/`attack`, and a one-state
    behaviour never does, so their `shoot.png` / `throw.png` had never once
    been drawn. Running the same `telegraph_cycle` the melee enemies use
    fixes the animation and gives the shot a tell in one stroke, and the
    shot leaves on the wind-up's end transition, so what the player reads
    and what the game does are one event.

    `attack_range` is the reach of the shot, separate from the `aggro_range`
    that decides whether the body is interested at all. It replaced an
    implicit `prefer_distance * 1.8`, which tied a weapon's reach to where
    the body liked to stand and quietly gave the long kiters far more of it
    than anything said out loud.

    It is also the cycle's `trigger_range`, so a body out of reach never
    begins a wind-up, and one that drifts out mid-wind-up aborts rather than
    loosing a shot the player was given no reason to expect.

    `shoot_interval` is the **true shot-to-shot gap** rather than the
    cooldown: the wind-up, the strike and the recovery come out of it, so
    the number in the data is the one a player could measure with a
    stopwatch (owner, 2026-09-19).

    A kiter that declares no `attack_telegraph` keeps the old single-state
    behaviour, so nothing that has not opted in moves.
    """
    pref = cfg.get("prefer_distance", 240)
    reach = cfg.get("attack_range", pref * 1.8)
    # `shot_style` / `shot_rig` / `shot_pierce` name the ammunition (R1,
    # `journals/enemy_roster_expansion_journal.md`). Absent, the shot is the
    # red arrow every kiter fired before.
    shot = FireProjectile(interval=cfg.get("shoot_interval", 2.0),
                          damage=cfg.get("shoot_damage", 6),
                          speed=cfg.get("shot_speed", 220),
                          radius=cfg.get("shot_radius", 6),
                          max_range=reach,
                          style=cfg.get("shot_style", ""),
                          rig=cfg.get("shot_rig", ""),
                          pierce=cfg.get("shot_pierce", 0),
                          tint=cfg.get("shot_tint"),
                          lifetime=cfg.get("shot_lifetime", 6.0),
                          stop_after=cfg.get("shot_stop_after", 0.0),
                          blast_radius=cfg.get("shot_blast_radius", 0.0))
    kite = MaintainRange(distance=pref, band=30, close_via="nav")

    telegraph = float(cfg.get("attack_telegraph", 0.0))
    if telegraph <= 0.0:
        return Behavior({"move": [kite, shot]})

    active = float(cfg.get("attack_active", 0.2))
    recover = float(cfg.get("attack_recover", 0.25))
    gap = float(cfg.get("shoot_interval", 2.0))
    # The cycle's own length comes out of the gap, so `shoot_interval` is
    # what the player experiences rather than what is left over after it.
    cooldown = max(0.05, gap - (telegraph + active + recover))

    return telegraph_cycle(
        chase=[kite],
        trigger_range=reach,
        telegraph=telegraph,
        active=active,
        recover=recover,
        cooldown=cooldown,
        on_windup_end=lambda actor, per, cmb: shot.fire(actor, per, cmb),
    )


@behavior("summoner")
def build_summoner(cfg: dict) -> Behavior:
    # old: flee at full speed inside 200 px, else drift in at 0.4x speed
    return Behavior({"move": [
        MaintainRange(distance=200, band=0, close_via="nav",
                      weight=1.0, close_weight=0.4),
        SummonBrood(interval=cfg.get("summon_interval", 4.0),
                    enemy_id=cfg.get("summon_id", "bumblebee"),
                    count=cfg.get("summon_count", 3)),
    ]})


@behavior("path_chase_summon")
def build_path_chase_summon(cfg: dict) -> Behavior:
    """`path_chase_attack`'s beat, but the swing summons as well as hits.

    The Beekeeper's torch swing (`journals/gnome_split_journal.md`). Plain
    `summoner` holds range in a single `move` state, which is why its sprite
    never played an attack animation: `Enemy._anim_name()` only returns
    "attack" while the machine sits in `telegraph`/`attack`. Running the same
    `telegraph_cycle` the melee enemies use gives the summon a readable
    wind-up and an animation, and both payloads land on the same transition,
    so what the player sees and what the game does are one event.

    The swing is on a **fixed cooldown and no range gate at all** (owner,
    2026-09-17): the summon is the point, so holding it until the actor is
    touching the player would gate the bees behind a melee range a summoner
    has no reason to close. It still chases, and the hitbox still lands in
    front of it -- a player who is nearby when the torch comes round is hit,
    and one who is not simply is not. `contact_damage` is tuned well under a
    real melee enemy's, because the damage is a garnish on the summon.

    Aggro still gates the whole behaviour, so it does not swing at a player it
    has never noticed.
    """
    active = cfg.get("attack_active", 0.45)
    enemy_id = cfg["summon_id"]
    count = int(cfg["summon_count"])

    def swing(actor, per, cmb):
        cmb.summon(enemy_id, actor.pos, count)
        d = per.player_pos - actor.pos
        facing = d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2(1, 0)
        cmb.melee_hit(actor.pos + facing * actor.radius,
                      actor.radius / 2.0, actor._base_contact, active)

    return telegraph_cycle(
        chase=pursuit_stack(cfg),
        trigger_range=None,             # swing on the timer, not on contact
        telegraph=cfg.get("attack_telegraph", 0.35),
        active=active,
        recover=cfg.get("attack_recover", 0.2),
        cooldown=cfg.get("attack_cooldown", 3.2),
        on_windup_end=swing,
    )
