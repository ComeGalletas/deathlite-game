# Splitting the gnome: Hammer Gnome and the torch-swinging Beekeeper

**Legacy ID:** ENT-006 · **Systems:** ENT · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The one gnome-sprited enemy becomes two: a plain melee chaser that finally uses
the gnome's unused hammer swing, and a Beekeeper rebuilt on the torch goblin
art whose torch swing is the summon.

---

## Requirement (owner, 2026-09-17)

- **Objective:** Rebuild the Beekeeper on the `torch_goblin` sprite from the
  unused folder, and turn the current beekeeper into a new `hammer_gnome`
  enemy.
- **Details:** Wire the gnome's attack animation with a collision hitbox for
  the attack, in the manner of the husk/skull work. Wire the torch goblin's
  torch-swing animation to summon the bees, and enlarge every bee by about
  30 %.
- **Constraint:** Confirm the reading before building.

and, answering the three questions that reading left open:

- **Hammer Gnome behaviour:** it only chases the player and attacks just like
  the husk — starting at 30 % more HP, 35 % more damage and 20 % less speed
  than the husk, with its spawn weight tunable upward as well.
- **The torch swing also deals damage** — a small amount on top of the
  summons.
- **Naming:** the new enemy's id carries "hammer", and the Beekeeper's entry
  references the `torch_goblin` art.

**This supersedes** the instruction earlier the same day to put the Beekeeper
on the Blight Caller sprite. That change was never built; the torch goblin
takes its place, which also removes the two objections raised against it — the
Beekeeper no longer shares art with Hexcaller, and it no longer shrinks (the
torch goblin measures about 62x52 against the gnome's 85x51, where the shaman
was 57x41).

## What the art already is

The `gnome` sprite is a gnome in an orange cap holding a large wooden mallet,
and its 7-frame `attack.png` is an overhead hammer swing. That strip has been
**dead art since it shipped**: `Enemy._anim_name()` only returns `"attack"`
while the AI machine sits in `telegraph` or `attack`, and `summoner` is a
single-state behaviour, so the Beekeeper has never played it. "Hammer gnome"
is not a reskin, it is what the art was drawn as.

`torch_goblin` (in `assets/unused/enemies/`) is a green goblin in a wide brown
hat swinging a burning brand through a fiery arc, with embers that linger a
frame past the swing. idle 8f, run 6f, attack 8f, 192 px frames.

## Confirmed reading

- **Two enemies, one behaviour each.** The Hammer Gnome *only* chases and
  swings — no summoning. The Beekeeper does the summoning, on the torch swing.
- **The melee hitbox is free.** `path_chase_attack` (Husk's behaviour) already
  runs chase → telegraph → attack and drops a `MeleeHitbox` on the actor's
  front-facing side at `radius / 2`, worth `contact_damage`, alive for the
  swing, with the attack animation driven by the machine state. So the Hammer
  Gnome needs **no new code** — it is a data block plus the rig.
- **The Beekeeper's swing is the work.** Today's `summoner` is
  `MaintainRange` + `SummonBrood` in a single `move` state, which is exactly
  why it never animates. Tying the summon to a swing needs a new behaviour on
  the same `telegraph_cycle` scaffold `path_chase_attack` uses, firing *both*
  a summon and a small hitbox at the wind-up end.
- **The Beekeeper stops being a kiter.** Because the swing now carries damage,
  it has to reach the player to use it, so the `MaintainRange(200)` hold is
  replaced by the ordinary pursuit stack. It changes from a back-line summoner
  that backs away to a mid-line one that walks in, swings, and leaves bees
  behind. That follows from "the torch swing also does damage" and is worth
  naming because it is a role change, not a tuning change.
- **Ids carry the names, and the art is renamed with them.** The owner asked
  for `hammer_gnome` and `torch_goblin` as ids. The R8 rule is that an id
  equals its sprite, so the rig and its folder are renamed `gnome` ->
  `hammer_gnome` too, and the invariant (and
  `tests/spawn/test_data_integrity.py`) holds with no exception entry. The
  unrelated `slingshot_gnome` sprite is untouched.

## Numbers

**Hammer Gnome**, from the owner's multipliers on Husk:

| | Husk | Hammer Gnome | |
|---|---|---|---|
| hp | 20 | **26** | +30% |
| contact damage | 13 | **18** | +35% |
| speed | 75 | **60** | −20% |
| weight | 7 | **11** | "can be tuned above" |
| xp | 3 | **5** | judgement |
| radius | 10 | **16** | judgement, see below |

`aggro_range`, `pursuit_seconds`, `attack_telegraph` and `attack_active` are
Husk's, since "just like the husk" is the brief.

**The radius is a judgement call, flagged.** The block inherits `radius: 20`
from the Beekeeper, which puts it in the `large` clearance class and makes it
need large spawn points. At its drawn size (85x51) the comparable bodies are
Stoutpaw (91x54, r16) and Gorehorn (68x56, r15), so 16 is the honest number
and keeps it in `small` clearance like the other basic chasers. Say the word
if the Hammer Gnome should be a large body instead.

**Beekeeper** keeps its HP, speed and summon triple; what changes is where it
stands and what the swing does:

| | before | after |
|---|---|---|
| sprite | `gnome` | `torch_goblin` |
| behaviour | `summoner` (hold 200 px) | `path_chase_summon` (close and swing) |
| radius | 20 (large) | **16** (small), matching the smaller art |
| contact damage | 13, **disabled** | **8**, via the swing's hitbox |
| summon | on a 4 s timer, no animation | **on the swing**, animated |

The swing's damage is deliberately below Husk's 13: it is "a small one on top
of the summons", not a melee threat in its own right.

**Stinger (the bees), +30%:**

| | before | after |
|---|---|---|
| radius | 7 | **9** |
| drawn scale | 23x35 | **30x46** |
| weight | 3 | 3 (unchanged) |

`weight` is mass for separation and knockback rather than size, so it is left
alone unless asked. Radius 9 is still inside the `small` clearance class, so
placement is unaffected. This applies to **every** Stinger — the band spawns
and the eight the boss's `summon_brood` pattern drops, not only the
Beekeeper's three.

## Plan

- `assets/`: move `unused/enemies/torch_goblin/` to `enemies/torch_goblin/`;
  rename `enemies/gnome/` to `enemies/hammer_gnome/`. Verify the torch
  goblin's facing against a known-right rig before wiring it, as was done for
  the gnoll — every rig in the pack is `"face": "right"` and a wrong call
  makes it walk backwards.
- `data/enemies/enemy_sprites.json`: rename the `gnome` rig to `hammer_gnome`;
  add a `torch_goblin` rig (content/scale/anchor measured the same way as the
  gnoll's — union ink over every frame, anchor from the idle silhouette).
- `data/enemies/enemies.json`: `gnome` becomes `hammer_gnome` with the table
  above; a new `torch_goblin` block carries the Beekeeper; `bumblebee` grows.
- `entities/ai/behaviors/`: a new `path_chase_summon` behaviour — the pursuit
  stack into `telegraph_cycle`, with `on_windup_end` firing the summon and the
  hitbox together.
- `data/enemies/spawn_tables.json`: the band `types` still name `gnome`; that
  key becomes `hammer_gnome`, and `torch_goblin` takes the summoner's place.
- `assets/CREDITS.md`: the torch goblin joins the used list.
- Tests: the new behaviour summons and hits on the same swing; the Hammer
  Gnome's numbers hold their ratios to Husk; the bees grew; both rigs carry
  all three anims; and the id/sprite invariant still holds.

## Built

- **Art.** `unused/enemies/torch_goblin/` moved to `enemies/torch_goblin/`;
  `enemies/gnome/` renamed `enemies/hammer_gnome/`. Facing checked against the
  known-right slingshot gnome: the torch goblin's nose points right, so
  `"face": "right"` matches the pack. The gnome rig was already declared right
  and only changed key.
- **Rigs.** `gnome` renamed to `hammer_gnome` (its three anim paths with it);
  `torch_goblin` added with `content [29, 50, 131, 83]`, `scale [76, 48]`,
  `anchor [32, 48]` — the union ink over all 22 frames, and the anchor from
  the idle silhouette, the construction validated against the shipped rigs in
  R3 of the roster journal.
- **`path_chase_summon`** in `entities/ai/behaviors/ranged.py`: the pursuit
  stack into `telegraph_cycle`, with `on_windup_end` firing the summon **and**
  the hitbox. `simple._pursuit_stack` became public `pursuit_stack` so the new
  behaviour could import it rather than reach into another module's privates.
- **Enemy blocks.** `gnome` became `hammer_gnome` on the numbers in the table
  above; a new `torch_goblin` block carries the Beekeeper; `bumblebee`'s
  radius went 7 -> 9 and its rig's `scale` 23x35 -> 30x46 (anchor moved with
  it, 12,34 -> 16,45).
- **Spawn tables.** The two band weights that named `gnome` now name
  `torch_goblin`, so the Beekeeper keeps its 5.7 % / 6.5 % of bands 4-5. The
  Hammer Gnome is a **new type and is in no band yet** — the same wait as
  Bonepicker and Gaffjaw.
- `assets/CREDITS.md`: the torch goblin joins the used list.

## Tests

`tests/entities/ai/test_gnome_split.py`, 19 tests. The load-bearing one is
`test_the_swing_summons_and_hits_on_the_same_beat`: it asserts the summon
count equals the hit count, so the two payloads can never drift back onto
separate clocks — which is the whole reason the behaviour exists. The rest
pin the telegraph cycle's four states (what the sprite reads to animate), the
hitbox's position/radius/damage/lifetime, that the swing damage stays under
the Husk's, that nothing summons out of reach, the Hammer Gnome's three
ratios against the Husk, that it no longer summons, both rigs' anim sets, the
retired `gnome` rig, and the bees' new collider and drawn size.

### Two guards fired, both correctly

- `test_melee_enemies.ATTACKING` is the set of behaviours that carry their own
  damage, so an enemy may disable its passive body bite. `path_chase_summon`
  had to be added — the guard was right that a `contact_damage_enabled: false`
  enemy on an unlisted behaviour would deal no damage at all.
- `test_enemy_ai.test_summoner_spawns_brood_on_interval` drove plain
  `summoner` through the roster id `gnome`, which no longer exists. **No
  shipped enemy runs `summoner` any more**; the behaviour is kept (it is the
  timer-driven summon, a reasonable thing to have) and the test now builds it
  from a literal block instead of a roster id. Worth knowing that it is now
  code with no data behind it.
- The **pinned S2 director fixture** failed on all three difficulties, because
  76 of its draws named `gnome`. Before re-keying it, the sequence was replayed
  against the live tables and diffed draw by draw: same length on every
  difficulty (1417 / 1275 / 1158), and the *only* difference across all three
  was the pair `('gnome', 'torch_goblin')`. So no draw moved and the S2 proof
  is intact — the fixture is the same sequence with one word changed.

## Progress

- [x] Art moved and renamed, facing verified
- [x] Rigs measured and manifested
- [x] `path_chase_summon` behaviour
- [x] Enemy blocks: Hammer Gnome, Beekeeper, bigger bees
- [x] Spawn tables re-keyed (Beekeeper only)
- [x] Tests
- [x] Hammer Gnome into a band — waiting on the band rework *(DOC-003: the band rework landed (SPN-002): `data/enemies/spawn_tables.json`, `hammer_gnome` 6 in `gnomes`)*
- [x] Full suite *(DOC-003: covered by later full-suite runs, e.g. `key_icons_journal.md` (2,640 passed))*

---

## The swing comes off the range gate (owner, 2026-09-17)

### Requirement (owner, 2026-09-17)

- **Objective:** Decouple the Beekeeper's swing from its melee range gate.
- **Details:** The weapon/torch animation swings on a fixed cooldown, and
  every attack does both: it spawns the melee hitbox from the torch's swing
  and summons bees from the animation. The chase-the-player behaviour stays,
  but proximity is no longer required to attack and summon.

### Why this was right

As first built, `path_chase_summon` inherited `path_chase_attack`'s trigger:
the wind-up only started once the player was inside
`radius + PLAYER_RADIUS + 5` — about **26 px** for this body. That gated the
bees behind a melee range a summoner has no reason to close, so in practice
the Beekeeper would have summoned almost never. The damage was always the
garnish; the summon is the point.

### Built

`telegraph_cycle` now accepts `trigger_range=None`, which drops the distance
predicate and starts the wind-up on the cooldown alone. It is a real option on
the shared scaffold rather than a fake huge range, so the intent reads in the
code instead of hiding in a magic number. Every other behaviour passes a
range and is untouched.

`path_chase_summon` passes `None` and no longer computes a reach at all. One
cycle is `attack_telegraph` (0.35) + `attack_active` (0.45) + `attack_recover`
(0.2) + `attack_cooldown` (3.2) = **4.2 s**, and nothing about the player's
position enters it.

Both payloads still fire on the same `telegraph -> attack` transition, so a
swing out of reach still drops its hitbox — it simply misses, rather than
being skipped. That keeps "one swing, two things" literally true.

### The nuance worth knowing

**Aggro still gates it.** `with_aggro` wraps every behaviour, so a Beekeeper
that has never noticed the player stands idle rather than summoning into an
empty island. "No range gate" is about the *swing*, not about noticing. This
was found by a test: the first version of the new test stood the player at
4000 px and saw zero summons, which looked like the change had not worked and
was actually `aggro_range` (540) doing its job. The tests now use 400 px —
fifteen times the old trigger, comfortably inside aggro — and a separate test
pins the aggro gate at four times the aggro range.

### Tests

`test_gnome_split.py` is 22 tests now. One was replaced rather than re-pinned:
`test_it_does_not_summon_while_the_player_is_out_of_reach` asserted exactly
the behaviour the owner asked to remove, so it became
`test_it_swings_far_outside_melee_reach`. Three joined it — the fixed cadence
is identical near and far, a swing out of reach still drops its hitbox, and
aggro still gates the whole thing.
