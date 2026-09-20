"""Drawing the run's opening hints (journal: key_icons_journal.md, pass
5): the clusters `core/hints.py` asks for, as blue keycaps over the hero.

Blue because these are "press this now" prompts, and blue has the pressed
frame: each cap sinks while its key is actually held, which is the
teaching. The block hangs off the hero's **drawn art** -- the sprite
frame's ink top, the way the key marker hangs off a chest -- its bottom
`CLEAR_PX` above the helmet, and follows the hero. A finished stage fades
out over `config.HINT_FADE` before the next appears. Drawn after the world,
inside the shake offset, before the HUD.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import keycap, scale
from ui.text import shadowed

CAP = keycap.CAP_PX
CAP_GAP = 4             # between caps of a cluster
WORD_GAP = 10           # cluster -> word
CLUSTER_GAP = 28        # between the clusters of one stage
CLEAR_PX = 6            # block bottom -> the hero's art top
WORD_PX = 18


def hero_top(ps) -> tuple[int, int]:
    """`(x, y)` of the hero on screen: the sprite's centre column and the
    top of its painted art (the collider's top without the art)."""
    r = ps.renderer
    z = ps.camera.zoom
    sx, sy = ps.camera.world_to_screen(ps.player.pos)
    frame = r.hero_sprite_frame()
    if frame is None:
        return int(round(sx)), int(round(sy - ps.player.radius * z))
    ax, ay = r.anchor_for(ps._hero_anim.rig, r._hero_flip())
    ox = sx - ax * z
    oy = sy - ay * z + r.sprite_drop(ps.player.radius)
    ink = frame.get_bounding_rect(min_alpha=8)
    return int(round(sx)), int(round(oy + ink.top))


def _cluster_size(rows: list[list[str]]) -> tuple[int, int]:
    cap, gap = scale.px(CAP), scale.px(CAP_GAP)
    w = max(len(r) * cap + (len(r) - 1) * gap for r in rows)
    h = len(rows) * cap + (len(rows) - 1) * gap
    return w, h


def layout(ps, clusters, top: int, cx: int, font) -> list:
    """Where everything goes: `[("cap", label, face_center) | ("word",
    surface, rect), ...]` for a block whose bottom sits `CLEAR_PX` above
    `top`, centred on `cx`."""
    cap, gap = scale.px(CAP), scale.px(CAP_GAP)
    words = [shadowed(font, w, config.COLOR_TEXT) for w, _rows in clusters]
    sizes = [_cluster_size(rows) for _w, rows in clusters]
    widths = [cw + scale.px(WORD_GAP) + word.get_width() for (cw, _), word in zip(sizes, words)]
    height = max(h for _, h in sizes)
    total = sum(widths) + scale.px(CLUSTER_GAP) * (len(clusters) - 1)
    x = cx - total // 2
    bottom = top - scale.px(CLEAR_PX)
    out = []
    for (word, rows), (cw, ch), surf in zip(clusters, sizes, words):
        cy0 = bottom - height + (height - ch) // 2      # cluster top, centred in the band
        for ri, row in enumerate(rows):
            rw = len(row) * cap + (len(row) - 1) * gap
            rx = x + (cw - rw) // 2
            y = cy0 + ri * (cap + gap) + cap // 2
            for label in row:
                # `cap_rect` puts the raised face `face_y` below the top:
                # the face centre is 4 px above the cap's centre at 32 px.
                face = (rx + cap // 2, y - (cap // 2 - scale.px(keycap.FACE_Y["raised"] // 2)))
                out.append(("cap", label, face))
                rx += cap + gap
        wr = surf.get_rect(midleft=(x + cw + scale.px(WORD_GAP), bottom - height // 2))
        out.append(("word", surf, wr))
        x += cw + scale.px(WORD_GAP) + surf.get_width() + scale.px(CLUSTER_GAP)
    return out


def draw(surface: pygame.Surface, ps) -> pygame.Rect | None:
    """Paint the current stage (or the one fading out); returns the rect
    the block covered, or None when nothing is shown."""
    hints = getattr(ps, "hints", None)
    if hints is None or not hints.visible:
        return None
    font = fonts.body(WORD_PX)
    cx, top = hero_top(ps)
    if hints.fading is not None:
        clusters, left = hints.fading
        alpha = max(0, min(255, int(255 * left / max(1e-6, config.HINT_FADE))))
        target = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    else:
        clusters, alpha, target = hints.clusters(), 255, surface
    if not clusters:
        return None
    items = layout(ps, clusters, top, cx, font)
    covered = None
    for kind, a, b in items:
        if kind == "cap":
            held = hints.held(a) if alpha == 255 else False
            r = keycap.draw_keycap(target, ps.game.assets, b, a, colour="blue",
                                   state="pressed" if held else "raised")
        else:
            target.blit(a, b)
            r = b
        covered = r if covered is None else covered.union(r)
    if target is not surface:
        target.set_alpha(alpha)
        surface.blit(target, (0, 0))
    return covered
