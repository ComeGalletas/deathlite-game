"""LD-10: which biome each terrace of an island wears, decided at generation.

The picking rule itself is unchanged and still documented below --- level 0 is
drawn like every other terrace but only from sheets that can meet the sea, and
each raised level differs in **biome** from the one under it. What moved is
*when* the answer is computed.

It used to be a rendering decision: `TileSheets` worked the palette out at bake
time from the seed and the room id. That was fine while the only consumer was
the tile painter, and it stops being fine the moment anything in the world
itself depends on the biome -- a rocky terrace wants rocks scattered on it, not
trees. Two modules deriving the same answer from the same seed is the setup for
them to disagree, which is a bug this feature has already had once (filename
adjacency against biome adjacency).

So the island's palette is generation output now, stored on the room, and
rendering reads it rather than re-deriving it. It is the same shape as the
stair rule: generation classifies, rendering picks the art.

Picking is a seeded shuffle rather than a per-level random draw. A shuffle over
a pool at least as large as the terrace count cannot repeat at all, so the
"differs from below" walk is only doing real work when the pool is smaller;
with a pool of one it has nothing to offer and the island wears that one sheet
throughout, which is the honest degenerate answer rather than an error.

The RNG is keyed by seed and room id and constructed here, so it consumes
nothing from the world's own stream --- the same world generates identically
whether or not anything ever asks for a palette.
"""
from __future__ import annotations

import random

from game import config

_SALT = "biome"


def _terrain() -> dict:
    from game.assets import get_assets
    return get_assets().terrain


def biome_of(sheet: str) -> str:
    """This tileset's biome. Unlisted sheets are their own biome.

    The adjacency rule compares biomes rather than filenames because it has to:
    `tilemap_7`'s ground came from `tilemap_1`'s grass and sits 6.4 RGB units
    from it, against 104 for the rock sheet. Comparing filenames satisfied the
    rule on paper and rendered islands whose shore and first terrace were one
    continuous green with a cliff line drawn through it. Defaulting an unknown
    sheet to *itself* means a new tileset reads as "unlike everything" rather
    than silently pairing itself with something.
    """
    return _terrain().get("sheet_biomes", {}).get(sheet, sheet)


def has_shoreline(sheet: str) -> bool:
    """Does this tileset's shoreline block carry real surf?

    A sheet flagged otherwise draws every fringe from its raised block -- the
    biome simply has no beaches, which is the honest reading for a rocky
    highland and needs no new art.
    """
    return bool(_terrain().get("sheet_flags", {}).get(sheet, {})
                .get("shoreline", True))


def scatter_mix(sheet: str | None):
    """`(kinds, weights, per_1000)` for a terrace wearing `sheet`, or None.

    The mix is the point of the biome table, not a decoration of it: a rock
    terrace wants boulders where a forest one wants trunks, and the density
    differs as much as the mix does -- open sand is meant to read as open.
    Values live in `data/terrain.json` under each biome's `scatter` block; None
    here means the biome declares none and the caller keeps its own default.
    """
    if not sheet:
        return None
    spec = _terrain().get("biomes", {}).get(biome_of(sheet), {}).get("scatter")
    if not spec:
        return None
    weights = spec.get("weights", {})
    if not weights:
        return None
    # JSON preserves author order, which is what keeps the weighted draw
    # reproducible for a seed; the table lists the kinds in one order
    # throughout.
    kinds = tuple(weights)
    return kinds, tuple(float(weights[k]) for k in kinds), float(spec["per_1000"])


def floor_palette(seed, room_id: int, levels, sheets, family=None,
                  allowed=None) -> dict[int, str]:
    """`{level: sheet}` for one island, level 0 included.

    `sheets` are the tilesets this island's topography may wear. `family` maps
    a sheet to its biome -- two sheets of one biome count as the same for the
    adjacency rule -- and defaults to identity, which makes the rule per-file.
    `allowed(level, sheet)` is the per-level filter: it is what keeps a sheet
    with no surf block off the shoreline.
    """
    if not sheets:
        return {}
    fam = family or (lambda sheet: sheet)
    ok = allowed or (lambda _level, _sheet: True)
    rng = random.Random(f"{seed}:{_SALT}:{room_id}")
    bag = list(sheets)
    rng.shuffle(bag)

    out: dict[int, str] = {}
    below = None
    i = 0
    for level in sorted(levels):
        legal = [s for s in bag if ok(level, s)]
        if not legal:
            continue                    # nothing this island owns fits here
        pick = legal[i % len(legal)]
        # Take the next sheet in the shuffled order whose biome is not the one
        # the terrace below wears. A full lap without finding one means the
        # island owns nothing else legal here; the repeat is then the only
        # answer.
        for _ in range(len(legal)):
            pick = legal[i % len(legal)]
            i += 1
            if fam(pick) != below:
                break
        out[level] = pick
        below = fam(pick)
    return out


def assign_palettes(rooms, seed) -> None:
    """Give every island its `{level: sheet}`, in place.

    Runs after the height maps are built (it needs the levels) and before the
    scatter (which reads the biomes). Draws no RNG from the world stream.
    """
    for room in rooms:
        if not room.topography:
            continue
        spec = config.HEIGHTMAP_TOPOGRAPHIES.get(room.topography, {})
        beachless = bool(spec.get("allow_beachless_shore", False))

        def allowed(level, sheet, _beachless=beachless):
            # Level 0 is the only terrace that meets the sea, so it is the only
            # one that needs a real surf block. Derived from the flag rather
            # than from a per-topography list, so a new tileset cannot silently
            # end up on a shoreline it has no art for. A topography may opt out
            # (`boss` does, deliberately, to see what beachless reads like).
            return level > 0 or _beachless or has_shoreline(sheet)

        levels = ({c.level for c in room.grid.values()} if room.grid
                  else set(range(room.floor + 1)))
        room.palette = floor_palette(seed, room.id, levels,
                                     spec.get("sheets", ()),
                                     family=biome_of, allowed=allowed)
