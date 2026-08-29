"""Mixer backend adapter -- decouples the procedural audio layer from *how* the
mixer is brought up on a given platform.

`systems/audio.py` synthesises every cue into a raw 16-bit **mono** buffer at
`SYNTH_RATE` and needs it wrapped in a `pygame.mixer.Sound`. The bring-up path
differs:

* **Desktop SDL** (`DesktopMixer`) -- we own the device. Tear down whatever
  `pygame.init()` opened and re-open it at exactly 22050 Hz / mono / 24 channels
  so buffers play back at the pitch they were rendered at.
* **Browser** (`BrowserMixer`, pygbag / emscripten) -- the WebAudio context is
  fragile: `pygame.mixer.quit()` followed by `init()` after startup routinely
  leaves audio dead. Init **once**, no teardown, accept whatever sample rate and
  channel count the browser hands back, and resample / up-mix each buffer once
  at load time so pitch stays correct.
* **Headless / dummy driver** (`SilentMixer`, tests + CI) -- no device; every
  call is a no-op and `ready` stays False.

`make_mixer_backend()` selects one (override with `force=`). `AudioManager`
talks only to the returned object -- it never calls `pygame.mixer` directly.
"""
from __future__ import annotations

import array
import logging
import sys

import pygame

log = logging.getLogger(__name__)

# The rate systems/audio.py renders every buffer at. A backend whose device
# runs at a different rate resamples to it in `make_sound`.
SYNTH_RATE = 22050


# --------------------------------------------------------------------------
# sample helpers -- pure Python, run once per cue at startup. On the desktop
# fast path (rate == SYNTH_RATE, mono) both are skipped entirely.
def _resample_i16(src: "array.array", src_rate: int, dst_rate: int) -> "array.array":
    if src_rate == dst_rate or len(src) == 0:
        return src
    ratio = dst_rate / src_rate
    n_out = max(1, int(len(src) * ratio))
    out = array.array("h", bytes(2 * n_out))
    last = len(src) - 1
    for i in range(n_out):
        pos = i / ratio
        j = int(pos)
        if j >= last:
            out[i] = src[last]
            continue
        frac = pos - j
        a = src[j]
        b = src[j + 1]
        out[i] = int(a + (b - a) * frac)
    return out


def _interleave(mono: "array.array", channels: int) -> "array.array":
    if channels <= 1:
        return mono
    n = len(mono)
    out = array.array("h", bytes(2 * n * channels))
    for i in range(n):
        s = mono[i]
        base = i * channels
        for c in range(channels):
            out[base + c] = s
    return out


# --------------------------------------------------------------------------
class MixerBackend:
    """Base: the shared buffer -> Sound path. Subclasses implement `prepare`."""

    name = "base"
    rate = SYNTH_RATE
    channels = 1
    ready = False

    def prepare(self) -> bool:
        """Bring the mixer up. Return True and set `ready`/`rate`/`channels` on
        success; return False (and leave `ready` False) on any failure."""
        raise NotImplementedError

    def make_sound(self, mono_i16: "array.array") -> "pygame.mixer.Sound | None":
        if not self.ready:
            return None
        data = _resample_i16(mono_i16, SYNTH_RATE, self.rate)
        data = _interleave(data, self.channels)
        try:
            return pygame.mixer.Sound(buffer=data.tobytes())
        except pygame.error as exc:
            log.warning("Sound() rejected a buffer: %s", exc)
            return None

    def shutdown(self) -> None:
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
        except pygame.error:
            pass
        self.ready = False


class SilentMixer(MixerBackend):
    name = "silent"

    def prepare(self) -> bool:
        self.ready = False
        return False

    def make_sound(self, mono_i16):
        return None


class DesktopMixer(MixerBackend):
    name = "desktop"

    def prepare(self) -> bool:
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
            pygame.mixer.init(frequency=SYNTH_RATE, size=-16, channels=1)
            pygame.mixer.set_num_channels(24)
        except pygame.error as exc:  # no device / dummy driver
            log.warning("desktop mixer unavailable: %s", exc)
            self.ready = False
            return False
        got = pygame.mixer.get_init() or (SYNTH_RATE, -16, 1)
        self.rate, _, self.channels = got
        self.ready = True
        return True


class BrowserMixer(MixerBackend):
    name = "browser"

    def prepare(self) -> bool:
        try:
            # No quit(): re-initialising the WebAudio context is what breaks it.
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=SYNTH_RATE)
            pygame.mixer.set_num_channels(16)
        except pygame.error as exc:
            log.warning("browser mixer unavailable: %s", exc)
            self.ready = False
            return False
        got = pygame.mixer.get_init()
        if not got:
            self.ready = False
            return False
        self.rate, _, self.channels = got
        self.channels = abs(self.channels) or 1
        self.ready = True
        log.info("browser mixer up: %d Hz, %d ch", self.rate, self.channels)
        return True


_BACKENDS = {
    "desktop": DesktopMixer,
    "browser": BrowserMixer,
    "silent": SilentMixer,
}


def make_mixer_backend(force: str | None = None) -> MixerBackend:
    """Pick and prepare a backend. `force` is one of "desktop" / "browser" /
    "silent"; by default the browser backend is used under emscripten and the
    desktop one everywhere else. Any bring-up failure falls back to silent."""
    choice = force or ("browser" if sys.platform == "emscripten" else "desktop")
    backend = _BACKENDS.get(choice, DesktopMixer)()
    if backend.prepare():
        return backend
    if backend.name != "silent":
        log.info("mixer backend %r unavailable -- audio will be silent", choice)
    return SilentMixer()
