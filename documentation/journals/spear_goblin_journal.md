# The Whirlspear — wiring the spear goblin

**Legacy ID:** ENT-009 · **Systems:** ENT · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

The last unwired goblin in the reserve art, brought in as the roster's first
melee **sweeper** and its first enemy with **two** swings.

---

## Requirement (owner, 2026-09-17)

- **Objective:** Check the unused folder for other goblin-like enemies still
  without wiring.

and then

- **Objective:** Wire the spear goblin as a new enemy.
- **Constraint:** Confirm first.

with the two open questions answered: both attacks, used in alternation — and
the display name **Whirlspear**.

## The review that led here

`spear_goblin` was the only goblin-like creature left unwired. Its family is
already in the game twice: `torch_goblin` became the Beekeeper earlier the
same day, and **`pig_rider` — the boss "The Tusked Lance" — is this same
goblin mounted on a pig**, same helmet, same spear, same face. So the
Whirlspear is that boss's foot soldier, a link the art draws for free.

The pack's other goblin units (TNT, barrel, dynamite) are not in the tree at
all. The remaining `*goblin*` / `*gnome*` files are scenery: `goblin_hut.png`,
`gnome_hut.png`, `gnome_tower.png`.

## Two things that needed new code

### 1. A sweep is not a poke

Every melee enemy until now pokes. `path_chase_attack` drops its hitbox at
`pos + facing * radius` with radius `radius / 2` — a small disc in front. This
art is a full 360° spin of the spear, so a front hitbox would have contradicted
what the player sees.

`MeleeHitbox` is already a disc at an arbitrary centre that deals its damage
once and dies, so the sweep is the same call with the actor's own position:
**no safe side, only a safe distance**. That is also why the wind-up is longer
than a poke's — a ring cannot be side-stepped, it has to be backed out of.

New behaviour `path_chase_sweep` in `entities/ai/behaviors/melee.py`.

### 2. An enemy with two swings had no way to be seen

`Enemy._anim_name()` returned `"attack"` and nothing else, so a second attack
strip was unreachable however the data was written. It now reads the strip the
machine named in `ATTACK_SLOT["anim"]`, checked against what the rig actually
declares:

* the valid variant names are cached per body in `Enemy.__init__` (mirroring
  the existing `_has_hurt` probe) rather than looked up every frame;
* an unknown name — a typo, or a sheet that never shipped — falls back to
  plain `"attack"`, so the worst case is the ordinary swing animating rather
  than nothing at all;
* an enemy whose rig has no variant strip gets `frozenset()` and is
  bit-for-bit unaffected. There is a test for each of those three.

`telegraph_cycle` also gained a callable `telegraph`, so the wind-up length can
depend on which swing was picked. The choice is made when the wind-up
**starts**, so the telegraph the player reads always belongs to the swing that
lands — pinned by a test that pairs each telegraph's anim with the size of the
hitbox that follows it.

## Numbers

| | Whirlspear | for comparison |
|---|---|---|
| hp | 42 | Gorehorn 55, Blink 36 |
| speed | 80 | Gorehorn 90, Blink 95 |
| contact damage | 13 | Husk 13, Gorehorn 14 |
| radius | 14 | Blink 13, Gorehorn 15 |
| weight / xp | 8 / 9 | Gorehorn 8 / 8 |

| swing | ring | damage | wind-up | plays |
|---|---|---|---|---|
| fast sweep | **34** px | 13 | 0.30 s | `attack` (7f) |
| heavy whirl, every 3rd | **44** px | 21 | 0.55 s | `attack_strong` (8f) |

### The rings are measured off the art, not chosen

Worth recording because the first attempt was wrong. `sweep_reach` and
`strong_reach` started at 26 and 46, giving rings of 40 and 60 px. Measuring
the widest frame of each strip against the rig's scale ratio (0.339) showed
the fast blade reaches about **33** world px from the anchor and the heavy
whirl about **43**. So the heavy ring had **17 px of reach with no blade drawn
in it** — a hit the player cannot see coming. Retuned to 20 and 30, giving 34
and 44, and checked by eye with the rings drawn over the frames at true scale.

### Rig

256 px frames, not the 192 the rest of the pack uses. `content` is the union
ink over all four strips, `[17, 46, 236, 151]` — far wider than the goblin,
because the heavy whirl spans 216 px while the body is only 88 × 126. Sizing
`scale` off the union would have drawn a tiny goblin in a large empty cell, so
it is sized off the **body**: `scale [80, 58]`, `anchor [37, 50]`, body drawn
about 30 × 48, between Blink and Gorehorn. The reason is recorded in a
`_scale_comment` in the rig. Faces right like the rest of the pack.

The strong sheet moved from `unused/enemies/extra/spear_goblin_strong_attack/`
to `enemies/spear_goblin/attack_strong.png`, beside the others, and its now
empty source folder is gone.

## Tests

`tests/entities/ai/test_spear_goblin.py`, 19 tests: the hitbox is centred on
the body (not in front) and wider than a poke; the fast ring matches its data;
every third swing is the heavy one, hits harder, and is read for longer —
measured in frames actually spent in `telegraph`, not just asserted from the
data; the swing names its strip; the choice happens at wind-up start; the four
animation-variant cases; the rig declares both strips; and `path_chase_sweep`
has exactly one user, so "no safe side" stays the Whirlspear's identity.

Two of my own harness bugs were fixed on the way — the anim was recorded on
every telegraph *frame* rather than once per swing, which misaligned it against
the hitbox list, and the wind-up run-length counter indexed an empty list.

### The guard that fired, again

`test_melee_enemies.ATTACKING` is the set of behaviours that carry their own
damage, so an enemy may disable its passive body bite. `path_chase_sweep` had
to be added — the guard correctly said a `contact_damage_enabled: false` enemy
on an unlisted behaviour deals no damage at all. Third time this guard has
caught a new behaviour; it earns its keep.

## Progress

- [x] Art moved, strong sheet brought in beside it
- [x] Rig measured (body-sized, not union-sized)
- [x] Attack-strip variants in `Enemy._anim_name()`
- [x] Callable wind-up in `telegraph_cycle`
- [x] `path_chase_sweep`
- [x] Enemy block, rings measured off the art
- [x] Tests (19) — `tests/entities` + `tests/spawn`: 435 passed
- [x] A band weight — waiting on the band rework, like Bonepicker, Gaffjaw and *(DOC-003: the band rework landed (SPN-002): `data/enemies/spawn_tables.json`, `spear_goblin` 6 in `goblin`)*
      the Hammer Gnome
- [x] Full suite *(DOC-003: covered by later full-suite runs, e.g. `key_icons_journal.md` (2,640 passed))*
