# Fish huts and seahorse boats (water NPCs)

Scenery on the sea that moves: a fish hut moored off an island's coast, and a
few seahorse boats drifting round it. Nothing here fights, blocks or drops.

---

## Requirement (owner, 2026-09-20)

- **Objective:** Draw the fish-hut and seahorse-boat sprites from
  `unused\enemies\extra` as water decoration and non-combat NPCs.
- **Details:** The folder holds a fish-hut sheet (a decoration on water) and
  the `seahorse_boat` folder (NPCs). Like the human NPCs, the boats only move
  around slightly and never interact with combat; draw them close to the fish
  hut, two to four of them.
- **Constraint:** Confirm the understanding before building.

## What the review found

**The art** (`assets/unused/enemies/extra/`):

| sheet | grid | frames | what it is |
|---|---|---|---|
| `fish_hut/fish_hut.png` | 192 px | 8 | a fish-shaped hut on a raft, bobbing on water |
| `seahorse_boat/seahorse_boat_idle.png` | 192 px | 8 | an empty seahorse boat, bobbing |
| `seahorse_boat/seahorse_boat_bomb_fish.png` | 192 px | 8 | the boat with a Bloat aboard |
| `seahorse_boat/seahorse_boat_harpoon_shark.png` | 192 px | 8 | the boat with a harpoon shark aboard |
| `seahorse_boat/seahorse_boat_paddle_shark.png` | 192 px | 8 | the boat with a paddle shark aboard |

Every sheet is one idle loop; there is no separate move strip, so a boat that
moves plays the same bob it plays standing still.

**How the human NPCs work today** (`entities/npc.py`,
`game/states/playing/core/npcs.py`, `data/village/npcs.json`):

- an `Npc` is scenery that moves: no health, no collider, walks through and
  is walked through; a state machine of stand / pick a spot near home / walk
  there / stand again, with `speed`, `idle`, `leash` and `radius` per kind in
  the data;
- `Npcs.build` reads the layout's `Village` records (a generation-time record
  of where things stand) and seats each kind from a world-seeded rng, so a
  seed's villagers are the same people every run;
- they are drawn through the depth-sorted character layer
  (`Npcs.actor_items`), so a pawn walking behind a house is hidden by it;
- only the ones near the view are stepped.

**Water scenery today** (`world/terrain/decor/scatter_water.py`): rocks,
ducks and clouds are scattered by chance per tile / lattice cell and drawn as
one flat list *under* the islands. That is the wrong home for a hut with
boats round it: the boats need to know where the hut is, and a boat drifting
north of the hut should draw behind it, which a flat under-layer cannot do.

## Confirmed reading

1. **The fish hut is a water decoration**: a static, animated prop on the sea
   off an island's coast. It is not an obstacle (nothing can reach it) and
   not an interactable.
2. **The seahorse boats are non-combat NPCs**, the water counterpart of the
   sheep: they drift slightly round the hut, never leave the water, never
   fight, are never targeted, and never block anything.
3. **Two to four boats per hut**, each drifting within a short leash of the
   hut it belongs to.

Decisions the request left open, taken as follows unless overruled:

- ~~**Where the huts go.** One hut at most per island, a few tiles off its
  coast at a seeded chance.~~ Overruled, see below.
- **Which boat.** Each boat draws its sheet at random from the four (empty,
  Bloat, harpoon shark, paddle shark), per instance, the way villager
  colours are dealt.
- **Riders are only art.** A Bloat in a boat is not a Bloat: the spawn master
  still owns every enemy, and the boats stay outside combat entirely.

## Correction (owner, 2026-09-20)

- **Objective:** Place the fish huts near bridges.
- **Details:** A hut may sit perpendicular to its bridge or simply close to
  where the bridge meets the island; one to three huts per island assignment.

So the huts belong to the bridges, not to the open coast:

- **One to three huts per island**, each moored beside one of that island's
  bridges. Every island with a bridge gets at least one hut if any spot fits.
- **Beside the bridge**: a hut sits off the side of the span, perpendicular
  to it, a tile or two out from the planks and a tile or two along the
  bridge from where it meets the island. "Close to the intersection" and
  "perpendicular to the bridge" are the same family of spot, nearer or
  further from the mouth.
- **Candidates**: for each bridge touching the island, one spot on each
  side of the span, at a seeded distance along and out. The island rolls
  1-3 and takes that many distinct candidates that pass the open-water
  check (clear of every floor, every other bridge and every other hut by
  the hut's own reach plus its boats' leash). Fewer passing candidates
  means fewer huts, never a hut on land.
- **A shared bridge** may carry a hut from either island, each from its own
  end; the clearance check keeps them apart.
- The boats' leash is small enough that a boat never crosses the planks or
  reaches the beach.

Lakes still get none.

## Proposal

1. **Assets** -- move the two folders to `assets/terrain/npcs/fish_hut/` and
   `assets/terrain/npcs/seahorse_boat/` beside the sheep and pig, and credit
   them with the corral animals.
2. **Rigs** -- `npc_fish_hut` and `npc_seahorse_boat_{idle,bomb_fish,
   harpoon_shark,paddle_shark}` in `data/heroes/character_sprites.json`: 192
   px cells, a content crop measured off the sheets, a `scale` to world px, a
   waterline anchor, one `idle` loop each (the boat's `walk` is the same
   strip).
3. **Placement record** -- a `FishHut(room_id, corridor, x, y)` record on
   the layout (`layout.fish_huts`, like `villages` and `chests`), decided by
   a new generation pass `world/gen/fish_huts.py` with its own rng keyed by
   seed and island, drawing nothing from the world stream. Per island it
   rolls 1-3, lists a candidate off each side of each of its bridges (a
   seeded distance along the span from the mouth and out from the planks),
   and keeps the first that many candidates whose clearance disc is open
   water. Runs after the corridors and villages are final.
4. **Tuning** -- `data/village/npcs.json` gains `kinds.seahorse_boat`
   (speed, idle, leash, radius) and `placement.fish_huts: [1, 3]`,
   `placement.boats: [2, 4]`; the along / out distances live with the
   generation tuning.
5. **Behaviour** -- `WaterNpc(Npc)` in `entities/npc.py`: `_choose` accepts a
   target only if it is open water (off every floor and bridge) and inside
   the leash of the hut; `_step_toward` glides straight there with no
   obstacle sliding, since nothing on the sea blocks. No aggro, ever.
6. **Manager** -- `game/states/playing/core/fish_huts.py`, one concern per
   module: builds the huts and their boats from the layout records, steps
   the boats near the view, and hands `(level, depth_y, draw_fn)` items for
   the huts *and* the boats to the character layer, so a boat north of the
   hut draws behind it and one south of it draws in front.
7. **Tests** -- a placement test on a pinned seed (every hut sits on open
   water clear of land, beside one of its island's bridges, one to three
   per island that has a bridge, two to four boats each), a
   drift test (a boat never leaves the water or its leash, never has an
   aggro radius), a draw test (huts and boats are in the character items),
   and a determinism test. The world digests move because the layout gains
   a record and a frame gains sprites; that is regenerated with
   `python -m tools.verification.world_digest --write` and said so here.
8. **Screenshot** of a hut with its boats, delivered at the end.

## Confirmed (owner, 2026-09-20)

"go", on the corrected reading above.

## Built

1. **Assets** -- `assets/terrain/npcs/fish_hut/` and
   `assets/terrain/npcs/seahorse_boat/`, moved from `unused/enemies/extra`
   (they were never tracked, so a plain move) and credited with the corral
   animals in `assets/CREDITS.md`.
2. **Rigs** -- `npc_fish_hut` and the four `npc_seahorse_boat_*` in
   `data/heroes/character_sprites.json`. Content crops are the union bbox
   over each sheet's eight frames; the hut is at 0.54 (80x87 world px), the
   boats share 0.45 so the hull is the same size whoever rides in it
   (36x38 empty, up to 49x48 with the harpoon shark). The anchor is the
   waterline, nine tenths down the crop. Each rig declares `walk` as the
   same strip as `idle`: there is no move strip, and a drifting boat bobs
   like a resting one.
3. **Generation** -- `world/gen/fish_huts.py`, the last stage of
   `generate_world_steps` after the chests. `bridge_ends` finds each
   bridge's mouth by stepping out along the span from the rect's island end
   until the island's cells stop (the rect edge is not the coast, as
   `_corridor_doorways` found). Per island with a bridge: roll
   `placement.fish_huts` (1-3), list one candidate per side per bridge at
   `_FH_ALONG` (1-3 tiles) along and `_FH_OUT` (2.4 tiles) out, shuffle, and
   keep the first `count` whose `_FH_CLEAR` (1.7 tile) disc is open water
   and which stand `_FH_APART` (3.6 tiles) from every hut so far. Private
   rng keyed by seed and island. The record is `FishHut(room_id, corridor,
   x, y)` on `layout.fish_huts`.
4. **Tuning** -- `kinds.seahorse_boat` in `data/village/npcs.json`: 14 px/s,
   idle 2-6 s, leash 0.3 tiles, radius 10, `rigs` a list of the four
   sheets. `placement.fish_huts [1, 3]`, `boats [2, 4]`, `boat_ring
   [0.7, 1.0]` tiles. The geometry constants sit with the generation tuning.
5. **Behaviour** -- `WaterNpc(Npc)` in `entities/npc.py`: `_choose` accepts a
   target only where `GameMap.is_open_water` (the floor rule's complement,
   new on the map) says so; `_step_toward` glides straight with no obstacle
   sliding. No aggro.
6. **Manager** -- `game/states/playing/core/fish_huts.py`: `FishHuts.build`
   makes a `FishHutProp` per record (an animator on the hut rig, radius 0
   so the render drop is off and the anchor is the waterline) and 2-4
   `WaterNpc`s per hut, each homed `boat_ring` out at a seeded angle on open
   water, with a sheet drawn at random. `update` steps huts and boats near
   the view; `actor_items` hands both to the character layer at their own
   depth, blitting through `Npcs.draw_one`. Hooked into `PlayingState`
   beside the villagers.
7. **Tests** -- `tests/entities/test_fish_huts.py`, 13 tests. Placement over
   every pinned seed: huts exist, 1-3 per island, each on a clear disc,
   exactly `_FH_OUT` off the centre line of a bridge that touches its
   island, past the mouth, apart from one another, and identical on a
   rebuild. One booted run: every hut has 2-4 boats homed within the ring,
   on the water, with no aggro, from the four sheets; a boat driven thirty
   seconds drifts, stays on the water and inside its leash; huts and boats
   are in the character items and a frame draws; a rebuild deals the same
   boats. The layout digests moved (a new field on the layout) and were
   regenerated; the bake and frame digests did not.

## What the pinned seeds grew

| seed | bridges | huts | per island |
|---|---|---|---|
| 35 | 13 | 11 | 2,1,2,1,1,1,1,1,1 |
| 7 | 15 | 12 | 3,1,2,1,1,1,1,1,1 |
| 1234 | 10 | 12 | 2,1,2,1,1,1,2,1,1 |
| 42 | 8 | 10 | two bridged islands got none: every candidate's disc touched land |

Most islands land one hut: a roll of two or three is often cut by the
clearance disc, since the coast wanders in beside a bridge mouth. That is
the rule as confirmed ("fewer passing candidates means fewer huts"); if more
huts are wanted, `_FH_CLEAR` or the candidate count per bridge is the knob.

## Progress

- [x] Confirmed by the owner
- [x] Assets moved and credited
- [x] Rigs
- [x] Generation pass and layout record
- [x] Tuning
- [x] `WaterNpc`
- [x] Manager and character-layer draw
- [x] Tests, digests regenerated
- [x] Screenshot delivered (seed 1234, two huts)

## Follow-up: a bigger hut (owner, 2026-09-20)

- **Objective:** Enlarge the fish-hut sprite by 30 %.

`npc_fish_hut`'s `scale` goes from 80x87 (0.54 of the sheet) to 104x113
(0.70), the anchor moved with it to stay on the waterline. Placement,
clearance and the boats' ring are untouched: the 1.7 tile disc still holds
the wider art with room, but a boat homed at the inner end of its ring now
sits closer to the hull. Screenshot delivered.

