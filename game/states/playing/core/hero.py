"""The hero's set-up and animation (structure review, D3).

`HeroAnim` is the hero's sprite state: which strip plays this frame --
death, hurt, the alternating attacks, the guard, walk, idle -- and the
per-hero accent colour the primitive fallback and the HUD tint use.
`main_weapon_for` and `apply_persistent_bonuses` are the two set-up rules
that read the save: the weapon the run starts with, and the meta upgrades
and equipped items applied before the first frame.

`PlayingState` keeps `_hero_anim`, `_hero_color`, `_hero_has_hurt`,
`_hero_has_anim`, `_hero_anim_name`, `_update_hero_anim` and
`_main_weapon_for` as forwarders here.
"""
from __future__ import annotations

from game import config
from progression.items import Item
from progression.stats import FLAT, MULT, PCT, Modifier
from systems.animation import Animator

STARTING_WEAPON = "sword"
_OP_MAP = {"flat": FLAT, "pct": PCT, "mult": MULT}


class HeroAnim:
    def __init__(self, run, cdef: dict) -> None:
        self.run = run
        assets = run.game.assets
        # Hero sprite: only the characters that declare a rig get one; the rest
        # keep the primitive circle (fallback in `WorldRenderer.player`).
        rig = cdef.get("sprite")
        self.anim = Animator(assets, rig) if rig else None
        self.has_hurt = rig is not None and assets.frame_count(rig, "hurt") > 0
        # Per-hero accent colour (primitive fallback + any HUD tint); the shared
        # config default covers characters with no `color`.
        self.color = tuple(cdef.get("color", config.COLOR_PLAYER))

    def has_anim(self, name: str) -> bool:
        return has_anim(self.anim, self.run.game.assets, name)

    def anim_name(self) -> str:
        return anim_name(self.run.player, self.has_hurt, self.has_anim)

    def update(self, dt: float) -> None:
        if self.anim is None:
            return
        self.anim.play(self.anim_name())
        self.anim.update(dt)


# The two rules as functions, so the state's `_hero_has_anim` /
# `_hero_anim_name` can apply them to a bare namespace (the tests' fakes)
# as well as to a `HeroAnim`.
def has_anim(anim, assets, name: str) -> bool:
    return anim is not None and assets.frame_count(anim.rig, name) > 0


def anim_name(p, has_hurt: bool, has_anim_fn) -> str:
    """Which strip the hero plays this frame."""
    if not p.alive:
        return "death"
    if p._hurt_t > 0.0 and has_hurt:
        return "hurt"
    if p._attack_t > 0.0:
        # P5: attacks alternate between the two attack sheets when the
        # rig has a second one -- the 1st, 3rd, 5th ... swing on sheet 1,
        # the 2nd, 4th ... on sheet 2 (`_attack_cycle` counts swings).
        if (p._attack_cycle > 0 and p._attack_cycle % 2 == 0
                and has_anim_fn("attack2")):
            return "attack2"
        return "attack"
    moving = p._move_dir.length_squared() > 0
    if not moving and p.bulwark_active and has_anim_fn("guard"):
        return "guard"                   # P5: Aegis's guard is up
    return "walk" if moving else "idle"


def main_weapon_for(run, cdef: dict, chosen: str | None) -> str:
    """The hero's starting weapon (P5, design §20): the data's default,
    or the weapon chosen on the hero select once the hero has cleared
    the boss -- the choice comes with the run (`main_weapon` kwarg, here
    `chosen`) or from the save. A summon or an unknown id falls back to the
    default."""
    default = cdef.get("starting_weapon", STARTING_WEAPON)
    save, content = run.game.save, run.content
    if chosen is None:
        chosen = save.main_weapon(run.character_id)
    if (chosen and chosen in content.weapons
            and content.weapon(chosen)["class"] != "summon"
            and save.hero_cleared(run.character_id)):
        return chosen
    return default


def apply_persistent_bonuses(run) -> None:
    """Meta upgrades and the equipped items, applied to the hero before the
    run starts; HP filled to the boosted maximum."""
    save, player = run.game.save, run.player
    # Meta upgrades.
    player.add_modifiers(*run.game.meta_catalog.player_modifiers(save.meta))
    # Equipped items: plain stat affixes -> StatSet; tag affixes are folded
    # into blessing_fx by rebuild_blessings via player.equipment.
    player.equipment = [Item.from_dict(d) for d in save.equipped_items()]
    for item in player.equipment:
        mods = [Modifier(stat, _OP_MAP[op], val, f"item:{item.slot}")
                for stat, op, val in item.stat_effects()]
        player.add_modifiers(*mods)
        if item.unique_effect == "overflow" and player.weapons:
            player.weapons[0].bonus["projectile_count"] += 1
    player.hp = player.max_hp  # fill to the boosted maximum
