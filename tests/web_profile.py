"""The browser build's profile inside a test (UI-016).

`config.apply_web_profile()` reassigns module-level constants (the screen
size, the interface scale, the camera zoom, the frame rate, saving, vsync,
resizing, the crowd and the frame pacing). A test that applies it by hand
has to restore every one of them, and a hand-kept list goes stale the day
the profile sets one more: `web_profile()` snapshots every upper-case
`config` value instead, so whatever the profile touches comes back.

    with web_profile():
        screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        ...

Anything built inside that caches a size (a state's fonts, a booted run)
belongs to the web profile and should not be used after the block.

`config_restored()` is the same snapshot without applying anything, for a
test whose code under test applies the profile itself (BLD-003.4:
`spawn_stress --web`).
"""
from __future__ import annotations

from contextlib import contextmanager

from game import config


@contextmanager
def config_restored():
    """Every upper-case `config` value as it was, when the block ends."""
    saved = {k: v for k, v in vars(config).items() if k.isupper()}
    try:
        yield
    finally:
        for k in [k for k in vars(config) if k.isupper() and k not in saved]:
            delattr(config, k)
        for k, v in saved.items():
            setattr(config, k, v)


@contextmanager
def web_profile():
    """`config.apply_web_profile()` for the duration of the block."""
    with config_restored():
        config.apply_web_profile()
        yield
