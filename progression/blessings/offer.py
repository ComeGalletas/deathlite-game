"""The offering: which blessings a run can be shown, at what weight, and the
weighted roll (design §21 "One offering, three kinds", "Weights").

Three kinds of card:

  * a **stat blessing** -- always valid below its max level;
  * a **weapon blessing** -- only for a weapon the hero owns (and, for a
    synergy, both weapons; for a post-Forge blessing, the Forge);
  * a **weapon grant** -- while the three weapon slots (or the summon slot)
    are open: the card adds the weapon, nothing else (CR3, 2026-09-10: the
    bundled level-I blessing was removed).

Weight = kind weight x level falloff x rarity weight (x summon factor for a
summon's blessings and the summon grant). Every number is `data/offering.json`.
`roll_offering` is a pure weighted pick without replacement given the RNG, so
it is testable seed by seed.
"""
from __future__ import annotations

import random

from combat.weapons import Weapon
from combat.weapons.forge import apply_forge, forge_eligible, get_forges
from progression.blessings.apply import apply_blessing, level_of
from progression.blessings.catalog import (BlessingDef, Catalog, OfferingRules,
                                           get_catalog, get_rules, roman)
from progression.upgrades import (MAX_SUMMONS, MAX_WEAPONS, Upgrade,
                                  summon_slot_full, weapon_slots_full)


def _owned(player) -> set[str]:
    return {w.weapon_id for w in player.weapons}


def _valid_blessing(bdef: BlessingDef, owned: set[str], player) -> bool:
    if level_of(player, bdef) >= bdef.max_level:
        return False
    if bdef.weapon is not None and bdef.weapon not in owned:
        return False
    if any(w not in owned for w in bdef.requires_weapons):
        return False
    if bdef.requires_forge is not None:
        forged = {getattr(w, "forge", None) for w in player.weapons}
        if bdef.requires_forge not in forged:
            return False
    return True


def blessing_weight(bdef: BlessingDef, level: int, catalog: Catalog,
                    rules: OfferingRules) -> float:
    w = float(rules.kind_weights[bdef.kind])
    w *= rules.falloff(level)
    w *= float(rules.rarity_weights[bdef.rarity])
    if catalog.is_summon(bdef):
        w *= rules.summon_factor
    return w


def _blessing_offer(bdef: BlessingDef, level: int, weight: float, content) -> Upgrade:
    tags = (content.weapons[bdef.weapon]["name"],) if bdef.weapon else ("hero",)
    return Upgrade(
        id=bdef.id, title=bdef.title(level), description=bdef.describe(level),
        weight=weight, apply=lambda p, _b=bdef: apply_blessing(p, _b),
        max_stacks=bdef.max_level, tags=tags + (bdef.category,),
        kind=bdef.kind, rarity=bdef.rarity, level=level, weapon=bdef.weapon)


def blessing_offers(player, content, *, kinds=None) -> list[Upgrade]:
    """Every stat / weapon blessing the run can take right now."""
    catalog, rules = get_catalog(content), get_rules(content)
    owned = _owned(player)
    out = []
    for bdef in catalog.by_id.values():
        if kinds is not None and bdef.kind not in kinds:
            continue
        if not _valid_blessing(bdef, owned, player):
            continue
        level = level_of(player, bdef) + 1
        out.append(_blessing_offer(bdef, level,
                                   blessing_weight(bdef, level, catalog, rules), content))
    return out


def grant_offers(player, content, rng: random.Random) -> list[Upgrade]:
    """A card per weapon the run can still take -- the weapon alone (CR3).
    None once the slots are full. `rng` is kept so the offer roll's callers
    are unchanged; a grant no longer rolls anything."""
    catalog, rules = get_catalog(content), get_rules(content)
    owned = _owned(player)
    weapons_full = weapon_slots_full(player)
    summons_full = summon_slot_full(player)
    out = []
    for wid, d in content.weapons.items():
        if wid in owned:
            continue
        is_summon = d["class"] == "summon"
        if summons_full if is_summon else weapons_full:
            continue
        weight = float(rules.kind_weights["grant"])
        if is_summon:
            weight *= rules.summon_factor
        name = d["name"]
        desc = d.get("description", "")
        def _apply(p, _wid=wid, _d=d):
            p.weapons.append(Weapon(_wid, _d))

        # CR4 (owner, 2026-09-10): the category line reads "<Class> Weapon
        # Grant" -- the class, not the weapon's name (the title has that).
        out.append(Upgrade(
            id=f"grant:{wid}", title=f"New: {name}", description=desc,
            weight=weight, apply=_apply, max_stacks=1,
            tags=(d["class"], "weapon", "grant"), kind="grant",
            rarity="common", level=1, weapon=wid))
    return out


def forge_offers_for(player, content, weapon: Weapon, *, weighted: bool = True) -> list[Upgrade]:
    """The Forge cards for one weapon (P3, design §7): one per Forging of
    that weapon. At Forge rarity in the level-up roll; the village Forge
    shows them all regardless of weight."""
    rules = get_rules(content)
    weight = float(rules.kind_weights["forge"]) * float(rules.rarity_weights["forge"])
    out = []
    for fdef in get_forges(content).for_weapon(weapon.weapon_id):
        out.append(Upgrade(
            # The card's own name, unprefixed (owner, 2026-09-12): the screen
            # title and the FORGE rarity tag already say it is a Forging, so
            # "Forge: Whirlwind" said it three times.
            id=f"forge:{fdef.id}", title=fdef.name,
            description=f"{fdef.description} ({fdef.identity}.)",
            weight=weight if weighted else 1.0,
            apply=lambda p, _w=weapon, _f=fdef: apply_forge(_w, _f),
            max_stacks=1, tags=(content.weapons[weapon.weapon_id]["name"], "forge"),
            kind="forge", rarity="forge", level=1, weapon=weapon.weapon_id))
    return out


def forge_offers(player, content) -> list[Upgrade]:
    """Forge cards for every eligible owned weapon."""
    need = get_rules(content).forge_requires_levels
    out = []
    for w in player.weapons:
        if forge_eligible(w, need):
            out.extend(forge_offers_for(player, content, w))
    return out


def valid_offers(player, content, rng: random.Random, *, kinds=None) -> list[Upgrade]:
    """The whole valid set: blessings, grants and Forge cards. `kinds` limits
    to a subset of ("stat", "weapon", "grant", "forge") -- shrines use it to
    offer only stat / weapon blessings."""
    out = blessing_offers(player, content, kinds=kinds)
    if kinds is None or "grant" in kinds:
        out.extend(grant_offers(player, content, rng))
    if kinds is None or "forge" in kinds:
        out.extend(forge_offers(player, content))
    return out


def roll_offering(player, content, rng: random.Random, n: int | None = None,
                  *, kinds=None) -> list[Upgrade]:
    """Pick up to `n` distinct cards by weight (default: the data's
    `choices`). Never an invalid or maxed option; fewer if fewer remain."""
    rules = get_rules(content)
    if n is None:
        n = rules.choices
    candidates = valid_offers(player, content, rng, kinds=kinds)
    chosen: list[Upgrade] = []
    while candidates and len(chosen) < n:
        weights = [u.weight for u in candidates]
        pick = rng.choices(candidates, weights=weights, k=1)[0]
        chosen.append(pick)
        candidates.remove(pick)
    return chosen


__all__ = ["MAX_SUMMONS", "MAX_WEAPONS", "blessing_offers", "blessing_weight",
           "forge_offers", "forge_offers_for", "grant_offers",
           "roll_offering", "roman", "valid_offers"]
