# Chest tiers — how to add one

The world's treasure chests (CB-9, `combat_balance_journal.md`) come in four
tiers: common, uncommon, rare and epic. The owner plans no more for now
(DOC-006, 2026-09-24), but the design stays modular so a tier can be added
later. A tier is mostly data. This page lists every place one is named.

## What a tier is

| where | what it holds |
|---|---|
| `data/loot/chests.json` `rarities` | The canonical tier order, poorest first. `game/content.py::_check_chests` validates the table against it at load. |
| `data/loot/chests.json` `chests.<tier>` | The payout: `sprite` (the rig), `color` (the prompt/fallback ink), `gold` [min, max], `potion` (a potion rarity; a tier richer than the best potion hands out the best one), and an optional `blessing` {`chance`, `weights` by blessing rarity}. |
| `data/loot/prop_sprites.json` `chest_<tier>` | The rig: a 4-frame `open` strip (frame 0 closed, frame 3 open), anchored bottom-centre. |
| `assets/items/chests/chest_<tier>.png` | The strip. Cut from `chests.png` by `tools/asset_pipeline/cut_chest_sheets.py`: add a row to its `STRIPS` table, then run it and its `--check`. The source sheet holds eight skins and four are used, so four spare skins are already in it. |
| `world/gen/tuning.py` | Placement: `_CHEST_RARITIES` (the order again), `_CHEST_RARITY_WEIGHTS` (the draw per chest), `_CHEST_CAPS` (at most one a tier per island, for the rarest). |

`progression/chests.py` (gold, potion, blessing rolls) and
`world/gen/chests.py` (count, tiers, anchors) read tiers by name and need no
change for a new one.

## Adding a tier, in order

1. Add it to `rarities` and `chests` in `data/loot/chests.json`.
2. Cut its strip (a new `STRIPS` row in `cut_chest_sheets.py`, then `--check`) and
   add its rig to `prop_sprites.json`.
3. Add it to the three placement tables in `world/gen/tuning.py`. A new rare
   tier should take a cap.
4. Re-pin the world digests (`python -m tools.verification.world_digest
   --write`): the chest draw changes every world. The tests follow the
   generator.
5. Extend `tests/progression/test_chests.py`: payout ranges, the potion
   fallback, the blessing weights.

## Known wrinkle

`world/gen/tuning.py`'s `_CHEST_RARITIES` repeats `chests.json`'s
`rarities`, and the placement weights and caps are code rather than data.
When a tier is added, fold them into `chests.json` (a `placement` block read
by `world/gen/chests.py`), so a tier lives in one file.
