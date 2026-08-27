# Death Must Die Lite: Coding Agent Game Specification

## 0. Purpose

Build a complete 2D action roguelite / bullet-heaven game in Python using Pygame.

The target is a **Death Must Die Lite** experience: one polished playable core loop first, then progressively add character progression, loot/build systems, and procedural content.

The project is inspired by the genre and high-level mechanics of games such as Vampire Survivors and Death Must Die. Do **not** copy their names, characters, art, maps, sounds, UI, text, or proprietary assets. Create original game content and use placeholder/generated assets where necessary.

Reference scope:
- Vampire Survivors establishes the basic time-survival, enemy-wave, XP, level-up and snowballing loop.
- Death Must Die adds the broader roguelite RPG layer: heroes, blessings, randomized items, synergies, bosses and procedural environments.

## 1. Non-negotiable development rules

### 1.1 Technology

- Python 3.12+.
- Pygame 2.x.
- Use a virtual environment.
- Keep dependencies minimal.
- No game engine other than Pygame.
- Prefer the Python standard library where practical.
- Use JSON or another simple human-readable format for static game data.
- Do not introduce a database unless a concrete requirement appears.
- The game must run locally with a simple documented command.

### 1.2 Architecture

Do NOT create one giant `main.py`.

Use clear modules with single responsibilities.

Recommended structure:

    death_must_die_lite/
    ├── main.py
    ├── game/
    │   ├── game.py
    │   ├── state.py
    │   ├── config.py
    │   └── events.py
    ├── entities/
    │   ├── player.py
    │   ├── enemy.py
    │   ├── projectile.py
    │   ├── pickup.py
    │   └── boss.py
    ├── combat/
    │   ├── weapons.py
    │   ├── damage.py
    │   ├── effects.py
    │   └── targeting.py
    ├── progression/
    │   ├── experience.py
    │   ├── upgrades.py
    │   ├── blessings.py
    │   ├── items.py
    │   └── talents.py
    ├── world/
    │   ├── map.py
    │   ├── spawning.py
    │   └── procedural.py
    ├── ui/
    │   ├── hud.py
    │   ├── menus.py
    │   └── level_up.py
    ├── systems/
    │   ├── collision.py
    │   ├── particles.py
    │   ├── camera.py
    │   └── object_pool.py
    ├── data/
    │   ├── weapons.json
    │   ├── enemies.json
    │   ├── blessings.json
    │   ├── items.json
    │   └── characters.json
    ├── assets/
    ├── tests/
    └── README.md

The exact structure may change if a better architecture is justified, but responsibilities must remain separated.

### 1.3 Main loop

Use a deterministic conceptual separation:

    INPUT
      ↓
    UPDATE
      ↓
    COLLISION / COMBAT
      ↓
    PROGRESSION
      ↓
    RENDER

Do not put gameplay logic inside rendering functions.

Do not use frame count as a substitute for elapsed time.

Use delta time (`dt`) for movement, cooldowns and timers.

The game should target 60 FPS but remain logically correct if FPS changes.

### 1.4 State management

Implement explicit game states.

Minimum:

    MENU
    PLAYING
    LEVEL_UP
    PAUSED
    GAME_OVER
    VICTORY

The state system must make it possible to add future states without rewriting the main loop.

## 2. Core design goals

The game should feel like:

- Fast.
- Readable.
- Satisfying.
- Increasingly chaotic.
- Easy to understand initially.
- Deep enough that different builds produce noticeably different results.

The core psychological loop is:

    Move
      ↓
    Kill enemies
      ↓
    Collect XP
      ↓
    Level up
      ↓
    Choose an upgrade
      ↓
    Become stronger
      ↓
    Face stronger/more numerous enemies
      ↓
    Boss
      ↓
    Victory / death
      ↓
    Persistent rewards
      ↓
    Try another build

Do not add complexity merely because the reference games contain it.

Every system must improve one of:
- combat,
- build variety,
- progression,
- exploration,
- readability,
- replayability.

## 3. Phase 1: Playable Core

Phase 1 must produce a complete game that can be played from start to finish.

### 3.1 Player

Implement one original hero.

Minimum stats:

    max_hp
    hp
    move_speed
    armor
    damage_multiplier
    attack_speed_multiplier
    projectile_speed_multiplier
    pickup_radius
    luck

Movement:
- WASD.
- Optional arrow-key support.
- Normalize diagonal movement.
- Keep the player inside the playable world.
- Use responsive movement.

Add a simple dash only if it does not delay the core loop.

### 3.2 Weapons

Implement at least 5 weapons.

Suggested original examples:

- Arcane Bolt
- Ember Ring
- Frost Shards
- Thunder Orb
- Soul Scythe

Each weapon must be data-driven.

A weapon should define things such as:

    damage
    cooldown
    projectile_count
    projectile_speed
    projectile_lifetime
    area
    knockback
    targeting_mode
    pierce
    special_effect

Weapons automatically attack.

The player should not need to manually aim basic weapons.

At least two weapons must behave differently enough that they encourage different builds.

Examples:

- Single-target projectile.
- Area-of-effect orbit.
- Piercing projectile.
- Chain attack.
- Short-range cone.

### 3.3 Enemies

Implement at least 10 enemy variants.

Start with simple behaviors:

- Basic chaser.
- Fast weak enemy.
- Slow tank.
- Ranged enemy.
- Exploder.
- Swarm enemy.
- Shielded enemy.
- Elite.
- Summoner.
- Mini-boss.

Enemies should have:

    hp
    speed
    contact_damage
    radius
    experience_reward
    behavior

Avoid expensive AI for ordinary enemies.

Most basic enemies should use simple steering toward the player.

### 3.4 Spawning

Create a wave/spawn director.

Requirements:

- Spawn enemies outside the visible play area.
- Avoid spawning directly on top of the player.
- Increase difficulty over time.
- Support different enemy compositions.
- Limit active entity counts.
- Use spawn budgets rather than arbitrary hardcoded spawn calls.

Difficulty should increase through combinations of:

    enemy_count
    enemy_hp
    enemy_speed
    elite_frequency
    spawn_rate
    enemy_type_distribution

Do not increase every variable simultaneously without reason.

### 3.5 XP and leveling

Enemies drop XP pickups.

The player collects XP.

Implement:

    XP
    level
    XP required for next level

Leveling must pause the game and present 3 upgrade choices.

Choices should be selected from a weighted pool.

Possible upgrades:

- Increase weapon damage.
- Reduce weapon cooldown.
- Increase projectile count.
- Increase area.
- Increase movement speed.
- Increase max HP.
- Increase pickup radius.
- Add a new weapon.
- Add a passive.

Prevent impossible or useless choices.

Example:
Do not offer "increase damage of weapon X" if weapon X is not owned.

### 3.6 Combat feedback

Every important combat event needs readable feedback.

At minimum:

- Hit flash.
- Damage numbers or equivalent visual feedback.
- Death animation/effect.
- XP pickup feedback.
- Level-up presentation.
- Boss warning.
- Player damage feedback.
- Screen shake for major events, used sparingly.

Do not allow visual effects to obscure the player.

### 3.7 Boss

Add at least one boss.

The boss should:

- Appear at a predictable time.
- Have a health bar.
- Have at least 3 attack patterns.
- Be visually distinct.
- Have a clear telegraph before dangerous attacks.
- Drop a meaningful reward.

Do not make the boss simply a large enemy with more HP.

### 3.8 Run structure

A run should last approximately 15-20 minutes in Phase 1.

Suggested structure:

    0-3 min: easy
    3-7 min: escalating
    7-12 min: difficult
    12-15 min: elite pressure
    15 min: boss / final encounter

The exact duration can change after playtesting.

### 3.9 Victory and defeat

On death:

- Stop gameplay.
- Show summary.
- Display:
  - survival time
  - level
  - enemies killed
  - damage dealt
  - build summary
- Allow restart.

On victory:

- Show run summary.
- Award persistent currency.
- Return to a meta-progression screen.

## 4. Phase 2: Roguelite depth

Phase 2 begins only after Phase 1 is stable and playable.

Do not start Phase 2 while Phase 1 has major crashes or broken progression.

### 4.1 Multiple characters

Add 3 characters.

Each character must have:

- Different base stats.
- One defining trait.
- One different starting weapon.
- One meaningful gameplay identity.

Do not create three characters that are identical with different numbers.

Example identities:

    Knight:
      slow, durable, close-range

    Ranger:
      fast, projectile-focused

    Occultist:
      fragile, status-effect-focused

### 4.2 Passive blessings

Introduce a blessing system inspired by the general concept of god-granted powers.

Create 4 original "factions" or "sources".

Example:

    Ember
    Tide
    Storm
    Grave

Each source has 8-12 blessings.

Blessings modify existing systems rather than creating hundreds of bespoke systems.

Examples:

    +15% fire damage
    attacks apply burn
    burning enemies explode on death
    +1 projectile
    lightning has chain chance
    defeated enemies have a chance to release a soul

Builds should have synergy.

Avoid making every blessing simply "+10% damage."

### 4.3 Synergy rules

Implement explicit tags.

Example:

    fire
    lightning
    frost
    summon
    projectile
    melee
    status
    critical
    area

A blessing can interact with tags.

Example:

    "Burning enemies take +20% damage from area attacks."

This allows many combinations without hardcoding every possible pair.

### 4.4 Items

Implement randomized equipment.

Minimum slots:

    weapon
    armor
    accessory

Items have:

    rarity
    base_stats
    affixes
    level
    optional_unique_effect

Rarities:

    common
    uncommon
    rare
    epic
    legendary

Use deterministic seeded RNG for debugging when possible.

An item generation function should be able to accept a seed.

### 4.5 Item affixes

Create at least 15 affixes.

Examples:

- +max HP
- +movement speed
- +attack speed
- +crit chance
- +crit damage
- +pickup radius
- +luck
- +area
- +projectile speed
- +burn duration
- +burn damage
- +armor
- +XP gain
- +gold gain
- +elite damage

At least 3 affixes should interact with build tags.

### 4.6 Meta progression

After a run, the player receives persistent currency.

Add an upgrade screen.

Persistent upgrades should be modest.

Examples:

    +2% max HP
    +1% movement speed
    +1% luck
    +2% XP gain

Do not make meta-progression so strong that future runs become trivial.

### 4.7 Save system

Persist:

- unlocked characters
- currency
- purchased meta upgrades
- best run statistics
- discovered items
- settings

Use a human-readable JSON save file.

Handle missing/corrupt save data gracefully.

Never crash because a save file is missing.

## 5. Phase 3: Procedural world and advanced builds

Phase 3 expands the game toward the more exploratory side of the genre.

Do not attempt a huge open world.

### 5.1 World

Implement a larger scrolling world.

Requirements:

- Camera follows player.
- World is larger than the screen.
- Enemies can exist outside the visible area.
- Spawn logic understands player/world position.
- Camera never reveals invalid map regions.

### 5.2 Tile/map system

Use a tile-based or chunk-based world.

Create reusable map pieces.

Example:

    open_ground
    corridor
    shrine_room
    arena
    obstacle_field
    treasure_room

The procedural system combines these pieces.

Prefer authored chunks assembled procedurally over purely random individual tiles.

This should preserve playability.

### 5.3 Obstacles

Implement:

- Trees.
- Rocks.
- Walls.
- Pillars.

Collision should be efficient.

Enemies must not constantly become trapped.

### 5.4 Procedural generation

Generate a run-specific map from a seed.

The same seed must reproduce the same map if the generation algorithm has not changed.

Generate:

- starting area
- combat areas
- special rooms
- reward locations
- boss arena

Use a graph to represent room connectivity.

Do not generate unreachable critical rooms.

### 5.5 Exploration rewards

Add special locations:

- Shrine.
- Treasure chest.
- Healing fountain.
- Risk/reward altar.
- Merchant.
- Elite arena.

Each location should have a simple interaction.

Do not build a giant quest system.

### 5.6 Advanced enemy behavior

Add 3-5 advanced enemy types.

Examples:

- Charger.
- Ranged caster.
- Summoner.
- Area-denial enemy.
- Teleporter.

Use finite state machines where behavior becomes complex.

Example:

    IDLE
      ↓
    CHASE
      ↓
    TELEGRAPH
      ↓
    ATTACK
      ↓
    RECOVER
      ↓
    CHASE

Do not use a state machine for a basic enemy that only follows the player.

### 5.7 Status effects

Implement a generic status-effect framework.

Minimum:

    burn
    freeze
    poison
    shock
    bleed

A status effect should define:

    duration
    stack_behavior
    tick_interval
    damage
    modifiers

Avoid creating a separate hardcoded update system for every effect.

### 5.8 Summons

Add at least two summon types.

Summons need:

- spawn
- lifetime
- targeting
- movement
- attack
- death

Keep summon AI simple.

Object pooling should be considered if summons/projectiles become numerous.

## 6. Performance requirements

This genre can produce hundreds or thousands of entities.

Performance must be considered from the beginning.

### 6.1 Avoid unnecessary O(N²)

Do not routinely perform:

    for every enemy:
        for every projectile:
            collision_check()

without a clear upper bound.

Use one or more of:

- spatial grids
- spatial hashing
- distance culling
- collision layers
- broad-phase checks
- object pools

The first implementation can be simple, but profiling must determine when optimization is necessary.

### 6.2 Object pooling

Pool high-frequency short-lived objects such as:

- projectiles
- XP gems
- particles
- damage numbers
- temporary effects

Do not prematurely pool every entity.

### 6.3 Entity limits

Define configurable limits:

    MAX_ENEMIES
    MAX_PROJECTILES
    MAX_PARTICLES
    MAX_DAMAGE_NUMBERS

When limits are reached, degrade gracefully rather than crashing.

### 6.4 Profiling

Create a developer/debug mode capable of displaying:

    FPS
    entity count
    projectile count
    particle count
    update time
    render time

If performance problems appear, profile before rewriting systems.

## 7. Data-driven design

Game content should live primarily in data files.

Bad:

    if weapon == "Fireball":
        damage = 30
    elif weapon == "Lightning":
        damage = 15

Preferred:

    weapons.json

Then load definitions into runtime objects.

Example conceptual structure:

    {
      "id": "arcane_bolt",
      "name": "Arcane Bolt",
      "damage": 20,
      "cooldown": 1.0,
      "projectile_count": 1,
      "tags": ["projectile", "arcane"]
    }

The exact schema can evolve.

The code should provide behavior.

The data should provide content.

## 8. Testing requirements

Tests are required for systems that can be tested without rendering.

Minimum tests:

- Damage calculation.
- XP progression.
- Level-up selection.
- Stat modifiers.
- Blessing stacking.
- Status effects.
- Item generation.
- Rarity probabilities.
- Save/load.
- Procedural generation determinism.
- Enemy spawn constraints.

Use seeded random generators in tests.

Example invariant:

    generate_map(seed=1234)
    generate_map(seed=1234)

must produce equivalent map structures.

## 9. Debugging tools

Create a debug mode.

Useful controls:

    F1 = toggle debug overlay
    F2 = spawn test enemy
    F3 = grant XP
    F4 = force level up
    F5 = spawn boss
    F6 = toggle invulnerability
    F7 = toggle collision visualization

These keys can change later.

Debug tools must never be required for normal gameplay.

## 10. Code quality rules for the coding agent

- Keep functions small enough to understand.
- Avoid unnecessary abstraction.
- Prefer composition over deep inheritance.
- Use type hints for public interfaces.
- Use dataclasses where appropriate.
- Avoid global mutable state.
- Keep configuration centralized.
- Give systems explicit dependencies.
- Avoid circular imports.
- Avoid hidden side effects.
- Do not duplicate game rules across modules.
- Do not silently swallow exceptions.
- Log unexpected failures with enough context to debug them.
- Use meaningful names.
- Comment WHY, not obvious WHAT.
- Remove dead code.
- Do not leave experimental code in production paths.

## 11. Architecture patterns to favor

Use patterns only where they solve an actual problem.

Recommended:

### State Pattern
For:

    MENU
    PLAYING
    PAUSED
    LEVEL_UP
    GAME_OVER
    VICTORY

### Strategy Pattern
For:

    enemy behavior
    targeting behavior
    weapon behavior
    procedural generation strategies

### Observer / Event Bus
For:

    enemy killed
    player damaged
    player leveled
    item collected
    boss spawned
    run ended

Keep events lightweight.

### Factory
For:

    enemies
    weapons
    items
    projectiles
    pickups

### Component-style composition

Prefer:

    Entity
      + Health
      + Movement
      + Combat
      + StatusEffects

over a deep inheritance tree such as:

    Entity
      -> Enemy
        -> FlyingEnemy
          -> FlyingFireEnemy
            -> EliteFlyingFireEnemy

### Object Pool

Use for high-frequency temporary objects.

### Finite State Machine

Use for complex enemy AI and bosses.

## 12. Development order

The coding agent must implement in this order.

### Milestone 1

- Window.
- Main loop.
- State management.
- Player movement.
- Camera.
- Basic rendering.

### Milestone 2

- One enemy.
- One weapon.
- Projectile collision.
- Damage.
- Enemy death.

### Milestone 3

- XP.
- Leveling.
- Upgrade selection.
- Three weapons.

### Milestone 4

- 10 enemies.
- Spawn director.
- Difficulty scaling.
- Five weapons.
- Basic boss.

### Milestone 5

- UI polish.
- Audio.
- Particles.
- Game-over.
- Victory.
- Run statistics.

At this point Phase 1 is complete.

### Milestone 6

- Three characters.
- Blessings.
- Tags.
- Synergies.

### Milestone 7

- Items.
- Affixes.
- Rarity.
- Meta progression.
- Save system.

Phase 2 is complete.

### Milestone 8

- Large world.
- Camera/world boundaries.
- Map chunks.
- Procedural generation.

### Milestone 9

- Obstacles.
- Advanced enemy AI.
- Status effects.
- Summons.

### Milestone 10

- Shrines.
- Shops.
- Treasure.
- Special encounters.
- Final balancing.

Phase 3 is complete.

## 13. Definition of done

A milestone is NOT complete because the code exists.

It is complete when:

- The game launches.
- The intended feature works in an actual run.
- No known blocking crash exists.
- The feature integrates with existing systems.
- Tests exist for important pure logic.
- Debugging is possible.
- The README explains how to run it.
- No temporary hardcoded hacks remain unless explicitly documented.

## 14. Coding-agent workflow

For every milestone:

1. Inspect the current project.
2. Identify existing architecture.
3. Plan the smallest implementation that satisfies the milestone.
4. Implement it.
5. Run tests.
6. Run the game.
7. Verify the feature manually.
8. Fix regressions.
9. Refactor only when justified.
10. Update documentation.
11. Summarize what changed.
12. State remaining risks or known limitations.

Do NOT jump ahead to later phases.

If a later feature requires an architectural change, implement the minimum extensibility needed now rather than prematurely building the entire future system.

## 15. Content creation rules

All game content must be original.

Do not use:

- Vampire Survivors characters.
- Death Must Die characters.
- Their names.
- Their gods.
- Their maps.
- Their artwork.
- Their sound effects.
- Their UI.
- Their exact item names.
- Their exact descriptions.
- Their copyrighted assets.

It is acceptable to implement genre-level mechanics such as:

- auto-attacking
- enemy waves
- XP gems
- level-up choices
- roguelite progression
- randomized items
- blessings
- procedural rooms
- bosses
- build synergies

The goal is an original game inspired by the genre, not a clone.

## 16. Final target

By the end of Phase 3, the game should support:

    3+ playable heroes
    5+ weapons
    4+ blessing sources
    30+ blessings
    10+ enemy types
    3+ bosses
    15+ item affixes
    5 item rarities
    5+ status effects
    procedural maps
    special locations
    persistent progression
    save/load
    multiple viable builds
    hundreds of simultaneous enemies
    performance/debug instrumentation

The most important success criterion is not content quantity.

The game should have a strong loop:

    movement → combat → XP → choices → build growth
          → escalating enemies → synergy → boss
          → reward → persistent progression → replay

Build the smallest version of this loop first, make it fun, then add depth.
