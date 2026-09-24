# Asset Credits

All game **content** — design, code, data, and the procedurally synthesised
sound effects in `systems/audio.py` — is original to this project, with three
exceptions that are licensed rather than original: the art packs listed below,
the two background music tracks in `assets/music/`, and the recorded sound
effects in `assets/sound_effects/`.

> **Attribution is required** for the two grass-footstep recordings (CC BY 4.0).
> Everything else here is either attribution-optional or covered by a purchase;
> the Sound effects section below is the one that must not be dropped from a
> shipped build.

## Art — "Tiny Swords" by Pixel Frog

**Most PNGs under `assets/` are from the "Tiny Swords" asset pack by Pixel Frog**
(itch.io); the remaining art comes from the purchased packs listed at the end of
this file. `.DS_Store` files were removed, and `.aseprite` editor sources are kept
out of the shipped folders -- the one that came with the imp is archived under
`assets/unused/enemies/imp/` rather than deleted, which is where source art lives
in this project. That archive is **tracked**: the reserve library around it is
gitignored for its size, but the editor sources inside it are re-included
(`.gitignore`, the reserve block), because a source for art we ship belongs in
history and in every clone. `tests/entities/ai/test_imp.py` holds this file to
both halves of the promise. `assets/enemies/` and its siblings hold only sprites the game
loads, plus a set of reserve packs kept for future use.

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
  and the corral animals (the sheep and pigs in `assets/terrain/npcs/`) are also
  from this pack, as are the fish huts moored beside the bridges and the
  seahorse boats drifting round them (`assets/terrain/npcs/fish_hut/`,
  `assets/terrain/npcs/seahorse_boat/`).
- **Characters** — `assets/characters/`: the three heroes are Tiny Swords units
  (Aegis = blue Warrior, Kestrel = yellow Archer, Nihil = purple Monk), with the
  shared death poof and the hero summons drawn from the same sheets.
- **Enemies** — `assets/enemies/`: every enemy variant and the boss are Tiny
  Swords mobs (skull, spider, turtle, bumblebee, gnomes, bomb fish, panda, bear,
  troll, minotaur, thief, hex shaman, gnoll, harpoon shark, torch goblin,
  spear goblin, imp, pig rider, giant bat), together with the projectiles three of them throw (the slingshot
  gnome's acorn, the gnoll's bone, the harpoon shark's spear).
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

## Sound effects — Freesound (`assets/sound_effects/`)

Three recordings from [Freesound](https://freesound.org). Freesound licences
are chosen per upload, so these are **not** all the same: the two footsteps
require attribution, the growl does not.

| File in game | Source | Author | Freesound ID | Licence |
|--------------|--------|--------|--------------|---------|
| `footstep_grass_hard.wav` | [grass_footstep_hard_4.wav](https://freesound.org/s/386678/) | [laurenmg95](https://freesound.org/people/laurenmg95/) | 386678 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — **attribution required** |
| `footstep_grass_soft.wav` | [grass_footstep_soft_4.wav](https://freesound.org/s/386686/) | [laurenmg95](https://freesound.org/people/laurenmg95/) | 386686 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — **attribution required** |
| `monster_growl.wav` | [Monster_Growls_Grunts_10](https://freesound.org/s/869056/) | [SignatureSoundsOrg](https://freesound.org/people/SignatureSoundsOrg/) | 869056 | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — attribution not required (given anyway) |

### Changes made

CC BY 4.0 requires that modifications be indicated. **All three files were
modified.** None is used as downloaded:

- **Trimmed.** Each source was mostly dead air. The growl ran 14.08 s with the
  growl itself over by ~2.2 s and the remaining 11.9 s at a −84 dBFS noise
  floor; both footsteps carried about a second of silence after the step, and
  a further 0.23 s (hard) and 0.09 s (soft) of handling noise *before* it.
- **Resampled.** The growl was 96 kHz and is now 44.1 kHz, the rate the game
  opens its audio device at.
- **Normalised.** The growl was raised from −21.6 dBFS to −2.9 dBFS peak; the
  two footsteps were raised by a single shared factor, so their relative
  loudness is unchanged.
- **Faded.** A short fade-out was applied at each new end point so the cut does
  not click.

The originals are kept unmodified in `assets/sound_effects/unused/` under their
Freesound filenames, which carry the ID and author. The transformation is
reproducible: `python -m tools.asset_pipeline.cut_sound_effects`.

### Attribution text

> "grass_footstep_hard_4.wav" and "grass_footstep_soft_4.wav" by laurenmg95
> (freesound.org/s/386678, freesound.org/s/386686), licensed under CC BY 4.0;
> trimmed, normalised and faded for use in this game.
> "Monster_Growls_Grunts_10" by SignatureSoundsOrg (freesound.org/s/869056),
> CC0; trimmed, resampled, normalised and faded.

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
| Super Pixel Effects Gigapack | Untied Games | https://untiedgames.itch.io/super-pixel-effects-gigapack — used for the sanctuary heal loop (`assets/terrain/facilities/heal_effect.png`, cut from `spell_heal_002_large_green` by `tools/asset_pipeline/cut_heal_effect.py`); credit line per the pack licence: "Super Pixel Effects Gigapack - Will Tice / unTied Games" |
| Free RPG Maker Chests | franjatesa | https://franjatesa.itch.io/free-rpgmaker-chests |
| 750+ Effect and FX Pixel All | BDragon1727 | https://bdragon1727.itch.io/750-effect-and-fx-pixel-all |
| Goth | ansimuz | https://ansimuz.itch.io/goth |

### Where the additional packs are used

- **750+ Effect and FX Pixel All** — the elemental system's aura and reaction
  art (`documentation/journals/elemental_system_journal.md`, M10), cut by
  `tools/asset_pipeline/cut_element_effects.py`. The four auras in
  `assets/effects/elements/` (`fire.png` Part 12/586 row 0, `ice.png`
  Part 13/623 row 2, `thunder.png` Part 14/652 row 5 remapped to purple,
  `wind.png` Part 1/26 row 3) and the six reactions in
  `assets/effects/reactions/` (`frostburn.png` Part 4/186 row 1,
  `overload.png` Part 14/674 row 5 remapped across its own pair,
  `superconduct.png` Part 9/446 row 5 remapped across its own pair, and
  `firewind.png` / `icewind.png` / `thunderwind.png` all from Part 15/711 in
  rows 0, 2 and 5). The magic rod's own effects came from this pack earlier
  and had not been listed here: `assets/effects/weapons/magic_rod/`
  (`arcane_circle.png`, `thunder_ball.png`, `thunder_aura.png`). The pack is
  kept unmodified under `assets/unused/unordered-effects/` and is not read at
  run time.
- **750+ Effect and FX Pixel All** — the melee attack effects
  (`elemental_system_journal.md`, M13), cut by the same script into
  `assets/effects/weapons/`: the Sword's `slash_*` (Part 11/509, a fanned
  arc), the Daggers' `slash_*` (Part 12/578) and `stab_*` (Part 8/395), and
  the Hammer's `impact_*` (Part 13/615). Five variants each — `plain` from
  the pack's neutral row, `fire` / `ice` / `wind` from their own, `thunder`
  from the neutral row remapped, since the pack has no purple. The art they
  replace is archived unmodified in
  `assets/unused/superseded-weapon-fx/`.
- **Derived, not new art** — everything under `assets/infused/` is a
  hue-rotated copy of a sheet already credited above or in the table: the
  Ember Ring's flame, the Bomb and its two explosions, the Grave Totem and
  the Spirit Wolf, four elements each (`elemental_system_journal.md`,
  M13 C). Generated by
  `tools/asset_pipeline/recolour_element_variants.py`, which reads the base
  rig's own sheets, so each copy carries its source's licence and is
  regenerated rather than edited. Nothing new was taken from any pack for
  it.
- **Super Pixel Effects Gigapack** — the freeze status
  (`assets/effects/elements/freeze.png`), cut from `spell_ice_001` large blue
  by the same script: a block of ice that forms over forty frames and
  shatters, replacing the bracket that used to sit over a frozen enemy's
  head.

- **Super Pixel Effects Gigapack** — the buff buildings' feedback
  (`documentation/journals/buff_buildings_journal.md`): the five hero
  activation strips in `assets/effects/buffs/` (`spell_absorb_001` yellow,
  `spell_buff_001` orange, `spell_haste_001` blue, `spell_dispel_001` violet,
  `spell_attack_up_001` red, all large) and the HUD stills in
  `assets/ui/hud/buffs/` (one frame each of those, plus `symbol_defense_up_001`
  and `symbol_attack_up_001` small), packed by
  `tools/asset_pipeline/cut_buff_buildings.py`. The buildings themselves
  (`assets/buildings/general/`), their dressing (`assets/terrain/props/dressing/`)
  and the pinball (`assets/projectiles/pinball.png`) are Tiny Swords pieces from
  the reserve, copied by the same script.
- **Super Pixel Effects Gigapack** — the end banners in `assets/ui/end_banners/`:
  `game_over.png` is the pack's `symbol_game_over_text_001` (large, red) and
  `you_won.png` its `symbol_you_won_text_001` (large, yellow), each re-laid as a
  grid sheet by `tools/asset_pipeline/cut_end_banners.py`. The pack itself is
  kept unmodified under `assets/unused/` and is not read at run time.
- **Super Pixel Effects Gigapack** — the Hexcaller's cast wind-up (ENT-013):
  `assets/enemies/hex_shaman/hex_shaman_cast_charge.png` joins the pack's
  `scifi_charge_up_003_small_violet` (16 frames, unmodified) into one strip,
  by `tools/asset_pipeline/cut_cast_charge.py`; the source frames are
  archived beside it in `assets/enemies/hex_shaman/unused/cast_charge/`.
- **Super Pixel Effects Gigapack** — the `mark` status's lock-on brackets
  (RND-007): `assets/effects/status/mark.png` is cut from the pack's
  `scifi_analyze_001_large_red` (frames 109–119 and 0–2, the brackets-only
  run) by `tools/asset_pipeline/cut_mark_brackets.py`. The script erases the
  scanner panel's leader line and recolours the frames from the pack's
  orange-red to raspberry (hue 340). The source frames are archived beside
  it in `assets/effects/status/unused/mark/`.
