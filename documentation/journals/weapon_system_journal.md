# Six-weapon system — execution journal

Progress log for `documentation/plans/weapon_system_plan.md`. One section per
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

---

## Change request 2 — weapon effect sheets moved; new Sword slashes (2026-09-10)

**Requirement (owner).** The weapon effect sheets now live per weapon under
`assets/effects/weapons/<weapon>/` (`sword/`, `magic_rod/`, `hammer/`) and
the bomb art under `assets/projectiles/bomb/`. Four rigs point at the old
paths and no longer load: `arcane_circle`, `thunder_ball`, `thunder_aura`
(now `magic_rod/`) and `soul_slash` (`circle_cuts.png`, now `sword/`).

The Sword's default slash changes to two strips of
`assets/effects/weapons/sword/Combat-Sheet.png` (a 10 x 29 grid of 64 px
cells): the **second strip** for a top-to-bottom swing, **flipped
vertically** so it reads that way, and the **third strip** for a
bottom-to-top swing. Both are the Sword's defaults. The Magic Rod's effects
are to be rewired to the moved sheets.

**Reading to confirm.** Strip 2 = row index 1 (4 frames: the plain grey
crescent); strip 3 = row index 2 (5 frames: the wedge with cyan sparks).
The two swings alternate with the hero's attack sheets: swing 1 top-to-
bottom (strip 2, flipped), swing 2 bottom-to-top (strip 3), swing 3 back.

**Todo.**

- [x] Repoint the four rigs in `data/weapon_sprites.json` to the new
      folders; add a loader test that every rig's sheet exists on disk so a
      move can never silently blank an effect again.
- [x] `game/assets.py`: a `flip_v` option on an anim spec (the loader only
      flips horizontally today), applied at slice time.
- [x] Two Sword rigs from `Combat-Sheet.png`: `sword_slash_down` (row 1,
      4 frames, `flip_v`) and `sword_slash_up` (row 2, 5 frames), one-shot,
      sized to the swing.
- [x] `projectiles/cone.py`: the slash rig per swing -- the cone spawn
      carries the swing's parity (`Weapon._shots`) in its `fx`, the cone
      style picks down / up from it; `circle_cuts` stays only as the fallback
      when a rig is absent. Whirlwind / Greatsword follow the same rule
      unless told otherwise.
- [x] Magic Rod: `arcane_circle` from `magic_rod/`; `thunder_ball` /
      `thunder_aura` repointed and kept registered (the `thunder` style)
      for a Rod Forge's look if wanted.
- [x] Tests (rigs resolve, `flip_v` flips, the cone picks the strip by
      parity, the Sword swings alternate in a run); journal; a frame of each
      swing.

**Done (2026-09-10).**

- `data/weapon_sprites.json`: `soul_slash` -> `sword/circle_cuts.png`,
  `arcane_circle` / `thunder_ball` / `thunder_aura` -> `magic_rod/`; two new
  rigs `sword_slash_down` (Combat-Sheet row index 1, 4 frames, 30 fps,
  `flip_v`) and `sword_slash_up` (row index 2, 5 frames, 36 fps), one-shot,
  72 px. `game/assets.py`: an anim's `flip_v` flips each frame vertically
  at slice time. `data/weapon_visuals.json`: the Sword's
  `fx.slash = ["sword_slash_down", "sword_slash_up"]`.
- `entities/projectile.py` / `combat/weapons/core.py`: a cone spawn carries
  `swing` (the attack's ordinal, `Weapon._shots`). `projectiles/cone.py`:
  `slash_rig(p)` picks from the list by that ordinal (1 -> down, 2 -> up,
  3 -> down ...), `true` keeps the old rig, `false` draws the sector alone;
  a one-shot rig plays along the hit's `age` instead of the run clock. The
  Whirlwind / Greatsword have no visual entry of their own, so they inherit
  the alternation. The Rod keeps its arcane look on the moved sheet; the
  thunder rigs stay registered for a Forge look.
- Tests: `tests/rendering/test_weapon_rigs.py` (12: every rig's sheet on
  disk, the moved sheets in their folders, the two strips' rows / frames /
  flip, whole-frame flip equality, the swings fit the hit's lifetime, the
  rig choice by ordinal and the legacy paths, the forged Swords inherit, the
  ordinal on each spawn, the cone draw asking the right rig by age).
- **Owner retuning found on the way** (`data/weapons.json`, respected, the
  tests now read these from the data): Sword cooldown 0.85 -> 1.2 and area
  74 -> 32; Hammer swing 1.2 -> 0.8 s, cooldown 1.7 -> 1.5, radius 42 -> 32.
  Every test that assumed the old Sword reach moved its target inside 32 px.
- `tests/combat tests/progression tests/characters` + the rig / projectile
  suites: 479 passed. Frames sent: swing 1 (the grey crescent, strip 2
  flipped) and swing 2 (the cyan-spark wedge, strip 3) on a tank.
- **Reach gate fix (found by the retuning).** Two dev-mode tests stand a
  tank 22-30 px from the hero and expect the Sword to hit it; with a 32 px
  swing the gate never fired because `_within_reach` measured the enemy's
  *centre* while the hit test overlaps bodies. The gate now counts the
  body (centre distance minus the enemy's radius; a stand-in with no radius
  keeps its centre), so what the arc can hit is what triggers the swing.
  Three tests in `test_weapons_reach.py`; the wide suites are green again
  (core + rendering 573, the rest as before).
- **Separate sheets (owner, same day).** The two effects were cut out of
  `Combat-Sheet.png` into their own files: `slash_down.png` (strip 2, 4
  frames, the vertical flip baked in) and `slash_up.png` (strip 3, 5 frames,
  as authored -- its first cell is blank and kept). The rigs
  `sword_slash_down` / `sword_slash_up` now load those files with no
  `row` / `flip_v`; the loader's `flip_v` stays for a sheet authored the
  other way up (a test proves it still flips). Rig tests updated: each sheet
  is compared frame-for-frame against the strip it came from.
- **Slash-up changed (owner, same day):** `slash_up.png` is now row 27 of
  the combat sheet (third from the bottom, the tan crescent, 6 frames, as
  authored); the rig plays it at 44 fps over the 0.14 s hit.
- **One swing, both strips, 50 % bigger (owner, same day).** Both Sword
  rigs scale 72 -> 108. The Sword's visual is now `slash_mode: "sequence"`:
  one attack plays the down strip and then the up strip. Together they run
  about 0.27 s against a 0.14 s hit, so the swing is its own timed visual --
  `game/states/playing/slash_fx.py`, queued by `_spawn_projectile` for a
  sequence weapon's cone, updated and drawn with the Hammer impacts; the
  cone style draws no slash for a sequence weapon. A list without the mode
  still alternates by swing (kept for other weapons); the Daggers' single
  strip is unchanged.
- **-10 % (owner, same day):** both Sword rigs 108 -> 97 px. Verified on
  request: the Sword's `area` does *not* drive its sprite size -- the Sword
  has no `slash_size` factor, so the rigs' fixed `scale` is used at every
  radius (probe: 16 / 32 / 64 / 128 -> 97 each). The Daggers do follow the
  area (`slash_size` 0.8: radius 23 / 46 / 92 -> 37 / 74 / 147).
- **Follows the area (owner, same day):** the Sword's visual gained
  `slash_size: 1.5` -- 1.5 x the cone's diameter, 96 px at reach 32, so
  area blessings and Forgings (Greatsword 112, Whirlwind 70) size the
  swing with the hit; the rigs' fixed 97 px `scale` stays as the fallback
  for a visual without the factor.

## Change request 3 — weapon grants come alone, no bundle (2026-09-10)

**Requirement (owner).** A weapon grant card offers **only the weapon**. The
level-I blessing that used to ride along ("Comes with Vitality I") goes.
Everything else about grants stays: they appear at random while the run
still has open weapon slots (three weapons, one summon), share the stat
weight (`kind_weights.grant`), summons at the summon factor, and stop once
the slots are full. This supersedes design decision 7 (§22) and the grant
paragraph in §21.

**Todo -- DONE (owner's go, same day).**

- [x] `progression/blessings/offer.py`: `grant_offers` builds the card from
  the weapon alone -- no bundle roll, no "Comes with ..." on the
  description, `_apply` only appends the `Weapon`. `bundle_candidates` is
  removed with its export. The `rng` parameter stays on `grant_offers` so
  the offer roll's signature (and the callers in `offer_choices`) is
  unchanged.
- [x] `progression/upgrades.py`: drop the `bundle` field from `Upgrade`
  (grep: nothing outside `offer.py` and its tests reads it).
- [x] `progression/blessings/catalog.py` + `data/offering.json`: remove
  `grant_bundle_level` from `OfferingRules` and the JSON (the rule has no
  other reader).
- [x] Tests, `tests/progression/test_blessings.py::GrantTests`: replace the
  three bundle tests with one asserting a grant adds the weapon and
  changes no blessing level, and that the description carries no
  "Comes with"; keep the slot / summon gating tests as they are. Re-run
  `tests/progression tests/combat tests/characters` and the rendering
  level-up suite (the card text is what changes on screen).
- [x] Docs: `six_weapon_system_design.md` §21 "Weapon grants" paragraph and
  §22 decision 7 rewritten to "weapon only"; `documentation/plans/weapon_system_plan.md`
  P2 test line ("grant bundles exactly one level-I blessing") amended;
  this entry closed with the evidence. Memory note updated.
- [x] Screenshot: a level-up frame with a grant card in the roll (the
  scratchpad capture forces `grant:bow` into the choices).

**Evidence.** `grant_offers` builds the card from the weapon alone; the
`bundle` field, `bundle_candidates` and `grant_bundle_level` are gone from
code and `data/offering.json`. Two grant tests replace the three bundle
tests (the weapon is added, no blessing level changes, no "Comes with",
the card is the same whatever the RNG). Suites: progression + combat +
characters + the level-up rendering = 466 passed. Design §21 / §22-7 and
the plan's P2 line rewritten. Frame sent: an early offering with
"New: Ember Ring" reading only the summon's own description.

## Change request 4 — grant cards read "<Type> Weapon Grant" (2026-09-10)

**Requirement (owner).** The category line on a weapon-grant card no longer
names the weapon. Instead of `<weapon name> <slot> grant` ("Daggers Melee
Grant", "Ember Ring Summon Grant") it reads `<type> Weapon Grant`, the type
being the weapon's `class` from `data/weapons.json`: "Melee Weapon Grant",
"Ranged Weapon Grant", "Summon Weapon Grant". The card title ("New:
Daggers") still names the weapon. The owner confirmed summons follow the same
format ("Summon Weapon Grant").

**Todo -- DONE (owner's go, same day).**

- [x] `progression/blessings/offer.py` `grant_offers`: `tags=(d["class"],
  "weapon", "grant")` -- the panel capitalises each word, so no literal
  casing in the data or code.
- [x] Test in `tests/progression/test_blessings.py::GrantTests`: a Daggers
  grant carries `("melee", "weapon", "grant")`, a Bow grant "ranged", a
  summon grant "summon"; the rendered line is "Melee Weapon Grant".
- [x] Re-run progression + level-up rendering suites; capture an early
  offering with a grant card; log the evidence here.

**Evidence.** `grant_offers` tags a grant `(class, "weapon", "grant")`;
`GrantTests.test_a_grant_is_tagged_by_class_not_by_name` pins the three
classes and the rendered line. Progression + level-up rendering: 115
passed. Frame sent: "New: Daggers" over "Melee Weapon Grant" beside "New:
Ember Ring" over "Summon Weapon Grant".

## Change request 5 — taller upgrade cards (2026-09-11) — DONE (option B)

**Requirement (owner).** Review how the upgrade cards are drawn and consider
making them **50 px taller**. Reviewed below; the owner then chose **option B**
— the extra 50 px, with the description centred rather than pinned.

**How they are drawn today.** `ui/level_up.py`. Three cards, 340 wide, 40 apart,
each the pack's `btn_*_panel` art through `ui.widgets.draw_button(shape="panel")`.
Two constants carry the height: `_CARD_TOP_H = 200` fixes the top edge at
`h // 2 - 100`, and `_CARD_H = 245` is the real height, so every past growth
(200 -> 215 -> 245) went **downward** and the top edge never moved. Content is
anchored to both ends: the `#n` badge (`y + 10`), rarity (`y + 14`), title
(`y + 46`) and the wrapped description (`y + 92`, 24 px a line) hang off the top;
the category line hangs off the bottom at `y + card_h - 39`, and the keyboard
hint sits at `y + card_h + 60`. So raising `_CARD_H` moves the category line and
the hint down and opens space **between the description and the category line** —
which is exactly where more room is wanted.

**What the review found.**

- *The art takes it cleanly.* The panel is a 192x192 nine-slice, so a taller
  card stretches the middle band and leaves the 64 px bevels and corners at
  native size. No distortion, no new asset.
- *Both display profiles have room.* At 1600x900 the card would run 350->645
  with the hint at 705 (195 px spare); on the 1280x720 web profile 260->555
  with the hint at 615 (105 px spare). `apply_web_profile` needs no change.
- *Nothing clips today, but the margin is zero.* The card fits exactly **four**
  description lines before the category line; at 295 it would fit **six**.
  Measured over all 345 rendered blessing descriptions (every blessing at every
  level, wrapped at 302 px in `fonts.body(18)`): 195 are one line, 121 two,
  24 three, and 5 are four — all five being `bow_crossfire` at Lv1-5, which uses
  the last available line with nothing to spare. One more word in that string,
  or one more blessing written like it, and the text collides with the category
  line.
- *The cost is emptiness.* 316 of 345 descriptions are one or two lines, and the
  card already shows a visible dead band between the description and the
  category line. Adding 50 px to a fixed height grows that band from roughly
  90 px to roughly 140 px on the great majority of cards. The before/after
  captures show this plainly.
- *Test impact is essentially nil* for a constant-only change.
  `test_cards_grew_downwards_only` reads `_CARD_H` rather than hard-coding it,
  and its `r.bottom + 60 + 20 < h` guard still holds on both profiles
  (725 < 900, 635 < 720). `CategoryLineTests` asserts the source text
  `"y + card_h - 39 + dy"`, which a height change does not touch.

**The question put to the owner, and the answer.** The headroom is real but
rare; the emptiness would be constant. Three ways to spend the 50 px were
offered — **the owner chose B**:

- **A — straight +50.** `_CARD_H = 295`, nothing else. Buys two spare lines,
  accepts the larger dead band on ~92 % of cards.
- **B — +50 with the description centred (recommended).** Same height, but
  block the description vertically between the title and the category line
  instead of pinning it to `y + 92`. Short cards keep their text visually
  centred and do not read as bottom-empty; long ones get the full six lines.
- **C — fit the height to the tallest of the three on offer.** One height for
  all three cards each roll, sized to the longest description. Headroom only
  when a roll actually needs it, and no dead band otherwise — the most work,
  and the card size would change between level-ups.

**Todo — DONE (owner's go, same day).**

- [x] `ui/level_up.py`: `_CARD_H` 245 -> 295, still growing downward only
  (`_CARD_TOP_H` stays 200, so the top edge does not move). Four named
  constants replace the magic numbers the block needed — `_DESC_TOP` (92),
  `_DESC_LINE_H` (24), `_TAG_UP` (39) and `_DESC_GAP` (8).
- [x] The description block is centred in the band between the title and the
  category line: `band_bottom = y + card_h - _TAG_UP - hint.get_height() -
  _DESC_GAP`, and the block's top is `band_top + max(0, slack // 2)`. The
  `max(0, ...)` is the clamp — a block too tall for the band starts at the
  band's top rather than riding up over the title.
- [x] Band arithmetic checked at every line count: the band is 136 px, so one
  line sits at `y + 148`, two at `y + 136`, four (`bow_crossfire`, the
  catalog's worst case) at `y + 112`, and five still fit at `y + 100`. Six
  would eat the 8 px gap, which nothing in the catalog reaches.
- [x] `tests/rendering/test_level_up.py`: new `DescriptionCentringTests` — five
  tests driving the panel directly with synthetic choices (no run, no assets),
  pinning that a one-line description is centred rather than pinned, that
  `bow_crossfire` is centred too, that an overflowing description clamps to the
  band's top, that no description reaches the category line, and that the card
  is 295 with the top edge unmoved.
- [x] `test_card_text_colours` fixed: it hard-coded the old `y + 90` band as a
  fixed 50 px slice, which a centred block no longer lands in. It now derives
  the band the description may occupy from the same constants, and still stops
  short of the category line — which is drawn in the same dim colour and would
  otherwise satisfy the check on its own.
- [x] Tidy in passing: `test_level_up.py` had a stray
  `if __name__ == "__main__": unittest.main()` in the middle of the file, so
  running the module directly executed only its first class. Moved to the end.
- [x] The 1280x720 web profile fits: card 260->555, hint at 615, 105 px spare
  (1600x900 runs 350->645 with the hint at 705).
- [x] Screenshots sent: the before/after pair at 245 and 295, and a roll with a
  forced four-line `bow_crossfire` card beside one- and two-line cards.

**Evidence.** `_CARD_H = 295` with the description centred between the title
and the category line; the nine-slice panel art stretches its middle band so
the 64 px bevels are untouched. `tests/rendering/test_level_up.py` 23 passed
(18 existing plus the five new), `tests/rendering` 496 passed, and the `unit`
tier is unchanged at 10 s. Nothing in the catalog clips: of the 345 rendered
blessing descriptions, the longest is `bow_crossfire` at four lines and the
band holds five.

## Change request 6 — choose which weapon the Forge reforges (2026-09-12) — CONFIRMED, ready to build

**Requirement (owner).** The Forge upgrade flow picks the weapon for you. It
should let the player choose.

1. A **weapon list down the left** of the screen showing each weapon and its
   blessing count against the requirement. Weapons that meet the requirement
   are highlighted and selectable.
2. The **middle stays as it is** -- the same upgrade cards -- and re-rolls to
   the selected weapon's Forgings when the left-hand selection changes.

Reviewed below. The owner has since settled both open questions:
**option A** for the layout, and **2 or more** is the right threshold.
Nothing is coded yet.

**What happens today.** `game/states/playing/locations.py:102` `use_forge`:

    eligible = [w for w in ps.player.weapons if forge_eligible(w, need)]
    if not eligible:
        ps.notice(self.forge_requirements(need))
        return
    weapon = eligible[0]                     # <- no choice at all

It then builds `forge_offers_for(player, content, weapon)` and pushes
`LevelUpState` with those cards, `cancelable=True` and a Forge title. So the
overlay, the cards and the mouse handling are all reusable as they stand; what
is missing is a way to say *which* weapon before the cards are built.

`forge_eligible` (`combat/weapons/forge.py:111`) is three conditions -- not
already forged, not a summon, and `blessing_levels(weapon) >= required_levels`
-- and `blessing_levels` is `max(0, weapon.level - 1)`. `required_levels` is
`forge_requires_levels` in `data/offering.json`, currently **2**. The three
failure reasons are distinct, which is what the left rail can finally show:
today they all collapse into one `notice` line naming a single weapon.

### Proposed design

**The rail is a list of every non-summon weapon**, eligible or not, at most
three of them (`MAX_WEAPONS = 3`; the summon slot is excluded because a summon
can never be forged). Each row: the weapon's name, its blessing count against
the requirement (`3 / 2`), and a state --

| state | shown as |
|---|---|
| eligible | highlighted, selectable |
| not enough blessings | dimmed, "needs 1 more" |
| already forged | dimmed, names the Forge it became |

**Selection rebuilds the middle.** `LevelUpState.enter` gains an optional
`weapons=` list and an `offers_for=` callable; when they are present it draws
the rail and rebuilds `self.choices = offers_for(weapon)` whenever the
selection moves. With them absent the overlay behaves exactly as it does now,
so the level-up path is untouched.

**A new module** rather than more of `ui/level_up.py`: `ui/forge_rail.py`,
owning its own `HitMap` so the mouse works the same way the cards do.

**Input.** Up/Down (and W/S) move the weapon selection, Left/Right and 1/2/3
stay on the cards, ESC still leaves. Hover highlights and a click selects, per
the standing mouse rules; a click on an ineligible row does nothing.

### The one real obstacle: there is no room on the web build

The cards are 3 x 340 with two 40 px gaps = **1100 px**, centred:

| profile | screen | margin per side |
|---|---:|---:|
| desktop | 1600 | **250 px** |
| web (`apply_web_profile`) | 1280 | **90 px** |

A rail fits comfortably in 250 px and not at all in 90. Requirement 2 says the
middle does not move, which on the web profile leaves nowhere to put it. Three
ways out, and this is the decision that blocks the work:

- **A — narrow the cards when the rail is up.** 3 x 260 + gaps = 860, leaving
  210 px each side on web. The middle changes size, against the letter of
  requirement 2, but only on the Forge screen.
- **B — the rail overlays the dimmed backdrop.** The cards do not move on
  either profile; on web the rail sits over the darkened world at the screen
  edge, roughly 90-140 px wide, which is enough for a name and a count but not
  a comfortable one.
- **C — desktop only.** The rail appears at 1600; the web build keeps today's
  automatic first-eligible pick. Simplest, and leaves the web build with the
  behaviour being replaced because it is unsatisfying.

**Owner's decision: A.** The Forge screen is a different screen from the
level-up screen, and a slightly narrower card there is a smaller cost than a
cramped rail or a split behaviour between builds. So the cards drop to 260 wide
*only while the rail is up*; the level-up path keeps its 340 and must stay
pixel-identical, which `tests/rendering/test_level_up.py` already pins.

### Second question: the requirement wording

The requirement says weapons with "more than 2 upgrades" are selectable, but
the description of today's behaviour says "two or more", and the code is
`>= forge_requires_levels` with the value 2 in the data. **Owner's decision: 2 or more is correct** -- the code's existing
`>= forge_requires_levels` rule stands, and "more than 2" was loose phrasing.
No data change.

**Todo -- not started, pending the answers above.**

- [ ] `game/states/playing/locations.py` `use_forge`: stop at `eligible[0]`.
      Pass every non-summon weapon plus an `offers_for` callable into the
      overlay, and keep the existing `notice` for the case where *no* weapon
      qualifies.
- [ ] `game/states/level_up_state.py`: optional `weapons=` / `offers_for=`;
      rail selection state; Up/Down and the rail's mouse events; rebuild
      `self.choices` on change. Absent those arguments, behave exactly as now.
- [ ] `ui/forge_rail.py` (new): draw the rows, their counts and their states,
      into a `HitMap`. One module per concern, not more of `ui/level_up.py`.
- [ ] `ui/level_up.py`: accept a left inset so the cards lay out beside the
      rail (option A), leaving the no-rail path pixel-identical.
- [ ] A reason string per ineligible weapon, replacing the single
      `forge_requirements` line -- the rail can show all three states at once,
      which is the point of it.
- [ ] Tests, `unit` where possible: the rail lists non-summons only and marks
      each state; selecting a weapon swaps the cards to that weapon's Forgings;
      an ineligible row cannot be picked by key or click; the level-up path is
      unchanged when the new arguments are absent; ESC still leaves.
- [ ] `integration`: walking a real run into the village Forge with two
      eligible weapons picks the *second* one and forges it -- the case that is
      impossible today.
- [ ] Check both profiles: 1600 and the 1280 web profile, whichever layout
      option is chosen.
- [ ] Screenshot the Forge screen with the rail, and close this entry.
