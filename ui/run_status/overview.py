"""Overview pane: the run line, the hero, the equipped items with what each
one gives, and the hero's stats as they resolve right now.

Two columns. The left is the run and the items; the right is every stat in
`common.STAT_ROWS`, printed through `fmt_stat` so a chance reads as a
percentage and a multiplier as `x1.25`. The values come from
`player.stats`, which is the resolved `StatSet` -- so whatever the equipped
items, blessings, meta upgrades and the hero's base contribute is already
inside them.

Items claim their bonuses (owner, 2026-09-12): under each item row come its
base stat, every affix (a stat, or extra damage against a tag) and the unique
effect's text where it has one.
"""
from __future__ import annotations

import pygame

from game import config
from ui.run_status import common as c
from ui.run_summary import fmt_time

MAX_ITEMS = 4                 # equipped slots; a run never has more


def item_lines(item, content=None) -> list[str]:
    """What the item gives, one line each: the base stat, the affixes, the
    unique effect. `content` resolves a unique effect's text; without it the
    effect's id is shown."""
    out = [c.fmt_mod(item.base_stat, item.base_op, item.base_value)]
    for a in item.affixes:
        if a.kind == "tag_damage":
            out.append(f"{a.value * 100:+.0f}% damage vs {a.tag}")
        else:
            out.append(c.fmt_mod(a.stat, a.op, a.value))
    if item.unique_effect:
        out.append(_unique_text(item.unique_effect, content))
    return out


def _unique_text(effect_id: str, content) -> str:
    table = getattr(content, "items", {}).get("unique_effects", {}) if content else {}
    for entry in table.values():
        if entry.get("id") == effect_id:
            return f"{entry.get('name', effect_id)}: {entry.get('desc', '')}".rstrip(": ")
    return effect_id.replace("_", " ").title()


class OverviewPane:
    def __init__(self, fonts: c.Fonts) -> None:
        self.f = fonts

    def move(self, delta: int) -> None:      # nothing to select here
        pass

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ps, hits) -> None:
        gap = 40
        col_w = (area.width - gap) // 2
        left = pygame.Rect(area.left, area.top, col_w, area.height)
        right = pygame.Rect(area.left + col_w + gap, area.top, col_w, area.height)
        self._draw_run(surface, left, ps)
        self._draw_stats(surface, right, ps)

    # --- left: the run and the items --------------------------------------
    def _draw_run(self, surface, area, ps) -> None:
        f, s, p = self.f, ps.stats, ps.player
        y = area.top + c.ROW_STEP // 2
        hero = ps.content.character(ps.character_id)["name"]
        trait = getattr(p, "trait", "")
        y = c.kv(surface, f.row, area, y, "Hero", f"{hero}" + (f"  ({trait})" if trait else ""))
        y = c.kv(surface, f.row, area, y, "Difficulty",
                 config.DIFFICULTY_LABELS.get(ps.difficulty, str(ps.difficulty)))
        y = c.kv(surface, f.row, area, y, "Survived", fmt_time(s.get("time", 0.0)))
        y = c.kv(surface, f.row, area, y, "HP", f"{int(p.hp)} / {int(p.max_hp)}")
        # Level, with the XP bar in the gap under its row.
        y = c.kv(surface, f.row, area, y, "Level", ps.levels.level)
        frac = max(0.0, min(1.0, float(ps.levels.progress_fraction)))
        bar = pygame.Rect(area.left, y - c.ROW_STEP // 2 + 1, area.width, 6)
        pygame.draw.rect(surface, (14, 20, 40), bar)
        pygame.draw.rect(surface, (90, 150, 240), (bar.left, bar.top, int(bar.width * frac), bar.height))
        y += 10
        y = c.kv(surface, f.row, area, y, "Kills", s.get("kills", 0))
        y = c.kv(surface, f.row, area, y, "Gold", s.get("gold", 0), colour=config.COLOR_ACCENT)
        y = c.kv(surface, f.row, area, y, "Salvage", s.get("currency", 0), colour=config.COLOR_ACCENT)

        items = list(getattr(p, "equipment", ()))
        y = c.subheader(surface, f.sub, area, y, f"Equipped items  ({len(items)})")
        if not items:
            c.line(surface, f.row, area, y, "none", colour=config.COLOR_TEXT_DIM)
            return
        for item in items[:MAX_ITEMS]:
            if y > area.bottom - c.ROW_STEP:
                break
            name = f"[{item.rarity[:1].upper()}] {item.name}"
            y = c.kv(surface, f.row, area, y, name, f"{item.slot}  Lv {item.level}",
                     label_colour=c.RARITY_ON_DARK.get(item.rarity, config.COLOR_TEXT))
            for text in item_lines(item, ps.content):
                if y > area.bottom - 10:
                    break
                y = c.line(surface, f.small, area, y, text, colour=config.COLOR_TEXT_DIM,
                           indent=18, step=22)
            y += 4

    # --- right: the stats -------------------------------------------------
    def _draw_stats(self, surface, area, ps) -> None:
        f = self.f
        stats = ps.player.stats
        y = c.subheader(surface, f.sub, area, area.top + 2, "Hero stats")
        for stat, label, _kind in c.STAT_ROWS:
            if y > area.bottom:
                break
            y = c.kv(surface, f.row, area, y, label, c.fmt_stat(stat, float(stats.get(stat, 0.0))))
