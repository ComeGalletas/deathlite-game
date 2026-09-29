"""Every player-facing screen, as a `draw(surface)` the fit test runs in
each language and at each size (UI-014.11).

A scene builds its state inside `draw`, so the text it composes at `enter`
is tracked. The in-run scenes share one booted run on a pinned world,
booted inside `fit_harness.tracking()` so the fonts it keeps are tracked
too. The data is the wordiest a run can show, measured in Spanish: four
weapons with a forging, the six longest blessing names, every enemy kind
killed (more than the column lists), a kill record with a four-digit
count, every element, the longest notice, boss and buff names, the
level-up offering with the most words out of 200 rolls, and the end
screens and Forge with their art.

The developer tools stay English (UI-014.D6) and are not here.
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

from game import config, locale
from game.content import get_content
from progression.items import generate_item
from tests.screens import fit_harness

SIZES = ((1600, 900), (1280, 720))


def _game():
    """A fresh game in the language the scene is drawn in: `Game()` applies
    its save's language, the default on a new save."""
    from game.game import Game
    lang = locale.language()
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    locale.set_language(lang)
    return game


def _records(game):
    for diff in config.DIFFICULTY_ORDER:
        game.save.records[diff] = {"time": 1799.0, "level": 38.0, "kills": 12345.0,
                                   "damage_dealt": 9876543.0}


def _items(n=6):
    content = get_content()
    return [generate_item(content, seed=s, item_level=9, luck=1.0) for s in range(n)]


def _enter(cls, game, surface, **kw):
    st = cls(game)
    st.enter(**kw)
    st.draw(surface)
    return st


# --- the menus ------------------------------------------------------------
def menu(surface):
    """The title menu over a played save: its summary line at its widest."""
    from game.states.menu_state import MenuState
    game = _game()
    _records(game)
    game.save.currency = 123456
    game.save.best.update(time=1799.0, level=38.0, kills=12345.0)
    game.save.discovered_items = [f"item_{i}" for i in range(157)]
    _enter(MenuState, game, surface)


def hero_select(index, unlocked=False):
    """The hero cards, the hardest difficulty picked; `unlocked`, every hero
    cleared, so each card carries its main-weapon picker (two more rows)."""
    def draw(surface):
        from game.states.character_select_state import CharacterSelectState
        game = _game()
        if unlocked:
            for cid in get_content().characters:
                game.save.mark_cleared(cid)
        st = CharacterSelectState(game)
        st.enter()
        st.index = index
        st._sync_preview()
        st.diff_index = len(config.DIFFICULTY_ORDER) - 1
        st.draw(surface)
    return draw


def options(in_run, display=None):
    """Options; `display` "borderless" or "custom" shows the display rows as
    a desktop does (the dummy driver has none: "Unavailable"), the second
    with a dragged window's "Custom 3437x1411"."""
    def draw(surface):
        from game.states.options_state import OptionsState
        game = _game()
        if display is not None:
            d = game.display
            d.available = True
            d.mode = "borderless" if display == "borderless" else "windowed"
            d.windowed_size = (3437, 1411)
        _enter(OptionsState, game, surface, in_run=in_run)
    return draw


def rankings(filled):
    def draw(surface):
        from game.states.rankings_state import RankingsState
        game = _game()
        if filled:
            _records(game)
        _enter(RankingsState, game, surface)
    return draw


def sanctuary(panel):
    def draw(surface):
        from game.states.meta_state import MetaState
        game = _game()
        game.save.currency = 12345
        game.save.meta = {k: 3 for k in list(game.meta_catalog.defs)[:4]}
        for it in _items(8):
            game.save.stash.append(it.to_dict())
        # Every slot filled, with the longest Spanish name the stash has for it.
        for slot in game.save.equipped:
            fits = [d for d in game.save.stash if d.get("slot") == slot]
            if fits:
                from ui.run_summary import _localized_item_name
                game.save.equipped[slot] = _longest_es(
                    fits, _localized_item_name)[0]["item_id"]
        st = MetaState(game)
        st.enter()
        st.panel = panel
        st.draw(surface)
    return draw


def loading(surface):
    from game.states.loading_state import LoadingState
    _enter(LoadingState, _game(), surface, seed=1)


def paused(surface):
    from game.states.paused_state import PausedState
    _enter(PausedState, _game(), surface)


# --- the TAB screen: the dressed run, and a run with nothing yet -----------
def run_status(pane, full):
    def draw(surface):
        from game.states.run_status_state import PANES
        from tests.screens.test_run_status import _run, _state
        ps = booted()[1] if full else _run(full=False)
        s = _state(ps)
        s.game.assets = booted()[0].assets       # the tab buttons' art, as the player sees it
        s.tab = PANES.index(pane)
        s.draw(surface)
    return draw


# --- the run ---------------------------------------------------------------
_RUN = {}


def _longest_es(items, name):
    """`items` sorted by their Spanish name, longest first."""
    was = locale.language()
    locale.set_language("es")
    try:
        return sorted(items, key=lambda x: -len(name(x)))
    finally:
        locale.set_language(was)


def _dress(ps):
    """The wordiest late run: four weapons, one forged; the six blessings with
    the longest Spanish names at level 3 and every other one the weapons can
    take at level 1 (more than the Blessings pane and the summary list);
    three items; damage on every weapon and a blessing proc; every enemy kind
    killed, the Spanish-longest names most; four-digit gold; every element."""
    from combat.elements.ids import ElementId
    from combat.weapons import Weapon
    from combat.weapons.forge import apply_forge, get_forges
    from progression.blessings import apply_blessing
    run = ps.run
    content, player = run.content, run.player
    player.weapons[:] = [Weapon(w, dict(content.weapon(w)))
                         for w in ("sword", "daggers", "bow", "spirit_wolf")]
    for w in player.weapons:
        w.level = 8
    apply_forge(player.weapons[0], get_forges(content).get("whirlwind"))
    player.weapons[2].element = ElementId.FIRE
    held = {w.weapon_id for w in player.weapons}
    lib = ps.blessing_lib
    fit = [b for b in lib.by_id.values()
           if (b.weapon is None or b.weapon in held) and not b.requires_forge
           and set(b.requires_weapons) <= held]
    ranked = _longest_es(fit, lambda b: b.display_name)
    for b in ranked[:6]:
        for _ in range(3):
            apply_blessing(player, b)
    for b in ranked[6:]:
        apply_blessing(player, b)
    player.equipment = _items(3)
    player.recompute()
    ledger = run.ledger
    ledger.track_held(held)
    for i, w in enumerate(player.weapons):
        ledger.record(2_400_000.0 / (i + 1), source=w.weapon_id)
    ledger.record(44_443.0, source=next(iter(lib.by_id)))
    enemies = _longest_es([(k, d) for k, d in content.enemies.items() if k != "training_dummy"],
                          lambda kd: locale.text(kd[1], "name"))
    counts = [2400, 900, 250, 100, 60, 40, 30, 25, 20, 15, 12, 9, 7, 5, 3, 2, 1, 1]
    for (key, cfg), n in zip(enemies, counts):
        foe = SimpleNamespace(enemy_id=key, name=cfg["name"], cfg=cfg)
        for _ in range(n):
            ledger.kill(foe)
    run.unlocked_elements = {ElementId.FIRE, ElementId.ICE, ElementId.THUNDER, ElementId.WIND}
    run.stats.update(time=1799.0, level=38, kills=ledger.total_kills, gold_earned=1840,
                     gold=1840,
                     currency=1840, potions=12, potion_healing=1234.5, chests=14,
                     damage_dealt=ledger.total,
                     dropped_items=[it.to_dict() for it in _items(6)])


def booted():
    """One dressed run on a pinned world, shared by every in-run scene."""
    if "ps" not in _RUN:
        from game.states.menu_state import MenuState
        from tests import worlds as W
        from tests.boot import start_run
        was = locale.language()
        with fit_harness.tracking():
            game = _game()
            game.state_machine.change(MenuState(game))
            ps = start_run(game, W.pinned(1))
        locale.set_language(was)
        _dress(ps)
        _RUN["game"], _RUN["ps"] = game, ps
    return _RUN["game"], _RUN["ps"]


def summary_stats(victory):
    """What the run hands the end screen, named in the language in use."""
    _game_, ps = booted()
    return ps.run_end.snapshot_summary(victory)


def _end(cls, victory):
    """An end screen with its art (the ribbons and buttons the player sees),
    past its input lock."""
    def draw(surface):
        st = cls(_game())
        st.enter(stats=summary_stats(victory))
        st.update(config.END_SCREEN_INPUT_LOCK)
        st.draw(surface)
    return draw


def end_banner(victory):
    """The banner mid-play with its art missing: the one case it draws text,
    the words in the language in use (`banner.win`, `banner.loss`). With the
    art it plays the pack's sprite in every language (UI-015.D1)."""
    def draw(surface):
        from game.states.end_banner_state import BANNER, EndBannerState
        game = _game()
        game.assets = None
        st = EndBannerState(game)
        st.enter(victory=victory, on_done=lambda: None)
        for _ in range(600):
            if st.phase == BANNER:
                break
            st.update(1 / 60)
        assert st.phase == BANNER, st.phase
        st.draw(surface)
    return draw


def game_over(surface):
    from game.states.game_over_state import GameOverState
    _end(GameOverState, False)(surface)


def victory(surface):
    from game.states.victory_state import VictoryState
    _end(VictoryState, True)(surface)


def hud(surface):
    """The run as it opens: the HUD and the tutorial hints."""
    from ui.hud import HUD
    game, ps = booted()
    ps.hud = HUD()
    ps.draw(surface)


def _notices(ps):
    """The run's longer notices, each composed as the run composes it: the
    Forge's answer (its weapon and forging the Spanish-longest), the Forge
    with nothing to work on, and a chest's payout at its richest -- four-
    digit gold, the Spanish-longest potion rarity and blessing title."""
    from combat.weapons.forge import get_forges
    from game.states.playing.core import chests as chests_mod
    run = ps.run
    fdef = _longest_es(list(get_forges(run.content).by_id.values()),
                       lambda f: f.display_name)[0]
    forged = locale.t("forge.reforged", weapon=ps.locations._base_name(fdef.weapon),
                      forge=fdef.display_name)
    weapon = _longest_es(list(run.player.weapons), lambda w: w.name)[0]
    needs = locale.plural("forge.needs", 2, need=3, weapon=weapon.name)
    rarities = ("common", "uncommon", "rare", "epic")
    chest = _longest_es(rarities, lambda r: chests_mod._rarity_word("chest", r))[0]
    potion = _longest_es(rarities, lambda r: chests_mod._rarity_word("potion", r))[0]
    bdef = _longest_es(list(ps.blessing_lib.by_id.values()), lambda b: b.title(3))[0]
    parts = [locale.t("chest.gold", n=1840),
             locale.t("chest.potion", rarity=chests_mod._rarity_word("potion", potion)),
             bdef.title(3)]
    payout = locale.t("chest.notice", contents=chests_mod.Chests._listed(parts),
                      rarity=chests_mod._rarity_word("chest", chest))
    return [forged, needs, payout]


def hud_notice(surface):
    """The HUD with the boss warning and the longest of the run's notices,
    chosen in Spanish (`_notices`; the chest's payout)."""
    from ui.hud import HUD
    game, ps = booted()
    run = ps.run
    ps.hud = HUD()
    boss = _longest_es(list(run.content.bosses.values()), lambda d: locale.text(d, "name"))[0]
    run._boss_name, run._boss_warning_t = locale.text(boss, "name"), 0.1
    was = locale.language()
    locale.set_language("es")
    try:
        k = max(range(3), key=lambda i: len(_notices(ps)[i]))
    finally:
        locale.set_language(was)
    run.notice(_notices(ps)[k])
    try:
        ps.draw(surface)
    finally:
        run._boss_warning_t, run._notice_t = 0.0, 0.0


def hud_boss(surface):
    """The HUD with the boss bar, the longest boss name in Spanish."""
    from ui.hud import HUD
    game, ps = booted()
    run = ps.run
    boss = _longest_es(list(run.content.bosses.values()), lambda d: locale.text(d, "name"))[0]
    HUD().draw(surface, run.player, run.stats, xp_fraction=0.5,
               boss=SimpleNamespace(name=locale.text(boss, "name"), hp_fraction=0.5,
                                    alive=True))


def boss_name() -> str:
    """The boss `hud_boss` names, in the language in use."""
    bosses = list(get_content().bosses.values())
    return locale.text(_longest_es(bosses, lambda d: locale.text(d, "name"))[0], "name")


def hud_hints_attack(surface):
    """The hints' second stage, the wordier one: Attack and Aim."""
    from ui.hud import HUD
    game, ps = booted()
    stage = ps.hints.stage
    ps.hints.stage, ps.hints.fading = "attack", None
    ps.hud = HUD()
    try:
        ps.draw(surface)
    finally:
        ps.hints.stage = stage


def hud_buff(surface):
    """A buff's flying name over the hero: the longest Spanish buff name."""
    from ui.hud import HUD
    game, ps = booted()
    buffs = ps.buffs
    kind = _longest_es(list(buffs.defs), lambda k: locale.text(buffs.defs[k], "name")
                       if "name" in buffs.defs[k] else k)[0]
    ps.hud = HUD()
    saved, stage = list(buffs.banners.items), ps.hints.stage
    # The hints are gone by then: a buff takes a walk to its building, and
    # the Move hint ends with the first steps.
    ps.hints.stage, ps.hints.fading = None, None
    buffs.banners.add(locale.text(buffs.defs[kind], "name"), buffs.palette(kind)[0])
    try:
        ps.draw(surface)
    finally:
        buffs.banners.items[:] = saved
        ps.hints.stage = stage


def _pushed(open_overlay):
    """Draw the overlay `open_overlay(ps)` pushes over the run, then pop it."""
    def draw(surface):
        from game.states.level_up_state import LevelUpState
        game, ps = booted()
        assert game.state_machine.current is ps, game.state_machine.current
        open_overlay(ps)
        st = game.state_machine.current
        assert isinstance(st, LevelUpState), st
        st.draw(surface)
        game.state_machine.pop()
    return draw


def _forge(ps):
    ps.locations.use_forge(SimpleNamespace(pos=ps.run.player.pos, colour=(255, 255, 255)))


def _infusion(ps):
    """The Monastery: every element, one weapon; its own title."""
    ps.locations.use_monastery(SimpleNamespace(pos=ps.run.player.pos, colour=(255, 255, 255)))


def _buff_infusion(ps):
    """An elemental buff building: the weapon picker for its element, the
    Spanish-longest one, through the building's own `activate` (the buff
    itself is not started, so the shared run's stats stay put)."""
    from unittest import mock
    from game.states.playing.core import infusion
    from combat.elements.ids import ElementId
    element = _longest_es([e for e in ElementId if e != ElementId.NONE],
                          infusion.element_name)[0]
    buffs = ps.buffs
    it = SimpleNamespace(kind=next(iter(buffs.defs)), element=element,
                         pos=ps.run.player.pos, used=False)
    with mock.patch.object(buffs, "start"), mock.patch.object(buffs, "_mark_used"):
        buffs.activate(it)


def _forge_row(k):
    """The Forge with the rail's `k`-th eligible weapon picked."""
    def open_it(ps):
        _forge(ps)
        st = ps.game.state_machine.current
        usable = [i for i, r in enumerate(st.weapon_rows) if r[1]]
        st._select_weapon(usable[k % len(usable)])
    return open_it


forge = _pushed(_forge)
infusion_picker = _pushed(_infusion)


_WORDIEST = {}


def _offering(ps, seed):
    import random
    from progression.blessings.offer import roll_offering
    return roll_offering(ps.run.player, ps.run.content, random.Random(seed))


def level_up(surface):
    """The offering with the most Spanish words out of 200 seeded rolls, in
    the language in use (the same cards: the roll does not read it)."""
    from game.states.level_up_state import LevelUpState
    game, ps = booted()
    assert game.state_machine.current is ps, game.state_machine.current
    if "seed" not in _WORDIEST:
        was = locale.language()
        locale.set_language("es")
        try:
            _WORDIEST["seed"] = max(range(200), key=lambda k: sum(
                len(u.title) + len(u.description) for u in _offering(ps, k)))
        finally:
            locale.set_language(was)
    game.state_machine.push(LevelUpState(game), player=ps.run.player,
                            choices=_offering(ps, _WORDIEST["seed"]), on_done=lambda u: None)
    lu = game.state_machine.current
    assert isinstance(lu, LevelUpState), lu
    lu.draw(surface)
    game.state_machine.pop()


SCENES = {
    "menu": menu,
    **{f"hero_select_{i}": hero_select(i) for i in range(3)},
    **{f"hero_select_unlocked_{i}": hero_select(i, unlocked=True) for i in range(3)},
    "options": options(False),
    "options_in_run": options(True),
    "options_borderless": options(False, "borderless"),
    "options_custom": options(False, "custom"),
    "rankings": rankings(True),
    "rankings_empty": rankings(False),
    "sanctuary_upgrades": sanctuary(0),
    "sanctuary_stash": sanctuary(1),
    "loading": loading,
    "paused": paused,
    **{f"tab_{p}": run_status(p, True) for p in ("overview", "build", "blessings")},
    **{f"tab_empty_{p}": run_status(p, False) for p in ("overview", "build", "blessings")},
    "game_over": game_over,
    "victory": victory,
    "hud": hud,
    "hud_notice": hud_notice,
    "hud_boss": hud_boss,
    "hud_hints_attack": hud_hints_attack,
    "hud_buff": hud_buff,
    "end_banner_win": end_banner(True),
    "end_banner_loss": end_banner(False),
    "level_up": level_up,
    "forge": forge,
    "forge_second_weapon": _pushed(_forge_row(1)),
    "infusion": infusion_picker,
    "buff_infusion": _pushed(_buff_infusion),
}
