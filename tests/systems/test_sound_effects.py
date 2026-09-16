"""The recorded cues and the footstep cadence
(`documentation/journals/sound_effects_journal.md`, 2026-09-16).

The cue *files* are checked on disk, which works headless; the loading and
mixing path needs a real device and is skipped under the dummy driver, in the
style of `test_audio.py`.
"""
import array
import contextlib
import os
import unittest
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import ASSETS_DIR
from game.events import EventBus, Events
from systems.audio import AudioManager, _Footsteps


def _wav(rel):
    with contextlib.closing(wave.open(str(ASSETS_DIR / rel))) as w:
        ch, fr, n = w.getnchannels(), w.getframerate(), w.getnframes()
        a = array.array("h")
        a.frombytes(w.readframes(n))
    return a, ch, fr, n


class CueFileTests(unittest.TestCase):
    """What the cut script guarantees, pinned so a re-cut that regresses one
    of these is caught rather than shipped."""

    def test_every_declared_effect_exists(self):
        self.assertTrue(config.SOUND_EFFECTS)
        for name, rel in config.SOUND_EFFECTS.items():
            self.assertTrue((ASSETS_DIR / rel).exists(), f"{name}: {rel}")

    def test_every_cue_is_at_the_device_rate_so_nothing_is_converted(self):
        for name, rel in config.SOUND_EFFECTS.items():
            _, _, fr, _ = _wav(rel)
            self.assertEqual(fr, 44100, name)

    def test_no_cue_opens_with_silence(self):
        """Silence at the head of a cue is latency: `Sound.play()` starts at
        frame 0, so the player hears it as lag. Every cue must be past a
        tenth of its own peak within 60 ms."""
        for name, rel in config.SOUND_EFFECTS.items():
            a, ch, fr, n = _wav(rel)
            peak = max(abs(v) for v in a)
            limit = int(fr * 0.060)
            reached = next(
                (i for i in range(min(n, limit))
                 if max(abs(a[i * ch + c]) for c in range(ch)) > peak * 0.1),
                None)
            self.assertIsNotNone(reached, f"{name}: still near-silent at 60 ms")

    def test_no_cue_ends_loud(self):
        """The tail must be faded, or the cut clicks."""
        for name, rel in config.SOUND_EFFECTS.items():
            a, ch, fr, n = _wav(rel)
            peak = max(abs(v) for v in a)
            tail = max(abs(a[i * ch + c])
                       for i in range(max(0, n - int(fr * 0.005)), n)
                       for c in range(ch))
            self.assertLess(tail, peak * 0.05, name)

    def test_cues_are_short_enough_to_be_cues(self):
        for name, rel in config.SOUND_EFFECTS.items():
            _, _, fr, n = _wav(rel)
            self.assertLess(n / fr, 3.0, f"{name} is {n / fr:.1f}s")

    def test_the_sources_are_kept_beside_the_cues(self):
        """The cut script reads from here, and the CC BY 4.0 credit points at
        these filenames for the author and the Freesound id."""
        src = ASSETS_DIR / "sound_effects" / "unused"
        self.assertTrue(src.is_dir())
        self.assertEqual(len(list(src.glob("*.wav"))), 3)


class FootstepCadenceTests(unittest.TestCase):
    """A step every stride of ground covered, alternating takes."""

    def _steps(self, speed, seconds=10.0, dt=1 / 60):
        f = _Footsteps()
        out, t = [], 0.0
        for _ in range(int(seconds / dt)):
            cue = f.tick(dt, True, speed)
            t += dt
            if cue:
                out.append((t, cue))
        return out

    def test_standing_still_is_silent(self):
        f = _Footsteps()
        for _ in range(600):
            self.assertIsNone(f.tick(1 / 60, False, 150.0))

    def test_zero_speed_is_silent(self):
        f = _Footsteps()
        for _ in range(600):
            self.assertIsNone(f.tick(1 / 60, True, 0.0))

    def test_the_two_takes_alternate(self):
        cues = [c for _, c in self._steps(150.0)]
        self.assertGreater(len(cues), 4)
        for a, b in zip(cues, cues[1:]):
            self.assertNotEqual(a, b)

    def test_a_faster_hero_steps_more_often(self):
        slow = self._steps(140.0)
        fast = self._steps(300.0)
        self.assertGreater(len(fast), len(slow))

    def test_the_interval_is_bounded_at_both_ends(self):
        for speed in (10.0, 60.0, 150.0, 400.0, 5000.0):
            steps = self._steps(speed, seconds=20.0)
            if len(steps) < 3:
                continue
            gaps = [b[0] - a[0] for a, b in zip(steps, steps[1:])]
            lo, hi = config.FOOTSTEP_INTERVAL_MIN_S, config.FOOTSTEP_INTERVAL_MAX_S
            self.assertGreaterEqual(min(gaps), lo - 0.02, speed)
            self.assertLessEqual(max(gaps), hi + 0.02, speed)

    def test_the_step_count_follows_distance_not_frame_rate(self):
        """The remainder carries across frames, so the same walk produces the
        same steps whether it ran at 60 fps or at the `MAX_DT` floor. (A
        single frame can never owe more than one step: the interval floor is
        0.16 s and `MAX_DT` is 0.05 s.)"""
        smooth = self._steps(150.0, seconds=20.0, dt=1 / 60)
        janky = self._steps(150.0, seconds=20.0, dt=config.MAX_DT)
        self.assertGreater(len(smooth), 10)
        self.assertLessEqual(abs(len(smooth) - len(janky)), 1)

    def test_the_stride_is_a_distance_so_the_count_scales_with_speed(self):
        """Twice the speed over the same time is twice the ground, so twice
        the steps -- as long as neither end hits the interval clamp."""
        slow = self._steps(150.0, seconds=20.0)
        fast = self._steps(300.0, seconds=20.0)
        self.assertAlmostEqual(len(fast) / len(slow), 2.0, delta=0.15)

    def test_stopping_resets_the_stride(self):
        f = _Footsteps()
        f.tick(0.1, True, 150.0)
        f.tick(0.1, False, 0.0)
        self.assertEqual(f._travelled, 0.0)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.mgr = AudioManager(EventBus())
        if not self.mgr.enabled:
            self.skipTest("mixer unavailable in this environment")

    def test_recorded_cues_are_in_the_library(self):
        for name in config.SOUND_EFFECTS:
            self.assertIn(name, self.mgr._sounds, name)

    def test_the_growl_replaced_the_synthesised_boss_sweep(self):
        """`boss_spawn` is declared in SOUND_EFFECTS, so the file must win
        over the synth buffer of the same name."""
        self.assertIn("boss_spawn", config.SOUND_EFFECTS)
        self.assertGreater(self.mgr._sounds["boss_spawn"].get_length(), 2.0)

    def test_the_synth_cues_still_exist_alongside(self):
        for name in ("shoot", "hit", "enemy_death", "xp", "level_up",
                     "player_hurt", "boss_death"):
            self.assertIn(name, self.mgr._sounds, name)

    def test_play_with_a_gain_is_safe(self):
        self.mgr.play("boss_spawn", gain=0.45)
        self.mgr.play("footstep_hard", gain=0.3)
        self.mgr.play("nope", gain=0.5)

    def test_tick_footsteps_never_raises(self):
        for moving in (True, False):
            for _ in range(120):
                self.mgr.tick_footsteps(1 / 60, moving, 150.0)


class RoomGrowlTests(unittest.TestCase):
    """ROOM_ACTIVATED plays the growl quietly, but only for a room that has
    actually just woken, and not more often than the configured floor."""

    def setUp(self):
        pygame.init()
        self.bus = EventBus()
        self.mgr = AudioManager(self.bus)
        self.played = []
        self.mgr.play = lambda name, gain=1.0: self.played.append((name, gain))

    def test_a_room_seeded_on_first_entry_growls(self):
        """The common case, and the one a `woke`-only gate got wrong:
        `SpawnMaster` reports a first visit as `woke=0, seeded=N`, because
        nothing was hibernating there yet."""
        self.mgr._on_room_activated(room=3, woke=0, seeded=7)
        self.assertEqual(self.played, [("boss_spawn", config.GROWL_ROOM_GAIN)])

    def test_a_revisited_room_waking_its_residents_growls(self):
        self.mgr._on_room_activated(room=3, woke=5, seeded=0)
        self.assertEqual(self.played, [("boss_spawn", config.GROWL_ROOM_GAIN)])

    def test_the_room_growl_is_quieter_than_the_boss_growl(self):
        self.assertLess(config.GROWL_ROOM_GAIN, 1.0)

    def test_an_empty_room_is_silent(self):
        self.mgr._on_room_activated(room=3, woke=0, seeded=0)
        self.assertEqual(self.played, [])

    def test_a_second_room_inside_the_gap_is_skipped(self):
        self.mgr._on_room_activated(room=1, woke=0, seeded=4)
        self.mgr._on_room_activated(room=2, woke=0, seeded=4)
        self.assertEqual(len(self.played), 1)

    def test_the_bus_is_wired(self):
        if not self.mgr.enabled:
            self.skipTest("mixer unavailable in this environment")
        self.bus.publish(Events.ROOM_ACTIVATED, room=1, woke=0, seeded=2)
        self.assertEqual(len(self.played), 1)


if __name__ == "__main__":
    unittest.main()
