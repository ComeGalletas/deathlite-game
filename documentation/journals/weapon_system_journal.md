# Six-weapon system — execution journal

Progress log for `documentation/weapon_system_plan.md`. One section per
phase: what was done, what was verified, what was deferred, the next item.
The design is `six_weapon_system_design.md`; the plan is the *what*; this is
the *when* and the *evidence*.

**Baseline** (2026-09-09, on top of `3d4c02a` plus the uncommitted terrain
and glow work): `tests/combat tests/progression tests/core` = 313 passed in
4 min 27 s.

---

## P1 — Weapon data and primitives — DONE (2026-09-09)

**What was done.**

- `combat/weapons.py` became the package `combat/weapons/` (`core.py`,
  `bomb.py`, `__init__.py` re-exports). Taxonomy: a required `class` field
  (`melee` / `ranged` / `summon`) validated in `Weapon.__post_init__` next to
  `category` and `special_effect`; `"bomb"` joined the specials.
- `data/weapons.json`: `sword`, `hammer`, `daggers`, `bow`, `magic_rod`,
  `bomb` plus the three summons (`ember_ring`, `grave_totem`, `spirit_wolf`)
  with `class: summon`. Arcane Bolt, Frost Shards, Thunder Orb and Soul
  Scythe are gone; their code paths (chain, orbit, cone, straight shot) stay.
  The Rod carries `aim_assist_deg: 45` -- the "rough area" of decision 6 --
  the Hammer `stun_chance` / `stun_duration`, the Bomb `fuse`, `throw_time`,
  `blast_radius`, `blast_lifetime`.
- **Stun**: a `stun` status family (`combat/status.py`). `speed_multiplier()`
  is 0 while stunned, `is_stunned()` is read by `Enemy.update`, which then
  skips the behaviour tick, zeroes velocity and contact damage (knockback
  still moves the body). `Boss.stun_immune = True`. The resolver rolls
  `CombatResolver.apply_stun` on every damaging hit.
- **Bomb**: an `inert` projectile (the resolver skips it) that flies for
  `stop_after` seconds -- the data's `throw_time`, shortened so it lands on
  the nearest candidate (`bomb.landing_time`) -- then sits until its `fuse`
  lifetime ends. `TransientFx.update_projectiles` calls `detonate` when a
  bomb goes inactive undetonated (fuse or obstacle): a stationary `blast`
  projectile (pierce 999, `no_block`, style `blast`) goes back through
  `projectile_hits`, so multipliers, crit, knockback and on-hit apply; the
  `_explosions` ring, a burst and a shake play. `Projectile` gained
  `weapon_id`, `age`, `stop_after`, `inert`, `blast_radius`,
  `blast_lifetime`, `detonated`, `stun_chance`, `stun_duration`, `no_block`.
  `_resolve_visual` no longer pops `weapon_id`; `Summon.reset` accepts it.
- **Heroes**: `characters.json` starts Aegis / Kestrel / Nihil with Sword /
  Bow / Magic Rod; each has `trait_params`. `Player.weapon_mods(weapon)` ->
  `WeaponMods(extra_projectiles, cooldown_mult, damage_mult)` reaches
  weapons through `FireContext.weapon_mods` (Double Shot: +1 Bow arrow at
  0.65; Quick Cast: Rod cooldown x0.85; Bulwark: unchanged rule, numbers in
  data, `bulwark_active` exposed for the guard sheet). Windborne / Momentum
  and Cursebrand are removed (player, resolver, HUD). Defensive stats:
  `config.PLAYER_DEFAULTS` evasion 5 %, block 0 %, block strength 50 %;
  Kestrel evasion 10 %, Aegis block 30 % in data. `Player.take_damage` rolls
  evasion, then block, then the trait multiplier, then armour, and records
  `last_defense`; the hero rolls on the run's seeded RNG.
- **Slots**: `MAX_WEAPONS = 3` counts non-summons, `MAX_SUMMONS = 1`; the
  current "new weapon" offers respect both (P2 replaces the pool).
- **Visuals**: `weapon_visuals.json` for the nine ids; the cone style's
  `slash` flag (only the Sword swings the rig); the arrow style's `tint`
  (the Bow is cream, hostiles stay red); a `blast` style module.
- Docs: `combat_calculations.md` (trait hooks, stun, bomb, incoming order),
  README content list.

**Verification.**

- New tests: `test_weapon_classes` (18), `test_bomb` (14), `test_stun` (14),
  `test_characters` rewritten (18), slot tests in `test_upgrades` (3);
  `tests/combat/fakes.py` is a `PlayingState`-shaped namespace with a real
  projectile pool for resolver / effects tests without a world. Migrated:
  `test_manual_aim`, `test_weapons_reach`, `test_weapons_special`,
  `test_weapons`, `test_upgrades`, `test_incoming_damage` (the bite tests now
  pin the hero's RNG so a defence roll cannot swallow a bite),
  `test_projectiles` (the `blast` family).
- `tests/combat tests/characters tests/progression tests/core`: **393
  passed** in 4 min 00 s (baseline 313). `tests/rendering tests/systems
  tests/ai`: 592 passed + the 3 cone-slash tests after the `fx` guard, 1
  skipped.
- Headless smoke (scratchpad): each hero starts with its weapon, trait
  params and defensive stats; all nine weapons deal damage over 2.5 s in a
  real run; a Bomb kills a tank with one explosion ring; a forced Hammer
  roll stuns a tank. Frames captured: Bow arrow cream-tinted, Hammer sector
  without the slash, Bomb blast disc + ring with three damage numbers.

**Deferred / notes.**

- The blast disc (alpha 150) reads strong next to the ring; tune in P5 with
  the weapon art.
- Melee cones with a large radius can still be cancelled by
  `block_on_obstacle` when the hero stands beside a wall (pre-existing; the
  blast is exempt via `no_block`, cones are not). Worth a look in P3 when
  hero-owned hazards land.
- `ui/hud.py` shows `[guard]` next to the trait while Bulwark is up; the
  guard sheet itself is P5.
- Enemies still spawn into a run whose test cleared `ps.enemies` (spawn
  master), which is why the smoke's "alive" counts grow; harmless.

**Next.** P2 -- the blessing catalog (below).

---

## P2 — Blessing catalog — DONE (2026-09-09)

**What was done.**

- `progression/blessings.py` became the package `progression/blessings/`:
  `catalog.py` (typed, strictly validated `BlessingDef`s from
  `data/blessings.json` + `OfferingRules` from `data/offering.json`, cached
  per content), `apply.py` (raise a blessing one level: stat modifiers with
  per-level deltas, `Weapon.bonus` add / mult deltas, `Weapon.effects`
  totals; max-HP blessings heal by the gain; the weapon's HUD level ticks),
  `offer.py` (valid set gated on owned weapons + `requires`, weapon grants
  while slots are open with a pre-rolled level-I bundle, weights, the pure
  weighted roll), `effects.py` (the `BlessingEffects` aggregate the resolver
  reads, now fed by item affixes only).
- `progression/upgrades.py` is the card record (`Upgrade` gained `kind`,
  `rarity`, `level`, `weapon`, `bundle`) plus the slot predicates and thin
  `roll_choices` / `valid_choices` wrappers; the coded generic / per-weapon
  upgrade pool is gone.
- **Catalog**: 14 stat blessings (max HP, move speed, XP gain, gold gain,
  melee damage, ranged damage, attack speed, armour, pickup radius, block
  chance, block strength, evasion, crit, luck) and 35 weapon blessings --
  4-5 per weapon from design §3, 3-4 per summon (Power / Coverage only,
  decision 8). Five levels each, cumulative values, `display` formats for the
  card text.
- **Weights** (`data/offering.json`, design §21): stat 10, weapon 7, grant
  10, summon factor 0.6, level falloff 1 / .85 / .7 / .55 / .4, rarity
  common 1 / uncommon .55 / rare .28 / forge .08, three cards.
- **Engine**: `Weapon.bonus` gained crit_chance, weight, stun_chance,
  stun_duration, blast_radius, aim_assist_deg, chain_count, chain_range,
  cone_half_angle, summon_lifetime, all read by the fire paths (a chain
  bonus makes any straight shot chain); `Weapon.effects` + `_begin_attack`
  (Overcharge); `FireContext.melee_damage_mult / ranged_damage_mult`
  (summons excluded, decision 12); `CombatResolver.weapon_effect_multiplier`
  (Executioner, Weak Point, Demolitionist), `.split` (Split Arrow children,
  tagged `split`, never split again), `enemy.killed_by` and the Bloodletting
  heal in `_apply_on_kill_effects`; `Player.weapon_by_id`; gold from kills
  scaled by `gold_gain` with a fractional carry.
- **Flow**: every level-up is `roll_offering` (the every-third-level split is
  gone); shrines / altars roll one card with `kinds=("stat", "weapon")` so
  they never hand out a weapon; the dev menu lists the catalog by kind /
  weapon / name and a weapon blessing for an unowned weapon grants the
  weapon first.
- **Removed**: the four elemental blessing families; the "of the Pyre /
  Storm / Frost" item affixes (decision 11); Focus / Velocity / Greed as
  code-defined upgrades (their stats are catalog entries or gone).
- **UI**: rarity label top-right in `config.RARITY_COLOURS`, the level as a
  roman numeral in the title, kind / weapon / category on the tag line.
- Docs: `combat_calculations.md` (blessing hooks), the plan.

**Verification.**

- New: `tests/progression/test_blessings.py` (36: catalog validity and
  monotone levels, descriptions at every level, bad data raises, apply
  totals for stat / add / mult / multi-effect / weapon_effect, gating, grant
  bundle exactly one level-I blessing named on the card and reproducible per
  seed, weights: stat > weapon, grant = stat while slots open, falloff
  monotone, summons lower, rarity, and a stat card in > 90 % of 300 rolls),
  `tests/combat/test_weapon_effects.py` (20: the resolver / fire-path
  hooks). Rewritten: `test_upgrades.py` (11). Pinned the hero RNG in the
  bite-arithmetic, movement and dev-restart tests that a 5 % evasion roll
  could flip.
- `tests/core tests/combat tests/characters tests/progression`: **442
  passed** in 4 min 08 s. `tests/rendering tests/systems tests/ai
  tests/spawn`: 713 passed, 1 skipped; the one failure
  (`test_terrain::test_rig_files_and_strip_widths`, the `forge` rig sheet
  2048 px wide vs a 256 x 1 frame spec) is in the owner's uncommitted
  `data/terrain.json` / facilities work, not this phase.
- Frames captured of the level-up panel: an early offering with a "New:
  Bow ... Comes with Sharpened Edge I" grant card, and a later one showing
  "Sharpened Edge III", "Vitality II" and a RARE "Heavy Blade I".

**Deferred (the design's remaining behaviour blessings).**

- Flurry (Daggers), Hunter's Mark (Bow), Echo (Rod), Sticky Bomb and
  Fragmentation (Bomb) need per-target or delayed-fire state; Hunter's Mark
  rides on P4's per-enemy hit memory, Fragmentation on P3's Cluster Bomb
  child-bomb code. They are not in the catalog so they are never offered.
- Weak Point is a damage bonus against wounded targets rather than the
  design's "crit against enemies damaged by another weapon"; the
  another-weapon part is P4's synergy memory.
- `data/blessings.json` is emitted one effect per line by a scratch
  formatter; keep that shape when editing.

**Next.** P3 -- Forging (below).

---

## P3 — Forging — DONE (2026-09-10)

**What was done.**

- `data/forges.json`: the design's twelve Forgings, two per weapon, none for
  summons. Each is `overrides` (merged over the base weapon definition;
  every Forging renames the weapon, so the HUD reads "Whirlwind Lv3") plus
  `effects` keys. `combat/weapons/forge.py` loads and validates them
  (overridable keys, known effect keys, no summons, no `class` change),
  applies them (`apply_forge`: merge, effects, `Weapon.forge`, orbiters
  dropped, `__post_init__` re-run) and answers eligibility
  (`forge_eligible`: unforged, not a summon, `forge_requires_levels` = 2
  blessing levels from `data/offering.json`).
- **Behaviours** with code: Twin Daggers (two cones at ±22°), Earthshaker
  (a shockwave `blast` past the impact at half damage), Meteor Hammer (a
  hero-owned crater `Hazard` -- `Hazard.owner`, ticks as hidden one-frame
  projectiles through the resolver, the hero never hurt), Cluster Bomb
  (`scatter_bomblets`: three `cluster`-tagged bomblets that never scatter
  again), Minefield (`Projectile.mine` / `arm_delay`; `trip_mine` detonates
  on enemy overlap; 25 s lifetime). The rest are overrides only: Whirlwind
  (0.24 s full circle at 6), Greatsword, Fan of Blades (category flips to
  projectile, four thrown blades, still the melee slot), Multishot,
  Ballista, Arcane Storm (special flips to orbit, four motes), Arcane Lance.
- **Delivery.** `locations.use_forge`: the first eligible weapon's two
  Forgings in the level-up overlay (`LevelUpState` gained `title` and
  `cancelable`; ESC walks away), one weapon at a time, never consumed; with
  nothing eligible a `PlayingState.notice` states the requirement ("needs
  2 more"). The offering (`offer.forge_offers`) adds `forge:` cards at kind
  weight 8 × rarity 0.08 for eligible weapons; shrines never offer one.
- **Post-Forge blessings**: 13 in the catalog with `requires.forge`
  (validated: the forge exists and belongs to the blessing's weapon):
  Dual Wield / Cross Cut (Twin Daggers, design §13), Cyclone, Cleaver,
  Aftershock, Crater, More Blades, Wide Volley, Siege Bolt, Tempest, Impale,
  Bomblets, Dense Field. `Weapon.effect(key)` = `effects + bonus`, so a
  bonus under a Forge key grows it.
- **Looks.** `Weapon.visual_id` (the Forge id) travels as `visual=` on every
  spawn; `_resolve_visual` uses the Forge's `weapon_visuals.json` entry when
  one exists (Fan of Blades, Ballista, Arcane Storm, Arcane Lance) and the
  weapon's otherwise. A `hidden` projectile style for hazard ticks.

**Verification.**

- New: `tests/combat/test_forge.py` (33: data, merge, exclusivity,
  eligibility, every behaviour on fakes, crater ticks hurt enemies not the
  hero, bomblets once, mines arm and trip, visual fallback),
  `tests/progression/test_forge_offers.py` (12: cards only at two levels,
  rarity / weight, never at shrines, gone once forged, rare in 400 rolls,
  post-Forge gating and catalog validation). `test_interactables` gained
  the Forge flow through a real run (message with nothing eligible; two
  cards, ESC cancels, key 1 forges, "already forged" afterwards).
- `tests/combat tests/progression tests/characters`: **386 passed**.
  `tests/world/test_interactables tests/core tests/rendering/test_projectiles
  tests/rendering/test_level_up`: 143 passed, 1 skipped, one seed-dependent
  flake (`test_stop_attacking_silences_the_hero_weapons`, green on rerun,
  also green before this phase).
- Frames captured and sent: the Forge panel ("The Forge - reforge the
  Sword", two FORGE cards, the ESC hint), Whirlwind's full circle,
  Earthshaker's shockwave disc, the Meteor Hammer crater ring, Cluster
  Bomb's bomblets.

**Deferred / notes.**

- The Forge shows one weapon at a time (the first eligible in slot order);
  a weapon picker would need a wider panel than three cards.
- Whirlwind still obeys the reach gate (it spins only with a foe inside
  its ring) and the manual aim (a click points the circle, which is moot).
- Fan of Blades keeps the melee slot and the melee damage blessing, by
  design (§20: the slot is the weapon's, not the attack's).
- The user's own `bomb` projectile style (`projectiles/bomb.py`, added
  outside this work) is registered alongside `blast` and `hidden`.

**Next.** P4 -- synergies (below).

---

## P4 — Synergies — DONE (2026-09-10)

**What was done.**

- `combat/synergy.py`: the hit memory (`record_hit` -> `enemy.recent_hits`
  time per weapon + `hit_streak` per weapon, streak kept only while hits
  land inside the window), `hit_within`, the Rod's `mark` status
  (`combat/status.py` family `mark`, applied by `remember_hit` when the
  firing weapon's data says `mark_on_hit`; `data/weapons.json` sets it on
  the Rod, so Arcane Storm / Lance keep marking), `synergy_multiplier`, and
  the Crowd Cleaner `pull`. One window, `config.SYNERGY_WINDOW_S = 1.5`.
- Resolver hooks (`game/states/playing/combat.py`): `damage_multiplier`
  now also multiplies by the synergy factor; `remember_hit` runs right after
  the damage so this hit's own record never feeds its own multiplier;
  `crowd_cleaner` runs after the weight knockback. `Enemy` and `Boss` carry
  the two dicts; the render tint table knows `mark`.
- Catalog (`data/blessings.json`, 69 entries now): the six explicit pairs of
  design §10 as rare synergy blessings on the benefiting weapon, gated by
  `requires.weapons` on the partner -- Blood in the Water (Daggers after
  the Sword), Linebreaker (Bow after the Hammer), Demolition (Bomb after
  the Hammer), Marked Prey (Daggers vs the mark), Crossfire (Bow vs the
  mark *and* the Rod after the Bow, both halves on the Bow card), Crowd
  Cleaner (Sword hits drag toward the swing centre: the behavioural one).
  Plus Hunter's Mark for the Bow (deferred from P2): +X % per consecutive
  arrow into the same enemy inside the window, up to five stacks. Every
  timed card states "1.5 s"; Crowd Cleaner has no window and says none.

**Verification.**

- New: `tests/combat/test_synergy.py` (23: the window value, every timed
  card names it, memory and streak edges at 1.49 / 1.51 s, the mark's
  lifetime and that only the Rod marks, each pair inside vs outside the
  window, Crossfire both halves, synergy stacking with the P2 conditional
  multipliers, Hunter's Mark ramp / cap / reset, the pull's direction),
  `tests/progression/test_synergy_offers.py` (5: the six pairs, both
  weapons required, applies to the owning weapon, Hunter's Mark needs only
  the Bow, unknown partner rejected).
- `tests/combat tests/progression tests/characters`: **414 passed**.
  `tests/core tests/rendering tests/systems tests/ai tests/spawn`: 817
  passed, 1 skipped, one failure in `test_loading::test_the_view_is_warmed`
  (see the note below). Headless smoke: all nine weapons deal damage in a
  real run with the new hooks; Bomb and Hammer stun as before.
- No frames this phase: the synergies are damage arithmetic and a pull,
  nothing a still frame shows.

**Deferred / notes.**

- Weak Point stays "against wounded targets"; the design's "damaged by
  another weapon" reading is one `syn_after_*` key away if wanted.
- Flurry (Daggers), Echo (Rod), Sticky Bomb and Fragmentation (Bomb) remain
  out of the catalog (delayed-fire / per-projectile state).
- The mark only shows on screen as a status ring in the primitive fallback
  or with `config.SHOW_ENEMY_STATE_RINGS`; a sprite overlay is P5 art.

**Next.** P5 -- heroes, persistence and presentation (below).

---

## P5 — Heroes, persistence and presentation — DONE (2026-09-10)

**What was done.**

- **Save** (`game/save.py`, version 2): `SaveData.heroes[cid] = {cleared,
  main_weapon}` with `hero_cleared`, `mark_cleared`, `main_weapon` (only
  once cleared) and `set_main_weapon`; `_coerce` tolerates a version-1 file
  and junk entries. `Game._on_run_ended` marks the hero cleared on a
  victory (never on a defeat or a dev run); the run summary now carries
  `character_id`.
- **Run start**: `PlayingState._main_weapon_for` -- the chosen weapon from
  the `main_weapon` kwarg (through `LoadingState`) or the save, only when
  cleared, only a non-summon that exists; else the data's default.
- **Hero select**: Q / E and two click targets on the selected card cycle
  the six weapons once the hero has cleared the boss ("Main weapon:  <
  Hammer  >"); a locked hero shows "Starts with: ..." and cannot cycle; the
  hint line names the keys only when unlocked. Begin stores the choice in
  the save (not in a dev run) and passes it to the run. The choice is per
  hero.
- **Animation**: `Player._attack_cycle` advances on each fresh attack
  (`trigger_attack_anim` when the previous swing has played out);
  `_hero_anim_name` alternates `attack` / `attack2` when the rig has the
  second sheet and plays `guard` while `bulwark_active` and standing still,
  with hurt / death / walk / attack taking precedence. `hero_aegis` gained
  `attack2` (4 frames, 16 fps) and `guard` (6 frames, 10 fps, loop) from the
  user's sheets; Kestrel and Nihil have no second attack or guard sheets
  yet, so the rule is a no-op for them.
- Docs: `combat_calculations.md` (a map of the rebuilt layer at the top and
  the P5 bullet), the plan marked complete.

**Verification.**

- New: `tests/core/test_hero_unlock.py` (10: victory clears and persists,
  defeat / dev do not, the summary names the hero, the run's first weapon
  by default / saved choice / summon or unknown fallback, the select screen
  locked vs cleared, Q / E / arrows, Begin remembers and the run uses it,
  per-hero choice), `tests/characters/test_hero_anim.py` (9: the alternation,
  a rig without a second sheet, the cycle advancing once per fresh attack,
  the guard and what beats it, the rig data and that the sheets exist with
  matching frame counts), `HeroStateTests` in `test_save.py` (5).
- `tests/core tests/combat tests/progression tests/characters`: **538
  passed**. `tests/rendering tests/systems tests/ai tests/spawn
  tests/world/test_interactables`: 739 passed, 2 skipped.
- Frames captured and sent: the hero select with Aegis unlocked and
  "Main weapon: < Hammer >" on the card, and Aegis in the guard pose with
  Bulwark up; the second attack sheet is asserted by the animation test.

**Deferred / notes.**

- Weapon art for the six (a dagger, a rod, a bomb sprite, a sword swing
  beyond the slash rig) and an on-screen mark overlay stay open: no assets.
- Kestrel's and Nihil's second attack and guard sheets are the user's to
  add; the rig data and the rule are ready for them.
- The character-select preview still cycles idle / walk / attack; showing
  the chosen weapon's art there needs the art above.

**Done.** Every phase of `weapon_system_plan.md` is complete.

---

## Change request 1 — the Hammer swings before it lands (2026-09-10)

**Requirement (owner, revised the same day).** The Hammer no longer hits the
instant it fires:

1. A **swing time** before the blow connects, default **1.2 s**. **Haste**
   (attack speed) shortens the swing; cooldown reductions (Quick Cast,
   Rapid-style blessings) shorten the cooldown, not the swing.
2. During the swing the **effective range indicator** is drawn faded but
   noticeable, and **darkens** as the swing completes.
3. The impact area is a **circle, not a cone**, with a reach roughly the
   cone's. Proposed (awaiting the owner's yes): the circle is centred
   **40 px ahead** of the hero along the swing direction with a **radius of
   52 px** -- its far edge sits 92 px out, next to the old cone's 84, and its
   area (~8 500 px²) matches the old 140° sector's (~8 600 px²). The impact
   sheet's 80 x 80 frame scales to that circle. A circle *around* the hero
   of the old reach (84) would cover 2.6 x the area and was not proposed.
4. When the swing completes, the impact plays
   `assets/effects/weapons/hammer/hammer_impact.png` (400 x 80: five
   80 x 80 frames) at the circle's centre.
5. Hammer damage is a fixed **25**.

**Understanding (confirmed).**

- The swing is a telegraph: the direction -- and so the circle's centre --
  locks when the swing starts (auto-aim at the nearest in reach, or the
  manual aim); the circle moves with the hero; the blow lands where the
  circle is when the timer ends. Enemies that leave it are missed, enemies
  that enter it are hit.
- The cooldown starts when the blow lands: one cycle is swing + cooldown.
- The hero's attack animation plays at the impact.
- Earthshaker's shockwave and the Meteor Hammer's crater land with the
  blow, at the circle's centre.
- `swing_time`, `impact_offset` and the radius (`area`) are Hammer data
  fields; `area` stays the field the Heavy Impact blessing grows.

**Todo.**

- [x] `data/weapons.json`: Hammer `special_effect: "slam"`, `swing_time`
      1.2, `impact_offset` 40, `area` 52 (the radius), `damage` 25; drop
      `cone_half_angle`. `weapon_sprites.json`: the `hammer_impact` rig
      (five 80 x 80 frames, one-shot). Forge overrides checked (Earthshaker
      / Meteor Hammer keep the slam).
- [x] `combat/weapons/core.py` (+ a `slam.py` module): the `slam` special
      -- a pending swing (`_swing_t`, `_swing_dir`) started where the
      weapon used to fire, timed by `swing_time / attack_speed_multiplier`;
      at completion a stationary circular hit at `origin + dir *
      impact_offset` with radius `area`, then the cooldown. Melee reach
      for a slam = offset + radius. Manual aim locks the direction at the
      start. The Forge extras (shockwave, crater) spawn at the impact.
- [x] Rendering: a new module drawing the pending circle each frame with
      alpha ramping faint -> dark over the swing, and the impact rig at the
      centre for its five frames.
- [x] Tests (`tests/combat/test_hammer_swing.py`): no hit before the timer,
      one circular hit at completion at the locked centre, Haste shortens
      the swing and not the cooldown, cooldown reductions the reverse,
      cooldown restarts at impact, manual aim locks, forged variants swing,
      reach = offset + radius, the indicator alpha at 0 / 50 / 100 %, the
      impact visual's lifetime; damage 25 pinned in `test_weapon_classes`.
- [x] Journal + `combat_calculations.md` note; a frame mid-swing and one of
      the impact.

**Done (2026-09-10).**

- `combat/weapons/slam.py`: `begin_swing` (locks the direction from the
  same aim pick as a shot; swing = `swing_time / attack_speed_multiplier`),
  `land` (the circular hit at `origin + dir * impact_offset`, radius `area`,
  drawn `hidden`, `no_block`; the Forge shockwave / crater at the same
  centre; `spawn_impact` for the sheet), `reach` (offset + radius).
  `core.py`: the `slam` special, `_update_slam` (swing countdown -> land ->
  cooldown; manual aim / auto-attack gate the *start*), `_pick_aim` split
  out of `_fire`, `_cooldown` skips the attack-speed division for a slam,
  `swing_progress` / `slam_centre` for the renderer.
- `game/states/playing/slam_fx.py`: `indicator_alpha` (a straight ramp over
  `config.SLAM_INDICATOR_ALPHA = (45, 170)`), the pending circle drawn as a
  flat effect after the hazards, the impact sheet (`hammer_impact`, five
  80 x 80 frames at 15 fps, scaled to the circle) drawn with the explosions.
- Data: Hammer `slam`, `swing_time 1.2`, `impact_offset 40`, `area 52`,
  `damage 25`, `impact_rig`; the rig in `weapon_sprites.json`; the Hammer
  visual keeps only its colour (the indicator's). Forge overrides may name
  the new fields.
- Tests: `test_hammer_swing.py` (19: data and the sheet's size, reach,
  nothing before the timer, one blow at the locked centre with the stun
  fields, the direction locks while the circle travels with the hero, the
  cooldown from the impact, manual aim starts the swing on an empty ring,
  auto-attack off holds it, no target no swing, Haste vs cooldown
  reductions each on their own timer, Earthshaker / Meteor Hammer land
  with the blow, the alpha ramp, the impact request, `pending_swings`, the
  visual's five-frame life). The older instant-cone expectations in
  `test_stun`, `test_weapon_classes`, `test_forge`, `test_weapon_effects`
  and `test_weapons_special` moved onto the swing.
- `tests/combat tests/progression tests/characters`: **443 passed**;
  `tests/core tests/rendering tests/systems tests/ai tests/spawn
  tests/world/test_interactables`: 854 passed, 2 skipped. Headless smoke
  green (the forced-stun check now outlasts the swing).
- Frames sent: the circle at 10 % and 90 % of the swing (faint -> dark) and
  the impact sheet with the 25 landing on a tank.
- **Anchor fix (owner, same day).** The sheet's art sits low in its 80 x 80
  cell, so the splash first read below the circle's centre. The rig now
  carries `content [2, 14, 75, 66]` -- the art's bounding box over all five
  frames, measured -- with the anchor at that box's centre, and
  `slam_fx.impact_size` scales the cropped frame to the circle's diameter
  keeping the crop's aspect; the frame is blitted centred, so the splash
  centres on the blow. Two tests pin the crop against the sheet and the
  drawn size.
- **Lift (owner, same day): "raise the sprite some 5 pixels."** The rig's
  anchor moved 4 crop px below the crop's centre (`[37, 37]`) and
  `slam_fx.impact_topleft` now honours the anchor the way the character
  rigs do (scaled with the frame), so the splash draws about 5.5 screen px
  above the blow at the circle's scale. A test pins the lift at two zooms.
- The owner tuned the blow's radius from the agreed 52 to **42** in
  `data/weapons.json` (confirmed intended); the tests read the radius from
  the data.
- **Size (owner, same day): "increase the sprite by about 25 %."** The rig's
  `over_circle: 1.25` makes the frame a quarter wider than the blow's
  diameter (`slam_fx.impact_size`); the lift scales with it (about 5.6 px at
  radius 42, zoom 1).
- **Lift again (owner): "5 px more."** Anchor `[37, 41]` -- 8 crop px below
  the centre, about 11 screen px above the blow at radius 42, zoom 1.
