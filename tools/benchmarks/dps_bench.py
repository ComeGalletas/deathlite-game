"""Damage-per-second bench: level-N builds against the training dummy.

What a build does is not readable off the data -- cooldowns, conditional
blessing multipliers, wind-ups and reach all land somewhere between the numbers
and the fight. This drives real runs and measures, the same way
`tools/benchmarks/spawn_stress.py` drives a real run to measure frame time.

    python -m tools.benchmarks.dps_bench                          # 30 builds at each of 1,5,10,15,20,25
    python -m tools.benchmarks.dps_bench --levels 1,10 --runs 5 --seconds 60
    python -m tools.benchmarks.dps_bench --seed 1234 --markdown report.md

**A build is what a hero at level N actually holds** (owner, 2026-09-19): the
starter weapon, then N-1 level-up picks taken through the real offering
(`progression.blessings.offer`) -- weapon grants, blessing levels, summons and
Forge cards, at the data's own weights. Each level-up shows three cards and one
is taken at random, so this measures an average player, not a planned build.
The one departure from the real offering is the owner's directive that
**blessings with no combat advantage are filtered out** before the roll
(`combat_relevant`): Magnet, Scholar, Vitality and the like never appear, so
every pick is a damage pick. Thirty builds per level give a mean, a median and
the spread of what a level-N hero can deal.

Four things the measurement depends on, each learned by getting it wrong:

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

The bench asserts all of them rather than trusting them: a run whose hero dies,
whose dummy leaves the live set, or whose weapons never land is reported
loudly rather than folded into the average.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import subprocess
import sys
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
# Every loadout is measured on one hero, so the build is what differs. Its
# trait still modifies the weapons, so these are that hero's numbers, not the
# roster's.
HERO = "aegis"
# The hero levels a report measures at (owner, 2026-09-19). 15 is the pacing
# milestone `progression/experience.py` is tuned around; 25 is where its
# late-game discount is fully in.
LEVELS = (1, 5, 10, 15, 20, 25)
# The hero stats a *stat* blessing must move to count as a combat advantage.
# Anything else (max HP, regen, armour, block, evasion, move speed, XP, gold,
# pickup radius) changes nothing about the damage that lands on the dummy, so
# the owner asked for those cards to be kept out of a measured build.
DAMAGE_STATS = frozenset({
    "melee_damage", "ranged_damage", "damage_multiplier",
    "attack_speed_multiplier", "crit_chance", "luck",
})


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
    elevation, nothing to miss around. Right for comparing builds with each
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


# --- what-if: weapon damage scaled ------------------------------------------

def scale_weapon_damage(scale: float):
    """Multiply the *base* `damage` of every weapon, and of every Forge
    override that sets its own, in the process-wide content -- a what-if
    the owner asked for (2026-09-19: "20 % more damage on the weapons'
    numbers, weapons only"). Not a data edit: `data/weapons/*.json` is
    untouched and the game the player runs is unchanged.

    Only the first term of `Weapon._damage` (`definition["damage"] +
    bonus["damage"]`) moves. The flat `+damage` a weapon blessing adds does
    not; the percent and multiplicative layers (Iron Arm, crit, Overcharge)
    scale with the base on their own.

    Applied once per process, before the first run boots, so the starter
    weapon gets it too. Returns an `undo` callable that puts every number
    back, for tests that share the singleton.
    """
    from combat.weapons.forge import get_forges
    from game.content import get_content

    content = get_content()
    undo: list[tuple[dict, float]] = []

    def _scale(d: dict) -> None:
        if "damage" in d:
            undo.append((d, d["damage"]))
            d["damage"] = float(d["damage"]) * scale

    for w in content.weapons.values():
        _scale(w)
    for fdef in get_forges(content).by_id.values():
        _scale(fdef.overrides)
        raw = content.forges.get(fdef.id, {}).get("overrides")
        if raw is not None and raw is not fdef.overrides:
            _scale(raw)

    def restore() -> None:
        for d, value in undo:
            d["damage"] = value
    return restore


# Blessing effects whose number *is* damage (owner, 2026-09-19): the flat
# `+damage` a weapon blessing adds, and the two percent stat blessings. Not
# the conditional multipliers (Executioner, Overcharge, the synergies) and
# not crit, speed, area, count or pierce.
DAMAGE_EFFECT = (("stat", "melee_damage"), ("stat", "ranged_damage"),
                 ("weapon_bonus", "damage"))


def is_damage_effect(effect) -> bool:
    key = effect.stat if effect.type == "stat" else effect.field
    return (effect.type, key) in DAMAGE_EFFECT


def damage_blessings(catalog) -> set[str]:
    """The blessing ids `--blessing-damage-scale` touches."""
    return {bid for bid, b in catalog.by_id.items()
            if any(is_damage_effect(e) for e in b.effects)}


def scale_blessing_damage(scale: float):
    """Multiply every level of every damage effect (`DAMAGE_EFFECT`) in the
    process-wide blessing catalog -- the what-if the owner asked for
    (2026-09-19: "the damage-type blessings +25 %"). Other effects on the
    same card (Heavy Blade's weight and slower swing, Siege Bolt's pierce)
    are left alone, and `data/weapons/blessings.json` is untouched.

    `apply_blessing` adds the per-level *delta* between `levels[N]` and
    `levels[N-1]`, so scaling the list scales every level's running total
    consistently. Records are frozen dataclasses, so each touched blessing
    is rebuilt with `dataclasses.replace` and swapped into `catalog.by_id`;
    the returned `undo` swaps the originals back.
    """
    import dataclasses

    from game.content import get_content
    from progression.blessings.catalog import get_catalog

    catalog = get_catalog(get_content())
    originals: dict[str, object] = {}
    for bid, b in catalog.by_id.items():
        if not any(is_damage_effect(e) for e in b.effects):
            continue
        effects = tuple(
            dataclasses.replace(e, levels=tuple(float(v) * scale for v in e.levels))
            if is_damage_effect(e) else e
            for e in b.effects)
        originals[bid] = b
        catalog.by_id[bid] = dataclasses.replace(b, effects=effects)

    def restore() -> None:
        catalog.by_id.update(originals)
    return restore


# --- the build ------------------------------------------------------------

def combat_relevant(bdef) -> bool:
    """Whether a blessing can change the damage that lands on the dummy.

    Weapon blessings always can -- they exist to. A stat blessing counts only
    if one of its effects moves a stat in `DAMAGE_STATS`; Fortune passes on
    the "touch more crit" its `luck` carries.
    """
    if bdef.kind != "stat":
        return True
    return any(e.type == "stat" and e.stat in DAMAGE_STATS for e in bdef.effects)


def excluded_blessings(catalog) -> set[str]:
    """The blessing ids the bench keeps out of a build."""
    return {bid for bid, b in catalog.by_id.items() if not combat_relevant(b)}


def offer_cards(ps, rng: random.Random, n: int | None = None) -> list:
    """One level-up's three cards, rolled exactly as `roll_offering` rolls
    them -- weighted, without replacement -- from the valid set with the
    non-combat stat blessings removed *before* the roll. Filtering afterwards
    would sometimes leave fewer than three cards, or none; filtering the pool
    keeps every offering a full hand of damage cards."""
    from progression.blessings.catalog import get_rules
    from progression.blessings.offer import valid_offers

    catalog = ps.catalog
    cards = [u for u in valid_offers(ps.player, ps.content, rng)
             if u.kind != "stat" or combat_relevant(catalog.by_id[u.id])]
    if n is None:
        n = get_rules(ps.content).choices
    chosen = []
    while cards and len(chosen) < n:
        pick = rng.choices(cards, weights=[u.weight for u in cards], k=1)[0]
        chosen.append(pick)
        cards.remove(pick)
    return chosen


def build_at_level(ps, level: int, rng: random.Random) -> list:
    """Take the hero from level 1 to `level`: one offering per level-up, one
    card taken at random from it. Returns the cards taken, in order.

    Random rather than best-of-three is deliberate: the report is the damage
    an *average* player holds at that level. A planned build sits above it.
    """
    from progression.upgrades import apply_choice

    taken = []
    for _ in range(max(0, level - 1)):
        cards = offer_cards(ps, rng)
        if not cards:                      # everything maxed; a very late level
            break
        card = rng.choice(cards)
        apply_choice(ps.player, card)
        taken.append(card)
    ps.levels.level = max(1, level)
    return taken


def _held(ps) -> list[tuple[str, int]]:
    """`[(weapon_id, blessing levels on it)]`, in slot order."""
    from combat.weapons.forge import blessing_levels
    return [(w.weapon_id, blessing_levels(w)) for w in ps.player.weapons]


def _describe(taken) -> list[str]:
    """`grant:bow` -> `+bow`, `forge:x` -> `forge:x`, a blessing -> its id;
    a blessing taken twice reads `id x2`."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for u in taken:
        label = ("+" + u.weapon) if u.kind == "grant" else u.id
        if label not in counts:
            order.append(label)
        counts[label] = counts.get(label, 0) + 1
    return [f"{k} x{counts[k]}" if counts[k] > 1 else k for k in order]


# --- one measurement ---------------------------------------------------------

def run_one(level: int, rng: random.Random, seconds: float) -> dict:
    game, ps = _start_dev_run()
    taken = build_at_level(ps, level, rng)
    weapons = [w.weapon_id for w in ps.player.weapons]

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
    return {"level": level, "hero": ps.character_id,
            "weapons": weapons, "held": _held(ps), "picks": _describe(taken),
            "n_picks": len(taken), "blessings": dict(ps.player.blessings),
            "dps": m.total_dps, "window": m.window_dps, "total": m.total,
            "elapsed": m.elapsed, "split": m.breakdown(), "silent": silent,
            "window_s": m.window_s}


def bench(levels, runs: int, seconds: float, seed: int,
          progress=None) -> dict[int, list[dict]]:
    """`{level: [row, ...]}`. One RNG per level, seeded from the bench seed
    and the level, so adding a level to the list does not move the others."""
    out: dict[int, list[dict]] = {}
    for level in levels:
        rng = random.Random(f"{seed}:{level}")
        rows = []
        for i in range(runs):
            rows.append(run_one(level, rng, seconds))
            if progress:
                progress(level, i + 1, runs, rows[-1])
        out[level] = rows
    return out


# --- statistics ---------------------------------------------------------------

def summarise(values) -> dict:
    """mean / median / quartiles / min / max / stdev of a list of dps figures.
    Population stdev, since the rows *are* the sample being described."""
    v = sorted(float(x) for x in values)
    if not v:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p25": 0.0, "p75": 0.0,
                "min": 0.0, "max": 0.0, "stdev": 0.0}
    if len(v) >= 2:
        q = statistics.quantiles(v, n=4, method="inclusive")
        p25, p75 = q[0], q[2]
    else:
        p25 = p75 = v[0]
    return {"n": len(v), "mean": statistics.fmean(v), "median": statistics.median(v),
            "p25": p25, "p75": p75, "min": v[0], "max": v[-1],
            "stdev": statistics.pstdev(v) if len(v) > 1 else 0.0}


def per_weapon(rows) -> list[tuple[str, int, float]]:
    """`(source, appearances, mean dps contribution)`, strongest first."""
    acc: dict[str, list[float]] = {}
    for r in rows:
        for k, dmg, _s in r["split"]:
            acc.setdefault(k, []).append(dmg / r["elapsed"])
    return sorted(((k, len(v), sum(v) / len(v)) for k, v in acc.items()),
                  key=lambda t: -t[2])


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True,
                              cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip()
    except Exception:                       # not a checkout, or no git
        return "unknown"


# --- output -------------------------------------------------------------------

def _split(row) -> str:
    return "  ".join(f"{k} {s * 100:.0f}%" for k, _d, s in row["split"]) or "-"


def _held_text(row) -> str:
    parts = []
    for w, lv in row["held"]:
        parts.append(w if lv == 0 else f"{w} L{lv + 1}")
    return ", ".join(parts)


def _picks_text(row) -> str:
    return ", ".join(row["picks"]) if row["picks"] else "-"


def _scale_note(damage_scale: float, blessing_scale: float = 1.0) -> str:
    note = "" if damage_scale == 1.0 else f", weapon damage x{damage_scale:g}"
    if blessing_scale != 1.0:
        note += f", damage blessings x{blessing_scale:g}"
    return note


def to_text(table, seconds, seed, damage_scale: float = 1.0,
            blessing_scale: float = 1.0) -> str:
    out = [f"\n{seconds:.0f}s per build, seed {seed}, commit {_commit()}"
           f"{_scale_note(damage_scale, blessing_scale)}"]
    for level, rows in table.items():
        s = summarise([r["dps"] for r in rows])
        out += ["", f"== level {level}: {s['n']} builds   mean {s['mean']:.1f}   "
                    f"median {s['median']:.1f}   p25..p75 {s['p25']:.1f}..{s['p75']:.1f}   "
                    f"min..max {s['min']:.1f}..{s['max']:.1f}   sd {s['stdev']:.1f}",
                f"{'#':>2}  {'avg dps':>8} {'window':>8}  {'total':>7}  build",
                "-" * 96]
        for i, r in enumerate(rows, 1):
            out.append(f"{i:>2}  {r['dps']:>8.1f} {r['window']:>8.1f}  {r['total']:>7.0f}  "
                       f"{_held_text(r)}")
            if r["picks"]:
                out.append(f"{'':>30}  + {_picks_text(r)}")
            out.append(f"{'':>30}  = {_split(r)}")
            if r["silent"]:
                out.append(f"  !! never landed a hit with: {', '.join(r['silent'])}")
    out += ["", f"{'level':>5} {'n':>3} {'mean':>7} {'median':>7} {'p25':>7} {'p75':>7} "
                f"{'min':>7} {'max':>7} {'sd':>6}"]
    for level, rows in table.items():
        s = summarise([r["dps"] for r in rows])
        out.append(f"{level:>5} {s['n']:>3} {s['mean']:>7.1f} {s['median']:>7.1f} "
                   f"{s['p25']:>7.1f} {s['p75']:>7.1f} {s['min']:>7.1f} {s['max']:>7.1f} "
                   f"{s['stdev']:>6.1f}")
    return "\n".join(out)


def to_markdown(table, seconds, seed, when: str, damage_scale: float = 1.0,
                blessing_scale: float = 1.0) -> str:
    levels = list(table)
    runs = max(len(r) for r in table.values())
    hero = next(iter(table.values()))[0]["hero"]
    scaled = damage_scale != 1.0
    bscaled = blessing_scale != 1.0
    suffix = ((f"_damage{round(damage_scale * 100)}" if scaled else "")
              + (f"_blessings{round(blessing_scale * 100)}" if bscaled else ""))
    title = (f"# DPS report — {when}"
             + (f" — weapon damage x{damage_scale:g}" if scaled else "")
             + (f" — damage blessings x{blessing_scale:g}" if bscaled else ""))
    L = [title, "",
         f"{runs} builds at each of levels {', '.join(map(str, levels))}, measured "
         f"against the training dummy, {seconds:.0f} s each, seed `{seed}`, "
         f"commit `{_commit()}`"
         + (f", **every weapon's base damage x{damage_scale:g}**" if scaled else "")
         + (f", **every damage blessing's values x{blessing_scale:g}**" if bscaled else "")
         + ".", ""]
    if scaled:
        L += ["A what-if, not the shipped numbers: the bench multiplied the base "
              "`damage` of every weapon and every Forge damage override before the "
              "first run booted. The flat damage a weapon blessing adds is not "
              "scaled; percent and multiplicative layers scale with the base on "
              "their own. `data/weapons/*.json` is unchanged. With the same seed the "
              "builds are identical to the baseline report's, row for row, so the "
              "two can be compared build by build.", ""]
    if bscaled:
        L += ["A what-if, not the shipped numbers: the bench multiplied every level "
              "of the damage effect of each damage-type blessing — Iron Arm and "
              "Keen Eye (percent), and the flat `+damage` weapon blessings — in the "
              "loaded catalog before the first run booted. Other effects on the same "
              "card, conditional multipliers, crit, speed, area, count and pierce are "
              "not scaled, and weapon base damage is the shipped number. "
              "`data/weapons/blessings.json` is unchanged. With the same seed the "
              "builds are identical to the baseline report's, row for row, so the "
              "two can be compared build by build.", ""]
    L += ["Regenerate with:", "", "```bash",
         f"python -m tools.benchmarks.dps_bench --levels {','.join(map(str, levels))} "
         f"--runs {runs} --seconds {seconds:.0f} --seed {seed}"
         + (f" --damage-scale {damage_scale:g}" if scaled else "")
         + (f" --blessing-damage-scale {blessing_scale:g}" if bscaled else "")
         + f" --markdown documentation/dps_calcs/dps_report_{when}{suffix}.md", "```", "",
         "## How a build is made", "",
         f"Each row is a fresh developer run on the empty arena with `{hero}`. The "
         "hero keeps the starter weapon and then takes **N-1 level-up picks** for "
         "level N, each through the real offering: three cards rolled at the data's "
         "weights from what the hero can take right now — weapon grants while a "
         "slot is open, blessing levels for what is held, summons, and Forge cards "
         "once a weapon carries two blessing levels — and **one taken at random**. "
         "That is an average player's build at that level, not a planned one.", "",
         "Blessings with no combat advantage are removed from the pool before every "
         "roll (owner, 2026-09-19), so each pick is a damage pick: a stat blessing "
         "stays only if it moves melee or ranged damage, attack speed, crit chance "
         "or luck. No chest items, potions or meta-upgrades. The hero stands 16 px "
         "from the dummy — inside the shortest melee reach in the roster — and "
         "every weapon fires on its own cadence.", "",
         "## Summary across levels", "",
         "| level | builds | mean dps | median | p25 | p75 | min | max | std dev |",
         "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for level, rows in table.items():
        s = summarise([r["dps"] for r in rows])
        L.append(f"| {level} | {s['n']} | **{s['mean']:.1f}** | **{s['median']:.1f}** "
                 f"| {s['p25']:.1f} | {s['p75']:.1f} | {s['min']:.1f} | {s['max']:.1f} "
                 f"| {s['stdev']:.1f} |")
    L += ["", "`p25`/`p75` are the quartiles: half of the builds at that level sit "
          "between them. `min`..`max` is the whole spread; the standard deviation is "
          "over the builds measured.", ""]
    for level, rows in table.items():
        s = summarise([r["dps"] for r in rows])
        lo = min(rows, key=lambda r: r["dps"])
        hi = max(rows, key=lambda r: r["dps"])
        L += [f"## Level {level}", "",
              f"{s['n']} builds — mean **{s['mean']:.1f}**, median **{s['median']:.1f}**, "
              f"spread {s['min']:.1f} to {s['max']:.1f} "
              f"(**{s['max'] / max(s['min'], 1e-9):.2f}x**).", "",
              f"- Weakest: {_held_text(lo)} + {_picks_text(lo)}.",
              f"- Strongest: {_held_text(hi)} + {_picks_text(hi)}.",
              "", "| # | avg dps | window | total | held (blessing level) | picks, in order | split |",
              "|---|--------:|-------:|------:|---|---|---|"]
        for i, r in enumerate(rows, 1):
            L.append(f"| {i} | **{r['dps']:.1f}** | {r['window']:.1f} | {r['total']:.0f} "
                     f"| {_held_text(r)} | {_picks_text(r)} | {_split(r)} |")
        pw = per_weapon(rows)
        if pw:
            L += ["", f"### Per source at level {level}, averaged over the builds it appeared in", "",
                  "| source | appearances | mean dps contribution |", "|---|---:|---:|"]
            L += [f"| {k} | {n} | {v:.1f} |" for k, n, v in pw]
        silent = [(i, r["silent"]) for i, r in enumerate(rows, 1) if r["silent"]]
        if silent:
            L += ["", "**Weapons that never landed:** "
                  + "; ".join(f"#{i}: {', '.join(s)}" for i, s in silent)]
        L.append("")
    L += ["## Checks", "",
          "- Every build ran the full duration with the hero alive and the dummy "
          "in the live set; the bench raises rather than reporting a partial run.",
          "- A weapon that never landed a hit is listed under its level above; "
          "none if no such line appears.",
          "- Deterministic for a given seed: spawns frozen, every other enemy "
          "cleared, the dummy at a fixed offset, one RNG per level seeded from "
          "the bench seed and the level — so adding a level to the list does not "
          "move the others.", "",
          "## Caveats", "",
          f"- One {seconds:.0f} s sample per build; the spread is between builds, "
          "not between repeats of one build.",
          f"- Every run uses the same hero (`{hero}`), whose trait modifies its "
          "weapons. That holds one variable still so the build is what differs — "
          "but these are that hero's numbers, not the roster's.",
          "- Picks are random among the three offered. A player choosing well "
          "sits above the median; the p75 and max columns are the nearer guide "
          "to a good build.",
          "- The hero stands still in reach. Weapons that depend on movement or "
          "on spacing are measured at their best; summons that leave the field "
          "between plantings are measured with their downtime included.",
          "- Orbit weapons (Ember Ring, the Rod's Arcane Storm) are measured at "
          "their worst: their motes circle well outside the 16 px standoff and "
          "only brush the dummy, so their contribution here is a floor, not a "
          "reading of the weapon.",
          "- Ideal-conditions numbers: no cover, no elevation, no crowd. Right "
          "for comparing levels and builds with each other; an upper bound on a "
          "real run.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    import datetime
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--levels", default=",".join(map(str, LEVELS)),
                    help="comma-separated hero levels to measure at")
    ap.add_argument("--runs", type=int, default=30, help="builds per level")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--markdown", help="also write a report to this path")
    ap.add_argument("--damage-scale", type=float, default=1.0,
                    help="what-if: multiply every weapon's base damage (data untouched)")
    ap.add_argument("--blessing-damage-scale", type=float, default=1.0,
                    help="what-if: multiply the damage-type blessings' values (data untouched)")
    a = ap.parse_args(argv)
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    levels = [int(x) for x in a.levels.split(",") if x.strip()]
    if a.damage_scale != 1.0:
        scale_weapon_damage(a.damage_scale)
    if a.blessing_damage_scale != 1.0:
        scale_blessing_damage(a.blessing_damage_scale)

    def progress(level, i, n, row):
        print(f"level {level:>2}  build {i:>2}/{n}  {row['dps']:6.1f} dps  "
              f"{_held_text(row)}", file=sys.stderr, flush=True)

    table = bench(levels, a.runs, a.seconds, seed, progress)
    print(to_text(table, a.seconds, seed, a.damage_scale, a.blessing_damage_scale))
    if a.markdown:
        when = datetime.date.today().isoformat()
        with open(a.markdown, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(to_markdown(table, a.seconds, seed, when, a.damage_scale,
                                 a.blessing_damage_scale))
        print(f"\nwrote {a.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
