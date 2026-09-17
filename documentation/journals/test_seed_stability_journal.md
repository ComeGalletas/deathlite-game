# Test seed stability journal

## Requirement (2026-09-17)

> "review the tests that depend on world generation and consider adding a
> fixed seed to make sure its stable. confirm."

Preceded, the same day, by two narrower requests: fix a ghost-render test that
passed roughly one run in five, and "pin those four helpers to a seed".

## Confirmed reading

**Where the randomness comes from.** `LoadingState.enter` draws the run seed
from `random.randrange(1 << 30)` when no seed is handed in. A test that walks
the menu into a run (ENTER, ENTER) therefore builds a *different world every
time it runs*. Nothing in the failure output says which one.

**What it costs, measured this session, not theorised:**

1. `tests/render/test_ghost.py::RunIntegrationTests` passed about one run in
   five. On the passing runs it was measuring the hero, not the enemy it
   names; the enemy was never drawn at all. The world randomness hid a real
   defect behind an intermittent pass.
2. Seven tests behind unpinned boots guarded themselves with
   `skipTest("no shrine in this layout")`, `"no fountain…"`, `"no treasure…"`,
   `"no altar…"`, `"no merchant…"`, `"no villager standing in the open on this
   seed"`, `"no spot clear of every lancer's aggro radius"`. On an unlucky
   world they reported green without asserting anything.
3. `test_dev_mode.py::test_no_damage_keeps_the_hero_attacking_but_deals_zero`
   fails on about 1 world in 24: a tank spawned at a fixed `+ (30, 0)` lands
   over a drop and walks to 163 px away, so the hero's attacks never reach it.
   `tests/nearby.py` already documents this family ("four seeds in twenty")
   and its sibling test three lines up was already fixed; this one was missed.
4. **Order coupling.** Every unpinned boot consumes one draw from the global
   `random` stream. Pinning a seed anywhere shifts every *later* unpinned
   world in the same process. Finding (3) surfaced exactly this way — it was
   latent for as long as the stream happened to favour it.

**What should not be pinned.** The generator's own tests in `tests/world/`
already take explicit seeds (`W.layout(seed)`, `W.baked(seed)`) and sweep seed
ranges under the `sweep` marker. Collapsing those to a single seed would
weaken them: a per-island invariant asserted on one seed holds by luck, where
a rate measured over a sweep says what the pass actually promises. They are
out of scope. (See `worldgen_refactor_plan.md` and the standing rule that the
generator leads and the tests follow.)

**The boundary, stated plainly:** a test that *uses* a world as a fixture pins
a seed. A test that *measures the generator* sweeps seeds. A test whose
subject is the menu path itself keeps pressing keys.

## Survey

Twenty-five test modules boot a run. Their state before this change:

| Group | Modules | Action |
| --- | --- | --- |
| Already pinned | `test_bomb` (7), `test_chest_open` (1234), `test_enemy_nav` (3/1234), `test_potion_drops` (1234) | none |
| Pinned earlier today | `test_depth_sort` (+ `test_ghost`, `test_render_cull`), `test_npcs`, `test_interactables`, `test_manual_aim` | none |
| Unpinned fixture boots | `test_incoming_damage`, `test_weapons_special`, `test_damage_numbers`, `test_enemy_sprite`, `test_gem_glow`, `test_hostile_glow`, `test_spawn_fx`, `test_level_up`, `test_pause`, `test_dev_mode` | **pin** |
| Menu path is the subject | `test_menu`, `test_hero_unlock`, `test_options`, `test_rankings`, `test_ui_scale`, `test_ultrawide` | leave |
| Random world is the point | `test_smoke` | leave |

`test_smoke` is excluded on its own authority: its docstring says "the run
seed is left random on purpose -- booting a different world every time is most
of this test's value -- so nothing here may depend on what the world looks
like", and it is already written that way, taking its spawn points from
`spots_near`. Pinning it would delete the coverage it exists for.

Fixed-offset spawns audited separately. Most are read immediately, with no
frames of movement in between, so an unwalkable spot cannot hurt them
(`test_enemy_sprite`, `test_spawn_fx`, `test_dev_mode:318`). The ones that let
the world run before asserting are the exposed ones, and they are what
`spots_near` is for.

## Proposal

1. Extend `start_run(game, seed=None, keys=(), dev=False)` in `tests/boot.py`
   — already the shared menu-to-run drive — so it covers the hero-index walk
   (`keys`) and the developer-mode row (`dev`) the remaining modules need.
2. Route each unpinned fixture boot through it with `SEED = W.SEEDS[0]`,
   keeping `seed=None` available for anything that deliberately wants variety.
3. Fix the fixed-offset spawn in `test_dev_mode` with `spots_near`, as its
   sibling already does.
4. Leave `tests/world/`, the six menu-flow modules and `test_smoke` alone.

## Progress

- [x] Ghost test fixed and seeded (`test_ghost.py`), 10/10 runs.
- [x] `start_run` added to `tests/boot.py`; four helpers pinned.
- [x] `test_dev_mode` fixed-offset tank spawn moved to `spots_near`; 0/24
      seeds fail where seed 13 used to.
- [x] Suite green with every collected test running: **2430 passed, 0 skipped,
      0 failed** (was 2429 passed + 1 skipped, with the ghost test green but
      vacuous).
- [x] Remaining fixture boots pinned: `test_gem_glow`, `test_hostile_glow`,
      `test_level_up`, `test_pause`, `test_spawn_fx`, `test_enemy_sprite`
      (four helpers), `test_incoming_damage`, `test_weapons_special`,
      `test_damage_numbers`, `test_dev_mode`. `start_run` grew `keys=()` for
      the hero-index walk and `dev=False` for the developer-mode row.
- [x] Suite green after pinning: **2430 passed, 0 skipped, 0 failed**, 12:18.

## Result

Every test that consumes a generated world now names the world it consumes,
except the three groups excluded above for stated reasons. A failure in one of
them is reproducible from the module alone, and no test can silently opt out
of its own assertions because the dice went against it.

## Seed range (2026-09-17, second pass)

> "apply the seed range, 3 could be a good start if you can test them
> properly. the other assumptions are fine, if the tests themselves depend on
> random seeds dont touch them."

One world shaping every assertion was its own hazard -- a quirk of that world
would be invisible, because nothing would disagree with it. `W.pinned(index)`
in `tests/worlds.py` now spreads the modules over `SEEDS[:3]` (35, 7, 1234)
and carries a `DEATHLITE_TEST_SEED` override that forces the whole suite onto
any world:

    DEATHLITE_TEST_SEED=99 python -m pytest -q

The override is the standing tool for "test them properly": a module that
holds on only one world is asserting something about that world by accident,
and this is what finds it.

| Seed 35 | Seed 7 | Seed 1234 |
| --- | --- | --- |
| `test_depth_sort` (+ `test_render_cull`) | `test_ghost` | `test_npcs` |
| `test_interactables` | `test_manual_aim` | `test_gem_glow` |
| `test_hostile_glow` | `test_level_up` | `test_pause` |
| `test_spawn_fx` | `test_enemy_sprite` | `test_incoming_damage` |
| `test_weapons_special` | `test_damage_numbers` | `test_dev_mode` |

Verified before the assignment was kept: all sixteen modules were run against
each of the three worlds with `-rs`, so a skip would have counted against the
assignment as loudly as a failure.

| Forced seed | Result |
| --- | --- |
| 35 | 289 passed, 0 skipped, 0 failed (6:47) |
| 7 | 289 passed, 0 skipped, 0 failed (6:56) |
| 1234 | 289 passed, 0 skipped, 0 failed (6:14) |

Every module holds on every seed in the pool, so the round-robin is not luck
and nothing needed reassigning.

Untouched on the owner's instruction, "if the tests themselves depend on
random seeds dont touch them": `test_smoke` (the random world is its subject),
the six menu-flow modules, `tests/world/`, and the four modules that were
already pinned to seeds of their own.

- [x] Full suite after the spread: **2430 passed, 0 skipped, 0 failed**,
      16:45.
