# Six-weapon system — implementation plan

The design is `six_weapon_system_design.md` at the repository root (sections
19 to 22 hold the decisions taken on 2026-09-07 and 2026-09-09). This document
is the *how* and the *order*. Progress and evidence go to
`journals/weapon_system_journal.md`.

> **Outcome (2026-09-10):** every phase is done, P1 → P5, on top of the
> design in `six_weapon_system_design.md`. Evidence per phase:
> `journals/weapon_system_journal.md`. What was left out on purpose is
> listed there under each phase's "Deferred".

**In one paragraph.** The engine already has most of the primitives the six
weapons need: melee cones, piercing straight shots, spread multi-shot, chain
redirect, orbiters, summons, weight-based knockback, a status framework,
on-kill hooks, ground hazards, explosions, manual aim with a fire-time assist
cone, and a weighted level-up roll whose per-upgrade stack cap already maps
onto levels I to V. What is missing is small and concrete: a stun status, a
fused bomb whose blast goes through the normal hit pipeline, hero-owned ground
hazards, per-enemy "who hit me when" memory, a data-driven blessing catalog
with rarity and requirements, a Forge, and the hero-side changes (traits,
defensive stats, three weapon slots plus a summon slot, per-hero save state).
The plan lands the weapons first so the game stays playable at every step,
then the blessing catalog, then Forging, then synergies, then the hero and
persistence work.

---

## 0. Ground rules

- **Data over code.** Every per-weapon, per-blessing and per-hero number lives
  in `data/*.json`; code keeps only taxonomies (`CATEGORIES`, `CLASSES`,
  status families, blessing kinds). A missing field is bad data and raises,
  never a silent default.
- **Sub-packages per concern.** New runtime code goes in small modules under
  a package (`combat/weapons/`, `progression/blessings/`), not appended to
  the existing large files.
- **Tests move with the code.** Any test module a phase opens loses its
  references to the retired weapons and stays on hand-built fakes or the
  shared cached worlds; no per-test world rebuilds.
- **Playable after every phase.** No phase leaves the run unable to start,
  level up or fight.
- **No homing.** "Tracking" stays a fire-time pick (the manual-aim rules of
  2026-09-04). The Rod's "rough area" is a wider assist cone
  (`aim_assist_deg`), and the "Seeking" upgrade widens it further.

---

## 1. Where the code stands (2026-09-09)

| Concern | Where | State |
|---|---|---|
| Weapon runtime | `combat/weapons.py` (336 lines) | data-driven; `category` ∈ projectile/melee/summon/orbit/spell; special ∈ chain/cone/orbit/summon |
| Weapon data | `data/weapons.json` | 7 weapons: arcane_bolt, frost_shards, thunder_orb, ember_ring, soul_scythe, grave_totem, spirit_wolf |
| Weapon look | `data/weapon_visuals.json`, `game/states/playing/projectiles/*` | colour + `@style` family per weapon id |
| Hit resolution | `game/states/playing/combat.py` | one pass; blessing tag bonus × status amp + vuln; knockback by weight; on-hit statuses |
| Statuses | `combat/status.py` | families dot / slow / amp; burn, poison, bleed, chill, shock |
| Level-up pool | `progression/upgrades.py` | code-defined `Upgrade` records; 8 generic + 5 per owned weapon + "new weapon"; `MAX_WEAPONS = 6`; every 3rd level offers blessings instead |
| Blessings | `progression/blessings.py`, `data/blessings.json` | 30 elemental blessings (Ember/Tide/Storm/Grave), six effect kinds |
| Items | `data/items.json` | 12 stat affixes + 5 tag-damage affixes (3 elemental) |
| Heroes | `data/characters.json`, `entities/player.py` | traits bulwark / windborne / cursebrand in code |
| Save | `game/save.py` | version 1; no per-hero state |
| Explosions / hazards | `game/states/playing/effects.py` | `enemy_explosion` bypasses the hit pipeline; hazards damage the player only |
| Village Forge | `world/layout.py`, `world/gen/*`, `assets/terrain/facilities/forge.png` | placed, one per village island; no interaction yet |
| Baseline tests | `tests/combat tests/progression tests/core` | 313 passed in 4 min 27 s |

---

## 2. Phases

### P1 — Weapon data and primitives — done 2026-09-09

**Goal.** The six weapons and the three summons exist in data and fire; the
old weapons are gone; heroes start with Sword, Bow and Magic Rod; the trait
and defensive-stat decisions are in; a run holds three weapons plus one
summon. Blessings and the level-up pool are untouched except for the slot
limits.

**Changes.**

1. `combat/weapons.py` becomes the package `combat/weapons/`:
   `core.py` (`Weapon`, `FireContext`, taxonomy), `bomb.py` (the fused throw),
   `__init__.py` re-exporting the public names so every import stays valid.
2. Taxonomy: a required `class` field ∈ `("melee", "ranged", "summon")` on
   every weapon; `category` and `special_effect` stay as the fire mechanism.
   New special `"bomb"`.
3. `data/weapons.json`: `sword`, `hammer`, `daggers`, `bow`, `magic_rod`,
   `bomb`, plus `grave_totem`, `spirit_wolf`, `ember_ring` with `class:
   summon`. The Rod carries `aim_assist_deg` wider than the default (the
   "rough area"). The Hammer carries `stun_chance` / `stun_duration`. The
   Bomb carries `fuse`, `throw_time`, `blast_radius`, `blast_lifetime`.
4. Stun: a `"stun"` status family. Stunned enemies do not move, do not tick
   their behaviour and deal no contact damage; the boss is immune. Applied by
   the hit resolver from the projectile's `stun_chance`.
5. Bomb: an inert projectile (no direct hits) that flies for `throw_time`
   (or until it reaches its target), sits, and after `fuse` seconds
   detonates: a short-lived stationary blast projectile with
   `blast_radius`, pierce 999 and the bomb's damage goes through
   `CombatResolver.projectile_hits`, so multipliers, crit, knockback and
   on-hit effects apply. A blast also fires when the bomb is blocked by an
   obstacle. The ring visual reuses `_explosions`.
6. `Projectile` gains `weapon_id`, `age`, `stop_after`, `blast_radius`,
   `blast_lifetime`, `inert`, `stun_chance`, `stun_duration`.
7. Heroes: `characters.json` starting weapons; `trait_params` per hero;
   `base_stats` gain `evasion_chance` / `block_chance` / `block_strength`
   (defaults in `config.PLAYER_DEFAULTS`: 5 %, 0 %, 50 %). Traits: Bulwark
   (unchanged rule, params in data), Double Shot (extra Bow arrow, damage
   split), Quick Cast (Rod cooldown multiplier). Windborne and Cursebrand
   code is removed. `Player.take_damage` rolls evasion, then block, then the
   trait multiplier, then armour.
8. `FireContext.weapon_mods`: a callable the hero supplies that returns
   per-weapon trait modifiers (extra projectiles, cooldown and damage
   multipliers), so traits reach weapons granted later in the run.
9. Slots: `MAX_WEAPONS = 3` counts melee + ranged; `MAX_SUMMONS = 1`. The
   "new weapon" offers in the current pool respect both.
10. Visuals: `weapon_visuals.json` for the nine ids; the cone style takes a
    `slash` flag (the slash rig only for the Sword); the arrow style takes a
    `tint` so the Bow's arrow is not the hostile red; a `blast` style.

**Tests.** `test_weapons_reach`, `test_weapons_special`, `test_manual_aim`,
`test_weapons`, `test_upgrades`, `test_characters` move onto the new ids;
chain behaviour is tested on an inline definition since chain is now an
upgrade. New: `test_weapon_classes` (nine weapons, classes, required fields),
`test_bomb` (throw, stop, fuse, blast through the resolver, block detonates),
`test_stun` (family, movement lock, contact lock, boss immunity, hammer roll),
`test_defense` (evasion, block, order, hero bases), `test_traits`
(double shot count and split, quick cast cooldown, bulwark), slot limits.

**Exit.** Combat + progression + core + characters green; a run starts with
each hero, fires each weapon, and the Bomb detonates on screen.

### P2 — Blessing catalog — done 2026-09-09

**Goal.** One data-driven offering with three kinds (stat, weapon, grant),
gated on owned weapons, weighted per §21, rarity and level on the cards.
Elemental blessings and element item affixes are removed.

**Changes.** `progression/blessings/` package: `catalog.py` (load + validate
`data/blessings.json` with `kind`, `weapon`, `category`, `rarity`,
`levels[]`, `requires`), `offer.py` (valid set + weighted roll: kind base
weights, level falloff, grant weight while slots are empty, summon weight),
`apply.py` (stat modifiers into `StatSet`, weapon bonuses into
`Weapon.bonus`, behaviour hooks by id). `Weapon.bonus` grows (crit, knockback,
stun, range, spread, chain, split, echo, overcharge). Every level-up is an
offering; shrines and altars offer one. `ui/level_up.py` shows rarity ribbon
and level. `data/items.json` loses the elemental affixes. New stats: `xp_gain`
(exists), `gold_gain`, `melee_damage`, `ranged_damage`, `block_chance`,
`evasion_chance`, `block_strength`.

**Tests.** Catalog validation (every weapon blessing names an owned-able
weapon, five levels, rarity), gating (no Hammer blessing without the Hammer),
weights (stat > weapon by default, grant = stat while slots empty, level
falloff monotone, summons lower), a grant adds the weapon alone (CR3),
apply paths per kind. Pure, seeded.

### P3 — Forging — done 2026-09-10

**Goal.** Twelve Forgings as data; a forged weapon is a variant definition
merged over the base plus a behaviour key; exclusive per weapon; requires two
upgrade levels; delivered at the village Forge and at Forge rarity in the
offering; post-Forge blessings gated on the Forge.

**Changes.** `data/forges.json`; `Weapon.forge`; `combat/weapons/forge.py`
(merge + the behaviours that need code: Whirlwind rotating cone, Twin Daggers
double cone, Earthshaker secondary blast, Meteor Hammer and Minefield
hero-owned hazards, Cluster Bomb child bombs, Arcane Storm orbiters, Arcane
Lance). Hero-owned `Hazard` (owner flag; damages enemies through the hit
pipeline). Forge interactable in `game/states/playing/locations.py` with the
requirements message. Offering: forge kind at forge rarity when eligible.

**Tests.** Merge semantics, exclusivity, eligibility, each Forge's behaviour on
fakes, the Forge interaction message, post-Forge gating.

### P4 — Synergies — done 2026-09-10

**Goal.** The six explicit synergies with the 1.5 s window, stated in the
blessing descriptions.

**Changes.** `Enemy.recent_hits: dict[weapon_id, time]` written by the
resolver; a `mark` status for the Rod; `combat/synergy.py` contributes to
`CombatResolver.damage_multiplier`; six synergy blessings in data with
`requires_weapons`; Crowd Cleaner as a pull on Sword hits; Linebreaker as a
Bow bonus against enemies knocked back by the Hammer in the window.

**Tests.** Window boundaries (1.49 s hits, 1.51 s does not), each pair on
fakes, gating on both weapons owned, descriptions carry "1.5 s".

### P5 — Heroes, persistence and presentation — done 2026-09-10

**Goal.** Main-weapon selection unlocked per hero by the first boss kill;
save version 2 with `heroes: {id: {cleared: bool, main_weapon: str}}`; the
attack1 / attack2 alternation and the guard sheet for Bulwark; weapon art for
the six; `combat_calculations.md` rewritten for the new pipeline.

**Tests.** Save round-trip and old-file fallback, unlock on boss kill, the
selection flow, animation alternation, guard while Bulwark is active.

---

## 3. Order and dependencies

P1 → P2 → P3 → P4 → P5. P3 and P4 both build on P2's catalog (Forgings and
synergies are blessings). P5's animation work only needs P1; it is last
because it is presentation, not because it depends on P4.

---

## 4. Out of scope

Elements and infusions (§16), elemental blessings, more than six weapons or
twelve Forgings, per-pair mechanics beyond the six synergies, homing.
