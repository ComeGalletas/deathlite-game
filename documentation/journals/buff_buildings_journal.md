# Buff buildings — execution journal

Interactive buildings scattered over the islands that hand the hero a short
timed advantage. Named `buff_buildings_journal.md` to match the other
journals in this folder.

## Requirement (owner, 2026-09-19)

Expand the building-obstacle placement and add interactivity.

Today houses are placed on islands as obstacles, from the house sprites only,
and that pass runs before the trees so the houses get the better spots. Now
multiple buildings with different functions go onto the map. Each function is
a **buff**: a short-term advantage for the player. The first five:

1. **Magnet** — pulls all currently stranded experience, and every orb that
   drops meanwhile, towards the player for 5 s.
2. **Turbo** — +300 units of move speed; the hero gets maximum weight so
   walking into enemies pushes them all away (bosses excepted) and deals small
   contact damage to them.
3. **Haste** — +100 % attack speed for every weapon and summon: double the
   attacks, i.e. the player's attack cooldowns halved by that 100 %, never
   below 0.
4. **Pinball** — while attacking, the hero also throws pinballs: very high
   contact damage, a weight like Turbo's so they shove every enemy away, and
   they bounce off obstacles and walls relative to the angle of contact.
   Moderate speed, one pinball every 2 s. A pinball lives until it has bounced
   10 times or for a fixed 10 s.
5. **Vampire** — +10 % damage on every weapon, and 1 HP per enemy hit by any
   weapon's attack, summons excluded, for a fixed 7 s.

Asked with it: confirm the reading, and review the unused asset folder for
building sprites that could carry these functions.

---

## Confirmed reading

Each item against what the code already tracks. Where the request left
something open the decision taken is stated so it can be overruled.

**Placement.** `_scatter_houses` (`world/gen/scatter.py:390`) is the pass
the request describes: houses first, one cluster per roomy island, capped at
`_HOUSE_GLOBAL_CAP = 7` world-wide (`world/gen/tuning.py:57`), and every
smaller obstacle spaces itself off them afterwards. It skips the village
island, which the village pass owns. The buff buildings join *that* pass as
new obstacle kinds, so trees and rocks keep spacing off them the same way,
and they are never seated on the village. Reading taken: **one building per
buff kind per world**, each on a different island where the islands allow it
(five buildings, five islands; on a small world two may share). The house
cluster keeps its own rule and is not replaced.

**Interactivity.** A building is an `Obstacle` (collides, blocks shots) plus
an `Interactable` seated at its door, the way the village forge is both an
obstacle kind and an interactable kind. The hero walks up, the interact keycap
appears over the art (`visual/key_marker.py` reads the drawn rectangle), the
key fires the buff. Reading taken: **one use per building per run**, like the
shrine and the fountain. A "used" building keeps standing as an obstacle; its
door goes dark (see the asset note on the gold mine, which ships an
active/inactive pair).

**Buffs are timed.** There is no timed-buff plumbing on the hero today: every
stat change is a permanent `Modifier` on the `StatSet`
(`entities/player.py:97`), and `FireContext` is rebuilt every frame from
`player.stats` (`core/state.py:600`). A buff is therefore a new small system
that owns `{kind: seconds_left}` on the hero, applies a `Modifier` with a
source name on start, and removes that source on expiry. The five kinds map
onto existing seams as follows.

1. **Magnet, 5 s.** Every `XPGem` sits still until it is inside
   `player.pickup_radius`, then homes (`entities/pickup.py:57`). The buff sets
   `gem.homing = True` on every active gem when it starts and on every gem
   spawned while it runs (`_spawn_gem`, `core/state.py:805/867`). Homing speed
   is the existing 320 px/s vacuum. Health potions are not orbs and are not
   pulled.

2. **Turbo, 5 s (duration not stated — taken as the same 5 s as Magnet).**
   `+300` is a flat add on the `move_speed` stat (base hero speed is in the
   low hundreds, so this is a big, visible sprint). Weight: the bump resolver
   splits the shove by `knock_split(a.weight, b.weight, ...)` and the boss
   weighs `inf` (`entities/boss.py:73`), so setting `player.weight = inf` for
   the duration makes every non-boss body take the whole impulse and the boss
   still wins against the hero. Contact damage: a new check in
   `Combat.enemy_contact`'s neighbourhood — while Turbo runs, each enemy the
   hero overlaps takes a small hit once per short interval (proposed 5 damage
   every 0.5 s per enemy, tunable) and is *not* allowed to bite back for that
   contact. Reading taken: the enemy's own contact damage still applies unless
   the owner wants Turbo to grant contact immunity too.

3. **Haste, duration not stated — taken as 5 s.** `Weapon._cooldown` divides
   by `attack_speed_multiplier` (`combat/weapons/core.py:248`) and clamps at
   0.05 s, so a +1.0 `Modifier` on `attack_speed_multiplier` halves every
   cooldown and already satisfies "never below 0". Summons run their own
   `attack_interval` (`entities/summon.py:177`), which the multiplier does not
   reach; the buff halves the live summons' `attack_cd` pacing through a
   summon-side multiplier read from the hero. Orbiting weapons and hazards
   keyed off the cooldown speed up with it.

4. **Pinball, duration not stated — taken as 10 s, matching a pinball's
   own life.** A pinball is a `Projectile` with a new `bounces_left` field.
   `Effects.block_on_obstacle` and `block_on_terrain` (`core/effects.py:81,
   116`) currently kill a shot on contact; for a pinball they reflect `vel`
   about the contact normal instead (obstacle: normal from the circle centre;
   wall/cliff: normal from the blocked axis, found by probing x and y
   separately) and decrement the count. Dies at 0 bounces or 10 s. It scores
   hits through the normal resolver, so `src_weight` gives the shove
   (`core/combat.py:88`) and `pierce=999` plus a re-hit interval lets it keep
   hitting as it caroms. Fired by the buff system on its own 2 s timer
   whenever the hero attacked in that window ("throws pinballs when
   attacking"), aimed along the current aim / last move direction. Damage:
   proposed 40 flat, tunable in data.

5. **Vampire, 7 s.** `+10 %` is a `Modifier` of +0.10 on `damage_multiplier`.
   The heal hooks into `Combat.projectile_hits` after `take_damage`
   (`core/combat.py:82`): 1 HP per enemy hit, gated on `proj.weapon_id` not
   naming a summon weapon (`Weapon.is_summon`). Each *hit* heals, so a
   piercing shot through three enemies heals 3.

**HUD.** The run HUD is fixed by decision to the level gem, bars and timer; a
buff needs *some* on-screen sign. Reading taken: a small icon row with a
draining timer under the HP bar, in the same hex-bar family, removed the
moment the last buff ends. Say so if the HUD should stay untouched and the
sign should be a world-space effect on the hero instead.

**Data.** The five buffs and their numbers live in a new
`data/world/buildings.json` (kind, duration, per-buff numbers, the obstacle
rig and the door offset), per the standing rule that tuning is data.

---

## Asset survey (`assets/unused/`, 2026-09-19)

`assets/unused/` is git-ignored and lives only in the main checkout. Every
building-shaped sprite in it, measured:

| Sprite | Path under `assets/unused/` | Frame | Frames | Notes |
|---|---|---|---|---|
| Gold mine (active / inactive / destroyed) | `buildings/general/gold_mine/goldmine_*.png` | 192×128 | 1 each | Lit-door and dark-door pair: a natural **used / unused** state. Low and wide. |
| Fish hut | `enemies/extra/fish_hut/fish_hut.png` | 192×192 | 8 | Animated fish-shaped hut on stilts, water at its base. Reads as a shoreline prop. |
| Gnome hut | `enemies/extra/gnome_buildings/gnome_hut.png` | 128×192 | 1 | Leafy round hut, house-sized. |
| Gnome tower | `enemies/extra/gnome_buildings/gnome_tower.png` | 128×256 | 1 | Purple mushroom tower with a ringed crown. Tower-sized. |
| Goblin hut | `enemies/extra/goblin_hut/goblin_hut.png` | 256×256 | 12 | Animated, smoking chimney, biggest of the set. |
| Cave | `enemies/extra/cave/cave_idle.png` | 192×192 | 8 | Animated rock cave with a dark mouth. |
| Pirate tower (ground) | `enemies/extra/pirate_tower/pirate_tower_ground.png` | 128×192 | 1 | Wooden watch platform. |
| Pirate tower (water) | `enemies/extra/pirate_tower/pirate_tower_water.png` | 128×192 | 8 | Same, standing in water. Not for land. |
| Dead tree | `enemies/extra/dead_tree/dead_tree.png` | 192×320 | 2 | A hollow tree with a door and steps, tree-shaped. |

Not buildings but also there: `terrain/resources` (gold / meat / tools / wood
piles), `orbs/orb_red.png` and `orb_yellow.png` (32 px, good pinball
candidates), the Tiny Swords `ui/icons` set (no buff icons among them), and
the Super Pixel Effects Gigapack (activation bursts, magnet swirl, haste
glow) for the buff feedback.

Wired but not yet scattered outside the village: `archery`, `barracks`,
`castle`, `tower`, `monastery` in all five colours (`assets/buildings/`).
These already have colliders, satellites and rigs and could carry a buff with
no art work at all.

### Proposed mapping (owner to confirm)

| Buff | Sprite | Why |
|---|---|---|
| Magnet | **Gold mine** | The lit door, the "pull the gold in" reading, and its active/inactive pair gives the used state for free. |
| Turbo | **Pirate tower (ground)** | Tall, light, "run up and go"; it is also the only unused sprite that reads as a launch point. |
| Haste | **Gnome tower** | The mushroom tower's crown reads as a spell / quickening. |
| Pinball | **Cave** | The dark mouth is where the balls roll out of; it animates. |
| Vampire | **Dead tree** | Hollow, sinister, with a door; it reads as the one building that takes something back. |

Alternatives if any of these clashes with the enemy roster that owns them
(the cave, gnome and goblin art are the enemy factions' buildings): the
village `tower` / `archery` / `barracks` in a distinct colour per buff, all
already wired. The goblin hut is set aside: at 256 px and 12 frames it is the
heaviest sheet and reads as a goblin camp, not a hero perk. The fish hut needs
water under it and is set aside for a shoreline feature later.

---

## Proposal

### 1. Data — `data/world/buildings.json`

One entry per buff kind: `duration`, per-buff numbers (`speed_add`,
`contact_damage`, `contact_interval`, `attack_speed_add`, `damage_add`,
`heal_per_hit`, `pinball: {damage, speed, weight, bounces, lifetime, every}`),
the obstacle `rig`, `radius`, `door` offset for the interactable, and the
`used_rig` where a second frame exists (gold mine).

The obstacle kinds go into `terrain.json` `obstacles` and
`obstacle_decor.rigs` beside `house`; the sprites are copied into
`assets/buildings/general/` and the strips cut with a script under
`utilities/`, sources archived per the standing rule.

### 2. Generation — `world/gen/scatter.py`

`_scatter_buildings(rooms, all_doors, rng, boss_id, out, reach)` runs right
after `_scatter_houses` and before the trees. It shuffles the five kinds,
walks the eligible islands (not start, boss or village; enough cells) and
seats one building per island with the same `_spot` rules the houses use
(inland, off doors, clear of the room centre, `_uphill_ok`), spacing off the
houses already placed. The building's position is recorded on the layout
(`layout.buildings` already exists for the village; a `layout.buffs` list of
`(kind, x, y)` is added) so the run can seat the interactable.

### 3. Run side — `game/states/playing/core/buffs.py`

`BuffSystem(ps)` owns `active: dict[str, float]`, `start(kind)`, `update(dt)`,
and the per-kind apply / expire pair. `SpecialLocations.build` seats one
`Interactable(kind, door)` per `layout.buffs` entry, and `use_<kind>` calls
`ps.buffs.start(kind)`. Hooks:

- `Player.weight` is set and restored by Turbo; `Combat.enemy_contact` gets a
  `turbo_contact` step.
- `_spawn_gem` marks gems homing while Magnet runs; `start("magnet")` marks
  the live pool.
- `Summon.update` reads `ctx.attack_speed_mult` (new field on the summon
  context) for Haste.
- `Effects.block_on_obstacle` / `block_on_terrain` bounce a projectile whose
  `bounces_left > 0`; the pinball's `style` gets its own draw family under
  `visual/projectiles/`.
- `Combat.projectile_hits` heals 1 HP per non-summon hit while Vampire runs.

### 4. HUD — `ui/hud.py`

A buff row under the bars: one icon per active buff with a draining ring,
gone when none is active.

### 5. Tests — `tests/`

- generation: on the shared cached worlds, at most one building per kind, none
  on the start / boss / village islands, every one inland and off a flight.
- buffs: each kind's numbers applied on start and gone on expiry; Haste never
  drives a cooldown below the 0.05 s floor; Magnet homes a gem outside the
  pickup radius; Vampire heals per hit and not for a summon's hit; Turbo's
  weight is restored; a pinball reflects off a wall and dies at 10 bounces.

### Progress

- [x] Requirement recorded, reading confirmed, assets surveyed
- [x] Owner's answers on the open points
- [x] Data + assets
- [x] Generation pass
- [x] Buff system + hooks
- [x] HUD row
- [x] Tests
- [x] Screenshot

### Open points for the owner

1. Sprite mapping as proposed above, or the village towers in colours?
2. Durations for Turbo, Haste and Pinball (taken as 5 / 5 / 10 s).
3. One use per building per run (taken), or re-arming after a cooldown?
4. Does Turbo also stop enemies biting the hero on contact? (taken: no)
5. A buff row on the HUD (taken), or no HUD change?

---

## Revision 1 (owner, 2026-09-19)

### Answers to the open points

1. Sprite mapping as proposed. Balance the drawn sizes so no building dwarfs
   another, and dress each building's surroundings with non-interactive
   decorations, which may be other obstacles or buildings. Unwired art first.
2. Durations 5 / 5 / 10 s for Turbo / Haste / Pinball, as taken.
3. **Several buildings per island, 2 to 5, parametrisable.** None on the
   human village islands.
4. Turbo does not stop enemy contact bites, but it adds **+20 armor** (flat
   reduction, `combat/damage.py:apply_armor`), so every bite lands lighter.
5. A buff row on the HUD, **under the hero cluster at the top left**, with an
   icon that echoes the buff's own effect. Check the assets for icon options.

### New requirement: three feedback effects per buff

Every buff, on activation, shows three things:

1. **A screen-wide colour tint** in the buff's colour — light, brief, and it
   may be a gradient of two or three colours from the buff's palette.
2. **A sprite effect on the hero** for a couple of seconds, in the same
   palette, so the buff granted is legible on the character.
3. **A flying name** — the buff's name in the buff's colour, visible for 7 s
   until it has completely faded out.

### Confirmed reading of the revision

**Placement (revised).** `_scatter_buildings` seats **2 to 5 buff buildings
on every island** the house pass is allowed on: not the village islands, and
not the boss arena (its clear disc is the fight). The start island counts as
an island, so the hero may find one at the start. The count is
`_BUFF_PER_ISLAND = (2, 5)` in `world/gen/tuning.py`; an island too small to
seat its draw seats what fits. Kinds are drawn without repeats within an
island while five are available, so an island with five shows all five.

**Sprite balance.** Each kind gets its own `render_scale` in
`terrain.json` so the five buildings draw at a house-to-tower footprint:

| Kind | Sheet | Native | Draw target |
|---|---|---|---|
| Magnet (gold mine) | 192×128 | wide, low | ~120 px wide, radius 34 |
| Turbo (pirate tower) | 128×192 | narrow, tall | ~90 px wide, radius 26 |
| Haste (gnome tower) | 128×256 | narrow, tallest | ~90 px wide, radius 28 |
| Pinball (cave) | 192×192 ×8 | round | ~120 px wide, radius 36 |
| Vampire (dead tree) | 192×320 ×2 | tall | ~110 px wide, radius 30 |

**Surroundings.** Each building brings a small dressing drawn from the same
seed, seated inside a ring of 1.5–3 tiles and off the door: non-colliding
decor from the unused resource art plus one or two colliding obstacles the
game already has.

| Building | Decor (non-colliding, from `assets/unused/`) | Colliders (already wired) |
|---|---|---|
| Gold mine | `terrain/resources/gold/gold_stone_1..6` (128 px, six sizes) | one or two `rock`s |
| Pirate tower | `terrain/resources/wood/wood_resource`, `tools/tool_1..4` (64 px) | a `stump` deco and a `rock` |
| Gnome tower | wired `deco_bush_*` and pumpkins | a `tree` |
| Cave | wired `deco_rock_*` (the small ground rocks) | two `rock`s |
| Dead tree | `enemies/extra/skull_decorations/bones_1..3` (64 px), `skull_spike_1..2` (64×128) | a `tree` |

The unused Tiny Swords art here is the same pack as the live decor
(`deco_ground_*`, `deco_stump_*`), so it drops straight into the
`decorations` rig list with no style risk. The gold stones and skull spikes
are the two that need a `rig` entry each; the rest are single 64 px frames.

**Armor.** Turbo adds a `Modifier(+20, "armor")` from the same source name as
its speed add, so both leave together.

**The three feedback effects.** One palette per buff drives all three, and
the HUD icon, from `data/world/buildings.json` (`palette: [c1, c2, c3]`):

| Buff | Palette | Screen tint | Hero effect (Gigapack, Fantasy Spells, 128 px) | HUD icon |
|---|---|---|---|---|
| Magnet | gold → amber | yellow top, amber bottom | `spell_absorb_001` yellow — motes converging on the hero, 31 f | a still of the absorb motes |
| Turbo | orange → red | orange top, red bottom | `spell_buff_001` orange — rising arrows, 30 f | `symbol_defense_up` orange (the +20 armor shield) |
| Haste | sky → blue | cyan top, blue bottom | `spell_haste_001` blue — the clock face, 29 f | a still of the clock |
| Pinball | violet → pink | violet top, pink bottom | `spell_dispel_001` violet — orbs circling the hero, 22 f | a still of one orb |
| Vampire | crimson → black | red top, dark bottom | `spell_attack_up_001` red — the sword and plus, 18 f | `symbol_attack_up` red |

- **Screen tint**: a full-screen `SRCALPHA` surface with a vertical two-colour
  gradient, alpha peaking at ~55 (the hurt flash peaks at 120) and fading to
  0 over 0.9 s. Drawn where the hurt flash is drawn
  (`visual/rendering.py:130`), before the HUD, so the HUD stays clean.
- **Hero effect**: the Gigapack strip packed to a horizontal sheet by a
  `utilities/cut_buff_fx_sheets.py` (the totem-bolt cutter's pattern), played
  once over the hero for ~2 s at the sheet's frame rate, anchored to the
  hero's feet like the heal loop (`rendering.py:171`). The Gigapack gets its
  `assets/CREDITS.md` entry.
- **Flying name**: a new `ui/buff_banner.py` — the buff's name in the title
  face (NunitoSans), the palette's first colour with a dark shadow, born over
  the hero's head, rising slowly for the first second then holding, alpha
  fading from full to 0 across the full 7 s. One banner per activation; a
  second buff stacks its banner above the first.
- **HUD row**: under the HP/XP cluster at `HUD_LEFT_TOP`, one 32 px icon per
  active buff in a small hex-family socket, tinted in the palette, with a
  draining arc for the time left. Icons are cut from the same effect strips
  (one still frame each) so the icon *is* the effect the player just saw;
  the two `Symbols` icons stand in where a still would not read at 32 px.

### Progress (revised)

- [x] Requirement recorded, reading confirmed, assets surveyed
- [x] Revision 1 recorded and confirmed
- [x] Data + assets (buildings, decor, five effect strips, credits)
- [x] Generation pass (2–5 per island, dressing)
- [x] Buff system + hooks (magnet, turbo + armor, haste, pinball, vampire)
- [x] Feedback: tint, hero effect, flying name
- [x] HUD row
- [x] Tests
- [x] Screenshot

---

## Revision 2 (owner, 2026-09-19)

**Turbo contact damage is 5 per second** of contact per enemy (the earlier
"5 every 0.5 s" is withdrawn). Applied as half-second bites of 2.5 so the
damage number and the hit flash keep a readable cadence; `contact_dps: 5`
and `contact_tick: 0.5` in `buildings.json`.

### Todo list (proposed, in build order)

**A. Data and assets**
- [x] A1 `data/world/buildings.json`: five buff entries — duration, palette,
      numbers (`speed_add 300`, `armor_add 20`, `contact_dps 5`,
      `contact_tick 0.5`, `attack_speed_add 1.0`, `damage_add 0.10`,
      `heal_per_hit 1`, pinball `{damage, speed, weight, bounces 10,
      lifetime 10, every 2}`), obstacle kind, rig, door offset, dressing list.
- [x] A2 Copy the five building sheets into `assets/buildings/general/`,
      the gold-mine inactive frame as the used state; add `obstacles`,
      `obstacle_decor.rigs`, `render_scale`, `sprite_drop`, `ghost` entries
      in `terrain.json`.
- [x] A3 Copy the dressing art (gold stones 1–6, wood, tools 1–4, bones 1–3,
      skull spikes 1–2) and add their `deco_*` rigs.
- [x] A4 `utilities/cut_buff_fx_sheets.py`: pack the five Gigapack strips
      (absorb yellow, buff orange, haste blue, dispel violet, attack-up red)
      into `assets/effects/buff_*.png`; cut one 32 px icon still each; the
      two Symbols icons for Turbo and Vampire. Credits entry for the Gigapack.

**B. Generation**
- [x] B1 `world/gen/tuning.py`: `_BUFF_PER_ISLAND = (2, 5)`, ring and gap
      constants for the dressing.
- [x] B2 `world/gen/scatter.py` `_scatter_buildings`: after the houses,
      before the trees; every island but village and boss; 2–5 per island,
      kinds unrepeated within an island; house-style `_spot` rules; records
      `(kind, x, y, door)` on `layout.buffs`.
- [x] B3 Dressing: per building, its decor pieces inside the ring, off the
      door, plus its one or two colliding obstacles.

**C. Run side**
- [x] C1 `entities/interactable.py`: the five kinds; `SpecialLocations.build`
      seats one per `layout.buffs`; `use_<kind>` starts the buff and flips
      the gold mine's rig to the dark door.
- [x] C2 `game/states/playing/core/buffs.py` `BuffSystem`: `active`,
      `start`, `update`, per-kind apply/expire with named `Modifier`s;
      ticked from `_phase_update`.
- [x] C3 Magnet: flag the live gem pool and every gem spawned while active.
- [x] C4 Turbo: `+300 move_speed`, `+20 armor`, `player.weight = inf`
      restored on expiry, 5 dps contact in `Combat` next to `enemy_contact`.
- [x] C5 Haste: `+1.0 attack_speed_multiplier`; summon context carries an
      `attack_speed_mult` the summons' `attack_cd` pacing divides by.
- [x] C6 Pinball: `Projectile.bounces_left`; reflection in
      `block_on_obstacle` / `block_on_terrain`; re-hit interval; the buff's
      2 s throw timer while the hero attacks; a `pinball` draw family.
- [x] C7 Vampire: `+0.10 damage_multiplier`; 1 HP per non-summon hit in
      `projectile_hits`.

**D. Feedback**
- [x] D1 Screen tint: gradient flash next to the hurt flash, peak alpha ~55,
      0.9 s fade.
- [x] D2 Hero effect: one-shot strip over the hero, ~2 s, feet-anchored.
- [x] D3 `ui/buff_banner.py`: the flying name, 7 s to full fade, stacking.
- [x] D4 `ui/hud.py`: buff row under the top-left cluster, icon + draining
      arc, gone when nothing is active.

**E. Tests and delivery**
- [x] E1 Generation tests on the shared cached worlds: 2–5 per eligible
      island, none on village/boss, inland, off flights, kinds unrepeated.
- [x] E2 Buff tests: apply/expire per kind, Haste floor, Magnet homing,
      Vampire per-hit and summon exclusion, Turbo weight/armor restore and
      5 dps, pinball reflection and the 10-bounce / 10 s death.
- [x] E3 Full suite green; screenshot of a dressed building and an active
      buff (tint, hero effect, name, HUD row) delivered.

---

## Built (2026-09-19)

### What changed, file by file

**Data and assets**

- `data/world/buildings.json` — new. The five buffs (name, duration, palette,
  numbers, effect rig, icon rig, the mine's `used_rig`, colliding company,
  dressing list), the `placement` knobs (2–5 per island, gap, ring, dressing
  count), the `feedback` timings, the obstacle kinds, their skins, the
  building / dressing / effect rigs and the single-image rigs (HUD stills,
  the pinball).
- `game/content.py` — loads and validates it (`_check_buildings`) and folds
  its blocks into the terrain and UI rigs (`_merge_buildings`), so the
  generator, the bake, the renderer and the HUD see the buildings as
  ordinary kinds. `terrain.json` is untouched.
- `tools/asset_pipeline/cut_buff_buildings.py` — new. Copies the five
  buildings (`assets/buildings/general/`), the dressing
  (`assets/buildings/dressing/`) and the pinball orb
  (`assets/projectiles/pinball.png`) from the reserve, packs the five
  Gigapack strips (`assets/effects/buffs/`) and cuts the 32 px HUD stills
  (`assets/ui/hud/buffs/`). `--meta` prints the measured rig metadata.
- `assets/CREDITS.md` — the Gigapack and Tiny Swords pieces credited.

**Generation**

- `world/gen/buildings.py` — new. `_scatter_buildings`: every island but the
  village and the boss arena draws 2–5 distinct kinds, seated inland, off
  doors and flights, a ring apart from each other; then `_company` seats the
  kind's colliding obstacles (rocks by the mine and the cave, a tree by the
  towers) on the ring, on the building's own terrace.
- `world/gen/scatter.py` — calls it right after `_scatter_houses`, before the
  trees. `world/gen/tuning.py` — the `_BUFF_*` defaults.
- `world/layout.py` — `WorldLayout.buff_buildings(kinds)`: the buildings are
  read off the obstacles by kind, so one the repair pass took back is gone
  for the run too.
- `world/terrain/decor/dressing.py` — new. At bake time each building draws
  3–6 non-colliding props from its dressing list onto the ring, under the
  clutter's own rules (40 px gap, +20 px off colliders, the edge inset and
  the uphill keep-back), appended to `room_decor`. `bake.py` runs it after
  the clutter (`"dressing"` stage).
- `world/terrain/decor/obstacle_skins.py` — `reskin_obstacle`: swaps one
  obstacle's skin (the mine's dark door once used).

**Run side**

- `game/states/playing/core/buffs.py` — new. `BuffSystem`: `{kind: seconds
  left}`, `activate` / `start` / `update`, the per-kind apply and expire
  (`Modifier`s under `buff:<kind>`, Turbo's weight and armor, Magnet's pull),
  Turbo's contact bites (5 dps as 2.5 every 0.5 s per touching enemy),
  Pinball's throws (every 2 s while the hero is mid-attack, aimed at the
  manual aim, else the nearest enemy, else the last move), Vampire's per-hit
  heal, and the feedback state (`tint`, `hero_fx`, `banners`).
- `core/locations.py` — seats one interactable per building and routes the
  buff kinds to `BuffSystem.activate`. `entities/interactable.py` — the five
  kinds.
- `core/state.py` — owns `self.buffs`; ticks it after the bump pass; hands
  Haste's multiplier to the summons; marks fresh gems for Magnet; passes the
  rows to the HUD.
- `core/combat.py` — Vampire hook after every projectile hit.
- `core/effects.py` — `bounce`: a projectile with `bounces_left` reflects off
  an obstacle (about the normal from its centre) or off terrain (about the
  axis it crossed, both at a corner; the shoreline and cliff faces count),
  spending one bounce; `update_projectiles` routes bouncing shots there.
- `entities/projectile.py` — `bounces_left`, and a re-hit interval on the
  straight path. `entities/summon.py` — `attack_cd` paced by
  `ctx.attack_speed_mult`.
- `visual/projectiles/pinball.py` — the ball: the orb spun by distance
  rolled over a soft glow.

**Feedback and HUD**

- `visual/rendering.py` — `buff_tint` (the palette as a vertical gradient,
  peak alpha 55, 0.9 s fade, drawn after the hurt flash), `hero_fx` (the
  strip played once over the hero, feet-anchored, right after the sprite),
  the banners drawn over the hero, and buff interactables left to the
  obstacle skin.
- `ui/buff_banner.py` — new. The flying name: title face, the palette's
  first colour, rises for a second then holds, alpha to zero over 7 s, older
  names pushed up a line.
- `ui/hud.py` — `_draw_buffs`: under the top-left cluster, one
  `HUD_BUFF_ICON_PX` (32) icon per active buff in a dark disc with a ring in
  the buff's colour that drains clockwise. `visual/key_marker.py` — the
  keycap measures the building's painted box like the forge's.

### Decisions made while building

- **Obstacle kind = buff kind.** The building obstacle is named after the
  buff it grants (`magnet`, `turbo`, ...), and so is its interactable, so
  the key marker, the renderer and the locations dispatch need no lookup
  table between the two.
- **The interactable stands on the building**, with the kind's radius as
  its reach, rather than at a door offset: the keycap already hangs over
  the art's peak, and the hero can fire it from any side.
- **Dressing art lives beside the buildings** (`assets/buildings/dressing/`),
  not under `terrain/props/`: the prop-coverage test treats everything there
  as clutter that must be reachable from the `decorations` registry, and
  the dressing is reachable from `buildings.json` instead.
- **The dressing keeps the clutter's rules.** The first cut used its own
  tighter gaps and the decor spacing / frontier tests caught it; the ring is
  wide enough for the standard 40 px gap and +20 px clearance, so the
  dressing now obeys them.
- **Single-image rigs go with the UI rigs.** The HUD stills and the pinball
  orb have no strip, and every terrain rig is expected to; they merge into
  `ui_sprites` instead.
- **Pinball damage is scaled by the hero's damage multiplier** (so Vampire's
  +10 % and the damage blessings reach it) but by nothing weapon-specific;
  it hits through the normal resolver, so its 400 weight shoves.
- **Vampire heals on projectile hits only.** Hazards (the Meteor crater)
  tick continuously and would heal every frame; they are not "a hit".
- **A refreshed buff restarts its timer and never stacks.**
- **The pathfinding test walker now honours the nav step mask.** Seed 7's
  new obstacle layout left a cost pocket the simplified walker clipped into
  diagonally; the real mover is gated by the mask and never sees the jump.

### Test results

- `tests/world/test_buff_buildings.py` (new, 8 tests): 2–5 per eligible
  island, kinds unrepeated, never on the village or the boss island,
  inland and off flights, a ring apart, listed by kind; every building
  skinned and dressed. Green on the four pinned seeds.
- `tests/playing/test_buffs.py` (new, 18 tests, one booted run on
  `W.pinned(2)`): activation and one-use, the keycap's art box, the three
  feedbacks firing and fading, the HUD rows draining, the mine's dark door,
  Turbo's speed / armor / weight and their return, Haste's ×2 and the 0.05 s
  floor, Haste pacing a summon, Vampire's +10 %, no stacking, Magnet on
  stranded and fresh gems and off after five seconds, Turbo's 5 dps bites,
  Vampire's per-hit heal and the summon exclusion, a ball every two seconds
  only while attacking, reflection off an obstacle and off the world's edge,
  the last bounce spending the ball, ordinary shots still dying.
- Full suite: 2711 passed, 658 subtests, in 15 min, with the two pre-existing
  failures below deselected.
- Existing tests updated: the interactable count, the obstacle-family
  allowlist, the projectile-style registry, the pathfinding walker; the
  world digests regenerated (`tools.verification.world_digest --write`).
- Two failures predate this branch and are unrelated: `test_imp`'s check for
  the untracked `assets/unused/` (absent in a worktree) and `test_menu`'s
  banner-rig check (the end banners' rigs on `main`).

### Screenshots

Delivered from seed 35: the Haste tower and the Vampire tree with their
dressing on one island; the keycap over the mine; the Magnet activation
(gold tint, converging motes, the flying name, the HUD icon); the Vampire
activation (red tint, the sword, the name).

---

## Revision 3 (owner, 2026-09-20): the two-tile tree

**Requirement.** Review the tree building: its sprite is relatively big and
needs two tiles to draw correctly.

**Confirmed reading.** The dead tree (Vampire) was the one building whose
art was shrunk to its collider: the same 192×320 sheet size as the
monastery, drawn at 0.47 (80×137 px, 1.25×2.1 tiles) because its scale came
from a single 32 px circle, where the monastery draws at 0.84 on a
three-circle base. The owner confirmed: draw it two tiles wide, on a
two-tile base.

**Change.**

- **The sheet was being cut in half.** `dead_tree.png` is one 384×320
  image, not two 192 px frames; the first screenshot after the change showed
  the tree clipped down its middle. The rig now reads the whole frame
  (anchor 184,315; paint 20,5,328,310; footprint 328; one still frame).
- `buildings.json`: `render_scale.vampire = 0.4`, so the tree paints
  131×124 px (2.05×1.9 tiles); the collider is a compound — primary r 36
  plus satellites `[-34, 6, 22]` and `[34, 6, 22]`, a 112 px base nothing
  walks through.
- The unseal repair may take a building back where its base sealed a route
  (seed 42, island 6 loses its cave); the placement test allows one island
  per world to sit one under the minimum for that reason.
- `world/gen/buildings.py`: `_seat` puts the satellites down the way the
  village pass does (collide only, `skin=False`); `_footprint` places and
  keeps a compound clear of doors by its whole base, and a compound's spot
  needs the cells either side inland too.
- `world/layout.py`: `buff_buildings` lists primaries only, so the run
  never seats an interactable on a root. The interactable reach follows the
  new radius.
- Tests: the two-tile base per tree on every pinned seed; the skinned-check
  skips satellites; digests regenerated. Two older tests assumed satellites
  only stand in a village (`test_village`) and that every in-view obstacle
  draws (`test_depth_sort`); both now allow a collide-only satellite.
- Full suite after the change: 2712 passed, 658 subtests, the two
  pre-existing failures deselected.

The other four buildings stay at house size (1.0–1.5 tiles wide), as agreed.

---

## Revision 4 (owner, 2026-09-20): the towers and the cave join the tree's class

**Requirement.** Raise the cave and both towers to the tree's class too.

**Change.**

- `buildings.json` `render_scale`: `turbo 1.19`, `haste 1.03`,
  `pinball 0.83` (the tree stays at `0.4`), so every one paints two tiles
  wide: the pirate tower 129×170 px, the mushroom tower 128×167 px, the cave
  128×102 px. The mine stays at 1.5 tiles: it is a low, wide sheet and reads
  right at that size.
- Their colliders become the tree's compound (primary r 36, satellites
  `[-34, 6, 22]` and `[34, 6, 22]`), and their interactable reach follows.
- **The unseal repair takes a compound back whole.** With four wide kinds on
  every island the repair started dropping a single satellite (seed 35, a
  mushroom tower lost one root), which left the art standing on a base the
  hero could walk through on one side. `world/gen/repair.py` now groups a
  primary with the collide-only satellites that follow it and drops the
  group together — the village's wide buildings included, which the village
  pass always meant (it seats them before the repair "so a building that
  seals a road is taken back too").
- Tests: the two-tile base check covers all four kinds; the village
  satellite allowlist too; digests regenerated.

**Where the building sprites live.**

| Building | Shipped (read by the game) | Reserve source (untracked, main checkout) |
|---|---|---|
| Magnet (gold mine) | `assets/buildings/general/magnet.png`, `magnet_used.png` | `assets/unused/buildings/general/gold_mine/goldmine_active.png`, `goldmine_inactive.png` |
| Turbo (goblin hut, rev. 5; was the pirate tower) | `assets/buildings/general/turbo.png` | `assets/unused/enemies/extra/goblin_hut/goblin_hut.png` |
| Haste (mushroom tower) | `assets/buildings/general/haste.png` | `assets/unused/enemies/extra/gnome_buildings/gnome_tower.png` |
| Pinball (cave) | `assets/buildings/general/pinball.png` | `assets/unused/enemies/extra/cave/cave_idle.png` |
| Vampire (dead tree) | `assets/buildings/general/vampire.png` | `assets/unused/enemies/extra/dead_tree/dead_tree.png` |

The dressing is under `assets/buildings/dressing/`, the activation strips
under `assets/effects/buffs/`, the HUD stills under `assets/ui/hud/buffs/`,
the pinball under `assets/projectiles/`; all written by
`tools/asset_pipeline/cut_buff_buildings.py`.

---

## Revision 5 (owner, 2026-09-20): the goblin hut replaces the pirate tower

**Requirement.** Change the pirate tower for the goblin hut, keeping the
same proportions.

**Change.** `assets/buildings/general/turbo.png` is now the reserve's
`enemies/extra/goblin_hut/goblin_hut.png`: sixteen frames of 192×256 (the
sheet is 3072 px wide; the frame pitch is 192, not the 256 a first cut
assumed), a smoking chimney on an 8 fps loop. The rig measures the hut's
body (footprint 140) and paints the union of every frame so the smoke never
clips; `render_scale.turbo = 0.914` keeps it two tiles wide (128×194 px).
Collider, interactable, dressing (tools and logs) and the Turbo buff are
unchanged. Digests regenerated. The cutter's `COPIES` and `FRAME_W` follow.

---

## Revision 6 (owner, 2026-09-20): seven tweaks after the first commit

Committed as `d4c92be` first, then the owner asked for:

1. Haste and Vampire hero effects 30 % smaller.
2. The buff timers drawn over the character instead of the HUD row, same
   icon and draining ring.
3. The mushroom tower 30 % smaller, with the gnome hut beside it as
   dressing (confirmed reading: a colliding, non-interactive companion,
   drawn smaller than the tower).
4. Every buff lasts 10 s.
5. Turbo's speed bonus 300 → 150.
6. Never more than two buildings close together: within a 500 px ring
   round any building at most one other building; spread the rest out.
7. The magnet mine 30 % bigger.

### Todo

- [x] T1 Data: durations 10 s, `speed_add 150`, per-buff `fx_scale` (haste,
      vampire 0.7), `render_scale` haste 0.72 / magnet 0.73 with matching
      compound bases, the `gnome_hut` obstacle kind and rig, the haste
      building's `colliders` gaining it, the `cluster` placement rule.
- [x] T2 Assets: `gnome_hut.png` copied into `assets/buildings/general/`
      by the cutter.
- [x] T3 Generation: the cluster check in `_spot` (a candidate is rejected
      when it or any building within the ring would end up with two
      neighbours inside it); the company pass seats the hut.
- [x] T4 Run side: `hero_fx` carries the buff's scale; the marks over the
      hero (`ui/buff_marks.py`) replace the HUD row; the flying name starts
      above them.
- [x] T5 Tests: numbers read from the data; the cluster rule and the hut on
      the pinned seeds; the families and satellite allowlists; digests
      re-pinned.
- [ ] T6 Full suite, screenshots (an active buff with the marks over the
      hero; the tower with its hut; the bigger mine).

### What landed (rev. 6)

- `buildings.json`: every buff 10 s; `speed_add 150`; `fx_scale 0.7` on
  Haste and Vampire; `render_scale` haste 0.72 (1.4 tiles, base r 30 +
  satellites at ±24) and magnet 0.73 (1.9 tiles, base r 36 + satellites at
  ±30); the `gnome_hut` obstacle kind (r 22, `building_gnome_hut`, scale
  0.63, about one tile wide) on the Haste building's `colliders`; the
  placement's `cluster_ring_px 500` / `cluster_max_neighbours 1`.
- `world/gen/buildings.py` `_crowds`: a candidate spot is rejected when it,
  or any building inside the ring round it, would end up with more than
  one neighbour inside its own ring. On the pinned seeds the islands now
  seat 1–5 (seed 1234's island 0 seats one), so the placement test allows
  up to half the islands to sit under the minimum.
- `ui/buff_marks.py` draws the timers over the hero, following it, in
  screen space at the interface size; `ui/hud.py` lost its buff row and
  `BUFF_MARK_PX` replaced `HUD_BUFF_ICON_PX`. The flying name starts 96
  design px up so it clears the marks.
- `hero_fx` entries carry the buff's `fx_scale`; the renderer scales the
  strip by it.
- Tests read the numbers from the data; new checks for the cluster rule
  and the hut; the mine's narrower base loosened the base-width check;
  `magnet` and `gnome_hut` joined the satellite and family allowlists.
  Digests re-pinned.
- Screenshots delivered from seed 35: Vampire active with the mark over
  the hero and the smaller sword; the Haste tower with its gnome hut; the
  bigger mine.

### Rev. 6, addendum: the goblin hut 20 % smaller (owner, 2026-09-20)

`render_scale.turbo` 0.914 → 0.731 (the hut paints 102×155 px, 1.6 tiles
wide) with its base scaled to match (r 32, satellites at ±27 r 18).
Digests re-pinned.

### Rev. 6, addendum: houses keep their ring (2026-09-20)

The full suite after the seven tweaks lost `test_houses`' flag-on check on
seed 35: the island's only scatter house stood 130 px from a Turbo hut
compound, the two sealed a route between them, and the unseal repair took
the house. The buildings pass now keeps a buff building a full building
ring (`building_gap_tiles`) from a house, as from another buff building,
not merely off its collider. Seed 35 keeps its house; digests re-pinned.

### Rev. 6, addendum: a world-dependent trail test (2026-09-20)

The full suite after the house fix lost `test_enemy_sprite`'s puff-count
test: it fires 300 px east from the hero on the pinned seed and, with
buff buildings on every island, that world now has an obstacle inside the
shot's path, so the shot died at three puffs. The test measures shedding,
not blocking, so its shot now opts out of the obstacle block (`no_block`)
the way it already opts out of the elevation rule.
