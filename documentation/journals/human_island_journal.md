# Human island — dev log

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
15. Re-pin `tests/world/digests.json` (`python -m world.digest --write`).
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
- `tests/world/digests.json` re-pinned with `python -m world.digest --write`.
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
