# Enemy despawn by distance — the master lets go of what the player has left behind

**Legacy ID:** SPN-003 · **Systems:** SPN · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The spawn master removes live bodies that are far from the player, so the
frame is cheaper and the live cap is spent on enemies the player can actually
meet.

**Status: built and green (2026-09-19).** See *Built* at the foot.

---

## Requirement (owner, 2026-09-18)

- **Objective:** Have the spawn master remove off-screen enemies that are far
  from the player.
- **Details:** Review how the master despawns enemies today. The goals are to
  save processing power and to lower the live count, so that more enemies can
  be spawned near the player.
- **Constraint:** The player must be constantly dealing with enemies, the
  human village aside.

---

## What despawns today

### One mechanism, and it is not a distance rule

`Population.hibernate` (`spawn/population.py:93`) is the only thing that takes
a living body out of the run for being in the wrong place. It runs every
`population.tick` (0.5 s) and sleeps an enemy when **all** of these hold:

| | test | knob |
|---|---|---|
| 1 | its owner is not in `owners.never_sleep` | `boss`, `dummy` |
| 2 | it stands on an island, and that island is **not in the active zone** | — |
| 3 | its pursuit timer has lapsed (`host.is_pursuing`) | per-enemy `pursuit_seconds`, 6–8 s |

The active zone is `Locality.active()` — the island the player is on, the one
they are heading to, and the one they left less than `grace` (6 s) ago.

**There is no distance test anywhere in that path.** Rule 2 is island
membership, pass/fail. The player's own island is always in the zone, so a
body standing on it is never hibernated, however far away it is. The only
place `player_pos` enters `population.py` is `activate()`, and there it only
sorts the wake queue.

### What the other three mechanisms are, so they are not mistaken for this

* **The watchdog** (`spawn/watchdog.py`) recycles bodies that are stuck,
  embedded or off-world. It is a repair for a body in a bad *spot*, not a
  removal for a body in a distant one, and it puts the body back on the field.
* **Tick LOD** (`config.ENEMY_LOD_SKIP = 2`, `ENEMY_LOD_VIEW_PAD = 192`): an
  enemy neither chasing nor near the view updates every other frame. This is
  the only thing today that answers "save processing power" — and it saves
  about 0.06 ms/frame since the obstacle index landed. The body stays live and
  **keeps its slot in the live cap**.
* **Render culling** (`RENDER_ACTOR_CULL_PAD = 320`) skips drawing it. Same
  again: live, and still counted.

Grepped the whole tree for other removals: the run's enemy list is only ever
shortened by `_cull_dead_enemies` (dead bodies) and `PlayingHost.sleep`
(hibernation). Nothing else lets go of an enemy.

### Measured: how far "still in the zone" reaches

Island extents and spawn-point spread over the four cached worlds
(`tests/worlds.py`), measuring from each island's centre:

| | islands | extent, corner to corner | farthest point from centre |
|---|---|---|---|
| seeds 35 / 7 / 1234 / 42 | 28 with points | **1,900 – 3,240 px** | **1,002 – 1,691 px** |

Against the numbers that bound the player's experience:

| | px |
|---|---|
| camera half-diagonal at 16:9 | 612 |
| placement's strict band (`far_min` .. `far_max`) | 700 – 1,100 |
| an island, corner to corner | ~2,900 (median) |
| up to three islands live at once (current + heading + grace) | — |

So a body can stand **~3,000 px from the player — five screens — on the
player's own island, fully simulated, holding a live-cap slot, for the whole
run.** The master will never spawn a company out there (the band stops at
1,100), but it will keep alive anything that walked there or was seated there
before the player moved on.

### Why this bites harder than it used to

`_cap_room` (`spawn/master.py:548`) counts `host.live_count()` — every live
body anywhere in the world, not the bodies near the player. Two consequences,
both new since the company model landed:

1. **A company is atomic.** A Swarm of 25 is 25 or nothing; if the cap has 20
   slots it does not arrive at all, it waits `cap_retry` (2 s) and asks again
   (`gate_waits`). Stale bodies three screens away do not merely dilute the
   crowd — they can stop the next company from existing.
2. **The cap is the binding constraint, and the last tuning commit says so.**
   `e383f7e` measured the field level off at ~155–162 by 300 s whatever the
   cadence, "because the live cap is the binding constraint there". Every slot
   held by an abandoned body is a slot that cannot become pressure.

That is exactly the owner's second clause — "to lower the current amount of
enemies to allow for more to be spawned near the player" — and it is a real
mechanism, not a feeling.

### The village is already a sanctuary, by construction

`world/gen/spawnpoints.py:362` gives a `village` room **no enemy spawn points
and no resource anchors** — confirmed on all four cached seeds (0 points on
every village island), and `residents.village` is `0`. Placement therefore has
nothing to draw from there.

So "besides the human village" is already true of *spawning*. What can still
happen is an enemy following the hero across a bridge into the village, which
the generator comments call out as intended.

---

## Confirmed reading

What I understand the owner to be asking for, stated as the rule I would
build:

> **A live enemy that is far enough from the player is removed by the master,
> on distance alone, regardless of which island it stands on.** It frees its
> live-cap slot immediately, so the company gate can spend that slot on a
> company seated inside the placement band — near the player. The player
> therefore meets a crowd that is always local and always refreshing, on every
> island except the human village, which stays a sanctuary.

Three things I read as **in scope**:

* despawn keyed to **distance from the player**, not to island membership —
  running *in addition to* today's island rule, which still correctly catches
  a whole island the player has left;
* the freed capacity being **actually spent near the player**, not just freed
  — the point of the change is pressure, not a lower number;
* the human village staying **exempt**, which today is a property of the
  generator rather than of the master.

Two things I read as **out of scope** unless told otherwise: changing
`ENEMY_LIVE_CAP` (250) or the cooldown ladders. This is about *where* the cap
is spent, not how large it is.

---

## What needs the owner's call before it is built

Five decisions. Each has my recommendation, and the reason it is a decision
rather than a detail.

**1. The despawn radius.** It has a hard floor: it must sit **above
`far_max_distance` (1,100)**, or the master would despawn the company it just
seated. It should also clear the camera so nothing vanishes in view — the 16:9
half-diagonal is 612, and an ultrawide render is wider.
*Recommend ~1,400 px*: past the strict band by 300, past a 16:9 view by more
than a screen, and about half an island — so the far end of the player's own
island despawns while the fight around them does not.

**2. Hibernate, or drop outright?** "Removes" reads both ways.
*Recommend hibernate* — it is the existing, tested machinery, the record is
~150 bytes, and the live slot is freed either way. But hibernating by distance
needs a matching **wake by distance**: today records only wake when an island
*enters* the zone, and an island the player never left will never fire that,
so distance-slept bodies would be stranded on it. That wake band needs
hysteresis (wake nearer than the despawn radius) or bodies will flap in and
out at the boundary.
The alternative — drop them, no record — is simpler and guarantees the crowd
near the player is always freshly composed, at the cost of an island no longer
remembering what stood on it.

**3. Does "off screen" need the camera, or does the distance carry it?**
S11 (2026-09-15) deliberately took the camera out of placement so a wider
render would not move spawns. *Recommend keeping it out here too* and letting
a 1,400 px floor be what guarantees off-screen — otherwise the ultrawide
extent changes despawn behaviour, which is the thing S11 was avoiding. Noting
the counter-precedent honestly: the watchdog *does* consult the view, holding
a verdict until the body leaves the screen, because a body vanishing in sight
reads as a glitch. The distance floor is what makes that check unnecessary
here.

**4. Do chasers stay exempt at any distance?** Today `is_pursuing` keeps a
body live wherever it is. *Recommend leaving it*, and recording why: no enemy
has an `aggro_range` above 640, so a body 1,400 px away cannot re-aggro, and
its pursuit timer lapses within 6–8 s — the exemption resolves itself within a
couple of ticks. Worth stating rather than discovering.

**5. The village exemption: generator or master?** It is a generator property
today (no points). If a distance despawn is added, nothing about the village
changes — but the *other* half of the clause ("constantly dealing with
enemies") means the player standing in the village may still draw companies
onto the **neighbouring** island, since the zone includes the heading and grace
islands and the band reaches 1,100 px. *Recommend leaving that alone* — the
player is not in the village's sanctuary radius when they are near the bridge —
but flagging it so it is not later read as a bug.

---

## How it should be proved

The requirement is a claim about what the player meets, so the measurement has
to be about that and not about the despawn count:

* **bodies within one screen of the hero**, sampled across a run, before and
  after — this is "constantly dealing with enemies", and it is the number that
  must go **up**;
* **`gate_waits`** — companies refused by the cap — which should go down;
* **total live** and **frame time p50/p90/p99** via
  `python -m tools.benchmarks.spawn_stress`, which should improve, since 250
  live spread over three islands becomes fewer bodies packed near the hero;
* **a camping run and a patrolling run**, the S10 pair, because a player who
  stays put is exactly who accumulates a ring of abandoned bodies;
* **nothing despawns in view**: the closest despawn over a run, which must stay
  above the view's half-diagonal.

## Risks worth naming now

**The cap may simply refill with the same bodies.** If the wake band is
generous, walking back toward a despawned crowd re-spends the freed slots on
old bodies instead of new companies. That is not wrong — a body near the player
is pressure either way — but it means the "more spawned near the player" effect
would show while moving and fade while standing, which is the opposite of the
S10 camping fix. Worth measuring both ways before choosing the wake band.

**A despawn the player can perceive.** The distance floor is the whole defence.
If it is set below the view diagonal on any aspect ratio, bodies will blink out
on screen.

**Residents interact with this.** An island is seeded once
(`population.seeded`) and `residents.combat` is now 1 company. If distance
despawn drops records rather than keeping them, a combat island the player
crosses, leaves and re-crosses is empty the second time — the resident company
is not re-seeded. That is an argument for hibernating rather than dropping, or
for revisiting `seeded`.

---

## Answered (owner, 2026-09-18)

1. Increase the radius to 1700.
2. Hibernate, but also remove them from the current max limit, so more
   enemies can spawn in other islands.
3. The camera is not needed with the spawn ring.
4. All enemies should be accounted for.
5. Every island should be constantly filled with enemies; the player should
   be constantly dealing with enemies.

### 1. The ring is 1,700 px

Taken as stated, and it clears every floor it has to:

| | px | margin at 1,700 |
|---|---|---|
| `far_max_distance` — the farthest a company is ever seated | 1,100 | +600 |
| camera half-diagonal at 16:9 | 612 | +1,088 |
| the widest `aggro_range` in the roster (`harpoon_shark`) | 640 | +1,060 |
| an island, corner to corner (median of the cached seeds) | ~2,900 | — |

So the live set is an annulus the player carries with them: bodies **arrive**
between 700 and 1,100 px and **are released** past 1,700. Nothing is ever
released inside the view, and nothing is released while it could still see the
player well enough to re-aggro. On a median island the ring covers a little
over half the ground, which is the intent — the far end of your own island
stops being simulated.

### 2. Dormant records stop competing with live spawns

This is a change to `_cap_room` (`spawn/master.py:548`), and it is worth being
exact about which of the two caps moves, because only one of them is in the
owner's way.

```
min(director.enemy_count_cap(elapsed) - live,      # the live cap: 100 -> 250
    world_cap - live - total_dormant)              # ENEMY_COUNT_HARD_CAP: 600
```

Dormant records **already** do not count against the live cap — hibernating a
body frees its simulation slot today. What they do count against is the second
term, and that is the one that blocks "more enemies can spawn in other
islands": bank enough records across the world and `world_cap - live -
total_dormant` becomes the smaller of the two and throttles live spawning
everywhere. With answer 5 asking every island to stay stocked, that is not
hypothetical — 7 to 8 islands carry points on the cached seeds, so a stock of
50 each is 350–400 records against a 600 budget that also has to hold 250 live.

**Confirmed reading:** `total_dormant` comes out of the live-spawn arithmetic
entirely. A sleeping body is a ledger entry, not a claim on the field.

**One thing this needs that the owner did not specify, and I will not invent
silently:** with dormant uncounted, nothing bounds it. At ~150 bytes a record
the memory is irrelevant (10,000 records is 1.5 MB), but an unbounded list
that only ever grows is a slow leak of a different kind, and the wake path
walks it. Proposing a **separate dormant budget** sized from answer 5 (a
per-island target × the islands that carry points, with the oldest-slept
evicted past it) rather than leaving it open. Flagged under "still to settle".

### 3. No camera, at either end

Confirmed, and it makes the rule symmetrical with placement: since S11
(2026-09-15) the camera has not been an input to *where a spawn lands*, and it
is now not an input to *when a body is released* either. Whether an arrival or
a departure happens on screen is a consequence of the distance and the view,
never a rule. The 1,700 px floor is what guarantees it never happens in sight,
on any aspect ratio — which is exactly why the number has to stay above the
render extent if the ultrawide work ever widens it.

The watchdog keeps its own view check (it holds a verdict until the body is off
screen, then poofs it), because that one is about a body vanishing from a spot
the player is looking at. Untouched here.

### 4. No pursuit exemption — every enemy obeys the ring

Read as the answer to the question asked: **a chaser is not exempt.** Today
`Population.hibernate` skips any body whose pursuit timer is running, wherever
it stands; under the ring, distance wins. A body 1,700 px away cannot re-aggro
anyway (the widest `aggro_range` is 640), so what this actually removes is the
long tail of enemies trailing the player across an island with a lapsing timer
— which is precisely the population the requirement is aimed at.

**Two owners I am reading as still exempt, and want confirmed rather than
assumed:** `owners.never_sleep` is `["boss", "dummy"]`.

* **The boss** must not obey the ring. A boss island is ~2,900 px across, so a
  player who backs off mid-fight would despawn it; and because `wake()`
  rebuilds the behaviour machine fresh, a re-woken boss would return with its
  phase state reset. That is a broken run, not a saved frame.
* **The training dummy** is a fixture the player placed on purpose; despawning
  it by walking away defeats the point of it.

Everything else — including elites, residents and a company's stragglers —
obeys the ring.

### 5. Every island stays stocked, and this is the larger half of the work

This is the part that goes beyond despawning, and it should be said plainly:
**it is a second mechanism, not a consequence of the first.**

The only reading consistent with "save processing power" is that an island is
filled with **dormant records**, not live bodies. So:

* every island that carries spawn points holds a **target population** of
  records at all times, not just the one resident company it gets on first
  visit (`population.seeded` gates that to a single seeding today);
* those records **materialise as the player approaches** and are released again
  behind them, so crossing an island is a continuous treadmill — waking in
  front, releasing behind;
* the live cap is then spent almost entirely on bodies inside the ring, which
  is the "constantly dealing with enemies" the owner is after.

What follows from it, worth knowing before it is built:

**The stock becomes the main source of pressure on a stocked island, and the
company cadence becomes the top-up.** Waking records and seating companies draw
on the same live cap, so on an island with a full stock the gate will often
find no room and wait — `gate_waits` will rise, and that is not a fault. The
companies are what *replenish* the world's population; the stock is what the
player meets.

**Waking has to become distance-driven and budgeted.** Today records only wake
when an island *enters* the zone (`Population.activate`), which never fires for
an island the player is already standing on — so a distance-slept body on your
own island would be stranded. The wake trigger becomes the ring, with
hysteresis (wake nearer than 1,700 so bodies do not flap at the boundary), and
`wake_budget` (8/frame) is the knob that stops a crossing from landing a
hundred bodies on one frame.

**`population.seeded` and `residents` need revisiting.** Seeding once per
island is the opposite of "constantly filled". Either the stock is topped up on
a timer, or it is replenished by the companies the director already emits.

### Still to settle

* **The dormant budget and its eviction rule** (from answer 2) — a number, and
  what happens past it.
* **What "filled" means as a number**: bodies per island, and whether it scales
  with the run clock the way the live cap does. This decides the whole feel and
  is the one value I would want the owner's hand on.
* **Boss and training dummy stay exempt** (answer 4) — confirm.
* **Whether the stock is topped up on a timer or by the director's companies.**
  The second reuses machinery that already exists and keeps one source of
  truth for composition; the first is more direct. Recommending the second.

---

## Answered again (owner, 2026-09-18) — the scope comes back down

> 1. Are there still boss islands implemented? Bosses are independent and never
>    despawn, they always chase the player. In case of the pig rider it needs to
>    follow topography to reach the player. Giant bat flies so no need. Dummy is
>    not even considered. It only appears for testing and never for actual
>    gameplay.
> 2. Filled means that the islands needs to have enemies. If the player already
>    visited an island this means that already contains enemies, if the island
>    doesn't contain it works as usual spawning enemies given the current rules.
> 3. Consider if these changes are too heavy or expensive during a gameplay run.
>    The live cap might overflow if the enemies woken up exceed the current cap,
>    in this case the spawning gets paused given the current rules and everything
>    keeps working as usual.

### 1. Boss islands exist; the boss no longer uses them — and it was never in this path

Answering the question as asked, from the code rather than from memory:

**Boss islands are still generated.** `room.kind == "boss"` is on every cached
seed, carrying 10 spawn points and an arena disc that the scatter keeps clear
of obstacles (`_GRID_BOSS_CLEAR_RADIUS`), with spawn points kept outside it
(`world/gen/spawnpoints.py:123`).

**The boss no longer spawns there.** `boss_spawn_point` places it
`BOSS_SPAWN_DISTANCE` (680 px) from the hero on a random side, and its
docstring is explicit: *"No room is consulted: the boss room stays the spawn
master's."* So a boss island is now an ordinary island with a cleared middle,
and the spawn master draws from it like any other. That is the R-series
free-roam work (`documentation/plans/boss_free_roam_todo.md`).

**The boss is not an enemy, and never enters this path at all.** `spawn_boss`
sets `ps.boss = Boss(...)` — a separate object, not a member of `ps.enemies`.
Since `PlayingHost.live_enemies()` *is* `ps.enemies` and `live_count()` is
`len(ps.enemies)`, the boss:

* is never walked by `Population.hibernate`, so the ring cannot despawn it;
* never counts against the live cap, so it never blocks a company;
* keeps chasing regardless of distance, which is the owner's requirement and is
  already true by construction.

So "bosses are independent and never despawn" needs **no code**. The
`owners.never_sleep: ["boss"]` entry is about *enemies tagged with that owner*
— the boss's adds — not about the boss object.

The two bosses, and the topography point:

| id | name | tags | terrain |
|---|---|---|---|
| `the_first_hunger` | The First Hunger (giant bat) | `boss`, **`flying`** | ignores it — the flying floor is the world rect, and `Boss._seek` beelines instead of reading the flow field |
| `the_tusked_lance` | The Tusked Lance (pig rider) | `boss` | walks: full walker collider, flow field, elevation and obstacle rules |

Both already behave the way the owner describes. `boss_spawn_point` even gives
the walker a collider test at its own radius so it is not dropped on water,
while the flyer is handed `None` because the sea is walkable to it.

**The training dummy is out of scope**, as stated — dev-only, never in a real
run. It keeps its `never_sleep` / `cap_exempt` entries because that is what
makes it a stable test fixture; nothing about gameplay depends on them.

### 2. "Filled" means what hibernation already leaves behind — no stocking mechanism

This retires most of what the previous entry proposed under answer 5, and the
correction is the useful part to record.

I had read "every island should be constantly filled" as a **new mechanism**:
a per-island target population, records manufactured for islands the player has
never seen, a top-up timer, a reworked `population.seeded`. That was an
over-reading. The owner's rule is simpler and uses only what is already there:

| the island | what fills it |
|---|---|
| **already visited** | the dormant records the ring left behind. Visiting it *is* what populated it |
| **never visited** | nothing new — the existing rules apply: `residents` seeded on first activation, then companies while it is in the zone |

So the feature is **one mechanism, not two**: the ring releases bodies behind
the player into records, and those records are the island's population when the
player comes back. Everything the previous entry listed as "the larger half of
the work" — per-island targets, stocking unvisited islands, replenishment — is
**out**.

Two consequences worth keeping:

* **The dormant budget question mostly dissolves.** Records are now bounded by
  what the player actually generated and walked away from, not by a stocking
  target across 7–8 islands. A bound is still worth having, but it is a safety
  rail rather than a sizing decision.
* **Waking still has to become distance-driven.** This part survives: records
  slept by the ring on an island the player never left would otherwise be
  stranded, because `Population.activate` only fires when an island *enters*
  the zone. The wake trigger becomes the ring with hysteresis, budgeted by the
  existing `wake_budget` (8/frame).

### 3. Cost: measured, and the old objection is obsolete

The owner asked whether this is too heavy. The harness that would answer it —
`tools/benchmarks/spawn_stress.py` — **was dead**: line 55 still called
`SpawnTables.phase_at`, which G3 deleted with the phase schedule. That is why
S12's last todo, *"Frame cost at 250 live re-measured — not run here"*, was
never ticked. Fixed here (it now composes from the resolved roster, elites
included, so the big radii stay in the mix) and run.

**Seed 35, 300 dormant, 600 frames, LOD 2, `PlayingState.update` only:**

| live | p50 | p90 | p99 | max | frames over 16.7 ms |
|---|---|---|---|---|---|
| 175 (the cap at 300 s) | 5.00 | 5.19 | 5.49 | 9.45 ms | **0** |
| **250 (the cap at 900 s)** | **6.22** | **6.41** | **7.01** | **9.46 ms** | **0** |

Against the table S12 recorded its concern from — measured 2026-09-03, *before*
the obstacle index and the sliced flow-field fill landed:

| live | p50 | p90 | p99 | over 16.7 ms |
|---|---|---|---|---|
| 197 | 15.22 | 17.80 | 23.06 | 126 / 600 |
| 297 | 16.47 | 18.41 | 30.03 | 250 / 600 |

**So the objection recorded against `ENEMY_LIVE_CAP = 250` no longer holds.**
S12 built it over a measured protest — "a crowded frame is expected to miss
60 fps" — and that protest was quoting numbers from a build with the per-frame
obstacle scan still in it. At 250 live packed around the hero the update budget
is now 6.2 ms of 16.7, with not one frame over budget in 600. That closes the
S12 todo.

**Why this matters for the ring specifically.** The harness deliberately packs
every body into the zone around the hero because that was the pessimistic case.
The ring *makes that the normal case* — 250 live inside 1,700 px instead of
spread over three islands. The number above is therefore measured on exactly
the population the change produces, which is the reason to trust it.

**The bookkeeping itself is free.** `Population.hibernate` already walks every
live body every 0.5 s and calls `host.room_at` on each; a squared-distance test
is cheaper than the lookup it sits beside. A distance-driven wake scans one
island's record list on the same tick — a few hundred squared distances, tens
of microseconds. The per-body wake work (`_spot`, `is_walkable`, the free-point
scan, constructing the `Enemy`) is already bounded by `wake_budget`.

**What is *not* measured, and I will not claim it is.** The harness times
`ps.update` only — no draw. Render is culled at `RENDER_ACTOR_CULL_PAD` (320 px
past the view), so cost there scales with **bodies in view**, and that is the
one number the ring genuinely raises: today's 250 live are spread over ~3
islands, afterwards they are all within 1,700 px. Geometrically the view covers
roughly 9 % of a 1,700 px disc, but bodies are not uniformly spread in it —
they arrive at 700–1,100 and walk inward — so in-view count could plausibly go
from the ~15 the render probe was measured at to several dozen. The last
measurement of draw (2026-09-03, after the render fixes) was p50 3.6 ms with 15
in view. **Recommend measuring update + render on a walking hero before the
ring ships**, since that is where the remaining risk sits.

### The overflow rule: already the behaviour, no code needed

The owner's ruling: the live cap may overflow when the enemies woken up exceed
the current cap; in that case spawning pauses under the current rules and
everything keeps working as usual.

Confirmed against the code, and it is already exactly this:

* `Population.wake_some` does **not** consult the cap. It wakes up to
  `wake_budget` records a frame whatever the live count is, so waking can and
  does push live past the cap today.
* `_cap_room` is `max(0, min(cap - live, ...))`, so once live is at or over the
  cap it returns **0**, `_under_cap` is False, and the company gate refuses —
  `gate_waits` rises and the prepared company waits `cap_retry` (2 s) and asks
  again.
* Nothing force-despawns to claw back under the cap. The overflow simply drains
  as bodies die, and spawning resumes.

So the owner's ruling needs no new rule: waking is allowed to overshoot, the
gate pauses, the run keeps going. Worth pinning with a test rather than leaving
it as an emergent property.

### What a per-island target would cost, measured (owner asked, 2026-09-18)

The owner asked the cost of the per-island stocking target after declining it
above. Measured, because the intuition points at the wrong half.

**Storage and bookkeeping are free.** A target of 500 per island across the 8
islands that carry points is 4,000 records:

| | |
|---|---|
| building 4,000 records | **2.3 ms**, once |
| memory, counting every referenced value | ~515 B each -> **2.0 MB** |
| `total_dormant` per call, 4,000 records over 8 islands | **0.41 us** |

`total_dormant` is `sum(len(v) for v in dormant.values())` — **O(islands), not
O(records)**, so it does not grow with the target at all. And nothing walks the
dormant lists per frame: `hibernate` iterates *live* enemies, and the records
are touched only on activation. A dormant record genuinely costs nothing to
hold.

**The whole cost is in what the target wakes.** Frame time against live bodies
packed around the hero (seed 35, 400 dormant, 400 frames, LOD 2, update only,
the director's cap lifted so the harness can seat past 325):

| live | p50 | p90 | p99 | max | frames over 16.7 ms |
|---|---|---|---|---|---|
| 250 | 3.15 | 6.26 | 6.59 | 11.72 ms | 0 / 400 |
| 350 | 4.93 | 8.01 | 8.27 | 14.23 ms | 0 / 400 |
| 450 | 6.94 | 9.96 | 10.88 | **16.76 ms** | 1 / 400 |
| 600 | 10.35 | 13.27 | 18.73 | 20.25 ms | **6 / 400** |

Roughly **+2 ms of p50 per 100 live bodies**, drifting superlinear. 450 is
where the max first touches the 16.7 ms budget; 600 loses frames outright.

**Why this is the number that matters:** `Population.wake_some` does **not**
consult the live cap (confirmed in the code). It wakes `wake_budget` records a
frame until its queue drains, so a stocked island walked into can push live
well past 250 — and the owner's overflow rule pauses *spawning*, which does not
drain an overflow. Only kills do. So the overflow persists for as long as the
player takes to clear it.

**The ring bounds it, and that is the reassuring part.** With a distance-driven
wake, only records inside the wake band are eligible, so the burst is set by
**record density**, not by the island total. A 1,300 px wake disc is ~5.3 M px²
against a ~2,900 px island, so arriving mid-island exposes roughly 60 % of that
island's records:

| target / island | woken at once (~60 %) | live if the field was at 250 | verdict |
|---|---|---|---|
| 100 | ~60 | 310 | comfortable |
| 300 | ~180 | 430 | at the edge |
| 500 | ~300 | 550 | drops frames |

**So the target is not the expensive knob — density inside the wake band is.**
The rule of thumb the numbers give: keep `live cap + 60 % of the largest island
target` under about **450** and no frame leaves budget.

### What is left to settle

Down to two, from five:

* **A bound on dormant records**, now a safety rail rather than a sizing
  decision — a ceiling with oldest-slept eviction, or explicitly unbounded.
* **The wake band**: how much nearer than 1,700 px a record wakes. Needs to be
  enough hysteresis that a player pacing a boundary does not flap bodies in and
  out, and far enough out that they materialise before entering the view.
  Suggest waking at ~1,300 px, giving a 400 px dead zone.

---

## Built (2026-09-19)

**Status: built and green.** Two changes went in together, and the second
turned out to matter more than the first.

### The ring

| knob | value | why |
|---|---|---|
| `population.despawn_radius` | **1400** | the owner's call on the day, over the 1700 recorded above |
| `population.wake_radius` | **1100** | `far_max_distance` at the time, so a record woke exactly as it re-entered the band |

`Population.hibernate` now sleeps a body when **either** rule fires: the
ring (beyond `despawn_radius`, no exemption for a chase and none for the
hero's own island) or the older zone rule (a whole island the hero left,
pursuit lapsed). An owner in `never_sleep` is exempt from both, and a body
on a bridge is left alone because a record is filed by island and there is
none to file it under.

`Population.wake_nearby` is the other half, and it is what made the ring
usable: `activate` only fires when an island *enters* the zone, which never
happens for the island underfoot, so a body the ring slept there would have
been stranded for the rest of the run. A `wake_radius` at or above
`despawn_radius` now raises at construction rather than flapping bodies
between the two states every tick.

`_cap_room` no longer counts `total_dormant`, per the 2026-09-18 answer.

### What the ring alone was worth

Measured on a fully ticking run -- `ps.update`, not the master alone. The
first pass ticked only the master, so bodies never moved and the
standing-still case was inert by construction; that measurement was wrong
and is not reported here.

| 4 minutes, hero walking a patrol | ring off | ring on |
|---|---|---|
| bodies within a screen, median | 10 | **21** |
| within a screen, p90 | 23 | **46** |
| released by the ring | 0 | 591 |
| re-woken by distance | 217 | 516 |

Good for a moving player. **For a standing one the ring did nothing at
all** -- `ringed` 0, median 5 bodies within a screen out of 152 live.

### The real fault the measurement exposed

The ring could not have fixed that at any radius, and the reason is a gap
between two numbers that had drifted apart:

```
placement band     700 .. 1100     where a company was seated
widest aggro_range 640             Gaffjaw; most of the roster 360-480
```

**A company was seated outside every enemy's aggro range.** A standing hero
never drew those bodies in, and they sat between 1100 and the 1400 ring
for the rest of the run -- too far to notice the hero, too near to be
released. 152 live, five of them met. That is the owner's "constantly
dealing with enemies" failing, and no despawn radius addresses it:
shrinking the ring below 1100 would have despawned the company the master
had just seated.

### The fix (owner, 2026-09-19)

- **Objective:** Increase the aggro range substantially, so far enemies are
  aggroed from closer.
- **Details:** Also consider spawning enemies even closer to the player.

Both levers, set against each other so that two invariants hold at once:

```
far_max_distance  <  min(aggro_range)     every arrival can see the hero
max(aggro_range)  <  despawn_radius       a released body cannot re-aggro
```

The second is the invariant the ring's whole design rests on, and it was
the constraint on how far the first could go.

* **Aggro**: the roster's span `[360, 640]` mapped linearly onto
  `[880, 1200]`, so ordering and relative spread survive -- Shellback
  360 -> 880, Husk 420 -> 950, Gaffjaw 640 -> 1200. Roughly a doubling.
* **Band**: `far_min_distance` 700 -> **620**, `far_max_distance`
  1100 -> **850**.

850 < 880 and 1200 < 1400, so both hold with room.

### Measured again, after both

| 4 minutes, full run tick | before | after |
|---|---|---|
| **hero standing still**, within a screen (median) | 5 | **111** |
| standing still, p90 | 7 | **143** |
| hero walking, within a screen (median) | 21 | **63** |
| walking, p90 | 46 | **106** |

The camping case goes from five bodies met to a hundred and eleven. Note
what this does to the ring's own contribution: `ringed` fell from 591 to
52, because with aggro raised almost nothing is left behind to collect.
**The ring is now the safety net and the aggro range is the mechanism** --
worth recording, because the ring looked like the feature and was not.

### Consequences to carry into the balance pass

* **This is a large difficulty increase.** The field went from 5 enemies
  engaged to ~111, on top of G1's +69 % elite item income and the
  front-loaded cadence from `e383f7e`. Nothing here was compensated for.
* **`far_min` 620 is 8 px past the 16:9 camera half-diagonal (612).**
  Arrivals now land at the very edge of the screen where 700 kept them
  clear -- S11 set that margin deliberately. The band could go back to
  700..850 and still satisfy both invariants; only the closeness would be
  lost.
* **Still unbuilt from the plan above**: a bound on dormant records (a
  safety rail now, since records are bounded by what the player generated),
  and an update **+ render** measurement. Only `ps.update` has been timed,
  and the ring makes "everything packed near the hero" the normal case,
  which is exactly where draw cost lives.

### Tests

New in `tests/spawn/test_population.py`: the ring and the zone rule each
taking their own with the geometry chosen so one rule decides each body; a
body on the hero's own island sleeping once it is far enough (the case that
did not exist before); the ring beating a chase; a record waking when the
hero walks back to it; the wake band sitting inside the ring; and a
`wake_radius` outside the ring being refused outright.

`test_the_world_cap_counts_the_dormant` became
`test_the_world_cap_no_longer_counts_the_dormant`, asserting the reversal
directly rather than being deleted.

Three tests elsewhere needed adjusting, none of them hiding a defect:
`tests/flows/test_lod.py` had its deliberately-distant enemy eaten by the
ring (the ring is held off there, since those tests measure the LOD),
`test_an_enemy_inside_the_ring_pursues` hard-coded four seconds for what is
now nearly nine seconds of walking, and the placement band test wrote out
700 / 1100. All three now read the data instead.

---

## The dormant bound, and the frame budget (2026-09-19)

The two items the build left open.

### The bound: a rail, sized from play

`population.dormant_cap` is **4000**, past which the **oldest-slept** record
is dropped -- so the island abandoned longest ago is the one that forgets
its population, which is both the least likely to be walked back into and
the one whose records are most stale.

It is deliberately several times above anything play produces. Measured over
five minutes on the pinned world:

| hero | peak dormant | ends at |
|---|---|---|
| standing still | 20 | 20 |
| patrolling | 22 | 3 |
| **touring every island** (teleporting every 20 s) | **1304** | 1250 |

The touring row is the pessimistic case and is not a real play pattern -- a
player walks -- yet it still lands at a quarter of the cap. At ~515 bytes a
record the cap is about 2 MB, and `total_dormant` is O(islands) rather than
O(records), so holding them costs nothing per frame.

`_evict` rescans to find each victim rather than keeping a heap. That is
deliberate: it should never run, and an index maintained on every sleep
would cost more in the case that actually happens than the scan costs in
the case that does not.

### The frame budget: the ring has a cost, and it is not where it was expected

`tools/benchmarks/spawn_stress` gained `--render`, which times `ps.draw`
alongside `ps.update` and reports the pair against the 16.7 ms budget. This
is the measurement the build entry said was missing.

| live | update p50 | draw p50 | **update + draw p50** | frames over 16.7 ms |
|---|---|---|---|---|
| 104 | 5.94 | 6.99 | 12.58 | 14 / 400 |
| 155 | 6.89 | 7.59 | **13.93** | 66 / 400 (17 %) |
| 201 | 7.93 | 8.02 | **16.00** | 164 / 400 (41 %) |
| 247 | 11.82 | 8.73 | **20.96** | 551 / 600 (92 %) |

*(seed 35, lod 2, elapsed 900 s, hero jittering.)*

A real run settles around 150 live, so roughly **one frame in six is over
budget**, with p90 already past it. *(Superseded -- these figures were
measured on a contended machine. See the correction at the foot.)* `ENEMY_LIVE_CAP = 250` is no longer
reachable at 60 fps: 92 % of frames miss.

This retires the claim in the build entry above that "the objection
recorded against `ENEMY_LIVE_CAP = 250` no longer holds". It held again the
moment aggro was raised -- that measurement was update-only *and* taken
before the aggro change.

### Why: the tick LOD has been switched off by accident

| lod | update p50 at 200 live |
|---|---|
| 1 -- everyone, every frame | 6.94 |
| 2 -- the shipped value | 6.80 |
| 4 | 6.70 |

Three per cent between "every frame" and "every fourth frame". **The LOD is
doing nothing.**

`SpawningSystem.lod_eligible` exempts any body that `is_pursuing`, on the
reasoning that what the player is fighting must tick every frame. With
aggro at 880-1200 and the ring at 1400, *almost every live body is
pursuing*, so the exemption is now universal and the LOD never fires. That
is the whole of the update regression: 6.22 ms at 250 live before the aggro
change, 11.82 ms after.

### The lever, not taken here

Let the LOD apply to pursuers the player **cannot see**. A body chasing from
off screen is still chasing; stepping it at half rate is imperceptible, and
it would restore most of the saving without touching difficulty, the ring,
or the aggro ranges.

Not done, because it is a design change and the owner is mid-way through
difficulty testing -- and because the alternative (lowering
`ENEMY_LIVE_CAP`) trades the same frames for a smaller crowd, which is a
different answer to the same question and theirs to pick.

**One caveat on the draw figures.** The harness is headless and pygame
reports *no fast renderer available*, so those are software blits. The
update numbers are real; the draw numbers are likely pessimistic against a
real machine. The shape -- draw scaling with bodies in view, which went
from ~15 to 40-69 -- holds either way.

---

## The LOD fixed, and the frame-budget numbers corrected (2026-09-19)

### The fault

`SpawningSystem.lod_eligible` asked two questions -- in the padded view, or
pursuing -- and exempted a chase wherever it happened. Raising the aggro
ranges made that exemption universal: with aggro at 660-900 almost every
live body is pursuing, so almost nothing was eligible and the LOD stopped
firing whatever `ENEMY_LOD_SKIP` said.

It now asks one question: **can the player see it?** A body chasing from off
screen is still chasing, the player cannot watch it do so, and it arrives at
the same moment either way because the skipped frames are paid back in the
next tick's `dt`. Anything inside the padded view still ticks every frame,
chasing or not -- that was the half of the rule worth protecting.

### Measured on a quiet machine, two repeats each

The LOD's own contribution, 200 live, update only:

| lod | p50 |
|---|---|
| 1 -- every frame | 7.16 / 6.87 ms |
| **2 -- shipped** | **6.31 / 6.00 ms** |
| 4 | 5.80 / 5.63 ms |

About **12 %** at the shipped value, against 2 % before. Since nearly every
body was pursuing, the game had effectively been running at lod 1, so
7.0 -> 6.15 is what the fix recovers.

Update + draw against the 16.7 ms budget:

| live | update p50 | draw p50 | total p50 | p90 | over 16.7 ms |
|---|---|---|---|---|---|
| 150 | 5.7 | 6.1 | **11.5** | 13.9 | 23 / 400, 10 / 400 |
| 250 | 7.3 | 6.8 | **14.0** | 16.2 | 27 / 400, 32 / 400 |

**Back inside budget.** At ~150 live, where a run settles, about 4 % of
frames miss; at the 250 cap about 7 %.

### Correcting the entry above

The previous entry reported "one frame in six over budget" at 150 live and
92 % missed at the 250 cap, and concluded that `ENEMY_LIVE_CAP = 250` was
unreachable at 60 fps. **Those numbers were taken on a contended machine** --
three pytest processes from another session were burning some 850 s of CPU
at the time -- and they are not trustworthy.

The LOD exemption was a real fault and this is a real fix, but the gap it
appeared to close was partly contention that should have been checked for
before any of it was quoted. The lesson is cheap and worth writing down: a
timing run is only a measurement if the machine was idle, and on a box that
other sessions share that has to be verified rather than assumed.

What survives from that entry: the *shape* is right -- draw scales with
bodies in view (38 at 150 live, 54 at 250), update scales with bodies alive,
and the ring makes "everything packed near the hero" the normal case. The
absolute figures did not.

Caveat unchanged: the harness is headless with no fast renderer, so the draw
figures are software blits and likely pessimistic against a real machine.
