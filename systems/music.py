"""Streamed background music (journal `documentation/journals/music_journal.md`,
2026-09-16).

Unlike `systems/audio.py`, whose eight cues are synthesised at startup into
`pygame.mixer.Sound` buffers, the two music tracks are *files* and are played
through `pygame.mixer.music`, which streams from disk. That matters: the
tracks decode to roughly 26 MB each at the device rate, so loading them as
`Sound` objects would cost ~50 MB of resident memory for no benefit.
`mixer.music` is also a stream of its own rather than one of the cue
channels, so nothing here competes with the sound effects.

Two properties do the real work:

* **`play()` is idempotent.** Asking for the track that is already playing
  returns immediately. That is what keeps the menu music unbroken as the
  player walks MENU -> CHARACTER SELECT -> OPTIONS -> RANKINGS -> SANCTUARY,
  even though each of those is a separate state that declares `music = "menu"`.
* **Fades are ramped here, not by SDL.** `pygame.mixer.music` has a single
  stream, so a true crossfade is impossible; a switch is a fade of the old
  track down to silence followed by a fade of the new one up. `fadeout()`
  would do the first half but blocks the calling thread, which would hitch
  the frame on every state change, so `update(dt)` walks a gain ramp from the
  main loop instead and nothing ever blocks.

Like the cue player, music is never load-bearing: a silent mixer backend (the
SDL dummy driver used by the tests and CI) makes every method a no-op, and a
missing or unreadable file logs once and leaves the game silent rather than
raising. `current` still tracks what *should* be playing in both cases, so
the state machine's bookkeeping is identical whether or not there is a device.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pygame

from game import config
from game.assets import ASSETS_DIR

log = logging.getLogger(__name__)


def track_path(track_id: str) -> Path | None:
    """Absolute path of `track_id` in `config.MUSIC_TRACKS`, or None if the id
    is not declared. Existence is not checked here -- `play()` reports that."""
    rel = config.MUSIC_TRACKS.get(track_id)
    return None if rel is None else ASSETS_DIR / rel


class MusicPlayer:
    """Owns `pygame.mixer.music`. One instance, built by `Game`."""

    def __init__(self, backend=None) -> None:
        # The cue player brought the mixer up (or failed to). No device means
        # every method below short-circuits, exactly like `AudioManager`.
        self.enabled = bool(backend is not None and getattr(backend, "ready", False))
        self.volume = float(config.MUSIC_VOLUME_DEFAULT)
        # The mixer's master, shared with the cue player (journal
        # `audio_mixer_journal.md`, 2026-09-16): the stream plays at
        # `master * volume`, the duck and the mute on top.
        self.master = float(config.MASTER_VOLUME_DEFAULT)
        self.muted = False
        self.ducked = False

        self._current: str | None = None   # what is loaded and playing
        self._next: str | None = None      # what to start when the fade-out ends
        self._switching = False            # a fade-out toward `_next` is running
        self._gain = 1.0                   # the fade ramp, 0..1
        self._gain_target = 1.0
        self._gain_rate = 0.0              # per second; 0 means "snap"
        self._fade_in_ms = 0               # fade to apply once `_next` starts
        self._failed: set[str] = set()     # ids already reported as unplayable

    # --- what should be playing ------------------------------------------
    @property
    def current(self) -> str | None:
        """The track this player is committed to -- the one being faded *in*
        during a switch, not the one still audible. `play()` compares against
        this, so a repeated request mid-fade is still a no-op."""
        return self._next if self._switching else self._current

    # --- transport --------------------------------------------------------
    def play(self, track_id: str | None, fade_ms: int | None = None) -> None:
        """Loop `track_id` forever. `None` fades out to silence. Asking for the
        current track does nothing, so callers may call this every time they
        are entered without restarting the music."""
        if track_id == self.current:
            return
        if fade_ms is None:
            fade_ms = int(config.MUSIC_FADE_MS)
        if not self.enabled:
            # Keep the bookkeeping honest even with no device, so `current`
            # means the same thing in tests as it does in a real run.
            self._current = track_id
            self._next = None
            self._switching = False
            return
        if fade_ms > 0 and self._busy():
            self._next = track_id
            self._switching = True
            self._fade_in_ms = fade_ms
            self._ramp_to(0.0, fade_ms)
            return
        self._begin(track_id, fade_ms)

    def stop(self, fade_ms: int | None = None) -> None:
        self.play(None, fade_ms)

    def update(self, dt: float) -> None:
        """Advance the fade ramp. Called once a frame by the main loop; cheap
        and a no-op whenever no fade is running."""
        if not self.enabled or self._gain_rate <= 0.0:
            return
        if self._gain < self._gain_target:
            self._gain = min(self._gain_target, self._gain + self._gain_rate * dt)
        else:
            self._gain = max(self._gain_target, self._gain - self._gain_rate * dt)
        self._apply_volume()
        if self._gain != self._gain_target:
            return
        self._gain_rate = 0.0
        self._finish_switch()

    # --- levels -----------------------------------------------------------
    def set_volume(self, v: float) -> None:
        """The music level, clamped to [0, 1]. Independent of the sound-effects
        level in `AudioManager` -- they are the master's two children, and the
        Options screen has a row for each."""
        self.volume = round(max(0.0, min(1.0, float(v))), 4)
        self._apply_volume()

    def set_master(self, v: float) -> None:
        """The level over the whole mixer, clamped to [0, 1]. `AudioManager`
        holds the same number for the cues; `Game` sets both."""
        self.master = round(max(0.0, min(1.0, float(v))), 4)
        self._apply_volume()

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        self._apply_volume()

    def set_ducked(self, ducked: bool) -> None:
        """Dip under an overlay (PAUSED) without touching the stored volume, so
        the Options value survives a pause."""
        self.ducked = bool(ducked)
        self._apply_volume()

    # --- internals --------------------------------------------------------
    def _busy(self) -> bool:
        try:
            return bool(pygame.mixer.music.get_busy())
        except pygame.error:
            return False

    def _finish_switch(self) -> None:
        """The outgoing track has reached silence: bring the pending one in.
        Called both from `update` and from `_ramp_to`, because a ramp that is
        already at its target completes synchronously -- without that second
        path, asking for a new track on the same frame a fade-in began (gain
        still 0) would leave `_switching` set forever and the music dead."""
        if not self._switching:
            return
        nxt, fade_in = self._next, self._fade_in_ms
        self._next, self._switching = None, False
        self._begin(nxt, fade_in)

    def _ramp_to(self, target: float, ms: int) -> None:
        self._gain_target = target
        self._gain_rate = (abs(target - self._gain) / (ms / 1000.0)) if ms > 0 else 0.0
        if self._gain_rate <= 0.0:
            self._gain = target
            self._apply_volume()
            self._finish_switch()

    def _begin(self, track_id: str | None, fade_ms: int) -> None:
        """Load and start `track_id` now (or stop, for None). Any failure ends
        in silence with `_current` still set, so the caller does not retry a
        file that is missing or that this SDL_mixer build cannot decode."""
        self._current = track_id
        self._next, self._switching = None, False
        if track_id is None:
            self._gain, self._gain_rate = 1.0, 0.0
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            return

        path = track_path(track_id)
        if path is None or not path.exists():
            self._report(track_id, "no such track" if path is None else f"missing: {path}")
            return
        try:
            pygame.mixer.music.load(str(path))
            self._gain = 0.0 if fade_ms > 0 else 1.0
            self._apply_volume()
            pygame.mixer.music.play(loops=-1)
        except pygame.error as exc:
            self._report(track_id, str(exc))
            return
        if fade_ms > 0:
            self._ramp_to(1.0, fade_ms)
        else:
            self._gain, self._gain_rate = 1.0, 0.0
            self._apply_volume()

    def _report(self, track_id: str, why: str) -> None:
        if track_id not in self._failed:
            self._failed.add(track_id)
            log.warning("music %r unavailable (%s) -- continuing silent", track_id, why)

    def _apply_volume(self) -> None:
        if not self.enabled:
            return
        level = 0.0 if self.muted else self.master * self.volume * self._gain
        if self.ducked:
            level *= float(config.MUSIC_DUCK)
        try:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, level)))
        except pygame.error:
            pass
