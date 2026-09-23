# Bridge clearance for large bodies — journal

**ID:** WLD-011 · **Systems:** world (+ ENT) · **Type:** bug ·
**Status:** done · **Branch:** claude/reaction-damage-rework

---

## WLD-011 — Requirement (owner, 2026-09-22)

- **Objective:** Let a boss-sized body cross a bridge, by giving
  `GameMap.is_walkable` the same corridor leniency the navigation field
  already has.
- **Details:** Chosen from three options after ENT-012.D3 measured that the
  pig-rider boss could not cross at radius 40 or 44. The rejected two were
  widening decks to two tiles and cutting the boss to radius ≤ 31.
- **Constraint:** None given.

## WLD-011 — Confirmed reading

Two rules disagreed, and the disagreement was the bug.

* **The collider.** `GameMap.is_walkable` probes a body as a four-point cross
  — `x ± radius`, `y ± radius` — and requires every probe on floor. A deck is
  **one tile**, `TILE_PX` = 64, so crossing needs `radius ≤ 31`.
* **The navigation field.** `world/nav/field.py` takes `corridor_lenient=True`
  by **default**, handing out corridor cells whatever their clearance.
  `world/rules/floor.py::in_corridor` says why in as many words: bridges get
  "clearance leniency in the navigation grid, so the big rare enemies can
  still thread it", and
  `test_pathfinding.py::test_one_tile_corridors_need_leniency_for_the_big_enemies`
  has pinned that promise since M3.

So the field routed a large body onto a deck the collider then refused. It
walked to the mouth and stalled, which reads exactly like a collider a few
pixels too wide — which is why the first attempt at this was a radius tweak.

**WLD-011.D1 — relax the probe, not the floor test.** The centre must still be
on floor and the obstacle test below is untouched, so the leniency only lets a
wide body *overhang the planks*. That is what a one-tile bridge has always
asked of anything bigger than a gnoll, and it is exactly what the nav grid
already assumed.

**WLD-011.D2 — `frm` is consulted as well as `pos`.** The mouths are the hard
part. Stepping off a deck puts the centre on a coast whose floor is irregular,
and demanding a full radius of it the moment the body leaves the planks would
stand it up on the deck and refuse to let it ashore. Measured: without this,
crossings still failed at the far mouth.

**WLD-011.D3 — the corridor lookup stays off the hot path.** `in_corridor` is
a linear scan over the layout's corridors, and `is_walkable` runs for every
body every frame. The test is therefore made only on the probe's *failure*
path, which ordinary movement on open ground never reaches.

## WLD-011 — Plan

One clause in `world/map.py`, one `on_bridge` helper beside `is_open_water`,
a new `tests/world/test_bridge_crossing.py`, and an update to the one existing
test that recomputes `is_walkable`'s logic inline.

## WLD-011 — Tasks

- [x] WLD-011.1 — Give `is_walkable` the corridor leniency, with tests

## WLD-011 — Results

Measured by driving a body along every bridge of three seeds through the real
`resolve_movement`, one frame at a time, as `Boss._move` does:

| radius | before | after |
|---|---|---|
| 28 | crosses | crosses |
| 31 | crosses | crosses |
| 32 | **none** | crosses |
| 40 (the boss) | **none** | crosses |
| 44 (the old value) | **none** | crosses |
| 46 | **none** | crosses |

Suite: `tests/world` + `tests/entities` green.
`tests/world/test_obstacle_index.py::test_walkability_and_projectile_blocking_are_unchanged`
needed the new clause added to its inline recomputation — it had caught the
change correctly.

### Still open: a prop can shut a bridge

*(DOC-003: tracked as **WLD-012**, proposed.)*

One bridge on seed 35 stays closed to a radius-40 body, and it is **not**
geometry. A prop sits 19 px past the planks with a 19.5 px radius, so a
radius-40 body's exclusion circle (59.5 px) reaches across the deck's centre
line. The obstacle test is deliberately untouched by this fix, so it blocks.

That is a **placement** defect: props are kept off decks but not kept a
largest-body radius clear of a mouth. `world/gen/chests.py` already keeps
chests "clear of obstacles and bridge mouths"; props have no equivalent rule.
`test_a_prop_beside_a_mouth_still_blocks_a_wide_body` pins it so it cannot be
forgotten, and says to delete itself when placement is fixed. Not fixed here —
it is a different subsystem and a different requirement.
