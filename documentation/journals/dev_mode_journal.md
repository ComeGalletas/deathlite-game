# Developer mode — dev log

A separate log for the **developer mode** feature, the same way `assets_journal.md`
tracks the art passes. The general `journal.md` gets a one-paragraph pointer here.

Milestones are **D1–D6** (unrelated to the spec's Milestones 1–10 or the
start-screen M1–M5). Each ends green — `python -m unittest discover -s tests`
plus a windowed / headless-screenshot check — before the next.

**Status:** D1–D5 done (D5 2026-08-28). D6 (docs) pending. All assumptions
confirmed. Post-plan toggles collected under **Later additions** below (latest:
the "Forges..." and "Remove weapon..." pages, 2026-09-10).

---

## Goal

A non-persistent "sandbox" run for testing: start it from the main menu, open a
dev menu with a key, and from there lock HP, silence the hero's weapons, spawn
any enemy, grant any blessing or item, or wipe the run back to a clean level-1
state. Leaving (pause → quit, or the dev menu's own exit) returns to the main
menu and **writes nothing to `save.json`**.

## Requirements (as given)

1. **Unlimited HP** — the hero can still take hits (flash / knockback / feedback
   all fire) but the HP value never drops.
2. **Stop-attacking toggle** — the hero's weapons stop firing; the hero can
   still take damage.
3. **Spawn enemies** — list every enemy type; selecting one spawns a single
   instance of it.
4. **Items & blessings** — a menu to grant items and blessings to the hero.
5. **Reset** — remove all changes and reset the hero and the level.

Plus: the mode **doesn't save**, and it can be exited to the main menu from
**both** the pause menu and the dev menu.

## Interpretations / assumptions (please confirm)

| # | Assumption |
|---|-----------|
| **A** | **Access key = backtick / tilde (`` ` ``, `pygame.K_BACKQUOTE`)**, and only while a dev-mode run is active. It doesn't collide with movement, `E`, `ESC`, `M`, or the `F1`–`F7` debug keys. |
| **B** | A dev run still goes through **Character Select** (so any hero can be tested); a `dev=True` flag is threaded `MenuState → CharacterSelectState → PlayingState`. |
| **C** | **"Unlimited HP" is a ratchet.** Each frame, after damage resolves, `player.hp` is clamped so it is never below where it was at the start of that frame, and `player.alive` is forced back to `True`. Healing can still raise the floor; it never lowers. So damage *registers* (hurt flash, screen shake, `PLAYER_DAMAGED`) but the number never goes down. |
| **D** | **"Stop attacking"** skips the `weapon.update()` loop in `_phase_combat`. Already-placed summons (totem / wolf) keep acting; incoming damage to the hero is untouched. |
| **E** | ~~**"Select items"** = pick a **slot** × **rarity**; `generate_item()` gains a `rarity=` argument.~~ **Superseded at D5** (user request): the Items page instead lists every weapon and every equipment base straight from the loaded content (like the Blessings page), and `generate_item()` gained `base_id=` (not `rarity=`). See the D5 row. |
| **F** | **"Reset"** = restart the dev run in place: **same world seed** (layout repeats, for reproducible testing), level 1, base hero, no blessings / items / upgrades, timer 0, enemies cleared. |
| **G** | The menu entry label drops the parenthetical — **"Start new developer mode game"** — now that it does something. |
| **H** | **"Doesn't save"** = the one run-data save path (`Game._on_run_ended` → `persist()`: salvage bank, best-run, item stash) is skipped for a dev run. Audio-settings persistence (Options screen / `M` key) is unaffected. |
| **I** | **Death in a dev run** (only possible with Unlimited HP off) triggers the **same reset as F** — the dev run restarts in place (same world seed, level 1, base hero, cleared) rather than going to a summary or the menu. |

## Milestones

| # | Scope | Ends when |
|---|-------|-----------|
| **D1 ✅** | **Plumbing + entry.** `PlayingState.enter(..., dev=False)` → `self.dev_mode`. `CharacterSelectState.enter` captures `_dev` from kwargs and forwards it to the run. `MenuState`: the dev entry is now `("Start new developer mode game", "dev_start")`; `_activate` routes both `start` and `dev_start` to `CharacterSelectState`, passing `dev=(action == "dev_start")`. `Game._on_run_ended(..., dev=False)` returns immediately when `dev` — no salvage bank / best / stash / `persist()`. `PlayingState._end_run` publishes `RUN_ENDED` with `dev=self.dev_mode`; for a dev run it calls the new `_restart_dev_run()` (`change(PlayingState, character_id=…, seed=self.run_seed, dev=True)`) instead of Victory/GameOver — this is also the death path (via the normal `_end_run(victory=False)`) and the future D2 "Reset run" row. **Done 2026-08-27** — `tests/test_dev_mode.py` (7): flag rides menu → char-select → playing; regular run isn't dev; `_on_run_ended(dev=True)` leaves `save` untouched and doesn't `persist`; a dev-run death re-enters a *fresh* `PlayingState` (same seed, empty `blessings`, starting weapon count, `time≈0`) with `persist` never called and `save.json` never written; a dev run end never opens a summary state; pause → `Q` → `MenuState` with no persist. `test_menu.py` updated (dev entry now opens a dev char-select). Full suite **269 → 277**; scripted `Game` flow confirms the whole path incl. `save.json` never created. |
| **D2 ✅** | **The dev menu overlay — root page + toggles.** New `game/states/dev_menu_state.py::DevMenuState` (`draw_below=True`, `update_below=False` — the run freezes, still visible). `PlayingState.handle_event` pushes it on `K_BACKQUOTE` **iff `self.dev_mode`**, passing `playing=self`. Rows: **Unlimited HP** / **Stop attacking** (toggles, `[ON]`/`[  ]`), **Spawn enemy… / Blessings… / Items…** (inert — status line "(coming soon)"), **Reset run**, **Exit to main menu**, **Close**. Up/Down/W/S + `ENTER`; `ESC` or `` ` `` closes. Toggles flip `_playing._dev_unlimited_hp` / `_dev_no_attack` (turning Unlimited HP on while dead also revives to full and seeds `_dev_hp_floor`). `PlayingState`: `_apply_dev_unlimited_hp()` runs in `update()` after `_phase_progression`, before the alive-check — a monotone HP floor (`max(floor, hp)` then clamp up, `alive=True`); `_run_death_sequence` cancels itself if the toggle came on mid-animation; the `weapon.update` loop in `_phase_combat` is skipped when `_dev_no_attack`. **Reset run** / death → `_restart_dev_run()`. **Exit** → `change(MenuState)`. **Close** → `pop()`. **Done 2026-08-27** — `tests/test_dev_mode.py` `DevMenuTests` (9): opens only in a dev run + is an overlay; run frozen while open; Unlimited HP keeps `player.hp` from dropping with a `tank` sat on the hero and `alive` stays True; Stop-attacking pins `stats["damage_dealt"]` (and it resumes rising when toggled back); Reset restarts on the same seed with a fresh hero; Exit → `MenuState` with `persist` uncalled; Close resumes the exact `PlayingState`; the three "…" rows don't navigate; headless `draw` per row. Full suite **277 → 286**; screenshot shows the panel over the frozen run with both toggles `[ON]`. |
| **D3 ✅** | **Spawn-enemy submenu.** `DevMenuState` gained a `page` field (`"root"` / `"enemies"`); the root **Spawn enemy…** row now `_goto("enemies")`. The enemies page lists `sorted(content.enemies)` (13); `ENTER` calls `_playing._spawn_enemy(eid, at=player.pos + Vector2(120,0).rotate(random))` and **stays on the page** (spam-friendly), bumping a per-id `_spawn_counts` shown as `(xN)` and in the status line; `ESC` / `` ` `` → root (a second `ESC` from root closes). **Done 2026-08-27** — `tests/test_dev_mode.py` `DevSpawnMenuTests` (5): the row opens the page and it lists every enemy id (sorted); `ENTER` appends exactly one `Enemy` of the selected id and increments its count; six presses → six enemies, page still open; `ESC` → root without closing the menu; the spawn lands within 300 px of the hero. D2's placeholder test narrowed to blessings/items only. Full suite **286 → 291**; screenshots show the 13-row page and the spawned cluster around the hero. |
| **D4 ✅** | **Blessings submenu + a scroll viewport (folded in).** `DevMenuState` now scrolls any page longer than `MAX_VISIBLE` (12): `_move()` keeps `self.sel` inside a window that `_clamp_scroll()` slides, `draw()` renders only `rows[scroll : scroll+window]` with `^ N more` / `v N more` markers and a **fixed** panel height — so adding enemies/blessings can never push rows off-screen. New page `"blessings"`: the root **Blessings…** row `_goto`s it; rows are `{source[0]}-{name}` (+ `xN` when owned), sorted by `(source, name)`; `ENTER` → `apply_blessing(_playing.player, _playing.blessing_lib.by_id[bid])` (stacks freely — it's a sandbox), status shows the new stack count; `ESC` → root. **Done 2026-08-27** — `tests/test_dev_mode.py`: `DevBlessingMenuTests` (3 — page lists every `content.blessings` id; `ENTER` sets `player.blessings[bid]` to 1 then 2 and swaps in a fresh `blessing_fx`; `ESC` → root) + `DevMenuScrollTests` (4 — selection stays in the window while sweeping/wrapping a 32-row page; `UP` from row 0 wraps to the last row with `scroll == n - MAX_VISIBLE`; an 8-row page never scrolls; headless `draw` at several scroll offsets). The enemies page (13 rows) now scrolls by one, same mechanism. Full suite **291 → 298**; screenshot shows the 12-row window with both "N more" markers on the 32-blessing list. |
| **D5 ✅** | **Items submenu — data-driven list.** *(Design changed from the original "slot × rarity chooser" at the user's request: the page lists the actual content, like the blessings page, so it grows/shrinks with the data.)* Page `"items"` rows are built in `enter()` from the loaded content — `[("weapon", id) for id in sorted(content.weapons)]` + `[("item", slot, base["id"]) for slot in sorted(content.items["bases"]) for base in …]` — so 7 weapons + 6 equipment bases today, more if `weapons.json` / `items.json` grow. `_row_label` renders `weapon   <name>` for an auto-fire weapon and `[<slot>]   <name>` for an equipment base, each with a `xN` grant counter. `ENTER`: a `weapon` row appends `Weapon(id, def)` to `player.weapons` (stacks — sandbox); an `item` row calls `generate_item(content, seed=run_seed*1000 + n, item_level=1, luck=…, slot=slot, base_id=bid)` then `_dev_equip()` — append to `player.equipment`, `player.add_modifiers(*Modifier(stat, _OP_MAP[op], val, "dev:item:<slot>#<n>") for stat/op/val in item.stat_effects())`, `rebuild_blessings(player, blessing_lib)` (folds tag affixes into `blessing_fx`), HP topped to the new max — mirrors `PlayingState._apply_persistent_bonuses`. `progression.items.generate_item` gained **`base_id: str \| None = None`** (not `rarity=`): the `rng.choice(bases[slot])` draw still happens unconditionally so a `base_id=None` call is byte-identical to before, then the result is overridden when a base is forced. `_activate("items")` → `_goto("items")`; `ESC` → root; the "(coming soon)" placeholder + its `else` branch removed. **Done 2026-08-28** — `tests/core/test_dev_mode.py` `DevItemMenuTests` (5): page lists every weapon + every base from `content`; `ENTER` on a weapon row adds it (`weapon_id` match, stacks); `ENTER` on the `weapon`/`sigil` base row grows `player.equipment` and raises `stats["damage_multiplier"]`; `generate_item(base_id=…)` forces the base; `ESC` → root + headless `draw` on every row. `test_items_row_is_an_inert_placeholder` → `test_items_row_opens_the_items_page`. Suite **587 → 592**; screenshot shows the 13-row `GRANT ITEM` page with the `weapon` / `[slot]` grouping and `xN` counters. |
| **D6** | **Docs.** Finish this file (tick D1–D6 + a "How to use" section). `README.md` — a "Developer mode" note (the `` ` `` key, what each option does, "does not save"). `journal.md` + `transcript.md` — short "Developer mode" entries. | full `unittest` + windowed `python main.py` dev run |

## Later additions (post-D5, outside the original D1–D6 plan)

### "Attacks deal 0 damage" toggle — done 2026-08-29

A third root toggle, between **Stop attacking** and **Collision shapes**:
`_ROOT_ROWS` gains `"no_damage"`, `_LABELS["no_damage"] = "Attacks deal 0
damage"`, and `_activate` / `_row_label` handle it exactly like `no_attack`
(flips `PlayingState._dev_no_damage`, shows `[ON]`/`[  ]`).

Unlike **Stop attacking** (which skips the `weapon.update()` loop entirely),
this keeps every weapon firing — animation, projectiles, orbiters, the summon
bite/bolt, and **CB-3 knockback** all still happen — but the hit does no HP
damage. Hook is a single guard at the top of
`CombatResolver.projectile_hits`: `no_dmg = ps.dev_mode and ps._dev_no_damage`
→ `amount = 0.0` before `take_damage`, and `apply_on_hit_effects` (burn / chill
/ shock, Cursebrand's shock-on-first-hit) is skipped so a DoT can't kill either.
`take_damage(0)` still plays the hit flash / hurt anim and leaves `shield_hp`
untouched; the floating number shows `0`, which doubles as "yes, it connected".
Enemy contact damage to the hero and hostile projectiles are unaffected — this
only zeroes the hero's outgoing weapon hits.

Purpose: watch attack cadence, reach gating, knockback and enemy reactions play
out without enemies dying (the exact gap that made the CB-3 knockback
measurements need `_dev_no_attack` + beefy enemies).

`PlayingState.__init__`: `self._dev_no_damage = False`. A fresh dev run (Reset /
death) clears it via `__init__` like the other flags.

**Tests:** `tests/core/test_dev_mode.py::DevMenuTests`
`test_no_damage_keeps_the_hero_attacking_but_deals_zero` — toggle on,
`_dev_no_attack` stays False, a `tank` at 30 px: over 180 frames the hero plays
an attack beat (`player._attack_t > 0`) yet `stats["damage_dealt"] == 0` and the
tank's `hp` is untouched; toggling it off, damage accrues again. Suite 647 → 648.

## Draw / update wiring (reference)

- `DevMenuState` sits on the stack above `PlayingState`; `draw_below=True` keeps
  the frozen run visible, `update_below=False` freezes it. It reaches the run as
  `self._playing = self.game.state_machine` second-from-top (captured in
  `enter`).
- Unlimited-HP ratchet goes in `PlayingState.update()` **after**
  `_phase_progression` and **before** `if not self.player.alive:` so a lethal
  frame is undone before the run-end check sees it.
- Stop-attacking gates `for weapon in self.player.weapons: weapon.update(...)`
  in `_phase_combat`.
- A single `PlayingState._restart_dev_run()` helper does
  `change(PlayingState, character_id=self.character_id, seed=self.run_seed,
  dev=True)`. Introduced in **D1** (called on a dev-run death); reused by the
  **D2** "Reset run" menu row.

## Touch list (anticipated)

- **New:** `game/states/dev_menu_state.py`, `tests/test_dev_mode.py`.
- **Changed:** `game/states/menu_state.py` (wire `"dev_start"`, relabel),
  `game/states/character_select_state.py` (forward `dev`),
  `game/states/playing_state.py` (`dev` kwarg, HP ratchet, no-attack gate,
  `K_BACKQUOTE`, dev-run `_end_run`), `game/game.py` (`_on_run_ended` early-out
  on `dev`), `game/events.py` (doc the `dev` field if enumerated),
  `progression/items.py` (`base_id=` arg — D5, not `rarity=`), `README.md`,
  `journal.md`, `transcript.md`.
- **No** new dependencies. **Nothing** committed.

### "Aim line" toggle — done 2026-09-04 (with CB-5 manual aim)

A dev-only overlay for the CB-5 manual-aim work
(`combat_balance_journal.md`, CB-5): while a manual aim is active, a line
from the hero's centre along the aim out to the main weapon's reach, plus
the two edges of the cone that decides the fire-time target pick, so the
pick can be read on screen. Nothing draws when no aim is active. Normal
gameplay never shows it — the user was explicit that aiming and the
auto-attack state carry no HUD element.

Root toggle **"Aim line"**, after **Spawn points**: `_ROOT_ROWS` gains
`"aim_line"`, `_LABELS["aim_line"] = "Aim line"`, `_activate` / `_row_label`
flip `PlayingState._dev_show_aim` and show `[ON]`/`[  ]` like the collider
and spawn-point rows. No F-key — the menu row is enough.

Hook: `WorldRenderer.aim_overlay(surface)` in `game/states/playing/rendering.py`,
same shape as `collider_overlay` (early-out unless
`ps.dev_mode and ps._dev_show_aim`, then unless `ps._aim.active`), called
from `PlayingState.draw` in the dev-only overlay group after
`spawn_point_overlay`. Reads the frame's `AimInput` (`ps._aim`, stored by
`_phase_input`) and the main weapon:

- **length** = `main._reach(area_multiplier)`; a main weapon with no finite
  reach falls back to `_AIM_LINE_PX = 160` world px.
- **cone** = the swing cone (`cone_half_angle`) for a melee main weapon,
  which takes no assist; otherwise `main._assist_half_angle()` (the
  weapon's `aim_assist_deg`, else `config.MANUAL_AIM_ASSIST_DEG`). With no
  weapon at all, the config angle.
- **colour** = `config.COLOR_DEBUG_AIM_MOUSE` (yellow) for a click / tap,
  `COLOR_DEBUG_AIM_KEYS` (cyan) for a held key, so the priority ladder
  (click beats key) is visible while testing; the edges are the half-tint.

`PlayingState._init_run`: `self._dev_show_aim = False`; a fresh dev run
clears it via `__init__` like the other flags.

**Tests** (`tests/core/test_dev_mode.py::DevMenuTests`, +2):
`test_aim_line_row_toggles_the_dev_overlay` — the row flips the flag, shows
`[ON]`, and `PlayingState.draw` survives a key aim, a mouse aim and no aim;
`test_aim_overlay_draws_only_in_dev_with_the_flag_and_an_aim` — counts
`pygame.draw.line` calls: 0 with the flag off, exactly 3 (aim + two edges)
with a held key or a tap, 0 with no aim, and 0 in a regular run even with
the flag forced on.

### "Forges..." page + "Remove weapon..." page — done 2026-09-10

Two new root rows for the dev menu, requested after P3 (Forging) landed in
`weapon_system_journal.md`. Both follow the D3-D5 pattern: a root row opens
a sub-page, the page is built from live data in `enter()`, ENTER acts and
**stays on the page**, ESC / right click returns to the root, the page
scrolls past `MAX_VISIBLE` like every other one.

**Root order.** `_ROOT_ROWS` becomes `... "spawn", "blessings", "items",
"forges", "remove_weapon", "reset", "exit", "close"` -- the two new rows sit
with the other "..." links, before the run-level actions.

#### Interpretations (confirmed by the user 2026-09-10, built as written)

| # | Assumption |
|---|-----------|
| **J** | **"Current forge upgrades" = the Forgings that currently exist in `data/forges.json`** (12 today, two per forgeable weapon), listed the way the Blessings page lists the catalog -- so the page grows and shrinks with the data. It is not a read-only "what is forged" display; that information shows on the rows instead (see L). |
| **K** | **ENTER on a Forging applies it to the hero's owned weapon of that id** via the real `combat.weapons.forge.apply_forge`, so the dev result is byte-for-byte what the village Forge or a Forge-rarity level-up card produces (overrides merged, `effects` taken, `weapon.forge` set, orbiters dropped, `visual_id` switches to the Forge's look). Two dev conveniences, mirroring the Blessings page: the **`forge_requires_levels` requirement is skipped** (a fresh weapon can be forged at once), and **a Forging for a weapon the hero lacks hands the weapon over first** (a base `Weapon` is appended, then forged). |
| **L** | **Exclusivity is kept.** A weapon already forged cannot be forged again (`apply_forge` raises; the design says one Forge per weapon, the two options mutually exclusive). The page picks the **first unforged instance** of that weapon id (the Items page stacks duplicates); when every instance is forged the row does nothing and the status line says `<weapon> already forged into <name>`. To try the other Forging: remove the weapon (the new page), re-grant it, forge. Rows read `<weapon name>   <Forge name>` and gain a `*` / `(forged)` marker while an owned weapon of that id carries that Forge, so the current state of the hero is visible on the page. Summons cannot be forged (design §3.7) and never appear in the data, so nothing to gate. |
| **M** | **"Remove current weapons" = a page listing the hero's owned weapon instances**, one row per `Weapon` in `player.weapons` in slot order (`<name>  Lv<level>` plus the Forge name when forged), with a first row **"All weapons"**. ENTER on a row removes that one instance; ENTER on "All weapons" empties the list. The page is rebuilt on every draw / action so it reflects what the Items and Forges pages add. An empty list shows a single `(no weapons)` row that does nothing. |
| **N** | **Removal unwinds what the weapon owned.** Its persistent projectiles are dropped (`_orbiters` deactivated and cleared) and its summons dismissed (`_summons` entries set inactive, so the summon system reaps them next frame); the weapon-kind blessing stacks that were taken *on that weapon id* are cleared from `player.blessings` (they lived in `weapon.bonus` / `weapon.effects`, which leave with the weapon; the stack counters would otherwise make a re-granted weapon look levelled and gate the offering wrongly). Stat blessings, items and equipment modifiers are untouched. Nothing is written to `save.json` (dev runs never save; `main_weapon` in the save is the character-select choice, not the run). |
| **O** | **A hero with no weapons is a legal sandbox state.** Auto-attack, manual aim and the aim-line overlay already tolerate an empty weapon list ("with no weapon at all, the config angle"); the level-up offering simply has no weapon cards to roll. No guard rail prevents removing the last weapon -- that is the point of the option (e.g. test an enemy with a defenceless hero, or rebuild a loadout from scratch with the Items page). |

#### Touch list (anticipated)

- **Changed:** `game/states/dev_menu_state.py` -- two rows, two pages
  (`"forges"`, `"weapons"`), `_forge()` and `_remove_weapon()` actions,
  headings `FORGE WEAPON` / `REMOVE WEAPON`, nav hints, `_row_label` cases.
  No change to `PlayingState`, `combat/weapons/forge.py` or the data.
- **Tests:** `tests/core/test_dev_mode.py` gains `DevForgeMenuTests` (page
  lists every `content.forges` id; ENTER forges the owned weapon and the
  weapon's `forge` / name / `visual_id` change; a missing weapon is granted
  first; the level requirement is not enforced; a second Forging on the same
  weapon is refused with a status and the weapon is unchanged; ESC -> root)
  and `DevRemoveWeaponMenuTests` (page lists the owned instances; ENTER drops
  exactly that one; "All weapons" empties the list; a removed weapon's
  weapon-blessing stacks are gone and its summons / orbiters inactive; the
  run keeps updating and drawing with zero weapons; ESC -> root). The
  existing `test_draw_runs_headless_on_every_page` and the mouse tests cover
  the new pages through `_rows()`.
- **Docs:** this entry ticked, `README.md` dev-mode note gains the two rows.

#### Done — what was built

`game/states/dev_menu_state.py`: `_ROOT_ROWS` gains `"forges"` and
`"remove_weapon"` after `"items"`; pages `"forges"` (heading `FORGE
WEAPON`, rows = `sorted(content.forges)` by weapon then name, label
`<weapon>: <Forge>` + `(forged)` while an owned weapon carries it) and
`"weapons"` (heading `REMOVE WEAPON`, rows rebuilt on every read by
`_weapon_rows()`: `("all",)` then `("weapon", i)` per owned instance, or
`("none",)` when the hand is empty; label `<base name>   Lv<n>   [<Forge
name>]`). `_forge()` hands over a missing weapon, picks the first unforged
instance of the id and calls the real `apply_forge` (no level gate);
every instance already forged -> status `"<weapon> already forged into
<name>"`, nothing changes. `_remove_weapon()` -> `_retire_weapon()` per
target: `player.weapons.remove`, orbiters and summons set inactive and
cleared, and -- once no instance of that id remains -- every `weapon` /
`grant` blessing stack for that weapon id dropped from `player.blessings`
followed by `rebuild`. The selection is clamped to the shrunken page.
`PlayingState`, `combat/weapons/forge.py` and the data are untouched.

**Tests** (`tests/core/test_dev_mode.py`, +11, module 52 -> 63; full suite 1631 green, 2 skipped):
`DevForgeMenuTests` (5) -- the page lists every `content.forges` id; ENTER
forges the level-1 starting weapon (`forge`, `name`, `visual_id` and every
override change, row shows `(forged)`); a Forging for an unowned weapon
grants it and forges it; the sibling Forging on the same weapon is refused
with the definition and weapon count unchanged; ESC -> root + headless
draw on every row. `DevRemoveWeaponMenuTests` (6) -- the page lists "All
weapons" + one row per instance; ENTER on the second of three removes
exactly that one and the page shrinks; "All weapons" empties the hand, the
`(no weapons)` row is inert and the run updates + draws weaponless; a
weapon blessing taken on the starting weapon is cleared on removal while a
stat blessing stays, and a re-granted weapon is back at Lv1; a spirit wolf
and an ember ring (tank in reach so the ring forms) leave their summon /
orbiters inactive after "All weapons"; ESC -> root + headless draw.
Two test-side gotchas worth remembering: the backquote from a sub-page
goes to the root (a second press closes), and the ember ring only orbits
with an enemy inside its reach or the mouse held.

Screenshots captured headless (Forges page with two `(forged)` rows and
the status line; Remove weapon page with three instances, two of them
showing their Forge name) and sent.
