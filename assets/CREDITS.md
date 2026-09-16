# Asset Credits

All game **content** — design, code, data, and the procedurally synthesised
sound effects in `systems/audio.py` — is original to this project, with two
exceptions that are licensed rather than original: the art packs listed below,
and the two background music tracks in `assets/music/`.

## Art — "Tiny Swords" by Pixel Frog

**Most PNGs under `assets/` are from the "Tiny Swords" asset pack by Pixel Frog**
(itch.io); the remaining art comes from the purchased packs listed at the end of
this file. `.aseprite` editor sources and `.DS_Store` files were removed; only
sprites the game loads (plus a set of reserve packs kept for future use) remain.

| Field | Value |
|-------|-------|
| Pack name | Tiny Swords |
| Author | Pixel Frog |
| Source URL | https://pixelfrog-assets.itch.io/tiny-swords |
| Licence | Pixel Frog's own terms (not CC0): use in personal and commercial projects is allowed, modification is allowed; redistributing, reselling or repackaging the assets is not, even when modified |
| Attribution required? | No (credit is optional but welcomed by the author) |
| Purchased? | Yes, paid for on itch.io (pay-what-you-want pack) |

### General usage

Tiny Swords supplies the main art of the game:

- **World** — `assets/terrain/`: the grass tilemaps, water and shoreline
  animations and the plank bridge that build every island, plus the trees,
  bushes, rocks, stumps, decorations, clouds and animals scattered over them.
  The village buildings in `assets/buildings/`, the forge and healing facilities
  and the sheep NPCs are also from this pack.
- **Characters** — `assets/characters/`: the three heroes are Tiny Swords units
  (Aegis = blue Warrior, Kestrel = yellow Archer, Nihil = purple Monk), with the
  shared death poof and the hero summons drawn from the same sheets.
- **Enemies** — `assets/enemies/`: every enemy variant and the boss are Tiny
  Swords mobs (skull, spider, turtle, bumblebee, gnomes, bomb fish, panda, bear,
  troll, minotaur, thief, hex shaman, pig rider, giant bat).
- **Interface** — `assets/ui/`: the buttons, ribbons and pointer cursors of the
  menus come from the Tiny Swords UI sheets.

Items, weapon effects, potions, chests and other visual effects come from the
purchased packs listed at the end of this file. `assets/unused/` holds reserve
art from all packs that is kept in the tree but not loaded by the game.

## Music — Pixabay (`assets/music/`)

The two streamed background tracks are from [Pixabay](https://pixabay.com) and
are the only audio in the game that is not synthesised at runtime. They are
named by `config.MUSIC_TRACKS` and played by `systems/music.py`.

| Slot | Track | Author | Pixabay ID |
|------|-------|--------|------------|
| Main menu, hero select, Options, Rankings, Sanctuary, loading | Shakuhachi Sunrise (Full Version) | kaazoom | 553468 |
| In-run gameplay | Happy Adventure Quest | jorisvermeer | 572050 |

| Field | Value |
|-------|-------|
| Licence | [Pixabay Content License](https://pixabay.com/service/license-summary/) |
| Commercial use? | Yes |
| Modification allowed? | Yes |
| Attribution required? | No (credit is optional but appreciated by the community — given here anyway) |
| Purchased? | No (free download) |

### The one restriction that matters here

The Pixabay Content License prohibits selling or distributing Content **on a
standalone basis** — that is, in substantially the form it has on the site,
with no creative effort applied. Shipping the tracks inside the game as its
score is not a standalone distribution, so both the desktop and the web builds
are within the licence. Selling the MP3s as files, or releasing a soundtrack
of them, would not be.

The files ship as downloaded, at 320 kbps, and are streamed rather than
decoded into memory (see `systems/music.py`).

## Main screen art (`assets/ui/start_screen/`)

- `menu_background.png` — the full-screen menu backdrop. Taken from the Tiny
  Swords store page on itch.io (Pixel Frog's promotional art for the pack), not
  from the downloaded asset files.
- `text_title.png` — the game logo drawn above the menu options. An AI-generated generic logo.

All three are optional at runtime: the menu falls back to drawn text and a flat
fill when a file is missing.

## Additional art packs (purchased on itch.io)

| Pack | Author | Source URL |
|------|--------|------------|
| Fire Totem | CreativeKind | https://creativekind.itch.io/fire-totem-free |
| Pixel Art Potion Pack 32x32 | xnaxlzz | https://xnaxlzz.itch.io/pixel-art-potion-pack-32x32 |
| 32x32 RPG Swords with Evolutions | maasa | https://maasa.itch.io/32x32-rpg-swords-with-evolutions |
| Combat FX | RagnaPixel | https://ragnapixel.itch.io/combat-fx |
| Super Pixel Effects Gigapack | Untied Games | https://untiedgames.itch.io/super-pixel-effects-gigapack |
| Free RPG Maker Chests | franjatesa | https://franjatesa.itch.io/free-rpgmaker-chests |
| 750+ Effect and FX Pixel All | BDragon1727 | https://bdragon1727.itch.io/750-effect-and-fx-pixel-all |
| Goth | ansimuz | https://ansimuz.itch.io/goth |
