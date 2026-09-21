# Special island facilities — parked (2026-09-20)

## The request

- **Objective:** Review the special areas / facilities / merchants usually
  placed at the centre of some islands.
- **Details:** Most of these functionalities are incomplete or do nothing at
  all — the merchant among them — and have no sprite wired in. Identify which
  of them are to be removed from world generation.
- **Constraint:** Keep the code templates in place, in case they are needed.

## What was there

Every world is nine islands. Before this pass the generator spent four of
them on `SPECIAL_KINDS` — `shrine`, `treasure`, `altar`, `merchant` — one of
each, in **every** world (12-seed census, seeds 0–11: all four present in all
twelve). With one or two villages and the start and boss islands on top, that
left only one or two plain combat islands per run.

| Facility | Sprite | What the interact key did |
| --- | --- | --- |
| `shrine` | none — a blue ring and a white dot | One random blessing; heals 30 if the pool is empty. One-shot. |
| `altar` | none — a purple ring | 25 % of max HP for one random blessing. Refuses when it would be near-lethal, refunds when there is nothing to grant. |
| `treasure` | none — a yellow ring | `_drop_item`: one item onto `stats["dropped_items"]`, banked into the save stash at run end. Nothing visible during the run. |
| `merchant` | none — a tan ring | 30 gold, then the same `_drop_item`. No shop, no price shown, no choice; silently does nothing when the player is short. |

All four drew the placeholder ring in `visual/rendering.py:interactables` —
they were the only interactables left doing so. The facilities that *are*
finished all have art and full behaviour: the village forge
(`assets/terrain/facilities/forge.png`, the reforge picker), the village
sanctuary heal (`heal_effect.png`), the five buff buildings (~60 an island
world, data-driven from `data/world/buildings.json`), the CB-9 chests and the
fish huts.

The merchant had already been parked once by the owner (2026-09-12,
`combat_balance_journal.md`): left as it is, doing nothing yet, with gold
consumption still work in progress. Nothing has changed since — there is
still no gold sink.

## The decision (owner, 2026-09-20)

Remove **all four** from world generation.

- **Objective:** Remove the merchant, treasure and altar from world
  generation.
- **Details:** Do not generate more islands to replace them — only remove
  those interactions and the tags that identify those islands. The islands
  left are the combat islands, the most of them, and the human island, which
  is treated separately.
- **Constraint:** These special facilities will be implemented later in
  different ways, so the referenced code is not to be removed.

Asked whether the shrine — the fourth special, which the decision above
implies but does not name — went with them: **yes**.

Three things follow, and they are the whole brief:

1. **Island count does not change.** Nine islands as before; the four that
   carried a facility become ordinary combat islands. No island is added or
   removed to compensate.
2. **The freed islands are plain combat islands** (owner's pick): normal
   obstacle scatter, normal spawn points, normal chest seeding. In
   particular they stop reserving the `_GRID_CLEAR_RADIUS` disc at their
   centre — there is nothing left there to reach.
3. **The code is parked, not deleted.** These facilities are coming back
   in different ways, so every handler, kind entry, colour and marker
   height stays exactly where it is. Only the generator's ability to emit
   the four tags goes away.

This is deliberately the opposite resolution to `elite_arena`
(`placement_review_journal.md` C2, 2026-09-12), which was removed outright.
The difference is intent: `elite_arena` was dead with nothing planned; these
four are on the way back.

## What changed

**The one switch.** `SPECIAL_KINDS` in `world/gen/tuning.py` is now the empty
tuple. Everything downstream already reads it rather than restating the
names, so emptying it is enough:

- `graph._assign_kinds` — its `zip(SPECIAL_KINDS, others)` assigns nothing,
  so every non-start, non-boss, non-village island keeps `"combat"`. The
  shuffle above it stays so the world RNG stream is not disturbed for an
  unrelated reason, and so the loop is still the working template.
- `scatter._clear_radius` — `special` is never true, so these islands return
  `0.0` and may fill their middle like any combat island.
- `scatter`'s house pass — the special `keep` branch is never taken; the
  0.30 combat fraction applies.
- `locations.build()` — the special loop appends nothing. Villages still get
  their forge and sanctuary, buff buildings still get theirs.

**Parked untouched:** `entities/interactable.py` `KINDS` (all four radii and
colours), `locations.use_shrine` / `use_treasure` / `use_altar` /
`use_merchant` and `MERCHANT_COST` / `ALTAR_HP_COST_FRACTION`, the
`state.py` forwarders, `key_marker.KEY_LIFT`, and
`world/terrain/render.py`'s `_SPECIAL_FLOORS` entries.

**Swept up while here:** `world/gen/spawnpoints.py` imported `SPECIAL_KINDS`
and never used it.

## Tests

The four handlers no longer appear in any generated world, so the tests that
found one in a layout would have gone quiet — `skipTest` on three of them,
which is worse than deleting them: it looks like coverage and is not. They
now **hand-build** the `Interactable`, which is the honest way to test parked
code: the handlers stay covered, and the test says out loud that generation
does not place them.

- `tests/playing/test_interactables.py` — shrine, treasure, altar and
  merchant build their own interactable; `PlacementTests` now asserts the
  positive fact that a generated world has *no* special-kind interactables,
  and counts only villages and buff buildings.
- `tests/world/test_layout.py` — `test_special_rooms_present` is replaced by
  `test_no_special_rooms_are_placed`, which pins the new rule.
- `tests/world/test_obstacles.py` — the clear-disc test is replaced by one
  asserting the freed islands are treated as combat islands.
- `tests/playing/test_chest_open.py` — the location-beats-chest tie test
  seats its own shrine instead of hunting the layout for one.
- `tests/world/digests.json` — regenerated. The worlds moved: four islands a
  world stopped holding their centres clear, so the scatter fills them.
