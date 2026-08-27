# Developer mode — dev log

A separate log for the **developer mode** feature, the same way `assets_journal.md`
tracks the art passes. The general `journal.md` gets a one-paragraph pointer here.

Milestones are **D1–D6** (unrelated to the spec's Milestones 1–10 or the
start-screen M1–M5). Each ends green — `python -m unittest discover -s tests`
plus a windowed / headless-screenshot check — before the next.

**Status:** D1–D4 done (2026-08-27). D5–D6 pending. All assumptions confirmed.

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
| **E** | **"Select items"** = pick a **slot** (weapon / armor / accessory) × **rarity** (common … legendary); the dev menu *generates* one (items are procedural — there is no fixed catalog) and equips it. `generate_item()` gains an optional `rarity=` argument so a rarity can be forced. |
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
| **D5** | **Items submenu.** `generate_item()` gains `rarity: str \| None = None` (skips `roll_rarity`). Page `"items"` — a slot × rarity chooser. `ENTER` generates the item and **dev-equips** it: append to `player.equipment`, add its `stat_effects()` as `Modifier(…, "dev:item:<slot>#<n>")`, `rebuild_blessings(...)`, top HP to max; show `item.short()`. `ESC` → root. | `unittest` green (`generate_item(..., rarity="epic")` → epic with 3 affixes; dev-equip grows `player.equipment` and moves a player stat; a `tag_damage` affix shows up in `player.blessing_fx.tag_damage`) + windowed |
| **D6** | **Docs.** Finish this file (tick D1–D6 + a "How to use" section). `README.md` — a "Developer mode" note (the `` ` `` key, what each option does, "does not save"). `journal.md` + `transcript.md` — short "Developer mode" entries. | full `unittest` + windowed `python main.py` dev run |

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
  `progression/items.py` (`rarity=` arg), `README.md`, `journal.md`,
  `transcript.md`.
- **No** new dependencies. **Nothing** committed.
