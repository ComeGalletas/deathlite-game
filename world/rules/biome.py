"""What a tileset *is*: its biome, whether its shoreline block carries surf,
and the obstacle mix its biome scatters. Lookups into `data/terrain.json`,
read by generation (the palette pick, the scatter), by the tile painter and
by the decor -- so they live here, below all three.

Deciding which sheet each terrace wears is generation's job
(`world/gen/biomes.py`); this module only says what a sheet is.
"""
from __future__ import annotations


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
