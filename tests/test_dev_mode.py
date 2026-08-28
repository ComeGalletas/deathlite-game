"""Developer mode D1: a non-persistent sandbox run.

The `dev` flag rides menu -> character select -> playing; a dev run never banks
salvage / best / loot and never writes `save.json`; when it ends (death or
otherwise) it restarts in place on the same world seed instead of showing a
summary. Leaving via the pause menu also persists nothing.
"""
import copy
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
from game.states.paused_state import PausedState
from game.states.playing_state import PlayingState


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def _start_dev_run(game):
    game.state_machine.change(MenuState(game))
    _key(game, pygame.K_DOWN)        # -> "Start new developer mode game"
    _key(game, pygame.K_RETURN)      # -> character select (dev)
    _key(game, pygame.K_RETURN)      # -> playing (dev)
    return game.state_machine.current


class DevFlagPropagationTests(unittest.TestCase):
    def test_flag_rides_menu_to_charselect_to_playing(self):
        game = _game()
        game.state_machine.change(MenuState(game))
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)
        self.assertTrue(game.state_machine.current._dev)
        _key(game, pygame.K_RETURN)
        playing = game.state_machine.current
        self.assertIsInstance(playing, PlayingState)
        self.assertTrue(playing.dev_mode)

    def test_regular_run_is_not_dev(self):
        game = _game()
        game.state_machine.change(MenuState(game))
        _key(game, pygame.K_RETURN)      # Start new game
        _key(game, pygame.K_RETURN)      # pick hero
        self.assertFalse(game.state_machine.current.dev_mode)


class DevRunDoesNotSaveTests(unittest.TestCase):
    def test_on_run_ended_with_dev_flag_is_a_noop(self):
        game = _game()
        before = copy.deepcopy(game.save)
        called = []
        game.persist = lambda: called.append(1)
        game._on_run_ended(
            stats={"currency": 999, "time": 500, "kills": 40, "level": 12,
                   "damage_dealt": 9999, "dropped_items": [{"item_id": "x"}]},
            victory=True, dev=True)
        self.assertEqual(called, [])
        self.assertEqual(game.save.currency, before.currency)
        self.assertEqual(game.save.best, before.best)
        self.assertEqual(game.save.stash, before.stash)

    def test_regular_run_ended_still_banks(self):
        game = _game()
        game.persist = lambda: None
        game._on_run_ended(
            stats={"currency": 50, "time": 100, "kills": 10, "level": 4,
                   "damage_dealt": 500, "dropped_items": []}, victory=True)
        self.assertGreater(game.save.currency, 0)

    def test_dev_run_death_restarts_in_place_and_never_persists(self):
        game = _game()
        called = []
        game.persist = lambda: called.append(1)
        playing = _start_dev_run(game)
        self.assertTrue(playing.dev_mode)
        seed = playing.run_seed
        weapons_at_start = len(playing.player.weapons)

        # dirty the run so the restart is provably a wipe
        from progression.blessings import apply_blessing
        apply_blessing(playing.player,
                       playing.blessing_lib.by_id[next(iter(playing.blessing_lib.by_id))])
        playing.player.weapons.append(playing.player.weapons[0])
        playing.stats["time"] = 5.0

        playing.player.take_damage(10 ** 9)             # lethal
        for _ in range(120):
            game.state_machine.update(1 / 60)
            if game.state_machine.current is not playing:
                break

        fresh = game.state_machine.current
        self.assertIsInstance(fresh, PlayingState)
        self.assertIsNot(fresh, playing)
        self.assertTrue(fresh.dev_mode)
        self.assertEqual(fresh.run_seed, seed)          # same world
        self.assertEqual(fresh.player.blessings, {})
        self.assertEqual(len(fresh.player.weapons), weapons_at_start)
        self.assertLess(fresh.stats["time"], 0.5)
        self.assertEqual(called, [])
        self.assertEqual(save_mod.load(game.save_path).currency, 0)

    def test_dev_run_end_does_not_open_a_summary_state(self):
        game = _game()
        playing = _start_dev_run(game)
        playing._end_run(victory=True)                  # e.g. a dev boss kill
        self.assertIsInstance(game.state_machine.current, PlayingState)
        self.assertTrue(game.state_machine.current.dev_mode)


class DevRunExitPathsTests(unittest.TestCase):
    def test_pause_quit_to_menu_from_a_dev_run_persists_nothing(self):
        game = _game()
        called = []
        game.persist = lambda: called.append(1)
        _start_dev_run(game)
        _key(game, pygame.K_ESCAPE)                     # -> paused
        self.assertIsInstance(game.state_machine.current, PausedState)
        _key(game, pygame.K_q)                          # -> main menu
        self.assertIsInstance(game.state_machine.current, MenuState)
        self.assertEqual(called, [])


def _open_dev_menu(game):
    playing = _start_dev_run(game)
    _key(game, pygame.K_BACKQUOTE)
    return playing, game.state_machine.current


class DevMenuTests(unittest.TestCase):
    def test_backquote_opens_the_menu_only_in_a_dev_run(self):
        from game.states.dev_menu_state import DevMenuState
        # regular run -- backquote does nothing
        game = _game()
        game.state_machine.change(MenuState(game))
        _key(game, pygame.K_RETURN)
        _key(game, pygame.K_RETURN)
        playing = game.state_machine.current
        _key(game, pygame.K_BACKQUOTE)
        self.assertIs(game.state_machine.current, playing)
        # dev run -- it opens as an overlay
        game2 = _game()
        playing2, menu = _open_dev_menu(game2)
        self.assertIsInstance(menu, DevMenuState)
        self.assertIs(menu._playing, playing2)
        self.assertTrue(menu.draw_below and not menu.update_below)

    def test_run_is_frozen_while_the_dev_menu_is_open(self):
        game = _game()
        playing, _ = _open_dev_menu(game)
        t0 = playing.stats["time"]
        for _ in range(30):
            game.state_machine.update(1 / 60)
        self.assertEqual(playing.stats["time"], t0)

    def test_unlimited_hp_ratchets_and_keeps_the_hero_alive(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("unlimited_hp")
        self.assertTrue(playing._dev_unlimited_hp)
        _key(game, pygame.K_BACKQUOTE)                  # close, resume
        hp0 = playing.player.hp
        playing._spawn_enemy("tank", at=playing.player.pos.copy())   # constant contact
        for _ in range(30):
            game.state_machine.update(1 / 60)
        self.assertGreaterEqual(playing.player.hp, hp0)
        self.assertTrue(playing.player.alive)

    def test_stop_attacking_silences_the_hero_weapons(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("no_attack")
        self.assertTrue(playing._dev_no_attack)
        _key(game, pygame.K_BACKQUOTE)
        playing._spawn_enemy("tank", at=playing.player.pos + pygame.Vector2(24, 0))
        d0 = playing.stats["damage_dealt"]
        for _ in range(90):
            game.state_machine.update(1 / 60)
        self.assertEqual(playing.stats["damage_dealt"], d0)
        # sanity: with attacks back on, damage does accrue
        menu2_playing = playing
        menu2_playing._dev_no_attack = False
        for _ in range(90):
            game.state_machine.update(1 / 60)
        self.assertGreater(playing.stats["damage_dealt"], d0)

    def test_reset_row_restarts_the_dev_run_in_place(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        seed = playing.run_seed
        playing.player.weapons.append(playing.player.weapons[0])
        menu._activate("reset")
        fresh = game.state_machine.current
        self.assertIsInstance(fresh, PlayingState)
        self.assertIsNot(fresh, playing)
        self.assertTrue(fresh.dev_mode)
        self.assertEqual(fresh.run_seed, seed)
        self.assertEqual(len(fresh.player.weapons), 1)
        self.assertEqual(fresh.player.blessings, {})

    def test_exit_row_returns_to_menu_without_persist(self):
        game = _game()
        called = []
        game.persist = lambda: called.append(1)
        _, menu = _open_dev_menu(game)
        menu._activate("exit")
        self.assertIsInstance(game.state_machine.current, MenuState)
        self.assertEqual(called, [])

    def test_close_row_resumes_the_run(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("close")
        self.assertIs(game.state_machine.current, playing)

    def test_items_row_is_an_inert_placeholder(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("items")
        self.assertIs(game.state_machine.current, menu)
        self.assertEqual(menu.page, "root")
        self.assertEqual(menu._status, "(coming soon)")

    def test_difficulty_row_cycles_the_live_run_difficulty(self):
        from game.states.dev_menu_state import _ROOT_ROWS
        game = _game()
        playing, menu = _open_dev_menu(game)
        self.assertEqual(playing.difficulty, "normal")          # dev default
        d0 = playing.director.boss_time()

        menu._activate("difficulty")
        self.assertEqual(playing.difficulty, "fast")
        self.assertEqual(playing.director.difficulty, "fast")   # director re-bound
        self.assertAlmostEqual(playing.director.boss_time(), d0 / 1.25)
        self.assertIn("[Fast]", menu._row_label("difficulty"))

        menu._activate("difficulty")
        self.assertEqual(playing.difficulty, "super_fast")
        menu._activate("difficulty")
        self.assertEqual(playing.difficulty, "normal")          # wraps
        self.assertIn("difficulty", _ROOT_ROWS)

    def test_draw_runs_headless_on_every_page(self):
        from game.states.dev_menu_state import _ROOT_ROWS
        game = _game()
        _, menu = _open_dev_menu(game)
        for i in range(len(_ROOT_ROWS)):
            menu.sel = i
            menu.draw(game.screen)
        menu._activate("spawn")
        for i in range(len(menu._enemy_ids)):
            menu.sel = i
            menu.draw(game.screen)


class DevSpawnMenuTests(unittest.TestCase):
    def _spawn_page(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("spawn")
        return game, playing, menu

    def test_spawn_row_opens_the_enemies_page_listing_every_id(self):
        game, playing, menu = self._spawn_page()
        self.assertEqual(menu.page, "enemies")
        self.assertEqual(menu._enemy_ids, sorted(playing.content.enemies))

    def test_enter_spawns_exactly_one_of_the_selected_enemy(self):
        game, playing, menu = self._spawn_page()
        menu.sel = menu._enemy_ids.index("warlock")
        n0 = len(playing.enemies)
        _key(game, pygame.K_RETURN)
        self.assertEqual(len(playing.enemies), n0 + 1)
        self.assertEqual(playing.enemies[-1].enemy_id, "warlock")
        self.assertEqual(menu._spawn_counts["warlock"], 1)

    def test_page_stays_open_for_repeat_spawns(self):
        game, playing, menu = self._spawn_page()
        menu.sel = menu._enemy_ids.index("chaser")
        for _ in range(6):
            _key(game, pygame.K_RETURN)
        self.assertEqual(menu.page, "enemies")
        self.assertEqual(len(playing.enemies), 6)
        self.assertEqual(menu._spawn_counts["chaser"], 6)

    def test_escape_returns_to_root_without_closing_the_menu(self):
        game, playing, menu = self._spawn_page()
        _key(game, pygame.K_ESCAPE)
        self.assertEqual(menu.page, "root")
        self.assertIs(game.state_machine.current, menu)

    def test_spawned_enemy_lands_near_the_hero(self):
        game, playing, menu = self._spawn_page()
        _key(game, pygame.K_RETURN)
        e = playing.enemies[-1]
        self.assertLess((e.pos - playing.player.pos).length(), 300)


class DevBlessingMenuTests(unittest.TestCase):
    def _bless_page(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("blessings")
        return game, playing, menu

    def test_blessings_row_opens_the_page_listing_every_blessing(self):
        game, playing, menu = self._bless_page()
        self.assertEqual(menu.page, "blessings")
        self.assertEqual(set(menu._blessing_ids), set(playing.content.blessings))
        self.assertEqual(len(menu._blessing_ids), len(playing.content.blessings))

    def test_enter_grants_the_selected_blessing_and_rebuilds_fx(self):
        game, playing, menu = self._bless_page()
        menu.sel = 5
        bid = menu._blessing_ids[5]
        fx_before = playing.player.blessing_fx
        _key(game, pygame.K_RETURN)
        self.assertEqual(playing.player.blessings.get(bid), 1)
        self.assertIsNot(playing.player.blessing_fx, fx_before)     # rebuilt
        _key(game, pygame.K_RETURN)
        self.assertEqual(playing.player.blessings.get(bid), 2)      # stacks
        self.assertEqual(menu.page, "blessings")                    # stays open

    def test_escape_returns_to_root_without_closing(self):
        game, playing, menu = self._bless_page()
        _key(game, pygame.K_ESCAPE)
        self.assertEqual(menu.page, "root")
        self.assertIs(game.state_machine.current, menu)


class DevMenuScrollTests(unittest.TestCase):
    def _long_page(self):
        game = _game()
        playing, menu = _open_dev_menu(game)
        menu._activate("blessings")            # 32 rows > MAX_VISIBLE
        return game, playing, menu

    def test_selection_stays_within_the_visible_window(self):
        from game.states.dev_menu_state import MAX_VISIBLE
        game, playing, menu = self._long_page()
        self.assertEqual(menu.scroll, 0)
        n = len(menu._blessing_ids)
        for _ in range(n + 5):                 # sweep the whole list, wrapping
            _key(game, pygame.K_DOWN)
            self.assertTrue(menu.scroll <= menu.sel < menu.scroll + MAX_VISIBLE)
            self.assertLessEqual(menu.scroll, n - MAX_VISIBLE)

    def test_up_from_the_top_wraps_and_scrolls_to_the_bottom(self):
        from game.states.dev_menu_state import MAX_VISIBLE
        game, playing, menu = self._long_page()
        _key(game, pygame.K_UP)
        n = len(menu._blessing_ids)
        self.assertEqual(menu.sel, n - 1)
        self.assertEqual(menu.scroll, n - MAX_VISIBLE)

    def test_short_pages_never_scroll(self):
        game = _game()
        _, menu = _open_dev_menu(game)         # root: 8 rows < MAX_VISIBLE
        for _ in range(20):
            _key(game, pygame.K_DOWN)
        self.assertEqual(menu.scroll, 0)

    def test_draw_headless_across_scroll_positions(self):
        game, playing, menu = self._long_page()
        for s in (0, 6, 18, 31):
            menu.sel = s
            menu.draw(game.screen)             # draw() re-clamps scroll itself


if __name__ == "__main__":
    unittest.main()
