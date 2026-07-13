"""Render a compact error-activity sparkline — pure, no Qt, so it's testable."""

from __future__ import annotations

from collections.abc import Iterable

_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[int], blocks: str = _BLOCKS) -> str:
    """Map values to block characters scaled to the max.

    Empty input returns ""; an all-zero input returns a flat baseline of the
    lowest block so the widget still shows a line.
    """
    if not values:
        return ""
    hi = max(values)
    if hi <= 0:
        return blocks[0] * len(values)
    top = len(blocks) - 1
    return "".join(blocks[round(v / hi * top)] for v in values)


def error_rate_sparkline(ranks: Iterable[int], error_rank: int, buckets: int = 20) -> str:
    """Sparkline of error-or-above counts across `buckets` slots of `ranks`."""
    ranks = list(ranks)
    n = len(ranks)
    if n == 0:
        return ""
    counts = [0] * buckets
    for i, rank in enumerate(ranks):
        if rank >= error_rank:
            counts[i * buckets // n] += 1
    return sparkline(counts)
