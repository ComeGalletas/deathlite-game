"""Raising a blessing one level on the hero (design §21).

`player.blessings` maps blessing id -> current level. Applying level N adds
each effect's *delta* between level N and N-1, so the running total always
equals `levels[N-1]`:

  * stat          -> one `Modifier` on the hero's StatSet, source
                     `bless:<id>#<level>` (removable per level, like upgrades)
  * weapon_bonus  -> `weapon.bonus[field] += delta` (or `*=` for a mult field)
  * weapon_effect -> `weapon.effects[key] = value` (a total, read live by the
                     fire path / hit resolver)

A weapon blessing needs the weapon on the hero; the offering never shows one
otherwise, and `apply_blessing` raises if it is asked to anyway.
"""
from __future__ import annotations

from progression.blessings.catalog import BlessingDef
from progression.stats import FLAT, MULT, PCT, Modifier

_OP = {"flat": FLAT, "pct": PCT, "mult": MULT}


def level_of(player, bdef: BlessingDef) -> int:
    return int(player.blessings.get(bdef.id, 0))


def weapon_of(player, weapon_id: str):
    for w in player.weapons:
        if w.weapon_id == weapon_id:
            return w
    return None


def apply_blessing(player, bdef: BlessingDef) -> int:
    """Raise `bdef` one level on `player`; return the new level. Rebuilds the
    combat aggregate afterwards so callers that watch it see a fresh object."""
    from progression.blessings.effects import rebuild

    level = level_of(player, bdef) + 1
    if level > bdef.max_level:
        raise ValueError(f"{bdef.id}: already at max level {bdef.max_level}")
    weapon = None
    if bdef.weapon is not None:
        weapon = weapon_of(player, bdef.weapon)
        if weapon is None:
            raise ValueError(f"{bdef.id}: the hero does not own {bdef.weapon}")

    mods = []
    heal = 0.0
    for e in bdef.effects:
        if e.type == "stat":
            delta = e.delta(level)
            mods.append(Modifier(e.stat, _OP[e.op], delta, f"bless:{bdef.id}#{level}"))
            if e.heal:
                heal += delta
        elif e.type == "weapon_bonus":
            if e.mode == "mult":
                weapon.bonus[e.field] = weapon.bonus.get(e.field, 1.0) * e.delta(level)
            else:
                weapon.bonus[e.field] = weapon.bonus.get(e.field, 0.0) + e.delta(level)
        else:
            weapon.effects[e.key] = e.value_at(level)
    if mods:
        player.add_modifiers(*mods)
    if heal > 0.0:
        player.heal(heal)                     # feel: new max HP is filled at once
    if weapon is not None:
        weapon.level += 1                     # the HUD's "Lv" is 1 + blessing levels
    player.blessings[bdef.id] = level
    rebuild(player)
    return level
