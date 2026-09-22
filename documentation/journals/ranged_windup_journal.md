# Ranged attacks get a range, a wind-up, and their animation back

**Legacy ID:** ENT-010 · **Systems:** ENT · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The four kiting enemies stop firing on an invisible timer from an
undeclared distance. Aggro comes down across the whole roster in the same
pass.

**Status: built and green (2026-09-19).**

---

## Requirement (owner, 2026-09-19)

- **Objective:** Increase every ranged enemy's attack cooldown by 100 %,
  making them much slower to attack.
- **Details:** Alongside, list the currently active ranged enemies and verify
  which of them have no attack animation wired for the ranged attack.

and then, after the audit:

- **Objective:** Reduce the aggro range of all enemies by 50 %.
- **Details:** Ranged enemies gain a new metadata value, separate from the
  aggro range: the attack range — the minimum range at which an enemy is able
  to attack specifically, not merely get close to the player. Start it at
  around 300 px for all units.

Answers to the three questions that followed: wire every enemy that can be
wired; use a wind-up before the shot and take 20 % off the interval to pay
for it; `shoot_interval` is the **true shot-to-shot gap**; a body out of
reach aborts rather than commits; Gaffjaw gets 400 px and the rest 300.

---

## The audit: six enemies had art they could never play

Checked by building every enemy and reading the states its machine
actually has, rather than by reading the JSON.

| enemy | behaviour | attack strip | can reach it |
|---|---|---|---|
| Slinger, Bloat, Bonepicker, Gaffjaw | `kite_shoot` | yes | **no** -- single `move` state |
| Skitter, Stinger | `path_chase` | yes | **no** -- single `move` state |
| the other twelve | melee / caster / charger / brute | yes | yes |

`Enemy._anim_name()` returns `"attack"` only while the machine sits in
`telegraph` or `attack`, or when a component names a strip through
`ATTACK_SLOT["anim"]`. `kite_shoot` was `MaintainRange` + `FireProjectile`
in one `move` state and `FireProjectile` never named a strip, so
**`shoot.png` and `throw.png` had not been drawn once since they were
delivered**.

This is the same fault the Beekeeper had, and `path_chase_summon`'s
docstring had already recorded the diagnosis -- "plain `summoner` holds
range in a single `move` state, which is why its sprite never played an
attack animation". The kiters never got the same treatment.

**Skitter and Stinger are left alone** (owner). They are contact-damage
chasers with no attack action at all, so wiring their art would mean
inventing an attack they do not have. A known gap now rather than an
undiscovered one.

---

## What changed

### Aggro, across the whole roster

Asked for a 50 % cut; settled at **25 %** after measuring what 50 % costs.
The span went `[880, 1200]` -> **`[660, 900]`**.

**A correction worth recording**, because the owner accepted a
recommendation that was wrong: I proposed 660-900 on the grounds that it
"keeps `far_max` 850 just inside the 900 minimum". 900 is the *maximum*.
The minimum is 660, so `far_max_distance` 850 sits above it and the
invariant `far_max < min(aggro)` is only partially restored.

Measured rather than argued. The fraction of the 620-850 spawn band each
enemy can notice the hero from:

| | aggro | band covered |
|---|---|---|
| Shellback | 660 | 17 % |
| Husk, Hammer Gnome, Grudge | 710 | 39 % |
| Skitter, Cinder | 760 | 61 % |
| Ravager, Bonepicker | 800 | 78 % |
| Slinger, Gorehorn, Hexcaller | 830 | 91 % |
| Blink, Gaffjaw | 860-900 | 100 % |

And the end-to-end number, a hero standing still for four minutes:

| aggro | bodies within a screen (median) |
|---|---|
| 360-640 (original) | 5 |
| 880-1200 | 111 |
| **660-900** | **60** |

So roughly half the gain is kept, and the shape is arguably better than
the flat 111: slow tanks hang back, fast and ranged bodies come. The lever
if 60 proves too few is `far_max_distance`, not aggro again.

### `attack_range`, and what it replaced

A new per-enemy key: the reach of the shot, separate from the
`aggro_range` that decides whether the body is interested at all.

| | `prefer_distance` | `attack_range` | old implicit reach |
|---|---|---|---|
| Slinger | 260 | 300 | 468 |
| Bloat | 210 | 300 | 378 |
| Bonepicker | 190 | 300 | 342 |
| Gaffjaw | 360 | **400** | 648 |

The old reach was `prefer_distance * 1.8` -- a weapon's range as a side
effect of where the body liked to stand, and never written down anywhere.
Every kiter loses reach, Gaffjaw most.

**Gaffjaw needed its own number.** At 300 it would have kited to its
preferred 360 and sat permanently outside its own attack range, never
firing a shot. `prefer_distance <= attack_range` is now a test.

### The wind-up

`kite_shoot` is rebuilt on `telegraph_cycle`, the scaffold the melee
enemies and the Beekeeper already use. The shot leaves on the wind-up's
end transition, so the animation and the projectile are one event rather
than two things that happen to coincide.

`attack_range` is also the cycle's `trigger_range`, so a body out of reach
never begins a wind-up -- and one that drifts out mid-wind-up **aborts**
rather than loosing a shot the player was given no reason to expect
(owner's call).

`shoot_interval` is the **true shot-to-shot gap**, not the cooldown: the
wind-up, the strike and the recovery are subtracted from it, so the number
in the data is what a stopwatch would measure.

| | old gap | x2 | -20 % = new gap | wind-up | cooldown |
|---|---|---|---|---|---|
| Slinger | 2.1 | 4.2 | **3.36** | 0.45 | 2.46 |
| Bloat | 2.8 | 5.6 | **4.48** | 0.55 | 3.43 |
| Bonepicker | 2.6 | 5.2 | **4.16** | 0.50 | 3.21 |
| Gaffjaw | 3.4 | 6.8 | **5.44** | 0.60 | 4.34 |

Net 1.6x slower than before, every shot announced. The wind-ups are scaled
loosely to how much the shot hurts -- Gaffjaw's piercing harpoon reads
longest, Slinger's acorn shortest.

`FireProjectile` gained a `fire()` method, split out of `tick`, so the
cycle and the old bare timer share one definition of what a shot *is*.
A kiter that declares no `attack_telegraph` keeps the old single-state
behaviour, so nothing outside these four moved.

---

## Tests

`tests/entities/ai/test_ranged_windup.py`. The shape half is read off the
data -- every kiter reaches `telegraph`/`attack`, the cycle fits inside the
declared gap, `prefer_distance <= attack_range`, the reach is declared
rather than derived, and a kiter without a wind-up keeps its single state.

The firing half runs a **real booted run**, because what is being checked
is that the animation and the shot are the same event, and only the live
machine can show that: each of the four plays its `attack` strip, and a
body aggroed but out of reach shows no tell at all.

---

## Left open

* **Skitter and Stinger** still have unreachable attack art, by decision.
* The difficulty of all of this is untested -- the owner is running that
  themselves. Nothing here was balanced against G1's elite item income or
  the front-loaded cadence.
