"""Sound effects: a synthesised core plus a few recorded cues.

One Options row governs the lot (journal `audio_mixer_journal.md`,
2026-09-16): `self.volume` is the **sound effects** level and covers the
synthesised cues and the recorded clips alike, including the growl, and
`self.master` is the level shared with the music stream.

Most effects are built at startup from sine/square/noise primitives into a raw
16-bit mono buffer and wrapped in a `pygame.mixer.Sound` -- no files, no numpy.
Since 2026-09-16 a handful of cues are instead *recorded*, loaded from
`assets/sound_effects/` as named by `config.SOUND_EFFECTS` (journal
`sound_effects_journal.md`). The two kinds live in one library and `play()`
does not care which a cue is; a recorded name simply overwrites the
synthesised one, which is how the boss growl replaced its saw sweep.

The files are pre-trimmed and pre-normalised at the device's own rate by
`tools/asset_pipeline/cut_sound_effects.py`, so loading them costs nothing and
they sound the instant they are played. A file that is missing or that this
SDL_mixer build cannot decode is skipped with a warning: the cue is then simply
absent and `play()` no-ops, exactly as for a synth buffer the mixer rejected.

Mixer bring-up is delegated to `systems/mixer_backend.py` so the same synth code
runs on desktop SDL and in the browser (pygbag). `AudioManager` subscribes to
the event bus and plays the matching cue. If no mixer backend is available
(e.g. the SDL dummy audio driver in tests) it degrades to a silent no-op --
audio is never load-bearing.
"""
from __future__ import annotations

import array
import logging
import math
import random

import pygame

from game import config
from game.assets import ASSETS_DIR
from game.events import Events
from systems.mixer_backend import SYNTH_RATE, make_mixer_backend

log = logging.getLogger(__name__)

_RATE = SYNTH_RATE
_AMP = 26000  # headroom below the int16 max so mixing does not clip


def _clamp16(v: float) -> int:
    return max(-32768, min(32767, int(v)))


def _render(samples: list[float], backend) -> "pygame.mixer.Sound | None":
    buf = array.array("h", (_clamp16(s) for s in samples))
    return backend.make_sound(buf)


def _osc(freq: float, t: float, shape: str) -> float:
    phase = 2 * math.pi * freq * t
    if shape == "square":
        return 1.0 if math.sin(phase) >= 0 else -1.0
    if shape == "saw":
        return 2.0 * ((freq * t) % 1.0) - 1.0
    return math.sin(phase)


def _tone(freq: float, dur: float, vol: float = 1.0, shape: str = "sine",
          f_end: float | None = None, attack: float = 0.005) -> list[float]:
    n = int(_RATE * dur)
    out = []
    for i in range(n):
        t = i / _RATE
        f = freq if f_end is None else freq + (f_end - freq) * (i / n)
        env = min(1.0, t / attack) * (1.0 - i / n) ** 1.6  # quick attack, decay
        out.append(_osc(f, t, shape) * env * vol * _AMP)
    return out


def _noise(dur: float, vol: float = 1.0, input_rng: random.Random | None = None) -> list[float]:
    rng = input_rng or random
    n = int(_RATE * dur)
    return [(rng.uniform(-1, 1)) * ((1.0 - i / n) ** 2) * vol * _AMP for i in range(n)]


def _mix(*layers: list[float]) -> list[float]:
    length = max(len(l) for l in layers)
    out = [0.0] * length
    for layer in layers:
        for i, s in enumerate(layer):
            out[i] += s
    return out


def _build_library(backend) -> dict[str, "pygame.mixer.Sound"]:
    rng = random.Random(1234)  # deterministic timbres
    cues = {
        "shoot":      _render(_tone(660, 0.09, 0.35, "square", f_end=880), backend),
        "hit":        _render(_tone(200, 0.06, 0.4, "saw", f_end=120), backend),
        "enemy_death": _render(_mix(_tone(150, 0.16, 0.4, "saw", f_end=60),
                                    _noise(0.16, 0.25, rng)), backend),
        "xp":         _render(_tone(880, 0.07, 0.25, "sine", f_end=1320), backend),
        "level_up":   _render(_mix(_tone(523, 0.18, 0.4),
                                   _tone(784, 0.18, 0.3, f_end=880)), backend),
        "player_hurt": _render(_mix(_tone(140, 0.22, 0.5, "square", f_end=90),
                                    _noise(0.12, 0.3, rng)), backend),
        "boss_spawn": _render(_tone(70, 0.7, 0.6, "saw", f_end=45), backend),
        "boss_death": _render(_mix(_tone(110, 0.9, 0.5, "saw", f_end=40),
                                   _noise(0.9, 0.35, rng)), backend),
    }
    return {name: snd for name, snd in cues.items() if snd is not None}


def _load_files(backend) -> dict[str, "pygame.mixer.Sound"]:
    """The recorded cues in `config.SOUND_EFFECTS`. Loaded straight through
    `pygame.mixer.Sound(path)` -- they are already at the device's rate, so
    SDL converts nothing -- and any that will not load are left out."""
    if not backend.ready:
        return {}
    out = {}
    for name, rel in config.SOUND_EFFECTS.items():
        path = ASSETS_DIR / rel
        if not path.exists():
            log.warning("sound effect %r missing: %s", name, path)
            continue
        try:
            out[name] = pygame.mixer.Sound(str(path))
        except pygame.error as exc:
            log.warning("sound effect %r could not load: %s", name, exc)
    return out


class _Footsteps:
    """Hero footstep cadence.

    A step every `config.FOOTSTEP_STRIDE_PX` of ground covered rather than
    every N seconds, so a speed-buffed run steps faster without this having to
    know the hero's base speed. The two grass takes alternate, which reads as
    a gait; playing one sample on repeat does not. Distance is accumulated
    rather than sampled, so a slow frame does not drop a step.
    """

    def __init__(self) -> None:
        self._travelled = 0.0
        self._left = True

    def reset(self) -> None:
        self._travelled = 0.0

    def tick(self, dt: float, moving: bool, speed: float):
        """-> the cue name to play this frame, or None."""
        if not moving or speed <= 0.0 or dt <= 0.0:
            self._travelled = 0.0     # a standing hero starts the next stride fresh
            return None
        stride = float(config.FOOTSTEP_STRIDE_PX)
        # The stride is clamped in *time*, which is what the two bounds mean,
        # so convert them back into a distance for this frame's speed.
        lo = speed * float(config.FOOTSTEP_INTERVAL_MIN_S)
        hi = speed * float(config.FOOTSTEP_INTERVAL_MAX_S)
        stride = max(lo, min(hi, stride))
        self._travelled += speed * dt
        if self._travelled < stride:
            return None
        self._travelled -= stride
        self._left = not self._left
        return "footstep_hard" if self._left else "footstep_soft"


class AudioManager:
    def __init__(self, event_bus) -> None:
        self.enabled = False
        self.muted = False
        # `volume` is the *sound effects* level, one of the mixer's two
        # children; `master` is the level over both it and the music
        # (journal `audio_mixer_journal.md`, 2026-09-16).
        self.volume = float(config.SFX_VOLUME_DEFAULT)
        self.master = float(config.MASTER_VOLUME_DEFAULT)
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._last_play: dict[str, int] = {}
        self._min_gap_ms = {"shoot": 75, "hit": 50, "xp": 45}  # minimum gap between consecutive plays of each sound in milliseconds
        self.footsteps = _Footsteps()
        self._last_growl_ms = -999999

        # Mixer bring-up is platform-specific (desktop vs browser vs headless);
        # the backend owns that decision. A silent backend leaves us disabled.
        self._backend = make_mixer_backend()
        if not self._backend.ready:
            log.warning("audio disabled: no mixer backend")
            return
        self._sounds = _build_library(self._backend)
        # Recorded cues land on top, so a name in both wins here. That is how
        # `boss_spawn` became the growl rather than the synthesised sweep.
        self._sounds.update(_load_files(self._backend))
        self.enabled = bool(self._sounds)
        if not self.enabled:
            log.warning("audio disabled: mixer produced no buffers")
            return

        bus = event_bus
        bus.subscribe(Events.DAMAGE_DEALT, lambda **kw: self.play("hit"))
        bus.subscribe(Events.ENEMY_KILLED, lambda **kw: self.play("enemy_death"))
        bus.subscribe(Events.XP_COLLECTED, lambda **kw: self.play("xp"))
        bus.subscribe(Events.PLAYER_LEVELED, lambda **kw: self.play("level_up"))
        bus.subscribe(Events.PLAYER_DAMAGED, lambda **kw: self.play("player_hurt"))
        bus.subscribe(Events.BOSS_SPAWNED, lambda **kw: self.play("boss_spawn"))
        bus.subscribe(Events.BOSS_KILLED, lambda **kw: self.play("boss_death"))
        # The same growl, quieter, when a room wakes with enemies in it: the
        # area noticing the hero, not one specific monster (owner, 2026-09-16).
        # `woke` is False for a room that was already awake, and a floor
        # between growls keeps a walk across several rooms from chaining them.
        bus.subscribe(Events.ROOM_ACTIVATED, self._on_room_activated)

    @property
    def backend(self):
        """The mixer backend this manager brought up. `MusicPlayer` reads
        `ready` off it -- the device is opened once, by whoever is built
        first, and the music stream shares it with the cues."""
        return self._backend

    def toggle_mute(self) -> None:
        self.muted = not self.muted

    def set_volume(self, v: float) -> None:
        """The sound-effects level, clamped to [0, 1]. `play()` applies it per
        cue, so a bare assignment would work too -- this is the one place the
        clamp and the float tidy-up live."""
        self.volume = round(max(0.0, min(1.0, float(v))), 4)

    def set_master(self, v: float) -> None:
        """The level over the whole mixer, clamped to [0, 1]. `MusicPlayer`
        holds the same number for the stream; `Game` sets both."""
        self.master = round(max(0.0, min(1.0, float(v))), 4)

    def play(self, name: str, gain: float = 1.0) -> None:
        """Play a cue at `master * volume * gain`. `gain` scales one play under
        the two settings -- it is how the room growl sounds quieter than the
        boss growl without a second copy of the same recording, and it keeps
        that balance wherever the player puts the sliders."""
        if not self.enabled or self.muted:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        now = pygame.time.get_ticks()
        gap = self._min_gap_ms.get(name)
        if gap is not None and now - self._last_play.get(name, -9999) < gap:
            return
        self._last_play[name] = now
        level = max(0.0, min(1.0, self.master * self.volume * gain))
        # Set the level on the *channel* rather than the Sound: a Sound's
        # volume is shared by every play of it, so two cues from one recording
        # at different gains would fight over it.
        channel = snd.play()
        if channel is None:
            snd.set_volume(level)     # every channel busy; nothing to adjust
            return
        channel.set_volume(level)

    def _on_room_activated(self, **kw) -> None:
        # The growl announces a *populated* area coming alive, so both halves
        # of the payload count. They are mutually exclusive in practice:
        # `seeded` is how many residents a room got on first entry, `woke` how
        # many previously hibernated ones were re-queued on a later visit.
        # Gating on `woke` alone would have been backwards -- silent the first
        # time into a room, growling only on the way back through.
        if not (kw.get("woke") or kw.get("seeded")):
            return                    # the room activated empty; nothing to announce
        now = pygame.time.get_ticks()
        if now - self._last_growl_ms < int(config.GROWL_ROOM_MIN_GAP_MS):
            return
        self._last_growl_ms = now
        self.play("boss_spawn", gain=float(config.GROWL_ROOM_GAIN))

    def tick_footsteps(self, dt: float, moving: bool, speed: float) -> None:
        """Called once a frame by the run. Plays a step when the hero has
        covered another stride; silent while standing still."""
        cue = self.footsteps.tick(dt, moving, speed)
        if cue is not None:
            self.play(cue, gain=float(config.FOOTSTEP_GAIN))

    def play_shoot(self) -> None:
        """Called directly by the weapon-fire path (no event for every shot)."""
        self.play("shoot")
