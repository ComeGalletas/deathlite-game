# Enemy AI — architecture & refactor journal

Scope: `entities/enemy_ai.py`, `entities/enemy.py`, `entities/boss.py`, and the
enemy-facing seam in `game/states/playing_state.py`. **Out of scope:**
`world/pathfinding.py` (`NavGrid` / `FlowField` / `NavField`) — already isolated,
pure, game-import-free; the refactor consumes it through a small `nav_dir`
protocol method and otherwise leaves it alone.

---

## Why

The behaviour module grew into a 377-line grab-bag:

- **`EnemyContext`** is an 11-field god-object, half of it bound `PlayingState`
  private methods, re-allocated every frame — the AI is coupled to PlayingState's
  shape, just implicitly.
- **`enemy.ai`** is an untyped `dict`; every behaviour invents its own keys
  (`nav_head`, `stuck_at`, `fs`, `ft`, `cd`, `slam_state`, `cast_at`, `dir`, …).
  Nothing declares a behaviour's state contract; collisions are a typo away.
- **Three paradigms, one file**: stateless steer (`chase`, `path_chase`), ad-hoc
  timers (`kite_shoot`, `summoner`, `brute`, `exploder`), and an FSM engine
  (`_fsm_common`) buried mid-module.
- **Steering primitives don't compose**: `path_chase` hand-assembles
  `head + separation + obstacle_avoid + unstick`; `_approach` is bare; every
  other mover rolls its own retreat with raw `_toward`.
- **Tuning is scattered**: per-enemy numbers in `data/enemies.json` (good), but
  the steering constants are module-level `_UPPER` in `enemy_ai.py`, the nav
  knobs split between `config.py`, `pathfinding.py` module constants, and
  `playing_state.py`.
- **`Boss` is a parallel implementation** — its own phase machine, its own
  `_approach`, shares only the `ctx`.

## Goals

1. Behaviours = **composed pipelines of small parametrized components**, not
   bespoke functions. Adding a variant that reuses components is data; adding a
   new *kind* of move is one component file.
2. **One code path for `Enemy` and `Boss`**.
3. AI package depends on **protocols**, never on `PlayingState`. The
   `EnemyContext` god-object is replaced by two narrow interfaces.
4. **Typed per-actor state** (a `Blackboard`) instead of `enemy.ai`.
5. One obvious home per tuning number: component *shape* is code
   (`behaviors/*.py`), component *numbers* are data (`enemies.json`), component
   *defaults* are dataclass fields.

---

## Target architecture

### Two-protocol context (`entities/ai/context.py`)

```python
class Perception(Protocol):        # read-only world snapshot
    dt: float; now: float
    player_pos: Vector2; player: object; rng: Random
    def nav_dir(pos, radius) -> Vector2: ...
    def neighbors(pos, radius) -> list: ...
    def obstacles_near(pos, radius) -> list: ...
    def is_walkable(pos, radius) -> bool: ...
    def resolve_movement(prev, new, radius) -> Vector2: ...

class Combat(Protocol):            # side-effect actions
    def fire_projectile(**kw): ...
    def summon(id, pos, n): ...
    def explosion(pos, r, dmg): ...
    def spawn_hazard(pos, r, dps, dur, tick=None): ...
    def report_damage(amount): ...
```

`PlayingState` supplies one adapter implementing both, built once per frame (or
once and mutated). Nothing in `entities/ai/` imports `game.states`.

### Actor protocol (`entities/ai/actor.py`)

What a component may touch: `pos`, `vel`, `radius`, `speed`, `alive`,
`contact_damage`, `facing`, `bb`. `Enemy` and `Boss` both satisfy it.

### Blackboard (`entities/ai/blackboard.py`)

Per-component namespaced scratch — `bb.slot(component.key)` returns that
component's private dict; keys cannot collide across components. Replaces
`enemy.ai`.

### Steering accumulator (`entities/ai/steering.py`)

Steering components `acc.add(vec, weight)`; a dash/blink component may
`acc.set_velocity(v)` to bypass the force sum. `acc.resolve(speed)` = weighted
sum → normalize → `* speed`, or the absolute override, or zero (an empty state =
rooted).

### Behaviour = a (possibly 1-state) machine (`entities/ai/machine.py`)

```python
class Behavior:
    states: dict[str, list[Component]]
    transitions: list[Transition]        # Transition(frm, to, when(actor, per)->bool)
    initial: str
    # stateless & shareable across all enemies of a type; per-actor current
    # state lives in actor.bb.slot("__machine__")["state"].
    def tick(self, actor, per, cmb): ...
```

A plain chaser is `{"move": [SeekTarget()]}`. The old
`chase → telegraph → attack → recover` FSM is four states, each a component list,
joined by `Transition`s.

### Registry (`entities/ai/registry.py`)

`@behavior("kite_shoot")` decorates a builder `fn(cfg) -> Behavior`;
`build_behavior(name, cfg)` resolves it (`cfg` = the enemy's `data/enemies.json`
block). `registered()` lists names.

### Folder layout

```
entities/ai/
    __init__.py            # public surface: build_behavior, behavior, protocols, primitives
    context.py             # Perception / Combat protocols
    actor.py               # Actor protocol
    blackboard.py          # Blackboard
    steering.py            # Steering
    machine.py             # Component, Transition, Behavior
    registry.py            # @behavior, build_behavior, registered
    components/
        seek.py            # SeekTarget(via="nav"|"straight", slew=), Flee, MaintainRange
        crowd.py           # Separation, AvoidObstacles
        recovery.py        # Unstick
        timing.py          # Cooldown, ProximityTrigger, Interval
        attacks.py         # TelegraphAttack, GroundSlam, Charge, Blink, Explode
        ranged.py          # FireProjectile, SummonBrood, CastHazard
    behaviors/
        simple.py          # "chase", "path_chase", "swarm"
        ranged.py          # "kite_shoot", "summoner", "warlock"
        melee.py           # "exploder", "brute", "charger", "teleporter"
        boss.py            # boss phase machine on the same components
```

### Component catalog (initial)

| component | params | replaces |
|---|---|---|
| `SeekTarget(via, slew, weight)` | `via="nav"\|"straight"`, `slew` (heading ease /s), `weight` | `_toward`, `_approach`, path_chase heading + slew |
| `Flee(target, weight)` | | kite / summoner / warlock retreat branch |
| `MaintainRange(distance, band, close_via)` | | `kite_shoot` / `fsm_warlock` hold logic |
| `Separation(radius_mult, weight, cap)` | | `_separation` |
| `AvoidObstacles(margin, weight, cap)` | | `_obstacle_avoid` |
| `Unstick(seconds, progress_frac, nudge_strength, nudge_seconds)` | | `_unstick` |
| `Cooldown(seconds)` | | `ai["cd"]`, `ai["slam_t"]`, `ai["shoot_t"]`, `ai["summon_t"]` |
| `ProximityTrigger(range)` | | the `dist <= trigger_range` checks |
| `TelegraphAttack(windup, active, recover, on_start, on_tick)` | | `_fsm_common` |
| `FireProjectile(interval, damage, speed, radius, range_mult)` | | `kite_shoot` shot |
| `SummonBrood(interval, id, count)` | | `summoner` |
| `CastHazard(radius, dps, duration, tick)` | | `fsm_warlock` hazard |
| `GroundSlam / Charge / Blink / Explode` | per-attack | `brute` / `fsm_charger` / `fsm_teleporter` / `exploder` |

### Migration map (old → new)

| today | becomes |
|---|---|
| `_toward` | `SeekTarget(via="straight")` |
| `_approach` | `SeekTarget(via="nav")` (internal straight fallback) |
| `_separation` / `_obstacle_avoid` / `_unstick` / inline slew | `Separation` / `AvoidObstacles` / `Unstick` components / `SeekTarget(slew=)` |
| `_fsm_common` + `on_attack_start/tick` | `TelegraphAttack` component + machine states |
| `enemy.ai["fs"/"ft"/"cd"/"nav_head"/"stuck_at"/…]` | `bb.slot(component.key)[...]` |
| `EnemyContext` (11 fields) | `Perception` + `Combat` protocols |
| `_SLEW_RATE`, `_SEP_MAX`, `_STUCK_SECONDS`, … module consts | component dataclass defaults, per-enemy override via `cfg` |
| `BEHAVIORS` dict | `registry` (`@behavior` + `build_behavior`) |
| `Boss` bespoke FSM + its own `_approach` | `behaviors/boss.py` machine on shared components |

### What changes outside the package

- `entities/enemy.py`: keeps stats; gains `self.ai = build_behavior(cfg["behavior"], cfg)` and `self.bb = Blackboard()`. `update()` → `ai.tick(self, per, cmb)` then the existing integrate / status / knockback / anim block.
- `entities/boss.py`: shrinks to stats + `behaviors/boss.py`.
- `game/states/playing_state.py`: build the `Perception`/`Combat` adapter once; enemy loop becomes `for a in enemies + [boss]: a.ai.tick(a, per, cmb)`. Still owns `NavField`, the spatial grids, and (later) a separate crowd-collision pass.
- `data/enemies.json`: shape unchanged — `"behavior": "<name>"` + the same param keys, now each flowing into a component.

---

## Milestones

Each milestone ends with the full suite green. The old `enemy_ai.py` path stays
live and untouched until **R6**; new code is added alongside and only wired in at
**R5**.

- **R1 — scaffold.** `entities/ai/` package: `Perception` / `Combat` / `Actor`
  protocols, `Blackboard`, `Steering`, `Component` / `Transition` / `Behavior`,
  `registry`. No components, no game wiring. Tests prove they compose (a 1-state
  and a 2-state demo machine, per-actor state isolation, registry).
- **R2 — steering components.** `SeekTarget`, `Flee`, `MaintainRange`,
  `Separation`, `AvoidObstacles`, `Unstick`. Each a dataclass with defaults
  ported from the current `_UPPER` constants; unit-tested against fake
  `Perception`s. Parity checks vs the current helpers where they overlap.
- **R3 — port the simple behaviours.** `behaviors/simple.py` builds `"chase"`,
  `"path_chase"`, `"swarm"` from R2 components; registry entries. Not yet used by
  `Enemy`. Test: `build_behavior("path_chase", cfg).tick(...)` reproduces the
  current chaser motion within tolerance.
- **R4 — machine + attack/timing components.** `Cooldown`, `ProximityTrigger`,
  `Interval`, `TelegraphAttack`, `FireProjectile`, `SummonBrood`, `CastHazard`,
  `GroundSlam` / `Charge` / `Blink` / `Explode`.
- **R5 — port the rest + wire it in.** `behaviors/ranged.py` / `melee.py` /
  `boss.py`. `Enemy` / `Boss` switch to `build_behavior` + `Blackboard`;
  `PlayingState` builds the `Perception`/`Combat` adapter and the unified loop.
  `config.ENEMY_AI_V2` (default on) gates it for one milestone.
- **R6 — delete the old path.** Remove `entities/enemy_ai.py`'s `BEHAVIORS`,
  behaviour fns, `_fsm_common`, `EnemyContext`, module constants; keep only what
  still has callers (or move it). Drop the `ENEMY_AI_V2` flag. Fold the pending
  `push_radius` crowd-collision pass in as its own system if desired.

---

## R1 — scaffold  ✅ (suite 528 → 544)

`entities/ai/` package created; **no game wiring, `entities/enemy_ai.py` untouched**.

| file | contents |
|---|---|
| `context.py` | `Perception` (dt, now, player_pos, player, rng + `nav_dir` / `neighbors` / `obstacles_near` / `is_walkable` / `resolve_movement`) and `Combat` (`fire_projectile` / `summon` / `explosion` / `spawn_hazard` / `report_damage`) `Protocol`s |
| `actor.py` | `Actor` protocol -- `pos, vel, radius, speed, alive, contact_damage, facing, bb` |
| `blackboard.py` | `Blackboard.slot(key) -> dict` (created empty on first touch), `clear()`, `__contains__` |
| `steering.py` | `Steering.add(vec, weight)`, `set_velocity(vec)` (absolute override), `resolve(speed)` = Σ forces → normalize → `* speed`, or the override, or zero (empty state ⇒ rooted); `is_empty` |
| `machine.py` | `Component` base (`key` set by `Behavior`, `tick(actor, per, cmb, acc)`); `Transition(frm, to, when)` frozen dataclass; `Behavior(states, transitions, initial)` -- stateless/shared, per-actor state in `bb.slot("__machine__")` (`state`, `entered`); `state_of` / `time_in_state` / `set_state` / `tick` (run active state's components → `resolve` → check transitions) |
| `registry.py` | `@behavior(name)` decorator, `build_behavior(name, cfg)` (raises `KeyError` listing registered names), `registered()` |
| `__init__.py` | re-exports the public surface |

Design points settled here:
- **A behaviour is always a state machine.** A plain chaser is `{"move":[...]}`;
  an empty state list roots the actor (`vel` = 0), which covers "telegraph".
- **Behaviours are immutable and shared** across all enemies of a type; every
  mutable byte lives on `actor.bb`. Component instances hold config only.
- **Component keys** are assigned by `Behavior` as `"{state}#{i}:{ClassName}"` --
  unique within a behaviour, so `bb.slot(self.key)` can never collide.
- **Transitions fire after** the active state ticks, so the frame a transition
  happens still shows the old state's motion (matches the current FSM feel).
- `set_velocity` is the escape hatch for dashes / blinks (absolute, bypasses the
  force blend).

Tests: `tests/test_ai_scaffold.py` (16) -- blackboard isolation; steering sum /
weight / override / empty; single-state run, empty-state root, per-actor state
isolation, `time_in_state` reset on transition, transition-after-tick ordering,
construction guards; registry build/cfg/unknown/double-register.

## R2 — steering components  (next)
