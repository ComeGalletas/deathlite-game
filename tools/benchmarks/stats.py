"""Small statistics the benchmark tools share: one definition each, and no
side effects on import (the stress harness sets SDL drivers when imported;
the trace report must not inherit that just to read a percentile)."""
from __future__ import annotations


def percentile(sorted_vals: list, q: float) -> float:
    """The value at index `round(q * (n - 1))` of already sorted values
    (Python's round, half to even), 0.0 for none. A nearest-index rule, not
    nearest-rank: the p50 of [1, 2, 3, 4] is 3."""
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, round(q * (len(sorted_vals) - 1)))
    return sorted_vals[i]
