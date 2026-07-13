"""Command-palette matching — pure, no Qt, so it's unit-testable."""

from __future__ import annotations


def _is_subsequence(needle: str, hay: str) -> bool:
    it = iter(hay)
    return all(ch in it for ch in needle)


def match_commands(labels: list[str], query: str) -> list[int]:
    """Indices of `labels` matching `query` (case-insensitive), ranked.

    Substring matches rank first (earlier position wins), then subsequence
    matches; an empty query returns every index in original order.
    """
    q = query.strip().lower()
    if not q:
        return list(range(len(labels)))
    scored: list[tuple[int, int, int]] = []
    for i, label in enumerate(labels):
        low = label.lower()
        if q in low:
            scored.append((0, low.index(q), i))
        elif _is_subsequence(q, low):
            scored.append((1, 0, i))
    scored.sort()
    return [i for _, _, i in scored]
