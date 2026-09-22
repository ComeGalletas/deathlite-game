"""Draw every infusable effect four more times, once per element.

The runtime alternative was measured and rejected. A multiply tint -- the
`wash` the enemy bodies wear -- cannot turn an orange flame blue, because
orange x blue is mud; turning it up only muddies it further. A per-pixel
hue rotation gives the right colours but costs ~2.4 ms a frame uncached,
which is a visible hitch on a cache miss. So the rotation is done here,
once, and the game blits an ordinary sprite.

This is `recolour_totem_fire.py`'s argument generalised: shape, shading and
alpha survive; only the hue moves.

**The source art is expected to change.** Nothing here is transcribed by
hand. The families are declared in the sprite data itself -- any rig
carrying an `infused` block -- and every source path is read from that
rig's own anims, so repointing a rig at new art and re-running is the whole
update. `--check` fails when the two have drifted apart, and a test runs it.

    python -m tools.asset_pipeline.recolour_element_variants
    python -m tools.asset_pipeline.recolour_element_variants --check
    python -m tools.asset_pipeline.recolour_element_variants --only ember

Writes `assets/infused/<rig>_<element>/<stem>.png` and the rig table
`data/weapons/infused_sprites.json`, both generated in full every run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "assets")
DATA = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ASSETS, "infused")
OUT_JSON = os.path.join(DATA, "weapons", "infused_sprites.json")
OUT_REL = "infused"

# The rig tables searched for an `infused` block.
SPRITE_FILES = ("weapons/weapon_sprites.json",)

# How much of a source pixel's distance from its family's own hue survives
# the rotation. 1.0 is a rigid turn -- a flame whose core is yellow and
# whose edge is red keeps them exactly that far apart -- and 0 flattens the
# sheet to a single hue. Under 1 because several of these sources span more
# hue than an element's palette wants to.
DEFAULT_SPREAD = 0.85


# --- the source data ---------------------------------------------------------

def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def element_colours() -> dict:
    """The four elements' RGB, from the one place M12 put them."""
    visuals = load_json(os.path.join(DATA, "weapons", "element_visuals.json"))
    out = {}
    for key, spec in visuals["elements"].items():
        colour = spec.get("colour")
        if colour:
            out[key] = tuple(int(c) for c in colour)
    return out


def families() -> dict:
    """Every rig carrying an `infused` block, by name."""
    found = {}
    for name in SPRITE_FILES:
        for rig, spec in load_json(os.path.join(DATA, name)).items():
            if isinstance(spec, dict) and spec.get("infused") is not None:
                found[rig] = spec
    return found


def sources(spec: dict) -> list:
    """The distinct sheets a rig reads, as paths relative to `assets/`.

    A rig names its file either once at the top (a still) or per anim, and
    several anims usually share one sheet -- the wolf's five are all rows of
    `wolf-spectral.png`. Each sheet is recoloured once.
    """
    paths = []
    if spec.get("file"):
        paths.append(spec["file"])
    for anim in spec.get("anims", {}).values():
        if anim.get("file") and anim["file"] not in paths:
            paths.append(anim["file"])
    return paths


# --- the recolour ------------------------------------------------------------

def to_hsv(rgb):
    """`rgb` as float 0..1, shape (..., 3) -> hue in turns, saturation, value."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(axis=-1)
    c = v - rgb.min(axis=-1)
    s = np.where(v > 0, c / np.maximum(v, 1e-6), 0.0)
    h = np.zeros_like(v)
    nz = c > 1e-6
    mr = nz & (v == r)
    mg = nz & (v == g) & ~mr
    mb = nz & ~mr & ~mg
    h[mr] = ((g - b)[mr] / c[mr]) % 6.0
    h[mg] = ((b - r)[mg] / c[mg]) + 2.0
    h[mb] = ((r - g)[mb] / c[mb]) + 4.0
    return h / 6.0, s, v


def to_rgb(h, s, v):
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    i = i.astype(np.int32) % 6
    out = np.empty(h.shape + (3,), dtype=np.float32)
    for k, (rr, gg, bb) in enumerate(((v, t, p), (q, v, p), (p, v, t),
                                      (p, q, v), (t, p, v), (v, p, q))):
        m = i == k
        out[m] = np.stack([rr[m], gg[m], bb[m]], axis=-1)
    return out


def dominant_hue(h, s, v, a) -> float:
    """The family's own hue, as a circular mean weighted by how much each
    pixel actually says about colour: a black outline and a transparent
    corner both have a hue and neither means anything."""
    w = s * v * a
    if w.sum() <= 1e-6:
        return 0.0
    ang = h * 2.0 * np.pi
    return float(np.arctan2((np.sin(ang) * w).sum(),
                            (np.cos(ang) * w).sum()) / (2.0 * np.pi)) % 1.0


def recolour(rgba, target, *, spread: float = DEFAULT_SPREAD,
             sat_gain: float = 1.0, sat_floor: float = 0.0,
             value_gain: float = 1.0):
    """`rgba` (uint8, H x W x 4) rotated onto `target`'s hue.

    Every pixel keeps its value and its alpha, so the shading and the
    silhouette are untouched, and the hue turns by one angle for the whole
    sheet, which keeps the art's internal colour relationships: a flame
    whose core is hotter than its edge still has a core hotter than its
    edge, in the new colour.

    `sat_floor` is for art too grey to rotate -- nothing happens to a steel
    blade if you only turn its hue. It lifts saturation toward the floor
    most in the midtones and not at all at the extremes, so a white
    highlight stays white and a black outline stays black.
    """
    f = rgba.astype(np.float32) / 255.0
    h, s, v = to_hsv(f[..., :3])
    a = f[..., 3]
    th, _ts, _tv = to_hsv(np.array([[c / 255.0 for c in target]],
                                   dtype=np.float32))
    delta = (h - dominant_hue(h, s, v, a) + 0.5) % 1.0 - 0.5
    h2 = (float(th[0]) + delta * spread) % 1.0
    s2 = np.clip(s * sat_gain, 0.0, 1.0)
    if sat_floor > 0.0:
        s2 = np.maximum(s2, sat_floor * (1.0 - np.abs(2.0 * v - 1.0)))
    v2 = np.clip(v * value_gain, 0.0, 1.0)
    out = np.empty_like(f)
    out[..., :3] = to_rgb(h2, s2, v2)
    out[..., 3] = a
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


# --- reading and writing PNGs ------------------------------------------------

def read_rgba(path: str):
    import pygame
    import pygame.surfarray as sa
    surf = pygame.image.load(path)
    conv = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    conv.blit(surf, (0, 0))
    rgb = sa.array3d(conv).transpose(1, 0, 2)
    alpha = sa.array_alpha(conv).transpose(1, 0)
    return np.dstack([rgb, alpha]).astype(np.uint8)


def write_rgba(path: str, arr) -> None:
    import pygame
    import pygame.surfarray as sa
    h, w = arr.shape[:2]
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    sa.blit_array(surf, arr[..., :3].transpose(1, 0, 2).copy())
    alpha = sa.pixels_alpha(surf)
    alpha[:] = arr[..., 3].transpose(1, 0)
    del alpha
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(surf, path)


# --- the run -----------------------------------------------------------------

def variant_spec(spec: dict, rig: str, element: str, remap: dict) -> dict:
    """`spec` with its sheets repointed at this element's copies."""
    out = {k: v for k, v in spec.items() if k not in ("infused", "_note")}
    out["_generated"] = (
        f"{rig} recoloured for {element} by "
        "tools/asset_pipeline/recolour_element_variants.py -- do not edit; "
        f"edit {rig} and re-run.")
    if out.get("file"):
        out["file"] = remap[out["file"]]
    if "anims" in out:
        out["anims"] = {
            name: ({**anim, "file": remap[anim["file"]]} if anim.get("file")
                   else dict(anim))
            for name, anim in out["anims"].items()}
    return out


def build(only=None):
    """The whole output: the rig table, and every PNG keyed by its path
    relative to `assets/`. Built in memory so writing and `--check` share
    one code path and cannot disagree."""
    colours = element_colours()
    rigs = {}
    images = {}
    for rig, spec in sorted(families().items()):
        if only and rig != only:
            continue
        tuning = spec["infused"]
        tuning = tuning if isinstance(tuning, dict) else {}
        knobs = {k: float(v) for k, v in tuning.items() if not k.startswith("_")}
        srcs = sources(spec)
        if not srcs:
            raise SystemExit(f"{rig}: declares `infused` but names no sheet")
        loaded = {p: read_rgba(os.path.join(ASSETS, p.replace("/", os.sep)))
                  for p in srcs}
        for element, colour in colours.items():
            remap = {}
            for path in srcs:
                rel = f"{OUT_REL}/{rig}_{element}/{os.path.basename(path)}"
                images[rel] = recolour(loaded[path], colour, **knobs)
                remap[path] = rel
            rigs[f"{rig}_{element}"] = variant_spec(spec, rig, element, remap)
    return rigs, images


HEADER = {
    "_doc": [
        "GENERATED -- do not edit by hand.",
        "",
        "One rig per (infusable effect, element). The art is the base rig's",
        "own sheets rotated onto the element's hue, because a runtime tint",
        "cannot turn an orange flame blue and a runtime hue rotation costs",
        "about 2.4 ms a frame (M13 C, elemental_system_journal.md).",
        "",
        "To change any of it -- the art, the `infused` tuning, anything --",
        "change the base rig in weapon_sprites.json and re-run",
        "    python -m tools.asset_pipeline.recolour_element_variants",
        "A test runs the same tool with --check and fails on a drift.",
    ],
}


def stale(images: dict) -> list:
    """Files under `assets/infused/` this run would not write."""
    out = []
    for dirpath, _dirs, names in os.walk(OUT_DIR):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name),
                                  ASSETS).replace(os.sep, "/")
            if rel not in images:
                out.append(rel)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="recolour the infusable effects")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the tree is not what this would write")
    ap.add_argument("--only", help="one rig, for iterating on its tuning")
    args = ap.parse_args(argv)

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()

    rigs, images = build(args.only)
    table = dict(HEADER)
    table.update(sorted(rigs.items()))
    text = json.dumps(table, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        bad = []
        if not os.path.exists(OUT_JSON):
            bad.append(os.path.relpath(OUT_JSON, ROOT) + " (missing)")
        else:
            with open(OUT_JSON, encoding="utf-8") as fh:
                if fh.read() != text:
                    bad.append(os.path.relpath(OUT_JSON, ROOT))
        for rel, arr in images.items():
            path = os.path.join(ASSETS, rel.replace("/", os.sep))
            if not os.path.exists(path):
                bad.append(f"assets/{rel} (missing)")
            elif not np.array_equal(read_rgba(path), arr):
                bad.append(f"assets/{rel}")
        bad += [f"assets/{rel} (orphan)" for rel in stale(images)]
        for line in bad:
            print(f"drifted: {line}")
        print(f"{len(images)} sheets checked, {len(bad)} drifted")
        return 1 if bad else 0

    if args.only is None and os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)          # generated in full; no orphans survive
    for rel, arr in images.items():
        write_rgba(os.path.join(ASSETS, rel.replace("/", os.sep)), arr)
    if args.only is None:
        with open(OUT_JSON, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"{len(images)} sheets, {len(rigs)} rigs -> "
          f"{os.path.relpath(OUT_JSON, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
