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

from game import config, fonts, locale
from ui import scale
from ui.text import fit_font

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
# shortened to what a keyboard prints. `_NAMES` are the legends the key
# itself carries, the same in every language (UI-014.D16); `_WORDS` are
# words the player reads, locale keys read each time a cap is labelled.
_NAMES = {
    "tab": "TAB", "escape": "ESC", "return": "ENTER",
    "left ctrl": "CTRL", "right ctrl": "CTRL",
    "left alt": "ALT", "right alt": "ALT",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
}
_WORDS = {
    "space": "keys.space", "backspace": "keys.backspace",
    "left shift": "keys.shift", "right shift": "keys.shift",
}


ARROWS = {"↑": (0, -1), "↓": (0, 1), "←": (-1, 0), "→": (1, 0)}
# The mouse: a label the cap draws as the game's own cursor arrow
# (`config.UI_CURSOR_IMAGE`, cropped to its ink) -- there is no mouse art
# in the pack, and the arrow is the thing the player clicks with. Falls
# back to the word when the cursor file is missing.
MOUSE = ""
MOUSE_WORD = "keys.click"  # a locale key: the word when the cursor art is missing
MOUSE_PX = 20           # the cursor glyph's height at CAP_PX
# The share of a wide cap's width its word may fill: the face spans columns
# 16-176 of the 192 px sheet (83 %), less a margin so no letter touches the
# bevel. A translation longer than that steps down in size (UI-014.8).
WORD_ROOM = 0.75
_glyphs: dict[tuple, pygame.Surface | None] = {}


def mouse_glyph(assets, height: int) -> pygame.Surface | None:
    """The cursor arrow at `height` native px (aspect kept), or None."""
    key = (id(assets), height)
    if key not in _glyphs:
        pic = assets.picture(config.UI_CURSOR_IMAGE) if assets is not None else None
        out = None
        if pic is not None:
            ink = pic.get_bounding_rect(min_alpha=8)
            if ink.width and ink.height:
                crop = pic.subsurface(ink)
                w = max(1, round(ink.width * height / ink.height))
                out = pygame.transform.scale(crop, (w, max(1, height)))
        _glyphs[key] = out
    return _glyphs[key]


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
    """The text on the cap of `keycode`, in the current language."""
    name = pygame.key.name(keycode)
    if name in _WORDS:
        return locale.t(_WORDS[name])
    return _NAMES.get(name, name.upper())


def is_wide(label: str) -> bool:
    """A word needs the wide cap; a letter, digit, arrow or the mouse glyph
    fits the square."""
    return len(label) > 1 and label != MOUSE


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


def _face(assets, face_center, state: str, colour: str, size: int, wide: bool,
          fallback_colour):
    """`(rect, art, ink, at)` for one cap: its frame, the art (None when
    missing), and the colour and centre of what goes on its face."""
    rect = cap_rect(face_center, size, colour=colour, wide=wide)
    art = (assets.image(keycap_sheet(colour, state, wide=wide), size=rect.size)
           if assets is not None else None)
    if art is not None:
        at = label_center(face_center, state, size, colour=colour, wide=wide)
        return rect, art, config.COLOR_ON_BUTTON, at
    return rect, None, fallback_colour, (rect.centerx, int(face_center[1]))


def _words(assets, label: str, size: int) -> tuple[str | None, pygame.Surface | None]:
    """`(words, glyph)`: what a cap writes on its face, or None when it
    draws its label instead, and the cursor glyph when that is what it
    draws. An arrow is neither. Without the cursor art the mouse cap
    writes `MOUSE_WORD`."""
    if label in ARROWS:
        return None, None
    if label == MOUSE:
        glyph = mouse_glyph(assets, scale.px(MOUSE_PX * size / CAP_PX))
        return (None, glyph) if glyph is not None else (locale.t(MOUSE_WORD), None)
    return label, None


def _text(words: str, ink, wide: bool, size: int, font, cache, rect) -> pygame.Surface:
    """`words` rendered in the cap's label face: `font` when given, else
    the body face at the cap's size, from `cache` when there is one. A wide
    cap's word longer than `WORD_ROOM` of its width steps down in size
    (UI-014.8: a translation); a caller's own font is theirs."""
    if font is not None:
        return font.render(words, True, ink)
    px = int(round((WORD_PX if wide else LABEL_PX) * size / CAP_PX))
    base = cache.font("body", px, bold=True) if cache is not None else fonts.body(px, bold=True)
    room = int(rect.width * WORD_ROOM)
    if wide and base.size(words)[0] > room:
        return fit_font(fonts.body, px, words, room, bold=True).render(words, True, ink)
    if cache is not None:
        return cache.render("body", px, words, ink, bold=True)
    return base.render(words, True, ink)


def draw_keycap(surface: pygame.Surface, assets, face_center, label: str, *,
                state: str = "raised", colour: str = "blue", size: int = CAP_PX,
                wide: bool | None = None, font: pygame.font.Font | None = None,
                fallback_colour=(240, 240, 245), cache=None) -> pygame.Rect:
    """Paint one cap with `label` on its face; returns the cap's frame rect.
    `wide` defaults to whatever the label needs. With no art the label
    alone is drawn in `fallback_colour` at the cap's raised face centre.
    `footprint` gives everything it paints, which can be wider than the
    frame.

    The label's font is `font` when given, else the body face at the cap's
    size. Anything drawn every frame passes `cache` (a `ui.text_cache.
    TextCache`), which keeps that font and the rendered label; without it
    both are built on each call, which is fine for a menu drawn once
    (RND-008.3). An arrow or the mouse glyph renders no text and builds
    no font."""
    if wide is None:
        wide = is_wide(label)
    rect, art, ink, at = _face(assets, face_center, state, colour, size, wide,
                               fallback_colour)
    if art is not None:
        surface.blit(art, rect.topleft)
    words, glyph = _words(assets, label, size)
    if words is None:
        if glyph is not None:
            surface.blit(glyph, glyph.get_rect(center=at))
        else:
            draw_arrow(surface, at, ARROWS[label], int(round(ARROW_PX * size / CAP_PX)), ink)
        return rect
    text = _text(words, ink, wide, size, font, cache, rect)
    surface.blit(text, text.get_rect(center=at))
    return rect


def footprint(assets, face_center, label: str, *, state: str = "raised",
              colour: str = "blue", size: int = CAP_PX, wide: bool | None = None,
              font: pygame.font.Font | None = None, fallback_colour=(240, 240, 245),
              cache=None) -> pygame.Rect:
    """Everything `draw_keycap` paints for the same arguments: the cap's
    frame, grown to take in its written label where that runs past it.
    It does, for the mouse cap without the cursor art: `MOUSE_WORD` on a
    square cap is wider than the cap (RND-008.3). The arrows and the
    cursor glyph are drawn inside the frame."""
    if wide is None:
        wide = is_wide(label)
    rect, _art, ink, at = _face(assets, face_center, state, colour, size, wide,
                                fallback_colour)
    words, _glyph = _words(assets, label, size)
    if words is None:
        return rect
    return rect.union(_text(words, ink, wide, size, font, cache, rect).get_rect(center=at))
