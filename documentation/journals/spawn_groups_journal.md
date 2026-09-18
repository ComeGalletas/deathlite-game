# Spawn groups and ranks — the spawn master picks a *company*, not a pack

Two levels of category over the roster — a **group** by social / sprite family,
and a **rank** of common or elite — and a spawn model built on them: the master
chooses a group, seats fifteen to twenty-five of it at once, and rolls elites
only if that group has any.

**Status: confirmed, not built.** The owner asked to confirm only.

---

## Requirement (owner, 2026-09-17)

> "now we need to create two types of categories, you can consider them levels.
>
> first is category by sprite grouping, you could call it by the relative
> social group. second will be simply by common and elite enemy.
>
> 1. Dark group: Husk, Blink, Imp
> 2. Goblin group: bonepicker, hexcaller, beekeeper, grudge.
> 3. Marine group: bloat, gaffjaw
> 4. Gnomes: hammer gnome, slinger
> 5. wild beasts: gorehorn, stoutpaw, turtle, bear.
> 6. swarm: skitter and stinger
>
> elite enemies will be: hexcaller, grudge, bear, gorehorn turtle.
> the rest will be considered common enemies.
>
> groups will be used to spawn enemies, this means that the spawn master will
> decide first which group to spawn, this will mean around 15 - 25 common
> enemies and if the group has elite enemies on it, the chance of spawing some
> of those enemies as elites.
>
> if the group doesnt have elites the elite check doesnt go off. each group
> should also have a variable that shows whats the minimum and maximum amount
> of enemies per group spawn. this means for example that the swarm group that
> is made of small enemies, needs a minimum of 20 enemies per spawn, while a
> big group like the wild beasts can settle for a minimum of 5 up to 20.
>
> this will also mean that some groups are more fitted for the start of the
> game and others for the end.
>
> the expectation is that dark, swarm, marine and gnomes are common groups that
> will be spawning throught the entire run, while the others that have elite
> enemies will be secondary up to a certain time thresholds that will be
> increasing as the run goes on."

## Confirmed reading

### The six groups, checked against the roster

| Group | Members | Elites in it | Available |
|---|---|---|---|
| **Dark** | Husk `skull`, Blink `thief`, Cinder `imp` | — | whole run |
| **Swarm** | Skitter `spider`, Stinger `bumblebee` | — | whole run |
| **Marine** | Bloat `bomb_fish`, Gaffjaw `harpoon_shark` | — | whole run |
| **Gnomes** | Hammer Gnome, Slinger `slingshot_gnome` | — | whole run |
| **Goblin** | Whirlspear `spear_goblin`, Beekeeper `torch_goblin`, **Hexcaller**, **Grudge** | 2 of 4 | time-gated |
| **Wild beasts** | Bonepicker `gnoll`, Stoutpaw `panda`, **Gorehorn**, **Shellback** `turtle`, **Ravager** `bear` | 3 of 5 | time-gated |

All **eighteen** combat enemies are placed and every id named exists.
`training_dummy` is not a creature and takes no group.

The owner corrected two placements immediately after the first list (2026-09-17):
**Bonepicker moves to Wild beasts** and **Whirlspear joins Goblin**. Both read
better than the first pass — the Bonepicker is a gnoll, a hyena on all fours,
and the Whirlspear is the dismounted rider of the pig-rider boss.

### The two elite-bearing groups are thin on commons

| Group | commons | of which available | elites |
|---|---|---|---|
| Goblin | 2 | 2 | 2 |
| Wild beasts | 2 | **1** | 3 |

**Wild beasts has exactly one available common enemy**, because Stoutpaw is
in the `unused` list. A company of 5–20 drawn from that group would be
Bonepickers and elites, nothing else. Either Stoutpaw comes back off the
bench, or Wild beasts needs another common, or its companies are accepted as
elite-heavy by design. Goblin is only slightly better at two and two.

### Ranks

Common is everything not listed as elite. The elite list is
**Hexcaller, Grudge, Ravager, Gorehorn, Shellback** — three of which are *not*
elite today:

| | today | proposed |
|---|---|---|
| Ravager `bear` | elite | elite |
| Grudge `troll` | elite | elite |
| Hexcaller `hex_shaman` | common | **elite** |
| Gorehorn `minotaur` | common | **elite** |
| Shellback `turtle` | common | **elite** |

This also settles a question that has been open since earlier today: Shellback
becomes an elite, which was asked for then along with **+70 HP (80 → 150)**.
That HP change is still unbuilt and belongs with this work — and it happens to
keep the potions' design rule intact, since the rare band starts at 105 base HP
and "the rare band is exactly the `is_elite` enemies". **Hexcaller (64) and
Gorehorn (55) do not clear 105**, so making them elite breaks that rule unless
their HP moves or the rule does. Called out under open questions.

### The spawn model

1. The master picks a **group** — not a type.
2. It seats a **company** of that group: a count drawn from the group's own
   `[min, max]`, in the region of 15–25.
3. If the group holds elites, it rolls for how many of the company are elites.
   If it holds none, **the elite roll does not happen at all** — not a roll
   that always fails, but no roll.
4. Groups without elites are available for the whole run. Groups with elites
   are gated behind time thresholds that move as the run goes on.

Per-group counts are the group's own knob, sized to the bodies in it: Swarm is
made of 5–10 HP fliers and wants **20 minimum**; Wild beasts are large bodies
and **5 to 20** is plenty. That knob is also what makes some groups read as
early-run and others as late.

---

## What this replaces, and why it is not a small change

The current model is the opposite shape in every dimension. Today the director
emits **one pack of 1–4** every ~30–80 ms from a per-band weighted list of
*types*, with a flat per-band elite chance. The proposal is **one company of
15–25** of a single family, occasionally, with elites decided per group.

Five things follow, and each is real work rather than a re-tune:

**1. The phase bands stop being the unit of composition.** `phases[].types` —
the weighted type list per band — is what a group now replaces. The bands
might survive as the *time* axis (which groups are unlocked, how many elites),
but their `types` maps do not survive as-is. The seven-band rework the owner
asked for earlier is superseded by this and should be folded into it rather
than built first.

**2. The cadence has to be rebuilt, not re-tuned.** The director's interval
lerp, `pacing.base` (15), and the pack-size table all assume small frequent
packs. At 20 bodies an emission the same cadence would be thousands of enemies
a second against a live cap of 250. The interval becomes seconds-to-tens-of-
seconds between companies, and `pacing` — which currently scales that interval
by the run's condition — needs re-deriving against the new unit.

**3. Placement is the hard part.** Seating twenty bodies *together* is not what
`spawn/placement.py` does: it picks one point for a leader and rings the
followers around it, dropping any that will not fit. The zone offers ten points
per terrace on a 3 s cooldown, and the S10 measurements showed the strict rung
is often empty even for a pack of three. A company of twenty needs either a
much larger multi-point seating strategy or a deliberate "arrive spread across
the island" model. **This is the piece most likely to decide whether the whole
idea feels good**, and it is worth prototyping before the data shape is fixed.

**4. The live cap is the ceiling the companies live under.** `ENEMY_LIVE_CAP`
is 250, but the time-growing cap starts at 100 and adds 5 every 20 s, so it
only reaches 250 at 600 s. A 25-body company is a quarter of the early cap in
one emission. Either the cap curve changes with this, or early companies are
clipped by `min(pack, cap - active)` and arrive short.

**5. Two tables collide on the word "group".** `spawn_tables.json` already has
a `groups` section — `husk_pack`, `runners`, `swarm`, `warband`, `brute`,
`artillery` — leader/follower templates for `SpawnMaster.spawn_group()`, which
has **no production caller** and one of which is literally named `swarm`. The
new concept needs either a different key (`families`? `companies`?) or those
templates retired as part of this.

### Smaller consequences, noted so they are not surprises

- **The pinned S2 director fixture dies.** `tests/spawn/director_sequence.json`
  replays 1,417 draws per difficulty from the current model. Nothing about it
  survives a change of unit, and it has been wound back twice already
  (`ramp_seconds`, the elite chances, `unused`). This is where that proof ends.
- **The `elites` table cannot express this.** It is
  `{default, rare, rare_chance}` — a single coin flip between two ids. Elites
  become a property of a group's membership plus a per-group chance.
- **Stoutpaw is currently benched** in the `unused` list — see the table
  above; it leaves Wild beasts with a single available common.
- **Residents** (an island's first population) roll off the director's current
  phase. They would presumably seed a company instead.
- **`summoner` and `exploder`** have no shipped user; unrelated, but this is
  the natural moment to decide their fate.

---

## Answered (owner, 2026-09-17)

**1. Stoutpaw comes off the bench.** It is a common enemy, so `panda` leaves
the `unused` list. Wild beasts then has two available commons (Bonepicker,
Stoutpaw) against three elites, and the `unused` category is left with no
members — which is fine; it is a mechanism, not a list that has to be full.

**2. `is_elite` becomes the only definition of elite, everywhere.** The HP
threshold is retired as a *rule*, not just re-tuned. Concretely that means
`potions.enemy_rarity()` stops deciding the **rare** band from
`enemy_rarity_hp` and reads the enemy's `is_elite` tag instead. Two knock-ons:

* `enemy_rarity(base_hp, table)` takes HP and nothing else, so it needs the
  enemy (or its flag) passed in. Its three call sites and `roll_rarity` move
  with it.
* Only the **rare** band is tag-driven. `common` vs `uncommon` still has to
  come from somewhere, and the `uncommon: 45` HP bound is the only thing
  offering — so the reading is *rare ⇔ `is_elite`; below that, HP still splits
  common from uncommon*. Flagged rather than assumed silently.

This removes the Hexcaller / Gorehorn problem entirely: they become elite by
tag at 64 and 55 HP and no threshold objects. `test_the_rare_band_is_exactly
_the_elite_enemies` stops being a check on a coincidence and becomes the
implementation.

**3. A company is one family.** Only its own group's members.

**4. Time drives both** — which groups are unlocked *and* the elite rate
within them. Basic rates to start; tuned later.

**5. The old `groups` section is renamed**, freeing the word for the new
concept. `husk_pack` / `runners` / `swarm` / `warband` / `brute` / `artillery`
are leader-follower templates with no production caller; they keep existing
under another key.

**6. Arrival differs by group.**

| Arrival | Groups |
|---|---|
| **All at once**, chasing immediately | Swarm, Goblin, Marine, Gnomes |
| **In waves** | Dark, Wild beasts |

Worth noting the shape this gives: the two at-once groups that are cheap
(Swarm, Gnomes) read as a rush, while Goblin arrives at once *with elites in
it*. Wild beasts — the biggest bodies and the most elites — trickles.

### The cooldown between companies

The master waits between companies, and the wait is set by the group it
**last** spawned, not the one it is about to:

| Last company | Normal cooldown |
|---|---|
| none yet (run start) | none — pick anything |
| a group with no elites | **5 s** |
| a group holding elites | **15 s** |

Scaled by difficulty; normal is the baseline above.

That is a real rate, and it is worth writing down what it implies: a
non-elite group of 15–25 every 5 s is **3–5 enemies a second sustained**,
which sits comfortably under the ~17/s placement ceiling measured in S10 and
fills an empty 100-cap in roughly half a minute. An elite group every 15 s is
1–1.7/s. So the elite groups are not just rarer, they are a third of the
pressure — the cooldown is doing double duty as a pacing knob.

---

## Refined (owner, 2026-09-17)

Three of the earlier answers were sharpened, two of them reversing a reading:

### Elites get their own count

A group carries **two** spans, not one:

* `commons: [min, max]` — the 15–25 figure, as before;
* `elites: [min, max]` — only on groups that have elites.

A group with elites always spawns **at least `min`** of them, and the number
climbs toward `max` as the run goes on. So elite groups are not "sometimes an
elite appears" — they are *guaranteed* elites, growing. Combined with the
company being all-at-once, a late-run Wild beasts arrival is a real event.

### The enemy taxonomy is elite / non-elite, and potions keep their HP check

This reverses half of the previous answer, and the reversal is the useful part
to record. Enemies are now only **elite** or **non-elite** — the common /
uncommon *enemy* tiering is gone. But potions **keep deciding their own
rarity from HP exactly as they do today**: `progression/potions.py` is
untouched, and `enemy_rarity_hp` keeps its `uncommon: 45` / `rare: 105`
bounds.

The consequence is that **the design rule linking them is retired**.
`test_the_rare_band_is_exactly_the_elite_enemies` asserts "a potion's rare
band is exactly the `is_elite` enemies", and its docstring says that if it
breaks, *the bounds* should move rather than the test. That is no longer the
design: three of the five new elites sit below the 105 bound —

| | hp | vs the 105 rare bound |
|---|---|---|
| Hexcaller | 64 | below |
| Gorehorn | 55 | below |
| Shellback | 80 | below (150 once it gains its +70) |
| Ravager | 125 | clears |
| Grudge | 290 | clears |

— so that test must be **removed, not re-pinned**. Potion rarity and enemy
rank are simply independent axes now: a tough enemy drops better potions, an
elite is an elite, and they no longer have to agree. Worth deleting the rule
deliberately rather than letting the test fail and get patched.

### The cooldown shortens with the run

Every **2 minutes**, both cooldowns drop by **1 second**:

| minute | non-elite | sustained inflow | elite | sustained inflow |
|---|---|---|---|---|
| 0 | 5 s | 3.0–5.0 /s | 15 s | 0.3–1.3 /s |
| 2 | 4 s | 3.8–6.2 /s | 14 s | 0.4–1.4 /s |
| 4 | 3 s | 5.0–8.3 /s | 13 s | 0.4–1.5 /s |
| 6 | 2 s | 7.5–12.5 /s | 12 s | 0.4–1.7 /s |
| 8 | 1 s | 15–25 /s | 11 s | 0.5–1.8 /s |
| 10 | **0 s** | unbounded | 10 s | 0.5–2.0 /s |

(inflow assumes a 15–25 company; elite rows assume 5–20.)

**Two things fall out of that table and both need a decision:**

1. **It reaches zero.** At ten minutes the non-elite cooldown is 0 s, which is
   not a cooldown — the master would emit a company every frame. It needs a
   floor (1 s? 2 s?), or the ladder needs to stop stepping.
2. **It outruns placement before then.** The S10 measurement puts the seating
   ceiling around **17 enemies/s**. The 1 s rung asks for 15–25/s, so from
   about minute eight the cooldown stops being the limiter and placement
   does — companies start arriving short or late whatever the data says.

Neither is a reason not to do it; both are reasons the last rungs want
choosing rather than extrapolating.

### Arrival is uniform

The waves idea is dropped. **Every company spawns all its enemies at once**;
what happens next is each enemy type's own behaviour — the Swarm rush because
Skitters and Stingers are fast, the Wild beasts lumber because Shellbacks are
slow. That is a simplification worth having: no per-group arrival mode to
implement, and the difference still reads because the bodies differ.

---

## The cap gate (owner, 2026-09-17)

The cooldown floors at **1 s** for non-elite groups, and the live cap becomes
the other half of the pacing:

1. The master **prepares** the next company — picks the group, counts its
   bodies — before it tries to seat it.
2. If that count fits under the live cap, it spawns.
3. If it does not, it **waits 2 s and asks again**, repeating until it fits.

All of it on the **internal clock** — the in-game elapsed time the HUD shows,
which pauses with the game, the same clock `enemy_count_cap()` already reads.
Never wall clock.

### Companies are atomic

This is the part that changes existing behaviour rather than adding to it.
Today `SpawnDirector.update` does `min(pack, cap - active)` — a pack that does
not fit **arrives short**. Under this rule a company that does not fit
**does not arrive at all** until it does. A Swarm of twenty is twenty or
nothing.

That clipping has to be removed, not just bypassed, or a company would still
be silently truncated on the way through.

### What the gate actually paces

The cap is the time-growing one, not the flat 250: it starts at **100** and
adds 5 every 20 s up to `ENEMY_LIVE_CAP`.

| minute | live cap | a 20-body company is |
|---|---|---|
| 0 | 100 | 20 % of it |
| 4 | 160 | 12.5 % |
| 8 | 220 | 9.1 % |
| 10 | 250 | 8 % |

Early on, a company is a fifth of everything allowed on the field — so the
gate bites hardest at the start, exactly where the cooldown is longest. The
two knobs pull the same way rather than fighting.

Late, they invert. At the 1 s rung the master wants 15–25 bodies a second,
which no cap growth can absorb, so **the 2 s retry becomes the real clock**:
the field pins at the cap, and a new company lands only once the player has
cleared roughly a company's worth. That is the "keep the player busier"
behaviour asked for, and it is self-limiting — pressure rises until the player
is the bottleneck, then holds there.

It also gives the late run a distinct **rhythm**: clear about twenty, receive
about twenty. Unlike the current trickle, the field refills in visible chunks.

### Two properties worth knowing before they surprise someone

**Head-of-line blocking is possible.** The company is prepared *before* the
wait, so a queued 20-body Wild beasts sits there while a 15-body Marine that
would have fit is never considered. Probably fine — the group is committed and
the delay is the point — but it is a choice, not an accident, and it means the
larger groups are naturally rarer late when headroom is tight.

**A stalled gate is not a quiet game.** Waiting means the field is *full*, so
the player is not starved of enemies, only of new ones. No lull rule is needed
to cover it.

---

## The two ladders, and how a group is chosen (owner, 2026-09-17)

### Two timers, not one

The earlier "the last group sets the next cooldown" reading was too coarse.
There are **two independent timers**, and the elite one is a *gate on
eligibility* rather than a pause on everything:

* a **common cadence** — how long before the next company of any kind;
* an **elite gate** — elite-bearing groups are only eligible when it is ready.

At the run's start the elite gate is 15 s, so for the first fifteen seconds
the master can only pick from Dark, Swarm, Marine and Gnomes. When the gate
opens, an elite group becomes choosable; spawning one resets its gate to the
gate's current length. Because that length shrinks 15 -> 3, **elite groups get
more frequent the longer the run goes**, which is the whole point.

### The ladders (normal, stepping every 2 minutes)

| minute | common cadence | elite gate | elite `min` bonus |
|---|---|---|---|
| 0 | 5 s | 15 s | +0 |
| 2 | 4 s | 12 s | +1 |
| 4 | 3 s | 9 s | +2 |
| 6 | 2 s | 6 s | +3 |
| 8 | **1 s** (floor) | **3 s** (floor) | +4 |
| 10 | 1 s | 3 s | +5 |
| 12 | 1 s | 3 s | +6 |

The elite gate falls **three times as fast** as the common cadence (-3 vs -1)
and floors three times higher (3 s vs 1 s). Read together that is a deliberate
shape: elite groups start almost absent and end only three times rarer than
common ones — from one elite company per three common ones at the start, to
roughly one in three by minute eight.

### The elite count climbs on the same steps

Every 2 minutes a group's elite **minimum** rises by 1, capped at that group's
`max`. So a group declaring `elites: [1, 5]` guarantees one elite at the start
and five from minute eight on — the count is drawn from
`[min + steps, max]`, not re-rolled from the base each time.

Both levers therefore push the same way late: elite groups arrive more often
*and* carry more elites.

### Difficulty

Everything time-shaped divides by `timeline_pace`, the factor that already
divides `run_duration` and `ramp_seconds` — so the whole ladder compresses
rather than just its values:

| | step | start (common / elite) | floor |
|---|---|---|---|
| normal | 120 s | 5 / 15 s | 1 / 3 s |
| fast | 96 s | 4 / 12 s | 0.8 / 2.4 s |
| super_fast | 80 s | 3.33 / 10 s | 0.67 / 2 s |

Confirmed by the owner: `timeline_pace` compresses the **2-minute step as
well** as the cooldown values, so the whole ladder scales together. Spawning
an elite group also resets the common cadence — confirmed — so an elite and a
common company never land back to back.

---

## Settled (owner, 2026-09-17)

### Company sizes

| Group | commons | elites |
|---|---|---|
| Dark | 5-30 | - |
| Marine | 5-30 | - |
| Gnomes | 5-30 | - |
| Goblin | 5-30 | **2-15** |
| Swarm | 20-? | - |
| Wild beasts | 5-20 | **1-13** |

### Selection

* **Which group**: random, and the two pools are **separate** - when the elite
  gate is open the master draws from the two elite groups, otherwise from the
  four common ones.
* **Which members**: per-member **weights**, kept from the band model, for
  commons *and* elites alike.
* **Hard unlock**: no elite group at all before **1 minute**; after that the
  gate ladder applies as described.

### What comes out

* **`phases` and `ramp_seconds` are removed.** The 2-minute step is the only
  time axis left.
* **`pacing` is removed entirely** - the 5-second cooldown replaces it.
  `spawn/pacing.py`, the `pacing` table section, `SpawnMaster.pressure` and
  its modifiers all go with it.
* **`spawn_rate` stops applying to spawns**; `timeline_pace` is the only
  difficulty factor the ladder reads.
* **The old `groups` templates are deleted**, freeing the key outright rather
  than renaming it.
* **`elites` (`default` / `rare` / `rare_chance`) goes too** - elite
  membership is now a property of a group.

### Residents

An island's first company is chosen and placed like any other, immediately on
arrival. No separate seeding path.

---

## Proposed weights, for review

The bands' weights are not flat and should not become flat, so here is a
starting set, normalised within each group. These are mine, not the owner's -
they need a look.

| Group | member | weight | share |
|---|---|---|---|
| **Dark** | Husk | 5 | 50 % |
| | Blink | 3 | 30 % |
| | Cinder | 2 | 20 % |
| **Swarm** | Skitter | 6 | 60 % |
| | Stinger | 4 | 40 % |
| **Marine** | Bloat | 5 | 50 % |
| | Gaffjaw | 5 | 50 % |
| **Gnomes** | Hammer Gnome | 6 | 60 % |
| | Slinger | 4 | 40 % |
| **Goblin** | Whirlspear | 6 | 60 % |
| | Beekeeper | 4 | 40 % |
| | *elite* Hexcaller | 7 | 70 % |
| | *elite* Grudge | 3 | 30 % |
| **Wild beasts** | Bonepicker | 5 | 50 % |
| | Stoutpaw | 5 | 50 % |
| | *elite* Gorehorn | 4 | 40 % |
| | *elite* Shellback | 4 | 40 % |
| | *elite* Ravager | 2 | 20 % |

The reasoning, so the numbers can be argued with rather than just replaced:
Husk leads Dark because it is the plainest body and Cinder's burning ground is
the loudest thing in that group; the Beekeeper is held under its group-mate
because every one of them adds three more bees on top of the company; and
Grudge and Ravager are held down among the elites because at 290 and 125 HP
they are the two that most change a fight on their own.

---

## How many elites: a per-group step (owner, 2026-09-17)

The `int(max / x)` formula is **dropped**. What replaces it is the thing that
was already doing the work: a step on the minimum, now a per-group knob.

```
steps = elapsed // (120 s / timeline_pace)
count = min(base_min + elite_step * steps, max_elites)
```

The count is **deterministic**; the randomness is in *which* elites are drawn,
by the group's weights. `max_elites` is a ceiling, not a target.

| Group | elites | `elite_step` | ladder (minute 0, 2, 4, ...) |
|---|---|---|---|
| Goblin | [2, 15] | 2 | 2, 4, 6, 8, 10, 12, 14, 15 |
| Wild beasts | [1, 13] | 2 | 1, 3, 5, 7, 9, 11, 13 |

Wild beasts stays odd - it starts at 1 and the owner is happy with that, so
the two groups read differently rather than in lockstep.

### Why the formula was dropped

It could not produce an even ladder at all. To get 2, 4, 6, 8 from
`int(15 / x)`, `x` must land in `[5, 7.5)`, then `[3, 3.75)`, then
`[2.14, 2.5)`, then `[1.67, 1.88)` - and the gaps between those windows
*shrink* (1.25-4.50, then 0.50-1.61, then 0.27-0.83), so no constant step fits
all three. A brute force over every `starting_x` from 1 to 60 against every
step from 0.05 to 10 found **zero** matches. That is inherent to the shape:
`int(max / x)` with a linear `x` is a hyperbola, so its steps accelerate. It
can pass through any single value but never as an evenly spaced sequence.

With the step doing the work, `starting_x` had nothing left to do.

### Two properties worth knowing

**The maxes are out of reach in a normal run.** Goblin needs 7 steps (14 min)
to reach 15 and Wild beasts 6 (12 min) to reach 13, while the boss arrives at
9:30. So `max_elites` is a safety rail for an overlong run rather than a
number the player will meet - which is fine, but it means tuning the *step*
changes the game and tuning the *max* mostly does not.

**Every difficulty reaches the same elite count at its boss.** The step period
scales by `timeline_pace` and so does the boss time, so the two cancel exactly:

| | step | boss at | steps | Goblin at boss |
|---|---|---|---|---|
| normal | 120 s | 570 s | 4 | 10 |
| fast | 96 s | 456 s | 4 | 10 |
| super fast | 80 s | 380 s | 4 | 10 |

Harder difficulties do not end up with *more* elites; they get the same number
in less time, which is still harder - more elites per second, and less room to
clear between companies. Worth stating because "scale the step by pace" sounds
like it should raise the ceiling and does not.

---

## Still to decide


Everything above is settled. What follows is what a build would have to invent
if it started now, grouped by whether it blocks the work.

### Resolved

How many elites a company carries is settled above: a deterministic count from
the per-group step, with `max` as a ceiling. The earlier worry - that a
minute-one Goblin company could roll fifteen elites - cannot happen: minute
one is exactly two.

**Swarm's maximum is also unset** - it has a minimum of 20 and no ceiling.
`[20, 30]` matches the other groups' upper bound; taken unless told otherwise.

### Still open

**Placement for twenty bodies** — still unprototyped, still the piece most
likely to decide whether this feels good.

**The cap check is a single gate.** A company that fits when checked is
seated whole; nothing re-checks between bodies. Assumed fine because the
master is the only spawner, but worth stating.

**Live difficulty switching.** The dev menu changes difficulty mid-run and
the ladder is difficulty-scaled — the timers presumably re-key immediately,
like `SpawnDirector.set_difficulty` already does.

**Does the 1-minute hard unlock scale by `timeline_pace` too?** Everything else
time-shaped does, which would give 48 s and 40 s. Assumed yes.

**`stat_multipliers` survives untouched.** The HP/speed ramp reads
`_base_run_duration` and `stat_ramp_pace`, neither of which this model changes.
Nothing to decide, but it is the one piece of the director that outlives
`phases` and is worth not deleting by association.

**The S2 director fixture ends here.** `tests/spawn/director_sequence.json`
replays the old unit and cannot survive; it has been wound back three times
already. Retire it with `phases` rather than trying to re-record it.


### Consequence worth noting rather than deciding

Five enemies currently cannot spawn at all — Bonepicker, Gaffjaw, Hammer
Gnome, Whirlspear, Cinder — because they have no band weight. **Under the
group model they all spawn the moment their group is picked**, with no band
edit. That was the original argument for categories and it still holds; it
also means the model arrives with five enemies that have never been seen in a
real run.

---

---

## Todo

Revised after G0. Ordered so each step lands on a green suite where it can.
The surface was measured, not guessed: the symbols that disappear touch 9
production files and 8 spawn test modules.

### G0 - Placement *(measured; the build remains)*

- [x] Measure the current placement at company scale - caps near 24, stacks
      badly, because `ring` uses one circle and never checks body vs body
- [x] Measure multi-point (scatters to 5400 px) and anchor-cluster (cohesive
      but capped near 17 by spawn-point density)
- [x] Measure concentric packing - 40 small bodies around **one** point inside
      250 px, zero overlaps
- [x] Measure random scatter (fills worse, especially on awkward ground) and
      jittered concentric (full fill, not banded)
- [x] **G0a - the packer.** Done: `Placement.pack` replaces
      `Placement.ring`. Concentric rings sized for the largest follower,
      each body jittered up to `pack_jitter` of a cell, radius derived as
      `start + step * pack_spread * sqrt(n)` under `pack_max_radius`. Both
      guarantees kept and one added - a candidate must also be clear of
      every body already seated. Measured: 40 small bodies seat whole with
      zero overlaps inside 174 px, Wild beasts at its real size (20, or 26
      with elites) seats whole at every anchor, ~2 ms per company
- [x] **G0b - the stagger.** Done: `company_stagger` 0.35 s, 0 still a
      supported value. Positions and the point decided up front; the cap
      gate moved to `_cap_room`, settled once per company, with bodies in
      flight counting as live so nothing overshoots. Only the director's
      companies stagger. Measured over 180 s of real run: no frame landed
      more than one body, and live + in-flight never passed the cap

### G1 - Roster changes that stand alone

Independent of the spawn model; can land green on their own.

- [x] `spawn_tables.json`: `unused` -> `[]` (Stoutpaw back)
- [x] `enemies.json`: `is_elite` on `hex_shaman`, `minotaur`, `turtle`;
      `turtle.hp` 80 -> 150
- [x] Deleted `test_the_rare_band_is_exactly_the_elite_enemies`, not
      re-pinned. Also had to rewrite `test_uncommon_enemies_can_drop_all_three`
      (it named the turtle as its uncommon exemplar) and
      `test_unused_category.py` (emptying the list made it vacuous)
- [x] Audited: six things ride on `is_elite`, and the 18 % item drop is the
      one that matters - elite share of bodies 28.8 % -> 48.8 %, item income
      +69 %, kill gold +15.5 %. Left alone deliberately; **balance call for
      G6**

### G2 - The new tables

- [ ] `groups`: six entries with `members` (id -> weight), `commons:
      [min, max]`, and where present `elites` (id -> weight),
      `elite_range: [min, max]`, `elite_step`
- [ ] `cooldowns`: common 5, elite 15, decay 1 / 3, floors 1 / 3,
      `step_seconds` 120, `elite_unlock` 60, `cap_retry` 2
- [ ] `company_stagger`
- [ ] Delete `phases`, `ramp_seconds`, `elites`, `pacing`, old `groups`
- [ ] `SpawnTables`: parse and validate; drop `phase_at`, `phases()`,
      `group()`, `ramp_seconds`, `elites`, `pacing`. Validation: member ids
      exist, weights > 0, `min <= max`, a group's elites are all `is_elite`
      and its commons are not, `elite_step >= 1`, no group empties once
      `unused` is filtered

### G3 - The director

Keep `enemy_count_cap`, `stat_multipliers`, `boss_time`, `should_spawn_boss`,
`set_difficulty`, `live_cap`. Remove `_ramp`, `_phase`, `_interval`,
`roll_pack`, `roll_elite`, `_roll_slots`, and the `min(pack, cap - active)`
clipping. Add:

- [ ] the two cooldown ladders, stepped on `120 / timeline_pace`
- [ ] the 1-minute elite hard unlock (`60 / timeline_pace`)
- [ ] group choice: random within the eligible pool, pools separate
- [ ] composition: commons by weight, elites by the step ladder and weight
- [ ] the cap gate: prepare -> count -> spawn if it fits, else retry in 2 s,
      on the in-game clock
- [ ] `spawn_rate` stops being read here

### G4 - The master

- [ ] Delete `spawn/pacing.py`; drop `Pacing` from `spawn/__init__.py`
- [ ] Remove `self.pacing`, `pressure`, `set_modifier` / `clear_modifier` /
      `modifiers`, the two subscriptions that only fed pacing, `spawn_group`
- [ ] `update()` drives the director with plain `dt`
- [ ] `_place_pack` becomes company seating on G0a, plus the G0b release queue
- [ ] `_seed_residents` places a chosen company immediately
- [ ] Drop the `pressure` dev metric (`core/state.py`) and the modifier
      control (`dev_menu_state.py`)

### G5 - Tests

Deletions - what they pin no longer exists:

- [ ] `tests/spawn/test_pacing.py`, whole module
- [ ] `director_sequence.json` and the S2 sequence test. It replays the old
      unit and has been wound back three times; this is where that proof ends
- [ ] The phase / interval / ramp / elite-slot tests in `test_budget.py` and
      `test_tables.py`
- [ ] `spawn_group` and pressure / modifier tests in `test_master.py`

Rewrites:

- [ ] `test_unused_category.py` - it benches Stoutpaw and drives `roll_pack`;
      point it at a synthetic table so the mechanism is still covered with the
      list empty
- [ ] `test_data_integrity.py` - band and elite-slot checks move to groups;
      add "every member exists and is on the right side of `is_elite`"
- [ ] `fakehost.py`, `test_population.py`, `test_watchdog.py` build a
      `SpawnDirector` - check the constructor calls still hold

New coverage:

- [ ] ladders step, floor, and scale by `timeline_pace`
- [ ] no elite group before the hard unlock, one immediately after
- [ ] pools stay separate while the gate is shut
- [ ] a company is one family, sized in its span, weighted, elite count per
      the ladder
- [ ] the cap gate waits and retries, and the company **arrives whole rather
      than clipped** - the behaviour replacing the old truncation
- [ ] residents place a company on first visit

### G6 - Balance pass

- [ ] Only once it runs. Five never-seen enemies enter play at once here and
      the weights are proposals; expect to re-tune

---

## Risks worth naming

**G0 is a real gate, not a formality.** If twenty bodies cannot be seated
together, the model needs an arrival shape it does not currently have.

**Everything lands at once.** The bands, the pacing, the elite slot and five
unseen enemies all change in one step, so a bad feel will be hard to
attribute. Landing G1 separately helps a little; there is no way to land the
rest incrementally, because the old and new models cannot both drive the
director.

**The suite will go red in the middle.** G2-G4 remove what eight spawn test
modules assert. The intermediate states are not green, which is unusual for
this project - worth doing on a branch.

---

## G0 result: the model is viable, and the fix is one function

Measured on a real booted run, pinned world, two minutes in - 7 islands in the
zone, 160 spawn points, live cap 130. Four seating strategies, companies of 5
to 40 `skull` bodies.

### What the current placement does

| want | got | spread | overlapping pairs |
|---|---|---|---|
| 5 | 5 | 28 px | 0 |
| 10 | **8** | 45 px | 0 |
| 20 | 20 | 28 px | **19** |
| 30 | **24** | 33 px | **63** |
| 40 | **24** | 40 px | **75** |

It caps out near 24 and stacks badly. The cause is in `Placement.ring`: every
follower goes on a **single circle** of radius `leader + follower + ring_gap`,
and each candidate is tested with `is_walkable` - terrain only, never against
the bodies already placed. Twenty bodies on a 34 px circle have about 214 px
of arc to share and need 800.

### Naive multi-point: solves stacking, destroys the company

Splitting the company over successive `_place_pack` calls never stacks, but
each call re-picks from the whole zone, so the "company" lands across the
world:

| want | got | spread |
|---|---|---|
| 10 | 10 | 1056 px |
| 20 | 18 | 2074 px |
| 40 | 35 | **5424 px** |

The camera's half-diagonal is 612 px. At 5424 the group is confetti across
several islands, which is not what a company is.

### Anchor plus nearest points: cohesive, but the points run out

Anchoring on one point and filling its island's nearest points keeps the group
together (spread 185-477 px) and never stacks - but it is capped by how many
spawn points sit near each other:

| within | spawn points near a point, same island |
|---|---|
| 300 px | min 1, **median 2**, max 8 |
| 500 px | min 1, **median 3**, max 12 |
| 800 px | min 1, median 7, max 17 |

At 4 bodies a point and a median of 3 points, a typical neighbourhood holds
about 12. Measured: 20 wanted gave 10, 40 wanted gave 17. **Spawn point
density, not placement logic, is the ceiling here** - and raising
`SPAWN_POINTS_PER_FLOOR` means regenerating every world and invalidating the
pinned-seed tests.

### The answer: pack properly around one point

Concentric rings outward from a single point, spaced by the bodies' own
diameter, each candidate checked against the terrain **and against the bodies
already down**:

| body | within 150 px | within 250 px |
|---|---|---|
| Stinger r9 | min 22, median 38 | **40** (the test's ceiling) |
| Husk r10 | min 19, median 37 | **40** |
| Shellback r24 | min 3, median 7 | min 9, median 20 |

A forty-body company of small bodies fits around **one** spawn point inside
250 px - comfortably within a screen - with **zero** overlaps. No extra spawn
points, no worldgen change, no multi-point cohesion problem.

### What this means for the build

**G0 passes.** The company model does not need a new arrival architecture; it
needs `Placement.ring` replaced by a packer. That is a contained change to one
function with its own tests, and it improves today's 2-4 body packs too.

Two caveats worth carrying forward:

* **Large bodies need more room.** Shellback (r24) fits a median of 20 within
  250 px, and Wild beasts is the group full of them - 20 commons plus a
  growing elite count. It will need a wider radius or a second point. That is
  a knob (`pack_radius` per group, or derived from the bodies), not a
  redesign, and Wild beasts is the group that should feel spread out anyway.
* **The packer must keep the existing guarantees.** The current ring only ever
  offers walkable spots and `_place_pack` still checks the cap per body; the
  replacement has to keep both, plus the terrace-margin and clearance rules
  that make a spot legal in the first place.

### A bigger ring, filled randomly (owner, 2026-09-17)

> "the placement ring can be bigger but enemies about to spawn can be placed
> randomly at different intervals inside this ring, this can allow for enemies
> to avoid spawning on top of each other at the exact time and allow room for
> different topographies"

Measured against the concentric packer on the same 16 real anchors. **Pure
random scatter fills worse**, and the gap is widest on exactly the awkward
ground it was meant to help with:

| | concentric | scatter |
|---|---|---|
| Husk r10, 40 wanted in 250 px | 40 / 40 / 40 | 32 / 40 / 40 |
| Shellback r24, 32 in 250 px | 9 / 19 / 32 | 8 / 18 / 31 |
| Shellback r24, 32 in 400 px | 26 / **32** / 32 | 17 / **28** / 32 |

*(min / median / max over the anchors.)* On the four worst anchors, concentric
got 26, 30, 32, 32 against scatter's 17, 17, 32, 26. Rejection sampling spends
its tries on unwalkable spots; the ring walks outward and finds the pockets.

**But the instinct behind the idea is right**, and the measurement above does
not capture it: a pure concentric fill lays bodies out in *visible circles*.
That is what "different intervals" is really asking for, and the fix is to
keep the rings as the skeleton and jitter each body inside its own cell:

| Husk r10, 40 in 250 px | got | ring-pattern score |
|---|---|---|
| no jitter | 40 / 40 / 40 | 0.00 (banded) |
| **jitter 0.35** | **40 / 40 / 40** | **0.22** |
| jitter 0.6 | 40 / 40 / 40 | 0.33 |

| Shellback r24, 32 in 400 px | got | ring-pattern score |
|---|---|---|
| no jitter | 26 / 32 / 32 | 0.00 |
| **jitter 0.35** | **27 / 32 / 32** | **0.39** |
| jitter 0.6 | 25 / 32 / 32 | 0.41 |

Jitter costs **nothing** in fill - at 0.35 the large-body worst case even
improves, because a nudged candidate can find ground the exact spot missed.
Past 0.35 the return flattens and the fill starts to slip.

**Settled**: rings as the skeleton, each body placed at a random offset within
its cell, radius sized by the company and the bodies - about 250 px for small
bodies and 400 px for large ones, rather than today's fixed 34.

### The other half of "at the exact time"

"Avoid spawning on top of each other **at the exact time**" also reads as a
*timing* idea, and it is a good one independent of placement: forty bodies
appearing on one frame is a pop, however well spaced they are. Staggering a
company over a few tenths of a second would let it materialise rather than
blink in, and the spawn burst effect already exists per body
(`spawn_veiled`).

**Settled (owner, 2026-09-17): both, and the data decides.**
`company_stagger` is a knob in seconds; at **0 the whole company lands on one
frame**, which stays a supported and expected setting rather than a
degenerate one.

How it works, given the rest of the model:

* every position is computed **up front**, by the packer, so a staggered
  company still never overlaps itself and still knows its own size;
* the **cap gate is still checked once**, before any body lands - a company
  that fits is committed whole, which is what "atomic" already meant;
* the master then holds the company and releases its bodies across
  `company_stagger`, oldest first.

**One tension worth naming rather than hiding.** A per-group stagger is a mild
version of the waves idea that was deliberately dropped - Swarm at 0 rushing
in while Wild beasts trickles over a second is exactly "arrival differs by
group" wearing a different hat. The difference is that this one is a single
number rather than an arrival *mode*, and 0 is a first-class value. Proposed
as a **global** knob with a per-group override left unused for now; say if it
should be per-group from the start.

### Revised G0 todo

- [x] Measure the current placement at company scale
- [x] Measure multi-point and anchor-cluster alternatives
- [x] Measure concentric packing around one point
- [x] Measure random scatter vs concentric, and jittered concentric
- [x] Wild beasts re-measured (r24, 32 bodies: 400 px radius, median 32 seated)
- [ ] Replace `Placement.ring` with the jittered packer, with tests: N bodies
      land, none overlap, all walkable, radius grows with body size and
      company size, jitter never costs fill, degrades gracefully when the
      ground runs out
- [ ] Decide `company_stagger` - whether a company materialises over a few
      tenths of a second rather than on one frame

---

---

## G0a built: `Placement.pack` (2026-09-17)

`Placement.ring` is gone. In its place `Placement.pack(centre,
leader_radius, follower_radii, is_walkable, rng)` keeps the old contract --
one position per follower, in the order given, `None` where nothing fits --
and changes how those positions are found.

**The skeleton.** Concentric rings outward from the leader. The first clears
it by the largest follower plus `pack_gap`; each ring after that is one body
diameter further out, and the slots on a ring are spaced by the same
diameter. Rings are sized for the *largest* follower, which is what makes
the order the bodies arrive in stop mattering: a heavy coming last still
fits any slot that is free.

**The jitter.** Each body is nudged a random direction and up to
`pack_jitter` of a cell, retried `pack_tries` times, with the exact slot as
the fallback. This is what the owner asked for - "placed randomly at
different intervals inside this ring" - and the measurement said it is free.

**The two checks.** A candidate is taken only if it is clear of every body
already seated, *the leader included*, and walkable for its own radius. The
second was all the old circle ever did, which is precisely why it stacked.
Bodies are tested first because they are arithmetic and the crowded middle
of a company is where most candidates die; the terrain test is the grid
lookup and goes second.

**The radius is derived, not fixed.** `start + step * pack_spread * sqrt(n)`,
capped at `pack_max_radius` and floored at two rings. The floor is there so
a blocked first choice can still be retried wider, the way the old
`1.6 x` retry did. Everything is a knob in `spawn_tables.json`'s `placement`
section: `pack_gap` 8 (the renamed `ring_gap`), `pack_jitter` 0.35,
`pack_tries` 3, `pack_spread` 1.4, `pack_max_radius` 420.

### Measured on the shipped code, booted run, pinned world, 16 real anchors

| company | seated (min / median / max) | overlaps | unwalkable | reach | cost |
|---|---|---|---|---|---|
| Stinger r9 x 40 | 40 / 40 / 40 | 0 | 0 | 159 px | 1.8 ms |
| Husk r10 x 40 | **40 / 40 / 40** | **0** | 0 | 174 px | 2.1 ms |
| Wild beasts r24 x 20 | **20 / 20 / 20** | 0 | 0 | 283 px | 1.2 ms |
| Wild beasts r24 x 26 | **26 / 26 / 26** | 0 | 0 | 298 px | 1.8 ms |
| Shellback r24 x 32 | 24 / 32 / 32 | 0 | 0 | 345 px | 1.9 ms |
| today's pack r26 x 3 | 3 / 3 / 3 | 0 | 0 | 121 px | 0.1 ms |

Against the circle it replaced, which managed **24 seated with 75
overlapping pairs** on the 40-body case.

**The large-body caveat from G0 is closed.** It was raised against a 32-body
stress case; at the size Wild beasts actually asks for - 20 commons, 26 with
its elites - the company seats *whole at every anchor*, inside 300 px. The
32-body row is kept as the stress test, not as a group.

**Cost.** About 2 ms for the largest company and 0.1 ms for the 2-4 body
packs the game spawns today, against a 33 ms frame. It is paid once when a
company is seated, not per frame, so it does not need a budget of its own.

Also worth noting: the reach came in *tighter* than the prototype's budget -
174 px where 250 was provisioned - because `pack_spread` sizes the disc for
the company rather than using a flat radius. A small pack stays on its first
ring.

### Tests

`RingTests` became `PackTests` in `tests/spawn/test_placement.py`. The two
tests that pinned the old geometry by its formula are gone - an exact
`leader + follower + gap` distance and an even 120-degree spread are not
things the packer promises. What replaced them:

* a forty-body company seats whole, nothing overlaps, everything is
  walkable, and it stays inside a screen's worth of ground;
* a small pack stays tight on its first ring;
* the radius grows with both the company and the bodies, and never passes
  the cap;
* the jitter breaks the rings without costing a body - the same count seats
  with it off, but the exact rings sit at under 10 discrete radii where the
  jittered ones sit at more than 30;
* a blocked spot is retried wider and then dropped *(kept, re-aimed at the
  new radii)*;
* a walled-in company spawns short, and the shortfall is a tail of `None`
  rather than a hole in the middle;
* no followers is no pack *(kept)*.

`tests/spawn/test_master.py` had the follower reach hard-coded as
`2 * (26 + 26 + ring_gap) * 1.6`. It now calls a `_reach` helper that
derives the packer's own bound from the knobs, so the test moves with the
data instead of duplicating a number out of it.

Suite green.

---

---

## G0b built: `company_stagger` (2026-09-17)

A company no longer has to appear on one frame. `company_stagger` is a
number of seconds in `spawn_tables.json`; the shipped value is **0.35**.

**What is decided up front, and what is not.** Everything that decides the
company still happens the moment it is seated - its point, its packed
spots, the cap it pays. The stagger spreads only *when* each body appears:
the leader lands immediately, the followers are queued oldest first, and
the last one lands as the window closes. `_release_pending` makes them and
re-decides nothing, because there is nothing left to decide.

**The cap gate had to move, and this is the interesting part.** It used to
be re-checked per follower, inside the seating loop, which is how a pack
"spawned short rather than over the cap". Under a stagger that is wrong:
the same company would arrive whole at 0 and arrive truncated at 0.35,
depending on what else spawned while it was in the air. So the gate is now
settled once, by `_cap_room(owner)`, for the whole company - what does not
fit is dropped *now* rather than discovered halfway through an arrival.

The other half of that: **a body still in flight counts as live** for every
later check. Without it the run would overshoot the cap by the size of
every company in the air. Measured over 180 s of real run, live + in-flight
never exceeded the cap on any frame.

Note this keeps the old *behaviour* - a company still spawns short rather
than over the cap - while changing *when* the shortfall is computed. The
`min(pack, cap - active)` clipping in the director is a separate thing and
still waiting for G3.

**0 stays first-class.** At 0 the branch is skipped entirely and bodies are
made in the seating loop exactly as before, which is why the whole suite
stayed green before the shipped value was raised off 0.

**Which spawns stagger.** Only the director's companies. `spawn_at`,
`spawn_group`, the dev menu, residents and the arena keep landing whole -
they have synchronous callers that count what came back, and a dev spawn
wants its bodies now. A deferred company carries its stagger through the
debt queue, so a company that had to wait still arrives the way it would
have.

### Measured on a booted run, pinned world, 180 s at 60 fps

| | |
|---|---|
| bodies spawned | 141 |
| frames that landed a body | 141 of 10800 |
| **biggest single-frame arrival** | **1 body** |
| live + in-flight over the cap, worst frame | **0** |

Not one frame landed more than a single body. That is the whole point of
the knob: at today's pack sizes (2-4) a 0.35 s window puts bodies about
120 ms apart, and the window divides by the company, so a company of 30
lands about one body per frame at 60 fps rather than thirty at once.

**The spawn burst comes free.** `PlayingHost.make_enemy` already calls
`fx.spawn_spawn_fx(enemy)` per body, so spreading the arrivals spreads the
bursts with them - a company now visibly materialises instead of blinking
in, with no new effect code.

### Tests

New `StaggerTests` in `tests/spawn/test_master.py`:

* at 0 the whole company lands on one frame;
* at 0.35 only the leader has landed, and once the window closes the
  company is at **the same spots in the same order** as the un-staggered
  run of the same seed - staggering changes the clock and nothing else;
* the bodies arrive across the window rather than in one jump;
* each body lands exactly once, the queue empties, and no two bodies share
  a spot;
* a body in flight already counts against the cap;
* `drop_pending()` stops the rest of a company from landing;
* a `frozen` run still finishes a company it has already paid for.

**One existing test had gone quietly vacuous** and this is worth recording,
because nothing failed to reveal it. `test_the_director_pack_lands_together_on_a_point`
asserted over `host.live[1:]`; with the stagger on, the followers had not
landed yet, so that loop iterated an empty list and every assertion in it
was skipped while the test still passed. It now waits for the company and
asserts the full count first.

The draining helper is `_settle`, which uses `frozen` rather than a zero
`dt`. A zero `dt` does **not** hold the director: its timer is already
negative after a tick, so it fires again whatever `dt` says - worth knowing
before writing any test that wants to advance time without spawning.

Suite green.

---

---

## G1 built: the roster changes (2026-09-17)

Three data edits and the test work they force. Nothing here touches the
spawn model - it is the roster the new model will draw from.

**`enemies.json`.** `is_elite: true` on `hex_shaman` (Hexcaller),
`minotaur` (Gorehorn) and `turtle` (Shellback), and Shellback's hp 80 ->
**150**. The elite roster is now Ravager, Grudge, Hexcaller, Gorehorn and
Shellback - five, where it was two.

Only the flag was set; the `tags` arrays were left alone. Ravager and Grudge
carry a redundant `"elite"` tag, but nothing reads it: `is_elite` is what
every consumer switches on, and enemy tags are only used for the `flying`
check and for the kill event's payload. Adding a second source of truth for
"is this an elite" would be the wrong kind of tidy.

**`spawn_tables.json`.** `unused` is now `[]` - Stoutpaw is unbenched and
nothing is benched today. The mechanism stays; see the test note below.

### What three more elites switch on

The todo asked what else rides on the flag. Six things, and one of them
matters:

| | |
|---|---|
| gold per kill | **x2** instead of x1 |
| item drop | **18 % chance**, scaling with run time |
| screen shake | 0.18 on death |
| death particles | 16 at 200 speed, instead of 10 at 160 |
| the gold ring | drawn round the body while it lives |
| `tag_bonus` | the `elite` blessing's damage bonus applies |

**The item drop is the material one.** Items come from elites and the boss
and nothing else - the meta screen says so in as many words ("beat elites /
the boss"). Measured over 40 seeds of the current director across a
10-minute run:

| | before G1 | after G1 |
|---|---|---|
| elite share of bodies | 28.8 % | **48.8 %** |
| items from elites (at 18 %) | 236 | **400** (+69 %) |
| gold from kills | 5870 | 6780 (+15.5 %) |

*(Absolute counts are inflated - the director emits more than the live cap
seats - but the ratios hold.)*

Nothing was changed in response. The 18 % and the x2 are balance numbers
and the owner's call, and the whole point of the new model is that elites
become a rank rather than a rarity, so item income rising is a consequence
of the design rather than a bug in it. **Flagging it for G6**, where it
should be decided with the companies actually running.

### Tests

**Deleted: `test_the_rare_band_is_exactly_the_elite_enemies`.** It asserted
that an enemy is rare-band exactly when it is `is_elite`, which held while
"elite" meant the two toughest bodies on the roster. Hexcaller (64) and
Gorehorn (55) are now elites in the *uncommon* band, so the rule is not
true any more. The owner settled the replacement in advance - "potions can
keep the same check by hp" - so there is no coupling left to pin and the
test is gone rather than re-pinned, with a comment in its place saying why.

**Rewritten: `test_uncommon_enemies_can_drop_all_three`.** It named
`turtle` as its uncommon exemplar; Shellback at 150 hp is rare-band now, so
the test failed for a reason that had nothing to do with what it was
checking. It reads the middle band off the roster instead. Its own sibling
test already carried a note about hand-listed cases going stale whenever an
enemy moves band - this was that, again.

**Rewritten: `test_unused_category.py`.** Emptying `unused` would have left
every assertion in it vacuous - the exact failure mode G0b turned up
elsewhere. It is now in two halves: `ShippedTests` checks what must hold of
the shipped table whatever its list contains (and that Stoutpaw is
genuinely rollable again), and `MechanismTests` / `DirectorTests` exercise
the filtering against a *synthetic* table that benches the panda the way
the shipped one used to. `DirectorTests` also gained the control it never
had: the same long run on the shipped table **does** roll Stoutpaw, so the
benched case cannot pass merely because the director never reaches those
bands.

Suite green.

---

## Progress

- [x] Groups and ranks confirmed against the roster (all 18 placed, after
      the owner's Bonepicker / Whirlspear correction)
- [x] Consequences and collisions identified
- [x] Open questions answered; cooldowns, elite counts and arrival settled
- [x] Placement prototype - G0 passed; the fix is a packer in place of
      `Placement.ring`, no architecture change
- [x] G0a - `Placement.pack` built, measured and tested; suite green
- [x] G0b - `company_stagger` built, measured and tested; suite green
- [x] G1 - roster changes: five elites, Shellback 150 hp, Stoutpaw
      unbenched, the potion/elite coupling test retired
- [x] Retire the potion/elite coupling test; potions.py itself unchanged
- [x] Stoutpaw unbenched; three enemies gain `is_elite`; Shellback +70 HP
- [ ] Old `groups` renamed, new `groups` defined with two spans each
- [ ] Two ladders: common 5 s (-1, floor 1), elite gate 15 s (-3, floor 3),
      elite `min` +1, all stepping every 2 min and scaled by timeline_pace
- [ ] Cap gate: prepare, count, spawn or retry every 2 s; companies atomic
- [ ] Remove `min(pack, cap - active)` clipping from the director
- [ ] Build
