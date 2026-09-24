"""`systems/mixer_backend.py`: the sample helpers, the three backends and
the pick-and-fall-back in `make_mixer_backend`.

Runs headless on SDL's dummy audio driver, which opens a device that plays
nothing, so the desktop and browser bring-ups are exercised for real; a
failed bring-up is simulated by making `pygame.mixer.init` raise.
"""
import array
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from systems import mixer_backend as mb


def _i16(values):
    return array.array("h", values)


class SampleHelperTests(unittest.TestCase):
    def test_resampling_to_the_same_rate_is_the_same_buffer(self):
        src = _i16([1, 2, 3])
        self.assertIs(mb._resample_i16(src, 22050, 22050), src)

    def test_an_empty_buffer_is_left_alone(self):
        src = _i16([])
        self.assertIs(mb._resample_i16(src, 22050, 44100), src)

    def test_doubling_the_rate_interpolates_between_samples(self):
        out = mb._resample_i16(_i16([0, 100, 200]), 22050, 44100)
        self.assertEqual(len(out), 6)
        self.assertEqual(list(out[:5]), [0, 50, 100, 150, 200])
        self.assertEqual(out[5], 200, "the tail holds the last sample")

    def test_halving_the_rate_keeps_every_other_sample(self):
        out = mb._resample_i16(_i16([0, 10, 20, 30]), 44100, 22050)
        self.assertEqual(list(out), [0, 20])

    def test_mono_stays_mono_and_stereo_duplicates_each_sample(self):
        mono = _i16([5, -5])
        self.assertIs(mb._interleave(mono, 1), mono)
        self.assertEqual(list(mb._interleave(mono, 2)), [5, 5, -5, -5])


class BackendTests(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        # Leave a mixer up for whatever runs next, as `pygame.init` would.
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()

    def test_the_base_class_leaves_prepare_to_its_subclasses(self):
        with self.assertRaises(NotImplementedError):
            mb.MixerBackend().prepare()

    def test_silent_never_comes_up_and_makes_no_sound(self):
        s = mb.SilentMixer()
        self.assertFalse(s.prepare())
        self.assertFalse(s.ready)
        self.assertIsNone(s.make_sound(_i16([1, 2, 3])))

    def test_a_backend_that_is_not_ready_makes_no_sound(self):
        d = mb.DesktopMixer()
        self.assertFalse(d.ready)
        self.assertIsNone(d.make_sound(_i16([1, 2, 3])))

    def test_desktop_opens_the_device_at_its_own_rate_and_makes_sounds(self):
        d = mb.DesktopMixer()
        self.assertTrue(d.prepare())
        self.assertTrue(d.ready)
        self.assertEqual((d.rate, d.channels), pygame.mixer.get_init()[::2])
        snd = d.make_sound(_i16([0, 1000, -1000, 0] * 50))
        self.assertIsInstance(snd, pygame.mixer.Sound)

    def test_desktop_falls_silent_when_the_device_will_not_open(self):
        d = mb.DesktopMixer()
        with mock.patch.object(pygame.mixer, "init", side_effect=pygame.error("no device")):
            self.assertFalse(d.prepare())
        self.assertFalse(d.ready)

    def test_browser_keeps_a_mixer_that_is_already_up(self):
        pygame.mixer.init()
        before = pygame.mixer.get_init()
        b = mb.BrowserMixer()
        with mock.patch.object(pygame.mixer, "quit") as quit_:
            self.assertTrue(b.prepare())
        quit_.assert_not_called()                  # no teardown: WebAudio dies on it
        self.assertEqual(pygame.mixer.get_init(), before)
        self.assertEqual(b.rate, before[0])
        self.assertGreaterEqual(b.channels, 1)

    def test_browser_brings_the_mixer_up_when_nothing_has(self):
        pygame.mixer.quit()
        b = mb.BrowserMixer()
        self.assertTrue(b.prepare())
        self.assertIsNotNone(pygame.mixer.get_init())

    def test_browser_falls_silent_when_init_raises_or_reports_nothing(self):
        pygame.mixer.quit()
        b = mb.BrowserMixer()
        with mock.patch.object(pygame.mixer, "init", side_effect=pygame.error("no ctx")):
            self.assertFalse(b.prepare())
        self.assertFalse(b.ready)
        with mock.patch.object(pygame.mixer, "init"), \
                mock.patch.object(pygame.mixer, "set_num_channels"), \
                mock.patch.object(pygame.mixer, "get_init", return_value=None):
            self.assertFalse(b.prepare())
        self.assertFalse(b.ready)

    def test_a_rejected_buffer_makes_no_sound(self):
        d = mb.DesktopMixer()
        self.assertTrue(d.prepare())
        with mock.patch.object(pygame.mixer, "Sound", side_effect=pygame.error("bad")):
            self.assertIsNone(d.make_sound(_i16([1, 2, 3])))

    def test_shutdown_closes_the_mixer_and_is_safe_twice(self):
        d = mb.DesktopMixer()
        self.assertTrue(d.prepare())
        d.shutdown()
        self.assertFalse(d.ready)
        self.assertIsNone(pygame.mixer.get_init())
        d.shutdown()                                # nothing open: still fine


class PickTests(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()

    def test_forced_silent_is_silent(self):
        self.assertIsInstance(mb.make_mixer_backend("silent"), mb.SilentMixer)

    def test_the_desktop_is_the_default_off_the_browser(self):
        got = mb.make_mixer_backend()
        self.assertIsInstance(got, mb.DesktopMixer)
        self.assertTrue(got.ready)

    def test_emscripten_picks_the_browser_backend(self):
        with mock.patch.object(mb.sys, "platform", "emscripten"):
            self.assertIsInstance(mb.make_mixer_backend(), mb.BrowserMixer)

    def test_an_unknown_name_falls_back_to_the_desktop(self):
        self.assertIsInstance(mb.make_mixer_backend("jukebox"), mb.DesktopMixer)

    def test_a_failed_bring_up_falls_back_to_silent(self):
        with mock.patch.object(pygame.mixer, "init", side_effect=pygame.error("no device")):
            self.assertIsInstance(mb.make_mixer_backend("desktop"), mb.SilentMixer)


if __name__ == "__main__":
    unittest.main()
