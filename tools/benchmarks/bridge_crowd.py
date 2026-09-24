"""The bridge-crowd bench: how well does a pack file across a bridge?

ENT-016. A bridge deck is one tile wide, so a pack arriving at a mouth has to
file through it, and every overlap it makes on the way is shoved back apart
by the bump pass (`game/states/playing/core/physics.py`). This bench measures
that at several crowd push radii (`config.CROWD_PUSH_RADIUS_FRAC`):

* one dev run per pinned seed; on each of its first `--bridges` bridges the
  field is cleared, the hero stands `HERO_IN` px past the far mouth (still,
  invulnerable, not attacking), and a mixed pack of `--pack` bodies -- the
  small, the middling and the big ones -- is set on the near side, kept
  provoked so it keeps hunting;
* `--seconds` of play per fraction, from the same start every time;
* per trial: how many crossed (a body is across once it is past the far
  mouth), when half of them had, and how many were still on the near side
  and had barely moved over the last five seconds (stuck).

    python -m tools.benchmarks.bridge_crowd
    python -m tools.benchmarks.bridge_crowd --fracs 1.0 0.6 --seconds 30

Headless, and a rate rather than a pinned outcome: the table lands in
`journals/enemy_ai_journal.md` (ENT-016); `tests/playing/test_bridge_crowd.py`
runs one small case.
"""
from __future__ import annotations

import argparse
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

SEEDS = (35, 7, 42)
# The pack: small, middling and big bodies (radius 10 -> 24), in that order
# of the list so a short `--pack` still mixes them.
MIX = ("skull", "bear", "spider", "panda", "turtle", "spear_goblin")
HERO_IN = 160.0        # px past the far mouth the hero stands
PACK_BACK = (60.0, 320.0)   # px behind the near mouth the pack is seated within
STUCK_WINDOW = 5.0     # s: a body that moved less than STUCK_PX over it...
STUCK_PX = 24.0        # ...and is not across is stuck


def boot(seed: int):
    from game.game import Game
    from game.states.loading_state import LoadingState
    from tests.boot import settle

    game = Game()
    game.state_machine.change(LoadingState(game), seed=seed, dev=True)
    ps = settle(game)
    ps.player.invulnerable = True
    ps._dev_no_attack = True
    m = ps.spawn.master
    m.frozen = True                          # the population is ours to set
    # The zone pass runs before the `frozen` gate: it would sleep a pack on
    # the island the hero has left (the one it is crossing *from*) and wake
    # records round the hero. And the watchdog recycles a body it judges
    # stuck -- which in play hides a jam at a mouth, and here would hide the
    # very thing measured. Both off: the bench sees the crowd as it moves.
    m.use_locality = False
    m.watchdog.update = lambda host, now: ()
    # No XP: a level-up would push its offering over the run and pause it,
    # freezing this trial and every one after it (it did, on seed 42).
    ps.run.levels.add_xp = lambda amount: 0
    return game, ps


def bridge_geometry(gm, corridor):
    """`(axis, sign, near, far)` for a corridor: the axis it runs along (0 = x,
    1 = y), the direction from `a`'s end to `b`'s, and the two mouths' centre
    points."""
    import pygame
    r = corridor.rect
    axis = 0 if r.width > r.height else 1
    rooms = {room.id: room for room in gm.layout.rooms}
    ca = rooms[corridor.a].rect.center
    if axis == 0:
        ends = (pygame.Vector2(r.left, r.centery), pygame.Vector2(r.right, r.centery))
    else:
        ends = (pygame.Vector2(r.centerx, r.top), pygame.Vector2(r.centerx, r.bottom))
    near, far = sorted(ends, key=lambda e: (e - pygame.Vector2(ca)).length())
    sign = 1 if (far - near)[axis] > 0 else -1
    return axis, sign, near, far


def _walkable_near(gm, p, radius, rng, spread=48.0, tries=200):
    import pygame
    for _ in range(tries):
        q = pygame.Vector2(p.x + rng.uniform(-spread, spread),
                           p.y + rng.uniform(-spread, spread))
        if gm.is_walkable(q, radius):
            return q
    return None


def setup_trial(ps, corridor, pack: int, seed: int):
    """Clear the field, stand the hero, seat the pack. Returns the pack's
    bodies and the crossing test, or None when the bridge has no room."""
    import pygame
    from entities.ai.components.aggro import provoke

    gm, run = ps.game_map, ps.run
    axis, sign, near, far = bridge_geometry(gm, corridor)
    rng = random.Random(seed * 1000 + corridor.a * 31 + corridor.b)
    unit = pygame.Vector2(1, 0) if axis == 0 else pygame.Vector2(0, 1)
    hero = _walkable_near(gm, far + unit * sign * HERO_IN, float(run.player.radius), rng)
    if hero is None:
        return None
    run.enemies.clear()
    run.player.pos.update(hero)
    # Candidate spots: a grid over the half-disc behind the near mouth,
    # `PACK_BACK` deep, nearest first, so the pack sits on whatever ground
    # the island has there (a beach can be a few tiles deep, or one).
    cands = []
    step = 20.0
    lo, hi = PACK_BACK
    k = int(hi // step)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            off = pygame.Vector2(i * step, j * step)
            d = off.length()
            if lo * 0.5 <= d <= hi and off.dot(unit * sign) < -lo * 0.5:
                cands.append(near + off)
    rng.shuffle(cands)
    cands.sort(key=lambda p: round((p - near).length() / 40.0))
    bodies, taken = [], []
    for i in range(pack):
        eid = MIX[i % len(MIX)]
        radius = float(ps.content.enemy(eid)["radius"])
        spot = next((p for p in cands
                     if gm.is_walkable(p, radius)
                     and all((p - q).length() >= radius + rq for q, rq in taken)), None)
        if spot is None:
            continue
        taken.append((spot, radius))
        ps._spawn_enemy(eid, at=spot, owner="bench")
        e = run.enemies[-1]
        provoke(e)
        bodies.append(e)
    if len(bodies) < pack // 2:
        return None
    line = far[axis]

    def across(e) -> bool:
        return (e.pos[axis] - line) * sign > 0

    return bodies, across


def trial(game, ps, corridor, pack: int, seconds: float, seed: int, frac: float):
    from entities.ai.components.aggro import provoke
    from game import config

    config.CROWD_PUSH_RADIUS_FRAC = frac
    got = setup_trial(ps, corridor, pack, seed)
    if got is None:
        return None
    bodies, across = got
    dt, frames = 1 / 60, int(seconds * 60)
    window = int(STUCK_WINDOW * 60)
    trail = {id(e): [] for e in bodies}
    t_half = None
    for f in range(frames):
        for e in bodies:
            if e.alive:
                provoke(e)                     # keep hunting across the water
        game.state_machine.update(dt)
        assert game.state_machine.current is ps, "an overlay paused the run"
        n = sum(1 for e in bodies if e.alive and across(e))
        if t_half is None and n * 2 >= len(bodies):
            t_half = (f + 1) * dt
        for e in bodies:
            trail[id(e)].append(e.pos.copy())
    crossed = sum(1 for e in bodies if e.alive and across(e))
    stuck = 0
    for e in bodies:
        tr = trail[id(e)]
        if e.alive and not across(e) and len(tr) > window \
                and (tr[-1] - tr[-1 - window]).length() < STUCK_PX:
            stuck += 1
    return {"pack": len(bodies), "crossed": crossed, "t_half": t_half, "stuck": stuck}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    ap.add_argument("--fracs", type=float, nargs="+", default=[1.0, 0.75, 0.6, 0.45])
    ap.add_argument("--bridges", type=int, default=2)
    ap.add_argument("--pack", type=int, default=24)
    ap.add_argument("--seconds", type=float, default=25.0)
    args = ap.parse_args(argv)

    from game import config
    keep = config.CROWD_PUSH_RADIUS_FRAC
    totals = {f: {"pack": 0, "crossed": 0, "stuck": 0, "halves": []} for f in args.fracs}
    print(f"{'seed':>4} {'bridge':>7} " + " ".join(f"{f:>16}" for f in args.fracs))
    for seed in args.seeds:
        game, ps = boot(seed)
        done = 0
        for c in ps.game_map.layout.corridors:
            if done >= args.bridges:
                break
            row = []
            for f in args.fracs:
                r = trial(game, ps, c, args.pack, args.seconds, seed, f)
                if r is None:
                    break
                row.append(r)
                t = totals[f]
                t["pack"] += r["pack"]
                t["crossed"] += r["crossed"]
                t["stuck"] += r["stuck"]
                t["halves"].append(r["t_half"])
            if len(row) != len(args.fracs):
                continue
            done += 1
            cells = [f"{r['crossed']:>2}/{r['pack']:<2} "
                     f"{'-' if r['t_half'] is None else format(r['t_half'], '4.1f')}s "
                     f"st{r['stuck']:<2}" for r in row]
            print(f"{seed:>4} {c.a:>3}-{c.b:<3} " + " ".join(f"{x:>16}" for x in cells))
    config.CROWD_PUSH_RADIUS_FRAC = keep
    print()
    for f, t in totals.items():
        halves = [h for h in t["halves"] if h is not None]
        med = sorted(halves)[len(halves) // 2] if halves else None
        print(f"frac {f:>4}: crossed {t['crossed']}/{t['pack']} "
              f"({100 * t['crossed'] / max(1, t['pack']):.0f} %), "
              f"half across in {'-' if med is None else format(med, '.1f') + ' s'} (median, "
              f"{len(halves)}/{len(t['halves'])} trials got there), stuck {t['stuck']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
