# Data layout journal

## 2026-09-12 -- `data/` regrouped by actor

**Request.** Review the JSON files that build the game's elements and group
them by the main element or actor they describe; then create the folders and
move the files.

**Before.** Twenty files flat in `data/`, all loaded by name in
`game/content.py` into one `Content` object. Every cross-reference between
files resolved either inside one actor's set or onto the weapon roster, which
is what made the grouping clean.

**After.** Each file moved with `git mv` into one of seven folders.

| Folder | Files | Why they sit together |
|---|---|---|
| `heroes/` | `characters`, `character_sprites`, `meta_upgrades` | a character names its sprite rig and starting weapon; meta upgrades are the hero's permanent stats |
| `weapons/` | `weapons`, `weapon_visuals`, `weapon_sprites`, `forges`, `blessings`, `offering`, `items` | forges and all weapon blessings key on a weapon id; visuals have one entry per weapon and per forge look and name rigs in `weapon_sprites` |
| `enemies/` | `enemies`, `bosses`, `enemy_sprites`, `spawn_tables` | enemies and bosses name a rig in `enemy_sprites`; the spawn tables are validated against the enemy ids at boot |
| `world/` | `terrain` | the tileset, biome, decoration and obstacle tables |
| `village/` | `npcs` | the human island's NPC tuning |
| `loot/` | `potions`, `chests`, `prop_sprites` | chests are checked against potions at load; `prop_sprites` is the orb, potion and chest art |
| `ui/` | `ui_sprites` | buttons, ribbons, HUD bars and the gem |

**What changed to follow the move.** The twenty `_load(...)` names and the
four-file sprite merge in `game/content.py`; four tests that open a data file
directly (`test_assets`, `test_melee_enemies`, `test_biome`,
`test_totem_sprite`); and every `data/<file>.json` path mention in code
comments, docstrings, `README.md`, `world/README.md` and the desktop spec
(55 files). The PyInstaller spec walks `data/` recursively and keeps
sub-folders, so packaging needed no change. Older journal entries keep the
flat paths they were written with.

**Left as is, noted for later.** `terrain.json` is four tables in one file
(floor sheets and palettes; biomes and decorations; obstacles; and 103 rigs of
which the village buildings are a quarter) and could be split the same way.
The village's art is still spread over `heroes/character_sprites.json` (the
NPC rigs) and `world/terrain.json` (`rigs`, `obstacles`); a sprite split by
actor rather than by domain would bring it under `village/`. `blessings.json`
mixes 15 stat blessings with 56 weapon blessings. None of these were part of
the request.

**Verification.** `get_content()` loads every file from the new paths; the
data-facing tests and the whole `unit` tier pass apart from failures caused by
a concurrent reorganisation in the same working tree (`game/dps_bench.py` and
the `utilities/` cut scripts moved by another session mid-run); a headless
`PlayingState` boots, spawns enemies, NPCs and chests, and draws a frame.
