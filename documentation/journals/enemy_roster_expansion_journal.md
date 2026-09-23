# Enemy roster expansion — journal

**Legacy ID:** ENT-005 · **Systems:** ENT, SPN · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The unused enemy art in `assets/unused/enemies/`, what each piece is, and the
work to bring the **ranged** ones into the game with their own projectiles.

---

## Requirement (owner, 2026-09-17)

- **Objective:** Survey the unused enemy sprites in the unused asset folder.
- **Details:** A summary for each one — what it looks like and how it could
  attack.
- **Constraint:** Confirm the survey before acting on it.

and then:

- **Objective:** Record the survey in this journal and propose a todo list
  for implementing the ranged enemies with their respective projectiles.
- **Constraint:** Confirm the proposal before building anything.

Status: **survey done, proposal written, nothing built.** The owner asked to
confirm the reading before the work starts, so this entry stops at the todo.

---

## The survey

### First, what "unused" actually contains

`assets/unused/enemies/` has 21 folders, and most are not unused creatures.
Twelve hold nothing but a portrait `avatar.png` for an enemy that is already
in the game:

| Folder | Already in the game as |
|---|---|
| `skull` | Husk (`chaser`) |
| `spider` | Skitter (`fast`) |
| `bumblebee` | Mite (`swarm`) |
| `turtle` | Lumberer (`tank`) |
| `slingshot_gnome` | Spitter (`ranged`) |
| `bomb_fish` | Bloat (`exploder`) |
| `panda` | Bulwark (`shielded`) |
| `minotaur` | Gorehound (`charger`) |
| `thief` | Blink (`teleporter`) |
| `gnome` | Broodmother (`summoner`) |
| `bear` | Ravager (`elite`) |
| `giant_bat` | a boss (`bosses.json`) |

Two more — `hex_shaman` and `troll` — are wired enemies (Blight Caller and
Warden) whose folders hold *spare animations*, covered further down.

**Seven are genuinely unused creatures**: full idle / run / attack sheets, and
zero references in `enemy_sprites.json`, `enemies.json` or any code. All are
Tiny Swords, the same pack and style as the shipped roster.

### The seven

**Gnoll** — `idle` 6f, `walk` 8f, `throw` 8f, `bone.png` 4f
A yellow-tan hyena on all fours with a shaggy brown mane and purple-spotted
haunches, a bone in its jaws. The throw rears it onto its hind legs, winds the
bone overhead and hurls it. **Ranged**, and the only unused creature whose
projectile art is *animated* — the bone is a 4-frame spin. A 2-frame
`gnoll_hit` flash sits in `extra/`.
*Could attack:* a lobbed bone. Where Spitter fires flat and fast, the gnoll is
a brawler that happens to throw — shorter range, heavier hit, slower cadence.

**Harpoon Shark** — `idle` 8f, `run` 6f, `throw` 8f, `harpoon.png` 1f
A teal shark on legs with a trident harpoon strapped to its back. The throw
draws the harpoon, hurls it, and leaves the shark empty-handed on the last
frame — the art itself suggests a reload beat. **Ranged**, still projectile.
*Could attack:* a long, slow, high-damage spear that runs through more than
one body. The projectile pool already supports `pierce`; no hostile shot uses
it today.

**Spear Goblin** — `idle` 8f, `run` 6f, `attack_fast` 7f
Small green goblin in a grey helmet with a long spear. Frames 2–4 of the
attack are a full white circular sweep arc around its body, settling to a
level thrust. An 8-frame `spear_goblin_attack_strong` sits in `extra/`.
*Could attack:* a 360° spin hitting everything in contact range. **Melee.**
The roster has no melee sweeper — every melee enemy today is a single-target
lunger.

**Torch Goblin** — `idle` 8f, `run` 6f, `attack` 8f
Green goblin in a wide brown hat swinging a burning brand through a broad arc
of orange fire, embers flying off and lingering a frame past the swing.
*Could attack:* a melee fire arc leaving burning ground. **Melee.** Would be
the only damage-over-time melee; Blight Caller is the sole area-denial source
and it is ranged.

**Lizard** — `idle` 7f, `run` 6f, `attack` 9f
A slim green lizard with a yellow crest that unfurls a huge circular frill
ringed with white-yellow spikes, holds it open about five frames, then folds
back down. Has a `lizard_hit` flash in `extra/`.
*Could attack:* a spiked bloom — damaging while open, armoured while open,
must close to move. **Melee / stance.** The clearest read in the whole set and
the only one whose vulnerability changes with its animation; nothing in the
roster does that.

**Snake** — `idle` 8f, `run` 8f, `attack` 6f
Orange-banded serpent with a pale belly, coiled in an S. The attack pulls back
into the coil then whips forward with motion streaks.
*Could attack:* a coil-and-lunge strike — telegraphed recoil, fast short leap.
**Melee.** Nearest existing thing is Gorehound's charge, but this is a
standing strike rather than a run-up.

**Paddle Shark** — `idle` 8f, `run` 6f, `attack` 6f
Stocky blue-grey shark on legs with a wooden oar. Raises it overhead, slams
down with a visible impact burst, follows through.
*Could attack:* heavy overhead smash with knockback. **Melee**, a bruiser
sitting between Lumberer and Bulwark.

### Spare art for enemies already in the game

- **Troll club throw** — `windup` 5f, the club in flight as two 10-frame
  sheets, `recovery` 10f, and `troll_dead` 10f. The Warden has only
  idle/walk/attack today, so this is a ready-made *ranged* attack and a death
  animation for it.
- **Hex Shaman transformation spell** — 11f, with a 3-frame pink orb
  `projectile.png` and a 9-frame `explosion.png`. Blight Caller already uses
  the *explosion* spell; this is an unused second one.
- **Guard variants** in `extra/` — `minotaur_guard`, `panda_guard`,
  `skull_guard` (7f), `turtle_guard_in`/`out` — stationary sentry poses of
  existing enemies, for defenders that hold a spot instead of chasing.
- **Slingshot Gnome acorn** — `acorn_projectile.png` 4f, unreferenced. Spitter
  fires the generic red arrow instead of its own ammunition.
- **21 avatar portraits** — framed headshots for every enemy, wired ones
  included. Nothing in the game reads them; the run-summary kill rows are
  text-only and would take them directly.
- **Scenery** in `extra/` — huts, boats, cannon, cave, dead tree, pirate
  tower, skull decorations, a rideable pig. Not enemies.

### Licence note

Tiny Swords (Pixel Frog, purchased) allows use and modification but forbids
redistributing or repackaging, so all of this stays inside the build. Already
recorded in `assets/CREDITS.md`.

---

## Confirmed reading of the build request

- **"the ranged enemies" = Gnoll and Harpoon Shark.** They are the only two of
  the seven that throw something, and the only two that ship projectile art of
  their own. The other five (Spear Goblin, Torch Goblin, Lizard, Snake, Paddle
  Shark) are melee and are **out of scope for this pass**.
- **"their respective projectiles" = `bone.png` and `harpoon.png`**, the files
  that sit beside each creature — not the generic arrow.
- **Not included:** the troll club throw and the hex shaman's second spell.
  Both are ranged-with-projectile, but they belong to enemies that already
  exist and are a different job from adding creatures.
- **The slingshot gnome's acorn *is* included** (owner, 2026-09-17). It falls
  out almost free once R1 lands, and Spitter firing a generic red arrow while
  its own ammunition sits unused is the exact bug R1 exists to fix.

### Resolved with the owner (2026-09-17)

- **Three ranged types, two of them new.** Spitter keeps its slot and gets its
  acorn; Gnoll and Harpoon Shark join it. The three read differently enough to
  earn their places — a flat fast pellet, a lobbed bone, a slow piercing
  spear. To stop the *total* ranged share growing, the per-band weight of
  `ranged` is trimmed as the two new ids are added, so the bands keep roughly
  the 9–12 % ranged presence they have now rather than tripling it.
- **Both naming layers change** — the internal id *and* the display name — so
  an enemy's reference matches the art it is drawn with. The two new enemies
  are named that way from the start (R4 / R5). Renaming the **thirteen
  existing** enemies is deliberately **the last task** (R8), because their ids
  appear in `enemies.json`, `spawn_tables.json`, `bosses.json`, the AI tests
  and the pinned spawn fixture — doing it first would churn every file the
  earlier tasks touch, and it collides with the band rework that is already
  paused mid-decision.

### The finding that shapes the whole todo

`EffectsMixin.fire_hostile` is

```python
def fire_hostile(self, *, pos, vel, damage, radius) -> None:
```

There is no `style`, no `fx`, no `pierce`. Every hostile shot in the game is
the same red-tinted `arrow` rig — that is why Spitter's acorn has never been
used. `Projectile.reset` already accepts `style`, `fx` and `pierce`; only this
one call site throws them away, and `FireProjectile` (the AI component) has no
fields to pass them with.

So **the first task is not either enemy** — it is widening that seam. Once it
is open, the harpoon is nearly free (the existing `thrown` style already
rotates a named rig to the shot's heading, which is exactly a flying spear),
and the bone needs one new draw style because no projectile in the game
animates today.

---

## Proposed todo

### R1 — Let a hostile shot choose its own look *(the enabler)*

- `entities/ai/components` `FireProjectile`: add `style`, `rig`, `pierce`
  fields, defaulting to today's behaviour so every current enemy is untouched.
- `game/states/playing/core/effects.py` `fire_hostile`: accept and forward
  `style`, `fx`, `pierce` to `Projectile.reset`. Defaults keep the red arrow.
- `entities/ai/behaviors/ranged.py` `kite_shoot`: read `shot_style`,
  `shot_rig`, `shot_pierce` from the enemy's JSON block.
- Test: an enemy with no shot keys still fires exactly what it fires today.

### R2 — A spinning-projectile draw style

- New `@style("spin")` in `game/states/playing/visual/projectiles/`: plays a
  rig's frames on the shot's own clock, rotated to its heading. Falls back to
  `bolt` when the rig or sheet is missing, as `thrown` does.
- The harpoon needs no new style — `thrown` already covers a still rotated to
  its heading; it only needs a rig with the right `heading_deg`.

### R3 — Art moved in and manifested

- Move `gnoll/` and `harpoon_shark/` from `assets/unused/enemies/` to
  `assets/enemies/`, leaving the source sheets archived per the project's
  `unused/` rule.
- `data/enemies/enemy_sprites.json`: a `gnoll` and a `harpoon_shark` entry
  (frame, content, scale, anchor, face, idle/walk/attack anims), plus rigs
  `gnoll_bone` and `harpoon_spear` with their `heading_deg` measured from the
  art. `Assets.rig` reads this file already, so no loader change.
- `assets/CREDITS.md`: move both from the reserve list to the used list.

### R4 — Gnoll: the lobbed bone

- `data/enemies/enemies.json`: a `bone_thrower` entry — `behavior:
  "kite_shoot"`, `sprite: "gnoll"`, `shot_style: "spin"`, `shot_rig:
  "gnoll_bone"`. Tuned as a brawler that throws: shorter `prefer_distance`
  than Spitter, slower `shoot_interval`, higher `shoot_damage`, more HP.
- Numbers proposed with the build, alongside Spitter's for comparison.

### R5 — Harpoon Shark: the piercing spear

- `data/enemies/enemies.json`: a `harpooner` entry — `behavior:
  "kite_shoot"`, `sprite: "harpoon_shark"`, `shot_style: "thrown"`,
  `shot_rig: "harpoon_spear"`, `shot_pierce: 1` or 2. Long `prefer_distance`,
  long `shoot_interval`, high `shoot_damage`, slow `speed`.
- The empty-handed last throw frame reads as a reload; worth considering a
  longer recovery so the animation and the cadence agree.

### R6 — Into the run

- `data/enemies/spawn_tables.json`: give both a weight in the bands they
  belong to. **Blocked on the band rework** currently paused mid-decision —
  the band count and boundaries are about to change, so this is the last
  step, not the first.
- Check the `groups` templates: `artillery` (warlock + shielded) has an
  obvious sibling in a gnoll pack.

### R7 — Tests and proof

- `tests/entities/ai/`: each new enemy fires at its interval, respects its
  range, and the shot carries the right style / rig / pierce.
- `tests/render/`: the `spin` style draws and falls back cleanly with the rig
  missing — the pattern `test_totem_bolt.py` uses.
- A content-load test that both ids resolve their sprite and rigs, so a typo
  fails at boot rather than at minute eight.
- A rendered screenshot of both enemies shooting, per the project's rule that
  visual milestones ship with one.

### R8 — Rename every enemy to match its art *(built 2026-09-17)*

**The scheme that shipped.** Id `==` sprite, display name chosen for the art:

| old id | new id | old name | new name |
|---|---|---|---|
| `chaser` | `skull` | Husk | Husk |
| `fast` | `spider` | Skitter | Skitter |
| `tank` | `turtle` | Lumberer | **Shellback** |
| `swarm` | `bumblebee` | Mite | **Stinger** |
| `ranged` | `slingshot_gnome` | Spitter | **Slinger** |
| `exploder` | `bomb_fish` | Bloat | Bloat |
| `shielded` | `panda` | Bulwark | **Stoutpaw** |
| `elite` | `bear` | Ravager | Ravager |
| `summoner` | `gnome` | Broodmother | **Beekeeper** |
| `brute` | `troll` | Warden | **Grudge** |
| `charger` | `minotaur` | Gorehound | **Gorehorn** |
| `teleporter` | `thief` | Blink | Blink |
| `warlock` | `hex_shaman` | Blight Caller | **Hexcaller** |
| `bonepicker` | `gnoll` | Bonepicker | Bonepicker |
| `gaffjaw` | `harpoon_shark` | Gaffjaw | Gaffjaw |

`training_dummy` keeps its id: it is not a creature and has no art of its own.

**R4 / R5 were corrected here.** Those two shipped as `bonepicker` and
`gaffjaw` — flavour ids, which is not the rule the owner set. Under "id ==
sprite" they are `gnoll` and `harpoon_shark`, with the flavour kept where it
belongs, on the display name. An assertion in the rename script now holds the
invariant: every id except the dummy equals its own `sprite` field.

**Why none of this could be a find-and-replace.** Every old id collides with a
word that means something else in the same files:

| word | also means |
|---|---|
| `fast` | a difficulty (`config.DIFFICULTIES`) — *and a top-level key of the pinned fixture* |
| `elite` | a tag, the `is_elite` flag, and the per-band elite **chance** key |
| `tank`, `ranged`, `charger`, `shielded` | tags; `ranged` is also a weapon class |
| `swarm`, `brute` | spawn-**group** names in the same file |
| `chaser`, `swarm`, `exploder`, `summoner`, `brute` | AI **behaviour** names |

So each replacement is anchored to the slot that actually holds an enemy id:
a type weight is `"<id>": <number>` (which `"elite": 0.25` can never match,
because `elite` was never a *type*), a follower span is `"<id>": [`, which the
group named `"swarm": {` can never match, and so on. The hand-formatted data
files keep their layout — no `json.dump` round trip.

`tests/spawn/director_sequence.json` had to be done structurally rather than
textually, because `"fast"` is a difficulty **key** and an enemy **value** in
that one file; a text pass would have renamed the key too. The fixture is 1,417
draws per difficulty and the rename cannot move any of them — it is the same
sequence with different words, so the S2 proof survives.

**Group names were deliberately left alone.** `husk_pack`, `runners`, `swarm`,
`warband`, `brute`, `artillery` are template ids, not enemy ids. Two of them
now read oddly (`brute` leads a `troll`, `swarm` leads a `bumblebee`) and are
worth a follow-up, but renaming them is a different key space and was not
asked for.

**Test surface.** 26 files were fixed by the slot patterns, then 56
replacements across 16 more were classified by reading each line. What was
checked and deliberately **not** touched: every weapon `source_tags=("ranged",
…)` and `"class": "ranged"`, the AI behaviour names passed to
`build_behavior`, the `spawn_group("swarm")` template id, the per-band elite
chance, and every `difficulty="fast"` / `records["fast"]` in the save, menu
and end-screen tests.

**A flaky test found on the way, and *not* caused by this.**
`tests/render/test_ghost.py::RunIntegrationTests` failed after the rename, so
it looked like fallout. It is not: with the rename correctly applied it passes
about one run in five, on unchanged code. The cause is that `fresh_playing()`
generates a different world each run, so `_tree(gm)` picks a different tree —
measured at (8215, 3688) on one run and (5596, 4502) on the next — and on most
worlds the enemy placed at a fixed `tree.y - 12` is never queued for the ghost
pass at all (the one queue entry on a failing run is the **hero**: its
`char_y` equals the player's y exactly and its frame is 69x64, not the skull
rig's). Raised as its own task rather than patched inside a rename.

**Code defers left in place.** `SummonBrood.enemy_id`, `build_summoner` and
`Boss`'s summon pattern each carry a `"bumblebee"` fallback where they carried
`"swarm"`. They are dead in production — both the gnome's block and the boss's
pattern set `summon_id` in data — but they are load-bearing for tests that
build a behaviour without one. Under the project's "no per-entity defaults in
code" rule they should be deleted and those tests made explicit; that is a
separate cleanup, noted here rather than smuggled into a rename.

### The original proposal, for the record

Ids and display names both. The roster today names by *role* in code and by
*flavour* on screen, and neither is tied to the art, which is how a panda ends
up called Bulwark and a turtle called Lumberer. The scheme below is a
**proposal to be signed off when R8 starts**, not a decision:

| id today | sprite | name today | proposed id | proposed name |
|---|---|---|---|---|
| `chaser` | skull | Husk | `skull` | Husk |
| `fast` | spider | Skitter | `spider` | Skitter |
| `swarm` | bumblebee | Mite | `bumblebee` | Stinger |
| `tank` | turtle | Lumberer | `turtle` | Shellback |
| `ranged` | slingshot_gnome | Spitter | `slingshot_gnome` | Slinger |
| `exploder` | bomb_fish | Bloat | `bomb_fish` | Bloat |
| `shielded` | panda | Bulwark | `panda` | Stoutpaw |
| `charger` | minotaur | Gorehound | `minotaur` | Gorehorn |
| `teleporter` | thief | Blink | `thief` | Blink |
| `summoner` | gnome | Broodmother | `gnome` | Beekeeper |
| `warlock` | hex_shaman | Blight Caller | `hex_shaman` | Hexcaller |
| `elite` | bear | Ravager | `bear` | Ravager |
| `brute` | troll | Warden | `troll` | Grudge |

"Broodmother" → "Beekeeper" is the one worth pointing at: the enemy is a gnome
and what it summons is `swarm`, which is drawn as a bumblebee. The current
name describes neither.

Every id is a key in `enemies.json`, the `types` maps of every band in
`spawn_tables.json`, the `groups` templates, `owners`, `bosses.json`, the AI
tests, and `tests/spawn/director_sequence.json` — the pinned fixture stores
enemy ids as strings, so it has to be re-keyed in the same commit or the S2
proof breaks.

---

## Built (R1–R6)

**R1 — the seam.** `TransientFx.fire_hostile` now takes `style`, `fx` and
`pierce` and forwards them to `Projectile.reset`, which had always accepted
them. `FireProjectile` gained `style` / `rig` / `pierce` fields and
`kite_shoot` reads `shot_style` / `shot_rig` / `shot_pierce` / `shot_radius`
off the enemy's JSON block. Every default is the old behaviour, so an enemy
that names no ammunition still fires the red arrow.

One detail worth keeping: the component sends `fx=None` rather than
`fx={"rig": ""}` when no rig is named, so `thrown` and `spin` fall back once
instead of looking up an empty rig every frame. There is a test for it.

**R2 — `spin`.** A new style in
`game/states/playing/visual/projectiles/spin.py` that plays a rig's `spin`
strip off `proj.age`. It deliberately does **not** rotate by heading: the
frames already carry the tumble, and rotating them too would spin the art
twice. Reading `age` (which the pool resets on reuse) rather than a global
clock is what keeps two bones in flight out of lockstep. Falls back to the
`bolt` disc when the rig or sheet is missing, as `thrown` does.

**R3 — art in, rigs measured.** `gnoll/` and `harpoon_shark/` moved from
`assets/unused/enemies/` into `assets/enemies/` (`assets/unused/` is
gitignored, so the move is what makes them tracked), and the acorn moved
beside the slingshot gnome's own sheets. Five entries added to
`enemy_sprites.json`: the two creatures, and the rigs `gnoll_bone`, `acorn`
(both with a `spin` strip) and `harpoon_spear` (a still with `heading_deg`).

Nothing here was guessed:

- `content` is the union ink rect over every frame of every anim.
- `anchor` is the idle silhouette's centre-x / bottom-y in the scaled content
  box. That construction was checked against the fifteen shipped rigs first
  and reproduces fourteen of them within 4 px — the miss is `giant_bat`, a
  flier whose anchor is deliberately offset.
- `harpoon_spear.heading_deg` is −45, measured off the art's principal axis
  (−44.5°), with the thick end at the bottom-left identifying the blunt end
  and the thin end at the top-right the tip.
- Both sheets face right, confirmed against the known-right slingshot gnome,
  so `"face": "right"` matches the rest of the pack.

**R4 / R5 — the two enemies.** Both ride the existing `kite_shoot`; what
separates them is the shape of the threat, not new code.

| | Spitter | Bonepicker | Gaffjaw |
|---|---|---|---|
| sprite | slingshot_gnome | gnoll | harpoon_shark |
| HP | 17 | 46 | 58 |
| speed | 45 | 82 | 40 |
| hold distance | 260 | 190 | 360 |
| damage / shot | 7 | 12 | 19 |
| interval | 2.1 s | 2.6 s | 3.4 s |
| shot speed | 230 | 190 | 300 |
| pierce | — | — | **2** |
| ammunition | acorn (spin) | bone (spin) | harpoon (thrown) |

Bonepicker is a brawler that happens to throw: it closes further in than
Spitter, hits harder and slower, and carries the HP to survive the trip.
Gaffjaw is the opposite — it sits at the back, fires rarely, and its spear
runs through two bodies, so a crowd between the player and it is cover for
nobody. That pierce is Gaffjaw's whole identity and a test pins that it is
the only ranged enemy with it.

**R6 — the acorn.** Two keys on the `ranged` block. Spitter has fired a
generic red arrow since it shipped while its own ammunition sat unread in
`unused/`; that is the bug R1 existed to fix, so fixing it is the proof R1
works.

## Tests

- `tests/entities/ai/test_ranged_ammunition.py` (11 tests) — the defaults
  produce exactly the old shot; style / rig / pierce reach the projectile
  through both the component and the behaviour; and, against the *shipped*
  data rather than a fixture, every ranged enemy names a rig that exists,
  none still falls back to the arrow, each `spin` rig really has a strip,
  each `thrown` rig declares its heading, the two new enemies have all three
  anims, and only Gaffjaw pierces.
- `tests/render/test_spin_projectile.py` (10 tests) — the strip advances with
  age and wraps, two ages give different frames, `fx.fps` overrides the rig,
  a rig with no strip reports `None`, a negative age does not index
  backwards, and — the one that guards the design — two shots travelling
  opposite ways render **byte-identical**, proving the style does not turn
  the art by its heading. Missing rigs fall back to the disc rather than
  crashing.

## Progress

- [x] Survey of `assets/unused/enemies/`
- [x] Confirmed reading of "the ranged enemies"
- [x] Todo proposed
- [x] Owner decisions: three ranged types, acorn in, both naming layers
- [x] R1 — `fire_hostile` / `FireProjectile` carry style, rig, pierce
- [x] R2 — `spin` projectile style
- [x] R3 — art moved and manifested
- [x] R4 — Gnoll → Bonepicker
- [x] R5 — Harpoon Shark → Gaffjaw
- [x] R6 — Spitter's acorn
- [x] R7 — spawn tables (blocked on the band rework) *(DOC-003: the band rework landed (SPN-002): `data/enemies/spawn_tables.json`, `harpoon_shark` in `marine`, `gnoll` in `wild_beasts`)*
- [x] R8 — rename every enemy to match its art *(DOC-003: built 2026-09-17, see R8 above)*
- [x] Tests (21 new) and a scale/anchor render
- [ ] In-game screenshot of both firing (needs R7 — they cannot spawn yet) *(DOC-003: no longer blocked; R7 is done)*

---

## The `unused` category — benching the Stoutpaw (owner, 2026-09-17)

### Requirement (owner, 2026-09-17)

- **Objective:** Add an "unused" category for currently unused enemies and
  move the current panda enemy into it.
- **Constraint:** Do not delete its code references — the enemy is only
  disabled.

### Confirmed reading

Two halves, and the second is the load-bearing one. The director must never
roll a benched enemy; and *everything else about it must survive* — its block
in `enemies.json`, its art and rig, its weights in the bands, the group that
lists it, `spawn_at` / `spawn_group` / the dev menu, and every test that builds
one directly. Re-enabling is deleting one string, not re-deriving numbers that
were thrown away.

### Built

- `data/enemies/spawn_tables.json`: a top-level `"unused": ["panda"]` with a
  comment saying exactly what listing an id does and does not do. The panda's
  band weights (0.04 / 0.07 / 0.09 in bands 3–5) and its place in the
  `artillery` group are **left in the file untouched**.
- `spawn/tables.py`: `SpawnTables.unused` is read and the benched ids are
  filtered out of the phase `types` (shared and per-difficulty) and the group
  followers **once, at construction**. Filtering per lookup would rebuild the
  phase dicts each call, and callers compare phases by identity
  (`_phase(a) is _phase(b)`) — there is a test pinning that a lookup returns
  the same object every time.

### Benching is tuning, but it can express table errors

Three things it must not be allowed to do quietly, each validated by name
rather than left to surface later as an empty draw:

| If you bench… | …you get |
|---|---|
| the only type in a band (`skull`) | "phase 0 has nothing left once ['skull'] are unused" |
| a group's leader (`hex_shaman`) | "group 'artillery': its leader is unused" |
| either elite slot (`bear`, `troll`) | "elites: `default` names the unused 'bear'" |

An id that names no enemy is rejected too.

### The pinned fixture, again

Benching changes the weight list every draw is taken from, so the S2 director
sequence would have moved. `_fixture_tables` now winds `unused` back to `[]`
alongside `ramp_seconds` and the elite chances — the fixture pins the recorded
behaviour, and the `unused` category is tuning like the rest of them.

### Not benched, and why

Bonepicker, Gaffjaw and the Hammer Gnome are *also* currently unspawnable, but
they are not in this list. Being absent from every band is pending work — they
are built and waiting for a weight — whereas `unused` is a decision to take a
finished enemy out of play. Listing them would also mean remembering to
un-list them later, which is exactly the kind of bookkeeping that rots. The
comment in the data says this.

### Tests

`tests/spawn/test_unused_category.py`, 18 tests: no band, difficulty override
or group can produce a benched enemy; the block, art, weights and group entry
all survive; clearing the list brings it straight back; the phase-identity
guarantee holds; the four validation errors fire; a table with no `unused` key
is still valid; and — end to end — a full 600 s scripted run and 120
`roll_pack` draws never emit a panda.
