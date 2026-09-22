"""Cut the elemental aura and reaction effects out of the reserve packs.

M10 (`documentation/journals/elemental_system_journal.md`). The game used to
have no authored art for the elements at all -- an aura was a procedural
ring and a reaction was a procedural flash. This lifts one animation per
element and per reaction out of the two unused packs and writes each as a
**single-row strip of its own**, so nothing at run time ever opens a parent
sheet or carries a `row` index.

Sources, both under the gitignored `assets/unused/`:

* `unordered-effects` -- 180 sheets of 64 px frames laid out N columns by
  **9 rows, where the rows are nine colour variants of the same
  animation**. The magic rod's arcane circle, thunder ball and thunder aura
  already came from here. The nine rows are, in order: coral (yellow
  highlight), magenta, blue, green, brown, grey, mauve, crimson, purple.
* `Super Pixel Effects Gigapack` -- one-shot bursts, already used for the
  buff buildings and the end banners. Only `spell_ice_001` is taken: a
  block of ice that forms over 40 frames and shatters, which is the freeze
  status exactly.

Two things this script has to do beyond copying pixels.

**Recolour**, for three of the eleven. Thunder is `#6C4AA3` and the pack's
purple rows are a dark indigo, a mauve and a saturated magenta -- none of
them that, and the magenta is Frostburn's. Overload and Superconduct want
to state *both* of their elements, and one authored row is one colour. All
three therefore take the neutral grey row and are remapped: a grey ramp
maps onto any coloured one exactly, which is the whole reason it is the row
to take, and recolouring a coloured row instead would be the mistake
`recolour_totem_fire.py` was written to avoid.

The two reaction ramps run between their *pair's* colours -- purple shadow
to a hot orange core for Overload, purple shadow to an icy highlight for
Superconduct -- so each burst names both of its elements in one shape. The
three Wind reactions stay one authored row each on purpose: they are the
same mechanic with different payloads and the family reading is worth more
there than naming the pair.

**Trim, on one common box.** Every frame of a strip is cropped to the
*union* of the row's content, never to its own, so the frames stay in
register with each other. The anchor is the original 64 px frame's centre
carried into the cropped box, so a rig still centres on the body.

    python -m tools.asset_pipeline.cut_element_effects
    python -m tools.asset_pipeline.cut_element_effects --dry-run

The printed table is the input to the rigs in `weapon_sprites.json`.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_ELEMENTS = ROOT / "assets" / "effects" / "elements"
OUT_REACTIONS = ROOT / "assets" / "effects" / "reactions"

# Set by `main` from `--reserve`, which defaults to `assets/unused`. It is a
# flag rather than a constant because that folder is gitignored, so a git
# worktree -- which is how this feature was built -- does not have one, and
# the packs then live in the main checkout beside it.
PACK = Path()
GIGA = Path()


def set_reserve(reserve: Path) -> None:
    global PACK, GIGA
    PACK = reserve / "unordered-effects"
    GIGA = reserve / "Super Pixel Effects Gigapack" / "spritesheet"


SIDE = 64
ALPHA_FLOOR = 24          # below this a pixel is pack noise, not content

# Thunder's ramp: a two-point gradient, dark end to light end, with a gamma
# that lifts the midtones. Centred on the element's own `#6C4AA3`.
#
# Two lessons from getting this wrong, both of which apply to whatever
# colour is asked for next; they were learned on a yellow Thunder, before
# the owner changed the element to purple, and neither depends on the hue.
#
# A plain per-channel multiply was the first attempt. The grey row's values
# sit in the middle -- its commonest pixel is #6f6f6f -- so scaling it by a
# colour triple darkens everything into mud. The pack's own coloured rows
# are not built that way either: each runs a pale highlight down to a
# saturated shadow. Interpolating between two ends the same way is what
# makes the result read as the same pack.
#
# The ends want to be saturated rather than pale. A pass with a light end
# near white and a gamma that lifted the midtones washed out entirely: this
# source is thin strokes and most of its pixels are already light, so
# lifting them puts the whole thing at the light end. A real colour at the
# light end and a gamma near 1 is what keeps it a colour.
PURPLE = ((58, 36, 92), (168, 132, 226), 0.8)

# The two reactions whose pair is *Thunder plus something*, each remapped
# across its own pair, dark end to light end. One authored row is one
# colour and a reaction has two elements; where the pair used to be two
# warm colours (Overload) or one of them was yellow (Superconduct), a
# single row could pass for the whole reaction. Purple ended that, and
# stating both is better anyway.
#
# The three Wind reactions are deliberately *not* done this way. They are
# one swirl in three colours because they are the same mechanic with
# different payloads, and that family reading is worth more there than
# naming the pair.
# Overload's ends are pushed further apart and its gamma above 1 on
# purpose. Fire and Thunder sit nearly opposite on the colour wheel, so a
# straight RGB interpolation between them runs through mud rather than
# through either of them, and the source's darkest pixels only reach about
# a fifth of the way along the ramp. A first attempt at `(92, 56, 140)` and
# gamma 0.9 therefore produced a strip with **no purple in it at all** --
# it looked plausible and `test_element_colours` counted the pixels and
# said otherwise. A deeper, more saturated dark end and a gamma that keeps
# values low for longer is what puts thunder back in it.
#
# Superconduct needs none of that: ice and thunder are adjacent hues, so
# anything between them is already both.
OVERLOAD_PAIR = ((68, 24, 185), (255, 168, 64), 1.5)       # purple -> fire orange
SUPERCONDUCT_PAIR = ((92, 56, 140), (150, 214, 255), 0.9)  # purple -> ice blue


class Cut:
    """One effect to lift: where it comes from and where it lands."""

    def __init__(self, name: str, out_dir: Path, part: int, sheet: str,
                 row: int, recolour=None, note: str = "") -> None:
        self.name = name
        self.out_dir = out_dir
        self.part = part
        self.sheet = sheet
        self.row = row
        self.recolour = recolour
        self.note = note

    @property
    def source(self) -> Path:
        return PACK / f"Part {self.part}" / f"{self.sheet}.png"

    @property
    def target(self) -> Path:
        return self.out_dir / f"{self.name}.png"


# The four auras. One distinct *shape* each rather than one shape in four
# hues: with the ring and the marker gone the sprite is the only thing
# telling the player what an enemy is primed with, and that has to survive
# colourblindness (design 8).
CUTS = [
    Cut("fire", OUT_ELEMENTS, 12, "586", 0,
        note="a ring that grows flame tongues outward"),
    Cut("ice", OUT_ELEMENTS, 13, "623", 2,
        note="a crystal that forms, then opens into a diamond outline"),
    Cut("thunder", OUT_ELEMENTS, 14, "652", 5, recolour=PURPLE,
        note="a radial spiked discharge; grey row remapped to purple"),
    Cut("wind", OUT_ELEMENTS, 1, "26", 3,
        note="concentric rings turning -- the only pick that rotates"),

    # The six reactions, one-shot at the body that reacted.
    Cut("frostburn", OUT_REACTIONS, 4, "186", 1,
        note="a violet sphere of motes -- where fire and ice blend"),
    Cut("overload", OUT_REACTIONS, 14, "674", 5, recolour=OVERLOAD_PAIR,
        note="a hexagonal detonation, the biggest of the six; the grey row "
             "remapped across its own pair, purple shadow to orange core"),
    Cut("superconduct", OUT_REACTIONS, 9, "446", 5, recolour=SUPERCONDUCT_PAIR,
        note="an orbiting star coming apart -- what a chain reads as; the "
             "grey row remapped across its own pair, thunder's purple in "
             "the shadows to ice's blue in the highlights"),
    # The three wind reactions are one swirl in three colours on purpose:
    # they are the same mechanic (a tornado with a payload) and should read
    # as siblings rather than as three unrelated effects.
    Cut("firewind", OUT_REACTIONS, 15, "711", 0,
        note="the swirl, fire's coral"),
    Cut("icewind", OUT_REACTIONS, 15, "711", 2,
        note="the swirl, ice's blue"),
    Cut("thunderwind", OUT_REACTIONS, 15, "711", 5, recolour=PURPLE,
        note="the swirl, thunder's purple; grey row remapped"),
]


def union_box(frames: list) -> pygame.Rect:
    """The smallest box holding every frame's content.

    Per-frame boxes would shrink the file further and put the frames out of
    register with each other, which for a looping aura shows up as a jitter
    no amount of anchoring fixes.
    """
    box = None
    for frame in frames:
        mask = pygame.mask.from_surface(frame, ALPHA_FLOOR)
        rects = mask.get_bounding_rects()
        if not rects:
            continue
        here = rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]
        box = here if box is None else box.union(here)
    return box or pygame.Rect(0, 0, SIDE, SIDE)


def remap(frame: pygame.Surface, ramp) -> pygame.Surface:
    """A grey frame onto a two-point colour ramp, keeping its alpha.

    Reads the pixel's luminance rather than its red channel, so a row that
    is *nearly* neutral rather than exactly neutral still maps smoothly,
    and raises it by `gamma` before interpolating -- the grey row's
    midtones are dark, and without the lift the light end is never reached.
    """
    dark, light, gamma = ramp
    lut = []
    for v in range(256):
        t = (v / 255.0) ** gamma
        lut.append(tuple(int(d + (l - d) * t) for d, l in zip(dark, light)))

    out = frame.copy()
    width, height = out.get_size()
    out.lock()
    for y in range(height):
        for x in range(width):
            r, g, b, a = out.get_at((x, y))
            if a == 0:
                continue
            v = int(0.299 * r + 0.587 * g + 0.114 * b)
            out.set_at((x, y), (*lut[min(255, v)], a))
    out.unlock()
    return out


def cut_one(cut: Cut, dry: bool) -> dict:
    sheet = pygame.image.load(str(cut.source)).convert_alpha()
    cols = sheet.get_width() // SIDE
    rows = sheet.get_height() // SIDE
    if not 0 <= cut.row < rows:
        raise SystemExit(f"{cut.name}: row {cut.row} outside {rows}-row sheet")

    frames = []
    for c in range(cols):
        frame = sheet.subsurface(
            pygame.Rect(c * SIDE, cut.row * SIDE, SIDE, SIDE)).copy()
        if cut.recolour:
            frame = remap(frame, cut.recolour)
        frames.append(frame)

    box = union_box(frames)
    strip = pygame.Surface((box.width * cols, box.height), pygame.SRCALPHA)
    for i, frame in enumerate(frames):
        strip.blit(frame, (i * box.width, 0), box)

    if not dry:
        cut.target.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(strip, str(cut.target))

    # The anchor is the original frame's centre carried into the crop, so a
    # rig still centres the effect on the body rather than on the art's
    # bounding box -- these animations are not symmetrical about their own
    # content and several drift as they play.
    return {
        "name": cut.name,
        "file": str(cut.target.relative_to(ROOT / "assets")).replace("\\", "/"),
        "frames": cols,
        "frame": [box.width, box.height],
        "anchor": [SIDE // 2 - box.x, SIDE // 2 - box.y],
        "source": f"Part {cut.part}/{cut.sheet}.png row {cut.row}",
        "note": cut.note,
    }


FREEZE = ("Fantasy Spells/spell_ice_001/spell_ice_001_large_blue", 128)


def cut_freeze(dry: bool) -> dict:
    """The Gigapack's ice block, for the freeze status.

    A frozen enemy carries a bracket over its head today. This is the body
    encased instead, which is what freeze has always wanted to look like
    and what no procedural shape was going to give it.
    """
    path = GIGA / FREEZE[0] / "spritesheet.png"
    side = FREEZE[1]
    sheet = pygame.image.load(str(path)).convert_alpha()
    cols = sheet.get_width() // side
    frames = [sheet.subsurface(pygame.Rect(c * side, 0, side, side)).copy()
              for c in range(cols)]
    box = union_box(frames)
    strip = pygame.Surface((box.width * cols, box.height), pygame.SRCALPHA)
    for i, frame in enumerate(frames):
        strip.blit(frame, (i * box.width, 0), box)
    target = OUT_ELEMENTS / "freeze.png"
    if not dry:
        target.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(strip, str(target))
    return {
        "name": "freeze",
        "file": str(target.relative_to(ROOT / "assets")).replace("\\", "/"),
        "frames": cols,
        "frame": [box.width, box.height],
        "anchor": [side // 2 - box.x, side // 2 - box.y],
        "source": f"Gigapack {FREEZE[0]}",
        "note": "a block of ice forming, then shattering",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and report without writing any file")
    ap.add_argument("--reserve", type=Path,
                    default=ROOT / "assets" / "unused",
                    help="where the source packs live (default: "
                         "assets/unused, which is gitignored and therefore "
                         "absent from a worktree)")
    args = ap.parse_args(argv)
    set_reserve(args.reserve)

    if not PACK.is_dir():
        raise SystemExit(
            f"the reserve pack is missing: {PACK}\n"
            "assets/unused/ is gitignored -- it lives in the working copy, "
            "not in the repository, like every other cut script's source.")

    pygame.init()
    pygame.display.set_mode((SIDE, SIDE))

    rows = [cut_one(cut, args.dry_run) for cut in CUTS]
    rows.append(cut_freeze(args.dry_run))

    print(f"\n{'name':<14}{'frames':>7}  {'frame':<11}{'anchor':<11}"
          f"{'file':<34}source")
    print("-" * 110)
    for r in rows:
        print(f"{r['name']:<14}{r['frames']:>7}  "
              f"{str(r['frame']):<11}{str(r['anchor']):<11}"
              f"{r['file']:<34}{r['source']}")
    print(f"\n{'(dry run -- nothing written)' if args.dry_run else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
