# Pending plans — what is built but not wired

Survey taken 2026-09-11 on `main` at `86aaa3f`, by booting the game rather
than by reading the other plans. Everything listed here is **unwired work, not
broken work**: the full suite was green when the list was made (1,641 passed,
2 skipped, 7 sweep deselected, 56 subtests, 9 min 51 s), a headless boot walks
MENU → hero select → LOADING (1.9–3.3 s) → PLAYING without raising, and a run
holds 61–72 live enemies at 150–219 fps headless on a 9-room world with a
village, 12 villagers and all six interactable kinds placed.

The point of the file is that the finished plans in this folder each end with
a "Deferred" note, and those notes are invisible once a plan is marked done.
This is where they are collected, together with what a fresh look at the code
found. Each item says **where** it would be wired, so none of them needs this
survey repeated.

Nothing here is a decision. When one of these is taken up, it gets its own
entry in a plan (or its own plan) and its evidence in a journal, as everywhere
else.

---

## 1. Designed content that can never be reached

The weapon rework's five phases all shipped, but four blessings in the design
were left out of the catalog, so the offering can never roll them — they are
content the player cannot see, not content that is merely rare.

- **Flurry** (Daggers), **Echo** (Magic Rod), **Sticky Bomb** and
  **Fragmentation** (Bomb) are absent from `data/blessings.json`. Each needs
  state the fire path does not keep today: delayed fire, or per-projectile
  memory. Fragmentation also wants P3's Cluster Bomb child-bomb code as its
  base. See `weapon_system_journal.md`, P2 and P4 "Deferred".
- **Weak Point** shipped as a damage bonus against *wounded* targets. The
  design asks for a crit against enemies **damaged by another weapon**, which
  P4's per-enemy hit memory (`Enemy.recent_hits`, `combat/synergy.py`) already
  records — it is one `syn_after_*` key away.
- **The Forge offers one weapon at a time**, the first eligible in slot order
  (`game/states/playing/locations.py:102`). A weapon picker needs a panel
  wider than three cards, which is why it was deferred rather than cut.

## 2. Art, and the rules that are waiting on it

These are all no-ops rather than bugs: the code path exists and does nothing
because the asset does not.

- **No weapon art for the six.** A dagger, a rod, a bomb sprite and a sword
  swing beyond the slash rig. The hero-select preview still cycles idle / walk
  / attack and cannot show the chosen main weapon until this exists.
- **Kestrel and Nihil have no `attack2` or `guard` sheets.** The attack
  alternation and the Bulwark guard pose are written, tested and live for
  Aegis; for the other two heroes the rule silently does nothing. The rig data
  is ready for the sheets.
- **The `mark` status has no on-screen overlay.** It shows only as a status
  ring in the primitive fallback or under `config.SHOW_ENEMY_STATE_RINGS`,
  so the Rod's synergies read as pure arithmetic to the player.
- **`assets/unused/` holds 40 MB across ~520 files** that neither code nor
  data names: 159 character strips (archer, monk, lancer defence poses), 85
  effect sheets, `chests.png`, 76 UI pieces. Some of it is content waiting for
  a system (an archer NPC, a chest prop); the rest is bundle weight — see §6.

## 3. Five screens the mouse and button pass never reached

`menu`, `paused`, `character_select`, `level_up` and `dev_menu` handle the
mouse and draw the Tiny Swords button / ribbon art. These do not, and are
still keyboard-only primitive screens:

| Screen | File | State |
|---|---|---|
| Sanctuary (meta) | `game/states/meta_state.py` | no mouse, no button art |
| Victory | `game/states/victory_state.py` | no mouse, no button art |
| Game over | `game/states/game_over_state.py` | no mouse, no button art |
| Options | `game/states/options_state.py` | no mouse, no button art |
| Rankings | `game/states/rankings_state.py` | no mouse, no button art |

Options is also the screen that should carry the **auto-attack toggle** and
the aim settings; today they exist only as the in-run `Q` key.

## 4. The HUD, for the same reason

`ui/hud.py` is still the milestone-era HUD — flat rects and plain labels while
every other surface moved to the art.

- Blessing names are **derived from ids** (`bid.split("_", 1)[-1].title()`)
  instead of read from the catalog's `name`, so a card the player chose as
  "Blood in the Water" appears in the HUD as something else.
- The blessing list is **capped at 8** with no overflow indication.
- Weapon rows do not distinguish the **summon slot** from the three weapon
  slots, and do not show that a weapon has been **Forged** (the weapon's own
  name changes, but nothing marks it as a Forging).
- The top-right labels (LV / Kills / Gold / Trait) draw **without**
  `ui.text.shadowed`. Over the sand biome they are close to illegible — the
  card titles were given the drop shadow for exactly this reason.

## 5. Audio — the thinnest layer in the game

`systems/audio.py` subscribes **seven** event cues (`hit`, `enemy_death`,
`xp`, `level_up`, `player_hurt`, `boss_spawn`, `boss_death`).

- **The `shoot` cue is never played.** It is synthesised in `_build_library`
  and even carries a 75 ms rate limit in `_min_gap_ms`, but nothing subscribes
  a weapon-fired event to it. This is the single cheapest item on this page.
- **There is no music**, of any kind, in any state.
- No cue for the Hammer's impact, the Bomb's blast, a stun, a Forging, a
  level-up card being taken, or an interactable being used.

## 6. Systems that generate data nobody reads

- **Resource points (spawn master S8).** `WorldLayout.resource_points` is
  generated per room and floor, tagged, and drawn by the dev overlay, but has
  no consumer: chests, breakables and ambient gems still search for a spot
  instead of reading the list. The open question S8 records is whether the tag
  semantics match what that first consumer needs — it cannot be answered until
  one exists.

## 7. The web build

`documentation/plans/web_plan.md` §6 has the ordered list; none of it has been
done, and two items block the build from being playable by anyone else.

- **There is no `.github/` directory at all**, so the W9 GitHub Pages deploy
  does not exist.
- **The pygbag wheel is not vendored.** A static host 404s on
  `/cdn/cp312/pygame_ce-…whl` and the page reloads in a loop; only pygbag's own
  dev server serves it. Vendoring it into `build/web/cdn/cp312/` is what makes
  the bundle hostable.
- **`assets/unused/` is not in `web/pygbag.ini`'s `ignoreDirs`**, so 40 MB of
  unreferenced art ships to the browser.
- Still open behind those: the finer loading steps and progress bar, the
  manifest-driven pack, and browser spawn-master knobs in
  `config.apply_web_profile()`.

## 8. Test and infrastructure debt

From `documentation/plans/test_suite_review.md` (§4 half done, §5–§7 open):

- Coverage gaps, in the review's own priority order: `meta_state` 22.5 %,
  `victory_state` 31.4 %, `world/gen/village_tidy.py` 67.8 %,
  `playing/slam_fx.py` 70.8 %, `world/gen/graph.py` 61 %,
  `world/gen/validate.py` 75 %, `systems/mixer_backend.py` 45.5 %.
- **25 self-disabling `skipTest` sites** that skip when the generated world
  does not happen to contain the feature under test. Two actually skip today;
  a generation change could retire any of the other 23 without a failure.
- **`coverage` is not a declared dependency** — `.coveragerc` exists, but
  nothing installs the tool it documents.

## 9. Bookkeeping

- **`six_weapon_system_design.md` still sits at the repository root**, while
  every other design reference is under `documentation/`. Moving it means
  updating the plan and journal references that name it.
- **`README.md` still describes `config.MENU_SCRIM`** and the scrim behind the
  start-menu option list (around line 355). Both were deleted in the
  2026-09-11 start-menu tidy; the paragraph describes a screen that no longer
  exists.

---

## If only two things were taken from this list

The **audio pass** (§5) and the **five keyboard-only screens** (§3). A
synthesised cue that is never played is one subscription away from the game
sounding twice as alive, and the button / ribbon rig the other screens already
use makes the second item mechanical rather than creative. The game currently
reads as half-converted, and those two are why.
