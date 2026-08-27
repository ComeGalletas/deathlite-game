"""Procedurally synthesised sound effects (spec 15: all content original, no
third-party assets).

Every effect is built at startup from sine/square/noise primitives into a raw
16-bit mono buffer and wrapped in a `pygame.mixer.Sound`. No files, no numpy.

`AudioManager` subscribes to the event bus and plays the matching cue. If the
mixer cannot initialise (e.g. the SDL dummy audio driver in tests) it degrades
to a silent no-op -- audio is never load-bearing.
"""
from __future__ import annotations

import array
import logging
import math
import random

import pygame

from game.events import Events

log = logging.getLogger(__name__)

_RATE = 22050
_AMP = 26000  # headroom below the int16 max so mixing does not clip


def _clamp16(v: float) -> int:
    return max(-32768, min(32767, int(v)))


def _render(samples: list[float]) -> "pygame.mixer.Sound":
    buf = array.array("h", (_clamp16(s) for s in samples))
    return pygame.mixer.Sound(buffer=buf.tobytes())


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


def _build_library() -> dict[str, "pygame.mixer.Sound"]:
    rng = random.Random(1234)  # deterministic timbres
    return {
        "shoot":      _render(_tone(660, 0.09, 0.35, "square", f_end=880)),
        "hit":        _render(_tone(200, 0.06, 0.4, "saw", f_end=120)),
        "enemy_death": _render(_mix(_tone(150, 0.16, 0.4, "saw", f_end=60),
                                    _noise(0.16, 0.25, rng))),
        "xp":         _render(_tone(880, 0.07, 0.25, "sine", f_end=1320)),
        "level_up":   _render(_mix(_tone(523, 0.18, 0.4),
                                   _tone(784, 0.18, 0.3, f_end=880))),
        "player_hurt": _render(_mix(_tone(140, 0.22, 0.5, "square", f_end=90),
                                    _noise(0.12, 0.3, rng))),
        "boss_spawn": _render(_tone(70, 0.7, 0.6, "saw", f_end=45)),
        "boss_death": _render(_mix(_tone(110, 0.9, 0.5, "saw", f_end=40),
                                   _noise(0.9, 0.35, rng))),
    }


class AudioManager:
    def __init__(self, event_bus) -> None:
        self.enabled = False
        self.muted = False
        self.volume = 0.7
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._last_play: dict[str, int] = {}
        self._min_gap_ms = {"shoot": 75, "hit": 50, "xp": 45}  # minimum gap between consecutive plays of each sound in milliseconds

        try:
            # Re-init to our exact format so buffers play at the right pitch
            # (pygame.init() may have opened the mixer at a different rate).
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
            pygame.mixer.init(frequency=_RATE, size=-16, channels=1)
            pygame.mixer.set_num_channels(24)
            self._sounds = _build_library()
            self.enabled = True
        except pygame.error as exc:  # dummy driver / no device
            log.warning("audio disabled: %s", exc)
            return

        bus = event_bus
        bus.subscribe(Events.DAMAGE_DEALT, lambda **kw: self.play("hit"))
        bus.subscribe(Events.ENEMY_KILLED, lambda **kw: self.play("enemy_death"))
        bus.subscribe(Events.XP_COLLECTED, lambda **kw: self.play("xp"))
        bus.subscribe(Events.PLAYER_LEVELED, lambda **kw: self.play("level_up"))
        bus.subscribe(Events.PLAYER_DAMAGED, lambda **kw: self.play("player_hurt"))
        bus.subscribe(Events.BOSS_SPAWNED, lambda **kw: self.play("boss_spawn"))
        bus.subscribe(Events.BOSS_KILLED, lambda **kw: self.play("boss_death"))

    def toggle_mute(self) -> None:
        self.muted = not self.muted

    def set_volume(self, v: float) -> None:
        """Master volume, clamped to [0, 1]. `play()` applies it per cue, so a
        bare assignment would work too -- this is the one place the clamp and
        the float tidy-up live."""
        self.volume = round(max(0.0, min(1.0, float(v))), 4)

    def play(self, name: str) -> None:
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
        snd.set_volume(self.volume)
        snd.play()

    def play_shoot(self) -> None:
        """Called directly by the weapon-fire path (no event for every shot)."""
        self.play("shoot")
