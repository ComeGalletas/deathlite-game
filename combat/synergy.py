"""Weapon synergies (six-weapon system P4; design §10, §11).

Every explicit synergy is "weapon A does more to an enemy that weapon B
touched recently". The memory lives on the enemy:

  * `enemy.recent_hits[weapon_id]` -- run-clock time of the last hit by that
    weapon (`record_hit`), and
  * `enemy.hit_streak[weapon_id]` -- consecutive hits by that weapon with no
    gap longer than the window (Hunter's Mark), and
  * the `mark` status the Rod leaves on what it hits (design decision 2).

One shared window, `config.SYNERGY_WINDOW_S` (1.5 s), which every synergy
blessing states in its card text. The bonuses are `weapon_effect` keys on the
benefiting weapon, read here by `synergy_multiplier` and added together:

  syn_after_<weapon>   +frac if <weapon> hit the target inside the window
  syn_vs_marked        +frac if the target carries the Rod's mark
  crossfire_rod_bonus  (on the Bow) +frac for the *Rod* against a target the
                       Bow hit inside the window -- Crossfire's other half
  hunters_mark_per_hit +frac per consecutive hit on the same target, up to
                       `hunters_mark_max` stacks
  pull_strength        Crowd Cleaner: Sword hits drag the target toward the
                       centre of the swing (`pull`), a behavioural synergy

Natural synergies (§11) need nothing here.
"""
from __future__ import annotations

import pygame

from game import config

MARK = "mark"
_AFTER = "syn_after_"


def window() -> float:
    return float(config.SYNERGY_WINDOW_S)


def hit_within(enemy, weapon_id: str, now: float) -> bool:
    t = getattr(enemy, "recent_hits", {}).get(weapon_id)
    return t is not None and now - t <= window()


def record_hit(enemy, weapon_id: str, now: float) -> None:
    """Remember that `weapon_id` hit `enemy` at `now`; extend or restart its
    streak. Shots with no weapon (a summon's bolt) record nothing."""
    if not weapon_id:
        return
    hits = enemy.recent_hits
    streak = enemy.hit_streak
    last = hits.get(weapon_id)
    streak[weapon_id] = (streak.get(weapon_id, 0) + 1
                         if last is not None and now - last <= window() else 1)
    hits[weapon_id] = now


def is_marked(enemy) -> bool:
    return MARK in enemy.status


def synergy_multiplier(player, weapon, enemy, now: float) -> float:
    """1 + every synergy bonus that applies to this hit. `weapon` is the
    firing weapon (None for an unowned source -> 1.0)."""
    if weapon is None:
        return 1.0
    bonus = 0.0
    for key, value in weapon.effects.items():
        val = weapon.effect(key)
        if key.startswith(_AFTER):
            if hit_within(enemy, key[len(_AFTER):], now):
                bonus += val
        elif key == "syn_vs_marked":
            if is_marked(enemy):
                bonus += val
        elif key == "hunters_mark_per_hit":
            # The streak of the *previous* arrows, and only while it is warm:
            # a stale streak (last hit outside the window) is worth nothing.
            streak = (enemy.hit_streak.get(weapon.weapon_id, 0)
                      if hit_within(enemy, weapon.weapon_id, now) else 0)
            cap = int(weapon.effect("hunters_mark_max", 5))
            bonus += val * min(max(streak, 0), cap)
    if weapon.weapon_id == "magic_rod":
        # Crossfire's other half lives on the Bow.
        bow = player.weapon_by_id("bow")
        if bow is not None and bow.effect("crossfire_rod_bonus") > 0.0 \
                and hit_within(enemy, "bow", now):
            bonus += bow.effect("crossfire_rod_bonus")
    return 1.0 + bonus


def pull(enemy, proj, strength: float) -> None:
    """Crowd Cleaner: drag `enemy` toward the centre of the swing -- the
    point half-way along the cone -- so a sweep bunches a crowd for the
    Bomb. A shot with no cone pulls toward its own position."""
    if strength <= 0.0:
        return
    if proj.cone_half_angle > 0.0:
        centre = proj.pos + proj.cone_dir * (proj.radius * 0.5)
    else:
        centre = pygame.Vector2(proj.pos)
    enemy.apply_knockback(centre - enemy.pos, strength)
