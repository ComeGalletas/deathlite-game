"""The web release has no audio (BLD-004, owner 2026-09-30).

`config.apply_web_profile()` sets `config.AUDIO_ENABLED = False`. The
`AudioManager` then closes the device `pygame.init()` opened, takes the
silent backend by name, builds no cue and loads no file; the `MusicPlayer`
built on that backend is disabled, so no track is ever opened. The desktop
keeps its audio exactly as before. The audio folders are left out of the web
bundle by `dist/web/pygbag.ini`, which the last class reads.

Runs headless on SDL's dummy audio driver, which opens a real device that
plays nothing, so "a device is open" and "no device is open" are both
observable through `pygame.mixer.get_init()`.
"""
import configparser
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import ASSETS_DIR
from game.events import EventBus, Events
from systems import audio as audio_mod
from systems.audio import AudioManager
from systems.music import MusicPlayer
from tests.web_profile import web_profile

REPO = Path(__file__).resolve().parents[2]
PYGBAG_INI = REPO / "dist" / "web" / "pygbag.ini"
AUDIO_SUFFIXES = {".mp3", ".ogg", ".wav", ".flac", ".opus", ".m4a", ".aac"}

# Every event the manager would subscribe a cue to on the desktop.
CUE_EVENTS = (Events.DAMAGE_DEALT, Events.ENEMY_KILLED, Events.XP_COLLECTED,
              Events.PLAYER_LEVELED, Events.PLAYER_DAMAGED,
              Events.BOSS_SPAWNED, Events.BOSS_KILLED, Events.ROOM_ACTIVATED)


def _no_file_loads():
    """Patches that fail the test if any sound or music file is opened."""
    boom = AssertionError("an audio file was loaded with audio off")
    return (mock.patch.object(pygame.mixer, "Sound", side_effect=boom),
            mock.patch.object(pygame.mixer.music, "load", side_effect=boom),
            mock.patch.object(pygame.mixer.music, "play", side_effect=boom))


class AudioSwitchTests(unittest.TestCase):
    def test_the_desktop_has_audio(self):
        self.assertIs(config.AUDIO_ENABLED, True)

    def test_the_web_profile_is_silent(self):
        with web_profile():
            self.assertIs(config.AUDIO_ENABLED, False)

    def test_leaving_the_profile_restores_desktop_audio(self):
        with web_profile():
            pass
        self.assertIs(config.AUDIO_ENABLED, True)


class SilentManagerTests(unittest.TestCase):
    """An `AudioManager` and `MusicPlayer` built under the web profile, the
    way `Game.__init__` builds them: after `pygame.init()`, which opens the
    default device on its own."""

    def setUp(self):
        pygame.init()
        self.assertIsNotNone(pygame.mixer.get_init(),
                             "precondition: pygame.init() opened a device")

    def _silent(self, bus=None):
        bus = bus or EventBus()
        sound, load, play = _no_file_loads()
        with web_profile(), sound, load, play, \
                mock.patch.object(audio_mod, "_build_library") as build, \
                mock.patch.object(audio_mod, "_load_files") as files:
            mgr = AudioManager(bus)
        build.assert_not_called()
        files.assert_not_called()
        return mgr

    def test_no_device_is_left_open(self):
        self._silent()
        self.assertIsNone(pygame.mixer.get_init())

    def test_it_takes_the_silent_backend_and_stays_disabled(self):
        mgr = self._silent()
        self.assertEqual(mgr.backend.name, "silent")
        self.assertFalse(mgr.backend.ready)
        self.assertFalse(mgr.enabled)
        self.assertEqual(mgr._sounds, {})

    def test_no_cue_is_wired_to_the_event_bus(self):
        bus = EventBus()
        self._silent(bus)
        for name in CUE_EVENTS:
            self.assertFalse(bus._subscribers.get(name), name)

    def test_the_silence_is_logged_as_information_not_a_warning(self):
        with self.assertLogs("systems.audio", level="INFO") as logs:
            self._silent()
        self.assertTrue(logs.records)
        for rec in logs.records:
            self.assertEqual(rec.levelname, "INFO", rec.getMessage())

    def test_every_cue_call_is_a_no_op(self):
        mgr = self._silent()
        sound, load, play = _no_file_loads()
        with sound, load, play:
            for name in config.SOUND_EFFECTS:
                mgr.play(name)
            mgr.play("hit")
            mgr.play_shoot()
            mgr.tick_footsteps(1.0, True, 400.0)
            mgr.toggle_mute()
            mgr.toggle_mute()
            mgr.set_volume(0.3)
            mgr.set_master(0.5)
        self.assertIsNone(pygame.mixer.get_init())

    def test_the_music_player_on_it_is_disabled_and_opens_nothing(self):
        mgr = self._silent()
        music = MusicPlayer(mgr.backend)
        self.assertFalse(music.enabled)
        sound, load, play = _no_file_loads()
        with sound, load, play:
            for track in config.MUSIC_TRACKS:
                music.play(track)
                music.update(1.0)
            music.set_volume(0.4)
            music.set_master(0.6)
            music.set_muted(True)
            music.set_ducked(True)
            music.stop()
            music.update(1.0)
        self.assertIsNone(music.current, "stop() still keeps the bookkeeping")
        self.assertIsNone(pygame.mixer.get_init())

    def test_the_desktop_manager_is_unchanged(self):
        """The control: with audio on, the same construction opens the
        device, builds every cue and loads every recorded one."""
        mgr = AudioManager(EventBus())
        self.assertEqual(mgr.backend.name, "desktop")
        self.assertTrue(mgr.enabled)
        self.assertIsNotNone(pygame.mixer.get_init())
        for name in config.SOUND_EFFECTS:
            self.assertIn(name, mgr._sounds)
        self.assertTrue(MusicPlayer(mgr.backend).enabled)


class SilentGameTests(unittest.TestCase):
    """A real `Game` booted under the web profile, the `main.py --web`
    path: the menu asks for its track and the cue events fire, and still
    no device is open and no file is read."""

    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(web_profile())
        from game.game import Game
        for patch in _no_file_loads():
            cls.enterClassContext(patch)
        cls.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        cls.game._start()                           # the menu, which wants "menu"
        for _ in range(3):
            cls.game._step()

    def test_neither_player_is_enabled(self):
        self.assertFalse(self.game.audio.enabled)
        self.assertFalse(self.game.music.enabled)
        self.assertEqual(self.game.audio.backend.name, "silent")

    def test_no_device_is_open(self):
        self.assertIsNone(pygame.mixer.get_init())

    def test_the_menu_track_is_asked_for_but_never_opened(self):
        self.assertEqual(self.game.music.current, "menu")

    def test_cue_events_play_nothing(self):
        for name in CUE_EVENTS:
            self.game.events.publish(name, woke=True)
        self.assertIsNone(pygame.mixer.get_init())


class WebBundleTests(unittest.TestCase):
    """`dist/web/pygbag.ini` keeps every audio file out of the bundle."""

    @classmethod
    def setUpClass(cls):
        ini = configparser.ConfigParser(inline_comment_prefixes=(";",))
        ini.read(PYGBAG_INI, encoding="utf-8")
        cls.ignored = json.loads(ini["DEPENDENCIES"]["ignoreDirs"])

    def _excluded(self, path: Path) -> bool:
        rel = "/" + path.resolve().relative_to(REPO).as_posix()
        return any(rel == d or rel.startswith(d + "/") for d in self.ignored)

    def test_both_audio_folders_are_excluded(self):
        self.assertIn("/assets/music", self.ignored)
        self.assertIn("/assets/sound_effects", self.ignored)

    def test_every_sound_effect_the_game_names_is_excluded(self):
        for name, rel in config.SOUND_EFFECTS.items():
            self.assertTrue(self._excluded(ASSETS_DIR / rel), name)

    def test_every_music_track_the_game_names_is_excluded(self):
        for name, rel in config.MUSIC_TRACKS.items():
            self.assertTrue(self._excluded(ASSETS_DIR / rel), name)

    def test_no_audio_file_anywhere_in_assets_would_ship(self):
        """Wider than the names: a new cue dropped anywhere in `assets/`
        outside an excluded folder fails here before it reaches a build."""
        shipped = [p for p in ASSETS_DIR.rglob("*")
                   if p.suffix.lower() in AUDIO_SUFFIXES and not self._excluded(p)]
        self.assertEqual(shipped, [])

    def test_the_check_sees_the_audio_it_excludes(self):
        """The control for the test above: the walk does find audio files,
        so an empty result means excluded, not unreadable."""
        found = [p for p in ASSETS_DIR.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES]
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
