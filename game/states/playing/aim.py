"""Manual aim input for PLAYING (CB-5).

Turns one frame's key state and mouse into an `AimInput`, the single record
the combat phase reads to decide *where* the hero attacks and *whether* a
manual attack is wanted. Nothing else in the game touches the mouse.

Priority ladder (`documentation/journals/combat_balance_journal.md`, CB-5):

  1. left click (held, or a queued tap)  -> aim at the cursor, source "mouse"
  2. any held aim key                    -> that direction,   source "keys"
  3. neither                             -> `AimInput.none()`; the weapons fall
                                            back to auto-aim (if enabled)

A tap is one attack: `PlayingState` queues it on `MOUSEBUTTONDOWN` and the
combat phase consumes it on the frame a directional weapon fires from it, so
a tap landing mid-cooldown still produces exactly one attack. A held click or
key reports `held=True` and keeps attacking at the weapon's cooldown.

`armed=False` makes a held button count as nothing: `PlayingState` disarms
the mouse whenever an overlay (pause, level-up, dev menu) covers the run and
re-arms it on the first frame with no button held, so the click that closed
the overlay can never come through as an attack (menus pick on release, but
this is the belt to that braces).
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from entities.player import input_vector

MOUSE_LEFT = 0        # index into `pygame.mouse.get_pressed()`


@dataclass(frozen=True)
class AimInput:
    direction: pygame.Vector2 | None   # unit vector, world space; None = no aim
    source: str | None                 # "mouse" | "keys" | None
    held: bool = False                 # keep attacking while this input lasts
    tap: bool = False                  # one queued click-attack is pending

    @property
    def active(self) -> bool:
        return self.direction is not None

    @property
    def wants_fire(self) -> bool:
        """A manual attack should go off as soon as the cooldown allows."""
        return self.active and (self.held or self.tap)

    @staticmethod
    def none() -> "AimInput":
        return AimInput(None, None)


def mouse_direction(mouse_pos, camera, origin: pygame.Vector2,
                    fallback: pygame.Vector2) -> pygame.Vector2:
    """Unit vector from the hero to the cursor's world position. A cursor
    sitting on the hero has no direction; `fallback` (the last movement
    direction) stands in so a click there still attacks somewhere."""
    to_cursor = camera.screen_to_world(mouse_pos) - origin
    if to_cursor.length_squared() > 1e-6:
        return to_cursor.normalize()
    if fallback.length_squared() > 1e-6:
        return fallback.normalize()
    return pygame.Vector2(1, 0)


def read_aim(pressed, mouse_buttons, mouse_pos, camera, origin: pygame.Vector2,
             aim_keys: dict, fallback: pygame.Vector2,
             tap_pending: bool = False, armed: bool = True) -> AimInput:
    """Resolve this frame's manual aim.

    `pressed` / `mouse_buttons` / `mouse_pos` are the raw pygame snapshots
    (`key.get_pressed()`, `mouse.get_pressed()`, `mouse.get_pos()`), passed in
    so the function is pure and testable. `aim_keys` is the active layout's
    `"aim"` table (`config.KEY_LAYOUTS[...]["aim"]`).
    """
    click_held = armed and bool(mouse_buttons[MOUSE_LEFT])
    if click_held or tap_pending:
        direction = mouse_direction(mouse_pos, camera, origin, fallback)
        return AimInput(direction, "mouse", held=click_held, tap=tap_pending)

    key_dir = input_vector(pressed, aim_keys)
    if key_dir.length_squared() > 0.0:
        return AimInput(key_dir, "keys", held=True)

    return AimInput.none()
