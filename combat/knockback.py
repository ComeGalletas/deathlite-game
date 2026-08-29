"""Weight-driven knockback split (CB-3). Pure math -- no pygame, no state.

A **bump** between two overlapping bodies and a **weapon hit** both call
`knock_split(w_src, w_tgt, base)`. It shares one impulse between the two bodies
by the *other* body's weight fraction, and amplifies the whole thing by how
lopsided the matchup is:

    total     = base * (1 + diff_gain * |w_src - w_tgt| / (w_src + w_tgt))
    push_src  = total * w_tgt / (w_src + w_tgt)     # recoil, per the target's mass
    push_tgt  = total * w_src / (w_src + w_tgt)     # shove,  per the source's mass

Callers pick `base`:
  * a bump -> ``config.BUMP_GAIN * penetration_px``
  * a hit  -> ``config.HIT_KNOCK_GAIN * weapon_weight``  (weight 0 -> base 0 -> nothing)

`inf` weights (the boss) are handled by explicit branches, never IEEE
``inf / inf`` arithmetic.
"""
from __future__ import annotations

import math

from game import config


def knock_split(w_src: float, w_tgt: float, base: float,
                *, diff_gain: float | None = None) -> tuple[float, float]:
    """Return ``(push_src, push_tgt)`` -- the impulse magnitudes for the source
    and the target of a bump / hit. Both are >= 0; ``push_src + push_tgt`` sums
    to the amplified ``total`` in the ordinary (finite, positive) case."""
    if diff_gain is None:
        diff_gain = config.BUMP_DIFF_GAIN

    if base <= 0.0 or w_src <= 0.0:
        return (0.0, 0.0)                       # no impulse / weightless source

    src_inf = math.isinf(w_src)
    tgt_inf = math.isinf(w_tgt)
    if src_inf and tgt_inf:
        return (0.0, 0.0)                       # two immovable bodies
    amplified = base * (1.0 + diff_gain)        # an infinite gap -> ratio == 1
    if tgt_inf:
        return (amplified, 0.0)                 # target immovable: all recoil
    if src_inf:
        return (0.0, amplified)                 # source immovable: all shove

    total_w = w_src + w_tgt
    if total_w <= 0.0:
        return (0.0, 0.0)
    diff_ratio = abs(w_src - w_tgt) / total_w
    total = base * (1.0 + diff_gain * diff_ratio)
    return (total * w_tgt / total_w, total * w_src / total_w)
