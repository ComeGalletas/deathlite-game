# Combat damage — full calculation reference

How a number travels from a weapon (or an enemy) all the way to an HP bar, with
the exact code at every step. Two pipelines:

- **Outgoing** — a hero weapon reducing an enemy's HP (§1)
- **Incoming** — an enemy reducing the hero's HP (§2)

Both are fed by the layered stat system (§0). Boss specifics are in §3, and §4
lists what the model deliberately does *not* do. §5 has worked numeric
examples.

> File references are `path — function`. Line numbers drift, so snippets are
> quoted inline; the function names are stable.

---

## 0 · Stat resolution — the inputs

Every hero stat is a base value plus layered modifiers from the character,
level-up upgrades, blessings, equipped items and meta-progression. Final value:

```
final = (base + ΣFLAT) · (1 + ΣPCT) · Π(1 + each MULT)
```

`progression/stats.py — StatSet._recompute`:

```python
for m in self._mods:
    if m.op == FLAT:  flat[m.stat] = flat.get(m.stat, 0.0) + m.value
    elif m.op == PCT: pct[m.stat]  = pct.get(m.stat, 0.0) + m.value
    else:             mult[m.stat] = mult.get(m.stat, 1.0) * (1.0 + m.value)   # MULT

for stat in set(list(out) + list(flat) + list(pct) + list(mult)):
    base = out.get(stat, 0.0)
    val = (base + flat.get(stat, 0.0)) * (1.0 + pct.get(stat, 0.0))
    val *= mult.get(stat, 1.0)
    if stat in _NON_NEGATIVE:
        val = max(0.0, val)
    out[stat] = val
```

`FLAT`/`PCT` are pooled (order-independent); `MULT` entries compound. Each
`Modifier` carries a `source` string so a whole blessing/item can be removed
atomically on unequip.

`entities/player.py — Player.recompute` caches the result as a plain dict so the
combat loop never runs the solver:

```python
def recompute(self) -> None:
    self.stats = self.statset.as_dict()
    if hasattr(self, "hp"):
        self.hp = min(self.hp, self.max_hp)
```

Damage-relevant stats: `damage_multiplier`, `attack_speed_multiplier`,
`projectile_speed_multiplier`, `area_multiplier`, `luck`, `crit_chance`,
`crit_damage`, `armor`, `max_hp`.

---

## 1 · Outgoing — hero weapon → enemy HP

### 1a · Base weapon damage

`combat/weapons.py — Weapon._damage`:

```python
def _damage(self) -> float:
    return float(self.definition["damage"]) + self.bonus["damage"]
```

`definition["damage"]` is from `data/weapons.json`; `bonus["damage"]` is added by
level-up upgrades.

### 1b · `outgoing_damage()` — global multiplier + crit, frozen at spawn

`combat/damage.py — outgoing_damage`:

```python
def outgoing_damage(base, damage_multiplier, crit_chance=0.0,
                    crit_multiplier=2.0, rng=None):
    amount = max(0.0, base) * max(0.0, damage_multiplier)
    is_crit = False
    if crit_chance > 0.0:
        roll = (rng or random).random()
        if roll < crit_chance:
            amount *= crit_multiplier
            is_crit = True
    return DamageResult(amount=amount, is_crit=is_crit)
```

This runs **once per projectile at fire time**; the result is written to
`projectile.damage` and does not recompute in flight. Multi-shot weapons roll
crit independently per projectile.

### 1c · `FireContext` assembly — where the multipliers come from

`game/states/playing_state.py — _phase_combat`:

```python
s = self.player.stats
ctx = FireContext(
    origin=self.player.pos, enemies=self._targetables(),
    damage_multiplier=s["damage_multiplier"] * self.player.outgoing_damage_multiplier(),
    attack_speed_multiplier=s["attack_speed_multiplier"],
    projectile_speed_multiplier=s["projectile_speed_multiplier"],
    area_multiplier=s["area_multiplier"], fallback_dir=self._last_move_dir,
    spawn_projectile=self._spawn_projectile, anchor=self.player.pos,
    crit_chance=min(0.75, 0.02 * s["luck"] + s["crit_chance"]),
    crit_multiplier=2.0 + s["crit_damage"],
    rng=self.rng, spawn_summon=self._spawn_summon)
if not (self.dev_mode and self._dev_no_attack):
    for weapon in self.player.weapons:
        weapon.update(dt, ctx)
```

- `damage_multiplier` = `stats["damage_multiplier"] · player.outgoing_damage_multiplier()`
- `crit_chance` = `min(0.75, 0.02·luck + stats["crit_chance"])`
- `crit_multiplier` = `2.0 + stats["crit_damage"]`

`entities/player.py — Player.outgoing_damage_multiplier` (Kestrel / Windborne
only):

```python
def outgoing_damage_multiplier(self) -> float:
    if self.trait == "windborne":
        return 1.0 + 0.07 * self.momentum      # momentum 0..5
    return 1.0
```

The weapon then calls `outgoing_damage(self._damage(), ctx.damage_multiplier,
ctx.crit_chance, ctx.crit_multiplier, ctx.rng)` per projectile
(`combat/weapons.py — Weapon._fire`). Orbit weapons refresh `damage` every frame
but skip the crit roll (`Weapon._maintain_orbit`:
`dmg = outgoing_damage(self._damage(), ctx.damage_multiplier).amount`).

### 1d · Hit resolution — the per-target multiplier

`game/states/playing_state.py — _resolve_projectile_hits`:

```python
for proj in self.projectiles:
    ...
    for enemy in near:
        if not enemy.alive or id(enemy) in proj.hit_ids:      continue
        if not circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                               enemy.pos.x, enemy.pos.y, enemy.radius):  continue
        if proj.cone_half_angle > 0.0 and not self._in_cone(proj, enemy):  continue

        amount = proj.damage * self._damage_multiplier(proj, enemy)
        dealt  = enemy.take_damage(amount)
        proj.hit_ids.add(id(enemy))
        self.stats["damage_dealt"] += dealt
        self.damage_numbers.add(enemy.pos, dealt, proj.is_crit)
        ...
        if proj.knockback:
            enemy.apply_knockback(enemy.pos - proj.pos, proj.knockback)
        self._apply_on_hit_effects(proj, enemy)
        self.game.events.publish(Events.DAMAGE_DEALT, amount=dealt)
        if proj.chain_left > 0 and self._chain_to_next(proj, targets):  continue
        proj.on_hit()
        if not proj.active:  break
```

`game/states/playing_state.py — _damage_multiplier`:

```python
def _damage_multiplier(self, proj, enemy) -> float:
    """Blessing tag bonuses + Shock + status-vulnerability synergy."""
    fx = self.player.blessing_fx
    mult = 1.0 + fx.tag_bonus(proj.source_tags, getattr(enemy, "is_elite", False))
    mult *= enemy.status.damage_taken_multiplier()
    mult += fx.vuln_bonus(proj.source_tags, enemy.status)
    return mult
```

Its three inputs:

**tag_bonus** — `progression/blessings.py — BlessingEffects.tag_bonus`:

```python
def tag_bonus(self, tags, is_elite: bool) -> float:
    total = sum(self.tag_damage.get(t, 0.0) for t in tags)
    if is_elite:
        total += self.tag_damage.get("elite", 0.0)
    return total
```

`tag_damage` is the flattened table built from every owned blessing stack **and**
every equipped item's `tag_damage` affixes (`progression/blessings.py — rebuild`).

**damage_taken_multiplier** — `combat/status.py — StatusState.damage_taken_multiplier`:

```python
def damage_taken_multiplier(self) -> float:
    m = 1.0
    for a in self._active.values():
        if a.kind.family == "amp":
            m *= (1.0 + a.potency)          # Shock: ×1.10 by default
    return m
```

**vuln_bonus** — `progression/blessings.py — BlessingEffects.vuln_bonus`:

```python
def vuln_bonus(self, tags, status_state) -> float:
    total = 0.0
    for status, atk_tag, frac in self.status_vuln:
        if status in status_state and (atk_tag is None or atk_tag in tags):
            total += frac
    return total
```

Note the structure: tag_bonus and amp **multiply** the base, then vuln_bonus is
**added** to that multiplier.

### 1e · `Enemy.take_damage()`

`entities/enemy.py — Enemy.take_damage`:

```python
def take_damage(self, amount: float, armor: float = 0.0) -> float:
    dealt = apply_armor(amount, armor)          # projectile path passes NO armor -> no-op
    self.hit_flash = 0.08
    if self.anim is not None:
        self._hurt_t = 0.26
        self.anim.play("hurt", restart=True)
    if self.shield_hp > 0.0:
        absorbed = min(self.shield_hp, dealt)
        self.shield_hp -= absorbed
        dealt -= absorbed
    self.hp -= dealt
    if self.hp <= 0:
        self.hp = 0.0
        self.alive = False
    return dealt
```

`_resolve_projectile_hits` calls `enemy.take_damage(amount)` with **no** `armor`
argument — enemies get no armor mitigation on hits; only **shields** absorb.

`combat/damage.py — apply_armor` (used here with `armor=0`, and by the boss / by
DoT-free paths):

```python
def apply_armor(amount: float, armor: float) -> float:
    """Flat armor: subtracts from incoming damage, never below zero."""
    return max(0.0, amount - max(0.0, armor))
```

### 1f · Side effects of a landed hit

**On-hit status procs** — `game/states/playing_state.py — _apply_on_hit_effects`:

```python
def _apply_on_hit_effects(self, proj, enemy) -> None:
    fx = self.player.blessing_fx
    for status, tag, chance, dur, potency in fx.on_hit:
        if tag is not None and tag not in proj.source_tags:
            continue
        if self.rng.random() < chance:
            enemy.status.apply(
                status,
                dur * (1.0 + fx.tuned(status, "duration")),
                potency * (1.0 + fx.tuned(status, "potency")),
                bonus_max_stacks=int(fx.tuned(status, "max_stacks")))
    # Nihil / Cursebrand: first hit on each enemy applies Shock.
    if self.player.trait == "cursebrand" and id(enemy) not in self.player._hexed:
        self.player._hexed.add(id(enemy))
        enemy.status.apply("shock", 4.0, 0.10)
```

**Chain** — `game/states/playing_state.py — _chain_to_next` redirects the
projectile to the nearest un-hit target, decrements `chain_left`, keeps it alive.

**Pierce** — `entities/projectile.py — Projectile.on_hit`:

```python
def on_hit(self) -> None:
    if self.pierce_left > 0:
        self.pierce_left -= 1
    else:
        self.active = False
```

Orbit projectiles never call `on_hit` to expire; instead they clear `hit_ids`
every `rehit_interval` so they keep scoring:

```python
if self.rehit_interval > 0.0:
    self.rehit_timer -= dt
    if self.rehit_timer <= 0.0:
        self.rehit_timer = self.rehit_interval
        self.hit_ids.clear()
```

### 1g · Damage over time (a separate loop)

`entities/enemy.py — Enemy.update` runs the status tick each frame:

```python
self.status.update(dt, lambda amt: self._status_damage(amt, ctx))
```

`combat/status.py — StatusState.update` — one loop, family dispatch:

```python
for sid, a in self._active.items():
    a.time_left -= dt
    if a.kind.family == "dot" and a.kind.tick_interval > 0.0:
        a._tick_accum += dt
        while (a._tick_accum >= a.kind.tick_interval
               and a.time_left > -a.kind.tick_interval):
            a._tick_accum -= a.kind.tick_interval
            apply_damage(a.potency * a.stacks)      # per tick, scaled by stacks
```

`entities/enemy.py — Enemy._status_damage` — straight to HP, no armor, no shield,
reported for the run stat:

```python
def _status_damage(self, amount: float, ctx) -> None:
    if not self.alive:
        return
    self.hp -= amount
    ctx.report_damage(amount)
    if self.hp <= 0:
        self.hp = 0.0
        self.alive = False
```

Tick intervals: `burn` 0.5 s, `poison` 0.75 s, `bleed` 0.4 s (`combat/status.py`).

### 1h · On-kill procs

At the instant `alive` flips false — `game/states/playing_state.py —
_cull_dead_enemies` → `_apply_on_kill_effects`:

```python
for effect, chance, amount in self.player.blessing_fx.on_kill:
    if self.rng.random() >= chance:
        continue
    if effect == "soul":       gem.reset(enemy.pos, int(amount) or 3, is_soul=True)
    elif effect == "heal":     self.player.heal(amount)
    elif effect == "fire_nova" and "burn" in enemy.status:
        self._enemy_explosion(enemy.pos, 70.0, float(amount) or 16.0)
    elif effect == "shock_spread" and "shock" in enemy.status:
        self._spread_status(enemy.pos, "shock", 3.0, 0.12)
```

`fire_nova` / `shock_spread` damage **other enemies** only, never the player
(`_enemy_explosion` iterates `grid.query_circle` and calls `enemy.take_damage`).

---

## 2 · Incoming — enemy → hero HP

### 2a · The source computes an amount

Every incoming source resolves to **one `take_damage` call per hit**. The two
continuous sources (contact, hazard) are chunked into timed "bites" — a per-frame
slice would be absorbed whole by flat armor (see `../journals/BUG_JOURNAL.md`
#1 → resolved by CB-1). The chunk is `rate · interval`, so pre-armor DPS is
unchanged; `interval` defaults to `config.INCOMING_TICK_INTERVAL` (0.5 s) and is
overridable per attack (§2a·i).

| Source | Amount passed to `take_damage` | Cadence | Site |
|--------|-------------------------------|---------|------|
| Hostile projectile | `enemy.cfg["shoot_damage"]` (default 6) | one call on overlap | `_resolve_hostile_hits` |
| Body contact | `enemy.contact_damage · enemy.contact_interval` | one call per `contact_interval` per enemy (paced by `enemy.contact_cd`) | `_resolve_enemy_contact` |
| Hazard pool | `hz.dps · hz.tick_interval` | one call per `tick_interval` per hazard (paced by `hz._tick_accum`) | `_update_hazards` |
| Explosion (exploder death / brute slam / boss) | `damage` | one call if in radius | `_explosion` |

`game/states/playing_state.py — _resolve_hostile_hits`:

```python
if circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                   self.player.pos.x, self.player.pos.y, pr):
    taken = self.player.take_damage(proj.damage)
    proj.active = False
    if taken > 0:
        self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
```

`game/states/playing_state.py — _resolve_enemy_contact` (a bite per
`contact_interval`; `Enemy.update` / `Boss.update` tick `contact_cd` down):

```python
for enemy in contacts:
    if not enemy.alive or enemy.contact_cd > 0.0:
        continue
    if circles_overlap(self.player.pos.x, self.player.pos.y, pr,
                       enemy.pos.x, enemy.pos.y, enemy.radius):
        enemy.contact_cd = enemy.contact_interval
        taken = self.player.take_damage(
            enemy.contact_damage * enemy.contact_interval)
        if taken > 0:
            self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
```

`game/states/playing_state.py — _update_hazards` +
`entities/hazard.py — Hazard.due_damage`:

```python
# _update_hazards
if hz.alive and hz.contains(self.player.pos, self.player.radius):
    bite = hz.due_damage(dt)                     # dps * tick_interval, or 0.0
    if bite > 0.0:
        taken = self.player.take_damage(bite)
        if taken > 0:
            self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
else:
    hz.reset_ticks()                             # partial exposure does not bank

# Hazard.due_damage
self._tick_accum += dt
owed = 0.0
while self._tick_accum >= self.tick_interval:
    self._tick_accum -= self.tick_interval
    owed += self.dps * self.tick_interval
return owed
```

`game/states/playing_state.py — _explosion`:

```python
if (self.player.pos - pos).length() <= radius + self.player.radius:
    taken = self.player.take_damage(damage)
    if taken > 0:
        self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
```

FSM chargers/teleporters raise their own `contact_damage` transiently during an
attack; `Enemy.update` resets it to `_base_contact` each frame, and
`enemy_ai._fsm_enter` zeroes `contact_cd` on entering the `attack` state so the
charge/blink always lands its first bite at the bumped value.

### 2a·i · Per-attack tick interval

`config.INCOMING_TICK_INTERVAL` (0.5 s) is only the default. A hazard can pass
its own via `hazard_tick` in `data/enemies.json` (→ `Hazard.tick_interval`); an
enemy or boss can set `contact_interval` in its JSON (→ `Enemy.contact_interval`
/ `Boss.contact_interval`).

Roles of the interval `T` (deliberately the same number for both):

- **cadence** — one `take_damage` per `T`
- **chunk** — each call carries `rate · T` before armor

Because `chunk / cadence = rate`, pre-armor DPS is independent of `T`. `T` only
changes how lumpy the damage is and **how often armor's flat subtraction
applies** (smaller `T` ⇒ more subtractions per second ⇒ armored heroes take
proportionally less).

**Floor condition.** A bite must beat armor or that attack does nothing to an
armored hero — re-introducing BUG #1 for that one attack:

```
rate · T · bulwark  >  armor        →     T  >  armor / (rate · bulwark)
```

Keep `rate · T ≥ ~20` for this game's armor range.

**"Same total damage, faster".** Scale `rate → k·rate`, `duration → duration/k`,
`T → T/k`: total raw (`rate·duration`), bite size (`rate·T`) and bite count
(`duration/T`) are all unchanged — the same bites just arrive `k×` faster.

### 2b · `Player.take_damage()`

`entities/player.py — Player.take_damage`:

```python
def take_damage(self, amount: float) -> float:
    if self.invulnerable or not self.alive:
        return 0.0
    amount *= self.incoming_damage_multiplier()
    dealt = max(0.0, amount - self.stats["armor"])       # FLAT armor, per call
    self.hp -= dealt
    if dealt > 0:
        self._hurt_t = 0.30
    if self.hp <= 0:
        self.hp = 0.0
        self.alive = False
    return dealt
```

`entities/player.py — Player.incoming_damage_multiplier` (Aegis / Bulwark only):

```python
def incoming_damage_multiplier(self) -> float:
    if self.trait == "bulwark" and self.still_time >= 0.4:
        return 0.7
    return 1.0
```

`still_time` accrues while `_move_dir` is zero and resets to 0 on any movement
(`entities/player.py — Player.update`).

`Player.take_damage` is **unchanged by CB-1** — flat armor still subtracts once
per call. What changed is that contact and hazard now call it **once per bite**
(§2a) instead of once per frame, so armor bites a `rate · interval` chunk.

The whole incoming model is: **invuln check → Bulwark ×0.7 (or ×1) → flat armor
→ HP → death**, applied per hit / per bite. No shield, no crit-taken, no status
amplification on the hero.

### 2c · Feedback

Every incoming site publishes `Events.PLAYER_DAMAGED` with `amount=taken` when
`taken > 0`. `game/states/playing_state.py — _on_player_damaged`:

```python
def _on_player_damaged(self, *, amount) -> None:
    self.shake.add(min(0.4, 0.05 + amount * 0.02))
    self._hurt_flash_t = min(0.35, self._hurt_flash_t + 0.12 + amount * 0.01)
```

The audio manager plays `player_hurt` off the same event. The pulsing red
low-HP vignette draws whenever `hp / max_hp < 0.3`
(`_draw_feedback_overlays`).

### 2d · Developer-mode HP ratchet

Only when the dev-menu "Unlimited HP" toggle is on. `game/states/playing_state.py
— update`:

```python
self.stats["time"] += dt
self._apply_dev_unlimited_hp()
if not self.player.alive:
    ...
```

`game/states/playing_state.py — _apply_dev_unlimited_hp`:

```python
def _apply_dev_unlimited_hp(self) -> None:
    if not (self.dev_mode and self._dev_unlimited_hp):
        return
    self._dev_hp_floor = max(self._dev_hp_floor, self.player.hp)
    if self.player.hp < self._dev_hp_floor:
        self.player.hp = self._dev_hp_floor
    if not self.player.alive and self._dev_hp_floor > 0.0:
        self.player.alive = True
```

It runs **after** the pipeline and **before** the death check, so HP can dip and
flash within a frame but never ends a frame below where it started; the floor
ratchets up with healing and never drops.

---

## 3 · Boss specifics

`entities/boss.py — Boss.take_damage`:

```python
def take_damage(self, amount: float, armor: float = 0.0) -> float:
    dealt = apply_armor(amount, armor)
    self.hp -= dealt
    self.hit_flash = 0.06
    if self.hp <= 0:
        self.hp = 0.0
        self.alive = False
    return dealt
```

- The boss is included in `_targetables()` while alive, so it goes through the
  full §1d outgoing pipeline (tag bonus, amp, vuln, damage numbers).
- It has **no shield** and, like enemies, is called with `armor=0` from the
  projectile resolver.
- `apply_knockback` is a no-op — the boss is immovable.
- Boss → player damage is via `_explosion` (radial barrage / slam patterns),
  `_fire_hostile` shots, and body contact — the ordinary §2 incoming paths. The
  boss also carries `contact_cd` / `contact_interval` and bites like an enemy.

---

## 4 · What the model does **not** do

- **Hero has no shield, no crit-taken, no status-amp.** Incoming = invuln →
  Bulwark → flat armor → HP.
- **Enemies/boss take no armor mitigation on projectile hits** — only shields
  (`Enemy.shield_hp`) absorb.
- **DoT ticks bypass armor and shields entirely** (`_status_damage` goes straight
  to `hp`).
- **Outgoing crit is rolled once at spawn** and frozen onto the projectile;
  in-flight buffs do not retro-apply (except orbit weapons, which refresh
  `damage`/`radius` live but never crit).
- **`damage_multiplier` from `player.stats` and the Windborne momentum factor are
  the only global scalars**; there is no separate "melee vs ranged" or
  elemental-resistance layer.

---

## 5 · Worked examples

### 5a · Aegis Soul Scythe hit on a burning, shocked elite

- Weapon: `damage` 14, `bonus["damage"]` +4 from an upgrade → base **18**.
- `stats["damage_multiplier"]` 1.15, not Windborne → `ctx.damage_multiplier` = **1.15**.
- `crit_chance` = `min(0.75, 0.02·2 + 0.05)` = **0.09**; roll misses → no crit.
- `outgoing_damage`: `18 · 1.15` = **20.7** → `projectile.damage`.
- Enemy is elite, burning (no amp), shocked (`amp` 0.10), and the build has
  "+25% to area hits" and "+40% vuln to shocked from area":
  - `tag_bonus` = 0.25 (area) + 0.10 (elite) = 0.35 → `1 + 0.35` = 1.35
  - `damage_taken_multiplier` = `1 + 0.10` (shock) = 1.10
  - `vuln_bonus` = 0.40
  - `_damage_multiplier` = `1.35 · 1.10 + 0.40` = **1.885**
- `amount` = `20.7 · 1.885` = **39.0**.
- `enemy.take_damage(39.0)`: no armor; shield 0 → `hp -= 39.0`.

### 5b · Tank body-contact on Aegis (post CB-1)

- `tank.contact_damage` = 21 (16 + the CB-1 compensation bump),
  `contact_interval` = 0.5 → bite = `21 · 0.5` = **10.5** before armor,
  once per 0.5 s.
- Aegis moving (no Bulwark): `dealt = max(0, 10.5·1.0 − 4)` = **6.5** per bite →
  **13 HP/s**.
- Aegis standing still (Bulwark ×0.7): `max(0, 10.5·0.7 − 4)` = **~4.05** per
  bite → **~8 HP/s**.
- Pre-CB-1 this was `max(0, (21/120)·0.7 − 4)` = **0** every frame — immune.
  Fixed; see `../journals/BUG_JOURNAL.md` entry #1.

### 5c · Warlock hazard on Kestrel (armor 0)

- `hazard_dps` = 23 (18 + the bump), `tick_interval` = 0.5 → bite = `23 · 0.5`
  = **11.5**, once per 0.5 s; Windborne, no incoming multiplier.
- `dealt = max(0, 11.5 − 0)` = **11.5** per bite → **23 HP/s**; over the 3.5 s
  pool ≈ 7 bites ≈ 80 HP.
- The same pool on Aegis moving (armor 4): `max(0, 11.5 − 4)` = **7.5** per bite
  → **15 HP/s** (mitigated, not immune).
