"""Putting an element on a weapon: the screen both sources share (design §7).

Two things hand out infusions and they differ only in who picks the
element:

* the **Monastery** offers all four and lets the player choose, then a
  weapon (owner's decision, 2026-09-21: it rolls nothing and is spent after
  one use);
* an **elemental buff building** has already rolled its element, so only
  the weapon is left to choose.

Both reuse the Forge's screen rather than growing one of their own. That
screen is a rail down the left and cards in the middle, which is exactly
"pick one of these, then one of those": the Monastery puts the elements on
the rail and the weapons on the cards, and a building with no choice of
element skips the rail entirely.

Infusions are run-scoped (§7): a weapon is rebuilt per run, so nothing here
has to be undone at the end of one.
"""
from __future__ import annotations

from dataclasses import dataclass

from combat.elements.ids import ELEMENTS, ElementId
from progression.upgrades import Upgrade

RAIL_HEADING = "INFUSE WITH WHICH ELEMENT"


@dataclass(frozen=True)
class ElementRow:
    """A rail row. The rail asks for `.name` and nothing else."""
    element: ElementId

    @property
    def name(self) -> str:
        return self.element.key.title()


def infusable(player) -> list:
    """Every weapon that can take an element -- which is all of them,
    summons included (owner's correction, 2026-09-21)."""
    return list(player.weapons)


def element_rows(player) -> list[tuple]:
    """`[(row, eligible, note)]` for the rail: one per element, always all
    four whatever the run has unlocked (§7.2, confirmed). The note says what
    the hero already carries it on, so a player can see at a glance which
    pairs are available."""
    rows = []
    for element in ELEMENTS:
        carriers = [w.name for w in player.weapons if w.element == element]
        note = f"on {', '.join(carriers)}" if carriers else "not carried"
        rows.append((ElementRow(element), True, note))
    return rows


def weapon_cards(player, element: ElementId) -> list[Upgrade]:
    """One card per weapon: taking it puts `element` on that weapon,
    replacing whatever it held."""
    cards = []
    for weapon in infusable(player):
        cards.append(Upgrade(
            id=f"infuse:{weapon.weapon_id}:{element.key}",
            title=weapon.name,
            description=_describe(weapon, element),
            weight=1.0,
            apply=_infuser(weapon, element),
            kind="weapon", rarity="rare", weapon=weapon.weapon_id))
    return cards


def _describe(weapon, element: ElementId) -> str:
    held = weapon.element
    if held == element:
        pace = _pace(weapon)
        return f"Already carries {element.key}. Refreshes it ({pace})."
    if held != ElementId.NONE:
        return f"Replaces {held.key} with {element.key} ({_pace(weapon)})."
    return f"Carries {element.key} {_pace(weapon)}."


def _pace(weapon) -> str:
    """How often this weapon would actually inflict -- the half of an
    infusion its numbers cannot show."""
    from combat.weapons.core import TIME_MODE

    if weapon.element_mode == TIME_MODE:
        return f"every {weapon.element_window:.2g}s"
    if weapon.element_interval:
        return f"on 1 attack in {weapon.element_interval + 1}"
    return "on every attack"


def _infuser(weapon, element: ElementId):
    def apply(player) -> None:
        weapon.element = element
    return apply


def offer(ps, *, element=None, title=None, on_done=None) -> None:
    """Push the picker. With `element` the rail is skipped and only the
    weapon is chosen; without it the player picks both."""
    run = getattr(ps, "run", ps)
    player = run.player
    if not infusable(player):
        ps.notice("No weapon to infuse.")
        return

    from game.states.level_up_state import LevelUpState

    if element is None:
        rows = element_rows(player)
        offers_for = lambda row: weapon_cards(player, row.element)
    else:
        rows = None
        offers_for = None

    ps._suspend_mouse()
    ps.game.state_machine.push(
        LevelUpState(ps.game), player=player,
        choices=() if element is None else weapon_cards(player, element),
        weapon_rows=rows, offers_for=offers_for,
        rail_heading=RAIL_HEADING,
        hint=("Up/Down pick the element    -    1/2/3 or Left/Right + Enter "
              "to infuse    -    ESC to leave")
        if element is None else
        ("1/2/3 or Left/Right + Enter to infuse    -    ESC to leave"),
        title=title or "Choose an element, then a weapon",
        cancelable=True,
        on_done=on_done or (lambda u: _noticed(ps, u)))


def _noticed(ps, upgrade) -> None:
    run = getattr(ps, "run", ps)
    weapon = run.player.weapon_by_id(upgrade.weapon)
    if weapon is not None and weapon.infused:
        run.unlocked_elements.add(weapon.element)
        ps.notice(f"The {weapon.name.lower()} carries {weapon.element.key}.")
