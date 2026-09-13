"""Health potion drops (CB-8): who drops one, and which one.

Two pure decisions, both driven entirely by `data/loot/potions.json`:

  * `drop_chance(base_hp, table)` -- how likely a kill is to drop anything. The
    chance rises with the enemy's **base** HP (the authored number in
    `data/enemies/enemies.json`, never the run-time `hp_mult`-scaled `max_hp`, or every
    enemy would drift toward the cap as a run goes on) and saturates at the
    table's `cap`.

  * `roll(base_hp, table, rng)` -- once a drop is won, which rarity it is. The
    enemy's own rarity band (also off base HP) selects a row of weights, so a
    common enemy can never roll a rare potion and a rare enemy can never roll a
    common one.

No pygame, no game state: `PlayingState` supplies the RNG and the table.
"""
from __future__ import annotations

import math
import random


def enemy_rarity(base_hp: float, table: dict) -> str:
    """The enemy's rarity band for `base_hp`, weakest band first."""
    order = table["rarities"]
    bands = table["enemy_rarity_hp"]
    rarity = order[0]
    for candidate in order[1:]:
        if base_hp >= float(bands[candidate]):
            rarity = candidate
        else:
            break
    return rarity


def drop_chance(base_hp: float, table: dict) -> float:
    """Probability in 0..1 that an enemy with `base_hp` drops a potion.

    `floor + (cap - floor) * t**exponent`, with `t` the log-normalised position
    of `base_hp` between `hp_min` and `hp_max`, clamped. Log-normalised because
    HP spans 5 -> 390: on a linear slide every enemy below the Lumberer would
    sit within a couple of points of the floor.
    """
    curve = table["drop_chance"]
    lo, hi = float(curve["hp_min"]), float(curve["hp_max"])
    floor, cap = float(curve["floor"]), float(curve["cap"])
    span = math.log(hi) - math.log(lo)
    t = (math.log(max(base_hp, 1e-9)) - math.log(lo)) / span if span > 0.0 else 1.0
    t = min(1.0, max(0.0, t))
    return floor + (cap - floor) * (t ** float(curve["exponent"]))


def roll_rarity(base_hp: float, table: dict, rng: random.Random) -> str:
    """Pick a potion rarity for an enemy of `base_hp` (a drop is assumed won)."""
    weights = table["rarity_weights"][enemy_rarity(base_hp, table)]
    order = table["rarities"]
    values = [float(weights[r]) for r in order]
    total = sum(values)
    cut = rng.random() * total
    upto = 0.0
    for rarity, weight in zip(order, values):
        upto += weight
        if cut < upto:
            return rarity
    # Float drift only: the last rarity with a non-zero weight.
    return next(r for r, w in zip(reversed(order), reversed(values)) if w > 0.0)


def roll(base_hp: float, table: dict, rng: random.Random) -> str | None:
    """The whole decision for one kill: a potion rarity, or `None` for no drop."""
    if rng.random() >= drop_chance(base_hp, table):
        return None
    return roll_rarity(base_hp, table, rng)


def heal_amount(rarity: str, table: dict) -> float:
    return float(table["potions"][rarity]["heal"])


def sprite_rig(rarity: str, table: dict) -> str:
    return table["potions"][rarity]["sprite"]


def colour(rarity: str, table: dict) -> tuple[int, int, int]:
    r, g, b = table["potions"][rarity].get("color", (235, 110, 130))
    return int(r), int(g), int(b)
