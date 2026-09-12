# DPS report — 2026-09-11

10 random loadouts measured against the training dummy, 30 s each, seed `911`.

Regenerate with:

```bash
python -m game.dps_bench --runs 10 --seconds 30 --seed 911 --markdown documentation/dps_report_2026-09-11.md
```

Each loadout is a fresh developer run: the hero's starting weapon is dropped, three random non-summon weapons are granted at level 1, and three random blessings applied. No items. The hero stands 16 px from the dummy — inside the shortest melee reach in the roster — and every weapon fires on its own cadence.

## Results

| # | avg dps | window | total | hero | weapons | blessings | split |
|---|--------:|-------:|------:|---|---|---|---|
| 1 | **40.3** | 41.4 | 1210 | aegis | bow, bomb, magic_rod | magnet, nimble, bow_crossfire | bow 35%  bomb 32%  magic_rod 32% |
| 2 | **43.3** | 43.9 | 1298 | aegis | hammer, bow, bomb | iron_arm, bow_hunters_mark, bomb_explosive_force | bomb 38%  bow 35%  hammer 27% |
| 3 | **38.2** | 37.6 | 1145 | aegis | hammer, bomb, sword | hammer_crushing_blow, gold_rush, iron_skin | hammer 35%  bomb 34%  sword 31% |
| 4 | **42.8** | 42.6 | 1284 | aegis | bow, daggers, magic_rod | daggers_quick_hands, daggers_blood_in_the_water, daggers_extended_reach | daggers 47%  bow 28%  magic_rod 25% |
| 5 | **50.2** | 48.8 | 1507 | aegis | sword, daggers, hammer | twin_daggers_dual_wield, iron_arm, daggers_extended_reach | daggers 52%  sword 25%  hammer 23% |
| 6 | **50.8** | 50.8 | 1524 | aegis | daggers, bow, magic_rod | shield_arm, bow_split_arrow, ballista_siege_bolt | bow 43%  daggers 35%  magic_rod 21% |
| 7 | **38.9** | 38.6 | 1168 | aegis | bow, magic_rod, sword | sword_bloodletting, nimble, bow_crossfire | bow 37%  magic_rod 33%  sword 30% |
| 8 | **43.2** | 42.4 | 1297 | aegis | hammer, bow, daggers | shield_arm, fortune, bow_rapid_draw | daggers 43%  bow 31%  hammer 25% |
| 9 | **42.4** | 40.6 | 1273 | aegis | daggers, hammer, bow | hammer_heavy_impact, lucky_strike, bow_split_arrow | daggers 45%  bow 29%  hammer 26% |
| 10 | **46.3** | 44.9 | 1389 | aegis | sword, hammer, bow | ballista_siege_bolt, hammer_titans_grip, iron_arm | bow 48%  sword 27%  hammer 25% |

## Summary

- **Spread** 38.2 to 50.8 dps — **1.33x** between the weakest and strongest of 10 random builds.
- **Mean** 43.7 dps.
- Weakest: hammer, bomb, sword.
- Strongest: daggers, bow, magic_rod.

### Per weapon, averaged over the loadouts it appeared in

| weapon | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 5 | 20.4 |
| bow | 8 | 15.7 |
| bomb | 3 | 14.2 |
| sword | 4 | 12.1 |
| magic_rod | 4 | 11.9 |
| hammer | 6 | 11.7 |

A weapon's contribution depends on what it is paired with, so this is a description of these loadouts, not a ranking.

### Checks

- Every loadout ran the full duration with the hero alive and the dummy in the live set; the bench raises rather than reporting a partial run.
- Every weapon in every loadout landed at least one hit.
- The bench is deterministic for a given seed: spawns frozen, every other enemy cleared, and the dummy's placement seeded. Two independent passes of this table produced byte-identical numbers.

## Caveats

- One 30 s sample per build. No repeats, so run-to-run variance is unmeasured.
- Every run uses the same hero (`aegis`), whose trait modifies its weapons. That holds one variable still so the weapons and blessings are what differ — but it also means these are that hero's numbers, not the roster's.
- Level-1 weapons, three blessings, no items: early-run power, not a full build.
- The hero stands still in reach. Weapons that depend on movement or on spacing are measured at their best.
- Summons are excluded by the brief, so builds that lean on them are not represented.
