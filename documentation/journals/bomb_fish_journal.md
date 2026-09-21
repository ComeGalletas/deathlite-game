# The Bloat throws its bomb

The bomb fish stops being a suicide rusher and starts lobbing the bomb it was
always drawn holding — and enemy shots learn how to explode.

---

## Requirement (owner, 2026-09-17)

- **Objective:** Wire the bomb fish's bomb attack.
- **Details:** Colour the bomb red, similar to the previous enemy arrow.
  Review the current bombfish enemy first.
- **Constraint:** Confirm the plan before building.

## What the check found

`bomb_fish` ran `exploder`: `Explode` sets `hp = 0` when the player comes
within `fuse_range`, and the cull pass turns the corpse into a blast. A suicide
rusher.

But its rig has **three** strips, and the third is `shoot.png` (7 frames),
wired as `attack` since the sprite shipped. `exploder` is a single-state
behaviour with no telegraph or attack state, so `Enemy._anim_name()` never
returned `"attack"` and **those frames had never once played**. The art is a
fish *lobbing* a bomb; only the behaviour said otherwise.

That is the third piece of dead art found this way — the gnome's hammer swing
and the slingshot gnome's acorn were the same story. The pattern is always the
same: art that only a state the behaviour never enters could reach.

## The thing that needed new code

A hostile bomb could not simply reuse the hero's. `TransientFx.detonate` turns
a spent bomb into a blast by spawning it into **`ps.projectiles`** — the
player's pool — so it damages *enemies*. Pointing an enemy's bomb at it would
have made the Bloat's bomb hurt its own side.

The hostile loop now detonates through `fx.explosion(pos, radius, damage)`,
which is the enemy side's area damage: it bursts, shakes, and hits the
**player**. Six lines in `update_projectiles`, mirroring the hero branch
directly above it.

Around that, the R1 seam widened again. `fire_hostile` gained `lifetime`,
`stop_after`, `blast_radius` and `inert`; `FireProjectile` gained the matching
fields plus `tint`; `kite_shoot` reads them as `shot_lifetime`,
`shot_stop_after`, `shot_blast_radius` and `shot_tint`. Every default is the
old behaviour, and a test drives the Slinger — which names none of them — to
prove it still fires a plain, non-exploding, non-inert shot.

## The bomb's life

| | |
|---|---|
| holds | 210 px (`prefer_distance`) |
| throws | every 2.8 s |
| flies | 0.55 s at 200 px/s, about 110 px out |
| then | `stop_after` halts it, and the `bomb` rig swaps `spin` -> lit `fuse` |
| burns | 0.8 s |
| blast | 62 px for 18 |

`stop_after` and the rig's two strips already existed for the hero's Bomb;
this only had to name them. `inert` is set so the bomb **is** its blast rather
than also punching on contact.

`explode_radius` / `explode_damage` stay untouched: that is the corpse blast
the cull pass makes when it dies, which is still true of a fish full of bombs.
It is not the attack, and removing it was never asked for.

## Red, like the arrow

`shot_tint` is `[150, 26, 12]` — `config.HOSTILE_ARROW_TINT`, the exact
constant the hostile arrow wears, so an incoming bomb reads as incoming.

**It has to be applied additively.** `Assets.frame(tint=)` *multiplies*
(`BLEND_RGBA_MULT`, written to recolour a white effect pack); multiplying a
dark bomb by a dark red gives near-black, not red. The additive path is
`frame_rotated(..., tint=)`, so the `bomb` style calls it at **zero degrees**
— which snaps to the identity rotation bucket and turns nothing, while giving
the additive blend. The reason is in a comment at the call site, because a
reader would otherwise reasonably "simplify" it back to `frame`.

A test asserts the tinted bomb is both brighter in red *and* redder relative
to blue than the untinted one, so that simplification fails loudly rather than
quietly producing a black ball.

## Tests

`tests/entities/ai/test_bomb_fish.py`, 13 tests: it throws rather than
detonating itself; the shot is a `bomb`, tinted with the arrow's own constant,
carrying its blast, fuse and lifetime, and inert; it fuses before it blows; an
ordinary kiter is untouched; the bomb halts partway and stays put until it
expires, driven through the real `Projectile`; the landing spot is inside the
range it kites at; the tinted bomb really is redder; and it still pops when
killed.

One harness bug of my own on the way: `Projectile.reset` does **not** set
`active` — the pool's `acquire()` does — so a directly-built projectile was
inert from frame zero and the flight test failed for the wrong reason.

### A behaviour with no data behind it, again

`exploder` now has no shipped user, exactly as `summoner` ended up after the
gnome split. `test_exploder_dies_when_it_reaches_player` drove it through the
roster id `bomb_fish` and failed once the Bloat moved; it is now built from a
literal block, the same treatment the summoner test got, so the behaviour
keeps its coverage while the roster moves on.

Two orphaned behaviours is worth a decision rather than a drift: either they
go, or something is written to use them.

## Left undone, deliberately

**The shoot animation still will not play.** `kite_shoot` has no telegraph
state either, so the strip is now reachable-but-not-driven. The test says
exactly that rather than pretending otherwise. Giving the throw a readable
wind-up means a telegraph-cycle shooter — the same shape `path_chase_sweep`
and `path_chase_breath` use — which is its own piece of work and was not asked
for.

## Progress

- [x] `fire_hostile` carries lifetime / stop_after / blast_radius / inert
- [x] Hostile bombs detonate on the player's side
- [x] `kite_shoot` reads the bomb keys
- [x] Additive hostile tint in the `bomb` style
- [x] Bloat rewired, numbers set
- [x] Tests (13)
- [ ] A telegraph so `shoot.png` actually animates
- [ ] A band weight is unaffected — it already has one and spawns today

---

## Follow-up: the thrown bomb stops shaking the screen (owner, 2026-09-19)

- **Objective:** Remove the screen shake from the bomb fish's thrown-bomb
  attack.
- **Constraint:** Do not delete the functionality — comment it out as unused
  but ready to implement. Review the enemy first; confirm before changing.

Confirmed before the change, with one question answered: the corpse blast on
death **keeps** its shake; only the thrown bomb goes quiet.

### What the review found

Since this journal was written the Bloat gained a wind-up
(`attack_telegraph` / `attack_active` / `attack_recover`, commit `fd8a276`),
so the "left undone" item below is done and `shoot.png` plays. The throw
interval is now 4.48 s, not 2.8 s. The `_bomb_comment` in the data still
tells the old `exploder` story; harmless, but stale.

Both the thrown bomb and the corpse blast detonate through the same hostile
helper, `TransientFx.explosion`, which added a 0.4 shake for either. The Bloat
is the only enemy on either path.

### The change

`explosion` takes `shake: bool = True`. The bomb detonation in
`update_projectiles` passes `shake=False`; the death pop in `combat.py` names
nothing and keeps the default. Inside the helper the shake line is still there
behind the switch, with a comment marking the thrown-bomb shake as unused and
saying how to bring it back (drop the argument, or give the bomb its own
lighter amplitude).

Two tests in `ShakeTests`: a spent bomb driven through the real hostile loop
bursts without touching `ps.shake`, and the helper called the way `combat.py`
calls it still shakes once.

### Progress

- [x] `shake` switch on the hostile `explosion` helper
- [x] Thrown bomb detonates without a shake; death pop unchanged
- [x] Tests (2)
- [x] A telegraph so `shoot.png` actually animates (done separately, `fd8a276`)
