"""Procedural audio manager -- builds without assets, degrades to
a no-op when the mixer is unavailable, and never raises from play()."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.events import EventBus, Events
from systems.audio import AudioManager


class _FakeChannel:
    def __init__(self):
        self.level = None

    def set_volume(self, v):
        self.level = v


class _FakeSound:
    """A cue with no device behind it: `play()` hands back a channel whose
    volume the manager sets, which is the number under test."""

    def __init__(self):
        self.channel = _FakeChannel()

    def play(self):
        return self.channel

    def set_volume(self, v):          # only reached when every channel is busy
        self.channel.level = v


# SDL's dummy audio driver (set above, and by every test module) opens a
# device that plays nothing, so the desktop mixer always comes up under the
# suite. A manager that is not `enabled` here is a broken bring-up, not an
# environment to skip in (TST-004.3.8).
_NO_MIXER = ("the mixer did not come up under SDL_AUDIODRIVER="
             f"{os.environ.get('SDL_AUDIODRIVER')!r}; the dummy driver provides one")


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
        self.assertTrue(mgr.enabled, _NO_MIXER)
        for cue in ("shoot", "hit", "enemy_death", "xp", "level_up",
                    "player_hurt", "boss_spawn", "boss_death"):
            self.assertIn(cue, mgr._sounds)

    def test_subscribes_to_event_bus(self):
        bus = EventBus()
        mgr = AudioManager(bus)
        self.assertTrue(mgr.enabled, _NO_MIXER)
        # publishing known events must not raise
        bus.publish(Events.ENEMY_KILLED, pos=None, color=(0, 0, 0), xp=1, tags=())
        bus.publish(Events.BOSS_SPAWNED, name="x")


class MixerLevelTests(unittest.TestCase):
    """The three-level mixer (journal `audio_mixer_journal.md`, 2026-09-16):
    a cue is heard at `master * sfx * per-cue gain`. Driven through an
    injected cue so the arithmetic is pinned with or without a real device."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.mgr = AudioManager(EventBus())
        self.sound = _FakeSound()
        self.mgr._sounds = {"probe": self.sound}
        self.mgr.enabled = True
        self.mgr.muted = False

    def _level(self, **kw):
        self.mgr._last_play.clear()          # never rate-limit the probe
        self.mgr.play("probe", **kw)
        return self.sound.channel.level

    def test_the_defaults_reproduce_the_level_the_game_shipped_with(self):
        self.assertEqual(self.mgr.master, config.MASTER_VOLUME_DEFAULT)
        self.assertEqual(self.mgr.volume, config.SFX_VOLUME_DEFAULT)
        self.assertAlmostEqual(self._level(), 0.7, places=6)

    def test_the_master_scales_every_cue(self):
        self.mgr.set_master(0.5)
        self.assertAlmostEqual(self._level(), 0.35, places=6)

    def test_the_effects_level_scales_every_cue(self):
        self.mgr.set_volume(0.4)
        self.assertAlmostEqual(self._level(), 0.4, places=6)

    def test_a_per_cue_gain_folds_under_both(self):
        """The footstep's 0.30 and the room growl's 0.45 keep their balance
        wherever the player puts the two sliders."""
        self.mgr.set_master(0.5)
        self.mgr.set_volume(0.8)
        self.assertAlmostEqual(self._level(gain=0.5), 0.2, places=6)

    def test_the_product_is_clamped_to_unit_range(self):
        self.assertEqual(self._level(gain=4.0), 1.0)
        self.mgr.set_master(0.0)
        self.assertEqual(self._level(gain=4.0), 0.0)

    def test_set_master_clamps_and_rounds_like_the_other_levels(self):
        self.mgr.set_master(5.0)
        self.assertEqual(self.mgr.master, 1.0)
        self.mgr.set_master(-2.0)
        self.assertEqual(self.mgr.master, 0.0)
        self.mgr.set_master(1 / 3)
        self.assertEqual(self.mgr.master, round(1 / 3, 4))

    def test_mute_still_wins_over_both_levels(self):
        self.mgr.muted = True
        self.assertIsNone(self._level())


if __name__ == "__main__":
    unittest.main()
