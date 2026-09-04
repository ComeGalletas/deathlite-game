"""Headless boot smoke test: the game must initialise, walk MENU -> PLAYING ->
PAUSED -> PLAYING and run frames without raising. Uses SDL's dummy drivers so
it works in CI with no display or audio device.

The run seed is left random on purpose -- booting a different world every time
is most of this test's value -- so nothing here may depend on what the world
looks like. Getting that wrong is what made it flaky: it used to drop its
enemies at five fixed offsets south of the player, and on a height-map world
the player often starts on a summit whose southern rim is a cliff, so four of
the five landed over the drop and never came back to be killed. Measured, that
was four seeds in twenty. `_spots_near_player` asks the map where a body can
actually stand instead.
"""
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
from tests.nearby import spots_near


class SmokeTest(unittest.TestCase):
    def test_boot_and_state_walk(self):
        save_path = os.path.join(tempfile.mkdtemp(), "save.json")
        game = Game(save_path=save_path)
        game.state_machine.change(MenuState(game))

        def key(k):
            game.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=k))

        # MENU -> CHARACTER_SELECT -> LOADING -> PLAYING
        key(pygame.K_RETURN)
        key(pygame.K_RETURN)  # pick the first hero
        from game.states.loading_state import LoadingState
        self.assertIsInstance(game.state_machine.current, LoadingState)
        for _ in range(5000):
            if not isinstance(game.state_machine.current, LoadingState):
                break
            game.state_machine.update(1 / 60)
            game._render()
        playing = game.state_machine.current
        self.assertIsInstance(playing, PlayingState)

        # Seed a few enemies right next to the player so the check does not
        # depend on the director's opening cadence or the hero's weapon range --
        # on ground the map agrees they can stand on and reach the player from,
        # so it does not depend on the shape of the world either.
        spots = spots_near(playing, want=5)
        self.assertEqual(len(spots), 5,
                         "no room to stand five enemies next to the player")
        for at in spots:
            playing._spawn_enemy("chaser", at=at)

        # advance ~15s: the starting weapon auto-fires, projectiles hit, enemies
        # die. The third kill is usually enough XP to level up, which pushes an
        # overlay that stops the world until it is answered -- so this loop has
        # to dismiss them exactly as the boss loop below does. Not doing so was
        # the other half of the flake: whether the level-up landed before or
        # after the fifth kill was a race, and when it landed first the state
        # machine sat in `LevelUpState` for the remaining fourteen seconds and
        # the count stopped where it was.
        for _ in range(900):
            game.state_machine.update(1 / 60)
            game._render()
            while isinstance(game.state_machine.current, LevelUpState):
                key(pygame.K_1)

        # (enemies may all be dead again -- a strong starting weapon keeps the
        # field clear; kills / damage are the meaningful signals.)
        self.assertGreater(playing.stats["damage_dealt"], 0, "weapon dealt no damage")
        self.assertGreaterEqual(playing.stats["kills"], 5, "nothing was killed")

        # PROGRESSION: force another level-up, confirm the choice overlay appears,
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
