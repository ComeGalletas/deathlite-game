# Bomb blast radius — journal

**Legacy ID:** CMB-004 · **Systems:** CMB · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## 1. The requirement (owner, 2026-09-12)

- **Objective:** Bind the Bomb weapon's blast area to its actual in-game
  radius for the explosion — today the explosion is independent and does not
  scale with anything.
- **Details:** Also add blessings that grow the radius in 15 % steps.

Two items:

1. The Bomb's explosion radius must be part of the weapon's **area** system
   rather than a stand-alone constant, so the area sources the rest of the
   game already has move it.
2. A blessing line that grows that radius in **15% steps**.

## 2. Confirmed reading

### What the code did before

`data/weapons.json` gives the Bomb two independent size numbers:

| field | value | what it actually is |
|---|---|---|
| `area` | 8 | the thrown ball's own collider |
| `blast_radius` | 72 | the detonation's damage radius |

`Weapon._area(area_multiplier)` scales `area` by `bonus["area"]` and the
hero's `area_multiplier`, exactly as it does for every other weapon, and
`Weapon._reach` scales the reach ring the same way (CB-2 decision 2). The
blast did neither: `combat/weapons/bomb.py` passed
`definition["blast_radius"] + bonus["blast_radius"]` straight through — no
`area_multiplier`, no `bonus["area"]`.

So the user's report is exact. Concretely, an item affix `of Expanse`
(`data/items.json`, `stat: area_multiplier`) widened every weapon's area and
every reach ring **and did nothing at all to the Bomb's explosion** — the one
weapon whose whole identity is area. That is the "independent and doesn't
modify".

The *visual* was already bound: `TransientFx.detonate` hands
`burst_visual(pos, bomb.blast_radius)` the same number the damage circle
uses, and `WorldRenderer._blit_burst` scales the `explosion` rig so its
`fireball` width spans the blast diameter. Nothing to fix there — the
explosion art follows whatever radius the blast is given, so binding the
radius binds the picture with it.

### Decision: the ball's collider stays separate

The blast radius is bound *to* the area system; `area` is **not** collapsed
into `blast_radius`. The thrown ball's 8 px collider is load-bearing physics
and is not a "size of the attack" number:

* `TransientFx.block_on_obstacle` / `block_on_terrain` stop the throw with
  it — a 72 px ball would be blocked by anything within 72 px and land at
  the hero's feet;
* `CombatResolver.trip_mine` (Minefield) uses it as the trip radius — a mine
  would go off from 72 px away;
* `scatter_bomblets` sizes a bomblet from it (`bomb.radius * 0.7`).

So the binding is: the explosion radius reads the Bomb's area **bonus** and
the hero's area **multiplier**, on top of its own `blast_radius` field. One
knob per thing, and every area source in the game now reaches the explosion.

### Decision: 15% steps are multiplicative, and a new card

`bomb_bigger_explosion` ("Bigger Explosion") already exists and adds **flat**
px (`+12 / +24 / +36 / +48 / +60` on a base of 72). The request is for *15%
steps*, and "add" is taken literally: the tuned flat card is left alone and a
new percentage line is added beside it. They compose the way the fire path
composes everything else — the flat adds land inside, the percentage scales
the total:

    blast = (blast_radius + bonus[blast_radius] + bonus[area])
            * area_multiplier * bonus[blast_radius_mult]

The steps are 15 percentage points of the base per level — `+15% / +30% /
+45% / +60% / +75%` — stored as the cumulative multipliers
`1.15 / 1.30 / 1.45 / 1.60 / 1.75` because `Effect.delta` turns a `mult`
bonus's levels into the ratio between consecutive levels, so the running
total is always exactly `levels[N-1]`.

## 3. The proposal

| file | change |
|---|---|
| `combat/weapons/core.py` | new `bonus["blast_radius_mult"] = 1.0`; new `Weapon._blast_radius(area_multiplier)` next to `_area` / `_reach` |
| `combat/weapons/bomb.py` | `throw_bombs` reads `weapon._blast_radius(ctx.area_multiplier)` |
| `progression/blessings/catalog.py` | new `pct_gain` display: `1.15` prints as `+15%` |
| `data/blessings.json` | new `bomb_blast_amplifier` — "Blast Amplifier", coverage / uncommon, 5 levels of `blast_radius_mult` |
| `ui/run_status/build.py` | the card's "Blast radius" row folds in `bonus["area"]` and `blast_radius_mult` so `base -> now` tells the truth |
| `tests/combat/test_bomb.py` | the area multiplier, the area bonus and the mult reach the blast; cluster bomblets inherit the grown radius |
| `tests/progression/test_blessings.py` | `pct_gain` formatting; the new blessing applies as 15% steps; a guard that every `weapon_bonus` field is a name some code reads |
| `tests/rendering/test_run_status.py` | the Blast radius row shows the multiplied value |

Nothing in `entities/projectile.py`, `game/states/playing/effects.py` or the
projectile styles changes: the `Projectile.blast_radius` field and the
detonation plumbing already carry whatever number the weapon hands them.

## 4. Progress

- [x] `_blast_radius` on `Weapon`, `blast_radius_mult` bonus key
- [x] `throw_bombs` uses it
- [x] `pct_gain` display
- [x] `bomb_blast_amplifier` blessing
- [x] run-status card row
- [x] tests
- [x] screenshot of a blessed blast
- [x] guard test: no `weapon_bonus` field can be a dead key

## 5. Results

14 new tests. Targeted suites green: `tests/combat` + `tests/progression`
**544 passed**, `tests/combat/test_bomb.py` **25 passed**,
`tests/progression/test_blessings.py` **46 passed**,
`tests/rendering/test_run_status.py` **22 passed**.

Measured through the real fire path (`tests/combat/test_bomb.py`), base 72:

| area source | blast radius |
|---|---|
| none | 72 |
| `area_multiplier` 1.25 (`of Expanse` affixes) | 90 |
| `bonus["area"] +10` | 82 |
| Blast Amplifier V (`x1.75`) | 126 |
| Bigger Explosion V (+60) and Amplifier V | 231 |

Cluster Bomb's bomblets inherit it: `cluster_radius_mult` 0.6 of the grown
parent radius, so a blessed Cluster blast scatters bigger bomblets too.

### A guard that came out of the new bonus field

Adding `blast_radius_mult` showed that nothing validated a `weapon_bonus`
effect's `field` at all: a typo would write a key into `weapon.bonus`, be
read by nobody, and the blessing would still level and still print its card
while doing nothing in the run. `CatalogTests` now walks the catalog and
requires every such field to be either a key of the fixed `Weapon.bonus`
dict or a key some Forging declares under `effects` in `data/forges.json`
(those are read through `Weapon.effect`, which sums the `effects` total with
`bonus.get(key, 0.0)`). The Forge set is derived from the data, so a new
Forge effect needs no edit to the test.

### Three pre-existing failures, none of them this work

The full suite finishes with three failures that live in other in-flight
changes in the working tree and touch nothing this feature reaches:

* `tests/rendering/test_menu.py::CharacterSelectInstructionsTests::test_content_comes_from_config`
  — `743 != 742`. `CharacterSelectState._draw_instructions` starts its block
  at `y = top - 20` while the instruction font's `get_linesize()` is 21, so
  the bottom it returns is one pixel below what the test derives from the
  line height. From the hero-select instruction-row work (commit `8d9aa98`
  plus the uncommitted `character_select_state.py` changes).
* `tests/world/test_repair.py::BridgeLengthTests::test_a_bridge_over_the_cap_had_no_shorter_lane`
  — "seed 7 link 0-4: 17 tiles when 10 was available".
* `tests/world/test_village_tidy.py::TidyTests::test_the_heal_has_company`
  — "seed 1234: the heal stands alone".

The last two sit with the uncommitted `world/gen/village.py`,
`world/gen/tuning.py`, `world/layout.py` and `tests/world/digests.json`
changes. Left alone deliberately: they are not this feature's to fix.

Screenshot delivered: two detonations on the same frame in open meadow — an
unblessed 72 px blast beside a Blast Amplifier V 126 px one — with the dev
collider overlay on, so the ring drawn at each fireball's edge is the true
damage circle the resolver uses. It shows both halves of the change at once:
the art follows the radius, and the radius answers to the blessing.

The still was produced by a throwaway script in the session scratchpad (boot
`PlayingState`, plant two blasts, step both fuses, freeze the burst at frame
4 of 10); it is not checked in, since no screenshot in this repo is.
