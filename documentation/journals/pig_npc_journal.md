# Pig NPC (village corral)

## Requirement (user, 2026-09-17)

> I have added a folder with pig sprites inside the `assets/terrain/npcs` folder.
> Add the pig npc just the same as the sheep for the village, same corral as the
> sheep just make pigs be between 2 and 3. dont modify the sheep behavior if
> necessary. confirm first.

So: a second pen animal, built the same way the sheep is (HI-3, see
`human_island_journal.md`), sharing the one corral each village already has,
placed 2-3 per village. The sheep's own tuning, count and behaviour stay exactly
as they are.

## What the sheep is today

- **Art** — `data/heroes/character_sprites.json`, rig `npc_sheep`: 128 px cells,
  a `content` crop, a `scale` to world pixels, a foot `anchor`, `face: right`,
  and two anims, `idle` and `walk` (the walk being the bounce strip).
- **Tuning** — `data/village/npcs.json`, `kinds.sheep` (speed, idle range, leash,
  radius) and `placement.sheep` `[2, 4]`.
- **Behaviour** — `entities/npc.py`, `SheepNpc(Npc)`: it overrides `_choose` to
  hop within its leash of where it stands, clamped to the pen's interior so it
  never walks into the fence. It hardcodes `kind="sheep"` when calling `super()`.
- **Spawning** — `game/states/playing/core/npcs.py`, in `Npcs.build`: if the
  village has a `pen`, and the pen's interior is bigger than twice the pad
  (`radius + 4`), it drops `placement.sheep` of them at uniform random spots.

Nothing outside `SheepNpc` branches on `kind == "sheep"`; `Npcs.update` only uses
the kind to look up that kind's `idle` range in the data.

## Proposal

1. **Assets** — copy `assets/terrain/npcs/pig/{pig_idle,pig_run}.png` into this
   worktree (they were added to the main checkout).
2. **Rig** — add `npc_pig` to `data/heroes/character_sprites.json`: frame
   `[192, 192]`, content `[62, 79, 70, 55]` (the union bbox over both strips),
   `face: right`, anims `idle` (`pig_idle.png`, 10 frames) and `walk`
   (`pig_run.png`, 4 frames). `scale`/`anchor` sized so a pig reads as a slightly
   longer, same-height animal beside a sheep (sheep is 24x21).
3. **Tuning** — add `kinds.pig` to `data/village/npcs.json` mirroring the sheep's
   shape (its own speed / idle / leash / radius) and `placement.pigs: [2, 3]`.
   The sheep's entries are untouched.
4. **Behaviour** — rename nothing and change no sheep code path: give
   `SheepNpc.__init__` an optional `kind="sheep"` keyword so a pig can be the
   same pen animal under its own kind. The class's `_choose` is already generic;
   a sheep constructed the old way behaves byte-identically.
5. **Spawning** — in `Npcs.build`, after the sheep loop, place the pigs in the
   same `v.pen` with the same pad check and the same uniform random spots.
6. **Credits** — add the pig pack to `assets/CREDITS.md` once its source is
   known.
7. **Tests** — extend `tests/entities/test_npcs.py` so a village with a pen has
   pigs too and no pig leaves the pen, and widen the corral-capacity test in
   `tests/world/test_village_tidy.py` to seat sheep *and* pigs.

### One thing worth flagging

Every village pen measures 115x58 world px; after the placement pad that is a
band roughly 89x32. It already takes 2-4 sheep at uniform random spots with no
anti-overlap check, and 2-3 pigs takes the corral to as many as seven animals in
that band.

## Confirmed (user, 2026-09-17)

The plan as written, with the pigs spaced out rather than dropped at plain
random spots, and the art credited to Tiny Swords alongside the sheep.

## Built

1. **Assets** -- `assets/terrain/npcs/pig/{pig_idle,pig_run}.png`, copied in
   from the main checkout.
2. **Rig** -- `npc_pig` in `data/heroes/character_sprites.json`, beside
   `npc_sheep`: 192 px cells, content `[62, 79, 70, 55]` (the union bbox over
   both strips), `face: right` like the sheep, `idle` 10 frames at 6 fps and
   `walk` 4 frames at 8 fps off the run strip. `scale` is `[27, 21]` against the
   sheep's `[24, 21]`: the same height, a longer body. That was picked by
   rendering both animals side by side at 21x17 / 24x19 / 27x21 / 30x24 and
   taking the one that reads as "a pig standing next to a sheep".
3. **Tuning** -- `kinds.pig` in `data/village/npcs.json` is the sheep's tuning
   exactly (speed 22, idle 2-7 s, leash 0.6 tiles) with radius 9 instead of 8,
   the sprite being wider. Matching it rather than inventing values keeps
   "just the same as the sheep" literally true: a pig roams its corral no
   further and no faster than a sheep does. `placement.pigs` is `[2, 3]`.
4. **Behaviour** -- `SheepNpc` gained an optional `kind="sheep"` keyword and
   nothing else; it was already generic, only the `super().__init__` call
   hardcoded the kind. A sheep built the old way is unchanged, and nothing
   outside the class branches on the kind (`Npcs.update` only uses it to look
   up that kind's `idle` range).
5. **Spawning** -- `Npcs.build` deals the sheep first, with the same draws in
   the same order as before, so a seed's flock does not move now that it shares
   the pen. The pigs follow through a new `pen_spot` helper: up to eight draws,
   the first one clear of every animal already in the corral wins, else the
   roomiest of the eight. A corral too full for the gap still seats the animal
   instead of looping.
6. **Credits** -- the pig is Tiny Swords like the sheep, so `assets/CREDITS.md`
   now names the corral animals in `assets/terrain/npcs/` rather than the sheep
   alone.
7. **Tests** -- `tests/entities/test_npcs.py` requires pigs wherever it
   required sheep and phrases the pen-containment failure per kind (the check
   was already `isinstance(n, SheepNpc)`, so it covered pigs the moment they
   existed); a new `PenSpotTests` pins `pen_spot` itself without booting a world
   -- an empty pen takes the first draw, a clear draw ends the search, a corral
   with no room returns the best of the eight, and the spot is always inside the
   padded interior. `tests/world/test_village_tidy.py`'s corral-capacity test
   now sizes the pen for a full flock *and* a full drift.

## What the spacing does and does not buy

It holds at spawn. Afterwards a pen animal wanders within its leash -- 0.6 tiles,
most of a 115x58 corral -- so sheep and pigs still drift over each other in play,
exactly as two sheep always could. Tightening that would mean giving the corral
animals collision, which is a change to the sheep and out of scope here.

## Status

Done. Screenshot of a corral with its sheep and pigs delivered to the user.
