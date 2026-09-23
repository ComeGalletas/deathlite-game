# Bridge clearance for large bodies — journal

**ID:** WLD-011 (+ WLD-012) · **Systems:** world (+ ENT) · **Type:** bug ·
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

---

## WLD-012 — Requirement (owner, 2026-09-22)

- **Objective:** Keep every bridge open to the widest walking body by
  keeping props clear of bridge mouths.
- **Details:** The one blocked bridge on seed 35 (above, *Still open*) is
  closed by a prop, not by geometry. The clearance a mouth needs is the
  widest walking body's radius; today that is the Tusked Lance at 40 (the
  First Hunger, radius 46, flies and ignores terrain; the widest regular
  enemy, the troll, is 26).
- **Constraint:** A generation change, so the world digests are re-pinned
  and a screenshot is delivered (the generator leads, the tests follow).
  No collider change — WLD-011's leniency stays as it is.
- **and then:** the owner chose the recommended WLD-012.D1 — the clearance
  follows the data (2026-09-23).

## WLD-012 — Confirmed reading

- `world/gen/scatter.py::_corridor_doorways` already builds a keep-clear
  rectangle at each bridge end — the end plank tile and the landing tile,
  inflated by one tile all round — and the obstacle scatter
  (`_scatter_obstacles`), the spawn points and the village placement all
  read it.
- The blocking prop sits 19 px past the planks with a 19.5 px radius, which
  is *inside* that one-tile margin. So either the prop comes from a stage
  that does not consult the doorways (decor, fish huts, village props, the
  bake), or the check tests the prop's centre where it should test its
  circle. Which one is not established yet; WLD-012.1 finds it.
- `tests/world/test_bridge_crossing.py` drives bodies over every bridge of
  seeds 35, 7 and 42 (`BOSS_R` 40, `SMALL_R` 24). The crossing test filters
  out prop-blocked bridges with `propped(...)`, and
  `test_a_prop_beside_a_mouth_still_blocks_a_wide_body` pins the defect and
  asks to be deleted when it is fixed.
- **WLD-012.D1 — The clearance follows the data (confirmed by the owner, 2026-09-23).**
  The margin is the largest `radius` among the non-flying bosses and
  enemies in `data/enemies/`, derived at run start, so a wider walker added
  later is covered without a code change. The alternative is a fixed
  number in `game/config.py`.

## WLD-012 — Plan

Find the stage that seats the blocking prop, give it the same mouth rule
with the body clearance applied to the prop's circle, then turn the pinning
test into a guarantee. `tests/world` before each commit; digests re-pinned
with `python -m tools.verification.world_digest --write` in the commit that
moves them.

## WLD-012 — Tasks

- [ ] WLD-012.1 — Identify the placement stage and the check that let the seed-35 prop through
- [ ] WLD-012.2 — Keep props a widest-walker radius clear of every bridge mouth (D1)
- [ ] WLD-012.3 — Replace the pinning test with "every bridge on the pinned seeds crosses at the widest walker's radius"; drop the `propped` filter
- [ ] WLD-012.4 — Re-pin the world digests; record how many props moved, as a rate over the seeds
- [ ] WLD-012.5 — Screenshot of the seed-35 bridge before and after

## WLD-012 — Results

*(filled in as the tasks land)*
