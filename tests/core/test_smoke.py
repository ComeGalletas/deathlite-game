"""Headless boot smoke test: the game must initialise, walk MENU -> PLAYING ->
PAUSED -> PLAYING and run frames without raising. Uses SDL's dummy drivers so
it works in CI with no display or audio device."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState
from game.states.paused_state import PausedState
from game.states.level_up_state import LevelUpState
from game.states.victory_state import VictoryState


class SmokeTest(unittest.TestCase):
    def test_boot_and_state_walk(self):
        save_path = os.path.join(tempfile.mkdtemp(), "save.json")
        game = Game(save_path=save_path)
        game.state_machine.change(MenuState(game))

        def key(k):
            game.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=k))

        # MENU -> CHARACTER_SELECT -> PLAYING
        key(pygame.K_RETURN)
        key(pygame.K_RETURN)  # pick the first hero
        playing = game.state_machine.current
        self.assertIsInstance(playing, PlayingState)

        # Seed a few enemies right next to the player so the check does not
        # depend on the director's opening cadence or the hero's weapon range.
        import pygame as _pg
        for dx in (-60, 60, -40, 40, 0):
            playing._spawn_enemy("chaser", at=playing.player.pos + _pg.Vector2(dx, 70))

        # advance ~15s: the starting weapon auto-fires, projectiles hit, enemies die.
        for _ in range(900):
            game.state_machine.update(1 / 60)
            game._render()

        # (enemies may all be dead again -- a strong starting weapon keeps the
        # field clear; kills / damage are the meaningful signals.)
        self.assertGreater(playing.stats["damage_dealt"], 0, "weapon dealt no damage")
        self.assertGreaterEqual(playing.stats["kills"], 5, "nothing was killed")

        # PROGRESSION: force a level-up, confirm the choice overlay appears,
        # pick option 1, confirm it applies and control returns to PLAYING.
        weapons_before = len(playing.player.weapons)
        stacks_before = sum(playing.player.upgrade_stacks.values())
        playing.levels.add_xp(10_000)
        game.state_machine.update(1 / 60)
        self.assertIsInstance(game.state_machine.current, LevelUpState)
        key(pygame.K_1)
        self.assertIsInstance(game.state_machine.current, PlayingState)
        applied = (sum(playing.player.upgrade_stacks.values()) > stacks_before
                   or len(playing.player.weapons) > weapons_before)
        self.assertTrue(applied, "level-up choice was not applied")

        # PLAYING -> PAUSED -> PLAYING
        key(pygame.K_ESCAPE)
        self.assertIsInstance(game.state_machine.current, PausedState)
        for _ in range(30):
            game.state_machine.update(1 / 60)
            game._render()
        key(pygame.K_ESCAPE)
        self.assertIsInstance(game.state_machine.current, PlayingState)

        # BOSS: force the boss in, let a few pattern cycles run (telegraphs,
        # bullets, summons), then finish it and confirm VICTORY + reward.
        playing._spawn_boss()
        self.assertIsNotNone(playing.boss)
        for _ in range(360):
            game.state_machine.update(1 / 60)
            game._render()
            # auto-dismiss any level-up screens triggered by the boss fight
            while isinstance(game.state_machine.current, LevelUpState):
                key(pygame.K_1)
        playing.boss.take_damage(10 ** 9)
        game.state_machine.update(1 / 60)
        self.assertIsInstance(game.state_machine.current, VictoryState)
        self.assertGreater(game.state_machine.current.stats["currency"], 0)

        pygame.quit()


if __name__ == "__main__":
    unittest.main()
