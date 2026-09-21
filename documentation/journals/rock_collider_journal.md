# Rock collider journal

## Requirement (owner, 2026-09-16)

- **Objective:** Reduce the rock obstacles' hitbox/collision ring by about
  35 %, after reviewing the current obstacle placements.
- **Constraint:** The sprite's size stays the same.

## Review: where a rock's numbers live today

One obstacle kind, `rock`, declared in `data/world/terrain.json`
`obstacles.rock`: `radius` 30, `blocks_projectiles` true. Its art is one of
four interchangeable rigs (`deco_rock_1..4`), picked by the run seed's
`variant`.

| | value |
|---|---|
| collider | r 30 -> a **60 px** ring |
| drawn content width | `2 * r * size_boost` = 2*30*1.25 = **75 px** |
| sprite seat | `SPRITE_ANCHOR_DROP * r` = 0.83*30 = **24.9 px** below the collider centre |
| rocks per world | **113.5** (measured, seeds 35/7/1234/42) |
| rock-to-rock nearest neighbour | min **77.1** px, p10 95.3, median 220.8 |

So the ring is already 80% of the visible boulder -- much tighter than a
tree, whose 26 px trunk ring sits under a 55 px canopy. That is why a rock
"feels" like it blocks more than it looks: it very nearly does.

The 77.1 px floor is not a coincidence. The world scatter accepts a new prop
only outside `placed.radius + _OBSTACLE_GAP` (46), so 30 + 46 = 76 is the
hard floor for anything placed next to a rock. The same `o.radius + gap`
shape appears in `world/gen/repair.py` (start/boss clear discs),
`world/gen/spawnpoints.py` (`+ _SPAWN_OBSTACLE_GAP`) and
`world/gen/village.py`. **Every one of them tightens when the collider
shrinks** -- that is the only real consequence of this change.

## Proposal

Three data edits, no code, following the tree (`render_radius`) and the
chaser-collider (seat compensation) precedents:

1. `obstacles.rock.radius` **30 -> 19.5** (-35%; a 39 px ring).
2. `obstacle_decor.render_radius.rock` = **30**, so `rig_scale` keeps
   scaling every rock rig to a 75 px footprint. Sprite size unchanged, and
   `obstacle_reach` / `paint_reach` -- the terrace-frontier and village-tidy
   rules -- keep seeing the same art, so nothing about overhangs or building
   clipping moves.
3. `obstacle_decor.sprite_drop.rock` = **1.28**, cancelling the smaller seat
   (1.28 * 19.5 = 24.96 px vs 24.9 today, a 0.06 px residual). Without it the
   art would lift ~8.7 px off its ground contact.

## Open decision: the placement drift

Measured by rebuilding the four pinned seeds with the new radius:

| | props/world | rocks/world | rock nn floor | rock nn median |
|---|---|---|---|---|
| today | 503.0 | 113.5 | 77.1 px | 220.8 px |
| r 19.5 | 511.2 | 114.2 | 66.2 px | 196.4 px |

About 1.6% more props fit, rocks pack ~11 px closer, and **every seed's
layout reshuffles** -- the worlds stay well-formed (66 px between 39 px
rings), they are simply different worlds.

## Decision (owner, 2026-09-16)

**A -- accept the reshuffle.** Data-only; the generator leads and the digests
follow. Option B (a 30 px "spacing radius" threaded through scatter, repair,
spawnpoints and village so worlds came out identical) was not worth a new
per-kind concept for an 11 px spacing difference.

## Progress

- [x] `data/world/terrain.json`: `obstacles.rock.radius` 19.5,
      `obstacle_decor.render_radius.rock` 30,
      `obstacle_decor.sprite_drop.rock` 1.28.
- [x] Verified against the bake, seed 35, all four rock rigs: frame sizes
      identical (81, 96, 123, 150 px) and the blit offset from `o.pos`
      unchanged to 0.06 px -- the art neither resizes nor moves.
- [x] `tests/world/digests.json` re-pinned
      (`python -m tools.verification.world_digest --write`). The twelve
      digest failures were the only ones in 322 world tests; nothing else
      needed touching, including `test_prop_coverage`, `test_decor_frontiers`
      and `test_obstacle_families`, which all read the art rather than the
      collider and so never saw the change.
- [x] Suites green: world 322, render 307, playing 222, combat 239,
      screens 402, spawn 132, flows 107, entities 218, progression 153,
      systems 98, display 64, devtools 34.
