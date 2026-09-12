# DPS report — 2026-09-12

10 random loadouts measured against the training dummy, 60 s each, seed `911`.

Regenerate with:

```bash
python -m game.dps_bench --runs 10 --seconds 60 --seed 911 --markdown documentation/dps_report_2026-09-12.md
```

Each loadout is a fresh developer run: the hero's starting weapon is dropped, three random non-summon weapons are granted at level 1, and three random blessings applied. No items. The hero stands 16 px from the dummy — inside the shortest melee reach in the roster — and every weapon fires on its own cadence.

## Results

| # | avg dps | window | total | hero | weapons | blessings | split |
|---|--------:|-------:|------:|---|---|---|---|
| 1 | **32.3** | 30.8 | 1939 | aegis | bow, bomb, magic_rod | magnet, nimble, bow_crossfire | magic_rod 37%  bomb 32%  bow 31% |
| 2 | **37.3** | 34.1 | 2238 | aegis | hammer, bow, bomb | iron_arm, bow_hunters_mark, bomb_explosive_force | bomb 36%  hammer 35%  bow 29% |
| 3 | **37.7** | 34.4 | 2262 | aegis | hammer, bomb, sword | hammer_crushing_blow, gold_rush, iron_skin | hammer 39%  sword 33%  bomb 27% |
| 4 | **30.8** | 30.5 | 1850 | aegis | bow, daggers, magic_rod | daggers_quick_hands, daggers_blood_in_the_water, daggers_extended_reach | daggers 41%  magic_rod 32%  bow 27% |
| 5 | **44.1** | 42.0 | 2648 | aegis | sword, daggers, hammer | twin_daggers_dual_wield, iron_arm, daggers_extended_reach | daggers 40%  sword 31%  hammer 30% |
| 6 | **38.3** | 37.5 | 2295 | aegis | daggers, bow, magic_rod | shield_arm, bow_split_arrow, ballista_siege_bolt | bow 44%  daggers 30%  magic_rod 26% |
| 7 | **34.5** | 33.6 | 2068 | aegis | bow, magic_rod, sword | sword_bloodletting, nimble, bow_crossfire | sword 36%  magic_rod 35%  bow 29% |
| 8 | **33.3** | 31.3 | 1999 | aegis | hammer, bow, daggers | shield_arm, fortune, bow_rapid_draw | hammer 36%  daggers 36%  bow 28% |
| 9 | **33.4** | 30.3 | 2004 | aegis | daggers, hammer, bow | hammer_heavy_impact, lucky_strike, bow_split_arrow | daggers 37%  hammer 36%  bow 26% |
| 10 | **43.3** | 40.6 | 2597 | aegis | sword, hammer, bow | ballista_siege_bolt, hammer_titans_grip, iron_arm | bow 39%  sword 31%  hammer 30% |

## Summary

- **Spread** 30.8 to 44.1 dps — **1.43x** between the weakest and strongest of 10 random builds.
- **Mean** 36.5 dps.
- Weakest: bow, daggers, magic_rod.
- Strongest: sword, daggers, hammer.

### Per weapon, averaged over the loadouts it appeared in

| weapon | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 5 | 13.2 |
| hammer | 6 | 13.1 |
| sword | 4 | 13.0 |
| bomb | 3 | 11.4 |
| bow | 8 | 11.3 |
| magic_rod | 4 | 11.0 |

A weapon's contribution depends on what it is paired with, so this is a description of these loadouts, not a ranking.

### Checks

- Every loadout ran the full duration with the hero alive and the dummy in the live set; the bench raises rather than reporting a partial run.
- Every weapon in every loadout landed at least one hit.
- The bench is deterministic for a given seed: spawns frozen, every other enemy cleared, and the dummy's placement seeded. Two independent passes of this table produced byte-identical numbers.

## Caveats

- One 60 s sample per build. No repeats, so run-to-run variance is unmeasured.
- Every run uses the same hero (`aegis`), whose trait modifies its weapons. That holds one variable still so the weapons and blessings are what differ — but it also means these are that hero's numbers, not the roster's.
- Level-1 weapons, three blessings, no items: early-run power, not a full build.
- The hero stands still in reach. Weapons that depend on movement or on spacing are measured at their best.
- Summons are excluded by the brief, so builds that lean on them are not represented.
