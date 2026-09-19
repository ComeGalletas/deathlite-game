"""Keyboard keys drawn as pixel-art keycaps (journal: key_icons_journal.md).

The art is the Tiny Swords square button, 64x64, in two frames: **raised**
(`keycap_blue`: bevelled face over a dark skirt) and **pressed**
(`keycap_blue_pressed`: the skirt gone and the face baked 4 px lower). Both
frames share the same 64 px canvas, so a key is drawn at one `topleft` in
either state and only the *label* moves, riding the face -- the owner's
correction of 2026-09-19: "the key label needs to move when the key icon is
not selected". `FACE_Y` holds the measured face centre of each frame.

The letter itself is text: the pack ships no letter glyphs, so the label is
the body face in `config.COLOR_ON_BUTTON` (black on the light cap, as every
button in the game). On screen a cap is `CAP_PX` design pixels -- an exact
x0.5 of the art, so the pixel grid stays clean -- and scales with the
interface through `ui.scale`.

In the run the cap floats over the element it fires
(`game/states/playing/visual/key_marker.py`). Without the art (an empty
`assets/`) the letter alone is drawn in `fallback_colour` where the cap
would be.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import scale

STATES = ("raised", "pressed")

# Face centre, in the 64 px frame, per state: the raised face fills rows
# 7-41, the pressed face rows 11-45 (measured 2026-09-19).
FACE_Y = {"raised": 24, "pressed": 28}
ART_PX = 64             # the frame the art is authored in
CAP_PX = 32             # a cap's design size on screen
LABEL_PX = 18           # the letter's design size at CAP_PX

# colour -> state -> rig. Only blue ships both frames; a neutral grey and a
# gold cap exist in reserve but only in the pressed position.
KEYCAP_SHEETS = {
    "blue": {"raised": "keycap_blue", "pressed": "keycap_blue_pressed"},
}

# What a key's cap says. `pygame.key.name` gives lower-case words; single
# characters are shown upper-case and the long names shortened to what a
# keyboard prints.
_NAMES = {
    "space": "SPACE", "tab": "TAB", "escape": "ESC", "return": "ENTER",
    "left shift": "SHIFT", "right shift": "SHIFT",
    "left ctrl": "CTRL", "right ctrl": "CTRL",
    "left alt": "ALT", "right alt": "ALT", "backspace": "BKSP",
}


def label_for(keycode: int) -> str:
    """The text on the cap of `keycode`."""
    name = pygame.key.name(keycode)
    return _NAMES.get(name, name.upper())


def keycap_sheet(colour: str, state: str) -> str:
    """The rig a cap in this colour and state draws from (raises on a bad
    key -- callers pass constants)."""
    if state not in STATES:
        raise ValueError(f"unknown keycap state {state!r}")
    return KEYCAP_SHEETS[colour][state]


def cap_rect(face_center, size: int = CAP_PX) -> pygame.Rect:
    """The frame a cap occupies when its *raised* face is centred on
    `face_center`. The same rect serves the pressed frame: the press is
    baked into the art."""
    px = scale.px(size)
    k = px / ART_PX
    left = int(face_center[0]) - px // 2
    top = int(face_center[1]) - int(round(FACE_Y["raised"] * k))
    return pygame.Rect(left, top, px, px)


def label_center(face_center, state: str, size: int = CAP_PX) -> tuple[int, int]:
    """Where the letter sits: on the raised face centre in the raised state,
    `FACE_Y` lower in the pressed state -- the label rides the face."""
    if state not in STATES:
        raise ValueError(f"unknown keycap state {state!r}")
    rect = cap_rect(face_center, size)
    k = rect.width / ART_PX
    return (rect.centerx, rect.top + int(round(FACE_Y[state] * k)))


def draw_keycap(surface: pygame.Surface, assets, face_center, label: str, *,
                state: str = "raised", colour: str = "blue", size: int = CAP_PX,
                font: pygame.font.Font | None = None,
                fallback_colour=(240, 240, 245)) -> pygame.Rect:
    """Paint one cap with `label` on its face; returns the cap's frame rect.
    With no art the label alone is drawn in `fallback_colour` at the cap's
    raised face centre."""
    rect = cap_rect(face_center, size)
    art = (assets.image(keycap_sheet(colour, state), size=rect.size)
           if assets is not None else None)
    if font is None:
        font = fonts.body(int(round(LABEL_PX * size / CAP_PX)), bold=True)
    if art is not None:
        surface.blit(art, rect.topleft)
        text = font.render(label, True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=label_center(face_center, state, size)))
    else:
        text = font.render(label, True, fallback_colour)
        surface.blit(text, text.get_rect(center=(rect.centerx, int(face_center[1]))))
    return rect

