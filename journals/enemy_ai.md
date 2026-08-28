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

## R2 — steering components  ✅ (suite 544 → 561)

`entities/ai/components/` -- six dataclasses, each ticked against a `Perception`,
defaults copied verbatim from `entities/enemy_ai.py`. **Still no game wiring.**

| component | params (default) | ports |
|---|---|---|
| `SeekTarget` | `via="nav"`, `slew=9.0`, `weight=1.0` | `_toward`, `_approach`, `path_chase` heading + slew. `via="nav"` reads `per.nav_dir`, straight-line fallback on a zero vector (so `config.ENEMY_PATHFINDING` off just means "always straight" -- `nav_enabled` disappears). `slew` state in `bb.slot(key)["heading"]`. |
| `Flee` | `weight=1.0` | the `-_toward` retreat branches |
| `MaintainRange` | `distance=240`, `band=30`, `close_via="nav"` | kiter / warlock hold logic. In-band ⇒ contributes nothing ⇒ actor roots (old `enemy.vel = 0` feel). |
| `Separation` | `radius_mult=1.6`, `cap=0.6`, `weight=1.0` | `_separation` (`per.neighbors`) |
| `AvoidObstacles` | `margin=14.0`, `cap=0.7`, `weight=1.0` | `_obstacle_avoid` (`per.obstacles_near`) |
| `Unstick` | `seconds=0.4`, `progress_frac=0.3`, `nudge_strength=1.5`, `nudge_seconds=0.35` | `_unstick`. Order it **last** -- it reads `acc.direction()` (new `Steering` method) to nudge perpendicular to the accumulated heading, so no key coupling to `SeekTarget`. |

`Steering` gained `direction()` -- unit of the running force sum (or the
`set_velocity` override's direction, or zero).

Tests: `tests/test_ai_components.py` (17) -- straight vs nav vs nav-fallback;
slew eases a turn / snaps a 180; flee/close/hold; separation close-only,
skip-self/dead, capped; obstacle push within/outside margin; unstick
progress-gate / fires-after-pinned / perpendicular / deterministic; **parity**:
`[SeekTarget(via="nav"), Separation, AvoidObstacles, Unstick]` with nav off + no
crowd + no props + not stuck resolves to exactly the old straight `chase`.

## R3 — port the simple behaviours  ✅ (suite 561 → 567)

`entities/ai/behaviors/simple.py` -- one `move` state each, built from R2
components; registered on import (`entities/ai/behaviors/__init__` is imported by
`entities/ai/__init__`, so `build_behavior` works everywhere). **Not yet
consumed by `Enemy`.**

| name | build |
|---|---|
| `chase`, `chaser` | `{"move": [SeekTarget(via="straight", slew=0)]}` |
| `path_chase` | `{"move": [SeekTarget(via="nav"), Separation, AvoidObstacles, Unstick]}` |
| `swarm` | same as `path_chase` today -- kept as the tuning hook for the planned tighter crowd behaviour |

Every component param reads `cfg.get(key, <old default>)` (`nav_slew`,
`seek_weight`, `separation_mult/cap`, `obstacle_margin/cap`, `stuck_seconds`,
`nudge_strength`) -- absent in `enemies.json` today so behaviour is unchanged,
but a variant can now be re-tuned in data without a new behaviour.

Tests: `tests/test_ai_behaviors_simple.py` (6) -- registration + state shape;
**frame-by-frame parity**: `build_behavior("path_chase").tick(...)` matches the
old `entities.enemy_ai.path_chase` `vel` to 1e-4 over 60 frames with a live nav
route + a crowding neighbour + a prop in the margin; `chase` matches the old
straight function; `path_chase` with the field silent reduces to the same result
the old code's `nav_enabled=False` early-return gave.

## R4 — machine + attack / timing components  ✅ (suite 567 → 579)

Machine grew the FSM plumbing; the attack primitives landed. **Still no game
wiring.**

`machine.py`:
- `time_in_state(actor)` free function (predicates need it without a `Behavior`).
- `OneShot(Component)` base -- `fire(actor, per, cmb)` runs once per state entry
  (tracks the machine's `visit` counter).
- `Transition` gains `on(actor, per)` -- a side-effect fired when the transition
  takes (locks a charge direction, snapshots a cast target).
- `Behavior(always=[...])` -- components ticked every frame in any state (for
  `Cooldown`, which the old FSM decremented regardless of phase); `set_state`
  bumps `visit`.

`steering.py`: `resolve()` -- a summed force with magnitude **< 1** now yields
`|acc| * speed` (proportional), so a lone weight-0.3 `SeekTarget` gives the old
`recover` / summoner-drift speed. `>= 1` still normalizes. Verified against the
R2/R3 parity tests.

`components/timing.py`: `Cooldown(seconds, start_ready)` (`ready` / `trigger`);
`OnEnter(action)`; predicates `after`, `in_range`, `out_of_range`, `ready(cd)`,
`all_of`, `any_of`.

`components/ranged.py`: `FireProjectile(interval, damage, speed, radius,
max_range)` (kiter shot -- timer stays elapsed while out of range, fires on
re-entry, matching the old code); `SummonBrood(interval, enemy_id, count)`;
`CastHazard(radius, dps, duration, tick_interval)` (`OneShot`; target from
`bb.slot(ATTACK_SLOT)["cast_at"]`).

`components/attacks.py`: `Charge(speed, damage)` (per-frame `set_velocity` along
`bb.slot(ATTACK_SLOT)["dir"]`); `Blink(min_offset, max_offset, damage)`
(`OneShot`, seeded); `Explosion(radius, damage, require_range)` (`OneShot`, the
brute's slam); `Explode(fuse_range)` (self-destruct).

`MaintainRange` gained `close_weight` (summoner closes in at 0.4x speed).

Tests: `tests/test_ai_machine_components.py` (9) -- cooldown count/reload/
start-ready; predicates; `FireProjectile` interval + range gate; `SummonBrood`
interval; `Explode` fuse; `Blink` deterministic + lands near the player; **a full
`chase → telegraph → attack → recover` machine** wired from the pieces: cycles
all four states, rooted during telegraph, exactly one blast per attack visit.

## R5 — port the rest + wire it in  ✅ (suite 579 → 586, `ENEMY_AI_V2` on)

### Builders

`entities/ai/behaviors/_telegraph.py` `telegraph_cycle(...)` -- the shared
`chase → telegraph → attack → recover` shape from R4 pieces: `Cooldown` in
`always`, `in_range` + `ready(cd)` guard into telegraph, `after(windup)` into
attack (its `on` runs `contact_cd = 0` then the caller's one-shot), `after`s
through attack/recover, `cd.trigger` on the way back to chase; `recover` drifts
at `recover_weight * speed`.

`behaviors/ranged.py` -- `kite_shoot` (`MaintainRange` + `FireProjectile`
`max_range = prefer_distance * 1.8`), `summoner` (`MaintainRange(band=0,
close_weight=0.4)` + `SummonBrood`).

`behaviors/melee.py` -- `exploder` (`SeekTarget(nav)` + `Explode`); `brute`
(2-state, slam fires on the `telegraph → chase` transition `on`); `fsm_charger`
(`telegraph_cycle`, `on_windup_end` locks the dash dir, `attack=[Charge]`);
`fsm_teleporter` (`telegraph_cycle`, `on_windup_end` = the seeded blink, empty
`attack` state = rooted); `fsm_warlock` (`telegraph_cycle`, `on_windup_start`
snapshots `cast_at`, `on_windup_end` drops the hazard). All 8 `enemies.json`
behaviour names resolve.

`Transition.on` now takes `(actor, per, cmb)` so a transition can fire a combat
action (the brute's slam).

### Wiring

- `config.ENEMY_AI_V2 = True` (via `getattr(config, ..., True)` at the call
  sites, so it survives config churn).
- `entities/enemy.py`: `self.bb = Blackboard()`, `self._behavior =
  build_behavior(self.behavior, self.cfg)` when v2; `update()` calls
  `self._behavior.tick(self, ctx, ctx)` (the ctx satisfies `Perception` +
  `Combat`) else the legacy `BEHAVIORS` dispatch. `_attacking` / `telegraphing`
  read `bb.slot("__machine__")["state"]` under v2 so the sprite still plays the
  wind-up / strike anims.
- `game/states/playing_state.py::_enemy_context`: builds a `SimpleNamespace`
  Perception+Combat adapter when v2 (adds `now`, `is_walkable`; drops the
  `EnemyContext` type and `nav_enabled`), else the legacy `EnemyContext`. The
  **boss reads it unchanged** either way (it only touches the shared callbacks).

### Verification

- Timer-free movers (`kite_shoot` / `summoner` / `exploder`) match the old
  function **frame-by-frame** (`tests/test_ai_behaviors_fsm.py`).
- The telegraph FSMs use a different timer engine (`entered >= t` vs subtractive
  `ft`), so they drift ~1 frame on a phase boundary -- checked for behavioural
  equivalence instead: same state set, effect counts within 1, right speed per
  phase (dash = `charge_speed`, telegraph rooted, recover ~`0.3 * speed`).
- `tests/test_fsm_enemies.py` / `test_enemy_sprite.py` updated to read the v2
  machine state.
- **Full-game A/B**: 11-type crowded PlayingState sim (600 frames) -- v1 and v2
  give **byte-identical** aggregate results (11/11 close, mean 378 → 117).
- One unrelated red: `test_menu.test_palette_constants` (a concurrent
  `config.MENU_FG` edit).

## R6 — delete the old path  ✅ (suite 586 → 573; **refactor complete**)

- **`entities/enemy_ai.py` deleted** -- `BEHAVIORS`, the ten behaviour fns,
  `_fsm_common` / `_fsm_enter`, the six steering helpers, the eight `_UPPER`
  constants and `EnemyContext` all gone.
- `config.ENEMY_AI_V2` removed; `Enemy` always builds a composable behaviour.
- `entities/enemy.py`: no legacy dispatch, no `self.ai` dict, no `_ai_v2`;
  `_attacking` / `telegraphing` read only `bb.slot("__machine__")["state"]`.
- `entities/boss.py`: dropped the `EnemyContext` import; `ctx` methods are now
  bare-annotated (the runtime object is the PlayingState adapter). Boss still
  runs its own phase FSM -- a future milestone can port it onto the same
  components, but it was never in this refactor's scope.
- `game/states/playing_state.py::_enemy_context`: one code path -- the
  `SimpleNamespace` Perception+Combat adapter, handed to every enemy **and the
  boss**.
- Tests: `tests/aictx.py` (`ai_ctx()` fake) replaces `EnemyContext` in
  `test_boss` / `test_enemy_sprite` / `test_fsm_enemies` / `test_incoming_damage`
  (the `_fsm_enter` poke became "drive the machine to `attack`, assert
  `contact_cd == 0`"). `test_enemy_ai.py` slimmed to `ShieldTests` +
  `BehaviorTests` (the helper-function tests moved to `test_ai_components` /
  `test_ai_behaviors_*`); the R5 parity files became self-contained
  behaviour tests now that there is nothing to compare against.
- Full-loop smoke (900 frames, all 10 enemy types + boss): 0.91 ms/frame, no
  crash, composable AI and the boss FSM coexist on the shared adapter.
- One unrelated red throughout: `test_menu.test_palette_constants` (a
  concurrent `config.MENU_FG` edit).

---

## Status: complete (R1–R6)

`entities/ai/` is a self-contained package -- `Perception` / `Combat` protocols,
`Blackboard`, `Steering`, a `Component` + state-machine core, a `@behavior`
registry, ~15 components, 10 behaviour builders. It imports only `pygame`,
`game.config`, and `world` is untouched. A new variant that reuses components is
JSON; a new *kind* of move is one component file + one line in a builder.

### Follow-ups parked
- Port `Boss` onto the same components (its phase FSM is the last bespoke AI).
- `push_radius` enemy-vs-enemy crowd-collision pass as its own system.
- `data/behaviors.json` so behaviour *shape* is data too, not just numbers.
