"""How many props a terrace gets, and of which kinds.

The density tiers and the split of a room's floor into per-biome terraces. Both
answer "how much of what goes here", which is one concern and not the same one
as placing it.
"""
from __future__ import annotations

from world.gen import biomes


# --- density tiers --------------------------------------------------------
#
# Taxonomy only: the names live here, every rate lives in `data/terrain.json`.
# An entry names the tier it belongs to; a biome prices each tier per thousand
# cells. One budget for all of them made props compete -- the authored counts
# were shares of a single number, so raising the grass rate could only take
# props away from the boulders -- and that is the whole reason grass could not
# simply be made common.
GROUND_COVER, FEATURE, LANDMARK = "ground_cover", "feature", "landmark"
TIERS = (GROUND_COVER, FEATURE, LANDMARK)


def _cell_biomes(room, floor) -> dict:
    """`{(col, row): biome}` for a height-map room's interior cells.

    Empty for a legacy room: no grid, no palette, nothing to key on -- and the
    callers then treat every entry as universal, which is what that world has
    always done.
    """
    if not floor or not room.grid or not room.palette:
        return {}
    out = {}
    for pos in floor:
        cell = room.grid.get(pos)
        if cell is None:
            continue
        sheet = room.palette.get(cell.level)
        if sheet:
            out[pos] = biomes.biome_of(sheet)
    return out


def _terraces(room, floor) -> list:
    """`[(biome, cells)]` -- the room's interior split by the biome standing on
    it. One `(None, floor)` group for a legacy room, which is what keeps that
    world's decor exactly as it was."""
    fam_of = _cell_biomes(room, floor)
    if not fam_of:
        return [(None, floor or [])]
    groups: dict = {}
    for cell in floor:
        groups.setdefault(fam_of.get(cell), []).append(cell)
    return sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))


def _tier_scales(terrain, fam, n_cells, legal) -> dict:
    """`{tier: scale}` -- how far to stretch each tier's authored `per_room`
    counts on this terrace.

    `per_room` was tuned against LD-8 rooms of ~60 cells and is applied to
    height-map islands of several hundred, so the counts cannot be used as
    written; a biome's per-thousand rate sets the real budget and the counts
    become the *weights* by which its props share it.

    Split by tier because a single budget made every prop compete for it:
    raising the grass rate could only take props away from the boulders. A
    biome prices ground cover, features and landmarks separately, so grass can
    be common on a meadow and sparse on sand without touching either's stones.

    An empty dict for a biome that prices nothing -- the legacy world, which
    then uses the authored counts exactly as written.
    """
    spec = (terrain.get("biomes", {}).get(fam, {}).get("decor") if fam else None)
    rates = (spec or {}).get("per_1000")
    if not isinstance(rates, dict) or not n_cells:
        return {}
    out = {}
    for tier in TIERS:
        members = [e for e in legal if e["tier"] == tier]
        expect = sum((e.get("per_room", [0, 2])[0]
                      + e.get("per_room", [0, 2])[1]) / 2 for e in members)
        want = n_cells * float(rates.get(tier, 0.0)) / 1000.0
        out[tier] = want / expect if expect > 0 else 0.0
    return out
