# Bug journal

Running log of confirmed bugs: symptom, root cause, evidence, and the proposed
fix. Entries stay until the fix lands, then get a **Resolved** stamp with the
commit / milestone. Newest first.

---

## #1 · Flat armor nullifies all continuous (per-frame) damage

| | |
|---|---|
| **Status** | **RESOLVED** 2026-08-27 by `combat_balance_journal.md` **CB-1** (option 1 — timed bites). Not committed yet. |
| **Severity** | High — a hero with any armor is invulnerable to a whole class of damage |
| **Discovered** | 2026-08-27, while checking developer-mode "Unlimited HP" — HP wasn't dropping for the default hero even with the toggle **off** |
| **Area** | `entities/player.py — Player.take_damage`; call sites `game/states/playing_state.py — _resolve_enemy_contact`, `_update_hazards` (and small `_explosion`s) |
| **Not caused by** | Developer mode. `_dev_unlimited_hp` defaults `False` and `_apply_dev_unlimited_hp()` early-returns when off. Dev mode only made the bug easy to trigger (spawn enemies, stand in them). |

### Symptom

Standing inside enemies or a hazard pool as **Aegis** (or any armored hero) does
no damage at all. Aegis is effectively immune to body contact, hazard pools, and
burn / poison / bleed style damage-over-time. Kestrel and Nihil (armor 0) take
this damage normally.

### Root cause

`Player.take_damage(amount)` subtracts **flat armor once per call**:

```python
def take_damage(self, amount: float) -> float:
    if self.invulnerable or not self.alive:
        return 0.0
    amount *= self.incoming_damage_multiplier()
    dealt = max(0.0, amount - self.stats["armor"])     # <-- flat, per call
    self.hp -= dealt
    ...
```

Continuous damage sources call `take_damage` **once per frame** with a `dt`-sized
slice:

```python
# _resolve_enemy_contact
taken = self.player.take_damage(enemy.contact_damage * dt)

# _update_hazards
taken = self.player.take_damage(hz.dps * dt)
```

At 60 fps a frame carries only `dps / 60` — roughly `0.2 – 0.4` for typical
contact damage (16) or a 20-dps hazard. Any `armor >= ~1` makes
`max(0.0, 0.3 - armor) == 0.0` **every single frame**, so the damage never lands.

Armor is a per-**hit** mechanic being fed per-**frame** fractions. Discrete hits
(projectiles 6–16, explosions ~20–28, boss slams ~28) exceed armor in one call
and still work — which is why the bug is invisible in normal ranged play and only
shows up on sustained contact / DoT.

Aegis's baseline is `armor: 4` (`data/characters.json`); anyone stacking armor
via items, meta upgrades, or the `warding` affix hits the same wall.

`data/enemies.json`: `chaser` contact 8, `tank` 16, `brute` 24, `fast` 6.
`data/characters.json`: aegis armor 4, kestrel/nihil armor 0.

### Evidence

Headless check — hero standing still, weapons removed, 6 tanks parked on top for
3 s; and a separate 20-dps hazard for 3 s:

| Hero | armor | contact, 3 s | 20-dps hazard, 3 s |
|------|-------|--------------|--------------------|
| aegis | 4 | 160 → **160** (immune) | 160 → **160** (immune) |
| kestrel | 0 | 92 → **0** (dead) | 92 → 32 (−60, correct) |
| nihil | 0 | 96 → **0** (dead) | — |

Per-frame trace on aegis: `take_damage(0.267)` → `dealt 0.000` every frame,
`hp` never moves.

### Fix options

1. **Discrete "bites" (recommended).** Contact damage lands as a full
   `contact_damage` hit on a per-target cooldown (~0.4–0.5 s); hazards tick
   `dps · tick_interval` every ~0.25 s instead of every frame. Armor then applies
   to a meaningful chunk, exactly as it does for projectile hits. This is the
   standard action-game model and needs no change to `Player.take_damage`.
   - Touch: add a per-target contact timer (a small dict on `PlayingState`, keyed
     by `id(enemy)`, or a `_contact_cd` field on `Enemy`); rework
     `_resolve_enemy_contact` to check/reset it; give `Hazard` a tick accumulator
     and change `_update_hazards` to deal `dps · tick` on the tick boundary.
   - Balance note: total DPS should stay ~unchanged for armor-0 heroes; armored
     heroes now actually take reduced-but-nonzero contact/DoT.

2. **Armor as a rate for continuous sources.** At the contact/hazard call sites,
   subtract `armor · dt` rather than the full `armor`. Smallest diff, but "armor"
   now means two different things depending on the source.

3. **Exempt continuous damage from flat armor.** Add a keyword to
   `take_damage` (`mitigate=False` or `flat_armor=False`); contact/hazard/DoT
   pass it. Simple, but armor then does nothing against contact/DoT — a
   deliberate balance choice, not just a bug fix.

**Recommendation:** option 1. It keeps armor meaningful, matches the existing
discrete-hit model, and localises the change to two call sites plus a timer.

### Regression coverage to add with the fix

- Armored hero (aegis) standing on a `tank` for N seconds loses a **non-zero,
  armor-reduced** amount of HP.
- Armor-0 hero (kestrel) standing in a 20-dps hazard for 3 s loses ≈ 60 HP
  (unchanged from today).
- A single contact "bite" respects armor: `contact_damage 16` vs `armor 4`
  deals `12` per bite, not `0`.
- DoT (burn) on the hero still ticks regardless of armor (decide during the fix
  whether DoT should be armor-gated at all — currently enemy DoT bypasses armor
  entirely via `_status_damage`, and there is no hero-DoT path yet).

### Resolution — CB-1 (2026-08-27)

Option 1 shipped. Contact and hazard now deal a **timed bite** — `rate ·
interval` before armor, one `take_damage` call per `interval` — instead of a
per-frame `rate · dt` sliver, so flat armor bites a meaningful chunk.
`interval` defaults to `config.INCOMING_TICK_INTERVAL` (0.5 s) and is
per-attack overridable (`contact_interval` on enemies/boss, `hazard_tick` on
warlock hazards). `contact_damage` and hazard `dps` were bumped +5 to offset the
armor subtraction. `Player.take_damage` is unchanged. Full checklist +
verification in `combat_balance_journal.md` CB-1; regression tests in
`tests/test_incoming_damage.py`. Headless check: Aegis (armor 4) with 5 chasers
on top for 3 s now goes 160 → 133 (was 160 → 160).

### Related reading

`../documentation/COMBAT_CALCS.md` §2 (incoming pipeline) and §5b / §5c (the two
worked examples, updated to the bite model).
