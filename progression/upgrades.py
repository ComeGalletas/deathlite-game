"""Level-up upgrade pool (spec 3.5).

An `Upgrade` is a small record: identity, weight, a validity predicate, and an
`apply` callback. Weapon-specific upgrades are generated per owned weapon so an
option like "Arcane Bolt: +3 damage" only appears if that weapon is owned
(spec 3.5: "Do not offer 'increase damage of weapon X' if weapon X is not
owned").

Upgrades are behavior, so they live in code; blessings and items (Phase 2) are
the data-driven content systems. `roll_choices` is pure given a seeded RNG so it
can be unit tested (spec 8: "Level-up selection").
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from combat.weapons import Weapon
from progression.stats import FLAT, MULT, Modifier

MAX_WEAPONS = 6


@dataclass
class Upgrade:
    id: str
    title: str
    description: str
    weight: float
    apply: Callable[["object"], None]
    max_stacks: int = 99
    tags: tuple[str, ...] = ()


# --- generic stat upgrades ----------------------------------------------
# Each stacks as its own StatSet modifier keyed by upgrade id + stack index, so
# taking "Fleet Foot" three times compounds as 1.10^3 and can be inspected /
# removed independently.
def _stat_mod(upgrade_id: str, stat: str, op: str, value: float):
    def _apply(player):
        stack = player.upgrade_stacks.get(upgrade_id, 0) + 1
        player.add_modifiers(Modifier(stat, op, value, f"upg:{upgrade_id}#{stack}"))
    return _apply


def _apply_vitality(amount: float):
    def _apply(player):
        stack = player.upgrade_stacks.get("max_hp", 0) + 1
        player.add_modifiers(Modifier("max_hp", FLAT, amount, f"upg:max_hp#{stack}"))
        player.heal(amount)  # feel: the extra HP is filled immediately
    return _apply


def _generic_upgrades() -> list[Upgrade]:
    return [
        Upgrade("move_speed", "Fleet Foot", "+10% movement speed", 10,
                _stat_mod("move_speed", "move_speed", MULT, 0.10),
                max_stacks=5, tags=("utility",)),
        Upgrade("max_hp", "Vitality", "+20 max HP (and heal 20)", 10,
                _apply_vitality(20), max_stacks=8, tags=("defense",)),
        Upgrade("pickup_radius", "Greed", "+30 pickup radius", 8,
                _stat_mod("pickup_radius", "pickup_radius", FLAT, 30),
                max_stacks=5, tags=("utility",)),
        Upgrade("damage_multiplier", "Focus", "+12% damage (all weapons)", 9,
                _stat_mod("damage_multiplier", "damage_multiplier", FLAT, 0.12),
                max_stacks=10, tags=("offense",)),
        Upgrade("attack_speed", "Haste", "+12% attack speed (all weapons)", 9,
                _stat_mod("attack_speed", "attack_speed_multiplier", FLAT, 0.12),
                max_stacks=10, tags=("offense",)),
        Upgrade("projectile_speed", "Velocity", "+15% projectile speed", 6,
                _stat_mod("projectile_speed", "projectile_speed_multiplier", FLAT, 0.15),
                max_stacks=6, tags=("offense",)),
        Upgrade("armor", "Iron Skin", "+2 armor", 7,
                _stat_mod("armor", "armor", FLAT, 2), max_stacks=6, tags=("defense",)),
        Upgrade("luck", "Fortune", "+1 luck", 5,
                _stat_mod("luck", "luck", FLAT, 1), max_stacks=5, tags=("utility",)),
    ]


# --- weapon-specific upgrades (generated per owned weapon) ------------
def _weapon_upgrades(weapon: Weapon) -> list[Upgrade]:
    wid = weapon.weapon_id
    name = weapon.name

    def dmg(player):
        weapon.bonus["damage"] += 4
    def cd(player):
        weapon.bonus["cooldown_mult"] *= 0.88
    def proj(player):
        weapon.bonus["projectile_count"] += 1
    def area(player):
        weapon.bonus["area"] += 3
    def pierce(player):
        weapon.bonus["pierce"] += 1

    return [
        Upgrade(f"{wid}:damage", f"{name}: Sharpen", "+4 damage", 8, dmg,
                max_stacks=12, tags=("offense", "weapon")),
        Upgrade(f"{wid}:cooldown", f"{name}: Rapid", "-12% cooldown", 7, cd,
                max_stacks=8, tags=("offense", "weapon")),
        Upgrade(f"{wid}:projectile", f"{name}: Multishot", "+1 projectile", 5,
                proj, max_stacks=4, tags=("offense", "weapon")),
        Upgrade(f"{wid}:area", f"{name}: Wide", "+3 area", 5, area,
                max_stacks=6, tags=("area", "weapon")),
        Upgrade(f"{wid}:pierce", f"{name}: Penetrate", "+1 pierce", 5, pierce,
                max_stacks=5, tags=("offense", "weapon")),
    ]


def _new_weapon_upgrades(player, content) -> list[Upgrade]:
    owned = {w.weapon_id for w in player.weapons}
    if len(owned) >= MAX_WEAPONS:
        return []
    out: list[Upgrade] = []
    for wid, definition in content.weapons.items():
        if wid in owned:
            continue
        d = definition

        def _apply(player, _wid=wid, _d=d):
            player.weapons.append(Weapon(_wid, _d))

        out.append(Upgrade(
            f"new:{wid}", f"New Weapon: {d.get('name', wid)}",
            d.get("description", "Add this weapon to your arsenal"),
            # More attractive while the arsenal is small.
            14 if len(owned) < 3 else 6,
            _apply, max_stacks=1, tags=("weapon", "new")))
    return out


# --- pool assembly + rolling -------------------------------------------
def build_pool(player, content) -> list[Upgrade]:
    pool = _generic_upgrades()
    for weapon in player.weapons:
        pool.extend(_weapon_upgrades(weapon))
    pool.extend(_new_weapon_upgrades(player, content))
    return pool


def valid_choices(player, content) -> list[Upgrade]:
    taken = player.upgrade_stacks
    return [u for u in build_pool(player, content)
            if taken.get(u.id, 0) < u.max_stacks]


def roll_choices(player, content, rng: random.Random,
                 n: int = 3) -> list[Upgrade]:
    """Pick up to `n` distinct upgrades by weight. Never returns an invalid or
    maxed-out option. If fewer than `n` remain, returns what is available."""
    candidates = valid_choices(player, content)
    chosen: list[Upgrade] = []
    while candidates and len(chosen) < n:
        weights = [u.weight for u in candidates]
        pick = rng.choices(candidates, weights=weights, k=1)[0]
        chosen.append(pick)
        candidates.remove(pick)
    return chosen


def apply_choice(player, upgrade: Upgrade) -> None:
    upgrade.apply(player)
    stacks = player.upgrade_stacks
    stacks[upgrade.id] = stacks.get(upgrade.id, 0) + 1
