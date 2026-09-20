# DPS report — 2026-09-19

30 builds at each of levels 1, 5, 10, 15, 20, 25, measured against the training dummy, 30 s each, seed `919`, commit `00f4965`.

Regenerate with:

```bash
python -m tools.benchmarks.dps_bench --levels 1,5,10,15,20,25 --runs 30 --seconds 30 --seed 919 --markdown documentation/dps_calcs/dps_report_2026-09-19.md
```

## How a build is made

Each row is a fresh developer run on the empty arena with `aegis`. The hero keeps the starter weapon and then takes **N-1 level-up picks** for level N, each through the real offering: three cards rolled at the data's weights from what the hero can take right now — weapon grants while a slot is open, blessing levels for what is held, summons, and Forge cards once a weapon carries two blessing levels — and **one taken at random**. That is an average player's build at that level, not a planned one.

Blessings with no combat advantage are removed from the pool before every roll (owner, 2026-09-19), so each pick is a damage pick: a stat blessing stays only if it moves melee or ranged damage, attack speed, crit chance or luck. No chest items, potions or meta-upgrades. The hero stands 16 px from the dummy — inside the shortest melee reach in the roster — and every weapon fires on its own cadence.

## Summary across levels

| level | builds | mean dps | median | p25 | p75 | min | max | std dev |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 30 | **12.5** | **12.5** | 12.5 | 12.5 | 12.5 | 12.5 | 0.0 |
| 5 | 30 | **33.5** | **33.5** | 26.6 | 39.5 | 14.0 | 65.2 | 11.4 |
| 10 | 30 | **55.0** | **57.0** | 44.2 | 64.6 | 35.1 | 77.8 | 13.1 |
| 15 | 30 | **67.6** | **68.1** | 57.8 | 76.4 | 44.3 | 106.5 | 14.0 |
| 20 | 30 | **86.3** | **83.4** | 72.1 | 107.6 | 44.4 | 115.6 | 19.9 |
| 25 | 30 | **85.0** | **84.7** | 65.6 | 100.8 | 39.4 | 143.4 | 24.0 |

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

30 builds — mean **33.5**, median **33.5**, spread 14.0 to 65.2 (**4.65x**).

- Weakest: sword L2 + lucky_strike, keen_eye x2, sword_wide_cleave.
- Strongest: sword, daggers, spirit_wolf, bow + +daggers, +spirit_wolf, +bow, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **34.7** | 33.6 | 1041 | sword L2, daggers, ember_ring | sword_wide_cleave, keen_eye, +daggers, +ember_ring | daggers 62%  sword 36%  ember_ring 2% |
| 2 | **14.0** | 13.5 | 420 | sword L2 | lucky_strike, keen_eye x2, sword_wide_cleave | sword 100% |
| 3 | **33.5** | 33.4 | 1005 | sword, spirit_wolf | keen_eye x2, iron_arm, +spirit_wolf | spirit_wolf 60%  sword 40% |
| 4 | **20.8** | 19.9 | 624 | sword L2, grave_totem L2 | fortune, +grave_totem, grave_totem_quick_plant, sword_critical_edge | sword 70%  grave_totem 30% |
| 5 | **38.5** | 37.0 | 1155 | sword, bomb, hammer L2 | +bomb, lucky_strike, +hammer, hammer_heavy_impact | sword 35%  hammer 35%  bomb 30% |
| 6 | **15.7** | 16.2 | 470 | sword L3 | sword_critical_edge x2, iron_arm, keen_eye | sword 100% |
| 7 | **45.2** | 44.0 | 1356 | sword, daggers L2, bow | +daggers, keen_eye, +bow, daggers_quick_hands | daggers 52%  sword 28%  bow 20% |
| 8 | **38.4** | 37.8 | 1152 | sword L2, magic_rod, hammer | +magic_rod, keen_eye, +hammer, sword_critical_edge | sword 39%  hammer 33%  magic_rod 28% |
| 9 | **28.9** | 30.0 | 867 | sword, hammer L2 | haste, keen_eye, +hammer, hammer_crushing_blow | hammer 53%  sword 47% |
| 10 | **34.6** | 31.2 | 1039 | sword, hammer L2, grave_totem | +hammer, lucky_strike, hammer_staggering_strike, +grave_totem | hammer 44%  sword 39%  grave_totem 17% |
| 11 | **35.1** | 31.2 | 1054 | sword, hammer, grave_totem | lucky_strike, +hammer, +grave_totem, fortune | hammer 44%  sword 40%  grave_totem 17% |
| 12 | **37.3** | 37.0 | 1118 | sword, magic_rod, hammer | +magic_rod, fortune, +hammer, haste | sword 38%  hammer 34%  magic_rod 29% |
| 13 | **28.8** | 27.0 | 864 | sword, hammer L3 | lucky_strike, +hammer, hammer_heavy_impact x2 | hammer 53%  sword 47% |
| 14 | **33.6** | 33.1 | 1008 | sword, bomb, bow | keen_eye, +bomb, +bow, fortune | sword 39%  bomb 35%  bow 27% |
| 15 | **48.7** | 50.4 | 1461 | sword L2, bow, daggers | sword_critical_edge, haste, +bow, +daggers | daggers 49%  sword 33%  bow 18% |
| 16 | **39.8** | 40.1 | 1194 | sword L2, magic_rod, hammer | iron_arm, sword_sharpened_edge, +magic_rod, +hammer | sword 41%  hammer 34%  magic_rod 25% |
| 17 | **27.6** | 27.1 | 828 | sword L2, ember_ring, bomb | keen_eye, +ember_ring, +bomb, sword_heavy_blade | sword 56%  bomb 42%  ember_ring 2% |
| 18 | **18.0** | 18.0 | 540 | sword L2, ember_ring | sword_sharpened_edge, lucky_strike x2, +ember_ring | sword 97%  ember_ring 3% |
| 19 | **16.3** | 16.2 | 488 | sword, ember_ring | fortune, +ember_ring, iron_arm, lucky_strike | sword 96%  ember_ring 4% |
| 20 | **27.0** | 24.2 | 810 | sword L2, bow, grave_totem | +bow, +grave_totem, fortune, sword_bloodletting | sword 46%  bow 32%  grave_totem 22% |
| 21 | **26.4** | 25.2 | 792 | sword L2, magic_rod, ember_ring | +magic_rod, sword_sharpened_edge, keen_eye, +ember_ring | sword 57%  magic_rod 41%  ember_ring 2% |
| 22 | **46.6** | 47.2 | 1398 | sword L2, spirit_wolf, bomb | +spirit_wolf, +bomb, sword_sharpened_edge, keen_eye | spirit_wolf 43%  sword 32%  bomb 25% |
| 23 | **42.3** | 41.5 | 1270 | sword L3, daggers | iron_arm, +daggers, sword_sharpened_edge, sword_heavy_blade | daggers 55%  sword 45% |
| 24 | **26.2** | 24.7 | 786 | sword L2, ember_ring L2, magic_rod | +ember_ring, sword_heavy_blade, +magic_rod, ember_ring_ember_heat | sword 59%  magic_rod 38%  ember_ring 3% |
| 25 | **24.4** | 23.0 | 733 | sword, ember_ring, magic_rod | +ember_ring, fortune, +magic_rod, iron_arm | sword 55%  magic_rod 42%  ember_ring 2% |
| 26 | **47.4** | 46.2 | 1423 | sword, daggers L2, bow | iron_arm, +daggers, +bow, daggers_quick_hands | daggers 54%  sword 28%  bow 18% |
| 27 | **65.2** | 64.7 | 1955 | sword, daggers, spirit_wolf, bow | +daggers, +spirit_wolf, +bow, iron_arm | daggers 36%  spirit_wolf 31%  sword 21%  bow 13% |
| 28 | **49.4** | 48.9 | 1482 | sword, ember_ring, daggers L2, hammer | +ember_ring, +daggers, +hammer, daggers_quick_hands | daggers 48%  hammer 26%  sword 25%  ember_ring 1% |
| 29 | **32.4** | 32.4 | 972 | sword L3, hammer | sword_heavy_blade x2, +hammer, fortune | sword 61%  hammer 39% |
| 30 | **27.7** | 27.0 | 832 | sword L2, magic_rod | keen_eye, haste, sword_sharpened_edge, +magic_rod | sword 58%  magic_rod 42% |

### Per source at level 5, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 7 | 23.6 |
| spirit_wolf | 3 | 20.0 |
| sword | 30 | 14.6 |
| hammer | 10 | 13.9 |
| bomb | 4 | 11.6 |
| magic_rod | 7 | 10.6 |
| bow | 6 | 8.7 |
| grave_totem | 4 | 6.0 |
| ember_ring | 8 | 0.6 |

## Level 10

30 builds — mean **55.0**, median **57.0**, spread 35.1 to 77.8 (**2.22x**).

- Weakest: sword L2, magic_rod L2, ember_ring, bow L3 + lucky_strike x2, +magic_rod, magic_rod_seeking, sword_wide_cleave, +ember_ring, +bow, bow_rapid_draw, bow_piercing_arrow.
- Strongest: sword, daggers L3, bow L2, spirit_wolf + iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **56.6** | 54.6 | 1699 | sword, daggers L2, bow L2, ember_ring | +daggers, +bow, iron_arm x2, bow_rapid_draw, keen_eye, haste, daggers_quick_hands, +ember_ring | daggers 53%  sword 28%  bow 18%  ember_ring 1% |
| 2 | **57.3** | 57.1 | 1720 | sword, magic_rod, bow L3, spirit_wolf | +magic_rod, +bow, +spirit_wolf, bow_rapid_draw x2, iron_arm x2, fortune, haste | spirit_wolf 35%  sword 27%  bow 19%  magic_rod 19% |
| 3 | **42.9** | 41.7 | 1288 | sword L2, magic_rod L3, grave_totem, hammer L3 | +magic_rod, sword_wide_cleave, +grave_totem, +hammer, magic_rod_seeking x2, iron_arm, hammer_staggering_strike x2 | hammer 32%  sword 31%  magic_rod 23%  grave_totem 14% |
| 4 | **42.8** | 40.1 | 1284 | sword L2, bomb, hammer | keen_eye x3, haste x3, sword_wide_cleave, +bomb, +hammer | bomb 36%  sword 35%  hammer 29% |
| 5 | **73.3** | 74.1 | 2199 | sword L2, hammer L2, daggers L2, spirit_wolf | +hammer, fortune, keen_eye x2, hammer_crushing_blow, +daggers, +spirit_wolf, daggers_quick_hands, sword_wide_cleave | daggers 33%  spirit_wolf 27%  hammer 23%  sword 17% |
| 6 | **70.3** | 70.7 | 2110 | sword, daggers L2, bomb L3, grave_totem L2 | +daggers, +bomb, bomb_explosive_force, daggers_sharpened_blades, iron_arm x2, bomb_blast_amplifier, +grave_totem, grave_totem_twin_totems | daggers 44%  sword 21%  bomb 20%  grave_totem 16% |
| 7 | **77.8** | 77.2 | 2335 | sword, daggers L3, bow L2, spirit_wolf | iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf | daggers 43%  spirit_wolf 26%  sword 19%  bow 12% |
| 8 | **65.5** | 63.6 | 1966 | sword L2, daggers L2, magic_rod, grave_totem L2 | iron_arm x2, sword_heavy_blade, +daggers, +magic_rod, daggers_sharpened_blades, +grave_totem, grave_totem_quick_plant, fortune | daggers 47%  sword 27%  magic_rod 16%  grave_totem 10% |
| 9 | **37.1** | 31.8 | 1113 | sword L2, grave_totem L2, bomb | +grave_totem, grave_totem_long_watch, sword_critical_edge, +bomb, keen_eye x2, lucky_strike, haste x2 | bomb 43%  sword 42%  grave_totem 15% |
| 10 | **48.1** | 47.3 | 1443 | sword L3, hammer, bow L2, grave_totem L2 | +hammer, sword_wide_cleave, +bow, bow_hunters_mark, iron_arm, haste, sword_sharpened_edge, +grave_totem, grave_totem_long_watch | sword 36%  hammer 28%  bow 24%  grave_totem 12% |
| 11 | **63.6** | 64.6 | 1909 | sword L2, hammer L3, spirit_wolf, magic_rod L2 | +hammer, iron_arm, +spirit_wolf, +magic_rod, sword_sharpened_edge, keen_eye, hammer_titans_grip, hammer_crushing_blow, magic_rod_chain | spirit_wolf 31%  hammer 26%  sword 25%  magic_rod 17% |
| 12 | **61.1** | 58.2 | 1833 | sword L4, hammer, spirit_wolf, magic_rod | +hammer, haste x3, +spirit_wolf, sword_critical_edge x2, +magic_rod, sword_wide_cleave | spirit_wolf 33%  sword 27%  hammer 21%  magic_rod 20% |
| 13 | **50.4** | 48.8 | 1513 | sword L3, bomb L4, bow, grave_totem | +bomb, +bow, sword_heavy_blade, sword_sharpened_edge, +grave_totem, iron_arm, bomb_blast_amplifier, bomb_explosive_force x2 | sword 38%  bomb 34%  bow 17%  grave_totem 12% |
| 14 | **72.5** | 78.0 | 2174 | sword L4, spirit_wolf L3, bow L2, bomb | sword_critical_edge, +spirit_wolf, +bow, bow_split_arrow, sword_heavy_blade, spirit_wolf_pack x2, sword_wide_cleave, +bomb | spirit_wolf 49%  sword 25%  bomb 15%  bow 11% |
| 15 | **35.6** | 34.3 | 1069 | sword L3, hammer L4, grave_totem | +hammer, sword_wide_cleave, +grave_totem, keen_eye, hammer_executioner, hammer_titans_grip, iron_arm, sword_sharpened_edge, hammer_staggering_strike | sword 45%  hammer 38%  grave_totem 16% |
| 16 | **62.0** | 64.1 | 1859 | sword, bow L2, hammer, spirit_wolf | +bow, +hammer, fortune x2, haste, iron_arm, +spirit_wolf, bow_piercing_arrow, lucky_strike | spirit_wolf 32%  hammer 27%  sword 24%  bow 17% |
| 17 | **36.1** | 35.5 | 1082 | sword L4, bomb | lucky_strike x2, keen_eye, iron_arm, sword_sharpened_edge x2, +bomb, sword_critical_edge, fortune | sword 59%  bomb 41% |
| 18 | **77.0** | 77.4 | 2311 | sword, hammer L4, daggers, spirit_wolf | lucky_strike, +hammer, hammer_staggering_strike, keen_eye, hammer_executioner, +daggers, hammer_crushing_blow, iron_arm, +spirit_wolf | daggers 33%  spirit_wolf 26%  hammer 22%  sword 20% |
| 19 | **69.6** | 69.8 | 2087 | sword L2, daggers L3, grave_totem L2, bow | +daggers, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, +bow, haste, iron_arm, sword_critical_edge | daggers 53%  sword 25%  bow 13%  grave_totem 9% |
| 20 | **58.8** | 54.6 | 1763 | sword, ember_ring, daggers L2, bomb L2 | keen_eye, +ember_ring, +daggers, daggers_quick_hands, +bomb, lucky_strike, iron_arm, haste, bomb_demolitionist | daggers 51%  sword 26%  bomb 23%  ember_ring 1% |
| 21 | **35.1** | 34.0 | 1053 | sword L2, magic_rod L2, ember_ring, bow L3 | lucky_strike x2, +magic_rod, magic_rod_seeking, sword_wide_cleave, +ember_ring, +bow, bow_rapid_draw, bow_piercing_arrow | sword 36%  magic_rod 32%  bow 30%  ember_ring 2% |
| 22 | **50.5** | 48.5 | 1514 | sword L3, grave_totem L2, bomb, magic_rod L2 | +grave_totem, haste, +bomb, +magic_rod, magic_rod_seeking, sword_sharpened_edge, iron_arm, grave_totem_spectral_bolts, sword_critical_edge | sword 41%  bomb 21%  magic_rod 21%  grave_totem 17% |
| 23 | **44.3** | 42.1 | 1330 | sword L4, bow, magic_rod L2 | +bow, +magic_rod, lucky_strike, magic_rod_overcharge, sword_critical_edge, sword_sharpened_edge, haste, keen_eye, sword_heavy_blade | sword 45%  magic_rod 30%  bow 25% |
| 24 | **48.6** | 44.6 | 1456 | sword L2, hammer, grave_totem, bomb L5 | +hammer, +grave_totem, +bomb, sword_wide_cleave, bomb_demolition, bomb_bigger_explosion, lucky_strike, bomb_blast_amplifier, bomb_demolitionist | bomb 32%  sword 28%  hammer 28%  grave_totem 12% |
| 25 | **61.9** | 62.8 | 1858 | sword L2, spirit_wolf, hammer L2, bow L2 | fortune x2, +spirit_wolf, +hammer, +bow, lucky_strike, sword_heavy_blade, bow_rapid_draw, hammer_titans_grip | spirit_wolf 32%  sword 29%  hammer 23%  bow 15% |
| 26 | **64.9** | 63.8 | 1947 | sword L2, magic_rod L4, daggers L2 | iron_arm x2, +magic_rod, sword_sharpened_edge, magic_rod_seeking, +daggers, magic_rod_chain, magic_rod_arcane_missiles, daggers_quick_hands | daggers 42%  magic_rod 31%  sword 27% |
| 27 | **35.6** | 30.7 | 1069 | sword L2, grave_totem, bomb | lucky_strike x3, +grave_totem, fortune, sword_wide_cleave, +bomb, haste x2 | sword 45%  bomb 39%  grave_totem 16% |
| 28 | **45.8** | 46.2 | 1375 | sword L4, hammer L3, magic_rod | keen_eye, +hammer, sword_sharpened_edge x2, hammer_crushing_blow, haste, +magic_rod, hammer_heavy_impact, sword_wide_cleave | sword 41%  hammer 34%  magic_rod 25% |
| 29 | **60.5** | 60.0 | 1815 | sword L2, bomb L2, daggers L3, ember_ring L3 | +bomb, +daggers, +ember_ring, bomb_explosive_force, daggers_blood_in_the_water, ember_ring_ember_heat x2, sword_wide_cleave, daggers_sharpened_blades | daggers 55%  bomb 23%  sword 21%  ember_ring 2% |
| 30 | **44.2** | 42.4 | 1325 | sword L3, daggers L2 | +daggers, daggers_weak_point, sword_critical_edge, haste x2, keen_eye, sword_wide_cleave, fortune, iron_arm | daggers 61%  sword 39% |

### Per source at level 10, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 11 | 29.9 |
| spirit_wolf | 9 | 21.7 |
| sword | 30 | 16.3 |
| hammer | 12 | 14.6 |
| bomb | 11 | 14.1 |
| magic_rod | 10 | 12.0 |
| bow | 11 | 10.0 |
| grave_totem | 11 | 6.6 |
| ember_ring | 4 | 0.7 |

## Level 15

30 builds — mean **67.6**, median **68.1**, spread 44.3 to 106.5 (**2.41x**).

- Weakest: sword L3, ember_ring L3, bow L3, bomb L2 + sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge.
- Strongest: sword L3, hammer L2, magic_rod L4, spirit_wolf L2 + iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **70.2** | 65.5 | 2105 | sword L3, hammer L3, spirit_wolf, bow L4 | sword_critical_edge, +hammer, sword_heavy_blade, +spirit_wolf, +bow, keen_eye, bow_rapid_draw x2, hammer_heavy_impact, haste x2, lucky_strike, hammer_crushing_blow, bow_split_arrow | spirit_wolf 28%  sword 27%  hammer 25%  bow 19% |
| 2 | **76.7** | 76.0 | 2300 | sword L2, hammer L2, spirit_wolf L4, bow L4 | +hammer, +spirit_wolf, hammer_titans_grip, keen_eye, spirit_wolf_swift, +bow, bow_linebreaker, iron_arm, sword_sharpened_edge, spirit_wolf_savage_bite x2, bow_rapid_draw, lucky_strike, bow_piercing_arrow | spirit_wolf 43%  sword 23%  hammer 19%  bow 15% |
| 3 | **68.0** | 68.9 | 2039 | sword L4, daggers L4, bomb L4 | iron_arm, +daggers, daggers_quick_hands x2, +bomb, daggers_sharpened_blades, sword_critical_edge, bomb_bigger_explosion x2, haste, bomb_blast_amplifier, keen_eye, sword_wide_cleave, sword_sharpened_edge | daggers 52%  sword 31%  bomb 17% |
| 4 | **60.3** | 58.5 | 1808 | sword L3, ember_ring L4, bomb L3, magic_rod | +ember_ring, +bomb, sword_sharpened_edge, ember_ring_ember_heat, sword_critical_edge, ember_ring_wide_orbit x2, +magic_rod, forge:greatsword, haste, bomb_bigger_explosion, iron_arm x2, bomb_explosive_force | sword 58%  bomb 23%  magic_rod 18%  ember_ring 1% |
| 5 | **58.5** | 55.4 | 1756 | sword L3, magic_rod L2, hammer L2, grave_totem L2 | +magic_rod, iron_arm x3, +hammer, haste, lucky_strike x2, sword_heavy_blade, sword_critical_edge, +grave_totem, magic_rod_seeking, grave_totem_long_watch, hammer_heavy_impact | sword 36%  hammer 34%  magic_rod 21%  grave_totem 10% |
| 6 | **53.2** | 49.9 | 1597 | sword L2, magic_rod L3, bomb L2, grave_totem L2 | iron_arm x2, +magic_rod, +bomb, keen_eye, bomb_explosive_force, fortune, magic_rod_overcharge, lucky_strike x2, sword_critical_edge, magic_rod_chain, +grave_totem, grave_totem_spectral_bolts | sword 29%  bomb 28%  magic_rod 27%  grave_totem 16% |
| 7 | **64.0** | 65.3 | 1919 | sword L6, bomb L3, magic_rod L2, ember_ring | sword_heavy_blade x2, iron_arm x2, +bomb, keen_eye, +magic_rod, magic_rod_arcane_missiles, bomb_blast_amplifier x2, sword_critical_edge x2, sword_sharpened_edge, +ember_ring | sword 47%  magic_rod 34%  bomb 18%  ember_ring 1% |
| 8 | **45.3** | 43.3 | 1358 | sword, bow L3, ember_ring, bomb L4 | keen_eye x3, +bow, +ember_ring, +bomb, bomb_bigger_explosion, bow_piercing_arrow x2, fortune, bomb_blast_amplifier, haste x2, bomb_explosive_force | bomb 41%  sword 32%  bow 26%  ember_ring 1% |
| 9 | **89.7** | 93.2 | 2690 | sword L2, bomb, hammer L3, spirit_wolf L2 | sword_sharpened_edge, lucky_strike x2, +bomb, +hammer, +spirit_wolf, haste, keen_eye x2, iron_arm x2, hammer_executioner, hammer_crushing_blow, spirit_wolf_pack | spirit_wolf 40%  sword 24%  hammer 21%  bomb 15% |
| 10 | **46.6** | 43.1 | 1398 | sword L6, magic_rod, bomb L2 | keen_eye, sword_critical_edge x3, +magic_rod, haste x2, fortune, iron_arm x2, sword_wide_cleave, +bomb, sword_sharpened_edge, bomb_blast_amplifier | sword 46%  magic_rod 27%  bomb 27% |
| 11 | **70.9** | 70.6 | 2128 | sword L3, magic_rod L4, hammer L4 | +magic_rod, +hammer, magic_rod_seeking, sword_sharpened_edge x2, magic_rod_arcane_missiles, haste, keen_eye, hammer_crushing_blow x3, fortune, magic_rod_overcharge, iron_arm | magic_rod 37%  hammer 34%  sword 29% |
| 12 | **68.9** | 65.6 | 2067 | sword L2, bow L5, spirit_wolf L2, bomb | +bow, iron_arm x3, bow_split_arrow x2, bow_rapid_draw x2, +spirit_wolf, +bomb, spirit_wolf_savage_bite, sword_heavy_blade, fortune, haste | spirit_wolf 39%  sword 30%  bomb 16%  bow 15% |
| 13 | **81.9** | 80.6 | 2456 | sword L3, daggers L4, grave_totem L2, hammer L3 | sword_sharpened_edge, iron_arm x2, +daggers, sword_bloodletting, lucky_strike, daggers_quick_hands, +grave_totem, +hammer, grave_totem_twin_totems, hammer_staggering_strike x2, daggers_extended_reach, daggers_sharpened_blades | daggers 45%  sword 21%  hammer 20%  grave_totem 14% |
| 14 | **83.4** | 83.4 | 2501 | sword, daggers L4, spirit_wolf, magic_rod L2 | fortune, +daggers, iron_arm x3, daggers_quick_hands x2, keen_eye x3, daggers_extended_reach, +spirit_wolf, +magic_rod, magic_rod_overcharge | daggers 39%  spirit_wolf 24%  sword 20%  magic_rod 17% |
| 15 | **63.0** | 60.7 | 1890 | sword, hammer L4, bomb L4, ember_ring | +hammer, hammer_crushing_blow x2, +bomb, +ember_ring, fortune, bomb_blast_amplifier x2, bomb_demolitionist, iron_arm, hammer_staggering_strike, haste, forge:minefield, forge:earthshaker | hammer 40%  bomb 36%  sword 23%  ember_ring 1% |
| 16 | **78.9** | 79.4 | 2367 | sword L4, spirit_wolf, bow L4, daggers L3 | fortune x2, +spirit_wolf, sword_wide_cleave, +bow, +daggers, iron_arm, daggers_sharpened_blades, sword_bloodletting, bow_rapid_draw, daggers_quick_hands, bow_split_arrow, bow_piercing_arrow, sword_critical_edge | daggers 44%  spirit_wolf 25%  sword 18%  bow 13% |
| 17 | **67.2** | 64.6 | 2017 | sword L4, spirit_wolf L2, bomb, hammer L3 | +spirit_wolf, lucky_strike x2, keen_eye x2, spirit_wolf_swift, sword_critical_edge x2, fortune, sword_sharpened_edge, +bomb, +hammer, hammer_crushing_blow, hammer_executioner | spirit_wolf 30%  sword 26%  hammer 25%  bomb 20% |
| 18 | **81.2** | 77.3 | 2436 | sword L5, daggers L5, bomb, spirit_wolf | +daggers, +bomb, sword_sharpened_edge, daggers_weak_point, fortune, lucky_strike, sword_bloodletting, daggers_sharpened_blades, sword_crowd_cleaner x2, daggers_extended_reach x2, +spirit_wolf, haste | daggers 39%  spirit_wolf 25%  sword 21%  bomb 15% |
| 19 | **44.3** | 41.0 | 1328 | sword L3, ember_ring L3, bow L3, bomb L2 | sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge | sword 37%  bomb 34%  bow 27%  ember_ring 2% |
| 20 | **57.5** | 56.2 | 1725 | sword L5, grave_totem L3, magic_rod, daggers L3 | +grave_totem, keen_eye x2, grave_totem_long_watch, +magic_rod, sword_critical_edge x2, sword_wide_cleave, +daggers, daggers_extended_reach, sword_bloodletting, daggers_quick_hands, fortune, grave_totem_spectral_bolts | daggers 43%  sword 23%  magic_rod 20%  grave_totem 14% |
| 21 | **74.4** | 74.1 | 2233 | sword L2, bow L3, magic_rod L3, spirit_wolf L2 | +bow, haste, +magic_rod, iron_arm x2, sword_sharpened_edge, +spirit_wolf, bow_split_arrow, keen_eye x2, spirit_wolf_savage_bite, magic_rod_seeking, bow_crossfire, magic_rod_overcharge | spirit_wolf 36%  sword 25%  magic_rod 22%  bow 17% |
| 22 | **75.8** | 70.7 | 2273 | sword L3, bomb, magic_rod L3, spirit_wolf L2 | +bomb, sword_heavy_blade, haste, lucky_strike x3, +magic_rod, +spirit_wolf, spirit_wolf_swift, magic_rod_arcane_missiles x2, iron_arm x2, sword_crowd_cleaner | magic_rod 32%  spirit_wolf 26%  sword 26%  bomb 16% |
| 23 | **66.2** | 65.4 | 1987 | sword L3, daggers L4, magic_rod L4, ember_ring | +daggers, +magic_rod, daggers_weak_point, daggers_quick_hands, magic_rod_chain, +ember_ring, keen_eye, sword_sharpened_edge, magic_rod_seeking, lucky_strike, iron_arm, magic_rod_overcharge, daggers_marked_prey, sword_bloodletting | daggers 56%  sword 24%  magic_rod 19%  ember_ring 1% |
| 24 | **68.3** | 67.0 | 2049 | sword L3, bomb L2, bow L4, spirit_wolf L2 | +bomb, bomb_explosive_force, +bow, lucky_strike, keen_eye x3, bow_hunters_mark, +spirit_wolf, bow_piercing_arrow, sword_critical_edge, bow_rapid_draw, sword_bloodletting, spirit_wolf_swift | spirit_wolf 29%  bomb 27%  bow 22%  sword 21% |
| 25 | **52.2** | 45.3 | 1567 | sword L3, grave_totem L5, magic_rod, bomb | +grave_totem, grave_totem_quick_plant, grave_totem_spectral_bolts x2, +magic_rod, keen_eye, lucky_strike, sword_wide_cleave, fortune, +bomb, sword_bloodletting, grave_totem_long_watch, iron_arm, haste | sword 30%  magic_rod 26%  bomb 24%  grave_totem 21% |
| 26 | **47.8** | 41.3 | 1433 | sword L4, ember_ring, bomb L2, hammer L3 | sword_critical_edge x2, +ember_ring, haste x2, +bomb, +hammer, bomb_blast_amplifier, hammer_crushing_blow, iron_arm, hammer_heavy_impact, lucky_strike, keen_eye, sword_wide_cleave | sword 36%  hammer 35%  bomb 28%  ember_ring 1% |
| 27 | **73.5** | 70.0 | 2204 | sword L2, hammer L2, magic_rod, spirit_wolf | iron_arm x3, sword_wide_cleave, keen_eye x2, lucky_strike, haste x3, +hammer, +magic_rod, hammer_titans_grip, +spirit_wolf | sword 30%  spirit_wolf 27%  hammer 24%  magic_rod 19% |
| 28 | **54.3** | 49.1 | 1629 | sword L3, magic_rod L2, hammer L2, grave_totem | keen_eye x3, +magic_rod, iron_arm, magic_rod_overcharge, +hammer, +grave_totem, fortune, hammer_heavy_impact, haste x2, sword_heavy_blade, sword_bloodletting | sword 35%  magic_rod 29%  hammer 25%  grave_totem 11% |
| 29 | **106.5** | 111.7 | 3195 | sword L3, hammer L2, magic_rod L4, spirit_wolf L2 | iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack | spirit_wolf 33%  magic_rod 31%  sword 19%  hammer 17% |
| 30 | **78.3** | 74.6 | 2350 | sword L3, bomb L2, daggers L2, grave_totem | sword_sharpened_edge x2, lucky_strike, haste x3, +bomb, +daggers, bomb_blast_amplifier, iron_arm, keen_eye x2, +grave_totem, daggers_quick_hands | daggers 42%  sword 30%  bomb 20%  grave_totem 7% |

### Per source at level 15, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 33.3 |
| spirit_wolf | 13 | 24.4 |
| sword | 30 | 19.0 |
| hammer | 12 | 18.3 |
| magic_rod | 15 | 16.8 |
| bomb | 17 | 14.3 |
| bow | 8 | 12.1 |
| grave_totem | 7 | 7.9 |
| ember_ring | 7 | 0.7 |

## Level 20

30 builds — mean **86.3**, median **83.4**, spread 44.4 to 115.6 (**2.60x**).

- Weakest: sword L5, bow L5, ember_ring L4, bomb L2 + haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat.
- Strongest: sword L2, magic_rod L2, daggers L3, spirit_wolf L2 + haste x4, +magic_rod, +daggers, sword_sharpened_edge, magic_rod_seeking, lucky_strike x2, +spirit_wolf, fortune x2, iron_arm x2, spirit_wolf_pack, daggers_quick_hands, daggers_weak_point, keen_eye.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **108.1** | 109.4 | 3243 | sword L4, spirit_wolf L4, magic_rod L2, bow | sword_heavy_blade, sword_critical_edge x2, +spirit_wolf, lucky_strike, iron_arm x2, haste x3, fortune, spirit_wolf_savage_bite x3, +magic_rod, magic_rod_arcane_missiles, +bow, keen_eye x2 | spirit_wolf 37%  magic_rod 29%  sword 23%  bow 11% |
| 2 | **67.0** | 62.4 | 2011 | sword L4, hammer L5, bomb L2, grave_totem | keen_eye x4, +hammer, hammer_heavy_impact, lucky_strike, sword_critical_edge, iron_arm, fortune x2, hammer_crushing_blow x2, hammer_staggering_strike, +bomb, sword_sharpened_edge x2, bomb_demolition, +grave_totem | sword 32%  hammer 31%  bomb 28%  grave_totem 9% |
| 3 | **108.9** | 110.5 | 3266 | sword L6, daggers L4, bow L3 | keen_eye, +daggers, sword_wide_cleave x2, haste x3, fortune, +bow, daggers_quick_hands, sword_critical_edge x2, bow_heavy_draw, sword_sharpened_edge, bow_hunters_mark, iron_arm, forge:multishot, daggers_sharpened_blades, daggers_weak_point | bow 44%  daggers 36%  sword 20% |
| 4 | **65.9** | 60.4 | 1978 | sword L4, magic_rod L3, bow L3, ember_ring | fortune, keen_eye x3, lucky_strike, sword_heavy_blade, iron_arm x2, +magic_rod, magic_rod_arcane_missiles, +bow, bow_piercing_arrow x2, sword_bloodletting, +ember_ring, sword_wide_cleave, haste x2, magic_rod_seeking | magic_rod 48%  sword 33%  bow 18%  ember_ring 1% |
| 5 | **115.6** | 121.7 | 3467 | sword L2, magic_rod L2, daggers L3, spirit_wolf L2 | haste x4, +magic_rod, +daggers, sword_sharpened_edge, magic_rod_seeking, lucky_strike x2, +spirit_wolf, fortune x2, iron_arm x2, spirit_wolf_pack, daggers_quick_hands, daggers_weak_point, keen_eye | daggers 34%  spirit_wolf 32%  sword 21%  magic_rod 13% |
| 6 | **81.3** | 81.4 | 2438 | sword L5, daggers L2, grave_totem L5, bomb L3 | +daggers, iron_arm x2, +grave_totem, +bomb, daggers_quick_hands, fortune, grave_totem_long_watch x2, sword_sharpened_edge x2, grave_totem_spectral_bolts, bomb_blast_amplifier, haste x2, grave_totem_quick_plant, sword_bloodletting, sword_critical_edge, bomb_explosive_force | daggers 40%  sword 29%  bomb 18%  grave_totem 12% |
| 7 | **80.1** | 82.5 | 2404 | sword L3, grave_totem L5, hammer L3, bomb L4 | +grave_totem, grave_totem_twin_totems x2, iron_arm x2, +hammer, fortune x2, +bomb, grave_totem_spectral_bolts, bomb_explosive_force x2, grave_totem_long_watch, hammer_crushing_blow, sword_wide_cleave, sword_crowd_cleaner, hammer_executioner, forge:cluster_bomb, bomb_bigger_explosion | bomb 33%  hammer 24%  grave_totem 23%  sword 20% |
| 8 | **54.5** | 52.8 | 1636 | sword L5, grave_totem, bomb L3, bow | +grave_totem, +bomb, sword_wide_cleave, bomb_blast_amplifier, haste x3, +bow, iron_arm x3, keen_eye, sword_critical_edge, sword_bloodletting, sword_crowd_cleaner, lucky_strike x3, bomb_demolitionist | sword 39%  bomb 29%  bow 22%  grave_totem 11% |
| 9 | **82.8** | 76.1 | 2484 | sword L6, spirit_wolf, bomb L3, magic_rod L2 | +spirit_wolf, +bomb, sword_wide_cleave, sword_heavy_blade x2, fortune x3, sword_sharpened_edge x2, +magic_rod, iron_arm, magic_rod_chain, bomb_explosive_force, bomb_blast_amplifier, keen_eye x2, haste, forge:cluster_bomb | sword 37%  spirit_wolf 24%  bomb 22%  magic_rod 17% |
| 10 | **85.6** | 86.1 | 2569 | sword L3, bomb L3, magic_rod L4, spirit_wolf | +bomb, bomb_explosive_force, iron_arm, fortune, keen_eye x3, +magic_rod, magic_rod_seeking x3, haste x3, lucky_strike, sword_sharpened_edge, +spirit_wolf, bomb_blast_amplifier, sword_heavy_blade | sword 31%  bomb 28%  spirit_wolf 23%  magic_rod 18% |
| 11 | **67.4** | 65.2 | 2021 | sword L3, bow L5, hammer L2, grave_totem L2 | sword_sharpened_edge, +bow, +hammer, +grave_totem, fortune x3, bow_rapid_draw, haste x2, sword_wide_cleave, keen_eye x2, lucky_strike, bow_heavy_draw, hammer_heavy_impact, bow_piercing_arrow, grave_totem_twin_totems, bow_hunters_mark | bow 33%  sword 26%  hammer 23%  grave_totem 19% |
| 12 | **71.7** | 69.9 | 2152 | sword L5, hammer L5, bomb L4, ember_ring L3 | +hammer, iron_arm, +bomb, hammer_crushing_blow x2, sword_sharpened_edge x2, +ember_ring, bomb_demolition x2, sword_critical_edge, hammer_staggering_strike, bomb_blast_amplifier, ember_ring_wide_orbit x2, haste, hammer_titans_grip, sword_wide_cleave, forge:meteor_hammer | hammer 46%  sword 33%  bomb 21%  ember_ring 1% |
| 13 | **82.3** | 81.8 | 2469 | sword L3, daggers L4, hammer L5, ember_ring L3 | +daggers, daggers_quick_hands x3, +hammer, +ember_ring, ember_ring_ember_heat, hammer_crushing_blow x2, iron_arm x3, sword_critical_edge, keen_eye, hammer_heavy_impact, hammer_titans_grip, haste, sword_bloodletting, ember_ring_more_embers | daggers 48%  hammer 27%  sword 23%  ember_ring 1% |
| 14 | **95.4** | 96.5 | 2863 | sword L4, spirit_wolf, daggers L3, bow L4 | +spirit_wolf, sword_heavy_blade, lucky_strike x2, +daggers, +bow, bow_piercing_arrow, haste, iron_arm x2, fortune x2, keen_eye, sword_bloodletting, sword_sharpened_edge, daggers_sharpened_blades, daggers_weak_point, bow_rapid_draw x2 | daggers 39%  sword 26%  spirit_wolf 21%  bow 14% |
| 15 | **113.3** | 111.8 | 3398 | sword L5, magic_rod L2, bomb L5, spirit_wolf L2 | +magic_rod, +bomb, sword_heavy_blade, iron_arm x2, +spirit_wolf, bomb_blast_amplifier, bomb_explosive_force x2, magic_rod_overcharge, forge:cluster_bomb, bomb_bigger_explosion, spirit_wolf_pack, haste, sword_wide_cleave, keen_eye, sword_critical_edge x2, lucky_strike | bomb 37%  spirit_wolf 31%  sword 19%  magic_rod 12% |
| 16 | **107.4** | 113.4 | 3222 | sword L2, magic_rod L4, bomb L6, spirit_wolf L4 | +magic_rod, +bomb, iron_arm, magic_rod_seeking x2, +spirit_wolf, lucky_strike x2, bomb_bigger_explosion, bomb_demolitionist x2, bomb_explosive_force x2, magic_rod_chain, keen_eye, spirit_wolf_pack, spirit_wolf_savage_bite x2, sword_sharpened_edge | spirit_wolf 55%  bomb 17%  sword 16%  magic_rod 12% |
| 17 | **100.2** | 92.7 | 3007 | sword L6, daggers L4, bomb L3, spirit_wolf | +daggers, sword_wide_cleave, sword_sharpened_edge x2, daggers_extended_reach, fortune x2, sword_heavy_blade, iron_arm, keen_eye x2, sword_critical_edge, +bomb, bomb_blast_amplifier, daggers_quick_hands, daggers_sharpened_blades, bomb_explosive_force, haste, +spirit_wolf | daggers 36%  sword 23%  bomb 21%  spirit_wolf 20% |
| 18 | **73.3** | 69.7 | 2200 | sword L4, daggers L4, hammer L8, grave_totem L2 | +daggers, keen_eye, daggers_quick_hands, +hammer, hammer_executioner x3, sword_wide_cleave, hammer_heavy_impact, hammer_crushing_blow, hammer_staggering_strike x2, sword_critical_edge x2, forge:earthshaker, daggers_weak_point, +grave_totem, grave_totem_twin_totems, daggers_sharpened_blades | daggers 40%  hammer 25%  sword 20%  grave_totem 15% |
| 19 | **110.1** | 107.4 | 3302 | sword L6, spirit_wolf L2, daggers L4, hammer L3 | sword_heavy_blade, +spirit_wolf, +daggers, +hammer, sword_critical_edge, iron_arm, hammer_crushing_blow, hammer_titans_grip, haste x3, sword_wide_cleave, sword_sharpened_edge x2, daggers_quick_hands, daggers_extended_reach, keen_eye, daggers_sharpened_blades, spirit_wolf_savage_bite | daggers 34%  sword 26%  spirit_wolf 24%  hammer 15% |
| 20 | **53.2** | 52.0 | 1596 | sword L6, hammer L3, magic_rod L4, ember_ring L2 | +hammer, sword_heavy_blade, sword_sharpened_edge x2, +magic_rod, +ember_ring, lucky_strike x2, ember_ring_wide_orbit, hammer_staggering_strike, keen_eye x2, magic_rod_seeking, hammer_titans_grip, haste, magic_rod_chain, magic_rod_overcharge, sword_wide_cleave, sword_critical_edge | sword 41%  magic_rod 30%  hammer 29%  ember_ring 1% |
| 21 | **113.5** | 117.5 | 3406 | sword L3, magic_rod L2, spirit_wolf L5, daggers L3 | sword_bloodletting, iron_arm x2, fortune x2, +magic_rod, +spirit_wolf, haste, spirit_wolf_swift x2, spirit_wolf_savage_bite, sword_sharpened_edge, +daggers, keen_eye x2, daggers_extended_reach, daggers_weak_point, magic_rod_overcharge, spirit_wolf_pack | spirit_wolf 43%  daggers 27%  sword 18%  magic_rod 13% |
| 22 | **67.9** | 66.0 | 2038 | sword L4, bomb L4, ember_ring L4, magic_rod L5 | +bomb, +ember_ring, sword_critical_edge, bomb_explosive_force x2, +magic_rod, ember_ring_more_embers x2, magic_rod_seeking, magic_rod_chain, ember_ring_ember_heat, keen_eye x2, magic_rod_arcane_missiles, magic_rod_overcharge, bomb_bigger_explosion, sword_bloodletting, lucky_strike, sword_sharpened_edge | magic_rod 40%  bomb 32%  sword 26%  ember_ring 2% |
| 23 | **114.8** | 117.1 | 3443 | sword L4, spirit_wolf L2, magic_rod L2, daggers L3 | +spirit_wolf, haste x2, spirit_wolf_savage_bite, fortune x3, +magic_rod, sword_sharpened_edge x3, +daggers, keen_eye x2, iron_arm, daggers_sharpened_blades, lucky_strike, daggers_marked_prey, magic_rod_seeking | daggers 40%  spirit_wolf 23%  sword 23%  magic_rod 14% |
| 24 | **107.7** | 113.6 | 3231 | sword L2, spirit_wolf L5, magic_rod L3, daggers | +spirit_wolf, fortune, spirit_wolf_savage_bite, keen_eye x3, +magic_rod, iron_arm x2, +daggers, lucky_strike x3, spirit_wolf_pack x2, spirit_wolf_swift, magic_rod_overcharge, sword_bloodletting, magic_rod_seeking | spirit_wolf 44%  daggers 26%  sword 15%  magic_rod 15% |
| 25 | **92.3** | 92.0 | 2770 | sword L3, ember_ring L2, hammer L4, daggers L5 | +ember_ring, +hammer, hammer_titans_grip, iron_arm x3, +daggers, daggers_sharpened_blades, sword_sharpened_edge, daggers_extended_reach, sword_wide_cleave, hammer_crushing_blow x2, keen_eye x2, ember_ring_ember_heat, daggers_blood_in_the_water, daggers_quick_hands, haste | daggers 53%  hammer 24%  sword 22%  ember_ring 1% |
| 26 | **88.4** | 87.2 | 2653 | sword L5, daggers L5, ember_ring L3, hammer L4 | +daggers, daggers_quick_hands x3, +ember_ring, sword_heavy_blade x2, daggers_sharpened_blades, ember_ring_wide_orbit, +hammer, sword_bloodletting, hammer_executioner, iron_arm x2, hammer_crushing_blow x2, sword_critical_edge, keen_eye, ember_ring_more_embers | daggers 46%  sword 30%  hammer 24%  ember_ring 1% |
| 27 | **44.4** | 41.5 | 1331 | sword L5, bow L5, ember_ring L4, bomb L2 | haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat | sword 46%  bomb 28%  bow 24%  ember_ring 2% |
| 28 | **76.5** | 75.6 | 2295 | sword L5, ember_ring L4, bomb L5, hammer | sword_sharpened_edge x2, +ember_ring, +bomb, bomb_explosive_force, ember_ring_wide_orbit, fortune, bomb_blast_amplifier, sword_critical_edge, forge:greatsword, forge:minefield, ember_ring_more_embers, bomb_demolitionist, ember_ring_ember_heat, sword_wide_cleave, keen_eye, haste, bomb_bigger_explosion, +hammer | sword 44%  bomb 38%  hammer 16%  ember_ring 1% |
| 29 | **84.0** | 76.1 | 2519 | sword L2, hammer L6, bow L2, spirit_wolf | +hammer, iron_arm x2, +bow, keen_eye x3, haste x3, hammer_crushing_blow x4, +spirit_wolf, lucky_strike, hammer_heavy_impact, bow_piercing_arrow, sword_critical_edge | hammer 38%  spirit_wolf 24%  sword 22%  bow 16% |
| 30 | **76.4** | 73.9 | 2292 | sword L3, magic_rod L3, bomb L4, grave_totem L4 | +magic_rod, +bomb, +grave_totem, bomb_explosive_force, sword_crowd_cleaner, magic_rod_chain, iron_arm x3, keen_eye x2, grave_totem_twin_totems, bomb_blast_amplifier, grave_totem_spectral_bolts, bomb_bigger_explosion, magic_rod_arcane_missiles, grave_totem_quick_plant, sword_wide_cleave, haste | magic_rod 32%  grave_totem 24%  sword 22%  bomb 21% |

### Per source at level 20, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 13 | 37.3 |
| spirit_wolf | 13 | 32.3 |
| sword | 30 | 22.1 |
| bomb | 14 | 20.9 |
| hammer | 12 | 20.8 |
| magic_rod | 13 | 19.0 |
| bow | 8 | 17.8 |
| grave_totem | 7 | 11.8 |
| ember_ring | 9 | 0.9 |

## Level 25

30 builds — mean **85.0**, median **84.7**, spread 39.4 to 143.4 (**3.64x**).

- Weakest: sword L6, hammer L7, magic_rod L5, ember_ring + sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles.
- Strongest: sword L6, magic_rod L4, spirit_wolf L4, bow L6 + +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **105.4** | 102.5 | 3163 | sword L4, bow L4, daggers L7, grave_totem L2 | lucky_strike, +bow, sword_sharpened_edge x2, +daggers, daggers_weak_point x2, iron_arm x3, keen_eye x3, sword_wide_cleave, daggers_blood_in_the_water, bow_rapid_draw x2, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, daggers_quick_hands, fortune, bow_hunters_mark | daggers 57%  sword 21%  bow 16%  grave_totem 6% |
| 2 | **116.0** | 118.0 | 3479 | sword L2, daggers L3, spirit_wolf L2, bomb L5 | haste x5, lucky_strike, +daggers, iron_arm x3, daggers_quick_hands, daggers_blood_in_the_water, +spirit_wolf, +bomb, bomb_blast_amplifier x2, fortune x2, sword_bloodletting, bomb_bigger_explosion x2, keen_eye x2, spirit_wolf_swift | daggers 48%  sword 18%  spirit_wolf 17%  bomb 17% |
| 3 | **96.8** | 100.0 | 2903 | sword L3, bomb L5, spirit_wolf L3, magic_rod L6 | lucky_strike, +bomb, fortune, +spirit_wolf, sword_bloodletting, bomb_explosive_force x3, haste x2, keen_eye x3, spirit_wolf_savage_bite, +magic_rod, iron_arm, magic_rod_overcharge x2, magic_rod_seeking x2, magic_rod_chain, bomb_bigger_explosion, sword_sharpened_edge, spirit_wolf_swift | bomb 34%  spirit_wolf 28%  sword 20%  magic_rod 19% |
| 4 | **143.4** | 143.4 | 4302 | sword L6, magic_rod L4, spirit_wolf L4, bow L6 | +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm | magic_rod 37%  spirit_wolf 33%  sword 16%  bow 15% |
| 5 | **88.8** | 93.6 | 2664 | sword L3, magic_rod L6, spirit_wolf L3, bow | +magic_rod, keen_eye x2, fortune x2, sword_wide_cleave, magic_rod_seeking x4, +spirit_wolf, iron_arm x2, haste x4, +bow, sword_critical_edge, spirit_wolf_pack x2, magic_rod_chain, lucky_strike x2 | spirit_wolf 41%  sword 25%  magic_rod 18%  bow 16% |
| 6 | **78.3** | 75.0 | 2350 | sword L7, magic_rod L4, grave_totem L4, bow | +magic_rod, magic_rod_arcane_missiles, +grave_totem, sword_heavy_blade x2, keen_eye x2, grave_totem_quick_plant x2, iron_arm x4, +bow, haste, sword_sharpened_edge x2, magic_rod_chain, fortune, forge:whirlwind, whirlwind_cyclone, magic_rod_seeking, grave_totem_long_watch, sword_bloodletting | sword 46%  magic_rod 33%  bow 14%  grave_totem 8% |
| 7 | **99.3** | 94.6 | 2979 | sword L3, ember_ring L2, daggers L7, hammer L5 | lucky_strike x2, +ember_ring, +daggers, +hammer, daggers_blood_in_the_water, haste x2, sword_critical_edge, daggers_extended_reach x2, keen_eye, ember_ring_ember_heat, iron_arm x3, hammer_titans_grip, daggers_quick_hands x2, daggers_sharpened_blades, sword_bloodletting, hammer_executioner, hammer_crushing_blow, hammer_heavy_impact | daggers 61%  hammer 19%  sword 19%  ember_ring 1% |
| 8 | **91.9** | 93.4 | 2756 | sword L6, hammer L2, ember_ring L2, magic_rod L4 | fortune x5, iron_arm x3, +hammer, +ember_ring, +magic_rod, magic_rod_arcane_missiles, keen_eye x2, sword_sharpened_edge x3, hammer_staggering_strike, sword_heavy_blade, magic_rod_seeking, sword_critical_edge, forge:greatsword, magic_rod_overcharge, ember_ring_wide_orbit | sword 49%  magic_rod 30%  hammer 21%  ember_ring 1% |
| 9 | **56.4** | 54.2 | 1693 | sword L3, bow L4, ember_ring L5, bomb L5 | +bow, iron_arm x3, haste x3, +ember_ring, +bomb, ember_ring_ember_heat x2, fortune, bomb_blast_amplifier x2, sword_critical_edge, ember_ring_more_embers, bow_hunters_mark x2, bomb_explosive_force, ember_ring_wide_orbit, bomb_demolitionist, keen_eye, sword_crowd_cleaner, bow_rapid_draw | sword 37%  bomb 31%  bow 30%  ember_ring 2% |
| 10 | **101.4** | 98.5 | 3041 | sword L5, bomb L4, daggers L5, ember_ring L3 | +bomb, bomb_blast_amplifier, iron_arm, +daggers, daggers_blood_in_the_water, sword_heavy_blade x2, keen_eye x3, lucky_strike, daggers_weak_point, fortune, haste x2, sword_crowd_cleaner, bomb_bigger_explosion, +ember_ring, daggers_quick_hands, ember_ring_more_embers, daggers_sharpened_blades, bomb_explosive_force, ember_ring_wide_orbit, sword_sharpened_edge | daggers 47%  sword 30%  bomb 22%  ember_ring 1% |
| 11 | **39.4** | 35.6 | 1182 | sword L6, hammer L7, magic_rod L5, ember_ring | sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles | sword 62%  hammer 35%  magic_rod 2%  ember_ring 2% |
| 12 | **101.3** | 95.3 | 3039 | sword L5, spirit_wolf L3, magic_rod L5, bomb L4 | +spirit_wolf, +magic_rod, +bomb, iron_arm x3, magic_rod_arcane_missiles, sword_wide_cleave, bomb_explosive_force x2, lucky_strike x2, magic_rod_seeking x3, keen_eye x2, sword_crowd_cleaner, spirit_wolf_savage_bite x2, sword_critical_edge, bomb_blast_amplifier, sword_bloodletting, haste | spirit_wolf 33%  magic_rod 26%  bomb 21%  sword 20% |
| 13 | **48.7** | 44.0 | 1461 | sword L3, ember_ring L6, bow L7, magic_rod L3 | +ember_ring, ember_ring_ember_heat x3, fortune x2, lucky_strike x2, ember_ring_more_embers, +bow, bow_piercing_arrow x2, +magic_rod, iron_arm, haste, bow_split_arrow, bow_rapid_draw, magic_rod_chain, ember_ring_wide_orbit, magic_rod_seeking, bow_heavy_draw, sword_wide_cleave x2, bow_crossfire | sword 33%  bow 33%  magic_rod 30%  ember_ring 3% |
| 14 | **72.7** | 64.4 | 2180 | sword L9, hammer L2, bomb L5, ember_ring | +hammer, fortune, +bomb, bomb_explosive_force x2, sword_sharpened_edge x2, sword_wide_cleave x3, +ember_ring, keen_eye x2, bomb_bigger_explosion, haste, sword_critical_edge, iron_arm x3, lucky_strike, hammer_crushing_blow, sword_heavy_blade, bomb_blast_amplifier, sword_crowd_cleaner | sword 41%  bomb 30%  hammer 28%  ember_ring 1% |
| 15 | **58.8** | 57.9 | 1764 | sword L3, hammer L9, bomb L7, ember_ring L2 | +hammer, +bomb, bomb_bigger_explosion x2, haste x3, bomb_demolitionist, +ember_ring, sword_heavy_blade, hammer_heavy_impact x3, forge:earthshaker, hammer_staggering_strike, bomb_blast_amplifier x2, hammer_crushing_blow x2, ember_ring_wide_orbit, sword_wide_cleave, bomb_explosive_force, hammer_titans_grip, earthshaker_aftershock | hammer 40%  sword 31%  bomb 28%  ember_ring 1% |
| 16 | **68.9** | 63.0 | 2067 | sword L6, magic_rod L3, bomb L3, grave_totem L7 | sword_bloodletting, +magic_rod, +bomb, +grave_totem, grave_totem_spectral_bolts x2, magic_rod_chain, fortune, keen_eye x2, iron_arm, grave_totem_long_watch x3, sword_critical_edge, sword_sharpened_edge, grave_totem_quick_plant, lucky_strike, bomb_explosive_force, sword_heavy_blade, bomb_demolitionist, haste, sword_wide_cleave, magic_rod_seeking | sword 33%  bomb 27%  grave_totem 21%  magic_rod 19% |
| 17 | **87.2** | 81.6 | 2615 | sword L4, magic_rod L3, bomb L4, grave_totem L6 | +magic_rod, haste, +bomb, magic_rod_chain, bomb_blast_amplifier, fortune x2, +grave_totem, grave_totem_quick_plant, iron_arm, sword_critical_edge x2, grave_totem_twin_totems x3, keen_eye x3, bomb_demolitionist, lucky_strike, grave_totem_spectral_bolts, sword_sharpened_edge, bomb_explosive_force, magic_rod_arcane_missiles | magic_rod 33%  sword 25%  grave_totem 21%  bomb 21% |
| 18 | **71.9** | 67.8 | 2156 | sword L8, magic_rod L3, hammer L4, grave_totem L2 | haste x4, keen_eye x2, +magic_rod, +hammer, hammer_heavy_impact x2, sword_bloodletting x2, fortune, sword_sharpened_edge x4, hammer_titans_grip, iron_arm, +grave_totem, magic_rod_seeking x2, grave_totem_quick_plant, sword_critical_edge | sword 50%  magic_rod 20%  hammer 20%  grave_totem 9% |
| 19 | **55.2** | 48.8 | 1656 | sword L5, bomb L6, ember_ring L2, magic_rod L3 | +bomb, fortune x2, keen_eye x2, +ember_ring, lucky_strike x2, bomb_blast_amplifier, bomb_bigger_explosion x2, haste, +magic_rod, sword_wide_cleave x2, sword_bloodletting x2, iron_arm x2, magic_rod_overcharge, bomb_explosive_force x2, ember_ring_wide_orbit, magic_rod_seeking | bomb 39%  sword 30%  magic_rod 30%  ember_ring 1% |
| 20 | **117.0** | 118.3 | 3511 | sword L4, magic_rod L2, hammer L6, spirit_wolf L3 | haste x2, sword_sharpened_edge x3, +magic_rod, +hammer, keen_eye x3, hammer_staggering_strike x2, hammer_titans_grip, iron_arm x3, lucky_strike, hammer_crushing_blow, fortune, +spirit_wolf, magic_rod_chain, spirit_wolf_pack, hammer_executioner, spirit_wolf_savage_bite | spirit_wolf 41%  sword 28%  hammer 19%  magic_rod 12% |
| 21 | **117.9** | 118.7 | 3537 | sword L4, daggers L5, bow L4, grave_totem L5 | +daggers, fortune x2, +bow, keen_eye x2, bow_rapid_draw, sword_wide_cleave, bow_hunters_mark, +grave_totem, daggers_sharpened_blades x3, sword_sharpened_edge, forge:greatsword, sword_heavy_blade, grave_totem_twin_totems x2, daggers_quick_hands, bow_split_arrow, grave_totem_spectral_bolts, haste x2, grave_totem_quick_plant | daggers 41%  sword 29%  grave_totem 17%  bow 14% |
| 22 | **93.8** | 91.6 | 2814 | sword L5, grave_totem L5, daggers L3, bomb L3 | haste x3, sword_wide_cleave x2, +grave_totem, +daggers, +bomb, grave_totem_long_watch x2, iron_arm x2, fortune x2, keen_eye, daggers_quick_hands, grave_totem_quick_plant x2, sword_critical_edge, daggers_sharpened_blades, sword_sharpened_edge, bomb_demolitionist, lucky_strike, bomb_explosive_force | daggers 48%  sword 24%  bomb 21%  grave_totem 7% |
| 23 | **120.5** | 111.3 | 3614 | sword L6, grave_totem L2, daggers L4, magic_rod L5 | +grave_totem, keen_eye x3, +daggers, +magic_rod, magic_rod_chain, grave_totem_spectral_bolts, sword_sharpened_edge x3, daggers_sharpened_blades, haste x3, lucky_strike, daggers_blood_in_the_water, daggers_extended_reach, magic_rod_seeking x2, sword_critical_edge, forge:greatsword, magic_rod_arcane_missiles, sword_bloodletting | daggers 35%  sword 31%  magic_rod 27%  grave_totem 7% |
| 24 | **82.3** | 79.3 | 2469 | sword L2, magic_rod L3, hammer L7, spirit_wolf L4 | keen_eye x2, +magic_rod, lucky_strike x3, +hammer, +spirit_wolf, iron_arm x2, hammer_crushing_blow, fortune, haste, magic_rod_overcharge, spirit_wolf_swift x2, hammer_heavy_impact x2, hammer_titans_grip x2, spirit_wolf_savage_bite, hammer_executioner, sword_sharpened_edge, magic_rod_seeking | spirit_wolf 32%  sword 26%  hammer 23%  magic_rod 18% |
| 25 | **77.4** | 72.3 | 2323 | sword L6, magic_rod L4, hammer L5, grave_totem L2 | keen_eye x4, sword_sharpened_edge x4, +magic_rod, iron_arm x2, +hammer, sword_critical_edge, hammer_heavy_impact x2, haste, hammer_crushing_blow x2, fortune, magic_rod_overcharge x2, magic_rod_chain, +grave_totem, grave_totem_quick_plant | sword 43%  hammer 27%  magic_rod 21%  grave_totem 8% |
| 26 | **63.1** | 55.6 | 1892 | sword L6, bow L2, bomb L3, grave_totem L3 | haste x2, sword_wide_cleave x2, +bow, +bomb, sword_crowd_cleaner x2, fortune x3, lucky_strike x2, +grave_totem, grave_totem_spectral_bolts, bomb_explosive_force, bomb_bigger_explosion, keen_eye x4, bow_split_arrow, grave_totem_long_watch, sword_heavy_blade | bomb 33%  sword 32%  bow 22%  grave_totem 13% |
| 27 | **64.6** | 63.1 | 1937 | sword L4, ember_ring L5, magic_rod L5, hammer L6 | +ember_ring, +magic_rod, ember_ring_more_embers, fortune x3, magic_rod_arcane_missiles x2, keen_eye x2, +hammer, hammer_crushing_blow x3, magic_rod_seeking x2, ember_ring_wide_orbit x2, hammer_heavy_impact, ember_ring_ember_heat, sword_wide_cleave, sword_critical_edge, hammer_staggering_strike, sword_sharpened_edge | magic_rod 41%  hammer 33%  sword 25%  ember_ring 2% |
| 28 | **95.5** | 90.3 | 2864 | sword L7, bow L4, daggers, spirit_wolf L3 | lucky_strike x2, fortune x3, sword_wide_cleave x2, sword_sharpened_edge x2, +bow, +daggers, bow_hunters_mark x2, keen_eye, +spirit_wolf, iron_arm x4, sword_heavy_blade, spirit_wolf_swift x2, bow_piercing_arrow, sword_critical_edge | daggers 33%  sword 31%  spirit_wolf 21%  bow 15% |
| 29 | **62.8** | 58.1 | 1883 | sword L5, magic_rod L4, hammer L6, grave_totem L3 | sword_critical_edge, +magic_rod, sword_bloodletting, +hammer, sword_wide_cleave, magic_rod_overcharge, haste x3, hammer_titans_grip, lucky_strike, magic_rod_seeking x2, sword_sharpened_edge, hammer_staggering_strike, iron_arm x2, +grave_totem, grave_totem_quick_plant x2, hammer_executioner x2, hammer_heavy_impact, keen_eye | sword 40%  hammer 27%  magic_rod 23%  grave_totem 10% |
| 30 | **73.0** | 73.3 | 2191 | sword L9, grave_totem, bow L4, magic_rod L3 | iron_arm, sword_sharpened_edge x2, +grave_totem, +bow, sword_critical_edge x4, +magic_rod, lucky_strike, magic_rod_overcharge x2, sword_wide_cleave, haste x4, sword_bloodletting, bow_rapid_draw, keen_eye, fortune, bow_piercing_arrow, bow_crossfire | sword 39%  magic_rod 30%  bow 22%  grave_totem 8% |

### Per source at level 25, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 48.8 |
| spirit_wolf | 8 | 32.3 |
| sword | 30 | 25.5 |
| bomb | 12 | 20.9 |
| magic_rod | 19 | 20.8 |
| hammer | 11 | 19.1 |
| bow | 10 | 15.6 |
| grave_totem | 12 | 9.5 |
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
