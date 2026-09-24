"""The code-built ranged shape: `kite_shoot`.

The summoner and the Beekeeper's swing are templates in
`data/enemies/behaviors.json` (ENT-017). The kiter stays code because its
machine depends on its data -- a kiter with no wind-up is a single state --
and its cooldown is derived from the shot gap. Its numbers come from the
merged block, with no fallbacks.
"""
from __future__ import annotations

from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.components import FireProjectile, MaintainRange
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
    that decides whether the body is interested at all. Absent, it is
    `prefer_distance x attack_range_mult` (the data's 1.8), the implicit
    reach every kiter had before it was named.

    It is also the cycle's `trigger_range`, so a body out of reach never
    begins a wind-up, and one that drifts out mid-wind-up aborts rather than
    loosing a shot the player was given no reason to expect.

    `shoot_interval` is the **true shot-to-shot gap** rather than the
    cooldown: the wind-up, the strike and the recovery come out of it, so
    the number in the data is the one a player could measure with a
    stopwatch (owner, 2026-09-19).

    A kiter whose `attack_telegraph` is 0 (the template's default) keeps the
    old single-state behaviour, so nothing that has not opted in moves.
    """
    pref = cfg["prefer_distance"]
    reach = (cfg["attack_range"] if "attack_range" in cfg
             else pref * cfg["attack_range_mult"])
    # `shot_style` / `shot_rig` / `shot_pierce` name the ammunition (R1,
    # `journals/enemy_roster_expansion_journal.md`). The template's empty
    # style is the red arrow every kiter fired before.
    shot = FireProjectile(interval=cfg["shoot_interval"],
                          damage=cfg["shoot_damage"],
                          speed=cfg["shot_speed"],
                          radius=cfg["shot_radius"],
                          max_range=reach,
                          style=cfg["shot_style"],
                          rig=cfg["shot_rig"],
                          pierce=cfg["shot_pierce"],
                          tint=cfg["shot_tint"],
                          lifetime=cfg["shot_lifetime"],
                          stop_after=cfg["shot_stop_after"],
                          blast_radius=cfg["shot_blast_radius"])
    kite = MaintainRange(distance=pref, band=cfg["kite_band"], close_via="nav")

    telegraph = float(cfg["attack_telegraph"])
    if telegraph <= 0.0:
        return Behavior({"move": [kite, shot]})

    active = float(cfg["attack_active"])
    recover = float(cfg["attack_recover"])
    gap = float(cfg["shoot_interval"])
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
        recover_weight=cfg["recover_weight"],
        on_windup_end=lambda actor, per, cmb: shot.fire(actor, per, cmb),
    )
