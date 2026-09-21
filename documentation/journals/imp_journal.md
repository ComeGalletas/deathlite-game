# The Imp ("Cinder") — wiring a delivered enemy

An enemy the owner dropped into `assets/enemies/imp/` on 2026-09-17, wired as
the roster's first fire-breather: a three-part attack that leaves a burning
pool on the ground.

---

## Requirement (owner, 2026-09-17)

- **Objective:** Wire the newly delivered `imp` enemy from the enemies
  folder.
- **Constraint:** Confirm the wiring plan first.

## What was delivered, and what it turned out to be

Six PNGs and an `.aseprite` source, with capitalised names:
`Imp_Idle` (8f), `Imp_Move` (6f), `Imp_Attack_Start` (4f),
`Imp_Attack_Loop` (4f), `Imp_Attack_End` (4f), `Imp_Avatar`. 192 px frames.

A rust-orange imp with white horns, mauve eyes and a long tail. It **spits a
stream of fire that pools on the ground in front of it**: the start rears it
back and the first drops fall, the loop holds the stream while the pool
burns, and the end breaks the pool into embers that fade.

Two things about it are new to the codebase:

* **The only three-part attack.** Every other attack is one strip. Start /
  loop / end maps exactly onto the three states `telegraph_cycle` already
  has — telegraph, attack, recover — which is what made this cheap.
* **A hazard, not a hitbox.** The damage should be where the fire is drawn:
  on the ground, over time. That is the area-denial machinery Hexcaller
  already uses, so no new damage path was needed.

### Which way it faces — measured, because looking was misleading

My first read off the frames was **wrong**: cropped to their own ink, the
frames put the flame on the left and I concluded it faced left, which would
have been a problem (`rendering.py` flips only when `face == "right"`, so a
rig declared `"left"` is never flipped at all and would have walked backwards
half the time).

Rendering the frames *uncropped* and taking the centroid of the flame-coloured
pixels against the body's settled it: flame mean x 149, body mean x 100 in a
192 px frame. It spits along **+x**, so `"face": "right"` like the rest of
the pack.

## Built

- **Files normalised and the source archived.** `Imp_Idle.png` ->
  `idle.png`, `Imp_Move.png` -> `walk.png`, the three attacks ->
  `attack_start` / `attack_loop` / `attack_end`, `Imp_Avatar.png` ->
  `avatar.png`, matching every other rig. `Imp.aseprite` moved to
  `assets/unused/enemies/imp/` — `CREDITS.md` states that editor sources are
  not shipped, and a test now enforces that for this folder.
- **Rig** `imp`: `content [34, 41, 152, 124]`, `scale [78, 54]`,
  `anchor [34, 48]`. Sized from the **body** (76 × 104 of the 152 × 124
  union) rather than the union, which the flame stretches well to the right —
  the same trap the Whirlspear's rig has a comment about. Drawn about
  39 × 45, between Husk and Gorehorn. Six anims: the three attack strips,
  plus a plain `attack` aliased to the loop so anything that asks for the
  generic name still gets fire.
- **`path_chase_breath`** in `entities/ai/behaviors/melee.py`: the pursuit
  stack into `telegraph_cycle`, naming a strip at each state and spawning the
  hazard when the loop begins. The hazard carries **no sprite** — the imp's
  own frames draw the flame, and a hazard sprite on top would render it
  twice.
- **Two small extensions to shared code**, both needed by the three-part
  shape:
  - `telegraph_cycle` gained `on_recover_start` (there was a hook for the
    wind-up's start and end, but none for entering recover), and now **clears
    the named strip** on its way back to chase — otherwise a multi-strip
    enemy walks around holding its last flame frame. Only the `anim` key is
    cleared; the Whirlspear's swing counter lives in the same slot.
  - `Enemy._anim_name()` lets a named strip win **wherever the machine is**,
    not only while `_attacking`. The imp's embers play over *recover*, which
    is not an attacking state, so the old gate would have dropped the tail of
    its animation.

## Numbers

| | Cinder | for comparison |
|---|---|---|
| hp | 34 | Blink 36, Bloat 29 |
| speed | 86 | Gorehorn 90, Blink 95 |
| radius | 13 | Blink 13 |
| weight / xp | 6 / 10 | Blink 6 / 9 |
| cycle | 0.4 wind-up / 0.65 loop / 0.4 embers / 2.6 cooldown | |
| pool | centre 25 px ahead, radius 15.3, 16 dps every 0.25 s for 1.05 s | |

`contact_damage_enabled` is false: only the fire hurts.

### The pool is measured off the art too

Same discipline as the Whirlspear's rings, and it caught the same class of
mistake. The first values — `breath_offset` 16, `hazard_radius` 30 — put the
burn 29 px ahead at nearly twice the drawn flame. Measuring the
flame-coloured pixels in all four loop frames gave a centre **25.5 px** ahead
of the anchor with a half-width of about **17**, consistently across frames.
Retuned to offset 12 (centre 25) and radius 19, so the burn covers 6–44 px
ahead and stays inside the fire the player can see. Recorded in a
`_breath_comment` in the data.

### Then 35 % smaller (owner, 2026-09-17)

- **Objective:** Reduce the area of the ember-circle attack by about 35 %.

**Area**, not radius — and a percentage on a size means area in this project
by standing convention, not the linear knob. So the radius scales by
`sqrt(0.65)`: **19 -> 15.3**, a 35.2 % smaller disc. Taking 35 % off the
radius instead would have cut the area by 58 %, nearly twice what was asked.

15.3 rather than a round 15 because the field is a float and 15 lands at
37.7 %; this data already carries values like `attack_telegraph: 0.2875`, so
the precision is in keeping.

Knock-on effects, both small and both fine: the burn covers **10-40 px**
ahead instead of 6-44, so it now sits just inside the drawn pool
(half-width ~17) rather than matching its edge — the fire reads slightly
wider than it bites, which errs toward the player. And `trigger_range` is
derived from the hazard radius, so the imp closes to **40 px** before
breathing instead of 44.

`hazard_duration` (1.05) is deliberately `attack_active + attack_recover`,
so the burning stops on the last drawn ember rather than while flame is still
on screen. A test pins that equality.

## Tests

`tests/entities/ai/test_imp.py`, 20 tests: it leaves a hazard and neither a
hitbox nor a shot; the pool lands in front at the measured offset and carries
its data; it has no sprite of its own; the burn spans loop *and* embers; it
does not breathe out of range and does breathe again on cooldown; each state
names its own strip and the name is cleared on the way back to chase; all
three variant strips are known to the body; the tail plays during recover
while `_attacking` is false; the loop strip loops and the other two do not;
the editor source is not shipped; and it is the only breather, with
`hazard_dps` appearing on exactly Hexcaller and the imp.

`test_melee_enemies.ATTACKING` got `path_chase_breath` added — pre-empted
this time rather than waiting for the guard to fire, which it has done for
each of the last three new behaviours.

## Provenance

The credits entry was deliberately left blank at first: a licence claim
guessed in a credits file is worse than a missing one, and the imp's chunkier,
more painterly look read to me as a different pack. The owner confirmed
(2026-09-17) that **it is Tiny Swords**, so it joins that pack's enemy list in
`assets/CREDITS.md` and needs no separate entry — Tiny Swords is already
covered there, purchased, attribution optional.

That fix also corrected a sentence that this delivery had made untrue.
`CREDITS.md` claimed "`.aseprite` editor sources ... were removed"; the imp
shipped with one, and this project archives source art under `assets/unused/`
rather than deleting it. The sentence now says what actually happens and
points at `assets/unused/enemies/imp/`.

## Progress

- [x] Files normalised, `.aseprite` archived
- [x] Facing measured (right)
- [x] Rig measured (body-sized)
- [x] `on_recover_start` + strip clearing in `telegraph_cycle`
- [x] A named strip wins outside the attack states
- [x] `path_chase_breath`
- [x] Enemy block, pool measured off the art
- [x] Tests (20) — `tests/entities` + `tests/spawn`: 455 passed
- [x] `CREDITS.md` — Tiny Swords, confirmed by the owner
- [ ] A band weight — waiting on the band rework, like the other four
