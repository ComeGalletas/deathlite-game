# DPS report — 2026-09-19 — damage blessings x1.25

30 builds at each of levels 1, 5, 10, 15, 20, 25, measured against the training dummy, 30 s each, seed `919`, commit `00f4965`, **every damage blessing's values x1.25**.

A what-if, not the shipped numbers: the bench multiplied every level of the damage effect of each damage-type blessing — Iron Arm and Keen Eye (percent), and the flat `+damage` weapon blessings — in the loaded catalog before the first run booted. Other effects on the same card, conditional multipliers, crit, speed, area, count and pierce are not scaled, and weapon base damage is the shipped number. `data/weapons/blessings.json` is unchanged. With the same seed the builds are identical to the baseline report's, row for row, so the two can be compared build by build.

Regenerate with:

```bash
python -m tools.benchmarks.dps_bench --levels 1,5,10,15,20,25 --runs 30 --seconds 30 --seed 919 --blessing-damage-scale 1.25 --markdown documentation/dps_calcs/dps_report_2026-09-19_blessings125.md
```

## How a build is made

Each row is a fresh developer run on the empty arena with `aegis`. The hero keeps the starter weapon and then takes **N-1 level-up picks** for level N, each through the real offering: three cards rolled at the data's weights from what the hero can take right now — weapon grants while a slot is open, blessing levels for what is held, summons, and Forge cards once a weapon carries two blessing levels — and **one taken at random**. That is an average player's build at that level, not a planned one.

Blessings with no combat advantage are removed from the pool before every roll (owner, 2026-09-19), so each pick is a damage pick: a stat blessing stays only if it moves melee or ranged damage, attack speed, crit chance or luck. No chest items, potions or meta-upgrades. The hero stands 16 px from the dummy — inside the shortest melee reach in the roster — and every weapon fires on its own cadence.

## Summary across levels

| level | builds | mean dps | median | p25 | p75 | min | max | std dev |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 30 | **12.5** | **12.5** | 12.5 | 12.5 | 12.5 | 12.5 | 0.0 |
| 5 | 30 | **34.0** | **34.3** | 27.3 | 40.4 | 14.0 | 65.8 | 11.5 |
| 10 | 30 | **56.6** | **58.1** | 45.4 | 66.9 | 35.1 | 81.2 | 13.7 |
| 15 | 30 | **70.6** | **71.4** | 59.4 | 80.7 | 46.0 | 110.8 | 14.6 |
| 20 | 30 | **92.2** | **90.1** | 75.9 | 115.8 | 47.1 | 122.9 | 21.6 |
| 25 | 30 | **91.5** | **89.7** | 70.2 | 109.0 | 43.8 | 154.2 | 25.8 |

`p25`/`p75` are the quartiles: half of the builds at that level sit between them. `min`..`max` is the whole spread; the standard deviation is over the builds measured.

## Level 1

30 builds — mean **12.5**, median **12.5**, spread 12.5 to 12.5 (**1.00x**).

- Weakest: sword + -.
- Strongest: sword + -.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 2 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 3 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 4 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 5 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 6 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 7 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 8 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 9 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 10 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 11 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 12 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 13 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 14 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 15 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 16 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 17 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 18 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 19 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 20 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 21 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 22 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 23 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 24 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 25 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 26 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 27 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 28 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 29 | **12.5** | 12.0 | 375 | sword | - | sword 100% |
| 30 | **12.5** | 12.0 | 375 | sword | - | sword 100% |

### Per source at level 1, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| sword | 30 | 12.5 |

## Level 5

30 builds — mean **34.0**, median **34.3**, spread 14.0 to 65.8 (**4.70x**).

- Weakest: sword L2 + lucky_strike, keen_eye x2, sword_wide_cleave.
- Strongest: sword, daggers, spirit_wolf, bow + +daggers, +spirit_wolf, +bow, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **34.7** | 33.6 | 1041 | sword L2, daggers, ember_ring | sword_wide_cleave, keen_eye, +daggers, +ember_ring | daggers 62%  sword 36%  ember_ring 2% |
| 2 | **14.0** | 13.5 | 420 | sword L2 | lucky_strike, keen_eye x2, sword_wide_cleave | sword 100% |
| 3 | **33.8** | 33.6 | 1012 | sword, spirit_wolf | keen_eye x2, iron_arm, +spirit_wolf | spirit_wolf 59%  sword 41% |
| 4 | **20.8** | 19.9 | 624 | sword L2, grave_totem L2 | fortune, +grave_totem, grave_totem_quick_plant, sword_critical_edge | sword 70%  grave_totem 30% |
| 5 | **38.5** | 37.0 | 1155 | sword, bomb, hammer L2 | +bomb, lucky_strike, +hammer, hammer_heavy_impact | sword 35%  hammer 35%  bomb 30% |
| 6 | **16.0** | 16.5 | 478 | sword L3 | sword_critical_edge x2, iron_arm, keen_eye | sword 100% |
| 7 | **45.4** | 44.2 | 1361 | sword, daggers L2, bow | +daggers, keen_eye, +bow, daggers_quick_hands | daggers 52%  sword 28%  bow 20% |
| 8 | **38.6** | 38.0 | 1158 | sword L2, magic_rod, hammer | +magic_rod, keen_eye, +hammer, sword_critical_edge | sword 39%  hammer 33%  magic_rod 28% |
| 9 | **29.6** | 30.8 | 888 | sword, hammer L2 | haste, keen_eye, +hammer, hammer_crushing_blow | hammer 54%  sword 46% |
| 10 | **34.6** | 31.2 | 1039 | sword, hammer L2, grave_totem | +hammer, lucky_strike, hammer_staggering_strike, +grave_totem | hammer 44%  sword 39%  grave_totem 17% |
| 11 | **35.1** | 31.2 | 1054 | sword, hammer, grave_totem | lucky_strike, +hammer, +grave_totem, fortune | hammer 44%  sword 40%  grave_totem 17% |
| 12 | **37.3** | 37.0 | 1118 | sword, magic_rod, hammer | +magic_rod, fortune, +hammer, haste | sword 38%  hammer 34%  magic_rod 29% |
| 13 | **28.8** | 27.0 | 864 | sword, hammer L3 | lucky_strike, +hammer, hammer_heavy_impact x2 | hammer 53%  sword 47% |
| 14 | **34.0** | 33.5 | 1019 | sword, bomb, bow | keen_eye, +bomb, +bow, fortune | sword 38%  bomb 35%  bow 27% |
| 15 | **48.7** | 50.4 | 1461 | sword L2, bow, daggers | sword_critical_edge, haste, +bow, +daggers | daggers 49%  sword 33%  bow 18% |
| 16 | **41.0** | 41.4 | 1231 | sword L2, magic_rod, hammer | iron_arm, sword_sharpened_edge, +magic_rod, +hammer | sword 42%  hammer 34%  magic_rod 24% |
| 17 | **28.9** | 28.4 | 867 | sword L2, ember_ring, bomb | keen_eye, +ember_ring, +bomb, sword_heavy_blade | sword 57%  bomb 41%  ember_ring 2% |
| 18 | **18.7** | 18.8 | 562 | sword L2, ember_ring | sword_sharpened_edge, lucky_strike x2, +ember_ring | sword 97%  ember_ring 3% |
| 19 | **16.6** | 16.5 | 496 | sword, ember_ring | fortune, +ember_ring, iron_arm, lucky_strike | sword 96%  ember_ring 4% |
| 20 | **27.0** | 24.2 | 810 | sword L2, bow, grave_totem | +bow, +grave_totem, fortune, sword_bloodletting | sword 46%  bow 32%  grave_totem 22% |
| 21 | **27.2** | 26.0 | 817 | sword L2, magic_rod, ember_ring | +magic_rod, sword_sharpened_edge, keen_eye, +ember_ring | sword 57%  magic_rod 40%  ember_ring 2% |
| 22 | **47.4** | 48.1 | 1423 | sword L2, spirit_wolf, bomb | +spirit_wolf, +bomb, sword_sharpened_edge, keen_eye | spirit_wolf 42%  sword 33%  bomb 25% |
| 23 | **44.9** | 44.0 | 1348 | sword L3, daggers | iron_arm, +daggers, sword_sharpened_edge, sword_heavy_blade | daggers 53%  sword 47% |
| 24 | **27.4** | 25.8 | 820 | sword L2, ember_ring L2, magic_rod | +ember_ring, sword_heavy_blade, +magic_rod, ember_ring_ember_heat | sword 60%  magic_rod 37%  ember_ring 3% |
| 25 | **24.7** | 23.2 | 740 | sword, ember_ring, magic_rod | +ember_ring, fortune, +magic_rod, iron_arm | sword 56%  magic_rod 42%  ember_ring 2% |
| 26 | **48.2** | 46.9 | 1445 | sword, daggers L2, bow | iron_arm, +daggers, +bow, daggers_quick_hands | daggers 54%  sword 29%  bow 17% |
| 27 | **65.8** | 65.4 | 1975 | sword, daggers, spirit_wolf, bow | +daggers, +spirit_wolf, +bow, iron_arm | daggers 36%  spirit_wolf 30%  sword 21%  bow 13% |
| 28 | **49.4** | 48.9 | 1482 | sword, ember_ring, daggers L2, hammer | +ember_ring, +daggers, +hammer, daggers_quick_hands | daggers 48%  hammer 26%  sword 25%  ember_ring 1% |
| 29 | **34.6** | 34.5 | 1038 | sword L3, hammer | sword_heavy_blade x2, +hammer, fortune | sword 64%  hammer 36% |
| 30 | **28.6** | 27.9 | 858 | sword L2, magic_rod | keen_eye, haste, sword_sharpened_edge, +magic_rod | sword 59%  magic_rod 41% |

### Per source at level 5, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 7 | 23.8 |
| spirit_wolf | 3 | 20.0 |
| sword | 30 | 15.0 |
| hammer | 10 | 14.0 |
| bomb | 4 | 11.7 |
| magic_rod | 7 | 10.7 |
| bow | 6 | 8.8 |
| grave_totem | 4 | 6.0 |
| ember_ring | 8 | 0.6 |

## Level 10

30 builds — mean **56.6**, median **58.1**, spread 35.1 to 81.2 (**2.31x**).

- Weakest: sword L2, magic_rod L2, ember_ring, bow L3 + lucky_strike x2, +magic_rod, magic_rod_seeking, sword_wide_cleave, +ember_ring, +bow, bow_rapid_draw, bow_piercing_arrow.
- Strongest: sword, daggers L3, bow L2, spirit_wolf + iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **58.4** | 56.3 | 1752 | sword, daggers L2, bow L2, ember_ring | +daggers, +bow, iron_arm x2, bow_rapid_draw, keen_eye, haste, daggers_quick_hands, +ember_ring | daggers 53%  sword 28%  bow 18%  ember_ring 1% |
| 2 | **57.9** | 57.6 | 1736 | sword, magic_rod, bow L3, spirit_wolf | +magic_rod, +bow, +spirit_wolf, bow_rapid_draw x2, iron_arm x2, fortune, haste | spirit_wolf 35%  sword 28%  bow 19%  magic_rod 18% |
| 3 | **43.4** | 42.2 | 1303 | sword L2, magic_rod L3, grave_totem, hammer L3 | +magic_rod, sword_wide_cleave, +grave_totem, +hammer, magic_rod_seeking x2, iron_arm, hammer_staggering_strike x2 | hammer 32%  sword 32%  magic_rod 23%  grave_totem 13% |
| 4 | **43.5** | 40.8 | 1306 | sword L2, bomb, hammer | keen_eye x3, haste x3, sword_wide_cleave, +bomb, +hammer | bomb 37%  sword 34%  hammer 29% |
| 5 | **74.1** | 74.8 | 2222 | sword L2, hammer L2, daggers L2, spirit_wolf | +hammer, fortune, keen_eye x2, hammer_crushing_blow, +daggers, +spirit_wolf, daggers_quick_hands, sword_wide_cleave | daggers 33%  spirit_wolf 27%  hammer 23%  sword 17% |
| 6 | **74.1** | 74.6 | 2224 | sword, daggers L2, bomb L3, grave_totem L2 | +daggers, +bomb, bomb_explosive_force, daggers_sharpened_blades, iron_arm x2, bomb_blast_amplifier, +grave_totem, grave_totem_twin_totems | daggers 45%  sword 20%  bomb 20%  grave_totem 15% |
| 7 | **81.2** | 80.6 | 2437 | sword, daggers L3, bow L2, spirit_wolf | iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf | daggers 45%  spirit_wolf 25%  sword 18%  bow 12% |
| 8 | **70.0** | 67.9 | 2100 | sword L2, daggers L2, magic_rod, grave_totem L2 | iron_arm x2, sword_heavy_blade, +daggers, +magic_rod, daggers_sharpened_blades, +grave_totem, grave_totem_quick_plant, fortune | daggers 48%  sword 28%  magic_rod 15%  grave_totem 9% |
| 9 | **37.7** | 32.3 | 1130 | sword L2, grave_totem L2, bomb | +grave_totem, grave_totem_long_watch, sword_critical_edge, +bomb, keen_eye x2, lucky_strike, haste x2 | bomb 44%  sword 41%  grave_totem 15% |
| 10 | **49.4** | 48.6 | 1483 | sword L3, hammer, bow L2, grave_totem L2 | +hammer, sword_wide_cleave, +bow, bow_hunters_mark, iron_arm, haste, sword_sharpened_edge, +grave_totem, grave_totem_long_watch | sword 38%  hammer 28%  bow 23%  grave_totem 11% |
| 11 | **65.9** | 66.9 | 1977 | sword L2, hammer L3, spirit_wolf, magic_rod L2 | +hammer, iron_arm, +spirit_wolf, +magic_rod, sword_sharpened_edge, keen_eye, hammer_titans_grip, hammer_crushing_blow, magic_rod_chain | spirit_wolf 30%  hammer 27%  sword 26%  magic_rod 17% |
| 12 | **61.1** | 58.2 | 1833 | sword L4, hammer, spirit_wolf, magic_rod | +hammer, haste x3, +spirit_wolf, sword_critical_edge x2, +magic_rod, sword_wide_cleave | spirit_wolf 33%  sword 27%  hammer 21%  magic_rod 20% |
| 13 | **54.2** | 52.7 | 1627 | sword L3, bomb L4, bow, grave_totem | +bomb, +bow, sword_heavy_blade, sword_sharpened_edge, +grave_totem, iron_arm, bomb_blast_amplifier, bomb_explosive_force x2 | sword 39%  bomb 35%  bow 15%  grave_totem 11% |
| 14 | **73.8** | 79.3 | 2213 | sword L4, spirit_wolf L3, bow L2, bomb | sword_critical_edge, +spirit_wolf, +bow, bow_split_arrow, sword_heavy_blade, spirit_wolf_pack x2, sword_wide_cleave, +bomb | spirit_wolf 48%  sword 26%  bomb 15%  bow 11% |
| 15 | **36.9** | 35.5 | 1106 | sword L3, hammer L4, grave_totem | +hammer, sword_wide_cleave, +grave_totem, keen_eye, hammer_executioner, hammer_titans_grip, iron_arm, sword_sharpened_edge, hammer_staggering_strike | sword 47%  hammer 38%  grave_totem 16% |
| 16 | **62.6** | 64.7 | 1877 | sword, bow L2, hammer, spirit_wolf | +bow, +hammer, fortune x2, haste, iron_arm, +spirit_wolf, bow_piercing_arrow, lucky_strike | spirit_wolf 32%  hammer 27%  sword 25%  bow 17% |
| 17 | **38.3** | 37.5 | 1148 | sword L4, bomb | lucky_strike x2, keen_eye, iron_arm, sword_sharpened_edge x2, +bomb, sword_critical_edge, fortune | sword 60%  bomb 40% |
| 18 | **78.9** | 79.3 | 2366 | sword, hammer L4, daggers, spirit_wolf | lucky_strike, +hammer, hammer_staggering_strike, keen_eye, hammer_executioner, +daggers, hammer_crushing_blow, iron_arm, +spirit_wolf | daggers 33%  spirit_wolf 25%  hammer 22%  sword 20% |
| 19 | **73.5** | 73.7 | 2204 | sword L2, daggers L3, grave_totem L2, bow | +daggers, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, +bow, haste, iron_arm, sword_critical_edge | daggers 55%  sword 24%  bow 12%  grave_totem 9% |
| 20 | **59.9** | 55.7 | 1796 | sword, ember_ring, daggers L2, bomb L2 | keen_eye, +ember_ring, +daggers, daggers_quick_hands, +bomb, lucky_strike, iron_arm, haste, bomb_demolitionist | daggers 51%  sword 26%  bomb 23%  ember_ring 1% |
| 21 | **35.1** | 34.0 | 1053 | sword L2, magic_rod L2, ember_ring, bow L3 | lucky_strike x2, +magic_rod, magic_rod_seeking, sword_wide_cleave, +ember_ring, +bow, bow_rapid_draw, bow_piercing_arrow | sword 36%  magic_rod 32%  bow 30%  ember_ring 2% |
| 22 | **52.4** | 50.4 | 1571 | sword L3, grave_totem L2, bomb, magic_rod L2 | +grave_totem, haste, +bomb, +magic_rod, magic_rod_seeking, sword_sharpened_edge, iron_arm, grave_totem_spectral_bolts, sword_critical_edge | sword 42%  bomb 20%  magic_rod 20%  grave_totem 17% |
| 23 | **46.7** | 44.3 | 1400 | sword L4, bow, magic_rod L2 | +bow, +magic_rod, lucky_strike, magic_rod_overcharge, sword_critical_edge, sword_sharpened_edge, haste, keen_eye, sword_heavy_blade | sword 47%  magic_rod 29%  bow 24% |
| 24 | **48.6** | 44.6 | 1456 | sword L2, hammer, grave_totem, bomb L5 | +hammer, +grave_totem, +bomb, sword_wide_cleave, bomb_demolition, bomb_bigger_explosion, lucky_strike, bomb_blast_amplifier, bomb_demolitionist | bomb 32%  sword 28%  hammer 28%  grave_totem 12% |
| 25 | **63.2** | 64.2 | 1897 | sword L2, spirit_wolf, hammer L2, bow L2 | fortune x2, +spirit_wolf, +hammer, +bow, lucky_strike, sword_heavy_blade, bow_rapid_draw, hammer_titans_grip | spirit_wolf 32%  sword 31%  hammer 23%  bow 15% |
| 26 | **67.2** | 66.1 | 2016 | sword L2, magic_rod L4, daggers L2 | iron_arm x2, +magic_rod, sword_sharpened_edge, magic_rod_seeking, +daggers, magic_rod_chain, magic_rod_arcane_missiles, daggers_quick_hands | daggers 42%  magic_rod 30%  sword 28% |
| 27 | **35.6** | 30.7 | 1069 | sword L2, grave_totem, bomb | lucky_strike x3, +grave_totem, fortune, sword_wide_cleave, +bomb, haste x2 | sword 45%  bomb 39%  grave_totem 16% |
| 28 | **48.1** | 48.5 | 1442 | sword L4, hammer L3, magic_rod | keen_eye, +hammer, sword_sharpened_edge x2, hammer_crushing_blow, haste, +magic_rod, hammer_heavy_impact, sword_wide_cleave | sword 42%  hammer 33%  magic_rod 24% |
| 29 | **62.9** | 62.4 | 1888 | sword L2, bomb L2, daggers L3, ember_ring L3 | +bomb, +daggers, +ember_ring, bomb_explosive_force, daggers_blood_in_the_water, ember_ring_ember_heat x2, sword_wide_cleave, daggers_sharpened_blades | daggers 55%  bomb 24%  sword 20%  ember_ring 2% |
| 30 | **45.0** | 43.2 | 1350 | sword L3, daggers L2 | +daggers, daggers_weak_point, sword_critical_edge, haste x2, keen_eye, sword_wide_cleave, fortune, iron_arm | daggers 61%  sword 39% |

### Per source at level 10, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 11 | 31.4 |
| spirit_wolf | 9 | 21.7 |
| sword | 30 | 17.0 |
| hammer | 12 | 15.0 |
| bomb | 11 | 14.6 |
| magic_rod | 10 | 12.1 |
| bow | 11 | 10.0 |
| grave_totem | 11 | 6.6 |
| ember_ring | 4 | 0.7 |

## Level 15

30 builds — mean **70.6**, median **71.4**, spread 46.0 to 110.8 (**2.41x**).

- Weakest: sword L3, ember_ring L3, bow L3, bomb L2 + sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge.
- Strongest: sword L3, hammer L2, magic_rod L4, spirit_wolf L2 + iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **72.6** | 67.7 | 2178 | sword L3, hammer L3, spirit_wolf, bow L4 | sword_critical_edge, +hammer, sword_heavy_blade, +spirit_wolf, +bow, keen_eye, bow_rapid_draw x2, hammer_heavy_impact, haste x2, lucky_strike, hammer_crushing_blow, bow_split_arrow | sword 28%  spirit_wolf 28%  hammer 25%  bow 19% |
| 2 | **81.5** | 80.8 | 2446 | sword L2, hammer L2, spirit_wolf L4, bow L4 | +hammer, +spirit_wolf, hammer_titans_grip, keen_eye, spirit_wolf_swift, +bow, bow_linebreaker, iron_arm, sword_sharpened_edge, spirit_wolf_savage_bite x2, bow_rapid_draw, lucky_strike, bow_piercing_arrow | spirit_wolf 45%  sword 23%  hammer 18%  bow 14% |
| 3 | **71.8** | 72.8 | 2153 | sword L4, daggers L4, bomb L4 | iron_arm, +daggers, daggers_quick_hands x2, +bomb, daggers_sharpened_blades, sword_critical_edge, bomb_bigger_explosion x2, haste, bomb_blast_amplifier, keen_eye, sword_wide_cleave, sword_sharpened_edge | daggers 53%  sword 31%  bomb 16% |
| 4 | **62.9** | 61.1 | 1888 | sword L3, ember_ring L4, bomb L3, magic_rod | +ember_ring, +bomb, sword_sharpened_edge, ember_ring_ember_heat, sword_critical_edge, ember_ring_wide_orbit x2, +magic_rod, forge:greatsword, haste, bomb_bigger_explosion, iron_arm x2, bomb_explosive_force | sword 58%  bomb 24%  magic_rod 17%  ember_ring 1% |
| 5 | **62.1** | 59.0 | 1862 | sword L3, magic_rod L2, hammer L2, grave_totem L2 | +magic_rod, iron_arm x3, +hammer, haste, lucky_strike x2, sword_heavy_blade, sword_critical_edge, +grave_totem, magic_rod_seeking, grave_totem_long_watch, hammer_heavy_impact | sword 38%  hammer 34%  magic_rod 19%  grave_totem 9% |
| 6 | **55.8** | 52.4 | 1675 | sword L2, magic_rod L3, bomb L2, grave_totem L2 | iron_arm x2, +magic_rod, +bomb, keen_eye, bomb_explosive_force, fortune, magic_rod_overcharge, lucky_strike x2, sword_critical_edge, magic_rod_chain, +grave_totem, grave_totem_spectral_bolts | bomb 29%  sword 29%  magic_rod 26%  grave_totem 16% |
| 7 | **69.5** | 71.1 | 2085 | sword L6, bomb L3, magic_rod L2, ember_ring | sword_heavy_blade x2, iron_arm x2, +bomb, keen_eye, +magic_rod, magic_rod_arcane_missiles, bomb_blast_amplifier x2, sword_critical_edge x2, sword_sharpened_edge, +ember_ring | sword 50%  magic_rod 32%  bomb 17%  ember_ring 1% |
| 8 | **47.9** | 45.8 | 1436 | sword, bow L3, ember_ring, bomb L4 | keen_eye x3, +bow, +ember_ring, +bomb, bomb_bigger_explosion, bow_piercing_arrow x2, fortune, bomb_blast_amplifier, haste x2, bomb_explosive_force | bomb 43%  sword 30%  bow 25%  ember_ring 1% |
| 9 | **93.4** | 96.9 | 2800 | sword L2, bomb, hammer L3, spirit_wolf L2 | sword_sharpened_edge, lucky_strike x2, +bomb, +hammer, +spirit_wolf, haste, keen_eye x2, iron_arm x2, hammer_executioner, hammer_crushing_blow, spirit_wolf_pack | spirit_wolf 38%  sword 25%  hammer 22%  bomb 15% |
| 10 | **48.7** | 45.0 | 1462 | sword L6, magic_rod, bomb L2 | keen_eye, sword_critical_edge x3, +magic_rod, haste x2, fortune, iron_arm x2, sword_wide_cleave, +bomb, sword_sharpened_edge, bomb_blast_amplifier | sword 48%  magic_rod 26%  bomb 26% |
| 11 | **76.2** | 75.9 | 2286 | sword L3, magic_rod L4, hammer L4 | +magic_rod, +hammer, magic_rod_seeking, sword_sharpened_edge x2, magic_rod_arcane_missiles, haste, keen_eye, hammer_crushing_blow x3, fortune, magic_rod_overcharge, iron_arm | hammer 36%  magic_rod 35%  sword 29% |
| 12 | **73.1** | 69.6 | 2194 | sword L2, bow L5, spirit_wolf L2, bomb | +bow, iron_arm x3, bow_split_arrow x2, bow_rapid_draw x2, +spirit_wolf, +bomb, spirit_wolf_savage_bite, sword_heavy_blade, fortune, haste | spirit_wolf 39%  sword 32%  bomb 15%  bow 15% |
| 13 | **86.8** | 85.4 | 2604 | sword L3, daggers L4, grave_totem L2, hammer L3 | sword_sharpened_edge, iron_arm x2, +daggers, sword_bloodletting, lucky_strike, daggers_quick_hands, +grave_totem, +hammer, grave_totem_twin_totems, hammer_staggering_strike x2, daggers_extended_reach, daggers_sharpened_blades | daggers 46%  sword 22%  hammer 20%  grave_totem 13% |
| 14 | **86.4** | 86.4 | 2593 | sword, daggers L4, spirit_wolf, magic_rod L2 | fortune, +daggers, iron_arm x3, daggers_quick_hands x2, keen_eye x3, daggers_extended_reach, +spirit_wolf, +magic_rod, magic_rod_overcharge | daggers 40%  spirit_wolf 23%  sword 20%  magic_rod 17% |
| 15 | **65.7** | 63.4 | 1971 | sword, hammer L4, bomb L4, ember_ring | +hammer, hammer_crushing_blow x2, +bomb, +ember_ring, fortune, bomb_blast_amplifier x2, bomb_demolitionist, iron_arm, hammer_staggering_strike, haste, forge:minefield, forge:earthshaker | hammer 42%  bomb 34%  sword 23%  ember_ring 1% |
| 16 | **81.4** | 81.9 | 2442 | sword L4, spirit_wolf, bow L4, daggers L3 | fortune x2, +spirit_wolf, sword_wide_cleave, +bow, +daggers, iron_arm, daggers_sharpened_blades, sword_bloodletting, bow_rapid_draw, daggers_quick_hands, bow_split_arrow, bow_piercing_arrow, sword_critical_edge | daggers 46%  spirit_wolf 25%  sword 18%  bow 12% |
| 17 | **69.2** | 66.5 | 2075 | sword L4, spirit_wolf L2, bomb, hammer L3 | +spirit_wolf, lucky_strike x2, keen_eye x2, spirit_wolf_swift, sword_critical_edge x2, fortune, sword_sharpened_edge, +bomb, +hammer, hammer_crushing_blow, hammer_executioner | spirit_wolf 29%  sword 26%  hammer 25%  bomb 20% |
| 18 | **83.4** | 79.4 | 2501 | sword L5, daggers L5, bomb, spirit_wolf | +daggers, +bomb, sword_sharpened_edge, daggers_weak_point, fortune, lucky_strike, sword_bloodletting, daggers_sharpened_blades, sword_crowd_cleaner x2, daggers_extended_reach x2, +spirit_wolf, haste | daggers 40%  spirit_wolf 24%  sword 22%  bomb 15% |
| 19 | **46.0** | 42.6 | 1381 | sword L3, ember_ring L3, bow L3, bomb L2 | sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge | sword 36%  bomb 35%  bow 26%  ember_ring 2% |
| 20 | **58.5** | 57.0 | 1755 | sword L5, grave_totem L3, magic_rod, daggers L3 | +grave_totem, keen_eye x2, grave_totem_long_watch, +magic_rod, sword_critical_edge x2, sword_wide_cleave, +daggers, daggers_extended_reach, sword_bloodletting, daggers_quick_hands, fortune, grave_totem_spectral_bolts | daggers 43%  sword 22%  magic_rod 21%  grave_totem 15% |
| 21 | **78.6** | 78.2 | 2357 | sword L2, bow L3, magic_rod L3, spirit_wolf L2 | +bow, haste, +magic_rod, iron_arm x2, sword_sharpened_edge, +spirit_wolf, bow_split_arrow, keen_eye x2, spirit_wolf_savage_bite, magic_rod_seeking, bow_crossfire, magic_rod_overcharge | spirit_wolf 36%  sword 26%  magic_rod 22%  bow 16% |
| 22 | **77.9** | 72.5 | 2336 | sword L3, bomb, magic_rod L3, spirit_wolf L2 | +bomb, sword_heavy_blade, haste, lucky_strike x3, +magic_rod, +spirit_wolf, spirit_wolf_swift, magic_rod_arcane_missiles x2, iron_arm x2, sword_crowd_cleaner | magic_rod 31%  sword 28%  spirit_wolf 26%  bomb 16% |
| 23 | **68.1** | 67.2 | 2044 | sword L3, daggers L4, magic_rod L4, ember_ring | +daggers, +magic_rod, daggers_weak_point, daggers_quick_hands, magic_rod_chain, +ember_ring, keen_eye, sword_sharpened_edge, magic_rod_seeking, lucky_strike, iron_arm, magic_rod_overcharge, daggers_marked_prey, sword_bloodletting | daggers 55%  sword 25%  magic_rod 19%  ember_ring 1% |
| 24 | **71.1** | 69.7 | 2133 | sword L3, bomb L2, bow L4, spirit_wolf L2 | +bomb, bomb_explosive_force, +bow, lucky_strike, keen_eye x3, bow_hunters_mark, +spirit_wolf, bow_piercing_arrow, sword_critical_edge, bow_rapid_draw, sword_bloodletting, spirit_wolf_swift | bomb 29%  spirit_wolf 28%  bow 22%  sword 20% |
| 25 | **54.3** | 46.9 | 1627 | sword L3, grave_totem L5, magic_rod, bomb | +grave_totem, grave_totem_quick_plant, grave_totem_spectral_bolts x2, +magic_rod, keen_eye, lucky_strike, sword_wide_cleave, fortune, +bomb, sword_bloodletting, grave_totem_long_watch, iron_arm, haste | sword 29%  magic_rod 25%  bomb 23%  grave_totem 22% |
| 26 | **49.4** | 42.7 | 1482 | sword L4, ember_ring, bomb L2, hammer L3 | sword_critical_edge x2, +ember_ring, haste x2, +bomb, +hammer, bomb_blast_amplifier, hammer_crushing_blow, iron_arm, hammer_heavy_impact, lucky_strike, keen_eye, sword_wide_cleave | hammer 36%  sword 36%  bomb 27%  ember_ring 1% |
| 27 | **75.9** | 72.2 | 2276 | sword L2, hammer L2, magic_rod, spirit_wolf | iron_arm x3, sword_wide_cleave, keen_eye x2, lucky_strike, haste x3, +hammer, +magic_rod, hammer_titans_grip, +spirit_wolf | sword 30%  spirit_wolf 26%  hammer 25%  magic_rod 19% |
| 28 | **57.0** | 51.7 | 1711 | sword L3, magic_rod L2, hammer L2, grave_totem | keen_eye x3, +magic_rod, iron_arm, magic_rod_overcharge, +hammer, +grave_totem, fortune, hammer_heavy_impact, haste x2, sword_heavy_blade, sword_bloodletting | sword 36%  magic_rod 29%  hammer 24%  grave_totem 10% |
| 29 | **110.8** | 116.0 | 3323 | sword L3, hammer L2, magic_rod L4, spirit_wolf L2 | iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack | spirit_wolf 32%  magic_rod 30%  sword 20%  hammer 17% |
| 30 | **81.6** | 77.9 | 2449 | sword L3, bomb L2, daggers L2, grave_totem | sword_sharpened_edge x2, lucky_strike, haste x3, +bomb, +daggers, bomb_blast_amplifier, iron_arm, keen_eye x2, +grave_totem, daggers_quick_hands | daggers 41%  sword 31%  bomb 20%  grave_totem 7% |

### Per source at level 15, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 34.8 |
| spirit_wolf | 13 | 24.9 |
| sword | 30 | 20.3 |
| hammer | 12 | 19.5 |
| magic_rod | 15 | 17.2 |
| bomb | 17 | 14.9 |
| bow | 8 | 12.4 |
| grave_totem | 7 | 8.3 |
| ember_ring | 7 | 0.7 |

## Level 20

30 builds — mean **92.2**, median **90.1**, spread 47.1 to 122.9 (**2.61x**).

- Weakest: sword L5, bow L5, ember_ring L4, bomb L2 + haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat.
- Strongest: sword L4, spirit_wolf L2, magic_rod L2, daggers L3 + +spirit_wolf, haste x2, spirit_wolf_savage_bite, fortune x3, +magic_rod, sword_sharpened_edge x3, +daggers, keen_eye x2, iron_arm, daggers_sharpened_blades, lucky_strike, daggers_marked_prey, magic_rod_seeking.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **117.3** | 118.8 | 3519 | sword L4, spirit_wolf L4, magic_rod L2, bow | sword_heavy_blade, sword_critical_edge x2, +spirit_wolf, lucky_strike, iron_arm x2, haste x3, fortune, spirit_wolf_savage_bite x3, +magic_rod, magic_rod_arcane_missiles, +bow, keen_eye x2 | spirit_wolf 38%  magic_rod 27%  sword 24%  bow 11% |
| 2 | **72.2** | 67.2 | 2165 | sword L4, hammer L5, bomb L2, grave_totem | keen_eye x4, +hammer, hammer_heavy_impact, lucky_strike, sword_critical_edge, iron_arm, fortune x2, hammer_crushing_blow x2, hammer_staggering_strike, +bomb, sword_sharpened_edge x2, bomb_demolition, +grave_totem | sword 32%  hammer 32%  bomb 28%  grave_totem 8% |
| 3 | **118.3** | 120.2 | 3549 | sword L6, daggers L4, bow L3 | keen_eye, +daggers, sword_wide_cleave x2, haste x3, fortune, +bow, daggers_quick_hands, sword_critical_edge x2, bow_heavy_draw, sword_sharpened_edge, bow_hunters_mark, iron_arm, forge:multishot, daggers_sharpened_blades, daggers_weak_point | bow 45%  daggers 35%  sword 20% |
| 4 | **70.4** | 64.5 | 2112 | sword L4, magic_rod L3, bow L3, ember_ring | fortune, keen_eye x3, lucky_strike, sword_heavy_blade, iron_arm x2, +magic_rod, magic_rod_arcane_missiles, +bow, bow_piercing_arrow x2, sword_bloodletting, +ember_ring, sword_wide_cleave, haste x2, magic_rod_seeking | magic_rod 47%  sword 35%  bow 18%  ember_ring 1% |
| 5 | **119.1** | 125.3 | 3573 | sword L2, magic_rod L2, daggers L3, spirit_wolf L2 | haste x4, +magic_rod, +daggers, sword_sharpened_edge, magic_rod_seeking, lucky_strike x2, +spirit_wolf, fortune x2, iron_arm x2, spirit_wolf_pack, daggers_quick_hands, daggers_weak_point, keen_eye | daggers 34%  spirit_wolf 31%  sword 22%  magic_rod 13% |
| 6 | **86.6** | 86.6 | 2597 | sword L5, daggers L2, grave_totem L5, bomb L3 | +daggers, iron_arm x2, +grave_totem, +bomb, daggers_quick_hands, fortune, grave_totem_long_watch x2, sword_sharpened_edge x2, grave_totem_spectral_bolts, bomb_blast_amplifier, haste x2, grave_totem_quick_plant, sword_bloodletting, sword_critical_edge, bomb_explosive_force | daggers 39%  sword 30%  bomb 18%  grave_totem 12% |
| 7 | **86.1** | 88.7 | 2582 | sword L3, grave_totem L5, hammer L3, bomb L4 | +grave_totem, grave_totem_twin_totems x2, iron_arm x2, +hammer, fortune x2, +bomb, grave_totem_spectral_bolts, bomb_explosive_force x2, grave_totem_long_watch, hammer_crushing_blow, sword_wide_cleave, sword_crowd_cleaner, hammer_executioner, forge:cluster_bomb, bomb_bigger_explosion | bomb 33%  hammer 24%  grave_totem 23%  sword 20% |
| 8 | **56.1** | 54.4 | 1682 | sword L5, grave_totem, bomb L3, bow | +grave_totem, +bomb, sword_wide_cleave, bomb_blast_amplifier, haste x3, +bow, iron_arm x3, keen_eye, sword_critical_edge, sword_bloodletting, sword_crowd_cleaner, lucky_strike x3, bomb_demolitionist | sword 39%  bomb 29%  bow 22%  grave_totem 10% |
| 9 | **89.8** | 82.3 | 2694 | sword L6, spirit_wolf, bomb L3, magic_rod L2 | +spirit_wolf, +bomb, sword_wide_cleave, sword_heavy_blade x2, fortune x3, sword_sharpened_edge x2, +magic_rod, iron_arm, magic_rod_chain, bomb_explosive_force, bomb_blast_amplifier, keen_eye x2, haste, forge:cluster_bomb | sword 40%  spirit_wolf 22%  bomb 22%  magic_rod 16% |
| 10 | **92.0** | 92.5 | 2760 | sword L3, bomb L3, magic_rod L4, spirit_wolf | +bomb, bomb_explosive_force, iron_arm, fortune, keen_eye x3, +magic_rod, magic_rod_seeking x3, haste x3, lucky_strike, sword_sharpened_edge, +spirit_wolf, bomb_blast_amplifier, sword_heavy_blade | sword 32%  bomb 28%  spirit_wolf 22%  magic_rod 17% |
| 11 | **70.8** | 68.4 | 2123 | sword L3, bow L5, hammer L2, grave_totem L2 | sword_sharpened_edge, +bow, +hammer, +grave_totem, fortune x3, bow_rapid_draw, haste x2, sword_wide_cleave, keen_eye x2, lucky_strike, bow_heavy_draw, hammer_heavy_impact, bow_piercing_arrow, grave_totem_twin_totems, bow_hunters_mark | bow 35%  sword 26%  hammer 22%  grave_totem 18% |
| 12 | **77.0** | 75.3 | 2311 | sword L5, hammer L5, bomb L4, ember_ring L3 | +hammer, iron_arm, +bomb, hammer_crushing_blow x2, sword_sharpened_edge x2, +ember_ring, bomb_demolition x2, sword_critical_edge, hammer_staggering_strike, bomb_blast_amplifier, ember_ring_wide_orbit x2, haste, hammer_titans_grip, sword_wide_cleave, forge:meteor_hammer | hammer 47%  sword 33%  bomb 20%  ember_ring 1% |
| 13 | **88.1** | 87.8 | 2643 | sword L3, daggers L4, hammer L5, ember_ring L3 | +daggers, daggers_quick_hands x3, +hammer, +ember_ring, ember_ring_ember_heat, hammer_crushing_blow x2, iron_arm x3, sword_critical_edge, keen_eye, hammer_heavy_impact, hammer_titans_grip, haste, sword_bloodletting, ember_ring_more_embers | daggers 47%  hammer 29%  sword 23%  ember_ring 1% |
| 14 | **102.0** | 103.1 | 3061 | sword L4, spirit_wolf, daggers L3, bow L4 | +spirit_wolf, sword_heavy_blade, lucky_strike x2, +daggers, +bow, bow_piercing_arrow, haste, iron_arm x2, fortune x2, keen_eye, sword_bloodletting, sword_sharpened_edge, daggers_sharpened_blades, daggers_weak_point, bow_rapid_draw x2 | daggers 40%  sword 28%  spirit_wolf 20%  bow 13% |
| 15 | **120.6** | 118.5 | 3618 | sword L5, magic_rod L2, bomb L5, spirit_wolf L2 | +magic_rod, +bomb, sword_heavy_blade, iron_arm x2, +spirit_wolf, bomb_blast_amplifier, bomb_explosive_force x2, magic_rod_overcharge, forge:cluster_bomb, bomb_bigger_explosion, spirit_wolf_pack, haste, sword_wide_cleave, keen_eye, sword_critical_edge x2, lucky_strike | bomb 39%  spirit_wolf 30%  sword 20%  magic_rod 12% |
| 16 | **116.7** | 123.5 | 3502 | sword L2, magic_rod L4, bomb L6, spirit_wolf L4 | +magic_rod, +bomb, iron_arm, magic_rod_seeking x2, +spirit_wolf, lucky_strike x2, bomb_bigger_explosion, bomb_demolitionist x2, bomb_explosive_force x2, magic_rod_chain, keen_eye, spirit_wolf_pack, spirit_wolf_savage_bite x2, sword_sharpened_edge | spirit_wolf 55%  bomb 18%  sword 16%  magic_rod 11% |
| 17 | **107.6** | 99.2 | 3229 | sword L6, daggers L4, bomb L3, spirit_wolf | +daggers, sword_wide_cleave, sword_sharpened_edge x2, daggers_extended_reach, fortune x2, sword_heavy_blade, iron_arm, keen_eye x2, sword_critical_edge, +bomb, bomb_blast_amplifier, daggers_quick_hands, daggers_sharpened_blades, bomb_explosive_force, haste, +spirit_wolf | daggers 36%  sword 25%  bomb 21%  spirit_wolf 19% |
| 18 | **75.5** | 71.6 | 2264 | sword L4, daggers L4, hammer L8, grave_totem L2 | +daggers, keen_eye, daggers_quick_hands, +hammer, hammer_executioner x3, sword_wide_cleave, hammer_heavy_impact, hammer_crushing_blow, hammer_staggering_strike x2, sword_critical_edge x2, forge:earthshaker, daggers_weak_point, +grave_totem, grave_totem_twin_totems, daggers_sharpened_blades | daggers 40%  hammer 25%  sword 20%  grave_totem 15% |
| 19 | **119.1** | 116.3 | 3573 | sword L6, spirit_wolf L2, daggers L4, hammer L3 | sword_heavy_blade, +spirit_wolf, +daggers, +hammer, sword_critical_edge, iron_arm, hammer_crushing_blow, hammer_titans_grip, haste x3, sword_wide_cleave, sword_sharpened_edge x2, daggers_quick_hands, daggers_extended_reach, keen_eye, daggers_sharpened_blades, spirit_wolf_savage_bite | daggers 34%  sword 28%  spirit_wolf 24%  hammer 15% |
| 20 | **56.1** | 54.8 | 1684 | sword L6, hammer L3, magic_rod L4, ember_ring L2 | +hammer, sword_heavy_blade, sword_sharpened_edge x2, +magic_rod, +ember_ring, lucky_strike x2, ember_ring_wide_orbit, hammer_staggering_strike, keen_eye x2, magic_rod_seeking, hammer_titans_grip, haste, magic_rod_chain, magic_rod_overcharge, sword_wide_cleave, sword_critical_edge | sword 43%  magic_rod 29%  hammer 27%  ember_ring 1% |
| 21 | **119.7** | 124.0 | 3590 | sword L3, magic_rod L2, spirit_wolf L5, daggers L3 | sword_bloodletting, iron_arm x2, fortune x2, +magic_rod, +spirit_wolf, haste, spirit_wolf_swift x2, spirit_wolf_savage_bite, sword_sharpened_edge, +daggers, keen_eye x2, daggers_extended_reach, daggers_weak_point, magic_rod_overcharge, spirit_wolf_pack | spirit_wolf 43%  daggers 26%  sword 18%  magic_rod 13% |
| 22 | **72.5** | 70.5 | 2176 | sword L4, bomb L4, ember_ring L4, magic_rod L5 | +bomb, +ember_ring, sword_critical_edge, bomb_explosive_force x2, +magic_rod, ember_ring_more_embers x2, magic_rod_seeking, magic_rod_chain, ember_ring_ember_heat, keen_eye x2, magic_rod_arcane_missiles, magic_rod_overcharge, bomb_bigger_explosion, sword_bloodletting, lucky_strike, sword_sharpened_edge | magic_rod 39%  bomb 33%  sword 26%  ember_ring 2% |
| 23 | **122.9** | 125.6 | 3688 | sword L4, spirit_wolf L2, magic_rod L2, daggers L3 | +spirit_wolf, haste x2, spirit_wolf_savage_bite, fortune x3, +magic_rod, sword_sharpened_edge x3, +daggers, keen_eye x2, iron_arm, daggers_sharpened_blades, lucky_strike, daggers_marked_prey, magic_rod_seeking | daggers 40%  sword 23%  spirit_wolf 23%  magic_rod 13% |
| 24 | **112.9** | 119.2 | 3388 | sword L2, spirit_wolf L5, magic_rod L3, daggers | +spirit_wolf, fortune, spirit_wolf_savage_bite, keen_eye x3, +magic_rod, iron_arm x2, +daggers, lucky_strike x3, spirit_wolf_pack x2, spirit_wolf_swift, magic_rod_overcharge, sword_bloodletting, magic_rod_seeking | spirit_wolf 45%  daggers 26%  sword 15%  magic_rod 15% |
| 25 | **101.8** | 101.6 | 3055 | sword L3, ember_ring L2, hammer L4, daggers L5 | +ember_ring, +hammer, hammer_titans_grip, iron_arm x3, +daggers, daggers_sharpened_blades, sword_sharpened_edge, daggers_extended_reach, sword_wide_cleave, hammer_crushing_blow x2, keen_eye x2, ember_ring_ember_heat, daggers_blood_in_the_water, daggers_quick_hands, haste | daggers 53%  hammer 25%  sword 22%  ember_ring 1% |
| 26 | **98.0** | 96.8 | 2941 | sword L5, daggers L5, ember_ring L3, hammer L4 | +daggers, daggers_quick_hands x3, +ember_ring, sword_heavy_blade x2, daggers_sharpened_blades, ember_ring_wide_orbit, +hammer, sword_bloodletting, hammer_executioner, iron_arm x2, hammer_crushing_blow x2, sword_critical_edge, keen_eye, ember_ring_more_embers | daggers 45%  sword 31%  hammer 24%  ember_ring 1% |
| 27 | **47.1** | 44.1 | 1413 | sword L5, bow L5, ember_ring L4, bomb L2 | haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat | sword 47%  bomb 27%  bow 23%  ember_ring 2% |
| 28 | **79.7** | 78.7 | 2392 | sword L5, ember_ring L4, bomb L5, hammer | sword_sharpened_edge x2, +ember_ring, +bomb, bomb_explosive_force, ember_ring_wide_orbit, fortune, bomb_blast_amplifier, sword_critical_edge, forge:greatsword, forge:minefield, ember_ring_more_embers, bomb_demolitionist, ember_ring_ember_heat, sword_wide_cleave, keen_eye, haste, bomb_bigger_explosion, +hammer | sword 43%  bomb 39%  hammer 16%  ember_ring 1% |
| 29 | **90.3** | 81.2 | 2710 | sword L2, hammer L6, bow L2, spirit_wolf | +hammer, iron_arm x2, +bow, keen_eye x3, haste x3, hammer_crushing_blow x4, +spirit_wolf, lucky_strike, hammer_heavy_impact, bow_piercing_arrow, sword_critical_edge | hammer 41%  spirit_wolf 22%  sword 21%  bow 15% |
| 30 | **81.0** | 78.3 | 2430 | sword L3, magic_rod L3, bomb L4, grave_totem L4 | +magic_rod, +bomb, +grave_totem, bomb_explosive_force, sword_crowd_cleaner, magic_rod_chain, iron_arm x3, keen_eye x2, grave_totem_twin_totems, bomb_blast_amplifier, grave_totem_spectral_bolts, bomb_bigger_explosion, magic_rod_arcane_missiles, grave_totem_quick_plant, sword_wide_cleave, haste | magic_rod 32%  grave_totem 25%  bomb 22%  sword 22% |

### Per source at level 20, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 13 | 39.6 |
| spirit_wolf | 13 | 33.9 |
| sword | 30 | 24.0 |
| bomb | 14 | 22.7 |
| hammer | 12 | 22.6 |
| magic_rod | 13 | 19.7 |
| bow | 8 | 19.1 |
| grave_totem | 7 | 12.3 |
| ember_ring | 9 | 0.9 |

## Level 25

30 builds — mean **91.5**, median **89.7**, spread 43.8 to 154.2 (**3.52x**).

- Weakest: sword L6, hammer L7, magic_rod L5, ember_ring + sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles.
- Strongest: sword L6, magic_rod L4, spirit_wolf L4, bow L6 + +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **116.8** | 113.5 | 3503 | sword L4, bow L4, daggers L7, grave_totem L2 | lucky_strike, +bow, sword_sharpened_edge x2, +daggers, daggers_weak_point x2, iron_arm x3, keen_eye x3, sword_wide_cleave, daggers_blood_in_the_water, bow_rapid_draw x2, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, daggers_quick_hands, fortune, bow_hunters_mark | daggers 58%  sword 22%  bow 15%  grave_totem 5% |
| 2 | **120.4** | 122.4 | 3611 | sword L2, daggers L3, spirit_wolf L2, bomb L5 | haste x5, lucky_strike, +daggers, iron_arm x3, daggers_quick_hands, daggers_blood_in_the_water, +spirit_wolf, +bomb, bomb_blast_amplifier x2, fortune x2, sword_bloodletting, bomb_bigger_explosion x2, keen_eye x2, spirit_wolf_swift | daggers 48%  sword 18%  bomb 17%  spirit_wolf 17% |
| 3 | **106.2** | 110.2 | 3185 | sword L3, bomb L5, spirit_wolf L3, magic_rod L6 | lucky_strike, +bomb, fortune, +spirit_wolf, sword_bloodletting, bomb_explosive_force x3, haste x2, keen_eye x3, spirit_wolf_savage_bite, +magic_rod, iron_arm, magic_rod_overcharge x2, magic_rod_seeking x2, magic_rod_chain, bomb_bigger_explosion, sword_sharpened_edge, spirit_wolf_swift | bomb 36%  spirit_wolf 27%  sword 19%  magic_rod 18% |
| 4 | **154.2** | 153.8 | 4625 | sword L6, magic_rod L4, spirit_wolf L4, bow L6 | +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm | magic_rod 35%  spirit_wolf 33%  sword 16%  bow 16% |
| 5 | **90.6** | 95.4 | 2718 | sword L3, magic_rod L6, spirit_wolf L3, bow | +magic_rod, keen_eye x2, fortune x2, sword_wide_cleave, magic_rod_seeking x4, +spirit_wolf, iron_arm x2, haste x4, +bow, sword_critical_edge, spirit_wolf_pack x2, magic_rod_chain, lucky_strike x2 | spirit_wolf 40%  sword 26%  magic_rod 18%  bow 16% |
| 6 | **88.9** | 85.3 | 2667 | sword L7, magic_rod L4, grave_totem L4, bow | +magic_rod, magic_rod_arcane_missiles, +grave_totem, sword_heavy_blade x2, keen_eye x2, grave_totem_quick_plant x2, iron_arm x4, +bow, haste, sword_sharpened_edge x2, magic_rod_chain, fortune, forge:whirlwind, whirlwind_cyclone, magic_rod_seeking, grave_totem_long_watch, sword_bloodletting | sword 51%  magic_rod 30%  bow 13%  grave_totem 7% |
| 7 | **107.9** | 102.8 | 3238 | sword L3, ember_ring L2, daggers L7, hammer L5 | lucky_strike x2, +ember_ring, +daggers, +hammer, daggers_blood_in_the_water, haste x2, sword_critical_edge, daggers_extended_reach x2, keen_eye, ember_ring_ember_heat, iron_arm x3, hammer_titans_grip, daggers_quick_hands x2, daggers_sharpened_blades, sword_bloodletting, hammer_executioner, hammer_crushing_blow, hammer_heavy_impact | daggers 62%  hammer 19%  sword 18%  ember_ring 1% |
| 8 | **99.0** | 100.9 | 2970 | sword L6, hammer L2, ember_ring L2, magic_rod L4 | fortune x5, iron_arm x3, +hammer, +ember_ring, +magic_rod, magic_rod_arcane_missiles, keen_eye x2, sword_sharpened_edge x3, hammer_staggering_strike, sword_heavy_blade, magic_rod_seeking, sword_critical_edge, forge:greatsword, magic_rod_overcharge, ember_ring_wide_orbit | sword 51%  magic_rod 29%  hammer 20%  ember_ring 1% |
| 9 | **59.2** | 56.8 | 1777 | sword L3, bow L4, ember_ring L5, bomb L5 | +bow, iron_arm x3, haste x3, +ember_ring, +bomb, ember_ring_ember_heat x2, fortune, bomb_blast_amplifier x2, sword_critical_edge, ember_ring_more_embers, bow_hunters_mark x2, bomb_explosive_force, ember_ring_wide_orbit, bomb_demolitionist, keen_eye, sword_crowd_cleaner, bow_rapid_draw | sword 37%  bomb 31%  bow 29%  ember_ring 2% |
| 10 | **111.3** | 108.4 | 3340 | sword L5, bomb L4, daggers L5, ember_ring L3 | +bomb, bomb_blast_amplifier, iron_arm, +daggers, daggers_blood_in_the_water, sword_heavy_blade x2, keen_eye x3, lucky_strike, daggers_weak_point, fortune, haste x2, sword_crowd_cleaner, bomb_bigger_explosion, +ember_ring, daggers_quick_hands, ember_ring_more_embers, daggers_sharpened_blades, bomb_explosive_force, ember_ring_wide_orbit, sword_sharpened_edge | daggers 46%  sword 31%  bomb 22%  ember_ring 1% |
| 11 | **43.8** | 39.5 | 1315 | sword L6, hammer L7, magic_rod L5, ember_ring | sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles | sword 65%  hammer 32%  magic_rod 2%  ember_ring 1% |
| 12 | **109.4** | 102.7 | 3281 | sword L5, spirit_wolf L3, magic_rod L5, bomb L4 | +spirit_wolf, +magic_rod, +bomb, iron_arm x3, magic_rod_arcane_missiles, sword_wide_cleave, bomb_explosive_force x2, lucky_strike x2, magic_rod_seeking x3, keen_eye x2, sword_crowd_cleaner, spirit_wolf_savage_bite x2, sword_critical_edge, bomb_blast_amplifier, sword_bloodletting, haste | spirit_wolf 34%  magic_rod 25%  bomb 22%  sword 19% |
| 13 | **50.5** | 45.6 | 1516 | sword L3, ember_ring L6, bow L7, magic_rod L3 | +ember_ring, ember_ring_ember_heat x3, fortune x2, lucky_strike x2, ember_ring_more_embers, +bow, bow_piercing_arrow x2, +magic_rod, iron_arm, haste, bow_split_arrow, bow_rapid_draw, magic_rod_chain, ember_ring_wide_orbit, magic_rod_seeking, bow_heavy_draw, sword_wide_cleave x2, bow_crossfire | bow 35%  sword 33%  magic_rod 29%  ember_ring 4% |
| 14 | **82.4** | 73.1 | 2473 | sword L9, hammer L2, bomb L5, ember_ring | +hammer, fortune, +bomb, bomb_explosive_force x2, sword_sharpened_edge x2, sword_wide_cleave x3, +ember_ring, keen_eye x2, bomb_bigger_explosion, haste, sword_critical_edge, iron_arm x3, lucky_strike, hammer_crushing_blow, sword_heavy_blade, bomb_blast_amplifier, sword_crowd_cleaner | sword 43%  bomb 29%  hammer 27%  ember_ring 1% |
| 15 | **62.9** | 62.0 | 1886 | sword L3, hammer L9, bomb L7, ember_ring L2 | +hammer, +bomb, bomb_bigger_explosion x2, haste x3, bomb_demolitionist, +ember_ring, sword_heavy_blade, hammer_heavy_impact x3, forge:earthshaker, hammer_staggering_strike, bomb_blast_amplifier x2, hammer_crushing_blow x2, ember_ring_wide_orbit, sword_wide_cleave, bomb_explosive_force, hammer_titans_grip, earthshaker_aftershock | hammer 40%  sword 31%  bomb 28%  ember_ring 1% |
| 16 | **75.4** | 69.0 | 2261 | sword L6, magic_rod L3, bomb L3, grave_totem L7 | sword_bloodletting, +magic_rod, +bomb, +grave_totem, grave_totem_spectral_bolts x2, magic_rod_chain, fortune, keen_eye x2, iron_arm, grave_totem_long_watch x3, sword_critical_edge, sword_sharpened_edge, grave_totem_quick_plant, lucky_strike, bomb_explosive_force, sword_heavy_blade, bomb_demolitionist, haste, sword_wide_cleave, magic_rod_seeking | sword 33%  bomb 27%  grave_totem 22%  magic_rod 18% |
| 17 | **93.3** | 87.2 | 2799 | sword L4, magic_rod L3, bomb L4, grave_totem L6 | +magic_rod, haste, +bomb, magic_rod_chain, bomb_blast_amplifier, fortune x2, +grave_totem, grave_totem_quick_plant, iron_arm, sword_critical_edge x2, grave_totem_twin_totems x3, keen_eye x3, bomb_demolitionist, lucky_strike, grave_totem_spectral_bolts, sword_sharpened_edge, bomb_explosive_force, magic_rod_arcane_missiles | magic_rod 32%  sword 24%  bomb 22%  grave_totem 22% |
| 18 | **77.6** | 73.2 | 2328 | sword L8, magic_rod L3, hammer L4, grave_totem L2 | haste x4, keen_eye x2, +magic_rod, +hammer, hammer_heavy_impact x2, sword_bloodletting x2, fortune, sword_sharpened_edge x4, hammer_titans_grip, iron_arm, +grave_totem, magic_rod_seeking x2, grave_totem_quick_plant, sword_critical_edge | sword 53%  magic_rod 20%  hammer 19%  grave_totem 8% |
| 19 | **59.2** | 52.2 | 1775 | sword L5, bomb L6, ember_ring L2, magic_rod L3 | +bomb, fortune x2, keen_eye x2, +ember_ring, lucky_strike x2, bomb_blast_amplifier, bomb_bigger_explosion x2, haste, +magic_rod, sword_wide_cleave x2, sword_bloodletting x2, iron_arm x2, magic_rod_overcharge, bomb_explosive_force x2, ember_ring_wide_orbit, magic_rod_seeking | bomb 41%  sword 29%  magic_rod 29%  ember_ring 1% |
| 20 | **127.6** | 128.7 | 3829 | sword L4, magic_rod L2, hammer L6, spirit_wolf L3 | haste x2, sword_sharpened_edge x3, +magic_rod, +hammer, keen_eye x3, hammer_staggering_strike x2, hammer_titans_grip, iron_arm x3, lucky_strike, hammer_crushing_blow, fortune, +spirit_wolf, magic_rod_chain, spirit_wolf_pack, hammer_executioner, spirit_wolf_savage_bite | spirit_wolf 40%  sword 29%  hammer 19%  magic_rod 12% |
| 21 | **126.2** | 127.2 | 3787 | sword L4, daggers L5, bow L4, grave_totem L5 | +daggers, fortune x2, +bow, keen_eye x2, bow_rapid_draw, sword_wide_cleave, bow_hunters_mark, +grave_totem, daggers_sharpened_blades x3, sword_sharpened_edge, forge:greatsword, sword_heavy_blade, grave_totem_twin_totems x2, daggers_quick_hands, bow_split_arrow, grave_totem_spectral_bolts, haste x2, grave_totem_quick_plant | daggers 42%  sword 28%  grave_totem 17%  bow 13% |
| 22 | **100.7** | 98.4 | 3021 | sword L5, grave_totem L5, daggers L3, bomb L3 | haste x3, sword_wide_cleave x2, +grave_totem, +daggers, +bomb, grave_totem_long_watch x2, iron_arm x2, fortune x2, keen_eye, daggers_quick_hands, grave_totem_quick_plant x2, sword_critical_edge, daggers_sharpened_blades, sword_sharpened_edge, bomb_demolitionist, lucky_strike, bomb_explosive_force | daggers 48%  sword 24%  bomb 21%  grave_totem 7% |
| 23 | **126.2** | 116.6 | 3787 | sword L6, grave_totem L2, daggers L4, magic_rod L5 | +grave_totem, keen_eye x3, +daggers, +magic_rod, magic_rod_chain, grave_totem_spectral_bolts, sword_sharpened_edge x3, daggers_sharpened_blades, haste x3, lucky_strike, daggers_blood_in_the_water, daggers_extended_reach, magic_rod_seeking x2, sword_critical_edge, forge:greatsword, magic_rod_arcane_missiles, sword_bloodletting | daggers 35%  sword 31%  magic_rod 27%  grave_totem 7% |
| 24 | **87.7** | 84.5 | 2632 | sword L2, magic_rod L3, hammer L7, spirit_wolf L4 | keen_eye x2, +magic_rod, lucky_strike x3, +hammer, +spirit_wolf, iron_arm x2, hammer_crushing_blow, fortune, haste, magic_rod_overcharge, spirit_wolf_swift x2, hammer_heavy_impact x2, hammer_titans_grip x2, spirit_wolf_savage_bite, hammer_executioner, sword_sharpened_edge, magic_rod_seeking | spirit_wolf 32%  sword 27%  hammer 24%  magic_rod 18% |
| 25 | **86.0** | 80.4 | 2581 | sword L6, magic_rod L4, hammer L5, grave_totem L2 | keen_eye x4, sword_sharpened_edge x4, +magic_rod, iron_arm x2, +hammer, sword_critical_edge, hammer_heavy_impact x2, haste, hammer_crushing_blow x2, fortune, magic_rod_overcharge x2, magic_rod_chain, +grave_totem, grave_totem_quick_plant | sword 45%  hammer 27%  magic_rod 20%  grave_totem 7% |
| 26 | **68.5** | 60.5 | 2056 | sword L6, bow L2, bomb L3, grave_totem L3 | haste x2, sword_wide_cleave x2, +bow, +bomb, sword_crowd_cleaner x2, fortune x3, lucky_strike x2, +grave_totem, grave_totem_spectral_bolts, bomb_explosive_force, bomb_bigger_explosion, keen_eye x4, bow_split_arrow, grave_totem_long_watch, sword_heavy_blade | bomb 35%  sword 32%  bow 21%  grave_totem 13% |
| 27 | **68.3** | 66.8 | 2049 | sword L4, ember_ring L5, magic_rod L5, hammer L6 | +ember_ring, +magic_rod, ember_ring_more_embers, fortune x3, magic_rod_arcane_missiles x2, keen_eye x2, +hammer, hammer_crushing_blow x3, magic_rod_seeking x2, ember_ring_wide_orbit x2, hammer_heavy_impact, ember_ring_ember_heat, sword_wide_cleave, sword_critical_edge, hammer_staggering_strike, sword_sharpened_edge | magic_rod 40%  hammer 34%  sword 25%  ember_ring 2% |
| 28 | **103.0** | 96.9 | 3089 | sword L7, bow L4, daggers, spirit_wolf L3 | lucky_strike x2, fortune x3, sword_wide_cleave x2, sword_sharpened_edge x2, +bow, +daggers, bow_hunters_mark x2, keen_eye, +spirit_wolf, iron_arm x4, sword_heavy_blade, spirit_wolf_swift x2, bow_piercing_arrow, sword_critical_edge | sword 34%  daggers 33%  spirit_wolf 19%  bow 14% |
| 29 | **65.6** | 60.7 | 1967 | sword L5, magic_rod L4, hammer L6, grave_totem L3 | sword_critical_edge, +magic_rod, sword_bloodletting, +hammer, sword_wide_cleave, magic_rod_overcharge, haste x3, hammer_titans_grip, lucky_strike, magic_rod_seeking x2, sword_sharpened_edge, hammer_staggering_strike, iron_arm x2, +grave_totem, grave_totem_quick_plant x2, hammer_executioner x2, hammer_heavy_impact, keen_eye | sword 41%  hammer 26%  magic_rod 22%  grave_totem 10% |
| 30 | **76.4** | 76.9 | 2291 | sword L9, grave_totem, bow L4, magic_rod L3 | iron_arm, sword_sharpened_edge x2, +grave_totem, +bow, sword_critical_edge x4, +magic_rod, lucky_strike, magic_rod_overcharge x2, sword_wide_cleave, haste x4, sword_bloodletting, bow_rapid_draw, keen_eye, fortune, bow_piercing_arrow, bow_crossfire | sword 41%  magic_rod 30%  bow 22%  grave_totem 8% |

### Per source at level 25, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 52.8 |
| spirit_wolf | 8 | 33.9 |
| sword | 30 | 28.2 |
| bomb | 12 | 23.2 |
| magic_rod | 19 | 21.6 |
| hammer | 11 | 20.5 |
| bow | 10 | 16.4 |
| grave_totem | 12 | 10.0 |
| ember_ring | 10 | 0.9 |

## Checks

- Every build ran the full duration with the hero alive and the dummy in the live set; the bench raises rather than reporting a partial run.
- A weapon that never landed a hit is listed under its level above; none if no such line appears.
- Deterministic for a given seed: spawns frozen, every other enemy cleared, the dummy at a fixed offset, one RNG per level seeded from the bench seed and the level — so adding a level to the list does not move the others.

## Caveats

- One 30 s sample per build; the spread is between builds, not between repeats of one build.
- Every run uses the same hero (`aegis`), whose trait modifies its weapons. That holds one variable still so the build is what differs — but these are that hero's numbers, not the roster's.
- Picks are random among the three offered. A player choosing well sits above the median; the p75 and max columns are the nearer guide to a good build.
- The hero stands still in reach. Weapons that depend on movement or on spacing are measured at their best; summons that leave the field between plantings are measured with their downtime included.
- Orbit weapons (Ember Ring, the Rod's Arcane Storm) are measured at their worst: their motes circle well outside the 16 px standoff and only brush the dummy, so their contribution here is a floor, not a reading of the weapon.
- Ideal-conditions numbers: no cover, no elevation, no crowd. Right for comparing levels and builds with each other; an upper bound on a real run.
