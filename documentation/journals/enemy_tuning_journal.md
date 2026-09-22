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
(`the_tusked_lance`, ENT-002). A four-pixel collider shrink; the owner's
reason is not recorded here. It brings the boss to the same radius as its
sprite's stablemates and slightly loosens how early a charge connects.

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

Open: **ENT-012.D2's rationale is inferred, not stated.** If the radius change
was for something specific — a charge that overshot, a sprite that read too
wide — say so and it goes in the decision above.
