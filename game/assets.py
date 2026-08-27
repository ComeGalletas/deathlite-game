"""Sprite / image loading and caching.

Lazy: nothing is read from disk until first requested, because image decoding
and `.convert_alpha()` need an initialised display. A missing or unreadable file
yields `None`, logged once -- callers fall back to primitive drawing, the same
degrade contract as `game/save.py`.

Sheet metadata (frame size, frame counts, fps, loop, anchor) lives in
`data/sprites.json`; this module only slices, transforms and memoises. Every
transform (slice, scale, flip, rotate) is cached -- nothing transforms per
frame.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ROTATION_BUCKET_DEG = 8      # arrow rotations are snapped to this granularity


class Assets:
    def __init__(self, metadata: dict | None = None) -> None:
        self._meta = metadata                       # None -> pulled from Content lazily
        self._terrain: dict | None = None
        self._sheets: dict[str, pygame.Surface | None] = {}
        self._frames: dict[tuple, list[pygame.Surface] | None] = {}
        self._rot: dict[tuple, pygame.Surface] = {}
        self._warned: set[str] = set()

    # --- metadata -------------------------------------------------
    @property
    def meta(self) -> dict:
        """Sprite rigs + terrain decoration rigs, one flat namespace so both use
        the same `frames()` / `frame()` path."""
        if self._meta is None:
            from game.content import get_content
            c = get_content()
            self._meta = {**c.sprites, **c.terrain.get("rigs", {})}
        return self._meta

    @property
    def terrain(self) -> dict:
        """The `data/terrain.json` config (tile_px, grid, slots, palettes)."""
        if self._terrain is None:
            from game.content import get_content
            self._terrain = get_content().terrain
        return self._terrain

    def rig(self, name: str) -> dict | None:
        return self.meta.get(name)

    def anchor(self, rig: str) -> tuple[int, int]:
        ax, ay = self.meta.get(rig, {}).get("anchor", (0, 0))
        return int(ax), int(ay)

    def face(self, rig: str) -> str:
        return self.meta.get(rig, {}).get("face", "right")

    def scale_for(self, rig: str) -> tuple[int, int] | None:
        s = self.meta.get(rig, {}).get("scale")
        return (int(s[0]), int(s[1])) if s else None

    def _anim(self, rig: str, anim: str) -> dict | None:
        try:
            return self.meta[rig]["anims"][anim]
        except (KeyError, TypeError):
            return None

    def frame_count(self, rig: str, anim: str) -> int:
        spec = self._anim(rig, anim)
        return int(spec["frames"]) if spec else 0

    def fps(self, rig: str, anim: str) -> float:
        spec = self._anim(rig, anim)
        return float(spec.get("fps", 12.0)) if spec else 12.0

    def loops(self, rig: str, anim: str) -> bool:
        spec = self._anim(rig, anim)
        return bool(spec.get("loop", False)) if spec else False

    # --- disk ----------------------------------------------------
    def _load_image(self, rel_path: str) -> pygame.Surface | None:
        if rel_path not in self._sheets:
            full = ASSETS_DIR / rel_path
            try:
                self._sheets[rel_path] = pygame.image.load(str(full)).convert_alpha()
            except (FileNotFoundError, pygame.error) as exc:
                if rel_path not in self._warned:
                    log.warning("asset missing/unreadable: %s (%s)", full, exc)
                    self._warned.add(rel_path)
                self._sheets[rel_path] = None
        return self._sheets[rel_path]

    # --- animation strips -----------------------------------
    def _build_frames(self, rig: str, anim: str, size, flip: bool):
        r = self.meta.get(rig)
        spec = self._anim(rig, anim)
        if not r or spec is None:
            return None
        sheet = self._load_image(spec["file"])
        if sheet is None:
            return None
        fw, fh = r.get("frame", [sheet.get_height(), sheet.get_height()])
        # `content` crops away the large transparent margin these packs ship
        # with -- same rect for every frame so the character does not jitter,
        # and much smaller surfaces to scale + blit.
        crop = r.get("content")
        out: list[pygame.Surface] = []
        for i in range(int(spec["frames"])):
            rect = pygame.Rect(i * fw, 0, fw, fh)
            if not sheet.get_rect().contains(rect):
                break                                   # declared count overruns the sheet
            fr = sheet.subsurface(rect)
            if crop:
                fr = fr.subsurface(pygame.Rect(*crop))
            fr = fr.copy()
            if flip:
                fr = pygame.transform.flip(fr, True, False)
            if size is not None:
                fr = pygame.transform.scale(fr, size)   # nearest -- keep the pixel look
            out.append(fr)
        return out or None

    def frames(self, rig: str, anim: str, *, size=None, flip: bool = False):
        key = (rig, anim, size, flip)
        if key not in self._frames:
            self._frames[key] = self._build_frames(rig, anim, size, flip)
        return self._frames[key]

    def frame(self, rig: str, anim: str, index: int, *, size=None, flip: bool = False):
        """One frame. `index` is clamped for one-shot anims, wrapped for loops."""
        frs = self.frames(rig, anim, size=size, flip=flip)
        if not frs:
            return None
        n = len(frs)
        i = index % n if self.loops(rig, anim) else max(0, min(index, n - 1))
        return frs[i]

    # --- single-image rigs (the arrow) --------------------
    def image(self, rig: str, *, size=None, flip: bool = False, tint=None):
        r = self.meta.get(rig)
        if not r or "file" not in r:
            return None
        surf = self._load_image(r["file"])
        if surf is None:
            return None
        key = ("<image>", rig, size, flip, tint)
        if key not in self._frames:
            out = surf
            crop = r.get("content")
            if crop:
                out = out.subsurface(pygame.Rect(*crop)).copy()
            if flip:
                out = pygame.transform.flip(out, True, False)
            if size is not None:
                out = pygame.transform.scale(out, size)
            if tint is not None:
                out = out.copy()
                # brighten toward `tint`, keeping the alpha silhouette.
                out.fill((*tint, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._frames[key] = [out]
        return self._frames[key][0]

    def rotated(self, rig: str, degrees: float, *, size=None, tint=None):
        base = self.image(rig, size=size, tint=tint)
        if base is None:
            return None
        bucket = round(degrees / ROTATION_BUCKET_DEG) * ROTATION_BUCKET_DEG
        key = (rig, size, tint, bucket)
        if key not in self._rot:
            # pygame rotates counter-clockwise; screen-y is down, so negate.
            self._rot[key] = pygame.transform.rotate(base, -bucket)
        return self._rot[key]

    # --- standalone images (menu title, etc.) -----------------
    def picture(self, rel_path: str, *, size=None):
        """A whole image that is not part of a rig (e.g. the menu title art).
        `None` for a missing / unreadable file (logged once), same degrade
        contract as the rest of the loader. `size` scales it -- smoothscale,
        since this is UI art rather than pixel sprites -- and caches the result."""
        base = self._load_image(rel_path)
        if base is None:
            return None
        if size is None:
            return base
        size = (int(size[0]), int(size[1]))
        key = ("<picture>", rel_path, size)
        if key not in self._frames:
            self._frames[key] = [pygame.transform.smoothscale(base, size)]
        return self._frames[key][0]

    # --- tilemap cells -----------------------------------------
    def tile(self, sheet_rel: str, index: int, *, size=None, cols: int | None = None):
        """One tile from a tilemap sheet by flat index (row-major, `cols` wide,
        `terrain.tile_px` per cell). `cols` defaults to `terrain.grid[0]` (the
        floor sheet); pass it for sheets with a different width (e.g. the bridge
        sheet). Memoised. `None` for a missing sheet or an out-of-range index."""
        sheet = self._load_image(sheet_rel)
        if sheet is None:
            return None
        px = int(self.terrain.get("tile_px", 64))
        if cols is None:
            cols = int(self.terrain.get("grid", [9, 6])[0])
        key = ("<tile>", sheet_rel, index, size, cols)
        if key not in self._frames:
            col, row = index % cols, index // cols
            rect = pygame.Rect(col * px, row * px, px, px)
            if not sheet.get_rect().contains(rect):
                self._frames[key] = None                 # cache the miss, don't re-probe
            else:
                cell = sheet.subsurface(rect).copy()
                if size is not None:
                    cell = pygame.transform.scale(cell, size)
                self._frames[key] = [cell]
        cached = self._frames[key]
        return cached[0] if cached else None


_assets: Assets | None = None


def get_assets() -> Assets:
    """Process-wide singleton; caches are built lazily on first use."""
    global _assets
    if _assets is None:
        _assets = Assets()
    return _assets


def reset_assets() -> None:
    """Test helper: drop the singleton and all its caches."""
    global _assets
    _assets = None
