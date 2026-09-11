"""The level-up card record and the run's slot limits.

Since P2 of the six-weapon system every card is a *blessing* (design §21):
the catalog, gating, weights and the roll live in `progression.blessings`.
This module keeps the small things the rest of the game imports:

  * `Upgrade` -- what a card is: identity, text, weight, an `apply` callback,
    plus the rarity / level / kind the level-up panel shows.
  * `apply_choice` -- apply a picked card and count it in
    `player.upgrade_stacks` (the run summary reads that).
  * `roll_choices` / `valid_choices` -- thin wrappers over the offering, kept
    under their old names for the callers and tests that use them.
  * `MAX_WEAPONS` / `MAX_SUMMONS` and the slot predicates (design §20, §3.7).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

MAX_WEAPONS = 3      # melee + ranged (design §20)
MAX_SUMMONS = 1      # design §3.7


@dataclass
class Upgrade:
    id: str
    title: str
    description: str
    weight: float
    apply: Callable[["object"], None]
    max_stacks: int = 99
    tags: tuple[str, ...] = ()
    kind: str = "stat"          # stat | weapon | grant (| forge, P3)
    rarity: str = "common"      # common | uncommon | rare | forge
    level: int = 1              # the level this card would reach
    weapon: str | None = None   # the weapon it belongs to / grants


def weapon_slots_full(player) -> bool:
    return sum(1 for w in player.weapons if not w.is_summon) >= MAX_WEAPONS


def summon_slot_full(player) -> bool:
    return sum(1 for w in player.weapons if w.is_summon) >= MAX_SUMMONS


def valid_choices(player, content, rng: random.Random | None = None) -> list[Upgrade]:
    from progression.blessings.offer import valid_offers
    return valid_offers(player, content, rng if rng is not None else random.Random(0))


def roll_choices(player, content, rng: random.Random, n: int | None = None) -> list[Upgrade]:
    from progression.blessings.offer import roll_offering
    return roll_offering(player, content, rng, n)


def apply_choice(player, upgrade: Upgrade) -> None:
    upgrade.apply(player)
    stacks = player.upgrade_stacks
    stacks[upgrade.id] = stacks.get(upgrade.id, 0) + 1
