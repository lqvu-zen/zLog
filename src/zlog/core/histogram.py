"""Reduce a capture to a small set of time buckets for the timeline band — pure,
no Qt, so it's unit-testable (like `core/heat.py` and `core/sparkline.py`).

Each bucket carries the number of rows in its time slot, how many of those are
warnings-or-worse (for an error tint), and the first source-row index in the slot
(so a click can seek the log there).
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

_ERROR_LEVELS = frozenset({"W", "E", "F"})


class Bucket(NamedTuple):
    count: int  # rows in this time slot
    error_count: int  # rows at level W/E/F
    first_index: int  # first source-row index in the slot (-1 if empty)


def bucketize(times: list[datetime | None], levels: list[str], buckets: int) -> list[Bucket]:
    """Bin rows into `buckets` equal time slots spanning min→max parseable time.

    `times[i]`/`levels[i]` describe source row `i`. Rows with an unparseable time
    (`None`) fold into the previous row's slot. If fewer than two distinct times
    are parseable (nothing to span), falls back to an even split by row index so
    the band still shows volume. Empty input (or `buckets <= 0`) yields `[]`.
    """
    n = len(times)
    if n == 0 or buckets <= 0:
        return []

    parseable = [t for t in times if t is not None]
    lo = min(parseable) if parseable else None
    hi = max(parseable) if parseable else None
    span = (hi - lo).total_seconds() if (lo is not None and hi is not None) else 0.0

    acc = [[0, 0, -1] for _ in range(buckets)]
    slot = 0
    for i in range(n):
        t = times[i]
        if span > 0 and t is not None:
            frac = (t - lo).total_seconds() / span
            slot = min(buckets - 1, max(0, int(frac * buckets)))
        elif span <= 0:
            # Volume-only fallback: even split by index.
            slot = min(buckets - 1, i * buckets // n)
        # else: keep the previous slot (fold an unparseable-time row forward)
        b = acc[slot]
        b[0] += 1
        if levels[i] in _ERROR_LEVELS:
            b[1] += 1
        if b[2] == -1:
            b[2] = i
    return [Bucket(c, e, f) for c, e, f in acc]
