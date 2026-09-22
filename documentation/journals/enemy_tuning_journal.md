# Enemy tuning — journal

**ID:** ENT-012 · **System:** entities · **Type:** balance ·
**Status:** done · **Branch:** claude/reaction-damage-rework

Hand tuning of shipped enemy numbers, with no code behind it. A place for
one-value changes to `data/enemies/*.json` that are too small to earn a
journal each; later tweaks of the same kind get a new requirement block here
rather than a new file.

---

## ENT-012 — Requirement (owner, 2026-09-22)

- **Objective:** Commit two enemy data tweaks the owner made by hand during
  the CMB-006 session.
- **Details:** Stoutpaw's `shield_hp` drops from 41 to 7; The Tusked Lance's
  `radius` drops from 44 to 40.
- **Constraint:** Values as the owner set them — this requirement carries them
  into history, it does not re-tune them.

## ENT-012 — Confirmed reading

Both are single values in shipped data, with no code path to change.

**ENT-012.D1 — Stoutpaw's shield.** The shield sat at 41 over 33 HP, so a
Stoutpaw carried more shield than body. `Enemy.take_damage`
(`entities/enemy.py:158`) subtracts the shield from `dealt` and `_absorb`
returns what is left, so while the shield holds, `world.deal` returns 0: the
floating number reads `0`, `stats["damage_dealt"]` gains 0 and the ledger
records 0. Elemental damage arrives in pieces of one to three points, so a
41-point shield swallowed an entire infusion's worth of them and every number
the player saw was a zero. This was the fourth of six findings in the
zero-damage review that opened the CMB-006 session; at 7 the shield is two
sword hits rather than a wall, and elemental damage starts landing almost
immediately.

**ENT-012.D2 — The Tusked Lance's radius.** 44 → 40, the pig-rider boss
(`the_tusked_lance`, ENT-002). **So it can cross bridges** (owner,
2026-09-22). The boss free-roams, and at 44 its collider caught on the
crossings between islands, leaving it stuck on whichever island it spawned on
instead of following the hero.

Worth knowing for the next time it snags: a bridge deck is **one tile wide**,
`TILE_PX` = 64, so its half-width is 32 — still under the 40 this leaves. The
radius is therefore not the whole story; whatever clearance the movement
resolver allows a body over a walkway edge is doing the rest. If the boss
catches again, the lever is the deck width or that tolerance, not another
four pixels off a collider already wider than the plank it walks on.

Neither value is read anywhere but the enemy definitions, so there is nothing
else to keep in step.

## ENT-012 — Plan

No code, no tests to add. Verify the existing suite still passes with the new
values, then one commit per value.

## ENT-012 — Tasks

- [x] ENT-012.1 — Stoutpaw's shield 41 → 7 (`data/enemies/enemies.json`)
- [x] ENT-012.2 — The Tusked Lance's radius 44 → 40 (`data/enemies/bosses.json`)

## ENT-012 — Results

`tests/combat`, `tests/entities` and `tests/spawn` with both values in place:
**1083 passed, 345 subtests passed**. No test pinned either number.

Both rationales are the owner's own, given on 2026-09-22; nothing
here is inferred.

## ENT-012 — Tasks (continued)

- [x] ENT-012.3 — Record why the radius changed

`a61e6f6`'s own message still reads as plain tuning: the reason arrived
after it was committed, and rewording a commit that already has three
on top of it needs a history rewrite this environment refuses. The
decision above is the record; `ENT-012.D2` is the citable form of it.
