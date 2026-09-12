# Placement review — obstacles, decorations, and the order they run in

A read-only review asked for on 2026-09-12, after the human island shrank a
quarter and gained a house row, a fill sweep and denser clutter (HI-4,
`human_island_journal.md`). Scope: how the world places obstacles and
decorations, the order the stages run in, and what has become dead weight.
Nothing here is implemented — this is the list, in the order I would do it.

Written against `eff0450` plus the uncommitted HI-4 work. Related but
distinct: `worldgen_modularity_todo.md` is the older structural review (test
cost, `world/rules/`, the terrain→gen edge). Its R5 (`world/rules/`) and R8
(retire the flat model) have since landed, and `world/pathfinding.py` is now
a 17-line shim over `world/nav/`, so R7 is largely done too. This file does
not repeat any of it.

---

## Measured baseline

Generation is **1.42 s a world** (3.34 s under `cProfile`; three seeds).
Cumulative cost per world, profiled:

| stage | cum |
|---|---|
| height maps (`islands.build_island`) | 0.86 s |
| inset fields (`rules/inset.build`, of which `_chamfer` 0.64) | 0.82 s |
| spawn points + resource anchors | 0.73 s |
| unseal repair | 0.63 s |
| obstacle scatter | 0.23 s |
| the village pass | below the top 30 |

A world carries **415 obstacles** (212 trees); a village island carries ~45
decor props. **Placement is not the hot path** — so the case for touching it
is legibility, and the one measurable speed win is in the spawn-point stage
(D1), not in the scatter.

---

## A. Complexity and duplication

**A1. Five near-identical placement loops.** `village.py` `_scatter` (:579),
`_fill_scatter` (:647) and `_grow_trees` (:701) are 146 lines running the
same five-condition guard — ground + coast pad, bridge mouths, gap, lanes,
art — differing only in the gap and in how the candidate point is chosen.
`_Site.circle_ok` (:231) is that chain again without `art_ok`, and
`scatter.py` `_scatter_obstacles` (:232) / `_topup_trees` (:338) are the same
pair at world scale. One `_Site.prop_fits(kind, x, y, gap)` plus a shared
"anchor → thicket offset" helper would leave each pass owning only its
candidate generator.
*Risk:* the RNG draw order must be preserved exactly, or every world moves.
That is the whole risk, and the digests are the test.

**A2. `_lay_out` is 245 lines** (`village.py`:332) — eight numbered steps in
one function. The numbered comments are already the function names; each
step takes `_Site` and mutates it. Biggest readability win in this code and
mechanical to do. *Risk:* low, same caveat as A1.

**A3. `build_decor_scatter` is 135 lines** (`world/terrain/decor/scatter_room.py`:18)
at five levels of nesting (room → terrace → entry → count → try). The inner
try is a self-contained "place one prop or give up".

**A4. Four "keep the centre clear" rules now coexist** where there used to be
one: `_clear_radius` (`scatter.py`:209) for the world scatter,
`Village.radius` (`layout.py`:210) for the bake's decor, `_V_FILL_SQUARE` for
the fill sweep, and `decor_placement.centre_clear` in `terrain.json` for
every other island. Propose `Village` carry both radii (settlement, square)
and every pass read them, so a change to the settlement's extent cannot move
only some passes. *This is new drift, introduced by HI-4.*

**A5. Four gap constants for one concept:** `_OBSTACLE_GAP` 46,
`_V_SCATTER_GAP` 40, `_V_FILL_GAP` 52, `_TREE_TREE_GAP_GRID` 55 /
`_V_TREE_GAP` 40. The per-pair special cases now inside `_Site.free` (house↔
house, tree↔tree) are the seam where this starts to smell; a small
pairing → gap table would replace both the constants and the branches.

---

## B. Order

**B1. The pipeline order is sound** and each step's reason is written down:
obstacles after the world is shifted to the origin so keep-clear rects match
final coordinates, the village after the scatter, the unseal repair after
both, spawn points and chests last on private RNG. **No change proposed.**

**B2. One village step is out of place for a real reason.** `_fill_beside`
(the houses the ring could not seat) sits between the pen and the scatter
because the pen must claim its ground first. That is a *priority*, not a
sequence, and it reads as an accident. Make the pass list explicit, with the
priority stated per entry.

**B3. Two frozen-history constraints still shape the code.** The variant pass
runs before `_topup_trees` "so every obstacle keeps its exact `variant` draw"
(`scatter.py`:319), and `shrub` rides the weighted pick with a zero radius
purely so spacing draws stay byte-identical to when it was an obstacle
(`scatter.py`:86, :334). Both cost a reader real effort and, since the
digests are re-pinned on every world change anyway, buy nothing now.
*Caveat:* dropping `shrub` from the mixes changes densities — it consumes
slots — so it is a re-tune of `per_1000`, not a free delete.

---

## C. Dead or meaningless code

**C1.** `_tree_spacing(room)` (`scatter.py`:62) takes a room, ignores it, and
returns three module constants. Two call sites. Delete.

**C2.** `elite_arena` is retired from `SPECIAL_KINDS` and can never be
placed, but is still wired through `entities/interactable.py`:23,
`locations.py`:49 and :159, `rendering.py`:214, a forwarder at
`state.py`:663, and a test that hand-builds one. Remove it, or record here
that it is parked deliberately.

**C3. Stale comments.** `tuning.py`:17 says `_DIRS` is "defined once in
tuning.py:11" — it is line 20. `tuning.py`:61 still says "a village island is
~34 x 18 tiles of ground"; it is ~24 x 14 after HI-3/HI-4, and that
sentence's conclusion about the ring is now precisely why houses fail to
seat on the tightest islands.

**C4. Lists rebuilt inside loops**, both from the HI-4 work: `village.py`:729
rebuilds the tree list on each of up to 120 tries, `village.py`:766 re-sorts
the houses on every placement. Build once and append, as `_topup_trees`
already does with `tagged`.

**C5. To verify, not assume.** The inner-rect containment scan in `_pen_fits`
(`village.py`:894) may be implied by the per-post `free` checks. It probably
still catches a prop *inside* the ring with no post near it — write the test
before anyone deletes it.

---

## D. Performance, where it actually is

**D1.** `spawnpoints.obstacle_free` (:123) — 10.3k calls and ~832k distance
comparisons a world, the largest O(n·m) left in generation. `_Neighbourhood`
(`world/terrain/decor/spacing.py`) exists for exactly this, but its
`blocked()` takes the *larger* of two gaps where this rule needs the *sum*:
either add a sum mode or hash-then-verify. ~10% off generation, identical
output.

**D2.** `spawnpoints.on_keepout` (:120) — 38k linear scans a world. Same fix,
same trip.

**D3.** The scatter's world-wide `for o in out` scan is **not** worth fixing
for speed at 415 obstacles. If it is touched, it is for symmetry with D1.

**D4.** For the record, the real hot spots are outside this review's scope:
`inset._chamfer` (0.64 s a world profiled), `build_island` (0.86), `unseal`
(0.63).

---

## Order of work

1. **One no-behaviour-change pass:** A2, then A1, then C1, C3, C4. The test
   is that `tests/world/digests.json` does **not** move.
2. **D1**, verified the same way — identical output, ~10% faster.
3. **A4 and A5**, which tidy the drift HI-4 introduced and may move worlds;
   re-pin and record the new figures.
4. **The judgement calls, B3 and C2**, each with its own journal entry: both
   change what a world contains.

---

## Pass 1 landed — no behaviour change (2026-09-12)

Items **A1, A2, C1, C3, C4**. The test for the whole pass was that the worlds
do not move, and they did not.

**How it was verified.** A 19-seed A/B (seeds 1–16, 35, 42, 1234) hashing the
layout digest plus every obstacle's kind, position, variant, radius, skin and
biome, every `Village` record, and every spawn point — captured before the
first edit and re-run after each step. All 19 byte-identical at every step,
and `tests/world/digests.json` never moved.

*The A/B script needed fixing before it could prove anything*: the first
version hashed `SpawnPoint.tags`, a `frozenset`, whose iteration order is
per-process — so every seed "moved" on the first run. The pinned digest test
is what caught the false alarm. Worth remembering for the next refactor: hash
sorted contents, never a set's repr.

**A2 — `_lay_out` split.** 245 lines → a 25-line `_lay_out` that reads as the
eight steps it always was, plus `_seat_forge`, `_lay_roads`, `_seat_axis`,
`_seat_houses`, `_seat_military`, `_seat_pen`, `_decorate`, `_record`. Longest
function in the module is now 56 lines. Bodies were moved verbatim — the split
was done by slicing the original text on its own numbered comments, not by
retyping — so the RNG draw order could not drift. Two locals were hoisted to
the caller (`mouths`, `fvec`); nothing else crosses a step boundary that is
not returned.

`_fill_beside`'s call moved up into `_lay_out`, where the priority it encodes
is now visible at the call site: the corral claims its ground before the house
row is finished, because a village has one pen and may have five houses. That
is review item **B2**, and it cost nothing to do here.

**A1 — one guard for every prop.** `_Site.prop_fits(kind, x, y, gap)` replaces
the five-condition chain that `_scatter`, `_fill_scatter` and `_grow_trees`
each carried by copy. One subtlety: `_scatter` used to call `free()` without a
kind, so tree-to-tree there used `_V_SCATTER_GAP`; through `prop_fits` it uses
`_V_TREE_GAP`. Both are 40.0, so the worlds are identical — but the two are
now coupled, which is the intended direction (the tree-to-tree rule should be
one rule) and is worth knowing if either number changes.

**Not done, deliberately:** the shared "anchor → thicket offset" helper the
review floated for `_grow_trees` and `_topup_trees`. They consume RNG
differently — `_topup_trees` draws degrees and rotates a vector,
`_grow_trees` draws radians — so unifying them *would* move every world. It
belongs in a pass that is allowed to, not this one.

**C1** `_tree_spacing` deleted (two call sites now read the constants).
**C3** the two stale comments corrected — `_DIRS`'s self-reference, and the
village-island size, which had said ~34 x 18 tiles since before HI-3.
**C4** the tree list and the house row are gathered once and appended to,
instead of being rebuilt on each of up to 120 tries.

Two dead locals the split exposed (`fvec` in `_seat_forge`, `px` in
`_seat_pen`) and one left by A1 (`r` in `_grow_trees`) were removed.

**Still open:** A3, A4, A5, B3, C2, C5, D1, D2 — see the order of work above.

---

## D1 landed — the spawn-point obstacle test, indexed (2026-09-12)

`_Island.obstacle_free` tested every candidate against every obstacle on its
island: ~10k calls a world over ~80 obstacles each. It now asks a spatial
hash, and the worlds are identical (same 19-seed A/B as pass 1).

**The helper moved rather than being imported across a layer.**
`_Neighbourhood` lived in `world/terrain/decor/spacing.py`, and
`world/gen/spawnpoints.py` importing it from there would have added a
gen → terrain edge -- the wrong direction, and the older review
(`worldgen_modularity_todo.md` R6) is about cutting that coupling, not
adding to it. It is pure geometry with no knowledge of props or terrain, so
it is now `world/rules/spacing.py`, beside the other shared rules both
layers already import. `git mv` plus two import lines; the decor pass is
otherwise untouched.

**It needed a second query, not a second class.** `blocked()` takes the
*larger* of the stored and queried separations, which is what prop spacing
means. A spawn point needs the *sum*: the obstacle's radius, plus the body
radius of the class that will stand there, plus `_SPAWN_OBSTACLE_GAP`. New
`within(x, y, extra)` adds them. The store carries `radius + gap` and the
query passes the body radius, and the hash's cell is sized to the widest sum
any query can produce -- widest obstacle + gap + widest body -- or a
rejecting obstacle could sit outside the nine cells searched.

**Measured, and smaller than the review predicted.** A/B'd in one process by
swapping `obstacle_free` back to the scan it replaced, 12 builds each:
median **1.726 s → 1.643 s, 4.8% off a world build**. The review's "~10%"
came from the function's share of a *profiled* run, and cProfile inflates a
function called thirty thousand times; 4.8% is what it is worth in wall
clock. Worth having and not worth chasing further.

**One test moved with it, and was right to resist.**
`test_layering.py` pins the contents of `world/rules/` on purpose -- the
package's own docstring calls the list "what keeps the package from becoming
`common`" -- so adding a module there fails it by design. The addition is
justified under the hardest reading of that rule (the hash imports nothing at
all, not even the data model), so the list now includes `spacing` and says
why, and a second test asserts the file's import set is *empty* -- so it
cannot quietly grow a dependency and turn the shared helper into a back door
between the generator and the bake.

**What that says about D2.** `on_keepout` is 38k calls a world over a much
shorter list than the obstacles, so by the same arithmetic it is worth well
under a percent. Demoted: do it only if that file is open anyway.
`_against_something` (:298, the resource anchors) is a third scan over the
same obstacles, asking a fixed 1.5-tile reach; it would want a third query
convention for a share that has not been measured. Both left alone.

---

## A4 and A5 landed — and neither had to move a world (2026-09-12)

The review expected these two to change world output. They did not, once the
work was framed as "say it once" rather than "pick a new number".

**A4 — the discs.** `_Site` now converts both to world px in one place:
`settlement` (`_V_CLUSTER_RADIUS`, the whole village's extent) and `square`
(`_V_FILL_SQUARE` -- the forge, the heal above it, the hall above that). The
first scatter reads `site.settlement`; the fill sweep and the tree top-up read
`site.square`. No pass multiplies tiles by `px` for itself any more, and the
two constants have exactly one use each.

`square` is deliberately **not** on the `Village` record. Adding it there was
the first cut, and it moved all nineteen seeds -- not because any obstacle
moved, but because `world/digest.py` hashes the dataclass, so a new field
changes the digest on its own. Nothing downstream reads the square, so the
field would have bought nothing and cost every pinned digest its meaning: the
next bisect over "what changed the world" would have had a false positive in
it. `radius` stays exported because three consumers read it (the repair, the
bake's clutter pass, and the record's own readers).

*Method note, worth keeping:* the A/B hashes the layout digest **and** an
explicit field-by-field placement hash. That is what separated "the schema
moved" from "the world moved" in one run -- the layout digest moved on 19
seeds, the placement hash on none. A single digest could not have told them
apart.

**A5 — the gaps.** Two questions were tangled in four constants. Each *pass*
carries a default -- how far what it places keeps from everything standing
(`_V_GAP` for buildings, `_V_SCATTER_GAP` for the first prop sweep,
`_V_FILL_GAP` for the second, `_OBSTACLE_GAP` for the world scatter) -- and
separately a few *pairings* answer differently whoever is asking. Those
exceptions are now one table each: `_V_PAIR_GAPS` (house↔house, tree↔tree)
read by `_Site.free`, and `_PAIR_GAPS` (tree↔tree) read by both world-scatter
loops. The per-pass defaults stay, because they are a real distinction: the
fill sweep is meant to be more generous than the sweep before it.

The two tables are deliberately **not** merged. The village's tree↔tree gap is
40 px and the world's is 55; merging them would move every world, and the
numbers differ for a reason -- a village's trees frame a settlement, a
wilderness island's are a wood.

**Still open:** A3, B3, C2, C5, D2 -- and D2 is demoted by the D1
measurement. A3 (`build_decor_scatter`, 135 lines, five levels deep) is the
last structural one worth doing.

---

## A3 landed — the decor scatter, in three pieces (2026-09-12)

`build_decor_scatter` was 135 lines and five loops deep: room, terrace,
registry entry, count, try. It is now 59 lines and three (room, terrace,
entry), with the two inner loops behind names:

- **`_Bake`** — what holds for the whole world: the placement knobs, the rig
  loader, the obstacle index, and the prop index's cell size. Built once.
- **`_RoomSite`** — one room while its clutter is seated: the disc kept clear
  at its centre (the island's, or the village's settlement disc), the village
  boost, what has gone down, and the index that spaces the next one.
- **`seat(entry, where, scale)`** places one registry entry's share of a
  terrace's budget; **`spot(where, reach, gap)`** tries six points for one
  prop and returns the first that passes, or `None`.

The village's clutter boost moved into `_RoomSite` with the rest of the
per-room state, which is where it belonged: it is a property of *this room
being a village*, not a branch in the middle of the entry loop.

**Verified** with an A/B of its own, since the generation A/B does not reach
the bake: every decor prop of nine seeds hashed by rig, anchor, frames and
position -- **9,551 props, all identical** -- plus the pinned bake digest.
Suite green (935), and the decor tests re-run against the final state after a
last cleanup (two `_Bake` slots nothing read).

**Worth keeping from this one:** the split needed a *third* A/B harness.
Generation has two (the pinned digests and the 19-seed layout/placement
sweep), and neither sees the bake. If more of the bake gets refactored,
`decor_ab.py` is the shape to reuse: hash what the pass produced, not what
the pass is.

---

## Review status

Done: **A1, A2, A3, A4, A5, B2, B3, C1, C2, C3, C4, C5, D1**.
Open: **D2** only, demoted by the D1 measurement to well under a percent --
worth doing if `spawnpoints.py` is open for another reason, not on its own.

Worth carrying forward from the whole pass:

- Generation output moved exactly once, for B3, where moving it was the
  point. Every other item was A/B'd to byte-identical worlds before the
  suite was trusted.
- Three A/B harnesses, because one does not cover the ground: the pinned
  digests, a 19-seed layout **and** field-by-field placement hash (they
  disagreed once -- a new dataclass field moved the digest without moving a
  world), and a decor hash for the bake, which the other two never reach.
- Twice the first answer was wrong and measurement corrected it: D1 was
  worth 4.8% rather than the ~10% the profile implied, and C5's first test
  passed for a reason that had nothing to do with the line it was testing.

---

## C2 landed — the elite arena removed (2026-09-12)

Retired by the brief long ago, never placed since (`SPECIAL_KINDS` has not
listed it), and still wired through eight places. All of it is gone:

- `entities/interactable.py`: the kind, and the `state` / `arena_ids` slots
  that existed only for it. `Interactable` is four fields lighter, and the
  render path's `done = it.used or it.state == "done"` is just `it.used`.
- `locations.py`: `update_elite_arenas` (26 lines) and the guard in the
  use-check that skipped arenas.
- `state.py`: the per-frame call and the test-facing forwarder.
- `world/terrain/render.py` (its room-kind colour), `world/README.md` (the
  kinds list), `world/gen/tuning.py` (the comment explaining it was dormant).
- Its two tests: the behaviour test, and `test_repair`'s guard that no room
  comes out with that kind -- moot once the kind does not exist.

**And the spawn owner it was the only producer of.** `arena` was on the
master's `cap_exempt` and `never_sleep` lists in `data/spawn_tables.json`.
That rippled into four tests which used `"arena"` as their stand-in scripted
owner; two of them genuinely read the data lists and would have started
failing, two only needed a valid name. They now use `dev` and `dummy`, which
are real. `test_master` asserts the exact `cap_exempt` list on purpose -- "an
owner that bypasses the cap has to be added on purpose and seen here" -- and
that tripwire did its job: it is now `["dev", "dummy"]` with a line saying
why.

Not touched: `elite` the *enemy* -- the tag, the spawn chance, the two
`is_elite` enemies and their potion band are all live and unrelated. The
grep that matters is `elite_arena`, not `elite`.

---

## B3 landed — two frozen-history constraints (2026-09-12)

Both existed to keep an old RNG stream byte-identical, and both cost a reader
real effort to decode. Worlds move here; that is the point, and the digests
were re-pinned.

**The phantom shrub.** `shrub` rode the weighted pick with a zero radius,
was placed into the obstacle list, reserved `_OBSTACLE_GAP` of space against
everything placed after it, and was then filtered out of the returned list.
It is gone from every biome's `scatter.weights`, and each biome's `per_1000`
is scaled down by the share it used to take (meadow 85 → 58, forest 100 → 70,
drab 80 → 61, wetland 75 → 56, rock 140 → 128, sand 45 → 37) so the number of
*real* attempts a terrace gets is what it was.

Measured over eleven seeds, that arithmetic held: **obstacles a world 479.6 →
480.4**. The mix shifted slightly -- trees 229.5 → 223.9, rocks 114.7 → 118.5,
pillars 74.8 → 76.2 -- because the phantoms had been reserving space, and the
kinds that gain are the ones that were easiest to reject (a canopy reaches
four tiles north, a boulder half of one). Two or three percent, and worth
knowing rather than hiding: if the tree count matters more than that, the
meadow's tree weight is the knob.

Bushes are unaffected -- they are `bush_a..d` in the bake's `decorations`
registry and always were; weighting a shrub in the *scatter* only ever spent
a slot.

**The variant pass.** Every obstacle's decoration `variant` was assigned in a
separate loop after placement, and `_topup_trees` had to run after *that*, so
that adding variants had not moved any world. The draw now happens where the
obstacle is constructed and the loop is gone.

**The village's own copy.** Both village sweeps tested each draw against
`KINDS` and skipped what was not an obstacle. That branch can no longer fire,
but deleting it outright would make a future decoration entry in a biome mix
raise on `KINDS[kind]`, so both now filter the mix *once* before drawing --
which is what `_fill_scatter` already did, and is now consistent.

**Tests.** `test_biome` required `shrub` in every biome's weights; it now
forbids it, with the reason. `test_obstacle_families` gains the stronger
guard that keeps it retired: no biome may weight a shrub at all, not merely
"no world returns one".

---

## C5 settled — the pen's containment test stays, and is now pinned (2026-09-12)

The review flagged `_pen_fits`'s last line -- no placed obstacle's centre may
lie inside the pen's footprint -- as possibly implied by the per-post checks,
and said to write the test before deleting anything. Good call: the answer was
not the obvious one.

**Measured first.** Instrumented over thirty-two villages: the containment
test **never once** rejected a candidate the posts had accepted, and deleting
it moved no pen on twenty-two seeds. On that evidence alone it looks dead.

**The geometry says otherwise.** A post rejects a centre closer than
`fence_r + radius + _V_GAP`; the deepest point inside a 7x5 pen is 72 px from
the nearest rail. For a tree that threshold is 38 px, so a tree can stand in
the middle of a candidate footprint with every post comfortably clear of it.
And `art_ok` for a fence post is tested against **buildings only**, so the art
rule does not catch a prop either. The pass that meets this is the tidy pass:
`_repen` re-seats a pen whose posts ended up under something's art, and it
runs *after* the scatter, when the island is full of trees and rocks.

So: kept, with a test that builds exactly that case -- a real village island,
a footprint that fits clean, a tree at its centre -- and asserts both halves:
every per-post rule accepts, and `_pen_fits` refuses anyway.

**The first version of that test was worthless, and only mutation-testing
showed it.** It used a *tower* in the middle, passed, and went on passing with
the containment line deleted: a building's painted box is far larger than its
collider, so `art_ok` was rejecting the footprint and the assertion never
exercised the line it named. The rule this leaves behind: after writing a test
for a specific line, delete that line and watch the test fail. A test that
passes either way is worse than no test, because it argues for keeping code
nobody has actually checked.

---

## D2 attempted, measured, and reverted (2026-09-12)

Done as asked, and the answer is that it should not be done.

**The scan is bigger than the review said.** `on_keepout` is asked ~11,400
times a world against ~58 rects an island: **675,000 rectangle tests**, the
same order as the obstacle scan D1 fixed. The review's "worth under a
percent" was reasoned from a list I had assumed was short. It is not short.

**And it still does not pay.** Three implementations, benchmarked in one
process with the runs interleaved to cancel drift, four repetitions of four
seeds each:

| | median a build |
|---|---|
| the scan, as it stands | 1.480 s |
| bucketed by tile (hash then verify) | 1.462 s (+1.3%) |
| a frozenset of tile coordinates, no rect test at all | 1.502 s (−1.5%) |

All three inside noise. `Rect.collidepoint` is a C call, so 675k of them cost
less than the per-call Python arithmetic an index adds -- a tuple key, two
floor divisions and a dict lookup, eleven thousand times. Both variants were
verified equivalent first (72,426 calls, zero disagreements; every keepout
rect is one aligned tile), so this is a measurement, not a bug.

So `spawnpoints.py` keeps the scan, with a comment saying it was measured and
why it stays, and the `_RectIndex` written for it was deleted rather than
left unused.

**The lesson is about the profiler, and it is the third time this pass.** The
profile attributed 0.881 s to `on_keepout`; wall clock says ~0. cProfile
charges per-call overhead, so a cheap function called often looks like a hot
spot and a C call inside a generator looks like Python work. D1 was predicted
at ~10% and measured 4.8%. D2 was predicted at ~25% of a profiled run and
measured nothing. **Rank optimisation candidates by wall-clock A/B, and treat
a profile as a list of suspects rather than a verdict.**

## Fixed in passing: comment keys in the spawn tables

Unrelated to the review, found because it blocked every content load: the
owner's in-flight `_starved_comment` in `data/spawn_tables.json` failed
validation, because `spawn/tables.py` requires every key in `placement`,
`locality`, `population` and `watchdog` to be a number. The rest of the data
layer treats `_`-prefixed keys as comments (`game/content.py` skips them in a
dozen places, `potions.json` documents its bands that way), so the validator
now skips them too.
