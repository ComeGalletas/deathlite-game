"""The Hammer's slam (change request 1, `weapon_system_journal.md`).

A slam does not land the instant it fires. When the weapon would have fired
it **begins a swing**: the direction locks (auto-aim at the nearest target in
reach, or the manual aim), and `swing_time / attack_speed_multiplier`
seconds later the blow **lands** as a stationary circular hit of radius
`area` centred `impact_offset` px ahead of the hero -- where the hero is
*then*, so the circle travels with them. Enemies that walked out are missed,
enemies that walked in are hit. The cooldown (`cooldown`, scaled by the
cooldown bonuses / trait mods but *not* by attack speed) runs from the
impact, so one cycle is swing + cooldown.

The Forge extras land with the blow at the circle's centre: Earthshaker's
shockwave blast and the Meteor Hammer's crater. The impact sheet
(`hammer_impact`) is spawned through `FireContext.spawn_impact` and the
pending swing is drawn by `game/states/playing/slam_fx.py` from
`Weapon.swing_progress` / `Weapon.slam_centre`.

All numbers are the weapon's data; nothing here has a default.
"""
from __future__ import annotations

import pygame

from combat.damage import outgoing_damage


def reach(weapon, area_multiplier: float) -> float:
    """How far the circle's far edge reaches from the hero: the offset plus
    the radius (`area`, with its bonuses and multiplier)."""
    return float(weapon.definition["impact_offset"]) + weapon._area(area_multiplier)


def centre(weapon, origin: pygame.Vector2, direction: pygame.Vector2) -> pygame.Vector2:
    return origin + direction * float(weapon.definition["impact_offset"])


def begin_swing(weapon, ctx, forced: bool) -> bool:
    """Start the swing if there is something to swing at (or a manual aim).
    Returns True when a swing began."""
    picked = weapon._pick_aim(ctx, forced)
    if picked is None:
        return False
    _aim, direction, _candidates = picked
    weapon._swing_dir = pygame.Vector2(direction)
    total = float(weapon.definition["swing_time"]) / max(0.05, ctx.attack_speed_multiplier)
    weapon._swing_total = total
    weapon._swing_t = total
    return True


def land(weapon, ctx) -> None:
    """The blow: one circular hit at the locked centre, the Forge extras,
    the impact visual. Called by `Weapon.update` when the swing timer ends."""
    d = weapon.definition
    direction = weapon._swing_dir if weapon._swing_dir is not None else ctx.fallback_dir
    if direction.length_squared() < 1e-6:
        direction = pygame.Vector2(1, 0)
    pos = centre(weapon, ctx.origin, direction)
    radius = weapon._area(ctx.area_multiplier)
    src_weight = weapon._weight()
    weapon._begin_attack()
    dmg = outgoing_damage(weapon._volley_damage(ctx), ctx.damage_multiplier,
                          weapon._crit_chance(ctx), ctx.crit_multiplier, ctx.rng)
    ctx.spawn_projectile(
        pos=pos, vel=pygame.Vector2(), damage=dmg.amount, radius=radius,
        lifetime=float(d["projectile_lifetime"]), pierce=weapon._pierce(),
        src_weight=src_weight, weapon_id=weapon.weapon_id, visual=weapon.visual_id,
        source_tags=weapon.tags, is_crit=dmg.is_crit, style="hidden", no_block=True,
        stun_chance=float(d.get("stun_chance", 0.0)) + weapon.bonus["stun_chance"],
        stun_duration=float(d.get("stun_duration", 0.0)) + weapon.bonus["stun_duration"])
    if ctx.spawn_impact is not None:
        ctx.spawn_impact(pos=pos, radius=radius, rig=str(d.get("impact_rig", "")),
                         weapon_id=weapon.weapon_id)
    fx = weapon.effects
    if weapon.effect("shockwave_radius") > 0.0:
        base = weapon._volley_damage(ctx) * float(fx.get("shockwave_damage_mult", 0.5))
        sdmg = outgoing_damage(base, ctx.damage_multiplier,
                               weapon._crit_chance(ctx), ctx.crit_multiplier, ctx.rng)
        ctx.spawn_projectile(
            pos=pos, vel=pygame.Vector2(), damage=sdmg.amount,
            radius=weapon.effect("shockwave_radius"), lifetime=0.15, pierce=999,
            src_weight=src_weight * 0.5, weapon_id=weapon.weapon_id,
            visual=weapon.visual_id, source_tags=weapon.tags + ("shockwave",),
            is_crit=sdmg.is_crit, style="blast", no_block=True)
    if weapon.effect("hazard_radius") > 0.0 and ctx.spawn_hazard is not None:
        ctx.spawn_hazard(
            pos=pos, radius=weapon.effect("hazard_radius"),
            dps=weapon._volley_damage(ctx) * float(fx.get("hazard_dps_mult", 0.3)),
            duration=weapon.effect("hazard_duration", 2.0),
            weapon_id=weapon.weapon_id, source_tags=weapon.tags + ("crater",))
    weapon._swing_dir = None
    weapon._swing_t = 0.0
    weapon._swing_total = 0.0
