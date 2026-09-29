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
from game import locale
from progression.upgrades import Upgrade

RAIL_HEADING = "infusion.rail.heading"       # a locale key, read when drawn


@dataclass(frozen=True)
class ElementRow:
    """A rail row. The rail asks for `.name` and nothing else."""
    element: ElementId

    @property
    def name(self) -> str:
        return element_name(self.element)


def element_name(element: ElementId) -> str:
    """The element's name, capitalised, in the current language (UI-014.8);
    a sentence lowers it. The id, title-cased, for an element the locale
    does not list."""
    key = f"element.{element.key}"
    return locale.t(key) if locale.has(key) else element.key.title()


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
        note = (locale.t("infusion.rail.on",
                         weapons=locale.t("list.separator").join(carriers))
                if carriers else locale.t("infusion.rail.none"))
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
    word = element_name(element).lower()
    if held == element:
        return locale.t("infusion.refresh", element=word, pace=_pace(weapon))
    if held != ElementId.NONE:
        return locale.t("infusion.replace", old=element_name(held).lower(),
                        element=word, pace=_pace(weapon))
    return locale.t("infusion.carry", element=word, pace=_pace(weapon))


def _pace(weapon) -> str:
    """How often this weapon would actually inflict -- the half of an
    infusion its numbers cannot show."""
    from combat.weapons.core import TIME_MODE

    if weapon.element_mode == TIME_MODE:
        # Two significant figures, exactly as before (`1e+02` included),
        # with the language's decimal point.
        return locale.t("infusion.pace.time", s=locale.unit(
            "seconds", locale.decimals(f"{weapon.element_window:.2g}")))
    if weapon.element_interval:
        return locale.t("infusion.pace.count", n=weapon.element_interval + 1)
    return locale.t("infusion.pace.every")


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
        ps.notice(locale.t("infusion.no_weapon"))
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
        hint=locale.t("infusion.hint_rail" if element is None else "infusion.hint"),
        title=title or locale.t("infusion.title"),
        cancelable=True,
        on_done=on_done or (lambda u: _noticed(ps, u)))


def _noticed(ps, upgrade) -> None:
    run = getattr(ps, "run", ps)
    weapon = run.player.weapon_by_id(upgrade.weapon)
    if weapon is not None and weapon.infused:
        run.unlocked_elements.add(weapon.element)
        ps.notice(locale.t("infusion.done", weapon=weapon.name.lower(),
                           element=element_name(weapon.element).lower()))
