# Pig rider boss — execution journal

## Requirement (owner, 2026-09-12)

Implement the pig rider from `assets/unused/` as a second boss. It gets a
charge pattern like the one The First Hunger already has, plus the melee sweep
identified when its attack animation was surveyed (see the "Proposals" section
of the unused-sprite review).

---

## Confirmed design (owner, 2026-09-12)

Three decisions were put to the owner before any code:

| | decision |
|---|---|
| Boss selection | **Random per seed.** The run picks from the pool, reproducibly — same seed, same boss. |
| Patterns | **charge + sweep + a short triple-charge.** Only two pattern *ids*; the triple is three extra `charge` entries with different numbers, so it costs no code. |
| Difficulty | **A peer of The First Hunger** — comparable HP and damage, a different shape: a ground bruiser that closes hard rather than a flyer that zones. |

---

## What the art gives, and what it does not

`assets/unused/enemies/extra/pig_rider_spear_goblin/` holds three 256 px sheets:
idle (8 frames), run (4), attack (7). Moved to `assets/enemies/pig_rider/` as
`idle.png`, `run.png`, `attack.png` — the same shape every other enemy rig
takes. Measured across all three animations the ink occupies `[33, 17, 192,
151]` of the 256 px frame, and the ground contact (the pig's feet in idle frame
0) sits at x 91, y 148 inside that crop.

Two things the frames decide for us:

* **The attack is a sweep, not a thrust.** Frames 2–4 carry a wide white arc all
  the way around the mount, and 5–6 recover with the spear levelled. That is an
  area centred on the boss, which is why the pattern calls `melee_hit` rather
  than firing a projectile — an earlier reading of this animation as
  `radial_barrage` was wrong and is corrected here.
* **Frame 5 levels the spear forward**, a couched-lance pose, which is what
  sells the charge.

What the art does *not* give is a wind-up long enough for a boss telegraph —
see the timing note below.

---

## Numbers

### Rig (`data/enemy_sprites.json`)

`content [33, 17, 192, 151]`, `scale [260, 204]`, `anchor [123, 200]`,
`face "right"`.

The scale is ×1.35 on the content. It looks large against the bat's `[154,
120]`, but most of the pig rider's height is a vertical spear: the *character*
in idle is only 87×145 of that 192×151 box, so at this scale the body reads at
roughly 118×196 and the pig itself about 95 px tall — a heavier ground
silhouette than the bat without the spear making it absurd. The anchor is the
measured ground contact carried through the same scale (91/192 → 123,
148/151 → 200), so the pig's feet sit on the boss position.

### Definition (`data/bosses.json`, `the_tusked_lance`)

Peer of The First Hunger: the same 9990 HP, 400 XP and 60 currency, but 92
speed against 78 and 28 contact against 31. It is faster because it is **not**
`flying` — it follows the flow field around cliffs and across bridges where the
bat goes straight over them, so equal speed would make it the slower threat.

`radius 44`, just under the bat's 46. **This is the one number carrying risk**:
no ground unit in the game is remotely this wide (the brute, the largest, is
26), so a body 88 px across may snag on a narrow terrace or bridge. It degrades
rather than breaks — `_seek` falls back to a straight line when the flow field
has no route, and every charge already beelines by design — but if it reads
badly in play the fix is to shrink the radius rather than to widen the world.

### Pattern cycle

Five entries, cycled in order by `_next_pattern`:

1. `charge` — long telegraph (1.0 s), the committed 760 px/s dash.
2. `sweep` — 0.5 s telegraph, a 150 px hitbox centred on the boss.
3. `charge` ×3 — 0.45 s telegraph, 900 px/s, short recover, so the three run
   together as a flurry. Each re-aims, because `_charge_dir` is taken when the
   telegraph ends.

Listing `charge` four times with different numbers is what keeps the
triple-charge free of code.

---

## Code

* `entities/boss.py` — a `sweep` branch in `_fire_pattern`, calling
  `ctx.melee_hit`. That verb has been on the `Combat` protocol and implemented
  in `effects.py` the whole time with no caller; this is its first boss use.
* `entities/boss.py` — `_anim_name` now plays **walk** during a charge's active
  phase instead of attack. A galloping pig reads as a charge; a held spear pose
  sliding across the ground does not. This improves The First Hunger too.
* `game/states/playing/spawning.py` — the boss is chosen from the pool instead
  of `next(iter(...))`.

### The selection is seeded off the run seed, not the run's RNG

`spawn_boss` builds its own `random.Random(f"{run_seed}:boss")` rather than
drawing from `ps.rng`. The shared stream has already been consumed an
unpredictable number of times by the time a boss spawns — how many depends on
how the run actually played — so drawing from it would make the boss a function
of the *playthrough* rather than of the seed, and two runs on the same seed
could meet different bosses. A private generator keyed off the seed makes the
choice reproducible, which is what "random per seed" has to mean if it is to be
worth anything for testing or for sharing a seed.

### A timing note worth keeping

The boss FSM plays the `attack` animation across both `telegraph` and `active`,
so an attack sheet is pulling double duty as wind-up and as impact. The sweep's
numbers are picked so the arc lands on the hitbox rather than before it: at 7
fps the 7 frames span 1.0 s, frames 0–1 (the raise) cover 0–0.29 s and the arc
frames 2–4 cover 0.29–0.71 s, so a 0.5 s telegraph puts the hitbox inside the
arc. Changing either the telegraph or the fps without the other will drift the
swing off its own hitbox.

---

## Follow-up: the lance spawned in the sea (owner, 2026-09-12)

### Requirement

> "the pig rider spawns on water/void similar to the giant bat, but because it
> doesn't have the flying tag it essentially gets stuck on the water and can't
> move. change the way the spawn works to make it spawn on ground, however
> increase the movement speed 3x in case its far away from the character so it
> can reach the character faster"

### The bug

`boss_spawn_point` was written for The First Hunger and says so in its own
docstring: one point at `BOSS_SPAWN_DISTANCE` on a random side, clamped to the
world rect, *"the boss flies, so what is under the spot -- floor, cliff, lake,
sea -- does not matter"*. The Tusked Lance inherited it without inheriting the
`flying` tag, so it was dropped wherever the ring landed and, off walkable
ground, `resolve_movement` refuses every step it tries to take.

Measured over the four pinned seeds with the hero at the start room, 40 spawns
each: **92 of 160 (57 %) landed somewhere the lance could not stand.** This was
not an edge case -- it was the common outcome.

### The fix

The ring becomes a *search* when the boss walks. `boss_spawn_point` takes an
optional `walkable(pos)` callback; with one supplied it samples
`BOSS_SPAWN_RING_SAMPLES` (12) angles around the circle from the drawn start
angle, at each radius in `BOSS_SPAWN_RING_SCALES` (`1.0, 0.8, 1.25, 0.6, 1.5,
0.4, 2.0` x the distance), and takes the first spot the collider accepts.

Three properties worth stating, because each is a thing that could have gone
wrong:

* **The flyer is untouched.** `EnemyControl.boss_spawn_point` only builds the
  callback for a definition without the `flying` tag, so The First Hunger still
  takes exactly one blind point and every existing assertion about it holds.
* **The random side survives.** The sweep *starts* at the angle the run RNG
  drew and only walks on from there, so the lance still arrives from a
  different direction each run rather than from a fixed compass point.
* **It always spawns.** If nothing in the whole sweep is walkable the
  unconstrained point is used. A boss that spawns awkwardly is recoverable; a
  boss that never spawns ends the run with no way to finish it.

After the change the same 160 spawns give **0 unwalkable**, and all 160 land on
the intended 680 px ring -- the first scale is `1.0`, and on these worlds there
is always land somewhere on the ring itself.

### The closing sprint

`BOSS_CLOSING_SPEED_MULT = 3.0`, applied in the one branch that already existed
for this: out of `vision_range` the boss holds its pattern clock and does
nothing but close, so that approach now runs at 3x `speed` and drops back to 1x
the instant the hero is in sight. The fight itself is unchanged -- every
telegraph, dash and sweep is fought at the authored speed.

It is deliberately a rule of the boss FSM rather than of the pig rider: nothing
about it depends on walking, and the bat can be left out of sight too. A
definition may override it with `closing_speed_mult`, the same shape
`contact_interval` already uses.

**Honest note on how much this one does.** With the search landing on the
intended ring every time, the lance spawns at 680 px against a `vision_range`
of 720 -- inside its own sight, so it is *not* closing at spawn and the sprint
does not fire. It is insurance for the case the requirement names (a spawn that
had to be pushed out to 1.5x or 2x to find land, on a world with less ground
near the hero) and for a hero who outruns the boss mid-fight. It is not a
routine part of the approach on the seeds measured.

### Files

* `game/config.py` — `BOSS_SPAWN_RING_SAMPLES`, `BOSS_SPAWN_RING_SCALES`,
  `BOSS_CLOSING_SPEED_MULT`.
* `game/states/playing/spawning.py` — the ring search; `spawn_boss` resolves the
  definition once and hands it to `boss_spawn_point`.
* `entities/boss.py` — `closing_speed`, applied in the out-of-sight branch.
* `tests/ai/test_boss_pig_rider.py` — `GroundSpawnTests`, `ClosingSprintTests`.
* `tests/ai/test_boss.py` — `test_out_of_sight_the_boss_only_closes_in` pinned
  the closing speed at exactly `speed`; it now asserts the sprint, since the
  rule it described has been deliberately changed.

## Progress

* **2026-09-12** — Options confirmed with the owner, sprites moved, rig and
  definition written, `sweep` pattern and boss selection implemented, tests
  added.
* **2026-09-12** — Ground spawn search + the 3x closing sprint (follow-up above).
