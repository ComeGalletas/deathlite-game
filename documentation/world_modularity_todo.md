# World Modularity TODO

## Purpose

Evolve the world system without changing game behavior. Preserve the stable
entry points `world.procedural.generate_world`, `world.map.GameMap`, and the
current renderer-facing methods while separating generation, runtime geometry,
terrain baking, and rendering state.

## Guardrails

- Do not change seeds, layouts, collision behavior, baked pixels, or draw
  ordering unless a task explicitly calls for a behavior change.
- Preserve compatibility imports in `world/procedural.py` until callers are
  migrated deliberately.
- Keep `GameMap` public methods and test-observed private attributes working
  through narrow forwarding properties where needed.
- Treat `game.config` as an input snapshot for new generation work. Do not let
  a layout be generated under one terrain mode and baked under another.
- Complete each phase independently: focused tests first, then the full suite.

## Phase 0 - Establish Characterization Coverage

- [ ] Inventory all callers of `generate_world`, `GameMap`, terrain bake
      fields, and renderer methods.
- [ ] Add a shared layout digest helper for rooms, cells/grids, corridors,
      stairs, obstacles, palettes, and tile metadata.
- [ ] Add deterministic fixtures for flat, flat-with-verticality, and
      heightmap configurations using a small representative seed set.
- [ ] Add a headless bake digest for every generated surface and anchor list.
- [ ] Add a composited screenshot or pixel-hash check for representative flat
      and heightmap scenes.

Acceptance criteria:

- The characterization checks identify a regression in layout, bake output, or
  draw output.
- Existing full-suite command remains green:
  `python -m unittest discover -s tests -t .`.

## Phase 1 - Make Layout Modes Explicit

- [ ] Add an immutable `GenerationRequest` or `GenerationSettings` value in
      `world/gen/` that snapshots the generation-relevant configuration.
- [ ] Pass that value through the generation orchestrator and its stages.
- [ ] Define explicit layout-mode invariants, for example:
      - flat rooms have complete `cells` and `tile_meta`;
      - heightmap rooms have a grid, a derived walkable cell set, palette data,
        and any required inset data;
      - all rooms and heightmap grids are tile-aligned where `LevelIndex`
        requires it;
      - all required links remain traversable.
- [ ] Implement a validation helper that is invoked at the end of generation
      in development/test contexts.
- [ ] Parameterize the structural world tests so all supported modes receive
      the same baseline contract checks.

Acceptance criteria:

- Same request and seed produce the same layout digest.
- Invalid or incomplete mode-specific layouts fail with an actionable error.
- No downstream caller needs to infer mode from a missing mutable field.

## Phase 2 - Give Both Generators First-Class Ownership

- [ ] Move the remaining flat verticality implementation out of
      `world/legacy/verticality.py` into `world/gen/verticality.py`, or retain
      a temporary compatibility module that only forwards imports.
- [ ] Split `generate_world` into small, mode-specific pipeline functions such
      as `_generate_flat_layout` and `_generate_heightmap_layout`.
- [ ] Keep common stages in the top-level orchestrator only when both modes
      truly share their inputs and outputs: lattice/tree construction, role
      assignment, bounds normalization, and final layout assembly.
- [ ] Document each stage's inputs, fields produced, and ordering constraints.
- [ ] Remove direct imports from `world/legacy/` once compatibility forwarding
      has no consumers.

Acceptance criteria:

- `generate_world(seed)` remains the public entry point.
- Both mode pipelines return the same `WorldLayout` public contract.
- Characterization layout digests remain unchanged.

## Phase 3 - Isolate Runtime Geometry from Presentation

- [ ] Extract collision, point lookup, inset checks, and elevation movement
      rules from `GameMap` into a focused runtime geometry object or module.
- [ ] Keep `GameMap` as a facade that owns a layout and delegates its current
      public query methods.
- [ ] Keep `LevelIndex` as the single runtime elevation source; do not add
      parallel rasterization logic in renderers or AI.
- [ ] Make the distinction between walkability, elevation, and terrain-top
      collision explicit in the runtime API.

Acceptance criteria:

- Movement, spawning, AI navigation, and projectile behavior retain existing
  results for characterization seeds.
- Runtime queries do not require terrain assets or a display surface.

## Phase 4 - Introduce an Explicit Baked Terrain Result

- [ ] Create `BakedTerrain` under `world/terrain/` to own terrain surfaces,
      shoreline anchors, foam, shadows, obstacle skins, and decor instances.
- [ ] Replace direct painter mutation of `GameMap._*` fields with mutation of
      this dedicated object.
- [ ] Give flat and heightmap terrain separate baking functions that return the
      same `BakedTerrain` contract.
- [ ] Keep `GameMap._build_tiles()` as a compatibility entry point that stores
      the result and provides any existing forwarding properties needed by
      callers/tests.
- [ ] Move the cliff-cap setup, terrain painting, shore filtering, and shared
      finishing steps into named functions with clear preconditions.

Acceptance criteria:

- Terrain painters no longer depend on unrelated `GameMap` behavior.
- The bake digest is byte-identical for characterization seeds.
- A missing tileset still takes the existing flat fallback path.

## Phase 5 - Make Rendering Consume the Baked Contract

- [ ] Update `TerrainRenderer` to receive layout/runtime geometry plus
      `BakedTerrain`, rather than reading a broad set of `GameMap._*` fields.
- [ ] Preserve existing layer order: water, foam/void decor, terrain bands,
      connectors, then depth-sorted scenery and entities.
- [ ] Make the terrain mode explicit in the baked result instead of using the
      presence of `_grid_surfs` as the mode signal.
- [ ] Keep zoom caching local to rendering or the baked result, with cache
      invalidation tied to zoom changes.

Acceptance criteria:

- Pixel/screenshot characterization checks remain unchanged.
- Existing depth-sort tests continue to pass.
- Renderers do not regenerate terrain or mutate layout data.

## Phase 6 - Clarify Shared World Services

- [ ] Classify `frontier`, biome selection, and inset calculations as shared
      world services with documented inputs and outputs.
- [ ] Move them to a neutral package only if import direction remains clear;
      avoid a generic dumping-ground package.
- [ ] Centralize palette and biome ownership so generation, scatter, and
      terrain painting all read the same generated palette contract.
- [ ] Remove compatibility shims only after all internal imports use the new
      ownership boundaries.

Acceptance criteria:

- No import cycle is introduced.
- Every shared service has a focused unit test and a documented producer /
  consumer contract.

## Phase 7 - Cleanup and Documentation

- [ ] Update `journals/world_refactor.md` with each completed phase, its
      verification evidence, and any compatibility shims retained.
- [ ] Update the project layout section in `README.md` if module ownership
      changes materially.
- [ ] Delete empty legacy modules only after a repository-wide import search.
- [ ] Record residual coupling that is intentionally retained and why.

Acceptance criteria:

- Public APIs and compatibility policy are documented.
- Full suite is green and no obsolete imports remain.

## Handoff Brief

Use the following as a task prompt for an AI coding agent or human implementer:

```text
Implement the world modularity plan in documentation/world_modularity_todo.md,
starting with Phase 0 only unless explicitly asked to continue.

Repository context:
- `world/gen/__init__.py` orchestrates seeded world generation.
- `world/layout.py` defines Room, Corridor, Stair, Cell, TileMeta, and
  WorldLayout.
- `world/map.py` currently combines runtime geometry, lazy terrain baking, and
  renderer-facing state.
- `world/terrain/bake.py` builds terrain surfaces; `world/terrain/render.py`
  composites them.
- Flat and heightmap worlds are both supported and selected by configuration.

Non-negotiable constraints:
1. Preserve behavior. Same seed and configuration must keep the existing
   layout, collision, bake, and draw results unless a requested task explicitly
   changes behavior.
2. Preserve public compatibility. Keep `world.procedural.generate_world` and
   `world.map.GameMap` stable. Maintain narrow forwards for private attributes
   reached by tests until consumers are deliberately migrated.
3. Do not perform broad rewrites. Work one phase at a time, with the smallest
   cohesive edit set.
4. Before editing, identify the owning code path and state one falsifiable
   hypothesis plus a focused check.
5. After each substantive edit, run the narrowest relevant test or
   characterization check before further edits. Run the full suite before
   declaring a phase complete:
   `python -m unittest discover -s tests -t .`
6. Preserve lazy baking: asset-dependent terrain work must not be required for
   runtime geometry or headless layout generation.
7. Do not add a generic `common` package by default. Move shared code only when
   its dependency direction and contract are clear.
8. Update `journals/world_refactor.md` and append a concise entry to
   `journals/journal.md` after each completed phase. Each entry must say what
   was done, verification performed, remaining risks, and the expected next
   phase.

Phase 0 deliverables:
- A reusable layout digest and deterministic multi-mode fixtures.
- Headless bake and representative draw characterization checks.
- No production behavior changes.

Report at the end:
- files changed;
- commands/tests run and results;
- whether layout, bake, and draw digests stayed identical;
- any blockers or intentionally deferred work;
- the exact next TODO item.
```