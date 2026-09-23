# Elemental extras — plan

**Serves:** CMB-009 (proposed) · **Journal:** `journals/elemental_system_journal.md`
(the CMB-009 block) · **Design:** `plans/ELEMENTAL_SYSTEM_DESIGN.md` §8.2, §9.8, §10.3

What the elemental system still lacks after CMB-005/006/007, collected on
2026-09-22 (DOC-003). Nothing here is built. Every item is a dev tool
except the building glow, which is the one the player sees.

---

## 1. An elemental buff building shows its element — a faint glow behind it

**Today.** A buff building that rolled an element carries it on
`Interactable.element` (M7), but nothing draws it: the obstacle draws the
building, and `WorldRenderer.interactables` skips buff buildings
(`visual/rendering.py`, `if ps.buffs.is_buff(it.kind): continue`). The player
learns the element only by using the building.

**Proposal (owner, 2026-09-22: a faint alpha glow behind the building).**

- A soft disc in the element's tint (`VisualSet.tint(element)`,
  `visual/elements/profiles.py`), drawn **behind** the building. This matches
  the standing draw order, where element effects sit under sprites and only
  reactions draw on top.
- Drawn from the flat terrace pass that already runs before the actors
  (`scene.py` → `ren.interactables(surface, level)`), so the baked building
  art covers its centre and only the rim shows. No new layer.
- Uses `GlowCache` (`visual/glow.py`): one pre-rendered disc per
  `(diameter, alpha)`, one blit per building per frame, no allocation.
- **Faint**: a low fixed alpha, with an optional slow breath using
  `pulse_alpha` between two close alphas so it reads as alive without
  pulling the eye. It goes out when the building is used (`it.used`), the
  same way a spent building stops offering.
- The Monastery rolls no element (the player picks one), so it gets no glow.
- **Data, not code:** the alpha(s), the diameter as a multiple of the
  building's radius and the breath period go in `data/world/buildings.json`
  beside the existing `elements` block, read without fallbacks.
- **Tests:** a building with an element blits one glow and a used or
  non-elemental one blits none; the tint follows the element; the knobs are
  validated in `game/content.py` with the other building fields.
- **Screenshot:** one elemental building of each element on seed 35, per the
  milestone-screenshot rule.

## 2. Profiling counters the design asked for (§9.8)

The F1 metrics (`devtools/dev_flags.py`) show auras, reactions per frame,
held reactions, particles and element fx. Missing:

- **Thunder jump nodes per frame:** a counter on the element stats that
  `thunder`/`spread` bump per node visited, reset each frame like
  `reactions_this_frame`.
- **Active Wind areas:** the length of the live area list next to its cap.

## 3. Dev extras (§10.3)

The force-aura tool is built (dev menu). Still proposed:

- **Hot-reload of the element data:** a dev key re-reads
  `data/weapons/elements.json` (and the reaction tables) into the live run,
  so a tuning pass needs no restart. It re-runs the same validation as a
  load and leaves the old values in place if they fail.
- **Reaction log:** a scrolling overlay of the last N reactions — pair,
  trigger, damage, whether it cascaded, frame — fed from the point where a
  reaction resolves.
- **Spawn a building with a chosen element:** a dev-menu row that seats a
  buff building next to the hero with the element picked from the four,
  going through the same placement and interactable code the world uses.

## Order

The glow first (the only player-facing item), then the counters (small, and
CMB-008's cascade measurement wants them), then the three dev tools.
Each is its own task with its own commit once CMB-009 is taken up.
