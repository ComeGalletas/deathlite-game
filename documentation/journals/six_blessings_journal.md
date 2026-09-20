# Six blessings per weapon

Journal for the request that every weapon carries six blessings of its own,
covering damage, area, speed / frequency and special effects, with each level
worth about 10-20 % more damage. Companion to
`documentation/designs/weapon_blessing_forge_tables.md` (the generated tables)
and `documentation/journals/weapon_system_journal.md` (the weapon system).

## Requirement (owner, 2026-09-19)

> Review the current `weapon_blessing_forge_tables.md` for the state of the
> weapon system. Propose a way for all weapons to have 6 blessings, that should
> cover damage, area, speed/frequency, and special effects to each one. Make it
> so that the increases are at around 10-20 % more damage for each level.
> Confirm.

## Review of the tables (state on 2026-09-19)

The tables were generated on 2026-09-12 and the data has moved since:

- **Daggers are stale in the doc.** `data/weapons/weapons.json` now has the
  Daggers at damage 9, cooldown 0.4 s, area 42, cone +-17 deg (commit
  `3cf7e6f`, 2026-09-16); the doc still prints 5 / 0.42 / 22 / +-23. Every
  Daggers "resulting value" line is therefore wrong. Regenerating the tables
  is part of this pass.
- **The three defects the doc lists are still open**: the Forge card texts
  that say "lighter" over overrides that are not lighter (Meteor Hammer,
  Cluster Bomb, Minefield), the Bomb's two overlapping coverage blessings
  (Bigger Explosion + Blast Amplifier), and the uneven blessing counts. The
  second and third are what this request is about. The Forge card texts are
  a separate defect and are left for their own pass (see "Not in this pass").

Blessing counts per weapon today, own blessings only (a synergy needs a second
weapon, a post-Forge blessing needs the Forge, so neither is "the weapon's
own"):

| Weapon | Own | Of which damage / speed / area / special | Synergies | Post-Forge |
|---|---|---|---|---|
| Sword | 5 | Sharpened Edge / - / Wide Cleave / Heavy Blade, Bloodletting, Critical Edge | 1 | 2 |
| Hammer | 5 | Crushing Blow / - / Heavy Impact / Titan's Grip, Staggering Strike, Executioner | 0 | 2 |
| Daggers | 4 | Sharpened Blades / Quick Hands / Extended Reach / Weak Point | 2 | 3 |
| Bow | 5 | (Heavy Draw, a trade) / Rapid Draw / Piercing Arrow / Split Arrow, Hunter's Mark | 2 | 2 |
| Magic Rod | 4 | - / - / Arcane Missiles / Seeking, Chain, Overcharge | 0 (trigger for 2) | 2 |
| Bomb | 4 | Explosive Force / - / Bigger Explosion, Blast Amplifier / Demolitionist | 1 | 2 |
| Ember Ring | 3 | Ember Heat / - / More Embers, Wide Orbit / - | - | - |
| Grave Totem | 4 | Spectral Bolts / Quick Plant / Twin Totems, Long Watch / - | - | - |
| Spirit Wolf | 3 | Savage Bite / Swift / Pack / - | - | - |

Gaps against the four axes: no speed blessing on Sword, Hammer, Rod, Bomb or
Ember Ring; no damage blessing on the Rod (and the Bow's only one is a trade);
no special effect on any summon; the Bomb has two area cards and the Daggers
have one special.

**How the current damage blessings scale.** Sharpened Edge on the Sword is
+3 / 6 / 9 / 13 / 17 on a base of 15: level I is +20 %, and the steps between
levels are 20 / 17 / 14 / 17 / 14 % of the previous total. Crushing Blow is
+22 % at I and ends at +122 %; Explosive Force is +30 % at I and ends at
+165 %; Spectral Bolts is +43 % at I and ends at +214 %. So the first level
is usually above the 10-20 % band and the endpoint varies from x2.1 to x3.1
between weapons. The speed blessings are the mirror: Quick Hands is
x0.92 / 0.84 / 0.75 / 0.65 / 0.5, so its steps are +9 / 10 / 12 / 15 / 30 %
attack rate -- flat until a large jump at V.

## Confirmed reading

1. **"Six blessings" means six blessings that are the weapon's own**: offered
   whenever the weapon is held, no other weapon and no Forge required. The six
   cross-weapon synergies (Blood in the Water, Marked Prey, Linebreaker,
   Crossfire, Demolition, Crowd Cleaner) stay as they are, on top of the six,
   still gated on the second weapon. Post-Forge blessings also stay as they
   are. *Decision taken here; the alternative (counting synergies inside the
   six) would leave a hero with one weapon short of the four axes.*
2. **The four axes map onto the existing categories.** Damage and speed are
   `power` (design section 5.1 lists attack speed under Power), area / count /
   reach are `coverage`, special effects are `behavior`. No new category is
   added to the catalog. Weak Point and Demolitionist are re-tagged from
   `synergy` to `behavior`: neither needs another weapon, and the synergy
   offer tests only list the six true synergies.
3. **Every weapon gets the same skeleton**: one damage blessing, one speed /
   frequency blessing, one or two coverage blessings, and the rest special
   effects, six in all. Summons included: the earlier decision (2026-09-09)
   that summons get only Power / Coverage upgrades is superseded for
   behaviour blessings by this request ("all weapons"); it still holds for
   synergies and Forgings.
4. **"10-20 % more damage for each level" is read as a compounding yardstick
   of x1.15 per level**: the damage blessing's cumulative total at level n is
   base x (1.15^n - 1), so level V doubles the weapon's damage
   (x1.15 / 1.32 / 1.52 / 1.75 / 2.01) and every step is 13-17 % over the
   previous level, rounding permitting. The same yardstick sizes the other
   axes so that one level of any blessing is worth about the same:
   - **speed**: cooldown (or attack interval) x1 / 1.15^n = x0.87 / 0.76 /
     0.66 / 0.57 / 0.50, so level V also doubles output;
   - **trade blessings** (Heavy Blade, Heavy Draw: x1.15 slower): damage sized
     so the *net* output still climbs x1.15 per level, x2.03 at V;
   - **coverage**: about +20-25 % hit area per level, x2.2-2.6 at V (a bigger
     area only pays in a crowd, so it is allowed to outgrow the damage line);
     the two identity count cards (Arcane Missiles, More Embers) are kept as
     they are and flagged as above the yardstick;
   - **special effects**: sized so that when their condition holds they are
     worth about the yardstick (worked out per card below).
5. **The old blessing names and ids are kept** where a blessing survives, so
   saves, tests and the run-status screen keep working; only levels and a few
   descriptions change. Blast Amplifier is removed.

## Proposal

### The yardstick, applied

Flat damage adds, `round(base x (1.15^n - 1))`, adjusted by one where rounding
would make a step fall under 10 % or over 20 %:

| Weapon | Base | I | II | III | IV | V | Steps over previous |
|---|---|---|---|---|---|---|---|
| Sword | 15 | +2 | +5 | +8 | +11 | +15 | 13 / 18 / 15 / 13 / 15 % |
| Hammer | 27 | +4 | +9 | +14 | +20 | +27 | 15 / 16 / 14 / 15 / 15 % |
| Daggers | 9 | +1 | +3 | +5 | +7 | +9 | 11 / 20 / 17 / 14 / 13 % |
| Bow | 10 | +1 | +3 | +5 | +7 | +10 | 10 / 18 / 15 / 13 / 18 % |
| Magic Rod | 10 | +1 | +3 | +5 | +7 | +10 | same |
| Bomb | 23 | +3 | +7 | +12 | +17 | +23 | 13 / 15 / 17 / 14 / 15 % |
| Ember Ring | 6 | +1 | +2 | +3 | +4 | +6 | 17 / 14 / 13 / 11 / 20 % |
| Grave Totem | 7 | +1 | +2 | +3 | +5 | +7 | 14 / 13 / 11 / 20 / 17 % |
| Spirit Wolf | 12 | +2 | +4 | +6 | +9 | +12 | 17 / 14 / 13 / 17 / 14 % |
| Greatsword (Cleaver) | 42 | +6 | +13 | +22 | +31 | +42 | 14 / 15 / 16 / 14 / 15 % |
| Twin Daggers (Dual Wield) | 4 | +0.6 | +1.3 | +2.1 | +3 | +4 | 15 / 15 / 15 / 15 / 14 % |
| Ballista (Siege Bolt) | 50 | +8 | +16 | +26 | +37 | +50 | 16 / 14 / 15 / 14 / 15 % |
| Arcane Lance (Impale) | 34 | +5 | +11 | +18 | +25 | +34 | 15 / 15 / 16 / 13 / 15 % |

Speed (cooldown multiplier, cumulative): **x0.87 / 0.76 / 0.66 / 0.57 / 0.50**,
printed as 13 / 24 / 34 / 43 / 50 % faster. Used by every speed and frequency
blessing, including the post-Forge Dense Field.

Trade blessings (cooldown x1.15 at every level, as now):

| Blessing | Base | I | II | III | IV | V | Net output |
|---|---|---|---|---|---|---|---|
| Heavy Blade (Sword) | 15 | +5 | +8 | +11 | +15 | +20 | x1.16 / 1.33 / 1.51 / 1.74 / 2.03 |
| Heavy Draw (Bow) | 10 | +3 | +5 | +8 | +10 | +13 | x1.13 / 1.30 / 1.57 / 1.74 / 2.00 |

### The six per weapon

Legend: **kept** = same id, levels re-sized; **new** = new id; *code* = needs
engine work, listed in "Engine work" below. Rarities: damage and speed common,
coverage uncommon, specials uncommon or rare.

**Sword** (15 dmg, 1.2 s, area 40, cone +-60)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Sharpened Edge (kept) | +2 / 5 / 8 / 11 / 15 | |
| 2 | speed | Swift Sweep (new) | cooldown x0.87 .. 0.50 | data only |
| 3 | area | Wide Cleave (kept) | area +3 / 6 / 9 / 12 / 16, cone +3 / 6 / 9 / 12 / 15 deg | sweep area x1.21 per level, x2.45 at V (was x5.7) |
| 4 | special | Heavy Blade (kept, rare) | +5 / 8 / 11 / 15 / 20 dmg, +10 .. +50 weight, x1.15 slower | |
| 5 | special | Bloodletting (kept, rare) | +1 .. +5 HP per kill | |
| 6 | special | Critical Edge (kept) | +5 / 10 / 15 / 20 / 25 % crit chance **and** +0.1 / 0.2 / 0.3 / 0.4 / 0.5 crit damage | *code*: a `crit_damage` weapon bonus; expected +5 / 12 / 20 / 28 / 38 % |

**Hammer** (27 dmg, 1.5 s, area 35)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Crushing Blow (kept) | +4 / 9 / 14 / 20 / 27 | |
| 2 | speed | Quick Swing (new) | cooldown x0.81 / 0.64 / 0.50 / 0.37 / 0.26 | data only; shortens the rest between blows, Haste shortens the swing (CR1); sized on the swing + rest cycle (see "Two corrections") |
| 3 | area | Heavy Impact (kept) | area +4 / 8 / 12 / 16 / 20 | impact area x1.24 per level, x2.5 at V (was x5.9) |
| 4 | special | Titan's Grip (kept) | weight +15 .. +80 | |
| 5 | special | Staggering Strike (kept) | stun +8 .. +40 %, +0.1 .. +0.5 s | |
| 6 | special | Executioner (kept, rare) | +25 .. +110 % under 35 % HP | |

**Daggers** (9 dmg, 0.4 s, area 42, cone +-17, pierce 1)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Sharpened Blades (kept) | +1 / 3 / 5 / 7 / 9 | |
| 2 | speed | Quick Hands (kept) | cooldown x0.87 .. 0.50 | was x0.92 .. 0.50 |
| 3 | area | Extended Reach (kept) | area +4 / 8 / 12 / 16 / 20 | x1.2 per level, x2.2 at V |
| 4 | special | Weak Point (kept, rare, now `behavior`) | +15 .. +80 % vs wounded | |
| 5 | special | Flurry (new, rare) | each consecutive hit on the same enemy within 1.5 s: +4 / 6 / 8 / 10 / 12 % attack speed per stack, 5 stacks | *code*; +20 .. +60 % rate at full stacks; from the design doc |
| 6 | special | Lacerate (new) | hits bleed for 2.5 / 5 / 7.5 / 10 / 12.5 % of the hit every 0.4 s for 2 s, 6 stacks | *code*; +15 .. +75 % on a target held at full stacks |

**Bow** (10 dmg, 1.2 s, pierce 2)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Broadhead (new) | +1 / 3 / 5 / 7 / 10 | data only |
| 2 | speed | Rapid Draw (kept) | cooldown x0.87 .. 0.50 | was x0.92 .. 0.55 |
| 3 | area | Piercing Arrow (kept) | pierce +1 / 2 / 3 / 4 / 6 | |
| 4 | special | Heavy Draw (kept, rare) | +3 / 5 / 8 / 10 / 13 dmg, x1.15 slower | |
| 5 | special | Split Arrow (kept, rare) | as now | |
| 6 | special | Hunter's Mark (kept, rare) | as now | |

**Magic Rod** (10 dmg, 1.0 s, count 1)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Arcane Focus (new) | +1 / 3 / 5 / 7 / 10 | data only |
| 2 | speed | Quick Cast (new) | cooldown x0.87 .. 0.50 | data only; stacks with Nihil's trait |
| 3 | area | Arcane Missiles (kept) | count +1 / 1 / 2 / 2 / 3 | identity card, above the yardstick; unchanged |
| 4 | special | Seeking (kept) | aim assist +10 .. +55 deg | |
| 5 | special | Chain (kept, rare) | as now | |
| 6 | special | Overcharge (kept, rare) | every **4th** cast at x1.6 / 2.1 / 2.6 / 3.2 / 3.8 | was every 5th at x1.6 .. 3.0 (+12 .. +40 % average); now +15 / 28 / 40 / 55 / 70 % average |

**Bomb** (23 dmg, 2.2 s, blast 42, fuse 1.1)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Explosive Force (kept) | +3 / 7 / 12 / 17 / 23 | |
| 2 | speed | Bandolier (new) | cooldown x0.87 .. 0.50 | data only |
| 3 | area | Bigger Explosion (kept) | blast +5 / 10 / 15 / 20 / 25 | blast area x1.25 per level, x2.55 at V; **Blast Amplifier removed** |
| 4 | special | Demolitionist (kept, rare, now `behavior`) | +20 .. +100 % vs stunned / shoved | |
| 5 | special | Sticky Bomb (new, rare) | the bomb sticks to the first enemy it touches and its blast hits +10 / 20 / 30 / 40 / 50 % harder | *code*; from the design doc |
| 6 | special | Powder Keg (new, rare) | an enemy killed by a blast bursts for 20 / 30 / 40 / 50 / 60 % of the blast's damage in 60 % of its radius; a burst never bursts again | *code* |

**Ember Ring** (6 dmg, count 3, ember size 8, orbit 96, rehit 0.4 s)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Ember Heat (kept) | +1 / 2 / 3 / 4 / 6 | |
| 2 | speed | Fanned Flames (new) | orbit speed x1.15 / 1.32 / 1.52 / 1.75 / 2.0, rehit interval x0.87 .. 0.50 | *code*: `orbit_speed_mult` and `rehit_mult` weapon bonuses (see "Two corrections") |
| 3 | area | More Embers (kept) | count +1 .. +5 | identity card, unchanged |
| 4 | area | Wide Orbit (kept) | ember size +1 / 2 / 3 / 4 / 5 | ember hit area x1.27 per level, x2.6 at V (was x8.3) |
| 5 | special | Scorch (new) | embers burn for 4 / 8 / 11 / 15 / 19 % of the hit every 0.5 s for 2 s, 5 stacks | *code*; +16 .. +76 % on a target held at full stacks |
| 6 | special | Far Orbit (new) | the ring spins +12 / 24 / 36 / 48 / 60 px further out and wakes +16 .. +80 px further | *code*: `orbit_radius` and `reach` weapon bonuses |

**Grave Totem** (7 dmg, cooldown 6 s, life 8 s, replant gap 5 s, bolt every 0.7 s)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Spectral Bolts (kept) | +1 / 2 / 3 / 5 / 7 | |
| 2 | speed | Rapid Bolts (new) | bolt interval x0.87 .. 0.50 | *code*: an `attack_interval_mult` weapon bonus, refreshed on live summons |
| 3 | frequency | Quick Plant (kept) | cooldown and replant gap x0.87 .. 0.50 | was x0.9 .. 0.5; the 5 s gap becomes 4.35 s at I, 2.5 s at V as before |
| 4 | area | Twin Totems (kept) | count +1 / 1 / 2 / 2 / 3 | |
| 5 | area | Long Watch (kept) | life +2 .. +10 s | |
| 6 | special | Chilling Bolts (new) | bolts slow the target by 15 / 20 / 25 / 30 / 35 % for 1.5 s | *code*; uses the existing `chill` status |

**Spirit Wolf** (12 dmg, respawn 7 s, bite every 0.6 s, range 70, speed 240, chase 180)

| # | Axis | Blessing | Levels | Note |
|---|---|---|---|---|
| 1 | damage | Savage Bite (kept) | +2 / 4 / 6 / 9 / 12 | |
| 2 | speed | Frenzy (new) | bite interval x0.87 .. 0.50 | *code*: the same `attack_interval_mult` |
| 3 | frequency | Swift (kept) | respawn x0.87 .. 0.50 | was x0.9 .. 0.5 |
| 4 | area | Pack (kept) | count +1 / 1 / 2 / 2 / 3 | |
| 5 | area | Long Stride (new) | run speed +30 .. +150, chase reach +30 .. +150 | *code*: `summon_speed` and `summon_reach` weapon bonuses |
| 6 | special | Pack Tactics (new, rare) | +15 / 30 / 45 / 60 / 75 % against an enemy the hero's weapons hit in the last 1.5 s | *code*; reads the same per-enemy hit record as the synergies |

Post-Forge blessings re-sized to the yardstick: Cleaver, Dual Wield, Siege
Bolt, Impale (damage per the table above); Dense Field (speed curve). Cyclone,
Cross Cut, More Blades, Wide Volley, Tempest, Aftershock, Crater, Bomblets are
unchanged.

### Engine work

Small, and all of it reuses a hook that exists.

| Piece | Where | What |
|---|---|---|
| `crit_damage` bonus | `combat/weapons/core.py` | `_crit_multiplier(ctx)` = hero crit multiplier + bonus, passed where `ctx.crit_multiplier` is today |
| `rehit_mult` bonus | `core.py` `_maintain_orbit` | rehit interval x bonus, refreshed on live orbiters like damage is |
| `attack_interval_mult`, `summon_speed`, `summon_reach` bonuses | `core.py` `_maintain_summons` | applied at plant time and refreshed on live summons each frame |
| `orbit_radius`, `reach` bonuses | `core.py` | orbit radius + bonus; `_reach` adds `bonus["reach"]` beside `bonus["area"]` |
| On-hit status from a weapon | `game/states/playing/core/combat.py` | effect keys `<status>_on_hit_frac` (dot potency as a fraction of the hit), `<status>_on_hit_potency` (raw potency for slow), `<status>_on_hit_duration`; applied in the hit resolver next to `apply_on_hit_effects`, source = the weapon so the DPS meter attributes the ticks |
| Flurry | `core.py` + hit resolver | `flurry_per_hit`, `flurry_max`; on a hit the weapon takes the target's streak (`enemy.hit_streak`), the cooldown divides by `1 + per_hit x stacks` while the window is warm |
| Pack Tactics | `combat/synergy.py` | `pack_tactics_mult`: bonus when any *other* weapon of the hero hit the enemy inside the window |
| Sticky Bomb | `combat/weapons/bomb.py` + projectile update | `sticky`, `sticky_damage_mult`; a flying bomb that overlaps an enemy attaches and follows it until the fuse; the blast carries the multiplier |
| Powder Keg | on-kill path in `game/states/playing/core/state.py` | `keg_frac`; a kill by a blast (tag `blast`, not `keg`) spawns a `keg` blast at the victim |

`tools/gen_weapon_tables.py` learns the new bonus fields' labels, and the doc
is regenerated.

### Tests

- `tests/progression/test_blessings.py`: every weapon has exactly six own
  blessings (no `requires`), and among them one damage add, one cooldown or
  interval mult, one coverage card; every damage blessing follows
  `base x (1.15^n - 1)` within +-1 (+-0.2 under a base of 5) and every speed
  blessing follows the x0.87 .. 0.50 curve; the catalog still loads and every
  card's description formats at every level.
- New engine behaviour, one test each in `tests/combat/`: crit damage bonus
  raises a crit's amount; rehit and attack-interval bonuses shorten the
  interval on live orbiters / summons; Far Orbit moves the ring out and wakes
  it further; an on-hit status lands with the weapon as source and its potency
  as the fraction of the hit; Flurry stacks with the streak and expires with
  the window; Pack Tactics needs another weapon's hit; a sticky bomb follows
  the enemy it touched and its blast is heavier; a Powder Keg burst spawns
  once and never chains from a burst.
- The DPS bench (`tools/benchmarks/dps_bench.py`) run before and after at the
  same seed, for the record.

### Not in this pass

- The three Forge card texts that claim a lighter blow (Meteor Hammer,
  Cluster Bomb, Minefield). Not a blessing; the doc's suggested overrides
  (about 22 / 18 / 20) are the fix when that pass is taken.
- Offering weights (`data/weapons/offering.json`). More cards per weapon
  share the same `weapon` kind weight, so each card appears less often; if
  that reads as too diluted, raising `weapon` from 7 is the knob.

## Build (2026-09-19) — DONE

Built as proposed, with two corrections the measurement forced (below).

**Data.** `data/weapons/blessings.json` rewritten: 88 blessings, 73 of them
weapon blessings (54 own, 6 synergies, 13 post-Forge). Ids of surviving cards
unchanged; new ids `sword_swift_sweep`, `hammer_quick_swing`,
`daggers_flurry`, `daggers_lacerate`, `bow_broadhead`,
`magic_rod_arcane_focus`, `magic_rod_quick_cast`, `bomb_bandolier`,
`bomb_sticky`, `bomb_powder_keg`, `ember_ring_fanned_flames`,
`ember_ring_scorch`, `ember_ring_far_orbit`, `grave_totem_rapid_bolts`,
`grave_totem_chilling_bolts`, `spirit_wolf_frenzy`,
`spirit_wolf_long_stride`, `spirit_wolf_pack_tactics`. `bomb_blast_amplifier`
removed. Weak Point and Demolitionist re-tagged `behavior`.

**Engine.**

- `combat/weapons/core.py`: bonus fields `crit_damage`, `reach`,
  `orbit_radius`, `orbit_speed_mult`, `rehit_mult`, `attack_interval_mult`,
  `summon_speed`, `summon_reach`; `_crit_multiplier`; Flurry state
  (`note_flurry`, `_flurry_rate`, ticked in `update`); live orbiters and
  summons refreshed each frame (`_refresh_summons`).
- `combat/weapons/bomb.py`, `slam.py`: crit multiplier through the weapon;
  the throw carries `sticky`.
- `entities/projectile.py`: `sticky`, `stuck_to`.
- `game/states/playing/core/combat.py`: `apply_weapon_statuses` (on-hit keys
  by suffix), `flurry`, `stick`, `killed_by_shot` on a kill.
- `combat/synergy.py`: `pack_tactics_mult`.
- `game/states/playing/core/effects.py`: `ride_stuck`, `keg_burst`; a
  detonation's blast now carries the `blast` tag.
- `game/states/playing/core/state.py`: Powder Keg on the on-kill path.
- `tools/gen_weapon_tables.py`: labels for the new fields and keys, review
  findings rewritten; tables regenerated.

### Two corrections from the measurement

Each weapon was measured alone against the training dummy (bench arena,
Aegis, 30 s per cell) at every level of its damage card and of its speed
card. Two speed cards missed the band on the first pass:

- **Hammer, Quick Swing** stepped +7 / 7 / 12 / 6 / 11 %. The blow is a 0.7 s
  swing plus a 1.5 s rest and a cooldown blessing only shortens the rest
  (CR1: Haste shortens the swing), so a x0.87 rest shrinks the 2.2 s cycle by
  only 9 %. The card's curve is now sized on the whole cycle,
  rest = (2.2 / 1.15^n − 0.7) / 1.5: **x0.81 / 0.64 / 0.50 / 0.37 / 0.26**
  (printed 19 / 36 / 50 / 63 / 74 %). Measured after: +14 / 12 / 17 / 14 / 12 %.
- **Ember Ring, Fanned Flames** did nothing: with three embers at 3.2 rad/s a
  pass comes every 0.65 s, so the 0.4 s rehit never binds and shortening it
  changes no hit. The card now spins the ring **x1.15 / 1.32 / 1.52 / 1.75 /
  2.0** (`orbit_speed_mult`) and shortens the rehit alongside so it never
  becomes the limit. Measured with the dummy on the ring: +8 / 18 / 13 / 15 /
  11 %.

### Measured ladder

30 s per cell, one weapon alone, Aegis, no items, dummy at the bench standoff
(on the orbit radius for the Ember Ring). dps.

| Weapon | Blessing | 0 | I | II | III | IV | V | Steps over previous |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Sword | Sharpened Edge | 12.5 | 14.2 | 16.7 | 19.2 | 21.7 | 25.0 | +13 / 18 / 15 / 13 / 15 % |
| Sword | Swift Sweep | 12.5 | 14.5 | 16.5 | 19.0 | 21.5 | 25.0 | +16 / 14 / 15 / 13 / 16 % |
| Hammer | Crushing Blow | 12.6 | 14.5 | 16.8 | 19.1 | 21.9 | 25.2 | +15 / 16 / 14 / 15 / 15 % |
| Hammer | Quick Swing | 12.6 | 14.4 | 16.2 | 18.9 | 21.6 | 24.3 | +14 / 12 / 17 / 14 / 12 % |
| Daggers | Sharpened Blades | 21.6 | 24.0 | 28.8 | 33.6 | 38.4 | 43.2 | +11 / 20 / 17 / 14 / 12 % |
| Daggers | Quick Hands | 21.6 | 25.8 | 28.5 | 33.9 | 38.7 | 41.7 | +19 / 10 / 19 / 14 / 8 % |
| Bow | Broadhead | 8.3 | 9.2 | 10.8 | 12.5 | 14.2 | 16.7 | +10 / 18 / 15 / 13 / 18 % |
| Bow | Rapid Draw | 8.3 | 9.7 | 11.0 | 12.7 | 14.3 | 16.7 | +16 / 14 / 15 / 13 / 16 % |
| Magic Rod | Arcane Focus | 10.0 | 11.0 | 13.0 | 15.0 | 17.0 | 20.0 | +10 / 18 / 15 / 13 / 18 % |
| Magic Rod | Quick Cast | 10.0 | 11.3 | 13.3 | 15.0 | 17.3 | 19.7 | +13 / 18 / 12 / 16 / 13 % |
| Bomb | Explosive Force | 10.7 | 12.1 | 14.0 | 16.3 | 18.7 | 21.5 | +13 / 15 / 17 / 14 / 15 % |
| Bomb | Bandolier | 10.7 | 12.3 | 13.8 | 15.3 | 17.6 | 20.7 | +14 / 12 / 11 / 15 / 17 % |
| Ember Ring | Ember Heat | 12.4 | 14.5 | 16.5 | 18.6 | 20.7 | 24.8 | +17 / 14 / 12 / 11 / 20 % |
| Ember Ring | Fanned Flames | 12.4 | 13.4 | 15.8 | 17.8 | 20.4 | 22.6 | +8 / 18 / 13 / 15 / 11 % |
| Grave Totem | Spectral Bolts | 5.8 | 6.7 | 7.5 | 8.3 | 10.0 | 11.7 | +14 / 12 / 11 / 20 / 17 % |
| Grave Totem | Rapid Bolts | 5.8 | 6.5 | 7.2 | 8.4 | 9.6 | 10.5 | +12 / 11 / 16 / 14 / 10 % |
| Spirit Wolf | Savage Bite | 20.0 | 23.3 | 26.7 | 30.0 | 35.0 | 40.0 | +17 / 14 / 12 / 17 / 14 % |
| Spirit Wolf | Frenzy | 20.0 | 22.4 | 25.6 | 30.0 | 34.0 | 37.6 | +12 / 14 / 17 / 13 / 11 % |

Every damage card doubles its weapon by V with 10-20 % steps. The speed cards
wobble around the band (Quick Hands +19 / 10 / 19 / 14 / 8 %) because a
cooldown is spent in whole 60 Hz frames: 0.4 s is 24 frames, x0.87 is 20.9
rounded to 21, x0.76 is 18.2 rounded to 19, so the steps alternate short and
long while the five-level total (x1.93) is on the curve. Not a data problem.

**Random-loadout bench** (`tools/benchmarks/dps_bench.py --seed 1234 --runs
10 --seconds 30`, three random blessings): before 32.4-66.4 dps (spread
2.05x), after 29.1-59.4 dps (2.04x). The catalog grew, so the same seed draws
different loadouts; the two tables are the same kind of number, not a
row-for-row comparison.

**Tests.** `tests/progression/test_six_blessings.py` (12: six per weapon, the
axes, synergy tagging, the yardstick on damage / speed / trade / post-Forge
cards, the Hammer's cycle curve, every card formats, on-hit statuses name
registered statuses) and `tests/combat/test_six_blessings.py` (25: crit
damage, Fanned Flames and Far Orbit on live embers, summon bonuses on planted
and live summons, Lacerate / Chilling Bolts / Scorch, Flurry, Pack Tactics,
Sticky Bomb, Powder Keg and the killing-shot record). Existing tests moved
with the data: `BlastAmplifierTests` removed, the synergy count 8 -> 6, the
Sharpened Edge II card text +6 -> +5. Full suite: 1111 passed in
progression / combat / playing / screens, 883 in the rest; the one failure,
`tests/entities/ai/test_imp.py::RigTests::test_the_editor_source_is_not_shipped`,
fails on the baseline too (an untracked `assets/unused/.../Imp.aseprite` the
worktree does not carry).

## Follow-up (owner, 2026-09-19): the Forge cards, the post-Forge gate, the weapon weight

> Fix the forge card defect and make sure the forge blessings aren't being
> offered as normal blessings, and the weapon weight should rise, but first
> propose how much.

**Forge cards fixed.** The three overrides are re-based on the current
weapons so the cards tell the truth: Meteor Hammer 27 → **23** (0.85 of the
Hammer's 27; the crater's 0.35 dps × 2.5 s is worth most of a blow on top),
Cluster Bomb 24 → **20** and Minefield 26 → **21** (0.86 and 0.93 of the
Bomb's 23, the ratios the Forgings shipped with on 2026-09-10 against a
28-damage Bomb). `data/weapons/forges.json`; the crater test now reads the
Forge's own damage instead of a literal; tables regenerated.

**Post-Forge cards are gated in the game, and now in the bench.** The
offering's `_valid_blessing` (`progression/blessings/offer.py`) already
refuses a `requires.forge` card unless one of the hero's weapons took that
Forge, and every roll in the game (level-up, chest, shrine) goes through it.
The one place that ignored the gate was the DPS bench, which sampled
blessings straight from the catalog by weapon: the tables in this journal
list rows such as Bomblets on an unforged Bomb. `tools/benchmarks/dps_bench.py`
now draws each card from `blessing_offers`, one at a time, so a measured
build only holds what a run could show it. A new test,
`PostForgeGateTests`, pins the gate: no post-Forge card for an unforged
weapon, the Forge taken unlocks its own cards and not its sibling's, with and
without the `kinds` filter the chest and shrine paths pass.

**Weapon weight: proposal (not applied).** The kind weight is applied per
card, so with six own cards per weapon the *weapon share* of a roll already
rose with the catalog: with three weapons and no levels taken, weapon cards
carry 75 of 216 points (35 %) against 55 of 196 (28 %) before, and a
level-up shows at least one weapon card 72 % of the time against 63 %. What
fell is each single card's chance, because the pool it competes in grew: a
given common weapon card at level I went from about 10 % to about 9 % of
level-ups. The knob, `kind_weights.weapon` in `data/weapons/offering.json`,
today 7 against stat 10 / grant 10 / forge 8:

| weapon weight | three weapons: weapon share | ≥1 weapon card per level-up | one weapon: share | a given common card per level-up |
|---:|---:|---:|---:|---:|
| 7 (now) | 35 % | 72 % | 12 % | 9 % |
| 8 | 38 % | 76 % | 13 % | 10 % |
| 9 | 41 % | 79 % | 15 % | 11 % |
| 10 | 43 % | 82 % | 16 % | 12 % |

Recommendation: **10**, parity with the stat and grant kinds. Stat cards
still outweigh weapon cards in every configuration (123 points against 107
with three weapons), which keeps the 2026-09-09 rule that a stat card shows
up in practically every level-up, and a given weapon card comes back to
where it was before the catalog grew, slightly above. 9 is the conservative
choice if the weapon share at three weapons (41 %) reads as too much. The
early game barely moves either way: with one weapon the grants (68 points)
dominate until the slots fill, by design.

## Progress

- [x] Journal written, reading confirmed
- [x] Forge card overrides re-based; post-Forge gate verified, bench brought under it; weapon weight proposed and set to 10 by the owner (2026-09-20)
- [x] Data: damage / speed / coverage re-sized, new data-only cards, Blast Amplifier removed, re-tags
- [x] Engine: crit damage, rehit / orbit speed / interval / orbit / reach / summon bonuses
- [x] Engine: on-hit statuses (Lacerate, Scorch, Chilling Bolts)
- [x] Engine: Flurry, Pack Tactics
- [x] Engine: Sticky Bomb, Powder Keg
- [x] Tests
- [x] Tables regenerated, bench before / after, per-level ladder measured

## Owner's ruling and the merge (2026-09-20)

> use the weights as 10, merge the six-blessings worktree into main but first
> confirm that it wont break anything currently.

**Weapon weight: 10.** Set in `data/weapons/offering.json`, parity with the
`stat` and `grant` kinds, as recommended above.

The number has a consequence the proposal did not measure: it retires the
2026-09-09 rule that a stat card shows up in practically every level-up.
Measured over 600 offerings with three weapons held and no grants:

| weapon weight | >=1 stat card | >=1 weapon card |
|---:|---:|---:|
| 7 (before) | 93.0 % | 74.5 % |
| 8 | 91.5 % | 78.2 % |
| 9 | 88.8 % | 81.5 % |
| **10 (chosen)** | **87.2 %** | **84.2 %** |

The owner was shown the trade and chose to keep 10 and relax the rule, so
three assertions in `tests/progression/test_blessings.py` moved with it:
`test_rules_load` now asserts stat and weapon weigh the same,
`test_stat_outweighs_weapon_at_equal_rarity_and_level` became
`test_stat_and_weapon_weigh_the_same_at_equal_rarity_and_level`, and the
90 % stat-card floor became 85 %, kept as a guard against a future weight
change pushing stat cards out of the offering rather than as the old rule.

**The merge.** The branch turned out to be an ancestor of `main` with the
work uncommitted on top, so this was not a branch merge but twenty commits of
`main` merged into the work. Four files conflicted, all of them where `main`'s
buff-buildings pass touched the same lines:

| File | Conflict | Resolution |
|---|---|---|
| `entities/projectile.py` | Sticky Bomb's `sticky` / `stuck_to` against the pinball's `bounces_left`, in four places | union; a sticky bomb never bounces and a pinball is never sticky |
| `game/states/playing/core/combat.py` | Flurry's hit hook against the Vampire buff's | union, Flurry first |
| `game/states/playing/core/effects.py` | `ride_stuck` against the pinball's bounce branch | `ride_stuck` first, then `main`'s bounce / block branch |
| `tools/benchmarks/dps_bench.py` | this pass's "draw cards through `blessing_offers`" against `main`'s by-hero-level rewrite | `main`'s entirely: `offer_cards` -> `valid_offers` already enforces the same gate, and by hero level is the owner's 2026-09-19 decision |

Two stale literals in tests that the Forge re-base invalidated, both missed by
the build pass because they live outside the files it touched:
`tests/combat/test_hammer_swing.py` pinned the Meteor Hammer's crater at
`27 * 0.35` (now reads the Forge's own damage, as its sibling in
`test_forge.py` already did), and `tests/devtools/test_dps_bench.py` pinned a
fifteen-id damage-blessing set and Sharpened Edge V at 17 (now seventeen ids
-- Broadhead and Arcane Focus joined -- and 15).

**Verification.** Full suite on the merged tree: **2761 passed, 12 failed**
before these fixes; after them every failure is either fixed or reproduces on
clean `main`. Baselined on `main` at `cf015dc`:
`tests/screens/test_menu.py::MenuHasNoScrollPanelTests::test_no_banner_rigs_are_declared`
and the three `tests/world/test_digest.py` failures are **pre-existing** --
the digest ones because an unresolved merge-conflict marker was committed
into `tests/world/digests.json` at `34f48ee`, which is a separate bug.
`tests/entities/ai/test_imp.py::RigTests::test_the_editor_source_is_not_shipped`
passes on `main` and fails only inside the worktree, which does not carry the
untracked `assets/unused/` source the test looks for.
