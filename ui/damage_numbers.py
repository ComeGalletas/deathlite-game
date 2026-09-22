"""Floating damage numbers (spec 3.6). Pooled and capped.

Numbers rise and fade. Crits render larger and in the accent colour; damage the
hero *takes* renders red and 25% larger than the common number, so the player
reads build spikes -- and their own health draining -- at a glance.

CB-8: a healing number (a collected health potion) renders green with a `+`,
at the incoming size, so a heal is as loud as a hit.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from systems.object_pool import Pool

_BASE_PT = 16
_CRIT_PT = 22
_IN_PT = round(_BASE_PT * 1.25)       # incoming damage: 25% bigger than common
_HEAL_COLOR = (120, 230, 140)         # CB-8: a collected health potion

# A number drawn in a caller's own colour (M11: elemental damage) is lifted
# toward white and outlined in near-black before it is drawn.
#
# Both are needed and for opposite reasons. Thunder is `(108, 74, 163)`, a
# dark violet, and Wind is `(170, 255, 190)`, a pale green over a green
# meadow: one is too dark to read against the world and the other too pale.
# Lifting fixes the dark end, the outline fixes the pale end, and together
# they let the hue carry *meaning* while the outline carries *contrast* --
# the same bargain the aura tint makes.
_OWN_LIFT = 0.35                      # toward white
_OWN_OUTLINE = (18, 16, 24)
_OUTLINE_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))
# A label's edge goes round all eight, so the second colour reads as a
# ring rather than as a cross.
_LABEL_OFFSETS = ((-1, -1), (0, -1), (1, -1), (-1, 0),
                  (1, 0), (-1, 1), (0, 1), (1, 1))


def _lift(colour, amount: float):
    return tuple(int(c + (255 - c) * amount) for c in colour)


def _lifted(colour):
    return _lift(colour, _OWN_LIFT)


# A number marked `low_priority` is refused once the pool is this full, so
# the last slice stays available to the ones that are not.
#
# This exists because of a measurement. Elemental numbers live longer than
# a weapon's (0.9 s against 0.6) and arrive in a stream -- a burn tick per
# burning body per second -- so a large Fire fight can fill the pool on
# its own: the stress harness saturates all 200 slots at high rates, and
# 200 burning enemies would do it in ordinary play. A full pool drops
# whatever asks next, and what asks next might be the *weapon's* number,
# which is the one the player is actually reading. Shortening the
# elemental lifetime would trade away the thing the change was for and
# still not fix the case; reserving does fix it.
_LOW_PRIORITY_FULL = 0.75

# A label (M11 C): a word rather than a number, in the two colours of
# whatever produced it -- a reaction's pair. Fill in the first, outline in
# the second, over the same near-black underneath.
#
# Two colours on one word, and not by splitting it. A reaction name is
# eight or nine characters at this size; colouring each half is mush and
# alternating letters is worse. An outline keeps the word one readable
# shape and still states the pair.
#
# The near-black goes under *both* because the pair is not always a strong
# contrast: Frostburn is orange on blue and reads on its own, but
# Superconduct is ice blue on thunder purple -- adjacent hues, both
# mid-dark -- and without a dark edge under them it is one muddy word.
_LABEL_PT = 15
_LABEL_LIFT = 0.22
_LABEL_RISE = 22.0                    # px/s, slower than a number's 38


class DamageNumber:
    __slots__ = ("active", "pos", "text", "life", "max_life", "crit", "incoming",
                 "healing", "colour", "outline", "rise")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.text = ""
        self.life = 0.0
        self.max_life = 0.6
        self.crit = False
        self.incoming = False
        self.healing = False
        # A colour the caller chose, or None for one of the four the class
        # decides itself (common, crit, incoming, healing). Reset on every
        # `add`, because a pooled object outlives its last use.
        self.colour = None
        # A second colour, which makes this a two-tone *label* rather than
        # a number: the fill is `colour` and the edge is this.
        self.outline = None
        self.rise = 38.0

    def update(self, dt: float) -> None:
        self.pos.y -= self.rise * dt  # drift upward
        self.life -= dt
        if self.life <= 0.0:
            self.active = False


class DamageNumbers:
    def __init__(self, max_numbers: int = config.MAX_DAMAGE_NUMBERS) -> None:
        self._pool: Pool[DamageNumber] = Pool(DamageNumber, max_numbers, prefill=32)
        self._cap = max_numbers
        self._font_cache: dict[int, tuple] = {}   # zoom-key -> (common, crit, incoming)

    def __len__(self) -> int:
        return len(self._pool)

    def _fonts(self, zoom: float = 1.0):
        """The (common, crit, incoming) font trio, sized for the camera zoom so
        world-space numbers scale with everything else. Cached per zoom."""
        key = max(1, round(zoom * 100))
        trio = self._font_cache.get(key)
        if trio is None:
            def f(pt):
                # The zoom already carries the render scale: not the UI seam.
                return fonts.body(max(6, round(pt * zoom)), bold=True, scaled=False)
            trio = (f(_BASE_PT), f(_CRIT_PT), f(_IN_PT))
            self._font_cache[key] = trio
        return trio

    def add(self, pos: pygame.Vector2, amount: float, crit: bool = False,
            incoming: bool = False, healing: bool = False,
            colour=None, life: float | None = None,
            low_priority: bool = False) -> None:
        """`colour` and `life` let a caller own a number's look.

        All three are deliberately generic: this module does not know what
        an element is, the same way it does not know what a weapon is. It
        is handed a colour, a lifetime and a priority, and draws them.

        `low_priority` yields the top slice of the pool -- see
        `_LOW_PRIORITY_FULL`.
        """
        if low_priority and len(self._pool) >= self._cap * _LOW_PRIORITY_FULL:
            return
        n = self._pool.acquire()
        if n is None:
            return
        n.pos.update(pos.x, pos.y - 10)
        whole = int(round(amount))
        n.text = f"+{whole}" if healing else str(whole)
        n.life = n.max_life = 0.6 if life is None else max(0.05, float(life))
        n.crit = crit
        n.incoming = incoming
        n.healing = healing
        n.colour = tuple(colour) if colour is not None else None
        n.outline = None
        n.rise = 38.0

    def add_label(self, pos: pygame.Vector2, text: str, colour, outline,
                  life: float = 0.9, lift: float = 0.0) -> None:
        """A word instead of a number, in two colours.

        Sits higher than a damage number and rises more slowly: the same
        body is usually taking the reaction's damage in the same frame, and
        a word has to be *read* rather than glanced at.
        """
        n = self._pool.acquire()
        if n is None:
            return
        n.pos.update(pos.x, pos.y - 10 - lift)
        n.text = str(text)
        n.life = n.max_life = max(0.05, float(life))
        n.crit = n.incoming = n.healing = False
        n.colour = tuple(colour)
        n.outline = tuple(outline)
        n.rise = _LABEL_RISE

    def update(self, dt: float) -> None:
        for n in self._pool:
            n.update(dt)
        self._pool.sweep()

    def draw(self, surface: pygame.Surface, camera) -> None:
        font, font_crit, font_in = self._fonts(getattr(camera, "zoom", 1.0))
        for n in self._pool:
            frac = max(0.0, min(1.0, n.life / n.max_life))
            if n.healing:
                fnt, colour = font_in, _HEAL_COLOR
            elif n.incoming:
                fnt, colour = font_in, config.COLOR_DAMAGE_IN
            elif n.crit:
                fnt, colour = font_crit, config.COLOR_ACCENT
            else:
                fnt, colour = font, config.COLOR_TEXT
            sx, sy = camera.world_to_screen(n.pos)
            if n.outline is not None:
                glyph = _labelled(self._label_font(getattr(camera, "zoom", 1.0)),
                                  n.text, n.colour, n.outline)
            elif n.colour is not None:
                glyph = _outlined(fnt, n.text, _lifted(n.colour))
            else:
                glyph = fnt.render(n.text, True, colour)
            glyph.set_alpha(int(255 * frac))
            surface.blit(glyph, glyph.get_rect(center=(sx, sy)))

    def _label_font(self, zoom: float = 1.0):
        key = ("label", max(1, round(zoom * 100)))
        font = self._font_cache.get(key)
        if font is None:
            font = fonts.body(max(6, round(_LABEL_PT * zoom)), bold=True,
                              scaled=False)
            self._font_cache[key] = font
        return font

    def clear(self) -> None:
        self._pool.clear()


_OUTLINE_CACHE: dict[tuple, pygame.Surface] = {}
_OUTLINE_CACHE_CAP = 256


def _outlined(font, text: str, colour):
    """`text` in `colour` over a near-black outline.

    Cached on (font, text, colour): the elemental numbers are short strings
    from a small set, they live about a second each, and a burning crowd
    asks for the same few every frame. Five glyph renders per number per
    frame would not be.
    """
    key = (id(font), text, colour)
    hit = _OUTLINE_CACHE.get(key)
    if hit is not None:
        return hit
    body = font.render(text, True, colour)
    edge = font.render(text, True, _OWN_OUTLINE)
    out = pygame.Surface((body.get_width() + 2, body.get_height() + 2),
                         pygame.SRCALPHA)
    for dx, dy in _OUTLINE_OFFSETS:
        out.blit(edge, (1 + dx, 1 + dy))
    out.blit(body, (1, 1))
    if len(_OUTLINE_CACHE) >= _OUTLINE_CACHE_CAP:
        _OUTLINE_CACHE.clear()
    _OUTLINE_CACHE[key] = out
    return out


def _labelled(font, text: str, fill, edge):
    """A word in two colours: `fill` inside, `edge` around it, over the
    same near-black the numbers use.

    Three renders of one glyph, cached like `_outlined` -- there are six
    reaction names and they repeat, so the cache hits almost always.
    """
    key = ("label", id(font), text, fill, edge)
    hit = _OUTLINE_CACHE.get(key)
    if hit is not None:
        return hit
    body = font.render(text, True, _lift(fill, _LABEL_LIFT))
    ring = font.render(text, True, _lift(edge, _LABEL_LIFT))
    dark = font.render(text, True, _OWN_OUTLINE)
    out = pygame.Surface((body.get_width() + 4, body.get_height() + 4),
                         pygame.SRCALPHA)
    # Near-black furthest out, the pair's second colour inside it, the
    # first colour on top. The dark ring is what keeps a close pair -- ice
    # blue on thunder purple -- from reading as one muddy word.
    for dx, dy in _LABEL_OFFSETS:
        out.blit(dark, (2 + dx * 2, 2 + dy * 2))
    for dx, dy in _LABEL_OFFSETS:
        out.blit(ring, (2 + dx, 2 + dy))
    out.blit(body, (2, 2))
    if len(_OUTLINE_CACHE) >= _OUTLINE_CACHE_CAP:
        _OUTLINE_CACHE.clear()
    _OUTLINE_CACHE[key] = out
    return out
