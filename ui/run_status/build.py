"""Build pane: one card per weapon, the selected weapon's Forging detail,
and the synergies.

A card shows the weapon's live numbers as `base -> now` where a blessing has
changed them (the fire path's own arithmetic: `definition + bonus`, cooldown
times `cooldown_mult`), and the blessing levels it has taken against the
Forge gate. The hero's own multipliers (damage, attack speed, area) are *not*
folded in: they sit on the Overview's stat list and apply to every weapon
alike, so a card shows what is the weapon's own.

Under the cards, two blocks side by side:

* **Forging** -- for the *selected* card (Up / Down, or a click): the
  Forging's name, identity and every number it changed
  (`combat.weapons.forge.forge_changes`), then its description in whatever
  room is left. An unforged weapon shows the gate instead. Keeping this out
  of the card is what lets the pane fit the 1280x720 web profile: a forged
  weapon's full readout is taller than a card can be there.
* **Synergies** -- the owned blessings in the catalog's `synergy` category:
  each names the weapon it belongs to and, through `requires_weapons`, the
  partner; that pair heads the row, the card text at the owned level is its
  body. Natural synergies have no rule in the code and are not listed.
"""
from __future__ import annotations

import pygame

from combat.weapons.forge import blessing_levels, forge_changes, get_forges
from game import config
from progression.blessings.catalog import roman
from progression.blessings.offer import get_rules
from ui.run_status import common as c
from ui.text import wrap

# (definition key, label, bonus key or None, kind) -- shown when the
# definition has the key. `kind` "s" prints seconds, "n" a number, "deg" degrees.
_NUMBERS = (
    ("damage", "Damage", "damage", "n"),
    ("cooldown", "Cooldown", None, "s"),
    ("projectile_count", "Projectiles", "projectile_count", "n"),
    ("area", "Area", "area", "n"),
    ("reach", "Reach", None, "n"),
    ("pierce", "Pierce", "pierce", "n"),
    ("blast_radius", "Blast radius", "blast_radius", "n"),
    ("cone_half_angle", "Cone", "cone_half_angle", "deg"),
    ("chain_count", "Chains", "chain_count", "n"),
    ("weight", "Weight", "weight", "n"),
)
MAX_SYNERGIES = 4
CARD_STEP = 24            # a card's number rows; tighter than the shared ROW_STEP
GATE_H = 54               # the two gate rows anchored at a card's bottom


def _fmt(v, kind: str) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    if kind == "s":
        return f"{float(v):g}s"
    if kind == "deg":
        return f"{float(v):g}°"
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return str(v)


def weapon_numbers(weapon) -> list[tuple[str, str, str | None]]:
    """`[(label, base, now)]` for the numbers the definition carries; `now`
    is None when no blessing changed it."""
    d, b = weapon.definition, weapon.bonus
    out = []
    for key, label, bkey, kind in _NUMBERS:
        if key not in d:
            continue
        base = float(d[key])
        now = base
        if key == "cooldown":
            now = base * float(b.get("cooldown_mult", 1.0))
        elif bkey is not None:
            now = base + float(b.get(bkey, 0.0))
        out.append((label, _fmt(base, kind), _fmt(now, kind) if abs(now - base) > 1e-9 else None))
    crit = float(b.get("crit_chance", 0.0))
    if crit > 0.0:
        out.append(("Crit chance", f"+{crit * 100:.0f}%", None))
    return out


def gate_text(weapon, need: int, forges) -> str:
    """The Forge line under a card's blessing count."""
    if weapon.is_summon:
        return "cannot be forged"
    if weapon.forge:
        return f"forged  -  {forges.get(weapon.forge).identity}"
    levels = blessing_levels(weapon)
    if levels >= need:
        return f"ready for the Forge ({need})"
    return f"Forge at {need}  -  has {levels}"


def synergy_rows(player, catalog, weapon_names) -> list[tuple[str, str]]:
    """`[(pair, text)]` for every owned synergy blessing."""
    rows = []
    for bid, lvl in player.blessings.items():
        bdef = catalog.by_id.get(bid)
        if bdef is None or bdef.category != "synergy":
            continue
        names = [weapon_names.get(bdef.weapon, bdef.weapon or "Hero")]
        names += [weapon_names.get(w, w) for w in bdef.requires_weapons]
        pair = " + ".join(n for n in names if n)
        rows.append((f"{pair}  -  {bdef.name} {roman(lvl)}", bdef.describe(lvl)))
    return rows


class BuildPane:
    def __init__(self, fonts: c.Fonts) -> None:
        self.f = fonts
        self.sel = 0
        self._count = 0

    def move(self, delta: int) -> None:
        if self._count:
            self.sel = max(0, min(self._count - 1, self.sel + delta))

    def select(self, index: int) -> None:
        if 0 <= index < self._count:
            self.sel = index

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ps, hits) -> None:
        f = self.f
        weapons = list(ps.player.weapons)
        self._count = len(weapons)
        self.sel = max(0, min(self.sel, max(0, len(weapons) - 1)))
        need = get_rules(ps.content).forge_requires_levels
        forges = get_forges(ps.content)
        names = {wid: d.get("name", wid) for wid, d in ps.content.weapons.items()}

        # Cards across the top; the detail strip takes the rest.
        card_h = min(380, int(area.height * 0.56))
        n = max(1, len(weapons))
        gap = 20
        card_w = (area.width - gap * (n - 1)) // n
        if not weapons:
            c.line(surface, f.row, area, area.top + c.ROW_STEP, "no weapons",
                   colour=config.COLOR_TEXT_DIM)
        for i, w in enumerate(weapons):
            card = pygame.Rect(area.left + i * (card_w + gap), area.top, card_w, card_h)
            hits.add(card, ("row", i))
            self._draw_card(surface, card, w, need, forges, selected=(i == self.sel))

        strip = pygame.Rect(area.left, area.top + card_h + 16, area.width, 0)
        strip.height = area.bottom - strip.top
        split = int(strip.width * 0.55)
        left = pygame.Rect(strip.left, strip.top, split - 20, strip.height)
        right = pygame.Rect(strip.left + split + 20, strip.top, strip.width - split - 20, strip.height)
        if weapons:
            self._draw_forging(surface, left, weapons[self.sel], need, forges, ps.content)
        self._draw_synergies(surface, right, synergy_rows(ps.player, ps.catalog, names))

    # --- a weapon card --------------------------------------------------
    def _draw_card(self, surface, card, w, need, forges, *, selected: bool) -> None:
        f = self.f
        pygame.draw.rect(surface, (40, 36, 60) if selected else (18, 16, 26), card, border_radius=8)
        pygame.draw.rect(surface, config.COLOR_ACCENT if selected else config.COLOR_WORLD_BORDER,
                         card, width=1, border_radius=8)
        area = pygame.Rect(card.left + 16, card.top, card.width - 32, card.height)
        y = area.top + 22
        y = c.line(surface, f.title, area, y, f"{w.name}  Lv {w.level}", step=30)
        # Class, then the category and the special effect where they say
        # something the class does not ("summon · summon" told the player nothing).
        parts = [w.weapon_class]
        if w.category != w.weapon_class:
            parts.append(w.category)
        if w.special and w.special != w.weapon_class:
            parts.append(str(w.special).replace("_", " "))
        y = c.line(surface, f.small, area, y, "  ·  ".join(parts), colour=config.COLOR_TEXT_DIM, step=24)

        # The gate block is anchored at the bottom; the numbers fill down to it.
        gate_top = area.bottom - GATE_H
        rows = weapon_numbers(w)
        room = max(0, (gate_top - y) // CARD_STEP)
        shown = rows if len(rows) <= room else rows[:max(0, room - 1)]
        for label, base, now in shown:
            value = base if now is None else f"{base}  ->  {now}"
            y = c.kv(surface, f.row, area, y, label, value,
                     colour=config.COLOR_ACCENT if now is not None else None)
            y -= c.ROW_STEP - CARD_STEP
        if len(shown) < len(rows):
            c.line(surface, f.small, area, y, f"+{len(rows) - len(shown)} more",
                   colour=config.COLOR_TEXT_DIM)

        y = c.rule(surface, area, gate_top + 6)
        y = c.kv(surface, f.row, area, y, "Blessing levels", blessing_levels(w))
        c.line(surface, f.small, area, y - 6, gate_text(w, need, forges), step=24,
               colour=config.COLOR_ACCENT if w.forge else config.COLOR_TEXT_DIM)

    # --- the selected weapon's Forging ----------------------------------
    def _draw_forging(self, surface, area, w, need, forges, content) -> None:
        f = self.f
        if not w.forge:
            y = c.subheader(surface, f.sub, area, area.top, f"{w.name}  -  not forged")
            c.line(surface, f.row, area, y, gate_text(w, need, forges).capitalize(),
                   colour=config.COLOR_TEXT_DIM)
            return
        fdef = forges.get(w.forge)
        y = c.subheader(surface, f.sub, area, area.top, f"Forging: {fdef.name}  -  {fdef.identity}")
        # The numbers first -- they are what the player came for -- then the
        # description in whatever room is left.
        for key, before, after in forge_changes(content, w):
            if y > area.bottom - 8:
                return
            value = (f"+ {_fmt(after, 'n')}" if before is None
                     else f"{_fmt(before, 'n')}  ->  {_fmt(after, 'n')}")
            y = c.kv(surface, f.small, area, y, key.replace("_", " "), value,
                     colour=config.COLOR_ACCENT)
            y -= c.ROW_STEP - 22
        y += 6
        for text_line in wrap(f.small, fdef.description, area.width):
            if y > area.bottom - 8:
                return
            y = c.line(surface, f.small, area, y, text_line, colour=config.COLOR_TEXT_DIM, step=20)

    # --- synergies --------------------------------------------------------
    def _draw_synergies(self, surface, area, syn) -> None:
        f = self.f
        y = c.subheader(surface, f.sub, area, area.top, f"Synergies  ({len(syn)})")
        if not syn:
            c.line(surface, f.row, area, y, "none yet  -  a synergy blessing links two weapons",
                   colour=config.COLOR_TEXT_DIM)
            return
        for head, text in syn[:MAX_SYNERGIES]:
            if y > area.bottom - 30:
                break
            y = c.line(surface, f.row, area, y, head, colour=config.COLOR_ACCENT)
            for text_line in wrap(f.small, text, area.width - 18):
                y = c.line(surface, f.small, area, y - 6, text_line, colour=config.COLOR_TEXT_DIM,
                           indent=18, step=22)
                y += 6
            y -= 6
        c.more(surface, f.small, area, y, len(syn) - MAX_SYNERGIES, "synergies")
