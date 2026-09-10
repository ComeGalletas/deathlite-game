# Six-Weapon Survivors-Like Game Design

## 1. Design Goal

Create a small, expandable weapon system for a Vampire Survivors-like game.

The initial game should contain exactly **6 weapons**:

- 3 melee weapons
- 3 ranged weapons

A separate **Summons** category (§3.7) sits beside them: it holds the three
existing summon-like weapons, does not interact with the six weapons, and has its own
single slot per run.

A run holds at most **3 weapons** chosen from the six, in any mix of melee and
ranged (§20), so the choice of which three is itself a build decision.

The goal is not to maximize the number of weapons, but to make the six weapons interact meaningfully so that different combinations produce distinct builds and playstyles.

The system should be designed so that a future **elemental infusion/reaction system** can be added without replacing the current weapon architecture.

### Current scope

Focus ONLY on:

- Weapons
- Regular weapon upgrades
- Weapon interactions
- Weapon synergies
- Weapon Forging
- The transition from the current build (§19), heroes and starting weapons (§20), and stat blessings (§21)

Do **not** implement or design the elemental system yet.

Future elemental mechanics may allow any weapon to be infused with an element and allow upgrades to interact with elemental properties.

---

# 2. Core Design Philosophy

The system has three major progression layers:

1. **Regular Upgrades**
2. **Weapon Forging**
3. **Weapon Interactions / Synergies**

The fundamental distinction is:

> Regular upgrades make a weapon better.  
> Forging makes a weapon different.  
> Synergies make weapons better together.

Avoid designing the game as a collection of independent weapons with only increasing damage numbers.

Each weapon should have a distinct combat identity.

---

# 3. Six Initial Weapons

## 3.1 Sword

### Role

Reliable close-range crowd control.

### Identity

The Sword is the dependable weapon for surviving when enemies surround the player.

### Base behavior

- Sweeping melee attacks
- Wide attack arc
- Medium damage
- Fast-medium attack speed
- Moderate knockback
- Hits multiple enemies
- No targeting requirement

### Gameplay question

> What do I use when enemies get close?

### Possible regular upgrades

#### Sharpened Edge
Increase damage.

#### Wide Cleave
Increase attack width and/or number of enemies hit.

#### Heavy Blade
Reduce attack speed in exchange for increased damage and knockback.

#### Bloodletting
Killing enemies with Sword restores a small amount of health.

#### Critical Edge
Increase critical-hit chance or critical-hit damage.

### Possible Forgings

#### Whirlwind

Transforms the Sword into a rotating defensive weapon.

- Attacks continuously or repeatedly around the player.
- Strong against surrounding enemies.
- Less focused on individual targets.

Identity:

> Defensive AoE.

#### Greatsword

Transforms the Sword into a slow, powerful weapon.

- Much slower attacks
- Large attack area
- Very high damage
- Huge knockback
- High enemy penetration

Identity:

> Crowd breaker / heavy hitter.

---

# 3.2 Hammer

### Role

Burst damage and crowd disruption.

### Identity

The Hammer is slow but extremely impactful.

### Base behavior

- Heavy melee attack
- Large impact area
- High damage
- Slow attack speed
- Strong knockback
- Possible stun
- Excellent against groups

### Gameplay question

> How do I disrupt a dangerous crowd?

### Possible regular upgrades

#### Crushing Blow
Increase damage, especially against high-health enemies.

#### Titan's Grip
Increase knockback.

#### Staggering Strike
Increase stun chance/duration.

#### Heavy Impact
Increase area of effect.

#### Executioner
Increase damage against enemies below a health threshold.

### Possible Forgings

#### Earthshaker

Every Hammer attack creates a secondary shockwave.

Identity:

> Massive area control.

#### Meteor Hammer

The Hammer creates a lingering impact zone after striking.

- Enemies entering the area are damaged or disrupted.
- Strong battlefield control.
- Less dependent on directly hitting every enemy.

Identity:

> Area denial.

---

# 3.3 Daggers

### Role

Fast single-target damage.

### Identity

Daggers are fast, precise and aggressive.

### Base behavior

- Short-range melee attacks
- Very high attack speed
- Low individual damage
- Small attack area
- Excellent single-target DPS
- Weak crowd control

### Gameplay question

> How do I quickly eliminate a dangerous target?

### Possible regular upgrades

#### Sharpened Blades
Increase damage.

#### Quick Hands
Increase attack speed.

#### Extended Reach
Increase attack range.

#### Weak Point
Increase critical chance or damage against enemies already damaged by another weapon.

#### Flurry
Repeated attacks against the same enemy temporarily increase attack speed.

### Possible Forgings

#### Twin Daggers

The player attacks with two daggers simultaneously.

- Two attacks per attack cycle
- Each dagger deals less damage than the original dagger
- Slightly wider attack pattern
- Same general attack speed
- Potentially slightly reduced range

Identity:

> High sustained DPS with better multi-target coverage.

The important design principle is that Twin Daggers should not simply be "Dagger + 100% damage." It should change the attack behavior and introduce tradeoffs.

#### Fan of Blades

Daggers become a wider cone/area attack.

- Throws multiple daggers
- Wider coverage
- Lower precision
- Better against groups

Identity:

> Crowd-clearing assassin.

---

# 3.4 Bow

### Role

Long-range precision and line damage.

### Identity

The Bow attacks through lines of enemies and rewards positioning.

### Base behavior

- Long range
- Medium/high damage
- Medium attack speed
- Narrow attack path
- Piercing projectiles
- Strong against lines of enemies

### Gameplay question

> How do I destroy enemies from a distance?

### Possible regular upgrades

#### Piercing Arrow
Increase penetration.

#### Heavy Draw
Increase damage while reducing attack speed.

#### Rapid Draw
Increase attack speed.

#### Split Arrow
Projectile splits after hitting an enemy.

#### Hunter's Mark
Repeated attacks against the same enemy increase damage against that enemy.

### Possible Forgings

#### Multishot

Bow fires several arrows in a spread.

Identity:

> Crowd clearing and coverage.

#### Ballista

Bow becomes a slow, extremely powerful projectile.

- Very high damage
- Huge penetration
- Very long range
- Slow firing rate

Identity:

> Elite and boss killer.

These two Forgings should represent opposing build philosophies:

- Multishot = many targets
- Ballista = high-value targets

---

# 3.5 Magic Rod

### Role

Automatic targeting and consistent ranged pressure.

### Identity

The Rod is reliable and intelligent rather than necessarily having the highest damage.

### Base behavior

- Automatically targets nearby enemies
- Medium damage
- Medium range
- Low penetration
- Reliable targeting
- Does not require precise player positioning

### Targeting and manual aim (decided 2026-09-09)

The Rod behaves like the current Arcane Bolt / Thunder Orb: an auto-aimed
shot at the nearest enemy in reach. A manual aim does not give it a precise
direction; it gives a **rough area**: the shot goes to the closest enemy
inside the assist cone around the aim, and only flies straight along the aim
when that area is empty.

### Gameplay question

> How do I maintain pressure across the battlefield?

### Possible regular upgrades

#### Arcane Missiles
Increase projectile count.

#### Seeking
Improve projectile homing.

#### Chain
Projectile can jump to another enemy.

#### Overcharge
Every N attacks launches a powerful projectile.

#### Echo
A percentage of attacks repeat after a short delay.

### Possible Forgings

#### Arcane Storm

Creates a large amount of persistent projectile/area coverage around the player.

Identity:

> Battlefield coverage.

#### Arcane Lance

Transforms the Rod into a powerful focused attack.

- High single-target damage
- Strong against elites/bosses
- Less general battlefield coverage

Identity:

> Single-target ranged destruction.

---

# 3.6 Bomb

### Role

Delayed area damage and crowd clearing.

### Identity

The Bomb controls space rather than simply attacking individual enemies.

### Base behavior

- Projectile or thrown explosive
- Slow attack speed
- High AoE damage
- Delayed impact
- Knockback
- Strong against groups

### Gameplay question

> How do I erase a cluster of enemies?

### Possible regular upgrades

#### Bigger Explosion
Increase explosion radius.

#### Explosive Force
Increase damage.

#### Cluster Bomb
Increase secondary explosions.

#### Sticky Bomb
Bomb attaches to enemies before exploding.

#### Demolitionist
Increase damage against enemies affected by knockback/stun.

### Possible Forgings

#### Cluster Bomb

Primary explosion creates smaller secondary bombs.

Identity:

> Chain-reaction AoE.

#### Minefield

Bombs become area-denial tools.

- Leave mines behind or place mines in locations.
- Enemies trigger the mines.
- Creates persistent danger zones.

Identity:

> Battlefield control / area denial.

---

# 3.7 Summons (separate category)

Decided 2026-09-09.

Summons are a category of their own, beside the six weapons. Three weapons
already in the build move into it:

- **Grave Totem** -- plants a totem that fires bolts at nearby foes.
- **Spirit Wolf** -- a wolf that hunts and mauls the nearest foe.
- **Ember Ring** (added 2026-09-09) -- embers that orbit the hero and scorch
  whatever they touch. It is a summon by role: a persistent companion effect
  the hero does not aim.

Rules:

- A run keeps **one summon at most**. The summon has its own slot and does
  not count toward the three-weapon limit.
- Summons **do not interact with any other weapon**: no synergies, no
  Forgings, and no place in the "recently hit" rules.
- A summon is offered like a weapon grant (§21) while the summon slot is
  empty. Once taken, only its own upgrades can appear.
- Their upgrades are plain Power / Coverage blessings (damage, cooldown,
  count, lifetime); see §22 for what is still open.

---

# 4. Regular Upgrade System

Regular upgrades are the most common form of weapon progression. In the game
they are presented as **Weapon Blessings** (§21): the same cards, the same
level-up offering, gated on owning the weapon.

They should be:

- Frequent
- Levelable
- Incremental
- Repeatable
- Build-defining over time

A regular upgrade should usually have several levels.

Example:

## Quick Hands

- Level I: +8% attack speed
- Level II: +16%
- Level III: +25%
- Level IV: +35%
- Level V: +50%

The exact numbers are placeholders and should be balanced during gameplay testing.

---

# 5. Upgrade Categories

Regular upgrades should fall into four broad categories.

## 5.1 Power

Direct numerical improvements.

Examples:

- Damage
- Attack speed
- Projectile speed
- Critical chance
- Critical damage

These are simple and reliable.

---

## 5.2 Coverage

Increase how many enemies a weapon can affect.

Examples:

- Area
- Range
- Projectile count
- Penetration
- Attack width

---

## 5.3 Behavior

Small changes to how a weapon behaves.

Examples:

- Bounce
- Split
- Knockback
- Stun
- Targeting
- Pull
- Chain effects
- Attack duration

These should be more interesting than pure stat increases.

---

## 5.4 Synergy

Upgrades that become stronger because another weapon is owned.

Examples:

### Marked Prey

Daggers deal increased damage to enemies marked by the Magic Rod.

### Demolition Protocol

Bombs deal increased damage to enemies recently hit by Hammer.

### Crossfire

Bow and Rod attacks against the same enemy increase each other's effectiveness.

Synergy upgrades should encourage players to think about their entire build rather than individual weapons.

---

# 6. Upgrade Leveling

Regular upgrades can have multiple levels.

Example:

## Demolition Protocol

### Level I
+25% Bomb damage against enemies recently hit by Hammer.

### Level II
+40%.

### Level III
+55%.

### Level IV
+75%.

### Level V
+100%.

The fundamental mechanic remains the same.

The upgrade becomes stronger, but does not fundamentally transform.

This is a core distinction from Forging.

---

# 7. Weapon Forging

## Definition

Weapon Forging is the rare, high-impact upgrade system.

A Forge should:

- Be significantly rarer than regular upgrades.
- Permanently transform a weapon.
- Change its attack pattern or gameplay identity.
- Have a fixed effect.
- Generally not have normal upgrade levels.
- Create meaningful tradeoffs.
- Potentially change which regular upgrades are most valuable.

The player should feel:

> "My weapon just became something new."

rather than:

> "My weapon got another 20% damage."

## Where forging happens (decided 2026-09-09)

- **Requirements:** one Forge per weapon, the two options mutually
  exclusive, and the weapon must have taken at least two regular upgrade
  levels.
- **The Forge building.** Village islands carry a Forge (`forge.png`, one
  per village, the settlement is laid out around it). Interacting with it
  opens the Forge choice for every eligible owned weapon. If no weapon is
  eligible, the interaction shows a message stating the requirements
  ("<weapon> needs two upgrades before it can be forged") instead of
  silently doing nothing.
- **The level-up roll.** A Forge can also appear as a blessing at Forge
  rarity (§12, §21) once a weapon is eligible.

---

# 8. Forging Rules

## Rule 1: Forging changes behavior

Example:

Dagger → Twin Daggers

is good.

Dagger → +50% damage

is not a Forge.

---

## Rule 2: Forging should have tradeoffs

A Forge should not simply make the weapon universally better.

Example:

Twin Daggers:

- Two attacks
- Each dagger deals less damage
- Better coverage
- Potentially lower precision/range

This creates a new weapon identity rather than a direct upgrade.

---

## Rule 3: Forging should be relatively fixed

Regular upgrades:

> Level I → II → III → IV → V

Forging:

> Select Forge → weapon permanently changes.

The Forge itself does not need five levels.

---

## Rule 4: Forging can change the future upgrade pool

After a weapon is forged, certain upgrade options can become more relevant or new weapon-specific upgrades can appear.

Example:

Before Forge:

- Damage
- Attack speed
- Range
- Critical chance

After Twin Daggers:

- Dual Wield
- Cross Cut
- Rapid Pair
- Increased spread
- Synergy effects involving both daggers

This allows the Forge to act as a branching point in the build.

---

# 9. Weapon Interaction Philosophy

Weapons should not all have explicit pair-specific mechanics.

There are 15 possible pairs between six weapons.

Creating a unique mechanic for all 15 pairs would create unnecessary complexity.

Instead:

- Create a smaller number of strong, intentional synergies.
- Let the remaining weapons interact naturally through their combat behaviors.
- Add more synergies later if gameplay testing shows a combination needs more identity.

Initial target:

**Approximately 6 strong weapon synergies.**

---

# 10. Initial Weapon Synergies

**Timing (decided 2026-09-09).** Every "recently hit" and "marked" rule uses
one shared window of **1.5 seconds** after the hit. The window is stated in
the description of every synergy blessing ("...hit by the Hammer in the last
1.5 s"), so the player never has to guess it.

## Sword + Daggers: Blood in the Water

Sword damages groups.

Enemies recently hit by Sword become vulnerable to Daggers.

Possible effect:

> Daggers deal bonus damage against enemies recently hit by Sword.

Gameplay loop:

Sword → soften/expose enemies → Daggers finish them.

Identity:

> Crowd damage followed by execution.

---

## Hammer + Bow: Linebreaker

Hammer knocks enemies into more predictable positions.

Bow becomes more effective against enemies recently affected by Hammer's knockback.

Gameplay loop:

Hammer → reposition enemies → Bow attacks the resulting line.

Identity:

> Crowd disruption + ranged precision.

---

## Hammer + Bomb: Demolition

Hammer creates unstable/disrupted enemies.

Bomb deals bonus damage to those enemies.

Possible effect:

> Enemies recently hit by Hammer take increased Bomb damage.

Alternative higher-tier effect:

> Bomb explosions against Hammer-affected enemies create secondary explosions.

Identity:

> Impact + explosion.

---

## Rod + Daggers: Marked Prey

Rod marks targets.

Daggers deal bonus damage to marked targets.

Gameplay loop:

Rod → mark → Daggers prioritize/execute.

Identity:

> Target acquisition + assassination.

---

## Sword + Bomb: Crowd Cleaner

Sword influences enemy positioning while Bomb destroys clustered enemies.

Possible interaction:

> Sword attacks slightly pull or push enemies into tighter groups, improving Bomb effectiveness.

This can be a behavioral synergy rather than a direct special effect.

Identity:

> Grouping + AoE.

---

## Bow + Rod: Crossfire

Rod provides targeting/marking while Bow provides precision damage.

Possible interaction:

> Rod-marked targets become preferred Bow targets or take bonus Bow damage.

Identity:

> Intelligent targeting + precision.

---

# 11. Natural Synergy vs Explicit Synergy

There should be two kinds of interaction.

## Explicit synergy

The game directly recognizes a relationship.

Example:

> Hammer-affected enemies take +50% Bomb damage.

This should be used sparingly.

---

## Natural synergy

Two weapons work well together because their mechanics complement each other.

Example:

> Hammer knocks enemies into lines and Bow pierces lines.

No special rule is required.

This is important because it makes the game feel less like a spreadsheet of predefined combinations.

---

# 12. Upgrade Rarity

A possible rarity hierarchy:

## Common

Very frequent.

Examples:

- +Damage
- +Attack Speed
- +Range

## Uncommon

Less frequent.

Examples:

- +Projectile
- +Penetration
- +Area
- +Critical effects

## Rare

Build-defining.

Examples:

- Weapon behavior modifications
- Strong synergy upgrades
- Conditional effects

## Forge

Very rare.

Examples:

- Twin Daggers
- Greatsword
- Multishot
- Ballista
- Arcane Storm
- Minefield

The exact rarity and appearance frequency should be tuned through playtesting.

---

# 13. Post-Forge Upgrade Design

Forging should not stop normal weapon progression.

Instead:

1. Player acquires a weapon.
2. Player upgrades it normally.
3. Player eventually finds a Forge.
4. Weapon changes identity.
5. Regular upgrades continue.
6. New Forge-specific upgrade opportunities may appear.

Example:

## Dagger

Before Forge:

- Damage
- Attack speed
- Range
- Crit

After:

## Twin Daggers

Potential new upgrades:

### Dual Wield
Both daggers gain increased damage.

### Cross Cut
Increase spread between daggers.

### Rapid Pair
If both daggers hit the same enemy, trigger an additional effect.

### Perfect Pair
Hitting two different enemies in the same attack grants a temporary attack-speed bonus.

The Forge therefore creates a new mini-upgrade ecosystem.

---

# 14. Build Archetypes

The six weapons should naturally support different builds.

## High-Speed Build

Example:

- Twin Daggers
- Multishot Bow
- Arcane Storm

Identity:

> High attack frequency and projectile saturation.

---

## Heavy Build

Example:

- Greatsword
- Ballista
- Meteor Hammer

Identity:

> Slow attacks, huge damage, elite/boss killing.

---

## Defensive AoE Build

Example:

- Whirlwind
- Cluster Bomb
- Minefield

Identity:

> Area control and survival.

---

## Assassin Build

Example:

- Twin Daggers
- Arcane Lance
- Rod/Dagger synergy

Identity:

> Priority-target elimination.

---

## Crowd-Control Build

Example:

- Hammer
- Sword
- Bomb

Identity:

> Disrupt, group and destroy enemies.

These are examples, not fixed classes. Players should be able to create hybrid builds.

---

# 15. Core Design Rules

The following rules should guide future weapon and upgrade design.

### Rule A: Every weapon must have a unique combat question.

Do not add a weapon merely because it has different damage numbers.

---

### Rule B: Regular upgrades improve.

They should mostly make the weapon stronger, faster, wider, more reliable or more synergistic.

---

### Rule C: Forging transforms.

A Forge should change the weapon's attack pattern, behavior or strategic purpose.

---

### Rule D: Forging should involve tradeoffs.

A transformed weapon should be better at some things and worse at others.

---

### Rule E: Synergies should reward combinations.

Players should benefit from thinking about their complete loadout.

---

### Rule F: Avoid the 15-pair-combination trap.

Do not create a unique special interaction for every weapon pair.

Start with approximately six strong synergies.

---

### Rule G: Do not make every interaction explicit.

Some of the best combinations should emerge naturally from the weapons' behaviors.

---

### Rule H: Avoid pure numerical power creep.

A new upgrade should ideally introduce a decision, not simply make an old decision obsolete.

---

# 16. Future Elemental Expansion

The elemental system is intentionally OUTSIDE the current scope.

Future design should allow:

> Any weapon can potentially receive an elemental infusion.

For example:

Sword + Fire

Bow + Ice

Bomb + Lightning

etc.

Elemental upgrades can then interact with:

- Weapon type
- Forge type
- Existing weapon synergies
- Enemy states
- Other elemental effects

The future system should be layered on top of the existing weapon system rather than replacing it.

Conceptually:

Weapon
→ Forge
→ Elemental Infusion
→ Regular Upgrades
→ Synergies
→ Final Build

The elemental system should therefore remain independent enough that the six base weapons remain fun without it.

---

# 17. Final Design Model

The complete progression philosophy is:

```text
WEAPON
  |
  +-- Regular Upgrades
  |      |
  |      +-- Power
  |      +-- Coverage
  |      +-- Behavior
  |      +-- Synergy
  |
  +-- FORGING
  |      |
  |      +-- Major transformation
  |      +-- Fixed effect
  |      +-- Tradeoffs
  |      +-- New upgrade possibilities
  |
  +-- Weapon Interactions
         |
         +-- Explicit synergies
         +-- Natural synergies
```

### The three most important concepts

**Upgrade**

> "Make my weapon better."

**Forge**

> "Change what my weapon is."

**Synergy**

> "Make my weapons work better together."

The goal is for a player to look at an upgrade choice and think about their build, not simply choose the largest number.

---

# 18. Initial Prototype Scope

For the first playable version, implement/design only:

### Weapons
- Sword
- Hammer
- Daggers
- Bow
- Magic Rod
- Bomb

### Forgings
- Whirlwind
- Greatsword
- Earthshaker
- Meteor Hammer
- Twin Daggers
- Fan of Blades
- Multishot
- Ballista
- Arcane Storm
- Arcane Lance
- Cluster Bomb
- Minefield

### Initial synergy targets
- Sword + Daggers
- Hammer + Bow
- Hammer + Bomb
- Rod + Daggers
- Sword + Bomb
- Bow + Rod

### Summons (see §3.7)
- Grave Totem
- Spirit Wolf
- Ember Ring

### Heroes and progression (see §20 and §21)
- Three weapons per run plus one summon
- Aegis starts with the Sword, Kestrel with the Bow, Nihil with the Magic Rod
- The three hero traits, re-pointed at the new weapons
- Per-hero main-weapon selection, unlocked by clearing the boss, persisted in the save file
- Stat blessings replacing the elemental blessing families

### Excluded for now
- Elemental system
- Elemental reactions
- Elemental blessings (Ember / Tide / Storm / Grave) -- removed, not redesigned
- Large numbers of weapons
- Large numbers of Forgings
- Complex passive-item systems
- Unique mechanics for every weapon pair

The first objective is to determine whether the six weapons, their upgrade choices, Forgings and interactions create genuinely different and enjoyable builds before expanding the system.

---

# 19. Relationship to the Current Build

Decided 2026-09-07.

The build currently ships seven weapons: Arcane Bolt, Frost Shards, Thunder
Orb, Ember Ring, Soul Scythe, Grave Totem and Spirit Wolf.

## What stays

- **Sword** and **Bow**. The hero sprites already carry them. The existing
  melee arc (Soul Scythe's cone) becomes the Sword definition and the existing
  piercing shot (Frost Shards) becomes the Bow definition. Their tuning is
  rewritten to §3.1 and §3.4; the code paths are kept.

## What goes

Every other weapon except the three summons is removed from `data/weapons.json`,
the weapon visuals and the hero starting weapons. The engine code behind them
is **not** deleted; it is repurposed for the six weapons and their Forgings:

| Current mechanic | Came from | Reused by |
|---|---|---|
| Auto-aimed straight shot | Arcane Bolt | Magic Rod base attack (with homing added) |
| Chain redirect on hit | Thunder Orb | Rod upgrade "Chain" |
| Orbiting persistent projectiles | Ember Ring | Ember Ring stays as a summon (§3.7); the orbit code is also reused by Whirlwind (Sword) and Arcane Storm (Rod) |
| Melee cone | Soul Scythe | Sword, Daggers, Hammer |
| Fan of piercing shots | Frost Shards | Bow, Multishot, Fan of Blades |
| Summons (totem, wolf) | Grave Totem, Spirit Wolf | Kept as the Summons category (§3.7); the placed-object logic is also a candidate for Minefield |
| Enemy-only ground hazards | enemy pools | Meteor Hammer, Minefield (need a hero-owned variant) |
| Explosions | exploder enemy, blessing procs | Bomb, Earthshaker, Cluster Bomb (must go through the normal damage pipeline) |

Blessing content tied to the removed weapons' elements goes with them (§21).

---

# 20. Heroes, Traits and Starting Weapons

## Starting weapons

| Hero | Starting weapon | Change |
|---|---|---|
| Aegis | Sword | Was Soul Scythe (same role) |
| Kestrel | Bow | Was Frost Shards (same role) |
| Nihil | Magic Rod | Was Thunder Orb |

## Traits

The heroes keep a trait each. The traits are re-pointed at the new weapons:

### Aegis -- Bulwark

Extra defence while standing still (today: after 0.4 s without moving, 30 %
less damage taken). The values may be tuned; the rule stays.

**Requirement:** the state must be readable on the sprite. While the bonus is
active the hero plays the **guard** sheet (`guard.png`, added 2026-09-09), so
the player knows when the defence is on and when it dropped.

Aegis also starts with a base **30 % block chance** (see "Hero defensive
stats" below).

### Kestrel -- Double Shot

The Bow fires two arrows per attack. This replaces the current Momentum
(damage-while-moving) trait. Double Shot keeps working after a Forge
(Multishot fires two spreads, Ballista two bolts), with the damage split so
the trait stays small.

Kestrel also starts with a raised base **10 % evasion** (see below).

### Nihil -- Quick Cast

A small casting-speed bonus with the Magic Rod. This replaces the current
Cursebrand (first hit applies Shock) trait. "Small" means a noticeable but not
build-defining bonus; the number is tuned in play.

## Hero defensive stats (decided 2026-09-09)

| Stat | Base | Aegis | Kestrel | Nihil |
|---|---|---|---|---|
| Evasion chance | 5 % | 5 % | 10 % | 5 % |
| Block chance | 0 % | 30 % | 0 % | 0 % |
| Block strength | 50 % damage reduced | same | same | same |

- **Evasion** negates a hit entirely. Every hero has the 5 % base; Kestrel
  has 10 %.
- **Block** reduces the blocked hit's damage by 50 %. Only Aegis has block by
  default; the others gain block chance through the stat blessing. Block
  strength (the 50 %) is itself upgradable through a general stat blessing.
- Both roll before armour in the incoming-damage calculation.

## Attack animation cycle (decided 2026-09-09)

Heroes have two attack sheets (`attack1.png`, `attack2.png`). Attacks
alternate: attack 1 plays, the next attack plays attack 2, the next goes back
to attack 1. Both sheets exist for the warrior today; the other heroes need
theirs before the cycle can apply to them.

## Weapons per run

- A hero holds at most **three** of the six weapons in a run, any mix of
  melee and ranged. The starting weapon is the first of the three.
- Plus **one summon** in its own slot (§3.7).
- Once three weapons are owned no further weapon grants appear; the
  offering is only blessings for what is owned (§21).
- This replaces today's limit of six.

## Main weapon selection (unlockable)

Eventually a hero can choose any of the six weapons as the main (starting)
weapon at the start of a run.

- **Unlock condition:** defeat the boss for the first time with that hero.
  The unlock is per hero: clearing with Aegis unlocks selection for Aegis
  only.
- **Before the unlock** the default main weapons above apply and no choice is
  offered.
- **Persistence:** the save file records, per hero, whether the boss has been
  cleared and which main weapon was last chosen. This is new save state and
  follows the existing save rules: missing keys fall back to defaults, so old
  save files keep working.
- The choice happens on the hero-select flow before the run starts, using the
  existing menu button art.

---

# 21. Blessings

Decided 2026-09-07, revised 2026-09-09.

## Elemental blessings are removed

The current blessing families (Ember, Tide, Storm, Grave) are built around the
elements of the removed weapons: tag damage, on-hit statuses (Burn, Chill,
Shock, ...) and status vulnerabilities. They are **deleted until the elemental
system is implemented** (§16). They are not redesigned now; when elements
return, they return as infusions layered on the six weapons.

## One offering, three kinds of blessing

"Blessing" is the name of anything the player is offered on a level-up (and
at shrines / altars). Every offering is drawn from the blessings the current
run can use, so nothing useless is ever shown: **no Hammer blessing appears
unless the Hammer is owned.**

### Stat blessings

Basic hero stats, always available:

- Max HP
- Movement speed
- Experience gain
- Gold drops
- Base melee damage / base ranged damage (apply to every owned weapon of
  that kind)
- Block chance and evasion chance (passive)
- Block strength (how much a blocked hit is reduced; base 50 %)
- Critical chance
- More may be added later (regeneration, pickup radius, armour, ...)

Block and evasion are new hero stats and need a defined place in the incoming
damage calculation (evasion negates a hit, block reduces it). Critical chance
already exists as a hero stat.

### Weapon blessings

The regular upgrades of §3 to §6, one weapon each, levelled I to V. Offered
only for weapons currently owned (equipped). Summons only grow through
blessings specific to each summon; the melee / ranged stat blessings do not
reach them. Synergy blessings (§5.4, §10)
require both weapons of the pair. Post-Forge blessings (§13) require the
Forge. Forgings themselves are offered here at Forge rarity (§12, §22).

### Weapon grants (while under three weapons)

While the run owns fewer than three weapons, an offering can be a **weapon
grant**: the card adds the weapon **and** one random **level-I** blessing of
any other kind (a stat blessing, or a weapon blessing for a weapon owned
after the grant). The bundled blessing is always level I, never a higher
level, so taking a new weapon never costs the player the progression of that
level-up.

Once three weapons are owned, weapon grants stop. A summon grant works the
same way for the summon slot (§3.7).

## Where blessings come from

- Every level-up offers three blessings (today only every third level does;
  the split between "upgrade" and "blessing" levels goes away).
- Shrines and altars offer one, as today.
- Blessings are levelable (stacks) and their levels are shown on the card.

## Weights

Decided 2026-09-09. The three cards of an offering are a weighted pick over
the valid set. The weights follow four rules:

1. **Stat blessings weigh slightly more than weapon blessings by default**,
   so that in practice at least one stat blessing appears in every level-up.
   This is a weight, not a reserved slot; the numbers are tuned so it holds
   almost always.
2. **Weapon blessings come after**, at a lower default weight, with one
   exception: while the run still has empty weapon slots, **weapon grants
   share the stat weight**, so a new weapon is as likely as a stat blessing
   until the three slots are full.
3. **Higher levels weigh less.** A blessing's weight drops with the level it
   would reach, so level I and II options appear more often than IV and V.
   The same falloff applies to every kind.
4. **Summons follow the same mechanism at a bit lower weight**, the summon
   grant included, because summons are meant to be sparse.

Rarity (§12) multiplies on top of these: Common > Uncommon > Rare > Forge.

## Data

All blessings, stat and weapon alike, are data with an id, kind, weapon (or
none), category, rarity, per-level values and requirements (owned weapons,
Forge, hero). Base weights per kind and the per-level falloff live in the
data as well. The roll stays a pure weighted pick over the valid set.

---

# 22. Decision Log

Every point the first draft left open, with its resolution. All resolved
2026-09-09 unless noted.

1. **Forge exclusivity and delivery.** One Forge per weapon, mutually
   exclusive, requires two regular upgrade levels. Delivered at the village
   Forge building (with a requirements message when nothing is eligible)
   and at Forge rarity in the level-up roll. See §7.
2. **"Recently hit" window.** 1.5 s, shared by every synergy, stated in each
   synergy blessing's description. The Rod's mark is a status on the enemy.
   See §10.
3. **Name collisions.** The regular Bomb upgrade "Cluster Bomb" is renamed
   "Fragmentation"; the old generic "Multishot" label is retired so the Bow
   Forge owns the name.
4. **Weapon slots per run.** Three weapons plus one summon (§20, §3.7).
5. **Numbers.** Placeholders; all tuning lives in data and is balanced in
   play.
6. **Manual aim.** Every directional weapon (Sword, Hammer, Daggers, Bow,
   Bomb) obeys the mouse aim. The Rod auto-targets like the current Arcane
   Bolt / Thunder Orb; a manual aim only gives it a rough area (§3.5).
7. **Bundled blessing in a weapon grant.** Exclusively level I, random among
   the stat and weapon blessings valid after the grant, until the run has
   three weapons (§21).
8. **Summon upgrades.** Power / Coverage blessings specific to each summon
   only; no Behavior, Synergy or Forge (§3.7).
9. **Summon grant.** Offered like a weapon grant while the slot is empty, at
   a bit lower weight, declinable for the run.
10. **Offering weights.** See §21 Weights.
11. **Element-tagged item affixes.** "of the Pyre / Storm / Frost" are
    removed with the elemental blessings; "of the Maw" (area) and "of the
    Hunt" (elite) stay.
12. **Melee / ranged stat blessings and summons.** They do not reach summons;
    summons scale only through their own blessings (§3.7, §21).
13. **Kestrel's Double Shot after a Forge.** Applies to the forged Bow too,
    damage split so the trait stays small (§20).
14. **Aegis's guard visual and the attack cycle.** The guard sheet plays
    while Bulwark is active; attacks alternate between the two attack sheets
    (§20).
15. **Block and evasion.** Base evasion 5 % (Kestrel 10 %); block only on
    Aegis by default at 30 %, others through the stat blessing; a block
    reduces the hit by 50 %, upgradable through a general stat blessing;
    both roll before armour (§20).
