"""Aggregate Choreographer "Skipped N frames!" jank lines — pure, no Qt.

Mirrors core/summary.py's tag_counts: takes any iterable of entry-like objects
and returns plain tuples, so it's directly unit-testable and drives the same
modal-dialog-with-table pattern as Tag Summary.
"""

from __future__ import annotations

import re
from collections import Counter

_SKIP_RE = re.compile(r"Skipped (\d+) frames!")


def jank_summary(entries) -> list[tuple[str, int, int]]:
    """Per-PID (pid, event_count, total_frames_skipped) from Choreographer
    "Skipped N frames!" lines, sorted by total frames skipped descending (then
    pid ascending). A Choreographer line that doesn't match the skip pattern is
    ignored, as is any non-Choreographer line.
    """
    events: Counter = Counter()
    frames: Counter = Counter()
    for entry in entries:
        if entry.tag != "Choreographer":
            continue
        m = _SKIP_RE.search(entry.message)
        if not m:
            continue
        events[entry.pid] += 1
        frames[entry.pid] += int(m.group(1))
    return sorted(
        ((pid, events[pid], frames[pid]) for pid in events),
        key=lambda row: (-row[2], row[0]),
    )
