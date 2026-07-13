"""Scrollbar heat-mark bucketing — pure, no Qt, so it's unit-testable.

Given the severity rank of each visible row, return the fractional positions
(0..1) of the buckets that contain an error-or-above line. Bucketing caps the
number of marks so a million-row log still paints a handful of ticks.
"""

from __future__ import annotations

from collections.abc import Iterable


def heat_marks(ranks: Iterable[int], n: int, error_rank: int, buckets: int = 200) -> list[float]:
    """Fractions (0..1) of the buckets holding an error-or-above row.

    `ranks` is any iterable of per-row severity ranks (a generator is fine, so the
    caller need not materialize them); `n` is the total row count.
    """
    if n <= 0 or buckets <= 0:
        return []
    hit: set[int] = set()
    for i, rank in enumerate(ranks):
        if rank >= error_rank:
            hit.add(i * buckets // n)
    return sorted(b / buckets for b in hit)
