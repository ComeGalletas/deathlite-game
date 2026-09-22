"""Which buff buildings hand out an element (design §7.1).

A buff building may roll elemental when the run seats its interactables.
One that did still gives its buff exactly as before, and then offers its
rolled element to a weapon of the player's choosing (owner's decision,
2026-09-21: it grants both, not one or the other).

The roll is taken from a generator seeded on the world seed and the
building's own spot rather than from the run's shared stream. That keeps it
deterministic for a seed without shifting every other roll in the run,
which is what would break the pinned world digests.
"""
from __future__ import annotations

import random

from combat.elements.ids import ELEMENTS, element_from_key

BLOCK = "elements"


def settings(content) -> dict | None:
    block = content.buildings.get(BLOCK)
    return block if isinstance(block, dict) else None


def roll(run, obstacle):
    """The element this building offers, or `None` for a plain one."""
    block = settings(run.content)
    if not block:
        return None
    chance = float(block.get("chance", 0.0))
    if chance <= 0.0:
        return None
    # A string seed, not a tuple: `random.Random` takes None, an int, a
    # float, a str or bytes, and a tuple raises.
    rng = random.Random(
        f"element:{int(run.seed)}:{round(obstacle.pos.x)}:{round(obstacle.pos.y)}")
    if rng.random() >= chance:
        return None
    return _weighted(block.get("weights", {}), rng)


def _weighted(weights: dict, rng: random.Random):
    """Pick an element by weight. An unknown or non-positive entry is
    ignored rather than fatal -- this is world data, which degrades in this
    project rather than refusing to load."""
    pool = []
    for key, weight in weights.items():
        if key.startswith("_"):
            continue
        try:
            element = element_from_key(key)
        except KeyError:
            continue
        if float(weight) > 0.0:
            pool.append((element, float(weight)))
    if not pool:
        return rng.choice(ELEMENTS)
    total = sum(w for _e, w in pool)
    roll_at = rng.random() * total
    for element, weight in pool:
        roll_at -= weight
        if roll_at <= 0.0:
            return element
    return pool[-1][0]
