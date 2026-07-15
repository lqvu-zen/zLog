"""Format logcat timestamps as absolute / elapsed / delta — pure, no Qt.

`adb logcat -v threadtime` stamps lines `MM-DD HH:MM:SS.mmm` with no year, so we
parse to a datetime with a fixed (arbitrary but consistent) year. Elapsed/delta
are then just datetime subtraction. A capture that crosses a year boundary would
mis-order — acceptable for a log session and documented here.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

_FMT = "%m-%d %H:%M:%S.%f"
_DATE_PREFIX = re.compile(r"\d{2}-\d{2}")


def parse_logcat_time(s: str) -> datetime | None:
    """Parse a threadtime stamp to a datetime, or None if it doesn't match."""
    if not s:
        return None
    try:
        return datetime.strptime(s, _FMT)
    except ValueError:
        return None


def parse_time_of_day(s: str) -> time | None:
    """Parse a time-of-day like "HH:MM:SS" or "HH:MM:SS.mmm", or None if it
    doesn't match. Tolerates (and discards) a leading "MM-DD " date prefix —
    comparison is time-of-day only, consistent with this module's single-day
    -capture assumption."""
    s = s.strip()
    if not s:
        return None
    head, sep, rest = s.partition(" ")
    if sep and _DATE_PREFIX.fullmatch(head):
        s = rest
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def first_at_or_after(times: list[str], target: time) -> int | None:
    """Index of the first entry (in `times`, raw threadtime stamps) whose
    time-of-day is at or after `target`. None if every entry is before it (or
    unparseable) — the caller then jumps to the last row instead."""
    for i, s in enumerate(times):
        dt = parse_logcat_time(s)
        if dt is not None and dt.time() >= target:
            return i
    return None


def format_delta(td: timedelta) -> str:
    """Format a signed duration compactly: +0.750, +1:23.450, +1:01:01.500."""
    total = td.total_seconds()
    sign = "-" if total < 0 else "+"
    total = abs(total)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    seconds = total - hours * 3600 - minutes * 60
    if hours:
        return f"{sign}{hours}:{minutes:02d}:{seconds:06.3f}"
    if minutes:
        return f"{sign}{minutes}:{seconds:06.3f}"
    return f"{sign}{seconds:.3f}"
