"""Keyboard keys drawn as pixel-art keycaps (journal: key_icons_journal.md).

The art is the Tiny Swords square button, 64x64, in two frames: **raised**
(`keycap_blue`: bevelled face over a dark skirt) and **pressed**
(`keycap_blue_pressed`: the skirt gone and the face baked 4 px lower). Both
frames share the same 64 px canvas, so a key is drawn at one `topleft` in
either state and only the *label* moves, riding the face -- the owner's
correction of 2026-09-19: "the key label needs to move when the key icon is
not selected". `KEYCAPS` holds, per colour and state, the rig and the
measured face centre.

Two colours: **blue** for the key the player is being asked to press (it
has both frames, so it can show the press), and **grey** for reference
listings such as the pause menu's Controls block -- the grey sheet only
exists in the down position, so both of its states are the same frame at
the pressed face height. A **wide** cap (the 192x64 sheets, drawn at 3:1)
carries a word: `TAB`, `ESC`, `CLICK`.

The letter itself is text: the pack ships no letter glyphs, so the label is
the body face in `config.COLOR_ON_BUTTON` (black on the light cap, as every
button in the game); the four arrows are drawn -- neither bundled face has
arrow glyphs, and a missing glyph renders as a box. On
screen a cap is `CAP_PX` design pixels -- an exact x0.5 of the art, so the
pixel grid stays clean -- and scales with the interface through `ui.scale`.

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
COLOURS = ("blue", "grey")

# Face centre, in the 64 px frame, per state, for the blue cap: the raised
# face fills rows 7-41, the pressed face rows 11-45 (measured 2026-09-19).
# The grey cap and every wide sheet's pressed / down frame measure the same.
FACE_Y = {"raised": 24, "pressed": 28}
ART_PX = 64             # the frame the art is authored in
WIDE_RATIO = 3          # a wide sheet is three frames across
CAP_PX = 32             # a cap's design size on screen
LABEL_PX = 18           # the letter's design size at CAP_PX
WORD_PX = 15            # a wide cap's word, a touch smaller than a letter
ARROW_PX = 12           # a drawn arrow's span at CAP_PX

# colour -> state -> (square rig, wide rig, face centre in the 64 px frame).
KEYCAPS = {
    "blue": {"raised":  ("keycap_blue", "keycap_blue_wide", FACE_Y["raised"]),
             "pressed": ("keycap_blue_pressed", "keycap_blue_wide_pressed", FACE_Y["pressed"])},
    "grey": {"raised":  ("keycap_grey", "keycap_grey_wide", FACE_Y["pressed"]),
             "pressed": ("keycap_grey", "keycap_grey_wide", FACE_Y["pressed"])},
}

# What a key's cap says. `pygame.key.name` gives lower-case words; single
# characters are shown upper-case, the arrows as arrows, and the long names
# shortened to what a keyboard prints.
_NAMES = {
    "space": "SPACE", "tab": "TAB", "escape": "ESC", "return": "ENTER",
    "left shift": "SHIFT", "right shift": "SHIFT",
    "left ctrl": "CTRL", "right ctrl": "CTRL",
    "left alt": "ALT", "right alt": "ALT", "backspace": "BKSP",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
}


ARROWS = {"↑": (0, -1), "↓": (0, 1), "←": (-1, 0), "→": (1, 0)}


def draw_arrow(surface: pygame.Surface, center, direction, size: int, colour) -> None:
    """A pixel arrow of `size` design px pointing along `direction`: a
    filled head with a short shaft, the same weight as the letters."""
    px = scale.px(size)
    cx, cy = int(center[0]), int(center[1])
    dx, dy = direction
    half = px // 2
    head = max(2, px // 2)                    # head length along the arrow
    shaft = max(1, px // 5)                   # shaft half-width
    tip = (cx + dx * half, cy + dy * half)
    base = (cx + dx * (half - head), cy + dy * (half - head))
    # perpendicular
    nx, ny = -dy, dx
    pygame.draw.polygon(surface, colour, [
        tip, (base[0] + nx * half, base[1] + ny * half),
        (base[0] - nx * half, base[1] - ny * half)])
    tail = (cx - dx * half, cy - dy * half)
    pygame.draw.polygon(surface, colour, [
        (base[0] + nx * shaft, base[1] + ny * shaft),
        (base[0] - nx * shaft, base[1] - ny * shaft),
        (tail[0] - nx * shaft, tail[1] - ny * shaft),
        (tail[0] + nx * shaft, tail[1] + ny * shaft)])


def label_for(keycode: int) -> str:
    """The text on the cap of `keycode`."""
    name = pygame.key.name(keycode)
    return _NAMES.get(name, name.upper())


def is_wide(label: str) -> bool:
    """A word needs the wide cap; a letter, digit or arrow fits the square."""
    return len(label) > 1


def _spec(colour: str, state: str):
    if state not in STATES:
        raise ValueError(f"unknown keycap state {state!r}")
    if colour not in KEYCAPS:
        raise ValueError(f"unknown keycap colour {colour!r}")
    return KEYCAPS[colour][state]


def keycap_sheet(colour: str, state: str, *, wide: bool = False) -> str:
    """The rig a cap in this colour and state draws from (raises on a bad
    key -- callers pass constants)."""
    square, wide_rig, _face = _spec(colour, state)
    return wide_rig if wide else square


def face_y(colour: str, state: str) -> int:
    """The face centre, in the 64 px frame, of this colour in this state."""
    return _spec(colour, state)[2]


def cap_rect(face_center, size: int = CAP_PX, *, colour: str = "blue",
             wide: bool = False) -> pygame.Rect:
    """The frame a cap occupies when its *raised* face is centred on
    `face_center`. The same rect serves the pressed frame: the press is
    baked into the art."""
    px = scale.px(size)
    k = px / ART_PX
    w = px * WIDE_RATIO if wide else px
    left = int(face_center[0]) - w // 2
    top = int(face_center[1]) - int(round(face_y(colour, "raised") * k))
    return pygame.Rect(left, top, w, px)


def label_center(face_center, state: str, size: int = CAP_PX, *,
                 colour: str = "blue", wide: bool = False) -> tuple[int, int]:
    """Where the letter sits: on the raised face centre in the raised state,
    lower in the pressed state -- the label rides the face."""
    rect = cap_rect(face_center, size, colour=colour, wide=wide)
    k = rect.height / ART_PX
    return (rect.centerx, rect.top + int(round(face_y(colour, state) * k)))


def draw_keycap(surface: pygame.Surface, assets, face_center, label: str, *,
                state: str = "raised", colour: str = "blue", size: int = CAP_PX,
                wide: bool | None = None, font: pygame.font.Font | None = None,
                fallback_colour=(240, 240, 245)) -> pygame.Rect:
    """Paint one cap with `label` on its face; returns the cap's frame rect.
    `wide` defaults to whatever the label needs. With no art the label
    alone is drawn in `fallback_colour` at the cap's raised face centre."""
    if wide is None:
        wide = is_wide(label)
    rect = cap_rect(face_center, size, colour=colour, wide=wide)
    art = (assets.image(keycap_sheet(colour, state, wide=wide), size=rect.size)
           if assets is not None else None)
    if font is None:
        px = (WORD_PX if wide else LABEL_PX) * size / CAP_PX
        font = fonts.body(int(round(px)), bold=True)
    if art is not None:
        surface.blit(art, rect.topleft)
        ink, at = config.COLOR_ON_BUTTON, label_center(face_center, state, size,
                                                       colour=colour, wide=wide)
    else:
        ink, at = fallback_colour, (rect.centerx, int(face_center[1]))
    if label in ARROWS:
        draw_arrow(surface, at, ARROWS[label], int(round(ARROW_PX * size / CAP_PX)), ink)
    else:
        text = font.render(label, True, ink)
        surface.blit(text, text.get_rect(center=at))
    return rect
