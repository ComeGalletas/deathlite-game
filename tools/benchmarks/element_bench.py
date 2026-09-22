"""What is an infusion worth?

An element's damage is a fraction of the hit that carried it (the owner's
rule), but what a player actually feels is the *extra damage per second* an
infusion adds, and that depends on things no formula has: how often the
weapon inflicts, whether its chain finds neighbours, whether its tornado
catches anyone, and how often a second element is around to react with.

So this measures instead of computing. It drives a real run: one infused
weapon firing into a standing crowd on its own cooldown, through the
ordinary hit pipeline, for a fixed stretch of run time. Then it reads the
run ledger, which splits damage by effect, and reports the elemental share
as a percentage of the weapon's own.

    python -m tools.benchmarks.element_bench
    python -m tools.benchmarks.element_bench --seconds 30 --crowd 12
    python -m tools.benchmarks.element_bench --weapons sword,bow --pairs

`--pairs` infuses two weapons with different elements, which is the only
way reactions appear: a lone element never meets another one.

The yardstick to read it against is the project's own
(`blessing-yardstick-six-per-weapon`): one weapon blessing level is worth
about 15 % more output. Numbers land in the journal, not in a test -- an
assertion on damage would only ever be flaky.
"""
from __future__ import annotations

import argparse
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ELEMENT_EFFECTS = None          # filled on first use, from the tracking module
WEAPONS = ("sword", "hammer", "daggers", "bow", "magic_rod", "bomb",
           "ember_ring", "grave_totem", "spirit_wolf")


def _effects():
    global ELEMENT_EFFECTS
    if ELEMENT_EFFECTS is None:
        from combat.elements import tracking
        ELEMENT_EFFECTS = set(tracking.EFFECTS)
    return ELEMENT_EFFECTS


def build(seed: int, crowd: int, spacing: float):
    """A dev run with a standing crowd round the hero and nothing else."""
    import pygame
    from game.game import Game
    from game.states.loading_state import LoadingState
    from tests.boot import settle
    from tests.nearby import spots_near

    game = Game()
    game.state_machine.change(LoadingState(game), seed=seed, dev=True)
    ps = settle(game)
    for _ in range(30):
        game.state_machine.update(1 / 60)

    ps.player.invulnerable = True
    ps.spawn.master.frozen = True
    for e in list(ps.enemies):
        e.alive = False
    ps.enemies = []

    # Tight rings, not the helper's default (70 px and out). A melee
    # weapon's arc is 40 px wide; a crowd seated where a ranged weapon
    # is comfortable would measure the sword as doing nothing at all.
    rings = (30, 44, 58, 74, 92, 112)
    for spot in spots_near(ps, crowd, radius=14.0, rings=rings, apart=spacing):
        enemy = ps.spawn.master.spawn_at("skull", spot, owner="bench")
        if enemy is not None:
            # Standing and unkillable: this measures output, not clear speed,
            # and a crowd that thins mid-measurement measures neither.
            enemy.max_hp = enemy.hp = 1e12
            enemy.speed = 0.0
            enemy.contact_damage_enabled = False
    # Where each body belongs. Knockback and the collision separation
    # walk the crowd outwards over a measurement -- after one 10 s run
    # the ring had drifted far enough out of a 40 px melee arc that the
    # next run measured a tenth of the damage. `reset` puts them back.
    ps.bench_home = [(e, pygame.Vector2(e.pos)) for e in ps.enemies]
    ps.bench_hero = pygame.Vector2(ps.player.pos)
    return game, ps


def measure(game, ps, weapons, seconds: float):
    """Fire `weapons` for `seconds` of run time; return the ledger split."""
    from combat.weapons import Weapon

    ps.player.weapons.clear()
    for wid, element in weapons:
        weapon = Weapon(wid, ps.content.weapon(wid))
        weapon.element = element
        ps.player.weapons.append(weapon)

    ledger = ps.run.ledger
    ledger.damage.clear()
    ledger.elements.damage.clear()
    ledger.elements.reactions.clear()
    ledger.elements.applications.clear()

    for _ in range(int(seconds * 60)):
        game.state_machine.update(1 / 60)

    elemental = sum(v for (_w, effect), v in ledger.elements.damage.items()
                    if effect in _effects())
    total = ledger.total
    return {
        "weapon": total - elemental,
        "element": elemental,
        "applications": sum(ledger.elements.applications.values()),
        "reactions": sum(ledger.elements.reactions.values()),
        "by_effect": ledger.elements.damage_by_effect(),
    }


def reset(ps):
    """Put the crowd back exactly where it started, with no elemental
    state left on it, so each run measures the same fight."""
    import pygame

    ps.player.pos.update(ps.bench_hero)
    for enemy, home in ps.bench_home:
        enemy.pos.update(home)
        enemy.vel.update(0, 0)
        enemy._knock.update(0, 0)
    for enemy in ps.enemies:
        enemy.status.clear()
        enemy.elemental.clear()
        enemy.hp = enemy.max_hp
    ps.run.wind_areas.clear()
    ps.run.element_fx.clear()
    ps.run.elements.clear()
    ps.run.stats["damage_dealt"] = 0.0


def main(argv=None) -> int:
    from combat.elements.ids import ELEMENTS, ElementId

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--crowd", type=int, default=10)
    ap.add_argument("--spacing", type=float, default=26.0)
    ap.add_argument("--weapons", default="sword,bow,magic_rod,ember_ring")
    ap.add_argument("--pairs", action="store_true",
                    help="infuse two weapons with different elements, which "
                         "is the only way reactions happen")
    args = ap.parse_args(argv)

    wanted = [w.strip() for w in args.weapons.split(",") if w.strip()]
    game, ps = build(args.seed, args.crowd, args.spacing)

    print(f"\ncrowd {len(ps.enemies)}  {args.seconds:.0f}s per run  seed {args.seed}")
    print("  the yardstick: one weapon blessing level is worth about +15 %\n")

    if args.pairs:
        _pairs(game, ps, wanted)
    else:
        _solo(game, ps, wanted, ELEMENTS, ElementId, args.seconds)
    return 0


def _solo(game, ps, wanted, elements, ElementId, seconds) -> None:
    print(f"  {'weapon':<13}{'plain dps':>11}{'element':>9}"
          f"{'  +element dps':>15}{'  share':>9}{'  applied':>10}")
    print("  " + "-" * 68)
    for wid in wanted:
        reset(ps)
        base = measure(game, ps, [(wid, ElementId.NONE)], seconds)
        plain = base["weapon"] / seconds
        print(f"  {wid:<13}{plain:>11.1f}{'-':>9}{'-':>15}{'-':>9}{'-':>10}")
        for element in elements:
            reset(ps)
            got = measure(game, ps, [(wid, element)], seconds)
            added = got["element"] / seconds
            share = (added / plain * 100.0) if plain else 0.0
            rows = {k: round(v) for k, v in got["by_effect"].items() if v > 0}
            print(f"  {'':<13}{'':>11}{element.key:>9}{added:>15.1f}"
                  f"{share:>8.0f}%{got['applications']:>10}  {rows}")
        print()


def _pairs(game, ps, wanted) -> None:
    from combat.elements.ids import ELEMENTS

    print(f"  {'pair':<28}{'element dps':>13}{'reactions':>11}  by effect")
    print("  " + "-" * 78)
    a, b = (wanted + wanted)[:2]
    seconds = 20.0
    for i, first in enumerate(ELEMENTS):
        for second in ELEMENTS[i + 1:]:
            reset(ps)
            got = measure(game, ps, [(a, first), (b, second)], seconds)
            rows = {k: round(v) for k, v in got["by_effect"].items() if v > 0}
            print(f"  {first.key + ' + ' + second.key:<28}"
                  f"{got['element'] / seconds:>13.1f}{got['reactions']:>11}  {rows}")


if __name__ == "__main__":
    raise SystemExit(main())
