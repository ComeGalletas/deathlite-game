"""Milestone 5: procedural audio manager -- builds without assets, degrades to
a no-op when the mixer is unavailable, and never raises from play()."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.events import EventBus, Events
from systems.audio import AudioManager


class AudioManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_constructs_and_play_is_safe(self):
        mgr = AudioManager(EventBus())
        # Either the mixer came up (dummy) or it degraded -- both are fine.
        mgr.play("shoot")
        mgr.play("does_not_exist")
        mgr.play_shoot()  # must not raise regardless

    def test_mute_toggle(self):
        mgr = AudioManager(EventBus())
        self.assertFalse(mgr.muted)
        mgr.toggle_mute()
        self.assertTrue(mgr.muted)
        mgr.play("shoot")  # muted path, still safe

    def test_library_has_every_cue_when_enabled(self):
        mgr = AudioManager(EventBus())
        if not mgr.enabled:
            self.skipTest("mixer unavailable in this environment")
        for cue in ("shoot", "hit", "enemy_death", "xp", "level_up",
                    "player_hurt", "boss_spawn", "boss_death"):
            self.assertIn(cue, mgr._sounds)

    def test_subscribes_to_event_bus(self):
        bus = EventBus()
        mgr = AudioManager(bus)
        if not mgr.enabled:
            self.skipTest("mixer unavailable in this environment")
        # publishing known events must not raise
        bus.publish(Events.ENEMY_KILLED, pos=None, color=(0, 0, 0), xp=1, tags=())
        bus.publish(Events.BOSS_SPAWNED, name="x")


if __name__ == "__main__":
    unittest.main()
