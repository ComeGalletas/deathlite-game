"""The crowd stress harness: how long does a frame take with the spawn
master's worst plausible population?

Spawn master S7. Builds a real dev run, seats `--live` enemies in the
active zone through the master's own placement, banks `--dormant` records
in the other islands, then runs `--frames` frames of `PlayingState.update`
with the hero jittering (so the flow field's drift trigger fires as it
would in play) and reports the update time's p50 / p90 / p99 / max.

    python -m tools.benchmarks.spawn_stress                         # 100 live, 400 dormant, 1200 frames
    python -m tools.benchmarks.spawn_stress --live 200 --lod 2      # a heavier crowd, half-rate LOD
    python -m tools.benchmarks.spawn_stress --render                # time the draw as well
    python -m tools.benchmarks.spawn_stress --profile               # cProfile's top entries too
    python -m tools.benchmarks.spawn_stress --cascade --render      # CMB-008: a staged reaction cascade
    python -m tools.benchmarks.spawn_stress --pack --bump           # RND-008: the bump pass alone

What it measures is play, not the run's opening (RND-008.D3):

* The opening hints are dismissed. The hero only jitters, by up to 24 px,
  and the Move hint waits for 96 px (`config.HINT_MOVE_DISTANCE`), so a
  kept hint never clears and every frame paid for it: about 17 ms of
  draw on the owner's machine, which the first findings report read as
  the cost of the resolution. `--hints` keeps them, whatever the Options
  "Tutorials" row says.
* The master stays frozen through the timing, with the company it had in
  flight dropped, so the director adds no one. Before RND-008 it was
  unfrozen once the crowd was seated and the director kept adding
  companies (60 asked became 79); `--live-director` is that behaviour, and
  what the numbers in `journals/spawn_master_journal.md` and the
  `game/config.py` notes were taken with. The crowd still moves: the
  despawn ring may put a few seated bodies to sleep during the warm-up,
  and enemy summons arrive while timing (they are behaviour, not the
  director). Every run prints the crowd at the start of timing and what
  arrived, by owner.
* One budget, `BUDGET_MS`, counts the frames over it.

Every run prints the display it drew into: surface, driver, vsync, render
scale and zoom, so two runs can be told apart.

Headless by default: the dummy SDL drivers are set before pygame is
imported, so this runs anywhere the tests do. `SDL_VIDEODRIVER=windows`
draws into the real window at its saved size. Numbers land in the
journals, not in a test -- a timing assertion in the suite would only
ever be flaky.
"""
from __future__ import annotations

import argparse
import os
import time
from collections import Counter

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# The frame budget: one 60 Hz vsync period. The game caps itself at
# `config.FPS` (62, 16.13 ms) but presents on vsync, so on a 60 Hz display a
# frame has 16.7 ms. pygame 2.5 cannot read the refresh rate, so this is the
# owner's display, fixed (RND-008.D3). The cap's figure is printed beside it.
BUDGET_MS = 1000.0 / 60.0

# Where `bump_times` parks the hero: far outside every broad-phase query, so
# the pass measured is enemy against enemy only.
_HERO_OFFSIDE = 1.0e6


def _percentile(sorted_vals: list, q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def _force_hints(ps) -> None:
    """The run's opening hints, as if the Options "Tutorials" row were on.
    The setting is flipped in memory only while `RunHints` reads it, and
    nothing is persisted."""
    from game.states.playing.core.hints import RunHints

    settings = ps.game.save.settings
    had = settings.get("tutorials", True)
    settings["tutorials"] = True
    try:
        ps.hints = RunHints(ps)
    finally:
        settings["tutorials"] = had


def build(seed: int, live: int, dormant: int, elapsed: float, lod: int, *,
          hints: bool = False, live_director: bool = False,
          save_path: str | None = None):
    """A dev run at `elapsed` seconds with the population asked for.

    `hints=False` dismisses the run's opening hints, as a player's first
    few steps do; `hints=True` shows them even with the Options
    "Tutorials" row off. `live_director=False` keeps the master frozen
    after the crowd is seated, so the director adds nothing while the
    frames are timed (see the module doc). `save_path` is the save the
    `Game` reads; the tests pass a fresh one, so the owner's settings
    cannot reach them."""
    import pygame
    from game import config
    from game.game import Game
    from game.states.loading_state import LoadingState
    from spawn.population import DormantEnemy
    from tests.boot import settle

    game = Game(save_path=save_path)
    game.state_machine.change(LoadingState(game), seed=seed, dev=True)
    ps = settle(game)
    if not hints:
        ps.hints.dismiss()
    elif not ps.hints.visible:
        _force_hints(ps)
    ps.player.invulnerable = True
    ps._dev_no_attack = True                     # the crowd survives the run
    ps.stats["time"] = elapsed
    m = ps.spawn.master
    m.frozen = True                              # the population is ours to set
    if not live_director:
        # A frozen master still lands a company it has paid for, and one
        # in flight counts as live against the cap while the crowd is
        # seated. Neither is the crowd asked for.
        m.drop_pending()
    m.update(0.0)                                # settle the zone
    config.ENEMY_LOD_SKIP = lod
    # Every body the master could field, from the resolved roster. This read
    # `phase_at(0.5)["types"]` until G3 deleted the phase schedule; the group
    # model's equivalent of "what a mid-run crowd is made of" is the roster,
    # elites included -- which also keeps the big radii in the mix.
    ids = sorted({eid for g in m.roster.groups.values()
                  for eid in (*g.commons, *g.elites)})
    # Live bodies, seated on the zone's own spawn points with a spread.
    # They used to go through `m.spawn_at` with no position, which is
    # placement's job -- and placement's 3 s point cooldown meant a tight
    # loop got a few dozen bodies and refusals after that, so the harness
    # silently measured a third of the crowd it was asked for. Placement
    # has its own tests; this is a population builder.
    import random as _random
    rng = _random.Random(seed)
    pts = ps.game_map.layout.spawn_points
    zone = [p for p in pts if p.room_id in m.active] or list(pts)
    i = 0
    while len(ps.enemies) < live and i < live * 20:
        p = zone[i % len(zone)]
        eid = ids[i % len(ids)]
        i += 1
        spot = pygame.Vector2(p.x + rng.uniform(-60, 60), p.y + rng.uniform(-60, 60))
        if ps.game_map.is_walkable(spot, ps.content.enemy(eid)["radius"]):
            m.spawn_at(eid, spot, owner="stress")
    # Dormant records: banked directly, spread over the other islands.
    lay = ps.game_map.layout
    others = [r for r in lay.rooms if r.id not in m.active] or lay.rooms
    for k in range(dormant):
        room = others[k % len(others)]
        c = room.center
        rec = DormantEnemy(ids[k % len(ids)], c.x + (k % 7) * 40, c.y + (k // 7 % 5) * 40,
                           10.0, 10.0, 0.0, 90.0, owner="stress", room_id=room.id)
        m.population.dormant.setdefault(room.id, []).append(rec)
    m.frozen = not live_director
    return game, ps


def infuse(ps, seed: int) -> None:
    """The elemental system at its worst plausible load (design §9,
    §11 stress test): three infused weapons firing into the crowd, and
    every enemy already primed so that *every* hit lands on an aura and
    sets off a reaction.

    Priming is the pessimistic part. In play an aura has to be applied
    before it can be consumed, and the global cooldown spaces the
    reactions out; here the crowd starts saturated, which is the shape
    of a late-run fight rather than an average one.
    """
    import random

    from combat.elements.ids import ELEMENTS, ElementId
    from combat.weapons import Weapon

    # Thunder into Fire auras is the expensive pair: a chain that sets
    # off an Overload at every node it reaches.
    loadout = (("magic_rod", ElementId.THUNDER), ("bow", ElementId.WIND),
               ("sword", ElementId.FIRE))
    ps.player.weapons.clear()
    for wid, element in loadout:
        weapon = Weapon(wid, ps.content.weapon(wid))
        weapon.element = element
        ps.player.weapons.append(weapon)
        ps.run.unlocked_elements.add(element)
    ps._dev_no_attack = False                    # the weapons must fire
    ps.player.invulnerable = True
    now = ps.stats["time"]
    rng = random.Random(seed)
    for enemy in ps.enemies:
        enemy.elemental.set_aura(rng.choice(ELEMENTS), now, 600.0)
        enemy.max_hp = enemy.hp = 1e9            # nothing dies, nothing respawns


def cascade_setup(ps, radius: float = 220.0, prime: bool = True) -> None:
    """CMB-008: stage the reaction cascade on purpose (after `infuse`).

    The live crowd is packed into a disc of `radius` px round the hero --
    inside a tornado's reach and a Superconduct jump's -- and primed with
    the four elements in turn, so neighbours hold *different* auras. Any
    aura a reaction spreads (a Wind reaction's tornado, a Superconduct
    tree) then lands on a body holding another element and sets off the
    next reaction, which is the chain the R38 rework made possible.

    `prime=False` packs the crowd the same way and primes nothing -- the
    `--pack` control, so what crowding costs on its own can be told apart
    from what the cascade costs.
    """
    import math
    import random

    from combat.elements.ids import ELEMENTS

    rng = random.Random(7)
    home = ps.player.pos
    now = ps.stats["time"]
    placed = 0
    for i, enemy in enumerate(ps.enemies):
        for _try in range(40):
            a = rng.uniform(0.0, math.tau)
            d = radius * math.sqrt(rng.random())
            x, y = home.x + math.cos(a) * d, home.y + math.sin(a) * d
            if ps.game_map.is_walkable(type(home)(x, y), enemy.radius):
                enemy.pos.update(x, y)
                placed += 1
                break
        if prime:
            enemy.elemental.set_aura(ELEMENTS[i % len(ELEMENTS)], now, 600.0)
    ps._cascade_placed = placed


class Instruments:
    """Per-frame readings for the CMB-008 cascade measurement, taken by
    wrapping -- nothing in the game is changed to be measured.

    * the resolver gets a large `ReactionLog`, for the cascade-depth
      histogram;
    * the damage-number pool's `add` / `add_label` are wrapped to count
      what they refused: element numbers ask `low_priority` and yield the
      pool's top quarter; weapon numbers and reaction labels do not.
    """

    def __init__(self, ps) -> None:
        from combat.elements.reaction_log import ReactionLog

        self.ps = ps
        self.reactions, self.backlog, self.refused, self.numbers = [], [], [], []
        self.asked = {"low": 0, "high": 0, "label": 0}
        self.dropped = {"low": 0, "high": 0, "label": 0}
        ps.run.elements.log = ReactionLog(1_000_000)
        pool = ps.run.damage_numbers
        add, add_label = pool.add, pool.add_label

        def counted_add(*a, low_priority=False, **k):
            key = "low" if low_priority else "high"
            before = len(pool)
            add(*a, low_priority=low_priority, **k)
            self.asked[key] += 1
            self.dropped[key] += len(pool) == before

        def counted_label(*a, **k):
            before = len(pool)
            add_label(*a, **k)
            self.asked["label"] += 1
            self.dropped["label"] += len(pool) == before

        pool.add, pool.add_label = counted_add, counted_label

    def frame(self) -> None:
        run = self.ps.run
        el = run.elements
        self.reactions.append(el.stats.reactions_this_frame)
        self.backlog.append(el.pending)
        vis = run.element_visuals
        self.refused.append(vis.budget.refused if vis else 0)
        self.numbers.append(len(run.damage_numbers))

    def report(self) -> str:
        from collections import Counter

        from game import config

        el = self.ps.run.elements
        cap = el.registry.global_cfg.max_reactions_per_frame
        r = sorted(self.reactions)
        at_cap = sum(1 for x in self.reactions if x >= cap)
        n = len(self.backlog)
        q = max(1, n // 4)
        early = sum(self.backlog[:q]) / q
        late = sum(self.backlog[-q:]) / q
        depth = Counter(e.depth for e in el.log.newest())
        depth_txt = "  ".join(f"d{k} {v}" for k, v in sorted(depth.items())) or "none"
        pool = config.MAX_DAMAGE_NUMBERS
        drops = "  ".join(
            f"{k} {self.dropped[k]}/{self.asked[k]}" for k in ("high", "label", "low"))
        return (
            f"  cascade   placed {getattr(self.ps, '_cascade_placed', '-')}  "
            f"reactions/frame p50 {_percentile(r, 0.5)} p99 {_percentile(r, 0.99)} "
            f"max {r[-1] if r else 0}  at cap {cap}: {at_cap}/{len(r)}\n"
            f"            backlog mean first quarter {early:.1f}  last quarter "
            f"{late:.1f}  max {max(self.backlog, default=0)}  "
            f"(draining if the last is not above the first)\n"
            f"            depth {depth_txt}\n"
            f"            particles refused/frame p50 "
            f"{_percentile(sorted(self.refused), 0.5)} max {max(self.refused, default=0)}\n"
            f"            damage numbers peak {max(self.numbers, default=0)}/{pool}  "
            f"refused (dropped/asked): {drops}")


def element_report(ps) -> str:
    from game import config

    peak = getattr(ps, "_numbers_peak", 0)
    cap = config.MAX_DAMAGE_NUMBERS
    run = ps.run
    el = run.elements
    vis = run.element_visuals
    now = run.stats["time"]
    budget = vis.budget.report() if vis else "n/a"
    return (f"  elements  auras {el.active_auras(run.enemies, now)}  "
            f"reactions {el.stats.reactions_total} "
            f"({el.stats.deferred_total} deferred, {el.pending} held)  "
            f"areas {len(run.wind_areas)}  fx {len(run.element_fx)}\n"
            f"            particles {len(run.particles)}  budget {budget}\n"
            f"            damage numbers peak {peak} / {cap} "
            f"({peak / cap:.0%} of the pool)")


def element_pump(ps, per_frame: int, seed: int = 3):
    """A callable that resolves `per_frame` element-carrying hits a
    frame, straight through the resolver.

    The weapons' own cadence is nowhere near the load the design asks
    this test for -- three infused weapons on their cooldowns land
    under two hits a second between them. This drives the elemental
    system at a rate no build could reach, which is the point: it
    measures the system rather than the weapons in front of it.
    """
    import random

    from combat.elements.ids import ELEMENTS

    rng = random.Random(seed)
    weapons = ("magic_rod", "bow", "sword")

    def pump() -> None:
        bodies = ps.enemies
        if not bodies:
            return
        now = ps.stats["time"]
        for _ in range(per_frame):
            target = bodies[rng.randrange(len(bodies))]
            ps.run.elements.apply(
                target, rng.choice(ELEMENTS),
                weapon_id=rng.choice(weapons), hit_damage=40.0, now=now)

    return pump


def run(ps, frames: int, jitter: float = 24.0, dt: float = 1 / 60,
        render: bool = False, pump=None, instruments=None) -> tuple:
    """Frame times in milliseconds for `frames` updates with the hero
    jittering by up to `jitter` px each frame.

    With `render`, `ps.draw` is timed too and returned separately. That
    matters since the despawn ring landed: it makes "the whole live
    population packed within `despawn_radius` of the hero" the normal case
    rather than the pessimistic one, and draw cost scales with bodies *in
    view* where update cost scales with bodies alive.
    """
    import random
    import pygame
    rng = random.Random(1)
    home = pygame.Vector2(ps.player.pos)
    surface = pygame.display.get_surface()
    if render and surface is None:
        surface = pygame.Surface((1280, 720)).convert_alpha()
    times, draws, in_view = [], [], []
    for _ in range(frames):
        ps.player.pos.update(home.x + rng.uniform(-jitter, jitter),
                             home.y + rng.uniform(-jitter, jitter))
        t0 = time.perf_counter()
        ps.update(dt)
        if pump is not None:
            pump()
        times.append((time.perf_counter() - t0) * 1000.0)
        if instruments is not None:
            instruments.frame()
        # M11: elemental damage numbers outlive a weapon's, so the floating
        # number pool is the thing that could saturate. A full pool drops
        # whatever asks next -- possibly the weapon's own number, the one
        # that matters more -- so the peak decides how long "a bit longer"
        # is allowed to be.
        ps._numbers_peak = max(getattr(ps, "_numbers_peak", 0),
                               len(ps.run.damage_numbers))
        if render:
            view = ps.camera.visible_rect()
            in_view.append(sum(1 for e in ps.enemies
                               if view.collidepoint(e.pos.x, e.pos.y)))
            t1 = time.perf_counter()
            ps.draw(surface)
            draws.append((time.perf_counter() - t1) * 1000.0)
    return times, draws, in_view


def report(times: list, ps) -> str:
    s = sorted(times)
    m = ps.spawn.master
    return (f"frames {len(s)}: p50 {_percentile(s, 0.5):.2f}  p90 {_percentile(s, 0.9):.2f}  "
            f"p99 {_percentile(s, 0.99):.2f}  max {s[-1]:.2f} ms  |  live {len(ps.enemies)} "
            f"dormant {m.population.total_dormant} recycled {m.recycled}")


def over_budget(frame_times: list) -> int:
    """How many of `frame_times` (ms) miss `BUDGET_MS`."""
    return sum(1 for x in frame_times if x > BUDGET_MS)


def arrivals(ps, before: list) -> Counter:
    """The bodies live now that were not in `before`, counted by spawn
    owner: `summon` for an enemy's summons, `director` for a company, the
    record's own owner for a body the ring woke or the watchdog rebuilt.

    `before` is the list of the bodies themselves, not their `id()`s: the
    list keeps them alive, so a body freed during the timing cannot hand
    its address to a newcomer and hide it."""
    owner_of = ps.spawn.master.host.owner_of
    seen = {id(e) for e in before}
    return Counter(owner_of(e) for e in ps.enemies if id(e) not in seen)


def arrivals_line(ps, before: list) -> str:
    """The crowd at the start of the timed frames and what joined it."""
    came = arrivals(ps, before)
    joined = "  ".join(f"{k} {v}" for k, v in sorted(came.items())) or "none"
    return (f"  crowd     {len(before)} at the start of timing, "
            f"{len(ps.enemies)} at the end  |  arrived: {joined}")


def display_line(ps) -> str:
    """What the frames were drawn into, and under which harness settings."""
    import pygame
    from game import config

    surface = pygame.display.get_surface()
    size = "x".join(map(str, surface.get_size())) if surface is not None else "none"
    try:
        driver = pygame.display.get_driver()
    except pygame.error:
        driver = "none"
    game = ps.game
    return (f"display {size} ({driver}, vsync {'on' if game.vsync else 'off'})  "
            f"render scale {config.RENDER_SCALE:.3f} zoom {config.effective_zoom():.3f}  |  "
            f"hints {'on' if ps.hints.visible else 'off'}  "
            f"director {'frozen' if ps.spawn.master.frozen else 'live'}  |  "
            f"budget {BUDGET_MS:.2f} ms (60 Hz vsync; the {config.FPS} fps cap is "
            f"{1000.0 / config.FPS:.2f} ms)")


def bump_times(ps, frames: int) -> list:
    """`BumpResolver.resolve` alone, `frames` times, in milliseconds.

    The report's isolated bump test (RND-008.2): nothing updates, so every
    pass sees the same positions, and the hero is parked out of reach so
    only enemy-against-enemy pairs are met. The impulses a pass adds are
    put back after it, outside the timer: left to pile up, they push
    bodies past the ice slide's speed and every later pass takes the
    frozen-contact branch no real frame takes. The hero goes back at the
    end, so the run is left as it was found. Not for an elemental run:
    the frozen-contact rule deals damage, which is not put back (`main`
    refuses `--bump` with the element flags).
    """
    import pygame

    home = pygame.Vector2(ps.player.pos)
    knocks = [(e, pygame.Vector2(e._knock)) for e in ps.enemies]
    ps.player.pos.update(home.x + _HERO_OFFSIDE, home.y + _HERO_OFFSIDE)
    times = []
    try:
        for _ in range(frames):
            t0 = time.perf_counter()
            ps.bump.resolve()
            times.append((time.perf_counter() - t0) * 1000.0)
            for e, k in knocks:
                e._knock.update(k)
    finally:
        ps.player.pos.update(home)
        for e, k in knocks:
            e._knock.update(k)
    return times


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35)
    ap.add_argument("--live", type=int, default=100)
    ap.add_argument("--dormant", type=int, default=400)
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--elapsed", type=float, default=300.0)
    ap.add_argument("--lod", type=int, default=None,
                    help="behaviour tick divisor for out-of-aggro, off-view enemies "
                         "(default: config.ENEMY_LOD_SKIP)")
    ap.add_argument("--render", action="store_true",
                    help="time ps.draw as well, and report update + draw "
                         "together against the frame budget (BUDGET_MS)")
    ap.add_argument("--elements", action="store_true",
                    help="infuse three weapons and prime every enemy, so the "
                         "elemental system runs at its worst plausible load")
    ap.add_argument("--element-rate", type=int, default=0,
                    help="element-carrying hits resolved per frame, over "
                         "and above what the weapons land (implies "
                         "--elements)")
    ap.add_argument("--cascade", action="store_true",
                    help="CMB-008: pack the crowd round the hero and prime "
                         "neighbours with different auras so reactions "
                         "chain; reports reactions per frame, the backlog, "
                         "cascade depth and the damage-number refusals "
                         "(implies --elements)")
    ap.add_argument("--pack", action="store_true",
                    help="the --cascade crowd, packed round the hero, with no "
                         "elements at all: the control for --cascade")
    ap.add_argument("--hints", action="store_true",
                    help="keep the run's opening hints; the jittered hero "
                         "never clears them, so every frame draws them")
    ap.add_argument("--live-director", action="store_true",
                    help="let the director add companies while the frames "
                         "are timed (the behaviour before RND-008)")
    ap.add_argument("--bump", action="store_true",
                    help="time BumpResolver.resolve alone, --frames times, "
                         "with nothing moving and the hero out of reach; "
                         "add --pack for the packed crowd (not with "
                         "--render, --profile or the element flags)")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args(argv)
    if args.frames < 1:
        ap.error("--frames must be at least 1")
    if args.bump:
        clash = [flag for flag, on in (
            ("--render", args.render), ("--profile", args.profile),
            ("--elements", args.elements), ("--element-rate", args.element_rate > 0),
            ("--cascade", args.cascade)) if on]
        if clash:
            ap.error(f"--bump times the bump pass alone; drop {', '.join(clash)}")
    from game import config
    lod = args.lod if args.lod is not None else config.ENEMY_LOD_SKIP
    game, ps = build(args.seed, args.live, args.dormant, args.elapsed, lod,
                     hints=args.hints, live_director=args.live_director)
    print(display_line(ps))
    elements = args.elements or args.element_rate > 0 or args.cascade
    pump = None
    instruments = None
    if elements:
        infuse(ps, args.seed)
        if args.element_rate > 0:
            pump = element_pump(ps, args.element_rate, args.seed)
    run(ps, 60, render=args.render, pump=pump)       # warm the caches
    if args.pack and not args.cascade:
        cascade_setup(ps, prime=False)
    if args.cascade:
        # Staged *after* the warm-up: a primed crowd spends most of its
        # auras in its first second, and that burst is the cascade this
        # measures -- warming on it would leave only the aftermath.
        cascade_setup(ps)
        instruments = Instruments(ps)
    before = list(ps.enemies)
    if args.bump:
        b = sorted(bump_times(ps, args.frames))
        print(f"seed {args.seed}  bump {len(b)} passes: p50 {_percentile(b, 0.5):.3f}  "
              f"p90 {_percentile(b, 0.9):.3f}  p99 {_percentile(b, 0.99):.3f}  "
              f"max {b[-1]:.3f} ms  |  crowd {len(before)}")
        return 0
    if args.profile:
        import cProfile
        import pstats
        prof = cProfile.Profile()
        prof.enable()
        times, draws, in_view = run(ps, args.frames, render=args.render,
                                    pump=pump, instruments=instruments)
        prof.disable()
        print(report(times, ps))
        print(arrivals_line(ps, before))
        if elements:
            print(element_report(ps))
        if instruments is not None:
            print(instruments.report())
        pstats.Stats(prof).sort_stats("cumulative").print_stats(28)
    else:
        times, draws, in_view = run(ps, args.frames, render=args.render,
                                    pump=pump, instruments=instruments)
        print(f"seed {args.seed} lod {lod}  " + report(times, ps))
        print(arrivals_line(ps, before))
        if elements:
            print(element_report(ps))
        if instruments is not None:
            print(instruments.report())
        if args.render:
            d, v = sorted(draws), sorted(in_view)
            print(f"  draw   p50 {_percentile(d, 0.5):.2f}  "
                  f"p90 {_percentile(d, 0.9):.2f}  p99 {_percentile(d, 0.99):.2f}  "
                  f"max {d[-1]:.2f} ms  |  in view p50 {_percentile(v, 0.5)} "
                  f"max {v[-1]}")
            both = sorted(a + b for a, b in zip(times, draws))
            print(f"  update + draw   p50 {_percentile(both, 0.5):.2f}  "
                  f"p90 {_percentile(both, 0.9):.2f}  p99 {_percentile(both, 0.99):.2f}  "
                  f"max {both[-1]:.2f} ms  |  over {BUDGET_MS:.2f} ms: "
                  f"{over_budget(both)} / {len(both)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
