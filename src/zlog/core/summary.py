"""Format the status-bar level-count summary — pure, no Qt, so it's testable."""

from __future__ import annotations

# Severity-first, so Fatal/Error stand out at the front.
_ORDER = ("F", "E", "W", "I", "D", "V")


def format_level_summary(total: int, counts: dict[str, int], visible: int | None = None) -> str:
    """Render e.g. ``"1,204 lines  F:2 E:12 W:30 I:900"``; zero counts omitted.

    When ``visible`` is given and less than ``total`` (a filter is hiding rows),
    the prefix becomes ``"Showing X of Y lines"`` so it's clear the view is filtered.
    """
    if visible is not None and visible < total:
        line = f"Showing {visible:,} of {total:,} lines"
    else:
        line = f"{total:,} lines"
    parts = [f"{level}:{counts[level]}" for level in _ORDER if counts.get(level)]
    if parts:
        line += "  " + " ".join(parts)
    return line


def tag_counts(entries) -> list[tuple[str, int]]:
    """Count entries per (non-empty) tag, sorted by count desc then tag asc.

    Pure — takes any iterable of objects with a `.tag`, so it's testable without Qt.
    Empty-tag lines (banners/unparsed) are ignored.
    """
    from collections import Counter

    counts: Counter = Counter()
    for entry in entries:
        if entry.tag:
            counts[entry.tag] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
