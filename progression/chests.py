"""What a treasure chest contains (CB-9).

Pure decisions driven entirely by `data/chests.json`; no pygame, no game
state. `PlayingState` supplies the RNG and the table, the way it does for
CB-8's potion drops.

Three payloads, and the tier is the only input:

  * `gold(rarity, table, rng)` -- a random amount inside the tier's range. The
    ladder starts at the brief's 10-25 and roughly doubles a tier.
  * `potion_rarity(rarity, table)` -- **one** potion, always, and it appears on
    top of the chest (`potion_lift`). The owner's rule is that a richer chest
    buys a *better* potion, never more of them, so this returns a bare CB-8
    rarity. There is no epic potion, so an epic chest hands out a rare one and
    its edge over a rare chest is the gold and the blessing tier.
  * `blessing_rarity(rarity, table, rng)` -- the rarity of the blessing this
    chest carries, or `None` when it carries none. Common chests never do;
    uncommon ones roll for it; rare and epic always have one, weighted toward
    the poorer of their two options.

Which *blessing* of that rarity is then the offering's business
(`progression.blessings.roll_offering(..., rarities=...)`), not this module's.
"""
from __future__ import annotations

import random


def spec(rarity: str, table: dict) -> dict:
    """The `data/chests.json` row for one tier."""
    return table["chests"][rarity]


def rarities(table: dict) -> tuple[str, ...]:
    """The canonical tier order, poorest first."""
    return tuple(table["rarities"])


def gold(rarity: str, table: dict, rng: random.Random) -> int:
    """A random gold amount inside the tier's range, both ends inclusive."""
    lo, hi = (int(v) for v in spec(rarity, table)["gold"])
    return rng.randint(lo, hi)


def potion_rarity(rarity: str, table: dict) -> str:
    """The CB-8 rarity of the one potion this chest holds."""
    return str(spec(rarity, table)["potion"])


def blessing_rarity(rarity: str, table: dict,
                    rng: random.Random) -> str | None:
    """The rarity of this chest's blessing, or `None` if it has none."""
    blessing = spec(rarity, table).get("blessing")
    if blessing is None:
        return None
    if rng.random() >= float(blessing.get("chance", 0.0)):
        return None
    weights = {k: float(v) for k, v in blessing["weights"].items()
               if not k.startswith("_")}
    keys = sorted(weights)
    total = sum(weights[k] for k in keys)
    if total <= 0.0:
        return None
    cut = rng.random() * total
    upto = 0.0
    for key in keys:
        upto += weights[key]
        if cut < upto:
            return key
    # Float drift only: the last rarity with a non-zero weight.
    return next(k for k in reversed(keys) if weights[k] > 0.0)


def sprite_rig(rarity: str, table: dict) -> str:
    return str(spec(rarity, table)["sprite"])


def colour(rarity: str, table: dict) -> tuple[int, int, int]:
    r, g, b = spec(rarity, table).get("color", (200, 180, 120))
    return int(r), int(g), int(b)


def radius(table: dict) -> float:
    """The interaction radius every chest carries."""
    return float(table.get("radius", 24))


def potion_lift(table: dict) -> float:
    """How far **above** the chest's baseline its potion is centred.

    The potion lands on the chest rather than beside it, so it reads as coming
    out of the box it was found in; the renderer draws potions after chests, so
    the chest art never covers it.
    """
    return float(table.get("potion_lift", 16))


def open_seconds(table: dict) -> float:
    """How long the lid takes to fly open."""
    return float(table.get("open_seconds", 0.45))
