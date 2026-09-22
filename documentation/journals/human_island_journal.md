# Human island — dev log

**Legacy ID:** WLD-005 · **Systems:** WLD, ENT · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The village island: a small, flat island with no enemy spawns that hosts
NPCs, buildings and facilities. First facility is the Forge the six-weapon
update needs (`six_weapon_system_design.md` §7). Milestones are prefixed
**HI**. Same rules as the other logs: full suite green per milestone,
determinism A/B-checked, nothing committed unless asked.

**Status:** HI-0 to HI-4 **COMPLETE** (2026-09-09). Nothing committed.

---

## Decisions (2026-09-09)

- **Count.** Every world has at least one human island and at most two.
- **Size.** About half a volcanic island's walkable area (`size 0.76`, the
  measured ratio is 0.49). Flat: `tiers (0, 0)`, no lakes, one bridge per
  side, a squarer coast preset.
- **Placement.** Chosen by role like the boss (`weight 0`), among islands at
  tree distance 1–2 from the start, never the boss island.
- **Sanctuary.** Enemies never spawn on it (no spawn points, `village: 0`
  residents) but may pursue the hero across a bridge.
- **Heal prop.** The fountain moves here and leaves the special-kind
  shuffle. It is skinned with `assets/heal_effect.png` (11 × 192 px, looped),
  placed at random but near the village centre, heals the hero once, then
  the prop is hidden.
- **Forge.** `Interactable("forge")` with a stub handler until forging lands.
  Skinned with `forge.png`; the interactable ring is only the placeholder
  when no sprite resolves.
- **Colours.** Buildings draw from all five colours (black included), NPCs
  from the four that have pawn/lancer art. Randomised per instance from the
  world seed, cycling a shuffled list so no colour repeats before every one
  has appeared. No colour band per village.
- **Layout** (revised 2026-09-09, see "Designed round a centre" below).
  Forge at the walkable centroid; the town hall due north; houses, monastery
  and archery in one compact ring on the other slots round the forge;
  barracks + tower a few tiles inside each bridge mouth; a fenced sheep pen
  on the side farthest from the bridges; trees, rocks and clutter outside
  the cluster, spread round it.
- **Colliders.** Circles only, as everywhere else. Wide buildings are
  compound: one primary circle carrying the skin plus invisible satellites.
- **Fence.** Small colliders per tile so the hero cannot cross; sheep are
  leashed by the pen rectangle, not by collision.
- **NPCs.** Pawn, lancer and sheep with idle / run (bounce) animations and
  basic wander around a home point. Non-blocking against the hero. A smith
  pawn at the forge uses the hammer strips.

## Todo

**HI-0 assets and data**
1. `git mv` the used art out of `assets/unused/`: five building types in
   five colours, the fence sheet, `forge.png`, the sheep sheets, and only
   the pawn (idle, run, hammer variants) and lancer (idle, run) strips.
2. Rigs in `data/terrain.json`: buildings, forge, the fence cells, the
   heal effect. Measure anchor and footprint like the houses.
3. Obstacle kinds: `forge`, `barracks`, `tower`, `archery`, `monastery`,
   `castle`, `fence`; `render_scale 1.0` so buildings draw 1:1.
4. NPC rigs in `data/character_sprites.json`: pawn, smith, lancer per
   colour, sheep.

**HI-1 the island**
5. Topography `human` in `HEIGHTMAP_TOPOGRAPHIES`; per-topography `lakes`
   override.
6. Room kind `village`, 1–2 per world, assigned before the special-kind
   shuffle; `fountain` removed from `SPECIAL_KINDS`.
7. Generic scatter skips village islands; `world/gen/village.py` owns them.
8. Spawn master: no points, no residents; test it.

**HI-2 the village pass**
9. Anchors: centroid, bridge mouths (`_corridor_doorways`), the back side.
10. Placement in order: forge, heal prop, house ring, monastery/archery,
    military at the bridges, pen, optional castle. Every building on
    `GROUND`, clear of mouths and of each other; `unseal` runs after.
11. Forge and heal interactables; `use_forge` stub, `use_fountain` reused
    and the prop hidden after use.

**HI-3 NPCs**
12. `entities/npc.py`: rig, `Animator`, wander state machine, `is_walkable`
    destination check, flip to face travel.
13. `game/states/playing/npcs.py`: build from the layout, update, feed the
    depth-sorted character layer. Smith at the forge, pawns in the house
    ring, one lancer per military post, 2–4 sheep in the pen.

**HI-4 tests, digests, docs**
14. Tests on the shared cached worlds: 1–2 villages per world at distance
    1–2; forge near the centroid; military within N tiles of a mouth; pen on
    ground; no overlapping colliders; connectivity; zero spawn points.
    Update `test_interactables` and `test_houses`.
15. Re-pin `tests/world/digests.json` (`python -m tools.verification.world_digest --write`).
16. `documentation/level_design.md` §1.2 and §1.7; entry in this log.

---

## HI-0 — assets and data (2026-09-09)

Art moved out of `assets/unused/` (130 renames, the untracked files by
plain move): five building types in five colours, the fence, `forge.png`,
the two sheep strips, and per colour the pawn strips `idle`, `run`,
`idle_hammer`, `run_hammer`, `interact_hammer` and the lancer `idle`, `run`.
`heal_effect.png` (untracked, at the assets root, byte-identical to the
monk's) now lives in `terrain/facilities/`. Audit: zero missing references,
zero unreferenced live files.

Data:
- `terrain.json` rigs: `<type>_<colour>` (25), `forge`, `fence_<slot>` (10),
  `fx_heal` (11 frames, loop). Anchors measured as for the houses.
- Obstacle kinds `forge`, `barracks`, `tower`, `archery`, `monastery`,
  `castle`, `fence` (fence does not block projectiles). `render_scale 1.0`
  for all, so the art is drawn as authored; `sprite_drop` 1.0 (buildings),
  0.8 (forge), 0 (fence). Buildings and the forge join the ghost kinds.
- `character_sprites.json`: `npc_pawn_<c>`, `npc_smith_<c>` (hammer strips,
  plus a one-shot `work`), `npc_lancer_<c>` for four colours; `npc_sheep`.
  (`npc_pig` joined it later and shares the corral with the sheep --
  `pig_npc_journal.md`.)

Deviations from the plan:
- No `wall` kind: a test wants every obstacle kind skinned, and satellites
  are a HI-2 decision (same kind, skip the skin, or a flag on `Obstacle`).
- No `native_scale` flag: `render_scale` already does it.
- The fence sheet is 4 × 3 cells with the south edge shipped as two gate
  halves and no plain south tile. A rig cannot pick a column of a sheet,
  so the ten cells were sliced to `buildings/wooden_fence/fence_<slot>.png`
  (as `dead.png` was repacked); the sheet stays parked.

Tests: assets, terrain, prop coverage, obstacles, biome, houses -- 160
green. The layout digests were already off before HI-0 (checked with the
new kinds removed at runtime); they belong to the in-flight terrain work
and HI-4 re-pins anyway.

---

## HI-1 — the island (2026-09-09)

- `HEIGHTMAP_TOPOGRAPHIES["human"]`: `tiers (0, 0)`, `size 0.76`, coast
  `square`, one bridge a side, `weight 0`, `lakes 0` (a new per-topography
  key, read in `build_island` over the global), meadow sheets only.
- `HEIGHTMAP_COAST_PRESETS["square"]`: margin 4, hold 4–6, run cap 6. Swept
  by bounding-box fill over five seeds: margin 3 gave 0.93–0.96 (a slab and
  a failed rectangle test); this gives 0.82–0.93. Villages come out at
  ~560 walkable tiles against a volcanic island's ~920 -- a flat island
  spends nothing on cliffs, so the linear 0.76 lands above half here.
- `HEIGHTMAP_VILLAGES (1, 2)`, `HEIGHTMAP_VILLAGE_DISTANCE (1, 2)`,
  `HEIGHTMAP_VILLAGE_TOPOGRAPHY`; all three are `GenSettings` fields.
- `_pick_villages` in `gen/graph.py` runs inside `_assign_kinds` before the
  special-kind shuffle: `randint` on the band, `sample` from the islands at
  that tree distance, never start or boss, with a fallback to any island
  should the band be empty. `assign_topography` gives them the human shape
  and draws nothing for them. `fountain` left `SPECIAL_KINDS`.
- Skips: `_scatter_obstacles` and `_scatter_houses` pass over a village;
  `place_points` yields it with no enemy or resource point; the residents
  table has `village: 0` and the kind is in `_RESIDENT_KINDS` so it cannot
  fall through to the `special` count.
- Tests: `tests/world/test_village.py` (count band, distance band, never
  boss, flat and lake-free, smaller than any volcanic island, bare, no
  points, no residents). Four existing tests now exempt the village or a
  one-terrace shape: no island bare, spawn points on every island / floor,
  the point index, two biomes per topography. World + spawn + biome +
  terrain + interactables: 459 green, 2 skips (the fountain effect tests,
  rewired in HI-2). Digests untouched until HI-4.

---

## HI-2 — the village pass (2026-09-09)

`world/gen/village.py`, a stage of its own after the scatter and before the
unseal repair. Per village, in order: forge at the walkable centroid (or
the nearest cell that takes it), heal prop drawn at random 2.5–4.5 tiles
out, 3–4 houses in a ring at 3.5–5, monastery and archery on opposite
sides at 5.5–8, a barracks and a tower flanking the road in from every
bridge mouth (3 tiles in, 2.5 to each side, fanned inland when blocked),
the sheep pen on the side away from the bridges (sweeping the full circle
if that side has no room), castle off by default (`HEIGHTMAP_VILLAGE_CASTLE`).
Every circle must sit on `GROUND` with 16 px of coast in hand, clear of
the bridge-mouth keep-clear rects, 24 px from any other village circle and
1.5 tiles off every mouth→forge lane; the guards are the only buildings
allowed that near a road. The result is a `Village` record on
`WorldLayout.villages` (forge, heal, buildings, guard posts, pen interior,
mouths) for the interactables now and the NPCs in HI-3.

- **Compound colliders.** A wide building is its primary circle plus the
  `satellites` its `terrain.json` entry declares (`[dx, dy, r]`); satellites
  are `Obstacle`s of the same kind with `skin = False`, so collision,
  navigation, spawn vetting and clutter spacing see them and the skins and
  the renderer skip them. Barracks / archery / monastery carry two at ±52–58
  px, the castle two at ±92.
- **Colours** from a shuffled five-colour cycle per village, houses
  included; no band.
- **Fence.** Radius 24 (20 left a 24 px slit the 10 px hero fit through).
  Pens are 6–7 × 4–5 tiles with a **two-tile gate** in the south rail; two
  tiles of ground kept round the ring.
- **The repair and the pen.** `unseal` pulled a post out of the far side of
  the pen on seeds 7 and 35: the 48 px lattice at the widest body read the
  gate as sealed whenever a column landed off its middle, and later the
  sliver between a house and the fence. The pen is not enemy ground (the
  hero fits, the sheep are leashed, nothing spawns there), so `_exempt_pens`
  closes the ring and one tile round it before the flood, in the repair
  and in `test_repair`'s baseline alike. Measured over 24 seeds after:
  zero village obstacles removed, pens on 32 of 35 villages.
- **Interactables.** `Interactable("forge")` (stub `use_forge`, never
  consumed) and `Interactable("fountain")` at the village's heal, prompt
  "Sanctuary - heal to full". The playing renderer draws the `fx_heal`
  loop on the fountain (hidden once used) and nothing on the forge while
  its obstacle skin resolved; the ring stays as the assetless placeholder.
- Tests: `test_village` gained the layout checks (only village kinds on
  the island, one record per village, forge ≤ 3 tiles from the centroid,
  heal ≤ 5 tiles and on ground, every guard ≤ 8 tiles from a mouth, the
  pen a closed ring on ground with one gate, satellites unskinned, no two
  circles of different buildings overlapping, castle off and a setting).
  `test_houses` reads the scatter's houses only; `test_terrain` counts
  skins over skinned obstacles and bounds variants by the rig list;
  `test_obstacle_families` knows the village kinds; `test_interactables`
  expects a forge and a heal per village. World + spawn + terrain: 469
  green; the rest of the tier 823 green, one seed-dependent flake in the
  projectile-trail test that passes on rerun (random run seed, an
  obstacle east of the hero) and predates this work.

Screenshots: `HI2_village_1_overview.png`, `HI2_forge_and_heal.png`,
`HI2_sheep_pen.png` (scratch, sent to the owner).

---

## HI-3 — the villagers, and a smaller island (2026-09-09)

**Size.** The owner asked for about a quarter less. `size` 0.76 → 0.67:
walkable mean 549 → ~410 tiles (0.59 → 0.44 of a volcanic island), swept
over twelve seeds. Pens fell with it, so `_place_pen` now tries the
smallest sizes first rather than a shuffled order.

**NPCs.** `entities/npc.py` is scenery that moves: a rig, an `Animator`, a
home and a three-state machine -- stand for an `idle` band of seconds, pick
a point within `leash` tiles of home that `is_walkable` accepts, walk there
in a straight line through `resolve_movement` (abandoning a walk that gets
nowhere for 0.8 s), stand again. No health, no collider anyone tests, no
effect on the run: the hero and the enemies walk through them. A lancer
patrols between the two spots of its guard post; a sheep is leashed to the
pen's interior rectangle and its walk is the bounce; the smith plays the
one-shot hammer `work` strip on some arrivals. Tuning is `data/npcs.json`
(speed, idle band, leash, probe radius, counts, the colour list).

`game/states/playing/npcs.py` builds them from `WorldLayout.villages`
under a `Random(f"{seed}:npcs")`: the smith at the forge's front, 0–1 pawn
per house plus 1–2 about the forge, one lancer per guard post, 2–4 sheep
where there is a pen. Colours cycle per kind (shuffled bag, no repeat until
every colour has appeared), never one per village. Only villagers within
three cull pads of the view are stepped; they draw through the character
layer (`_actor_items`) with the same blit, shade and ghost path as the hero.

Tests: `tests/world/test_npcs.py` (one shared headless run): a smith,
pawns, guards and sheep per village, all on the village; the smith by the
forge and the guards by their posts; colours mixed and every rig declared;
ten seconds of stepping with nobody off its leash, no sheep out of the pen,
nobody off the floor and somebody moving; villagers never block the hero;
the same seed builds the same people; they draw with the characters. World
+ spawn 365 green, the rest of the tier 927 green; `test_ghost` now picks a
sign clear of other ghosting art (the world moved under its pinned seed).

Screenshots: `HI3_village_overview.png`, `HI3_forge_smith.png`,
`HI3_sheep_pen.png`, `HI3_guard_post.png`.

Left for HI-4: `documentation/level_design.md` §1.2 / §1.7, re-pinning
`tests/world/digests.json`, and a note in the general journal.

---

## HI-4 — tests, digests, docs (2026-09-09)

- The tests landed with their milestones (`test_village.py`, `test_npcs.py`,
  and the updates to `test_houses`, `test_terrain`, `test_obstacle_families`,
  `test_interactables`, `test_repair`, `test_spawn_points`, `test_biome`,
  `test_ghost`).
- `tests/world/digests.json` re-pinned with `python -m tools.verification.world_digest --write`.
  The layout digests had already drifted before HI-0 (in-flight terrain
  work); every stage moves again here because the village draws from the
  world stream in `_assign_kinds`. Intended.
- `documentation/level_design.md` §1.2 (roles, the human topography), §1.7
  (the village pass, the pen exemption in the repair) and §1.8 (`villages`
  on the layout); a pointer in `journals/journal.md`.

**Open, for later.** Villagers are hero-sized (the pack's scale) and read
small against the buildings; `scale` in `character_sprites.json` is the
knob. Enemies may follow the hero onto the island and the active zone keeps
spawning on its neighbours; a leash at the bridge is a follow-up if wanted.
The forge handler waits for weapon forging.

---

## Sizes and a village scatter (2026-09-09, owner's request)

- **Houses +20%.** The house art scales off its collider, so `house`
  `radius` 34 → 41 in `terrain.json`; every house in the game, the
  scatter's included, since it is one kind.
- **New buildings and the forge −40%.** `render_scale` 1.0 → 0.6 for
  barracks, tower, archery, monastery, castle and forge, and their colliders
  scaled with the art: radii 48/34/50/48/64/40 → 29/20/30/29/38/24,
  satellites 52/58/92 → 31/35/55 px out at 18/18/24 px.
- **Trees and rocks on the village.** `_scatter` in `gen/village.py`, after
  the buildings: the island's own biome mix at `_V_SCATTER_SCALE` (1.0) of
  its density, every prop on ground with the coast pad, off the roads and
  the bridge mouths, `_V_SCATTER_GAP` (40 px) from every building so a
  canopy never covers a door; `shrub` stays decoration. Measured ~10 props
  a village (4 trees, a rock, a few pillars, the odd sign or scarecrow).
  `test_village` whitelists the scatter kinds.
- **Private RNG.** The village pass drew from the world stream after the
  tree top-up, so a top-up change moved the village's rocks and
  `test_boost_leaves_minerals_byte_identical` failed. It now keys a
  `Random(f"{seed}:village:{room.id}")` per island, like the bridges and
  the palettes, and takes nothing from the stream. Digests re-pinned.

---

## Designed round a centre (2026-09-09, owner's request)

The owner asked for the village to be built round a centre: the forge in
the middle, the town hall at the top, the rest of the buildings compact
and close together, and the decorations and trees spread round the centre.

- **Slots.** Eight angular slots round the forge. The north slot is the
  town hall's -- the pack's castle at 0.6, `_V_HALL_DIST` 3.5–5 tiles due
  north, on by default (`HEIGHTMAP_VILLAGE_TOWN_HALL`, replacing the old
  castle knob). The other seven take the monastery, the archery and 3–4
  houses in a shuffled order, one building a slot, each on `_V_RING`
  2.5–4.5 tiles and fanned up to 0.8 of a slot until it fits. Roads still
  cut through, so a village seats ~2.8 houses of the 3–4 it wants and the
  archery four times in five, measured over nineteen villages; on an
  island this size that is the compactness, not a bug.
- **The heal** moved in to 1.5–2.5 tiles of the forge.
- **Outside the cluster.** `_V_CLUSTER_RADIUS` 5.5 tiles: the village's
  own scatter (now `_V_SCATTER_SCALE` 1.5 over the island's cells, ~12
  props a village) places nothing inside it, and the bake's clutter pass
  (`terrain/decor/scatter_room.py`) uses the same disc round the forge as
  its centre-clear on a village island, so bushes and pumpkins keep out of
  the square as well. The disc travels on the record (`Village.radius`):
  the bake reads data and imports nothing from `world.gen`, which
  `test_layering` pins.
- Tests: `test_the_town_hall_stands_due_north_of_the_forge` (and off as a
  setting), `test_the_ring_is_compact_and_the_props_stay_outside_it`.
  Digests re-pinned.

---

## The north axis, clusters, closer (2026-09-09, owner's request)

The owner sent the monastery sprite: *that* is the town hall (the castle
read as a barracks), and it belongs on the tile above the heal zone. Also:
buildings closer together, houses clustered, military grouped.

- **Axis.** Forge at the centre; the heal zone `_V_HEAL_NORTH` (2) tiles
  due north of it, sliding up a tile if its spot is taken; the town hall --
  the monastery now, the castle is no longer placed -- `_V_HALL_NORTH`
  4–5.5 tiles due north, within π/12 of the axis.
- **Houses cluster.** A walk round the ring (`_V_RING` 2–4 tiles) off the
  axis (the north three slots of eight are the hall's), from a random slot
  one way or the other, each house within `_V_HOUSE_LINK` (3) tiles of the
  one before it and a spot that will not take a house stepped past in
  0.15 rad, until 3–4 stand. Fixed slots came first and left a house cut
  off from the rest on nine villages of twenty-four when a slot failed;
  the walk leaves none. `_V_GAP` 24 → 12 px, lane half-width 1.5 → 1
  tile: everything sits closer.
- **The forge slides for the axis.** The forge takes the nearest cell to
  the centroid that has ground two tiles north for the heal and four to
  five and a half tiles north for the hall; a centroid near the north
  coast used to put the hall in the sea (one village in five had none).
- **Military groups.** Per bridge, a row beside the road: barracks nearest
  it (`_V_MILITARY_FLANK` 1.8 tiles off), the tower `_V_MILITARY_PITCH`
  1.4 further, and at the first bridge the archery beyond that; the side of
  the road that seats more wins. Guard posts unchanged for the lancers.
- **The repair.** A tight cluster leaves slivers between houses the widest
  body can stand on but never reach, and `unseal` pulled a house out on
  three seeds of twelve. The village square is not enemy ground (nothing
  spawns there, the roads are kept a tile clear to the forge), so
  `_open_villages` clears every killer inside `Village.radius` before each
  flood -- the square is walked through, not judged -- in the repair and in
  `test_repair`'s baseline. Over sixteen seeds after: no building lost.
- Measured over twenty-four villages: hall 1.0, houses 3.1 (every
  cluster one piece), barracks 2.0, tower 1.8, archery 0.8. Tests: the axis test (heal above forge, hall
  above heal, both on the line), the cluster test (every house within
  three tiles of another; every military building within eight tiles of a
  bridge). Digests re-pinned.

---

## Military +25%, the corral at 0.6, sheep that stir, a third less island (2026-09-09, owner's request)

- **Military +25%.** `render_scale` 0.6 → 0.75 for barracks, tower and
  archery; colliders with it (36 / 25 / 38, satellites 39 / 44 px out at
  22).
- **The corral −40%.** The fence has its own pitch now, `_V_PEN_SCALE`
  (0.6) of a world tile: the ring's posts are laid 38.4 px apart from the
  pen's own origin rather than on the world grid, and the art is drawn at
  0.6 so it still meets post to post. `fence` radius 24 → 14 (a 10 px slit,
  under the hero's 20). `_place_pen` and `_pen_fits` work in world px; the
  ground check is the footprint plus one world tile. Pens on every village
  over the pinned and the first eight seeds.
- **Sheep.** Still 2–4 a pen. `SheepNpc` takes a leash of its own
  (`leash` 0.6 tiles) round the spot it stands on, clamped to the pen's
  interior; speed 40 → 22, idle 2–7 s: they stir rather than roam.
- **Island −35%.** `size` 0.67 → 0.56: walkable 377 → ~250 tiles (0.27 of
  a volcanic island), swept at 0.58 / 0.56 / 0.54 by what still fits. Two
  sample seeds then came out without a hall: the forge's axis check tested
  only the hall's primary disc, and a road from the north ran down the
  axis. `axis_room` now tests the hall's whole footprint with `fits`, and
  the hall may stand within π/6 of due north (beside such a road; the test
  allows three tiles off the line). Per village over thirty-two: hall 1.0,
  houses 2.7, barracks 1.8, tower 1.2, archery 0.7, pen 1.0. The tower is
  what the larger military row loses first.
- The village scatter keeps two tiles clear of the pen: a tree rooted
  just south of the rail hung its canopy over the whole 0.6 corral.
- Tests: the pen test reads the ring at its pitch; the hero-blocking test
  picks a villager standing in the open (the smith stands at the forge,
  and the forge was what it hit). Digests re-pinned.

## Garrison of four or five (2026-09-09, owner's request)

- **Lancers 4–5 a village** (`placement.lancers` in `data/npcs.json`), dealt
  round the guard posts in turn instead of one per post; a shared post's
  pair start from opposite ends. No military row at all → they muster at
  the forge. Over twelve seeds every village came out at 4 or 5.
- Tests: a per-village garrison count joins `test_npcs.py`.

---

## The hall on the heal's x, more trees (2026-09-09, owner's request)

- **Hall.** Straight above the heal on the very same x, `_V_HALL_ABOVE`
  2–3.5 tiles up (sliding only up), no angular fan any more. Since a road
  down the axis is the one thing the hall cannot step aside from,
  `axis_room` -- the check that sites the forge -- now tests the hall's
  full footprint against the roads a forge there would have, and the
  heal's ground, before it accepts a forge cell. Over thirty-two villages
  every hall stands on the heal's x; the test asserts the equality.
- **Trees.** `_V_SCATTER_SCALE` 1.5 → 2.5 and the biome's tree weight
  doubled in the village scatter (`_V_SCATTER_TREES`): trees a village
  4 → 7.7, rocks and posts about as before, still outside the cluster and
  two tiles clear of the pen.
- Digests re-pinned.

---

## The tidy pass, the square and the street (2026-09-10, owner's request)

Buildings painted over one another and over the heal (the art is two to
four times the collider). Landed as LD-Z in `level_design_journal.md`:
measured `paint` boxes on every village rig, art-aware `fits`, a tidy pass
(`world/gen/village_tidy.py`) that relocates or removes what paints over
the forge, the heal or the hall and pulls a house onto each flank of the
heal, roads that bend onto the street (the forge's row) instead of cutting
the square, the hall at 3–4 tiles above the heal, and the corral at 0.45
with the sheep unchanged. Over 43 villages: no clip, 42 heals with company
on both flanks, every pen and hall in place.

---

## HI-4 — a quarter less island (2026-09-12, owner's request)

**The request.** Reduce the island's size by 25 %, keeping every other
functionality the same. Confirmed as a quarter less *walkable ground*, the
reading the two earlier cuts used, not a quarter off the `size` number:
`size` scales the rect on both axes and the coast erosion costs a fixed
ring, so the literal 0.42 would have taken 56% of the ground and left a
third of the villages without a hall.

**Size.** `size` 0.56 → **0.51**: walkable mean 250 → 185 tiles (−26.1%),
0.27 → 0.20 of a volcanic island, rect 26–30 × 16–18 → 24–26 × 14–16.
Measured over 35 seeds / 52 villages; the even-tile rounding quantises the
steps, so 0.52 landed at −20% and 0.51 was the closest to the quarter.
Nothing else about the topography changed: flat, square coast, one bridge a
side, no lakes, the two meadow sheets.

**What the smaller island cost, and what was given back.** The buildings'
art does not shrink with the island, so the settlement gets tighter rather
than smaller. Two searches were too coarse for the new ground and now take
a second, finer pass *only when the first finds nothing*, so nothing that
already had a spot moves:

- `_place_pen` (`_V_PEN_SWEEPS`): the fan combs 0.1 rad instead of 0.3 and
  keeps a quarter tile of ground round the rail instead of half. Pens
  49/52 → **52/52**. A/B'd against the hand-typed fan it replaces and
  against the single pass: every pen that already had a spot kept it, to
  the pixel, and the three it gained are the three that had none.
- `flank_spot` (`_V_HEAL_FLANK_LAPS`): a wider lattice of flank offsets,
  still inside `_V_HEAL_NEAR`. The heal's full company 44 → 45 of 52, and
  no village is left with a bare sanctuary.

**What it cost anyway.** Houses per village 3–4 → 1–4 (44 of 52 still get
3–4); the heal's full company 51/52 → 45/52; the forge more than 5 tiles
off the island's centre on 3 of 52 (0 before). All three are the same
cause: a quarter less ground with the street, the north axis and the coast
taking the same absolute width as before. Keeping 3–4 houses everywhere
would mean re-tuning the settlement itself, which this request excluded.
Tried and rejected: judging the forge's cell on its ring as well as its
axis (moved the forge 5–7 tiles off centre), a tighter street
(`_V_STREET_REACH` 3.0: no more houses, worse company), a shallower coast
margin, a wider house ring, a longer house link.

**Tests.** Two "every village" assertions were holding on the four pinned
seeds by luck -- the heal's full company was already failing elsewhere at
0.56 -- so the owner asked for tests that measure the generation rather
than tests the generation has to satisfy. New module
`tests/world/test_village_quality.py`: fifteen shared worlds (the pinned
seeds plus the repair suite's twelve, so the sweep costs nothing in a full
run), twenty-three villages, split into what every village gets and what
the ground can refuse. Always: a forge within six tiles of the island's
centre, the heal due north on its x, a hall, a pen, a military building, a
house, a companion; the island 110-280 walkable tiles, flat, under 0.35 of
the smallest volcanic island and at least a third of its own rect.
Measured: 145-222 tiles, 0.16-0.26 of volcanic, fill 0.41-0.57, three or
four houses on 20 of 23 and the full company on 20 of 23 -- both asserted
as a rate of at least three in four. `test_the_heal_has_company` keeps the
floor and the both-flanks shape; `test_village_is_about_half_a_volcanic_island`
is now `..._is_smaller_than_any_volcanic_island`, since the ratio it named
has been wrong since HI-3 and the band lives in the new module. The bridge
test's "no over-cap bridge had a shorter lane" became the seating's own
measured rate (three of seventy-four over-cap bridges at 0.56, three of
seventy-three at 0.51: unchanged by this work, and its probe re-seats a
link in an empty world, so it never sees the gap the real pick has to
keep). Digests re-pinned.

Screenshots: `village_before_0.56.png`, `village_after_0.51.png` (seed 42,
the same island) and `village_after_seed2.png` (scratch, sent to the owner).

---

## A row of three to five houses (2026-09-12, owner's request)

**The request.** Place 3-5 houses this time; they may stand close together as
long as they do not disrupt the main heal area, forge and monastery. So the
row grew and the spacing between *houses only* went:

- `_V_HOUSES` 3-4 → **3-5**.
- `_V_HOUSE_GAP` (0 px): two houses may stand on adjacent tile centres, 64
  px apart, which still clears their 31 px colliders by 2 px -- nothing
  overlaps, they just touch. Every other pairing keeps `_V_GAP`.
- House art may paint over house art: `_Site.art_ok` and the tidy pass's
  `_unclip_buildings` skip that one pairing. Only that one. The forge, the
  heal and the hall keep their protected boxes, and the tidy pass still
  moves or removes anything -- house included -- that crosses them.
- `_fill_beside`: the houses the ring cannot seat go on a tile centre next
  to one it did, nearest the forge first, so the row closes up toward the
  middle. It runs **after the pen** has taken its ground: a village has one
  corral and may have five houses, and placing the houses first cost one
  village in fifty-two its pen.

Measured over 35 seeds / 52 villages: houses 1-5, **47 of 52 with three or
more and 36 with four or five** (before this: 3-4 always at `size` 0.56, and
1-4 with 44 of 52 at three or more once the island shrank). The heal's
company rose with it -- 46 of 52 have the full pair and seven of those have
three or four, since the crowding row gathers round the square. Hall 52/52,
pen 52/52. Verified over the same sweep: nothing paints over the forge, the
heal or the hall; no pairing but house-to-house paints over another
building; no two colliders overlap.

Tests: `test_no_building_paints_over_another` skips the house-to-house
pairing and says why; the rates in `test_village_quality.py` were
re-measured (20 of 23 villages at three or more, 16 of 23 at four or five).
Digests re-pinned.

Screenshots: `village_houses_seed42.png`, `village_houses_seed1234.png`
(scratch, sent to the owner) -- the second is the island that used to seat
a single house.

---

## A second decoration sweep, to fill out the island (2026-09-12, owner's request)

**The request.** After the buildings and facilities are placed, run another
decoration and tree placement sweep to fill the remaining empty spaces — not
too much, but enough to fill out the outsides of the island.

`_fill_scatter` (`world/gen/village.py`), run straight after the first
scatter and before the tidy pass, so anything it puts too near the square
is judged with the rest. Three things make it different from the scatter it
follows:

- **It sweeps, it does not throw darts.** The first scatter takes
  `cells * per_1000 * _V_SCATTER_SCALE / 1000` random shots at the island,
  so coverage is luck and the shore comes out half bare. This walks every
  walkable cell in order and offers the empty ones a prop.
- **It knows where the outside is.** `_edge_distance` is a breadth-first
  walk in from the coast: 1 on the shore, then inward. A cell within
  `_V_FILL_BAND` (3) tiles of the shore takes `_V_FILL_CHANCE` (0.5), one
  further in `_V_FILL_INNER` (0.3) of that. A radius from the middle would
  not do -- on a ragged island the middle is not where the coast is.
- **It keeps the square, not the cluster.** `_V_FILL_SQUARE` (4 tiles round
  the forge) instead of the first scatter's `_V_CLUSTER_RADIUS` (5.5). The
  cluster radius is a circle round the forge but the buildings are not: on a
  ragged island they all end up on one side and the lawn on the other is
  inside the circle with nothing in it, which is exactly the empty space
  this was asked to fill. Every prop still keeps `_V_FILL_GAP` (52 px) from
  every building and every other prop, which is what keeps it a meadow and
  not a wood.

`shrub` is dropped from the mix *before* the weighted draw rather than after
it -- it is decoration, not an obstacle, and it is a third of the meadow's
weight, so a one-visit-per-cell sweep would otherwise spend a third of its
cells on nothing.

Measured over 35 seeds / 52 villages: props a village 5.1 → **12.4**
(min 3, max 24), of which trees 211 → 523; props standing in the three-tile
shore band 247 → **618**; island cells with nothing within a tile 90% →
78%. The settlement's own ground is untouched.

Tests: `test_the_ring_is_compact_and_the_props_stay_outside_it` became
`..._stay_off_the_square` -- the cluster radius is no longer the prop rule,
so it now asserts the square (`_V_FILL_SQUARE`) and, in its place, the
spacing that does still hold for every prop on the island: its own radius
plus the building's plus `_V_SCATTER_GAP`, which is the stricter thing the
old assertion never checked. Digests re-pinned.

Screenshots: `village_fill_seed2.png`, `village_fill_seed42.png`,
`village_fill_seed1234.png`, `village_fill_seed7.png` (scratch, sent to the
owner).

---

## Four more trees a village (2026-09-12, owner's request)

**The request.** Increase the amount of trees by an average of four more.
Trees a village **10.1 → 13.9** over 35 seeds / 52 villages (total 523 →
724), from two changes that both keep the grove a grove:

- **`_V_TREE_GAP` (40 px):** trees, and only trees, have their own spacing
  now -- 15 px trunk + 15 px trunk + 40 = 70 px between centres, the figure
  the world scatter settled on (`_TREE_TREE_GAP_GRID`), where a canopy's
  near edge sits inside its neighbour by about a third. The first scatter
  already asked exactly this (`_V_SCATTER_GAP` is 40), so nothing changes
  there; it is the fill sweep, which asks 52 px of everything, that can now
  let two trees stand closer than it lets a tree stand to a rock.
- **`_grow_trees` (`_V_TREE_TOPUP` = 4):** four more trees a village, each
  grown beside one already standing, at the world scatter's own thicket
  offsets (`_TREE_THICKET_MIN_GRID`..`_MAX_GRID`). Raising the fill sweep's
  chance instead would have sprinkled four lone trunks over the lawn; this
  deepens the groves the island already has. Same guards as the sweep it
  follows: the square, the pen, the roads, the bridge mouths, the coast pad
  and the three protected boxes.

Props a village 12.4 → 16.1, island cells with nothing within a tile 78% →
74%.

Note for later: a tree may still stand with its canopy over a house, which
is the rule the village has had since HI-2 (a prop may stand before or
behind a house, so a tree by a house is legal) and is not new here; with
more trees it simply happens more often. If it should stop, the change is
to make `art_ok` treat a building's painted box as blocking for trees, or
to give trees a wider gap from buildings than from each other.

Screenshots: `village_trees_seed2.png`, `village_trees_seed42.png`
(scratch, sent to the owner).

---

## Denser clutter on the village island (2026-09-12, owner's request)

**The request.** Increase the density of the decorations as well: keep the
centre (the heal area) clean, but fill out the edges by around 35 % more.

The decorations are the bake's own non-colliding clutter -- the pebbles,
bushes, mushrooms and pumpkins of `data/terrain.json` `decorations` -- not
the obstacle scatter the last two entries were about. They are budgeted per
terrace by the biome's `decor.per_1000`, and a village island already blanks
a disc of `Village.radius` (5.5 tiles, `_V_CLUSTER_RADIUS`) round the forge:
the centre the owner asked to keep clean was already clean, so the whole
increase lands where it was wanted, on the ground between the buildings and
the shore.

`decor_placement.village_boost` (**1.4**) in `data/terrain.json`, applied to
the tier scales in `world/terrain/decor/scatter_room.py` for a village room
only. It is a data value, not a constant in code, because every other decor
rate in this system is.

Measured over eight seeds: clutter on a village island 32.9 → **45.0** props
(190.7 → 260.5 per thousand cells), **+36.8%**; every other island
unchanged at 134.2 (164.4 per thousand). The boost is 1.4 rather than 1.35
because the placement retries eat some of it: 1.35 measured +30%, 1.42 +40%.

Digests re-pinned (clutter is part of the bake, so the bake and draw digests
move with it).

Screenshots: `village_decor_seed2.png`, `village_decor_seed42.png` (scratch,
sent to the owner).
