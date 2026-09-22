# Chaser collider journal

**Legacy ID:** ENT-003 · **Systems:** ENT · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-14)

- **Objective:** Shrink the chaser enemy's collision ring.
- **Constraint:** The sprite's drawn size stays exactly as it is.

## Confirmed reading

- The chaser (Husk, `skull` rig) keeps its collider in one field:
  `radius` in `data/enemies/enemies.json`, previously 14 (a 28 px ring).
- The sprite's drawn size comes only from the rig's `scale` in
  `data/enemies/enemy_sprites.json` (56x36) and never reads the radius, so
  the change is data-only.
- Everything else that reads `radius` tightens with it: world and bump
  collision, projectile hit tests, the melee trigger reach
  (`radius + PLAYER_RADIUS + 5`), the swing hitbox (`radius / 2`), spawn
  clearance and the death-fx size.
- One rendering coupling: the sprite is seated `SPRITE_ANCHOR_DROP * radius`
  (0.83 x radius) px below the collider centre. Shrinking the radius alone
  would lift the skull ~3.3 px. The user asked for the sprite to stay put.

## Decision

- `radius` 14 -> 10 (matches the Skitter; a 20 px ring that hugs the skull
  body instead of its wings).
- Skull rig `anchor` y 36 -> 33 to cancel the 3.32 px smaller drop
  (anchors are integer, so a 0.32 px residual remains -- sub-pixel).

## Progress

- [x] `data/enemies/enemies.json`: chaser `radius` 10.
- [x] `data/enemies/enemy_sprites.json`: skull `anchor` [20, 33].
- [x] Tests: no test pinned the chaser radius; enemy / combat / render /
      spawn / playing suites run below.

## Result

`pytest tests/entities tests/combat tests/render tests/spawn tests/playing`:
1111 passed, 132 subtests passed, 0 failures. No test changes were needed.
