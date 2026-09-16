"""Cut the Freesound downloads in `assets/sound_effects/unused/` into the short
cues the game loads from `assets/sound_effects/`.

The three source files are usable recordings wrapped in a lot of dead air, and
one of them is in a format the game has no use for:

| source | 5.6 MB total | problem |
|--------|--------------|---------|
| `386678__laurenmg95__grass_footstep_hard_4.wav` | 1.46 s | 1.13 s of it is silence after the step |
| `386686__laurenmg95__grass_footstep_soft_4.wav` | 1.31 s | 1.01 s of silence after the step |
| `869056__signaturesoundsorg__monster_growls_grunts_10.wav` | 14.08 s | the growl ends at ~2.2 s; the other 11.9 s is a -84 dBFS noise floor. Also 96 kHz, against a 44.1 kHz device |

A cue has to be *instant*: `Sound.play()` starts at frame 0, so any silence at
the head of the file is latency the player hears as lag, and any silence at the
tail is memory held for nothing. So each source is trimmed to its actual
content, faded out to avoid a click at the new end, resampled to the device
rate, and peak-normalised.

**Normalisation is per group, not per file.** The two footsteps are a matched
pair -- "hard" is meant to be louder than "soft" -- so they share one gain
factor and keep that contrast. The growl is normalised on its own; at -23 dBFS
peak it is far quieter than the footsteps and would otherwise be inaudible
under them.

Run from the repo root:

    python -m tools.asset_pipeline.cut_sound_effects          # write the cues
    python -m tools.asset_pipeline.cut_sound_effects --check  # report only

Pure stdlib (`wave` + `array`) -- no numpy, so this runs in the game's own venv.
"""
from __future__ import annotations

import argparse
import array
import contextlib
import math
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "assets" / "sound_effects"
SRC_DIR = OUT_DIR / "unused"

# The device `systems/mixer_backend.DesktopMixer` opens (see DESKTOP_RATE).
# Matching it means SDL does no conversion when the cue is loaded.
RATE = 44100
# Headroom below full scale, matching the synthesised cues' `_AMP = 26000`
# (about -2 dBFS) with a little more room since these mix on top of music.
TARGET_PEAK = 0.72

# Everything below this fraction of a file's own peak counts as silence when
# looking for where the content *stops*.
SILENCE_REL = 0.01          # -40 dB relative to the file's peak
PRE_ROLL_S = 0.015          # keep a hair before the attack so it is not clipped

# Finding where the content *starts* needs a stricter threshold than finding
# where it ends, and this is the whole reason the footsteps sound right. Both
# grass recordings open with a couple of hundred milliseconds of handling noise
# and rustle sitting above -40 dB but below -26 dB; the actual step lands at
# 0.230 s in the hard take and 0.090 s in the soft one. Trimming on the silence
# floor alone kept all of that, which in a cue is not texture -- it is latency,
# heard as a lag between pressing a key and the step landing. A per-cue
# `attack_rel` says "the content starts where the level first crosses this
# fraction of the file's peak", and the pre-roll above puts the attack's
# leading edge back.
DEFAULT_ATTACK_REL = 0.01


class Cue:
    """One source file and how to cut it.

    `end_s` pins the cut where the automatic search would run on into an
    inaudible tail (the growl decays for another two seconds below -57 dBFS
    before the noise floor takes over, and the search follows it).
    `group` names the files that share a normalisation factor.
    """

    def __init__(self, src, out, group, end_s=None, fade_out_s=0.03,
                 attack_rel=DEFAULT_ATTACK_REL):
        self.src, self.out, self.group = src, out, group
        self.end_s, self.fade_out_s = end_s, fade_out_s
        self.attack_rel = attack_rel


CUES = [
    # attack_rel 0.05 skips the run-up; see DEFAULT_ATTACK_REL above.
    Cue("386678__laurenmg95__grass_footstep_hard_4.wav",
        "footstep_grass_hard.wav", group="footstep", attack_rel=0.05),
    Cue("386686__laurenmg95__grass_footstep_soft_4.wav",
        "footstep_grass_soft.wav", group="footstep", attack_rel=0.05),
    # The growl is already at 19% of its peak in the first 20 ms, so the
    # default threshold leaves its onset alone; what it needs is the *end*
    # pinned, because it decays below -57 dBFS for another two seconds.
    Cue("869056__signaturesoundsorg__monster_growls_grunts_10.wav",
        "monster_growl.wav", group="growl", end_s=2.4, fade_out_s=0.20),
]


# --------------------------------------------------------------------------
def _read(path: Path):
    """-> (frames as a list of per-channel int lists, rate). Any channel count."""
    with contextlib.closing(wave.open(str(path))) as w:
        ch, width, rate, n = (w.getnchannels(), w.getsampwidth(),
                              w.getframerate(), w.getnframes())
        raw = w.readframes(n)
    if width != 2:
        raise SystemExit(f"{path.name}: expected 16-bit, got {width * 8}-bit")
    flat = array.array("h")
    flat.frombytes(raw)
    return flat, ch, rate


def _peak(flat: "array.array") -> float:
    return max((abs(v) for v in flat), default=0) / 32768.0


def _bounds(flat, ch, rate, peak, attack_rel):
    """First frame at the attack threshold, last frame above the silence floor."""
    floor = peak * 32768.0 * SILENCE_REL
    onset = peak * 32768.0 * attack_rel
    n = len(flat) // ch
    first, last = 0, n - 1
    for i in range(n):
        if max(abs(flat[i * ch + c]) for c in range(ch)) > onset:
            first = i
            break
    for i in range(n - 1, -1, -1):
        if max(abs(flat[i * ch + c]) for c in range(ch)) > floor:
            last = i
            break
    return max(0, first - int(rate * PRE_ROLL_S)), last


def _resample(frames, ch, src_rate, dst_rate):
    """Linear resample of an interleaved buffer. Same approach as
    `systems/mixer_backend._resample_i16`, kept separate because that one is
    mono-only and runs in the shipped game."""
    if src_rate == dst_rate:
        return frames
    n_in = len(frames) // ch
    ratio = dst_rate / src_rate
    n_out = max(1, int(n_in * ratio))
    out = array.array("h", bytes(2 * n_out * ch))
    for i in range(n_out):
        pos = i / ratio
        j = int(pos)
        frac = pos - j
        k = min(j + 1, n_in - 1)
        for c in range(ch):
            a, b = frames[j * ch + c], frames[k * ch + c]
            out[i * ch + c] = int(a + (b - a) * frac)
    return out


def _fade_out(frames, ch, rate, seconds):
    n = len(frames) // ch
    f = min(n, int(rate * seconds))
    for i in range(n - f, n):
        g = (n - i) / f
        for c in range(ch):
            frames[i * ch + c] = int(frames[i * ch + c] * g)
    return frames


def _scaled(frames, gain):
    out = array.array("h", bytes(2 * len(frames)))
    for i, v in enumerate(frames):
        out[i] = max(-32768, min(32767, int(v * gain)))
    return out


def _write(path: Path, frames, ch, rate):
    with contextlib.closing(wave.open(str(path), "wb")) as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames.tobytes())


def _db(x: float) -> float:
    return 20 * math.log10(x) if x > 0 else -99.0


# --------------------------------------------------------------------------
def build(check_only: bool = False) -> int:
    if not SRC_DIR.is_dir():
        raise SystemExit(f"no source folder: {SRC_DIR}")

    staged, groups = [], {}
    for cue in CUES:
        src = SRC_DIR / cue.src
        if not src.exists():
            raise SystemExit(f"missing source: {src}")
        flat, ch, rate = _read(src)
        peak = _peak(flat)
        first, last = _bounds(flat, ch, rate, peak, cue.attack_rel)
        if cue.end_s is not None:
            last = min(last, int(rate * cue.end_s))
        cut = flat[first * ch:(last + 1) * ch]
        cut = _resample(cut, ch, rate, RATE)
        cut = _fade_out(cut, ch, RATE, cue.fade_out_s)
        cut_peak = _peak(cut)
        groups[cue.group] = max(groups.get(cue.group, 0.0), cut_peak)
        staged.append((cue, src, cut, ch, rate, len(flat) // ch, peak, cut_peak))

    for cue, src, cut, ch, src_rate, src_frames, src_peak, cut_peak in staged:
        gain = TARGET_PEAK / groups[cue.group] if groups[cue.group] else 1.0
        out_frames = _scaled(cut, gain)
        n = len(out_frames) // ch
        print("%-56s -> %s" % (src.name, cue.out))
        print("    %.2fs @ %d Hz  ->  %.2fs @ %d Hz   (%.0f%% shorter)"
              % (src_frames / src_rate, src_rate, n / RATE, RATE,
                 100 * (1 - (n / RATE) / (src_frames / src_rate))))
        print("    peak %.1f dBFS -> %.1f dBFS   (group %r, gain x%.2f)"
              % (_db(src_peak), _db(_peak(out_frames)), cue.group, gain))
        if not check_only:
            _write(OUT_DIR / cue.out, out_frames, ch, RATE)
            print("    wrote %s  (%.0f KB, was %.0f KB)"
                  % (cue.out, (OUT_DIR / cue.out).stat().st_size / 1024,
                     src.stat().st_size / 1024))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="report what would be written, write nothing")
    args = ap.parse_args(argv)
    return build(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
