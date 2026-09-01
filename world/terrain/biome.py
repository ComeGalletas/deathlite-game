"""LD-9: which ground tileset each terrace of an island wears.

Until now the height-map worlds read a fixed `floor -> sheet` map out of
`data/terrain.json`, so every island on every seed wore sand at level 1 and rock
at level 2. That was always labelled a stand-in. This replaces it with a
**pool**: the tilesets are listed without a floor attached, and each island
draws its own terraces from that list.

The brief set the rule --- *at least three tilemaps per island, and no two
adjacent floors share one*. An island here is one room, and its floors are its
levels, so the two halves of that rule land as:

* **level 0 is not drawn from the pool.** It keeps the room-kind palette, and
  that is a constraint rather than a preference: level 0 is the only terrace
  that meets the sea, so it is the only one that needs a real shoreline block
  with surf in it. Every sheet in the pool is flagged `shoreline: false`. Level
  0 therefore supplies the island's *first* tileset for free, and the pool only
  has to cover the raised terraces.
* **each raised level differs from the one below it**, level 1 included ---
  which is what stops an island being one flat colour from the waterline up.

That second rule compares the **material**, not the filename, and it has to.
`tilemap_7` is a different file from `tilemap_1` but its ground was built from
`tilemap_1`'s grass and sits 6.4 RGB units away from it, against 104 for the
rock sheet and 110 for the sand. Comparing filenames satisfied the rule on
paper and rendered islands whose shore and first terrace were one continuous
green with a cliff line drawn through it. `data/terrain.json` names each
sheet's family in `sheet_biomes`; an unlisted sheet is its own family, so a new
tileset defaults to "unlike everything" rather than silently pairing itself
with something.

Picking is a seeded shuffle rather than a per-level random draw. A shuffle over
a pool at least as large as the terrace count cannot repeat at all, so the
"differs from below" walk below is only doing real work when the pool is
smaller; with a pool of one it has nothing to offer and the island wears that
one sheet throughout, which is the honest degenerate answer rather than an
error.

The RNG is keyed by seed and room id and constructed here, so it consumes
nothing from the world's own stream --- the same world generates identically
whether or not anything ever asks for a palette.
"""
from __future__ import annotations

import random

_SALT = "biome"


def floor_palette(seed, room_id: int, levels, pool, base=None,
                  family=None) -> dict[int, str]:
    """`{level: sheet}` for one island's raised terraces.

    `levels` are the room's raised levels (0 is the caller's business, see the
    module docstring); `base` is what level 0 wears, so the lowest terrace can
    avoid matching the ground it rises out of. `family` maps a sheet to its
    material -- two sheets of one material count as the same for the adjacency
    rule. It defaults to identity, which makes the rule per-file.
    """
    if not pool:
        return {}
    fam = family or (lambda sheet: sheet)
    rng = random.Random(f"{seed}:{_SALT}:{room_id}")
    bag = list(pool)
    rng.shuffle(bag)

    out: dict[int, str] = {}
    below = fam(base) if base is not None else None
    i = 0
    for level in sorted(levels):
        pick = bag[i % len(bag)]
        # Take the next sheet in the shuffled order whose material is not the
        # one the terrace below wears. A full lap without finding one means the
        # pool holds nothing else; the repeat is then the only answer.
        for _ in range(len(bag)):
            pick = bag[i % len(bag)]
            i += 1
            if fam(pick) != below:
                break
        out[level] = pick
        below = fam(pick)
    return out
