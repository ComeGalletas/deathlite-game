"""The overhead enemy health bar (journal: enemy_health_bar_journal.md).

One bar over any enemy standing below full HP, and nothing over one at full
HP. Its **height is fixed** -- the hex family's fill art is 5 native px tall
and is drawn at x1, so every enemy carries the same 5-px bar -- and its
**length states the enemy's maximum HP**, so a tank reads as a tank before the
first hit lands and the fill inside it reads as the fraction left.

The boss is excluded structurally rather than by a check: `run.boss` is a
separate object and never a member of `run.enemies`, so the enemy draw path
this hangs off never sees it, and it keeps the bottom-centre HUD bar it
already has. The training dummy excludes itself too -- it is `invulnerable`,
so its HP never drops.

Drawn from `WorldRenderer.one_enemy`, which means inside the enemy's own
terrace band: a higher terrace occludes the bar exactly as it occludes the
head the bar sits over.

`ui/bars` builds the bar itself out of the same authored hex art as the HUD,
and returns `None` when that art is missing -- so this keeps the primitive
rectangles as its fallback, the same degrade contract as `ui/hud.py`.
"""
from __future__ import annotations

import math

import pygame

from game import config
from game.states.playing.visual.key_marker import ink_of
from ui import bars, scale
from ui.bars import slices

# The fallback bar's height in native px: the hex fill art's own height, so
# the art and the rectangles that stand in for it are the same bar.
_FLAT_TRACK_H = 5
# The sheet's own trough and red (`#D90F1E`), sampled off the art, so the
# fallback degrades to the same bar rather than to a different one.
_FLAT_EMPTY = (32, 32, 32)
_FLAT_FILL = (217, 15, 30)

_pad_cache: dict[str, int | None] = {}
_lift_cache: dict[str, float | None] = {}


def native_track(max_hp: float) -> int:
    """The bar's track -- its meaningful length -- in native art px.

    Square root of `max_hp`, rounded to even px and clamped; the curve and
    the reasons for it are in `game/config.py` next to the knobs.
    """
    ref_hp = max(1e-6, float(config.ENEMY_HP_BAR_REF_HP))
    raw = config.ENEMY_HP_BAR_REF_WIDTH * math.sqrt(max(0.0, float(max_hp)) / ref_hp)
    even = 2 * round(raw / 2)
    return int(max(config.ENEMY_HP_BAR_MIN_WIDTH,
                   min(config.ENEMY_HP_BAR_MAX_WIDTH, even)))


def _pad(assets) -> int | None:
    """`bars.inset` for the configured housing, memoised: this is asked once
    per visible enemy per frame and is a constant for the whole run."""
    frame = config.ENEMY_HP_BAR_FRAME
    if frame not in _pad_cache:
        _pad_cache[frame] = bars.inset(assets, frame=frame)
    return _pad_cache[frame]


def _art_bar(assets, track: int, fraction: float, art_scale: int):
    """The bar cut from the hex family, or `None` when the art is missing."""
    pad = _pad(assets)
    if pad is None:
        return None
    # Below its own two caps a fill has no body left to draw and `bars.bar`
    # skips it. On the hero's 104-px bar that is the deliberate "no sliver at
    # death"; on a 22-px enemy track the same rule would blank the bar for the
    # last fifth of the enemy's life, which is the fifth worth seeing. So an
    # enemy that is still standing keeps the shortest fill the art can build.
    if fraction > 0.0:
        fraction = max(fraction, sum(slices.caps(assets, config.ENEMY_HP_BAR_FILL)) / track)
    return bars.bar(assets, frame=config.ENEMY_HP_BAR_FRAME,
                    fill=config.ENEMY_HP_BAR_FILL,
                    empty=config.ENEMY_HP_BAR_EMPTY,
                    width=track + pad, fraction=fraction,
                    framed=config.ENEMY_HP_BAR_FRAMED, scale=art_scale)


def _flat(surface, cx: float, bottom: float, width: int, fraction: float,
          art_scale: int) -> None:
    """Trough and fill as two rectangles -- the fallback when the hex sheets
    are missing, so a fight stays readable without them."""
    h = _FLAT_TRACK_H * art_scale
    x, y = round(cx - width / 2), round(bottom - h)
    pygame.draw.rect(surface, _FLAT_EMPTY, (x, y, width, h))
    filled = int(width * max(0.0, min(1.0, fraction)))
    if filled > 0:
        pygame.draw.rect(surface, _FLAT_FILL, (x, y, filled, h))


def rig_lift(assets, rig: str) -> float:
    """How far above its feet anchor a rig's body starts, in the rig's own
    unscaled px -- the height the bar has to clear.

    Measured off the **idle** frame's ink through `key_marker.ink_of`, once
    per rig, for two reasons. The rig's declared box is no good: it is sized
    for the tallest pose the rig ever strikes, so a bear that rears up to
    swing carries 40 px of empty box over its head all the time and its bar
    would float away from it. The *live* frame is no good either: it changes
    under the bar every time the enemy swings, and the bar would bob. One
    fixed frame is both tight and still. `ink_of` skips a thin tip -- a
    raised spear, an antenna -- the same way it does under the interact cap.

    Falls back to the box's own top when the rig has no idle art to measure.
    """
    if rig not in _lift_cache:
        lift = None
        box = assets.scale_for(rig)
        frame = assets.frame(rig, "idle", 0, size=box) if box else None
        if frame is not None:
            ink, _peak = ink_of(frame, ("enemy_hp_bar", rig, box))
            if ink.height:
                lift = assets.anchor(rig)[1] - ink.top
        _lift_cache[rig] = lift
    lift = _lift_cache[rig]
    return assets.anchor(rig)[1] if lift is None else lift


def sprite_top(renderer, e, sy: float, z: float) -> float:
    """Screen y of the top of `e`'s body -- where the bar hangs from. A
    primitive-fallback enemy has no rig, so its collider is its body."""
    rig = getattr(e.anim, "rig", None) if getattr(e, "anim", None) else None
    if rig is None:
        return sy - e.radius * z
    assets = renderer.ps.game.assets
    return sy - rig_lift(assets, rig) * z + renderer.sprite_drop(e.radius)


def draw(surface, renderer, e) -> None:
    """The bar over `e`, or nothing at all when it is at full health."""
    max_hp = float(getattr(e, "max_hp", 0.0))
    hp = float(getattr(e, "hp", 0.0))
    if max_hp <= 0.0 or hp >= max_hp:
        return
    fraction = max(0.0, hp) / max_hp
    run = renderer.run
    z = run.camera.zoom
    sx, sy = run.camera.world_to_screen(e.pos)
    art_scale = scale.int_scale(config.ENEMY_HP_BAR_SCALE)
    track = native_track(max_hp)
    bottom = sprite_top(renderer, e, sy, z) - config.ENEMY_HP_BAR_GAP * art_scale

    bar = _art_bar(renderer.ps.game.assets, track, fraction, art_scale)
    if bar is None:
        _flat(surface, sx, bottom, track * art_scale, fraction, art_scale)
        return
    # The frameless bar keeps the housing's horizontal inset, but it is
    # symmetric, so centring the surface centres the track inside it.
    surface.blit(bar, (round(sx - bar.get_width() / 2),
                       round(bottom - bar.get_height())))


def clear_cache() -> None:
    """Test helper: drop the memoised housing inset and rig lifts."""
    _pad_cache.clear()
    _lift_cache.clear()
