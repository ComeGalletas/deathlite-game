"""Buttons and ribbons drawn from the Tiny Swords UI sheets (journal:
"Buttons and ribbons as real UI art", 2026-09-04).

`draw_button` paints one button at `rect` in one of three **states** --
`normal` (blue), `hover` (gold: the highlighted / selected / keyboard-cursor
look) or `pressed` (the blue sheet drawn 4 px lower with its bevel gone, as
the pack authored it) -- and one of two **shapes**, `wide` (the 192x64
3-slice) or `panel` (the 192x192 9-slice). `variant="danger"` swaps blue
for red (Quit). The label follows the baked press: it sits `PRESSED_DY`
lower in the pressed state.

`draw_ribbon` paints a forked ribbon strip in one of the pack's three
colours with a label on it.

Labels default to `config.COLOR_ON_BUTTON` (black -- the sheets are light)
and sit on the art's *visual* centre: a wide button's ink is 56 px tall in
its 64 px frame with the empty 8 px at the bottom, so a label centred on the
rect reads low; `LABEL_DY` lifts it. The ribbon fills its frame and takes no
lift.

Both fall back to the flat rounded rectangle the screens drew before the art
when a sheet is missing (`ui.panels.slice` returns None), so an empty
`assets/` still plays.
"""
from __future__ import annotations

import pygame

from game import config
from ui import panels

STATES = ("normal", "hover", "pressed")
SHAPES = ("wide", "panel")
VARIANTS = ("primary", "danger")
RIBBON_COLOURS = ("blue", "yellow", "red")

PRESSED_DY = 4          # the pressed sheets sit this much lower
LABEL_DY = -6           # button labels: the 4-px ink offset plus a 2-px optical nudge

# (shape, variant) -> state -> rig. Gold has no pressed art; a pressed hover
# shows the base colour's pressed sheet, which is what the eye expects.
BUTTON_SHEETS = {
    ("wide", "primary"):  {"normal": "btn_blue_wide", "hover": "btn_gold_wide",
                           "pressed": "btn_blue_wide_pressed"},
    ("wide", "danger"):   {"normal": "btn_red_wide", "hover": "btn_gold_wide",
                           "pressed": "btn_red_wide_pressed"},
    ("panel", "primary"): {"normal": "btn_blue_panel", "hover": "btn_gold_panel",
                           "pressed": "btn_blue_panel_pressed"},
}

# The flat fallback, matching what the screens drew before the art.
_FALLBACK_FILL = {"normal": (28, 26, 40), "hover": (48, 44, 74), "pressed": (18, 16, 28)}
_FALLBACK_EDGE = {"normal": None, "hover": None, "pressed": None}


def button_sheet(shape: str, variant: str, state: str) -> str:
    """The rig a button in this state draws from (raises on a bad key --
    every caller passes constants)."""
    return BUTTON_SHEETS[(shape, variant)][state]


def draw_button(surface: pygame.Surface, assets, rect: pygame.Rect, label: str | None,
                *, state: str = "normal", shape: str = "wide",
                variant: str = "primary", font=None,
                text_colour=None, label_dy: int | None = None) -> pygame.Rect | None:
    """Paint a button; returns the label's rect (None with no label) so a
    caller can place more content relative to it. `label_dy` overrides the
    shared `LABEL_DY` lift for one button (the character select's Begin sits
    higher than the rows); the pressed shift is added on top either way."""
    if state not in STATES:
        raise ValueError(f"unknown button state {state!r}")
    rect = pygame.Rect(rect)
    art = (panels.slice(assets, button_sheet(shape, variant, state), rect.size)
           if assets is not None else None)
    if art is not None:
        surface.blit(art, rect.topleft)
    else:
        pygame.draw.rect(surface, _FALLBACK_FILL[state], rect, border_radius=12)
        edge = config.COLOR_ACCENT if state == "hover" else config.COLOR_WORLD_BORDER
        pygame.draw.rect(surface, edge, rect, width=3 if state == "hover" else 2,
                         border_radius=12)
    if label is None or font is None:
        return None
    text = font.render(label, True, text_colour or config.COLOR_ON_BUTTON)
    lift = LABEL_DY if label_dy is None else label_dy
    dy = lift + (PRESSED_DY if state == "pressed" else 0)
    text_rect = text.get_rect(center=(rect.centerx, rect.centery + dy))
    surface.blit(text, text_rect)
    return text_rect


def ribbon_sheet(colour: str) -> str:
    if colour not in RIBBON_COLOURS:
        raise ValueError(f"unknown ribbon colour {colour!r}")
    return f"ribbon_{colour}"


def draw_ribbon(surface: pygame.Surface, assets, rect: pygame.Rect, label: str | None,
                *, colour: str = "blue", font=None,
                text_colour=None) -> pygame.Rect | None:
    """Paint a ribbon strip with `label` centred on it; returns the label
    rect (None with no label)."""
    rect = pygame.Rect(rect)
    art = (panels.slice(assets, ribbon_sheet(colour), rect.size)
           if assets is not None else None)
    if art is not None:
        surface.blit(art, rect.topleft)
    else:
        pygame.draw.rect(surface, (36, 40, 60), rect, border_radius=6)
        pygame.draw.rect(surface, config.COLOR_ACCENT, rect, width=2, border_radius=6)
    if label is None or font is None:
        return None
    text = font.render(label, True, text_colour or config.COLOR_ON_BUTTON)
    text_rect = text.get_rect(center=rect.center)
    surface.blit(text, text_rect)
    return text_rect
