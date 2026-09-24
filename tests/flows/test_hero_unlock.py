"""The main-weapon choice. Unlocked per
hero by the first boss kill, remembered in the save, picked on the hero
select, and used by the run; defaults hold until then (design §20)."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import save as save_mod
from game.game import Game
from game.states.character_select_state import CharacterSelectState
from game.states.menu_state import MenuState
from game.states.playing.core.state import PlayingState
from tests.boot import settle



def _ride_out_banner(game, limit=700):
    """The end banner plays between the boss kill and the victory screen
    (journal: end_banner_journal.md, 2026-09-19): step until it has."""
    from game.states.end_banner_state import EndBannerState
    for _ in range(limit):
        if not isinstance(game.state_machine.current, EndBannerState):
            break
        game.state_machine.update(1 / 60)
    return game.state_machine.current

def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def _to_select(game) -> CharacterSelectState:
    game.state_machine.change(MenuState(game))
    _key(game, pygame.K_RETURN)
    sel = game.state_machine.current
    assert isinstance(sel, CharacterSelectState)
    return sel


class UnlockOnVictoryTests(unittest.TestCase):
    def test_a_victory_clears_the_hero_and_persists(self):
        game = _game()
        game._on_run_ended(stats={"character_id": "kestrel", "currency": 0},
                           victory=True)
        self.assertTrue(game.save.hero_cleared("kestrel"))
        self.assertFalse(game.save.hero_cleared("aegis"))
        self.assertTrue(save_mod.load(game.save_path).hero_cleared("kestrel"))
        pygame.quit()

    def test_a_defeat_or_a_dev_run_clears_nothing(self):
        game = _game()
        game._on_run_ended(stats={"character_id": "kestrel"}, victory=False)
        game._on_run_ended(stats={"character_id": "aegis"}, victory=True, dev=True)
        self.assertFalse(game.save.hero_cleared("kestrel"))
        self.assertFalse(game.save.hero_cleared("aegis"))
        pygame.quit()

    def test_the_run_summary_names_the_hero_id(self):
        game = _game()
        _to_select(game)
        _key(game, pygame.K_RETURN)
        p = settle(game)
        self.assertIsInstance(p, PlayingState)
        seen = []
        game.events.subscribe = getattr(game.events, "subscribe", None)
        from game.events import Events
        game.events.subscribe(Events.RUN_ENDED, lambda **kw: seen.append(kw))
        p.player.weapons = []
        p._end_run(victory=True)
        self.assertEqual(seen[-1]["stats"]["character_id"], "aegis")
        pygame.quit()

    def test_a_real_boss_kill_hands_the_victory_screen_what_it_draws(self):
        """The victory screen's extra facts, from a real kill rather than a
        hand-built dict: which boss fell, that this was a win, whether the
        clear was the hero's first, and the build snapshot the Hero column
        needs. `first_clear` in particular can only be read *before*
        `Game._on_run_ended` marks the hero cleared, so it is asserted here
        where the real ordering applies.
        """
        game = _game()
        _to_select(game)
        _key(game, pygame.K_RETURN)
        p = settle(game)
        self.assertIsInstance(p, PlayingState)
        p.player.invulnerable = True
        p.spawn.spawn_boss()
        boss_name = p.boss.name
        p._on_boss_killed()

        from game.states.victory_state import VictoryState
        state = _ride_out_banner(game)
        self.assertIsInstance(state, VictoryState)
        s = state.stats
        self.assertTrue(s["victory"])
        self.assertEqual(s["boss"], boss_name)
        self.assertIn(s["boss_id"], game.content.bosses)
        self.assertTrue(s["first_clear"], "a fresh save's first win is a first clear")
        self.assertIn(boss_name, state._screen.subtitle)
        # The Hero column's inputs: the resolved stats are a plain dict on the
        # player, not the StatSet beside them.
        self.assertIsInstance(s["hero_stats"], dict)
        self.assertIn("max_hp", s["hero_stats"])
        self.assertIsInstance(s["equipment"], list)
        # Gold is reported gross: a run tracks what it earned alongside the
        # balance the Merchant spends from.
        self.assertIn("gold_earned", s)
        self.assertGreaterEqual(s["gold_earned"], s["gold"],
                                "the total earned cannot be under the balance")
        pygame.quit()

    def test_a_later_clear_with_the_same_hero_is_not_a_first_clear(self):
        game = _game()
        game.save.mark_cleared("aegis")
        _to_select(game)
        _key(game, pygame.K_RETURN)
        p = settle(game)
        p.player.invulnerable = True
        p.spawn.spawn_boss()
        p._on_boss_killed()
        self.assertFalse(_ride_out_banner(game).stats["first_clear"])
        pygame.quit()


class RunStartTests(unittest.TestCase):
    def _run(self, game):
        _to_select(game)
        _key(game, pygame.K_RETURN)
        p = settle(game)
        self.assertIsInstance(p, PlayingState)
        return p

    def test_default_until_cleared(self):
        game = _game()
        game.save.set_main_weapon("aegis", "hammer")        # chosen but not cleared
        p = self._run(game)
        self.assertEqual(p.player.weapons[0].weapon_id, "sword")
        pygame.quit()

    def test_the_saved_choice_once_cleared(self):
        game = _game()
        game.save.mark_cleared("aegis")
        game.save.set_main_weapon("aegis", "hammer")
        p = self._run(game)
        self.assertEqual(p.player.weapons[0].weapon_id, "hammer")
        pygame.quit()

    def test_a_summon_or_unknown_choice_falls_back(self):
        game = _game()
        game.save.mark_cleared("aegis")
        game.save.set_main_weapon("aegis", "spirit_wolf")
        self.assertEqual(self._run(game).player.weapons[0].weapon_id, "sword")
        pygame.quit()
        game = _game()
        game.save.mark_cleared("aegis")
        game.save.set_main_weapon("aegis", "no_such_weapon")
        self.assertEqual(self._run(game).player.weapons[0].weapon_id, "sword")
        pygame.quit()


class SelectScreenTests(unittest.TestCase):
    def test_locked_hero_cannot_cycle(self):
        game = _game()
        sel = _to_select(game)
        _key(game, pygame.K_e)
        self.assertEqual(sel.main_weapon(), "sword")
        game._render()
        self.assertIsNone(sel._mouse.hits.rect_of("weapon_next"))
        pygame.quit()

    def test_cleared_hero_cycles_with_q_and_e_and_the_arrows(self):
        game = _game()
        game.save.mark_cleared("aegis")
        sel = _to_select(game)
        self.assertEqual(sel.main_weapon(), "sword")
        _key(game, pygame.K_e)
        self.assertEqual(sel.main_weapon(), "hammer")
        _key(game, pygame.K_q); _key(game, pygame.K_q)
        self.assertEqual(sel.main_weapon(), "bomb")          # wraps, summons skipped
        sel._mouse_action("click", "weapon_next")
        self.assertEqual(sel.main_weapon(), "sword")
        game._render()
        self.assertIsNotNone(sel._mouse.hits.rect_of("weapon_next"))
        self.assertIsNotNone(sel._mouse.hits.rect_of("weapon_prev"))
        pygame.quit()

    def test_begin_remembers_the_choice_and_the_run_uses_it(self):
        game = _game()
        game.save.mark_cleared("aegis")
        sel = _to_select(game)
        _key(game, pygame.K_e); _key(game, pygame.K_e)          # hammer, daggers
        self.assertEqual(sel.main_weapon(), "daggers")
        _key(game, pygame.K_RETURN)
        p = settle(game)
        self.assertIsInstance(p, PlayingState)
        self.assertEqual(p.player.weapons[0].weapon_id, "daggers")
        self.assertEqual(game.save.main_weapon("aegis"), "daggers")
        self.assertEqual(save_mod.load(game.save_path).main_weapon("aegis"), "daggers")
        pygame.quit()

    def test_the_choice_is_per_hero(self):
        game = _game()
        game.save.mark_cleared("aegis")
        sel = _to_select(game)
        _key(game, pygame.K_e)                                  # aegis -> hammer
        _key(game, pygame.K_RIGHT)                              # kestrel (locked)
        self.assertEqual(sel.main_weapon(), "bow")
        _key(game, pygame.K_e)
        self.assertEqual(sel.main_weapon(), "bow")
        _key(game, pygame.K_LEFT)
        self.assertEqual(sel.main_weapon(), "hammer")
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
