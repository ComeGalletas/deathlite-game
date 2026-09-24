"""Cut the `mark` status's lock-on brackets into the strip the game reads (RND-007).

The source is the Super Pixel Effects Gigapack's
`Sci-fi/scifi_analyze_001/scifi_analyze_001_large_red`, 120 frames of 144 x 144
in which four corner brackets frame a target while scanner panels come and go.
Only the brackets-only run is used -- frames 109-119 then 0-2, where the box
tightens from 62 px wide to 50 and opens again, a lock-on breathe that loops.
Those 14 frames are archived, tracked, in `assets/effects/status/unused/mark/`
(named `<loop order>_frame<source number>.png`), so the check below always has
its input.

Two passes per frame, then the join:

* **The leader is erased.** A line from the retracting panel trails off the
  top-right bracket in these frames. Everything above the brackets' top row
  goes, the row read off the left brackets' vertical strokes, which the
  leader never reaches.
* **The colour is replaced.** The pack's "red" is a salmon orange (hue ~14),
  too close to the fire element's orange. Each coloured pixel takes the hue in
  `data/weapons/status_visuals.json` `mark.recolour` (raspberry, 340), with
  its saturation and value scaled by the data; near-white glints are kept.

* `assets/effects/status/mark.png` -- the 14 frames in order, one row,
  2016 x 144.

    python tools/asset_pipeline/cut_mark_brackets.py            # writes the strip
    python tools/asset_pipeline/cut_mark_brackets.py --check    # exits 1 on a drift
"""
from __future__ import annotations

import colorsys
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, "assets", "effects", "status")
SOURCE = os.path.join(FOLDER, "unused", "mark")
STRIP_NAME = "mark.png"
DATA = os.path.join(ROOT, "data", "weapons", "status_visuals.json")
FRAME = 144


def frames() -> list[str]:
    """The archived source frames, in loop order."""
    if not os.path.isdir(SOURCE):
        return []
    return sorted(f for f in os.listdir(SOURCE) if f.lower().endswith(".png"))


def recolour_spec() -> dict:
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)["mark"]["recolour"]


def erase_leader(img: pygame.Surface) -> None:
    """Clear everything above the brackets' top row.

    The top row is read off the left brackets' vertical strokes -- the
    frame's leftmost opaque columns -- which the leader never reaches (it
    starts left of centre but well inside the box). Nothing that belongs to
    the mark sits above the top brackets."""
    w, h = img.get_size()
    x0 = next((x for x in range(w) for y in range(h) if img.get_at((x, y)).a > 0), None)
    if x0 is None:
        return
    top = min(y for x in range(x0, min(w, x0 + 3)) for y in range(h)
              if img.get_at((x, y)).a > 0)
    for y in range(top):
        for x in range(w):
            img.set_at((x, y), (0, 0, 0, 0))


def recolour(img: pygame.Surface, spec: dict) -> None:
    hue = spec["hue"] / 360.0
    sat_mult, val_mult, keep = spec["sat_mult"], spec["val_mult"], spec["keep_below_sat"]
    w, h = img.get_size()
    for x in range(w):
        for y in range(h):
            r, g, b, a = img.get_at((x, y))
            if a == 0:
                continue
            _h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < keep:
                continue                              # near-white glints stay white
            nr, ng, nb = colorsys.hsv_to_rgb(hue, min(1.0, s * sat_mult), min(1.0, v * val_mult))
            img.set_at((x, y), (round(nr * 255), round(ng * 255), round(nb * 255), a))


def strip(names: list[str], spec: dict) -> pygame.Surface:
    out = pygame.Surface((FRAME * len(names), FRAME), pygame.SRCALPHA)
    for i, name in enumerate(names):
        img = pygame.image.load(os.path.join(SOURCE, name)).convert_alpha()
        if img.get_size() != (FRAME, FRAME):
            raise ValueError(f"{name} is {img.get_size()}, expected {FRAME} x {FRAME}")
        erase_leader(img)
        recolour(img, spec)
        out.blit(img, (i * FRAME, 0))
    return out


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    names = frames()
    if not names:
        print(f"no source frames in {SOURCE} -- nothing to cut")
        return 2
    want = strip(names, recolour_spec())
    out = os.path.join(FOLDER, STRIP_NAME)
    if "--check" in argv:
        if not os.path.exists(out):
            print(f"missing {out}")
            return 1
        have = pygame.image.load(out).convert_alpha()
        if (have.get_size() != want.get_size()
                or pygame.image.tostring(have, "RGBA") != pygame.image.tostring(want, "RGBA")):
            print(f"{out} differs from what the script cuts -- rerun it")
            return 1
        print(f"{STRIP_NAME}: in step ({len(names)} frames)")
        return 0
    pygame.image.save(want, out)
    print(f"wrote {out} ({len(names)} frames, {want.get_width()} x {want.get_height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
