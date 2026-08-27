# Build Transcript — Death Lite Die

A curated transcript of the most important steps of each milestone, with the
reason behind each one. This is not a full command log — it captures the
decisions and turning points that shaped the code. The full milestone log lives
in `journal.md`.

---

## Milestone 1

### Step 1 — Confirm environment before writing anything
**What:** Checked Python (3.12.0) and Pygame (2.5.2 global) were present; created
a project-local `.venv` and installed pygame (2.6.1) into it.
**Reason:** Spec rule 1.1 mandates a virtualenv and Python 3.12+. Verifying up
front avoids building against an environment that can't run the result. An
isolated venv keeps the project reproducible regardless of what's installed
globally.

### Step 2 — `config.py` as the single source of constants
**What:** Put every tunable (screen size, FPS, world size, colours, entity caps,
player base stats, debug key bindings, `MAX_DT`) in one dependency-free module.
**Reason:** Spec rules 7 and 10 ("keep configuration centralized", "data
provides content, code provides behavior"). A dependency-free config means every
other module can import it with zero risk of a cycle.

### Step 3 — Stack-based state machine
**What:** `StateMachine` holds a list (stack) of `State` objects. `push`/`pop`
for overlays, `change` to replace everything. Each state declares `draw_below`
and `update_below`; the machine walks the stack and stops updating below an
opaque overlay but keeps drawing the frozen scene.
**Reason:** Spec §1.4 requires PAUSED and LEVEL_UP. Both must sit *on top of* a
preserved PLAYING state — a single "current state" variable would force
destroying and rebuilding the run. The propagation flags let PAUSED freeze
gameplay while still showing it dimmed behind the menu, with no special-casing
in the main loop (spec: "add future states without rewriting the main loop").

### Step 4 — Delta-time loop with a clamp
**What:** `dt = clock.tick(FPS) / 1000`, then `dt = min(dt, MAX_DT)` where
`MAX_DT = 1/20`. All movement and timers use `dt`.
**Reason:** Spec §1.3 forbids using frame count as a clock and requires logical
correctness at any FPS. The clamp stops a one-off stall (window drag, GC pause)
from producing a giant `dt` that teleports entities through walls or each other
— the classic "spiral of death".

### Step 5 — Pipeline phases as named methods inside PlayingState
**What:** `PlayingState.update` calls `_phase_input`, `_phase_update`,
`_phase_combat`, `_phase_progression` in the spec's order. M1 only fills the
first two; the others are empty and documented as "Milestone N".
**Reason:** Spec §1.3 defines INPUT → UPDATE → COLLISION/COMBAT → PROGRESSION →
RENDER. Establishing the skeleton now means M2/M3 drop systems into the right
slot rather than rewriting the update flow, and the ordering stays visible in
one place.

### Step 6 — Camera built in Milestone 1
**What:** Full `Camera` with clamped, frame-rate-independent smoothed follow and
world/screen transforms, even though the world is only ~2.5 screens wide.
**Reason:** Spec §12 lists Camera in M1, and every render call from M2 onward
needs world→screen translation. The exponential smoothing uses
`1 - e^(-k·dt)` so it behaves identically at any frame rate — consistent with
the delta-time rule.

### Step 7 — stdlib `unittest`, headless smoke test
**What:** Tests use `unittest` (no pytest). Added `test_smoke.py` which boots
`Game` with SDL dummy video/audio drivers and walks MENU→PLAYING→PAUSED.
**Reason:** Spec rule 1.1 (minimal deps, prefer stdlib) rules out pytest for
now. The dummy-driver smoke test catches integration/import breakage that pure
unit tests miss, and runs anywhere with no display.

### Step 8 — Verify by running, not just compiling
**What:** Ran the full suite (24 pass) *and* launched the actual window for 5s.
**Reason:** Spec §13: "A milestone is NOT complete because the code exists." The
windowed run confirmed the parts tests can't — that a window actually appears,
input reaches the player, and pause works on a real event loop.

---

## Milestone 2

### Step 1 — Content loader before any weapon/enemy code
**What:** `game/content.py` reads `data/weapons.json` and `data/enemies.json`
into dicts, raising `ContentError` with the file path on any problem.
**Reason:** Spec §7 mandates data-driven content. Building the load path first
forces every later system (weapons, enemies, spawner) to consume data rather
than hardcode values, and fail-fast on bad data beats a `KeyError` deep in a
frame.

### Step 2 — Generic capped object pool
**What:** `Pool[T]` with `acquire()` / `sweep()` / `clear()` and a hard
`max_size`; `acquire()` returns `None` at the cap.
**Reason:** Spec §6.2/6.3: pool high-frequency short-lived objects
(projectiles, particles, damage numbers) and *degrade gracefully* at limits.
One generic pool avoids a bespoke recycler per type. Returning `None` (vs
raising) lets the caller just skip spawning that frame.

### Step 3 — Spatial-grid broad-phase, not nested loops
**What:** `SpatialGrid` is rebuilt from the enemy list once per frame;
projectile-hit and player-contact checks call `query_circle` instead of
scanning all enemies.
**Reason:** Spec §6.1 explicitly forbids routine unbounded `for enemy: for
projectile` checks. With hundreds of enemies and projectiles that is
O(N·M) per frame; the grid makes each query roughly constant. Rebuild-per-frame
is the "first implementation can be simple" the spec allows — profile before
making it incremental.

### Step 4 — Contact damage as a rate, not an event
**What:** Enemy touching the player applies `contact_damage * dt` each frame of
contact, not a fixed hit per collision.
**Reason:** A per-collision hit fires 60×/second while touching — a hidden
machine gun that also scales with frame rate. A per-second rate is both
frame-rate-fair (spec §1.3) and tunable as an intuitive "damage per second".

### Step 5 — Feedback via the event bus
**What:** Combat publishes `ENEMY_KILLED` / `PLAYER_DAMAGED`; `PlayingState`
subscribes handlers that spawn particles and add screen-shake trauma.
**Reason:** Spec §11 Observer pattern. Combat/collision code should not import
the particle system or the camera. The bus keeps the dependency one-way and
makes it trivial for M5 (audio) and Phase 2 (blessings like "enemies explode on
death") to hook the same events without editing combat.

### Step 6 — Screen shake as a render-only camera nudge
**What:** In `draw`, `camera.pos -= shake.offset` before the world pass and
`+= offset` in a `finally`; the HUD is drawn afterward, unshaken.
**Reason:** Spec §3.6 wants shake "used sparingly" and §3.6 also says effects
must not obscure the player or, here, the readable HUD. Nudging the logical
camera position only for the world blit — and restoring it — keeps culling and
spawn math (which read `camera.pos`) correct.

### Step 7 — Upgrade hooks added before upgrades exist
**What:** `Weapon` carries a `bonus` dict (`damage`, `cooldown_mult`,
`projectile_count`, `area`, `pierce`) that all stat derivations already read,
though nothing writes to it yet.
**Reason:** Spec §14: "implement the minimum extensibility needed now rather
than prematurely building the entire future system." M3's upgrade system writes
these keys; the weapon math does not change.

### Step 8 — Minimal spawner in its own module, documented as a seam
**What:** `world/spawning.py` has the real geometry helper plus a deliberately
tiny `Spawner` (one type, fixed interval), with a comment that M4 expands it.
**Reason:** Spec §13 forbids *undocumented* temporary hacks. Combat needs
targets now, but the budgeted wave director is M4 scope. Isolating the stand-in
in the module that will own the real thing keeps the boundary honest.

---

## Milestone 3

### Step 1 — XP curve as pure code, tested first
**What:** `xp_for_level` = `BASE + LINEAR·n + QUADRATIC·n²`; `LevelTracker`
handles rollover. `test_experience` asserts monotonicity and multi-level dumps.
**Reason:** Spec §8 names "XP progression" as a required test. A pure function
with no pygame is trivial to pin down, and the loop's whole pacing rides on this
curve — early levels fast, later levels slower, never a spike.

### Step 2 — Generate weapon upgrades per owned weapon
**What:** `build_pool` walks `player.weapons` and emits `"<wid>:damage"`,
`"<wid>:pierce"`, ... only for weapons actually held; "new weapon" options are
emitted only for weapons *not* held.
**Reason:** Spec §3.5 is explicit: "Do not offer 'increase damage of weapon X'
if weapon X is not owned." Generating from the owned set makes the invalid
option unrepresentable rather than something to filter and hope you caught.

### Step 3 — Separate `level` from `pending_level_ups`
**What:** `add_xp` bumps `level` immediately for every threshold crossed, and
separately increments `pending_level_ups`; the state machine shows one
`LevelUpState` per pending count.
**Reason:** If a boss's XP dump crosses three levels at once, the HUD should say
the true level right away, but the player must still get all three upgrade
picks. One combined counter would either lie about the level or drop picks.

### Step 4 — Level-up overlay pushed from the progression phase
**What:** `_phase_progression` checks `pending_level_ups` and, guarded by
`_awaiting_level_up`, pushes `LevelUpState` (which has `update_below = False`).
`on_done` consumes one pending level and clears the guard.
**Reason:** Spec §3.5: "Leveling must pause the game." Reusing the existing
overlay mechanism (from PAUSED) means no special pause plumbing. The guard plus
the freeze makes stacked level-ups resolve safely one screen at a time.

### Step 5 — Upgrades in code, content in JSON — on purpose
**What:** `progression/upgrades.py` holds `Upgrade` records whose `apply` is a
closure over stats/weapons; `data/` still only has weapons/enemies.
**Reason:** Spec §7 wants *content* in data, and §10 wants game rules not
duplicated. Upgrades are behavior (they mutate systems), so a closure is the
honest representation. Phase 2's blessings/items are where the data-driven
content pipeline goes.

### Step 6 — One run seed threaded everywhere
**What:** `PlayingState` builds `random.Random(run_seed)` and passes it to the
spawner, the weapon `FireContext` (crit rolls) and `roll_choices`. The seed is
shown in the debug overlay.
**Reason:** Spec §4.4/§8 call for deterministic seeded RNG for debugging. A
single run seed means a bug report plus that number reproduces the exact run —
spawns, crits and offered upgrades all replay.

### Step 7 — Third weapon = chain, reusing the projectile pool
**What:** Thunder Orb sets `special_effect: "chain"`; on hit,
`_chain_to_next` redirects the same pooled projectile at the nearest un-hit
enemy until `chain_left` runs out.
**Reason:** Spec §3.2 wants at least two weapons different enough to drive
different builds — single-target bolt vs piercing fan vs bouncing chain covers
that. Chain rides the existing pool with only a velocity redirect; true orbit
needs persistent anchored entities, so it waits for M4 where it is explicitly
listed.

---

## Milestone 4

### Step 1 — One enemy class, behavior as a lookup, data in `cfg`
**What:** `Enemy` reads its variant dict into `self.cfg`; `update` calls
`BEHAVIORS[self.behavior]`. Ten variants, five behavior functions (stats alone
distinguish fast/tank/swarm/elite/shielded).
**Reason:** Spec §11 explicitly prefers component/composition over a deep
inheritance tree, and §3.3 wants cheap steering for ordinary enemies. A
name→function table adds a variant by adding data plus at most one small
function.

### Step 2 — Behaviors get a context object, not global reach
**What:** `EnemyContext` carries `dt`, player position, rng and three callbacks
(`fire_projectile`, `summon`, `explosion`). Behaviors call those instead of
touching `PlayingState`.
**Reason:** Spec §10 (explicit dependencies, no hidden side effects). The ranged
enemy can fire and the summoner can spawn without importing the pool or the
state; `PlayingState` decides what those callbacks actually do.

### Step 3 — Boss is an FSM whose damage is gated behind the telegraph
**What:** `intro → telegraph → active → recover → next pattern`. The pattern's
effect (`_fire_pattern`) runs exactly once, on the telegraph→active transition;
`test_boss` asserts no bullets exist until the telegraph ends.
**Reason:** Spec §3.7: a boss must telegraph dangerous attacks and must not be
"a large enemy with more HP". Firing on the state edge guarantees the wind-up
is always visible before the payload.

### Step 4 — Difficulty on independent axes
**What:** `SpawnDirector` has a 5-entry phase schedule (composition, interval,
pack size, elite chance, soft cap) plus a *separate* `stat_multipliers(elapsed)`
ramp for HP/speed.
**Reason:** Spec §3.4: "Do not increase every variable simultaneously without
reason." Composition changes are discrete and authored per phase; the stat ramp
is smooth and continuous. Keeping them separate makes each tunable in isolation.

### Step 5 — A second pool for hostile projectiles
**What:** `self.hostiles` is its own `Pool[Projectile]`; enemy/boss shots go
there with `hostile=True`, and only that pool is tested against the player.
**Reason:** Spec §6.1 (collision layers, avoid needless checks). One shared pool
would force every friendly bolt through the player-hit test and every hostile
bullet through the enemy-hit test. Two pools = two clean one-way checks.

### Step 6 — `spawn_projectile` returns the projectile, for orbit only
**What:** The callback now returns the pooled instance (or None at the cap).
`Weapon._maintain_orbit` holds its orbiters in a list, tops them up to
`projectile_count`, and re-spaces their angles when the count changes.
**Reason:** Orbit is the one weapon whose projectiles are persistent and
weapon-owned. Returning the handle avoids a bespoke "orbit manager" system; the
straight/chain/cone paths simply ignore the return value.

### Step 7 — Verify the 15-minute run without waiting 15 minutes
**What:** `RUN_DURATION_SECONDS` stays 900 per spec §3.8. Verification is F5 for
the boss plus a headless playtest that rebuilds the director with
`run_duration=60` and fast-forwards the whole arc.
**Reason:** Spec §13 requires the feature to work "in an actual run", but a
real-time 15-minute manual pass every iteration is impractical. Compressing
time exercises every phase, the cap behaviour and the auto boss spawn in
seconds, and the ratios are identical.

---

## Milestone 5

### Step 1 — Synthesise audio instead of shipping sample files
**What:** `systems/audio.py` builds every cue at startup from sine/square/noise
oscillators into raw int16 buffers wrapped in `pygame.mixer.Sound`. No files, no
numpy.
**Reason:** Spec §15 bans third-party assets and §1.1 wants minimal
dependencies. Oscillator math is a few hundred lines and gives fully original
cues that need no asset pipeline.

### Step 2 — Audio is never allowed to break the game
**What:** Every mixer call is inside `try/except pygame.error`; a failed init
sets `enabled = False` and every `play()` becomes a no-op. Tests run under SDL's
dummy audio driver.
**Reason:** Spec §13 ("no known blocking crash") and the general rule that debug
/ polish features must not be required for normal play. A machine with no sound
device must still run the game and the test suite.

### Step 3 — Replace `EventBus.clear()` with scoped unsubscribe
**What:** `PlayingState` now records its `(event, handler)` pairs and removes
exactly those in a new `exit()`, instead of calling `bus.clear()` on entry.
**Reason:** Adding `AudioManager` as a *persistent* bus subscriber turned the
old blanket clear into a latent bug — starting a run would have silenced the
game. Scoped cleanup lets persistent and per-run listeners coexist on one bus.

### Step 4 — Draw feedback overlays last, keep them subtle
**What:** Low-HP vignette, hit flash and boss banner are drawn in
`PlayingState.draw` after the HUD, with low alpha / blink.
**Reason:** Spec §3.6 requires player-damage and boss warnings but also says
effects must not obscure the player. Drawing after the HUD keeps them on top
where a warning belongs; low alpha keeps the battlefield and HUD readable
through them.

### Step 5 — Derive richer numbers for the run summary, don't store them
**What:** Game-over / victory screens compute kills-per-minute and DPS from the
already-tracked `time`, `kills`, `damage_dealt`.
**Reason:** Spec §3.9 wants a meaningful summary and §10 warns against
duplicating state. The raw counters are the single source of truth; the rates
are a presentation concern computed where they are shown.

---

## Milestone 6

### Step 1 — A single layered stat system before adding stat sources
**What:** `progression/stats.py`: `StatSet` holds base values plus `Modifier`s
(FLAT pooled, PCT pooled, MULT compounded), each tagged with a `source`.
`player.stats` becomes a cached dict rebuilt by `recompute()`.
**Reason:** Phase 2 adds four things that all modify stats (characters,
blessings, items, meta). Without a modifier layer each would mutate the dict
directly and collide; with `source` strings an item can be unequipped by
`remove_source`. The cache keeps the hot combat loop reading a dict, not a
solver (spec §8 "Stat modifiers", §10 "don't duplicate game rules").

### Step 2 — Six generic blessing effect kinds
**What:** Every blessing is `effects: [...]` of `stat_mod` / `tag_damage` /
`on_hit_status` / `status_vuln` / `status_tune` / `on_kill`. `rebuild()`
flattens all owned stacks into one `BlessingEffects` the combat loop reads.
**Reason:** Spec §4.2: "Blessings modify existing systems rather than creating
hundreds of bespoke systems." 32 blessings share 6 handlers. `status_vuln`
(attack-tag × enemy-status) is the §4.3 synergy example verbatim
("area attacks deal +25% to Burning").

### Step 3 — Status framework now, but only three effects
**What:** `combat/status.py` has a data `StatusType` table (burn / chill /
shock) and a per-enemy `StatusState`; poison/bleed are future rows.
**Reason:** Blessings need burn/chill/shock to have anything to synergise with,
but the full generic framework is a Phase 3 milestone (§5.7). §14: "implement
the minimum extensibility needed now."

### Step 4 — Blessings ride the existing level-up screen
**What:** Every 3rd level, `_open_level_up` calls `roll_blessing_choices`, which
returns `Upgrade`-shaped records; the panel and selection code are untouched.
**Reason:** Spec mandates a blessing *system*, not a separate flow. Reusing the
level-up UI means one tested code path and gives blessings a natural cadence
without new plumbing.

### Step 5 — Traits are mechanics, not stat lines
**What:** Aegis reduces incoming damage after 0.4 s of not moving; Kestrel
builds Momentum stacks while moving (+7% damage each) that bleed away when
still; Nihil's first hit on every enemy applies Shock. Each is one hook in
`Player` or the hit resolver.
**Reason:** Spec §4.1: "Do not create three characters that are identical with
different numbers." Three different decisions — hold ground, keep moving, tag
everything — give three playstyles.

### Step 6 — DoT damage flows back through the enemy context
**What:** `EnemyContext.report_damage` is called for every burn tick;
`PlayingState` adds it to `damage_dealt`, and burn setting `hp <= 0` is picked
up by the normal `_cull_dead_enemies` pass (XP, on-kill effects, `ENEMY_KILLED`).
**Reason:** Spec §10 (don't duplicate rules). Burn is just another damage
source; routing it through the same accounting and death path means kills from
burn drop gems, trigger Cinders, and count in the summary with no special case.

---

## Milestone 7

### Step 1 — `generate_item` is a pure function of a seed
**What:** `generate_item(content, seed=, item_level=, luck=, slot=)` builds one
`random.Random(seed)` and draws everything (slot, base, rarity, affixes) from
it. `item_id` embeds the seed.
**Reason:** Spec §4.4/§8: "An item generation function should be able to accept
a seed", "same seed ⇒ equivalent structure". A pure generator is trivially
testable and makes a boss drop reproducible from the run seed for debugging.

### Step 2 — Tag affixes feed the existing synergy aggregate
**What:** An affix is either `stat` (→ StatSet `Modifier`) or `tag_damage`
(→ `blessing_fx.tag_damage[tag]`). `rebuild_blessings` now also walks
`player.equipment`.
**Reason:** Spec §4.5: "At least 3 affixes should interact with build tags."
Rather than a parallel item-synergy system, an item "of the Pyre" pours into the
same `fire` bucket the Ember blessings use — one damage pipeline, five such
affixes shipped.

### Step 3 — Defend the save field-by-field, write it atomically
**What:** `load` returns a default on a missing file and, on unparseable JSON,
renames it to `.corrupt` and returns a default. `_coerce` type-checks every key
independently. `save` writes a temp file then `os.replace`.
**Reason:** Spec §4.7: "Handle missing/corrupt save data gracefully. Never
crash." A file can be valid JSON but have `"currency": "lots"` — wrapping only
`json.loads` isn't enough. Atomic write means a crash mid-save can't leave a
half-written file.

### Step 4 — `__`-prefixed stats are meta-only knobs
**What:** `__salvage_gain` lives in `meta_upgrades.json` like any upgrade, but
`MetaCatalog.player_modifiers` skips any stat starting with `__`; the reward
path reads it via `salvage_multiplier`.
**Reason:** Keeps all meta upgrades in one data file and one buy flow, while
letting some of them affect systems other than the player's stat block without a
separate mechanism.

### Step 5 — Injectable save path
**What:** `Game(save_path=...)`; `main.py` uses the default next to `main.py`,
tests pass a temp path.
**Reason:** `Game()` now does file I/O in `__init__`. Without the injection
point the smoke test would read and overwrite the real `save.json` and stop
being hermetic. One optional parameter, default unchanged.

### Step 6 — A test found a real crash
**What:** `test_save.test_junk_types_are_ignored` failed with
`int("not a number")` from `_coerce`. Fixed `_coerce` to gate every field
through `_is_int` / `_is_num` / `isinstance` before converting.
**Reason:** Spec §8 lists "Save/load" as a required test precisely to catch
this; the crash would have hit any player whose save was touched by a bad
external edit or a version mismatch.

---

## Milestone 8

### Step 1 — Generate a spanning tree, don't generate-then-validate
**What:** `generate_world` keeps a set of occupied chunk cells; each new room is
placed on a free cell orthogonally adjacent to an occupied one and connected to
it. The result is a tree.
**Reason:** Spec §5.4: "Do not generate unreachable critical rooms." A tree is
connected by construction — `is_connected()` is a sanity check in tests, not a
generation gate that could reject-and-retry.

### Step 2 — One room per chunk cell
**What:** Rooms sit on a lattice; only orthogonal neighbours are joined.
**Reason:** Neighbours therefore share a full edge axis, so a corridor is one
straight rectangle. No L-bends, no diagonal overlap maths, and the geometry
tests (`corridor bridges its two rooms`, `no room overlap`) stay trivial.

### Step 3 — Movement resolution is three cheap checks
**What:** `resolve_movement(prev, new, r)` returns `new` if walkable, else
`(new.x, prev.y)` if that is, else `(prev.x, new.y)`, else `prev`.
**Reason:** Against axis-aligned walls this gives correct wall-sliding with no
physics library (spec §1.1 minimal deps). One function shared by player, enemy
and boss means nothing can ever be outside the walkable area — which is also how
"the camera never reveals invalid map regions" (§5.1) is satisfied: there is
nothing invalid to reach.

### Step 4 — Spawn from the nearest off-screen rooms
**What:** `offscreen_spawn_point` sorts rooms by distance to the view centre,
picks among the closest three, and samples a point in that room that is off
screen and not right on top of the player.
**Reason:** The Phase-1 ring spawner assumed a small arena. In a 16-room world,
random room selection would drop enemies minutes away and the fight would
starve. Nearest-off-screen keeps the §3.4 constraints (off-screen, not on the
player) while preserving pressure.

### Step 5 — The boss room is the BFS-farthest, and the boss spawns there
**What:** `boss_id = max(bfs_distances(start))`; `_boss_arena_point` returns
that room's centre.
**Reason:** Spec §5.4 lists a "boss arena" as generated content, and §3.7 wants
the boss to "appear at a predictable time". Farthest-from-start makes the run a
journey toward it; the existing 95%-of-run timer still triggers the spawn.

---

## Milestone 9

### Step 1 — Status effects: one loop, dispatch by family
**What:** `StatusType` gains `family` (`dot`/`slow`/`amp`). `StatusState.update`
is a single loop; DoT ticks call the damage callback, slow/amp are read by
`speed_multiplier` / `damage_taken_multiplier`. Poison and bleed are new table
rows.
**Reason:** Spec §5.7: "Avoid creating a separate hardcoded update system for
every effect." The M6 version still had `if sid == "burn"`. Generalising it made
poison + bleed a data change with no new update code, and got us to the §16
"5+ status effects" target cleanly.

### Step 2 — Circular obstacles + the movement resolver we already had
**What:** `Obstacle` is a circle; `GameMap.is_walkable` also rejects obstacle
overlap; `resolve_movement` is unchanged.
**Reason:** Spec §5.3 wants obstacles that enemies don't "constantly become
trapped" in. Convex circles + axis-slide resolution means an enemy walking into
a rock slides around it. Keeping room centres clear during generation protects
spawn points and corridor mouths.

### Step 3 — One FSM skeleton, three strategy callbacks
**What:** `_fsm_common(enemy, ctx, *, ranges/timers, on_attack_start,
on_attack_tick)` runs chase→telegraph→attack→recover. Charger/teleporter/
warlock each supply just the callbacks.
**Reason:** Spec §5.6 shows exactly this cycle and §11 says use FSMs "where
behavior becomes complex". Sharing the skeleton means the telegraph→attack edge
— the one dangerous moment — is defined in a single place, so every advanced
enemy telegraphs by construction.

### Step 4 — Summons damage through the friendly projectile pool
**What:** A totem bolt is a normal projectile; a wolf bite is a 0.12 s,
high-pierce projectile. `Summon.update` calls `ctx.spawn_projectile`.
**Reason:** Spec §10 (don't duplicate rules) and §5.8. Routing summon damage
through `_resolve_projectile_hits` means blessing tag-synergy, crit, status
procs and screen feedback all apply to summons for free — no summon-specific
combat code.

### Step 5 — `projectile_count` doubles as the summon cap
**What:** `_maintain_summons` tops up to `_projectile_count()` live summons.
**Reason:** Summons are pooled (spec §5.8) and need a cap. Reusing the existing
per-weapon stat means the "Multishot" level-up upgrade and the "of the Storm"-
style item affixes already understood by that number also grow a summon army —
one knob, consistent behaviour across weapon families.

---

## Milestone 10

### Step 1 — Interactables dispatch by `_use_<kind>`
**What:** `_build_interactables` reads room kinds; `E` finds the nearby one and
calls `getattr(self, f"_use_{it.kind}")`. Six small methods.
**Reason:** Spec §5.5: "Each location should have a simple interaction. Do not
build a giant quest system." A method per kind is the smallest thing that
works; adding a location is a data kind plus one method.

### Step 2 — In-run gold is a different currency from banked Salvage
**What:** Kills add `stats["gold"]` (1, elites 2), spent only at the Merchant.
Only the boss and the elite arena add `stats["currency"]`, which `Game`
banks to the save on `RUN_ENDED`.
**Reason:** The Merchant needs a spendable in-run resource, but if per-kill
income banked as Salvage, meta-progression would balloon (hundreds of Salvage a
run instead of ~60-120). Two names, one line of separation.

### Step 3 — The altar refuses a lethal trade
**What:** `_use_altar` checks `hp > cost + 1` before charging 25% max HP.
**Reason:** Risk/reward (spec §5.5) means a real cost, not a way to accidentally
end your run on a decoration. Refusing is the safe failure.

### Step 4 — Balancing is data-side and modest
**What:** HP ramp 1.9→1.4, speed 0.35→0.30, phase caps down ~20%, intervals
eased, Kestrel/Nihil +~15 HP, run 900→600 s. No mechanics touched.
**Reason:** Spec §13 wants the milestone to work "in an actual run", and
playtests showed a solid run never reached the boss at 900 s. The changes are
small, all in JSON / `config.py`, and explicitly a first pass — §3.8 says the
duration "can change after playtesting", and it did.

### Step 5 — `test_smoke` stopped asserting on a live enemy count
**What:** It now seeds enemies next to the player and asserts kills ≥ 5 and
damage > 0, instead of `len(enemies) > 0` after the run.
**Reason:** After the M8 procedural world + the M10 slower opening, a
short-range starting weapon (Aegis's Soul Scythe) can clear its spawns as fast
as they arrive, leaving the list empty at the check. Kills/damage are what the
smoke test actually means to prove.
