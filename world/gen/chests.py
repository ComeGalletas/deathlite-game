"""Treasure chests, seated once the world is final (CB-9).

The last stage of `generate_world_steps`, and the one that finally *uses*
`layout.resource_points`. That stage (`world/gen/spawnpoints.py`) already did
the hard part: eight anchors per island, each on plain ground inside its
terrace margin, clear of obstacles and bridge mouths, two tiles off any enemy
spawn point, two tiles off the straight line between bridge mouths -- "so loot
is found by looking around, not by walking through" -- farthest-point spaced,
and *preferring cells that touch a cliff or an obstacle so a chest has
something to sit against*. Its `kind` hint already includes `"chest"`. All this
stage has to decide is how many chests an island carries, which tier each is,
and which of the anchors they take.

**How many.** `_CHEST_COUNT_WEIGHTS`: at most 5, averaging 2.50, never 0 --
the owner's brief. An island with fewer anchors than that gets what it has.

**Which tier.** `_CHEST_RARITY_WEIGHTS`, with `_CHEST_CAPS` holding `rare` and
`epic` to one per island; a capped draw falls back to `common` rather than
being re-rolled, so a run of unlucky draws cannot loop.

**Which anchor.** Anchors hinted `"chest"` first (that hint averages 1.6 an
island, so it usually covers a 2-3 draw), then the rest. The richest chest is
seated first so the epic gets the best-sheltered spot rather than whatever is
left.

**Villages carry none**, for free: `place_points` gives a village island no
anchors at all, which is the sanctuary rule (HI-1) holding without a special
case here.

**RNG.** A private `random.Random` keyed by seed and island, the same trick
`_island_resource_points` uses, so this stage draws nothing from the world's
stream and moves no room, bridge, obstacle or spawn point. What it *does*
change is the layout fingerprint, because `world/digest.py` walks the model
generically and `layout.chests` is a new field on it -- see the CB-9 journal
entry.
"""
from __future__ import annotations

import random

from world.gen.tuning import (
    _CHEST_CAPS, _CHEST_COUNT_WEIGHTS, _CHEST_RARITIES, _CHEST_RARITY_WEIGHTS,
)
from world.layout import Chest

__all__ = ["place_chests", "island_chest_count", "island_chest_rarities"]


def island_chest_count(rng: random.Random, available: int) -> int:
    """How many chests one island carries, capped by the anchors it has."""
    if available <= 0:
        return 0
    counts = sorted(_CHEST_COUNT_WEIGHTS)
    weights = [_CHEST_COUNT_WEIGHTS[c] for c in counts]
    return min(available, rng.choices(counts, weights=weights, k=1)[0])


def island_chest_rarities(rng: random.Random, count: int) -> list[str]:
    """`count` tiers for one island, poorest first, honouring the per-island
    caps. Sorted so the caller seats the richest chest on the best anchor."""
    seated: dict[str, int] = {}
    out: list[str] = []
    weights = [_CHEST_RARITY_WEIGHTS[r] for r in _CHEST_RARITIES]
    for _ in range(count):
        rarity = rng.choices(_CHEST_RARITIES, weights=weights, k=1)[0]
        cap = _CHEST_CAPS.get(rarity)
        if cap is not None and seated.get(rarity, 0) >= cap:
            rarity = _CHEST_RARITIES[0]     # capped out: a common one instead
        seated[rarity] = seated.get(rarity, 0) + 1
        out.append(rarity)
    out.sort(key=_CHEST_RARITIES.index)
    return out


def _island_anchors(layout, room_id: int) -> list:
    """This island's resource anchors, the ones hinted `"chest"` first. Both
    groups keep the order `place_points` emitted them in, which is
    farthest-point sampled, so taking from the front spreads the chests."""
    mine = [p for p in layout.resource_points if p.room_id == room_id]
    return ([p for p in mine if p.kind == "chest"]
            + [p for p in mine if p.kind != "chest"])


def place_chests(layout) -> list:
    """Fill and return `layout.chests`. Idempotent: it starts from empty."""
    layout.chests = []
    for room in layout.rooms:
        anchors = _island_anchors(layout, room.id)
        if not anchors:
            continue                        # a village, or an island with no room
        rng = random.Random(layout.seed * 104729 + room.id)
        rarities = island_chest_rarities(
            rng, island_chest_count(rng, len(anchors)))
        # Richest first onto the best anchors, then recorded poorest first so
        # the list reads in the order the tiers are authored.
        seated = [Chest(room.id, a.floor, a.x, a.y, r)
                  for a, r in zip(anchors, reversed(rarities))]
        seated.sort(key=lambda c: _CHEST_RARITIES.index(c.rarity))
        layout.chests.extend(seated)
    return layout.chests
