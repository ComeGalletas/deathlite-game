# Spawn Master — design proposal

> Proposal only (2026-09-03). Nothing here is implemented. Numbers quoted
> from the tree are from `journals/journal.md` (nav M6 profile) and
> `game/config.py`; everything else is a design choice, marked as such.

The Spawn Master owns three things the game currently spreads over
`world/spawning.py`, `game/states/playing/spawning.py` and
`GameMap.offscreen_spawn_point`: **where** enemies may appear, **how many**
exist at once and in what mix, and **which** of them are simulated this
frame. It also emits the **resource anchors** later systems (chests,
breakables, ambient pickups) will consume. It talks to the run through one
narrow adapter, the way `PlayingPerception` already fronts the AI.

**In one paragraph.** Precompute spawn points as the last world-generation
stage, after obstacles and the unseal repair, so runtime placement is a
filtered table lookup. Keep only the enemies of the player's room, the room
they are heading to, and the bridge between them as live objects; everything
else is a frozen record. Drive the mix from data tables (run fraction x
difficulty x group template) with a bounded pressure multiplier on top.
A watchdog recycles enemies that are stuck or off the floor by despawning
them with their state and re-placing them off screen. The existing profile
(220 live enemies at p50 4.3 ms per update) says 100 live enemies is already
inside budget; the design keeps it there by bounding the *live* set, not by
making each enemy cheaper.

---

## 1. Where the code stands

| Concern | Today | Problem for the goal |
|---|---|---|
| Schedule | `_PHASES` in `world/spawning.py`, five bands, code constants | Not data; no grouping; no difficulty-specific mix |
| Placement | `GameMap.offscreen_spawn_point`: pick one of the 3 nearest rooms, 12 random tries | No obstacle / inset / clearance check; can land on a prop or a rim; searches at runtime |
| Population | `ps.enemies`, one flat list, all updated every frame | Enemies three rooms away still tick AI, nav sampling, bumping |
| Cap | `enemy_count_cap` grows to `ENEMY_COUNT_HARD_CAP = 600` | Cap is global, so a far room can hold the budget hostage |
| Stuck | `Unstick` component nudges sideways | Per-enemy only; nothing recycles an enemy embedded in a cliff or lost off-world |
| Arena / boss | `SpecialLocations` and `EnemyControl.spawn_boss` call `spawn_enemy(at=)` | Fine; must keep working and must bypass locality rules |

World facts the design leans on (`game/config.py`): 9 rooms per run; a
room is 46-52 x 28-32 tiles of 64 px, about 3000 x 1900 px; the view is
1600/1.5 x 900/1.5, about 1067 x 600 px. A room is roughly three views wide,
so "off screen but in the same room" always has space. Rooms form a tree, so
"adjacent" means at most four neighbours, usually one or two.

---

## 2. Layout

Per the one-module-per-concern rule, a new top-level package alongside
`combat/` and `progression/`:

```
spawn/
    __init__.py      SpawnMaster facade + the Host protocol
    points.py        SpawnPoint / ResourcePoint records, per-room index
    tables.py        loads data/spawn_tables.json; phase / group lookup
    budget.py        the interval / cap / elite / stat-ramp director (moved from world/spawning.py)
    pacing.py        the bounded pressure multiplier and the named-modifier stack
    locality.py      current room, heading room, active zone, hysteresis
    population.py    live / dormant registry, hibernate + wake, per-frame wake budget
    placement.py     choose a point for a spawn request; group ring placement
    watchdog.py      stuck / off-floor detection and recycle
world/gen/spawnpoints.py   the generation stage (emits layout.spawn_points)
data/spawn_tables.json     phases, groups, difficulty rows, pacing bounds
```

`world/spawning.py` shrinks to `ring_point_outside_view` (used by the
no-layout fallback) or goes away. `game/states/playing/spawning.py` becomes
the adapter: it builds the `Host`, forwards `spawn_boss`, `summon` and the
arena's `spawn_at`, and constructs `Enemy` objects. The master never
imports `entities` or `game.states`.

### 2.1 The Host protocol (what the master is allowed to know)

```
Host
    elapsed: float                 # HUD clock, pause-safe
    rng: random.Random             # the run's stream
    difficulty: str
    player_pos() -> Vector2
    player_heading() -> Vector2    # last non-zero move dir
    player_hp_frac() -> float
    visible_rect() -> Rect
    is_walkable(pos, radius) -> bool
    room_at(pos) -> Room | None
    live_enemies() -> list         # read-only view of ps.enemies
    make_enemy(enemy_id, pos, hp_mult, spd_mult) -> Enemy
    add(enemy) / remove(enemy)     # the only writes into ps.enemies
    neighbors_near(pos, r) -> list # the combat SpatialGrid query
    publish(event, **kw)           # event bus
```

Everything else (`Camera`, `NavField`, `Animator`, the arena state machine)
stays on the far side of this line. Tests build a fake Host in ten lines.

The master has **full control over every enemy spawn**, scripted ones
included: the live cap is the master's rule, and so is its exception, a
list of spawn owners (`owners.cap_exempt` in the tables, the arena today)
it always seats. The hero's own summons (wolf, totem) are not enemies and
are outside the master entirely.

---

## 3. Spawn points at generation (rule 1)

A new stage in `generate_world_steps`, after `unseal` (so the lattice the
game steers on is final) and before the layout is returned. It yields one
loading label per room, like the terrace stage does.

**Candidate lattice.** Walk each room's ground cells on a coarse stride
(every 3rd tile, offset per room). A candidate survives if:

1. it is ground (`Cell.kind == GROUND`), not a flight or its landing tile;
2. `inset.world_clear(room, x, y, margin)` with margin = the large nav
   class clearance (22 px) plus the body inset, so no one straddles a rim;
3. no obstacle within `radius + 22 px` (the same test `scatter._blocks`
   runs, against the final obstacle list);
4. not inside a bridge-mouth keep-clear rect or a flight keep-out
   (`_corridor_doorways`, `_flight_keepouts`: reuse, do not re-derive);
5. at least 4 tiles from the room's interactable centre and from the boss
   room's arena centre;
6. passable on the **large** nav class (`NavGrid.passable`): the widest
   body can stand there and reach the rest of the room; the small class is
   implied.

**How many.** One parameter, `SPAWN_POINTS_PER_FLOOR` (default **10**),
snapshotted into `GenSettings` as `spawn_points_per_floor` like every other
generation knob. It is the target count **per terrace of each island**: an
island with three floors carries 30 enemy points. Selection per floor is
farthest-point sampling over the surviving candidates (start from a random
survivor, repeatedly add the candidate farthest from every kept point) until
the target is met, so the points spread over the whole terrace instead of
clustering. A floor that runs out of candidates before the target keeps what
it has and logs the seed, room and floor; a floor below 3 relaxes step 2's
margin once and retries. Small upper terraces will commonly stop short, and
that is fine: the director draws from the whole active zone, not one floor.

**Record.**

```
SpawnPoint(room_id, floor, pos: (x, y), clearance: "small" | "large",
           tags: frozenset)      # "edge" (within 4 tiles of the coastline),
                                 # "bridge" (within 6 tiles of a bridge mouth),
                                 # "upper" (floor > 0), "arena", "boss"
```

`WorldLayout.spawn_points: list[SpawnPoint]` plus an index
`points_by_room: dict[int, list[int]]` built once. The boss room gets
`"boss"`-tagged points only (the director is silent during the fight; they
serve boss adds). The start room's points are all at least 8 tiles from the
start centre so the opening seconds are calm.

**Resource points** run the same filter with different knobs: smaller
clearance (small class), a *preference* for cells adjacent to a cliff base or
a prop (so a chest sits against something), never on the shortest bridge-to-
bridge line (cheap approximation: not within 2 tiles of the segment joining
the room's bridge mouths). 6-10 per room, tagged `"chest" | "breakable" |
"ambient"` by a weighted roll. Nothing consumes them yet; they exist so the
future pickup/loot system reads the layout instead of searching.

**RNG.** Key a private `random.Random(seed * 7919 + room.id)` per room, the
way `_connection_lane` does, so the stage draws nothing from the world
stream and the pinned layout digests stay valid.

**Cost.** About 1500 cells x 6 cheap tests per room, then a farthest-point
pass over a few hundred survivors per floor; well under one loading slice.

---

## 4. Locality: which rooms are "near" (rule 2)

`locality.py` keeps:

- **current room**: `room_at(player_pos)`, recomputed only when the player
  leaves the cached room's rect. On a bridge, current stays the room just
  left and the *bridge's other end* is the heading room, no guessing.
- **heading room**: among `current.neighbors`, the one whose
  `(center - player_pos)` best aligns with `player_heading()` (dot product),
  accepted only when the alignment exceeds a threshold *and* holds for a
  dwell time (1.0 s). While the player stands still or circles, heading is
  `None`. This is the hysteresis that stops rooms flapping in and out.
- **grace room**: the room the player most recently left, kept active for
  a grace window (6 s, data) so pursuers crossing the bridge behind the
  player do not blink out mid-chase.

**Active zone** = {current, heading, grace} rooms plus the corridors between
them. The zone is a set of room ids; every other component asks it one
question: `is_active(room_id)`.

Rooms are 3 views wide, so the zone is never smaller than "everything the
player could reach in the next few seconds" and never larger than three
islands.

---

## 5. Population: live and dormant (rule 3)

Every enemy the master owns is in exactly one of:

| State | Representation | Cost |
|---|---|---|
| **live** | an `Enemy` in `ps.enemies` | full AI, nav, bump, anim |
| **dormant** | a `DormantEnemy` record in `population.dormant[room_id]` | zero per frame |
| **dead** | gone; XP/gold already handled by the existing event | none |

`DormantEnemy` is a `__slots__` record: `enemy_id, pos, floor, hp, max_hp,
shield_hp, speed, status snapshot, group_id, owner, spawned_at`. No Animator,
no Blackboard, no behaviour object; those are rebuilt on wake from
`build_behavior`, which is what `Enemy.__init__` already does. Roughly 150
bytes; the hard cap of 600 is about 90 KB.

**Hibernate** (every 0.5 s, not every frame): for each live enemy whose
`room_at(pos)` is not in the active zone *and* whose aggro timer has lapsed
(`bb` aggro slot `until < now`), serialise to dormant and `host.remove(e)`.
An enemy still in pursuit stays live wherever it is; that is the chase the
player is watching. Enemies with `owner == "arena"` or `"boss"` never
hibernate.

**Wake** on zone change: a room entering the zone re-materialises its
dormant list at **N per frame** (8, data) so a full room does not land on a
single frame. Each record is validated with `is_walkable(pos, radius)`; a
record whose saved spot is now blocked (a hazard, another body) is placed on
the nearest free spawn point of the same floor instead. Wake order:
farthest from the player first, so the ones that could be on screen appear
last and off screen.

**Freeze, do not simulate.** Dormant enemies do not move, heal or regroup.
Cheap, deterministic, and matches genre expectations. One optional knob:
records dormant longer than `scatter_after` (45 s) are re-placed on a random
spawn point of their room on wake, so the player cannot memorise a room's
layout of threats.

**First visit.** A room with no dormant list is seeded on first activation
with a **resident population** from the tables (see section 6), placed on
its own spawn points, all off screen, tagged `owner == "resident"`. Rooms
feel inhabited on entry without the director having to burst-spawn.

**Caps.** Two numbers replace one: `live_cap` (the performance budget,
default 100, grows with the existing step schedule only up to that hard
ceiling) and `world_cap` (live + dormant, the old 600). The director spawns
against `live_cap - live_in_zone`.

---

## 6. Tables: what spawns when (rule 5)

`data/spawn_tables.json`, loaded once by `tables.py`. Four sections.

**Phases**: the current `_PHASES`, verbatim numbers, moved out of code:

```json
{"until": 0.45, "interval": [1.0, 0.82], "pack": [1, 2], "elite": 0.02,
 "groups": {"husk_pack": 0.6, "runners": 0.25, "swarm": 0.15}}
```

**Groups**: the new unit of spawning. A group is a template placed on one
spawn point; followers ring the leader:

```json
"husk_pack":  {"leader": "chaser", "followers": {"chaser": [1, 2]}},
"warband":    {"leader": "elite",  "followers": {"chaser": [2, 3], "ranged": [0, 1]}},
"swarm":      {"leader": "swarm",  "followers": {"swarm": [4, 6]}, "clearance": "small"},
"artillery":  {"leader": "warlock","followers": {"shielded": [1, 2]}, "prefer": ["upper"]}
```

`prefer` biases point selection by tag (a warlock on a terrace above the
player is the elevation rule paying off). `clearance` says which point class
the group needs.

**Difficulty**: the four factors that live in `config.DIFFICULTIES` today
stay there (they are already data); the table adds per-difficulty
**overrides** on phase rows (e.g. `super_fast` reaches the third mix at 0.35
instead of 0.45) and a per-difficulty **resident** population size.

**Residents**: per room kind and run fraction, how many groups seed a room
on first visit. Start room 0, boss room 0, special rooms 1, combat rooms
2-3 scaled by run fraction.

Elite selection keeps the current shape (a `brute` on 15 % of elite rolls),
expressed as a group entry rather than a literal in code. Enemy ids in the
tables are validated against `data/enemies.json` at load, so a typo fails
at boot, not mid-run.

---

## 7. Pacing: dynamic modulation (rule 6)

`pacing.py` produces one number, **pressure** in `[lo, hi]` (default
0.6-1.5), applied as a divisor on the spawn interval and a multiplier on
`live_cap`. It is the product of two parts.

**Condition signal.** An exponential moving average (tau = 8 s) of a
weighted sum of run-state signals, each normalised to -1..1:

| Signal | Source | Effect |
|---|---|---|
| player HP fraction | `host.player_hp_frac()` | low HP -> lower pressure |
| damage taken rate | `PLAYER_DAMAGED` events | high -> lower |
| kill rate vs spawn rate | `ENEMY_KILLED` events vs the master's own log | player clearing fast -> raise |
| live enemies vs `live_cap` | population | near cap -> hold |
| time since last hit | events | long lull -> raise slowly |

Weights, tau, bounds and a dead-band all live in the `pacing` section of the
JSON. The dead-band (0.1 either side of 1.0) plus the EMA is the hysteresis;
the bounds are the safety rail so a bad weight cannot empty or flood the map.

**Named modifiers.** `master.set_modifier("dev_menu", 2.0)`,
`master.clear_modifier("dev_menu")`. A dict of name -> factor, multiplied
together, so the dev menu, a blessing ("Beacon: +25 % spawns"), an arena or
a future curse can push pacing without knowing about each other. The debug
overlay shows pressure and the modifier list.

Pacing never touches the *mix* or the stat ramp; it only moves cadence and
headcount. That keeps the difficulty knobs independent, per spec 3.4.

---

## 8. Placement at runtime (rules 1-2 again)

`placement.py` answers `choose(request) -> SpawnPoint | None` where a
request carries the group's clearance, preferred tags and the enemy radius.

Filter the active zone's points, in this order (cheapest first):

1. room in the active zone; heading room weighted x1.5 (the tide comes from
   where the player is going), grace room x0.5;
2. point not on cooldown (each point remembers its last use; 3 s);
3. outside `visible_rect()` inflated by 96 px, and farther than 220 px from
   the player (the two rules `offscreen_spawn_point` already enforces);
4. clearance class at least the group's;
5. no live body within `2 x radius` (`host.neighbors_near`);
6. same floor as the player weighted x1.3, unless the group `prefer`s
   `"upper"`.

Weighted random over the survivors with the run's RNG. Followers are placed
on a ring of radius `leader.radius + follower.radius + 8` around the leader,
each checked with `is_walkable`, retried at a wider radius once, dropped if
still blocked (the group spawns short rather than stacked).

If nothing survives (the player is pressed into a corner of a tiny room and
the whole zone is on screen) the request is **deferred**, not dropped: the
director keeps its spawn debt and retries next tick. A debt older than 5 s
relaxes rule 3 to "outside the view" only.

The no-layout `GameMap(seed=None)` world keeps `ring_point_outside_view` as
its whole placement; the master detects `layout is None` and uses that path,
so the non-run tests are untouched.

---

## 9. Watchdog: stuck and lost enemies (rule 4)

Independent of the AI's `Unstick` (which is a steering nudge and stays).
`watchdog.py` samples every live enemy once a second (staggered across
frames by `id % 60`, so about 2 enemies per frame at 100 live):

**Off-floor**: `not is_walkable(pos, radius)` or `room_at(pos) is None`
(off world) -> recycle immediately.

**Stuck**: the enemy has movement intent (`vel` non-zero), is not
attacking (`_attacking` false), is farther than contact range from the
player, and has moved less than `radius` over the last 4 samples -> recycle.

**Recycle** = serialise to a `DormantEnemy` (hp, shield, status preserved:
no free heal, no free kill, no XP), `host.remove`, then re-place on a fresh
spawn point of the same room chosen by section 8 with the enemy's own
radius. If the enemy is on screen, wait until it leaves the view or until
8 s pass, then recycle with a small poof so the vanish reads as intentional.
Each enemy carries a recycle count; after the third it is quietly removed
off screen and its budget returned. A body that cannot be placed three
times is a generation bug to log (`seed`, room, pos), not a gameplay event.

The arena's enemies are recycled within the arena ring only. The arena
state machine tracks ids, so the master hands back the *same* `Enemy`
object re-positioned rather than a new one, to keep `arena_ids` valid.

---

## 10. Keeping 100 live enemies smooth

The bounded live set does most of the work. The measured baseline is 220
live enemies at p50 4.3 ms per update with nav rebuilds at about 4 ms
staggered, so 100 live enemies is inside the 120 fps budget before any of
this. What the master adds, in order of value:

1. **The zone bound.** Far rooms cost nothing; the director never spawns
   into a room the player is not heading to.
2. **Tick LOD for live enemies out of aggro** (optional, `population.py`):
   an enemy whose aggro timer has lapsed and who is outside the inflated
   view ticks its behaviour every other frame with doubled `dt` and skips
   `anim.update`. Movement integration still runs every frame so bumping
   stays exact. Parametrised by `lod_skip` (2) and off by default until
   profiled.
3. **Wake budget** (section 5) so a room activation is spread, never a
   spike.
4. **One spatial grid per frame.** Today `ps.grid` (combat) and
   `BumpResolver._grid` are both rebuilt from the same list each frame.
   Building once and sharing is a small, separate tidy-up; noted, not
   required.

Nothing here changes an enemy's behaviour when the player is looking at it.

---

## 11. Events and debug

Published through the existing bus: `ENEMY_SPAWNED(enemy_id, group, room)`,
`ROOM_ACTIVATED(room_id, woke, seeded)`, `ROOM_DORMANT(room_id, slept)`,
`ENEMY_RECYCLED(enemy_id, reason)`. Audio and HUD can subscribe or ignore.

Debug overlay lines: `zone cur/head/grace`, `live / dormant / cap`,
`pressure x mods`, `recycled n`, `points used/total`. The dev menu gains
"activate all rooms" (perf stress) and "freeze spawns".

**Spawn points are visible in dev mode** (an S1 rule), modelled on the
collision-circle overlay: a `_dev_show_spawn_points` flag on `PlayingState`
that only dev runs honour, its own `DEBUG_KEYS` entry, a dev-menu toggle
beside "Collision shapes", and a `WorldRenderer` pass next to the collider
pass that draws enemy points as diamonds coloured by clearance and resource
points as squares coloured by tag, each labelled with its floor. From S3 on
a point on cooldown draws dimmed. The pass costs nothing while the flag is
off.

---

## 12. Tests

All against the shared cached worlds (no per-test generation):

- **Points**: for every cached seed, every point passes the six filters;
  no two points on one floor closer than 2 tiles; every floor with enough
  candidates carries exactly `spawn_points_per_floor`; a `GenSettings` with
  a different count changes the total accordingly; the boss room has only
  `"boss"`-tagged points; start room points at least 8 tiles from centre;
  same seed -> identical list (determinism); layout digest unchanged by the
  stage (RNG isolation).
- **Locality**: synthetic Host; heading flips only after the dwell time;
  a bridge crossing yields the correct pair; grace expires.
- **Population**: hibernate -> wake round-trips hp / shield / status;
  pursuit keeps an enemy live; wake budget never exceeds N per frame;
  a blocked saved position falls back to a point on the same floor; arena
  and boss owners never sleep.
- **Tables**: JSON loads; every enemy id exists; phase bands cover 0..1
  with no gap; the moved `_PHASES` produce the same spawn sequence as today
  for a scripted 600 s under the same RNG (behaviour-preserving move).
- **Pacing**: bounds hold under extreme signals; the dead-band holds at
  rest; modifiers multiply and clear.
- **Placement**: never inside the view; never nearer than 220 px; never on
  a cooled-down point; the follower ring stays walkable; deferral leaves
  the debt intact.
- **Watchdog**: an attacking enemy is never recycled; an off-floor enemy
  is; hp survives a recycle; the third recycle removes.
- **Perf**: the existing crowded-scene harness with 100 live in the zone
  and 400 dormant elsewhere; whole-update p99 under the 60 fps budget.

---

## 13. Rollout (each phase ships on its own)

| Phase | Work | Risk |
|---|---|---|
| **S1** | `world/gen/spawnpoints.py`, `SpawnPoint`, layout field, loading label, point tests | none: nothing reads the points yet |
| **S2** | `data/spawn_tables.json` + `tables.py` + `budget.py`; `SpawnDirector` reads tables (same numbers) | behaviour-preserving, checked by the sequence test |
| **S3** | `spawn/` facade + Host adapter; placement from points replaces `offscreen_spawn_point`; groups | visible change: packs arrive together |
| **S4** | locality + population (hibernate / wake / residents); `live_cap` | the big one; behind `config.SPAWN_LOCALITY` for one milestone |
| **S5** | watchdog | small |
| **S6** | pacing + named modifiers + dev-menu hooks | tuning only |
| **S7** | tick LOD, shared spatial grid, perf pass with the stress harness | optional, measured |
| **S8** | resource points consumed by whatever loot/breakable system comes next | future |

---

## 14. Decisions taken here (say so if you want them otherwise)

1. **Dormant rooms freeze; no catch-up simulation.** Cheapest, deterministic.
2. **Rooms are seeded with residents on first visit** in addition to the
   director's trickle, so islands feel inhabited. Sizes in data.
3. **Tables move to `data/spawn_tables.json`** with today's numbers copied
   verbatim, per the no-code-defaults rule.
4. **Two caps** (`live_cap` for performance, `world_cap` for the run) replace
   the single growing cap.
5. **Resource points are emitted now, consumed later.** There is no placed
   resource in the game today (XP gems and items drop on kill), so the
   stage costs nothing and saves a search when chests or breakables arrive.
6. **Recycle keeps hp and grants nothing.** A stuck enemy is neither a free
   kill nor a healed one.
