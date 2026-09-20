# DPS report — 2026-09-19 — weapon damage x1.2

30 builds at each of levels 1, 5, 10, 15, 20, 25, measured against the training dummy, 30 s each, seed `919`, commit `00f4965`, **every weapon's base damage x1.2**.

A what-if, not the shipped numbers: the bench multiplied the base `damage` of every weapon and every Forge damage override before the first run booted. The flat damage a weapon blessing adds is not scaled; percent and multiplicative layers scale with the base on their own. `data/weapons/*.json` is unchanged. With the same seed the builds are identical to the baseline report's, row for row, so the two can be compared build by build.

Regenerate with:

```bash
python -m tools.benchmarks.dps_bench --levels 1,5,10,15,20,25 --runs 30 --seconds 30 --seed 919 --damage-scale 1.2 --markdown documentation/dps_calcs/dps_report_2026-09-19_damage120.md
```

## How a build is made

Each row is a fresh developer run on the empty arena with `aegis`. The hero keeps the starter weapon and then takes **N-1 level-up picks** for level N, each through the real offering: three cards rolled at the data's weights from what the hero can take right now — weapon grants while a slot is open, blessing levels for what is held, summons, and Forge cards once a weapon carries two blessing levels — and **one taken at random**. That is an average player's build at that level, not a planned one.

Blessings with no combat advantage are removed from the pool before every roll (owner, 2026-09-19), so each pick is a damage pick: a stat blessing stays only if it moves melee or ranged damage, attack speed, crit chance or luck. No chest items, potions or meta-upgrades. The hero stands 16 px from the dummy — inside the shortest melee reach in the roster — and every weapon fires on its own cadence.

## Summary across levels

| level | builds | mean dps | median | p25 | p75 | min | max | std dev |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 30 | **15.0** | **15.0** | 15.0 | 15.0 | 15.0 | 15.0 | 0.0 |
| 5 | 30 | **39.9** | **40.3** | 31.4 | 47.0 | 16.8 | 78.2 | 13.7 |
| 10 | 30 | **65.2** | **68.4** | 52.0 | 76.2 | 42.1 | 92.2 | 15.4 |
| 15 | 30 | **79.7** | **79.9** | 68.6 | 89.5 | 52.4 | 126.0 | 16.6 |
| 20 | 30 | **100.5** | **97.5** | 83.6 | 123.8 | 52.0 | 137.9 | 22.9 |
| 25 | 30 | **98.7** | **99.0** | 76.1 | 116.1 | 44.4 | 165.9 | 28.0 |

`p25`/`p75` are the quartiles: half of the builds at that level sit between them. `min`..`max` is the whole spread; the standard deviation is over the builds measured.

## Level 1

30 builds — mean **15.0**, median **15.0**, spread 15.0 to 15.0 (**1.00x**).

- Weakest: sword + -.
- Strongest: sword + -.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 2 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 3 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 4 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 5 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 6 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 7 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 8 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 9 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 10 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 11 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 12 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 13 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 14 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 15 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 16 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 17 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 18 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 19 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 20 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 21 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 22 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 23 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 24 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 25 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 26 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 27 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 28 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 29 | **15.0** | 14.4 | 450 | sword | - | sword 100% |
| 30 | **15.0** | 14.4 | 450 | sword | - | sword 100% |

### Per source at level 1, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| sword | 30 | 15.0 |

## Level 5

30 builds — mean **39.9**, median **40.3**, spread 16.8 to 78.2 (**4.65x**).

- Weakest: sword L2 + lucky_strike, keen_eye x2, sword_wide_cleave.
- Strongest: sword, daggers, spirit_wolf, bow + +daggers, +spirit_wolf, +bow, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **41.6** | 40.3 | 1249 | sword L2, daggers, ember_ring | sword_wide_cleave, keen_eye, +daggers, +ember_ring | daggers 62%  sword 36%  ember_ring 2% |
| 2 | **16.8** | 16.2 | 504 | sword L2 | lucky_strike, keen_eye x2, sword_wide_cleave | sword 100% |
| 3 | **40.2** | 40.0 | 1206 | sword, spirit_wolf | keen_eye x2, iron_arm, +spirit_wolf | spirit_wolf 60%  sword 40% |
| 4 | **25.0** | 23.9 | 749 | sword L2, grave_totem L2 | fortune, +grave_totem, grave_totem_quick_plant, sword_critical_edge | sword 70%  grave_totem 30% |
| 5 | **46.2** | 44.4 | 1386 | sword, bomb, hammer L2 | +bomb, lucky_strike, +hammer, hammer_heavy_impact | sword 35%  hammer 35%  bomb 30% |
| 6 | **18.8** | 19.4 | 564 | sword L3 | sword_critical_edge x2, iron_arm, keen_eye | sword 100% |
| 7 | **54.2** | 52.8 | 1627 | sword, daggers L2, bow | +daggers, keen_eye, +bow, daggers_quick_hands | daggers 52%  sword 28%  bow 20% |
| 8 | **46.1** | 45.4 | 1382 | sword L2, magic_rod, hammer | +magic_rod, keen_eye, +hammer, sword_critical_edge | sword 39%  hammer 33%  magic_rod 28% |
| 9 | **34.1** | 35.4 | 1024 | sword, hammer L2 | haste, keen_eye, +hammer, hammer_crushing_blow | hammer 53%  sword 47% |
| 10 | **41.6** | 37.4 | 1247 | sword, hammer L2, grave_totem | +hammer, lucky_strike, hammer_staggering_strike, +grave_totem | hammer 44%  sword 39%  grave_totem 17% |
| 11 | **42.2** | 37.4 | 1265 | sword, hammer, grave_totem | lucky_strike, +hammer, +grave_totem, fortune | hammer 44%  sword 40%  grave_totem 17% |
| 12 | **44.7** | 44.4 | 1342 | sword, magic_rod, hammer | +magic_rod, fortune, +hammer, haste | sword 38%  hammer 34%  magic_rod 29% |
| 13 | **34.6** | 32.4 | 1037 | sword, hammer L3 | lucky_strike, +hammer, hammer_heavy_impact x2 | hammer 53%  sword 47% |
| 14 | **40.3** | 39.7 | 1209 | sword, bomb, bow | keen_eye, +bomb, +bow, fortune | sword 39%  bomb 35%  bow 27% |
| 15 | **58.4** | 60.5 | 1753 | sword L2, bow, daggers | sword_critical_edge, haste, +bow, +daggers | daggers 49%  sword 33%  bow 18% |
| 16 | **47.2** | 47.6 | 1417 | sword L2, magic_rod, hammer | iron_arm, sword_sharpened_edge, +magic_rod, +hammer | sword 40%  hammer 35%  magic_rod 25% |
| 17 | **32.2** | 31.7 | 967 | sword L2, ember_ring, bomb | keen_eye, +ember_ring, +bomb, sword_heavy_blade | sword 55%  bomb 43%  ember_ring 2% |
| 18 | **21.0** | 21.0 | 631 | sword L2, ember_ring | sword_sharpened_edge, lucky_strike x2, +ember_ring | sword 97%  ember_ring 3% |
| 19 | **19.5** | 19.4 | 585 | sword, ember_ring | fortune, +ember_ring, iron_arm, lucky_strike | sword 96%  ember_ring 4% |
| 20 | **32.4** | 29.0 | 972 | sword L2, bow, grave_totem | +bow, +grave_totem, fortune, sword_bloodletting | sword 46%  bow 32%  grave_totem 22% |
| 21 | **31.2** | 29.8 | 935 | sword L2, magic_rod, ember_ring | +magic_rod, sword_sharpened_edge, keen_eye, +ember_ring | sword 56%  magic_rod 42%  ember_ring 2% |
| 22 | **55.4** | 56.2 | 1662 | sword L2, spirit_wolf, bomb | +spirit_wolf, +bomb, sword_sharpened_edge, keen_eye | spirit_wolf 43%  sword 32%  bomb 25% |
| 23 | **49.4** | 48.4 | 1481 | sword L3, daggers | iron_arm, +daggers, sword_sharpened_edge, sword_heavy_blade | daggers 57%  sword 43% |
| 24 | **30.5** | 28.8 | 916 | sword L2, ember_ring L2, magic_rod | +ember_ring, sword_heavy_blade, +magic_rod, ember_ring_ember_heat | sword 58%  magic_rod 39%  ember_ring 3% |
| 25 | **29.3** | 27.6 | 880 | sword, ember_ring, magic_rod | +ember_ring, fortune, +magic_rod, iron_arm | sword 55%  magic_rod 42%  ember_ring 2% |
| 26 | **56.9** | 55.5 | 1707 | sword, daggers L2, bow | iron_arm, +daggers, +bow, daggers_quick_hands | daggers 54%  sword 28%  bow 18% |
| 27 | **78.2** | 77.6 | 2346 | sword, daggers, spirit_wolf, bow | +daggers, +spirit_wolf, +bow, iron_arm | daggers 36%  spirit_wolf 31%  sword 21%  bow 13% |
| 28 | **59.3** | 58.7 | 1778 | sword, ember_ring, daggers L2, hammer | +ember_ring, +daggers, +hammer, daggers_quick_hands | daggers 48%  hammer 26%  sword 25%  ember_ring 1% |
| 29 | **37.1** | 37.2 | 1114 | sword L3, hammer | sword_heavy_blade x2, +hammer, fortune | sword 59%  hammer 41% |
| 30 | **32.7** | 31.9 | 982 | sword L2, magic_rod | keen_eye, haste, sword_sharpened_edge, +magic_rod | sword 58%  magic_rod 42% |

### Per source at level 5, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 7 | 28.3 |
| spirit_wolf | 3 | 24.0 |
| sword | 30 | 17.3 |
| hammer | 10 | 16.6 |
| bomb | 4 | 13.9 |
| magic_rod | 7 | 12.7 |
| bow | 6 | 10.5 |
| grave_totem | 4 | 7.1 |
| ember_ring | 8 | 0.7 |

## Level 10

30 builds — mean **65.2**, median **68.4**, spread 42.1 to 92.2 (**2.19x**).

- Weakest: sword L4, bomb + lucky_strike x2, keen_eye, iron_arm, sword_sharpened_edge x2, +bomb, sword_critical_edge, fortune.
- Strongest: sword, daggers L3, bow L2, spirit_wolf + iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **68.0** | 65.5 | 2039 | sword, daggers L2, bow L2, ember_ring | +daggers, +bow, iron_arm x2, bow_rapid_draw, keen_eye, haste, daggers_quick_hands, +ember_ring | daggers 53%  sword 28%  bow 18%  ember_ring 1% |
| 2 | **68.8** | 68.5 | 2064 | sword, magic_rod, bow L3, spirit_wolf | +magic_rod, +bow, +spirit_wolf, bow_rapid_draw x2, iron_arm x2, fortune, haste | spirit_wolf 35%  sword 27%  bow 19%  magic_rod 19% |
| 3 | **51.5** | 50.1 | 1546 | sword L2, magic_rod L3, grave_totem, hammer L3 | +magic_rod, sword_wide_cleave, +grave_totem, +hammer, magic_rod_seeking x2, iron_arm, hammer_staggering_strike x2 | hammer 32%  sword 31%  magic_rod 23%  grave_totem 14% |
| 4 | **51.4** | 48.1 | 1541 | sword L2, bomb, hammer | keen_eye x3, haste x3, sword_wide_cleave, +bomb, +hammer | bomb 36%  sword 35%  hammer 29% |
| 5 | **87.4** | 88.3 | 2621 | sword L2, hammer L2, daggers L2, spirit_wolf | +hammer, fortune, keen_eye x2, hammer_crushing_blow, +daggers, +spirit_wolf, daggers_quick_hands, sword_wide_cleave | daggers 33%  spirit_wolf 27%  hammer 22%  sword 17% |
| 6 | **82.6** | 83.1 | 2479 | sword, daggers L2, bomb L3, grave_totem L2 | +daggers, +bomb, bomb_explosive_force, daggers_sharpened_blades, iron_arm x2, bomb_blast_amplifier, +grave_totem, grave_totem_twin_totems | daggers 43%  sword 21%  bomb 20%  grave_totem 16% |
| 7 | **92.2** | 91.5 | 2765 | sword, daggers L3, bow L2, spirit_wolf | iron_arm x2, +daggers, daggers_sharpened_blades, +bow, keen_eye, bow_rapid_draw, daggers_quick_hands, +spirit_wolf | daggers 42%  spirit_wolf 26%  sword 19%  bow 13% |
| 8 | **76.5** | 74.2 | 2295 | sword L2, daggers L2, magic_rod, grave_totem L2 | iron_arm x2, sword_heavy_blade, +daggers, +magic_rod, daggers_sharpened_blades, +grave_totem, grave_totem_quick_plant, fortune | daggers 47%  sword 27%  magic_rod 16%  grave_totem 10% |
| 9 | **44.5** | 38.2 | 1336 | sword L2, grave_totem L2, bomb | +grave_totem, grave_totem_long_watch, sword_critical_edge, +bomb, keen_eye x2, lucky_strike, haste x2 | bomb 43%  sword 42%  grave_totem 15% |
| 10 | **57.1** | 56.1 | 1714 | sword L3, hammer, bow L2, grave_totem L2 | +hammer, sword_wide_cleave, +bow, bow_hunters_mark, iron_arm, haste, sword_sharpened_edge, +grave_totem, grave_totem_long_watch | sword 36%  hammer 29%  bow 24%  grave_totem 12% |
| 11 | **75.2** | 76.3 | 2256 | sword L2, hammer L3, spirit_wolf, magic_rod L2 | +hammer, iron_arm, +spirit_wolf, +magic_rod, sword_sharpened_edge, keen_eye, hammer_titans_grip, hammer_crushing_blow, magic_rod_chain | spirit_wolf 32%  hammer 26%  sword 25%  magic_rod 17% |
| 12 | **73.3** | 69.8 | 2200 | sword L4, hammer, spirit_wolf, magic_rod | +hammer, haste x3, +spirit_wolf, sword_critical_edge x2, +magic_rod, sword_wide_cleave | spirit_wolf 33%  sword 27%  hammer 21%  magic_rod 20% |
| 13 | **57.8** | 55.9 | 1734 | sword L3, bomb L4, bow, grave_totem | +bomb, +bow, sword_heavy_blade, sword_sharpened_edge, +grave_totem, iron_arm, bomb_blast_amplifier, bomb_explosive_force x2 | sword 37%  bomb 34%  bow 17%  grave_totem 12% |
| 14 | **85.9** | 92.5 | 2578 | sword L4, spirit_wolf L3, bow L2, bomb | sword_critical_edge, +spirit_wolf, +bow, bow_split_arrow, sword_heavy_blade, spirit_wolf_pack x2, sword_wide_cleave, +bomb | spirit_wolf 49%  sword 24%  bomb 15%  bow 12% |
| 15 | **42.2** | 40.7 | 1267 | sword L3, hammer L4, grave_totem | +hammer, sword_wide_cleave, +grave_totem, keen_eye, hammer_executioner, hammer_titans_grip, iron_arm, sword_sharpened_edge, hammer_staggering_strike | sword 45%  hammer 39%  grave_totem 17% |
| 16 | **74.4** | 76.9 | 2231 | sword, bow L2, hammer, spirit_wolf | +bow, +hammer, fortune x2, haste, iron_arm, +spirit_wolf, bow_piercing_arrow, lucky_strike | spirit_wolf 32%  hammer 27%  sword 24%  bow 17% |
| 17 | **42.1** | 41.6 | 1262 | sword L4, bomb | lucky_strike x2, keen_eye, iron_arm, sword_sharpened_edge x2, +bomb, sword_critical_edge, fortune | sword 57%  bomb 43% |
| 18 | **91.8** | 92.3 | 2755 | sword, hammer L4, daggers, spirit_wolf | lucky_strike, +hammer, hammer_staggering_strike, keen_eye, hammer_executioner, +daggers, hammer_crushing_blow, iron_arm, +spirit_wolf | daggers 33%  spirit_wolf 26%  hammer 21%  sword 20% |
| 19 | **81.2** | 81.6 | 2436 | sword L2, daggers L3, grave_totem L2, bow | +daggers, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, +bow, haste, iron_arm, sword_critical_edge | daggers 52%  sword 26%  bow 13%  grave_totem 9% |
| 20 | **70.5** | 65.6 | 2116 | sword, ember_ring, daggers L2, bomb L2 | keen_eye, +ember_ring, +daggers, daggers_quick_hands, +bomb, lucky_strike, iron_arm, haste, bomb_demolitionist | daggers 51%  sword 26%  bomb 23%  ember_ring 1% |
| 21 | **42.1** | 40.8 | 1264 | sword L2, magic_rod L2, ember_ring, bow L3 | lucky_strike x2, +magic_rod, magic_rod_seeking, sword_wide_cleave, +ember_ring, +bow, bow_rapid_draw, bow_piercing_arrow | sword 36%  magic_rod 32%  bow 30%  ember_ring 2% |
| 22 | **59.4** | 57.1 | 1781 | sword L3, grave_totem L2, bomb, magic_rod L2 | +grave_totem, haste, +bomb, +magic_rod, magic_rod_seeking, sword_sharpened_edge, iron_arm, grave_totem_spectral_bolts, sword_critical_edge | sword 41%  bomb 22%  magic_rod 22%  grave_totem 16% |
| 23 | **51.7** | 49.1 | 1551 | sword L4, bow, magic_rod L2 | +bow, +magic_rod, lucky_strike, magic_rod_overcharge, sword_critical_edge, sword_sharpened_edge, haste, keen_eye, sword_heavy_blade | sword 44%  magic_rod 31%  bow 26% |
| 24 | **58.3** | 53.6 | 1748 | sword L2, hammer, grave_totem, bomb L5 | +hammer, +grave_totem, +bomb, sword_wide_cleave, bomb_demolition, bomb_bigger_explosion, lucky_strike, bomb_blast_amplifier, bomb_demolitionist | bomb 32%  sword 28%  hammer 28%  grave_totem 12% |
| 25 | **73.3** | 74.3 | 2198 | sword L2, spirit_wolf, hammer L2, bow L2 | fortune x2, +spirit_wolf, +hammer, +bow, lucky_strike, sword_heavy_blade, bow_rapid_draw, hammer_titans_grip | spirit_wolf 33%  sword 28%  hammer 24%  bow 15% |
| 26 | **77.3** | 76.1 | 2319 | sword L2, magic_rod L4, daggers L2 | iron_arm x2, +magic_rod, sword_sharpened_edge, magic_rod_seeking, +daggers, magic_rod_chain, magic_rod_arcane_missiles, daggers_quick_hands | daggers 43%  magic_rod 31%  sword 26% |
| 27 | **42.8** | 36.8 | 1283 | sword L2, grave_totem, bomb | lucky_strike x3, +grave_totem, fortune, sword_wide_cleave, +bomb, haste x2 | sword 45%  bomb 39%  grave_totem 16% |
| 28 | **53.3** | 53.8 | 1600 | sword L4, hammer L3, magic_rod | keen_eye, +hammer, sword_sharpened_edge x2, hammer_crushing_blow, haste, +magic_rod, hammer_heavy_impact, sword_wide_cleave | sword 40%  hammer 34%  magic_rod 26% |
| 29 | **70.7** | 70.1 | 2120 | sword L2, bomb L2, daggers L3, ember_ring L3 | +bomb, +daggers, +ember_ring, bomb_explosive_force, daggers_blood_in_the_water, ember_ring_ember_heat x2, sword_wide_cleave, daggers_sharpened_blades | daggers 54%  bomb 23%  sword 21%  ember_ring 2% |
| 30 | **53.0** | 50.9 | 1590 | sword L3, daggers L2 | +daggers, daggers_weak_point, sword_critical_edge, haste x2, keen_eye, sword_wide_cleave, fortune, iron_arm | daggers 61%  sword 39% |

### Per source at level 10, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 11 | 35.3 |
| spirit_wolf | 9 | 26.0 |
| sword | 30 | 19.2 |
| hammer | 12 | 17.4 |
| bomb | 11 | 16.7 |
| magic_rod | 10 | 14.5 |
| bow | 11 | 12.0 |
| grave_totem | 11 | 7.9 |
| ember_ring | 4 | 0.8 |

## Level 15

30 builds — mean **79.7**, median **79.9**, spread 52.4 to 126.0 (**2.41x**).

- Weakest: sword L3, ember_ring L3, bow L3, bomb L2 + sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge.
- Strongest: sword L3, hammer L2, magic_rod L4, spirit_wolf L2 + iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **82.5** | 77.0 | 2475 | sword L3, hammer L3, spirit_wolf, bow L4 | sword_critical_edge, +hammer, sword_heavy_blade, +spirit_wolf, +bow, keen_eye, bow_rapid_draw x2, hammer_heavy_impact, haste x2, lucky_strike, hammer_crushing_blow, bow_split_arrow | spirit_wolf 29%  sword 26%  hammer 25%  bow 20% |
| 2 | **88.7** | 88.0 | 2662 | sword L2, hammer L2, spirit_wolf L4, bow L4 | +hammer, +spirit_wolf, hammer_titans_grip, keen_eye, spirit_wolf_swift, +bow, bow_linebreaker, iron_arm, sword_sharpened_edge, spirit_wolf_savage_bite x2, bow_rapid_draw, lucky_strike, bow_piercing_arrow | spirit_wolf 42%  sword 23%  hammer 20%  bow 15% |
| 3 | **79.6** | 80.6 | 2387 | sword L4, daggers L4, bomb L4 | iron_arm, +daggers, daggers_quick_hands x2, +bomb, daggers_sharpened_blades, sword_critical_edge, bomb_bigger_explosion x2, haste, bomb_blast_amplifier, keen_eye, sword_wide_cleave, sword_sharpened_edge | daggers 52%  sword 30%  bomb 17% |
| 4 | **71.2** | 69.2 | 2135 | sword L3, ember_ring L4, bomb L3, magic_rod | +ember_ring, +bomb, sword_sharpened_edge, ember_ring_ember_heat, sword_critical_edge, ember_ring_wide_orbit x2, +magic_rod, forge:greatsword, haste, bomb_bigger_explosion, iron_arm x2, bomb_explosive_force | sword 58%  bomb 23%  magic_rod 18%  ember_ring 1% |
| 5 | **69.0** | 65.3 | 2071 | sword L3, magic_rod L2, hammer L2, grave_totem L2 | +magic_rod, iron_arm x3, +hammer, haste, lucky_strike x2, sword_heavy_blade, sword_critical_edge, +grave_totem, magic_rod_seeking, grave_totem_long_watch, hammer_heavy_impact | hammer 35%  sword 34%  magic_rod 21%  grave_totem 10% |
| 6 | **62.7** | 58.8 | 1880 | sword L2, magic_rod L3, bomb L2, grave_totem L2 | iron_arm x2, +magic_rod, +bomb, keen_eye, bomb_explosive_force, fortune, magic_rod_overcharge, lucky_strike x2, sword_critical_edge, magic_rod_chain, +grave_totem, grave_totem_spectral_bolts | sword 30%  bomb 28%  magic_rod 27%  grave_totem 15% |
| 7 | **73.7** | 75.3 | 2212 | sword L6, bomb L3, magic_rod L2, ember_ring | sword_heavy_blade x2, iron_arm x2, +bomb, keen_eye, +magic_rod, magic_rod_arcane_missiles, bomb_blast_amplifier x2, sword_critical_edge x2, sword_sharpened_edge, +ember_ring | sword 45%  magic_rod 35%  bomb 19%  ember_ring 1% |
| 8 | **53.5** | 51.0 | 1604 | sword, bow L3, ember_ring, bomb L4 | keen_eye x3, +bow, +ember_ring, +bomb, bomb_bigger_explosion, bow_piercing_arrow x2, fortune, bomb_blast_amplifier, haste x2, bomb_explosive_force | bomb 40%  sword 33%  bow 26%  ember_ring 1% |
| 9 | **106.2** | 110.4 | 3185 | sword L2, bomb, hammer L3, spirit_wolf L2 | sword_sharpened_edge, lucky_strike x2, +bomb, +hammer, +spirit_wolf, haste, keen_eye x2, iron_arm x2, hammer_executioner, hammer_crushing_blow, spirit_wolf_pack | spirit_wolf 40%  sword 24%  hammer 21%  bomb 15% |
| 10 | **55.2** | 51.1 | 1656 | sword L6, magic_rod, bomb L2 | keen_eye, sword_critical_edge x3, +magic_rod, haste x2, fortune, iron_arm x2, sword_wide_cleave, +bomb, sword_sharpened_edge, bomb_blast_amplifier | sword 46%  magic_rod 27%  bomb 27% |
| 11 | **82.0** | 81.6 | 2460 | sword L3, magic_rod L4, hammer L4 | +magic_rod, +hammer, magic_rod_seeking, sword_sharpened_edge x2, magic_rod_arcane_missiles, haste, keen_eye, hammer_crushing_blow x3, fortune, magic_rod_overcharge, iron_arm | magic_rod 38%  hammer 33%  sword 28% |
| 12 | **80.2** | 76.4 | 2405 | sword L2, bow L5, spirit_wolf L2, bomb | +bow, iron_arm x3, bow_split_arrow x2, bow_rapid_draw x2, +spirit_wolf, +bomb, spirit_wolf_savage_bite, sword_heavy_blade, fortune, haste | spirit_wolf 38%  sword 30%  bomb 16%  bow 16% |
| 13 | **96.3** | 94.8 | 2890 | sword L3, daggers L4, grave_totem L2, hammer L3 | sword_sharpened_edge, iron_arm x2, +daggers, sword_bloodletting, lucky_strike, daggers_quick_hands, +grave_totem, +hammer, grave_totem_twin_totems, hammer_staggering_strike x2, daggers_extended_reach, daggers_sharpened_blades | daggers 44%  sword 21%  hammer 21%  grave_totem 14% |
| 14 | **100.0** | 100.1 | 3001 | sword, daggers L4, spirit_wolf, magic_rod L2 | fortune, +daggers, iron_arm x3, daggers_quick_hands x2, keen_eye x3, daggers_extended_reach, +spirit_wolf, +magic_rod, magic_rod_overcharge | daggers 39%  spirit_wolf 24%  sword 20%  magic_rod 17% |
| 15 | **74.0** | 71.2 | 2221 | sword, hammer L4, bomb L4, ember_ring | +hammer, hammer_crushing_blow x2, +bomb, +ember_ring, fortune, bomb_blast_amplifier x2, bomb_demolitionist, iron_arm, hammer_staggering_strike, haste, forge:minefield, forge:earthshaker | hammer 39%  bomb 37%  sword 24%  ember_ring 1% |
| 16 | **93.4** | 94.1 | 2802 | sword L4, spirit_wolf, bow L4, daggers L3 | fortune x2, +spirit_wolf, sword_wide_cleave, +bow, +daggers, iron_arm, daggers_sharpened_blades, sword_bloodletting, bow_rapid_draw, daggers_quick_hands, bow_split_arrow, bow_piercing_arrow, sword_critical_edge | daggers 43%  spirit_wolf 26%  sword 18%  bow 13% |
| 17 | **79.5** | 76.5 | 2385 | sword L4, spirit_wolf L2, bomb, hammer L3 | +spirit_wolf, lucky_strike x2, keen_eye x2, spirit_wolf_swift, sword_critical_edge x2, fortune, sword_sharpened_edge, +bomb, +hammer, hammer_crushing_blow, hammer_executioner | spirit_wolf 30%  sword 26%  hammer 24%  bomb 20% |
| 18 | **95.7** | 91.1 | 2871 | sword L5, daggers L5, bomb, spirit_wolf | +daggers, +bomb, sword_sharpened_edge, daggers_weak_point, fortune, lucky_strike, sword_bloodletting, daggers_sharpened_blades, sword_crowd_cleaner x2, daggers_extended_reach x2, +spirit_wolf, haste | daggers 38%  spirit_wolf 25%  sword 21%  bomb 15% |
| 19 | **52.4** | 48.6 | 1571 | sword L3, ember_ring L3, bow L3, bomb L2 | sword_wide_cleave, iron_arm, +ember_ring, +bow, haste, ember_ring_ember_heat, keen_eye, ember_ring_more_embers, +bomb, bow_rapid_draw x2, fortune, bomb_explosive_force, sword_critical_edge | sword 37%  bomb 33%  bow 27%  ember_ring 2% |
| 20 | **68.5** | 67.1 | 2056 | sword L5, grave_totem L3, magic_rod, daggers L3 | +grave_totem, keen_eye x2, grave_totem_long_watch, +magic_rod, sword_critical_edge x2, sword_wide_cleave, +daggers, daggers_extended_reach, sword_bloodletting, daggers_quick_hands, fortune, grave_totem_spectral_bolts | daggers 44%  sword 23%  magic_rod 20%  grave_totem 13% |
| 21 | **87.4** | 86.9 | 2621 | sword L2, bow L3, magic_rod L3, spirit_wolf L2 | +bow, haste, +magic_rod, iron_arm x2, sword_sharpened_edge, +spirit_wolf, bow_split_arrow, keen_eye x2, spirit_wolf_savage_bite, magic_rod_seeking, bow_crossfire, magic_rod_overcharge | spirit_wolf 35%  sword 25%  magic_rod 23%  bow 17% |
| 22 | **89.8** | 83.8 | 2694 | sword L3, bomb, magic_rod L3, spirit_wolf L2 | +bomb, sword_heavy_blade, haste, lucky_strike x3, +magic_rod, +spirit_wolf, spirit_wolf_swift, magic_rod_arcane_missiles x2, iron_arm x2, sword_crowd_cleaner | magic_rod 32%  spirit_wolf 27%  sword 25%  bomb 16% |
| 23 | **78.9** | 77.9 | 2368 | sword L3, daggers L4, magic_rod L4, ember_ring | +daggers, +magic_rod, daggers_weak_point, daggers_quick_hands, magic_rod_chain, +ember_ring, keen_eye, sword_sharpened_edge, magic_rod_seeking, lucky_strike, iron_arm, magic_rod_overcharge, daggers_marked_prey, sword_bloodletting | daggers 56%  sword 24%  magic_rod 19%  ember_ring 1% |
| 24 | **81.1** | 79.5 | 2433 | sword L3, bomb L2, bow L4, spirit_wolf L2 | +bomb, bomb_explosive_force, +bow, lucky_strike, keen_eye x3, bow_hunters_mark, +spirit_wolf, bow_piercing_arrow, sword_critical_edge, bow_rapid_draw, sword_bloodletting, spirit_wolf_swift | spirit_wolf 30%  bomb 26%  bow 23%  sword 21% |
| 25 | **61.7** | 53.6 | 1850 | sword L3, grave_totem L5, magic_rod, bomb | +grave_totem, grave_totem_quick_plant, grave_totem_spectral_bolts x2, +magic_rod, keen_eye, lucky_strike, sword_wide_cleave, fortune, +bomb, sword_bloodletting, grave_totem_long_watch, iron_arm, haste | sword 30%  magic_rod 26%  bomb 24%  grave_totem 19% |
| 26 | **56.7** | 49.0 | 1701 | sword L4, ember_ring, bomb L2, hammer L3 | sword_critical_edge x2, +ember_ring, haste x2, +bomb, +hammer, bomb_blast_amplifier, hammer_crushing_blow, iron_arm, hammer_heavy_impact, lucky_strike, keen_eye, sword_wide_cleave | sword 37%  hammer 34%  bomb 28%  ember_ring 1% |
| 27 | **88.2** | 84.0 | 2645 | sword L2, hammer L2, magic_rod, spirit_wolf | iron_arm x3, sword_wide_cleave, keen_eye x2, lucky_strike, haste x3, +hammer, +magic_rod, hammer_titans_grip, +spirit_wolf | sword 30%  spirit_wolf 27%  hammer 24%  magic_rod 19% |
| 28 | **64.1** | 57.9 | 1922 | sword L3, magic_rod L2, hammer L2, grave_totem | keen_eye x3, +magic_rod, iron_arm, magic_rod_overcharge, +hammer, +grave_totem, fortune, hammer_heavy_impact, haste x2, sword_heavy_blade, sword_bloodletting | sword 34%  magic_rod 30%  hammer 25%  grave_totem 11% |
| 29 | **126.0** | 132.2 | 3779 | sword L3, hammer L2, magic_rod L4, spirit_wolf L2 | iron_arm x2, sword_critical_edge, +hammer, sword_heavy_blade, +magic_rod, fortune, hammer_crushing_blow, keen_eye, magic_rod_arcane_missiles x3, +spirit_wolf, spirit_wolf_pack | spirit_wolf 34%  magic_rod 32%  sword 18%  hammer 17% |
| 30 | **92.7** | 88.1 | 2780 | sword L3, bomb L2, daggers L2, grave_totem | sword_sharpened_edge x2, lucky_strike, haste x3, +bomb, +daggers, bomb_blast_amplifier, iron_arm, keen_eye x2, +grave_totem, daggers_quick_hands | daggers 43%  sword 29%  bomb 21%  grave_totem 8% |

### Per source at level 15, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 39.3 |
| spirit_wolf | 13 | 28.9 |
| sword | 30 | 22.2 |
| hammer | 12 | 21.5 |
| magic_rod | 15 | 20.2 |
| bomb | 17 | 16.9 |
| bow | 8 | 14.5 |
| grave_totem | 7 | 9.3 |
| ember_ring | 7 | 0.8 |

## Level 20

30 builds — mean **100.5**, median **97.5**, spread 52.0 to 137.9 (**2.65x**).

- Weakest: sword L5, bow L5, ember_ring L4, bomb L2 + haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat.
- Strongest: sword L2, magic_rod L2, daggers L3, spirit_wolf L2 + haste x4, +magic_rod, +daggers, sword_sharpened_edge, magic_rod_seeking, lucky_strike x2, +spirit_wolf, fortune x2, iron_arm x2, spirit_wolf_pack, daggers_quick_hands, daggers_weak_point, keen_eye.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **124.3** | 125.6 | 3728 | sword L4, spirit_wolf L4, magic_rod L2, bow | sword_heavy_blade, sword_critical_edge x2, +spirit_wolf, lucky_strike, iron_arm x2, haste x3, fortune, spirit_wolf_savage_bite x3, +magic_rod, magic_rod_arcane_missiles, +bow, keen_eye x2 | spirit_wolf 35%  magic_rod 30%  sword 23%  bow 12% |
| 2 | **77.9** | 72.5 | 2338 | sword L4, hammer L5, bomb L2, grave_totem | keen_eye x4, +hammer, hammer_heavy_impact, lucky_strike, sword_critical_edge, iron_arm, fortune x2, hammer_crushing_blow x2, hammer_staggering_strike, +bomb, sword_sharpened_edge x2, bomb_demolition, +grave_totem | sword 31%  hammer 31%  bomb 29%  grave_totem 9% |
| 3 | **124.8** | 126.6 | 3745 | sword L6, daggers L4, bow L3 | keen_eye, +daggers, sword_wide_cleave x2, haste x3, fortune, +bow, daggers_quick_hands, sword_critical_edge x2, bow_heavy_draw, sword_sharpened_edge, bow_hunters_mark, iron_arm, forge:multishot, daggers_sharpened_blades, daggers_weak_point | bow 43%  daggers 37%  sword 21% |
| 4 | **77.9** | 71.4 | 2336 | sword L4, magic_rod L3, bow L3, ember_ring | fortune, keen_eye x3, lucky_strike, sword_heavy_blade, iron_arm x2, +magic_rod, magic_rod_arcane_missiles, +bow, bow_piercing_arrow x2, sword_bloodletting, +ember_ring, sword_wide_cleave, haste x2, magic_rod_seeking | magic_rod 48%  sword 32%  bow 18%  ember_ring 1% |
| 5 | **137.9** | 145.2 | 4136 | sword L2, magic_rod L2, daggers L3, spirit_wolf L2 | haste x4, +magic_rod, +daggers, sword_sharpened_edge, magic_rod_seeking, lucky_strike x2, +spirit_wolf, fortune x2, iron_arm x2, spirit_wolf_pack, daggers_quick_hands, daggers_weak_point, keen_eye | daggers 35%  spirit_wolf 32%  sword 21%  magic_rod 13% |
| 6 | **94.9** | 95.1 | 2846 | sword L5, daggers L2, grave_totem L5, bomb L3 | +daggers, iron_arm x2, +grave_totem, +bomb, daggers_quick_hands, fortune, grave_totem_long_watch x2, sword_sharpened_edge x2, grave_totem_spectral_bolts, bomb_blast_amplifier, haste x2, grave_totem_quick_plant, sword_bloodletting, sword_critical_edge, bomb_explosive_force | daggers 41%  sword 28%  bomb 18%  grave_totem 12% |
| 7 | **92.4** | 94.9 | 2773 | sword L3, grave_totem L5, hammer L3, bomb L4 | +grave_totem, grave_totem_twin_totems x2, iron_arm x2, +hammer, fortune x2, +bomb, grave_totem_spectral_bolts, bomb_explosive_force x2, grave_totem_long_watch, hammer_crushing_blow, sword_wide_cleave, sword_crowd_cleaner, hammer_executioner, forge:cluster_bomb, bomb_bigger_explosion | bomb 32%  hammer 24%  grave_totem 23%  sword 21% |
| 8 | **65.4** | 63.4 | 1963 | sword L5, grave_totem, bomb L3, bow | +grave_totem, +bomb, sword_wide_cleave, bomb_blast_amplifier, haste x3, +bow, iron_arm x3, keen_eye, sword_critical_edge, sword_bloodletting, sword_crowd_cleaner, lucky_strike x3, bomb_demolitionist | sword 39%  bomb 29%  bow 22%  grave_totem 11% |
| 9 | **95.2** | 87.5 | 2855 | sword L6, spirit_wolf, bomb L3, magic_rod L2 | +spirit_wolf, +bomb, sword_wide_cleave, sword_heavy_blade x2, fortune x3, sword_sharpened_edge x2, +magic_rod, iron_arm, magic_rod_chain, bomb_explosive_force, bomb_blast_amplifier, keen_eye x2, haste, forge:cluster_bomb | sword 35%  spirit_wolf 25%  bomb 22%  magic_rod 18% |
| 10 | **99.7** | 100.2 | 2990 | sword L3, bomb L3, magic_rod L4, spirit_wolf | +bomb, bomb_explosive_force, iron_arm, fortune, keen_eye x3, +magic_rod, magic_rod_seeking x3, haste x3, lucky_strike, sword_sharpened_edge, +spirit_wolf, bomb_blast_amplifier, sword_heavy_blade | sword 30%  bomb 27%  spirit_wolf 24%  magic_rod 18% |
| 11 | **78.8** | 76.2 | 2364 | sword L3, bow L5, hammer L2, grave_totem L2 | sword_sharpened_edge, +bow, +hammer, +grave_totem, fortune x3, bow_rapid_draw, haste x2, sword_wide_cleave, keen_eye x2, lucky_strike, bow_heavy_draw, hammer_heavy_impact, bow_piercing_arrow, grave_totem_twin_totems, bow_hunters_mark | bow 32%  sword 26%  hammer 23%  grave_totem 19% |
| 12 | **82.7** | 80.5 | 2482 | sword L5, hammer L5, bomb L4, ember_ring L3 | +hammer, iron_arm, +bomb, hammer_crushing_blow x2, sword_sharpened_edge x2, +ember_ring, bomb_demolition x2, sword_critical_edge, hammer_staggering_strike, bomb_blast_amplifier, ember_ring_wide_orbit x2, haste, hammer_titans_grip, sword_wide_cleave, forge:meteor_hammer | hammer 45%  sword 32%  bomb 22%  ember_ring 1% |
| 13 | **97.3** | 96.7 | 2919 | sword L3, daggers L4, hammer L5, ember_ring L3 | +daggers, daggers_quick_hands x3, +hammer, +ember_ring, ember_ring_ember_heat, hammer_crushing_blow x2, iron_arm x3, sword_critical_edge, keen_eye, hammer_heavy_impact, hammer_titans_grip, haste, sword_bloodletting, ember_ring_more_embers | daggers 49%  hammer 26%  sword 24%  ember_ring 1% |
| 14 | **111.3** | 112.6 | 3339 | sword L4, spirit_wolf, daggers L3, bow L4 | +spirit_wolf, sword_heavy_blade, lucky_strike x2, +daggers, +bow, bow_piercing_arrow, haste, iron_arm x2, fortune x2, keen_eye, sword_bloodletting, sword_sharpened_edge, daggers_sharpened_blades, daggers_weak_point, bow_rapid_draw x2 | daggers 39%  sword 25%  spirit_wolf 22%  bow 14% |
| 15 | **131.6** | 130.1 | 3948 | sword L5, magic_rod L2, bomb L5, spirit_wolf L2 | +magic_rod, +bomb, sword_heavy_blade, iron_arm x2, +spirit_wolf, bomb_blast_amplifier, bomb_explosive_force x2, magic_rod_overcharge, forge:cluster_bomb, bomb_bigger_explosion, spirit_wolf_pack, haste, sword_wide_cleave, keen_eye, sword_critical_edge x2, lucky_strike | bomb 36%  spirit_wolf 32%  sword 19%  magic_rod 13% |
| 16 | **122.2** | 128.8 | 3666 | sword L2, magic_rod L4, bomb L6, spirit_wolf L4 | +magic_rod, +bomb, iron_arm, magic_rod_seeking x2, +spirit_wolf, lucky_strike x2, bomb_bigger_explosion, bomb_demolitionist x2, bomb_explosive_force x2, magic_rod_chain, keen_eye, spirit_wolf_pack, spirit_wolf_savage_bite x2, sword_sharpened_edge | spirit_wolf 54%  bomb 17%  sword 17%  magic_rod 12% |
| 17 | **115.9** | 107.3 | 3478 | sword L6, daggers L4, bomb L3, spirit_wolf | +daggers, sword_wide_cleave, sword_sharpened_edge x2, daggers_extended_reach, fortune x2, sword_heavy_blade, iron_arm, keen_eye x2, sword_critical_edge, +bomb, bomb_blast_amplifier, daggers_quick_hands, daggers_sharpened_blades, bomb_explosive_force, haste, +spirit_wolf | daggers 36%  sword 22%  bomb 21%  spirit_wolf 21% |
| 18 | **86.3** | 82.0 | 2588 | sword L4, daggers L4, hammer L8, grave_totem L2 | +daggers, keen_eye, daggers_quick_hands, +hammer, hammer_executioner x3, sword_wide_cleave, hammer_heavy_impact, hammer_crushing_blow, hammer_staggering_strike x2, sword_critical_edge x2, forge:earthshaker, daggers_weak_point, +grave_totem, grave_totem_twin_totems, daggers_sharpened_blades | daggers 39%  hammer 24%  sword 21%  grave_totem 16% |
| 19 | **126.2** | 123.1 | 3786 | sword L6, spirit_wolf L2, daggers L4, hammer L3 | sword_heavy_blade, +spirit_wolf, +daggers, +hammer, sword_critical_edge, iron_arm, hammer_crushing_blow, hammer_titans_grip, haste x3, sword_wide_cleave, sword_sharpened_edge x2, daggers_quick_hands, daggers_extended_reach, keen_eye, daggers_sharpened_blades, spirit_wolf_savage_bite | daggers 35%  sword 26%  spirit_wolf 24%  hammer 15% |
| 20 | **61.9** | 60.4 | 1858 | sword L6, hammer L3, magic_rod L4, ember_ring L2 | +hammer, sword_heavy_blade, sword_sharpened_edge x2, +magic_rod, +ember_ring, lucky_strike x2, ember_ring_wide_orbit, hammer_staggering_strike, keen_eye x2, magic_rod_seeking, hammer_titans_grip, haste, magic_rod_chain, magic_rod_overcharge, sword_wide_cleave, sword_critical_edge | sword 39%  magic_rod 30%  hammer 30%  ember_ring 1% |
| 21 | **133.1** | 137.6 | 3994 | sword L3, magic_rod L2, spirit_wolf L5, daggers L3 | sword_bloodletting, iron_arm x2, fortune x2, +magic_rod, +spirit_wolf, haste, spirit_wolf_swift x2, spirit_wolf_savage_bite, sword_sharpened_edge, +daggers, keen_eye x2, daggers_extended_reach, daggers_weak_point, magic_rod_overcharge, spirit_wolf_pack | spirit_wolf 42%  daggers 27%  sword 18%  magic_rod 13% |
| 22 | **79.2** | 77.0 | 2377 | sword L4, bomb L4, ember_ring L4, magic_rod L5 | +bomb, +ember_ring, sword_critical_edge, bomb_explosive_force x2, +magic_rod, ember_ring_more_embers x2, magic_rod_seeking, magic_rod_chain, ember_ring_ember_heat, keen_eye x2, magic_rod_arcane_missiles, magic_rod_overcharge, bomb_bigger_explosion, sword_bloodletting, lucky_strike, sword_sharpened_edge | magic_rod 41%  bomb 30%  sword 27%  ember_ring 2% |
| 23 | **132.8** | 135.4 | 3983 | sword L4, spirit_wolf L2, magic_rod L2, daggers L3 | +spirit_wolf, haste x2, spirit_wolf_savage_bite, fortune x3, +magic_rod, sword_sharpened_edge x3, +daggers, keen_eye x2, iron_arm, daggers_sharpened_blades, lucky_strike, daggers_marked_prey, magic_rod_seeking | daggers 41%  spirit_wolf 23%  sword 22%  magic_rod 14% |
| 24 | **126.8** | 133.6 | 3805 | sword L2, spirit_wolf L5, magic_rod L3, daggers | +spirit_wolf, fortune, spirit_wolf_savage_bite, keen_eye x3, +magic_rod, iron_arm x2, +daggers, lucky_strike x3, spirit_wolf_pack x2, spirit_wolf_swift, magic_rod_overcharge, sword_bloodletting, magic_rod_seeking | spirit_wolf 43%  daggers 27%  sword 15%  magic_rod 15% |
| 25 | **106.9** | 106.5 | 3208 | sword L3, ember_ring L2, hammer L4, daggers L5 | +ember_ring, +hammer, hammer_titans_grip, iron_arm x3, +daggers, daggers_sharpened_blades, sword_sharpened_edge, daggers_extended_reach, sword_wide_cleave, hammer_crushing_blow x2, keen_eye x2, ember_ring_ember_heat, daggers_blood_in_the_water, daggers_quick_hands, haste | daggers 53%  hammer 24%  sword 22%  ember_ring 1% |
| 26 | **101.0** | 99.6 | 3030 | sword L5, daggers L5, ember_ring L3, hammer L4 | +daggers, daggers_quick_hands x3, +ember_ring, sword_heavy_blade x2, daggers_sharpened_blades, ember_ring_wide_orbit, +hammer, sword_bloodletting, hammer_executioner, iron_arm x2, hammer_crushing_blow x2, sword_critical_edge, keen_eye, ember_ring_more_embers | daggers 47%  sword 29%  hammer 24%  ember_ring 1% |
| 27 | **52.0** | 48.7 | 1561 | sword L5, bow L5, ember_ring L4, bomb L2 | haste, +bow, sword_sharpened_edge x2, +ember_ring, ember_ring_wide_orbit, +bomb, bow_piercing_arrow x3, iron_arm, ember_ring_more_embers, sword_wide_cleave, bow_split_arrow, bomb_bigger_explosion, sword_bloodletting, keen_eye x2, ember_ring_ember_heat | sword 45%  bomb 29%  bow 24%  ember_ring 2% |
| 28 | **89.7** | 88.7 | 2690 | sword L5, ember_ring L4, bomb L5, hammer | sword_sharpened_edge x2, +ember_ring, +bomb, bomb_explosive_force, ember_ring_wide_orbit, fortune, bomb_blast_amplifier, sword_critical_edge, forge:greatsword, forge:minefield, ember_ring_more_embers, bomb_demolitionist, ember_ring_ember_heat, sword_wide_cleave, keen_eye, haste, bomb_bigger_explosion, +hammer | sword 44%  bomb 38%  hammer 17%  ember_ring 1% |
| 29 | **97.7** | 89.0 | 2930 | sword L2, hammer L6, bow L2, spirit_wolf | +hammer, iron_arm x2, +bow, keen_eye x3, haste x3, hammer_crushing_blow x4, +spirit_wolf, lucky_strike, hammer_heavy_impact, bow_piercing_arrow, sword_critical_edge | hammer 36%  spirit_wolf 25%  sword 23%  bow 16% |
| 30 | **89.8** | 86.8 | 2694 | sword L3, magic_rod L3, bomb L4, grave_totem L4 | +magic_rod, +bomb, +grave_totem, bomb_explosive_force, sword_crowd_cleaner, magic_rod_chain, iron_arm x3, keen_eye x2, grave_totem_twin_totems, bomb_blast_amplifier, grave_totem_spectral_bolts, bomb_bigger_explosion, magic_rod_arcane_missiles, grave_totem_quick_plant, sword_wide_cleave, haste | magic_rod 33%  grave_totem 24%  sword 22%  bomb 21% |

### Per source at level 20, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 13 | 43.9 |
| spirit_wolf | 13 | 37.5 |
| sword | 30 | 25.4 |
| bomb | 14 | 24.2 |
| hammer | 12 | 23.9 |
| magic_rod | 13 | 22.8 |
| bow | 8 | 20.7 |
| grave_totem | 7 | 13.8 |
| ember_ring | 9 | 1.0 |

## Level 25

30 builds — mean **98.7**, median **99.0**, spread 44.4 to 165.9 (**3.74x**).

- Weakest: sword L6, hammer L7, magic_rod L5, ember_ring + sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles.
- Strongest: sword L6, magic_rod L4, spirit_wolf L4, bow L6 + +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm.

| # | avg dps | window | total | held (blessing level) | picks, in order | split |
|---|--------:|-------:|------:|---|---|---|
| 1 | **121.6** | 118.2 | 3647 | sword L4, bow L4, daggers L7, grave_totem L2 | lucky_strike, +bow, sword_sharpened_edge x2, +daggers, daggers_weak_point x2, iron_arm x3, keen_eye x3, sword_wide_cleave, daggers_blood_in_the_water, bow_rapid_draw x2, +grave_totem, daggers_sharpened_blades x2, grave_totem_quick_plant, daggers_quick_hands, fortune, bow_hunters_mark | daggers 56%  sword 21%  bow 17%  grave_totem 6% |
| 2 | **139.2** | 141.6 | 4175 | sword L2, daggers L3, spirit_wolf L2, bomb L5 | haste x5, lucky_strike, +daggers, iron_arm x3, daggers_quick_hands, daggers_blood_in_the_water, +spirit_wolf, +bomb, bomb_blast_amplifier x2, fortune x2, sword_bloodletting, bomb_bigger_explosion x2, keen_eye x2, spirit_wolf_swift | daggers 48%  sword 18%  spirit_wolf 17%  bomb 17% |
| 3 | **111.0** | 114.4 | 3331 | sword L3, bomb L5, spirit_wolf L3, magic_rod L6 | lucky_strike, +bomb, fortune, +spirit_wolf, sword_bloodletting, bomb_explosive_force x3, haste x2, keen_eye x3, spirit_wolf_savage_bite, +magic_rod, iron_arm, magic_rod_overcharge x2, magic_rod_seeking x2, magic_rod_chain, bomb_bigger_explosion, sword_sharpened_edge, spirit_wolf_swift | bomb 33%  spirit_wolf 28%  sword 20%  magic_rod 19% |
| 4 | **165.9** | 166.0 | 4978 | sword L6, magic_rod L4, spirit_wolf L4, bow L6 | +magic_rod, magic_rod_arcane_missiles, +spirit_wolf, magic_rod_chain, +bow, bow_split_arrow, sword_sharpened_edge x3, keen_eye x2, magic_rod_seeking, sword_bloodletting, spirit_wolf_savage_bite, bow_heavy_draw x2, lucky_strike, spirit_wolf_swift, spirit_wolf_pack, forge:arcane_lance, bow_piercing_arrow, sword_wide_cleave, bow_rapid_draw, iron_arm | magic_rod 38%  spirit_wolf 33%  sword 15%  bow 14% |
| 5 | **106.6** | 112.3 | 3197 | sword L3, magic_rod L6, spirit_wolf L3, bow | +magic_rod, keen_eye x2, fortune x2, sword_wide_cleave, magic_rod_seeking x4, +spirit_wolf, iron_arm x2, haste x4, +bow, sword_critical_edge, spirit_wolf_pack x2, magic_rod_chain, lucky_strike x2 | spirit_wolf 41%  sword 25%  magic_rod 18%  bow 16% |
| 6 | **88.6** | 84.8 | 2658 | sword L7, magic_rod L4, grave_totem L4, bow | +magic_rod, magic_rod_arcane_missiles, +grave_totem, sword_heavy_blade x2, keen_eye x2, grave_totem_quick_plant x2, iron_arm x4, +bow, haste, sword_sharpened_edge x2, magic_rod_chain, fortune, forge:whirlwind, whirlwind_cyclone, magic_rod_seeking, grave_totem_long_watch, sword_bloodletting | sword 43%  magic_rod 35%  bow 15%  grave_totem 8% |
| 7 | **116.2** | 110.8 | 3487 | sword L3, ember_ring L2, daggers L7, hammer L5 | lucky_strike x2, +ember_ring, +daggers, +hammer, daggers_blood_in_the_water, haste x2, sword_critical_edge, daggers_extended_reach x2, keen_eye, ember_ring_ember_heat, iron_arm x3, hammer_titans_grip, daggers_quick_hands x2, daggers_sharpened_blades, sword_bloodletting, hammer_executioner, hammer_crushing_blow, hammer_heavy_impact | daggers 61%  sword 19%  hammer 19%  ember_ring 1% |
| 8 | **107.9** | 109.4 | 3237 | sword L6, hammer L2, ember_ring L2, magic_rod L4 | fortune x5, iron_arm x3, +hammer, +ember_ring, +magic_rod, magic_rod_arcane_missiles, keen_eye x2, sword_sharpened_edge x3, hammer_staggering_strike, sword_heavy_blade, magic_rod_seeking, sword_critical_edge, forge:greatsword, magic_rod_overcharge, ember_ring_wide_orbit | sword 48%  magic_rod 31%  hammer 21%  ember_ring 1% |
| 9 | **66.8** | 64.3 | 2004 | sword L3, bow L4, ember_ring L5, bomb L5 | +bow, iron_arm x3, haste x3, +ember_ring, +bomb, ember_ring_ember_heat x2, fortune, bomb_blast_amplifier x2, sword_critical_edge, ember_ring_more_embers, bow_hunters_mark x2, bomb_explosive_force, ember_ring_wide_orbit, bomb_demolitionist, keen_eye, sword_crowd_cleaner, bow_rapid_draw | sword 38%  bow 30%  bomb 30%  ember_ring 2% |
| 10 | **115.8** | 112.4 | 3475 | sword L5, bomb L4, daggers L5, ember_ring L3 | +bomb, bomb_blast_amplifier, iron_arm, +daggers, daggers_blood_in_the_water, sword_heavy_blade x2, keen_eye x3, lucky_strike, daggers_weak_point, fortune, haste x2, sword_crowd_cleaner, bomb_bigger_explosion, +ember_ring, daggers_quick_hands, ember_ring_more_embers, daggers_sharpened_blades, bomb_explosive_force, ember_ring_wide_orbit, sword_sharpened_edge | daggers 48%  sword 29%  bomb 22%  ember_ring 1% |
| 11 | **44.4** | 40.2 | 1331 | sword L6, hammer L7, magic_rod L5, ember_ring | sword_critical_edge x2, sword_sharpened_edge x3, +hammer, +magic_rod, keen_eye, magic_rod_overcharge, iron_arm, fortune, forge:whirlwind, +ember_ring, hammer_heavy_impact x3, haste, hammer_executioner, magic_rod_seeking x2, hammer_titans_grip x2, forge:arcane_storm, magic_rod_arcane_missiles | sword 59%  hammer 37%  magic_rod 2%  ember_ring 2% |
| 12 | **117.3** | 110.3 | 3519 | sword L5, spirit_wolf L3, magic_rod L5, bomb L4 | +spirit_wolf, +magic_rod, +bomb, iron_arm x3, magic_rod_arcane_missiles, sword_wide_cleave, bomb_explosive_force x2, lucky_strike x2, magic_rod_seeking x3, keen_eye x2, sword_crowd_cleaner, spirit_wolf_savage_bite x2, sword_critical_edge, bomb_blast_amplifier, sword_bloodletting, haste | spirit_wolf 32%  magic_rod 27%  bomb 21%  sword 20% |
| 13 | **57.2** | 51.7 | 1716 | sword L3, ember_ring L6, bow L7, magic_rod L3 | +ember_ring, ember_ring_ember_heat x3, fortune x2, lucky_strike x2, ember_ring_more_embers, +bow, bow_piercing_arrow x2, +magic_rod, iron_arm, haste, bow_split_arrow, bow_rapid_draw, magic_rod_chain, ember_ring_wide_orbit, magic_rod_seeking, bow_heavy_draw, sword_wide_cleave x2, bow_crossfire | sword 34%  bow 32%  magic_rod 31%  ember_ring 3% |
| 14 | **82.1** | 72.9 | 2464 | sword L9, hammer L2, bomb L5, ember_ring | +hammer, fortune, +bomb, bomb_explosive_force x2, sword_sharpened_edge x2, sword_wide_cleave x3, +ember_ring, keen_eye x2, bomb_bigger_explosion, haste, sword_critical_edge, iron_arm x3, lucky_strike, hammer_crushing_blow, sword_heavy_blade, bomb_blast_amplifier, sword_crowd_cleaner | sword 41%  bomb 29%  hammer 29%  ember_ring 1% |
| 15 | **67.3** | 66.2 | 2019 | sword L3, hammer L9, bomb L7, ember_ring L2 | +hammer, +bomb, bomb_bigger_explosion x2, haste x3, bomb_demolitionist, +ember_ring, sword_heavy_blade, hammer_heavy_impact x3, forge:earthshaker, hammer_staggering_strike, bomb_blast_amplifier x2, hammer_crushing_blow x2, ember_ring_wide_orbit, sword_wide_cleave, bomb_explosive_force, hammer_titans_grip, earthshaker_aftershock | hammer 40%  sword 31%  bomb 28%  ember_ring 1% |
| 16 | **78.8** | 71.9 | 2363 | sword L6, magic_rod L3, bomb L3, grave_totem L7 | sword_bloodletting, +magic_rod, +bomb, +grave_totem, grave_totem_spectral_bolts x2, magic_rod_chain, fortune, keen_eye x2, iron_arm, grave_totem_long_watch x3, sword_critical_edge, sword_sharpened_edge, grave_totem_quick_plant, lucky_strike, bomb_explosive_force, sword_heavy_blade, bomb_demolitionist, haste, sword_wide_cleave, magic_rod_seeking | sword 32%  bomb 27%  grave_totem 21%  magic_rod 20% |
| 17 | **101.9** | 95.4 | 3057 | sword L4, magic_rod L3, bomb L4, grave_totem L6 | +magic_rod, haste, +bomb, magic_rod_chain, bomb_blast_amplifier, fortune x2, +grave_totem, grave_totem_quick_plant, iron_arm, sword_critical_edge x2, grave_totem_twin_totems x3, keen_eye x3, bomb_demolitionist, lucky_strike, grave_totem_spectral_bolts, sword_sharpened_edge, bomb_explosive_force, magic_rod_arcane_missiles | magic_rod 34%  sword 24%  bomb 21%  grave_totem 21% |
| 18 | **82.9** | 78.3 | 2486 | sword L8, magic_rod L3, hammer L4, grave_totem L2 | haste x4, keen_eye x2, +magic_rod, +hammer, hammer_heavy_impact x2, sword_bloodletting x2, fortune, sword_sharpened_edge x4, hammer_titans_grip, iron_arm, +grave_totem, magic_rod_seeking x2, grave_totem_quick_plant, sword_critical_edge | sword 48%  magic_rod 21%  hammer 21%  grave_totem 9% |
| 19 | **64.6** | 57.3 | 1938 | sword L5, bomb L6, ember_ring L2, magic_rod L3 | +bomb, fortune x2, keen_eye x2, +ember_ring, lucky_strike x2, bomb_blast_amplifier, bomb_bigger_explosion x2, haste, +magic_rod, sword_wide_cleave x2, sword_bloodletting x2, iron_arm x2, magic_rod_overcharge, bomb_explosive_force x2, ember_ring_wide_orbit, magic_rod_seeking | bomb 37%  sword 31%  magic_rod 30%  ember_ring 1% |
| 20 | **134.8** | 136.2 | 4043 | sword L4, magic_rod L2, hammer L6, spirit_wolf L3 | haste x2, sword_sharpened_edge x3, +magic_rod, +hammer, keen_eye x3, hammer_staggering_strike x2, hammer_titans_grip, iron_arm x3, lucky_strike, hammer_crushing_blow, fortune, +spirit_wolf, magic_rod_chain, spirit_wolf_pack, hammer_executioner, spirit_wolf_savage_bite | spirit_wolf 41%  sword 27%  hammer 19%  magic_rod 13% |
| 21 | **135.2** | 136.1 | 4057 | sword L4, daggers L5, bow L4, grave_totem L5 | +daggers, fortune x2, +bow, keen_eye x2, bow_rapid_draw, sword_wide_cleave, bow_hunters_mark, +grave_totem, daggers_sharpened_blades x3, sword_sharpened_edge, forge:greatsword, sword_heavy_blade, grave_totem_twin_totems x2, daggers_quick_hands, bow_split_arrow, grave_totem_spectral_bolts, haste x2, grave_totem_quick_plant | daggers 40%  sword 29%  grave_totem 17%  bow 14% |
| 22 | **109.3** | 106.8 | 3278 | sword L5, grave_totem L5, daggers L3, bomb L3 | haste x3, sword_wide_cleave x2, +grave_totem, +daggers, +bomb, grave_totem_long_watch x2, iron_arm x2, fortune x2, keen_eye, daggers_quick_hands, grave_totem_quick_plant x2, sword_critical_edge, daggers_sharpened_blades, sword_sharpened_edge, bomb_demolitionist, lucky_strike, bomb_explosive_force | daggers 48%  sword 24%  bomb 21%  grave_totem 8% |
| 23 | **141.2** | 130.7 | 4236 | sword L6, grave_totem L2, daggers L4, magic_rod L5 | +grave_totem, keen_eye x3, +daggers, +magic_rod, magic_rod_chain, grave_totem_spectral_bolts, sword_sharpened_edge x3, daggers_sharpened_blades, haste x3, lucky_strike, daggers_blood_in_the_water, daggers_extended_reach, magic_rod_seeking x2, sword_critical_edge, forge:greatsword, magic_rod_arcane_missiles, sword_bloodletting | daggers 35%  sword 31%  magic_rod 28%  grave_totem 7% |
| 24 | **96.0** | 92.5 | 2881 | sword L2, magic_rod L3, hammer L7, spirit_wolf L4 | keen_eye x2, +magic_rod, lucky_strike x3, +hammer, +spirit_wolf, iron_arm x2, hammer_crushing_blow, fortune, haste, magic_rod_overcharge, spirit_wolf_swift x2, hammer_heavy_impact x2, hammer_titans_grip x2, spirit_wolf_savage_bite, hammer_executioner, sword_sharpened_edge, magic_rod_seeking | spirit_wolf 32%  sword 26%  hammer 23%  magic_rod 19% |
| 25 | **88.5** | 82.7 | 2655 | sword L6, magic_rod L4, hammer L5, grave_totem L2 | keen_eye x4, sword_sharpened_edge x4, +magic_rod, iron_arm x2, +hammer, sword_critical_edge, hammer_heavy_impact x2, haste, hammer_crushing_blow x2, fortune, magic_rod_overcharge x2, magic_rod_chain, +grave_totem, grave_totem_quick_plant | sword 42%  hammer 27%  magic_rod 22%  grave_totem 9% |
| 26 | **73.0** | 64.4 | 2191 | sword L6, bow L2, bomb L3, grave_totem L3 | haste x2, sword_wide_cleave x2, +bow, +bomb, sword_crowd_cleaner x2, fortune x3, lucky_strike x2, +grave_totem, grave_totem_spectral_bolts, bomb_explosive_force, bomb_bigger_explosion, keen_eye x4, bow_split_arrow, grave_totem_long_watch, sword_heavy_blade | bomb 33%  sword 32%  bow 22%  grave_totem 12% |
| 27 | **75.2** | 73.3 | 2256 | sword L4, ember_ring L5, magic_rod L5, hammer L6 | +ember_ring, +magic_rod, ember_ring_more_embers, fortune x3, magic_rod_arcane_missiles x2, keen_eye x2, +hammer, hammer_crushing_blow x3, magic_rod_seeking x2, ember_ring_wide_orbit x2, hammer_heavy_impact, ember_ring_ember_heat, sword_wide_cleave, sword_critical_edge, hammer_staggering_strike, sword_sharpened_edge | magic_rod 42%  hammer 31%  sword 25%  ember_ring 2% |
| 28 | **111.9** | 106.2 | 3358 | sword L7, bow L4, daggers, spirit_wolf L3 | lucky_strike x2, fortune x3, sword_wide_cleave x2, sword_sharpened_edge x2, +bow, +daggers, bow_hunters_mark x2, keen_eye, +spirit_wolf, iron_arm x4, sword_heavy_blade, spirit_wolf_swift x2, bow_piercing_arrow, sword_critical_edge | daggers 34%  sword 29%  spirit_wolf 21%  bow 15% |
| 29 | **74.5** | 68.9 | 2234 | sword L5, magic_rod L4, hammer L6, grave_totem L3 | sword_critical_edge, +magic_rod, sword_bloodletting, +hammer, sword_wide_cleave, magic_rod_overcharge, haste x3, hammer_titans_grip, lucky_strike, magic_rod_seeking x2, sword_sharpened_edge, hammer_staggering_strike, iron_arm x2, +grave_totem, grave_totem_quick_plant x2, hammer_executioner x2, hammer_heavy_impact, keen_eye | sword 39%  hammer 27%  magic_rod 23%  grave_totem 11% |
| 30 | **86.0** | 86.1 | 2580 | sword L9, grave_totem, bow L4, magic_rod L3 | iron_arm, sword_sharpened_edge x2, +grave_totem, +bow, sword_critical_edge x4, +magic_rod, lucky_strike, magic_rod_overcharge x2, sword_wide_cleave, haste x4, sword_bloodletting, bow_rapid_draw, keen_eye, fortune, bow_piercing_arrow, bow_crossfire | sword 38%  magic_rod 31%  bow 23%  grave_totem 8% |

### Per source at level 25, averaged over the builds it appeared in

| source | appearances | mean dps contribution |
|---|---:|---:|
| daggers | 8 | 56.8 |
| spirit_wolf | 8 | 37.5 |
| sword | 30 | 29.2 |
| magic_rod | 19 | 25.0 |
| bomb | 12 | 23.9 |
| hammer | 11 | 22.2 |
| bow | 10 | 18.4 |
| grave_totem | 12 | 11.0 |
| ember_ring | 10 | 1.0 |

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
