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
(`the_tusked_lance`, ENT-002). The owner's intent (2026-09-22) was **so it
can cross bridges**: the boss free-roams, and at 44 it was stuck on whichever
island it spawned on instead of following the hero.

> **Measured 2026-09-22: the change does not achieve that.** Driving a body
> along all 13 bridges of seed 35 through the real `GameMap.resolve_movement`,
> the widest radius that crosses is **31**. At 32 and above every bridge is
> impassable, and 40 fails exactly as 44 did. The value is kept — it is the
> owner's and it harms nothing — but the bug it was aimed at is still open.
> See **ENT-012.D3**.
>
> **Resolved by WLD-011** (`f1b4aa3`, 2026-09-22): `is_walkable` now gives a
> body on a bridge the same corridor leniency the nav field already had, so
> radius 40 crosses. See `bridge_clearance_journal.md`. *(DOC-003)*

**ENT-012.D3 — Why the boss cannot cross, and what would fix it.** Not a
tuning problem. Two rules disagree:

* `GameMap.is_walkable` (`world/map.py:267`) probes a body's radius as a
  four-point cross — `x ± radius`, `y ± radius` — and every probe must be on
  floor. A bridge deck is **one tile**, `TILE_PX` = 64, so a body crossing a
  horizontal bridge needs `y ± radius` inside a 64 px band: radius ≤ 31.
* The navigation flow field (`world/nav/field.py`) takes
  `corridor_lenient=True` by **default**, so corridor cells are traversable
  whatever their clearance — the docstring says it exists "so the big rare
  enemies can still thread it".

So the pathfinder routes a large body onto a bridge that the collider then
refuses. The boss walks to the mouth and stalls there, which reads exactly
like a collider being a few pixels too wide. Three ways out, none taken yet:

1. give `is_walkable` the same leniency the nav grid already has — skip or
   shrink the radius probe when the centre is on a corridor. Smallest change,
   and it removes the disagreement rather than working around it;
2. widen the deck to two tiles, which changes world generation and the look
   of every crossing;
3. bring the boss to radius ≤ 31, an 11 px cut on a body whose sprite is much
   wider than that.

Option 1 is the one that matches the nav grid's stated intent. It needs the
owner's call.

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

`a61e6f6` and `5eac856` both say 40 clears the crossings; **ENT-012.D2
above supersedes that** — it was measured afterwards and it does not.

`a61e6f6`'s own message still reads as plain tuning: the reason arrived
after it was committed, and rewording a commit that already has three
on top of it needs a history rewrite this environment refuses. The
decision above is the record; `ENT-012.D2` is the citable form of it.
