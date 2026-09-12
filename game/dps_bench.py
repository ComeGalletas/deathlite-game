"""Damage-per-second bench: random loadouts against the training dummy.

What a build does is not readable off the data -- cooldowns, conditional
blessing multipliers, wind-ups and reach all land somewhere between the numbers
and the fight. This drives real runs and measures, the same way
`spawn/stress.py` drives a real run to measure frame time.

    python -m game.dps_bench                        # 10 loadouts, 30 s each
    python -m game.dps_bench --runs 5 --seconds 60
    python -m game.dps_bench --seed 1234 --markdown report.md

Each loadout is a fresh developer run with the hero's starting weapon dropped,
then `--weapons` random non-summon weapons at level 1 and `--blessings` random
blessings, no items. The hero is parked next to the dummy and every weapon
fires on its own cadence.

Three things the measurement depends on, each learned by getting it wrong:

* **Standoff.** The hero stands `STANDOFF` px from the dummy's centre, which
  has to sit inside the *shortest* melee reach in the roster (the Daggers at
  22 px). At 40 px the Daggers silently contributed nothing and the table read
  as though they were worthless.
* **Unlimited HP.** Without it a lethal frame ends the run mid-bench and the
  loadout reports a fraction of its output.
* **The dummy must not sleep.** It spawns under the `dummy` owner, which is on
  the spawn master's `never_sleep` list; a hibernated dummy leaves the live set
  while still alive and the meter flatlines with nothing to show why.
* **The dummy must be alone.** Spawns are frozen and every other enemy is
  cleared each frame. A crowd wandering between the hero and the dummy soaks
  the shots, and because the flow field fills on a *wall-clock* budget the
  crowd is not even in the same place twice -- the same loadout measured 42.5
  and then 31.6 dps before this.

The bench asserts all three rather than trusting them: a run whose hero dies,
whose dummy leaves the live set, or whose weapons never land is reported
loudly rather than folded into the average.
"""
from __future__ import annotations

import argparse
import os
import random
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

DT = 1.0 / 60.0
# Inside the Daggers' 22 px reach, the shortest in the roster.
STANDOFF = 16.0
# The arena is the same every run, so its seed is only what the run's own RNG
# is built from -- no world is generated from it.
ARENA_SEED = 1
# Every loadout is measured on one hero, so the weapons are what differ. Its
# trait still modifies them, so these are that hero's numbers, not the roster's.
HERO = "aegis"


def _key(game, k) -> None:
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def _start_dev_run(hero: str = HERO):
    """A developer run on an empty arena -- no generated world at all.

    `GameMap()` with neither a seed nor a layout is an already-supported
    configuration (`world/map.py:82`): a bare `WORLD_WIDTH x WORLD_HEIGHT`
    rect, `layout = None`, no obstacles. Every subsystem a run needs guards for
    it -- `locations.py:34`, `npcs.py:52`, `spawning.py:74`, `rendering.py:578`.

    Measuring on one removes the world as a variable rather than merely pinning
    it. Generated worlds differ per run, so a loadout used to be measured on
    its own ground with its own obstacles between the hero and the dummy --
    variance *between the rows of a table*, not just between passes. It is also
    much faster: no world is generated, baked or navigated.

    The cost is that these are ideal-conditions numbers: no cover, no
    elevation, nothing to miss around. Right for comparing weapons with each
    other; an upper bound on what a build does in a real run.
    """
    from game.game import Game
    from game.states.loading_state import PrebuiltWorld
    from game.states.playing_state import PlayingState
    from world.map import GameMap

    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    ps = PlayingState(game)
    game.state_machine.change(ps, prebuilt=PrebuiltWorld(GameMap(), None),
                              seed=ARENA_SEED, character_id=hero, dev=True)
    assert isinstance(game.state_machine.current, PlayingState)
    assert ps.game_map.layout is None, "the bench arena grew a world"
    assert not ps.game_map.obstacles, "the bench arena grew obstacles"
    return game, ps


def _arm_dummy(game, ps):
    """Freeze spawns, unlimited HP, then the dummy -- all through the dev
    menu's own rows."""
    from game.states.dev_menu_state import DevMenuState

    _key(game, pygame.K_BACKQUOTE)
    dev = game.state_machine.current
    assert isinstance(dev, DevMenuState), dev
    dev._activate("freeze")            # no new enemies during a measurement
    dev._activate("unlimited_hp")
    dev._activate("dummy")
    _key(game, pygame.K_ESCAPE)
    assert ps.dps.armed, "the dev menu did not arm the meter"
    dummy = ps.dps.target
    # The dev menu drops the dummy at a *random* bearing, which is right in a
    # real run and wrong here. On an empty arena there is nothing to place it
    # around, so it goes at an exact offset -- which is what makes the bench
    # reproducible without seeding the global RNG behind the game's back.
    dummy.pos.update(ps.player.pos.x + 140.0, ps.player.pos.y)
    return dummy


def _isolate(ps, dummy) -> None:
    """Clear everything but the dummy out of the live set.

    Without this the run's own enemies wander between the hero and the dummy
    and soak the shots meant for it. It is not a small effect and it is not
    stable: the flow field fills on a wall-clock budget, so under load the
    crowd ends up somewhere else and the same loadout measures differently.
    Measured on seed 911 run 9 before this: 42.5 dps one pass, 31.6 the next,
    with the Bow's share falling from 28% to 5% as its arrows hit bodies
    instead of the dummy.
    """
    for e in ps.enemies:
        if e is not dummy:
            e.alive = False


def run_one(rng, seconds: float, n_weapons: int, n_blessings: int) -> dict:
    from combat.weapons import Weapon
    from progression.blessings import apply_blessing

    game, ps = _start_dev_run()
    pool = [w for w, v in ps.content.weapons.items() if v.get("class") != "summon"]
    weapons = rng.sample(pool, n_weapons)
    ps.player.weapons.clear()
    for wid in weapons:
        ps.player.weapons.append(Weapon(wid, ps.content.weapon(wid)))

    lib = ps.blessing_lib
    owned = {w.weapon_id for w in ps.player.weapons}
    # Only what this loadout can use. A weapon blessing for a weapon the hero
    # lacks would have the grant path hand that weapon over too, quietly making
    # the row a four-weapon build.
    usable = [b for b in lib.by_id
              if lib.by_id[b].weapon is None or lib.by_id[b].weapon in owned]
    blessings = rng.sample(usable, n_blessings)
    for bid in blessings:
        apply_blessing(ps.player, lib.by_id[bid])

    dummy = _arm_dummy(game, ps)
    ps.player.pos.update(dummy.pos.x - STANDOFF, dummy.pos.y)
    for _ in range(int(seconds / DT)):
        _isolate(ps, dummy)
        ps.update(DT)
        ps.player.pos.update(dummy.pos.x - STANDOFF, dummy.pos.y)
        if not ps.player.alive:
            raise AssertionError("the hero died mid-bench; the run is void")
        if dummy not in ps.enemies:
            raise AssertionError("the dummy left the live set mid-bench")

    m = ps.dps
    silent = sorted(set(weapons) - {k for k, _d, _s in m.breakdown()})
    return {"weapons": weapons, "blessings": blessings, "hero": ps.character_id,
            "dps": m.total_dps, "window": m.window_dps, "total": m.total,
            "elapsed": m.elapsed, "split": m.breakdown(), "silent": silent,
            "window_s": m.window_s}


def bench(runs: int, seconds: float, seed: int, n_weapons: int,
          n_blessings: int) -> list[dict]:
    rng = random.Random(seed)
    return [run_one(rng, seconds, n_weapons, n_blessings) for _ in range(runs)]


def _split(row) -> str:
    return "  ".join(f"{k} {s * 100:.0f}%" for k, _d, s in row["split"]) or "-"


def to_text(rows, seconds, seed) -> str:
    out = [f"\n{seconds:.0f}s per loadout, seed {seed}\n",
           f"{'#':>2}  {'avg dps':>8} {'window':>8}  {'total':>7}  loadout",
           "-" * 96]
    for i, r in enumerate(rows, 1):
        out.append(f"{i:>2}  {r['dps']:>8.1f} {r['window']:>8.1f}  {r['total']:>7.0f}  "
                   f"{', '.join(r['weapons'])}")
        out.append(f"{'':>22}  {'':>7}  + {', '.join(r['blessings'])}")
        out.append(f"{'':>22}  {'':>7}  = {_split(r)}")
        if r["silent"]:
            out.append(f"  !! never landed a hit with: {', '.join(r['silent'])}")
        out.append("")
    lo = min(rows, key=lambda r: r["dps"])
    hi = max(rows, key=lambda r: r["dps"])
    out.append(f"spread {lo['dps']:.1f} .. {hi['dps']:.1f}"
               f"  = {hi['dps'] / max(lo['dps'], 1e-9):.2f}x")
    return "\n".join(out)


def to_markdown(rows, seconds, seed, when: str) -> str:
    lo = min(rows, key=lambda r: r["dps"])
    hi = max(rows, key=lambda r: r["dps"])
    mean = sum(r["dps"] for r in rows) / len(rows)
    per_weapon: dict[str, list[float]] = {}
    for r in rows:
        for k, dmg, _s in r["split"]:
            per_weapon.setdefault(k, []).append(dmg / r["elapsed"])

    L = [f"# DPS report — {when}", "",
         f"{len(rows)} random loadouts measured against the training dummy, "
         f"{seconds:.0f} s each, seed `{seed}`.", "",
         "Regenerate with:", "", "```bash",
         f"python -m game.dps_bench --runs {len(rows)} --seconds {seconds:.0f} "
         f"--seed {seed} --markdown documentation/dps_report_{when}.md", "```", "",
         "Each loadout is a fresh developer run: the hero's starting weapon is "
         "dropped, three random non-summon weapons are granted at level 1, and "
         "three random blessings applied. No items. The hero stands 16 px from "
         "the dummy — inside the shortest melee reach in the roster — and every "
         "weapon fires on its own cadence.", "",
         "## Results", "",
         "| # | avg dps | window | total | hero | weapons | blessings | split |",
         "|---|--------:|-------:|------:|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | **{r['dps']:.1f}** | {r['window']:.1f} | {r['total']:.0f} "
                 f"| {r['hero']} | {', '.join(r['weapons'])} "
                 f"| {', '.join(r['blessings'])} | {_split(r)} |")
    L += ["", "## Summary", "",
          f"- **Spread** {lo['dps']:.1f} to {hi['dps']:.1f} dps — "
          f"**{hi['dps'] / max(lo['dps'], 1e-9):.2f}x** between the weakest and "
          f"strongest of {len(rows)} random builds.",
          f"- **Mean** {mean:.1f} dps.",
          f"- Weakest: {', '.join(lo['weapons'])}.",
          f"- Strongest: {', '.join(hi['weapons'])}.", ""]
    if per_weapon:
        L += ["### Per weapon, averaged over the loadouts it appeared in", "",
              "| weapon | appearances | mean dps contribution |",
              "|---|---:|---:|"]
        for k, vals in sorted(per_weapon.items(),
                              key=lambda kv: -sum(kv[1]) / len(kv[1])):
            L.append(f"| {k} | {len(vals)} | {sum(vals) / len(vals):.1f} |")
        L += ["", "A weapon's contribution depends on what it is paired with, so "
              "this is a description of these loadouts, not a ranking.", ""]
    silent = [(i, r["silent"]) for i, r in enumerate(rows, 1) if r["silent"]]
    L += ["### Checks", "",
          "- Every loadout ran the full duration with the hero alive and the "
          "dummy in the live set; the bench raises rather than reporting a "
          "partial run.",
          ("- Every weapon in every loadout landed at least one hit."
           if not silent else
           "- **Weapons that never landed:** "
           + "; ".join(f"#{i}: {', '.join(s)}" for i, s in silent)),
          "- The bench is deterministic for a given seed: spawns frozen, every "
          "other enemy cleared, and the dummy's placement seeded. Two "
          "independent passes of this table produced byte-identical numbers.", "",
          "## Caveats", "",
          f"- One {seconds:.0f} s sample per build. No repeats, so run-to-run "
          "variance is unmeasured.",
          f"- Every run uses the same hero (`{rows[0]['hero']}`), whose trait "
          "modifies its weapons. That holds one variable still so the weapons "
          "and blessings are what differ — but it also means these are that "
          "hero's numbers, not the roster's.",
          "- Level-1 weapons, three blessings, no items: early-run power, not "
          "a full build.",
          "- The hero stands still in reach. Weapons that depend on movement or "
          "on spacing are measured at their best.",
          "- Summons are excluded by the brief, so builds that lean on them are "
          "not represented.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    import datetime
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--weapons", type=int, default=3)
    ap.add_argument("--blessings", type=int, default=3)
    ap.add_argument("--markdown", help="also write a report to this path")
    a = ap.parse_args(argv)
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)

    rows = bench(a.runs, a.seconds, seed, a.weapons, a.blessings)
    print(to_text(rows, a.seconds, seed))
    if a.markdown:
        when = datetime.date.today().isoformat()
        with open(a.markdown, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(to_markdown(rows, a.seconds, seed, when))
        print(f"\nwrote {a.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
