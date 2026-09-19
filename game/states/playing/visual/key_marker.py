"""The interact keycap floating over the element it fires (journal:
key_icons_journal.md, passes 2 and 3).

One cap at most, over `interactions.nearest(ps)`: the closest usable
chest or special location within reach. It is drawn in world space -- over
the element's art -- but at the interface's own size (`ui.keycap.CAP_PX`
design px), not zoomed with the world, so it stays as crisp as the HUD. It
is painted after the whole world so the hero standing on a chest never
covers it, and inside the shake offset so it shakes with the element. The
cap shows its pressed frame while the interact key is held.

**Where it hangs is read from the drawn art, not typed** (pass 3, after
the owner saw it drift on the rare chest and sit left of the forge's
chimney): `art_box` returns the element's painted rectangle on screen and
the x of its **highest ink column**, and the cap is centred on that column
with its bottom edge `CLEAR_PX` above the box. For a chest that is the
lid's centre -- the ink box's middle column, since a vine or a clasp can
poke above the lid off-centre -- measured from the closed frame at the
drawn scale and from the same truncated blit origin the chest painter
uses, so the two round alike. For the forge it is the chimney, from the bake's own record of
where the obstacle skin lands (`gm._art_rects`) and its frames
(`gm._decos`). Elements with no art -- the rings, the sanctuary's loop --
fall back to `KEY_LIFT`, a world-px height above their position.
"""
from __future__ import annotations

import pygame

from game import config
from game.states.playing.core import interactions
from progression import chests as _chests
from ui import keycap, scale

# Fallback heights above `pos` (world px) for elements the marker cannot
# measure: the rings are their own radius, the sanctuary is eyeballed
# against its heal loop.
KEY_LIFT = {
    "chest": 26,
    "shrine": 26, "altar": 26, "merchant": 26, "treasure": 24,
    "fountain": 40,
    "forge": 56,
}
CLEAR_PX = 4            # design px between the art's top and the cap's bottom

# (rig, size) -> (ink rect in the frame, x of the highest ink column). A
# rig's closed / first frame is measured once per drawn size.
_ink_cache: dict[tuple, tuple[pygame.Rect, int]] = {}


def interact_held() -> bool:
    """Is the interact key down right now? False when the keyboard cannot
    be read (no display -- the headless suite)."""
    try:
        return bool(pygame.key.get_pressed()[config.KEY_INTERACT])
    except (pygame.error, IndexError):
        return False


def ink_of(frame: pygame.Surface, key=None) -> tuple[pygame.Rect, int]:
    """The opaque box of `frame` and the x (in the frame) of its highest
    opaque column -- the peak the cap sits over. Cached under `key`."""
    if key is not None and key in _ink_cache:
        return _ink_cache[key]
    box = frame.get_bounding_rect(min_alpha=8)
    peak = box.centerx
    if box.width and box.height:
        top = box.top
        cols = [x for x in range(box.left, box.right)
                if frame.get_at((x, top)).a >= 8]
        if cols:
            peak = (cols[0] + cols[-1]) // 2
    out = (box, peak)
    if key is not None:
        _ink_cache[key] = out
    return out


def _chest_box(ps, chest):
    """The closed chest's painted box on screen, from the chest painter's
    own numbers (`rendering.chests`)."""
    assets = ps.game.assets
    z = ps.camera.zoom
    rig = _chests.sprite_rig(chest.rarity, ps.content.chests)
    base = assets.scale_for(rig) or (30, 30)
    size = (max(1, round(base[0] * z)), max(1, round(base[1] * z)))
    art = assets.frame(rig, "open", 0, size=size)
    if art is None:
        return None
    ax, ay = assets.anchor(rig)
    sx, sy = ps.camera.world_to_screen(chest.pos)
    ox, oy = int(sx - ax * z), int(sy - ay * z)
    box, _peak = ink_of(art, (rig, size))
    return pygame.Rect(ox + box.left, oy + box.top, box.width, box.height), ox + box.centerx


def _obstacle_box(ps, it):
    """The painted box of the obstacle skin standing on `it.pos` (the
    forge), from the bake's record of where the skin is drawn."""
    gm = ps.game_map
    rects = getattr(gm, "_art_rects", None) or {}
    decos = getattr(gm, "_decos", None) or {}
    for i, o in enumerate(getattr(gm, "obstacles", ())):
        if o.kind != it.kind or i not in rects or i not in decos:
            continue
        if (o.pos - it.pos).length_squared() > 1.0:
            continue
        wx, wy, w, h = rects[i]
        frs = decos[i][3]
        z = ps.camera.zoom
        sx, sy = ps.camera.world_to_screen(pygame.Vector2(wx, wy))
        box, peak = ink_of(frs[0], ("obstacle", o.kind, frs[0].get_size()))
        k = z                      # the baked frame is at world scale; the screen adds the zoom
        return (pygame.Rect(round(sx + box.left * k), round(sy + box.top * k),
                            round(box.width * k), round(box.height * k)),
                round(sx + (peak + 0.5) * k))
    return None


def art_box(ps, obj):
    """`(screen rect of the element's painted art, x of its peak)`, or
    `None` when the element draws nothing the marker can measure."""
    kind = interactions.kind_of(obj)
    if kind == "chest":
        return _chest_box(ps, obj)
    if kind == "forge":
        return _obstacle_box(ps, obj)
    return None


def anchor(ps, obj) -> tuple[int, int]:
    """Where the cap's raised face centre goes for `obj`: over the peak of
    its art, the cap's bottom edge `CLEAR_PX` above the art's top; or, with
    nothing to measure, over `pos` lifted by the kind's `KEY_LIFT`."""
    drop = keycap.cap_rect((0, 0)).bottom        # face centre -> cap bottom
    found = art_box(ps, obj)
    if found is not None:
        box, peak = found
        return (int(peak), int(box.top - scale.px(CLEAR_PX) - drop))
    sx, sy = ps.camera.world_to_screen(obj.pos)
    lift = KEY_LIFT.get(interactions.kind_of(obj), 26) * ps.camera.zoom
    return (int(round(sx)), int(round(sy - lift - scale.px(CLEAR_PX) - drop)))


def draw(surface: pygame.Surface, ps) -> None:
    obj = interactions.nearest(ps)
    if obj is None:
        return
    keycap.draw_keycap(surface, ps.game.assets, anchor(ps, obj),
                       keycap.label_for(config.KEY_INTERACT),
                       state="pressed" if interact_held() else "raised")
