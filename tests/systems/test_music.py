"""The streamed music player and the `State.music` wiring
(`documentation/journals/music_journal.md`, 2026-09-16).

These run under the SDL dummy audio driver, where `MusicPlayer.enabled` is
normally False. That is deliberate: the first thing worth proving is that
music is never load-bearing. The bookkeeping (`current`, the volume value)
is kept even with no device, so the state-machine assertions below hold
either way and do not have to be skipped on a headless machine.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.state import MUSIC_INHERIT, State, StateMachine
from systems.music import MusicPlayer, track_path


class _FakeGame:
    """Just enough of `Game` for `StateMachine` to run: it only ever reads
    `.music` off it in the music path."""

    def __init__(self):
        self.music = MusicPlayer(None)


def _state(machine, music_value):
    s = State(machine.game)
    s.music = music_value
    return s


class TrackDeclarationTests(unittest.TestCase):
    """Every file the config names must actually be on disk, and every state
    must declare something the player can act on."""

    def test_every_declared_track_file_exists(self):
        self.assertTrue(config.MUSIC_TRACKS, "no tracks declared")
        for track_id in config.MUSIC_TRACKS:
            path = track_path(track_id)
            self.assertIsNotNone(path)
            self.assertTrue(path.exists(), f"{track_id}: missing {path}")

    def test_unknown_id_resolves_to_nothing(self):
        self.assertIsNone(track_path("no_such_track"))

    def test_every_state_declares_a_usable_value(self):
        # Imported here so a screen that fails to import is a clear error in
        # this test rather than at module load.
        from game.states.character_select_state import CharacterSelectState
        from game.states.dev_menu_state import DevMenuState
        from game.states.game_over_state import GameOverState
        from game.states.level_up_state import LevelUpState
        from game.states.loading_state import LoadingState
        from game.states.menu_state import MenuState
        from game.states.meta_state import MetaState
        from game.states.options_state import OptionsState
        from game.states.paused_state import PausedState
        from game.states.playing_state import PlayingState
        from game.states.rankings_state import RankingsState
        from game.states.run_status_state import RunStatusState
        from game.states.victory_state import VictoryState

        every = (CharacterSelectState, DevMenuState, GameOverState, LevelUpState,
                 LoadingState, MenuState, MetaState, OptionsState, PausedState,
                 PlayingState, RankingsState, RunStatusState, VictoryState)
        for cls in every:
            value = cls.music
            if value is MUSIC_INHERIT or value is None:
                continue
            self.assertIn(value, config.MUSIC_TRACKS, f"{cls.__name__}: {value!r}")

    def test_the_screens_that_share_the_menu_track_agree(self):
        from game.states.character_select_state import CharacterSelectState
        from game.states.menu_state import MenuState
        from game.states.meta_state import MetaState
        from game.states.options_state import OptionsState
        from game.states.rankings_state import RankingsState
        for cls in (MenuState, CharacterSelectState, OptionsState,
                    RankingsState, MetaState):
            self.assertEqual(cls.music, "menu", cls.__name__)

    def test_the_run_declares_the_gameplay_track_and_the_overlays_inherit(self):
        from game.states.level_up_state import LevelUpState
        from game.states.loading_state import LoadingState
        from game.states.paused_state import PausedState
        from game.states.playing_state import PlayingState
        from game.states.run_status_state import RunStatusState
        self.assertEqual(PlayingState.music, "gameplay")
        # The loading screen inheriting is what carries the menu track through
        # world generation -- see StateMachine._apply_music.
        self.assertIs(LoadingState.music, MUSIC_INHERIT)
        for cls in (PausedState, LevelUpState, RunStatusState):
            self.assertIs(cls.music, MUSIC_INHERIT, cls.__name__)

    def test_both_end_screens_fade_to_silence(self):
        from game.states.game_over_state import GameOverState
        from game.states.victory_state import VictoryState
        self.assertIsNone(GameOverState.music)
        self.assertIsNone(VictoryState.music)


class SilentBackendTests(unittest.TestCase):
    """No device: every call is safe, and `current` still tracks intent."""

    def test_no_backend_disables_but_still_tracks(self):
        p = MusicPlayer(None)
        self.assertFalse(p.enabled)
        p.play("menu")
        self.assertEqual(p.current, "menu")
        p.update(0.016)
        p.set_volume(0.3)
        p.set_muted(True)
        p.set_ducked(True)
        p.stop()
        self.assertIsNone(p.current)

    def test_an_unready_backend_is_treated_as_no_device(self):
        class _NotReady:
            ready = False
        self.assertFalse(MusicPlayer(_NotReady()).enabled)

    def test_a_missing_file_never_raises(self):
        class _Ready:
            ready = True
        p = MusicPlayer(_Ready())
        p.play("no_such_track", fade_ms=0)      # unknown id -> reported, silent
        self.assertEqual(p.current, "no_such_track")


class LevelTests(unittest.TestCase):
    def test_volume_is_clamped(self):
        p = MusicPlayer(None)
        p.set_volume(5.0)
        self.assertEqual(p.volume, 1.0)
        p.set_volume(-2.0)
        self.assertEqual(p.volume, 0.0)

    def test_ducking_leaves_the_stored_volume_alone(self):
        p = MusicPlayer(None)
        p.set_volume(0.8)
        p.set_ducked(True)
        self.assertEqual(p.volume, 0.8)
        p.set_ducked(False)
        self.assertEqual(p.volume, 0.8)

    def test_default_sits_under_the_cue_master(self):
        self.assertLess(config.MUSIC_VOLUME_DEFAULT, 0.7)


class StateMachineMusicTests(unittest.TestCase):
    """`StateMachine` applies the top state's declaration after every stack
    change; `MUSIC_INHERIT` walks further down."""

    def setUp(self):
        self.game = _FakeGame()
        self.machine = StateMachine(self.game)
        self.machine.game = self.game

    def test_pushing_a_declaring_state_sets_the_track(self):
        self.machine.push(_state(self.machine, "menu"))
        self.assertEqual(self.game.music.current, "menu")

    def test_an_inheriting_overlay_leaves_the_track_alone(self):
        self.machine.push(_state(self.machine, "gameplay"))
        self.machine.push(_state(self.machine, MUSIC_INHERIT))
        self.assertEqual(self.game.music.current, "gameplay")

    def test_popping_an_overlay_restores_the_track_below(self):
        self.machine.push(_state(self.machine, "gameplay"))
        self.machine.push(_state(self.machine, "menu"))
        self.assertEqual(self.game.music.current, "menu")
        self.machine.pop()
        self.assertEqual(self.game.music.current, "gameplay")

    def test_none_fades_to_silence(self):
        self.machine.push(_state(self.machine, "gameplay"))
        self.machine.change(_state(self.machine, None))
        self.assertIsNone(self.game.music.current)

    def test_a_stack_of_only_inheriting_states_changes_nothing(self):
        """`change()` clears the stack, so the loading screen -- which
        inherits -- is briefly the only state there. The menu track must
        survive that, which is why "nobody declares" means "leave it"."""
        self.machine.push(_state(self.machine, "menu"))
        self.machine.change(_state(self.machine, MUSIC_INHERIT))
        self.assertEqual(self.game.music.current, "menu")

    def test_sibling_screens_do_not_restart_the_track(self):
        first = _state(self.machine, "menu")
        self.machine.push(first)
        played = []
        real = self.game.music.play
        self.game.music.play = lambda t, *a, **k: (played.append(t), real(t, *a, **k))[1]
        self.machine.change(_state(self.machine, "menu"))
        # play() is still called -- it is idempotent, so the *player* is what
        # refuses to restart, not the machine.
        self.assertEqual(played, ["menu"])
        self.assertEqual(self.game.music.current, "menu")


class _FakeMusic:
    """Stands in for `pygame.mixer.music` so the fade ramp can be driven with
    no audio device. Records what was loaded and what volume was applied."""

    def __init__(self):
        self.loaded = []
        self.volume = 0.0
        self.playing = False

    def get_busy(self):
        return self.playing

    def load(self, path):
        self.loaded.append(path)

    def play(self, loops=0, **kw):
        self.playing = True

    def stop(self):
        self.playing = False

    def set_volume(self, v):
        self.volume = v


class _Ready:
    ready = True


class FadeRampTests(unittest.TestCase):
    """The ramp is walked by `update(dt)` rather than SDL's blocking
    `fadeout()`, so a track switch never hitches the frame."""

    def setUp(self):
        self.fake = _FakeMusic()
        self._real = pygame.mixer.music
        pygame.mixer.music = self.fake
        self.p = MusicPlayer(_Ready())
        self.p.set_volume(1.0)

    def tearDown(self):
        pygame.mixer.music = self._real

    def _run(self, seconds, step=1 / 60):
        for _ in range(int(seconds / step) + 1):
            self.p.update(step)

    def test_update_is_a_noop_when_no_fade_is_running(self):
        p = MusicPlayer(None)
        p.update(0.016)     # must not raise with no device and no ramp
        self.assertEqual(p._gain_rate, 0.0)

    def test_a_switch_mid_fade_is_still_idempotent(self):
        p = MusicPlayer(None)
        p.play("menu")
        p.play("menu")
        self.assertEqual(p.current, "menu")

    def test_a_track_fades_in_from_silence(self):
        self.p.play("menu", fade_ms=600)
        self.assertEqual(len(self.fake.loaded), 1)
        self.assertAlmostEqual(self.fake.volume, 0.0, places=6)
        self._run(0.6)
        self.assertAlmostEqual(self.fake.volume, 1.0, places=6)

    def test_switching_fades_out_then_loads_the_next_track(self):
        self.p.play("menu", fade_ms=600)
        self._run(0.6)
        self.p.play("gameplay", fade_ms=600)
        # Still the old file until the fade-out finishes.
        self.assertEqual(len(self.fake.loaded), 1)
        self.assertEqual(self.p.current, "gameplay")
        self._run(0.6)
        self.assertEqual(len(self.fake.loaded), 2)
        self._run(0.6)
        self.assertAlmostEqual(self.fake.volume, 1.0, places=6)

    def test_switching_on_the_frame_a_fade_in_began_still_starts_the_track(self):
        """Regression: the ramp to zero is already satisfied (gain is 0), so
        it completes synchronously. Before `_finish_switch` was reachable
        from `_ramp_to`, `_switching` stuck and the music went dead."""
        self.p.play("menu", fade_ms=600)        # gain is 0 right now
        self.p.play("gameplay", fade_ms=600)    # ...and we switch immediately
        self.assertEqual(self.p.current, "gameplay")
        self.assertEqual(self.fake.loaded[-1], str(track_path("gameplay")))
        self.assertFalse(self.p._switching)
        self._run(0.6)
        self.assertAlmostEqual(self.fake.volume, 1.0, places=6)
        self.assertTrue(self.fake.playing)

    def test_stopping_fades_out_and_then_stops(self):
        self.p.play("menu", fade_ms=600)
        self._run(0.6)
        self.p.stop(fade_ms=600)
        self.assertTrue(self.fake.playing)
        self._run(0.6)
        self.assertFalse(self.fake.playing)
        self.assertIsNone(self.p.current)

    def test_zero_fade_starts_at_full_level_at_once(self):
        self.p.play("menu", fade_ms=0)
        self.assertAlmostEqual(self.fake.volume, 1.0, places=6)

    def test_muting_mid_fade_silences_without_losing_the_volume(self):
        self.p.play("menu", fade_ms=600)
        self._run(0.3)
        self.p.set_muted(True)
        self.assertEqual(self.fake.volume, 0.0)
        self._run(0.3)
        self.assertEqual(self.fake.volume, 0.0)
        self.p.set_muted(False)
        self.assertAlmostEqual(self.fake.volume, 1.0, places=6)
        self.assertEqual(self.p.volume, 1.0)


if __name__ == "__main__":
    pygame.init()
    unittest.main()
