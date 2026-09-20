# North stairs — dev log

A straight flight on the **north** rim of a plateau, so an island can be
climbed from its back and not only from its south wall and its two flanks.
Milestones are prefixed **NS**. Same rules as the other logs: full suite
green per milestone, digests re-pinned when generation moves, nothing
committed unless asked.

**Status:** NS-0 to NS-5 **COMPLETE** (2026-09-14). NS-0 to NS-4
committed as `00bc70c` (full default suite green: 2193 passed). NS-5 is
in the working tree, world and render tiers green (620 passed);
uncommitted.

---

## The request (2026-09-14)

The user's snip showed the north side of a volcanic island's plateau: teal
second-floor stone to the south, green ground floor to the north, and a
one-tile bite in the rim marked with an X. The ask: make that cell a
gateway between the two floors, the way the south wall has its straight
flights and the flanks their lateral crossings.

The notch in the picture is only how it happened to look. The rule is
general — **any** rim cell on the north edge may become the flight:

    = = = = = =            = = = = = =
    # # # # # #     ->     # # # ^ # #
    # # # # # #            # # # # # #

`=` is the ground floor, `#` the top floor, `^` the staircase. The flight is
carved out of the top floor's own rim cell; it takes nothing from the
ground floor, and it needs no pre-existing gap.

This is world and level-design generation work. The tile is undecided, so
the flight is drawn as a plain interior ground tile until one is chosen.

## Decisions

- **Orientation is a field, not a tag.** `Cell` gains `dir: str = "s"`,
  the direction a straight flight descends. `tag` keeps carrying
  grass/rock for straight flights and the `w`/`e`/`side_` vocabulary for
  east/west ones; stacking a second prefix onto it is what makes such
  fields unreadable. `TileMeta.ramp` already says `s`/`w`/`e` and simply
  gains `n`. The default `"s"` keeps every existing `Cell(...)` call and
  every pinned expectation about south flights unchanged.
- **The cell is the plateau's own rim cell.** A south flight lives in the
  wall between the plateau and the low ground; a north flight lives in the
  rim cell itself, because a north face has no wall. Both leave the
  plateau's interior alone and both sit between the two floors.
- **One cell per flight.** A north face has no depth to fill, so the flight
  is one cell whatever the drop (1 or 2, as `MAX_DROP` allows). `row` is 0
  and `drop` is the level difference, so everything that reads
  `row == 0` for the head keeps working; only which end opens where is
  mirrored.
- **Site rule** (`_nstair_site`): the cell is ground at level `L > 0`;
  the cell north of it is ground at `L - d`; the cell south of it and
  both flanks are ground at `L`; and the landing beyond the foot is a
  place a large body can stand — the two cells beside it and the one
  north of it are ground at `L - d`, the same clearance rule the lateral
  crossings use.
- **Placement** uses the regional quota, the spacing and the shuffled
  buckets of `_cut_flights`, in a pass of its own after every other
  flight and off a restored stream, so a region on the north rim, which
  has no wall and so never had a candidate, gets its own way up and
  nothing downstream sees a different world. A plateau still stranded
  afterwards is joined from its back.
- **Connectivity.** Row 0 opens *north* onto ground at `L - d` and *south*
  onto ground at `L`. `walk_links` is the authority; `steps._flight_opens`
  mirrors it; `check_grid` gains the invariant.
- **Rendering placeholder.** The cell is painted with the plateau sheet's
  plain interior tile on the plateau's own band, no sprite and no drop
  shadow (a shadow falling north fights the lighting, the same rule the
  ground casters follow). The plateau cell south of the flight does not
  fringe north — its floor runs on into the flight — and the flanking
  cells keep their north lip, so the gateway reads as a bite in the rim.
- **Out of scope for now:** grass/rock styling of the north flight and
  its final art; carving a rim where none qualifies.

## Todo

**NS-0 data model** — `Cell.dir`, ASCII glyph `^`, `TileMeta.ramp = "n"`.

**NS-1 generation** — `_nstair_site`, north candidates in `_cut_flights`
and `_link_levels`, `_free_flight_feet` skips them, `check_grid` invariant.

**NS-2 runtime** — `walk_links` and `steps._flight_opens` mirrored ends.

**NS-3 painter** — plain interior tile, no shadow, rim fringe rules.

**NS-4 tests and pins** — hand-built grid tests for the site rule and the
step rule, shared-world tests that north flights exist and are walkable
end to end by both nav classes, digests re-pinned, screenshot delivered.

---

## Log

### What landed (2026-09-14)

**The data (NS-0).** `Cell.dir` in `world/layout.py`, default `"s"`, so
no existing constructor moved; `to_ascii` draws a north flight as `^`;
`TileMeta.ramp` carries `cell.dir` for straight flights, so it reads `"n"`
here and `"s"` as before.

**Generation (NS-1).** `_nstair_site` in `world/gen/height/flights.py`
is the site rule from the Decisions above. `_cut_north_flights` is its
own pass: it buckets north sites by the same region, spacing and quota
`_cut_flights` uses, against every crossing already standing, and then
joins any cap still stranded from its back, the way `_link_levels` does
from wall sites. It runs after `_link_levels` and **off a restored
stream**, exactly as the lateral crossings do. The first build had the
north candidates inside `_cut_flights` itself, drawing once per
candidate cell; that moved the stream for every stage after it, and
seed 42's village lost its hall and its pen to a layout the tidy pass
could not save (four village tests, none of them about stairs). With the
pass isolated, everything but the north flights is byte-identical to the
world before. `_free_flight_feet` skips north flights (there is no stone
south of one to give back). `check_grid` complains about a north flight
with no low landing north or no terrace south.

**The cut is provisional.** The first build left three flights on seeds
35 and 7 with a missing flank. A rim cell can be the only thing joining a
strip of terrace to the rest -- level 1 pinched between the low ground
and a level-2 cap -- and a flight links only at its ends, so taking the
cell stranded the strip and `_prune_unreachable` deleted it, flank
included. `_cut` now keeps a north cut only if both flanks still reach the
terrace south of the flight, and rolls it back otherwise, the same guard
the lateral crossings use. The stranded-cap loop walks on round its
candidate list from the drawn start when a cut is rolled back, one RNG
draw either way.

**Runtime (NS-2).** `walk_links` and `steps._flight_opens` gain the
mirrored branch: row 0 opens north onto ground at `level - drop` and
south onto ground at `level`. Nothing else in nav, collision, the inset
field, the scatter keep-outs or the level index needed to change; they
all read the link rule.

**Painter (NS-3).** `grid_paint` paints a north flight as the plateau
sheet's plain interior tile on the plateau's own band, casts no shadow
for it, and lets the terrace cell south of it run on unfringed. The
result reads as a one-tile bite out of the rim's lip, which is the
gateway. Placeholder until the tile is chosen.

**Tests and pins (NS-4).** `tests/world/test_north_flights.py` (18):
hand-built rims for the site rule, the rollback, `_cut_flights`,
`_link_levels`, the link rule, the `check_grid` complaints and the ASCII
glyph; on the shared worlds, that the generator places them, that every
one sits on an intact rim, that tile meta says `"n"`, that the runtime
rule mirrors the generator on every one, that both nav classes climb
every one in both directions, and that the cell is painted opaque on its
terrace's band with no shadow. `test_elevation`'s head-to-foot walk
takes a north flight from its terrace down to the low ground. Digests
re-pinned. The digest tool's pin path was one directory short since the
tools folder moved; fixed.

**Measured** over six seeds (35, 7, 1234, 42, 3, 99), with the pass
isolated: 106 north flights against 73 wall-cut and 324 lateral; per
plateau 0 to 7, mean 2.3, in line with the two to three laterals a side.
Nine of the 47 plateaus carry none -- small upper caps whose whole rim is
within spacing of a crossing already standing. Every world validates.

**Nav note.** The large class walks a 48 px lattice against 64 px tiles,
so a landing tile's centre maps to one nav cell that can straddle the
tile below, and a tree standing diagonally off the landing can take that
one cell's clearance under the radius. The tile is still crossed through
its other cells, so the test samples the tile's quarter points. Same
keep-out rule as every other flight (the flight and its two landings).

**Screenshot delivered**: seed 35, island 1, a level-1 north rim with the
flight outlined, plus the full frame.

### NS-5 — the stone flight, upside down (2026-09-14)

The user asked for the flipped `vstairs_1` from the orientation survey to
be the north flight's tile. Measured first: every north flight over six
seeds is a one-level drop (concentric caps put level 1 north of every
level-2 rim), so only the 64 px sprite is ever needed, and the tags split
57 rock / 49 grass.

- `TileSheets.vstair_sprite(drop, north=True)` in `world/terrain/sheets.py`:
  the same art flipped vertically at load, cached under its own key. No new
  file -- the source has no north-ascending flight and a flip is the whole
  of what one would be. The prep script can bake a `vstairs_1n.png` later
  if the lighting wants hand-fixing; the loader would then prefer the file.
- `grid_paint`: a **rock** north flight paints the interior tile and then
  the flipped sprite through the tall-sprite pass, on the plateau's band.
  A **grass** north flight stays the plain tile: with no wall to cut a
  channel through, the bare gap in the rim's lip is the grass reading, so
  the two styles come for free as they do on the south wall. The interior
  tile under a rock flight is what shows in the sprite's transparent side
  margins, so the stone sits in plateau grass rather than over a hole.
  After the flip the full-width rows sit north, so nothing leaks against
  the low ground. No shadow, rim and fringe rules unchanged.
- Tests: the painter test now reads the centre pixel per tag (stone is
  teal, blue level with green; grass has green well over blue) and requires
  both styles per seed; a new test pins the north sprite as the south one
  row-reversed and cached. Bake and draw digests re-pinned; layouts are
  untouched.
- The known lie stands: flipped risers read as shade falling north. Shipped
  as is, to be judged in a frame.

### NS-6 — the stairs on the seam (2026-09-14)

**Decisions.** North flights only; south and east/west painting stay
byte-identical. The rim cell goes back to ordinary plateau ground,
autotiled with its lip. One stair sprite -- the flipped stone flight,
foot end north -- is centred on the seam between the landing and the rim,
at least half on each tile (the 64 px sprite: exactly half and half).
Grass and rock north flights look the same. Generation and walkability
untouched.

**Layering.** The sprite is split at the seam and each half drawn on its
own floor's band: the foot half on the low floor after the landing's
grass, so a body on the landing draws over it; the top half on the
plateau's band after the rim tile, so it covers the rim's lip in that
column and the stairs read as cutting through the edge rather than
vanishing under it. A body on the rim draws over that half as usual.

**What landed.** `TileSheets.vstair_seam(drop)` returns the flipped
sprite cut at its middle, `(foot_half, top_half)`, cached. In
`grid_paint` pass 1 a north flight now joins the ground floors list, so
it is autotiled with its lip like the rim cells beside it and casts
nothing; the pass-3 branch that painted a plain tile is gone. A new step
after the tall-sprite pass blits the foot half at the landing's lower
half on the low band and the top half at the rim's upper half on the
plateau's band, whatever the tag. The painter test samples the most
opaque pixel down each half's middle column and checks the baked pixel
against it within a small blend tolerance on the rim and on the landing,
plus opaque ground beyond the sprite on both tiles, both styles required.
South flights re-checked pixel-identical by the south-flight test. Bake
and draw digests re-pinned; layouts untouched. Screenshot delivered:
seed 35, island 0, a rock and a grass north flight side by side, both
now the stairs on the seam.

### Regression: south flights painted as cliff faces (2026-09-14)

Reported off a screenshot: a wall-cut staircase drawn as a plain cliff
face with a strip of water showing under it, still walkable. Confirmed
against a worktree at `b4b302e`, the commit before the north flights: the
same cells rendered the stone flight and the grass channel there and a
cliff face here.

The cause was in `grid_paint` pass 3. Adding the north branch *replaced*
the `elif` that caught every straight flight instead of going above it,
so the channel-and-sprite lines were indented under the north branch and
a south flight fell through to the east/west branch: cliff body, then a
wedge looked up by the flight's tag, which "rock" and "grass" do not
name. The water strip was the body art's scalloped bottom over the
floor a straight flight is deliberately not given. It shipped in
`00bc70c`; the digests were re-pinned over it, and nothing tested how a
south flight is painted.

Fixed by restoring the branch, so the three are north flight, south
flight, east/west flight, each self-contained. `test_south_flights_are_
still_painted_as_flights` now composes the channel piece and the sprite
as the painter does and compares the centre pixel on every south head of
the pinned seeds, both styles required. Re-rendered against the baseline
worktree: the flight tiles and their wall rows are pixel-identical; what
still differs in the crops is an obstacle or two moved by the north
flights' keep-outs. Digests re-pinned.

### NS-7 -- the grass channel on the rim (2026-09-20)

**Request.** Reviewing the north flights beside the buff-building work,
the owner noted they are the inverted stairs between two level tiles and
asked whether the grass n/s tile could join them. Confirmed reading: the
rim cell wears the south flight's grass channel piece, grass flights are
the channel alone, rock flights the channel with the flipped stone on top
-- the south rule, carried to the back rim.

**What landed.**

- `terrain.json` `slots.ramp.n = [17, 17]`: the north channel slot, the
  south piece by default, so a north-specific tile can be authored later
  without touching code (the ramp vocabulary already gained "n" for the
  tile metadata).
- `grid_paint` pass 4: every north flight blits the `ramp.n` piece over its
  autotiled rim tile on the plateau's band -- the rim's north lip goes and
  the two side lips of the channel take over, so the gateway reads as a cut
  through the edge. A grass flight stops there. A rock flight goes on to
  the seam halves as before: foot half on the landing's band, top half over
  the channel on the plateau's band.
- The painter test reads the channel's own pixel at the rim cell's lower
  quarter for both styles, the top step and the foot for rock only, and
  the channel where the top step would be for grass. Bake and draw digests
  re-pinned; layouts untouched. Screenshot delivered: seed 35, island 0,
  a rock and a grass north flight.

**Amended the same day.** The owner wants one thing or the other: a
grass flight is the channel alone, a rock flight the stone alone on its
ordinary rim tile, never the stone in a channel. The painter now lays the
channel only for grass flights; the rock branch is byte-for-byte the NS-6
painting again. The test checks the rock flight's rim below the stone is
plain plateau ground (no channel lip at its side) and the grass flight's
rim is the channel with no stone. Digests re-pinned; screenshot delivered.

**Amended again the same day: the grass flight straddles the seam.** From
a marked screenshot: the upper floor's grass should run past the rim line
onto the lower floor the way the stone does, not stop at the rim. Two
steps, as the owner laid them out: the rim cell first becomes the sheet's
plain interior tile (no lips), then the channel piece is cut at its middle
(`TileSheets.channel_halves`) and centred on the seam -- its upper half on
the landing's lower half, on the low band after the landing's grass; its
lower half on the rim's upper half, on the plateau band. The rock flight
is unchanged. The test reads plain grass on the rim's lower quarter, the
channel's lip on the rim's upper quarter and on the landing's lower
quarter, and no stone. Digests re-pinned; screenshot delivered.
