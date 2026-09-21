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

Headless: the dummy SDL drivers are set before pygame is imported, so
this runs anywhere the tests do. Numbers land in
`journals/spawn_master_journal.md`, not in a test -- a timing assertion
in the suite would only ever be flaky.
"""
from __future__ import annotations

import argparse
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _percentile(sorted_vals: list, q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def build(seed: int, live: int, dormant: int, elapsed: float, lod: int):
    """A dev run at `elapsed` seconds with the population asked for."""
    import pygame
    from game import config
    from game.game import Game
    from game.states.loading_state import LoadingState
    from spawn.population import DormantEnemy
    from tests.boot import settle

    game = Game()
    game.state_machine.change(LoadingState(game), seed=seed, dev=True)
    ps = settle(game)
    ps.player.invulnerable = True
    ps._dev_no_attack = True                     # the crowd survives the run
    ps.stats["time"] = elapsed
    m = ps.spawn.master
    m.frozen = True                              # the population is ours to set
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
    m.frozen = False
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


def element_report(ps) -> str:
    run = ps.run
    el = run.elements
    vis = run.element_visuals
    now = run.stats["time"]
    budget = vis.budget.report() if vis else "n/a"
    return (f"  elements  auras {el.active_auras(run.enemies, now)}  "
            f"reactions {el.stats.reactions_total} "
            f"({el.stats.deferred_total} deferred, {el.pending} held)  "
            f"areas {len(run.wind_areas)}  fx {len(run.element_fx)}\n"
            f"            particles {len(run.particles)}  budget {budget}")


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
        render: bool = False, pump=None) -> tuple:
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
                         "together against the 16.7 ms frame budget")
    ap.add_argument("--elements", action="store_true",
                    help="infuse three weapons and prime every enemy, so the "
                         "elemental system runs at its worst plausible load")
    ap.add_argument("--element-rate", type=int, default=0,
                    help="element-carrying hits resolved per frame, over "
                         "and above what the weapons land (implies "
                         "--elements)")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args(argv)
    from game import config
    lod = args.lod if args.lod is not None else config.ENEMY_LOD_SKIP
    game, ps = build(args.seed, args.live, args.dormant, args.elapsed, lod)
    elements = args.elements or args.element_rate > 0
    pump = None
    if elements:
        infuse(ps, args.seed)
        if args.element_rate > 0:
            pump = element_pump(ps, args.element_rate, args.seed)
    run(ps, 60, render=args.render, pump=pump)       # warm the caches
    if args.profile:
        import cProfile
        import pstats
        prof = cProfile.Profile()
        prof.enable()
        times, draws, in_view = run(ps, args.frames, render=args.render,
                                    pump=pump)
        prof.disable()
        print(report(times, ps))
        if elements:
            print(element_report(ps))
        pstats.Stats(prof).sort_stats("cumulative").print_stats(28)
    else:
        times, draws, in_view = run(ps, args.frames, render=args.render,
                                    pump=pump)
        print(f"seed {args.seed} lod {lod}  " + report(times, ps))
        if elements:
            print(element_report(ps))
        if args.render:
            d, v = sorted(draws), sorted(in_view)
            print(f"  draw   p50 {_percentile(d, 0.5):.2f}  "
                  f"p90 {_percentile(d, 0.9):.2f}  p99 {_percentile(d, 0.99):.2f}  "
                  f"max {d[-1]:.2f} ms  |  in view p50 {_percentile(v, 0.5)} "
                  f"max {v[-1]}")
            both = sorted(a + b for a, b in zip(times, draws))
            over = sum(1 for x in both if x > 16.7)
            print(f"  update + draw   p50 {_percentile(both, 0.5):.2f}  "
                  f"p90 {_percentile(both, 0.9):.2f}  p99 {_percentile(both, 0.99):.2f}  "
                  f"max {both[-1]:.2f} ms  |  over 16.7 ms: {over} / {len(both)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
